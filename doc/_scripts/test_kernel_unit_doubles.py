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
          - id: TDL-1
            review: R1
            severity: high
            title: A wait result has no connection to a wake.
            applies:
              - fake: z_pend_curr
                how: [value, sequence]
          - id: TDL-3
            severity: high
            title: The waiting-threads model has no order.
            applies:
              - uses: kernel_unit_set_waiting_threads
          - id: TDL-4
            severity: high
            title: The reschedule decision is not modeled.
            applies:
              - checks: z_reschedule
          - id: TDL-5
            severity: low
            title: The wake value of the suite is fixed.
            applies:
              - fake: z_sched_wake
                how: value
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

    assert ids("test_sequence") == ["TDL-1", "TDL-4"]
    assert ids("test_spy_and_model") == ["TDL-3"]
    assert ids("test_nothing") == []


def test_check_finds_a_stale_selector(harness):
    errors, _, _ = kud.check(harness, kud.read_limits(harness))
    assert errors == []
    stale = kud.Limit("TDL-9", "low", "t", "", [{"fake": "z_valid", "how": "value"}])
    bad = kud.Limit("TDL-8", "low", "t", "", [{"fake": "no_such", "color": 1}])
    errors, _, _ = kud.check(harness, [stale, bad])
    assert any("TDL-9" in e and "stale" in e for e in errors)
    assert any("TDL-8" in e and "unknown keys" in e for e in errors)
    assert any("TDL-8" in e and "is not a fake" in e for e in errors)


def test_check_prose_runs_always_as_warning(harness):
    errors, warnings, _ = kud.check(harness, [])
    assert errors == []
    # The doc comments of the two tests do not name z_pend_curr(). The model
    # of wake_two() is a statement of a helper, not of the test body.
    assert any("test_sequence" in w and "z_pend_curr()" in w for w in warnings)
    assert any("test_spy_and_model" in w and "z_pend_curr()" in w for w in warnings)
    assert not any("z_sched_wake" in w for w in warnings)


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
    assert "@kunit_doubles" in seq and "@kunit_limits <ul>" in seq and "SET_RETURN_SEQ" in seq
    assert "@kunit_limit{" not in seq and "xrefitem" not in out
    nothing = next(x for x in out.splitlines() if "kunit_doubles_test_obj_test_nothing" in x)
    # The suite setup configures a fake: the test itself configures none.
    assert "None: the test itself configures no fake." in nothing
    assert "None: each fake has its default" not in nothing


def test_annotate_without_marker_is_unchanged(harness):
    text = "/** @brief x */\nZTEST(s, test_x)\n{\n}\n"
    assert kud.annotate(text, harness.root / "obj/src/x.c", harness) == text


def test_catalog_has_anchors(harness):
    text = kud.catalog_comment(harness, kud.read_limits(harness))
    for anchor in ("kunit_doubles_fake_z_pend_curr", "kunit_doubles_group_sched",
                   "kunit_doubles_model_waiting_threads", "kunit_doubles_limit_TDL_1",
                   "kunit_doubles_local_obj_pend_spy"):
        assert re.search(rf"@(anchor|subsection|section) {anchor}\b", text), anchor
    assert '@ref kunit_doubles_test_obj_test_sequence "test_sequence"' in text
    assert "History: finding R1 of the review" in text


def test_real_harness():
    """The harness of the repository: the sem unit and the reference fake."""
    h = kud.Harness()
    unit = kud.Unit(h, "sem")
    t = {x.name: x for x in unit.tests}
    own = [u for u in unit.uses(t["test_take_returns_wait_result"]) if u.origin == "test"]
    assert [(u.fake, u.how) for u in own if u.what == "config"] == [("z_pend_curr", "sequence")]
    assert "TDL-1" in [lim.id for lim in kud.limits_of(kud.read_limits(h), unit, own)]
    assert h.ref["z_sched_wake"].custom == "ref_sched_wake"
    assert unit.uses_reference(unit.uses(t["test_ref_give_wakes_highest_priority_waiter"]))
    errors, _, _ = kud.check(h, kud.read_limits(h))
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


