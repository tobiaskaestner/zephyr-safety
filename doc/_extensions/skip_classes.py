"""Sphinx extension: the test report's skipped results by class and board.

zdocs gives every skipped test result a ``skip_class`` (config, platform,
build-only, unexplained) and every result a ``depends_met``. The
``skipclasscounts`` directive renders a table with one row per class and one
column per board of the run, each cell a ``:need_count:`` that sphinx-needs
resolves over the report's results. The boards are read from the run's
``twister.json`` (``twister_output_dir``), so a run on other boards gets its own
columns without an edit here.

Usage::

    .. skipclasscounts::
"""

import json
from pathlib import Path

from docutils import nodes
from docutils.parsers.rst import Directive
from docutils.statemachine import ViewList
from sphinx.util import logging

logger = logging.getLogger(__name__)

#: zdocs' skip classes, in the order the table shows them.
SKIP_CLASSES = ("config", "platform", "build-only", "unexplained")


def _count(condition):
    return f':need_count:`type == "test_result" and {condition}`'


def table_rst(platforms):
    """RST lines of the class x board table for ``platforms``."""
    columns = [(p, f'platform == "{p}"') for p in platforms] + [("all boards", "True")]
    lines = [
        ".. list-table:: Skipped results by class and board",
        "   :header-rows: 1",
        "   :stub-columns: 1",
        "",
        "   * - class",
    ]
    lines += [f"     - ``{name}``" for name in platforms] + ["     - all boards"]
    rows = [(f"``{cls}``", f'skip_class == "{cls}"') for cls in SKIP_CLASSES]
    rows.append(("skipped", 'status == "skipped"'))
    for label, row in rows:
        lines.append(f"   * - {label}")
        lines += [f"     - {_count(f'{row} and {col}')}" for _, col in columns]
    lines.append("")
    return lines


class SkipClassCounts(Directive):
    has_content = False

    def run(self):
        env = self.state.document.settings.env
        twister_json = Path(env.config.twister_output_dir or "") / "twister.json"
        env.note_dependency(str(twister_json))
        try:
            data = json.loads(twister_json.read_text())
        except (OSError, ValueError) as exc:
            logger.warning(f"skipclasscounts: cannot read {twister_json}: {exc}")
            return [nodes.paragraph(text="[skipclasscounts: twister.json not found]")]
        platforms = sorted({ts.get("platform", "") for ts in data.get("testsuites", [])} - {""})
        container = nodes.container()
        self.state.nested_parse(ViewList(table_rst(platforms), source="<skipclasscounts>"),
                                self.content_offset, container)
        return container.children


def setup(app):
    app.add_directive("skipclasscounts", SkipClassCounts)
    return {"version": "0.1", "parallel_read_safe": True, "parallel_write_safe": True}
