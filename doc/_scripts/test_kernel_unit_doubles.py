# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for kernel_unit_doubles.py: python -m pytest doc/_scripts -q"""

import re
import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kernel_unit_doubles as kud  # noqa: E402


def src(text):
    return textwrap.dedent(text).lstrip("\n")


# A small harness: one fake group, one shadow header, one model, one unit.
FILES = {
    "common/include/ksched.h": """
        /*
         * Copyright
         *
         * SPDX-License-Identifier: Apache-2.0
         */

        /*
         * Shadow of kernel/include/ksched.h.
         */

        #ifdef __cplusplus
        extern "C" {
        #endif

        DECLARE_FAKE_VALUE_FUNC(int, z_pend_curr, struct k_spinlock *, k_spinlock_key_t);
        DECLARE_FAKE_VALUE_FUNC(bool, z_sched_wake, _wait_q_t *, int, void *);
        DECLARE_FAKE_VOID_FUNC(z_reschedule, struct k_spinlock *, k_spinlock_key_t);
        DECLARE_FAKE_VALUE_FUNC(bool, z_valid, int);

        /* KERNEL_UNIT_REAL_COPY_BEGIN kernel/include/ksched.h */
        static inline bool z_is_prio_higher(int prio, int test_prio)
        {
                return prio < test_prio;
        }
        /* KERNEL_UNIT_REAL_COPY_END */

        #ifdef __cplusplus
        }
        #endif
        """,
    "common/fakes/sched.c": """
        #include <ksched.h>

        z_pend_curr_Fake z_pend_curr_fake;

        int z_pend_curr(struct k_spinlock *a, k_spinlock_key_t k)
        {
                return 0;
        }

        DEFINE_FAKE_VALUE_FUNC(bool, z_sched_wake, _wait_q_t *, int, void *);
        DEFINE_FAKE_VOID_FUNC(z_reschedule, struct k_spinlock *, k_spinlock_key_t);
        DEFINE_FAKE_VALUE_FUNC(bool, z_valid, int);

        static void sched_fakes_reset(const struct ztest_unit_test *test, void *fixture)
        {
                z_valid_fake.return_val = true;
        }
        """,
    "common/include/kernel_unit.h": """
        static inline size_t kernel_unit_history_len(void)
        {
                return 0;
        }
        """,
    "common/include/kernel_unit_models.h": """
        #ifdef __cplusplus
        extern "C" {
        #endif

        /**
         * @name Waiting threads
         *
         * Assumption: z_sched_wake() wakes the first waiting thread.
         * @{
         */

        static inline bool kernel_unit_wake_waiting_thread(_wait_q_t *q, int r, void *d)
        {
                return true;
        }

        /** @brief Let n threads wait. */
        static inline void kernel_unit_set_waiting_threads(unsigned int n)
        {
                z_sched_wake_fake.custom_fake = kernel_unit_wake_waiting_thread;
        }

        /** @} */

        /** @brief Assert that the lock was released once. */
        static inline void kernel_unit_assert_released(void)
        {
                zassert_equal(z_reschedule_fake.call_count, 1);
        }

        #ifdef __cplusplus
        }
        #endif
        """,
    "common/fake_limits.yaml": """
        limits:
          - id: R1
            severity: high
            title: A wait result has no connection to a wake.
            applies:
              - fake: z_pend_curr
                how: [value, sequence]
          - id: R3
            severity: high
            title: The waiting-threads model has no order.
            applies:
              - uses: kernel_unit_set_waiting_threads
          - id: R4
            severity: high
            title: The reschedule decision is not modeled.
            applies:
              - checks: z_reschedule
        """,
    "obj/CMakeLists.txt": """
        include(${ZEPHYR_SAFETY_MODULE_DIR}/cmake/kernel_unit.cmake)
        # kernel_unit_fakes(commented out)
        kernel_unit_fakes(sched)
        kernel_unit_fakes_ifdef(CONFIG_ASSERT assert)
        """,
    "obj/src/test_obj.c": """
        /**
         * @defgroup kernel_unit_obj kernel/obj.c
         * @brief The unit.
         *
         * @kunit_interfaces
         */

        #include <kernel/obj.c>

        /* Spy z_pend_curr(): return 0. */
        static int pend_spy(struct k_spinlock *l, k_spinlock_key_t k)
        {
                return 0;
        }

        static void wake_two(void)
        {
                kernel_unit_set_waiting_threads(2);
        }

        /* An action of another thread. */
        static void other(void)
        {
        }

        static void obj_before(void *fixture)
        {
                z_sched_wake_fake.return_val = true;
        }

        ZTEST_SUITE(obj_unit, NULL, NULL, obj_before, NULL, NULL);

        /**
         * @brief A test with a sequence.
         */
        ZTEST(obj_unit, test_sequence)
        {
                int r[] = {0, -EAGAIN};

                SET_RETURN_SEQ(z_pend_curr, r, 2);
                run(other);
                zassert_equal(z_pend_curr_fake.call_count, 2);
                zassert_call_history(z_pend_curr, KERNEL_UNIT_IF_ENABLED(CONFIG_X, z_reschedule));
        }

        /**
         * @brief A test with a local spy and a model.
         */
        ZTEST(obj_unit, test_spy_and_model)
        {
                z_pend_curr_fake.custom_fake = pend_spy;
                wake_two();
                zassert_called_before(z_sched_wake, z_pend_curr);
                kernel_unit_assert_released();
        }

        /**
         * @brief A test without doubles.
         */
        ZTEST(obj_unit, test_nothing)
        {
                zassert_equal(kernel_unit_history_len(), 0);
        }
        """,
}


