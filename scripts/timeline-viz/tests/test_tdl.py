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
# The diagrams of the documentation (timeline-viz directive).
DOC_DIAGRAMS = sorted((TOOL.parents[1] / "doc").glob("**/diagrams/*.tdl"))

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


@pytest.mark.parametrize("path", DOC_DIAGRAMS, ids=lambda p: p.name)
def test_doc_diagrams_compile_without_overlap(path):
    card = tdl.compile_file(path, {})
    pieces = card.get("pieces") or [{"from": card["from"], "to": card["to"]}]
    lanes = {}
    for s in card["segs"]:
        pc = pieces[s.get("p", 0)]
        assert pc["from"] <= s["t0"] < s["t1"] <= pc["to"], s
        lanes.setdefault((s["lane"], s.get("p", 0)), []).append((s["t0"], s["t1"]))
    for steps in lanes.values():
        steps.sort()
        assert all(b[0] >= a[1] for a, b in zip(steps, steps[1:])), steps


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


def test_lock_range_inside_a_step(tmp_path):
    card = compile_text(tmp_path, """\
diagram x "x"
axis "cycles" 0..1000
waker 100 "take" {basepri}
dev 60 "switch" {basepri 20..40}
waker 30 "idle" {primask}
""")
    assert segs(card, "mask") == [(0, 100, "mask", "BASEPRI"), (120, 140, "mask", "BASEPRI"),
                                  (160, 190, "mask", "PRIMASK")]
    assert [s["lock"] for s in card["segs"] if s["lane"] == "mask"] == ["basepri", "basepri", "primask"]


@pytest.mark.parametrize("lock, msg", [
    ("{basepri 20..80}", "the lock range 20..80 is not inside the step"),
    ("{basepri 20}", "expected '{basepri <from>..<to>}'"),
])
def test_lock_range_errors(tmp_path, lock, msg):
    with pytest.raises(tdl.TdlError, match=msg.replace("{", r"\{").replace("}", r"\}")):
        compile_text(tmp_path, f'diagram x "x"\naxis "c" 0..100\ndev 60 "s" {lock}\n')


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
def test_schematic_has_no_cycle_counts(tmp_path):
    card = compile_text(tmp_path, """\
diagram x "x"
schematic
axis "time" 0..1000
dev 100 "isr" : The ISR.
""")
    assert card["schematic"] is True
    data = json.dumps({"lanes": {"dev": {"label": "Device ISR", "kind": "dev", "group": "isr", "prio": 0}},
                       "laneKeys": ["dev"], "cards": [card]})
    run = subprocess.run(["node", str(TOOL / "tdl-svg.cjs"), "--fragments"], input=data,
                         capture_output=True, text=True, check=True)
    svg = json.loads(run.stdout)["x"]
    assert "<title>Device ISR: isr. The ISR.</title>" in svg
    assert "cycles" not in svg
    assert ">500<" not in svg  # no tick labels
    assert 'stroke-dasharray="4 3"' not in svg  # solid outlines


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


@pytest.mark.skipif(not shutil.which("node"), reason="node is not on PATH")
def test_schematic_width(tmp_path):
    card = compile_text(tmp_path, 'diagram x "x"\nschematic\naxis "t" 0..500\ndev 100 "isr"\n')
    data = {"lanes": {"dev": {"label": "Device ISR", "kind": "dev", "group": "isr", "prio": 0}},
            "laneKeys": ["dev"], "cards": [card]}

    def width(*args):
        run = subprocess.run(["node", str(TOOL / "tdl-svg.cjs"), "--fragments", *args], input=json.dumps(data),
                             capture_output=True, text=True, check=True)
        return int(json.loads(run.stdout)["x"].split(' width="')[1].split('"')[0])

    assert width() == 186 + 500 + 14  # 1 pixel per unit
    assert width("--width", "1000") == 1000
    assert width("--width", "300") == 700  # never narrower than the content
