# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the tail witnesses (LATBENCH_TAIL): the parser, the
causes (tails.py), the extractor, the stats of the checks and data.py.

The rows of LOG are real rows of a manual run of irq_latency (direct path,
idle CPU, 100000 samples, 2026-10-29), shortened to four rows.
"""

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
REPO = SCRIPTS.parents[2]
sys.path.insert(0, str(REPO / "tests" / "benchmarks" / "common" / "scripts"))

from probatrix.benchmarks import latbench  # noqa: E402
from probatrix.benchmarks import tails  # noqa: E402
from probatrix.benchmarks.studylib import stats
from probatrix.core import checks  # noqa: E402
from probatrix.benchmarks.studylib.stats import NoValue  # noqa: E402

META = {"sys_timer_hz": "170000000", "stim_timer_hz": "170000000", "tick_period_cyc": "17000"}

LOG = """\
LAT BEGIN
LAT META app=irq_latency
LAT META tick_period_cyc=17000
LAT HIST irq n=3 min=51 max=1526 mean=51.00 overflow=0 invalid=0
LAT BIN 51 2
LAT CBIN 1504 1 32
LAT END irq
LAT TAIL irq n=4 seen=100000 min_cyc=0 exc_min=18 exc_max=96 fields=seq,lat,aux,phase,win,exc,st0,st1,ld,tmr,wake,pc,icsr
LAT TW 51103 1526 0 263 86701 44 84880 3398209 3399999 0 0 0x0800404e 0x1000e816
LAT TW 2659 63 0 8534 76477 96 33847 16738084 16777215 0 0 0x0800404e 0x00000816
LAT TW 7 60 0 9000 50000 18 900000 850000 999999 0 0 0x08001000 0x00000816
LAT TW 8 70 0 9100 50000 18 900000 850000 999999 0 0 0x00000000 0x0000e016
LAT END irq
LAT DONE
"""


def write_log(tmp_path, text=LOG):
    p = tmp_path / "rep1.log"
    p.write_text(text)
    return p


def table(tmp_path):
    return latbench.parse_log(write_log(tmp_path))["tails"]["irq"]


# ------------------------------------------------------------------ parser
def test_parse_log_reads_the_witness_table(tmp_path):
    run = latbench.parse_log(write_log(tmp_path))
    t = run["tails"]["irq"]
    assert (t["n"], t["seen"], t["exc_min"], t["exc_max"]) == (4, 100000, 18, 96)
    assert t["fields"][:3] == ["seq", "lat", "aux"] and len(t["rows"]) == 4
    assert t["rows"][0]["pc"] == 0x0800404e and t["rows"][0]["icsr"] == 0x1000e816 and t["rows"][0]["ld"] == 3399999
    # the histogram before the table is not changed by it
    assert run["hists"]["irq"]["bins"] == {51: 2, 1504: 1}


def test_a_log_without_witnesses_has_no_tables(tmp_path):
    assert latbench.parse_log(write_log(tmp_path, "LAT BEGIN\nLAT DONE\n"))["tails"] == {}


# ------------------------------------------------------------------ causes
def test_systick_during_the_sample_is_the_cause(tmp_path):
    t = table(tmp_path)
    r = t["rows"][0]
    assert tails.systick_jump(r, META)
    assert tails.systick_age(r, META) == 3399999 - 3398209          # 1790 <= 1526 + ADD_DELAY
    assert tails.labels(r, t, META) == ["systick", "exception", "switch"]
    assert tails.cause(r, t, META) == "systick"


def test_a_systick_reload_long_before_the_sample_is_no_cause(tmp_path):
    t = table(tmp_path)
    r = t["rows"][1]
    # the reload was 39131 counts before the end, the edge at phase 8534 (not near a boundary)
    assert tails.labels(r, t, META) == ["systick-earlier", "exception"]
    assert tails.cause(r, t, META) == "exception"


def test_near_a_tick_boundary_counts_without_the_age(tmp_path):
    t = table(tmp_path)
    r = dict(t["rows"][1], phase=500)
    assert "systick" in tails.labels(r, t, META)
    r = dict(t["rows"][1], phase=16990)                            # the sample reaches the next boundary
    assert "systick" in tails.labels(r, t, META)


def test_no_witness_and_nested(tmp_path):
    t = table(tmp_path)
    assert tails.labels(t["rows"][2], t, META) == [] and tails.cause(t["rows"][2], t, META) == "none"
    # RETTOBASE 0: the ISR preempted another exception
    assert tails.cause(t["rows"][3], t, META) == "nested"


def test_timers_in_the_window_name_the_systick_cause(tmp_path):
    t = table(tmp_path)
    assert tails.cause(dict(t["rows"][0], tmr=2), t, META) == "systick+timers"
    # timers without a SysTick reload at the sample are only a label
    assert tails.cause(dict(t["rows"][2], tmr=1), t, META) == "none"


def test_rows_and_shares(tmp_path):
    t = table(tmp_path)
    rows = tails.rows(t, META)
    assert [r["lat"] for r in rows] == [1526, 70, 63, 60] and rows[0]["extra_exc"] == 26
    assert tails.explained_share(t, META, 0) == 0.75
    assert tails.explained_share(t, META, 100) == 1.0
    assert tails.explained_share(t, META, 5000) is None
    assert tails.label_share(t, META, "systick", 0) == 0.25


def test_rows_of_the_app_data_have_hex_text(tmp_path):
    t = table(tmp_path)
    row = dict(t["rows"][0], pc="0x0800404e", icsr="0x1000e816")
    assert tails.labels(row, t, META) == ["systick", "exception", "switch"]
    assert tails.labels(dict(row, function="arch_cpu_idle"), t, META)[-1] == "idle"


def test_the_ratio_of_the_clocks_scales_the_window(tmp_path):
    t = table(tmp_path)
    r = dict(t["rows"][2], st0=900000, st1=875000, win=50000)      # sys clock at half the stimulus clock
    assert tails.systick_jump(r, META)
    assert not tails.systick_jump(r, {**META, "sys_timer_hz": "85000000"})


# ------------------------------------------------------------------ extractor
def test_extractor_writes_hex_and_no_function_without_binutils(tmp_path):
    import latextract
    run = latbench.parse_log(write_log(tmp_path))
    out = latextract.tails_out(run, tmp_path / "rep1.log", None)
    assert out["irq"]["symbols"] is False and out["irq"]["seen"] == 100000
    row = out["irq"]["rows"][0]
    assert row["pc"] == "0x0800404e" and row["icsr"] == "0x1000e816" and row["function"] is None
    assert out["irq"]["rows"][3]["function"] is None                  # pc 0: no function
    assert latextract.tails_out({"tails": {}}, tmp_path / "rep1.log", None) == {}


# ------------------------------------------------------------------ stats and checks
def rep_with_table(tmp_path):
    import latextract
    run = latbench.parse_log(write_log(tmp_path))
    return {"meta": META, "hists": {}, "phases": {}, "m4": None,
            "tails": latextract.tails_out(run, tmp_path / "rep1.log", None)}


def test_stats_of_the_tail_metric(tmp_path):
    r = rep_with_table(tmp_path)
    assert stats.value(r, "tail.irq", "n") == 4
    assert stats.value(r, "tail.irq", "seen") == 100000
    assert stats.value(r, "tail.irq", "rows_ge(64)") == 2
    assert stats.value(r, "tail.irq", "explained_share(100)") == 1.0
    assert stats.value(r, "tail.irq", "cause_share(systick, 0)") == 0.25
    assert stats.value(r, "tail.irq", "label_share(exception,0)") == 0.5
    with pytest.raises(NoValue):
        stats.value(r, "tail.irq", "explained_share(99999)")
    with pytest.raises(NoValue):
        stats.value(r, "tail.wake", "n")
    with pytest.raises(NoValue):
        stats.value(r, "tail.irq", "p50")
    assert stats.known("tail.irq", "explained_share(100)") and stats.known("tail.irq", "cause_share(systick+timers, 9)")
    assert not stats.known("tail.irq", "p50")
    assert stats.value_width(r, "tail.irq", "n") == 1


def test_a_check_reads_the_tail_metric(tmp_path):
    r = rep_with_table(tmp_path)
    o = [checks.Obs("e/1", "ws-up", "a", {}, r)]

    class S:
        def observations(self, exp, series=None):
            return o

    c = {"experiment": "e", "metric": "tail.irq", "stat": "explained_share(100)", "expect": {"range": [0.9, 1]}}
    assert not checks.problems(c)
    assert checks.evaluate(c, S())["verdict"] == "confirmed"


# ------------------------------------------------------------------ data.py
def test_data_tables_of_the_witnesses(tmp_path):
    pytest.importorskip("pandas")
    from probatrix.benchmarks import data

    class Fake:
        def points(self, experiment):
            return [("e/1", "ws-up", "p1", rep_with_table(tmp_path))]

    df = data.Instance.tails(Fake(), "e")
    assert list(df.columns) == data.TAIL_COLUMNS
    assert list(df.lat) == [1526, 70, 63, 60] and list(df.cause) == ["systick", "nested", "exception", "none"]
    assert df.systick_age[0] == 1790 and df.labels[0] == "systick exception switch"
    assert len(data.Instance.tails(Fake(), "e", at_least=100)) == 1
    assert data.Instance.tails(Fake(), "e", metric="other").empty

    class Fake2(Fake):
        tails = data.Instance.tails

    counts = data.Instance.tail_causes(Fake2(), "e")
    assert list(counts.columns) == ["tree", "point", "metric", "systick", "nested", "exception", "none"]
    assert counts.iloc[0]["systick"] == 1


def test_notebook_figure_of_the_witnesses(tmp_path):
    pytest.importorskip("pandas")
    pytest.importorskip("plotly")
    from probatrix.benchmarks import data
    from probatrix.benchmarks import nbfig

    class Fake:
        def points(self, experiment):
            return [("e/1", "ws-up", "p1", rep_with_table(tmp_path))]

    fig = nbfig.tails(data.Instance.tails(Fake(), "e"), "t")
    assert [t.name for t in fig.data] == ["systick", "nested", "exception", "none"]
    assert list(fig.data[0].y) == [1526] and list(fig.data[0].x) == [263]


# ------------------------------------------------------------------ prestamp.py
DIS_A = """
08000cac <resp_isr>:
 8000cac:\t4668      \tmov\tr0, sp
 8000cae:\tf020 0107 \tbic.w\tr1, r0, #7
 8000cb2:\tb5f1      \tpush\t{r0, r4, r5, r6, r7, lr}
 8000cb4:\t4a42      \tldr\tr2, [pc, #264]\t@ (8000dc0 <resp_isr+0x114>)
 8000cb6:\tf04f 4380 \tmov.w\tr3, #1073741824\t@ 0x40000000
 8000cba:\t6a58      \tldr\tr0, [r3, #36]\t@ 0x24
 8000cbc:\t6151      \tstr\tr1, [r2, #20]
"""


def test_prestamp_masks_registers_and_literal_offsets():
    from probatrix.benchmarks import prestamp
    a = prestamp.parse(DIS_A)
    assert a[0] == (2, "mov", "r0, sp") and a[1][0] == 4
    b = prestamp.parse(DIS_A.replace("ldr\tr2, [pc, #264]", "ldr\tr6, [pc, #276]").replace("r0, [r3, #36]",
                                                                                          "r4, [r3, #36]"))
    same, na, _ = prestamp.compare(a, b)
    assert same and len(na) == 6                     # up to and with the counter load
    c = prestamp.parse(DIS_A.replace("b5f1      \tpush\t{r0, r4, r5, r6, r7, lr}",
                                     "e92d 41f1 \tstmdb\tsp!, {r0, r4, r5, r6, r7, r8, lr}"))
    assert not prestamp.compare(a, c)[0]             # a longer push before the stamp
    with pytest.raises(ValueError):
        prestamp.compare(a[:2], b)


def test_two_tables_in_one_log(tmp_path):
    # wake_latency with LATBENCH_SWTRIG prints irq2thr and irq2thr_sw
    two = LOG.replace("LAT DONE\n", "LAT TAIL irq2thr_sw n=1 seen=7 min_cyc=0 exc_min=75 exc_max=80 "
                      "fields=seq,lat,aux,phase,win,exc,st0,st1,ld,tmr,wake,pc,icsr\n"
                      "LAT TW 3 2132 78 100 9000 80 5000 4000 16999 0 0 0x00000000 0x00000000\n"
                      "LAT END irq2thr_sw\nLAT DONE\n")
    run = latbench.parse_log(write_log(tmp_path, two))
    assert sorted(run["tails"]) == ["irq", "irq2thr_sw"]
    assert len(run["tails"]["irq"]["rows"]) == 4 and run["tails"]["irq2thr_sw"]["rows"][0]["aux"] == 78


def test_a_reprogram_without_an_interrupt(tmp_path):
    # a slow-mode wake: the slice reset reprograms SysTick during the sample, no extra exception
    t = table(tmp_path)
    r = dict(t["rows"][0], exc=18)
    assert tails.labels(r, t, META) == ["systick-reprogram", "switch"]
    assert tails.cause(r, t, META) == "reprogram"
    assert tails.cause(dict(r, nested=1, icsr=0x0000e016), t, META) == "nested"
