# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for scripts/m4.py (the M4 site tables).

The fixtures m4_*.log are the console output of the ztest app
unit/irqmask (one log for each scenario). ref_values() makes the same
values as its fixture test, so that the tests compare the parsed log with
values that do not come from the code under test.
"""

import argparse
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(SCRIPTS))

import m4  # noqa: E402

# The sites of test_emit_fixture() in unit/irqmask/src/main.c: pc, ipsr, kind, span.
FIX_SITES = [
    (0x08001001, 0, "mask", 200),
    (0x08001101, 15, "mask", 8000),
    (0x08002201, 14, "mask", 40),
    (0x08003301, 15, "isr", 80000),
]


def lcg(s):
    return (s * 1664525 + 1013904223) & 0xFFFFFFFF


def ref_values(meta):
    """{pc: [values]} of test_emit_fixture()."""
    s = int(meta["seed"])
    out = {pc: [] for pc, *_ in FIX_SITES}
    for _ in range(int(meta["samples"])):
        s = lcg(s)
        k = (s >> 24) % len(FIX_SITES)
        s = lcg(s)
        out[FIX_SITES[k][0]].append(12 + (s >> 8) % FIX_SITES[k][3])
    return out


def ref_bin(v, sub_bits):
    """Lower edge and width of the bin of v from the documented layout, or None for >= 2^16."""
    if v < (2 << sub_bits):
        return v, 1
    if v >= 1 << 16:
        return None
    k = v.bit_length() - 1
    w = 1 << (k - sub_bits)
    return v & ~(w - 1), w


FIXTURE_LOGS = sorted(FIXTURES.glob("m4_*.log"))


def test_fixtures_present():
    assert {p.stem for p in FIXTURE_LOGS} >= {"m4_default", "m4_small"}


@pytest.fixture(params=FIXTURE_LOGS, ids=lambda p: p.stem)
def fixture_run(request):
    run = m4.parse_m4(request.param)
    return run, ref_values(run["meta"])


def test_roundtrip_sites(fixture_run):
    run, ref = fixture_run
    sites = {s["pc"]: s for s in run["m4"]["sites"]}
    assert run["m4"]["table"]["used"] == len(FIX_SITES)
    assert run["m4"]["table"]["dropped"] == 0
    for pc, ipsr, kind, _ in FIX_SITES:
        s, vals = sites[pc], ref[pc]
        assert (s["kind"], s["ipsr"]) == (kind, ipsr)
        assert s["n"] == len(vals)
        assert s["sum"] == sum(vals)
        assert s["min"] == min(vals)
        assert s["max"] == max(vals)
        assert s["end_pc"] == pc + 0x40


def test_roundtrip_bins(fixture_run):
    run, ref = fixture_run
    sub_bits = run["m4"]["table"]["sub_bits"]
    for s in run["m4"]["sites"]:
        want, width, over = {}, {}, 0
        for v in ref[s["pc"]]:
            b = ref_bin(v, sub_bits)
            if b is None:
                over += 1
                continue
            want[b[0]] = want.get(b[0], 0) + 1
            if b[1] > 1:
                width[b[0]] = b[1]
        h = s["hist"]
        assert h["bins"] == want
        assert h["width"] == width
        assert h["overflow"] == over
        assert sum(h["ovf_log2"].values()) == over
        assert h["n"] == s["n"]


def test_ctx_names():
    assert m4.ctx_name(0) == "thread"
    assert m4.ctx_name(14) == "PendSV"
    assert m4.ctx_name(15) == "SysTick"
    assert m4.ctx_name(16) == "irq0"
    assert m4.ctx_name(22) == "irq6"
    assert m4.ctx_name(5) == "exc5"


def test_site_rows_sorted_and_net(fixture_run):
    run, ref = fixture_run
    rows = m4.site_rows(run, None, "mask")
    assert [r["max"] for r in rows] == sorted((r["max"] for r in rows), reverse=True)
    assert all(r["max_net"] == r["max"] - 12 for r in rows)
    assert abs(sum(r["share%"] for r in rows) - 100) < 0.5
    isr = m4.site_rows(run, None, "isr")
    assert len(isr) == 1 and isr[0]["ctx"] == "SysTick"
    # The ISR site has values of 2^16 and more: the top quantile is in the overflow bin.
    assert isr[0]["p99.99"] == ">=65536"


def test_no_m4(tmp_path):
    p = tmp_path / "run.log"
    p.write_text("LAT BEGIN\nLAT META app=x\nLAT DONE\n")
    assert m4.parse_m4(p)["m4"] is None
    assert m4.sweep_row(p)["m4"] == "no"


def test_last_run_only(tmp_path):
    text = FIXTURE_LOGS[0].read_text()
    p = tmp_path / "run.log"
    # A first run with one other site; only the last run counts.
    p.write_text("LAT BEGIN\nLAT M4 BEGIN sites=64 used=1 dropped=0 bins=112 sub_bits=3\n"
                 "LAT M4SITE m4.mask.t.09000001 kind=mask ipsr=0 pc=0x09000001 end_pc=0x0 "
                 "n=1 sum=5 min=5 max=5\nLAT M4 END\nLAT DONE\n" + text)
    run = m4.parse_m4(p)
    assert 0x09000001 not in {s["pc"] for s in run["m4"]["sites"]}


def test_sweep_row(fixture_run):
    run, _ = fixture_run
    row = m4.sweep_row(run["source"])
    assert row["mask_max"] == max(s["max"] for s in run["m4"]["sites"] if s["kind"] == "mask")
    assert row["mask_max_ctx"] == "SysTick"
    assert row["isr_max_ctx"] == "SysTick"
    assert row["irq_max"] == "-"


# ------------------------------------------------------------------ names

NM = """\
08000f30 T z_arm_irq_mask_hook_begin
08000f60 T z_arm_irq_mask_hook_end
08001fd8 T z_arm_pendsv
08002090 t z_add_timeout
20000000 B _kernel
"""

ADDR2LINE = """\
0x08002100
arch_irq_lock
/z/include/zephyr/arch/arm/asm_inline_gcc.h:65
k_spin_lock
/z/include/zephyr/spinlock.h:203
z_add_timeout
/z/kernel/timeout.c:191 (discriminator 2)
0x08001ff0
z_arm_pendsv
/z/arch/arm/core/cortex_m/swap_helper.S:136
0x08009000
??
??:0
"""


def test_parse_nm():
    syms = m4.parse_nm(NM)
    assert syms[0] == (0x08000f30, "z_arm_irq_mask_hook_begin")
    assert (0x20000000, "_kernel") not in syms


def test_parse_addr2line():
    out = m4.parse_addr2line(ADDR2LINE)
    assert list(out) == [0x08002100, 0x08001ff0, 0x08009000]
    assert out[0x08002100][-1] == ("z_add_timeout", "/z/kernel/timeout.c:191 (discriminator 2)")
    assert len(out[0x08002100]) == 3


def test_describe():
    out = m4.parse_addr2line(ADDR2LINE)
    assert m4.describe(out[0x08002100], "x") == ("z_add_timeout", "timeout.c:191", "k_spin_lock")
    assert m4.describe(out[0x08001ff0], "x") == ("z_arm_pendsv", "swap_helper.S:136", "")
    # No line information: the nm name.
    assert m4.describe(out[0x08009000], "foo+0x10") == ("foo+0x10", "?", "")


def test_call_addr():
    # The return address after a 4-byte BL at 0x08000100 is 0x08000104 | 1.
    assert m4.call_addr(0x08000105) == 0x08000102
    assert m4.site_addr({"kind": "isr", "pc": 0x08003301}) == 0x08003300
    assert m4.site_addr({"kind": "mask", "pc": 0x08000105}) == 0x08000102


class FakeSym:
    def __init__(self):
        self.syms = m4.parse_nm(NM)
        self.addrs = [a for a, _ in self.syms]

    nm_name = m4.Symbolizer.nm_name

    def lookup(self, addrs):
        return {a: [("k_spin_lock", "/z/spinlock.h:1"), ("f_%x" % a, "/z/x.c:%d" % (a & 0xff))]
                for a in addrs}


def test_nm_name():
    s = FakeSym()
    assert s.nm_name(0x08001fd8) == "z_arm_pendsv"
    assert s.nm_name(0x08001fe0) == "z_arm_pendsv+0x8"
    assert s.nm_name(0x08000000) == "?"


def test_site_rows_names(fixture_run):
    run, _ = fixture_run
    rows = m4.site_rows(run, FakeSym(), "mask")
    r = rows[0]
    a = m4.call_addr(int(r["pc"], 16))
    assert r["function"] == "f_%x" % a
    assert r["via"] == "k_spin_lock"
    assert r["max_end"].startswith("f_")


def test_find_prefix(tmp_path):
    sdk = tmp_path / "sdk"
    bindir = sdk / "gnu" / "arm-zephyr-eabi" / "bin"
    bindir.mkdir(parents=True)
    (bindir / "arm-zephyr-eabi-nm").write_text("")
    run_dir = tmp_path / "run"
    (run_dir / "ws-up-irqoff" / "p").mkdir(parents=True)
    (run_dir / "manifest.json").write_text('{"toolchain": {"path": "%s"}}' % sdk)
    log = run_dir / "ws-up-irqoff" / "p" / "rep1.log"
    assert m4.find_prefix(log) == str(bindir / "arm-zephyr-eabi-")
    assert m4.find_prefix(log, "/x/arm-") == "/x/arm-"
    assert m4.find_prefix(tmp_path / "other.log") is None


def test_cli_table(fixture_run, capsys):
    run, _ = fixture_run
    m4.cmd_table(argparse.Namespace(log=run["source"], elf=None, binutils=None, no_names=True,
                                    top=2, md=True, json=False))
    out = capsys.readouterr().out
    assert "Mask sections" in out and "ISR bodies" in out
    assert out.count("| mask |") == 2