# --------------------------------------------------------------------------
# Decisions of 2026-10-28: TDL ids, suite-setup line, TLA+ links, unit
# marker, limits grouped by unit, callbacks of a test descriptor.


def test_limit_ids_of_the_repository():
    """The ids are TDL-1 to TDL-17. The review finding is history."""
    limits = kud.read_limits(kud.Harness())
    assert [lim.id for lim in limits] == [f"TDL-{n}" for n in range(1, 18)]
    review = {lim.id: lim.review for lim in limits}
    assert review["TDL-1"] == "R1" and review["TDL-13"] == "R13"
    assert review["TDL-14"].startswith("R14") and review["TDL-15"].startswith("R14")
    assert review["TDL-16"] == "R15"
    assert all(lim.severity in kud.SEVERITIES for lim in limits)
    assert kud.limit_anchor("TDL-16") == "kunit_doubles_limit_TDL_16"


def test_check_rejects_bad_limit_ids(harness):
    sel = [{"fake": "z_pend_curr", "how": "sequence"}]
    limits = [kud.Limit("R1", "high", "t", "", sel),
              kud.Limit("TDL-2", "high", "t", "", sel),
              kud.Limit("TDL-2", "high", "t", "", sel),
              kud.Limit("TDL-03", "high", "t", "", sel),
              kud.Limit("TDL-4", "severe", "t", "", sel, unknown=["source"])]
    errors, _, _ = kud.check(harness, limits)
    assert any("R1" in e and "not TDL-<n>" in e for e in errors)
    assert any("TDL-03" in e and "not TDL-<n>" in e for e in errors)
    assert any("TDL-2" in e and "two limits" in e for e in errors)
    assert any("TDL-4" in e and "severity" in e for e in errors)
    assert any("TDL-4" in e and "unknown keys ['source']" in e for e in errors)


def test_suite_setup_line(harness):
    """Each test of a suite whose setup has a limit gets one line with links."""
    unit = kud.Unit(harness, "obj")
    limits = kud.read_limits(harness)
    t = {x.name: x for x in unit.tests}
    for name in ("test_sequence", "test_nothing"):
        text = kud.render_test(harness, unit, t[name], limits)
        assert ('<li>Limits of the suite setup: @ref kunit_doubles_limit_TDL_5 "TDL-5" '
                '(see @ref kernel_unit_obj "kernel/obj.c")</li>') in text
    # The full text is once in the file group.
    table = kud.render_unit(harness, unit, limits)
    assert "TDL-5" in table and "The wake value of the suite is fixed." in table
    # test_nothing has no limit of its own: the section has only the line.
    text = kud.render_test(harness, unit, t["test_nothing"], limits)
    section = text[text.index("@kunit_limits"):]
    assert section.count("<li>") == 1 and "Limits of the suite setup" in section


def test_suite_setup_line_of_mutex():
    h = kud.Harness()
    unit = kud.Unit(h, "mutex")
    t = {x.name: x for x in unit.tests}
    text = kud.render_test(h, unit, t["test_lock_free_mutex_takes_ownership"], kud.read_limits(h))
    line = re.search(r"Limits of the suite setup: (.*?) \(see", text).group(1)
    assert re.findall(r'"(TDL-\d+)"', line) == ["TDL-2", "TDL-6", "TDL-7", "TDL-11", "TDL-13",
                                                 "TDL-16"]


def test_catalog_groups_the_tests_of_a_limit_by_unit(harness):
    text = kud.catalog_comment(harness, kud.read_limits(harness))
    sect = text[text.index("@subsection kunit_doubles_limit_TDL_1 "):]
    sect = sect[:sect.index("@subsection", 10)]
    assert ('<li>@ref kernel_unit_obj "kernel/obj.c" (1): '
            '@ref kunit_doubles_test_obj_test_sequence "test_sequence"</li>') in sect
    sect = text[text.index("@subsection kunit_doubles_limit_TDL_5 "):]
    assert ('<li>@ref kernel_unit_obj "kernel/obj.c": the 3 tests of the suite '
            '<code>obj_unit</code> (<code>obj_before()</code>)</li>') in sect


