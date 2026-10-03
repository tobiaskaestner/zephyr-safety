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
      area -> module -> suite. A group the sources already define with
      ``@defgroup`` is left to them — a hand-written group carries prose that a
      generated one cannot, so it takes precedence. The area group is Zephyr's
      own per-area test group (``tests_<path>``, see ``area_group``), so the
      area level is normally upstream's.
    * The test-specification and test-report page trees: one page per area, one
      per module, and the top-level ``specs.rst`` / ``reports.rst`` toctrees.

The testspec Doxyfile's ``ZTEST_SUITE`` expansion defines no group, so every
suite group has exactly one definition — here or in the sources — and the
result does not depend on the order Doxygen reads its INPUT in.

A generated suite group has the id ``<module group>__<suite>``
(``QUALIFIER``), not the bare suite name. There are two causes:

* A suite can have the name of a C function (``irq_offload``, ``printk``).
  With a bare id, Doxygen resolves ``@see irq_offload()`` to the group, not to
  the function.
* Two modules in scope can have tests of the same suite (``workqueue_api`` in
  tests/kernel/workq/user_work and work_queue). With a bare id, this suite is
  one group in both modules, and each module page shows the tests of the other
  module too.

zdocs' ``testmodule_suite_qualifier`` in the conf.py of the test
specification removes the qualifier again, so the test cases keep the real
suite name. ``generate --suites-out`` writes these groups as JSON for
doxygen_filter_kconfig.py, which points the ZTESTs of each module at them. A
suite group that the sources define by hand keeps its name.
"""

import argparse
import collections
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from doxygen_filter_kconfig import ZTEST_MACRO  # noqa: E402

DEFGROUP = re.compile(r"[@\\]defgroup\s+(\w+)[ \t]*([^\n]*)")
ZTEST_SUITE = re.compile(r"^\s*ZTEST_SUITE\s*\(\s*(\w+)", re.M)
# The suite of every test (see doxygen_filter_kconfig.ZTEST_MACRO).
ZTEST_OF = re.compile(rf"^[ \t]*{ZTEST_MACRO}\s*\(\s*(\w+)\s*,", re.M)
ROOT_GROUP = "all_tests"
# Between the module group and the suite in the id of a generated suite group.
# Must match testmodule_suite_qualifier in specification/test-specification/conf.py.
QUALIFIER = "__"


@dataclass
class Module:
    path: str
    group: str
    title: str
    scenario_prefix: str
    suites: list = field(default_factory=list)
    hand_groups: dict = field(default_factory=dict)
    # suite -> its group here, for every suite whose group is generated
    qualified: dict = field(default_factory=dict)

    @property
    def generate_group(self):
        return self.group not in self.hand_groups

    def suite_group(self, suite):
        return self.qualified.get(suite, suite)


@dataclass
class Area:
    path: str
    code: str
    title: str
    description: str
    group: str
    modules: list = field(default_factory=list)
    hand_group: bool = False


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
    """Zephyr's test group for an area: tests/kernel/fifo -> tests_kernel_fifo.

    Upstream's documentation guidelines put test documentation in groups
    prefixed ``tests_`` under ``all_tests``. Areas still on the older
    ``kernel_<area>_tests`` naming set ``group:`` in the scope file."""
    return "_".join(["tests"] + _slug_parts(rel))


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


def _check_hand_suites(rel, text, module, suites):
    """A suite group the sources define by hand must sit in its module group.

    Otherwise `testmodule::` never walks it and every test in the suite drops
    out of the test specification without a warning.
    """
    for suite in suites:
        m = re.search(rf"[@\\]defgroup\s+{re.escape(suite)}\b", text)
        block = text[m.end():text.find("*/", m.end())]
        if not re.search(rf"[@\\]ingroup\s+(?:\w+\s+)*{re.escape(module)}\b", block):
            raise SystemExit(
                f"test-scope: {rel}: suite group {suite!r} is defined in the sources "
                f"but not @ingroup {module}; drop the @defgroup or add the @ingroup"
            )


def _check_hand_area(zephyr_base, area):
    """Whether the sources define the area group; if they do, it must sit in
    ROOT_GROUP, or the whole area drops out of the Doxygen nav."""
    for m in area.modules:
        for f in _sources(zephyr_base / m.path):
            text = f.read_text(errors="replace")
            d = re.search(rf"[@\\]defgroup\s+{re.escape(area.group)}\b", text)
            if not d:
                continue
            block = text[d.end():text.find("*/", d.end())]
            if not re.search(rf"[@\\]ingroup\s+(?:\w+\s+)*{ROOT_GROUP}\b", block):
                raise SystemExit(
                    f"test-scope: {f.relative_to(zephyr_base)}: area group {area.group!r} "
                    f"is defined in the sources but not @ingroup {ROOT_GROUP}"
                )
            return True
    return False


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
            group=entry.get("group") or area_group(entry["path"]),
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
            # A suite the module declares but holds no test of gets no group
            # here: a suite name another module also declares
            # (tests/arch/common/interrupt declares gen_isr_table_multilevel,
            # whose tests are in gen_isr_table) would otherwise be one group
            # in both modules, and its tests render on both pages.
            tested = set(ZTEST_OF.findall(text))
            suites = [s for s in dict.fromkeys(ZTEST_SUITE.findall(text)) if s in tested]
            _check_hand_suites(rel, text, group, [s for s in suites if s in hand])
            area.modules.append(
                Module(
                    path=rel,
                    group=group,
                    title=hand.get(group) or f"{Path(rel).name} test module",
                    scenario_prefix=_scenario_prefix(mdir),
                    suites=suites,
                    hand_groups=hand,
                )
            )
        area.hand_group = _check_hand_area(zephyr_base, area)
        areas.append(area)
    qualify_suites(areas)
    return areas


def qualify_suites(areas):
    """Give every suite whose group is generated the group id
    ``<module group>__<suite>``.

    Thus a suite group cannot have the name of a C symbol, and a suite that
    two modules have tests of gets one group in each module. A suite group that
    the sources define by hand keeps its name. Such a group is not permitted for
    a suite that more than one module has tests of, because it would be one
    group in all of these modules. A module's suites are the ones it has tests
    of (see load_scope), so a suite that a module only declares
    (gen_isr_table_multilevel) is not shared."""
    users = collections.defaultdict(list)
    for m in (m for a in areas for m in a.modules):
        for suite in m.suites:
            users[suite].append(m)
    for suite, mods in users.items():
        for m in mods:
            if QUALIFIER in suite:
                raise SystemExit(
                    f"test-scope: {m.path}: suite name {suite!r} contains {QUALIFIER!r}, "
                    f"which testmodule_suite_qualifier cannot remove correctly"
                )
            if suite in m.hand_groups:
                if len(mods) > 1:
                    raise SystemExit(
                        f"test-scope: {m.path}: suite group {suite!r} is defined in the "
                        f"sources, but {', '.join(o.path for o in mods if o is not m)} "
                        f"has tests of suite {suite!r} too; drop the @defgroup"
                    )
                continue
            m.qualified[suite] = f"{m.group}{QUALIFIER}{suite}"


def qualified_suites(areas, zephyr_base):
    """{module directory: {suite: group}} of the generated suite groups, for
    doxygen_filter_kconfig.py --suites."""
    return {
        str((zephyr_base / m.path).resolve()): dict(sorted(m.qualified.items()))
        for a in areas
        for m in a.modules
        if m.qualified
    }


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
        if not area.hand_group:
            group(area.group, area.title, ROOT_GROUP)
        for m in area.modules:
            if m.generate_group:
                group(m.group, m.title, area.group, f"Test module at {m.path}.")
            for suite in m.suites:
                if suite not in m.hand_groups:
                    group(m.suite_group(suite), f"{suite} ZTest suite", m.group)
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
                    # By test directory, not scenario prefix: scenario names do
                    # not follow directories (tests/kernel/timer/timer_api runs
                    # as kernel.timer, a prefix of timer_error_case's), so a
                    # prefix match put one module's results on another's page.
                    ".. testreport:: twister_report.xml",
                    f"   :path: {m.path}",
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
    gen.add_argument("--suites-out", type=Path, help="qualified suite groups, as JSON")
    args = ap.parse_args()

    areas = load_scope(args.scope, args.zephyr_base)
    if args.cmd == "input":
        print(doxygen_input(areas, args.zephyr_base))
        return 0

    for m in (m for a in areas for m in a.modules):
        if not m.scenario_prefix:
            print(f"testspec_scope: {m.path}: no twister scenarios found", file=sys.stderr)
    _write(args.dox_out, render_dox(areas), set())
    if args.suites_out:
        suites = qualified_suites(areas, args.zephyr_base)
        _write(args.suites_out, json.dumps(suites, indent=2, sort_keys=True) + "\n", set())
    write_pages(areas, args.spec_out, "spec")
    write_pages(areas, args.report_out, "report")
    return 0


if __name__ == "__main__":
    sys.exit(main())
