# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Read a TLA+ module and split it into units (definitions, declarations).

``parse_module(text)`` returns a ``Module``. It does not run SANY. It finds
the parts of the module from the layout of the lines and from the tokens of
``tla_lexer``.

Extent rule
-----------

Only the text between the module header (``---- MODULE Name ----``) and the
module footer (``====``) is read. A line "starts at column 0" if its first
character is not a space and the line does not start inside a block comment.

1. A unit starts at a line that starts at column 0 with code: a definition,
   ``EXTENDS``, ``CONSTANT(S)``, ``VARIABLE(S)``, ``ASSUME``, ``THEOREM``
   (and the other proof keywords), ``INSTANCE``, ``LOCAL`` or
   ``RECURSIVE``.
2. The unit ends before the next line that starts at column 0: the next
   unit, a comment at column 0 (``\\*`` or ``(*``), a separator line
   (``----``), a nested module or the module footer. Blank lines at the end
   of a unit are not part of it.
3. Lines with indentation belong to the unit above them. This includes the
   indented comments in a definition body.
4. A definition is a unit with ``==`` outside brackets. The text before the
   first ``==`` is the head. The head gives the name:

   - ``Name``, ``Name(p, q)`` or ``Name[x \\in S]``: the name is ``Name``.
   - ``a OP b``: an infix definition, the name is ``OP``.
   - ``OP a`` (prefix) or ``a OP`` (postfix): the name is ``OP``.
   - ``LOCAL`` before the head makes the definition local.
   - If the first word after ``==`` is ``INSTANCE``, the definition is an
     instance (``W == INSTANCE M WITH ...``).

5. A ``RECURSIVE`` declaration belongs to the next definition of a name that
   it declares. That definition shows the declaration as its first line.

Doc comment
-----------

The comment lines at column 0 directly above a unit (no blank line between)
are its doc comment. This is a block of ``\\*`` lines, or a ``(* *)`` block
(also a box of ``(* ... *)`` lines). The comment markers are removed and the
text is dedented. A comment at column 0 that is not directly above a unit is
a section comment (for example ``(* Helpers *)`` after a ``----`` line).

A line of the doc comment that starts with ``@`` is a tag, not prose::

    \\* @expresses ZEP-SRS-5-3
    \\* @kind invariant
    \\* @c-function z_impl_k_sem_give
    \\* @expected violation

A tag can occur more than one time. The tags are in ``Unit.tags`` (tag name
-> list of values, in order).

The doc comment of the ``EXTENDS`` unit, or else the first comment directly
after the module header, is the doc comment of the module.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from pygments.token import Comment, Keyword, Name, Operator, Punctuation, String, Whitespace

from tla_lexer import TLALexer

__all__ = ["Module", "Unit", "TLAParseError", "parse_module", "parse_file"]

#: Keywords that start a unit at column 0, and the kind of the unit.
_UNIT_KEYWORDS = {
    "EXTENDS": "extends",
    "CONSTANT": "constants",
    "CONSTANTS": "constants",
    "VARIABLE": "variables",
    "VARIABLES": "variables",
    "ASSUME": "assume",
    "ASSUMPTION": "assume",
    "AXIOM": "assume",
    "THEOREM": "theorem",
    "LEMMA": "theorem",
    "PROPOSITION": "theorem",
    "COROLLARY": "theorem",
    "INSTANCE": "instance",
    "RECURSIVE": "recursive",
    "USE": "proof",
    "HIDE": "proof",
}

_HEADER = re.compile(r"^\s*-{4,}\s*MODULE\s+(\w+)\s*-{4,}\s*$")
_FOOTER = re.compile(r"^\s*={4,}\s*$")
_SEPARATOR = re.compile(r"^-{4,}\s*$")
_TAG = re.compile(r"^@([A-Za-z][\w-]*)\s*(.*?)\s*$")
_RULE = re.compile(r"^[\s*=\-]*$")
_PLUSCAL = re.compile(r"^\(\*\s*--(?:fair\s+)?algorithm\b")


class TLAParseError(ValueError):
    """The text has no module header or no module footer."""


@dataclass
class Unit:
    """One part of a module: a definition, a declaration or a comment."""

    #: definition, extends, constants, variables, assume, theorem, instance,
    #: recursive, proof, comment, pluscal (an algorithm in a comment), other
    kind: str
    #: The source text of the unit (without its doc comment).
    text: str
    #: First and last line of ``text`` in the file (1-based).
    start_line: int
    end_line: int
    #: The defined name (definitions, named theorems), else None.
    name: str | None = None
    #: The head of a definition (the text before ``==``).
    head: str = ""
    #: The parameters of a definition.
    params: list[str] = field(default_factory=list)
    #: True for ``Name(p) == ...`` and ``Name == ...``. False for infix,
    #: prefix, postfix and function definitions.
    plain_head: bool = True
    local: bool = False
    instance: bool = False
    #: The names that a declaration declares (EXTENDS, CONSTANTS, VARIABLES,
    #: RECURSIVE).
    names: list[str] = field(default_factory=list)
    #: The prose of the doc comment (tags removed), or "".
    doc: str = ""
    #: The file line of each line of ``doc``.
    doc_lines: list[int] = field(default_factory=list)
    tags: dict[str, list[str]] = field(default_factory=dict)
    #: The line of each tag, for messages: list of (tag, value, line).
    tag_lines: list[tuple[str, str, int]] = field(default_factory=list)
    #: A RECURSIVE declaration for this definition, else "".
    recursive: str = ""


@dataclass
class Module:
    name: str
    path: str | None
    extends: list[str]
    constants: list[str]
    variables: list[str]
    units: list[Unit]
    doc: str = ""
    doc_lines: list[int] = field(default_factory=list)
    header_line: int = 0
    footer_line: int = 0

    def definitions(self):
        return [u for u in self.units if u.kind == "definition"]

    def definition(self, name):
        """The definition ``name``, else None."""
        for unit in self.units:
            if unit.kind == "definition" and unit.name == name:
                return unit
        return None

    def declarations(self):
        """The EXTENDS, CONSTANTS and VARIABLES units, in source order."""
        return [u for u in self.units if u.kind in ("extends", "constants", "variables")]


# -- Lines ---------------------------------------------------------------------


def _lex(text):
    return list(TLALexer(stripnl=False, ensurenl=False).get_tokens_unprocessed(text))


def _block_comment_spans(text):
    """The (start, end) offsets of the block comments (nested ones in one span).

    The scan skips strings and line comments. A PlusCal algorithm is a block
    comment too.
    """
    spans = []
    i, n = 0, len(text)
    while i < n:
        if text.startswith("\\*", i):
            j = text.find("\n", i)
            i = n if j < 0 else j
        elif text[i] == '"':
            i += 1
            while i < n and text[i] not in '"\n':
                i += 2 if text[i] == "\\" else 1
            i += 1
        elif text.startswith("(*", i):
            start, depth = i, 1
            i += 2
            while i < n and depth:
                if text.startswith("(*", i):
                    depth += 1
                    i += 2
                elif text.startswith("*)", i):
                    depth -= 1
                    i += 2
                else:
                    i += 1
            spans.append((start, i))
        else:
            i += 1
    return spans


def _comment_starts(text, offsets):
    """The offsets of the lines that start inside a block comment."""
    inside = set()
    spans = _block_comment_spans(text)
    k = 0
    for off in offsets:
        while k < len(spans) and spans[k][1] <= off:
            k += 1
        if k < len(spans) and spans[k][0] < off < spans[k][1]:
            inside.add(off)
    return inside


def _significant(tokens):
    return [(t, v) for t, v in tokens if t not in Whitespace and t not in Comment]


def parse_file(path):
    path = Path(path)
    return parse_module(path.read_text(encoding="utf-8"), path=str(path))


def parse_module(text, path=None):
    """Parse the TLA+ module in ``text``. Return a ``Module``."""
    text = text.expandtabs(8)
    lines = text.split("\n")
    header = footer = None
    name = None
    depth = 0
    for idx, line in enumerate(lines):
        m = _HEADER.match(line)
        if m:
            if header is None:
                header, name = idx, m.group(1)
            depth += 1
        elif _FOOTER.match(line) and header is not None:
            depth -= 1
            if depth == 0:
                footer = idx
                break
    if header is None:
        raise TLAParseError(f"{path or 'text'}: no module header (---- MODULE Name ----)")
    if footer is None:
        raise TLAParseError(f"{path or 'text'}: no module footer (====) for module {name}")

    tokens = _lex(text)
    offsets = []
    off = 0
    for line in lines:
        offsets.append(off)
        off += len(line) + 1
    inside = _comment_starts(text, offsets)

    # Classify the body lines.
    kinds = {}  # line index -> "blank" | "cont" | "comment" | "sep" | "code" | "nested"
    nested = 0
    for idx in range(header + 1, footer):
        line = lines[idx]
        if nested:
            kinds[idx] = "nested"
            if _HEADER.match(line):
                nested += 1
            elif _FOOTER.match(line):
                nested -= 1
            continue
        if not line.strip():
            kinds[idx] = "blank"
        elif offsets[idx] in inside or line[0] in " \t":
            kinds[idx] = "cont"
        elif _HEADER.match(line):
            kinds[idx] = "nested"
            nested = 1
        elif _SEPARATOR.match(line):
            kinds[idx] = "sep"
        elif line.startswith("\\*") or line.startswith("(*"):
            kinds[idx] = "comment"
        else:
            kinds[idx] = "code"

    # Group the lines. A comment group: consecutive comment lines, with the
    # continuation lines of a block comment. A code group: a code line and
    # the lines after it up to the next line at column 0.
    groups = []  # (kind, first, last)
    idx = header + 1
    while idx < footer:
        kind = kinds[idx]
        if kind == "comment":
            first = idx
            idx += 1
            while idx < footer and (
                kinds[idx] == "comment" or (kinds[idx] == "cont" and offsets[idx] in inside)
            ):
                idx += 1
            groups.append(("comment", first, idx - 1))
        elif kind == "code":
            first = idx
            idx += 1
            while idx < footer and kinds[idx] in ("cont", "blank"):
                idx += 1
            last = idx - 1
            while last > first and kinds[last] == "blank":
                last -= 1
            groups.append(("code", first, last))
        else:
            if kind in ("sep", "nested"):
                groups.append((kind, idx, idx))
            idx += 1

    units = []
    module_doc, module_doc_lines = "", []
    pending = None  # a comment group directly above the current line
    for kind, first, last in groups:
        if kind == "comment":
            if pending is not None:
                units.append(_comment_unit(lines, *pending))
                pending = None
            if _PLUSCAL.match(lines[first]):
                units.append(
                    Unit(
                        kind="pluscal",
                        text="\n".join(lines[first : last + 1]),
                        start_line=first + 1,
                        end_line=last + 1,
                    )
                )
                continue
            pending = (first, last)
            continue
        if kind != "code":
            if pending is not None:
                units.append(_comment_unit(lines, *pending))
                pending = None
            continue
        unit = _code_unit(lines, first, last, tokens, offsets)
        if pending is not None:
            c_first, c_last = pending
            if c_last == first - 1:
                _attach_doc(unit, lines, c_first, c_last)
            else:
                units.append(_comment_unit(lines, c_first, c_last))
            pending = None
        units.append(unit)
    if pending is not None:
        units.append(_comment_unit(lines, *pending))

    _attach_recursive(units)

    extends, constants, variables = [], [], []
    for unit in units:
        if unit.kind == "extends":
            extends += unit.names
            if unit.doc and not module_doc:
                module_doc, module_doc_lines = unit.doc, unit.doc_lines
        elif unit.kind == "constants":
            constants += unit.names
        elif unit.kind == "variables":
            variables += unit.names
    if not module_doc and groups and groups[0][0] == "comment" and groups[0][1] == header + 1:
        first_comment = next((u for u in units if u.kind == "comment" or u.doc), None)
        if first_comment is not None:
            module_doc = first_comment.doc
            module_doc_lines = first_comment.doc_lines

    return Module(
        name=name,
        path=path,
        extends=extends,
        constants=constants,
        variables=variables,
        units=units,
        doc=module_doc,
        doc_lines=module_doc_lines,
        header_line=header + 1,
        footer_line=footer + 1,
    )


# -- Comments ------------------------------------------------------------------


def comment_text(raw_lines, first_line):
    """Remove the comment markers. Return (list of text lines, file lines)."""
    out = []
    box = all(re.match(r"^\s*\(\*.*\*\)\s*$", ln) for ln in raw_lines if ln.strip()) and raw_lines[
        0
    ].lstrip().startswith("(*")
    in_block = False
    for k, raw in enumerate(raw_lines):
        line_no = first_line + k
        s = raw.rstrip()
        opener = False
        if box:
            s = re.sub(r"^\s*\(\*", "", s)
            s = re.sub(r"\*\)$", "", s)
            if _RULE.match(s) and s.strip():
                continue
        elif not in_block and s.startswith("\\*"):
            s = s[2:]
            if _RULE.match(s) and s.strip():
                continue
        else:
            if not in_block and s.lstrip().startswith("(*"):
                # The text after "(*" on the first line of a block. The
                # dedent below does not use this line.
                s = s.lstrip()[2:].lstrip()
                in_block = opener = True
            if in_block and s.endswith("*)"):
                s = s[:-2]
                in_block = False
            if _RULE.match(s) and s.strip():
                continue
        out.append((s.rstrip(), line_no, opener))
    # Dedent: remove the common leading spaces of the lines with text.
    indents = [len(s) - len(s.lstrip(" ")) for s, _, op in out if s.strip() and not op]
    cut = min(indents) if indents else 0
    out = [((s if op else s[cut:]) if s.strip() else "", n) for s, n, op in out]
    while out and not out[0][0]:
        out.pop(0)
    while out and not out[-1][0]:
        out.pop()
    return [s for s, _ in out], [n for _, n in out]


def _split_tags(text_lines, line_nos):
    prose, prose_lines, tags, tag_lines = [], [], {}, []
    for s, n in zip(text_lines, line_nos):
        m = _TAG.match(s.strip()) if s.strip().startswith("@") else None
        if m:
            tags.setdefault(m.group(1), []).append(m.group(2))
            tag_lines.append((m.group(1), m.group(2), n))
        else:
            prose.append(s)
            prose_lines.append(n)
    while prose and not prose[-1].strip():
        prose.pop()
        prose_lines.pop()
    return prose, prose_lines, tags, tag_lines


def _attach_doc(unit, lines, first, last):
    text_lines, line_nos = comment_text(lines[first : last + 1], first + 1)
    prose, prose_lines, tags, tag_lines = _split_tags(text_lines, line_nos)
    unit.doc = "\n".join(prose)
    unit.doc_lines = prose_lines
    unit.tags = tags
    unit.tag_lines = tag_lines


def _comment_unit(lines, first, last):
    unit = Unit(
        kind="comment",
        text="\n".join(lines[first : last + 1]),
        start_line=first + 1,
        end_line=last + 1,
    )
    _attach_doc(unit, lines, first, last)
    return unit


# -- Code units ----------------------------------------------------------------


def _unit_tokens(tokens, start, end):
    """Tokens (ttype, value) in [start, end) of the text."""
    out = []
    for pos, ttype, value in tokens:
        if pos + len(value) <= start or pos >= end:
            continue
        lo, hi = max(pos, start), min(pos + len(value), end)
        out.append((ttype, value[lo - pos : hi - pos]))
    return out


def _code_unit(lines, first, last, tokens, offsets):
    text = "\n".join(lines[first : last + 1])
    start = offsets[first]
    toks = _unit_tokens(tokens, start, start + len(text))
    sig = _significant(toks)
    unit = Unit(kind="other", text=text, start_line=first + 1, end_line=last + 1)
    if not sig:
        return unit
    head_word = sig[0][1]
    local = False
    if head_word == "LOCAL" and len(sig) > 1:
        local = True
        sig = sig[1:]
        head_word = sig[0][1]
    unit.local = local
    kw = _UNIT_KEYWORDS.get(head_word) if sig[0][0] in Keyword else None
    if kw in ("extends", "constants", "variables", "recursive"):
        unit.kind = kw
        unit.names = _declared_names(sig[1:])
        return unit
    if kw == "instance":
        unit.kind = "instance"
        unit.names = [sig[1][1]] if len(sig) > 1 else []
        return unit
    if kw in ("assume", "theorem", "proof"):
        unit.kind = kw
        if len(sig) > 2 and sig[1][0] in Name and sig[2][1] in ("==", "≜"):
            unit.name = sig[1][1]
        return unit
    # A definition: the first == at bracket depth 0.
    depth = 0
    eq = None
    for k, (ttype, value) in enumerate(sig):
        if ttype in Punctuation and value in "([{":
            depth += 1
        elif ttype in Punctuation and value in ")]}":
            depth -= 1
        elif ttype in Operator and value in ("==", "≜") and depth == 0:
            eq = k
            break
    if eq is None or eq == 0:
        return unit
    head = sig[:eq]
    body = sig[eq + 1 :]
    name, params, plain = _head_name(head)
    if name is None:
        return unit
    unit.kind = "definition"
    unit.name = name
    unit.params = params
    unit.plain_head = plain
    unit.instance = bool(body) and body[0][1] == "INSTANCE"
    # The head as text: from the first significant token to the "==".
    head_text = text
    m = re.search(r"==|≜", head_text)
    unit.head = re.sub(r"\s+", " ", _strip_comments(head_text[: m.start()] if m else "")).strip()
    if local:
        unit.head = re.sub(r"^LOCAL\s+", "", unit.head)
    return unit


def _strip_comments(text):
    return re.sub(r"\\\*.*$", "", text, flags=re.M)


def _head_name(head):
    """(name, params, plain) of a definition head, else (None, [], False)."""
    first_t, first_v = head[0]
    if first_t in Name and (len(head) == 1 or head[1][1] in ("(", "[")):
        params = []
        if len(head) > 1:
            depth = 0
            expect = True
            for ttype, value in head[2:]:
                if value in ("(", "["):
                    depth += 1
                elif value in (")", "]"):
                    if depth == 0:
                        break
                    depth -= 1
                elif value == "," and depth == 0:
                    expect = True
                elif expect and ttype in Name and depth == 0:
                    params.append(value)
                    expect = False
        plain = len(head) == 1 or head[1][1] == "("
        return first_v, params, plain
    if len(head) == 3 and head[0][0] in Name and head[2][0] in Name and head[1][0] in Operator:
        return head[1][1], [head[0][1], head[2][1]], False
    if len(head) == 2 and head[0][0] in Operator and head[1][0] in Name:
        return head[0][1], [head[1][1]], False
    if len(head) == 2 and head[0][0] in Name and head[1][0] in Operator:
        return head[1][1], [head[0][1]], False
    return None, [], False


def _declared_names(sig):
    """The names at depth 0 of a declaration, before each comma."""
    names = []
    depth = 0
    expect = True
    for ttype, value in sig:
        if ttype in Punctuation and value in "([{":
            depth += 1
        elif ttype in Punctuation and value in ")]}":
            depth -= 1
        elif depth == 0 and value == ",":
            expect = True
        elif depth == 0 and expect and (ttype in Name or ttype in Operator) and ttype not in String:
            if ttype in Name:
                names.append(value)
                expect = False
    return names


def _attach_recursive(units):
    """Give a RECURSIVE declaration to the next definition of its names."""
    for k, unit in enumerate(units):
        if unit.kind != "recursive":
            continue
        for later in units[k + 1 :]:
            if later.kind == "definition" and later.name in unit.names and not later.recursive:
                later.recursive = unit.text
                if not later.doc and not later.tags and unit.doc:
                    later.doc, later.doc_lines = unit.doc, unit.doc_lines
                    later.tags, later.tag_lines = unit.tags, unit.tag_lines
                break
