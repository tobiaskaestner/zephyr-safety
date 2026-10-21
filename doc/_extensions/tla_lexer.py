# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""A Pygments lexer for TLA+.

Pygments has no lexer for TLA+. This module gives one. It reads the ASCII
syntax and the Unicode syntax of the TLA+ standard (the symbols of tlauc).

The lexer marks these parts of a module:

- The module header (``---- MODULE Name ----``), the separator lines
  (``----``) and the module footer (``====``).
- Line comments (``\\*``) and block comments (``(* *)``). Block comments can
  be nested. A PlusCal algorithm (``(* --algorithm ... *)``) is lexed as code,
  with the PlusCal keywords.
- Keywords, ``WF_`` and ``SF_``, the operators in ASCII and Unicode,
  strings and numbers.
- The name of a top-level definition (a name at column 0 before ``==``,
  ``(`` or ``[``) gets the token type ``Name.Function``.

In Sphinx, ``tla_domain`` registers the lexer for the names ``tla`` and
``tlaplus``. It also registers ``tla-unicode``: this lexer shows ASCII source
in the Unicode syntax (see ``tla_unicode``).
"""

import re

from pygments.lexer import RegexLexer, bygroups, include, words
from pygments.token import (
    Comment,
    Keyword,
    Name,
    Number,
    Operator,
    Punctuation,
    String,
    Text,
    Whitespace,
)

__all__ = ["TLALexer", "KEYWORDS", "ASCII_OPERATORS", "UNICODE_OPERATORS"]

#: The reserved words of TLA+ (with the proof language).
KEYWORDS = (
    "ACTION", "ASSUME", "ASSUMPTION", "AXIOM", "BY", "CASE", "CHOOSE",
    "CONSTANT", "CONSTANTS", "COROLLARY", "DEF", "DEFINE", "DEFS", "DOMAIN",
    "ELSE", "ENABLED", "EXCEPT", "EXTENDS", "HAVE", "HIDE", "IF", "IN",
    "INSTANCE", "LAMBDA", "LEMMA", "LET", "LOCAL", "MODULE", "NEW",
    "OBVIOUS", "OMITTED", "ONLY", "OTHER", "PICK", "PROOF", "PROPOSITION",
    "PROVE", "QED", "RECURSIVE", "STATE", "SUBSET", "SUFFICES", "TAKE",
    "TEMPORAL", "THEN", "THEOREM", "UNCHANGED", "UNION", "USE", "VARIABLE",
    "VARIABLES", "WITH", "WITNESS",
)  # fmt: skip

#: The keywords of PlusCal (only inside ``(* --algorithm ... *)``).
PLUSCAL_KEYWORDS = (
    "algorithm", "assert", "await", "begin", "call", "define", "do",
    "either", "else", "elsif", "end", "fair", "goto", "if", "macro", "or",
    "print", "procedure", "process", "return", "skip", "then", "variable",
    "variables", "when", "while", "with",
)  # fmt: skip

#: The ASCII operators. The lexer tries the longest operator first.
ASCII_OPERATORS = (
    "<=>", "-+->", "|->", "::=", "...", "(\\X)", "(+)", "(-)", "(.)", "(/)",
    "/\\", "\\/", "==", "=>", "=<", "<=", ">=", "/=", "<<", ">>", "[]",
    "<>", "~>", "->", "<-", ":=", "::", "..", "||", "!!", "??", "|-", "-|",
    "|=", "=|", "^+", "^*", "^#", "++", "--", "**", "//", "^^", "&&", "@@",
    ":>", "<:", "%%", "$$", "##", "-.", "#", "=", "<", ">", "+", "-", "*",
    "/", "^", "~", "'", "%", "&", "|", "$", "\\",
)  # fmt: skip

#: The Unicode operators of the TLA+ standard (tlauc).
UNICODE_OPERATORS = "≜∈←∀∃↦→⟨⟩□∷¬◇⇒⇸≡⇔↝∧∨≔⩴≠≤≥≈⊢⊨⊣⫤≍≅≐≫≪∉≺≻⪯⪰∝∼≃⊏⊐⊑⊒⊂⊃⊆⊇∩∪‥…⊕⊖‖⊙⊘⊗◯●÷∘⋆‼⁇⊓⊔⊎×≀⋅⁺′"

_NAME = r"[A-Za-z0-9_]*[A-Za-z_][A-Za-z0-9_]*"
_KEYWORD_ALT = "|".join(KEYWORDS)


def _operator_regex():
    ordered = sorted(ASCII_OPERATORS, key=len, reverse=True)
    return "|".join(re.escape(op) for op in ordered)


class TLALexer(RegexLexer):
    """Lexer for TLA+ modules, in ASCII or Unicode syntax."""

    name = "TLA+"
    aliases = ["tla", "tlaplus"]
    filenames = ["*.tla"]
    mimetypes = ["text/x-tlaplus"]
    url = "https://lamport.azurewebsites.net/tla/tla.html"
    flags = re.MULTILINE

    tokens = {
        "root": [
            # The module header, the module footer and the separator lines.
            (
                r"^(\s*)(-{4,})(\s*)(MODULE)(\s+)(" + _NAME + r")(\s*)(-{4,})",
                bygroups(
                    Whitespace,
                    Punctuation,
                    Whitespace,
                    Keyword.Namespace,
                    Whitespace,
                    Name.Namespace,
                    Whitespace,
                    Punctuation,
                ),
            ),
            (r"^\s*={4,}", Punctuation),
            (r"^\s*-{4,}", Punctuation),
            # A top-level definition: a name at column 0, not a keyword.
            (
                r"^(LOCAL)(\s+)(?!(?:" + _KEYWORD_ALT + r")\b)(" + _NAME + r")"
                r"(?=\s*(?:\(|\[|==|≜))",
                bygroups(Keyword, Whitespace, Name.Function),
            ),
            (
                r"^(?!(?:" + _KEYWORD_ALT + r")\b)(" + _NAME + r")(?=\s*(?:\(|\[|==|≜))",
                Name.Function,
            ),
            include("code"),
        ],
        "code": [
            (r"\s+", Whitespace),
            (r"\\\*.*?$", Comment.Single),
            (r"\(\*(?=\s*--(?:fair\s+)?algorithm\b)", Comment.Multiline, "pluscal"),
            (r"\(\*", Comment.Multiline, "comment"),
            (r'"(?:[^"\\\n]|\\.)*"', String),
            (r"\\[bB][01]+\b", Number.Bin),
            (r"\\[oO][0-7]+\b", Number.Oct),
            (r"\\[hH][0-9a-fA-F]+\b", Number.Hex),
            (r"\d+\.\d+\b", Number.Float),
            (r"\d+(?![A-Za-z_])", Number.Integer),
            (r"\b(WF|SF)(_)", bygroups(Keyword, Punctuation)),
            (words(("TRUE", "FALSE"), prefix=r"\b", suffix=r"\b"), Keyword.Constant),
            (words(("BOOLEAN", "STRING"), prefix=r"\b", suffix=r"\b"), Keyword.Type),
            (words(KEYWORDS, prefix=r"\b", suffix=r"\b"), Keyword),
            # A subscript after ] or >> (as in [][Next]_vars or <<A>>_vars).
            (r"(?<=[\]>⟩])_", Punctuation),
            (r"\\(?:AA|EE|A|E)\b", Operator.Word),
            (r"\\[A-Za-z]+", Operator.Word),
            (_operator_regex(), Operator),
            (r"[" + UNICODE_OPERATORS + r"]", Operator),
            (r"[ℕℤℝ]", Name.Builtin),
            (r"!", Punctuation),
            (r"@", Name.Builtin),
            (_NAME, Name),
            (r"[\[\](){},.:;]", Punctuation),
            (r".", Text),
        ],
        "comment": [
            (r"[^(*]+", Comment.Multiline),
            (r"\(\*", Comment.Multiline, "#push"),
            (r"\*\)", Comment.Multiline, "#pop"),
            (r"[(*]", Comment.Multiline),
        ],
        "pluscal": [
            (r"\*\)", Comment.Multiline, "#pop"),
            (r"--(?:fair\s+)?algorithm\b", Keyword),
            (words(PLUSCAL_KEYWORDS, prefix=r"\b", suffix=r"\b"), Keyword),
            include("code"),
        ],
    }
