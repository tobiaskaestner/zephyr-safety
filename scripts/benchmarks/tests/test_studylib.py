# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Unit tests of studylib: seals, values, check forms, central results and a build (no board)."""

import json
import sys
from pathlib import Path

import pytest
import yaml

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))

from studylib import build, central, checks, instance, jsonout, layout, seal, stats  # noqa: E402
from studylib.design import Design  # noqa: E402
from studylib.stats import NoValue  # noqa: E402


# ------------------------------------------------------------------ helpers
def hist(bins, coarse=(), ovf=(), n=None, mx=None):
    n = n if n is not None else sum(c for _, c in bins) + sum(c for _, c, _ in coarse) + sum(c for _, c in ovf)
    vals = [v for v, _ in bins] + [v for v, _, _ in coarse]
    return {"n": n, "min": min(vals), "max": mx if mx is not None else max(vals), "mean": 0.0, "overflow": 0,
            "invalid": 0, "bins": [list(b) for b in bins], "coarse": [list(c) for c in coarse],
            "ovf_log2": [list(o) for o in ovf]}


def rep(hists=None, meta=None, m4=None):
    return {"meta": meta or {}, "hists": hists or {}, "phases": {}, "m4": m4}


def obs(point, value, tree="ws-up", run="e/20260101T000000Z", axes=None, metric="irq"):
    return checks.Obs(run, tree, point, axes or {}, rep({metric: hist([(value, 10)])}))


class Src:
    """A check source over a fixed list of points."""

    def __init__(self, points, runs=None):
        self.points, self.runs = points, runs or {}

    def observations(self, exp, series=None):
        if series is not None:
            return [o for o in self.points if o.series == series]
        return list(self.points)

    def run_obs(self, ref):
        return self.runs[ref]


# ------------------------------------------------------------------ seal and layout
def test_seal_write_verify_and_tamper(tmp_path):
    run = tmp_path / "ex-a" / "20260101T000000Z"
    (run / "t" / "p").mkdir(parents=True)
    (run / "manifest.json").write_text("{}")
    (run / "t" / "p" / "rep1.log").write_text("LAT BEGIN\n")
    d = seal.write(run)
    assert d.startswith("sha256:") and seal.verify(run) == d
    assert seal.write(run) == d  # the same seal again
    (run / "t" / "p" / "rep1.log").write_text("changed\n")
    with pytest.raises(seal.SealError):
        seal.verify(run)
    with pytest.raises(seal.SealError):
        seal.write(run)


def test_layout_names_and_folders(tmp_path):
    assert str(layout.study_folder("load-scaling@x/t2t")) == "st-load-scaling@x/st-t2t"
    assert str(layout.run_folder("e/20260101T000000Z")) == "ex-e/20260101T000000Z"
    assert layout.strip_board("a@b/c") == "a/c"
    root = tmp_path / "top"
    (root / "st-a@b" / "st-c").mkdir(parents=True)
    for f in (root, root / "st-a@b", root / "st-a@b" / "st-c"):
        (f / "instance.json").write_text("{}")
    assert layout.instance_path_of(root / "st-a@b" / "st-c", root) == "a@b/c"
    assert layout.find_root(root / "st-a@b" / "st-c") == root.resolve()
    assert layout.run_id_of(root / "ex-e" / "20260101T000000Z") == "e/20260101T000000Z"


def test_jsonout_is_deterministic(tmp_path):
    obj = {"b": [1, 2], "a": {"rows": [[1, "x"], [2, "y"]]}, "c": [{"d": 1}]}
    s1 = jsonout.write(tmp_path / "x.json", obj)
    s2 = jsonout.write(tmp_path / "y.json", json.loads((tmp_path / "x.json").read_text()))
    assert s1 == s2
    assert json.loads((tmp_path / "x.json").read_text()) == obj


# ------------------------------------------------------------------ values
def test_quantile_count_and_coarse_edges():
    h = hist([(10, 90), (20, 9)], coarse=[(2048, 1, 32)])
    assert stats.hist_value(h, "p50") == 10
    assert stats.hist_value(h, "p99") == 20
    assert stats.hist_value(h, "p99.9") == 2048
    assert stats.hist_value(h, "count_ge(20)") == 10
    assert stats.hist_value(h, "count_ge(2048)") == 1
    with pytest.raises(NoValue):
        stats.hist_value(h, "count_ge(2050)")  # inside a coarse bin


def test_quantile_in_overflow_is_no_value():
    h = hist([(10, 50)], ovf=[(14, 50)])
    with pytest.raises(NoValue):
        stats.hist_value(h, "p99")


def test_mode_share():
    h = hist([(41, 9900), (50, 5), (61, 60), (62, 35)])
    assert stats.modes(h) == [(41, 41, 9900), (61, 62, 95)]
    assert stats.hist_value(h, "mode_share(2)") == pytest.approx(0.0095)
    assert stats.hist_value(h, "mode_share(3)") == 0


