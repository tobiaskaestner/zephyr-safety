#!/usr/bin/env python3
# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Doxygen input filter: resolve Kconfig conditionals, annotate what they guard.

Doxygen reads the sources with no Kconfig configuration, so everything under
``#ifdef CONFIG_X`` would drop out of the documentation. This filter evaluates
the conditionals that depend on Kconfig alone under the "feature enabled" rule
and rewrites them in place, so that Doxygen needs no ``#define`` for them:

* ``#ifdef CONFIG_X`` is true, ``#ifndef CONFIG_X`` is false;
* an ``#if`` / ``#elif`` built only from ``defined(CONFIG_*)``,
  ``defined(__DOXYGEN__)``, ``!``, ``&&``, ``||`` and parentheses is evaluated
  with every ``defined()`` true;
* anything else (numeric CONFIG comparisons, other macros, include guards) is
  left to Doxygen and annotates nothing.

An evaluated directive becomes ``#if 1`` / ``#if 0`` / ``#elif 1`` /
``#elif 0`` on the same line. No ``#define`` is emitted, so nothing leaks into
the files Doxygen reads next and the result does not depend on the INPUT order.

Twin rule: when a branch that is not taken holds a ZTEST with its own doc
comment, the whole conditional is opened up (its directive lines blanked) and
every branch stays visible, each annotated with its own condition. A ZTEST
whose body is only ``ztest_test_skip();`` is a stub, not a twin: an
undocumented or documented feature-off stub stays excluded.

Every documented entity inside evaluated conditionals gets one
``@kconfig_depends{<condition>}`` per enclosing condition, outermost first,
appended to the last line of its doc comment. In ``.c`` files that is the doc
comment of a ZTEST; in headers every entity doc comment and ``/**<`` member
comment, but not the structural ones (``@defgroup``, ``@{``, ``@cond``, ...).
The condition is the branch's own: ``CONFIG_X`` for ``#ifdef``, ``!CONFIG_X``
for ``#ifndef``, the expression as written (whitespace normalised, a
``|| defined(__DOXYGEN__)`` dropped) for ``#if`` and ``#elif``, and the
negation of every earlier branch for ``#else``.

The output has exactly as many lines as the input, so Doxygen's line numbers
still point into the real file.

Usage: doxygen_filter_kconfig.py [--rename-impl] [--suites <json>] <file>

``--rename-impl`` also applies doxygen_filter_remove_impl.py (``z_impl_k_*`` ->
``k_*``), for a pattern that needs both filters.

``--suites`` names the JSON testspec_scope.py writes for a suite that more than
one test module in scope uses: {module directory: {suite: group}}. In a file
under such a module, each ZTEST of the suite gets the module's own group as
its suite argument (``ZTEST(workqueue_api, fn)`` ->
``ZTEST(kernel_workq_user_work_module__workqueue_api, fn)``), so the testspec
Doxyfile's ZTEST expansion puts it in that group: one group per module, not
one shared by both.
"""

import json

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

DIRECTIVE = re.compile(r"^[ \t]*#[ \t]*(ifdef|ifndef|if|elif|else|endif)\b(.*)$", re.S)
# The macros that define a test: ZTEST, ZTEST_USER, their _F (fixture) and _P
# (parameterized) forms, and sys_mutex's local ZTEST_USER_OR_NOT (ZTEST_USER
# with CONFIG_USERSPACE, ZTEST without). Not ZTEST_EXPECT_FAIL / _SKIP, which
# only mark one, nor ZTEST_SUITE.
ZTEST_MACRO = r"ZTEST(?:_USER(?:_OR_NOT)?)?(?:_F|_P)?"
ZTEST = re.compile(rf"^[ \t]*{ZTEST_MACRO}\s*\(\s*(\w+)\s*,\s*(\w+)")
# A doc comment that structures the documentation rather than documenting the
# entity after it.
STRUCTURAL = re.compile(
    r"[@\\](?:defgroup|addtogroup|weakgroup|name|file|page|mainpage|cond|endcond|\{|\})"
    r"(?![\w-])"
)
DOXYGEN_TERM = re.compile(r"^!?\s*\(?\s*defined\s*(?:\(\s*__DOXYGEN__\s*\)|__DOXYGEN__)\s*\)?$")
ATOM = re.compile(r"^!?(?:\w+|defined\s*\(\s*\w+\s*\))$")


# --------------------------------------------------------------------------
# Lexing: which lines start inside a block comment, and where the comments are


@dataclass
class Comment:
    start: tuple  # (line, col) of "/*"
    end: tuple  # (line, col) of the closing "*/"
    doc: bool  # /** or /*!
    member: bool  # /**< or /*!<


