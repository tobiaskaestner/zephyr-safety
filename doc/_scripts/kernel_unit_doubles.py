#!/usr/bin/env python3
# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""The test doubles of the kernel unit tests, read from the sources.

Usage:
  kernel_unit_doubles.py catalog            print the page "Test doubles" (Doxygen)
  kernel_unit_doubles.py unit <unit>        print the doubles of each test of a unit
  kernel_unit_doubles.py check [--deploy D] find drift, exit status 1 on an error

The harness of the kernel unit tests (``tests/kernel/unit``) replaces each
function below a unit with a test double. This script reads the doubles from
the sources. Nothing in its output is written by hand, except the known limits
(``common/fake_limits.yaml``). Each known limit has a stable id ``TDL-<n>``
("test double limit"). The number is not a rank: a new limit gets the next
free number, and an id is never used again or changed.

- The fakes: ``DEFINE_FAKE_*`` in ``common/fakes/<group>.c`` (the fake group)
  and ``DECLARE_FAKE_*`` in the shadow headers and in ``common/include/fakes``.
  The default of a fake after the reset is the default of FFF (0, NULL or
  false), or the value that the reset rule of the group sets.
- The real code: the copies between the markers ``KERNEL_UNIT_REAL_COPY_BEGIN``
  and ``KERNEL_UNIT_REAL_COPY_END`` (see ``common/check_real_copies.py``).
- The shared models: the ``@name`` sections of ``kernel_unit_models.h``. The
  text of a section gives the assumption of the model.
- The reference fake: ``kernel_unit_sched_ref_install()`` in
  ``common/fakes/sched_ref.c`` sets the custom fakes. The comment of each
  custom fake names the operator of ``spec/tla/lib/Scheduler.tla``. Each
  operator name becomes a relative link to its definition on the page of
  the formal model in the architecture document (``formal-model.rst``).
  Both documents deploy below ``<build>/deploy/html``.
- The callbacks of a test descriptor: an FFF fake of a test source that the
  test source puts into the initializer of a structure (for example the
  statistics descriptor of an object type). The unit calls it through the
  descriptor. It is not a function of a layer below.
- The fake groups of a unit: ``kernel_unit_fakes()`` and
  ``kernel_unit_fakes_ifdef()`` in ``<unit>/CMakeLists.txt``.
- The use in a test: the statements of the test body, of the local functions
  that it calls or gives as an argument, and of the shared functions that it
  calls. A statement ``<fake>_fake.return_val = x``, ``SET_RETURN_SEQ()``,
  ``<fake>_fake.custom_fake = f`` or ``SET_CUSTOM_FAKE_SEQ()`` configures a
  fake. A read of ``call_count``, ``argN_val`` or ``argN_history``, and the
  history helpers (``zassert_call_history()``, ``zassert_called_before()``,
  ``KERNEL_UNIT_FN()``) check its calls. The ``before`` function of the
  suite (``ZTEST_SUITE()``) applies to each test of the suite.

The analysis reads the C text, not a preprocessed file. It sees the
statements of all ``#if`` branches and of all branches of an ``if``. Thus the
result is the set of doubles that a test can use. A double that a test gets
only from a pointer that it reads at run time is not in the result.

The Doxygen input filter of the Kernel Unit Test Specification
(``doxygen_filter_kernel_unit.py``) calls this module. A unit with the marker
``@kunit_interfaces`` in the file group of one of its test sources gets the
generated sections. The table of the unit goes after the marker.

