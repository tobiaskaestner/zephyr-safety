# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""tla_unicode: the ASCII to Unicode rendering and its alignment rule."""

import pytest
from pygments.token import Comment, Operator, Whitespace

from tla_extract import parse_file
from tla_unicode import (
    ASCII_TO_UNICODE,
    NAME_TO_UNICODE,
    TLAUnicodeLexer,
    ascii_tokens,
    to_unicode,
    unicode_tokens,
    width,
)


@pytest.mark.parametrize("ascii_op, uni", sorted(ASCII_TO_UNICODE.items()))
def test_each_operator_of_the_table_converts(ascii_op, uni):
    assert to_unicode(f"  A {ascii_op} B") == f"  A {uni} B"


@pytest.mark.parametrize(
    "uni", sorted(set(ASCII_TO_UNICODE.values()) | set(NAME_TO_UNICODE.values()))
)
def test_each_unicode_symbol_takes_one_column(uni):
    assert width(uni) == len(uni)


def test_the_standard_number_sets_convert():
    assert to_unicode("  x \\in Nat \\cup Int \\cup Real") == "  x ∈ ℕ ∪ ℤ ∪ ℝ"


def test_the_prime_converts_and_the_option_keeps_it():
    assert to_unicode("  x' = x + 1") == "  x′ = x + 1"
    assert to_unicode("  x' = x + 1", prime=False) == "  x' = x + 1"


def test_strings_and_comments_do_not_change():
    text = '  x = "a /\\ b" \\* c /\\ d => e\n  (* f \\in g *) y'
    assert to_unicode(text) == '  x = "a /\\ b" \\* c /\\ d => e\n  (* f \\in g *) y'


def test_longest_operator_wins():
    assert to_unicode("  a <=> b") == "  a ⇔ b"
    assert to_unicode("  <<>>") == "  ⟨⟩"
    assert to_unicode("  [][Next]_vars") == "  □[Next]_vars"
    assert to_unicode("  []<><<A>>_v") == "  □◇⟨A⟩_v"
    assert to_unicode("  a |-> b") == "  a ↦ b"


def test_a_bullet_list_stays_aligned():
    text = "Inv ==\n    /\\ a\n    /\\ \\/ b\n       \\/ c\n    /\\ d"
    assert to_unicode(text) == "Inv ≜\n    ∧ a\n    ∧ ∨ b\n      ∨ c\n    ∧ d"


def test_a_list_after_the_head_moves_with_the_head():
    text = "Next == \\/ A\n        \\/ B"
    assert to_unicode(text) == "Next ≜ ∨ A\n       ∨ B"


def test_if_then_else_stays_below_if():
    text = "X ==\n    /\\ IF a\n         THEN b\n         ELSE c"
    assert to_unicode(text) == "X ≜\n    ∧ IF a\n        THEN b\n        ELSE c"


def test_the_pad_rule_keeps_each_column():
    text = "Next == \\/ A\n        \\/ B"
    assert to_unicode(text, align="pad") == "Next ≜  ∨  A\n        ∨  B"


def test_an_unknown_rule_is_an_error():
    with pytest.raises(ValueError):
        to_unicode("x", align="wide")


def test_trailing_comments_stay_in_one_column():
    text = "R == [a |-> <<>>,   \\* one\n      b |-> 1,      \\* two\n      c |-> 2]"
    out = to_unicode(text).split("\n")
    assert out[0].index("\\*") == out[1].index("\\*")


def test_the_unicode_lexer_converts_before_it_lexes():
    toks = [(t, v) for t, v in TLAUnicodeLexer().get_tokens("  a /\\ b") if v.strip()]
    assert toks[1] == (Operator, "∧")


# -- The alignment of the KSem copy --------------------------------------------


def _starts(line):
    """The tokens of a line with their start column: [(col, ttype, value)]."""
    out, col = [], 0
    for ttype, value in line:
        out.append((col, ttype, value))
        col += width(value)
    return out


def _sig(line):
    return [(c, t, v) for c, t, v in _starts(line) if t not in Whitespace]


