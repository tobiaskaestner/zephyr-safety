#!/usr/bin/env python3
# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""The design layer: one ``design`` need per ``.. design::`` block in Zephyr's docs.

The Zephyr branch marks design elements in its own documentation pages with
the ``design`` directive of ``doc/_extensions/zephyr/requirement_traceability.py``::

    .. design:: DESIGN-LIFOS LIFOs
       :fulfills: ZEP-SRS-23-1 ZEP-SRS-23-2

In practice each block is a body-less marker at the top of an ordinary Zephyr
page; the design content is the page it heads. This docset does not build
those pages, so it does not run that directive. It scans the sources instead
(like the StrictDoc -> ``req`` generator, see doc/CMakeLists.txt) and writes
the needs itself, into the architecture document:

``generate``
    Scans ``<zephyr>/doc/kernel`` (not ``doc/_build``, which holds copies) and
    writes ``generated/design_elements.rst``: one ``design`` need per block —
    the id and caption as authored, ``fulfills`` links (``satisfies`` and
    ``realizes`` fold into it, as in the directive), ``source_file`` /
    ``source_line`` / ``source_url`` fields, and a link to the page at the
    zephyr commit being documented. Fails on a ``fulfills`` target that is no
    requirement in the StrictDoc export (dangling), on a duplicate id, on an
    option the need model has no place for, and on a block it cannot parse.
    Also writes a manifest (the expected ids) for ``check``.

``check``
    After the build: every block yields exactly one ``design`` need in the
    architecture's needs.json, and nothing else does. Prints the gap-view
    numbers (requirement x design x verification) from the deploy tree.