def test_m4_sites_by_kind_ctx_and_function():
    sites = [
        {"name": "m4.mask.t.1", "kind": "mask", "ctx": "thread", "n": 3, "min": 30, "max": 500,
         "function": "z_impl_k_sleep_ticks", "via": "z_sched_spinlock_lock<k_spin_lock"},
        {"name": "m4.mask.e15.2", "kind": "mask", "ctx": "SysTick", "n": 2, "min": 40, "max": 900,
         "function": "z_timer_expiration_handler", "via": ""},
        {"name": "m4.isr.e15.3", "kind": "isr", "ctx": "SysTick", "n": 5, "min": 100, "max": 3000,
         "function": "sys_clock_isr", "via": ""},
    ]
    r = rep(meta={"m4_floor_cyc": 30, "m4_isr_floor_cyc": 20, "m4_masked_cyc": 10, "m4_window_cyc": 100},
            m4={"table": {"used": 3, "dropped": 0}, "symbols": True, "sites": sites})
    assert stats.value(r, "m4.mask", "max(max_net)") == 870
    assert stats.value(r, "m4.mask.t", "max(max)") == 500
    assert stats.value(r, "m4.mask[k_spin_lock]", "n") == 3  # only the first site has it in its chain
    assert stats.value(r, "m4.mask.e15[z_add_timeout]", "max(max_net)") == 0
    assert stats.value(r, "m4.isr.e15", "max(max)") == 3000
    assert stats.value(r, "m4.mask", "top_place") == "z_timer_expiration_handler"
    assert stats.value(r, "meta.m4_masked_share", "value") == pytest.approx(0.1)
    assert stats.value(r, "meta.dropped", "value") == 0


def test_point_values():
    r = rep(meta={"clock_drift_cyc": 800, "samples": 100, "clock_elapsed_cyc": 1000000})
    assert stats.value(r, None, "drift_per_wake") == 8
    assert stats.value(r, None, "drift_ppm") == pytest.approx(800)


def test_known_forms():
    assert stats.known("irq", "p99.99") and stats.known("irq", "max(max)") and stats.known("irq", ["mean", "p99"])
    assert stats.known("m4.mask.e22[z_add_timeout]", "max(max_net)") and stats.known(None, "drift_ppm")
    assert not stats.known("irq", "p99x") and not stats.known("meta.x", "p50")
    assert checks.problems({"metric": "irq", "stat": "p50", "expect": {"rangee": [0, 1]}})


def test_all_design_checks_use_known_forms():
    """Each check of each design: the tools know its metric, stat and expect forms."""
    d = Design()
    bad = []
    for path, st in d.studies.items():
        for h in st.hypotheses:
            for c in h["checks"]:
                bad += [f"{path} {h['id']}{c['id']}: {p}" for p in checks.problems(c)]
    for name, e in d.experiments.items():
        for a in e.acceptance:
            bad += [f"{name} {a['id']}: {p}" for p in checks.problems(a)]
    assert not bad, "\n".join(bad)


# ------------------------------------------------------------------ check forms
def ev(check, points, runs=None):
    return checks.evaluate({"experiment": "e", "metric": "irq", **check}, Src(points, runs))


def test_range_equals_and_select():
    pts = [obs("a", 10), obs("b", 20)]
    assert ev({"stat": "p50", "expect": {"range": [5, 25]}}, pts)["verdict"] == "confirmed"
    assert ev({"stat": "p50", "expect": {"range": [5, 15]}}, pts)["verdict"] == "wrong"
    assert ev({"select": {"point": "a"}, "stat": "p50", "expect": {"range": [5, 15]}}, pts)["verdict"] == "confirmed"
    assert ev({"stat": "p50", "expect": {"range": [None, 20]}}, pts)["verdict"] == "confirmed"
    assert ev({"stat": "max(p50)", "expect": {"range": [20, 20]}}, pts)["verdict"] == "confirmed"


def test_spread_forms():
    pts = [obs("a", 100), obs("b", 103)]
    assert ev({"stat": "p50", "expect": {"spread_le": 0.03}}, pts)["verdict"] == "confirmed"
    assert ev({"stat": "p50", "expect": {"spread_le": 0.02}}, pts)["verdict"] == "wrong"
    assert ev({"stat": "p50", "expect": {"spread_abs_le": 3}}, pts)["verdict"] == "confirmed"


def test_order_by_points_and_by_axis():
    pts = [obs("t0-a", 10, axes={"t": "t0", "x": "a"}), obs("t16-a", 20, axes={"t": "t16", "x": "a"}),
           obs("t0-b", 30, axes={"t": "t0", "x": "b"}), obs("t16-b", 25, axes={"t": "t16", "x": "b"})]
    assert ev({"stat": "p50", "expect": {"order": ["t0-a", "t16-a"]}}, pts)["verdict"] == "confirmed"
    r = ev({"stat": "p50", "expect": {"order": {"t": ["t0", "t16"]}}}, pts)
    assert r["verdict"] == "wrong" and "x=b" in r["measured"]
    assert ev({"select": {"x": "a"}, "stat": "p50", "expect": {"order": {"t": ["t0", "t16"]}}}, pts)["verdict"] == "confirmed"