The check finds the drift of the hand-written parts: a selector of a known
limit that matches no test, a bad limit id, a TLA+ link without its anchor,
a local custom fake without a comment, a unit test source in the INPUT of
the document without a unit marker, and a doc comment that does not name a
fake that the test body configures. Only the errors fail the check.
"""

import argparse
import html
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

SAFETY_BASE = Path(__file__).resolve().parents[2]
HARNESS = SAFETY_BASE / "tests" / "kernel" / "unit"
DOXYFILE = SAFETY_BASE / "doc" / "dox" / "kernel-unit-testspec" / "Doxyfile.in"

# The TLA+ library and the page of the architecture document that shows it.
# The reference fake implements the module CONTRACT. A link goes from the
# Doxygen page (deploy/html/<doxygen id>/) to deploy/html/<ARCH_DOC>/<page>.
TLA_LIB = SAFETY_BASE / "spec" / "tla" / "lib"
CONTRACT = "Scheduler"
ARCH_DOC = "architecture"
MODEL_RST = SAFETY_BASE / "doc" / "specification" / "architecture" / "formal-model.rst"
MODEL_PAGE = "formal-model.html"

# The marker of a test source that has the generated sections. It is an alias
# of the Doxyfile (a heading), so that a doc comment with the marker is also
# valid without this filter.
MARKER = "@kunit_interfaces"

# The page of the catalog, and the prefix of its anchors.
PAGE = "kunit_doubles"


# --------------------------------------------------------------------------
# C text


def mask(text):
    """The text with comments, strings and character constants as blanks.

    The result has the same length and the same line breaks, so an offset in
    the result is an offset in the text. Also returns the comments as
    (start, end, text) with end after the closing ``*/``."""
    out = list(text)
    comments = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == "/" and text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            comments.append((i, j, text[i:j]))
            for k in range(i, j):
                if out[k] != "\n":
                    out[k] = " "
            i = j
        elif c == "/" and text.startswith("//", i):
            j = text.find("\n", i)
            j = n if j < 0 else j
            for k in range(i, j):
                out[k] = " "
            i = j
        elif c in "\"'":
            j = i + 1
            while j < n and text[j] != c and text[j] != "\n":
                j += 2 if text[j] == "\\" else 1
            for k in range(i + 1, min(j, n)):
                out[k] = " "
            i = j + 1
        else:
            i += 1
    return "".join(out), comments


CPLUSPLUS = re.compile(r"^\s*#\s*if(?:def\s+__cplusplus|\s+defined\s*\(?\s*__cplusplus)")


def blank_directives(code):
    """The masked code with each preprocessor line (and its continuations) blank.

    A block ``#ifdef __cplusplus`` (``extern "C" {`` and its ``}``) is blank
    too, so that the functions of a header are at the top level."""
    lines = code.split("\n")
    cont = False
    cpp = False
    for k, line in enumerate(lines):
        if CPLUSPLUS.match(line):
            cpp = True
        if cont or cpp or line.lstrip().startswith("#"):
            if cpp and re.match(r"^\s*#\s*endif", line):
                cpp = False
            cont = line.rstrip().endswith("\\")
            lines[k] = " " * len(line)
    return "\n".join(lines)


def match_paren(code, i, pair="()"):
    """The offset after the parenthesis (or the other pair) that closes the one at offset i."""
    depth = 0
    for k in range(i, len(code)):
        if code[k] == pair[0]:
            depth += 1
        elif code[k] == pair[1]:
            depth -= 1
            if depth == 0:
                return k + 1
    return len(code)


@dataclass
class Function:
    name: str
    body: str  # masked code: the braces of a function, the text of a macro
    file: Path
    line: int  # 1-based line of the definition
    comment: str = ""  # the comment directly before the definition
    test: bool = False
    suite: str = ""


ZTEST_SIG = re.compile(r"\bZTEST\s*\(\s*(\w+)\s*,\s*(\w+)\s*\)\s*$")
FUNC_SIG = re.compile(r"\b([A-Za-z_]\w*)\s*\((?:[^()]|\([^()]*\))*\)\s*$")
KEYWORDS = {"if", "for", "while", "switch", "return", "sizeof", "defined"}
MACRO = re.compile(r"^[ \t]*#[ \t]*define[ \t]+(\w+)\(([^)]*)\)", re.M)


def comment_before(text, comments, start):
    """The text of the comment that ends directly before offset start, or ""."""
    best = ""
    for c0, c1, ctext in comments:
        if c1 <= start and not text[c1:start].strip():
            best = ctext
    return best


def functions_of(path):
    """The function definitions, the ZTESTs and the function-like macros of a file."""
    text = path.read_text(encoding="utf-8", errors="surrogateescape")
    code, comments = mask(text)
    flat = blank_directives(code)
    found = []
    depth, boundary, open_at = 0, 0, None
    for i, ch in enumerate(flat):
        if ch == "{":
            if depth == 0:
                open_at = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and open_at is not None:
                sig_text = flat[boundary:open_at]
                start = boundary + len(sig_text) - len(sig_text.lstrip())
                sig = " ".join(sig_text.split())
                body = code[open_at:i + 1]
                line = text.count("\n", 0, start) + 1
                m = ZTEST_SIG.search(sig)
                f = None
                if m:
                    f = Function(m.group(2), body, path, line, test=True, suite=m.group(1))
                elif "=" not in sig:
                    m = FUNC_SIG.search(sig)
                    if m and m.group(1) not in KEYWORDS:
                        f = Function(m.group(1), body, path, line)
                if f is not None:
                    f.comment = comment_before(text, comments, start)
                    found.append(f)
                boundary = i + 1
        elif ch == ";" and depth == 0:
            boundary = i + 1
    for m in MACRO.finditer(text):
        end = m.end()
        while True:
            nl = text.find("\n", end)
            if nl < 0:
                end = len(text)
                break
            if not text[:nl].rstrip().endswith("\\"):
                end = nl
                break
            end = nl + 1
        line = text.count("\n", 0, m.start()) + 1
        found.append(Function(m.group(1), code[m.end():end], path, line,
                              comment=comment_before(text, comments, m.start())))
    return found


DOX_REF = re.compile(r"[@\\]ref\s+\S+\s+\"([^\"]*)\"|[@\\]ref\s+(\S+)")
DOX_WORD = re.compile(r"[@\\](?:p|c|a|e|b|em)\s+(\S+)")
DOX_BRACE = re.compile(r"[@\\]\w+\{([^}]*)\}")
DOX_OTHER = re.compile(r"[@\\](?!\\)[A-Za-z_]+\b\s*")


def plain(text):
    """Text of a comment without Doxygen commands.

    ``@ref x "text"`` gives text, ``@ref x``, ``@p x``, ``@c x`` and ``@a x``
    give x, ``@kconfig{X}`` gives X. Each other command is removed."""
    text = DOX_REF.sub(lambda m: m.group(1) if m.group(1) is not None else m.group(2), text)
    text = DOX_WORD.sub(r"\1", text)
    text = DOX_BRACE.sub(r"\1", text)
    text = DOX_OTHER.sub("", text)
    return " ".join(text.split())


def first_sentence(comment):
    """The first sentence of a comment, without the comment markers and commands."""
    lines = []
    for line in comment.splitlines():
        line = re.sub(r"^\s*/\*+!?<?|\*+/\s*$|^\s*\*", "", line).strip()
        if line.startswith(("@{", "@}")):
            continue
        line = re.sub(r"^@(brief|name)\s*", "", line)
        if not line:
            if lines:
                break
            continue
        lines.append(line)
    text = plain(" ".join(lines))
    m = re.match(r"(.+?[.:])(\s|$)", text)
    return (m.group(1) if m else text).rstrip(":") + ("" if not m or m.group(1).endswith(".") else ".")


def comment_body(comment):
    """The text of a comment without the markers, as lines."""
    out = []
    for line in comment.splitlines():
        line = re.sub(r"^\s*/\*+!?", "", line)
        line = re.sub(r"\*+/\s*$", "", line)
        line = re.sub(r"^\s*\* ?", "", line)
        out.append(line.rstrip())
    while out and not out[0].strip():
        out.pop(0)
    while out and not out[-1].strip():
        out.pop()
    return out


# --------------------------------------------------------------------------
# The harness


@dataclass
class Fake:
    name: str
    group: str = ""
    header: str = ""  # path relative to common/include
    returns: str = ""  # the C return type; "" for void
    default: str = ""  # the value after the reset, if the rule sets one
    hand_written: bool = False  # not a DEFINE_FAKE_* of FFF
    descriptor: str = ""  # a fake of a test source: the structure that has it as a callback

    def default_text(self):
        if self.default:
            return f"returns {self.default}"
        if not self.returns:
            return "records the call"
        if "*" in self.returns:
            return "returns NULL"
        if self.returns.strip() == "bool":
            return "returns false"
        return "returns 0"


@dataclass
class ModelSection:
    title: str
    text: list  # lines of the section comment
    functions: list = field(default_factory=list)
    slug: str = ""


@dataclass
class RefFake:
    fake: str
    custom: str  # the name of the custom fake in sched_ref.c
    comment: str


@dataclass
class RealCopy:
    names: list
    shadow: str
    real: str


DEFINE = re.compile(
    r"\bDEFINE_FAKE_(?:VALUE_FUNC(?:_VARARG)?\s*\(\s*([^,()]+?)\s*,\s*(\w+)"
    r"|VOID_FUNC(?:_VARARG)?\s*\(\s*(\w+))\s*[,)]")
DECLARE = re.compile(
    r"\bDECLARE_FAKE_(VALUE|VOID)_FUNC(?:_VARARG)?\s*\(\s*([^,()]+?)\s*[,)]\s*(\w+)?")
HAND = re.compile(r"^(\w+)_Fake\s+(\w+)_fake\s*;", re.M)
RESET_VALUE = re.compile(r"\b(\w+)_fake\.return_val\s*=\s*([^;]+);")
REAL_BEGIN = re.compile(r"/\*\s*KERNEL_UNIT_REAL_COPY_BEGIN\s+(\S+)\s*\*/")
STATIC_INLINE_NAME = re.compile(r"\b(\w+)\s*\(")


def tla_anchor(module, name=None):
    """The HTML id of a TLA+ module or definition.

    This is the rule of anchor_id() in doc/_extensions/tla_domain.py. A copy,
    so that the filter does not need Sphinx. A test compares the two."""

    def clean(text):
        return re.sub(r"[^A-Za-z0-9_]", lambda m: f"-x{ord(m.group(0)):x}-", text)

    if name is None:
        return f"tla-module-{clean(module)}"
    return f"tla-{clean(module)}-{clean(name)}"


@dataclass
class TlaRef:
    """A name of a TLA+ operator in the text of a comment."""
    start: int
    end: int
    text: str  # as the comment writes it, for example WaitQueue!Best
    module: str
    name: str
    found: bool  # the module of the library defines the name

    @property
    def anchor(self):
        return tla_anchor(self.module, self.name)

    def href(self):
        return f"../{ARCH_DOC}/{MODEL_PAGE}#{self.anchor}"


TLA_TOKEN = re.compile(r"\b(?:([A-Z]\w*)!)?([A-Za-z]\w*)\b(\()?")


class Tla:
    """The definitions of the modules of the TLA+ library."""

    def __init__(self, lib=TLA_LIB):
        self.lib = Path(lib)
        self.defs = {}  # module: set of the names of its definitions
        self.instances = {}  # name of an INSTANCE in CONTRACT: module
        if not self.lib.is_dir():
            return
        sys.path.insert(0, str(SAFETY_BASE / "doc" / "_extensions"))
        from tla_extract import parse_file  # noqa: E402

        for p in sorted(self.lib.glob("*.tla")):
            mod = parse_file(str(p))
            self.defs[mod.name] = {u.name for u in mod.units if u.kind == "definition"}
            if mod.name == CONTRACT:
                text = p.read_text(encoding="utf-8")
                self.instances = dict(re.findall(r"^(\w+)\s*==\s*INSTANCE\s+(\w+)", text, re.M))

    def refs(self, text):
        """The operator names in a text.

        ``Module!Name`` is always an operator name. A name without a module
        is an operator of CONTRACT if it has a lower-case letter and an
        opening parenthesis follows it (``WakeFirst(o, ret, data)``), or if
        CONTRACT defines it and it has two upper-case letters
        (``ArmedArePending``). Other words are text."""
        out = []
        contract = self.defs.get(CONTRACT, set())
        for m in TLA_TOKEN.finditer(text):
            qual, name, call = m.groups()
            if qual:
                module = self.instances.get(qual, qual)
                end = m.start(2) + len(name)
                out.append(TlaRef(m.start(), end, text[m.start():end], module, name,
                                  name in self.defs.get(module, set())))
                continue
            if not name[0].isupper() or not re.search(r"[a-z]", name):
                continue
            camel = sum(c.isupper() for c in name) >= 2
            if call or (camel and name in contract):
                out.append(TlaRef(m.start(), m.start() + len(name), name, CONTRACT, name,
                                  name in contract))
        return out


def rendered_anchors(tla, rst):
    """The anchors that the tla directives of a page give, read from the .rst.

    ``tla:module`` gives the anchor of the module, and with ``:body:`` the
    anchor of each definition. ``tla:module-body`` gives each definition
    except ``:exclude:``. ``tla:definition`` and ``tla:property`` give one."""
    ids = set()
    lines = Path(rst).read_text(encoding="utf-8").splitlines()
    current = None
    k = 0
    while k < len(lines):
        m = re.match(r"\.\.\s+tla:(module|module-body|definition|property)::\s*(\S*)", lines[k])
        k += 1
        if not m:
            continue
        kind, arg = m.groups()
        opts = {}
        while k < len(lines) and re.match(r"\s+:", lines[k]):
            o = re.match(r"\s+:([\w-]+):\s*(.*)", lines[k])
            if o:
                opts[o.group(1)] = o.group(2).strip()
            k += 1
        if kind == "module":
            current = Path(arg).stem
            ids.add(tla_anchor(current))
            if "body" in opts:
                ids |= {tla_anchor(current, n) for n in tla.defs.get(current, ())}
        elif kind == "module-body":
            mod = Path(arg or opts.get("module", current or "")).stem
            skip = set(re.split(r"[\s,]+", opts.get("exclude", "")))
            ids |= {tla_anchor(mod, n) for n in tla.defs.get(mod, ()) if n not in skip}
        else:
            mod, name = arg.split("!", 1) if "!" in arg else (opts.get("module", current), arg)
            if mod:
                ids.add(tla_anchor(Path(mod).stem, name))
    return ids


class Harness:
    """The fakes, models, real copies and the reference fake of the harness."""

    def __init__(self, root=HARNESS, tla_lib=TLA_LIB):
        self.root = Path(root)
        self.tla = Tla(tla_lib)
        self.common = self.root / "common"
        self.include = self.common / "include"
        self.fakes = {}
        self.groups = {}  # group: [fake names], in the order of the file
        self.group_data = {}  # group: [data names] (no fakes)
        self.headers = {}  # header (relative): comment text
        self.real = []
        self.models = []
        self.shared = {}  # name: Function, of the models header, kernel_unit.h, sched_ref
        self.model_of = {}  # function name: ModelSection
        self.ref = {}  # fake: RefFake
        self.ref_api = set()
        self._read_fakes()
        self._read_real_copies()
        self._read_models()
        self._read_ref()

    def _read_fakes(self):
        for h in sorted(self.include.rglob("*.h")):
            text = h.read_text(encoding="utf-8")
            rel = h.relative_to(self.include).as_posix()
            code, comments = mask(text)
            for m in DECLARE.finditer(code):
                kind, first, second = m.groups()
                name, ret = (second, first) if kind == "VALUE" else (first, "")
                if kind == "VOID" and second is None:
                    name = first
                f = self.fakes.setdefault(name, Fake(name))
                f.header, f.returns = rel, ret
            if comments:
                # The first comment after the license comment describes the header.
                for c0, c1, ctext in comments:
                    if "SPDX-License-Identifier" in ctext:
                        continue
                    self.headers[rel] = ctext
                    break
        for c in sorted((self.common / "fakes").glob("*.c")):
            group = c.stem
            text = c.read_text(encoding="utf-8")
            code, _ = mask(text)
            found = []
            for m in DEFINE.finditer(code):
                ret, vname, void_name = m.groups()
                name = vname or void_name
                f = self.fakes.setdefault(name, Fake(name))
                f.group = group
                if vname:
                    f.returns = ret
                found.append((m.start(), name))
            for m in HAND.finditer(code):
                if m.group(1) == m.group(2):
                    f = self.fakes.setdefault(m.group(2), Fake(m.group(2)))
                    f.group, f.hand_written = group, True
                    found.append((m.start(), f.name))
            names = list(dict.fromkeys(n for _, n in sorted(found)))
            # A value that the reset rule sets: return_val in a ZTEST_RULE function.
            for fn in functions_of(c):
                if fn.name.endswith("_reset"):
                    for m in RESET_VALUE.finditer(fn.body):
                        if m.group(1) in self.fakes:
                            self.fakes[m.group(1)].default = m.group(2).strip()
            self.groups[group] = names
            if not names:
                self.group_data[group] = re.findall(r"^struct\s+\w+\s+(\w+)\s*;", code, re.M)

    def _read_real_copies(self):
        for h in sorted(self.include.rglob("*.h")):
            text = h.read_text(encoding="utf-8")
            for m in REAL_BEGIN.finditer(text):
                end = text.find("KERNEL_UNIT_REAL_COPY_END", m.end())
                block = text[m.end():end]
                names = []
                for line in block.splitlines():
                    s = re.match(r"\s*static\s+inline\s+[\w\s\*]+?\b(\w+)\s*\(", line)
                    d = re.match(r"\s*#\s*define\s+(\w+)", line)
                    if s:
                        names.append(s.group(1))
                    elif d:
                        names.append(d.group(1))
                names = list(dict.fromkeys(names))
                shadow = h.relative_to(self.include).as_posix()
                same = [r for r in self.real if r.shadow == shadow and r.real == m.group(1)]
                if same:
                    same[0].names += [x for x in names if x not in same[0].names]
                elif names:
                    self.real.append(RealCopy(names, shadow, m.group(1)))

    def _read_models(self):
        path = self.include / "kernel_unit_models.h"
        if not path.exists():
            return
        text = path.read_text(encoding="utf-8")
        _, comments = mask(text)
        sections = []
        for c0, c1, ctext in comments:
            m = re.search(r"@name\s+(.+)", ctext)
            if m:
                body = comment_body(ctext)[1:]
                body = [x for x in body if x.strip() != "@{"]
                sections.append((c0, ModelSection(m.group(1).strip(), body)))
            elif "@}" in ctext and sections and ctext.strip() == "/** @} */":
                sections.append((c0, None))
        funcs = functions_of(path)
        if (self.include / "kernel_unit.h").exists():
            funcs += functions_of(self.include / "kernel_unit.h")
        for f in funcs:
            self.shared[f.name] = f
        # The section of each function of the models header: the last @name
        # before it that is still open.
        line_of = {}
        for off, sec in sections:
            line_of[text.count("\n", 0, off) + 1] = sec
        marks = sorted(line_of.items())
        for f in funcs:
            if f.file != path:
                continue
            current = None
            for ln, sec in marks:
                if ln > f.line:
                    break
                current = sec
            if current is not None:
                current.functions.append(f.name)
                self.model_of[f.name] = current
        self.models = [s for _, s in sections if s is not None]
        for s in self.models:
            s.slug = re.sub(r"\W+", "_", s.title.lower()).strip("_")

    def _read_ref(self):
        path = self.common / "fakes" / "sched_ref.c"
        self.ref_text = []
        if not path.exists() or not (self.include / "kernel_unit_sched_ref.h").exists():
            return
        funcs = {f.name: f for f in functions_of(path)}
        hfuncs = (self.include / "kernel_unit_sched_ref.h").read_text(encoding="utf-8")
        self.ref_api = set(re.findall(r"^\w[\w\s\*]*?\b(kernel_unit_sched_ref_\w+)\s*\(",
                                      hfuncs, re.M))
        install = funcs.get("kernel_unit_sched_ref_install")
        if install is None:
            return
        for m in re.finditer(r"\b(\w+)_fake\.custom_fake\s*=\s*(\w+)", install.body):
            fake, custom = m.groups()
            comment = funcs[custom].comment if custom in funcs else ""
            self.ref[fake] = RefFake(fake, custom, comment)
        for name, f in funcs.items():
            if name in self.ref_api:
                m = re.search(r"(/\*\*(?:(?!\*/).)*\*/)\s*[\w\s\*]*?\b" + name + r"\s*\(",
                              hfuncs, re.S)
                if m:
                    f.comment = m.group(1)
                self.shared[name] = f
        _, comments = mask(hfuncs)
        for c0, c1, ctext in comments:
            if "@defgroup kernel_unit_sched_ref" in ctext:
                self.ref_text = comment_body(ctext)
                break
        else:
            self.ref_text = []

    def kind_of_custom(self, name, unit):
        """'reference', 'model' or 'local' for the name of a custom fake."""
        if any(r.custom == name for r in self.ref.values()):
            return "reference"
        if name in self.model_of:
            return "model"
        if unit is not None and name in unit.local:
            return "local"
        return "other"


# --------------------------------------------------------------------------
# A unit and its tests


@dataclass
class Use:
    """One configuration or check of a fake, or one call of a shared function."""
    what: str  # 'config', 'check', 'shared', 'action', 'call'
    fake: str = ""
    how: str = ""  # config: value, sequence, custom, custom_seq, plain; check: kinds
    detail: str = ""  # the value, or the name of the custom fake
    via: tuple = ()  # the local and shared functions between the test and the statement
    origin: str = "test"  # 'test', or 'suite' (the before function of the suite)


CONFIG = re.compile(r"\b(\w+)_fake\.(return_val|custom_fake)\s*=(?!=)\s*([^;]*);")
SEQ = re.compile(r"\bSET_RETURN_SEQ\s*\(\s*(\w+)")
CSEQ = re.compile(r"\bSET_CUSTOM_FAKE_SEQ\s*\(\s*(\w+)\s*,\s*(\w+)")
READ = re.compile(r"\b(\w+)_fake\.(call_count|arg\d+_val|arg\d+_history|return_val_history)\b")
HIST = re.compile(r"\b(zassert_call_history)\s*\(")
FN = re.compile(r"\bKERNEL_UNIT_FN\s*\(\s*(\w+)\s*\)")
BEFORE = re.compile(r"\bzassert_called_before\s*\(\s*(\w+)\s*,\s*(\w+)")
CALL = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
IDENT = re.compile(r"\b([A-Za-z_]\w*)\b")
CMAKE_FAKES = re.compile(r"kernel_unit_fakes(_ifdef)?\s*\(([^)]*)\)")
INCLUDE_UNIT = re.compile(r"#\s*include\s*<(kernel/[\w/]+\.c)>")
READ_KIND = {"call_count": "calls"}
# Helpers of kernel_unit.h that only name fakes: the fakes are the result.
NOT_LISTED = {"KERNEL_UNIT_FN", "KERNEL_UNIT_IF_ENABLED", "zassert_call_history",
              "zassert_called_before"}
# Shared functions that check: the test lists them as checks.
CHECKS = ("kernel_unit_assert", "zassert_stopped", "kernel_unit_sched_ref_assert_ok")
# The history helpers of kernel_unit.h. A call of one of them by the test
# checks the call history of all fakes. kernel_unit_history_index() is not
# here: KERNEL_UNIT_FN() in its argument names the fake.
HISTORY = {
    "kernel_unit_history_len": "the number of calls",
    "kernel_unit_history_equal": "the list of calls",
    "kernel_unit_history": "the list of calls",
}
NO_CALL = re.compile(r"\bzassert_equal\s*\(\s*kernel_unit_history_len\s*\(\s*\)\s*,\s*0U?\s*[,)]")
ALL_FAKES = "*"
# The functions of the reference fake that set its state for a test.
REF_SETUP = ("kernel_unit_sched_ref_thread", "kernel_unit_sched_ref_set_current",
             "kernel_unit_sched_ref_wait", "kernel_unit_sched_ref_env_",
             "kernel_unit_sched_ref_run_isr", "kernel_unit_sched_ref_timeout",
             "kernel_unit_sched_ref_abort", "kernel_unit_sched_ref_expect")


class Unit:
    """The test sources of one application and the doubles of each test."""

    def __init__(self, harness, name):
        self.h = harness
        self.name = name
        self.dir = harness.root / name
        self.sources = sorted((self.dir / "src").glob("*.c"))
        self.local = {}
        self.tests = []
        self.suites = {}  # suite: (setup, before)
        for src in self.sources:
            for f in functions_of(src):
                if f.test:
                    self.tests.append(f)
                elif f.name not in self.local:
                    self.local[f.name] = f
            text = src.read_text(encoding="utf-8")
            for m in re.finditer(r"\bZTEST_SUITE\s*\(([^;]*)\)\s*;", mask(text)[0]):
                args = [a.strip() for a in m.group(1).split(",")]
                if len(args) >= 4:
                    self.suites[args[0]] = (args[2], args[3])
        # Fakes that a test source defines itself (DEFINE_FAKE_* of FFF).
        self.local_fakes = {}
        for src in self.sources:
            code_ = mask(src.read_text(encoding="utf-8"))[0]
            for m in DEFINE.finditer(code_):
                ret, vname, void_name = m.groups()
                name = vname or void_name
                self.local_fakes[name] = Fake(name, group="", header=src.name,
                                              returns=ret if vname else "")
        # A fake of a test source in the initializer of a structure of the test
        # source is a callback of a test descriptor, not a fake of a layer below.
        for src in self.sources:
            code_ = blank_directives(mask(src.read_text(encoding="utf-8"))[0])
            for m in re.finditer(r"\b(\w+)\s*=\s*\{", code_):
                init = code_[m.end() - 1:match_paren(code_, m.end() - 1, "{}")]
                for name in re.findall(r"\.\w+\s*=\s*&?\s*(\w+)", init):
                    if name in self.local_fakes and not self.local_fakes[name].descriptor:
                        self.local_fakes[name].descriptor = m.group(1)
        self.kernel_source = ""
        for src in self.sources:
            m = INCLUDE_UNIT.search(src.read_text(encoding="utf-8"))
            if m:
                self.kernel_source = m.group(1)
                break
        self.fake_groups = []  # (condition or "", group)
        cm = self.dir / "CMakeLists.txt"
        if cm.exists():
            text = re.sub(r"#.*", "", cm.read_text(encoding="utf-8"))
            for m in CMAKE_FAKES.finditer(text):
                words = m.group(2).split()
                cond = words.pop(0) if m.group(1) else ""
                self.fake_groups += [(cond, w) for w in words]
        self._uses = {}
        self._suite_uses = {}

    def is_fake(self, name):
        return name in self.h.fakes or name in self.local_fakes

    # -- analysis ---------------------------------------------------------

    def _scan(self, body, via, origin, seen, out):
        events = []
        for m in CONFIG.finditer(body):
            fake, field_, value = m.group(1), m.group(2), " ".join(m.group(3).split())
            if field_ == "return_val":
                events.append((m.start(), Use("config", fake, "value", value, via, origin)))
            elif value in ("NULL", "0"):
                events.append((m.start(), Use("config", fake, "plain", "", via, origin)))
            else:
                events.append((m.start(), Use("config", fake, "custom", value, via, origin)))
        for m in SEQ.finditer(body):
            events.append((m.start(), Use("config", m.group(1), "sequence", "", via, origin)))
        for m in CSEQ.finditer(body):
            events.append((m.start(), Use("config", m.group(1), "custom_seq", m.group(2),
                                          via, origin)))
        for m in NO_CALL.finditer(body):
            events.append((m.start(), Use("check", ALL_FAKES, "no call",
                                          "kernel_unit_history_len", via, origin)))
        for m in re.finditer(r"\b(" + "|".join(HISTORY) + r")\s*\(", body):
            if not NO_CALL.match(body, max(0, m.start() - 40)) and not re.search(
                    r"zassert_equal\s*\(\s*$", body[max(0, m.start() - 40):m.start()]):
                events.append((m.start(), Use("check", ALL_FAKES, HISTORY[m.group(1)],
                                              m.group(1), via, origin)))
        for m in READ.finditer(body):
            kind = READ_KIND.get(m.group(2), "arguments")
            if m.group(2) == "return_val_history":
                kind = "return values"
            events.append((m.start(), Use("check", m.group(1), kind, "", via, origin)))
        for m in HIST.finditer(body):
            args = body[m.end() - 1:match_paren(body, m.end() - 1)]
            for name in IDENT.findall(args):
                if self.is_fake(name):
                    events.append((m.start(), Use("check", name, "call history", "", via,
                                                  origin)))
        for m in FN.finditer(body):
            if self.is_fake(m.group(1)):
                events.append((m.start(), Use("check", m.group(1), "call history", "", via,
                                              origin)))
        for m in BEFORE.finditer(body):
            for name in m.groups():
                if self.is_fake(name):
                    events.append((m.start(), Use("check", name, "order", "", via, origin)))
        # Calls of local and shared functions, and local functions given as an
        # argument (an action of another thread, an observer).
        for m in IDENT.finditer(body):
            name = m.group(1)
            if name in seen or name in NOT_LISTED or (
                    name not in self.local and name not in self.h.shared):
                continue
            called = body[m.end():m.end() + 1] == "(" or re.match(r"\s*\(", body[m.end():])
            if name in self.local:
                f = self.local[name]
                # A custom fake is not an action: the assignment names it.
                before = body[max(0, m.start() - 40):m.start()]
                if not called and re.search(r"custom_fake\s*=\s*$|SET_CUSTOM_FAKE_SEQ\s*\([^,]*,\s*$",
                                            before):
                    continue
                kind = "call" if called else "action"
                events.append((m.start(), Use(kind, "", "", name, via, origin)))
                sub = []
                self._scan(f.body, via + (name,), origin, seen | {name}, sub)
                events += [(m.start(), u) for u in sub]
            elif called:
                f = self.h.shared[name]
                events.append((m.start(), Use("shared", "", "", name, via, origin)))
                sub = []
                self._scan(f.body, via + (name,), origin, seen | {name}, sub)
                # From a shared function, take only its configurations: a
                # shared check is listed by its name.
                # A shared function that it calls is not listed: the test does
                # not call it.
                events += [(m.start(), u) for u in sub if u.what == "config"]
        events.sort(key=lambda e: e[0])
        out += [u for _, u in events]

    def uses(self, test):
        """The uses of the test itself, then of the before function of its suite."""
        if test.name in self._uses:
            return self._uses[test.name]
        out = []
        self._scan(test.body, (), "test", {test.name}, out)
        setup, before = self.suites.get(test.suite, ("NULL", "NULL"))
        for fn in (setup, before):
            if fn in self.local:
                sub = []
                self._scan(self.local[fn].body, (fn,), "suite", {fn}, sub)
                out += sub
        self._uses[test.name] = out
        return out

    def suite_uses(self, suite):
        """The uses of the setup and the before function of a suite."""
        if suite in self._suite_uses:
            return self._suite_uses[suite]
        out = []
        for fn in self.suites.get(suite, ("NULL", "NULL")):
            if fn in self.local:
                self._scan(self.local[fn].body, (fn,), "suite", {fn}, out)
        self._suite_uses[suite] = out
        return out

    def uses_reference(self, uses):
        return any(u.what == "shared" and u.detail == "kernel_unit_sched_ref_install"
                   for u in uses)

    def named(self):
        """The fakes that the kernel source file of the unit names."""
        if getattr(self, "_named", None) is None:
            ktext = self.kernel_text()
            self._named = set()
            for f in list(self.h.fakes) + list(self.local_fakes):
                if ktext and re.search(rf"\b{re.escape(f)}\b", ktext):
                    self._named.add(f)
                elif f.startswith("unit_") and ktext and re.search(rf"\b{f[5:]}\b", ktext):
                    self._named.add(f)  # the shadow arch_*() functions call unit_arch_*()
        return self._named

    def kernel_text(self):
        base = Path(os.environ.get("ZEPHYR_BASE", SAFETY_BASE.parent / "zephyr"))
        p = base / self.kernel_source
        if self.kernel_source and p.exists():
            return mask(p.read_text(encoding="utf-8"))[0]
        return ""


# --------------------------------------------------------------------------
# Known limits


@dataclass
class Limit:
    id: str  # TDL-<n>: stable, not a rank
    severity: str
    title: str
    text: str
    applies: list
    review: str = ""  # history: the finding of the review that found the limit
    unknown: list = field(default_factory=list)  # keys that a limit cannot have


LIMIT_ID = re.compile(r"^TDL-[1-9]\d*$")
LIMIT_IN_TEXT = re.compile(r"\bTDL-[1-9]\d*\b")
LIMIT_KEYS = {"id", "severity", "title", "text", "applies", "review"}
SEVERITIES = ("high", "medium", "low")


def read_limits(harness):
    path = harness.common / "fake_limits.yaml"
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [Limit(str(x["id"]), x.get("severity", ""), x["title"], x.get("text", "").strip(),
                  x.get("applies") or [], str(x.get("review", "")), sorted(set(x) - LIMIT_KEYS))
            for x in data.get("limits", [])]


def limit_anchor(lid):
    """The Doxygen anchor of a limit on the page "Test doubles"."""
    return f"{PAGE}_limit_{lid.replace('-', '_')}"


def limit_ref(lid):
    return f'@ref {limit_anchor(lid)} "{lid}"'


SELECTOR_KEYS = {"fake", "how", "custom", "uses", "checks", "unit", "reference"}


def selector_matches(sel, unit, uses):
    """True if the uses of a test match one selector of a limit.

    ``fake``, ``how`` and ``custom`` must match the same configuration.
    ``uses`` is a local or shared function that the test calls or gives as an
    argument. ``checks`` is a fake whose calls the test checks. ``unit``
    restricts the selector to one unit. ``reference: false`` (or true) needs a
    test without (or with) the reference fake."""
    if "unit" in sel and sel["unit"] != unit.name:
        return False
    if "reference" in sel and bool(sel["reference"]) != unit.uses_reference(uses):
        return False
    if {"fake", "how", "custom"} & sel.keys():
        hows = sel.get("how")
        hows = [hows] if isinstance(hows, str) else hows
        ok = False
        for u in uses:
            if u.what != "config":
                continue
            if "fake" in sel and u.fake != sel["fake"]:
                continue
            if hows and u.how not in hows:
                continue
            if "custom" in sel and u.detail != sel["custom"]:
                continue
            ok = True
            break
        if not ok:
            return False
    if "uses" in sel:
        names = {u.detail for u in uses if u.what in ("shared", "action", "call")}
        names |= {v for u in uses for v in u.via}
        if sel["uses"] not in names:
            return False
    if "checks" in sel:
        if not any(u.what == "check" and u.fake == sel["checks"] for u in uses):
            return False
    return True


def limits_of(limits, unit, uses):
    return [lim for lim in limits if any(selector_matches(s, unit, uses) for s in lim.applies)]


# --------------------------------------------------------------------------
# Doxygen text


def esc(text):
    """Text for a Doxygen comment: no command, no HTML tag, no automatic link."""
    return re.sub(r"([\\@#%$])", r"\\\1", html.escape(text, quote=False))


def code(text):
    return f"<code>{html.escape(text, quote=False)}</code>"


def rich(h, text):
    """Plain text of a comment for Doxygen, with links.

    Each TLA+ operator that the library defines links to its definition in
    the architecture document. Each id of a known limit (TDL-<n>) links to
    the limit on the page. A name that the library does not define stays
    text: the check reports it."""
    out, pos = [], 0
    for r in h.tla.refs(text):
        if not r.found:
            continue
        out.append(esc(text[pos:r.start]))
        out.append(f'<a href="{r.href()}">{esc(r.text)}</a>')
        pos = r.end
    out.append(esc(text[pos:]))
    return LIMIT_IN_TEXT.sub(lambda m: limit_ref(m.group(0)), "".join(out))


def is_callback(unit, name):
    """True for a fake of the test source that a test descriptor has as a callback."""
    return (unit is not None and name in unit.local_fakes and name not in unit.h.fakes
            and bool(unit.local_fakes[name].descriptor))


def fake_ref(name, unit=None):
    """A link to the fake on the page, or the name of a fake of the test source."""
    if is_callback(unit, name):
        return (f"{code(name + '()')} (callback of the test descriptor "
                f"{code(unit.local_fakes[name].descriptor)})")
    if unit is not None and name in unit.local_fakes and name not in unit.h.fakes:
        return f"{code(name + '()')} (fake of {code(unit.local_fakes[name].header)})"
    return f'@ref {PAGE}_fake_{name} "{name}()"'


def test_anchor(unit, test):
    return f"{PAGE}_test_{unit}_{test}"


def effective(h, unit, uses):
    """The configurations that stay: a later statement of the same call of the
    test (the same first function in via) replaces an earlier one of the same
    fake. The replaced one is in the attribute ``replaces`` of the later one."""
    out = []
    for u in uses:
        if u.what != "config":
            continue
        prev = next((x for x in reversed(out) if x.fake == u.fake), None)
        if (prev is not None and prev.via[:1] == u.via[:1] and u.via
                and prev.origin == u.origin and out[-1] is prev):
            out.pop()
            u = Use(u.what, u.fake, u.how, u.detail, u.via, u.origin)
            u.replaces = describe_config(h, unit, prev)
        out.append(u)
    return out


def describe_config(h, unit, u):
    if u.how == "value":
        return f"fixed value {code(u.detail)} (<code>return_val</code>)"
    if u.how == "sequence":
        return "sequence of return values (<code>SET_RETURN_SEQ()</code>)"
    if u.how == "plain":
        return "plain fake again (<code>custom_fake</code> = NULL)"
    kind = h.kind_of_custom(u.detail, unit)
    seq = " (sequence, <code>SET_CUSTOM_FAKE_SEQ()</code>)" if u.how == "custom_seq" else ""
    if kind == "model":
        sec = h.model_of[u.detail]
        return (f'model @ref {PAGE}_model_{sec.slug} "{esc(sec.title)}" '
                f"({code(u.detail + '()')}){seq}")
    if kind == "local":
        return (f'local custom fake @ref {PAGE}_local_{unit.name}_{u.detail} '
                f'"{u.detail}()"{seq}')
    return f"custom fake {code(u.detail + '()')}{seq}"


def first_paragraph(comment):
    """The first paragraph of a comment, as one line of plain text."""
    out = []
    for line in comment_body(comment):
        if not line.strip():
            if out:
                break
            continue
        out.append(line.strip())
    return plain(" ".join(out))


def operator_of(ref):
    """What the custom fake of the reference fake does: the first paragraph of its
    comment, after the name of the C function."""
    text = first_paragraph(ref.comment)
    m = re.match(r"[\w\s(),]*?\):\s*(.*)$", text)
    return m.group(1) if m else text


def via_text(u, skip=0):
    via = u.via[skip:]
    if not via:
        return ""
    return " (in " + ", ".join(code(v + "()") for v in via) + ")"


def render_test(h, unit, test, limits):
    """The text that the filter adds to the doc comment of a test: one line."""
    uses = unit.uses(test)
    own = [u for u in uses if u.origin == "test"]
    parts = []

    ref = unit.uses_reference(own)
    items = []
    for u in effective(h, unit, own):
        if ref and h.kind_of_custom(u.detail, unit) == "reference":
            continue
        rep = f", over {getattr(u, 'replaces')}" if hasattr(u, "replaces") else ""
        items.append(f"<li>{fake_ref(u.fake, unit)}: {describe_config(h, unit, u)}{via_text(u)}"
                     f"{rep}</li>")
    if ref:
        inst = next(u for u in own if u.what == "shared"
                    and u.detail == "kernel_unit_sched_ref_install")
        api = [u.detail for u in own if u.what == "shared" and u.detail.startswith(REF_SETUP)]
        api = list(dict.fromkeys(api))
        setup = ""
        if api:
            setup = ". Setup: " + ", ".join(code(a + "()") for a in api)
        ops = [f"{fake_ref(f)}: {rich(h, operator_of(h.ref[f]))}" for f in h.ref
               if f in unit.named()]
        opt = ""
        if ops:
            opt = (". For the calls of the unit, the reference fake does this:<ul>"
                   + "".join(f"<li>{x}</li>" for x in ops) + "</ul>")
        items.insert(0, f'<li>@ref {PAGE}_ref "Reference fake of the scheduler contract" for '
                        f"{len(h.ref)} fakes{via_text(inst)}{setup}{opt}</li>")
    actions = list(dict.fromkeys(u.detail for u in own if u.what == "action"))
    if actions:
        items.append("<li>Actions of other threads or of an observer: "
                     + ", ".join(code(a + "()") for a in actions) + "</li>")
    models = list(dict.fromkeys(u.detail for u in own if u.what == "shared"
                                and u.detail in h.model_of and not u.detail.startswith(CHECKS)))
    used_models = [m for m in models
                   if not any(c.what == "config" and m in c.via for c in own)]
    if used_models:
        items.append("<li>Shared helpers: " + ", ".join(
            f'@ref {PAGE}_model_{h.model_of[m].slug} "{m}()"' for m in used_models) + "</li>")
    if not items:
        items.append("<li>None: each fake has its default after the reset.</li>")
    suite = [u for u in uses if u.origin == "suite" and u.what == "config"]
    if suite:
        fn = suite[0].via[0]
        n = len({u.fake for u in suite})
        items.append(f'<li>Before each test: {code(fn + "()")} configures '
                     f'{n} {"fake" if n == 1 else "fakes"} (see @ref kernel_unit_{unit.name} '
                     f'"{esc(unit.kernel_source or unit.name)}").</li>')
    parts.append("<ul>" + "".join(items) + "</ul>")

    checks = {}
    for u in own:
        if u.what == "check":
            checks.setdefault(u.fake, []).append(u)
    shared_checks = list(dict.fromkeys(
        u.detail for u in own if u.what == "shared" and u.detail.startswith(CHECKS)))
    citems = []
    for fake, us in checks.items():
        kinds = ", ".join(dict.fromkeys(u.how for u in us))
        if fake == ALL_FAKES:
            helpers = ", ".join(code(x + "()") for x in dict.fromkeys(u.detail for u in us))
            citems.append(f"<li>Call history of all fakes: {kinds} ({helpers})</li>")
            continue
        vias = {u.via for u in us if u.via}
        where = ""
        if vias and all(u.via for u in us):
            where = " (in " + ", ".join(code(v + "()") for v in
                                        dict.fromkeys(x for vv in vias for x in vv)) + ")"
        citems.append(f"<li>{fake_ref(fake, unit)}: {kinds}{where}</li>")
    for s in shared_checks:
        f = h.shared.get(s)
        brief = esc(first_sentence(f.comment)) if f is not None and f.comment else ""
        citems.append(f"<li>{code(s + '()')}" + (f": {brief}" if brief else "") + "</li>")
    if not citems:
        citems.append("<li>None: the test checks only the state of the object and the "
                      "return values of the unit.</li>")
    checked = "@kunit_checks <ul>" + "".join(citems) + "</ul>"

    litems = [f"<li>{limit_ref(lim.id)} ({esc(lim.severity)}): {esc(lim.title)}</li>"
              for lim in limits_of(limits, unit, own)]
    suite_lims = limits_of(limits, unit, unit.suite_uses(test.suite))
    if suite_lims:
        litems.append("<li>Limits of the suite setup: "
                      + ", ".join(limit_ref(lim.id) for lim in suite_lims)
                      + f' (see @ref kernel_unit_{unit.name} '
                      f'"{esc(unit.kernel_source or unit.name)}")</li>')
    ltext = ("@kunit_limits <ul>" + "".join(litems) + "</ul>") if litems else ""
    return (f"@anchor {test_anchor(unit.name, test.name)} @kunit_doubles "
            + " ".join(parts) + " " + checked + " " + ltext).rstrip()


def unit_rows(h, unit):
    """{fake: {'config': {kind: n}, 'checked': n}} over the tests of a unit."""
    rows = {}
    for t in unit.tests:
        own = [u for u in unit.uses(t) if u.origin == "test"]
        ref = unit.uses_reference(own)
        kinds, checked = {}, set()
        for u in effective(h, unit, own):
            k = u.how
            if u.how in ("custom", "custom_seq"):
                k = h.kind_of_custom(u.detail, unit)
            kinds.setdefault(u.fake, set()).add(k)
        checked = {u.fake for u in own if u.what == "check" and u.fake != ALL_FAKES}
        if ref:
            for fake in h.ref:
                kinds.setdefault(fake, set()).add("reference")
        for fake, ks in kinds.items():
            r = rows.setdefault(fake, {"config": {}, "checked": 0})
            for k in ks:
                r["config"][k] = r["config"].get(k, 0) + 1
        for fake in checked:
            rows.setdefault(fake, {"config": {}, "checked": 0})["checked"] += 1
    return rows


KIND_TEXT = {
    "value": "fixed value", "sequence": "sequence", "plain": "plain again",
    "local": "local custom fake", "model": "model", "reference": "reference fake",
    "other": "other custom fake",
}


def render_unit(h, unit, limits):
    """The text that the filter adds after the marker in the file group: one line."""
    ktext = unit.kernel_text()
    named = unit.named()
    linked = {g for _, g in unit.fake_groups}
    rows = unit_rows(h, unit)
    # The reference fake replaces each scheduler fake. A row of a fake that
    # the unit does not name and no test configures or checks in another way
    # is left out.
    names = [f for f in h.fakes
             if (f in named and h.fakes[f].group in linked)
             or (f in rows and (rows[f]["checked"]
                                or set(rows[f]["config"]) - {"reference"}))]
    order = {g: i for i, (_, g) in enumerate(unit.fake_groups)}
    names.sort(key=lambda f: (order.get(h.fakes[f].group, 99), f))
    cond = {g: c for c, g in unit.fake_groups}
    head = (f"<tr><th>Function</th><th>Fake group</th><th>Named in {code(unit.kernel_source)}</th>"
            "<th>Configured by tests</th><th>Checked by tests</th></tr>")
    trs, callbacks = [], []
    for f in sorted(unit.local_fakes):
        if f in h.fakes:
            continue
        r = rows.get(f, {"config": {}, "checked": 0})
        conf = ", ".join(f"{KIND_TEXT.get(k, k)} {r['config'][k]}"
                         for k in KIND_TEXT if k in r["config"])
        if is_callback(unit, f):
            # Not a function below the unit: the unit calls it through a
            # descriptor that the test gives.
            callbacks.append(
                f"<tr><td>{code(f + '()')}</td><td>none: callback of the test descriptor "
                f"{code(unit.local_fakes[f].descriptor)} (FFF fake of "
                f"{code(unit.local_fakes[f].header)})</td><td>-</td><td>{conf or '-'}</td>"
                f"<td>{r['checked'] or '-'}</td></tr>")
            continue
        trs.append(f"<tr><td>{fake_ref(f, unit)}</td><td>test source</td><td>"
                   f"{'yes' if f in named else 'no'}</td><td>{conf or '-'}</td>"
                   f"<td>{r['checked'] or '-'}</td></tr>")
    for f in names:
        fk = h.fakes[f]
        r = rows.get(f, {"config": {}, "checked": 0})
        conf = ", ".join(f"{KIND_TEXT.get(k, k)} {r['config'][k]}"
                         for k in KIND_TEXT if k in r["config"])
        g = fk.group or "?"
        if cond.get(g):
            g += f" (with {cond[g]})"
        trs.append(f"<tr><td>{fake_ref(f)}</td><td>@ref {PAGE}_group_{fk.group} \"{fk.group}\""
                   f"{esc(g[len(fk.group):])}</td><td>{'yes' if f in named else 'no'}</td>"
                   f"<td>{conf or '-'}</td><td>{r['checked'] or '-'}</td></tr>")
    table = f'<table class="doxtable">{head}{"".join(trs + callbacks)}</table>'
    real = []
    for rc in h.real:
        used = [n for n in rc.names if ktext and re.search(rf"\b{n}\b", ktext)]
        if used:
            real.append(f"{', '.join(code(n + '()') for n in used)} "
                        f"(copy of {code(rc.real)} in {code(rc.shadow)})")
    text = [f"{len(unit.tests)} tests. The table has each fake that "
            f"{code(unit.kernel_source)} names, and each fake that a test configures or "
            f"checks. The counts are numbers of tests. See @ref {PAGE} "
            f'"Test doubles" for the default and the source of each double.']
    if callbacks:
        text.append("A callback of a test descriptor is not a function below the unit. "
                    "The test source gives the unit a descriptor with this fake, and the "
                    "unit calls it through the descriptor.")
    text.append(table)
    if real:
        text.append("Real code (@ref " + PAGE + "_real \"real copies\"): " + ". ".join(real)
                    + ".")
    suites = []
    for suite, (setup, before) in unit.suites.items():
        su = unit.suite_uses(suite)
        conf = effective(h, unit, su)
        if not conf:
            continue
        items = "".join(f"<li>{fake_ref(u.fake, unit)}: {describe_config(h, unit, u)}"
                        f"{via_text(u, 1)}"
                        + (f", over {u.replaces}" if hasattr(u, "replaces") else "")
                        + "</li>" for u in conf)
        lims = limits_of(limits, unit, su)
        ltext = ""
        if lims:
            ltext = ("Known limits of these doubles:<ul>" + "".join(
                f"<li>{limit_ref(lim.id)} ({esc(lim.severity)}): {esc(lim.title)}</li>"
                for lim in lims) + "</ul>Each test of the suite shows these ids in the line "
                "\"Limits of the suite setup\".")
        suites.append(f"Before each test of the suite {code(suite)}, "
                      f"{code(before + '()')} configures:<ul>{items}</ul>{ltext}")
    text += suites
    return " ".join(text)


# --------------------------------------------------------------------------
# The catalog page


def units_of(harness):
    return sorted({p.parent.parent.name for p in harness.root.glob("*/src/*.c")
                   if p.parent.parent.name != "common"})


def marked_units(root):
    """The units with the marker in one of their test sources."""
    return sorted({p.parent.parent.name for p in Path(root).glob("*/src/*.c")
                   if p.parent.parent.name != "common"
                   and MARKER in p.read_text(encoding="utf-8")})


def documented_units(harness):
    return marked_units(harness.root)


def doc_text(lines):
    """The lines of a Doxygen comment of the harness, for the page.

    The text is already Doxygen markup. The structural commands go."""
    out = []
    for x in lines:
        if x.strip().startswith(("@defgroup", "@ingroup", "@{", "@}", "@name")):
            continue
        out.append(re.sub(r"^(\s*)@brief\s+", r"\1", x))
    return out


def verbatim(lines):
    return ["@verbatim"] + [x for x in lines] + ["@endverbatim"]


def render_catalog(h, limits):
    """The page "Test doubles", as the lines of a Doxygen comment."""
    units = {u: Unit(h, u) for u in units_of(h)}
    shown = documented_units(h)
    out = [f"@page {PAGE} Test doubles", ""]
    out += [
        "This page is generated from the sources of the harness "
        "(<code>tests/kernel/unit/common</code>) by <code>doc/_scripts/kernel_unit_doubles.py</code>.",
        "Only the known limits come from a file that is written by hand "
        "(<code>common/fake_limits.yaml</code>). Each known limit has a stable id "
        "TDL-&lt;n&gt; (\"test double limit\").",
        "",
        "A test double replaces a function below the unit under test. The harness has these kinds:",
        "",
        '<table class="doxtable"><tr><th>Kind</th><th>What it does</th>'
        "<th>Source of its behavior</th></tr>",
        "<tr><td>Plain fake</td><td>An FFF fake. It records each call. It returns its default "
        "or the value of the test.</td><td>The test. The fake knows nothing of the real "
        "function.</td></tr>",
        "<tr><td>Fake with an addition</td><td>A plain fake with one behavior of the real "
        "function, for example the ISR refusal of <code>z_pend_curr()</code>.</td>"
        "<td>The real code, copied by hand into the fake.</td></tr>",
        "<tr><td>Local custom fake</td><td>A function of the test source that a test sets as "
        "<code>custom_fake</code>: a spy or a small model.</td><td>The comment of the "
        "function.</td></tr>",
        "<tr><td>Model</td><td>A shared custom fake with a state, in "
        "<code>kernel_unit_models.h</code>.</td><td>An assumption, written in the header.</td>"
        "</tr>",
        "<tr><td>Reference fake</td><td>Custom fakes for the scheduler interface with the "
        "state and the rules of the scheduler contract.</td><td>The TLA+ contract "
        "<code>spec/tla/lib/Scheduler.tla</code> (layer A), and the code where they "
        "differ.</td></tr>",
        "<tr><td>Real copy</td><td>The real function: a copy of a pure helper of a "
        "kernel header.</td><td>The real code. <code>check_real_copies.py</code> compares "
        "the copy with the header.</td></tr>",
        "</table>",
        "",
        "The unit groups with generated sections: " + ", ".join(
            f'@ref kernel_unit_{u} "{esc(units[u].kernel_source or u)}"' for u in shown) + ".",
        "",
    ]

    # Fake groups.
    out += [f"@section {PAGE}_groups Fake groups", ""]
    users = {}
    for uname, unit in units.items():
        for _, g in unit.fake_groups:
            users.setdefault(g, []).append(uname)
    totals = {}
    for uname, unit in units.items():
        for fake, r in unit_rows(h, unit).items():
            t = totals.setdefault(fake, [0, 0])
            t[0] += sum(r["config"].values())
            t[1] += r["checked"]
    for group, names in h.groups.items():
        out += [f"@subsection {PAGE}_group_{group} Fake group {group}", ""]
        apps = ", ".join(sorted(set(users.get(group, [])))) or "none"
        out += [f"File <code>common/fakes/{group}.c</code>. Linked by: {esc(apps)}.", ""]
        if not names:
            data = h.group_data.get(group, [])
            text = "This group has no fakes."
            if data:
                text += " It defines the data " + ", ".join(code(d) for d in data) + "."
            if group == "sched_ref":
                text += (f' It has the custom fakes of the @ref {PAGE}_ref "reference fake of '
                         'the scheduler contract".')
            out += [text, ""]
            continue
        out.append('<table class="doxtable"><tr><th>Fake</th><th>Header</th>'
                   "<th>After the reset</th><th>Kind</th><th>Tests that configure it</th>"
                   "<th>Tests that check it</th></tr>")
        for n in names:
            f = h.fakes[n]
            kind = "fake with an addition (hand-written)" if f.hand_written else "plain fake"
            if n in h.ref:
                kind += ", reference fake"
            t = totals.get(n, [0, 0])
            out.append(f"<tr><td>@anchor {PAGE}_fake_{n} {code(n + '()')}</td>"
                       f"<td>{code(f.header)}</td><td>{esc(f.default_text())}</td>"
                       f"<td>{kind}</td><td>{t[0]}</td><td>{t[1]}</td></tr>")
        out += ["</table>", ""]
        headers = list(dict.fromkeys(h.fakes[n].header for n in names if h.fakes[n].header))
        for hd in headers:
            if hd in h.headers:
                out += [f"Comment of the header <code>{hd}</code>:", ""]
                out += verbatim(comment_body(h.headers[hd])) + [""]

    # Real copies.
    out += [f"@section {PAGE}_real Real copies", "",
            "These functions are real in each unit test. The shadow header has a copy of the "
            "real function between the markers <code>KERNEL_UNIT_REAL_COPY_BEGIN</code> and "
            "<code>KERNEL_UNIT_REAL_COPY_END</code>.", "",
            '<table class="doxtable"><tr><th>Functions</th><th>Shadow header</th>'
            "<th>Real header</th></tr>"]
    for rc in h.real:
        out.append(f"<tr><td>{', '.join(code(n) for n in rc.names)}</td>"
                   f"<td>{code(rc.shadow)}</td><td>{code(rc.real)}</td></tr>")
    out += ["</table>", ""]

    # Models.
    out += [f"@section {PAGE}_models Shared models and checks", "",
            "The sections of <code>common/include/kernel_unit_models.h</code>. The text is the "
            "comment of the section in the header. It gives the assumption of the model.", ""]
    for sec in h.models:
        out += [f"@subsection {PAGE}_model_{sec.slug} {esc(sec.title)}", ""]
        out += doc_text(sec.text) + [""]
        sets = []
        for fn in sec.functions:
            f = h.shared.get(fn)
            if f is None:
                continue
            for m in CONFIG.finditer(f.body):
                if m.group(1) in h.fakes:
                    sets.append(m.group(1))
        sets = list(dict.fromkeys(sets))
        out += ["Functions: " + ", ".join(code(fn + "()") for fn in sec.functions) + "."]
        if sets:
            out += ["", "Fakes that it configures: " + ", ".join(fake_ref(s) for s in sets) + "."]
        out.append("")

    # Reference fake.
    out += [f"@section {PAGE}_ref Reference fake of the scheduler contract", ""]
    out += ["The comment of the group in <code>common/include/kernel_unit_sched_ref.h</code>:",
            ""]
    out += doc_text(h.ref_text)
    out += ["", "kernel_unit_sched_ref_install() sets these custom fakes "
            "(<code>common/fakes/sched_ref.c</code>). The comment of each custom fake names "
            "the operator of the contract and each difference from it. Each operator name "
            "links to its definition on the page \"Formal Design Model\" of the architecture "
            "document.", "",
            '<table class="doxtable"><tr><th>Fake</th><th>Custom fake</th><th>Comment</th></tr>']
    for r in h.ref.values():
        body = plain(" ".join(x.strip() for x in comment_body(r.comment)))
        out.append(f"<tr><td>{fake_ref(r.fake)}</td><td>{code(r.custom + '()')}</td>"
                   f"<td>{rich(h, body)}</td></tr>")
    out += ["</table>", ""]

    # Local custom fakes.
    out += [f"@section {PAGE}_local Local custom fakes", "",
            "The custom fakes that a test source defines, for the units with generated "
            "sections. The text is the comment of the function.", ""]
    for uname in shown:
        unit = units[uname]
        used = {}
        for t in unit.tests:
            for u in unit.uses(t):
                if (u.what == "config" and u.how in ("custom", "custom_seq")
                        and h.kind_of_custom(u.detail, unit) == "local"):
                    used.setdefault(u.detail, [set(), set()])[0].add(u.fake)
                    used[u.detail][1].add(t.name)
        if not used:
            continue
        out += [f"@subsection {PAGE}_local_{uname} {esc(unit.kernel_source or uname)}", "",
                '<table class="doxtable"><tr><th>Custom fake</th><th>Replaces</th>'
                "<th>Tests</th><th>Comment</th></tr>"]
        for name, (fakes, tests) in used.items():
            f = unit.local[name]
            body = plain(" ".join(x.strip() for x in comment_body(f.comment))) or "(no comment)"
            out.append(f"<tr><td>@anchor {PAGE}_local_{uname}_{name} {code(name + '()')}</td>"
                       f"<td>{', '.join(fake_ref(x, unit) for x in sorted(fakes))}</td>"
                       f"<td>{len(tests)}</td><td>{esc(body)}</td></tr>")
        out += ["</table>", ""]

    # Known limits.
    out += [f"@section {PAGE}_limits Known limits", "",
            "The known limits of the test doubles, from <code>common/fake_limits.yaml</code>. "
            "This file is the only source of the limits. Each limit has a stable id "
            "TDL-&lt;n&gt; (\"test double limit\"). The number is not a rank: the severity is a "
            "field of its own. A new limit gets the next free number. An id is never used "
            "again or changed.", "",
            "Each limit names the doubles that it applies to. The lists of tests are "
            "generated, one item for each unit with generated sections. The first list has "
            "each test whose own statements use such a double. The second list has the "
            "suites whose setup before each test uses such a double: each test of such a "
            "suite has the line \"Limits of the suite setup\".", ""]
    for lim in limits:
        out += [f"@subsection {limit_anchor(lim.id)} {lim.id} ({esc(lim.severity)}): "
                f"{esc(lim.title)}", ""]
        if lim.text:
            out += [esc(lim.text), ""]
        if lim.review:
            out += [f"History: finding {esc(lim.review)} of the review of the fakes against "
                    "the scheduler contract.", ""]
        sels = []
        for s in lim.applies:
            sels.append(", ".join(f"{k} = {code(str(v))}" for k, v in s.items()))
        out += ["Applies to:", ""] + ([f"- {x}" for x in sels] if sels else ["- no selector yet"]) \
            + [""]
        hits = []
        suite_hits = []
        for uname in shown:
            unit = units[uname]
            utests = [t for t in unit.tests
                      if lim in limits_of(limits, unit, [u for u in unit.uses(t)
                                                         if u.origin == "test"])]
            group = f'@ref kernel_unit_{uname} "{esc(unit.kernel_source or uname)}"'
            if utests:
                hits.append(f"<li>{group} ({len(utests)}): " + ", ".join(
                    f'@ref {test_anchor(uname, t.name)} "{t.name}"' for t in utests) + "</li>")
            for suite, (_, before) in unit.suites.items():
                if lim in limits_of(limits, unit, unit.suite_uses(suite)):
                    n = sum(1 for t in unit.tests if t.suite == suite)
                    suite_hits.append(f"<li>{group}: the {n} tests of the suite {code(suite)} "
                                      f"({code(before + '()')})</li>")
        if hits:
            out += ["Tests whose own statements use such a double:<ul>" + "".join(hits)
                    + "</ul>", ""]
        if suite_hits:
            out += ["Suites whose setup before each test uses such a double:<ul>"
                    + "".join(suite_hits) + "</ul>", ""]
        if not hits and not suite_hits:
            out += ["No test of a unit with generated sections uses such a double.", ""]
    return out


def catalog_comment(h, limits):
    lines = render_catalog(h, limits)
    # No leading "*" on the lines: Doxygen keeps it in a @verbatim block.
    return "/**\n" + "".join(f"{x}".rstrip() + "\n" for x in lines) + "*/\n"


# --------------------------------------------------------------------------
# Filter support


def annotate(text, path, harness=None, limits=None):
    """Add the generated sections to a test source with the marker.

    Each documented ZTEST of a unit with the marker gets the section on the
    closing line of its doc comment. The marker is in the file group of one
    test source of the unit, and it gets the table of the unit. The number of
    lines does not change."""
    path = Path(path)
    root = HARNESS if harness is None else harness.root
    if MARKER not in text and path.parent.parent.name not in marked_units(root):
        return text
    h = harness or Harness()
    limits = read_limits(h) if limits is None else limits
    unit = Unit(h, path.parent.parent.name)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from doxygen_filter_kconfig import documented_ztests, lex  # noqa: E402

    lines = re.findall(r"[^\n]*\n|[^\n]+$", text)
    comments, in_comment = lex(lines)
    ztests, _ = documented_ztests(lines, comments, in_comment)
    by_name = {t.name: t for t in unit.tests if t.file.resolve() == path.resolve()}
    for n, cm in ztests.items():
        m = re.search(r"ZTEST\s*\(\s*\w+\s*,\s*(\w+)", lines[n])
        if not m or m.group(1) not in by_name:
            continue
        add = render_test(h, unit, by_name[m.group(1)], limits)
        ln, col = cm.end
        line = lines[ln]
        before = line[:col]
        lines[ln] = (before.rstrip() + " " if before.strip() else before + "* ") + add + " " \
            + line[col:]
    for k, line in enumerate(lines):
        if MARKER in line:
            i = line.index(MARKER) + len(MARKER)
            lines[k] = line[:i] + " " + render_unit(h, unit, limits) + line[i:]
            break
    return "".join(lines)


# --------------------------------------------------------------------------
# Drift check


def doc_inputs(doxyfile=DOXYFILE, root=HARNESS):
    """The unit test sources in the INPUT of the document, as {unit: [file names]}."""
    out = {}
    text = Path(doxyfile).read_text(encoding="utf-8") if Path(doxyfile).exists() else ""
    m = re.search(r"^INPUT\s*=((?:.*\\\n)*.*)$", text, re.M)
    for word in (m.group(1).replace("\\\n", " ").split() if m else []):
        w = re.search(r"tests/kernel/unit/(\w+)/src/([\w.]+\.c)$", word)
        if w and (Path(root) / w.group(1) / "src" / w.group(2)).exists():
            out.setdefault(w.group(1), []).append(w.group(2))
    return out


def rel(path):
    """A path relative to the safety repository, if it is in it."""
    try:
        return Path(path).resolve().relative_to(SAFETY_BASE).as_posix()
    except ValueError:
        return str(path)


def tla_link_check(h, deploy=None, rst=MODEL_RST):
    """Each TLA+ link of the reference fake goes to an anchor of the page.

    The anchors come from the built page <deploy>/<ARCH_DOC>/<MODEL_PAGE> if
    it exists, else from the tla directives of the .rst of the page and the
    .tla sources. Returns (errors, note); the note says which way."""
    errors, refs = [], {}
    for r in h.ref.values():
        text = plain(" ".join(x.strip() for x in comment_body(r.comment)))
        for t in h.tla.refs(text):
            if t.found:
                refs.setdefault(t.anchor, t)
            else:
                errors.append(f"reference fake {r.fake}(): the comment names the operator "
                              f"{t.text}, which the TLA+ library ({rel(h.tla.lib)}) does not "
                              "define")
    page = Path(deploy) / ARCH_DOC / MODEL_PAGE if deploy else None
    if page is not None and page.is_file():
        ids = set(re.findall(r'\bid="([^"]+)"', page.read_text(encoding="utf-8")))
        how = f"the built page {page}"
    elif Path(rst).is_file():
        ids = rendered_anchors(h.tla, rst)
        how = f"the tla directives of {rel(rst)} and the .tla sources"
        if page is not None:
            how += f" ({page} is not built)"
    else:
        ids = set()
        how = f"nothing: {rel(rst)} does not exist"
    for anchor, t in sorted(refs.items()):
        if anchor not in ids:
            errors.append(f"TLA+ link {t.text}: the page {ARCH_DOC}/{MODEL_PAGE} has no "
                          f"anchor #{anchor}")
    return errors, f"TLA+ links: {len(refs)} anchors, checked against {how}"


def check(h, limits, deploy=None, doxyfile=DOXYFILE, rst=MODEL_RST):
    """Return (errors, warnings, notes) as lists of text."""
    errors, warnings, notes = [], [], []
    units = {u: Unit(h, u) for u in units_of(h)}
    shown = documented_units(h)
    for name, f in h.fakes.items():
        if not f.group:
            errors.append(f"fake {name}() ({f.header}): no fake group defines it")
        if not f.header:
            errors.append(f"fake {name}() (group {f.group}): no header declares it")
    seen = set()
    for lim in limits:
        if not LIMIT_ID.match(lim.id):
            errors.append(f"limit {lim.id}: the id is not TDL-<n>")
        if lim.id in seen:
            errors.append(f"limit {lim.id}: two limits have this id")
        if lim.unknown:
            errors.append(f"limit {lim.id}: unknown keys {lim.unknown}")
        seen.add(lim.id)
        if lim.severity not in SEVERITIES:
            errors.append(f"limit {lim.id}: severity {lim.severity!r} is not one of "
                          f"{', '.join(SEVERITIES)}")
        if not lim.applies:
            warnings.append(f"limit {lim.id}: no selector")
        for s in lim.applies:
            bad = set(s) - SELECTOR_KEYS
            if bad:
                errors.append(f"limit {lim.id}: unknown keys {sorted(bad)}")
            for key in ("fake", "checks"):
                if key in s and s[key] not in h.fakes:
                    errors.append(f"limit {lim.id}: {key} {s[key]} is not a fake")
            if "unit" in s and s["unit"] not in units:
                errors.append(f"limit {lim.id}: unit {s['unit']} does not exist")
            hit = False
            for unit in units.values():
                for t in unit.tests:
                    if selector_matches(s, unit, unit.uses(t)):
                        hit = True
                        break
                if hit:
                    break
            if not hit:
                errors.append(f"limit {lim.id}: the selector {s} matches no test (stale)")
    # A limit id in a comment of the reference fake links to the limit.
    for r in h.ref.values():
        for lid in LIMIT_IN_TEXT.findall(r.comment):
            if lid not in seen:
                errors.append(f"reference fake {r.fake}(): the comment names {lid}, which "
                              "fake_limits.yaml does not define")
    tla_errors, note = tla_link_check(h, deploy, rst)
    errors += tla_errors
    notes.append(note)
    for uname, files in sorted(doc_inputs(doxyfile, h.root).items()):
        if uname not in shown:
            warnings.append(f"{uname}: no test source has the marker {MARKER} "
                            f"({', '.join(files)}): the document shows no test doubles of "
                            "this unit")
    for uname in shown:
        unit = units[uname]
        for t in unit.tests:
            for u in unit.uses(t):
                if (u.what in ("config", "check") and u.fake != ALL_FAKES
                        and not unit.is_fake(u.fake)):
                    errors.append(f"{uname}: {t.name}: {u.fake}_fake is not a fake")
                if (u.what == "config" and u.how in ("custom", "custom_seq")
                        and h.kind_of_custom(u.detail, unit) == "local"
                        and not unit.local[u.detail].comment):
                    warnings.append(f"{uname}: local custom fake {u.detail}() has no comment")
            # The prose: the doc comment names each fake that the test body
            # configures. Only the statements of the test body: a helper names
            # its fakes in its own comment.
            comment = _doc_of(t)
            for u in unit.uses(t):
                if u.origin != "test" or u.what != "config" or u.via:
                    continue
                if h.kind_of_custom(u.detail, unit) == "reference":
                    continue
                shown_name = u.fake[5:] if u.fake.startswith("unit_") else u.fake
                if shown_name not in comment and u.fake not in comment:
                    warnings.append(f"{uname}: {t.name}: the doc comment does not name "
                                    f"{shown_name}(), which the test configures ({u.how})")
    return errors, list(dict.fromkeys(warnings)), notes


def _doc_of(test):
    text = test.file.read_text(encoding="utf-8")
    lines = text.splitlines()
    end = test.line - 1
    k = end - 1
    while k >= 0 and "/**" not in lines[k]:
        k -= 1
    return "\n".join(lines[k:end])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0], allow_abbrev=False)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("catalog")
    u = sub.add_parser("unit")
    u.add_argument("unit")
    c = sub.add_parser("check")
    c.add_argument("--deploy", type=Path,
                   help="the deploy/html folder of the documentation build: check the TLA+ "
                        "links against the built page of the formal model, if it exists")
    ap.add_argument("--harness", type=Path, default=HARNESS)
    args = ap.parse_args(argv)
    h = Harness(args.harness)
    limits = read_limits(h)
    if args.cmd == "catalog":
        sys.stdout.write(catalog_comment(h, limits))
        return 0
    if args.cmd == "unit":
        unit = Unit(h, args.unit)
        for t in unit.tests:
            print(f"{t.name}:")
            for x in unit.uses(t):
                print(f"  {x.origin:5} {x.what:6} {x.fake or '-':32} {x.how:14} "
                      f"{x.detail} {'/'.join(x.via)}")
            for lim in limits_of(limits, unit, [x for x in unit.uses(t) if x.origin == "test"]):
                print(f"  limit {lim.id}")
            for lim in limits_of(limits, unit, unit.suite_uses(t.suite)):
                print(f"  limit {lim.id} (suite setup)")
        return 0
    errors, warnings, notes = check(h, limits, deploy=args.deploy)
    for n in notes:
        print(f"note: {n}")
    for w in warnings:
        print(f"warning: {w}")
    for e in errors:
        print(f"error: {e}")
    print(f"{len(errors)} errors, {len(warnings)} warnings")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
