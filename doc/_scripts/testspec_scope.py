#!/usr/bin/env python3
# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Derive the per-module test documentation scaffolding from test-scope.yaml.

What used to be written by hand for every test module is generated here from
the scope file and the Zephyr test sources:

``input``
    The testspec Doxygen INPUT: every module's ``src/`` directory (the module
    directory itself when it has none), space-separated, for CMake to substitute
    into the Doxyfile at configure time.

``generate``
    * A ``.dox`` defining the groups the ``testmodule`` directive walks:
      area -> module -> suite. A group the module's sources already define with
      ``@defgroup`` is left to them — a hand-written group carries prose that a
      generated one cannot, so it takes precedence.
    * The test-specification and test-report page trees: one page per area, one
      per module, and the top-level ``specs.rst`` / ``reports.rst`` toctrees.

The testspec Doxyfile's ``ZTEST_SUITE`` expansion defines no group, so every
suite group has exactly one definition — here or in the sources — and the
result does not depend on the order Doxygen reads its INPUT in.
"""

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFGROUP = re.compile(r"[@\\]defgroup\s+(\w+)[ \t]*([^\n]*)")
ZTEST_SUITE = re.compile(r"^\s*ZTEST_SUITE\s*\(\s*(\w+)", re.M)
ROOT_GROUP = "all_tests"


@dataclass
class Module:
    path: str
    group: str
    title: str
    scenario_prefix: str
    suites: list = field(default_factory=list)
    hand_groups: dict = field(default_factory=dict)

    @property
    def generate_group(self):
        return self.group not in self.hand_groups


@dataclass
class Area:
    path: str
    code: str
    title: str
    description: str
    group: str
    modules: list = field(default_factory=list)


def _slug_parts(rel):
    """Path parts below tests/, each with a leading `<previous part>_` dropped.

    tests/kernel/fifo/fifo_api -> kernel, fifo, api — matching the group names
    the hand-written queue/fifo scaffolding already uses."""
    parts = Path(rel).parts[1:] if Path(rel).parts[0] == "tests" else Path(rel).parts
    out = []
    for part in parts:
        if out and part.startswith(out[-1] + "_"):
            part = part[len(out[-1]) + 1:]
        out.append(part)
    return out


def area_group(rel):
    return "_".join(_slug_parts(rel)) + "_tests"


def module_group(rel):
    return "_".join(_slug_parts(rel)) + "_module"


def _sources(module_dir):
    return sorted(p for p in module_dir.rglob("*") if p.suffix in (".c", ".h") and p.is_file())


def _scenario_prefix(module_dir):
    """The dotted prefix every twister scenario of the module shares."""
    for name in ("tests.yaml", "testcase.yaml"):
        f = module_dir / name
        if f.is_file():
            scenarios = list((yaml.safe_load(f.read_text()) or {}).get("tests", {}))
            break
    else:
        return ""
    if not scenarios:
        return ""
    split = [s.split(".") for s in scenarios]
    common = []
    for parts in zip(*split):
        if len(set(parts)) != 1:
            break
        common.append(parts[0])
    return ".".join(common)


def load_scope(scope_file, zephyr_base):
    data = yaml.safe_load(Path(scope_file).read_text()) or {}
    areas, codes = [], set()
    for entry in data.get("areas", []):
        code = entry["code"]
        if code in codes:
            raise SystemExit(f"test-scope: area code {code!r} used twice")
        codes.add(code)
        area = Area(
            path=entry["path"],
            code=code,
            title=entry["title"],
            description=entry.get("description", ""),
            group=area_group(entry["path"]),
        )
        rels = entry.get("modules") or sorted(
            str(p.parent.relative_to(zephyr_base))
            for p in (zephyr_base / entry["path"]).rglob("tests.yaml")
        )
        for rel in rels:
            mdir = zephyr_base / rel
            text = "\n".join(p.read_text(errors="replace") for p in _sources(mdir))
            hand = {gid: title.strip() for gid, title in DEFGROUP.findall(text)}
            group = module_group(rel)
            area.modules.append(
                Module(
                    path=rel,
                    group=group,
                    title=hand.get(group) or f"{Path(rel).name} test module",
                    scenario_prefix=_scenario_prefix(mdir),
                    suites=list(dict.fromkeys(ZTEST_SUITE.findall(text))),
                    hand_groups=hand,
                )
            )
        areas.append(area)
    return areas


def doxygen_input(areas, zephyr_base):
    dirs = []
    for area in areas:
        for m in area.modules:
            src = zephyr_base / m.path / "src"
            dirs.append(str(src if src.is_dir() else zephyr_base / m.path))
    return " ".join(dirs)


def render_dox(areas):
    # A plain comment, not `@file`: a file page would link to a source page for
    # a build-tree file that Doxygen never generates.
    out = ["/* Generated by testspec_scope.py from test-scope.yaml. Do not edit. */", ""]

    def group(gid, title, parent, brief=""):
        out.append("/**")
        out.append(f" * @defgroup {gid} {title}")
        out.append(f" * @ingroup {parent}")
        if brief:
            out.append(f" * @brief {brief}")
        out.append(" */")
        out.append("")

    for area in areas:
        group(area.group, area.title, ROOT_GROUP)
        for m in area.modules:
            if m.generate_group:
                group(m.group, m.title, area.group, f"Test module at {m.path}.")
            for suite in m.suites:
                if suite not in m.hand_groups:
                    group(suite, f"{suite} ZTest suite", m.group)
    return "\n".join(out)


def _write(path, text, written):
    """Write only if the content changed, so a rebuild does not re-read it."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file() or path.read_text() != text:
        path.write_text(text)
    written.add(path.resolve())