def test_marker_warning(harness, tmp_path):
    """A unit test source in the INPUT of the document without a unit marker."""
    other = tmp_path / "other/src/test_other.c"
    other.parent.mkdir(parents=True)
    other.write_text("/** @brief x */\nZTEST(s, test_x)\n{\n}\n")
    doxyfile = tmp_path / "Doxyfile.in"
    doxyfile.write_text("INPUT = @DOXY_SRC_DIR@/mainpage.md \\\n"
                        "        @SAFETY_BASE@/tests/kernel/unit/obj/src/test_obj.c \\\n"
                        "        @SAFETY_BASE@/tests/kernel/unit/other/src/test_other.c\n"
                        "RECURSIVE = NO\n")
    assert kud.doc_inputs(doxyfile, tmp_path) == {"obj": ["test_obj.c"],
                                                  "other": ["test_other.c"]}
    _, warnings, _ = kud.check(harness, kud.read_limits(harness), doxyfile=doxyfile)
    marker = [w for w in warnings if kud.MARKER in w]
    assert marker == [f"other: no test source has the marker {kud.MARKER} (test_other.c): "
                      "the document shows no test doubles of this unit"]


def test_marker_is_per_unit(harness):
    """A second test source of a unit with the marker gets the test sections too."""
    second = harness.root / "obj/src/test_obj_more.c"
    second.write_text(src("""
        /**
         * @brief A test of the second source.
         */
        ZTEST(obj_unit, test_more)
        {
                z_pend_curr_fake.return_val = 1;
        }
        """))
    out = kud.annotate(second.read_text(), second, kud.Harness(harness.root))
    assert "kunit_doubles_test_obj_test_more" in out and "@kunit_doubles" in out


def test_tla_anchor_is_the_rule_of_the_tla_domain():
    pytest.importorskip("sphinx")
    sys.path.insert(0, str(kud.SAFETY_BASE / "doc" / "_extensions"))
    import tla_domain  # noqa: E402

    for args in (("Scheduler", "WakeFirst"), ("WaitQueue", "Best"), ("Scheduler",),
                 ("M", "x_y'"), ("M", "a!b")):
        assert kud.tla_anchor(*args) == tla_domain.anchor_id(*args)


def test_tla_refs():
    tla = kud.Harness().tla
    text = ("WakeFirst(o, ret, data). The return value is HasWaiters(o). The value F(t)[1] "
            "of WakeFirstWith, WaitQueue!Best(o), WQ!Restamp, the check ArmedArePending, "
            "Head(o), ISR and NULL. Release the lock.")
    refs = [(r.text, r.anchor, r.found) for r in tla.refs(text)]
    assert refs == [
        ("WakeFirst", "tla-Scheduler-WakeFirst", True),
        ("HasWaiters", "tla-Scheduler-HasWaiters", True),
        ("WakeFirstWith", "tla-Scheduler-WakeFirstWith", True),
        ("WaitQueue!Best", "tla-WaitQueue-Best", True),
        ("WQ!Restamp", "tla-WaitQueue-Restamp", True),
        ("ArmedArePending", "tla-Scheduler-ArmedArePending", True),
        ("Head", "tla-Scheduler-Head", False),
    ]


def test_rich_links_operators_and_limits():
    h = kud.Harness()
    text = kud.rich(h, "WakeFirst(o, ret, data), Head(o) and the key (known limit TDL-8).")
    assert ('<a href="../architecture/formal-model.html#tla-Scheduler-WakeFirst">WakeFirst</a>'
            "(o, ret, data)") in text
    assert "Head(o)" in text and "tla-Scheduler-Head" not in text
    assert '@ref kunit_doubles_limit_TDL_8 "TDL-8"' in text