"""

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

SCAN_DIR = "doc/kernel"
URL = "https://github.com/tiacsys/zephyr/blob/{sha}/{path}#L{line}"

# The directive's options (requirement_traceability.DESIGN_OPTIONS) and how
# they map onto this need model: the three "fulfils" spellings are one link.
LINK_OPTIONS = {"fulfills": "fulfills", "satisfies": "fulfills", "realizes": "fulfills"}
FIELD_OPTIONS = {"status"}
# Directive options with no counterpart here (design -> code / design -> design
# links). None is authored today; one appearing is a decision, not a default.
UNSUPPORTED_OPTIONS = {"implements", "trace"}

DIRECTIVE_RE = re.compile(r"^(?P<indent>\s*)\.\.\s+design::(?P<arg>.*)$")
OPTION_RE = re.compile(r"^:(?P<name>[A-Za-z_-]+):(?P<value>.*)$")
RAW_RE = re.compile(r"\.\.\s+design::")


@dataclass
class Block:
    id: str
    caption: str
    path: str  # relative to the zephyr base
    line: int  # 1-based, the directive line
    fulfills: list = field(default_factory=list)
    fields: dict = field(default_factory=dict)


class DesignError(Exception):
    pass


def _indent(line):
    return len(line) - len(line.lstrip())


def parse_file(path, rel):
    """The design blocks of one rst file, and the number of raw directive hits."""
    lines = path.read_text(encoding="utf-8").splitlines()
    blocks = []
    raw = sum(1 for line in lines if RAW_RE.search(line))
    i = 0
    while i < len(lines):
        m = DIRECTIVE_RE.match(lines[i])
        if not m:
            i += 1
            continue
        start = i
        indent = len(m.group("indent"))
        arg = m.group("arg").strip()
        options = {}
        current = None
        i += 1
        # The directive's option block: lines indented deeper than the
        # directive, up to the first blank line (the body, if any, follows it).
        while i < len(lines) and lines[i].strip() and _indent(lines[i]) > indent:
            text = lines[i].strip()
            om = OPTION_RE.match(text)
            if om:
                current = om.group("name")
                if current in options:
                    raise DesignError(f"{rel}:{i + 1}: option :{current}: given twice")
                options[current] = om.group("value").strip()
            elif current is None:
                arg = f"{arg} {text}"  # caption continued (final_argument_whitespace)
            else:
                options[current] = f"{options[current]} {text}".strip()
            i += 1
        parts = arg.split(None, 1)
        if not parts:
            raise DesignError(f"{rel}:{start + 1}: design block without an id")
        block = Block(
            id=parts[0],
            caption=parts[1] if len(parts) > 1 else parts[0],
            path=rel,
            line=start + 1,
        )
        for name, value in options.items():
            if name in LINK_OPTIONS:
                block.fulfills.extend(value.replace(",", " ").split())
            elif name in FIELD_OPTIONS:
                block.fields[name] = value
            elif name in UNSUPPORTED_OPTIONS:
                raise DesignError(
                    f"{rel}:{start + 1}: {block.id}: option :{name}: has no place in the design need model"
                )
            else:
                raise DesignError(f"{rel}:{start + 1}: {block.id}: unknown option :{name}:")
        blocks.append(block)
    return blocks, raw


def scan(zephyr_base):
    root = zephyr_base / SCAN_DIR
    blocks, raw = [], 0
    for path in sorted(root.rglob("*.rst")):
        rel = path.relative_to(zephyr_base).as_posix()
        if "/_build/" in f"/{rel}":
            continue
        found, hits = parse_file(path, rel)
        blocks.extend(found)
        raw += hits
    return blocks, raw


def requirement_uids(strictdoc_json):
    """Every requirement UID in the StrictDoc JSON export."""

    def walk(nodes):
        for node in nodes:
            if not isinstance(node, dict):
                continue
            if node.get("_NODE_TYPE") == "REQUIREMENT":
                uid = (node.get("UID") or "").strip()
                if uid:
                    yield uid
            yield from walk(node.get("NODES") or [])

    data = json.loads(Path(strictdoc_json).read_text())
    return {uid for doc in data["DOCUMENTS"] for uid in walk(doc.get("NODES") or [])}


def validate(blocks, raw, uids):
    errors = []
    seen = {}
    for b in blocks:
        if b.id in seen:
            errors.append(f"{b.path}:{b.line}: duplicate design id {b.id} (first at {seen[b.id]})")
        seen.setdefault(b.id, f"{b.path}:{b.line}")
        if not b.fulfills:
            errors.append(f"{b.path}:{b.line}: {b.id} fulfills nothing")
        dup = sorted({r for r in b.fulfills if b.fulfills.count(r) > 1})
        if dup:
            errors.append(f"{b.path}:{b.line}: {b.id} lists {', '.join(dup)} twice")
        for r in b.fulfills:
            if r not in uids:
                errors.append(f"{b.path}:{b.line}: {b.id} fulfills {r}: no such requirement (dangling)")
    if raw != len(blocks):
        errors.append(f"{raw} '.. design::' lines under {SCAN_DIR}, but {len(blocks)} parsed blocks")
    return errors


def _heading(text, char):
    return [text, char * len(text), ""]


def render(blocks, sha):
    out = _heading("Design Elements", "=")
    out += [
        "Generated by ``doc/_scripts/design_gen.py`` from the ``.. design::`` blocks",
        f"under ``{SCAN_DIR}`` of the Zephyr tree at commit ``{sha}``.",
        "Each element is the Zephyr documentation page it heads; the link opens that",
        "page's source at this commit.",
        "",
        f"{len(blocks)} design elements, "
        f"{len({r for b in blocks for r in b.fulfills})} requirements fulfilled.",
        "",
    ]
    section = None
    for b in sorted(blocks, key=lambda b: (b.path, b.line)):
        sec = Path(b.path).parent.as_posix()
        if sec != section:
            section = sec
            out += _heading(sec, "-")
        url = URL.format(sha=sha, path=b.path, line=b.line)
        out += [
            f".. design:: {b.caption}",
            f"   :id: {b.id}",
            f"   :fulfills: {', '.join(b.fulfills)}",
            f"   :source_file: {b.path}",
            f"   :source_line: {b.line}",
            f"   :source_url: {url}",
        ]
        out += [f"   :{k}: {v}" for k, v in sorted(b.fields.items())]
        out += ["", f"   Design content: `{b.path}:{b.line} <{url}>`__", ""]
    return "\n".join(out) + "\n"


def _write(path, text):
    """Write only if the content changed, so a rebuild does not re-read it."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file() or path.read_text() != text:
        path.write_text(text)


