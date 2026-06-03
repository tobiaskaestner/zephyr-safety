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
        if child.tag in ("xrefsect", "simplesect", "orderedlist", "itemizedlist", "parameterlist"):
            pass  # skip structural children
        elif child.tag == "computeroutput":
            t = _elem_text(child)
            if t.endswith("()"):
                parts.append(f":c:func:`{t[:-2]}`")
            else:
                parts.append(f"``{t}``")
        elif child.tag in ("bold", "emphasis"):
            parts.append(_elem_text(child))
        elif child.tag == "ref":
            kindref = child.get("kindref", "")
            t = (child.text or "").strip()
            if kindref == "member" and t:
                parts.append(f":c:func:`{t.rstrip('()').strip()}`")
            else:
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
        lines.append(f".. rubric:: {title}")
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


def _see_to_rst(simplesect_see, api_html_dir):
    """
    Convert a <simplesect kind="see"> to a 'See also:' RST line.
    API refs (external attribute pointing to safety-api tag) get local file:// URLs.
    Non-API member refs are rendered as :c:func: roles.
    """
    refs = []
    for ref in simplesect_see.findall(".//ref"):
        name = (ref.text or "").strip()
        if not name:
            continue
        refid = ref.get("refid", "")
        external = ref.get("external", "")
        kindref = ref.get("kindref", "")
        if refid and "_1" in refid:
            idx = refid.index("_1")
            compound = refid[:idx]
            anchor = refid[idx + 2:]
            if "zephyr-safety-api" in external:
                url = f"{api_html_dir}/{compound}.html#{anchor}"
                refs.append(f"`{name} <{url}>`__")
            elif kindref == "member":
                func_name = name.rstrip("()").strip()
                refs.append(f":c:func:`{func_name}`")
            else:
                refs.append(f"``{name}``")
        else:
            refs.append(f":c:func:`{name.rstrip('()').strip()}`")
    if refs:
        return "**See also:** " + ", ".join(refs)
    return ""


# ---------------------------------------------------------------------------
# Doxygen XML extraction
# ---------------------------------------------------------------------------

