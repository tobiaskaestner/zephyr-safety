"""Sphinx extension: testmodule and testreport directives (Route B — sphinx-needs)."""

import glob
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml
from docutils import nodes
from docutils.parsers.rst import Directive, directives
from docutils.statemachine import ViewList
from sphinx.util import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# XML → text helpers
# ---------------------------------------------------------------------------

def _elem_text(elem):
    """Recursively extract text from an XML element, collapsing whitespace."""
    if elem is None:
        return ""
    buf = []
    if elem.text:
        buf.append(elem.text)
    for child in elem:
        buf.append(_elem_text(child))
        if child.tail:
            buf.append(child.tail)
    return " ".join(" ".join(buf).split())


def _para_text(para):
    """Extract inline text from a <para>, rendering code/ref as plain text."""
    if para is None:
        return ""
    parts = []
    if para.text:
        parts.append(para.text)
    for child in para:
        if child.tag in ("xrefsect", "simplesect", "orderedlist", "itemizedlist"):
            pass  # skip structural children
        elif child.tag == "computeroutput":
            parts.append(f"``{_elem_text(child)}``")
        elif child.tag in ("bold", "emphasis"):
            parts.append(_elem_text(child))
        else:
            parts.append(_elem_text(child))
        if child.tail:
            parts.append(child.tail)
    return " ".join(" ".join(parts).split())


def _list_to_rst_lines(listelem, marker):
    """Convert <orderedlist> or <itemizedlist> children to RST list lines."""
    lines = []
    for item in listelem.findall("listitem"):
        item_parts = []
        for para in item.findall("para"):
            t = _para_text(para).strip()
            if t:
                item_parts.append(t)
        if item_parts:
            first = item_parts[0]
            rest = item_parts[1:]
            lines.append(f"{marker} {first}")
            for extra in rest:
                # continuation paragraphs indented under the list item
                lines.append(f"   {extra}")
    return lines


def _section_to_rst(simplesect):
    """
    Convert a <simplesect kind="par"> (Arrange / Act / Assert) to RST lines.
    Returns a list of strings.
    """
    title_el = simplesect.find("title")
    title = _elem_text(title_el).strip() if title_el is not None else ""

    lines = []
    if title:
        lines.append(f"**{title}**")
        lines.append("")

    for child in simplesect:
        if child.tag == "title":
            continue
        if child.tag != "para":
            continue

        ol = child.find("orderedlist")
        il = child.find("itemizedlist")
        if ol is not None:
            lines.extend(_list_to_rst_lines(ol, "#."))
            lines.append("")
        elif il is not None:
            lines.extend(_list_to_rst_lines(il, "-"))
            lines.append("")
        else:
            text = _para_text(child).strip()
            if text:
                lines.append(text)
                lines.append("")

    # Remove trailing blank
    while lines and lines[-1] == "":
        lines.pop()
    return lines


def _see_to_rst(simplesect_see, base_url):
    """
    Convert a <simplesect kind="see"> to a 'See also:' RST line.
    API refs (external attribute pointing to safety-api tag) get URLs.
    """
    refs = []
    for ref in simplesect_see.findall(".//ref"):
        name = (ref.text or "").strip()
        if not name:
            continue
        refid = ref.get("refid", "")
        external = ref.get("external", "")
        if refid and "_1" in refid:
            # Split compound_id from member anchor at first _1 occurrence
            idx = refid.index("_1")
            compound = refid[:idx]
            anchor = refid[idx + 2:]  # skip "_1"
            if "zephyr-safety-api" in external:
                url = (
                    f"{base_url}doxygen-zephyr-safety-api/html/"
                    f"{compound}.html#{anchor}"
                )
                refs.append(f"`{name} <{url}>`__")
            else:
                refs.append(name)
        else:
            refs.append(name)
    if refs:
        return "**See also:** " + ", ".join(refs)
    return ""


# ---------------------------------------------------------------------------
# Doxygen XML extraction
# ---------------------------------------------------------------------------

