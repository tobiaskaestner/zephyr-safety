"""Sphinx extension: testmodule and testreport directives (Route B — sphinx-needs)."""

from docutils import nodes
from docutils.parsers.rst import Directive, directives
from sphinx.util import logging

logger = logging.getLogger(__name__)


class TestModuleDirective(Directive):
    required_arguments = 1
    optional_arguments = 0
    has_content = False
    option_spec = {}

    def run(self):
        module_path = self.arguments[0]
        msg = f"[testmodule stub] module: {module_path} — directive not yet implemented"
        logger.info(msg)
        para = nodes.paragraph(text=msg)
        return [para]


class TestReportDirective(Directive):
    required_arguments = 1
    optional_arguments = 0
    has_content = False
    option_spec = {
        "module": directives.unchanged_required,
    }

    def run(self):
        twister_path = self.arguments[0]
        module_path = self.options.get("module", "")
        msg = (
            f"[testreport stub] twister: {twister_path}, module: {module_path}"
            " — directive not yet implemented"
        )
        logger.info(msg)
        para = nodes.paragraph(text=msg)
        return [para]


def setup(app):
    app.add_directive("testmodule", TestModuleDirective)
    app.add_directive("testreport", TestReportDirective)
    return {"version": "0.1", "parallel_read_safe": True}