def test_reference_test_links_into_the_formal_model():
    h = kud.Harness()
    unit = kud.Unit(h, "sem")
    t = {x.name: x for x in unit.tests}
    text = kud.render_test(h, unit, t["test_ref_give_wakes_highest_priority_waiter"],
                           kud.read_limits(h))
    assert ('<a href="../architecture/formal-model.html#tla-Scheduler-WakeFirst">WakeFirst</a>'
            in text)


def test_tla_link_check_against_the_sources(tmp_path):
    h = kud.Harness()
    errors, note = kud.tla_link_check(h)
    assert errors == []
    assert "checked against the tla directives of doc/specification/architecture/" in note
    assert "tla-Scheduler-WakeFirst" in kud.rendered_anchors(h.tla, kud.MODEL_RST)
    # A page without the module Timeout: the link Timeout!Cancel has no anchor.
    rst = tmp_path / "formal-model.rst"
    rst.write_text(".. tla:module:: Scheduler\n   :body:\n\n"
                   ".. tla:definition:: WaitQueue!Best\n\n"
                   ".. tla:module:: WaitQueue\n\n"
                   ".. tla:definition:: Restamp\n")
    ids = kud.rendered_anchors(h.tla, rst)
    assert {"tla-WaitQueue-Best", "tla-WaitQueue-Restamp", "tla-module-WaitQueue"} <= ids
    assert "tla-WaitQueue-W" not in ids
    errors, _ = kud.tla_link_check(h, rst=rst)
    assert errors == ["TLA+ link Timeout!Cancel: the page architecture/formal-model.html has no "
                      "anchor #tla-Timeout-Cancel"]


def test_tla_link_check_against_the_built_page(tmp_path):
    h = kud.Harness()
    page = tmp_path / kud.ARCH_DOC / kud.MODEL_PAGE
    page.parent.mkdir()
    page.write_text('<dt id="tla-Scheduler-WakeFirst">x</dt>')
    errors, note = kud.tla_link_check(h, deploy=tmp_path)
    assert f"checked against the built page {page}" in note
    assert "TLA+ link PendCurr: the page architecture/formal-model.html has no anchor " \
           "#tla-Scheduler-PendCurr" in errors
    assert not any("WakeFirst:" in e for e in errors)
    errors, note = kud.tla_link_check(h, deploy=tmp_path / "missing")
    assert errors == [] and "is not built" in note


def test_check_reports_an_operator_that_the_library_does_not_define(monkeypatch):
    h = kud.Harness()
    ref = h.ref["z_waitq_head"]
    monkeypatch.setattr(ref, "comment", "/* z_waitq_head(): Head(o), see TDL-99. */")
    errors, _, _ = kud.check(h, kud.read_limits(h))
    assert any("z_waitq_head()" in e and "operator Head" in e for e in errors)
    assert any("z_waitq_head()" in e and "TDL-99" in e for e in errors)


def test_callbacks_of_a_test_descriptor(harness):
    path = harness.root / "obj/src/test_obj.c"
    path.write_text(path.read_text() + src("""
        DEFINE_FAKE_VALUE_FUNC(int, unit_cb, int);
        DEFINE_FAKE_VALUE_FUNC(int, z_below, int);

        static struct obj_desc unit_desc = {
                .name = "d",
                .cb = unit_cb,
        };

        /**
         * @brief A test with a callback of the descriptor.
         */
        ZTEST(obj_unit, test_callback)
        {
                unit_cb_fake.return_val = 2;
                z_below_fake.return_val = 1;
                zassert_equal(unit_cb_fake.call_count, 1);
        }
        """))
    unit = kud.Unit(harness, "obj")
    assert kud.is_callback(unit, "unit_cb") and not kud.is_callback(unit, "z_below")
    t = {x.name: x for x in unit.tests}
    text = kud.render_test(harness, unit, t["test_callback"], [])
    assert ("<code>unit_cb()</code> (callback of the test descriptor <code>unit_desc</code>): "
            "fixed value") in text
    assert "<code>z_below()</code> (fake of <code>test_obj.c</code>)" in text
    table = kud.render_unit(harness, unit, [])
    assert ("<td>none: callback of the test descriptor <code>unit_desc</code> (FFF fake of "
            "<code>test_obj.c</code>)</td>") in table
    assert "A callback of a test descriptor is not a function below the unit." in table


