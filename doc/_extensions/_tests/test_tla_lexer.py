# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""tla_lexer: the Pygments lexer for TLA+."""

import pytest
from pygments.token import Comment, Error, Keyword, Name, Number, Operator, Punctuation, String

from tla_lexer import TLALexer


def tokens(text):
    lexer = TLALexer(stripnl=False, ensurenl=False)
    return [(t, v) for t, v in lexer.get_tokens(text) if v.strip()]


def kind_of(text, value):
    for ttype, v in tokens(text):
        if v == value:
            return ttype
    raise AssertionError(f"{value!r} not in {tokens(text)}")


@pytest.mark.parametrize(
    "word",
    [
        "EXTENDS", "CONSTANT", "CONSTANTS", "VARIABLE", "VARIABLES", "ASSUME",
        "THEOREM", "LET", "IN", "IF", "THEN", "ELSE", "CASE", "OTHER", "CHOOSE",
        "EXCEPT", "UNCHANGED", "ENABLED", "SUBSET", "UNION", "DOMAIN",
        "INSTANCE", "WITH", "LOCAL", "RECURSIVE", "LAMBDA",
    ],
)  # fmt: skip
def test_a_keyword_is_a_keyword(word):
    assert kind_of(f"  x {word} y", word) in Keyword


@pytest.mark.parametrize("prefix", ["WF", "SF"])
def test_fairness_prefix_is_a_keyword_and_the_subscript_a_name(prefix):
    toks = tokens(f"  {prefix}_vars(Next)")
    assert toks[0] == (Keyword, prefix)
    assert toks[1] == (Punctuation, "_")
    assert toks[2] == (Name, "vars")


@pytest.mark.parametrize(
    "op",
    ["/\\", "\\/", "==", "=>", "<=>", "|->", "->", "~>", "<<", ">>", "[]", "<>",
     "\\in", "\\notin", "\\subseteq", "\\cup", "\\X", "#", "/=", "=<", ">=", "~", "'",
     "..", "\\o", "@@", ":>"],
)  # fmt: skip
def test_an_ascii_operator_is_one_operator_token(op):
    toks = tokens(f"  a {op} b")
    assert toks[1] == (toks[1][0], op)
    assert toks[1][0] in Operator


@pytest.mark.parametrize("op", list("∧∨≜∀∃□◇′∈∉≠⟨⟩⇒⇔∪∩⊆×↦→↝≤≥¬∘"))
def test_a_unicode_operator_is_an_operator(op):
    assert kind_of(f"  a {op} b", op) in Operator


def test_the_unicode_number_sets_are_builtin_names():
    assert kind_of("  x ∈ ℕ", "ℕ") in Name.Builtin


def test_strings_and_numbers():
    assert kind_of('  x = "a == \\" b"', '"a == \\" b"') in String
    assert kind_of("  x = 42", "42") in Number
    assert kind_of("  x = 3.14", "3.14") in Number
    assert kind_of("  x = \\b1010", "\\b1010") in Number
    assert kind_of("  x = \\hFF", "\\hFF") in Number
    assert kind_of("  x = \\o17", "\\o17") in Number


def test_a_range_is_not_a_float():
    toks = tokens("  0..UMax")
    assert toks[0] == (Number.Integer, "0")
    assert toks[1] == (Operator, "..")


def test_line_comment():
    assert kind_of("  x == 1 \\* a == comment", "\\* a == comment") in Comment.Single


def test_nested_block_comment_is_one_comment():
    text = "(* a (* b *) c == *) X"
    lexer = TLALexer(stripnl=False, ensurenl=False)
    toks = list(lexer.get_tokens(text))
    comment = "".join(v for t, v in toks if t in Comment)
    assert comment == "(* a (* b *) c == *)"
    assert (Name, "X") in toks


def test_block_comment_over_lines():
    toks = tokens("(* line 1\n   line 2 *)\nX == 1")
    assert toks[0][0] in Comment.Multiline
    assert (Name.Function, "X") in toks


def test_module_header_and_footer():
    text = "---- MODULE KSem ----\nEXTENDS TLC\n----\nX == 1\n===="
    toks = tokens(text)
    assert toks[:4] == [
        (Punctuation, "----"),
        (Keyword.Namespace, "MODULE"),
        (Name.Namespace, "KSem"),
        (Punctuation, "----"),
    ]
    assert toks[-1] == (Punctuation, "====")
    assert (Punctuation, "----") in toks[4:]


def test_a_definition_head_at_column_0_is_a_function_name():
    assert kind_of("Give(a) == TRUE", "Give") is Name.Function
    assert kind_of("Spec == Init", "Spec") is Name.Function
    assert kind_of("f[x \\in S] == x", "f") is Name.Function
    assert kind_of("LOCAL Helper(n) == n", "Helper") is Name.Function
    assert kind_of("  Give(a)", "Give") is Name


def test_a_keyword_at_column_0_is_not_a_function_name():
    assert kind_of("ASSUME (x)", "ASSUME") in Keyword


def test_pluscal_is_code_inside_the_comment():
    text = "(* --algorithm C\nvariables y = 0;\nbegin\n  y := 1;\nend algorithm; *)"
    toks = tokens(text)
    assert (Keyword, "--algorithm") in toks
    assert (Keyword, "variables") in toks
    assert (Operator, ":=") in toks
    assert toks[-1] == (Comment.Multiline, "*)")


def test_the_ksem_copy_lexes_without_errors_and_round_trips(ksem_copy):
    text = ksem_copy.read_text()
    lexer = TLALexer(stripnl=False, ensurenl=False)
    toks = list(lexer.get_tokens(text))
    assert not [v for t, v in toks if t in Error]
    assert "".join(v for _, v in toks) == text


def test_the_lexer_names():
    assert set(TLALexer.aliases) == {"tla", "tlaplus"}
