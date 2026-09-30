# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for doxygen_filter_kconfig.py: python -m pytest doc/_scripts -q"""

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from doxygen_filter_kconfig import condition_text, evaluate, filter_text  # noqa: E402

SCRIPT = Path(__file__).resolve().parent / "doxygen_filter_kconfig.py"


def src(text):
    return textwrap.dedent(text).lstrip("\n")


def run(text, header=False):
    out = filter_text(text, is_header=header)
    assert len(out.splitlines()) == len(text.splitlines())
    assert out.count("#define") == text.count("#define")
    return out.splitlines()


@pytest.mark.parametrize(
    "expr, value",
    [
        ("defined(CONFIG_A)", True),
        ("defined CONFIG_A", True),
        ("!defined(CONFIG_A)", False),
        ("defined(CONFIG_A) && !defined(CONFIG_B)", False),
        ("defined(CONFIG_A) || !defined(CONFIG_B)", True),
        ("!(defined(CONFIG_A) && defined(CONFIG_B))", False),
        ("(defined(CONFIG_A) && defined(CONFIG_B)) || defined(__DOXYGEN__)", True),
        ("defined(CONFIG_A) /* comment */", True),
        ("defined(CONFIG_A) && \\\n\t!defined(CONFIG_B)", False),
        # Left to Doxygen.
        ("(CONFIG_MP_MAX_NUM_CPUS == 1) || defined(__DOXYGEN__)", None),
        ("CONFIG_A", None),
        ("defined(HAS_POWERSAVE_INSTRUCTION)", None),
        ("defined(CONFIG_A) && defined(_ASMLANGUAGE)", None),
        ("0", None),
        ("defined(CONFIG_A) &&", None),
    ],
)
def test_evaluate(expr, value):
    assert evaluate(expr) is value


def test_condition_text_drops_doxygen_term():
    assert condition_text("defined(CONFIG_A)  ||   defined(__DOXYGEN__)") == "defined(CONFIG_A)"
    assert condition_text("defined(__DOXYGEN__)") is None
    assert condition_text("defined(CONFIG_A) &&\\\n  defined(CONFIG_B)") == (
        "defined(CONFIG_A) && defined(CONFIG_B)"
    )


def test_line_count_preserved_on_real_sources():
    zephyr = Path(__file__).resolve().parents[3] / "zephyr"
    files = [
        zephyr / "include/zephyr/kernel.h",
        zephyr / "tests/kernel/fatal/exception/src/main.c",
        zephyr / "tests/kernel/condvar/condvar_api/src/main.c",
    ]
    files = [f for f in files if f.is_file()]
    if not files:
        pytest.skip("no zephyr tree next to safety")
    for f in files:
        text = f.read_text()
        out = filter_text(text, is_header=f.suffix == ".h")
        assert out.count("\n") == text.count("\n"), f
        assert "#define CONFIG_" not in out


def test_directive_forms():
    lines = run(src("""
        #ifdef CONFIG_A
        #endif
        #ifndef CONFIG_B
        #else
        #endif
        #if defined(CONFIG_C) && !defined(CONFIG_D)
        #elif defined(CONFIG_E)
        #else
        #endif
        #if defined(CONFIG_F) && \\
            defined(CONFIG_G)
        #endif /* CONFIG_F && CONFIG_G */
        """))
    assert lines == [
        "#if 1", "#endif",
        "#if 0", "#else", "#endif",
        "#if 0", "#elif 1", "#else", "#endif",
        "#if 1", "", "#endif /* CONFIG_F && CONFIG_G */",
    ]


def test_non_config_conditions_untouched():
    text = src("""
        #ifndef ZEPHYR_INCLUDE_FOO_H_
        #define ZEPHYR_INCLUDE_FOO_H_
        #if (CONFIG_MP_MAX_NUM_CPUS == 1) || defined(__DOXYGEN__)
        /** Doc. */
        void a(void);
        #endif
        #ifdef HAS_POWERSAVE_INSTRUCTION
        /** Doc. */
        void b(void);
        #elif defined(CONFIG_X)
        /** Doc. */
        void c(void);
        #endif
        #endif
        """)
    lines = run(text, header=True)
    expected = text.splitlines()
    expected[9] = "#elif 1"
    expected[10] = "/** Doc. @kconfig_depends{defined(CONFIG_X)} */"
    assert lines == expected