def test_obj_core_usage_group_and_callbacks():
    h = kud.Harness()
    assert h.groups["usage"] == ["z_kernel_stats_raw", "z_kernel_stats_query"]
    assert h.fakes["z_kernel_stats_raw"].header == "fakes/usage.h"
    unit = kud.Unit(h, "obj_core")
    assert ("CONFIG_OBJ_CORE_STATS_SYSTEM", "usage") in unit.fake_groups
    assert set(unit.local_fakes) == {f"unit_stats_{x}" for x in
                                     ("raw", "query", "reset", "disable", "enable")}
    assert all(f.descriptor == "unit_stats_desc" for f in unit.local_fakes.values())


# --------------------------------------------------------------------------
# Roll-out to all units (2026-10-28): fixes found in the review of the pages
# of the 7 other units.


def test_split_args_and_enclosing_call():
    assert kud.split_args("a, f(b, c), {d, e}, ") == ["a", "f(b, c)", "{d, e}", ""]
    assert kud.split_args("") == []
    body = ("{\n\tx = 1;\n\tcheck(&(const struct rule){.lock = &l, .before = filt});\n"
            "\trun(act, 2);\n\tw = act2;\n\tif (y) {\n\t\tz(other);\n\t}\n}")
    assert kud.enclosing_call(body, body.index("filt")) == "check"
    assert kud.enclosing_call(body, body.index("act,")) == "run"
    assert kud.enclosing_call(body, body.index("act2")) == ""
    assert kud.enclosing_call(body, body.index("other")) == "z"


def add_tests(harness, text):
    path = harness.root / "obj/src/test_obj.c"
    path.write_text(path.read_text() + src(text))
    unit = kud.Unit(harness, "obj")
    return unit, {x.name: x for x in unit.tests}


def test_macro_gets_the_arguments_of_the_call(harness):
    """zassert_oops_before(fn) of the units: the order check names the fake of the call."""
    unit, t = add_tests(harness, """
        #define zassert_pend_before(fn)                                        \\
                do {                                                           \\
                        zassert_equal(z_pend_curr_fake.call_count, 1);         \\
                        zassert_called_before(z_pend_curr, fn);                \\
                } while (false)

        /**
         * @brief A test with a local macro.
         */
        ZTEST(obj_unit, test_macro)
        {
                zassert_pend_before(z_reschedule);
        }
        """)
    checks = {(u.fake, u.how, u.via) for u in unit.uses(t["test_macro"]) if u.what == "check"}
    assert checks == {("z_pend_curr", "calls", ("zassert_pend_before",)),
                      ("z_pend_curr", "order", ("zassert_pend_before",)),
                      ("z_reschedule", "order", ("zassert_pend_before",))}
    assert unit.local["zassert_pend_before"].params == ("fn",)


def test_struct_tag_and_check_arguments_are_not_actions(harness):
    """A tag with the name of a function, and a function that a check gets."""
    unit, t = add_tests(harness, """
        struct state {
                int a;
        };

        static struct state state(void)
        {
                return (struct state){1};
        }

        /* Return true for a call that can come before the lock. */
        static bool early(fff_function_t fn)
        {
                return fn == KERNEL_UNIT_FN(z_valid);
        }

        /**
         * @brief A test with a tag, a filter of a check and an action.
         */
        ZTEST(obj_unit, test_tag_and_filter)
        {
                struct state s = (struct state){0};

                kernel_unit_assert_rule(&(const struct rule){.before_lock = early});
                zassert_list(&s, early);
                run(other);
        }
        """)
    uses = unit.uses(t["test_tag_and_filter"])
    assert [u.detail for u in uses if u.what in ("action", "call")] == ["other"]
    assert not any(u.fake == "z_valid" for u in uses)
    text = kud.render_test(harness, unit, t["test_tag_and_filter"], [])
    assert "<li>Actions of other threads, observers and callbacks: <code>other()</code></li>" in text