@pytest.fixture
def harness(tmp_path):
    for rel, text in FILES.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(src(text))
    return kud.Harness(tmp_path)


def test_mask_keeps_length_and_lines():
    text = 'a /* b\n c */ "d*/" // e\nf'
    code, comments = kud.mask(text)
    assert len(code) == len(text)
    assert code.count("\n") == text.count("\n")
    assert "b" not in code and "d" not in code and "e" not in code
    assert [c[2] for c in comments] == ["/* b\n c */"]


def test_functions_of_header_with_extern_c(harness):
    names = [f.name for f in kud.functions_of(harness.include / "kernel_unit_models.h")]
    assert names == ["kernel_unit_wake_waiting_thread", "kernel_unit_set_waiting_threads",
                     "kernel_unit_assert_released"]


def test_functions_of_tests_and_comments(harness):
    fs = {f.name: f for f in kud.functions_of(harness.root / "obj/src/test_obj.c")}
    assert fs["test_sequence"].test and fs["test_sequence"].suite == "obj_unit"
    assert "Spy z_pend_curr()" in fs["pend_spy"].comment
    assert fs["wake_two"].comment == ""


def test_fakes_groups_defaults(harness):
    f = harness.fakes
    assert harness.groups["sched"] == ["z_pend_curr", "z_sched_wake", "z_reschedule", "z_valid"]
    assert f["z_pend_curr"].hand_written and f["z_pend_curr"].returns == "int"
    assert f["z_reschedule"].default_text() == "records the call"
    assert f["z_sched_wake"].default_text() == "returns false"
    assert f["z_valid"].default_text() == "returns true"
    assert f["z_sched_wake"].header == "ksched.h"
    assert "Shadow of kernel/include/ksched.h." in harness.headers["ksched.h"]


def test_real_copies_and_models(harness):
    assert [(r.names, r.shadow, r.real) for r in harness.real] == [
        (["z_is_prio_higher"], "ksched.h", "kernel/include/ksched.h")]
    sec = harness.model_of["kernel_unit_set_waiting_threads"]
    assert sec.title == "Waiting threads" and sec.slug == "waiting_threads"
    assert any("Assumption" in x for x in sec.text)
    assert "kernel_unit_assert_released" not in harness.model_of