def test_nested_conditions_annotate_twice():
    lines = run(src("""
        #ifdef CONFIG_A
        #if defined(CONFIG_B) || defined(__DOXYGEN__)
        /**
         * @brief Test.
         */
        ZTEST(suite, test_x)
        {
        }
        #endif
        #endif
        """))
    assert lines[4] == " * @kconfig_depends{CONFIG_A} @kconfig_depends{defined(CONFIG_B)} */"


def test_else_stub_dropped():
    lines = run(src("""
        #ifdef CONFIG_USERSPACE
        /**
         * @brief Real test.
         */
        ZTEST_USER(suite, test_x)
        {
        	do_it();
        }
        #else
        ZTEST_USER(suite, test_x)
        {
        	ztest_test_skip();
        }
        #endif
        """))
    assert lines[0] == "#if 1"
    assert lines[3] == " * @kconfig_depends{CONFIG_USERSPACE} */"
    assert lines[8] == "#else"
    assert lines[13] == "#endif"


def test_documented_skip_stub_is_still_a_stub():
    # common/src/main.c: the printk test's feature-off twin carries a doc
    # comment but only skips; the real test lives in another file.
    lines = run(src("""
        #ifndef CONFIG_PRINTK
        /**
         * @brief Skipped stub.
         */
        ZTEST(printk, test_printk)
        {
        	/* nothing to do */
        	ztest_test_skip();
        }
        #endif
        """))
    assert lines[0] == "#if 0"
    assert lines[3] == " */"
    assert lines[9] == "#endif"


def test_documented_twin_kept():
    lines = run(src("""
        #if defined(CONFIG_A)
        /** @brief Feature on. */
        ZTEST(suite, test_on)
        {
        	on();
        }
        #else
        /** @brief Feature off. */
        ZTEST(suite, test_off)
        {
        	off();
        }
        #endif
        """))
    assert lines[0] == lines[6] == lines[12] == ""
    assert lines[1] == "/** @brief Feature on. @kconfig_depends{defined(CONFIG_A)} */"
    assert lines[7] == "/** @brief Feature off. @kconfig_depends{!defined(CONFIG_A)} */"


def test_ifndef_twin_opens_up():
    lines = run(src("""
        #ifndef CONFIG_ARCH_POSIX
        /**
         * @brief Test.
         */
        ZTEST(suite, test_x)
        {
        	x();
        }
        #endif /* !CONFIG_ARCH_POSIX */
        """))
    assert lines[0] == lines[8] == ""
    assert lines[3] == " * @kconfig_depends{!CONFIG_ARCH_POSIX} */"


def test_else_after_elif_negates_every_branch():
    lines = run(src("""
        #if defined(CONFIG_A) && defined(CONFIG_B)
        /** @brief A. */
        ZTEST(s, a)
        {
        	a();
        }
        #elif defined(CONFIG_C)
        /** @brief C. */
        ZTEST(s, c)
        {
        	c();
        }
        #else
        /** @brief Other. */
        ZTEST(s, other)
        {
        	other();
        }
        #endif
        """))
    assert lines[7] == "/** @brief C. @kconfig_depends{defined(CONFIG_C)} */"
    assert lines[13] == (
        "/** @brief Other. @kconfig_depends{!(defined(CONFIG_A) && defined(CONFIG_B))"
        " && !defined(CONFIG_C)} */"
    )


