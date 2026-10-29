# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The causes of the tail samples, from the witness tables (LATBENCH_TAIL).

An app with LATBENCH_TAIL prints one table per main histogram
(common/src/tail.c, see doc/benchmark-guide/reference/log-format.rst):

    LAT TAIL <name> n=.. seen=.. min_cyc=.. exc_min=.. exc_max=.. fields=seq,lat,...
    LAT TW <seq> <lat> <aux> <phase> <win> <exc> <st0> <st1> <ld> <tmr> <wake> <pc> <icsr>
    LAT END <name>

Each row is one of the largest samples, with the counters of a window
from the arm of its stimulus to the end of the sample. labels() gives the
witnesses that the counters show:

    systick    SysTick VAL did not count down by the window (the counter
               wrapped, or the driver reprogrammed it), and the system
               timer was active at the sample: the last reload was during
               the sample (ld - st1 <= lat + ADD_DELAY), or the edge came
               less than NEAR_PHASE cycles after a tick boundary, or the
               sample reached the next boundary
    systick-earlier  the same jump, but the last reload was before the
               sample: the system timer ran in the window, not during
               the sample
    timers     load timers expired in the window
    wakes      sleeper load threads woke in the window
    exception  more exception entry and exit cycles than the smallest
               window of the table (exc - exc_min >= EXC_STEP)
    nested     the ISR preempted another exception (ICSR RETTOBASE 0)
    switch     a PendSV (a thread switch) was pending at the end
    idle       the interrupted code is the idle loop (WFI)

cause() gives one name per row, the first that fits:

    systick+timers   systick, and load timers expired in the window (their
                     expiry functions run in the SysTick ISR)
    systick          systick
    nested           nested
    exception        extra exception cycles in the window, but no SysTick
                     reload during the sample. A weak witness: the window
                     starts at the arm, before the sample
    none             no witness: the cause is not in the counters (for
                     example a section with masked interrupts in the code
                     at pc)
"""

# Smallest extra exception overhead that counts: one exception entry and
# exit cost about 20 to 26 cycles on a Cortex-M4 (tail chaining less).
EXC_STEP = 6
# Tolerance of the SysTick check, in system timer cycles: the reads of
# the stimulus timer and of SysTick VAL are a few cycles apart.
ST_TOL = 64
# Largest time from the end time stamp of a sample to the reads of
# lat_tail_add() (histogram and phase adds of the app before it), in
# stimulus timer counts.
ADD_DELAY = 600
# A SysTick ISR and the thread switch after it end at most this many
# cycles after the tick boundary (review-2026-10-25: the two ramps of the
# max in the tick phase data are in the first 4000 cycles).
NEAR_PHASE = 4000

ICSR_RETTOBASE = 1 << 11
ICSR_PENDSVSET = 1 << 28

FIELDS = ["seq", "lat", "aux", "phase", "win", "exc", "st0", "st1", "ld", "tmr", "wake", "pc", "icsr"]

CAUSES = ["systick+timers", "systick", "nested", "exception", "none"]

# Functions of the idle loop: an interrupt there met the CPU in WFI.
IDLE_FUNCTIONS = {"arch_cpu_idle", "k_cpu_idle", "idle", "z_arm_cpu_idle"}


def _num(v):
    return int(v, 0) if isinstance(v, str) else v


def norm(row):
    """A row with int values (the app data has pc and icsr as "0x.." text)."""
    return {k: (_num(v) if k in FIELDS else v) for k, v in row.items()}


def parse_row(text, fields=FIELDS):
    """One LAT TW line (without the prefix) as a dict of ints."""
    return {k: int(v, 0) for k, v in zip(fields, text.split())}


def _ratio(meta):
    """System timer cycles per stimulus timer count."""
    try:
        return int(meta["sys_timer_hz"]) / int(meta["stim_timer_hz"])
    except (KeyError, ValueError, TypeError, ZeroDivisionError):
        return 1.0


def systick_jump(row, meta=None):
    """True if SysTick VAL did not count down by the window (a wrap or a reprogram)."""
    expect = row["st0"] - row["win"] * _ratio(meta or {})
    return expect < 0 or abs(expect - row["st1"]) > ST_TOL


def systick_age(row, meta=None):
    """Stimulus timer counts from the last SysTick reload to the add, or None (no jump, no ld)."""
    if not systick_jump(row, meta) or "ld" not in row or row["ld"] < row["st1"]:
        return None
    return (row["ld"] - row["st1"]) / _ratio(meta or {})


def systick_near(row, meta=None):
    """True if the system timer was active at the sample (see the module text)."""
    row = norm(row)
    if "ld" not in row:
        return True                     # an old table: the jump alone
    age = systick_age(row, meta)
    if age is not None and age <= row["lat"] + ADD_DELAY:
        return True
    try:
        period = int((meta or {})["tick_period_cyc"])
    except (KeyError, ValueError, TypeError):
        return False
    return row["phase"] <= NEAR_PHASE or row["phase"] + row["lat"] >= period


def labels(row, table, meta=None):
    """The witnesses of one row (a list, in the order of the module text)."""
    row = norm(row)
    out = []
    if systick_jump(row, meta):
        out.append("systick" if systick_near(row, meta) else "systick-earlier")
    if row.get("tmr", 0) > 0:
        out.append("timers")
    if row.get("wake", 0) > 0:
        out.append("wakes")
    if row["exc"] - table.get("exc_min", row["exc"]) >= EXC_STEP:
        out.append("exception")
    if row.get("icsr", 0) and not row["icsr"] & ICSR_RETTOBASE:
        out.append("nested")
    if row.get("icsr", 0) & ICSR_PENDSVSET:
        out.append("switch")
    if row.get("function") in IDLE_FUNCTIONS:
        out.append("idle")
    return out


def cause(row, table, meta=None):
    found = labels(row, table, meta)
    if "systick" in found:
        return "systick+timers" if "timers" in found else "systick"
    for c in ("nested", "exception"):
        if c in found:
            return c
    return "none"


def rows(table, meta=None, at_least=0):
    """The rows of a table with lat >= at_least, largest first, each with labels and cause."""
    out = []
    for r in table.get("rows", []):
        if r["lat"] < at_least:
            continue
        out.append({**r, "extra_exc": r["exc"] - table.get("exc_min", r["exc"]),
                    "labels": labels(r, table, meta), "cause": cause(r, table, meta)})
    return sorted(out, key=lambda r: -r["lat"])


def explained_share(table, meta, at_least):
    """Share of the rows with lat >= at_least that have a cause other than none."""
    sel = rows(table, meta, at_least)
    if not sel:
        return None
    return sum(r["cause"] != "none" for r in sel) / len(sel)


def label_share(table, meta, label, at_least):
    """Share of the rows with lat >= at_least that have this witness label."""
    sel = rows(table, meta, at_least)
    if not sel:
        return None
    return sum(label in r["labels"] for r in sel) / len(sel)
