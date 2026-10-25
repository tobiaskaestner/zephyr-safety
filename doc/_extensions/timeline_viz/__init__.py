# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Sphinx extension: timing diagrams from TDL files.

The ``timeline-viz`` directive compiles a TDL file with
``scripts/timeline-viz/tdl.py`` and renders it with
``scripts/timeline-viz/render.js`` (through Node). The latency-modes page
uses the same renderer, so a diagram looks the same in both places. The
SVG goes into the HTML page inline. Its ``<title>`` elements give the
tooltips.

Usage::

    .. timeline-viz:: diagrams/isr-to-thread.tdl
       :name: fig-isr-to-thread
       :width: 980

       Optional caption. Without content, the caption is the title of
       the ``diagram`` statement.

The path is relative to the document, or to the source directory if it
starts with ``/``. An ``include`` statement in the TDL file looks for the
context file next to the TDL file, then in each directory of the config
value ``timeline_viz_include_path``, then in ``scripts/timeline-viz/contexts``.

The output is HTML only. Other builders get the caption and a note.
"""

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

from docutils import nodes
from docutils.parsers.rst import directives
from sphinx import addnodes
from sphinx.util.docutils import SphinxDirective

HERE = Path(__file__).resolve().parent
#: scripts/timeline-viz of this repository.
TOOL = HERE.parents[2] / "scripts" / "timeline-viz"

# Load tdl.py under its own module name: a plain "import tdl" through
# sys.path could load another module of that name.
_spec = importlib.util.spec_from_file_location("timeline_viz_tdl", TOOL / "tdl.py")
tdl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tdl)


def render(card, lanes):
    """The inline SVG of one compiled card (tdl-svg.cjs --fragments)."""
    node = shutil.which("node")
    if not node:
        raise RuntimeError("node is not on PATH (timeline-viz renders the SVG with Node)")
    data = json.dumps({"lanes": lanes, "laneKeys": list(lanes), "cards": [card]})
    run = subprocess.run([node, str(TOOL / "tdl-svg.cjs"), "--fragments"], input=data,
                         capture_output=True, text=True)
    if run.returncode:
        raise RuntimeError(f"tdl-svg.cjs failed: {run.stderr.strip()}")
    return json.loads(run.stdout)[card["id"]]


def page_svg(svg, width):
    """Change the size style of the renderer for a documentation page.

    The renderer gives the SVG a fixed minimum width. Here the SVG shrinks
    to the width of the text column, but not below ``width`` pixels. The
    ``.timeline-viz`` box scrolls if the column is narrower.
    """
    head, rest = svg.split(">", 1)
    start = head.index(' style="')
    end = head.index('"', start + 8)
    style = f' style="width:100%;min-width:{width}px;height:auto"'
    return head[:start] + style + head[end + 1:] + ">" + rest


class TimelineViz(SphinxDirective):
    required_arguments = 1
    has_content = True
    option_spec = {
        "name": directives.unchanged,
        "width": directives.positive_int,
        "class": directives.class_option,
    }

    def run(self):
        rel, path = self.env.relfn2path(self.arguments[0])
        path = Path(path)
        self.env.note_dependency(rel)
        include_path = [Path(self.env.srcdir) / p for p in self.config.timeline_viz_include_path]
        includes = []
        try:
            lanes = {}
            card = tdl.compile_file(path, lanes, include_path, includes)
            svg = render(card, lanes)
        except (OSError, tdl.TdlError, RuntimeError) as e:
            return [self.state.document.reporter.error(f"timeline-viz: {e}", line=self.lineno)]
        for inc in includes:
            self.env.note_dependency(str(inc))

        fig = nodes.figure(classes=["timeline-viz-figure"] + self.options.get("class", []))
        box = nodes.container(classes=["timeline-viz"])
        box += nodes.raw("", page_svg(svg, self.options.get("width", self.config.timeline_viz_min_width)),
                         format="html")
        box += addnodes.only("", nodes.paragraph(text="(The timing diagram is in the HTML output only.)"),
                             expr="not html")
        fig += box
        if self.content:
            cap = nodes.caption()
            self.state.nested_parse(self.content, self.content_offset, cap)
            # a caption is one paragraph: take its inline nodes
            if len(cap) == 1 and isinstance(cap[0], nodes.paragraph):
                cap.children = cap[0].children
        else:
            cap = nodes.caption(text=card["title"])
        fig += cap
        self.set_source_info(fig)
        self.add_name(fig)
        return [fig]


def add_static(app, config):
    config.html_static_path.append(str(HERE / "static"))


def setup(app):
    app.add_config_value("timeline_viz_include_path", [], "env")
    app.add_config_value("timeline_viz_min_width", 760, "env")
    app.add_directive("timeline-viz", TimelineViz)
    app.connect("config-inited", add_static)
    app.add_css_file("timeline-viz.css")
    return {"version": "1", "parallel_read_safe": True, "parallel_write_safe": True}
