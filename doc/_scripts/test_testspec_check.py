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


def test_misattached(tree, tmp_path, capsys):
    """test_plain's id names a case of another function: Doxygen gave its doc
    comment to a macro call before it, and test_plain itself is not in the spec."""
    cases = [("TSPEC-FOO-001", "K_APP_DMEM")] + CASES[1:]
    rc, out = check(tree, tmp_path, cases, capsys)
    assert rc == 1
    assert (
        "error: MISATTACHED  tests/kernel/foo/src/main.c:10  foo.test_plain  id=TSPEC-FOO-001"
        "  (the spec's case is named 'K_APP_DMEM')"
    ) in out


def test_strays(tree, tmp_path, capsys):
    """Spec cases no ZTEST accounts for: a helper Doxygen put into a suite
    group, and a test on the page of a module it is not in."""
    scope, zephyr = tree
    f = needs(tmp_path, CASES + [("testspec-foo-foo_setup", "foo_setup")])
    data = json.loads(f.read_text())
    cases = data["versions"][""]["needs"]
    for n in cases.values():
        n["test_module"] = "tests/kernel/foo"
    cases["TSPEC-FOO-002"]["test_module"] = "tests/kernel/bar"
    f.write_text(json.dumps(data))
    rc = testspec_check.main(["--scope", str(scope), "--zephyr-base", str(zephyr), "--needs", str(f)])
    out = capsys.readouterr().out
    assert rc == 0  # warnings only
    assert "2 spec cases not a ZTEST of their module" in out
    assert "warning: NOT A TEST  testspec-foo-foo_setup  foo.foo_setup  test_module=tests/kernel/foo" in out
    assert (
        "warning: WRONG MODULE (the ZTEST is in tests/kernel/foo/src/main.c)  TSPEC-FOO-002"
        "  foo.test_user  test_module=tests/kernel/bar"
    ) in out


def test_cross_module_pair_in_the_sources(tree, tmp_path, capsys):
    """A second module with a test of the same (suite, function): a result
    of either is ambiguous, whatever groups the tests are in."""
    scope, zephyr = tree
    bar = zephyr / "tests/kernel/foo/bar"
    (bar / "src").mkdir(parents=True)
    (bar / "tests.yaml").write_text("tests:\n  kernel.foo.bar:\n    tags: kernel\n")
    (bar / "src/main.c").write_text("/**\n * @brief Same pair.\n */\nZTEST(foo, test_plain)\n{\n}\n")
    rc, out = check(tree, tmp_path, CASES, capsys)
    assert rc == 1
    assert "1 CROSS-MODULE (suite, function) pairs" in out
    assert "error: CROSS-MODULE  foo.test_plain  in tests/kernel/foo, tests/kernel/foo/bar" in out


def test_cross_module_pair_in_the_spec(tree, tmp_path, capsys):
    """Two test cases of one pair on two module pages: one suite group
    shared by both modules."""
    scope, zephyr = tree
    f = needs(tmp_path, CASES + [("testspec-foo-test_plain", "test_plain")])
    data = json.loads(f.read_text())
    cases = data["versions"][""]["needs"]
    for n in cases.values():
        n["test_module"] = "tests/kernel/foo"
    cases["testspec-foo-test_plain"]["test_module"] = "tests/kernel/bar"
    f.write_text(json.dumps(data))
    rc = testspec_check.main(["--scope", str(scope), "--zephyr-base", str(zephyr), "--needs", str(f)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "error: CROSS-MODULE  foo.test_plain  in tests/kernel/bar, tests/kernel/foo" in out