def lex(lines):
    """Comments in the text, and for each line whether it starts inside one."""
    comments = []
    in_comment = [False] * len(lines)
    state = None  # None, or the Comment being read
    for n, line in enumerate(lines):
        in_comment[n] = state is not None
        i, end = 0, len(line)
        while i < end:
            if state is not None:
                j = line.find("*/", i)
                if j < 0:
                    break
                state.end = (n, j)
                comments.append(state)
                state = None
                i = j + 2
                continue
            c = line[i]
            if c == "/" and line.startswith("//", i):
                break
            if c == "/" and line.startswith("/*", i):
                body = line[i + 2:i + 4]
                doc = body[:1] == "!" or (body[:1] == "*" and body[1:2] not in ("*", "/"))
                state = Comment((n, i), None, doc, doc and body[1:2] == "<")
                i += 2
                continue
            if c in "\"'":
                j = i + 1
                while j < end and line[j] != c:
                    j += 2 if line[j] == "\\" else 1
                i = j + 1
                continue
            i += 1
    return comments, in_comment


# --------------------------------------------------------------------------
# Expressions


def _strip_comments(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r"/\*.*$", " ", text, flags=re.S)  # a comment left open
    return re.sub(r"//.*", " ", text)


def normalise(expr):
    return " ".join(_strip_comments(expr.replace("\\\n", " ")).split())


TOKEN = re.compile(r"\s*(defined\b|[A-Za-z_]\w*|&&|\|\||!|\(|\)|\S)")


class _Unevaluable(Exception):
    pass


def evaluate(expr):
    """True/False for a pure-Kconfig expression, None for anything else."""
    tokens = TOKEN.findall(normalise(expr))
    pos = 0

    def peek():
        return tokens[pos] if pos < len(tokens) else None

    def take(expected=None):
        nonlocal pos
        tok = peek()
        if tok is None or (expected is not None and tok != expected):
            raise _Unevaluable
        pos += 1
        return tok

    def symbol(name):
        if name.startswith("CONFIG_") or name == "__DOXYGEN__":
            return True
        raise _Unevaluable

    def primary():
        tok = take()
        if tok == "(":
            v = disj()
            take(")")
            return v
        if tok == "defined":
            if peek() == "(":
                take("(")
                v = symbol(take())
                take(")")
                return v
            return symbol(take())
        raise _Unevaluable

    def unary():
        if peek() == "!":
            take()
            return not unary()
        return primary()

    def conj():
        v = unary()
        while peek() == "&&":
            take()
            v = unary() and v
        return v

    def disj():
        v = conj()
        while peek() == "||":
            take()
            v = conj() or v
        return v

    try:
        v = disj()
        if pos != len(tokens):
            return None
        return v
    except _Unevaluable:
        return None


