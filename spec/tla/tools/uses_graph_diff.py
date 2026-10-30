#!/usr/bin/env python3
# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Compare the uses graph of the kernel at two Zephyr commits.

The unit map (``units.yaml`` of the workspace notes) comes from three
scripts. ``tools/unitmap/`` has copies of them. This script runs the copies
on two commits and compares the results:

- the edges between the components after the cuts (``meta.layers.edges``):
  new edges and removed edges;
- the cut edges (``meta.cut_edges``): new and removed cuts, by
  (from, to, reason), and the file pairs of each cut;
- the edges against the layer order of the architecture (layers world,
  foundation, scheduler, kernel API, client): an edge from a component to a
  component of a higher layer;
- the unit files: new files, removed files, and the files that are not in
  the table of the generator (group ``New``).

For each commit, the script extracts the necessary directories of the tree
with ``git archive`` into ``<work>/<commit>/tree`` and writes the output of
the generator to ``<work>/<commit>/out``. It does not change the Zephyr
repository. A second run reuses the output (``--rerun`` deletes it).

Usage::

   uses_graph_diff.py --other <rev> [--base <rev>] [--reference units.yaml]

``--base`` defaults to the pin of ``spec/tla/c-functions.json``.
``--reference`` compares the output for the base with a ``units.yaml`` that
the original scripts wrote (a calibration of the copies).

It needs universal-ctags 6.x and PyYAML. Exit status: 0 without a
difference, 1 with a difference, 2 on a setup error.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

TOOLS = Path(__file__).resolve().parent
SPEC = TOOLS.parent
SAFETY = SPEC.parent.parent
UNITMAP = TOOLS / "unitmap"

# The directories that callgraph.py reads (UNIT_GLOBS, DRIVER_UNITS,
# INDEX_DIRS) and that enrich.py reads (the @satisfies tags).
ARCHIVE_PATHS = [
    "kernel", "include/zephyr", "lib/os", "lib/heap", "lib/utils",
    "lib/libc/common", "arch/arm/core", "arch/arm/include", "arch/common",
    "drivers/timer", "subsys/tracing/include", "soc/st/stm32/common",
    "drivers/clock_control",
]

# spec-architecture.md, section 2: the layers, from the bottom. "Queues" is
# the group of RunQueue and WaitQueue in the unit map.
LAYERS = ["world", "foundation", "scheduler", "kernel API", "client"]
LAYER_OF = {
    "Platform": "world", "Device": "world",
    "SysClock": "foundation", "TimeoutQueue": "foundation", "SchedLock": "foundation",
    "Usage": "foundation", "Timeout": "foundation", "ThreadState": "foundation",
    "Queues": "foundation", "RunQueue": "foundation", "WaitQueue": "foundation",
    "Ipi": "foundation",
    "Scheduler": "scheduler",
    "TimeSlice": "kernel API", "Idle": "kernel API", "ObjRegistry": "kernel API",
    "Thread": "kernel API", "SchedApi": "kernel API", "Fatal": "kernel API",
    "Userspace": "kernel API", "Boot": "kernel API",
}


def layer(group):
    if group.startswith("Obj:"):
        return "kernel API"
    return LAYER_OF.get(group)


def git(repo, *args, **kw):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, **kw)


def resolve(repo, rev):
    r = git(repo, "rev-parse", "--verify", "--quiet", rev + "^{commit}", text=True)
    if r.returncode != 0:
        sys.exit(f"error: {rev} is not a commit in {repo}")
    return r.stdout.strip()


def generate(repo, rev, work, rerun):
    """Run the copies of the generator on one commit. Return units.yaml."""
    sha = resolve(repo, rev)
    base = work / sha[:12]
    out = base / "out"
    if rerun and base.exists():
        shutil.rmtree(base)
    if (out / "units.yaml").exists():
        return sha, yaml.safe_load((out / "units.yaml").read_text())
    tree = base / "tree"
    tree.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    have = git(repo, "ls-tree", "--name-only", sha, "--", *ARCHIVE_PATHS, text=True)
    paths = have.stdout.split()
    arch = git(repo, "archive", "--format=tar", sha, "--", *paths)
    if arch.returncode != 0:
        sys.exit("error: git archive: " + arch.stderr.decode(errors="replace"))
    subprocess.run(["tar", "-x", "-C", str(tree)], input=arch.stdout, check=True)
    py = [sys.executable, "-I"]
    label = f"zephyr @ {sha[:11]} ({rev})"
    for cmd in ([*py, str(UNITMAP / "callgraph.py"), str(tree), str(SAFETY), str(out)],
                [*py, str(UNITMAP / "enrich.py"), str(tree), str(SAFETY), "-", str(out)],
                [*py, str(UNITMAP / "gen.py"), str(tree), str(out), label]):
        r = subprocess.run(cmd, capture_output=True, text=True)
        (out / "run.log").open("a").write(" ".join(cmd) + "\n" + r.stdout + r.stderr)
        if r.returncode != 0:
            sys.exit(f"error: {cmd[2]} failed, see {out / 'run.log'}\n{r.stderr[-2000:]}")
    return sha, yaml.safe_load((out / "units.yaml").read_text())


def edges(doc):
    return {(a, b) for a, ts in doc["meta"]["layers"]["edges"].items() for b in ts}


def cuts(doc):
    return {(c["from"], c["to"], c["reason"]): set(c["files"]) for c in doc["meta"]["cut_edges"]}


def groups(doc):
    return {u: d.get("contract_group") for u, d in doc["units"].items()}