def test_diff_ratio_and_change():
    pts = [obs("base", 100, axes={"v": "base", "load": "none"}), obs("opt", 80, axes={"v": "opt", "load": "none"}),
           obs("base-l", 200, axes={"v": "base", "load": "l"}), obs("opt-l", 150, axes={"v": "opt", "load": "l"})]
    sel = {"select": {"point": "opt"}, "stat": "p50"}
    assert ev({**sel, "expect": {"diff_to": {"point": "base", "range": [-25, -15]}}}, pts)["verdict"] == "confirmed"
    # spread_abs_le in diff_to: the differences over the points differ by x or less (-20 and -50: 30)
    two = {"select": {"v": "opt"}, "stat": "p50"}
    assert ev({**two, "expect": {"diff_to": {"axes": {"v": "base"}, "spread_abs_le": 30}}}, pts)["verdict"] == "confirmed"
    assert ev({**two, "expect": {"diff_to": {"axes": {"v": "base"}, "spread_abs_le": 29}}}, pts)["verdict"] == "wrong"
    assert ev({**sel, "expect": {"ratio_to": {"point": "base", "stat": "p50"}, "range": [0.75, 0.85]}},
              pts)["verdict"] == "confirmed"
    r = ev({"select": {"point": "opt-l"}, "stat": "p50",
            "expect": {"diff_change": {"point": "base-l", "of": ["opt", "base"], "range": [None, -20]}}}, pts)
    assert r["verdict"] == "confirmed"  # (150 - 200) - (80 - 100) = -30


def test_reference_run_and_hist_identical():
    ref = [obs("p", 90, run="r/20260101T000001Z")]
    pts = [obs("q", 100)]
    runs = {"st/r/20260101T000001Z": ref}
    r = ev({"stat": "p50", "expect": {"diff_to": {"run": "st/r/20260101T000001Z", "points": {"q": "p"}, "range": [10, 10]}}},
           pts, runs)
    assert r["verdict"] == "confirmed"
    same = [obs("q", 90)]
    assert ev({"stat": None, "expect": {"hist_identical_to": {"run": "st/r/20260101T000001Z", "point": "p"}}},
              same, runs)["verdict"] == "confirmed"


def test_reference_run_of_a_different_revision():
    """revision: different: a reference run of the same safety revision gives no verdict."""
    def at(rev, value=90):
        return checks.Obs("r/20260101T000001Z", "ws-up", "p", {}, rep({"irq": hist([(value, 10)])}), safety_rev=rev)
    pts = [checks.Obs("e/20260101T000000Z", "ws-up", "q", {}, rep({"irq": hist([(100, 10)])}), safety_rev="aaa")]
    spec = {"run": "st/r/20260101T000001Z", "points": {"q": "p"}, "range": [10, 10], "revision": "different"}
    with pytest.raises(NoValue, match="same safety revision"):
        ev({"stat": "p50", "expect": {"diff_to": spec}}, pts, {"st/r/20260101T000001Z": [at("aaa")]})
    r = ev({"stat": "p50", "expect": {"diff_to": spec}}, pts, {"st/r/20260101T000001Z": [at("bbb")]})
    assert r["verdict"] == "confirmed"


def test_within_with_tolerance():
    """within: the value is in min..max of the other experiment, +- k coarse bins (32 cycles)."""
    def run(v):
        pts = [checks.Obs("e/1", "ws-up", "x", {}, rep({"irq": hist([(v, 1)], coarse=[(4096, 0, 32)])}))]

        class S(Src):
            def observations(self, exp, series=None):
                return [obs("a", 2000), obs("b", 2010)] if exp == "other" else pts
        return checks.evaluate({"experiment": "e", "metric": "irq", "stat": "p50",
                                "expect": {"within": {"experiment": "other", "stat": "range"}, "tolerance_bins": 1}},
                               S([]))["verdict"]
    assert run(2042) == "confirmed"
    assert run(2043) == "wrong"
    assert run(1968) == "confirmed"


def test_no_points_is_no_value():
    with pytest.raises(NoValue):
        ev({"select": {"point": "zzz"}, "stat": "p50", "expect": {"range": [0, 1]}}, [obs("a", 1)])


# ------------------------------------------------------------------ central results
def test_fill_and_poisson_bound():
    text, missing = central.fill("p {p99.99} at {tree:>3}, {nope}", {"p99.99": 7, "tree": "up"})
    assert text == "p 7 at  up, {nope}" and missing == ["nope"]
    assert central.poisson_upper(0, 4_000_000, 0.95) == pytest.approx(7.49e-7, rel=1e-2)
    assert central.poisson_upper(20, 4_000_000, 0.95) == pytest.approx(7.27e-6, rel=1e-2)
    slope, icept = central.lstsq([0, 16, 64], [100, 132, 228])
    assert slope == pytest.approx(2) and icept == pytest.approx(100)


# ------------------------------------------------------------------ a build of a small tree
LOG = """LAT BEGIN
LAT META app=wake_latency
LAT META core_hz=170000000
LAT META samples=100
LAT META clock_drift_cyc=800
LAT META clock_elapsed_cyc=1000000
LAT CFG TIMESLICING=1
LAT HIST isr2thr n=100 min={lo} max={hi} mean={mean} overflow=0 invalid=0
LAT BIN {lo} 90
LAT BIN {hi} 10
LAT END
"""