def cmd_generate(args):
    zephyr_base = Path(args.zephyr_base).resolve()
    sha = subprocess.run(
        ["git", "-C", str(zephyr_base), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    try:
        blocks, raw = scan(zephyr_base)
    except DesignError as e:
        print(f"design_gen: error: {e}", file=sys.stderr)
        return 1
    errors = validate(blocks, raw, requirement_uids(args.requirements_json))
    for e in errors:
        print(f"design_gen: error: {e}", file=sys.stderr)
    if errors:
        return 1
    _write(Path(args.rst_out) / "generated" / "design_elements.rst", render(blocks, sha))
    manifest = {
        "zephyr_sha": sha,
        "blocks": [
            {"id": b.id, "path": b.path, "line": b.line, "fulfills": b.fulfills} for b in blocks
        ],
    }
    _write(args.manifest, json.dumps(manifest, indent=1) + "\n")
    files = len({b.path for b in blocks})
    reqs = len({r for b in blocks for r in b.fulfills})
    print(f"design_gen: {len(blocks)} design needs from {files} files, {reqs} requirements fulfilled")
    return 0


def _needs(path):
    data = json.loads(Path(path).read_text())
    version = data["versions"][data.get("current_version") or next(iter(data["versions"]))]
    return version["needs"]


def cmd_check(args):
    manifest = json.loads(Path(args.manifest).read_text())
    expected = [b["id"] for b in manifest["blocks"]]
    deploy = Path(args.deploy)
    arch = _needs(deploy / "architecture" / "needs.json")
    designs = {i: n for i, n in arch.items() if n.get("type") == "design"}
    errors = []
    missing = sorted(set(expected) - set(designs))
    extra = sorted(set(designs) - set(expected))
    errors += [f"MISSING design need {i}" for i in missing]
    errors += [f"EXTRA design need {i} (no block)" for i in extra]
    for b in manifest["blocks"]:
        n = designs.get(b["id"])
        if n is not None and sorted(n.get("fulfills", [])) != sorted(b["fulfills"]):
            errors.append(f"LINKS {b['id']}: need {n.get('fulfills')} != block {b['fulfills']}")

    # Gap view: software requirements x design x verification.
    reqs = _needs(deploy / "requirements" / "needs.json")
    tests = _needs(deploy / "test-specification" / "needs.json")
    srs = {i for i, n in reqs.items() if n.get("type") == "req" and i.startswith("ZEP-SRS-")}
    designed = {r for n in designs.values() for r in n.get("fulfills", [])}
    verified = {r for n in tests.values() if n.get("type") == "test_case" for r in n.get("verifies", [])}
    dangling = sorted(designed - set(reqs))
    errors += [f"DANGLING fulfills target {r}" for r in dangling]
    print(
        f"design-check: {len(designs)} design needs / {len(expected)} blocks; "
        f"{len(missing)} missing, {len(extra)} extra, {len(dangling)} dangling"
    )
    print(
        f"design-check: {len(srs)} SRS requirements: {len(srs & designed)} designed, "
        f"{len(srs - designed)} not designed; {len(srs & verified)} verified; "
        f"designed+verified {len(srs & designed & verified)}, "
        f"designed not verified {len(srs & designed - verified)}, "
        f"verified not designed {len(srs & verified - designed)}, "
        f"neither {len(srs - designed - verified)}"
    )
    for e in errors:
        print(f"design-check: {e}", file=sys.stderr)
    return 1 if errors else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--zephyr-base", required=True)
    g.add_argument("--requirements-json", required=True, help="StrictDoc json/index.json")
    g.add_argument("--rst-out", required=True)
    g.add_argument("--manifest", required=True)
    c = sub.add_parser("check")
    c.add_argument("--manifest", required=True)
    c.add_argument("--deploy", required=True, help="the deploy/html directory")
    args = parser.parse_args(argv)
    return cmd_generate(args) if args.cmd == "generate" else cmd_check(args)


if __name__ == "__main__":
    sys.exit(main())