def _parse_memberdef(memberdef, compound_id, base_url):
    """Return a dict of extracted fields for one <memberdef>."""
    name = memberdef.findtext("name", "").strip()

    # Source location
    loc = memberdef.find("location")
    source_file = ""
    if loc is not None:
        fpath = loc.get("bodyfile") or loc.get("file", "")
        line = loc.get("bodystart") or loc.get("line", "")
        if fpath:
            source_file = f"{Path(fpath).name} (line {line})"

    # Doxygen HTML URL
    member_id = memberdef.get("id", "")
    prefix = compound_id + "_1"
    anchor = member_id[len(prefix):] if member_id.startswith(prefix) else member_id
    doxygen_url = (
        f"{base_url}doxygen-zephyr-safety-testspec/html/"
        f"{compound_id}.html#{anchor}"
    )

    # Brief
    brief = _para_text(memberdef.find(".//briefdescription/para"))

    # Detailed description: testid, reqrefs, status, see
    dd = memberdef.find("detaileddescription")
    test_id = ""
    req_ids = []
    status = "draft"
    see_rst = ""
    if dd is not None:
        for xrefsect in dd.findall(".//xrefsect"):
            xid = xrefsect.get("id", "")
            xdesc = (xrefsect.findtext(".//xrefdescription/para") or "").strip()
            if "testids" in xid:
                test_id = xdesc
            elif "reqrefs" in xid and xdesc:
                req_ids.append(xdesc)
            elif "test_active" in xid:
                status = "active"
            elif "test_obsolete" in xid:
                status = "obsolete"
            # test_draft is the default
        see_sect = dd.find(".//simplesect[@kind='see']")
        if see_sect is not None:
            see_rst = _see_to_rst(see_sect, base_url)

    # In-body: Arrange / Act / Assert
    ibd = memberdef.find("inbodydescription")
    body_sections = []
    if ibd is not None:
        for ss in ibd.findall(".//simplesect[@kind='par']"):
            section_lines = _section_to_rst(ss)
            if section_lines:
                body_sections.append(section_lines)

    return {
        "name": name,
        "test_id": test_id,
        "req_ids": req_ids,
        "status": status,
        "source_file": source_file,
        "doxygen_url": doxygen_url,
        "brief": brief,
        "see_rst": see_rst,
        "body_sections": body_sections,
    }


