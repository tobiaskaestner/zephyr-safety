#!/usr/bin/env python3
# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0
#
# Copy of claude/kernel-unit/unit-map/.work/enrich.py of the workspace notes
# (2026-10-28, the generator of units.yaml). Changes in the copy, for
# tools/uses_graph_diff.py:
# - the directory of graph.json is the optional fourth argument;
# - the notes directory is optional ("-");
# - in a tree without git (git archive), git grep finds nothing: the
#   field other_files_using_it is empty, the edges do not change.
"""Add callers, requirements, TLA+ tags and fakes to graph.json.

python3 -I enrich.py <zephyr> <safety> <claude-kernel-unit> [<dir>]

<claude-kernel-unit> can be "-": then only the tags of <safety> count.
"""
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

Z, S = (Path(a) for a in sys.argv[1:3])
K = None if sys.argv[3] == "-" else Path(sys.argv[3])
HERE = Path(sys.argv[4]) if len(sys.argv) > 4 else Path(__file__).parent
g = json.load(open(HERE / "graph.json"))
U = g["units"]

# --- API names: group z_impl_/z_vrfy_ ------------------------------------
name2unit = defaultdict(set)
for u, d in U.items():
    for f in d["gives"]:
        n = f["name"]
        name2unit[n].add(u)
        if n.startswith("z_impl_"):
            name2unit[n[len("z_impl_"):]].add(u)
        if n.startswith("z_vrfy_"):
            name2unit[n[len("z_vrfy_"):]].add(u)

for u, d in U.items():
    apis = {}
    for f in d["gives"]:
        n = f["name"]
        api = re.sub(r"^z_(impl|vrfy)_", "", n)
        e = apis.setdefault(api, {"api": api, "forms": [], "syscall": False})
        e["forms"].append(n)
        if n != api:
            e["syscall"] = True
    d["api"] = sorted(apis.values(), key=lambda x: x["api"])

# --- internal callers from the edges --------------------------------------
for u, d in U.items():
    d["called_by_units"] = defaultdict(set)
for u, d in U.items():
    for cat in ("unit", "unit-via-inline"):
        for tgt, names in d["edges"].get(cat, {}).items():
            if tgt in U:
                for n in names:
                    n = n.split("->")[-1]
                    U[tgt]["called_by_units"][u].add(n)
    for tgt, names in d.get("uses_unit_macros", {}).items():
        if tgt in U:
            for n in names:
                U[tgt]["called_by_units"][u].add(n + " (macro)")

# --- external callers by area (git grep) ----------------------------------
names = set()
for u, d in U.items():
    for a in d["api"]:
        names.add(a["api"])
        names.update(a["forms"])
names = sorted(n for n in names if len(n) > 3)
(HERE / "names.txt").write_text("\n".join(names) + "\n")
r = subprocess.run(["git", "grep", "-o", "-w", "-F", "-f", str(HERE / "names.txt"),
                    "--", "*.c", "*.h", "*.S", "*.cpp"],
                   cwd=Z, capture_output=True, text=True)


def area(p):
    for pre, a in (("kernel/", "kernel"), ("arch/", "arch"), ("drivers/", "drivers"),
                   ("subsys/", "subsys"), ("lib/", "lib"), ("include/", "include"),
                   ("tests/", "tests"), ("samples/", "samples"), ("soc/", "soc"),
                   ("boards/", "boards"), ("modules/", "modules")):
        if p.startswith(pre):
            return a
    return "other"


ext = defaultdict(lambda: defaultdict(set))   # name -> area -> files
for line in r.stdout.splitlines():
    p, _, n = line.rpartition(":")
    if not p:
        continue
    ext[n][area(p)].add(p)

for u, d in U.items():
    for a in d["api"]:
        ar = defaultdict(set)
        for n in [a["api"]] + a["forms"]:
            for k, files in ext.get(n, {}).items():
                ar[k] |= {f for f in files if f != u}
        a["ext_files"] = {k: len(v) for k, v in sorted(ar.items())}
        a["ext_examples"] = {k: sorted(v)[:3] for k, v in sorted(ar.items())
                             if k in ("arch", "drivers", "subsys", "lib", "soc")}

