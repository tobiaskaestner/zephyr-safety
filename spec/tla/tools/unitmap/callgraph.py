#!/usr/bin/env python3
# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0
#
# Copy of claude/kernel-unit/unit-map/.work/callgraph.py of the workspace notes
# (2026-10-28, the generator of units.yaml). Changes in the copy, for
# tools/uses_graph_diff.py:
# - the output directory is the optional third argument;
# - the unit set also has kernel/timeout/*.h;
# - a driver file that does not exist in the tree is not a unit.
"""Lexical call graph of the Zephyr kernel units and the system timer drivers.

All #if branches count (no preprocessor). Output: graph.json in the script
directory. Run from anywhere: python3 -I callgraph.py <zephyr> <safety> [<outdir>]
"""
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

Z = Path(sys.argv[1])
S = Path(sys.argv[2])
OUT = Path(sys.argv[3]) if len(sys.argv) > 3 else Path(__file__).parent

UNIT_GLOBS = [
    "kernel/*.c", "kernel/smp/*.c", "kernel/sys/*.c", "kernel/userspace/*.c",
    "kernel/paging/*.c", "kernel/include/*.h", "kernel/timeout_*.h",
    "kernel/timeout/*.h",   # copy: the backends moved there after the pin (d268ad0259e)
]
DRIVER_UNITS = [
    "drivers/timer/sys_clock_init.c", "drivers/timer/system_timer_generic.h",
    "drivers/timer/cortex_m_systick.c", "drivers/timer/nrf_grtc_timer.c",
    "drivers/timer/mcux_gpt_timer.c", "drivers/timer/stm32_lptim_timer.c",
    "drivers/timer/sys_lpm_hooks_counter.c",
    "include/zephyr/drivers/timer/system_timer.h",
]
units = []
for g in UNIT_GLOBS:
    units += sorted(str(p.relative_to(Z)) for p in Z.glob(g))
units += [d for d in DRIVER_UNITS if (Z / d).exists()]   # copy: an old tree lacks some
unitset = set(units)

# Index for name resolution: units + public headers + lib + arch/arm.
INDEX_DIRS = ["kernel", "include/zephyr", "lib/os", "lib/heap", "lib/utils",
              "lib/libc/common", "arch/arm/core", "arch/arm/include",
              "arch/common", "drivers/timer", "subsys/tracing/include",
              "soc/st/stm32/common", "drivers/clock_control"]


def ctags(paths):
    cmd = ["ctags", "--output-format=json", "--fields=+neKSZ",
           "--kinds-C=+p+x-m", "--languages=C", "--langmap=C:.c.h", "-o", "-",
           "-R"] + paths
    r = subprocess.run(cmd, cwd=Z, capture_output=True, text=True)
    tags = []
    for line in r.stdout.splitlines():
        try:
            t = json.loads(line)
        except json.JSONDecodeError:
            continue
        if t.get("_type") == "tag":
            tags.append(t)
    return tags


all_tags = ctags(INDEX_DIRS)
defs = defaultdict(list)      # name -> [(path, kind, static)]
fdefs = defaultdict(list)     # path -> function tags (definitions)
vars_ = defaultdict(list)     # name -> [(path, static)]
for t in all_tags:
    k = t["kind"]
    static = "static" in t.get("pattern", "")[:40] or t.get("file", False)
    if k == "function":
        defs[t["name"]].append((t["path"], "function", static))
        fdefs[t["path"]].append(t)
    elif k == "macro":
        defs[t["name"]].append((t["path"], "macro", False))
        fdefs[t["path"]].append(t)
    elif k == "variable":
        vars_[t["name"]].append((t["path"], static))

ALIAS = re.compile(r"\b(\w+)\s*\([^;{)]*\)\s*ALIAS_OF\((\w+)\)")
FALIAS = re.compile(r"FUNC_ALIAS\((\w+),\s*(\w+),")
aliases = {}   # (path, alias) -> target
for p in units:
    txt = (Z / p).read_text(errors="replace")
    for m in ALIAS.finditer(txt):
        aliases[(p, m.group(1))] = m.group(2)
    for m in FALIAS.finditer(txt):
        aliases[(p, m.group(2))] = m.group(1)
for (p, a), tgt in aliases.items():
    defs[a].append((p, "function", False))

STRIP = re.compile(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',
                   re.S)


def strip(text):
    return STRIP.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)


src_cache = {}


def lines_of(path):
    if path not in src_cache:
        txt = (Z / path).read_text(errors="replace")
        src_cache[path] = (txt.split("\n"), strip(txt).split("\n"))
    return src_cache[path]


