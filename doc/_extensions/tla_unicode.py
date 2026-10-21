# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""ASCII to Unicode rendering of TLA+ source.

The mapping is the table of the TLA+ Unicode standard, as the tool tlauc
uses it (https://codeberg.org/tlaplus/tlauc, ``resources/tla-unicode.csv``).
One addition: the prime ``'`` becomes ``′`` (U+2032). tlauc keeps the ASCII
prime. Set ``prime=False`` to keep it too.

The conversion is token-aware. It uses ``tla_lexer.TLALexer``, and it changes
only operator tokens and the names ``Nat``, ``Int`` and ``Real``. It does not
change comments or strings.

Alignment rule
--------------

TLA+ uses the indentation of a line to find the structure. The bullets of a
conjunction list (``/\\``) or a disjunction list (``\\/``) are in one column,
and the next lines of a bullet are to the right of the bullet. A Unicode
symbol is shorter than its ASCII form (``/\\`` is 2 columns, ``∧`` is 1). Thus
the conversion moves text to the left, and the columns of the lines below do
not agree any more.

The rule ``relative`` (the default) keeps the structure:

1. Each symbol takes the width of its Unicode form (1 column for each symbol
   of the table; ``unicodedata`` wide characters take 2 columns).
2. For each line, find the parent line: the nearest line above it that is not
   blank and has the same or a smaller indentation.
3. If the parent has the same indentation, the line gets the new indentation
   of the parent. Thus the bullets of a list stay in one column.
4. If the parent has a smaller indentation, the line starts below the same
   character of the parent as in ASCII. Thus a line below ``IF`` stays below
   ``IF``, and the bullets below ``LET`` stay below ``LET``. If the line
   starts to the right of the end of the parent, it keeps its distance to
   the indentation of the parent (a body below ``Name ==``).
5. Trailing comments that are in one column in ASCII on lines that follow
   each other stay in one column.

The rule ``pad`` keeps each column: each symbol gets spaces after it to the
width of its ASCII form. Use it if the rule ``relative`` gives a wrong
result.
"""

import unicodedata

from pygments.token import Comment, Name, Operator, String, Whitespace

from tla_lexer import TLALexer

__all__ = [
    "ASCII_TO_UNICODE",
    "NAME_TO_UNICODE",
    "TLAUnicodeLexer",
    "ascii_tokens",
    "to_unicode",
    "unicode_tokens",
    "width",
]

#: Operator token (ASCII) -> Unicode, from tlauc's tla-unicode.csv.
ASCII_TO_UNICODE = {
    "==": "≜",
    "\\in": "∈",
    "<-": "←",
    "\\A": "∀",
    "\\forall": "∀",
    "\\E": "∃",
    "\\exists": "∃",
    "|->": "↦",
    "->": "→",
    "<<": "⟨",
    ">>": "⟩",
    "[]": "□",
    "::": "∷",
    "~": "¬",
    "\\lnot": "¬",
    "\\neg": "¬",
    "<>": "◇",
    "=>": "⇒",
    "-+->": "⇸",
    "\\equiv": "≡",
    "<=>": "⇔",
    "~>": "↝",
    "/\\": "∧",
    "\\land": "∧",
    "\\/": "∨",
    "\\lor": "∨",
    ":=": "≔",
    "::=": "⩴",
    "/=": "≠",
    "#": "≠",
    "<=": "≤",
    "=<": "≤",
    "\\leq": "≤",
    ">=": "≥",
    "\\geq": "≥",
    "\\approx": "≈",
    "|-": "⊢",
    "|=": "⊨",
    "-|": "⊣",
    "=|": "⫤",
    "\\asymp": "≍",
    "\\cong": "≅",
    "\\doteq": "≐",
    "\\gg": "≫",
    "\\ll": "≪",
    "\\notin": "∉",
    "\\prec": "≺",
    "\\succ": "≻",
    "\\preceq": "⪯",
    "\\succeq": "⪰",
    "\\propto": "∝",
    "\\sim": "∼",
    "\\simeq": "≃",
    "\\sqsubset": "⊏",
    "\\sqsupset": "⊐",
    "\\sqsubseteq": "⊑",
    "\\sqsupseteq": "⊒",
    "\\subset": "⊂",
    "\\supset": "⊃",
    "\\subseteq": "⊆",
    "\\supseteq": "⊇",
    "\\intersect": "∩",
    "\\cap": "∩",
    "\\union": "∪",
    "\\cup": "∪",
    "..": "‥",
    "...": "…",
    "(+)": "⊕",
    "\\oplus": "⊕",
    "(-)": "⊖",
    "\\ominus": "⊖",
    "||": "‖",
    "(.)": "⊙",
    "\\odot": "⊙",
    "(/)": "⊘",
    "\\oslash": "⊘",
    "(\\X)": "⊗",
    "\\otimes": "⊗",
    "\\bigcirc": "◯",
    "\\bullet": "●",
    "\\div": "÷",
    "\\o": "∘",
    "\\circ": "∘",
    "\\star": "⋆",
    "!!": "‼",
    "??": "⁇",
    "\\sqcap": "⊓",
    "\\sqcup": "⊔",
    "\\uplus": "⊎",
    "\\X": "×",
    "\\times": "×",
    "\\wr": "≀",
    "\\cdot": "⋅",
    "^+": "⁺",
}

#: Names of the standard modules that the table also converts.
NAME_TO_UNICODE = {"Nat": "ℕ", "Int": "ℤ", "Real": "ℝ"}

PRIME = "′"


def width(text):
    """The number of terminal columns of ``text`` (wide characters take 2)."""
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def _convert(ttype, value, prime):
    if ttype in Comment or ttype in String:
        return value
    if ttype in Operator:
        if value == "'":
            return PRIME if prime else value
        return ASCII_TO_UNICODE.get(value, value)
    if ttype in Name and value in NAME_TO_UNICODE:
        return NAME_TO_UNICODE[value]
    return value


def _lines(tokens):
    """Split a token stream into lines of (ttype, value), without newlines."""
    lines = [[]]
    for ttype, value in tokens:
        parts = value.split("\n")
        for k, part in enumerate(parts):
            if k:
                lines.append([])
            if part:
                lines[-1].append((ttype, part))
    return lines


def _lex(text):
    lexer = TLALexer(stripnl=False, ensurenl=False)
    return list(lexer.get_tokens(text.expandtabs(8)))


def _indent(line):
    """ASCII indentation of a line, and the line without it (None if blank)."""
    text = "".join(v for _, v in line)
    if not text.strip():
        return None, []
    n = len(text) - len(text.lstrip(" "))
    rest = []
    skip = n
    for ttype, value in line:
        if skip >= len(value):
            skip -= len(value)
            continue
        rest.append((ttype, value[skip:]))
        skip = 0
    return n, rest


def unicode_tokens(text, *, prime=True, align="relative"):
    """Convert ASCII TLA+ ``text``. Return a list of lines of (ttype, value).

    ``align`` is ``relative`` or ``pad`` (see the module documentation). The
    indentation of a line is a leading ``Whitespace`` token.
    """
    if align not in ("relative", "pad"):
        raise ValueError(f"unknown alignment rule {align!r}")
    out = []
    # Per converted line: ASCII indentation, new indentation, column map.
    info = []
    for line in _lines(_lex(text)):
        indent, rest = _indent(line)
        if indent is None:
            out.append([])
            info.append(None)
            continue
        if align == "pad":
            new_indent = indent
        else:
            new_indent = _new_indent(info, indent)
        colmap = []  # ASCII column (from the indentation) -> new column
        new_line = [(Whitespace, " " * new_indent)] if new_indent else []
        col = new_indent
        trail = _trailing_comment(rest)
        trail_col = indent + sum(len(v) for _, v in rest[:trail]) if trail is not None else None
        for ttype, value in rest:
            conv = _convert(ttype, value, prime)
            w_old, w_new = len(value), width(conv)
            if align == "pad" and w_new < w_old:
                conv += " " * (w_old - w_new)
                w_new = w_old
            for k in range(w_old):
                colmap.append(col + min(k, max(w_new - 1, 0)))
            new_line.append((ttype, conv))
            col += w_new
        colmap.append(col)
        out.append(new_line)
        info.append((indent, new_indent, colmap, trail_col))
    _align_trailing_comments(out, info)
    return out


def _new_indent(info, indent):
    for prev in reversed(info):
        if prev is None:
            continue
        p_indent, p_new, colmap, _ = prev
        if p_indent > indent:
            continue
        if p_indent == indent:
            return p_new
        k = indent - p_indent
        if k < len(colmap) - 1:
            return colmap[k]
        # The line starts to the right of the end of the parent: keep the
        # distance to the indentation of the parent.
        return p_new + k
    return indent


def _trailing_comment(line):
    """Index of a trailing comment token (a comment after code), else None."""
    seen_code = False
    for k, (ttype, _) in enumerate(line):
        if ttype in Comment:
            return k if seen_code and k > 0 and line[k - 1][0] in Whitespace else None
        if ttype not in Whitespace:
            seen_code = True
    return None


def _align_trailing_comments(out, info):
    """Keep trailing comments in one column if they were in one column."""
    group = []  # (line index, ASCII column, new column)

    def flush():
        if len(group) > 1:
            target = max(new for _, _, new in group)
            for idx, _, new in group:
                if new < target:
                    k = _trailing_comment(out[idx])
                    ttype, value = out[idx][k - 1]
                    out[idx][k - 1] = (ttype, value + " " * (target - new))
        group.clear()

    for idx, line in enumerate(out):
        k = _trailing_comment(line) if line else None
        if k is None:
            flush()
            continue
        new_col = sum(width(v) for _, v in line[:k])
        old_col = info[idx][3]
        if group and group[-1][1] != old_col:
            flush()
        group.append((idx, old_col, new_col))
    flush()


def to_unicode(text, *, prime=True, align="relative"):
    """Convert ASCII TLA+ ``text`` to the Unicode syntax. Return a string."""
    lines = unicode_tokens(text, prime=prime, align=align)
    return "\n".join("".join(v for _, v in line).rstrip() for line in lines)


def ascii_tokens(text):
    """The lines of ``text`` as (ttype, value), without a change."""
    return _lines(_lex(text))


class TLAUnicodeLexer(TLALexer):
    """Show ASCII TLA+ in the Unicode syntax (lexer name ``tla-unicode``).

    The lexer converts the text with ``to_unicode()``, then lexes the result.
    Use it in a ``code-block`` that has no links.
    """

    name = "TLA+ (Unicode)"
    aliases = ["tla-unicode"]
    filenames = []
    mimetypes = []

    def get_tokens_unprocessed(self, text, stack=("root",)):
        return super().get_tokens_unprocessed(to_unicode(text), stack)