def _parse_memberdef(memberdef, compound_id, testspec_html_dir, api_html_dir):
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

    # Doxygen HTML URL (local file:// into testspec doxygen output)
    member_id = memberdef.get("id", "")
    prefix = compound_id + "_1"
    anchor = member_id[len(prefix):] if member_id.startswith(prefix) else member_id
    doxygen_url = f"{testspec_html_dir}/{compound_id}.html#{anchor}"

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
            see_rst = _see_to_rst(see_sect, api_html_dir)

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
    # Title: function name with leading "test_" stripped and underscores → spaces
    stem = name[5:] if name.startswith("test_") else name
    title = stem.replace("_", " ")

    if not test_id:
        logger.warning(
            f"testmodule: {suite_name}/{name} has no @testid annotation"
        )

    lines = [f".. test_case:: {title}"]
    lines.append(f"   :id: {need_id}")
    if test_id:
        lines.append(f"   :test_id: {test_id}")
    lines.append(f"   :test_function: {name}")
    lines.append(f"   :suite: {suite_name}")
    lines.append(f"   :status: {status}")
    if req_ids:
        lines.append(f"   :links: {' '.join(req_ids)}")
    lines.append("")

    # Body: Arrange/Act/Assert first, Source and See also at the bottom
    for section_lines in body_sections:
        for sline in section_lines:
            lines.append(f"   {sline}")
        lines.append("")

    if source_file and doxygen_url:
        lines.append(f"   **Source:** `{source_file} <{doxygen_url}>`__")
        lines.append("")
    elif source_file:
        lines.append(f"   **Source:** {source_file}")
        lines.append("")

    if see_rst:
        lines.append(f"   {see_rst}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Shared test procedure helpers
# ---------------------------------------------------------------------------

def _extract_params(detaileddesc):
    """Return list of (name, description) pairs from a parameterlist in detaileddesc."""
    params = []
    for pl in detaileddesc.findall(".//parameterlist[@kind='param']"):
        for item in pl.findall("parameteritem"):
            names = [
                (n.text or "").strip()
                for n in item.findall(".//parametername")
            ]
            name = ", ".join(n for n in names if n)
            desc = " ".join(
                _para_text(p)
                for p in item.findall(".//parameterdescription/para")
            ).strip()
            if name:
                params.append((name, desc))
    return params


def _check_no_ztest_members(proc_cdef):
    """Warn if a group ending in _procedures contains ZTEST-annotated functions."""
    proc_name = proc_cdef.findtext("compoundname", "")
    for md in proc_cdef.findall(".//memberdef[@kind='function']"):
        fn_name = md.findtext("name", "")
        dd = md.find("detaileddescription")
        if dd is not None:
            for x in dd.findall(".//xrefsect"):
                if "testids" in x.get("id", ""):
                    logger.warning(
                        f"testmodule: procedure group '{proc_name}' contains "
                        f"ZTEST-annotated function '{fn_name}' — check @ingroup annotations"
                    )


def _build_procedure_need_rst(memberdef, proc_compound_id, proc_group_name, testspec_html_dir, api_html_dir):
    """Build a test_procedure needs item for one shared test procedure."""
    name = memberdef.findtext("name", "").strip()
    need_id = f"test-proc-{proc_group_name}-{name}"

    brief = _para_text(memberdef.find(".//briefdescription/para"))
    title = (brief[:90] + "…") if len(brief) > 90 else brief
    if not title:
        title = name

    # Source location
    loc = memberdef.find("location")
    source_file = ""
    if loc is not None:
        fpath = loc.get("bodyfile") or loc.get("file", "")
        line = loc.get("bodystart") or loc.get("line", "")
        if fpath:
            source_file = f"{Path(fpath).name} (line {line})"

    # Doxygen URL
    member_id = memberdef.get("id", "")
    prefix = proc_compound_id + "_1"
    anchor = member_id[len(prefix):] if member_id.startswith(prefix) else member_id
    doxygen_url = f"{testspec_html_dir}/{proc_compound_id}.html#{anchor}"

    # Detailed description prose and parameters
    dd = memberdef.find("detaileddescription")
    detail_lines = []
    params = []
    see_rst = ""
    if dd is not None:
        params = _extract_params(dd)
        for para in dd.findall("para"):
            text = _para_text(para).strip()
            if text:
                detail_lines.append(text)
        see_sect = dd.find(".//simplesect[@kind='see']")
        if see_sect is not None:
            see_rst = _see_to_rst(see_sect, api_html_dir)

    lines = []
    lines.append(f".. test_procedure:: {title}")
    lines.append(f"   :id: {need_id}")
    lines.append(f"   :status: active")
    lines.append("")

    # Body: prose, params, source link, see also
    for text in detail_lines:
        lines.append(f"   {text}")
        lines.append("")

    if params:
        for pname, pdesc in params:
            lines.append(f"   :``{pname}``: {pdesc}")
        lines.append("")

    if source_file and doxygen_url:
        lines.append(
            f"   **Source:** :c:func:`{name}` — `{source_file} <{doxygen_url}>`__"
        )
        lines.append("")

    if see_rst:
        lines.append(f"   {see_rst}")
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

    heading = "Test Scenarios"
    lines = [
        heading,
        "-" * len(heading),
        "",
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

def _load_group_index(xml_dir):
    """Parse index.xml and return a dict mapping group name → refid."""
    index_file = xml_dir / "index.xml"
    try:
        root = ET.parse(index_file).getroot()
    except (OSError, ET.ParseError) as e:
        raise RuntimeError(f"testmodule: cannot parse {index_file}: {e}") from e
    return {
        c.findtext("name"): c.get("refid")
        for c in root.findall("compound[@kind='group']")
    }


class TestModuleDirective(Directive):
    """
    Emit sphinx-needs test_case nodes for all ZTEST functions in a module group.

    Usage::

        .. testmodule:: kernel_queue_module
           :module: tests/kernel/queue
    """

    required_arguments = 1   # Doxygen group name, e.g. "kernel_queue_module"
    optional_arguments = 0
    has_content = False
    option_spec = {
        # Relative path from ZEPHYR_BASE to the module dir (for testcase.yaml lookup)
        "module": directives.unchanged,
    }

    def run(self):
        group_name = self.arguments[0].strip()
        module_path = self.options.get("module", "").strip("/")
        env = self.state.document.settings.env
        app = env.app

        # Paths from conf
        breathe_projects = getattr(app.config, "breathe_projects", {})
        xml_dir = Path(breathe_projects.get("testspec", ""))
        if not xml_dir.is_dir():
            err = self.state_machine.reporter.error(
                f"testmodule: breathe_projects['testspec'] XML dir not found: {xml_dir}",
                nodes.literal_block(group_name, group_name),
                line=self.lineno,
            )
            return [err]

        # conf.py gives URLs relative to the HTML output root; adjust for page depth.
        page_depth = len(Path(env.docname).parts) - 1
        page_prefix = "../" * page_depth
        testspec_html_dir = page_prefix + app.config.testspec_doxygen_url
        api_html_dir = page_prefix + app.config.api_doxygen_url

        zephyr_base = Path(os.environ.get("ZEPHYR_BASE", ""))

        # --- Resolve module group via index.xml (O(1) lookup, no full scan) ---
        # Cache the index on env so parallel workers parse it at most once per build.
        if not hasattr(env, "_testmodule_group_index"):
            try:
                env._testmodule_group_index = _load_group_index(xml_dir)
            except RuntimeError as exc:
                logger.warning(str(exc))
                return [nodes.paragraph(text=str(exc))]

        group_index = env._testmodule_group_index
        module_refid = group_index.get(group_name)
        if module_refid is None:
            logger.warning(
                f"testmodule: Doxygen group '{group_name}' not found in index.xml"
            )
            return [nodes.paragraph(text=f"[testmodule: group '{group_name}' not in Doxygen index]")]

        module_group_xml = xml_dir / f"{module_refid}.xml"
        if not module_group_xml.exists():
            logger.warning(f"testmodule: XML file not found for group '{group_name}': {module_group_xml}")
            return [nodes.paragraph(text=f"[testmodule: XML missing for '{group_name}']")]

        module_tree = ET.parse(module_group_xml)
        module_cdef = module_tree.getroot().find("compounddef")

        # Classify module inner groups: suites vs procedure groups (by _procedures suffix)
        suite_refids = []
        proc_refids = []
        for ig in module_cdef.findall("innergroup"):
            refid = ig.get("refid")
            ig_xml = xml_dir / f"{refid}.xml"
            if not ig_xml.exists():
                logger.warning(f"testmodule: inner group XML not found: {ig_xml}")
                continue
            ig_cdef = ET.parse(ig_xml).getroot().find("compounddef")
            if ig_cdef.findtext("compoundname", "").endswith("_procedures"):
                proc_refids.append(refid)
            else:
                suite_refids.append(refid)

        # --- Scenario table ---
        testcase_yaml = zephyr_base / module_path / "testcase.yaml"
        scenario_lines = _build_scenario_table(testcase_yaml)

        # --- Test suite sections ---
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

            suite_title = suite_cdef.findtext("title", suite_name)
            all_rst_lines.append(suite_title)
            all_rst_lines.append("-" * len(suite_title))
            all_rst_lines.append("")

            for memberdef in suite_cdef.findall(".//memberdef[@kind='function']"):
                info = _parse_memberdef(memberdef, compound_id, testspec_html_dir, api_html_dir)
                if not info["name"]:
                    continue
                need_rst = _build_need_rst(info, suite_name)
                all_rst_lines.extend(need_rst.splitlines())
                all_rst_lines.append("")

        # --- Procedure sections (siblings of suites) ---
        for proc_refid in proc_refids:
            proc_xml = xml_dir / f"{proc_refid}.xml"
            proc_tree = ET.parse(proc_xml)
            proc_cdef = proc_tree.getroot().find("compounddef")
            proc_compound_id = proc_cdef.get("id", proc_refid)
            proc_group_name = proc_cdef.findtext("compoundname", proc_refid)
            proc_heading = proc_cdef.findtext("title", "Shared Test Procedures")

            _check_no_ztest_members(proc_cdef)

            all_rst_lines.append(proc_heading)
            all_rst_lines.append("-" * len(proc_heading))
            all_rst_lines.append("")

            for md in proc_cdef.findall(".//memberdef[@kind='function']"):
                proc_rst = _build_procedure_need_rst(
                    md, proc_compound_id, proc_group_name, testspec_html_dir, api_html_dir
                )
                all_rst_lines.extend(proc_rst.splitlines())
                all_rst_lines.append("")

        # --- nested_parse ---
        rst_text = "\n".join(all_rst_lines)
        vl = ViewList(rst_text.splitlines(), source="<testmodule>")
        container = nodes.container()
        self.state.nested_parse(vl, self.content_offset, container, match_titles=True)
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
    app.add_config_value("testspec_doxygen_url", "", "env")
    app.add_config_value("api_doxygen_url", "", "env")
    app.add_config_value("requirements_url", "", "env")
    app.add_directive("testmodule", TestModuleDirective)
    app.add_directive("testreport", TestReportDirective)
    return {"version": "0.2", "parallel_read_safe": True}