def make_design(tmp_path):
    root = tmp_path / "design"
    exp = root / "st-sub" / "ex-exp1"
    exp.mkdir(parents=True)
    (root / "study.yaml").write_text(yaml.safe_dump({"name": "top", "question": "q", "substudies": [{"use": "sub"}],
                                                     "central_results": [{"id": "c1", "from": {"substudy": "sub"}}]}))
    (root / "st-sub" / "study.yaml").write_text(yaml.safe_dump({
        "name": "sub", "question": "q", "experiments": ["exp1"],
        "central_results": [{"id": "c1", "statement": "{point} p50 {p50}", "from": {"experiment": "exp1",
                                                                                   "metric": "isr2thr"},
                             "stat": "p50"}]}))
    (root / "st-sub" / "hypotheses.yaml").write_text(yaml.safe_dump({"hypotheses": [{
        "id": "H1", "type": "model", "statement": "b is slower", "basis": "x", "wrong_if": "y",
        "checks": [{"id": "a", "experiment": "exp1", "metric": "isr2thr", "stat": "p50",
                    "expect": {"order": ["a", "b"]}},
                   {"id": "b", "manual": True, "statement": "looks right"}]}]}))
    (exp / "experiment.yaml").write_text(yaml.safe_dump({
        "name": "exp1", "app": "wake_latency", "trees": ["ws-up"],
        "axes": {"variant": {"a": {}, "b": {"kconfig": {"X": 1}}}},
        "acceptance": [{"id": "A1", "metric": "isr2thr", "stat": "invalid", "expect": {"equals": 0}}]}))
    (exp / "experiment.md").write_text("# exp1\n")
    return Design(root)


def make_run(folder, values):
    run = folder / "20260101T000000Z"
    points = []
    for pid, (lo, hi) in values.items():
        (run / "ws-up" / pid).mkdir(parents=True)
        (run / "ws-up" / pid / "rep1.log").write_text(LOG.format(lo=lo, hi=hi, mean=(lo * 90 + hi * 10) / 100))
        points.append({"tree": "ws-up", "id": pid, "axes": {"variant": pid}, "logs": [f"ws-up/{pid}/rep1.log"]})
    (run / "manifest.json").write_text(json.dumps({
        "experiment": "exp1", "experiment_file": "x", "experiment_yaml": "app: wake_latency\n",
        "board": "nucleo_g474re", "host": "h", "safety": {"rev": "r"}, "trees": {}, "points": points}))
    return run


def test_build_small_tree(tmp_path, monkeypatch):
    design = make_design(tmp_path)
    res = tmp_path / "results"
    monkeypatch.setattr(build, "Design", lambda: design)
    instance.new(design, res, "top", "sub", "nucleo_g474re")
    inst = res / "top" / "st-sub@nucleo_g474re"
    src = make_run(tmp_path / "flat" / "exp1", {"a": (100, 200), "b": (150, 300)})
    instance.add(design, inst, src, copy=True)
    t, w = build.build(res / "top", log=lambda *a: None)
    sj = json.loads((inst / "study.json").read_text())
    h = sj["hypotheses"][0]
    assert h["checks"][0]["verdict"] == "confirmed" and h["verdict"] == "open"
    assert sj["acceptance"][0]["checks"][0]["verdict"] == "confirmed"
    assert sj["central_results"][0]["texts"] == ["a p50 100", "b p50 150"]
    top = json.loads((res / "top" / "study.json").read_text())
    assert top["central_results"][0]["texts"] == ["a p50 100", "b p50 150"]
    assert (inst / "ex-exp1" / "experiment.json").is_file()
    # a manual verdict closes the hypothesis; the same inputs give the same bytes
    instance.add_verdict(inst, "confirmed", "tester", hypothesis="H1", check="b")
    build.build(res / "top", log=lambda *a: None)
    sj = json.loads((inst / "study.json").read_text())
    assert sj["hypotheses"][0]["verdict"] == "confirmed"
    t, w = build.build(res / "top", dry=True, log=lambda *a: None)
    assert w.differ == []
    from studylib import html
    files = html.write_pages(res / "top", design=design)
    sub = (inst / "index.html").read_text()
    assert "b is slower" in sub and "<a href='../index.html'>top</a>" in sub
    top_page = (res / "top" / "index.html").read_text()
    assert "<a href='st-sub@nucleo_g474re/index.html'>st-sub@nucleo_g474re</a>" in top_page
    exp_page = (inst / "ex-exp1" / "index.html").read_text()
    assert "exp1/20260101T000000Z" in exp_page and "<a href='../../index.html'>top</a>" in exp_page
    assert [f.read_bytes() for f in files] == [f.read_bytes() for f in html.write_pages(res / "top", design=design)]
    # a changed raw file breaks the build
    (inst / "ex-exp1" / "20260101T000000Z" / "ws-up" / "a" / "rep1.log").write_text("x")
    with pytest.raises(seal.SealError):
        build.build(res / "top", log=lambda *a: None)