def _heading(text, char):
    return [text, char * len(text), ""]


def _module_dir(area, m):
    rel = Path(m.path).relative_to(area.path)
    return str(rel) if str(rel) != "." else Path(area.path).name


def _area_dir(area):
    return str(Path(area.path).relative_to("tests"))


def write_pages(areas, out_dir, kind):
    """kind: 'spec' or 'report'."""
    page = "test-spec" if kind == "spec" else "test-report"
    out_dir = Path(out_dir)
    written = set()
    top = ["Detailed Test Specifications" if kind == "spec" else "Detailed Test Reports"]
    top = _heading(top[0], "#") + [".. toctree::", "   :maxdepth: 2", ""]
    for area in areas:
        adir = _area_dir(area)
        top.append(f"   {adir}/{page}")
        title = area.title if kind == "spec" else f"{area.title} — Report"
        lines = _heading(title, "=")
        if area.description:
            lines += [area.description, ""]
        lines += [".. toctree::", ""]
        for m in area.modules:
            mdir = _module_dir(area, m)
            lines.append(f"   {mdir}/{page}")
            if kind == "spec":
                body = _heading(m.title, "#") + [
                    f".. testmodule:: {m.group}",
                    f"   :module: {m.path}",
                ]
            else:
                body = _heading(f"{m.title} — Report", "#") + [
                    ".. testreport:: twister_report.xml",
                    f"   :module: {m.scenario_prefix}",
                ]
            _write(out_dir / adir / mdir / f"{page}.rst", "\n".join(body) + "\n", written)
        _write(out_dir / adir / f"{page}.rst", "\n".join(lines) + "\n", written)
    _write(out_dir / ("specs.rst" if kind == "spec" else "reports.rst"), "\n".join(top) + "\n", written)
    # Pages of modules no longer in scope would linger as orphans.
    for stale in out_dir.rglob("*.rst"):
        if stale.resolve() not in written:
            stale.unlink()


def main():
    ap = argparse.ArgumentParser(allow_abbrev=False)
    ap.add_argument("--scope", required=True, type=Path)
    ap.add_argument("--zephyr-base", required=True, type=Path)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("input")
    gen = sub.add_parser("generate")
    gen.add_argument("--dox-out", required=True, type=Path)
    gen.add_argument("--spec-out", required=True, type=Path)
    gen.add_argument("--report-out", required=True, type=Path)
    args = ap.parse_args()

    areas = load_scope(args.scope, args.zephyr_base)
    if args.cmd == "input":
        print(doxygen_input(areas, args.zephyr_base))
        return 0

    for m in (m for a in areas for m in a.modules):
        if not m.scenario_prefix:
            print(f"testspec_scope: {m.path}: no twister scenarios found", file=sys.stderr)
    _write(args.dox_out, render_dox(areas), set())
    write_pages(areas, args.spec_out, "spec")
    write_pages(areas, args.report_out, "report")
    return 0


if __name__ == "__main__":
    sys.exit(main())