def _split_top(expr, op):
    parts, depth, last, i = [], 0, 0, 0
    while i < len(expr):
        c = expr[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        elif depth == 0 and expr.startswith(op, i):
            parts.append(expr[last:i].strip())
            last = i + len(op)
            i += len(op)
            continue
        i += 1
    parts.append(expr[last:].strip())
    return parts


def condition_text(expr):
    """The annotation for an evaluated #if/#elif expression, or None.

    `|| defined(__DOXYGEN__)` only makes the documentation build see the code;
    it is not a Kconfig dependency and is dropped."""
    parts = [p for p in _split_top(normalise(expr), "||") if not DOXYGEN_TERM.match(p)]
    text = " || ".join(parts)
    return text if "CONFIG_" in text else None


def negate(cond):
    if ATOM.match(cond):
        return cond[1:] if cond.startswith("!") else "!" + cond
    return f"!({cond})"


def escape_arg(cond):
    """A Doxygen alias argument ends at an unescaped comma."""
    return cond.replace(",", "\\,")


# --------------------------------------------------------------------------
# Conditionals


@dataclass
class Branch:
    kind: str
    line: int  # first line of the directive
    last: int  # last line of the directive (continuations)
    value: object = None  # True / False / None (left to Doxygen)
    cond: object = None  # annotation text, or None
    taken: object = None  # True / False / None (unknown)
    end: int = 0  # the line of the next directive of this conditional


@dataclass
class Conditional:
    branches: list = field(default_factory=list)
    endif: tuple = None  # (line, last)
    open_up: bool = False


def directives(lines, in_comment):
    """(kind, rest, first line, last line) for every conditional directive."""
    n = 0
    while n < len(lines):
        m = DIRECTIVE.match(lines[n]) if not in_comment[n] else None
        if not m:
            n += 1
            continue
        first, text = n, lines[n]
        while text.rstrip("\r\n").endswith("\\") and n + 1 < len(lines):
            n += 1
            text += lines[n]
        m = DIRECTIVE.match(text)
        yield m.group(1), m.group(2), first, n
        n += 1


def parse(lines, in_comment):
    conds, stack = [], []
    for kind, rest, first, last in directives(lines, in_comment):
        if kind in ("if", "ifdef", "ifndef"):
            c = Conditional()
            conds.append(c)
            stack.append(c)
        elif not stack:
            continue  # unbalanced; leave it to Doxygen
        c = stack[-1]
        if kind == "endif":
            c.branches[-1].end = first
            c.endif = (first, last)
            stack.pop()
            continue
        if c.branches:
            c.branches[-1].end = first
        b = Branch(kind, first, last)
        words = normalise(rest).split()
        if kind in ("ifdef", "ifndef"):
            name = words[0] if words else ""
            if name.startswith("CONFIG_"):
                b.value = kind == "ifdef"
                b.cond = name if kind == "ifdef" else "!" + name
        elif kind in ("if", "elif"):
            b.value = evaluate(rest)
            if b.value is not None:
                b.cond = condition_text(rest)
        c.branches.append(b)
    for c in stack:  # unterminated: close at the end of the file
        c.branches[-1].end = len(lines)
    for c in conds:
        _resolve(c)
    return conds


def _resolve(c):
    """Which branch is taken, and the #else conditions."""
    decided = False  # an earlier branch is known to be taken
    unknown = False  # an earlier branch is left to Doxygen
    for i, b in enumerate(c.branches):
        v = True if b.kind == "else" else b.value
        if decided or v is False:
            b.taken = False
        elif unknown or v is None:
            b.taken = None
            unknown = True
        else:
            b.taken = True
            decided = True
        if b.kind == "else":
            earlier = [p.cond for p in c.branches[:i]]
            if earlier and all(earlier) and all(p.value is not None for p in c.branches[:i]):
                b.cond = " && ".join(negate(e) for e in earlier)


# --------------------------------------------------------------------------
# ZTESTs


def is_skip_stub(text_from_ztest):
    """Whether the ZTEST the text starts with has a body of only
    `ztest_test_skip();`, comments and whitespace aside."""
    code = _strip_comments(text_from_ztest)
    start = code.find("{")
    if start < 0:
        return False
    depth = 0
    for i in range(start, len(code)):
        if code[i] == "{":
            depth += 1
        elif code[i] == "}":
            depth -= 1
            if depth == 0:
                return "".join(code[start + 1:i].split()) == "ztest_test_skip();"
    return False


def attached_doc(lines, comments, in_comment, n):
    """The doc comment Doxygen attaches to the declaration on line n, or None.

    Doxygen skips what the preprocessor or the scanner drops between a doc
    comment and the declaration it documents: blank lines, conditional
    directives (``#if``, ``#ifdef``, ``#else``, ...; a ``#define`` is a
    declaration of its own and takes the comment) and plain comments."""
    ends = {c.end[0]: c for c in comments}
    p = n - 1
    while p >= 0:
        line = lines[p]
        if not line.strip():
            p -= 1
            continue
        if not in_comment[p] and DIRECTIVE.match(line):
            p -= 1
            continue
        c = ends.get(p)
        if c is None or line[c.end[1] + 2:].strip():
            return None
        if c.doc:
            return None if c.member else c
        if lines[c.start[0]][:c.start[1]].strip():
            return None  # code before a plain comment
        p = c.start[0] - 1
    return None


def documented_ztests(lines, comments, in_comment=None):
    """{ztest line: doc comment} for the ZTESTs with a doc comment of their
    own (attached_doc()), and the set of those that are only a
    ztest_test_skip() stub."""
    if in_comment is None:
        in_comment = lex(lines)[1]
    found, stubs = {}, set()
    for n, line in enumerate(lines):
        if not ZTEST.match(line):
            continue
        c = attached_doc(lines, comments, in_comment, n)
        if c is None:
            continue
        found[n] = c
        if is_skip_stub("".join(lines[n:n + 200])):
            stubs.add(n)
    return found, stubs


# --------------------------------------------------------------------------
# The filter


def _enclosing(conds, line):
    """(Conditional, Branch) pairs whose branch body holds the line, outermost first."""
    out = []
    for c in conds:
        for b in c.branches:
            if b.last < line < b.end:
                out.append((c, b))
    return out  # conds are in source order, so outer before inner


def _rewrite_directive(lines, out, first, last, new, keep_open_comment):
    nl = lambda s: s[len(s.rstrip("\r\n")):]  # noqa: E731
    for n in range(first, last + 1):
        out[n] = nl(lines[n])
    tail = keep_open_comment.get(last, "")
    out[first] = new + (" " + tail if tail and first == last else "") + nl(lines[first])
    if tail and last != first:
        out[last] = tail + nl(lines[last])


def qualify_suites(out, suite_groups):
    """Point every ZTEST of a suite in suite_groups at the suite's group."""
    for n, line in enumerate(out):
        m = ZTEST.match(line)
        if m and m.group(1) in suite_groups:
            out[n] = line[:m.start(1)] + suite_groups[m.group(1)] + line[m.end(1):]


def suite_groups_for(path, suites_file):
    """The {suite: group} of the module the file is in, from --suites."""
    table = json.loads(Path(suites_file).read_text())
    path = Path(path).resolve()
    for d in (path, *path.parents):
        if str(d) in table:
            return table[str(d)]
    return {}


def filter_text(text, is_header, suite_groups=None):
    # Lines as Doxygen counts them: split at "\n" only, not at every
    # separator str.splitlines() knows (form feed, ...).
    lines = re.findall(r"[^\n]*\n|[^\n]+$", text)
    comments, in_comment = lex(lines)
    conds = parse(lines, in_comment)
    ztests, stubs = documented_ztests(lines, comments, in_comment)

    # Twin rule: open up a conditional whose not-taken branch holds a
    # documented, non-stub ZTEST.
    for n in ztests:
        if n in stubs:
            continue
        for c, b in _enclosing(conds, n):
            if b.taken is False:
                c.open_up = True

    # The text of a comment left open at the end of a directive line.
    open_tail = {}
    for c in comments:
        if c.start[0] != c.end[0]:
            open_tail[c.start[0]] = lines[c.start[0]][c.start[1]:].rstrip("\r\n")

    out = list(lines)
    for c in conds:
        for b in c.branches:
            if c.open_up:
                _rewrite_directive(lines, out, b.line, b.last, "", open_tail)
            elif b.value is not None:
                kw = "elif" if b.kind == "elif" else "if"
                _rewrite_directive(lines, out, b.line, b.last, f"#{kw} {int(b.value)}", open_tail)
        if c.open_up and c.endif:
            _rewrite_directive(lines, out, c.endif[0], c.endif[1], "", open_tail)

    # Annotations: (comment, the line whose enclosing conditions apply). For a
    # ZTEST that is its own line: its doc comment may sit outside the
    # conditional (`/** ... */ #ifdef CONFIG_X ZTEST(...)`).
    if is_header:
        targets = [
            (c, c.end[0]) for c in comments
            if c.doc and (c.member or not STRUCTURAL.search(_comment_text(lines, c)))
        ]
    else:
        targets = [(c, n) for n, c in ztests.items() if n not in stubs]
    inserts = {}
    for cm, at in targets:
        conds_here = []
        for c, b in _enclosing(conds, at):
            if (b.taken is not False or c.open_up) and b.cond:
                conds_here.append(b.cond)
        if conds_here:
            inserts[cm.end] = conds_here
    for (n, col), conds_here in inserts.items():
        line = out[n]
        if not line.startswith("*/", col):
            continue  # a rewritten directive line; the column moved
        cmds = " ".join(f"@kconfig_depends{{{escape_arg(x)}}}" for x in conds_here)
        before = line[:col]
        if before.strip():
            new = before.rstrip() + " " + cmds + " "
        else:
            # A closing line of its own: keep the comment's leading "*".
            new = before + "* " + cmds + " "
        out[n] = new + line[col:]
    if suite_groups:
        qualify_suites(out, suite_groups)
    return "".join(out)


def _comment_text(lines, c):
    (l0, c0), (l1, c1) = c.start, c.end
    if l0 == l1:
        return lines[l0][c0:c1]
    return lines[l0][c0:] + "".join(lines[l0 + 1:l1]) + lines[l1][:c1]


def main():
    ap = argparse.ArgumentParser(allow_abbrev=False)
    ap.add_argument("--rename-impl", action="store_true")
    ap.add_argument("--suites", type=Path, help="qualified suite groups (testspec_scope.py)")
    ap.add_argument("file", type=Path)
    args = ap.parse_args()
    text = args.file.read_text(encoding="utf-8", errors="surrogateescape")
    groups = suite_groups_for(args.file, args.suites) if args.suites else None
    text = filter_text(text, is_header=args.file.suffix != ".c", suite_groups=groups)
    if args.rename_impl:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from doxygen_filter_remove_impl import rename_impl

        text = rename_impl(text)
    sys.stdout.buffer.write(text.encode("utf-8", errors="surrogateescape"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
