# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for scripts/loadmodel.py (the model of the periodic load timers)."""

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))

import loadmodel  # noqa: E402


def test_xorshift32_reference_values():
    # Marsaglia's xorshift32 (13, 17, 5) from the state 1 (the first value by hand).
    assert loadmodel.xorshift32(1) == 270369
    assert loadmodel.xorshift32(270369) == 67634689


def test_ms_to_ticks_ceil():
    assert loadmodel.ms_to_ticks_ceil(10, 10000) == 100
    assert loadmodel.ms_to_ticks_ceil(1, 300) == 1  # 0.3 ticks rounds up
    assert loadmodel.ms_to_ticks_ceil(10, 300) == 3


def test_timers_follow_rng_range():
    # The same calculation as timers_start(): period, then first expiry.
    seed = 0x6A09E667
    r1 = loadmodel.xorshift32(seed)
    r2 = loadmodel.xorshift32(r1)
    period = 100 + r1 % 901
    first = 1 + r2 % period
    tset = loadmodel.timers(seed, 64)
    assert len(tset) == 64
    assert tset[0] == (first, period)
    assert all(100 <= p <= 1000 and 1 <= f <= p for f, p in tset)


def test_expiries_per_tick_small():
    arr = loadmodel.expiries_per_tick([(1, 2), (1, 3), (6, 10)], 7)
    # ticks:          0  1  2  3  4  5  6  7
    assert list(arr) == [0, 2, 0, 1, 1, 1, 1, 2]


def test_summary_counts_and_first():
    arr = loadmodel.expiries_per_tick([(1, 2), (1, 3), (6, 10)], 7)
    s = loadmodel.summary(arr, parts=2)
    assert s["counts"] == {1: 4, 2: 2}
    assert s["expiries"] == 8
    assert s["first"] == {1: 1, 2: 1}
    assert s["kmax"] == 2
    # parts: ticks 0..3 and 4..7
    assert s["parts"] == [{1: 1, 2: 1}, {1: 3, 2: 1}]
    assert loadmodel.at_least(s["counts"], 1) == 6


def test_expiries_closed_form():
    tset = loadmodel.timers(0x90BEFFFA, 64)
    ticks = 200000
    s = loadmodel.summary(loadmodel.expiries_per_tick(tset, ticks))
    assert s["expiries"] == sum((ticks - f) // p + 1 for f, p in tset)


def test_log_params(tmp_path):
    log = tmp_path / "rep1.log"
    log.write_text(
        "LAT META core_hz=170000000\n"
        "LAT META ticks_per_sec=10000\n"
        "LAT META clock_elapsed_cyc=1700000000\n"
        "LAT META load_timers=64\n"
        "LAT META load_timer_kind=periodic\n"
        "LAT META load_timer_ms=10..100\n"
        "LAT META load_timer_seed=0x90befffa\n"
        "LAT META load_timer_expiries=1234\n"
    )
    p = loadmodel.log_params(loadmodel.parse_meta(log))
    assert p == {"seed": 0x90BEFFFA, "timers": 64, "min_ms": 10, "max_ms": 100,
                 "ticks_per_sec": 10000, "seconds": 10.0, "expiries": 1234}


def test_log_params_old_log_uses_default_seed(tmp_path):
    log = tmp_path / "rep1.log"
    log.write_text(
        "LAT META core_hz=170000000\nLAT META ticks_per_sec=10000\n"
        "LAT META clock_elapsed_cyc=170000000\nLAT META load_timers=8\n"
        "LAT META load_timer_kind=periodic\nLAT META load_timer_ms=10..100\n"
        "LAT META load_timer_expiries=10\n"
    )
    assert loadmodel.log_params(loadmodel.parse_meta(log))["seed"] == loadmodel.DEFAULT_SEED


def test_log_params_far_timers(tmp_path):
    log = tmp_path / "rep1.log"
    log.write_text("LAT META load_timers=64\nLAT META load_timer_kind=far\n")
    with pytest.raises(KeyError):
        loadmodel.log_params(loadmodel.parse_meta(log))