def test_uses_of_a_test(harness):
    unit = kud.Unit(harness, "obj")
    t = {x.name: x for x in unit.tests}
    uses = unit.uses(t["test_sequence"])
    configs = [(u.fake, u.how, u.origin) for u in uses if u.what == "config"]
    assert configs == [("z_pend_curr", "sequence", "test"), ("z_sched_wake", "value", "suite")]
    checks = {(u.fake, u.how) for u in uses if u.what == "check"}
    assert checks == {("z_pend_curr", "calls"), ("z_pend_curr", "call history"),
                      ("z_reschedule", "call history")}
    assert [u.detail for u in uses if u.what == "action"] == ["other"]

    uses = unit.uses(t["test_spy_and_model"])
    own = [u for u in uses if u.origin == "test" and u.what == "config"]
    assert [(u.fake, u.detail, u.via) for u in own] == [
        ("z_pend_curr", "pend_spy", ()),
        ("z_sched_wake", "kernel_unit_wake_waiting_thread",
         ("wake_two", "kernel_unit_set_waiting_threads"))]
    assert harness.kind_of_custom("pend_spy", unit) == "local"
    assert harness.kind_of_custom("kernel_unit_wake_waiting_thread", unit) == "model"
    # A shared check is listed by its name, not by the fakes that it reads.
    assert not any(u.fake == "z_reschedule" for u in uses if u.what == "check")
    assert "kernel_unit_assert_released" in {u.detail for u in uses if u.what == "shared"}
    assert unit.fake_groups == [("", "sched"), ("CONFIG_ASSERT", "assert")]


def test_effective_keeps_the_last_of_one_call(harness):
    unit = kud.Unit(harness, "obj")
    a = kud.Use("config", "z_pend_curr", "custom", "kernel_unit_wake_waiting_thread",
                ("helper", "shared"))
    b = kud.Use("config", "z_pend_curr", "custom", "pend_spy", ("helper",))
    c = kud.Use("config", "z_pend_curr", "value", "1", ())
    out = kud.effective(harness, unit, [a, b, c])
    assert [u.detail for u in out] == ["pend_spy", "1"]
    assert "Waiting threads" in out[0].replaces


def test_limits(harness):
    unit = kud.Unit(harness, "obj")
    limits = kud.read_limits(harness)
    t = {x.name: x for x in unit.tests}

    def ids(name):
        own = [u for u in unit.uses(t[name]) if u.origin == "test"]
        return [lim.id for lim in kud.limits_of(limits, unit, own)]

    assert ids("test_sequence") == ["R1", "R4"]
    assert ids("test_spy_and_model") == ["R3"]
    assert ids("test_nothing") == []


def test_check_finds_a_stale_selector(harness):
    errors, _ = kud.check(harness, kud.read_limits(harness))
    assert errors == []
    stale = kud.Limit("R9", "low", "t", "", [{"fake": "z_valid", "how": "value"}])
    bad = kud.Limit("R8", "low", "t", "", [{"fake": "no_such", "color": 1}])
    errors, _ = kud.check(harness, [stale, bad])
    assert any("R9" in e and "stale" in e for e in errors)
    assert any("R8" in e and "unknown keys" in e for e in errors)
    assert any("R8" in e and "is not a fake" in e for e in errors)


def test_check_prose_and_comments(harness):
    _, warnings = kud.check(harness, [], prose=True)
    # The doc comments of the two tests do not name z_pend_curr(). The model
    # of wake_two() is a statement of a helper, not of the test body.
    assert any("test_sequence" in w and "z_pend_curr()" in w for w in warnings)
    assert any("test_spy_and_model" in w and "z_pend_curr()" in w for w in warnings)
    assert not any("z_sched_wake" in w for w in warnings)
    _, warnings = kud.check(harness, [])
    assert warnings == []


def test_annotate_keeps_lines(harness):
    path = harness.root / "obj/src/test_obj.c"
    text = path.read_text()
    out = kud.annotate(text, path, harness)
    assert len(out.splitlines()) == len(text.splitlines())
    assert out.count("/**") == text.count("/**") and out.count("*/") == text.count("*/")
    line = next(x for x in out.splitlines() if "@kunit_interfaces" in x)
    assert "<table" in line and "kunit_doubles_fake_z_pend_curr" in line
    seq = next(x for x in out.splitlines() if "kunit_doubles_test_obj_test_sequence" in x)
    assert seq.rstrip().endswith("*/")
    assert "@kunit_doubles" in seq and "@kunit_limit{" in seq and "SET_RETURN_SEQ" in seq
    nothing = next(x for x in out.splitlines() if "kunit_doubles_test_obj_test_nothing" in x)
    assert "None: each fake has its default" in nothing


