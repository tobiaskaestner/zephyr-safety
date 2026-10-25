# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Tests for the Sphinx extension doc/_extensions/timeline_viz.

Each test builds a small Sphinx project in a temporary folder.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parent.parent
EXTENSIONS = TOOL.parents[1] / "doc" / "_extensions"

pytest.importorskip("sphinx")
pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="node is not on PATH")

CONF = f"""\
import sys
sys.path.append({str(EXTENSIONS)!r})
extensions = ["timeline_viz"]
"""

DIAGRAM = """\
include g474.tdc
diagram demo "A demo diagram"
axis "cycles" 0..400
dev 100 "ISR" : The ISR runs.
waker 50 "thread"
"""


def build(tmp_path, index, files=None, builder="html"):
    src = tmp_path / "src"
    src.mkdir()
    (src / "conf.py").write_text(CONF)
    (src / "index.rst").write_text(index)
    for name, text in (files or {}).items():
        (src / name).parent.mkdir(parents=True, exist_ok=True)
        (src / name).write_text(text)
    out = tmp_path / "out"
    run = subprocess.run([sys.executable, "-m", "sphinx", "-b", builder, "-q", str(src), str(out)],
                         capture_output=True, text=True)
    return run, out


def test_inline_svg_with_caption_and_css(tmp_path):
    run, out = build(tmp_path, """\
Title
=====

.. timeline-viz:: diagrams/demo.tdl
   :name: fig-demo

   The *caption*.

See :ref:`fig-demo`.
""", {"diagrams/demo.tdl": DIAGRAM})
    assert run.returncode == 0, run.stderr
    assert run.stderr == ""
    html = (out / "index.html").read_text()
    assert '<div class="timeline-viz docutils container">' in html
    assert 'aria-label="A demo diagram"' in html
    assert "<title>EXTI0 ISR: ISR. 100 cycles (estimate). The ISR runs.</title>" in html
    assert "<em>caption</em>" in html
    assert 'id="fig-demo"' in html
    assert "min-width:760px" in html and "min-width:980px" not in html
    assert "timeline-viz.css" in html
    assert (out / "_static" / "timeline-viz.css").is_file()


def test_default_caption_is_the_diagram_title(tmp_path):
    run, out = build(tmp_path, "T\n=\n\n.. timeline-viz:: demo.tdl\n   :width: 900\n", {"demo.tdl": DIAGRAM})
    assert run.returncode == 0, run.stderr
    html = (out / "index.html").read_text()
    assert '<span class="caption-text">A demo diagram</span>' in html
    assert "min-width:900px" in html


def test_tdl_error_is_a_build_error(tmp_path):
    run, _ = build(tmp_path, "T\n=\n\n.. timeline-viz:: demo.tdl\n",
                   {"demo.tdl": DIAGRAM + "nobody 5\n"})
    assert "timeline-viz:" in run.stderr
    assert "demo.tdl:6: unknown statement or context 'nobody'" in run.stderr


def test_text_builder_gets_a_note(tmp_path):
    run, out = build(tmp_path, "T\n=\n\n.. timeline-viz:: demo.tdl\n", {"demo.tdl": DIAGRAM}, builder="text")
    assert run.returncode == 0, run.stderr
    text = (out / "index.txt").read_text()
    assert "HTML output only" in text
    assert "<svg" not in text
