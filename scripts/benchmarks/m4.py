#!/usr/bin/env python3
# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Tables of the M4 measurement: interrupt mask time and ISR body time per call site.

An app with M4 (common/src/irqmask.c, tree ws-up-irqoff) prints, after its
latency histograms:

    LAT META m4=1
    LAT META m4_floor_cyc=..       smallest value of an empty mask section
    LAT META m4_pair_cost_cyc=..   extra CPU time of the hooks per section
    LAT META m4_isr_floor_cyc=..   smallest value of an empty ISR body
    LAT META m4_window_cyc=..      length of the measurement (kernel clock)
    LAT META m4_masked_cyc=..      sum of all mask sections
    LAT M4 BEGIN sites=.. used=.. dropped=.. bins=.. sub_bits=..
    LAT M4SITE <name> kind=mask|isr ipsr=.. pc=0x.. end_pc=0x.. n=.. sum=.. min=.. max=..
    LAT HIST <name> ...            (the histogram of the site, see latbench.py)
    LAT M4 END

<name> is m4.<kind>.<ctx>.<pc>: ctx "t" is a thread, e<n> the exception
number (14 PendSV, 15 SysTick, 16 + n IRQ n). For a mask section, pc is the
return address of the start hook: it points into the code that masked the
interrupts. For an ISR body, pc is the address of the ISR function.

The latency histograms of an M4 run are not data: the hooks make each mask
section longer.

Subcommands:

    table  LOG   one table per kind, sorted by max, with function names
                 from the ELF of the point (addr2line and nm of the SDK)
    sweep  LOG.. one row per log: calibration, totals, the longest mask
                 section and ISR body, the IRQ tail of the same run