def test_same_configuration_once(harness):
    """A helper that the test calls twice, and a second statement with the same value."""
    unit, t = add_tests(harness, """
        static void two_waiters(void)
        {
                z_pend_curr_fake.return_val = 0;
                kernel_unit_set_waiting_threads(2);
        }

        /**
         * @brief A test that calls a helper twice.
         */
        ZTEST(obj_unit, test_twice)
        {
                two_waiters();
                two_waiters();
        }
        """)
    text = kud.render_test(harness, unit, t["test_twice"], [])
    assert text.count("kernel_unit_wake_waiting_thread()") == 1
    a = kud.Use("config", "z_valid", "value", "true", ("setup",))
    b = kud.Use("config", "z_valid", "value", "true", ("setup",))
    out = kud.effective(harness, unit, [a, b])
    assert len(out) == 1 and not hasattr(out[0], "replaces")


def test_repeat_of_the_suite_setup_adds_no_limit(harness):
    """The suite setup has TDL-5: a test that sets the same value again shows it once."""
    unit, t = add_tests(harness, """
        /**
         * @brief A test that resets the fakes and sets the value of the suite again.
         */
        ZTEST(obj_unit, test_again)
        {
                z_sched_wake_fake.return_val = true;
        }

        /**
         * @brief A test with another value.
         */
        ZTEST(obj_unit, test_other_value)
        {
                z_sched_wake_fake.return_val = false;
        }
        """)
    limits = kud.read_limits(harness)
    assert [lim.id for lim in kud.limits_of(limits, unit, unit.limit_uses(t["test_again"]))] == []
    assert [lim.id for lim in kud.limits_of(
        limits, unit, unit.limit_uses(t["test_other_value"]))] == ["TDL-5"]
    text = kud.render_test(harness, unit, t["test_again"], limits)
    section = text[text.index("@kunit_limits"):]
    assert section.count("<li>") == 1 and "Limits of the suite setup" in section


def test_selector_with_a_test_name(harness):
    unit = kud.Unit(harness, "obj")
    t = {x.name: x for x in unit.tests}
    lim = kud.Limit("TDL-9", "low", "t", "", [{"test": ["test_nothing"], "unit": "obj"}])
    assert kud.limits_of([lim], unit, unit.limit_uses(t["test_nothing"]), t["test_nothing"])
    assert not kud.limits_of([lim], unit, unit.limit_uses(t["test_sequence"]),
                             t["test_sequence"])
    assert not kud.limits_of([lim], unit, unit.suite_uses("obj_unit"))
    errors, _, _ = kud.check(harness, [lim])
    assert errors == []
    stale = kud.Limit("TDL-9", "low", "t", "", [{"test": "test_gone"}])
    errors, _, _ = kud.check(harness, [stale])
    assert any("stale" in e for e in errors)


def test_catalog_shows_a_list_of_a_selector_as_names(harness):
    lim = kud.Limit("TDL-9", "low", "t", "",
                    [{"test": ["test_nothing", "test_sequence"], "unit": "obj"}])
    text = "\n".join(kud.render_catalog(harness, [lim]))
    assert ("- test = <code>test_nothing</code>, <code>test_sequence</code>, "
            "unit = <code>obj</code>") in text


def test_brief_of_a_shared_check_shows_parameters_as_code():
    comment = "/**\n * @brief Call @p call and assert that a panic stops it.\n */"
    assert kud.first_sentence(comment) == "Call call and assert that a panic stops it."
    text = kud.code_marks(kud.esc(kud.first_sentence(comment, True)))
    assert text == "Call <code>call</code> and assert that a panic stops it."