def test_add_refuses_wrong_board_and_unknown_experiment(tmp_path):
    design = make_design(tmp_path)
    res = tmp_path / "results"
    instance.new(design, res, "top", "sub", "nucleo_g474re")
    inst = res / "top" / "st-sub@nucleo_g474re"
    run = make_run(tmp_path / "flat" / "exp1", {"a": (1, 2)})
    m = json.loads((run / "manifest.json").read_text())
    m["board"] = "nrf52840dk/nrf52840"
    (run / "manifest.json").write_text(json.dumps(m))
    with pytest.raises(instance.InstanceError):
        instance.add(design, inst, run, copy=True)


def tiny_elf(payload):
    """An ELF32 little-endian file with one PT_LOAD segment of payload at paddr 0x08000000."""
    import struct
    ehdr = bytearray(52)
    ehdr[:6] = b"\x7fELF\x01\x01"
    struct.pack_into("<I", ehdr, 0x1C, 52)          # e_phoff
    struct.pack_into("<HH", ehdr, 0x2A, 32, 1)      # e_phentsize, e_phnum
    phdr = struct.pack("<IIIIIIII", 1, 84, 0x08000000, 0x08000000, len(payload), len(payload), 5, 4)
    return bytes(ehdr) + phdr + payload


def test_image_and_code_digest(tmp_path):
    from studylib import runfiles
    rev_a, rev_b = "a" * 40, "b" * 40
    (tmp_path / "a.elf").write_bytes(tiny_elf(b"code" + rev_a.encode() + b"more"))
    (tmp_path / "b.elf").write_bytes(tiny_elf(b"code" + rev_b.encode() + b"more"))
    assert runfiles.image_sha256(tmp_path / "a.elf") != runfiles.image_sha256(tmp_path / "b.elf")
    assert runfiles.code_sha256(tmp_path / "a.elf", rev_a) == runfiles.code_sha256(tmp_path / "b.elf", rev_b)
    assert runfiles.bench_rev({"cmake": ["cmake", f"-DLATBENCH_SRC_REV={rev_a}"]}) == rev_a


# ------------------------------------------------------------------ regressions of the review 2026-10-26
def test_count_ge_inside_an_overflow_bin_is_no_value():
    h = hist([(100, 90)], ovf=[(12, 10)])  # 10 samples in 4096..8191
    assert stats.hist_value(h, "count_ge(4096)") == 10
    with pytest.raises(NoValue):
        stats.hist_value(h, "count_ge(5000)")


def test_empty_histogram_is_no_value():
    h = {"n": 0, "min": 0, "max": 0, "mean": 0.0, "overflow": 0, "invalid": 0, "bins": [], "coarse": [], "ovf_log2": []}
    with pytest.raises(NoValue):
        stats.hist_value(h, "p99")
    with pytest.raises(NoValue):
        stats.hist_value(h, "max")
    assert stats.hist_value(h, "n") == 0


def test_point_aggregate_uses_the_reference_of_its_point():
    pts = [obs("a", 10), obs("b", 100)]

    class S(Src):
        def observations(self, exp, series=None):
            return [obs("a", 9, run="e2/1"), obs("b", 99, run="e2/1")] if exp == "E" else pts
    r = checks.evaluate({"experiment": "e", "metric": "irq", "stat": "max(p50)",
                         "expect": {"diff_to": {"experiment": "E", "point": "same", "stat": "p50", "range": [1, 1]}}},
                        S([]))
    assert r["verdict"] == "confirmed", r["measured"]  # b (100) against E b (99)


def test_quantile_in_a_coarse_bin_against_a_limit_in_the_bin():
    h = hist([(10, 99)], coarse=[(4096, 1, 32)])
    p = [checks.Obs("e/1", "t", "x", {}, rep({"irq": h}))]
    with pytest.raises(NoValue):  # p99.95 in 4096..4127, the limit 4100 is in the bin
        ev({"stat": "p99.95", "expect": {"range": [None, 4100]}}, p)
    assert ev({"stat": "p99.95", "expect": {"range": [None, 4127]}}, p)["verdict"] == "confirmed"
    assert ev({"stat": "p99.95", "expect": {"range": [None, 4095]}}, p)["verdict"] == "wrong"


def test_silent_passes_are_no_value():
    with pytest.raises(NoValue):  # one point: no spread
        ev({"stat": "p50", "expect": {"spread_abs_le": 0}}, [obs("a", 1)])
    with pytest.raises(NoValue):  # relative spread with a value <= 0
        ev({"metric": "meta.x", "stat": "value", "expect": {"spread_le": 0.1}},
           [checks.Obs("e/1", "t", p, {}, rep(meta={"x": v})) for p, v in (("a", -10), ("b", -1))])
    with pytest.raises(NoValue):  # a point of the order is not there
        ev({"stat": "p50", "expect": {"order": ["a", "b", "c"]}}, [obs("a", 1), obs("c", 3)])
    with pytest.raises(NoValue):  # a selected point is not there
        ev({"select": {"point": ["a", "zz"]}, "stat": "p50", "expect": {"range": [0, 9]}}, [obs("a", 1)])
    with pytest.raises(NoValue):  # two forms
        ev({"stat": "p50", "expect": {"range": [0, 9], "order": ["a"]}}, [obs("a", 1)])
    assert checks.problems({"metric": "irq", "stat": "p50", "expect": {"range": [0, 1], "order": ["a"]}})
    assert checks.problems({"metric": "irq", "expect": {"range": [0, 1]}})  # no stat