KEYWORDS = set("""if while for switch return sizeof __typeof__ typeof defined
__attribute__ __asm__ asm __volatile__ alignof _Alignof offsetof _Static_assert
__builtin_expect __builtin_unreachable likely unlikely do else case""".split())
CALL = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
IDENT = re.compile(r"\b([A-Za-z_]\w*)\b")


def calls_in(path, start, end):
    _, s = lines_of(path)
    body = "\n".join(s[start - 1:end])
    return [m.group(1) for m in CALL.finditer(body) if m.group(1) not in KEYWORDS]


def area(path):
    p = path
    if p in unitset:
        return "unit"
    if p.startswith("arch/") or p.startswith("include/zephyr/arch/"):
        return "arch"
    if p.startswith("drivers/clock_control") or "clock_control" in p:
        return "clock_control"
    if p.startswith("drivers/timer") or "drivers/timer" in p:
        return "driver"
    if p.startswith("subsys/tracing") or "tracing" in p:
        return "tracing"
    if p.startswith("soc/"):
        return "soc"
    return "lib"


# Names that are tracing, logging, assert, or syscall glue macros.
GLUE = re.compile(r"^(SYS_PORT_TRACING\w*|LOG_\w+|__ASSERT\w*|CHECKIF|K_OOPS|"
                  r"Z_OOPS|K_SYSCALL_\w+|Z_SYSCALL_\w+|BUILD_ASSERT|"
                  r"SYS_INIT\w*|IS_ENABLED|COND_CODE_\w+|IF_ENABLED|"
                  r"Z_STRUCT_SECTION\w*|STRUCT_SECTION\w*|ARG_UNUSED|"
                  r"CONTAINER_OF|ARRAY_SIZE|MIN|MAX|CLAMP|BIT|BIT64|ROUND_UP|"
                  r"ROUND_DOWN|DIV_ROUND_UP|POINTER_TO_UINT|UINT_TO_POINTER|"
                  r"POINTER_TO_INT|INT_TO_POINTER|__ASSERT_NO_MSG|"
                  r"K_TIMEOUT_EQ|K_TICKS|K_MSEC|K_USEC|K_NO_WAIT|"
                  r"Z_TICK_ABS|SYS_DLIST_FOR_EACH\w*|SYS_SLIST_FOR_EACH\w*|"
                  r"RB_FOR_EACH\w*|_WAIT_Q_FOR_EACH\w*|DT_\w+|DEVICE_\w+|"
                  r"Z_IS_\w+|z_syscall_trap|LOG_MODULE_\w+|K_KERNEL_STACK_\w+|"
                  r"Z_THREAD_\w+|SYS_TRACING_\w+|TOOLCHAIN_\w+|UTIL_\w+|"
                  r"FOR_EACH\w*|LISTIFY|STRINGIFY|Z_LINK_ITERABLE\w*)$")


def resolve(name, path):
    """Return (category, target) for a called name in file path."""
    if GLUE.match(name):
        return ("glue", name)
    cands = [d for d in defs.get(name, []) if d[1] == "function"]
    local = [d for d in cands if d[0] == path]
    if local:
        return ("local", path)
    unit_c = [d for d in cands if d[0] in unitset and d[0] != path]
    if unit_c:
        return ("unit", sorted({d[0] for d in unit_c}))
    if not cands and not name.startswith("z_impl_"):
        zi = [d for d in defs.get("z_impl_" + name, []) if d[1] == "function"]
        if zi:
            return ("unit", sorted({d[0] for d in zi if d[0] in unitset}) or
                    ["?" + zi[0][0]])
    if name.startswith("arch_") or name.startswith("z_arm_") or \
            name.startswith("z_arch_"):
        return ("arch", name)
    if name.startswith("sys_clock_"):
        return ("driver", name)
    if cands:
        a = area(cands[0][0])
        return (a, cands[0][0])
    macros = [d for d in defs.get(name, []) if d[1] == "macro"]
    if macros:
        mp = macros[0][0]
        if mp in unitset:
            return ("unit-macro", mp)
        return ("macro:" + area(mp), mp)
    if re.match(r"^(mem|str)\w+$", name):
        return ("libc", name)
    return ("unresolved", name)


# Transitive closure of inline functions in public headers (depth 3).
inline_cache = {}