def _alignment_pairs(ascii_lines):
    """Pairs (line, parent, token index) where the line starts below a token.

    The parent is the nearest line above with a smaller indentation that has
    a token which starts in the column of the first token of the line.
    """
    pairs = []
    for k, line in enumerate(ascii_lines):
        sig = _sig(line)
        if not sig:
            continue
        col = sig[0][0]
        for p in range(k - 1, -1, -1):
            psig = _sig(ascii_lines[p])
            if not psig or psig[0][0] > col:
                continue
            for idx, (pcol, _, _) in enumerate(psig):
                if pcol == col:
                    pairs.append((k, p, idx))
                    break
            break
    return pairs


@pytest.fixture
def ksem_units(ksem_copy):
    module = parse_file(ksem_copy)
    return [u for u in module.units if u.kind in ("definition", "constants", "variables")]


def test_ksem_has_alignment_cases(ksem_units):
    count = sum(len(_alignment_pairs(ascii_tokens(u.text))) for u in ksem_units)
    assert count > 100


def test_ksem_each_aligned_line_stays_below_the_same_token(ksem_units):
    """The independent check of the rule: in ASCII, a line starts below a token
    of the line above. In Unicode, the line starts below the same token."""
    for unit in ksem_units:
        ascii_lines = ascii_tokens(unit.text)
        uni_lines = unicode_tokens(unit.text)
        assert len(ascii_lines) == len(uni_lines), unit.name
        for k, p, idx in _alignment_pairs(ascii_lines):
            line_col = _sig(uni_lines[k])[0][0]
            parent_col = _sig(uni_lines[p])[idx][0]
            assert line_col == parent_col, (unit.name, unit.start_line + k)


def test_ksem_each_line_keeps_its_tokens(ksem_units):
    for unit in ksem_units:
        for a_line, u_line in zip(ascii_tokens(unit.text), unicode_tokens(unit.text)):
            a_sig = [(t, v) for _, t, v in _sig(a_line)]
            u_sig = [(t, v) for _, t, v in _sig(u_line)]
            assert [t for t, _ in a_sig] == [t for t, _ in u_sig]
            for (t, a), (_, u) in zip(a_sig, u_sig):
                if t in Comment:
                    assert a == u


def test_ksem_junction_bullets_stay_in_one_column(ksem_units):
    give = next(u for u in ksem_units if u.name == "Take")
    out = to_unicode(give.text).split("\n")
    # The three disjuncts of Take, and their first conjuncts.
    disjuncts = [ln for ln in out if "∨ ∧" in ln]
    assert len(disjuncts) == 3
    assert len({ln.index("∨") for ln in disjuncts}) == 1
    assert len({ln.index("∨ ∧") for ln in disjuncts}) == 1


TAKE_UNICODE = """\
Take(a, to) ≜
    ∧ initialized
    ∧ CanCall(a)
    ∧ a = Isr ⇒ to = "NO_WAIT"
    ∧ ∨ ∧ count > 0
        ∧ count′ = count - 1
        ∧ tokens′ = tokens - 1
        ∧ obs′ = [NoObs EXCEPT !.actor = a, !.op = "take", !.timeout = to,
                               !.release = "unlock", !.ret = OK]
        ∧ UNCHANGED ⟨initialized, limit, waitq, pc, tmo, swapRet⟩
      ∨ ∧ count = 0
        ∧ to = "NO_WAIT"
        ∧ obs′ = [NoObs EXCEPT !.actor = a, !.op = "take", !.timeout = to,
                               !.release = "unlock", !.ret = EBUSY]
        ∧ UNCHANGED ⟨initialized, count, limit, waitq, pc, tmo, swapRet, tokens⟩
      ∨ ∧ count = 0
        ∧ to ≠ "NO_WAIT"
        ∧ IF PendAtomic
            THEN ∧ waitq′ = Enqueue(waitq, a)
                 ∧ pc′ = [pc EXCEPT ![a] = "waiting"]
            ELSE ∧ waitq′ = waitq
                 ∧ pc′ = [pc EXCEPT ![a] = "pending"]
        ∧ tmo′ = [tmo EXCEPT ![a] = to]
        ∧ obs′ = [NoObs EXCEPT !.actor = a, !.op = "take", !.timeout = to,
                               !.release = "pend"]
        ∧ UNCHANGED ⟨initialized, count, limit, swapRet, tokens⟩"""


def test_ksem_take_renders_as_pinned(ksem_units):
    take = next(u for u in ksem_units if u.name == "Take")
    assert to_unicode(take.text) == TAKE_UNICODE