def test_header_entities_and_members():
    lines = run(src("""
        /**
         * @defgroup g Group
         * @{
         */
        #ifdef CONFIG_POLL
        /** @brief A struct. */
        struct s {
        	int a; /**< Member a. */
        	int b;
        };

        /**
         * @brief A macro.
         */
        #define M(x) (x)
        /** @} */
        #endif
        """), header=True)
    assert lines[3] == " */"
    assert lines[5] == "/** @brief A struct. @kconfig_depends{CONFIG_POLL} */"
    assert lines[7] == "\tint a; /**< Member a. @kconfig_depends{CONFIG_POLL} */"
    assert lines[13] == " * @kconfig_depends{CONFIG_POLL} */"
    assert lines[15] == "/** @} */"


def test_c_file_annotates_only_ztests():
    lines = run(src("""
        #ifdef CONFIG_A
        /** @brief Helper. */
        static void helper(void) {}
        #endif
        """))
    assert lines[1] == "/** @brief Helper. */"


def test_directives_in_comments_ignored():
    text = src("""
        /*
        #ifdef CONFIG_A
        #endif
        */
        """)
    assert run(text) == text.splitlines()


def test_comma_escaped():
    lines = run(src("""
        #if defined(CONFIG_A) && \\
            defined(CONFIG_B)
        /** @brief X. */
        void f(void);
        #endif
        """), header=True)
    assert lines[2] == "/** @brief X. @kconfig_depends{defined(CONFIG_A) && defined(CONFIG_B)} */"
    from doxygen_filter_kconfig import escape_arg

    assert escape_arg("FOO(a, b)") == "FOO(a\\, b)"


def test_command_line(tmp_path):
    f = tmp_path / "q.c"
    f.write_text("#ifdef CONFIG_A\nint z_impl_k_foo;\n#endif\n")
    out = subprocess.run(
        [sys.executable, SCRIPT, "--rename-impl", f], check=True, capture_output=True, text=True
    ).stdout
    assert out == "#if 1\nint k_foo;\n#endif\n"


def test_doc_comment_before_the_conditional_is_attached():
    # log_core_additional's test_log_thread, smp's test_smp_ipi: the doc
    # comment stands before the #ifdef that guards the test; Doxygen still
    # attaches it, and the test depends on the condition.
    lines = run(src("""
        /**
         * @brief Real test.
         */

        #ifdef CONFIG_LOG_PROCESS_THREAD
        ZTEST(suite, test_x)
        {
        	do_it();
        }
        #else
        ZTEST(suite, test_x)
        {
        	ztest_test_skip();
        }
        #endif
        """))
    assert lines[2] == " * @kconfig_depends{CONFIG_LOG_PROCESS_THREAD} */"
    assert lines[4] == "#if 1"


def test_plain_comment_between_doc_and_ztest():
    # mutex_error_case: `/* TESTPOINT: ... */` between the doc comment and
    # the ZTEST; Doxygen skips a plain comment.
    text = src("""
        /**
         * @brief Documented.
         */
        /* TESTPOINT: plain */
        ZTEST_USER(suite, test_x)
        {
        }
        """)
    from doxygen_filter_kconfig import documented_ztests, lex

    lines = text.splitlines(keepends=True)
    comments, _ = lex(lines)
    found, _ = documented_ztests(lines, comments)
    assert list(found) == [4]


def test_define_takes_the_doc_comment():
    # mem_domain.c's test_mem_domain_migration: a #define between the doc
    # comment and the ZTEST is what Doxygen documents instead.
    text = src("""
        /**
         * @brief Documents PRIO, as Doxygen sees it.
         */
        #if CONFIG_MP_MAX_NUM_CPUS > 1
        #define PRIO 0
        #endif

        ZTEST(suite, test_x)
        {
        }
        """)
    from doxygen_filter_kconfig import documented_ztests, lex

    lines = text.splitlines(keepends=True)
    assert documented_ztests(lines, lex(lines)[0])[0] == {}


def test_ztest_user_or_not_is_a_ztest():
    # sys_mutex's local alias.
    lines = run(src("""
        #ifdef CONFIG_USERSPACE
        /** @brief Documented. */
        ZTEST_USER_OR_NOT(suite, test_x)
        {
        }
        #endif
        """))
    assert lines[1] == "/** @brief Documented. @kconfig_depends{CONFIG_USERSPACE} */"