"""

import argparse
import bisect
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import latbench  # noqa: E402

EXC_NAMES = {0: "thread", 2: "NMI", 3: "HardFault", 11: "SVC", 14: "PendSV", 15: "SysTick"}

# Functions of the mask path itself. A name chain does not show them.
PLUMBING = {"arch_irq_lock", "arch_irq_unlock", "z_arm_irq_mask_hook_begin", "z_arm_irq_mask_hook_end"}


def ctx_name(ipsr):
    if ipsr in EXC_NAMES:
        return EXC_NAMES[ipsr]
    if ipsr >= 16:
        return f"irq{ipsr - 16}"
    return f"exc{ipsr}"


def _fields(text):
    out = {}
    for item in text.split():
        key, _, value = item.partition("=")
        out[key] = value
    return out


def parse_m4(path):
    """Return the last run of the log with an "m4" entry.

    run["m4"] = {"table": {sites, used, dropped, bins, sub_bits},
                 "sites": [site, ...]}; each site has name, kind, ipsr, ctx,
    pc, end_pc, n, sum, min, max and hist (the parsed LAT HIST block).
    A run without M4 lines has run["m4"] = None.
    """
    run = latbench.parse_log(path)
    table = None
    sites = []
    for line in Path(path).read_text().splitlines():
        if line.startswith("LAT BEGIN"):
            table, sites = None, []
        elif line.startswith("LAT M4 BEGIN"):
            table = {k: int(v) for k, v in _fields(line[len("LAT M4 BEGIN"):]).items()}
            sites = []
        elif line.startswith("LAT M4SITE "):
            name, _, rest = line[len("LAT M4SITE "):].partition(" ")
            f = _fields(rest)
            site = {
                "name": name,
                "kind": f["kind"],
                "ipsr": int(f["ipsr"]),
                "ctx": ctx_name(int(f["ipsr"])),
                "pc": int(f["pc"], 16),
                "end_pc": int(f["end_pc"], 16),
                **{k: int(f[k]) for k in ("n", "sum", "min", "max")},
            }
            site["hist"] = run["hists"].get(name)
            sites.append(site)
    run["m4"] = None if table is None else {"table": table, "sites": sites}
    return run


def meta_int(meta, key, default=0):
    try:
        return int(meta[key])
    except (KeyError, ValueError):
        return default


# ------------------------------------------------------------------ names

def parse_nm(text):
    """Return a sorted list of (address, name) of the function symbols in 'nm -n' output."""
    out = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[1] in "tTwW":
            out.append((int(parts[0], 16) & ~1, parts[2]))
    out.sort()
    return out


def parse_addr2line(text):
    """Parse 'addr2line -a -f -i' output into {address: [(function, file:line), ...]}.

    The first pair of each address is the innermost inline level, the last
    one is the real function.
    """
    out = {}
    cur = None
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("0x"):
            cur = int(line, 16)
            out[cur] = []
            i += 1
            continue
        if cur is not None and i + 1 < len(lines):
            out[cur].append((line, lines[i + 1].strip()))
            i += 2
            continue
        i += 1
    return out


class Symbolizer:
    """Function names for code addresses, from addr2line (inline chain) and nm (fallback)."""

    def __init__(self, elf, prefix):
        self.elf = str(elf)
        self.prefix = prefix
        nm = subprocess.run([prefix + "nm", "-n", "--defined-only", self.elf],
                            capture_output=True, text=True, check=True).stdout
        self.syms = parse_nm(nm)
        self.addrs = [a for a, _ in self.syms]

    def nm_name(self, addr):
        i = bisect.bisect_right(self.addrs, addr) - 1
        if i < 0:
            return "?"
        a, name = self.syms[i]
        return name if addr == a else f"{name}+0x{addr - a:x}"

    def lookup(self, addrs):
        """Return {address: [(function, file:line), ...]} for code addresses (Thumb bit clear)."""
        if not addrs:
            return {}
        r = subprocess.run([self.prefix + "addr2line", "-e", self.elf, "-a", "-f", "-i", "-C"]
                           + [f"0x{a:x}" for a in addrs], capture_output=True, text=True, check=True)
        return parse_addr2line(r.stdout)


def call_addr(pc):
    """The address of the call instruction for a return address (Thumb: bit 0 set, BL is 4 bytes)."""
    return (pc & ~1) - 2


def site_addr(site):
    return (site["pc"] & ~1) if site["kind"] == "isr" else call_addr(site["pc"])


def describe(chain, nm_name):
    """Return (function, place, via) for an inline chain.

    function: the real function; place: its file:line (file name only);
    via: the inlined functions between, innermost last, without the mask
    plumbing.
    """
    chain = [(f, loc) for f, loc in chain if f != "??"]
    if not chain:
        return nm_name, "?", ""
    func, loc = chain[-1]
    place = re.sub(r" \(discriminator \d+\)", "", Path(loc).name)
    via = [f for f, _ in reversed(chain[:-1]) if f not in PLUMBING]
    return func, place, "<".join(via)


def find_prefix(log, given=None):
    """The binutils prefix: --binutils, else the SDK of the run manifest, else none."""
    if given:
        return given
    for d in Path(log).resolve().parents:
        m = d / "manifest.json"
        if m.is_file():
            sdk = json.loads(m.read_text()).get("toolchain", {}).get("path")
            if sdk:
                p = Path(sdk) / "gnu" / "arm-zephyr-eabi" / "bin" / "arm-zephyr-eabi-"
                if Path(str(p) + "nm").exists():
                    return str(p)
            break
    return None


def symbolizer_for(log, elf=None, prefix=None):
    elf = Path(elf) if elf else Path(log).parent / "zephyr.elf"
    prefix = find_prefix(log, prefix)
    if not elf.is_file() or not prefix:
        return None
    return Symbolizer(elf, prefix)


# ------------------------------------------------------------------ tables

def site_rows(run, sym=None, kind=None):
    """One row per site, sorted by max (largest first)."""
    m4 = run["m4"]
    meta = run["meta"]
    sites = [s for s in m4["sites"] if kind is None or s["kind"] == kind]
    names = {}
    if sym is not None:
        addrs = sorted({site_addr(s) for s in sites} | {call_addr(s["end_pc"]) for s in sites if s["end_pc"]})
        names = sym.lookup(addrs)
    total = {k: sum(s["sum"] for s in m4["sites"] if s["kind"] == k) for k in ("mask", "isr")}
    rows = []
    for s in sorted(sites, key=lambda s: (-s["max"], s["name"])):
        floor = meta_int(meta, "m4_isr_floor_cyc" if s["kind"] == "isr" else "m4_floor_cyc")
        h = s["hist"]
        row = {
            "kind": s["kind"],
            "ctx": s["ctx"],
            "n": s["n"],
            "mean": round(s["sum"] / s["n"], 1) if s["n"] else 0,
            "p50": latbench.quantile(h, 0.5) if h else "-",
            "p99": latbench.quantile(h, 0.99) if h else "-",
            "p99.99": latbench.quantile(h, 0.9999) if h else "-",
            "max": s["max"],
            "max_net": max(s["max"] - floor, 0),
            "share%": round(100 * s["sum"] / total[s["kind"]], 1) if total[s["kind"]] else 0,
            "pc": f"0x{s['pc']:08x}",
        }
        if sym is not None:
            a = site_addr(s)
            func, place, via = describe(names.get(a, []), sym.nm_name(a))
            row.update(function=func, place=place, via=via)
            if s["end_pc"]:
                e = call_addr(s["end_pc"])
                efunc, eplace, _ = describe(names.get(e, []), sym.nm_name(e))
                row["max_end"] = f"{efunc} ({eplace})"
            else:
                row["max_end"] = ""
        rows.append(row)
    return rows


def print_rows(rows, md=False, out=None):
    out = out or sys.stdout
    if not rows:
        print("(no sites)", file=out)
        return
    cols = list(rows[0].keys())
    if md:
        print("| " + " | ".join(cols) + " |", file=out)
        print("|" + "|".join("---" for _ in cols) + "|", file=out)
        for r in rows:
            print("| " + " | ".join(str(r[c]) for c in cols) + " |", file=out)
        return
    widths = {c: max(len(c), *(len(str(r[c])) for r in rows)) for c in cols}
    print("  ".join(c.rjust(widths[c]) for c in cols), file=out)
    for r in rows:
        print("  ".join(str(r[c]).rjust(widths[c]) for c in cols), file=out)


def header(run, out=None):
    out = out or sys.stdout
    meta = run["meta"]
    t = run["m4"]["table"]
    window = meta_int(meta, "m4_window_cyc")
    masked = meta_int(meta, "m4_masked_cyc")
    frac = f"{100 * masked / window:.2f} %" if window else "?"
    print(f"{meta.get('app', '?')} {meta.get('variant', '?')}  floor {meta.get('m4_floor_cyc', '?')}"
          f"  pair cost {meta.get('m4_pair_cost_cyc', '?')}  isr floor {meta.get('m4_isr_floor_cyc', '?')}"
          f"  sites {t['used']}/{t['sites']}  dropped {t['dropped']}"
          f"  sections {meta.get('m4_sections', '?')}  masked {frac} of the window"
          f"  unmatched end {meta.get('m4_unmatched_end', '?')}  begin open {meta.get('m4_begin_open', '?')}",
          file=out)


def cmd_table(args):
    run = parse_m4(args.log)
    if run["m4"] is None:
        sys.exit(f"{args.log}: no M4 output")
    sym = None if args.no_names else symbolizer_for(args.log, args.elf, args.binutils)
    if sym is None and not args.no_names:
        print("note: no ELF or no binutils, no function names (--elf, --binutils)", file=sys.stderr)
    if args.json:
        print(json.dumps({k: site_rows(run, sym, k)[: args.top] for k in ("mask", "isr")}, indent=1))
        return
    header(run)
    for kind, title in (("mask", "Mask sections (interrupts masked)"), ("isr", "ISR bodies")):
        rows = site_rows(run, sym, kind)[: args.top]
        if rows:
            print(f"\n{title}: values in cycles, max_net = max - floor")
            print_rows(rows, args.md)


def sweep_row(path):
    run = parse_m4(path)
    meta = run["meta"]
    row = {"log": "/".join(Path(path).parts[-3:-1])}
    if run["m4"] is None:
        row["m4"] = "no"
        return row
    sites = run["m4"]["sites"]
    mask = [s for s in sites if s["kind"] == "mask"]
    isr = [s for s in sites if s["kind"] == "isr"]
    window = meta_int(meta, "m4_window_cyc")
    top_m = max(mask, key=lambda s: s["max"], default=None)
    top_i = max(isr, key=lambda s: s["max"], default=None)
    irq = run["hists"].get("irq")
    probe = meta_int(meta, "m4_probe_cyc")
    row.update({
        "floor": meta.get("m4_floor_cyc"),
        "cost": meta.get("m4_pair_cost_cyc"),
        "sites": run["m4"]["table"]["used"],
        "drop": run["m4"]["table"]["dropped"],
        "masked%": round(100 * meta_int(meta, "m4_masked_cyc") / window, 2) if window else "?",
        "mask_max": top_m["max"] if top_m else "-",
        "mask_max_ctx": top_m["ctx"] if top_m else "-",
        "mask_max_pc": f"0x{top_m['pc']:08x}" if top_m else "-",
        "isr_max": top_i["max"] if top_i else "-",
        "isr_max_ctx": top_i["ctx"] if top_i else "-",
        "irq_p99.99": latbench.quantile(irq, 0.9999) if irq else "-",
        "irq_max": irq["max"] if irq else "-",
    })
    if probe:
        # The probe site: the mask site with the smallest distance of its min to the probe length.
        p = min(mask, key=lambda s: abs(s["min"] - probe), default=None)
        row["probe_min_max"] = f"{p['min']}..{p['max']}" if p else "-"
    return row


def cmd_sweep(args):
    rows = [sweep_row(p) for p in args.logs]
    if args.json:
        print(json.dumps(rows, indent=1))
        return
    cols = []
    for r in rows:
        cols += [c for c in r if c not in cols]
    rows = [{c: r.get(c, "") for c in cols} for r in rows]
    print_rows(rows, args.md)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("table", help="site tables of one log")
    t.add_argument("log")
    t.add_argument("--elf", help="ELF of the build (default: zephyr.elf next to the log)")
    t.add_argument("--binutils", help="prefix of nm and addr2line (default: from the run manifest)")
    t.add_argument("--no-names", action="store_true")
    t.add_argument("--top", type=int, default=None, help="only the first N sites of each kind")
    t.add_argument("--md", action="store_true")
    t.add_argument("--json", action="store_true")
    t.set_defaults(fn=cmd_table)

    s = sub.add_parser("sweep", help="one row per log")
    s.add_argument("logs", nargs="+")
    s.add_argument("--md", action="store_true")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_sweep)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
