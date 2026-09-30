#!/usr/bin/env python3
# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Check that every @satisfies in the documented sources lands on one impl need.

A ``@satisfies`` can drop out of the implementation layer without a warning:
on a symbol a Doxyfile's EXCLUDE_SYMBOLS hides, on a static function a project
does not extract, in a comment Doxygen attaches to nothing, on a struct (the
``symbolneeds`` directive reads members only). This reads every ``@satisfies``
site from the INPUT files of the given Doxygen projects, the documented entities
from their XML and the ``impl`` needs from the given needs.json files, and
classifies each site:

OK
    the doc comment it is in documents a member whose XML carries the UID,
    and ``IMPL-<member>`` is an impl need of exactly one document.
MISSING
    anything else: the comment documents no entity Doxygen extracted, or one
    without that UID, or one no impl need was made of. An error: exit status 1.
DUPLICATE
    ``IMPL-<member>`` is a need of more than one document, or more than one
    member of that name carries the UID: an error too.

A site is attributed to the first entity Doxygen documents after the end of
its doc comment in the same file, with no other doc comment in between (the
entity's declaration, definition or body start). ``--unscanned <dir>`` also
lists the files under ``<dir>`` that carry a ``@satisfies`` but are in no
project's INPUT, as warnings.

``--accepted <yaml>`` lets findings through on purpose: a list under
``accepted:`` of ``site: "<path relative to --zephyr-base> <UID>"`` entries,
each with a ``reason``. An accepted finding is printed as a warning; an entry
that matches no finding any more is a warning too (drop it).
"""

import argparse
import collections
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

import yaml

SATISFIES = re.compile(r"[@\\]satisfies\s+([\w-]+)")
# A requirement's refid in the XML: requirement_<UID>.
REQ_REFID = re.compile(r"^requirement_(.+)$")
SOURCE_SUFFIXES = {".c", ".h", ".h_", ".S"}
MEMBER_COMPOUNDS = ("group", "file", "namespace", "struct", "union", "class")


@dataclass
class Comment:
    start: int  # 1-based line numbers
    end: int
    doc: bool


@dataclass
class Site:
    file: Path
    line: int
    uid: str
    comment: object = None
    entity: object = None
    verdict: str = ""
    reason: str = ""

    def where(self, base):
        try:
            return f"{self.file.relative_to(base)}:{self.line}"
        except ValueError:
            return f"{self.file}:{self.line}"


@dataclass
class Entity:
    name: str
    kind: str
    ident: str
    member: bool  # a memberdef (a compound otherwise)
    uids: set = field(default_factory=set)
    positions: set = field(default_factory=set)  # {(location path, line)}
    project: str = ""


def comments(text):
    """Every comment of a C source, with its line span, doc or not."""
    out, i, n = [], 0, len(text)
    line = 1
    while i < n:
        c = text[i]
        if c == "\n":
            line += 1
            i += 1
        elif c in "\"'":
            j = i + 1
            while j < n and text[j] != c and text[j] != "\n":
                j += 2 if text[j] == "\\" else 1
            i = j + 1
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            body = text[i:j]
            doc = body.startswith(("/**", "/*!")) and not body.startswith("/**/")
            out.append(Comment(line, line + body.count("\n"), doc))
            line += body.count("\n")
            i = j
        elif text.startswith("//", i):
            j = text.find("\n", i)
            j = n if j < 0 else j
            out.append(Comment(line, line, text.startswith(("///", "//!"), i)))
            i = j
        else:
            i += 1
    return out


def doxyfile_inputs(doxyfile):
    """The INPUT paths of an expanded Doxyfile."""
    text = Path(doxyfile).read_text()
    m = re.search(r"^INPUT[ \t]*=((?:[^\n]*\\\n)*[^\n]*)", text, re.M)
    if not m:
        return []
    return [Path(p) for p in m.group(1).replace("\\\n", " ").split()]


def source_files(paths):
    out = []
    for p in paths:
        if p.is_dir():
            out += sorted(f for f in p.rglob("*") if f.suffix in SOURCE_SUFFIXES)
        elif p.suffix in SOURCE_SUFFIXES:
            out.append(p)
    return out


def sites_of(path):
    text = path.read_text(errors="replace")
    cmts = comments(text)
    out = []
    for no, line in enumerate(text.splitlines(), 1):
        for m in SATISFIES.finditer(line):
            cmt = next((c for c in cmts if c.start <= no <= c.end), None)
            if cmt is not None:
                out.append(Site(path, no, m.group(1), cmt))
    return out, cmts


def _uids(elem):
    sat = elem.find("satisfies")
    if sat is None:
        return set()
    return {
        m.group(1)
        for r in sat.iter("requirement")
        if (m := REQ_REFID.match(r.get("refid", "")))
    }


def _positions(elem):
    loc = elem.find("location")
    if loc is None:
        return set()
    out = set()
    for f, ln in (("file", "line"), ("declfile", "declline"), ("bodyfile", "bodystart")):
        if loc.get(f) and loc.get(ln, "").isdigit() and int(loc.get(ln)) > 0:
            out.add((loc.get(f), int(loc.get(ln))))
    return out


def entities(xml_dir, project):
    """Every documented member and struct-like compound of a Doxygen project."""
    xml_dir = Path(xml_dir)
    root = ET.parse(xml_dir / "index.xml").getroot()
    out = {}
    for c in root.findall("compound"):
        if c.get("kind") not in MEMBER_COMPOUNDS:
            continue
        cdef = ET.parse(xml_dir / f"{c.get('refid')}.xml").getroot().find("compounddef")
        if cdef is None:
            continue
        if cdef.get("kind") in ("struct", "union", "class"):
            ident = cdef.get("id")
            out.setdefault(ident, Entity(
                cdef.findtext("compoundname", ""), cdef.get("kind"), ident, False,
                _uids(cdef), _positions(cdef), project,
            ))
        for md in cdef.iter("memberdef"):
            ident = md.get("id")
            if ident in out:
                continue
            out[ident] = Entity(
                md.findtext("name", "").strip(), md.get("kind", ""), ident, True,
                _uids(md), _positions(md), project,
            )
    return list(out.values())


def impl_needs(needs_files):
    """{need id: [needs.json it is in, ...]} of the impl needs."""
    out = collections.defaultdict(list)
    for f in needs_files:
        data = json.loads(Path(f).read_text())
        versions = data["versions"]
        version = versions.get(data.get("current_version")) or next(iter(versions.values()))
        for n in version["needs"].values():
            if n.get("type") == "impl" and not n.get("is_external"):
                out[n["id"]].append(Path(f).parent.name)
    return out


def _matches(loc_path, source):
    """Whether an XML location (path stripped by Doxygen) names ``source``."""
    parts = Path(loc_path).parts
    return len(parts) <= len(source.parts) and source.parts[-len(parts):] == parts


def attribute(sites, cmts_by_file, all_entities):
    """Set each site's entity: the first one documented after its comment."""
    by_file = collections.defaultdict(list)  # source -> [(line, entity)]
    locs = collections.defaultdict(list)
    for e in all_entities:
        for p, ln in e.positions:
            locs[p].append((ln, e))
    for source in cmts_by_file:
        for p, pos in locs.items():
            if _matches(p, source):
                by_file[source] += pos
    for s in sites:
        end = s.comment.end
        after = sorted(
            ((ln, e) for ln, e in by_file[s.file] if ln > end), key=lambda p: (p[0], p[1].ident)
        )
        if not after:
            continue
        ln = after[0][0]
        # A declaration and a definition Doxygen did not merge are two members
        # at the same place: the one carrying the UID is the site's.
        here = [e for n, e in after if n == ln]
        e = next((e for e in here if s.uid in e.uids), here[0])
        between = [
            c for c in cmts_by_file[s.file] if c.doc and end < c.start < ln
        ]
        if not between:
            s.entity = e


def classify(sites, all_entities, needs):
    holders = collections.defaultdict(list)  # (name, uid) -> [entity]
    for e in all_entities:
        if e.member:
            for uid in e.uids:
                holders[(e.name, uid)].append(e)
    for s in sites:
        e = s.entity
        if not s.comment.doc:
            s.verdict, s.reason = "MISSING", "in a plain comment, not a doc comment"
        elif e is None:
            s.verdict, s.reason = "MISSING", "its comment documents no entity Doxygen extracted"
        elif s.uid not in e.uids:
            s.verdict = "MISSING"
            s.reason = f"documents {e.kind} {e.name} ({e.project}), which has no \\satisfies {s.uid}"
        elif not e.member:
            s.verdict = "MISSING"
            s.reason = f"on {e.kind} {e.name} ({e.project}): symbolneeds reads members only"
        elif not needs.get(f"IMPL-{e.name}"):
            s.verdict, s.reason = "MISSING", f"no impl need IMPL-{e.name}"
        elif len(needs[f"IMPL-{e.name}"]) > 1 or len(holders[(e.name, s.uid)]) > 1:
            docs = ", ".join(needs[f"IMPL-{e.name}"])
            projects = ", ".join(sorted({h.project for h in holders[(e.name, s.uid)]}))
            s.verdict = "DUPLICATE"
            s.reason = f"IMPL-{e.name} in {docs}; members with {s.uid} in {projects}"
        else:
            s.verdict, s.reason = "OK", f"IMPL-{e.name} ({needs[f'IMPL-{e.name}'][0]})"


def unscanned(roots, scanned):
    scanned = {p.resolve() for p in scanned}
    out = []
    for root in roots:
        for f in source_files([root]):
            if f.resolve() not in scanned and SATISFIES.search(f.read_text(errors="replace")):
                out.append(f)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(allow_abbrev=False, description=__doc__.split("\n")[0])
    ap.add_argument(
        "--doxygen", nargs=2, action="append", required=True, metavar=("DOXYFILE", "XML_DIR"),
        help="an expanded Doxyfile (its INPUT is scanned) and the project's XML output",
    )
    ap.add_argument("--needs", action="append", required=True, type=Path,
                    help="the needs.json of a document with impl needs")
    ap.add_argument("--zephyr-base", type=Path, default=Path("/"),
                    help="paths in the report are relative to it")
    ap.add_argument("--unscanned", action="append", type=Path, default=[],
                    help="a directory whose files with @satisfies must all be scanned")
    ap.add_argument("--accepted", type=Path,
                    help="findings let through on purpose (YAML, see above)")
    ap.add_argument("-v", "--verbose", action="store_true", help="also list the OK sites")
    args = ap.parse_args(argv)

    files, all_entities = [], []
    for doxyfile, xml_dir in args.doxygen:
        files += source_files(doxyfile_inputs(doxyfile))
        all_entities += entities(xml_dir, Path(xml_dir).name)
    files = list(dict.fromkeys(files))
    all_sites, cmts_by_file = [], {}
    for f in files:
        s, c = sites_of(f)
        all_sites += s
        cmts_by_file[f] = c
    attribute(all_sites, cmts_by_file, all_entities)
    needs = impl_needs(args.needs)
    classify(all_sites, all_entities, needs)
    stray = unscanned(args.unscanned, files)
    accepted = {}
    if args.accepted:
        for a in (yaml.safe_load(args.accepted.read_text()) or {}).get("accepted") or []:
            accepted[a["site"]] = a["reason"]
    used = set()
    for s in all_sites:
        key = f"{s.where(args.zephyr_base).rsplit(':', 1)[0]} {s.uid}"
        if s.verdict != "OK" and key in accepted:
            s.reason += f"; accepted: {accepted[key]}"
            s.verdict = f"{s.verdict} (accepted)"
            used.add(key)

    count = collections.Counter(s.verdict for s in all_sites)
    landed = {s.entity.name for s in all_sites if s.verdict == "OK"}
    print(
        f"satisfies-check: {len(all_sites)} @satisfies sites in {len(files)} files: "
        f"{count['OK']} OK on {len(landed)} impl needs, {count['MISSING']} MISSING, "
        f"{count['DUPLICATE']} DUPLICATE, "
        f"{count['MISSING (accepted)'] + count['DUPLICATE (accepted)']} accepted; "
        f"{len(stray)} files with @satisfies not scanned"
    )
    for s in all_sites:
        if s.verdict != "OK" or args.verbose:
            level = {"OK": "info", "MISSING": "error", "DUPLICATE": "error"}.get(
                s.verdict, "warning"
            )
            print(f"  {level}: {s.verdict}  {s.where(args.zephyr_base)}  {s.uid}  {s.reason}")
    for f in stray:
        print(f"  warning: NOT SCANNED  {f}")
    for key in sorted(set(accepted) - used):
        print(f"  warning: STALE accepted entry  {key}  (matches no finding)")
    return 1 if count["MISSING"] or count["DUPLICATE"] else 0


if __name__ == "__main__":
    sys.exit(main())