def test_suite_gets_the_module_group():
    text = src("""
        /** @brief A. */
        ZTEST(workqueue_api, test_a)
        {
        }

        ZTEST_USER(other, test_b)
        {
        }

        ZTEST_SUITE(workqueue_api, NULL, NULL, NULL, NULL, NULL);
        """)
    out = filter_text(text, is_header=False, suite_groups={"workqueue_api": "m__workqueue_api"})
    lines = out.splitlines()
    assert len(lines) == len(text.splitlines())
    assert lines[1] == "ZTEST(m__workqueue_api, test_a)"
    assert lines[5] == "ZTEST_USER(other, test_b)"
    assert lines[9] == "ZTEST_SUITE(workqueue_api, NULL, NULL, NULL, NULL, NULL);"


def test_command_line_suites(tmp_path):
    mod = tmp_path / "tests/kernel/workq/user_work"
    (mod / "src").mkdir(parents=True)
    f = mod / "src/main.c"
    f.write_text("ZTEST_USER(workqueue_api, test_a)\n{\n}\n")
    other = tmp_path / "tests/kernel/other.c"
    other.write_text("ZTEST(workqueue_api, test_a)\n")
    suites = tmp_path / "suites.json"
    suites.write_text('{"%s": {"workqueue_api": "u__workqueue_api"}}' % mod)

    def filt(path):
        return subprocess.run(
            [sys.executable, SCRIPT, "--suites", suites, path], check=True, capture_output=True, text=True
        ).stdout

    assert filt(f).splitlines()[0] == "ZTEST_USER(u__workqueue_api, test_a)"
    assert filt(other) == "ZTEST(workqueue_api, test_a)\n"


# --------------------------------------------------------------------------
# In-body skips


def test_in_body_is_enabled_skip():
    # log_api/src/main.c:296
    lines = run(src("""
        /**
         * @brief Runtime filtering.
         */
        ZTEST(test_log_api, test_log_backend_runtime_filtering)
        {
        	if (!IS_ENABLED(CONFIG_LOG_RUNTIME_FILTERING)) {
        		ztest_test_skip();
        	}
        	check();
        }
        """))
    assert lines[2] == " * @kconfig_depends{CONFIG_LOG_RUNTIME_FILTERING} */"


def test_in_body_skips_accumulate_after_enclosing():
    lines = run(src("""
        #ifdef CONFIG_A
        /** @brief Test. */
        ZTEST(s, t)
        {
        	if (IS_ENABLED(CONFIG_LOG_MODE_IMMEDIATE)) {
        		ztest_test_skip();
        	}

        	if (!IS_ENABLED(CONFIG_LOG_MODE_OVERFLOW)) {
        		ztest_test_skip();
        	}
        	if (!IS_ENABLED(CONFIG_A)) {
        		ztest_test_skip();
        	}
        }
        #endif
        """))
    assert lines[1] == (
        "/** @brief Test. @kconfig_depends{CONFIG_A} @kconfig_depends{!CONFIG_LOG_MODE_IMMEDIATE}"
        " @kconfig_depends{CONFIG_LOG_MODE_OVERFLOW} */"
    )