# --- requirements via API doc comments ------------------------------------
req_by_name = defaultdict(set)
hdrs = list((Z / "include/zephyr").rglob("*.h")) + list((Z / "kernel").rglob("*.h")) \
    + list((Z / "kernel").rglob("*.c"))
DECL = re.compile(r"(?:#define\s+(\w+)|(\w+)\s*\()")
for h in hdrs:
    txt = h.read_text(errors="replace")
    if "@satisfies" not in txt:
        continue
    for m in re.finditer(r"@satisfies\s+(ZEP-SRS-[\d-]+)", txt):
        end = txt.find("*/", m.end())
        if end < 0:
            continue
        rest = txt[end + 2:end + 600]
        # skip blank lines and further comments
        rest = re.sub(r"/\*.*?\*/", " ", rest, flags=re.S)
        dm = DECL.search(rest)
        if dm:
            req_by_name[dm.group(1) or dm.group(2)].add(m.group(1))
for u, d in U.items():
    reqs = defaultdict(set)
    for a in d["api"]:
        for n in [a["api"]] + a["forms"]:
            for rq in req_by_name.get(n, ()):
                reqs[rq].add(a["api"])
    d["req_via_api"] = {k: sorted(v) for k, v in sorted(reqs.items())}

# --- TLA+ @c-function tags --------------------------------------------------
tla = defaultdict(set)
for root, label in ((S / "spec/tla", "safety/spec/tla/"),
                    (K / "tla" if K else S / "-", "claude/kernel-unit/tla/")):
    for f in root.rglob("*.tla"):
        for m in re.finditer(r"@c-function\s+(\w+)", f.read_text(errors="replace")):
            tla[m.group(1)].add(label + str(f.relative_to(root)))
for u, d in U.items():
    hits = defaultdict(set)
    for a in d["api"]:
        for n in [a["api"]] + a["forms"]:
            for mod in tla.get(n, ()):
                hits[mod].add(n)
    # static functions too (next_up, should_preempt, halt_thread)
    _, = [None]
    d["tla"] = {k: sorted(v) for k, v in hits.items()}
statics = defaultdict(set)
for n, mods in tla.items():
    statics[n] = mods
g["tla_tags"] = {k: sorted(v) for k, v in tla.items()}

# --- unit tests and fakes ---------------------------------------------------
UT = S / "tests/kernel/unit"
inc = defaultdict(set)
for f in UT.rglob("*.c"):
    for m in re.finditer(r"#include\s+<(kernel/[\w/]+\.c)>", f.read_text(errors="replace")):
        inc[m.group(1)].add(str(f.relative_to(S)))
faked = defaultdict(set)
for f in list((UT / "common").rglob("*.h")) + list((UT / "common").rglob("*.c")):
    txt = f.read_text(errors="replace")
    for m in re.finditer(r"(?:DECLARE|DEFINE)_FAKE_(?:VOID|VALUE)_FUNC\w*\(\s*(?:[^,()]+,\s*)?(\w+)\s*[,)]", txt):
        faked[m.group(1)].add(str(f.relative_to(S)))
for u, d in U.items():
    d["unit_test"] = sorted(inc.get(u, ()))
    fk = defaultdict(set)
    for a in d["api"]:
        for n in [a["api"]] + a["forms"]:
            for f in faked.get(n, ()):
                fk[f].add(n)
    d["faked_in"] = {k: sorted(v) for k, v in fk.items()}
    d["called_by_units"] = {k: sorted(v) for k, v in sorted(d["called_by_units"].items())}
g["faked_names"] = {k: sorted(v) for k, v in faked.items()}

json.dump(g, open(HERE / "graph2.json", "w"), indent=1)
print("ok", len(U), "names", len(names), "req-names", len(req_by_name),
      "tla", len(tla), "faked", len(faked))
