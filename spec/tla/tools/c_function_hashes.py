#!/usr/bin/env python3
# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Record and check the C functions that the ``@c-function`` tags name.

Each ``@c-function`` tag of ``spec/tla/**/*.tla`` names a C function (or a
macro, or an assembly routine) of the Zephyr tree. This script finds each
definition of the name in a Zephyr commit, normalizes its text, and hashes
it. The record file (default ``spec/tla/c-functions.json``) holds the
result at the pin: for each name, each definition with its file, line and
hash, and the full commit hash of the pin.

Modes:

``record --commit <rev>``
   Write the record for the commit ``<rev>`` (the pin).
``tags``
   For each tag name, make sure that a definition exists at the commit of
   the record. Also compare the tag names with the names in the record and
   with the pin that ``lib/Platform.tla`` states.
``check --against <rev>``
   Compare the record with the commit ``<rev>``. For each definition, the
   result is one of: unchanged, shifted (same file, same hash, other line),
   moved (other file, same hash), changed, changed-trace (only tracing or
   logging statements changed), moved-changed, missing (the definition is
   gone), added (a new definition of a recorded name).
``log <rev>...``
   For each commit, compare its first parent with the commit, for the
   recorded names. This tells which commit changed a recorded body.

The script reads the Zephyr tree only through ``git grep <rev>`` and
``git show <rev>:<path>``. It needs no checkout. ``--tree <dir>`` reads a
plain directory instead (for example the output of ``git archive``).

The normalization:

- Comments are removed. A change of a comment is not a change.
- Whitespace is removed: the text becomes a list of C tokens with one
  space between two tokens. A new indentation, a new line break or the
  output of clang-format is not a change.