@pytest.mark.parametrize(
    "cond, depends",
    [
        ("IS_ENABLED(CONFIG_X86) || IS_ENABLED(CONFIG_SPARC)", ["!CONFIG_X86", "!CONFIG_SPARC"]),
        ("IS_ENABLED(CONFIG_A) && !IS_ENABLED(CONFIG_B)", ["!CONFIG_A || CONFIG_B"]),
        ("!(IS_ENABLED(CONFIG_A))", ["CONFIG_A"]),
        ("!(IS_ENABLED(CONFIG_A) && (IS_ENABLED(CONFIG_B) || IS_ENABLED(CONFIG_C)))",
         ["CONFIG_A", "CONFIG_B || CONFIG_C"]),
        # A pure-Kconfig disjunct of the skip condition is still a dependency.
        ("arch_num_cpus() > 1 || !IS_ENABLED(CONFIG_IRQ_OFFLOAD_NESTED)", ["CONFIG_IRQ_OFFLOAD_NESTED"]),
        ("!IS_ENABLED(CONFIG_SMP) || (CONFIG_MP_MAX_NUM_CPUS == 1)", ["CONFIG_SMP"]),
        # Run-time conditions: nothing.
        ("IS_ENABLED(CONFIG_USERSPACE) && !tls_domain_ready", []),
        ("!k_is_user_context()", []),
        ("CONFIG_MP_MAX_NUM_CPUS > 1", []),
        ("IS_ENABLED(CONFIG_A) == 1", []),
    ],
)
def test_in_body_compound_conditions(cond, depends):
    lines = run(src(f"""
        /** @brief T. */
        ZTEST(s, t)
        {{
        	if ({cond}) {{
        		ztest_test_skip();
        		return;
        	}}
        }}
        """))
    cmds = "".join(f" @kconfig_depends{{{d}}}" for d in depends)
    assert lines[0] == f"/** @brief T.{cmds} */"


def test_in_body_preprocessor_skips():
    # mutex_api/src/priority_inheritance_enhanced.c:268 (with a Kconfig
    # condition), timer_error_case (#ifndef with no #else), bitfield.c (#ifdef).
    lines = run(src("""
        /** @brief A. */
        ZTEST(s, a)
        {
        #if defined(CONFIG_A) && defined(CONFIG_B)
        	run();
        #else
        	ztest_test_skip();
        #endif
        }
        /** @brief B. */
        ZTEST(s, b)
        {
        #ifndef CONFIG_USERSPACE
        	ztest_test_skip();
        #endif
        	run();
        }
        /** @brief C. */
        ZTEST(s, c)
        {
        #ifdef CONFIG_ARM
        	ztest_test_skip();
        #else
        	run();
        #endif
        }
        /** @brief D. */
        ZTEST(s, d)
        {
        #if defined(CONFIG_A)
        	a();
        #elif defined(CONFIG_B)
        	b();
        #else
        	ztest_test_skip();
        #endif
        }
        """))
    assert lines[0] == "/** @brief A. @kconfig_depends{CONFIG_A} @kconfig_depends{CONFIG_B} */"
    assert lines[3] == "#if 1"
    assert lines[9] == "/** @brief B. @kconfig_depends{CONFIG_USERSPACE} */"
    assert lines[12] == "#if 0"
    assert lines[17] == "/** @brief C. @kconfig_depends{!CONFIG_ARM} */"
    assert lines[26] == "/** @brief D. @kconfig_depends{CONFIG_A || CONFIG_B} */"


def test_in_body_non_kconfig_directive_is_not_a_dependency():
    lines = run(src("""
        /** @brief A. */
        ZTEST(s, a)
        {
        #if Z_MUTEX_PI_ENABLED
        	run();
        #else
        	ztest_test_skip();
        #endif
        }
        /** @brief B. */
        ZTEST(s, b)
        {
        #if defined(CONFIG_MUTEX_DEADLOCK_DETECT) && Z_MUTEX_PI_ENABLED
        	run();
        #else
        	ztest_test_skip();
        #endif
        }
        """))
    assert lines[0] == "/** @brief A. */"
    assert lines[3] == "#if Z_MUTEX_PI_ENABLED"
    # The Kconfig half of a && is still necessary.
    assert lines[9] == "/** @brief B. @kconfig_depends{CONFIG_MUTEX_DEADLOCK_DETECT} */"


def test_in_body_nested_skip_simplified_by_the_else_skip():
    # schedule_api/src/test_slice_scheduling.c: test_slice_perthread.
    lines = run(src("""
        /** @brief T. */
        ZTEST(s, t)
        {
        #ifdef CONFIG_TIMESLICING
        	if (!IS_ENABLED(CONFIG_TIMESLICE_PER_THREAD)) {
        		ztest_test_skip();
        		return;
        	}
        	run();
        #else
        	ztest_test_skip();
        #endif
        }
        """))
    assert lines[0] == (
        "/** @brief T. @kconfig_depends{CONFIG_TIMESLICE_PER_THREAD} @kconfig_depends{CONFIG_TIMESLICING} */"
    )


