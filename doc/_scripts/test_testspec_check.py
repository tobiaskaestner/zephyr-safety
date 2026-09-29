# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for testspec_check.py: python -m pytest doc/_scripts -q"""

import json
import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import testspec_check  # noqa: E402

SOURCE = """
#include <zephyr/ztest.h>

/**
 * @brief Plain test.
 *
 * @testid{TSPEC-FOO-001}
 * @draft
 */
ZTEST(foo, test_plain)
{
	run();
}

ZTEST(foo, test_undocumented)
{
	run();
}

#ifdef CONFIG_USERSPACE
/**
 * @brief Feature on.
 *
 * @testid{TSPEC-FOO-002}
 * @draft
 */
ZTEST_USER(foo, test_user)
{
	run();
}
#else
ZTEST_USER(foo, test_user)
{
	ztest_test_skip();
}
#endif

#ifndef CONFIG_PRINTK
/**
 * @brief Skipped stub.
 *
 * @testid{TSPEC-FOO-003}
 * @draft
 */
ZTEST(foo, test_printk)
{
	ztest_test_skip();
}
#endif

ZTEST_SUITE(foo, NULL, NULL, NULL, NULL, NULL);
"""

# The real printk test, in another file of the module.
PRINTK = """
/**
 * @brief Real printk test.
 *
 * @testid{TSPEC-FOO-004}
 * @draft
 */
ZTEST(foo, test_printk)
{
	printk("x");
}
"""

CASES = [
    ("TSPEC-FOO-001", "test_plain"),
    ("testspec-foo-test_undocumented", "test_undocumented"),
    ("TSPEC-FOO-002", "test_user"),
    ("TSPEC-FOO-004", "test_printk"),
]


@pytest.fixture
def tree(tmp_path):
    zephyr = tmp_path / "zephyr"
    mod = zephyr / "tests/kernel/foo"
    (mod / "src").mkdir(parents=True)
    (mod / "tests.yaml").write_text("tests:\n  kernel.foo:\n    tags: kernel\n")
    (mod / "src/main.c").write_text(textwrap.dedent(SOURCE))
    (mod / "src/printk.c").write_text(textwrap.dedent(PRINTK))
    scope = tmp_path / "test-scope.yaml"
    scope.write_text("areas:\n  - path: tests/kernel/foo\n    code: FOO\n    title: Foo\n")
    return scope, zephyr


def needs(tmp_path, cases):
    data = {
        "current_version": "",
        "versions": {
            "": {
                "needs": {
                    cid: {"id": cid, "type": "test_case", "suite": "foo", "test_function": fn}
                    for cid, fn in cases
                }
            }
        },
    }
    f = tmp_path / "needs.json"
    f.write_text(json.dumps(data))
    return f


def check(tree, tmp_path, cases, capsys):
    scope, zephyr = tree
    rc = testspec_check.main(
        ["--scope", str(scope), "--zephyr-base", str(zephyr), "--needs", str(needs(tmp_path, cases))]
    )
    return rc, capsys.readouterr().out


def test_all_in_spec(tree, tmp_path, capsys):
    rc, out = check(tree, tmp_path, CASES, capsys)
    assert rc == 0
    assert "6 ZTEST sites in scope: 4 in the spec, 2 twin not chosen, 0 MISSING" in out
    # The undocumented feature-off stub: info only, with its deciding condition.
    assert "info: TWIN not chosen  tests/kernel/foo/src/main.c:32  foo.test_user" in out
    assert "excluded by #else (line 31) of #ifdef CONFIG_USERSPACE (line 20)" in out
    # A twin that carries an id is a warning.
    assert "warning: TWIN not chosen  tests/kernel/foo/src/main.c:45  foo.test_printk" in out
    assert "id=TSPEC-FOO-003  excluded by #ifndef CONFIG_PRINTK (line 38)" in out


def test_missing(tree, tmp_path, capsys):
    rc, out = check(tree, tmp_path, CASES[1:3], capsys)
    assert rc == 1
    assert "error: MISSING  tests/kernel/foo/src/main.c:10  foo.test_plain  id=TSPEC-FOO-001" in out
    # With no test_printk in the spec, both printk sites are missing.
    assert "error: MISSING  tests/kernel/foo/src/printk.c:8  foo.test_printk  id=TSPEC-FOO-004" in out
    assert "error: MISSING  tests/kernel/foo/src/main.c:45  foo.test_printk  id=TSPEC-FOO-003" in out


def test_missing_undocumented(tree, tmp_path, capsys):
    rc, out = check(tree, tmp_path, [c for c in CASES if c[1] != "test_undocumented"], capsys)
    assert rc == 1
    assert "error: MISSING  tests/kernel/foo/src/main.c:15  foo.test_undocumented  id=-" in out