def inline_targets(name, depth=0):
    """Units, arch and driver functions reached through a public inline."""
    if name in inline_cache:
        return inline_cache[name]
    inline_cache[name] = set()
    out = set()
    if depth > 3:
        return out
    for t in fdefs_by_name.get(name, []):
        if t["path"] in unitset or not t["path"].endswith(".h"):
            continue
        for c in calls_in(t["path"], t["line"], t.get("end", t["line"])):
            cat, tgt = resolve(c, t["path"])
            if cat == "unit":
                for u in tgt:
                    out.add(("unit", u, c))
            elif cat in ("arch", "driver"):
                out.add((cat, c, c))
            elif cat in ("lib", "macro:lib") and isinstance(tgt, str) and \
                    tgt.endswith(".h"):
                out |= inline_targets(c, depth + 1)
    inline_cache[name] = out
    return out


fdefs_by_name = defaultdict(list)
for p, ts in fdefs.items():
    for t in ts:
        fdefs_by_name[t["name"]].append(t)

KERNEL_FIELD = re.compile(r"\b_kernel\s*\.\s*(\w+)(?:\s*\[[^\]]*\]\s*\.\s*(\w+))?")
CPU_FIELD = re.compile(r"\b(?:_current_cpu|arch_curr_cpu\(\s*\))\s*->\s*(\w+)")

result = {}
for u in units:
    raw, s = lines_of(u)
    ftags = [t for t in fdefs.get(u, []) if t["kind"] == "function"]
    mtags = [t for t in fdefs.get(u, []) if t["kind"] == "macro"]
    gives = []
    for t in ftags:
        static = t.get("file", False) or raw[t["line"] - 1].lstrip().startswith("static")
        inline = "inline" in raw[t["line"] - 1] or "inline" in raw[t["line"] - 2]
        if not static or u.endswith(".h"):
            gives.append({"name": t["name"], "line": t["line"],
                          "static_inline": bool(static)})
    for (p, a), tgt in aliases.items():
        if p == u:
            gives.append({"name": a, "line": 0, "static_inline": False,
                          "alias_of": tgt})
    edges = defaultdict(lambda: defaultdict(set))   # category -> target -> names
    for t in ftags:
        for c in calls_in(u, t["line"], t.get("end", t["line"])):
            cat, tgt = resolve(c, u)
            if cat == "local" or cat == "glue":
                continue
            if cat == "unit":
                for x in tgt:
                    edges["unit"][x].add(c)
            else:
                edges[cat][tgt if isinstance(tgt, str) else str(tgt)].add(c)
                if cat in ("lib", "macro:lib") and str(tgt).endswith(".h"):
                    for kind, x, via in inline_targets(c):
                        if kind == "unit" and x != u:
                            edges["unit-via-inline"][x].add(f"{c}->{via}")
                        elif kind in ("arch", "driver"):
                            edges[kind + "-via-inline"][x].add(c)
    # macros of kernel headers that the file uses (names, not calls)
    body = "\n".join(s)
    idents = set(IDENT.findall(body))
    used_unit_macros = defaultdict(set)
    for n in idents:
        for d in defs.get(n, []):
            if d[1] == "macro" and d[0] in unitset and d[0] != u:
                used_unit_macros[d[0]].add(n)
    # shared state
    kfields = sorted({m.group(1) + ("[]." + m.group(2) if m.group(2) else "")
                      for m in KERNEL_FIELD.finditer(body)})
    cfields = sorted({m.group(1) for m in CPU_FIELD.finditer(body)})
    own_vars = sorted({t["name"] for t in all_tags if t["path"] == u and
                       t["kind"] == "variable"})
    ext_vars = defaultdict(set)
    for n in idents:
        for p, st in vars_.get(n, []):
            if p != u and p in unitset and not st:
                ext_vars[p].add(n)
    configs = defaultdict(int)
    for m in re.finditer(r"\bCONFIG_\w+", body):
        configs[m.group(0)] += 1
    result[u] = {
        "lines": len(raw),
        "gives": gives,
        "macros_defined": [t["name"] for t in mtags],
        "edges": {k: {t: sorted(v) for t, v in d.items()} for k, d in edges.items()},
        "uses_unit_macros": {k: sorted(v) for k, v in used_unit_macros.items()},
        "kernel_fields": kfields,
        "cpu_fields": cfields,
        "current": bool(re.search(r"\b_current\b", body)),
        "own_vars": own_vars,
        "ext_vars": {k: sorted(v) for k, v in ext_vars.items()},
        "configs": dict(sorted(configs.items(), key=lambda x: -x[1])),
        "satisfies": sorted(set(re.findall(r"@satisfies\s+(ZEP-SRS-[\d-]+)",
                                           "\n".join(raw)))),
    }

json.dump({"units": result}, open(OUT / "graph.json", "w"), indent=1)
print("units", len(result))
