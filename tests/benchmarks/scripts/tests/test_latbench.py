# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the log parser and the statistics of latbench.py and plot.py.

The fixtures in fixtures/ are the console output of the ztest app
unit/hist (one log for each scenario). That app prints a histogram of
pseudo-random samples. ref_samples() makes the same samples, so that the
tests can compare the parsed log with values that do not come from the code
under test.
"""

import argparse
import json
import math
import sys
from fractions import Fraction
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(SCRIPTS))

import latbench  # noqa: E402


def write_log(tmp_path, text, name="run.log"):
    p = tmp_path / name
    p.write_text(text)
    return p


def hist(bins=None, width=None, ovf=None, n=None, mean=0.0, vmax=0, vmin=0, invalid=None):
    """A parsed histogram, as parse_log() returns it. invalid=None makes an old log (no field)."""
    bins = dict(bins or {})
    ovf = dict(ovf or {})
    if n is None:
        n = sum(bins.values()) + sum(ovf.values())
    h = {"name": "h", "n": n, "min": vmin, "max": vmax, "mean": mean, "overflow": sum(ovf.values()),
         "bins": bins, "width": dict(width or {}), "ovf_log2": ovf}
    if invalid is not None:
        h["invalid"] = invalid
    return h


# ------------------------------------------------------------------ parse_log

LOG = """\
*** Booting Zephyr OS ***
LAT BEGIN
LAT META variant=old
LAT HIST old n=1 min=1 max=1 mean=1.00 overflow=0
LAT BIN 1 1
LAT END old
LAT DONE
noise before the second run
LAT BEGIN
LAT META board=nucleo_g474re
LAT META variant=a=b
LAT CFG TIMESLICING=0 SPEED_OPTIMIZATIONS=1
LAT ERROR stim overrun 3
LAT HIST irq n=12 min=0 max=70000 mean=1234.56 overflow=2
LAT BIN 0 3
LAT BIN 2047 4\r
LAT CBIN 2048 2 32
LAT CBIN 67552 1 32
LAT OVF 16 1
LAT OVF 31 1
LAT END irq
LAT BIN 5 99
LAT OVF 3 99
LAT PHASE irq bins=64 period=17000
LAT PB 0 2 3 9 12
LAT PB 63 1 4294967295 4294967295 4294967295
LAT END irq
LAT PB 1 1 1 1 1
LAT DONE
"""


def test_parse_log_all_line_types(tmp_path):
    run = latbench.parse_log(write_log(tmp_path, LOG))
    assert run["meta"] == {"board": "nucleo_g474re", "variant": "a=b"}, "last run only; value after the first '='"
    assert run["cfg"] == {"TIMESLICING": 0, "SPEED_OPTIMIZATIONS": 1}
    assert run["errors"] == ["stim overrun 3"]
    assert list(run["hists"]) == ["irq"]

    h = run["hists"]["irq"]
    assert (h["n"], h["min"], h["max"], h["overflow"]) == (12, 0, 70000, 2)
    assert h["mean"] == pytest.approx(1234.56)
    assert isinstance(h["mean"], float)
    assert h["bins"] == {0: 3, 2047: 4, 2048: 2, 67552: 1}
    assert h["width"] == {2048: 32, 67552: 32}, "only the coarse bins have a width"
    assert h["ovf_log2"] == {16: 1, 31: 1}, "BIN/OVF lines after END are not part of the histogram"

    ph = run["phases"]["irq"]
    assert ph["nbins"] == 64, "the PHASE header 'bins=' is stored as 'nbins'"
    assert ph["period"] == 17000
    assert ph["bins"] == {
        0: {"count": 2, "min": 3, "max": 9, "sum": 12},
        63: {"count": 1, "min": 4294967295, "max": 4294967295, "sum": 4294967295},
    }, "PB lines after END are not part of the table"


def test_parse_log_invalid_field(tmp_path):
    text = ("LAT BEGIN\nLAT HIST irq n=3 min=49 max=785 mean=294.33 overflow=0 invalid=2\n"
            "LAT BIN 49 2\nLAT BIN 785 1\nLAT END irq\n")
    h = latbench.parse_log(write_log(tmp_path, text))["hists"]["irq"]
    assert h["invalid"] == 2
    assert isinstance(h["invalid"], int)
    assert (h["n"], h["overflow"]) == (3, 0)


def test_parse_log_phase_error(tmp_path):
    text = "LAT BEGIN\nLAT ERROR phase irq period=67108864 is larger than 67108863\nLAT DONE\n"
    assert latbench.parse_log(write_log(tmp_path, text))["errors"] == [
        "phase irq period=67108864 is larger than 67108863"]


def test_parse_log_no_begin(tmp_path):
    with pytest.raises(ValueError):
        latbench.parse_log(write_log(tmp_path, "LAT HIST x n=0 min=0 max=0 mean=0.00 overflow=0\n"))


def test_parse_log_lines_before_begin_ignored(tmp_path):
    text = "LAT HIST early n=1 min=1 max=1 mean=1.00 overflow=0\nLAT BEGIN\nLAT DONE\n"
    run = latbench.parse_log(write_log(tmp_path, text))
    assert run["hists"] == {}


def test_parse_log_crlf(tmp_path):
    text = "LAT BEGIN\r\nLAT HIST a n=2 min=3 max=3 mean=3.00 overflow=0\r\nLAT BIN 3 2\r\nLAT END a\r\n"
    run = latbench.parse_log(write_log(tmp_path, text))
    assert run["hists"]["a"]["bins"] == {3: 2}


def test_parse_log_large_sum(tmp_path):
    text = "LAT BEGIN\nLAT PHASE p bins=8 period=100\nLAT PB 7 3 1 4294967295 12884901885\nLAT END p\n"
    run = latbench.parse_log(write_log(tmp_path, text))
    assert run["phases"]["p"]["bins"][7]["sum"] == 3 * (2**32 - 1)


# ------------------------------------------------------------------- quantile

def test_quantile_fine_exact_rank():
    # One sample at each value 0..99. The q quantile is the sample at rank ceil(q * n).
    h = hist(bins={v: 1 for v in range(100)})
    assert latbench.quantile(h, 0.5) == 49
    assert latbench.quantile(h, 0.9) == 89
    assert latbench.quantile(h, 0.91) == 90
    assert latbench.quantile(h, 0.905) == 90, "rank ceil(90.5) = 91"
    assert latbench.quantile(h, 0.99) == 98
    assert latbench.quantile(h, 0.9999) == 99
    assert latbench.quantile(h, 1.0) == 99


@pytest.mark.parametrize("n", [1, 7, 100, 999, 1000, 10000, 100000, 999999, 1000000])
@pytest.mark.parametrize("q", [q for _, q in latbench.QUANTILES])
def test_quantile_rank_no_float_error(n, q):
    # One sample at each value 0..n-1: the result is rank - 1, with the rank in exact arithmetic.
    rank = math.ceil(Fraction(str(q)) * n)
    h = hist(bins={v: 1 for v in range(n)} if n <= 1000 else {0: rank - 1, 1: 1, 2: n - rank})
    want = rank - 1 if n <= 1000 else 1
    assert latbench.quantile(h, q) == want


def test_quantile_counts():
    h = hist(bins={10: 50, 11: 40, 12: 9, 13: 1})
    assert latbench.quantile(h, 0.5) == 10
    assert latbench.quantile(h, 0.51) == 11
    assert latbench.quantile(h, 0.9) == 11
    assert latbench.quantile(h, 0.99) == 12
    assert latbench.quantile(h, 0.999) == 13


def test_quantile_coarse_lower_edge():
    # Fine bins 0..15, coarse bins of 4 cycles from 16. A coarse bin gives its lower edge.
    h = hist(bins={15: 5, 16: 3, 28: 2}, width={16: 4, 28: 4})
    assert latbench.quantile(h, 0.5) == 15
    assert latbench.quantile(h, 0.6) == 16
    assert latbench.quantile(h, 0.8) == 16
    assert latbench.quantile(h, 0.81) == 28
    assert latbench.quantile(h, 1.0) == 28


def test_quantile_overflow_strings():
    h = hist(bins={5: 90}, ovf={12: 9, 31: 1}, vmax=4294967290)
    assert latbench.quantile(h, 0.9) == 5
    assert latbench.quantile(h, 0.91) == ">=4096"
    assert latbench.quantile(h, 0.99) == ">=4096"
    assert latbench.quantile(h, 0.991) == ">=2147483648"


def test_quantile_overflow_after_coarse():
    # An overflow bin comes after all bins, also if 2^e is less than a coarse edge.
    h = hist(bins={2047: 1, 67552: 1}, width={67552: 32}, ovf={16: 1})
    assert latbench.quantile(h, 1.0) == ">=65536"
    assert latbench.quantile(h, 0.6) == 67552


def test_quantile_empty():
    assert latbench.quantile(hist(n=0, vmax=0), 0.5) == 0


# --------------------------------------------------------------------- stddev

def test_stddev_fine():
    assert latbench.stddev(hist(bins={2: 1, 4: 1}, mean=3.0)) == pytest.approx(1.0)
    assert latbench.stddev(hist(bins={7: 10}, mean=7.0)) == 0.0


def test_stddev_nan():
    assert math.isnan(latbench.stddev(hist(n=0)))
    assert math.isnan(latbench.stddev(hist(bins={3: 9}, ovf={12: 1}, mean=3.0))), "a sample outside the bins"
    assert math.isnan(latbench.stddev(hist(bins={3: 9}, n=10, mean=3.0)))


def test_stddev_coarse_centre():
    # A coarse bin [16, 20) counts at its centre 17.5.
    assert latbench.stddev(hist(bins={16: 2}, width={16: 4}, mean=17.5)) == pytest.approx(0.0)
    assert latbench.stddev(hist(bins={0: 1, 16: 1}, width={16: 4}, mean=8.75)) == pytest.approx(8.75)
    # Width 32: [2048, 2080) has its centre at 2063.5.
    assert latbench.stddev(hist(bins={2047: 1, 2048: 1}, width={2048: 32}, mean=2055.25)) == pytest.approx(8.25)


# -------------------------------------------------------------------- summary

def summary_rows(paths, capsys):
    latbench.summary(argparse.Namespace(logs=[str(p) for p in paths], json=True))
    return json.loads(capsys.readouterr().out)


def test_summary(tmp_path, capsys):
    text = ("LAT BEGIN\nLAT META variant=v1\n"
            "LAT HIST irq n=4 min=2 max=4 mean=3.00 overflow=0\nLAT BIN 2 1\nLAT BIN 3 2\nLAT BIN 4 1\nLAT END irq\n")
    (row,) = summary_rows([write_log(tmp_path, text)], capsys)
    assert row["variant"] == "v1"
    assert (row["n"], row["min"], row["max"], row["ovf"], row["inv"]) == (4, 2, 4, 0, 0)
    assert (row["p50"], row["p90"], row["p99.99"]) == (3, 4, 4)
    assert row["sd"] == pytest.approx(0.71)


def test_summary_mean_without_negative(tmp_path, capsys):
    # An old log (no "invalid=" field): 999 samples of 50 cycles and one
    # negative difference of -1 (2^32 - 1) in n, max, mean and overflow bin 31.
    total = 999 * 50 + (2**32 - 1)
    mean100 = total * 100 // 1000
    text = ("LAT BEGIN\n"
            f"LAT HIST irq n=1000 min=50 max=4294967295 mean={mean100 // 100}.{mean100 % 100:02d} overflow=1\n"
            "LAT BIN 50 999\nLAT OVF 31 1\nLAT END irq\n")
    (row,) = summary_rows([write_log(tmp_path, text)], capsys)
    assert row["mean"] == pytest.approx(50.0, abs=0.01)
    assert row["inv"] == 1


def test_summary_new_log(tmp_path, capsys):
    # A new log: the negative difference is only in "invalid=".
    text = ("LAT BEGIN\nLAT HIST irq n=999 min=50 max=50 mean=50.00 overflow=0 invalid=1\n"
            "LAT BIN 50 999\nLAT END irq\n")
    (row,) = summary_rows([write_log(tmp_path, text)], capsys)
    assert (row["n"], row["max"], row["mean"], row["inv"]) == (999, 50, 50.0, 1)
    assert row["sd"] == 0.0


def test_mean():
    # A new log keeps the printed mean, also with invalid samples.
    assert latbench.mean(hist(bins={50: 9}, mean=50.0, invalid=3)) == 50.0
    # An old log without negative differences keeps the printed mean.
    assert latbench.mean(hist(bins={3: 1}, ovf={12: 1}, mean=2049.5)) == 2049.5
    # An old log: the mean from the bins, a coarse bin at its centre.
    h = hist(bins={2047: 1, 2048: 1}, width={2048: 32}, ovf={31: 2}, mean=1e9)
    assert latbench.mean(h) == pytest.approx(2055.25)
    # An old log with a sample outside the bins (overflow bin 12): the printed mean stays.
    assert latbench.mean(hist(bins={3: 1}, ovf={12: 1, 31: 1}, mean=1431656532.0)) == 1431656532.0
    # Only negative differences: the printed mean stays.
    assert latbench.mean(hist(ovf={31: 2}, mean=4294967295.0)) == 4294967295.0


# ----------------------------------------------------------------------- plot

plot = pytest.importorskip("plot")


def test_values_and_invalid():
    h = hist(bins={3: 2, 5: 1}, ovf={12: 4, 30: 1, 31: 7})
    assert plot.values(h) == [(3, 2), (5, 1), (4096, 4), (1 << 30, 1)]
    assert plot.invalid(h) == 7, "an old log: overflow bin 31"
    assert plot.invalid(hist(bins={3: 1})) == 0
    assert plot.invalid(hist(bins={3: 1}, invalid=4)) == 4, "a new log: the invalid= field"
    assert plot.invalid(hist(bins={3: 1}, ovf={31: 1}, invalid=4)) == 5


def test_max_text():
    assert plot.max_text(hist(bins={3: 1}, vmax=3)) == "max 3"
    assert plot.max_text(hist(bins={3: 1, 9: 1}, ovf={31: 2}, vmax=4294967295)) == "max 9, 2 negative"
    # A new log: max is the largest valid sample, also if it is in an overflow bin.
    assert plot.max_text(hist(bins={3: 1}, ovf={14: 1}, vmax=20000, invalid=2)) == "max 20000, 2 negative"


def test_values_sorted_with_coarse_bins():
    # 2048 + 2048 x 32 (experiments/*-1m.yaml): overflow bin 16 is at 65536,
    # below the last coarse edges (up to 67552).
    h = hist(bins={100: 5, 66016: 1, 67552: 1}, width={66016: 32, 67552: 32}, ovf={16: 1})
    assert plot.values(h) == [(100, 5), (65536, 1), (66016, 1), (67552, 1)]


def test_max_text_all_negative():
    assert plot.max_text(hist(ovf={31: 3}, vmax=4294967295)) == "max -, 3 negative"
    assert plot.max_text(hist(n=0, invalid=3)) == "max -, 3 negative"


# ---------------------------------------------- round trip with the ztest app

def lcg(s):
    return (s * 1664525 + 1013904223) & 0xFFFFFFFF


def ref_samples(meta):
    """The samples of fixture_sample() in unit/hist/src/main.c: list of (value, phase)."""
    bins, cbins = int(meta["hist_bins"]), int(meta["coarse_bins"])
    cend = bins + (cbins << int(meta["coarse_shift"]))
    period = int(meta["period"])
    span0 = min(bins, 256)
    lo1 = bins - 8 if bins > 8 else 0
    s = int(meta["seed"])
    out = []
    for _ in range(int(meta["samples"])):
        s = lcg(s)
        r = s >> 24
        s = lcg(s)
        y = s >> 8
        if r < 179:
            v = bins - span0 + y % span0
        elif r < 230:
            v = lo1 + y % (cend - lo1 + 16)
        elif r < 251:
            v = cend + y % (4 * cend)
        else:
            v = (-(1 + y % 1000)) & 0xFFFFFFFF
        s = lcg(s)
        out.append((v, s % period))
    return out


def ref_bin(meta, v):
    """('bin', lower edge) or ('ovf', e) for a value, from the documented bin layout."""
    bins, cbins, shift = int(meta["hist_bins"]), int(meta["coarse_bins"]), int(meta["coarse_shift"])
    if v < bins:
        return "bin", v
    if v < bins + (cbins << shift):
        return "bin", bins + ((v - bins) >> shift << shift)
    return "ovf", v.bit_length() - 1


FIXTURE_LOGS = sorted(FIXTURES.glob("hist_*.log"))


def test_fixtures_present():
    assert {p.stem for p in FIXTURE_LOGS} >= {"hist_fine", "hist_coarse"}


@pytest.fixture(params=FIXTURE_LOGS, ids=lambda p: p.stem)
def fixture_run(request):
    run = latbench.parse_log(request.param)
    return run, ref_samples(run["meta"])


def test_roundtrip_hist(fixture_run):
    run, samples = fixture_run
    meta = run["meta"]
    vals = [v for v, _ in samples if v < 2**31]
    h = run["hists"]["fix"]
    n = len(vals)
    assert h["invalid"] == len(samples) - n
    assert h["invalid"] > 0

    assert run["cfg"] == {"LATBENCH_FIXTURE": 1}
    assert h["n"] == n
    assert h["min"] == min(vals)
    assert h["max"] == max(vals)
    mean100 = sum(vals) * 100 // n
    assert h["mean"] == float(f"{mean100 // 100}.{mean100 % 100:02d}"), "mean cut to 1/100"

    want_bins, want_width, want_ovf = {}, {}, {}
    w = 1 << int(meta["coarse_shift"])
    for v in vals:
        kind, key = ref_bin(meta, v)
        if kind == "bin":
            want_bins[key] = want_bins.get(key, 0) + 1
            if key >= int(meta["hist_bins"]):
                want_width[key] = w
        else:
            want_ovf[key] = want_ovf.get(key, 0) + 1
    assert h["bins"] == want_bins
    assert h["width"] == want_width
    assert h["ovf_log2"] == want_ovf
    assert h["overflow"] == sum(want_ovf.values())
    # The generator reaches each region.
    assert any(k >= int(meta["hist_bins"]) for k in want_width) == (int(meta["coarse_bins"]) > 0)
    assert 31 not in h["ovf_log2"]
    assert latbench.mean(h) == h["mean"]


def test_roundtrip_quantiles(fixture_run):
    run, samples = fixture_run
    meta = run["meta"]
    h = run["hists"]["fix"]
    ordered = sorted(v for v, _ in samples if v < 2**31)
    for _, q in latbench.QUANTILES + [("p10", 0.1), ("p70", 0.7), ("p75", 0.75), ("p80", 0.8)]:
        x = ordered[math.ceil(Fraction(str(q)) * len(ordered)) - 1]
        kind, key = ref_bin(meta, x)
        want = key if kind == "bin" else f">={1 << key}"
        assert latbench.quantile(h, q) == want, f"q={q}"


def test_roundtrip_stddev(fixture_run):
    run, _ = fixture_run
    # The fixture has overflow samples, so there is no stddev.
    assert math.isnan(latbench.stddev(run["hists"]["fix"]))


def test_roundtrip_phase(fixture_run):
    run, samples = fixture_run
    meta = run["meta"]
    ph = run["phases"]["fixph"]
    nbins, period = int(meta["phase_bins"]), int(meta["period"])
    assert (ph["nbins"], ph["period"]) == (nbins, period)
    want = {}
    for v, phase in samples:
        if v >= 2**31:
            continue
        b = phase * nbins // period
        e = want.setdefault(b, {"count": 0, "min": v, "max": v, "sum": 0})
        e["count"] += 1
        e["min"] = min(e["min"], v)
        e["max"] = max(e["max"], v)
        e["sum"] += v
    assert ph["bins"] == want


def test_roundtrip_plot(fixture_run):
    run, samples = fixture_run
    h = run["hists"]["fix"]
    negative = sum(1 for v, _ in samples if v >= 2**31)
    assert plot.invalid(h) == negative
    assert sum(c for _, c in plot.values(h)) == len(samples) - negative == h["n"]
    pairs = plot.values(h)
    assert pairs == sorted(pairs)
    assert plot.max_text(h) == f"max {h['max']}, {negative} negative"


def test_roundtrip_summary(fixture_run, capsys):
    run, _ = fixture_run
    (row,) = summary_rows([run["source"]], capsys)
    h = run["hists"]["fix"]
    assert row["n"] + row["inv"] == int(run["meta"]["samples"])
    assert row["inv"] == h["invalid"]
    assert row["ovf"] == h["overflow"]