- Line continuations (backslash and newline) are removed.
- A preprocessor line in a body stays one item (``#if CONFIG_X``), because
  the Kconfig options select the code.
- Nothing else changes. A new name of a local variable, a new order of
  two statements and a new cast are changes. The hash covers the
  signature (return type, qualifiers, parameters) and the body.
- A second hash (``core``) also removes the statements of the tracing and
  logging macros (``SYS_PORT_TRACING_*``, ``LOG_*``). If only the first
  hash changes, the result is ``changed-trace``. Assertions stay in both
  hashes: an assertion is a behavior of the assert builds.

What the script finds:

- A function definition: the name at the start of a line after a return
  type (or on the line after the return type), the parameters, optional
  attributes, then ``{``. Static inline functions of headers are
  definitions too. A declaration (``;``) is not a definition.
- An alias: ``FUNC_ALIAS(target, name, type)``. The hash is the hash of the
  target in the same file.
- A macro: ``#define name`` with all its continuation lines.
- An assembly routine: ``SECTION_FUNC(<section>, name)`` or
  ``SECTION_SUBSEC_FUNC(<section>, <sub>, name)`` in a ``.S`` file. The
  body is the text up to the next ``SECTION_*FUNC`` or the end of the file.

A name can have more than one definition: one for each timeout backend
(``z_timeout_q_insert``), one for each ``#if`` branch (``irq_lock``), or
one in a header and one in a C file (``z_arm_int_exit``). The record holds
all of them. The Kconfig options select one; the script does not.

The search scope is the code of the safety case on ARM Cortex-M: see
``SCOPE`` below. Other architectures are out of the scope, so
``arch_irq_lock`` has one definition, not twelve.

Exit status: 0 without a difference, 1 with a difference or a missing
name, 2 on a setup error.
"""

import argparse
import difflib
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

TOOL_VERSION = 1
SPEC = Path(__file__).resolve().parent.parent
DEFAULT_RECORD = SPEC / "c-functions.json"

# ---- scope ----------------------------------------------------------------

SCOPE_DIRS = ["kernel", "include/zephyr", "arch/arm", "drivers/timer"]
SCOPE_TIMER_FILES = {
    "drivers/timer/cortex_m_systick.c",
    "drivers/timer/system_timer_generic.h",
    "drivers/timer/sys_clock_init.c",
}
SCOPE_TEXT = (
    "kernel/; include/zephyr/ without include/zephyr/arch/<other arch>/; "
    "arch/arm/ without cortex_a_r; drivers/timer/{cortex_m_systick.c,"
    "system_timer_generic.h,sys_clock_init.c}"
)


def in_scope(path):
    """True if the file belongs to the scope of the record."""
    if not path.endswith((".c", ".h", ".S")):
        return False
    if path.startswith("kernel/"):
        return True
    if path.startswith("include/zephyr/arch/"):
        rest = path[len("include/zephyr/arch/"):]
        if "/" not in rest:
            return True
        return rest.startswith(("arm/", "common/")) and "cortex_a_r" not in rest
    if path.startswith("include/zephyr/"):
        return True
    if path.startswith("arch/arm/"):
        return "cortex_a_r" not in path
    return path in SCOPE_TIMER_FILES


# ---- trees ----------------------------------------------------------------


class GitTree:
    """A commit of a git repository, read without a checkout."""

    def __init__(self, repo, rev):
        self.repo = Path(repo)
        r = self._git("rev-parse", "--verify", "--quiet", rev + "^{commit}")
        if r.returncode != 0:
            raise SystemExit(f"error: {rev} is not a commit in {repo}")
        self.commit = r.stdout.strip()
        self.label = rev
        self._cache = {}

    def _git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args],
                              capture_output=True, text=True,
                              errors="replace")

    def files_with(self, names):
        args = ["grep", "-l", "-w", "-F"]
        for n in sorted(names):
            args += ["-e", n]
        r = self._git(*args, self.commit, "--", *SCOPE_DIRS)
        if r.returncode not in (0, 1):
            raise SystemExit("error: git grep: " + r.stderr.strip())
        out = []
        for line in r.stdout.splitlines():
            path = line.split(":", 1)[1]
            if in_scope(path):
                out.append(path)
        return sorted(out)

    def read(self, path):
        if path not in self._cache:
            r = self._git("show", f"{self.commit}:{path}")
            self._cache[path] = r.stdout if r.returncode == 0 else None
        return self._cache[path]


class DirTree:
    """A plain directory, for example the output of git archive."""

    def __init__(self, root, commit=None):
        self.root = Path(root)
        self.commit = commit or "unknown"
        self.label = str(root)

    def files_with(self, names):
        pat = re.compile(r"\b(?:" + "|".join(map(re.escape, names)) + r")\b")
        out = []
        for d in SCOPE_DIRS:
            for dirpath, _, files in os.walk(self.root / d):
                for f in files:
                    p = Path(dirpath) / f
                    rel = str(p.relative_to(self.root))
                    if in_scope(rel) and pat.search(p.read_text(errors="replace")):
                        out.append(rel)
        return sorted(out)

    def read(self, path):
        p = self.root / path
        return p.read_text(errors="replace") if p.exists() else None


# ---- C text ---------------------------------------------------------------

LEX = re.compile(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'', re.S)


def _blank(s):
    return re.sub(r"[^\n]", " ", s)


def strip_comments(text):
    """Comments become spaces; strings stay. Lines and columns stay."""
    return LEX.sub(lambda m: _blank(m.group(0)) if m.group(0)[0] == "/" else m.group(0), text)


def blank_all(text):
    """Comments and literals become spaces. For the structure scan."""
    return LEX.sub(lambda m: _blank(m.group(0)) if m.group(0)[0] == "/"
                   else m.group(0)[0] + _blank(m.group(0)[1:-1]) + m.group(0)[-1], text)


TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[A-Za-z_]\w*|\d[\w.]*'
                   r'|<<=|>>=|\.\.\.|->|\+\+|--|<<|>>|<=|>=|==|!=|&&|\|\||##'
                   r'|[-+*/%&|^]=|\S')
TRACE_LOG = re.compile(r"^(SYS_PORT_TRACING\w*|LOG_(?:DBG|INF|WRN|ERR|HEXDUMP_\w+|PRINTK))$")


def tokens(text):
    """Token list of comment-free text. A preprocessor line is one item."""
    text = text.replace("\\\n", " ")
    out = []
    for line in text.split("\n"):
        s = line.strip()
        if s.startswith("#"):
            out.append("#" + " ".join(TOKEN.findall(s[1:])))
        else:
            out.extend(TOKEN.findall(line))
    return out


def drop_trace_log(toks):
    """Remove the statements of the tracing and logging macros."""
    out, i = [], 0
    while i < len(toks):
        if TRACE_LOG.match(toks[i]) and i + 1 < len(toks) and toks[i + 1] == "(":
            depth, j = 0, i + 1
            while j < len(toks):
                if toks[j] == "(":
                    depth += 1
                elif toks[j] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            i = j + 1
            if i < len(toks) and toks[i] == ";":
                i += 1
            continue
        out.append(toks[i])
        i += 1
    return out


def digest(toks):
    return hashlib.sha256(" ".join(toks).encode()).hexdigest()[:16]


def match_close(s, i, open_c, close_c):
    """Index of the bracket that closes the one at s[i], or -1."""
    depth = 0
    for j in range(i, len(s)):
        c = s[j]
        if c == open_c:
            depth += 1
        elif c == close_c:
            depth -= 1
            if depth == 0:
                return j
    return -1


def line_of(s, pos):
    return s.count("\n", 0, pos) + 1


@dataclass
class Def:
    name: str
    file: str
    line: int
    end: int
    kind: str          # function, alias, macro, asm
    text: str          # comment-free source text of the definition
    hash: str = ""
    core: str = ""
    notes: list = field(default_factory=list)

    def finish(self):
        toks = tokens(self.text)
        self.hash = digest(toks)
        self.core = digest(drop_trace_log(toks))
        if self.kind == "function":
            w = wrapper_target(toks)
            if w:
                self.notes.append(f"wrapper: one statement, calls {w}")
        return self

    def as_record(self):
        r = {"file": self.file, "line": self.line, "end": self.end,
             "kind": self.kind, "hash": self.hash, "core": self.core}
        if self.notes:
            r["notes"] = self.notes
        return r


CONTROL = {"if", "for", "while", "switch", "do", "goto", "else", "case"}


def wrapper_target(toks):
    """The callees if the body is one statement without a branch, else None.

    Such a body is a wrapper: a change of the callee does not change its
    hash.
    """
    try:
        b = toks.index("{")
    except ValueError:
        return None
    body = toks[b + 1:-1]
    if body.count(";") != 1 or CONTROL & set(body) or any(t.startswith("#") for t in body):
        return None
    calls = [body[i] for i in range(len(body) - 1)
             if body[i + 1] == "(" and re.match(r"[A-Za-z_]\w*$", body[i])
             and body[i] not in ("return", "sizeof")]
    return ", ".join(c + "()" for c in dict.fromkeys(calls)) or None


DECL_PREFIX = re.compile(r"^(?!(?:return|if|while|for|switch|case|else|do|goto)\b)"
                         r"[A-Za-z_][\w \t*().,]*$")
ATTR = re.compile(r"\s*([A-Za-z_]\w*)\s*")


def find_defs(name, path, text):
    """All definitions of name in one file."""
    if text is None:
        return []
    clean = strip_comments(text)
    blank = blank_all(text)
    lines = blank.split("\n")
    out = []
    if path.endswith(".S"):
        for m in re.finditer(r"^[ \t]*SECTION_(?:SUBSEC_)?FUNC\s*\([^)]*\b" + re.escape(name)
                             + r"\s*\)", blank, re.M):
            nxt = re.compile(r"^[ \t]*SECTION_(?:SUBSEC_)?FUNC\s*\(", re.M).search(blank, m.end())
            end = nxt.start() if nxt else len(blank)
            out.append(Def(name, path, line_of(blank, m.start()), line_of(blank, end - 1),
                           "asm", clean[m.start():end]).finish())
        return out
    # macros
    for m in re.finditer(r"^[ \t]*#[ \t]*define[ \t]+" + re.escape(name) + r"\b", blank, re.M):
        end = m.end()
        while True:
            nl = blank.find("\n", end)
            if nl < 0:
                end = len(blank)
                break
            if clean[:nl].rstrip(" \t").endswith("\\"):
                end = nl + 1
                continue
            end = nl
            break
        out.append(Def(name, path, line_of(blank, m.start()), line_of(blank, end),
                       "macro", clean[m.start():end]).finish())
    # aliases
    alias_res = [r"\bFUNC_ALIAS\s*\(\s*(\w+)\s*,\s*" + re.escape(name) + r"\s*,",
                 r"\b" + re.escape(name) + r"\s*\([^;{}]*\)\s*ALIAS_OF\(\s*(\w+)\s*\)"]
    for m in (m for a in alias_res for m in re.finditer(a, blank)):
        target = m.group(1)
        tdefs = [d for d in find_defs(target, path, text) if d.kind == "function"]
        ls = blank.rfind("\n", 0, m.start()) + 1
        se = blank.find(";", m.end())
        stmt = clean[ls:se + 1 if se >= 0 else m.end()]
        aline = line_of(blank, m.start())
        if tdefs:
            t = tdefs[0]
            d = Def(name, path, aline, aline, "alias", stmt + "\n" + t.text)
            d.finish()
            d.notes.insert(0, f"alias of {target}() at lines {t.line}-{t.end}")
        else:
            d = Def(name, path, aline, aline, "alias", stmt).finish()
            d.notes.insert(0, f"alias of {target}(): no definition of it in this file")
        out.append(d)
    # functions
    for m in re.finditer(r"\b" + re.escape(name) + r"\s*\(", blank):
        ls = blank.rfind("\n", 0, m.start()) + 1
        prefix = blank[ls:m.start()]
        lno = line_of(blank, m.start())
        start = ls
        if prefix.strip():
            if not DECL_PREFIX.match(prefix):
                continue
        else:
            if prefix:            # indented: a call or a nested use
                continue
            prev = lno - 2
            while prev >= 0 and not lines[prev].strip():
                prev -= 1
            if prev < 0 or not DECL_PREFIX.match(lines[prev]):
                continue
            start = sum(len(x) + 1 for x in lines[:prev])
        po = m.end() - 1
        pc = match_close(blank, po, "(", ")")
        if pc < 0:
            continue
        k = pc + 1
        while True:                 # attributes such as __attribute__((x))
            a = ATTR.match(blank, k)
            if not a:
                break
            k = a.end()
            if k < len(blank) and blank[k] == "(":
                k2 = match_close(blank, k, "(", ")")
                if k2 < 0:
                    break
                k = k2 + 1
        while k < len(blank) and blank[k] in " \t\n":
            k += 1
        if k >= len(blank) or blank[k] != "{":
            continue
        bc = match_close(blank, k, "{", "}")
        d = Def(name, path, line_of(blank, start), line_of(blank, bc if bc > 0 else k),
                "function", clean[start:bc + 1] if bc > 0 else "")
        if bc < 0:
            d.notes.append("no closing brace (an #if branch has its own brace?)")
        out.append(d.finish())
    out.sort(key=lambda d: d.line)
    return out


def _extract(tree, names):
    files = tree.files_with(names)
    res = {n: [] for n in names}
    for f in files:
        text = tree.read(f)
        for n in names:
            if text is not None and re.search(r"\b" + re.escape(n) + r"\b", text):
                res[n].extend(find_defs(n, f, text))
    return res


def extract(tree, names):
    """name -> list of Def, for all names, in the scope of the tree.

    A name without a definition can be the API name of a system call. Then
    the definitions of z_impl_<name> count, with a note.
    """
    res = _extract(tree, names)
    retry = {"z_impl_" + n: n for n in names if not res[n] and not n.startswith("z_impl_")}
    if retry:
        for zn, defs in _extract(tree, list(retry)).items():
            for d in defs:
                d.notes.insert(0, f"system call: the definition is {zn}()")
            res[retry[zn]] = defs
    return res


# ---- tags -----------------------------------------------------------------

TAG = re.compile(r"^\s*\\\*\s*@c-function\s+(\S+)", re.M)


def read_tags(spec):
    """name -> sorted list of modules that tag it; plus bad tags."""
    tags, bad = {}, []
    for f in sorted(spec.rglob("*.tla")):
        if "/states/" in str(f):
            continue
        for m in TAG.finditer(f.read_text(errors="replace")):
            n = m.group(1).rstrip("()")
            mod = str(f.relative_to(spec))
            if not re.match(r"^[A-Za-z_]\w*$", n):
                bad.append((mod, m.group(1)))
                continue
            tags.setdefault(n, set()).add(mod)
    return {k: sorted(v) for k, v in sorted(tags.items())}, bad


def platform_pin(spec):
    p = spec / "lib/Platform.tla"
    if not p.exists():
        return None
    m = re.search(r"Zephyr\s+(?:\(\*\s*)?([0-9a-f]{7,40})", p.read_text().replace("*)\n(*", " "))
    return m.group(1) if m else None


# ---- modes ----------------------------------------------------------------


def make_tree(args, rev):
    if args.tree:
        return DirTree(args.tree, rev)
    return GitTree(args.zephyr, rev)


def cmd_record(args):
    tags, bad = read_tags(args.spec)
    rev = args.commit
    if not rev:
        if args.record.exists():
            rev = json.loads(args.record.read_text())["meta"]["commit"]
        else:
            raise SystemExit("error: give --commit for a new record")
    tree = make_tree(args, rev)
    defs = extract(tree, list(tags))
    funcs = {}
    for n in tags:
        e = {"tagged_in": tags[n], "defs": [d.as_record() for d in defs[n]]}
        funcs[n] = e
    rec = {
        "meta": {
            "tool": "spec/tla/tools/c_function_hashes.py",
            "tool_version": TOOL_VERSION,
            "commit": tree.commit,
            "scope": SCOPE_TEXT,
            "normalization": "comments and whitespace removed, C tokens joined by one space, "
                             "preprocessor lines kept; 'core' also without SYS_PORT_TRACING_* "
                             "and LOG_* statements",
        },
        "functions": funcs,
    }
    args.record.write_text(json.dumps(rec, indent=1) + "\n")
    missing = [n for n in tags if not defs[n]]
    print(f"recorded {len(tags)} names, {sum(len(v) for v in defs.values())} definitions "
          f"at {tree.commit[:12]} in {args.record}")
    for n in missing:
        print(f"MISSING {n} (tagged in {', '.join(tags[n])})")
    for mod, t in bad:
        print(f"BAD TAG {t!r} in {mod}")
    return 1 if missing or bad else 0


def load_record(args):
    if not args.record.exists():
        raise SystemExit(f"error: no record {args.record}; run the mode record first")
    rec = json.loads(args.record.read_text())
    if rec["meta"].get("tool_version") != TOOL_VERSION:
        raise SystemExit("error: the record has another tool version; record again")
    return rec


def cmd_tags(args):
    rec = load_record(args)
    tags, bad = read_tags(args.spec)
    rev = args.commit or rec["meta"]["commit"]
    tree = make_tree(args, rev)
    defs = extract(tree, list(tags))
    rc = 0
    print(f"tags: {len(tags)} names in {args.spec}, checked at {tree.commit[:12]}")
    for n in tags:
        if not defs[n]:
            print(f"MISSING  {n}: no definition at {tree.commit[:12]} (tagged in "
                  f"{', '.join(tags[n])})")
            rc = 1
    for mod, t in bad:
        print(f"BAD TAG  {t!r} in {mod}")
        rc = 1
    recn = set(rec["functions"])
    for n in sorted(set(tags) - recn):
        print(f"NEW TAG  {n}: tagged, not in the record (record again)")
        rc = 1
    for n in sorted(recn - set(tags)):
        print(f"OLD      {n}: in the record, no longer tagged (record again)")
        rc = 1
    pin = platform_pin(args.spec)
    if pin and not rec["meta"]["commit"].startswith(pin):
        print(f"PIN      lib/Platform.tla names Zephyr {pin}, the record has "
              f"{rec['meta']['commit'][:12]}")
        rc = 1
    for n in tags:
        for d in defs[n]:
            for note in d.notes:
                if note.startswith("no closing"):
                    print(f"WARN     {n} {d.file}:{d.line}: {note}")
                elif note.startswith("system call"):
                    print(f"INDIRECT {n} {d.file}:{d.line}: {note}")
                elif note.startswith("wrapper"):
                    callees = re.findall(r"(\w+)\(\)", note)
                    untagged = [c for c in callees if c not in tags]
                    if untagged:
                        print(f"WRAPPER  {n} {d.file}:{d.line}: the hash does not cover "
                              f"{', '.join(c + '()' for c in untagged)} (not tagged)")
    if rc == 0:
        print("ok: each tag names a definition at the pin, and the record has each tag")
    return rc


@dataclass
class Result:
    name: str
    status: str
    old: dict = None
    new: Def = None
    note: str = ""


def compare(name, old_defs, new_defs):
    res = []
    used = set()
    for od in old_defs:
        hit = None
        for i, nd in enumerate(new_defs):        # same file, same hash
            if i not in used and nd.file == od["file"] and nd.hash == od["hash"]:
                hit = i
                break
        if hit is not None:
            used.add(hit)
            nd = new_defs[hit]
            st = "unchanged" if nd.line == od["line"] else "shifted"
            res.append(Result(name, st, od, nd))
            continue
        for i, nd in enumerate(new_defs):        # other file, same hash
            if i not in used and nd.hash == od["hash"]:
                hit = i
                break
        if hit is not None:
            used.add(hit)
            res.append(Result(name, "moved", od, new_defs[hit]))
            continue
        for i, nd in enumerate(new_defs):        # same file, same kind
            if i not in used and nd.file == od["file"] and nd.kind == od["kind"]:
                hit = i
                break
        if hit is not None:
            used.add(hit)
            nd = new_defs[hit]
            st = "changed-trace" if nd.core == od["core"] else "changed"
            res.append(Result(name, st, od, nd))
            continue
        res.append(Result(name, "missing", od, None))
    # a definition that is missing in its file can be in a new file
    rest = [i for i in range(len(new_defs)) if i not in used]
    for r in res:
        if r.status == "missing" and rest:
            same_base = [i for i in rest if os.path.basename(new_defs[i].file)
                         == os.path.basename(r.old["file"])]
            pick = (same_base or rest)[0]
            rest.remove(pick)
            r.new = new_defs[pick]
            r.status = "moved-changed"
    for i in rest:
        res.append(Result(name, "added", None, new_defs[i]))
    return res


def loc(d):
    if d is None:
        return "-"
    if isinstance(d, dict):
        return f"{d['file']}:{d['line']}"
    return f"{d.file}:{d.line}"


def source_diff(base_tree, other, r):
    """Unified diff of the comment-free text of one definition."""
    if r.old is None or r.new is None or base_tree is None:
        return ""
    od = [d for d in find_defs(r.name, r.old["file"], base_tree.read(r.old["file"]))
          if d.line == r.old["line"]]
    if not od:
        return ""

    def norm(t):
        return [x.rstrip() for x in t.replace("\\\n", "\n").split("\n") if x.strip()]

    return "\n".join(difflib.unified_diff(norm(od[0].text), norm(r.new.text),
                                          loc(r.old), loc(r.new), lineterm="", n=1))


def run_check(rec, tree):
    names = list(rec["functions"])
    defs = extract(tree, names)
    out = []
    for n in names:
        out.extend(compare(n, rec["functions"][n]["defs"], defs[n]))
        if not rec["functions"][n]["defs"] and not defs[n]:
            out.append(Result(n, "missing", None, None, "no definition at the pin either"))
    return out


SEVERE = {"changed", "changed-trace", "moved", "moved-changed", "missing", "added"}


def cmd_check(args):
    rec = load_record(args)
    tree = make_tree(args, args.against)
    base = None
    if not args.tree:
        try:
            base = GitTree(args.zephyr, rec["meta"]["commit"])
        except SystemExit:
            base = None
    results = run_check(rec, tree)
    if base is not None and args.verify:
        again = run_check(rec, base)
        bad = [r for r in again if r.status not in ("unchanged",)]
        if bad:
            print("error: the record does not match its own commit "
                  f"({', '.join(sorted({r.name for r in bad}))}); record again")
            return 2
    counts = {}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
    print(f"check: record {rec['meta']['commit'][:12]} against {tree.label} "
          f"({tree.commit[:12]})")
    print("summary: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    for r in results:
        if r.status in ("unchanged",) and not args.all:
            continue
        if r.status == "shifted" and not args.all:
            continue
        extra = ""
        if r.new is not None and r.new.notes:
            extra = "  [" + "; ".join(r.new.notes) + "]"
        print(f"{r.status:14} {r.name:32} {loc(r.old)} -> {loc(r.new)}{extra}"
              + (f"  {r.note}" if r.note else ""))
        if args.diff and r.status in ("changed", "changed-trace", "moved-changed"):
            d = source_diff(base, tree, r)
            if d:
                print("    " + d.replace("\n", "\n    "))
    if args.json:
        Path(args.json).write_text(json.dumps([
            {"name": r.name, "status": r.status, "old": r.old,
             "new": r.new.as_record() if r.new else None} for r in results], indent=1) + "\n")
    return 1 if any(r.status in SEVERE for r in results) else 0


def cmd_log(args):
    rec = load_record(args)
    names = list(rec["functions"])
    revs = list(args.revs)
    if args.file:
        revs += [x.split()[0] for x in Path(args.file).read_text().splitlines()
                 if x.strip() and not x.startswith("#")]
    if args.range:
        files = sorted({d["file"] for e in rec["functions"].values() for d in e["defs"]})
        r = subprocess.run(["git", "-C", str(args.zephyr), "log", "--no-merges", "--reverse",
                            "--format=%H", args.range, "--", *files],
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit("error: git log: " + r.stderr.strip())
        revs += r.stdout.split()
        print(f"{len(revs)} commits in {args.range} touch the {len(files)} files of the record "
              "(a moved file is not followed)")
    rc = 0
    for rev in revs:
        new = GitTree(args.zephyr, rev)
        old = GitTree(args.zephyr, rev + "^")
        olddefs = extract(old, names)
        newdefs = extract(new, names)
        changed = []
        for n in names:
            od = [d.as_record() for d in olddefs[n]]
            for r in compare(n, od, newdefs[n]):
                if r.status not in ("unchanged", "shifted"):
                    changed.append(r)
        subj = subprocess.run(["git", "-C", str(args.zephyr), "log", "-1", "--format=%s",
                               new.commit], capture_output=True, text=True).stdout.strip()
        if changed or not args.quiet:
            print(f"{new.commit[:11]} {subj}")
        if not changed and not args.quiet:
            print("    no recorded name changed")
        for r in changed:
            print(f"    {r.status:14} {r.name:32} {loc(r.old)} -> {loc(r.new)}")
            if args.diff:
                d = source_diff(old, new, r)
                if d:
                    print("        " + d.replace("\n", "\n        "))
        if changed:
            rc = 1
    return rc


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--zephyr", type=Path,
                    default=Path(os.environ.get("ZEPHYR_BASE", SPEC.parent.parent.parent / "zephyr")),
                    help="the Zephyr git repository (default: $ZEPHYR_BASE)")
    ap.add_argument("--tree", type=Path, help="read a plain directory instead of git")
    ap.add_argument("--record", type=Path, default=DEFAULT_RECORD)
    ap.add_argument("--spec", type=Path, default=SPEC)
    sub = ap.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("record", help="write the record at the pin")
    p.add_argument("--commit", help="the pin (default: the commit of the record)")
    p = sub.add_parser("tags", help="each tag names a definition at the pin")
    p.add_argument("--commit", help="check at this commit, not at the pin")
    p = sub.add_parser("check", help="compare the record with another commit")
    p.add_argument("--against", required=True)
    p.add_argument("--all", action="store_true", help="also list unchanged names")
    p.add_argument("--diff", action="store_true", help="show the source diff of a change")
    p.add_argument("--json", help="write the results to this file")
    p.add_argument("--no-verify", dest="verify", action="store_false",
                   help="do not compare the record with its own commit first")
    p = sub.add_parser("log", help="which commit changed a recorded body")
    p.add_argument("revs", nargs="*")
    p.add_argument("--file", help="a file with one commit on each line")
    p.add_argument("--range", help="the commits A..B that touch a file of the record")
    p.add_argument("--quiet", action="store_true", help="list only commits with a change")
    p.add_argument("--diff", action="store_true")
    args = ap.parse_args()
    return {"record": cmd_record, "tags": cmd_tags, "check": cmd_check,
            "log": cmd_log}[args.mode](args)


if __name__ == "__main__":
    sys.exit(main())
