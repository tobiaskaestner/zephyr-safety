# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""tla_extract: the units of a module, their extent and their doc comments."""

import pytest

from tla_extract import TLAParseError, comment_text, parse_file, parse_module


@pytest.fixture
def ksem(ksem_copy):
    return parse_file(ksem_copy)


@pytest.fixture
def extra(extra_tla):
    return parse_file(extra_tla)


def line_of(path, text):
    """The 1-based line of the first line of ``path`` that starts with ``text``."""
    for k, line in enumerate(path.read_text().split("\n")):
        if line.startswith(text):
            return k + 1
    raise AssertionError(text)


def test_ksem_header(ksem):
    assert ksem.name == "KSem"
    assert ksem.extends == ["Integers", "Sequences", "FiniteSets", "TLC"]
    assert ksem.constants[:3] == ["Threads", "Isr", "Prio"]
    assert "PendAtomic" in ksem.constants
    assert ksem.variables == [
        "initialized", "count", "limit", "waitq", "pc", "tmo", "swapRet", "tokens", "obs",
    ]  # fmt: skip
    assert ksem.doc.startswith("Design specification of the Zephyr semaphore")
    assert "(* " not in ksem.doc and "*)" not in ksem.doc


def test_ksem_definitions_in_order(ksem):
    names = [u.name for u in ksem.definitions()]
    assert names[:3] == ["Actors", "OK", "EAGAIN"]
    assert names[-3:] == ["WaiterServedIfGives", "TimedWaitEnds", "WokenReturns"]
    assert len(names) == len(set(names)) == 43


def test_a_definition_ends_before_the_next_comment_at_column_0(ksem, ksem_copy):
    give = ksem.definition("Give")
    assert give.start_line == line_of(ksem_copy, "Give(a) ==")
    take_comment = line_of(ksem_copy, "\\* z_impl_k_sem_take()")
    assert give.end_line == take_comment - 2  # a blank line between
    assert give.text.split("\n")[-1].strip().startswith("/\\ UNCHANGED")
    # The indented comment in the body is part of the definition.
    assert "\\* API view: a give at the limit has no effect." in give.text


def test_a_definition_ends_before_a_separator(ksem):
    unit = ksem.definition("Inflight")
    assert unit.end_line == unit.start_line
    assert "----" not in unit.text


def test_the_last_definition_ends_before_the_footer(ksem):
    unit = ksem.definition("WokenReturns")
    assert unit.end_line == ksem.footer_line - 2
    assert "====" not in unit.text


def test_doc_comment_and_tags(ksem):
    give = ksem.definition("Give")
    assert give.doc.startswith("z_impl_k_sem_give(). z_sched_wake()")
    assert "@" not in give.doc
    assert give.tags == {"kind": ["action"], "c-function": ["z_impl_k_sem_give"]}
    nwa = ksem.definition("NoWaitWhileAvailable")
    assert nwa.tags == {"expresses": ["TEST-REQ-2", "TEST-REQ-3"]}
    assert nwa.doc == "No thread waits while the semaphore is available."
    assert [n for _, _, n in nwa.tag_lines] == [nwa.start_line - 2, nwa.start_line - 1]


def test_a_doc_comment_line_maps_to_its_file_line(ksem, ksem_copy):
    unit = ksem.definition("Enqueue")
    lines = ksem_copy.read_text().split("\n")
    for text, line_no in zip(unit.doc.split("\n"), unit.doc_lines):
        assert lines[line_no - 1] == "\\* " + text


def test_a_comment_with_a_blank_line_below_is_a_section_comment(ksem):
    sections = [u.doc for u in ksem.units if u.kind == "comment"]
    assert sections == [
        "Helpers",
        "Initial state: the semaphore memory is not initialized.",
        "Actions. Each action is one call of sem.c, under sem_lock.",
        "Safety properties (state invariants)",
        "Safety properties (action properties)",
        "Liveness properties",
    ]
    assert ksem.definition("Init").doc == ""


def test_parameters(ksem):
    assert ksem.definition("Take").params == ["a", "to"]
    assert ksem.definition("Take").head == "Take(a, to)"
    assert ksem.definition("Spec").params == []


def test_infix_prefix_postfix(extra):
    infix = extra.definition("++")
    assert (infix.params, infix.plain_head, infix.head) == (["a", "b"], False, "a ++ b")
    assert extra.definition("-.").params == ["a"]
    assert extra.definition("^#").params == ["a"]


def test_local_and_function_definitions(extra):
    helper = extra.definition("Helper")
    assert helper.local and helper.params == ["n"] and helper.head == "Helper(n)"
    double = extra.definition("Double")
    assert double.params == ["k"] and not double.plain_head
    assert double.head == "Double[k \\in Nat]"


def test_recursive_belongs_to_its_definition(extra):
    unit = extra.definition("Sum")
    assert unit.recursive == "RECURSIVE Sum(_)"
    assert unit.doc == "The sum of a sequence. The doc comment is above RECURSIVE."


def test_a_box_comment_is_a_doc_comment(extra):
    assert extra.definition("Double").doc == (
        "A box comment as the doc comment.\n\nThe text can use *RST* markup."
    )


def test_a_block_comment_is_dedented(extra):
    assert extra.definition("Long").doc == "A block comment\non two lines."


def test_a_head_over_two_lines(extra):
    unit = extra.definition("Long")
    assert unit.params == ["p", "q"]
    assert unit.head == "Long(p, q)"
    assert "(* A nested (* block *) comment. *)" in unit.text
    assert unit.text.rstrip().endswith("/\\ q \\in Nat")


def test_an_instance(extra):
    unit = extra.definition("Seqs")
    assert unit.instance and unit.tags == {"kind": ["definition"]}


def test_double_equals_in_a_string_or_a_comment(extra):
    unit = extra.definition("Text")
    assert unit.head == "Text"
    assert unit.text == 'Text == "a == b \\* c"   \\* not a definition == here'


def test_theorem_and_pluscal(extra):
    theorem = next(u for u in extra.units if u.kind == "theorem")
    assert theorem.name == "SpecTyped"
    pluscal = next(u for u in extra.units if u.kind == "pluscal")
    assert pluscal.text.startswith("(* --algorithm Counter")
    assert pluscal.text.endswith("end algorithm; *)")


def test_declarations(extra):
    assert extra.constants == ["N", "F"]
    assert extra.variables == ["x"]
    assert extra.extends == ["Naturals", "Sequences"]
    assert extra.doc == "Edge cases for the extractor of tla_domain. Not a model."


def test_text_after_the_footer_is_ignored(extra):
    assert extra.definition("Ghost") is None


def test_errors():
    with pytest.raises(TLAParseError):
        parse_module("X == 1\n")
    with pytest.raises(TLAParseError):
        parse_module("---- MODULE M ----\nX == 1\n")


def test_a_nested_module_is_skipped():
    text = "---- MODULE Outer ----\nA == 1\n---- MODULE Inner ----\nB == 2\n====\nC == 3\n====\n"
    module = parse_module(text)
    assert [u.name for u in module.definitions()] == ["A", "C"]


def test_comment_text_removes_markers_and_rules():
    lines, nos = comment_text(["\\* one", "\\*", "\\*   indented", "\\* ****"], 10)
    assert lines == ["one", "", "  indented"]
    assert nos == [10, 11, 12]