def test_m4_function_that_is_not_in_the_data_is_no_value():
    site = {"name": "m4.mask.t.1", "kind": "mask", "ctx": "thread", "n": 1, "min": 1, "max": 5,
            "function": "f", "via": ""}
    p = [checks.Obs("e/1", "t", "x", {}, rep(meta={"m4_floor_cyc": 0},
                                             m4={"table": {}, "symbols": True, "sites": [site]}))]
    assert ev({"metric": "m4.mask[f]", "stat": "n", "expect": {"range": [1, 1]}}, p)["verdict"] == "confirmed"
    with pytest.raises(NoValue):
        ev({"metric": "m4.mask[g]", "stat": "n", "expect": {"range": [0, 0]}}, p)


def test_within_tolerance_uses_the_coarse_width_of_the_metric():
    pts = [obs("x", 1050)]

    class S(Src):
        def observations(self, exp, series=None):
            if exp == "other":
                return [checks.Obs("o/1", "ws-up", "a", {}, rep({"irq": hist([(1000, 1)], coarse=[(2048, 1, 32)])})),
                        obs("b", 1020)]
            return pts
    r = checks.evaluate({"experiment": "e", "metric": "irq", "stat": "p50",
                         "expect": {"within": {"experiment": "other", "stat": "range"}, "tolerance_bins": 1}}, S([]))
    assert r["verdict"] == "confirmed", r["measured"]  # 1050 <= 1020 + 32


def test_hist_identical_to_an_experiment():
    """The reference can be an experiment: the point of its one evidence run."""
    class S(Src):
        def observations(self, exp, series=None):
            return ref if exp == "other" else self.points
    ref = [obs("p", 90, run="other/20260101T000001Z")]
    check = {"experiment": "e", "metric": "irq", "stat": None,
             "expect": {"hist_identical_to": {"experiment": "other", "point": "p"}}}
    assert checks.evaluate(check, S([obs("q", 90)]))["verdict"] == "confirmed"
    assert checks.evaluate(check, S([obs("q", 91)]))["verdict"] == "wrong"
    ref.append(obs("p", 90, run="other/20260102T000001Z"))
    with pytest.raises(NoValue):
        checks.evaluate(check, S([obs("q", 90)]))


def test_hist_identical_needs_the_same_tree():
    runs = {"st/r/1": [obs("p", 90, tree="ws-up", run="r/1")]}
    with pytest.raises(NoValue):
        ev({"stat": None, "expect": {"hist_identical_to": {"run": "st/r/1", "point": "p"}}},
           [obs("q", 90, tree="ws-safety")], runs)


def test_phase_share_counts_the_absent_bins():
    class Ctx:
        def defaults(self):
            return {}
    ph = {"period": 100, "nbins": 4, "bins": [[0, 10, 0, 0, 0], [1, 10, 0, 0, 0]]}
    o = checks.Obs("e/1", "t", "x", {}, {"meta": {}, "hists": {}, "phases": {"irq": ph}, "m4": None})
    out = central.evaluate({"id": "c", "statement": "{min} {max}", "stat": "phase_share_range",
                            "from": {"experiment": "e", "metric": "irq"}}, Src([o]), Ctx())
    assert out["rows"][0]["min"] == 0 and out["rows"][0]["max"] == 2


def test_poisson_bound_without_samples_and_rounding_up():
    with pytest.raises(NoValue):
        central.poisson_upper(0, 0, 0.95)
    assert central.round_up(0.0001081) == pytest.approx(0.000109)


def test_rerun_import_does_not_read_the_owner(tmp_path, monkeypatch):
    design_root = tmp_path / "design"
    make_design(tmp_path)
    d = yaml.safe_load((design_root / "study.yaml").read_text())
    d["substudies"].append({"use": "rr"})
    (design_root / "study.yaml").write_text(yaml.safe_dump(d))
    (design_root / "st-rr").mkdir()
    (design_root / "st-rr" / "study.yaml").write_text(yaml.safe_dump({
        "name": "rr", "question": "q", "imports": [{"study": "sub", "experiment": "exp1", "mode": "rerun"}],
        "central_results": [{"id": "same", "statement": "{hist_identical_count} of {n}",
                             "from": {"experiment": "exp1"}, "stat": "hist_identical_count"}]}))
    design = Design(design_root)
    monkeypatch.setattr(build, "Design", lambda: design)
    res = tmp_path / "results"
    instance.new(design, res, "top", "sub", "nucleo_g474re")
    instance.new(design, res, "top", "rr", "nucleo_g474re")
    instance.add(design, res / "top" / "st-sub@nucleo_g474re", make_run(tmp_path / "flat" / "exp1", {"a": (1, 2)}),
                 copy=True)
    build.build(res / "top", log=lambda *a: None)
    sj = json.loads((res / "top" / "st-rr@nucleo_g474re" / "study.json").read_text())
    assert "not_evaluated" in sj["central_results"][0], sj["central_results"][0]


