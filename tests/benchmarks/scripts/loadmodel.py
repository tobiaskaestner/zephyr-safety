#!/usr/bin/env python3
# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Model of the periodic load timers: how many expire on the same tick.

common/src/load.c gives each of LATBENCH_LOAD_TIMERS timers a period in
[LATBENCH_LOAD_TIMER_MIN_MS, LATBENCH_LOAD_TIMER_MAX_MS] and a first expiry
in [1, period] ticks, from xorshift32 with the seed
LATBENCH_LOAD_TIMER_SEED. The timers do not depend on the stimulus, so the
ticks with k expiries are the same in each run with the same seed. The
system timer ISR processes the k expiries one after the other: a tick with
many expiries is a long ISR, and the tail of the IRQ latency comes from
these ticks.

Subcommands:

    run   one timer set: ticks with k expiries, the first tick with at
          least k, the counts in each part of the run
    scan  many seeds: the counts of ticks with k expiries for each seed
    log   the timer set of a run log (LAT META): the model against the
          load_timer_expiries of the log

The model starts the timers at tick 0. The real start is some ticks after
the boot, so the model expiries of a log are a few more or less than the
log value.
"""

import argparse
import json
import math
import sys

DEFAULT_SEED = 0x6A09E667
M32 = 0xFFFFFFFF

# The first 32 bits of the fractional parts of the cube roots of the
# first 64 primes (the SHA-256 round constants). scan uses them as seeds,
# so that no seed is a choice by hand.
SHA256_K = [
    0x428A2F98, 0x71374491, 0xB5C0FBCF, 0xE9B5DBA5, 0x3956C25B, 0x59F111F1, 0x923F82A4, 0xAB1C5ED5,
    0xD807AA98, 0x12835B01, 0x243185BE, 0x550C7DC3, 0x72BE5D74, 0x80DEB1FE, 0x9BDC06A7, 0xC19BF174,
    0xE49B69C1, 0xEFBE4786, 0x0FC19DC6, 0x240CA1CC, 0x2DE92C6F, 0x4A7484AA, 0x5CB0A9DC, 0x76F988DA,
    0x983E5152, 0xA831C66D, 0xB00327C8, 0xBF597FC7, 0xC6E00BF3, 0xD5A79147, 0x06CA6351, 0x14292967,
    0x27B70A85, 0x2E1B2138, 0x4D2C6DFC, 0x53380D13, 0x650A7354, 0x766A0ABB, 0x81C2C92E, 0x92722C85,
    0xA2BFE8A1, 0xA81A664B, 0xC24B8B70, 0xC76C51A3, 0xD192E819, 0xD6990624, 0xF40E3585, 0x106AA070,
    0x19A4C116, 0x1E376C08, 0x2748774C, 0x34B0BCB5, 0x391C0CB3, 0x4ED8AA4A, 0x5B9CCA4F, 0x682E6FF3,
    0x748F82EE, 0x78A5636F, 0x84C87814, 0x8CC70208, 0x90BEFFFA, 0xA4506CEB, 0xBEF9A3F7, 0xC67178F2,
]


def xorshift32(x):
    """One step of rng_next() in load.c."""
    x ^= (x << 13) & M32
    x ^= x >> 17
    x ^= (x << 5) & M32
    return x


def ms_to_ticks_ceil(ms, ticks_per_sec):
    """k_ms_to_ticks_ceil32()."""
    return -(-ms * ticks_per_sec // 1000)


def timers(seed=DEFAULT_SEED, n=64, min_ms=10, max_ms=100, ticks_per_sec=10000):
    """(first, period) in ticks for each timer, in the order of timers_start()."""
    lo = ms_to_ticks_ceil(min_ms, ticks_per_sec)
    hi = ms_to_ticks_ceil(max_ms, ticks_per_sec)
    rng = seed
    out = []
    for _ in range(n):
        rng = xorshift32(rng)
        period = lo + rng % (hi - lo + 1)
        rng = xorshift32(rng)
        first = 1 + rng % period
        out.append((first, period))
    return out


def expiries_per_tick(tset, ticks):
    """bytearray: the number of expiries on each tick 0..ticks."""
    arr = bytearray(ticks + 1)
    for first, period in tset:
        for t in range(first, ticks + 1, period):
            arr[t] += 1
    return arr


def summary(arr, parts=2):
    """Ticks with k expiries (k >= 1), the first tick with at least k, and the counts per part."""
    kmax = max(arr)
    counts = {k: arr.count(k) for k in range(1, kmax + 1)}
    first_exact = {k: arr.find(k) for k in range(1, kmax + 1)}
    first = {}
    for k in range(1, kmax + 1):
        hits = [first_exact[j] for j in range(k, kmax + 1) if first_exact[j] >= 0]
        first[k] = min(hits)
    n = len(arr)
    bounds = [n * i // parts for i in range(parts + 1)]
    per_part = [{k: arr.count(k, bounds[i], bounds[i + 1]) for k in range(1, kmax + 1)}
                for i in range(parts)]
    return {"ticks": n - 1, "expiries": sum(k * c for k, c in counts.items()), "kmax": kmax,
            "counts": counts, "first": first, "parts": per_part}


def at_least(counts, k):
    return sum(c for j, c in counts.items() if j >= k)


def print_summary(s, ticks_per_sec, out=sys.stdout):
    print(f"ticks {s['ticks']} ({s['ticks'] / ticks_per_sec:.1f} s), expiries {s['expiries']}", file=out)
    print(f"{'k':>3} {'ticks':>9} {'>=k':>9} {'first >=k (s)':>14}  per part", file=out)
    for k in sorted(s["counts"]):
        parts = " ".join(f"{p[k]:7d}" for p in s["parts"])
        print(f"{k:3d} {s['counts'][k]:9d} {at_least(s['counts'], k):9d} "
              f"{s['first'][k] / ticks_per_sec:14.1f}  {parts}", file=out)


def ticks_for(args):
    return int(math.ceil(args.seconds * args.ticks_per_sec))


def cmd_run(args):
    tset = timers(args.seed, args.timers, args.min_ms, args.max_ms, args.ticks_per_sec)
    s = summary(expiries_per_tick(tset, ticks_for(args)), args.parts)
    if args.json:
        json.dump(s, sys.stdout, indent=1)
        print()
    else:
        print(f"seed 0x{args.seed:08x}, {args.timers} timers, {args.min_ms}..{args.max_ms} ms")
        print_summary(s, args.ticks_per_sec)


def cmd_scan(args):
    seeds = args.seeds or SHA256_K
    rows = []
    for seed in seeds:
        tset = timers(seed, args.timers, args.min_ms, args.max_ms, args.ticks_per_sec)
        s = summary(expiries_per_tick(tset, ticks_for(args)), 1)
        rows.append((seed, s))
    kmax = max(s["kmax"] for _, s in rows)
    print(f"{args.timers} timers, {args.min_ms}..{args.max_ms} ms, {args.seconds} s; ticks with >= k expiries")
    print("seed       " + " ".join(f"{'>=' + str(k):>8}" for k in range(2, kmax + 1)))
    key = lambda r: tuple(at_least(r[1]["counts"], k) for k in range(kmax, 1, -1))
    for seed, s in sorted(rows, key=key):
        print(f"0x{seed:08x} " + " ".join(f"{at_least(s['counts'], k):8d}" for k in range(2, kmax + 1)))


def parse_meta(path):
    meta = {}
    with open(path, errors="replace") as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 3 and parts[:2] == ["LAT", "META"] and "=" in parts[2]:
                key, _, value = parts[2].partition("=")
                meta[key] = value
    return meta


def log_params(meta):
    """Timer parameters and run length of a log. KeyError if the log has no periodic load timers."""
    if meta.get("load_timer_kind") != "periodic":
        raise KeyError("load_timer_kind")
    lo, _, hi = meta["load_timer_ms"].partition("..")
    tps = int(meta["ticks_per_sec"])
    seconds = int(meta["clock_elapsed_cyc"]) / int(meta["core_hz"])
    return {"seed": int(meta.get("load_timer_seed", hex(DEFAULT_SEED)), 16),
            "timers": int(meta["load_timers"]), "min_ms": int(lo), "max_ms": int(hi),
            "ticks_per_sec": tps, "seconds": seconds,
            "expiries": int(meta["load_timer_expiries"])}


def cmd_log(args):
    try:
        p = log_params(parse_meta(args.log))
    except KeyError as e:
        sys.exit(f"{args.log}: no periodic load timers or no {e} in LAT META")
    tset = timers(p["seed"], p["timers"], p["min_ms"], p["max_ms"], p["ticks_per_sec"])
    s = summary(expiries_per_tick(tset, int(p["seconds"] * p["ticks_per_sec"])), args.parts)
    print(f"seed 0x{p['seed']:08x}, {p['timers']} timers, {p['min_ms']}..{p['max_ms']} ms, "
          f"{p['seconds']:.1f} s (clock_elapsed_cyc)")
    print(f"expiries: model {s['expiries']}, log {p['expiries']}")
    print_summary(s, p["ticks_per_sec"])


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def timer_args(sp):
        sp.add_argument("--timers", type=int, default=64)
        sp.add_argument("--min-ms", type=int, default=10)
        sp.add_argument("--max-ms", type=int, default=100)
        sp.add_argument("--ticks-per-sec", type=int, default=10000)
        sp.add_argument("--seconds", type=float, default=311.0,
                        help="run length (default 311: 1M samples of wake_latency)")

    r = sub.add_parser("run", help="one timer set")
    r.add_argument("--seed", type=lambda v: int(v, 0), default=DEFAULT_SEED)
    timer_args(r)
    r.add_argument("--parts", type=int, default=2, help="split the run into N parts (default 2)")
    r.add_argument("--json", action="store_true")
    r.set_defaults(func=cmd_run)

    s = sub.add_parser("scan", help="many seeds (default: the SHA-256 round constants)")
    s.add_argument("seeds", nargs="*", type=lambda v: int(v, 0))
    timer_args(s)
    s.set_defaults(func=cmd_scan)

    lg = sub.add_parser("log", help="the timer set of a run log")
    lg.add_argument("log")
    lg.add_argument("--parts", type=int, default=2)
    lg.set_defaults(func=cmd_log)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