def test_annotate_without_marker_is_unchanged(harness):
    text = "/** @brief x */\nZTEST(s, test_x)\n{\n}\n"
    assert kud.annotate(text, harness.root / "obj/src/x.c", harness) == text


def test_catalog_has_anchors(harness):
    text = kud.catalog_comment(harness, kud.read_limits(harness))
    for anchor in ("kunit_doubles_fake_z_pend_curr", "kunit_doubles_group_sched",
                   "kunit_doubles_model_waiting_threads", "kunit_doubles_limit_R1",
                   "kunit_doubles_local_obj_pend_spy"):
        assert re.search(rf"@(anchor|subsection|section) {anchor}\b", text), anchor
    assert "@ref kunit_doubles_test_obj_test_sequence" in text


def test_real_harness():
    """The harness of the repository: the sem unit and the reference fake."""
    h = kud.Harness()
    unit = kud.Unit(h, "sem")
    t = {x.name: x for x in unit.tests}
    own = [u for u in unit.uses(t["test_take_returns_wait_result"]) if u.origin == "test"]
    assert [(u.fake, u.how) for u in own if u.what == "config"] == [("z_pend_curr", "sequence")]
    assert "R1" in [lim.id for lim in kud.limits_of(kud.read_limits(h), unit, own)]
    assert h.ref["z_sched_wake"].custom == "ref_sched_wake"
    assert unit.uses_reference(unit.uses(t["test_ref_give_wakes_highest_priority_waiter"]))
    errors, _ = kud.check(h, kud.read_limits(h))
    assert errors == []


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Copy the call history to @p out.", "Copy the call history to out."),
        ("Set @c custom_fake and \\c return_val.", "Set custom_fake and return_val."),
        ('See @ref kunit_x "the page" and @ref other.', "See the page and other."),
        ("With @kconfig{CONFIG_POLL} only.", "With CONFIG_POLL only."),
        ("@brief Assert one thing.", "Assert one thing."),
        ("Plain text, no command.", "Plain text, no command."),
    ],
)
def test_plain_removes_doxygen_commands(text, expected):
    assert kud.plain(text) == expected


def test_first_sentence_is_plain():
    comment = "/**\n * @brief Copy the history to @p out, see @ref x \"X\".\n *\n * More.\n */"
    assert kud.first_sentence(comment) == "Copy the history to out, see X."


def test_history_helper_is_one_line(harness):
    unit = kud.Unit(harness, "obj")
    t = {x.name: x for x in unit.tests}
    text = kud.render_test(harness, unit, t["test_nothing"], [])
    assert "Call history of all fakes: no call (<code>kernel_unit_history_len()</code>)" in text
    assert "kernel_unit_history_len()</code>:" not in text


def test_no_doxygen_command_leaks_into_generated_text():
    """A command of a comment of the harness must not reach the page as text.

    esc() escapes "@" and "\\", so a leaked command shows as "\\@" or "\\\\"."""
    h = kud.Harness()
    limits = kud.read_limits(h)
    texts = []
    for name in kud.units_of(h):
        unit = kud.Unit(h, name)
        texts.append(kud.render_unit(h, unit, limits))
        texts += [kud.render_test(h, unit, t, limits) for t in unit.tests]
    texts.append(kud.catalog_comment(h, limits))
    for text in texts:
        assert "\\@" not in text, text[:200]
        assert "\\\\" not in text, text[:200]


def test_operator_of_is_the_first_paragraph():
    ref = kud.RefFake("z_x", "ref_x", "/*\n * z_x(): Op(a). The fake does this.\n *\n"
                      " * Difference: more text.\n */")
    assert kud.operator_of(ref) == "Op(a). The fake does this."