def test_reference_digest_and_manual_verdict_are_checked(tmp_path, monkeypatch):
    design = make_design(tmp_path)
    monkeypatch.setattr(build, "Design", lambda: design)
    res = tmp_path / "results"
    instance.new(design, res, "top", "sub", "nucleo_g474re")
    inst = res / "top" / "st-sub@nucleo_g474re"
    rid = instance.add(design, inst, make_run(tmp_path / "flat" / "exp1", {"a": (1, 2), "b": (3, 4)}), copy=True)
    with pytest.raises(instance.InstanceError):
        instance.add_verdict(inst, "Wrong", "tester", hypothesis="H1", check="b")
    top = instance.load(res / "top")
    top["references"] = [{"instance": "top/sub@nucleo_g474re", "id": rid, "digest": "sha256:0", "role": "reference"}]
    instance.save(res / "top", top)
    with pytest.raises(build.BuildError):
        build.build(res / "top", log=lambda *a: None)


def test_data_module_reads_a_built_instance(tmp_path, monkeypatch):
    pytest.importorskip("pandas")
    import data
    design = make_design(tmp_path)
    monkeypatch.setattr(build, "Design", lambda: design)
    res = tmp_path / "results"
    instance.new(design, res, "top", "sub", "nucleo_g474re")
    inst = res / "top" / "st-sub@nucleo_g474re"
    rid = instance.add(design, inst, make_run(tmp_path / "flat" / "exp1", {"a": (100, 200), "b": (150, 300)}),
                       copy=True)
    build.build(res / "top", log=lambda *a: None)
    monkeypatch.setattr(data.trees, "REPO_DIR", Path("/"))
    d = data.load_instance(inst)
    assert list(d.hypotheses()["id"]) == ["H1"]
    assert len(d.checks()) == 2
    assert list(d.central()["result"]) == ["a p50 100", "b p50 150"]
    assert len(d.rows("exp1")) == 2
    assert d.hist("b", "isr2thr", "exp1")["min"] == 150
    assert d.app_data(rid)["app"] == "wake_latency"
    x, y = data.ccdf(d.hist("a", "isr2thr", "exp1"))
    assert x == [100, 200] and y == [1.0, 0.1]


def test_merge_takes_the_new_runs_of_another_tree(tmp_path, monkeypatch):
    design = make_design(tmp_path)
    for host in ("lab", "here"):
        instance.new(design, tmp_path / host, "top", "sub", "nucleo_g474re")
    lab = tmp_path / "lab" / "top" / "st-sub@nucleo_g474re"
    instance.add(design, lab, make_run(tmp_path / "flat" / "exp1", {"a": (1, 2)}), copy=True)
    added = instance.merge(design, tmp_path / "lab" / "top", tmp_path / "here" / "top", log=lambda *a: None)
    assert added == ["exp1/20260101T000000Z"]
    here = tmp_path / "here" / "top" / "st-sub@nucleo_g474re"
    assert instance.load(here)["runs"][0]["digest"] == instance.load(lab)["runs"][0]["digest"]
    assert instance.merge(design, tmp_path / "lab" / "top", tmp_path / "here" / "top", log=lambda *a: None) == []


def test_merge_records_the_origin_of_a_copy(tmp_path):
    design = make_design(tmp_path)
    for host in ("lab", "here"):
        instance.new(design, tmp_path / host, "top", "sub", "nucleo_g474re")
    lab = tmp_path / "lab" / "top" / "st-sub@nucleo_g474re"
    instance.add(design, lab, make_run(tmp_path / "flat" / "exp1", {"a": (1, 2)}), copy=True)
    instance.merge(design, tmp_path / "lab" / "top", tmp_path / "here" / "top", log=lambda *a: None,
                   origin="lab-host:/results/top/")
    here = tmp_path / "here" / "top" / "st-sub@nucleo_g474re"
    assert instance.load(here)["runs"][0]["copied_from"] == \
        "lab-host:/results/top/st-sub@nucleo_g474re/ex-exp1/20260101T000000Z"


