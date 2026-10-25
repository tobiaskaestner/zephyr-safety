# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the TDL compiler (tdl.py) and the renderer (render.js).

Run: pytest scripts/timeline-viz/tests
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOL))

import tdl  # noqa: E402

CARDS = sorted((TOOL / "latency-modes" / "cards").glob("*.tdl"))

CONTEXTS = """\
core   hw     "Hardware"
core   mask   "PRIMASK, BASEPRI"
isr    dev    0    "Device ISR"
thread waker  0    "Woken thread"
thread main   10   "main"
"""


def compile_text(tmp_path, text, contexts=CONTEXTS):
    (tmp_path / "ctx.tdc").write_text(contexts)
    f = tmp_path / "d.tdl"
    f.write_text("include ctx.tdc\n" + text)
    return tdl.compile_file(f, {})


def segs(card, lane):
    return [(s["t0"], s["t1"], s["s"], s["label"]) for s in card["segs"] if s["lane"] == lane]


def test_all_cards_compile():
    lanes = {}
    cards = [tdl.compile_file(f, lanes) for f in CARDS]
    assert len(cards) == len(CARDS) == 18
    assert len({c["id"] for c in cards}) == len(cards)


def test_sequence_moves_the_cursor(tmp_path):
    card = compile_text(tmp_path, """\
diagram x "x"
axis "cycles" 0..1000
dev 100 "a"
waker 50 "b"
@done
span 0..done "150" !
""")
    assert segs(card, "dev") == [(0, 100, "run", "a")]
    assert segs(card, "waker") == [(100, 150, "run", "b")]
    assert card["brackets"] == [{"t0": 0, "t1": 150, "label": "150", "m": True}]
    assert card["events"] == [{"t": 150, "label": "done", "kind": "stamp"}]


def test_open_end_closes_at_next_step(tmp_path):
    card = compile_text(tmp_path, """\
diagram x "x"
axis "cycles" 0..1000
@edge
dev pending edge.. "pending"
at 40
dev 100 "isr"
""")
    assert segs(card, "dev") == [(0, 40, "pending", "pending"), (40, 140, "run", "isr")]


def test_lock_attributes_merge_into_the_mask_lane(tmp_path):
    card = compile_text(tmp_path, """\
diagram x "x"
axis "cycles" 0..1000
waker 100 "a" {basepri}
waker 50 "b" {basepri}
waker 30 "c"
waker 20 "d" {basepri}
""")
    assert segs(card, "mask") == [(0, 150, "mask", "BASEPRI"), (180, 200, "mask", "BASEPRI")]


def test_flags(tmp_path):
    card = compile_text(tmp_path, """\
diagram x "x"
axis "cycles" 0..1000
dev 100! "measured"
dev 50? "place not known"
""")
    a, b = card["segs"]
    assert a["m"] and a["s"] == "run"
    assert b["s"] == "unk" and "m" not in b


def test_lanes_and_priority(tmp_path):
    card = compile_text(tmp_path, """\
diagram x "x"
axis "cycles" 0..1000
prio main 0
main 10
dev 10
""")
    assert card["lanes"] == ["main", "dev"]
    assert card["prio"] == {"main": 0}


def test_include_search_path(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "ctx.tdc").write_text(CONTEXTS)
    f = tmp_path / "d.tdl"
    f.write_text('include ctx.tdc\ndiagram x "x"\naxis "c" 0..10\ndev 5\n')
    with pytest.raises(tdl.TdlError, match="ctx.tdc' not found"):
        tdl.compile_file(f, {})
    found = []
    tdl.compile_file(f, {}, [lib], found)
    assert found == [(lib / "ctx.tdc").resolve()]


def test_default_contexts_folder():
    assert (tdl.CONTEXTS / "g474.tdc").is_file()


@pytest.mark.parametrize("text, msg", [
    ('diagram x "x"\naxis "c" 0..10\nnobody 5\n', "d.tdl:4: unknown statement or context 'nobody'"),
    ('diagram x "x"\naxis "c" 0..10\ndev 5..later\n', "d.tdl:4: unknown time point 'later'"),
    ('diagram x "x"\naxis "c" 0..10\ndev pending 0..\n', "d.tdl:4: the open end of 'dev' has no later step"),
    ('diagram x "x"\naxis "c" 0..10\ndev 5 {lock}\n', "d.tdl:4: unknown lock 'lock'"),
    ('axis "c" 0..10\ndev 5\n', "no 'diagram' statement"),
])
def test_errors_name_file_and_line(tmp_path, text, msg):
    with pytest.raises(tdl.TdlError, match=msg.replace("(", r"\(")):
        compile_text(tmp_path, text)


@pytest.mark.skipif(not shutil.which("node"), reason="node is not on PATH")
def test_fragments_render_every_card():
    lanes = {}
    cards = [tdl.compile_file(f, lanes) for f in CARDS]
    data = json.dumps({"lanes": lanes, "laneKeys": list(lanes), "cards": cards})
    run = subprocess.run(["node", str(TOOL / "tdl-svg.cjs"), "--fragments"], input=data,
                         capture_output=True, text=True, check=True)
    svgs = json.loads(run.stdout)
    assert sorted(svgs) == sorted(c["id"] for c in cards)
    for svg in svgs.values():
        assert svg.startswith("<svg ") and svg.endswith("</svg>")
        assert "<title>" in svg