def against_order(es):
    bad, unknown = [], set()
    for a, b in sorted(es):
        la, lb = layer(a), layer(b)
        if la is None:
            unknown.add(a)
        if lb is None:
            unknown.add(b)
        if la and lb and LAYERS.index(la) < LAYERS.index(lb):
            bad.append((a, b, la, lb))
    return bad, sorted(unknown)


def compare(bdoc, odoc):
    """The differences as a dict of lists."""
    be, oe = edges(bdoc), edges(odoc)
    bc, oc = cuts(bdoc), cuts(odoc)
    bg, og = groups(bdoc), groups(odoc)
    res = {
        "new_edges": sorted(oe - be),
        "removed_edges": sorted(be - oe),
        "new_cuts": sorted(set(oc) - set(bc)),
        "removed_cuts": sorted(set(bc) - set(oc)),
        "cut_files_changed": [],
        "new_units": sorted(set(og) - set(bg)),
        "removed_units": sorted(set(bg) - set(og)),
        "group_changed": sorted((u, bg[u], og[u]) for u in set(bg) & set(og) if bg[u] != og[u]),
        "not_in_table": odoc["meta"].get("unit_files_not_in_table", {}),
        "not_in_table_base": bdoc["meta"].get("unit_files_not_in_table", {}),
    }
    for k in sorted(set(bc) & set(oc)):
        if bc[k] != oc[k]:
            res["cut_files_changed"].append((k, sorted(bc[k] - oc[k]), sorted(oc[k] - bc[k])))
    res["against_order"], res["unknown_groups"] = against_order(oe)
    res["against_order_base"], _ = against_order(be)
    return res


def report(res, blabel, olabel):
    lines = [f"# Uses graph: {blabel} -> {olabel}", ""]

    def section(title, items, fmt):
        lines.append(f"## {title}: {len(items)}")
        lines.extend("- " + fmt(x) for x in items)
        lines.append("")

    section("New edges (after the cuts)", res["new_edges"], lambda e: f"{e[0]} -> {e[1]}")
    section("Removed edges", res["removed_edges"], lambda e: f"{e[0]} -> {e[1]}")
    section("Edges against the layer order (other commit)", res["against_order"],
            lambda e: f"{e[0]} ({e[2]}) -> {e[1]} ({e[3]})")
    if res["against_order_base"]:
        section("Edges against the layer order (base commit)", res["against_order_base"],
                lambda e: f"{e[0]} ({e[2]}) -> {e[1]} ({e[3]})")
    section("Groups without a layer", res["unknown_groups"], str)
    section("New cut edges", res["new_cuts"], lambda c: f"{c[0]} -> {c[1]}: {c[2]}")
    section("Removed cut edges", res["removed_cuts"], lambda c: f"{c[0]} -> {c[1]}: {c[2]}")
    section("Cut edges with other file pairs", res["cut_files_changed"],
            lambda c: f"{c[0][0]} -> {c[0][1]} ({c[0][2]}): only base {c[1]}; only other {c[2]}")
    section("New unit files", res["new_units"], str)
    section("Removed unit files", res["removed_units"], str)
    section("Unit files with another component", res["group_changed"],
            lambda g: f"{g[0]}: {g[1]} -> {g[2]}")
    for key, which in (("not_in_table_base", "base"), ("not_in_table", "other")):
        section(f"Unit files that are not in the table of gen.py ({which} commit)",
                sorted(res[key].items()),
                lambda x: f"{x[0]}: " + (f"as {x[1]}" if x[1] else "group New"))
    return "\n".join(lines)


def calibrate(doc, ref_path):
    ref = yaml.safe_load(Path(ref_path).read_text())
    msgs = []
    if edges(doc) != edges(ref):
        msgs.append(f"edges differ: only copy {sorted(edges(doc) - edges(ref))}, "
                    f"only reference {sorted(edges(ref) - edges(doc))}")
    if cuts(doc) != cuts(ref):
        msgs.append("cut edges differ")
    if groups(doc) != groups(ref):
        msgs.append("components of the unit files differ")
    return msgs


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--zephyr", type=Path,
                    default=Path(os.environ.get("ZEPHYR_BASE", SAFETY.parent / "zephyr")))
    ap.add_argument("--base", help="default: the pin of spec/tla/c-functions.json")
    ap.add_argument("--other", required=True)
    ap.add_argument("--work", type=Path, default=SAFETY / "build/drift/unitmap")
    ap.add_argument("--reference", help="units.yaml of the original scripts, for the base")
    ap.add_argument("--rerun", action="store_true")
    ap.add_argument("--json", help="write the differences to this file")
    args = ap.parse_args()
    if shutil.which("ctags") is None:
        sys.exit("error: universal-ctags is necessary")
    base = args.base or json.loads((SPEC / "c-functions.json").read_text())["meta"]["commit"]
    bsha, bdoc = generate(args.zephyr, base, args.work, args.rerun)
    osha, odoc = generate(args.zephyr, args.other, args.work, args.rerun)
    rc = 0
    if args.reference:
        msgs = calibrate(bdoc, args.reference)
        print("calibration: " + ("the copies give the reference edges, cuts and components"
                                 if not msgs else "; ".join(msgs)))
        rc = 1 if msgs else 0
    res = compare(bdoc, odoc)
    print(report(res, f"{bsha[:11]} ({base})", f"{osha[:11]} ({args.other})"))
    if args.json:
        Path(args.json).write_text(json.dumps(res, indent=1, default=list) + "\n")
    keys = ("new_edges", "removed_edges", "against_order", "new_cuts", "removed_cuts",
            "new_units", "removed_units", "group_changed")
    return 1 if rc or any(res[k] for k in keys) else 0


if __name__ == "__main__":
    sys.exit(main())