def test_provisional_while_a_campaign_runs_and_reuse(tmp_path, monkeypatch):
    design = make_design(tmp_path)
    res = tmp_path / "results"
    monkeypatch.setattr(build, "Design", lambda: design)
    instance.new(design, res, "top", "sub", "nucleo_g474re")
    inst = res / "top" / "st-sub@nucleo_g474re"
    instance.add(design, inst, make_run(tmp_path / "flat" / "exp1", {"a": (100, 200), "b": (150, 300)}), copy=True)
    pending = {(inst.resolve(), "exp1"): "20260101T120000Z"}
    build.build(res / "top", log=lambda *a: None, pending=pending)
    sj = json.loads((inst / "study.json").read_text())
    assert sj["state"] == {"final": False, "waits": ["waits for exp1 of the campaign 20260101T120000Z"]}
    h = sj["hypotheses"][0]
    assert h["provisional"] and h["checks"][0]["provisional"].startswith("waits for exp1")
    assert "provisional" not in h["checks"][1]        # a manual check reads no experiment
    assert sj["central_results"][0]["provisional"]
    build.build(res / "top", log=lambda *a: None, pending={})
    sj = json.loads((inst / "study.json").read_text())
    assert sj["state"] == {"final": True, "waits": []} and "provisional" not in sj["hypotheses"][0]
    # a second build takes the app data of the first one (no extractor), unless the tool is dirty
    monkeypatch.setattr(build.Tree, "find_pending", lambda self: {})
    monkeypatch.setattr(build, "repo_rev", lambda: ("c" * 40, False))
    build.build(res / "top", log=lambda *a: None)
    calls = []
    monkeypatch.setattr(build.runfiles, "app_json", lambda *a: calls.append(a) or (_ for _ in ()).throw(RuntimeError))
    build.build(res / "top", log=lambda *a: None)
    assert calls == []


def test_a_check_with_a_todo_text_is_a_draft(tmp_path, monkeypatch):
    design = make_design(tmp_path)
    h = design.study("sub").hypotheses[0]
    h["checks"][0]["basis"] = "TODO: where the number comes from"
    res = tmp_path / "results"
    monkeypatch.setattr(build, "Design", lambda: design)
    instance.new(design, res, "top", "sub", "nucleo_g474re")
    inst = res / "top" / "st-sub@nucleo_g474re"
    instance.add(design, inst, make_run(tmp_path / "flat" / "exp1", {"a": (100, 200), "b": (150, 300)}), copy=True)
    instance.add_verdict(inst, "confirmed", "tester", hypothesis="H1", check="b")
    build.build(res / "top", log=lambda *a: None)
    hj = json.loads((inst / "study.json").read_text())["hypotheses"][0]
    assert hj["checks"][0]["verdict"] == "draft"        # the order holds, but nobody wrote the basis
    assert hj["verdict"] == "open" and "draft" in hj["open"]


def test_missing_runs_and_the_summary(tmp_path, monkeypatch):
    import study
    design = make_design(tmp_path)
    res = tmp_path / "results"
    monkeypatch.setattr(build, "Design", lambda: design)
    instance.new(design, res, "top", "sub", "nucleo_g474re")
    build.build(res / "top", log=lambda *a: None)
    root, results = study.load_results(res / "top")
    m = study.missing(results)
    assert {k: set(v) for k, v in m.items()} == {("top/st-sub@nucleo_g474re", "exp1"): {"H1 a", "[c1]"}}
    inst = res / "top" / "st-sub@nucleo_g474re"
    assert study.summary_line(results[inst], inst) == (
        "top/st-sub@nucleo_g474re: H 0 confirmed, 0 wrong, 1 open; central 0 of 1")
    assert set(study.load_results(inst)[1]) == {inst}          # a folder shows only its own instances


def test_a_long_measured_text_is_short():
    pts = [obs(f"p{i}", 100 + i) for i in range(6)]
    out = ev({"experiment": "e", "metric": "irq", "stat": "p50", "expect": {"range": [0, 102]}}, pts)
    assert out["measured"].startswith("6 values, min 100, max 105; 3 outside the limit: FAIL ")
    assert len(out["measured_lines"]) == 6


def test_notebooks_run_once_for_the_same_inputs(tmp_path, monkeypatch):
    from studylib import notebooks
    design = make_design(tmp_path)
    nb = tmp_path / "design" / "st-sub" / "report.ipynb"
    nb.write_text('{"cells": [], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}\n')
    res = tmp_path / "results"
    monkeypatch.setattr(build, "Design", lambda: design)
    monkeypatch.setattr(notebooks.trees, "REPO_DIR", tmp_path)
    instance.new(design, res, "top", "sub", "nucleo_g474re")
    build.build(res / "top", log=lambda *a: None)
    inst = res / "top" / "st-sub@nucleo_g474re"
    sj = json.loads((inst / "study.json").read_text())
    sj["design"]["folder"] = "design/st-sub"
    (inst / "study.json").write_text(json.dumps(sj))
    calls = []

    def fake(nb_file, folder, repo):
        calls.append((nb_file.name, folder))
        return "<html>ok</html>"
    out = notebooks.run(res / "top", log=lambda *a: None, executor=fake)
    assert [x[2] for x in out] == ["ran"] and calls == [("report.ipynb", inst)]
    assert (inst / "notebooks" / "report.html").read_text() == "<html>ok</html>"
    assert [x[2] for x in notebooks.run(res / "top", log=lambda *a: None, executor=fake)] == ["the same inputs"]
    assert len(calls) == 1

    def broken(nb_file, folder, repo):
        raise notebooks.NotebookError("cell 3: KeyError")
    out = notebooks.run(res / "top", force=True, log=lambda *a: None, executor=broken)
    assert out[0][2] == "FAILED: cell 3: KeyError"
