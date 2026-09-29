# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for assign_testids.py: python -m pytest doc/_scripts -q"""

import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import assign_testids  # noqa: E402
from assign_testids import STUB, plan  # noqa: E402
from testspec_scope import load_scope  # noqa: E402

SOURCE = """
/**
 * @brief Has an id.
 *
 * @testid{TSPEC-FOO-001}
 * @draft
 */
ZTEST(foo, test_done)
{
	run();
}

/**
 * @brief Needs an id.
 */
ZTEST(foo, test_new)
{
	run();
}

ZTEST(foo, test_undocumented)
{
	run();
}

#ifndef CONFIG_PRINTK
/**
 * @brief Documented stub of a test that lives elsewhere.
 */
ZTEST(foo, test_printk)
{
	/* printk is off */
	ztest_test_skip();
}
#endif

/**
 * @brief Skips at run time, but is a real test.
 */
ZTEST(foo, test_conditional_skip)
{
	if (!IS_ENABLED(CONFIG_FOO)) {
		ztest_test_skip();
	}
	run();
}

ZTEST_SUITE(foo, NULL, NULL, NULL, NULL, NULL);
"""


def test_skip_stub_gets_no_id(tmp_path):
    zephyr = tmp_path / "zephyr"
    mod = zephyr / "tests/kernel/foo"
    (mod / "src").mkdir(parents=True)
    (mod / "tests.yaml").write_text("tests:\n  kernel.foo:\n    tags: kernel\n")
    (mod / "src/main.c").write_text(textwrap.dedent(SOURCE))
    scope = tmp_path / "test-scope.yaml"
    scope.write_text("areas:\n  - path: tests/kernel/foo\n    code: FOO\n    title: Foo\n")

    ledger = {}
    got = [(fn, tid) for _, _, fn, tid in plan(load_scope(scope, zephyr), ledger, zephyr)]
    assert got == [
        ("test_new", "TSPEC-FOO-002"),
        ("test_undocumented", None),
        ("test_printk", STUB),
        ("test_conditional_skip", "TSPEC-FOO-003"),
    ]
    assert ledger == {"FOO": 3}


TWINS = """
#ifdef CONFIG_FOO
/**
 * @brief Feature on.
 */
ZTEST(foo, test_twin)
{
	run();
}
#else
/**
 * @brief Feature off, tested differently.
 */
ZTEST(foo, test_twin)
{
	run_other();
}
#endif
"""


def test_twins_in_one_file_each_get_an_id(tmp_path, monkeypatch):
    zephyr = tmp_path / "zephyr"
    mod = zephyr / "tests/kernel/foo"
    (mod / "src").mkdir(parents=True)
    (mod / "tests.yaml").write_text("tests:\n  kernel.foo:\n    tags: kernel\n")
    src = mod / "src/main.c"
    src.write_text(TWINS)
    scope = tmp_path / "test-scope.yaml"
    scope.write_text("areas:\n  - path: tests/kernel/foo\n    code: FOO\n    title: Foo\n")
    ledger = tmp_path / "testids.yaml"
    argv = ["assign_testids.py", "--scope", str(scope), "--ledger", str(ledger),
            "--zephyr-base", str(zephyr), "--write"]
    monkeypatch.setattr(sys, "argv", argv)
    assign_testids.main()
    text = src.read_text()
    on, off = text.split("#else")
    assert "@testid{TSPEC-FOO-001}" in on and "TSPEC-FOO-002" not in on
    assert "@testid{TSPEC-FOO-002}" in off
    # A second run finds nothing left to assign.
    assign_testids.main()
    assert src.read_text() == text


ATTACHED = """
/**
 * @brief Doc comment before the conditional, as in log_core_additional.
 */

#ifdef CONFIG_FOO
ZTEST(foo, test_guarded)
{
	run();
}
#else
ZTEST(foo, test_guarded)
{
	ztest_test_skip();
}
#endif

/**
 * @brief A plain comment follows, as in mutex_error_case.
 *
 * @see run()
 */
/* TESTPOINT: not a doc comment */
ZTEST_USER(foo, test_testpoint)
{
	run();
}

/**
 * @brief sys_mutex's local alias.
 */
ZTEST_USER_OR_NOT(foo, test_alias)
{
	run();
}

/**
 * @brief Doxygen gives this one to PRIO, as in mem_domain.c.
 */
#if CONFIG_MP_MAX_NUM_CPUS > 1
#define PRIO 0
#endif

ZTEST(foo, test_after_define)
{
	run();
}
"""


def test_ids_follow_doxygens_attachment(tmp_path, monkeypatch):
    """A doc comment Doxygen attaches across a conditional directive or a
    plain comment gets the id; one a #define takes does not."""
    zephyr = tmp_path / "zephyr"
    mod = zephyr / "tests/kernel/foo"
    (mod / "src").mkdir(parents=True)
    (mod / "tests.yaml").write_text("tests:\n  kernel.foo:\n    tags: kernel\n")
    src = mod / "src/main.c"
    src.write_text(ATTACHED)
    scope = tmp_path / "test-scope.yaml"
    scope.write_text("areas:\n  - path: tests/kernel/foo\n    code: FOO\n    title: Foo\n")

    got = [(fn, tid) for _, _, fn, tid in plan(load_scope(scope, zephyr), {}, zephyr)]
    assert got == [
        ("test_guarded", "TSPEC-FOO-001"),
        ("test_guarded", STUB),
        ("test_testpoint", "TSPEC-FOO-002"),
        ("test_alias", "TSPEC-FOO-003"),
        ("test_after_define", None),
    ]

    ledger = tmp_path / "testids.yaml"
    monkeypatch.setattr(sys, "argv", ["assign_testids.py", "--scope", str(scope), "--ledger",
                                      str(ledger), "--zephyr-base", str(zephyr), "--write"])
    assign_testids.main()
    text = src.read_text()
    assert " * @testid{TSPEC-FOO-001}\n * @draft\n */\n\n#ifdef CONFIG_FOO\n" in text
    assert " * @testid{TSPEC-FOO-002}\n * @draft\n * @see run()\n */\n/* TESTPOINT" in text
    assert "@testid{TSPEC-FOO-003}\n * @draft\n */\nZTEST_USER_OR_NOT" in text
    assign_testids.main()
    assert src.read_text() == text