def test_in_body_else_branches():
    # log_core_additional/src/log_test.c: test_log_sync.
    lines = run(src("""
        /** @brief A. */
        ZTEST(s, a)
        {
        	if (IS_ENABLED(CONFIG_LOG_MODE_IMMEDIATE)) {
        		run();
        	} else {
        		ztest_test_skip();
        	}
        }
        /** @brief B. */
        ZTEST(s, b)
        {
        	if (IS_ENABLED(CONFIG_A)) {
        		a();
        	} else if (!IS_ENABLED(CONFIG_B)) {
        		ztest_test_skip();
        	}
        }
        /** @brief C. */
        ZTEST(s, c)
        {
        	if (IS_ENABLED(CONFIG_A))
        		ztest_test_skip();
        	else
        		run();
        }
        """))
    assert lines[0] == "/** @brief A. @kconfig_depends{CONFIG_LOG_MODE_IMMEDIATE} */"
    assert lines[9] == "/** @brief B. @kconfig_depends{CONFIG_A || CONFIG_B} */"
    assert lines[18] == "/** @brief C. @kconfig_depends{!CONFIG_A} */"


def test_in_body_skips_left_alone():
    # Under a loop or a switch, unconditional, after a run-time check, in a
    # string or a comment, or in a helper: no dependency.
    text = src("""
        static void helper(void)
        {
        	if (!IS_ENABLED(CONFIG_H)) {
        		ztest_test_skip();
        	}
        }
        /** @brief T. */
        ZTEST(s, t)
        {
        	for (int i = 0; i < 2; i++) {
        		if (!IS_ENABLED(CONFIG_A)) {
        			ztest_test_skip();
        		}
        	}
        	switch (k) {
        	case 1:
        		if (!IS_ENABLED(CONFIG_B)) {
        			ztest_test_skip();
        		}
        		break;
        	}
        	if (stack == NULL) {
        		ztest_test_skip();
        	}
        	/* if (!IS_ENABLED(CONFIG_C)) { ztest_test_skip(); } */
        	printk("if (!IS_ENABLED(CONFIG_D)) { ztest_test_skip(); }");
        	helper();
        	ztest_test_skip();
        }
        """)
    assert run(text) == text.splitlines()


def test_in_body_skip_stub_rule_unchanged():
    # A whole-body stub is still no test case and gets nothing; its
    # feature-on twin gets the enclosing condition only.
    lines = run(src("""
        #ifdef CONFIG_USERSPACE
        /** @brief Real. */
        ZTEST(s, t)
        {
        	run();
        }
        #else
        /** @brief Stub. */
        ZTEST(s, t)
        {
        	ztest_test_skip();
        }
        #endif
        """))
    assert lines[1] == "/** @brief Real. @kconfig_depends{CONFIG_USERSPACE} */"
    assert lines[7] == "/** @brief Stub. */"


def test_list_skips(tmp_path):
    f = tmp_path / "t.c"
    f.write_text(src("""
        /** @brief T. */
        ZTEST(s, t)
        {
        	if (!IS_ENABLED(CONFIG_A)) {
        		ztest_test_skip();
        	}
        	if (arch_num_cpus() > 1) {
        		ztest_test_skip();
        	}
        }
        ZTEST(s, u)
        {
        	ztest_test_skip();
        }
        """))
    out = subprocess.run(
        [sys.executable, SCRIPT, "--list-skips", f], check=True, capture_output=True, text=True
    ).stdout.splitlines()
    assert out == [
        f"{f}:5\ts.t\tkconfig\tCONFIG_A\t",
        f"{f}:8\ts.t\truntime\t\t!(arch_num_cpus() > 1)",
        f"{f}:13\ts.u\tstub\t\tskip stub (the whole body)",
    ]