def _build_need_rst(info, suite_name):
    """Build the RST block for a single test_case need."""
    name = info["name"]
    brief = info["brief"]
    test_id = info["test_id"]
    req_ids = info["req_ids"]
    status = info["status"]
    source_file = info["source_file"]
    doxygen_url = info["doxygen_url"]
    see_rst = info["see_rst"]
    body_sections = info["body_sections"]

    need_id = f"testspec-{suite_name}-{name}"
    # Title: use brief (truncated) if available, else function name
    title = (brief[:90] + "…") if len(brief) > 90 else brief
    if not title:
        title = name

    lines = [f".. test_case:: {title}"]
    lines.append(f"   :id: {need_id}")
    if test_id:
        lines.append(f"   :test_id: {test_id}")
    lines.append(f"   :suite: {suite_name}")
    if source_file:
        lines.append(f"   :source_file: {source_file}")
    if doxygen_url:
        lines.append(f"   :doxygen_url: {doxygen_url}")
    if req_ids:
        # Store as links — sphinx-needs will warn if they don't exist in this build
        lines.append(f"   :links: {' '.join(req_ids)}")
    lines.append("")

    # Body
    if brief:
        lines.append(f"   {brief}")
        lines.append("")

    if see_rst:
        lines.append(f"   {see_rst}")
        lines.append("")

    for section_lines in body_sections:
        for sline in section_lines:
            lines.append(f"   {sline}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Scenario table from testcase.yaml
# ---------------------------------------------------------------------------

def _build_scenario_table(testcase_yaml_path):
    """Return RST lines for a list-table of scenarios from testcase.yaml."""
    try:
        with open(testcase_yaml_path) as f:
            data = yaml.safe_load(f)
    except (OSError, yaml.YAMLError) as e:
        logger.warning(f"testmodule: could not read {testcase_yaml_path}: {e}")
        return []

    scenarios = data.get("tests", {})
    if not scenarios:
        return []

    lines = [
        ".. list-table:: Test Scenarios",
        "   :header-rows: 1",
        "   :widths: 30 25 45",
        "",
        "   * - Scenario",
        "     - Tags",
        "     - Extra config",
    ]
    for scenario_name, scenario_data in scenarios.items():
        tags = ", ".join(scenario_data.get("tags", []))
        extra = ", ".join(scenario_data.get("extra_configs", []))
        lines.append(f"   * - ``{scenario_name}``")
        lines.append(f"     - {tags}")
        lines.append(f"     - {extra or '—'}")
    lines.append("")
    return lines


# ---------------------------------------------------------------------------
# TestModuleDirective
# ---------------------------------------------------------------------------

class TestModuleDirective(Directive):
    """
    Emit sphinx-needs test_case nodes for all ZTEST functions in a module.

    Usage::

        .. testmodule:: tests/kernel/queue
    """

    required_arguments = 1   # module path, e.g. "tests/kernel/queue"
    optional_arguments = 0
    has_content = False
    option_spec = {}

    def run(self):
        module_path = self.arguments[0].strip("/")
        env = self.state.document.settings.env
        app = env.app

        # Paths from conf
        breathe_projects = getattr(app.config, "breathe_projects", {})
        xml_dir = Path(breathe_projects.get("testspec", ""))
        if not xml_dir.is_dir():
            err = self.state_machine.reporter.error(
                f"testmodule: breathe_projects['testspec'] XML dir not found: {xml_dir}",
                nodes.literal_block(module_path, module_path),
                line=self.lineno,
            )
            return [err]

        base_url = getattr(app.config, "html_baseurl", "") or "http://localhost:8000/"
        # Ensure trailing slash
        if not base_url.endswith("/"):
            base_url += "/"

        zephyr_base = Path(os.environ.get("ZEPHYR_BASE", ""))

        # --- Find the module group in Doxygen XML ---
        # Scan all group XMLs for the one whose brief mentions module_path
        module_group_xml = None
        for xml_file in sorted(xml_dir.glob("group__*.xml")):
            tree = ET.parse(xml_file)
            cdef = tree.getroot().find("compounddef")
            if cdef is None:
                continue
            brief = _elem_text(cdef.find(".//briefdescription/para"))
            if module_path in brief:
                module_group_xml = xml_file
                break

        if module_group_xml is None:
            logger.warning(
                f"testmodule: no Doxygen group found mentioning '{module_path}'"
            )
            return [nodes.paragraph(text=f"[testmodule: no group found for {module_path}]")]

        module_tree = ET.parse(module_group_xml)
        module_cdef = module_tree.getroot().find("compounddef")

        # Inner groups = the test suites
        suite_refids = [
            ig.get("refid") for ig in module_cdef.findall("innergroup")
        ]

        # --- Scenario table ---
        testcase_yaml = zephyr_base / module_path / "testcase.yaml"
        scenario_lines = _build_scenario_table(testcase_yaml)

        # --- Collect all test_case RST blocks ---
        all_rst_lines = list(scenario_lines)

        for suite_refid in suite_refids:
            suite_xml = xml_dir / f"{suite_refid}.xml"
            if not suite_xml.exists():
                logger.warning(f"testmodule: suite XML not found: {suite_xml}")
                continue

            suite_tree = ET.parse(suite_xml)
            suite_cdef = suite_tree.getroot().find("compounddef")
            suite_name = suite_cdef.findtext("compoundname", suite_refid)
            compound_id = suite_cdef.get("id", suite_refid)

            # Section heading for this suite
            suite_title = suite_cdef.findtext(".//briefdescription/para", suite_name)
            all_rst_lines.append(suite_title)
            all_rst_lines.append("-" * len(suite_title))
            all_rst_lines.append("")

            for memberdef in suite_cdef.findall(".//memberdef[@kind='function']"):
                info = _parse_memberdef(memberdef, compound_id, base_url)
                if not info["name"]:
                    continue
                need_rst = _build_need_rst(info, suite_name)
                all_rst_lines.extend(need_rst.splitlines())
                all_rst_lines.append("")

        # --- nested_parse ---
        rst_text = "\n".join(all_rst_lines)
        vl = ViewList(rst_text.splitlines(), source="<testmodule>")
        container = nodes.container()
        self.state.nested_parse(vl, self.content_offset, container)
        return container.children


# ---------------------------------------------------------------------------
# TestReportDirective (stub — implemented in Step 5)
# ---------------------------------------------------------------------------

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
            " — Step 5 not yet implemented"
        )
        logger.info(msg)
        return [nodes.paragraph(text=msg)]


# ---------------------------------------------------------------------------
# Extension setup
# ---------------------------------------------------------------------------

def setup(app):
    app.add_directive("testmodule", TestModuleDirective)
    app.add_directive("testreport", TestReportDirective)
    return {"version": "0.2", "parallel_read_safe": True}
