"""Sphinx extension: testmodule and testreport directives (Route B — sphinx-needs)."""

import glob
import json
import os
import re
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
            elif "reqrefs" in xid:
                for _p in xrefsect.findall(".//xrefdescription/para"):
                    _rid = (_p.text or "").strip()
                    if _rid:
                        req_ids.append(_rid)
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


def _build_need_rst(info, suite_name, module_path=""):
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

    # Title: function name with leading "test_" stripped and underscores → spaces
    stem = name[5:] if name.startswith("test_") else name
    title = stem.replace("_", " ")

    if test_id:
        need_id = test_id
    else:
        need_id = f"testspec-{suite_name}-{name}"
        logger.warning(
            f"testmodule: {suite_name}/{name} has no @testid annotation"
        )

    lines = [f".. test_case:: {title}"]
    lines.append(f"   :id: {need_id}")
    lines.append(f"   :test_function: {name}")
    if module_path:
        lines.append(f"   :test_module: {module_path}")
    lines.append(f"   :suite: {suite_name}")
    lines.append(f"   :status: {status}")
    if req_ids:
        lines.append(f"   :verifies: {'; '.join(req_ids)}")
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
                need_rst = _build_need_rst(info, suite_name, module_path)
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
# testreport helpers
# ---------------------------------------------------------------------------

def _slugify(s):
    """Replace non-alphanumeric runs with '-' and strip leading/trailing dashes."""
    return re.sub(r'[^a-zA-Z0-9]+', '-', s).strip('-')


def _find_handler_log(twister_out_dir, platform, toolchain, test_path, scenario_name):
    """Return the Path to handler.log for a (platform, scenario) run, or None.

    Constructs the nominal path from the twister output directory layout:
        {twister_out_dir}/{platform_slug}/{toolchain_slug}/{test_path}/{scenario}/handler.log

    Falls back to a directory scan when the scenario directory was named after an
    older scenario name (stale incremental build cache).
    """
    platform_slug = platform.replace("/", "_")
    toolchain_slug = toolchain.replace("/", "_")
    base = Path(twister_out_dir) / platform_slug / toolchain_slug / test_path
    exact = base / scenario_name / "handler.log"
    if exact.exists():
        return exact
    # Stale-cache fallback: scan for handler.log files under test_path
    candidates = sorted(base.glob("*/handler.log")) if base.exists() else []
    if len(candidates) == 1:
        return candidates[0]
    # Multiple candidates: prefer the directory whose name is a prefix of the scenario
    for c in candidates:
        if scenario_name.startswith(c.parent.name):
            return c
    return None


def _load_spec_lookup(json_path):
    """Read spec needs.json; return {test_function: {id, test_module, suite, req_ids}}."""
    with open(json_path) as f:
        data = json.load(f)
    versions = data.get("versions", {})
    if not versions:
        raise RuntimeError(f"testreport: no versions key in {json_path}")
    current = data.get("current_version") or next(iter(versions))
    needs = versions.get(current, {}).get("needs", {})
    lookup = {}
    for need_id, need in needs.items():
        if need.get("type") != "test_case":
            continue
        fn = need.get("test_function", "")
        if fn:
            lookup[fn] = {
                "id": need_id,
                "test_module": need.get("test_module", ""),
                "suite": need.get("suite", ""),
                "suite_title": need.get("section_name", ""),
                "req_ids": need.get("verifies", []),
            }
    return lookup


def _parse_twister_results(xml_path, module_filter=None):
    """Parse twister_report.xml into a list of result dicts."""
    root = ET.parse(xml_path).getroot()
    results = []
    for ts in root.findall("testsuite"):
        platform = ts.get("name", "")
        for tc in ts.findall("testcase"):
            classname = tc.get("classname", "")
            if module_filter:
                if not (classname == module_filter or classname.startswith(module_filter + ".")):
                    continue
            name = tc.get("name", "")
            scenario = classname
            # strip scenario prefix to get "suite.function"
            suffix = name[len(scenario) + 1:] if name.startswith(scenario + ".") else name
            parts = suffix.rsplit(".", 1)
            suite = parts[0] if len(parts) == 2 else ""
            function = parts[-1]
            failure = tc.find("failure")
            error = tc.find("error")
            skipped = tc.find("skipped")
            if failure is not None:
                status, reason = "failed", failure.get("message", "") or _elem_text(failure)
            elif error is not None:
                status, reason = "error", error.get("message", "") or _elem_text(error)
            elif skipped is not None:
                status, reason = "skipped", skipped.get("message", "") or _elem_text(skipped)
            else:
                status, reason = "passed", ""
            results.append({
                "platform": platform, "scenario": scenario, "suite": suite,
                "function": function, "twister_id": name, "time": tc.get("time", ""),
                "status": status, "reason": reason,
            })
    return results


def _build_result_rst(r, spec_id, test_module, req_ids=None):
    """Build RST block for one test_result need."""
    need_id = f"TR-{_slugify(r['platform'])}-{_slugify(r['scenario'])}-{spec_id}"
    fn = r["function"]
    title = (fn[5:] if fn.startswith("test_") else fn).replace("_", " ")
    lines = [
        f".. test_result:: {title}",
        f"   :id: {need_id}",
        f"   :status: {r['status']}",
    ]
    if test_module:
        lines.append(f"   :test_module: {test_module}")
    lines += [
        f"   :platform: {r['platform']}",
        f"   :scenario: {r['scenario']}",
        f"   :twister_id: {r['twister_id']}",
        f"   :execution_time: {r['time']}",
        f"   :result_of: {spec_id}",
    ]
    if req_ids:
        lines.append(f"   :covers: {'; '.join(req_ids)}")
    if r["reason"]:
        lines.append(f"   :reason: {r['reason']}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# TestReportDirective
# ---------------------------------------------------------------------------

class TestReportDirective(Directive):
    """
    Emit sphinx-needs test_result nodes from a twister_report.xml.

    Usage::

        .. testreport:: /path/to/twister-out/twister_report.xml
           :module: kernel.queue
    """

    required_arguments = 1  # absolute path to twister_report.xml
    optional_arguments = 0
    has_content = False
    option_spec = {
        "module": directives.unchanged,  # classname prefix filter, e.g. "kernel.queue"
    }

    def run(self):
        xml_path = self.arguments[0].strip()
        module_filter = self.options.get("module", "").strip() or None
        env = self.state.document.settings.env
        app = env.app

        if not Path(xml_path).is_absolute():
            base = getattr(app.config, "twister_output_dir", "") or str(
                Path(env.doc2path(env.docname)).parent
            )
            xml_path = str(Path(base) / xml_path)

        ext_needs = getattr(app.config, "needs_external_needs", [])
        spec_json = ext_needs[0].get("json_path", "") if ext_needs else ""
        if not spec_json or not Path(spec_json).exists():
            msg = f"[testreport: spec needs.json not found: {spec_json!r}]"
            logger.warning(f"testreport: {msg}")
            return [nodes.paragraph(text=msg)]

        try:
            spec_lookup = _load_spec_lookup(spec_json)
        except Exception as exc:
            logger.warning(str(exc))
            return [nodes.paragraph(text=str(exc))]

        if not Path(xml_path).exists():
            msg = f"[testreport: twister XML not found: {xml_path}]"
            logger.warning(f"testreport: {msg}")
            return [nodes.paragraph(text=msg)]

        try:
            results = _parse_twister_results(xml_path, module_filter)
        except Exception as exc:
            logger.warning(str(exc))
            return [nodes.paragraph(text=str(exc))]

        if not results:
            return [nodes.paragraph(text="[testreport: no matching results]")]

        # Organize: suite → function (stable insertion order) → result list
        suite_order = []
        func_order = {}  # suite → [functions in order]
        grouped = {}     # (suite, function) → [results]
        seen = set()

        for r in results:
            s, fn = r["suite"], r["function"]
            if s not in func_order:
                suite_order.append(s)
                func_order[s] = []
            if (s, fn) not in seen:
                func_order[s].append(fn)
                seen.add((s, fn))
            grouped.setdefault((s, fn), []).append(r)

        for key in grouped:
            grouped[key].sort(key=lambda r: (r["platform"], r["scenario"]))

        all_rst = []

        for suite in suite_order:
            # Use the human-readable Doxygen group title from the spec (section_name),
            # falling back to a title-cased derivation when the suite has no known functions.
            suite_title = next(
                (
                    (spec_lookup.get(fn) or spec_lookup.get("test_" + fn) or {}).get("suite_title")
                    for fn in func_order[suite]
                    if (spec_lookup.get(fn) or spec_lookup.get("test_" + fn) or {}).get("suite_title")
                ),
                None,
            )
            heading = suite_title or suite.replace("_", " ").title()
            all_rst += [heading, "-" * len(heading), ""]

            for fn in func_order[suite]:
                # Twister XML omits the leading test_ prefix; try both forms
                info = spec_lookup.get(fn) or spec_lookup.get("test_" + fn)
                if info is None:
                    logger.warning(f"testreport: '{fn}' not in spec needs.json — skipped")
                    continue
                for r in grouped[(suite, fn)]:
                    all_rst += _build_result_rst(
                        r, info["id"], info["test_module"], info.get("req_ids")
                    ).splitlines()
                    all_rst.append("")

        # Summary needtable filtered by test_module
        modules = sorted({
            (spec_lookup.get(fn) or spec_lookup.get("test_" + fn) or {}).get("test_module", "")
            for _, fn in grouped
        } - {""})
        if len(modules) == 1:
            tbl_filter = f'type == "test_result" and test_module == "{modules[0]}"'
        else:
            tbl_filter = 'type == "test_result"'

        summary_heading = "Result summary"
        all_rst += [
            "----", "",
            summary_heading, "-" * len(summary_heading), "",
            ".. needtable::",
            f'   :filter: {tbl_filter}',
            "   :columns: id, title, test_module, platform, scenario, status, execution_time, result_of",
            "   :style: table",
            "",
        ]

        # Execution logs — one subsection per (scenario, platform), sorted
        twister_out_dir = getattr(app.config, "twister_output_dir", "")
        twister_json = Path(twister_out_dir) / "twister.json" if twister_out_dir else None
        if twister_json and twister_json.exists():
            try:
                with open(twister_json) as f:
                    tw = json.load(f)
                # Collect matching (scenario, platform, path, toolchain) entries
                log_entries = []
                for ts in tw.get("testsuites", []):
                    sname = ts["name"]
                    if module_filter and not (
                        sname == module_filter or sname.startswith(module_filter + ".")
                    ):
                        continue
                    log_entries.append((
                        sname,
                        ts["platform"],
                        ts.get("path", ""),
                        ts.get("toolchain", ""),
                    ))
                log_entries.sort()

                if log_entries:
                    all_rst += ["----", "", "Execution Logs", "-" * len("Execution Logs"), ""]
                    for scenario, platform, test_path, toolchain in log_entries:
                        sub = f"{scenario} — {platform}"
                        all_rst += [sub, "~" * len(sub), ""]
                        log_file = _find_handler_log(
                            twister_out_dir, platform, toolchain, test_path, scenario
                        )
                        if log_file:
                            all_rst += [".. code-block:: none", ""]
                            for line in log_file.read_text(errors="replace").splitlines():
                                all_rst.append("   " + line)
                            all_rst.append("")
                        else:
                            all_rst += [
                                f"*handler.log not found for* ``{scenario}`` *on* ``{platform}``",
                                "",
                            ]
            except Exception as exc:
                logger.warning(f"testreport: could not load execution logs: {exc}")

        vl = ViewList(all_rst, source="<testreport>")
        container = nodes.container()
        self.state.nested_parse(vl, self.content_offset, container, match_titles=True)
        return container.children


# ---------------------------------------------------------------------------
# twisterinfo directive
# ---------------------------------------------------------------------------

class TwisterInfoDirective(Directive):
    """Emit a run-metadata block and per-platform summary table from twister.json.

    Usage::

        .. twisterinfo:: /path/to/twister-out/twister.json
    """

    required_arguments = 1
    optional_arguments = 0
    has_content = False
    option_spec = {}

    def run(self):
        json_path = self.arguments[0].strip()
        env = self.state.document.settings.env
        app = env.app

        if not Path(json_path).is_absolute():
            base = getattr(app.config, "twister_output_dir", "") or str(
                Path(env.doc2path(env.docname)).parent
            )
            json_path = str(Path(base) / json_path)

        if not Path(json_path).exists():
            msg = f"[twisterinfo: twister.json not found: {json_path!r}]"
            logger.warning(f"twisterinfo: {msg}")
            return [nodes.paragraph(text=msg)]

        try:
            with open(json_path) as f:
                data = json.load(f)
        except Exception as exc:
            logger.warning(f"twisterinfo: cannot read {json_path}: {exc}")
            return [nodes.paragraph(text=str(exc))]

        env = data.get("environment", {})
        suites = data.get("testsuites", [])

        # --- Normalise run date ---
        run_date_raw = env.get("run_date", "")
        try:
            from datetime import datetime, timezone
            dt = datetime.fromisoformat(run_date_raw)
            run_date = dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        except Exception:
            run_date = run_date_raw

        zephyr_version = env.get("zephyr_version", "—")
        toolchain = env.get("toolchain", "—")
        host_os = env.get("os", "—")

        # Scenarios: unique scenario names from testsuites (deduplicated, sorted)
        scenarios = sorted({s["name"] for s in suites})

        # Platforms: unique platforms (sorted)
        platforms = sorted({s["platform"] for s in suites})

        # --- Per-platform counts ---
        from collections import defaultdict, Counter
        by_platform = defaultdict(list)
        for s in suites:
            by_platform[s["platform"]].extend(s.get("testcases", []))
        platform_stats = []
        total_passed = total_failed = total_skipped = total_error = 0
        for plat in platforms:
            tcs = by_platform[plat]
            counts = Counter(tc.get("status", "") for tc in tcs)
            p, f, s, e = (counts.get("passed", 0), counts.get("failed", 0),
                          counts.get("skipped", 0), counts.get("error", 0))
            total_passed += p
            total_failed += f
            total_skipped += s
            total_error += e
            platform_stats.append((plat, p, f, s, e, len(tcs)))

        # --- Build RST ---
        lines = []

        # Metadata field list (list-table for consistent rendering)
        lines += [
            ".. list-table:: Test Run Metadata",
            "   :header-rows: 0",
            "   :widths: 25 75",
            "",
            f"   * - Run date",
            f"     - {run_date}",
            f"   * - Zephyr version",
            f"     - ``{zephyr_version}``",
            f"   * - Toolchain",
            f"     - {toolchain}",
            f"   * - Host OS",
            f"     - {host_os}",
            f"   * - Test scenarios",
            f"     - {', '.join(f'``{s}``' for s in scenarios)}",
            f"   * - Platforms",
            f"     - {', '.join(f'``{p}``' for p in platforms)}",
            f"   * - Total test cases",
            f"     - {total_passed + total_failed + total_skipped + total_error}"
            f" (passed: {total_passed}"
            + (f", failed: {total_failed}" if total_failed else "")
            + (f", skipped: {total_skipped}" if total_skipped else "")
            + (f", error: {total_error}" if total_error else "")
            + ")",
            "",
        ]

        # Per-platform summary table
        lines += [
            ".. list-table:: Results per Platform",
            "   :header-rows: 1",
            "   :widths: 50 15 15 10 10",
            "",
            "   * - Platform",
            "     - Passed",
            "     - Failed",
            "     - Skipped",
            "     - Total",
        ]
        for plat, p, f, s, e, total in platform_stats:
            lines += [
                f"   * - ``{plat}``",
                f"     - {p}",
                f"     - {f + e}",
                f"     - {s}",
                f"     - {total}",
            ]
        lines.append("")

        vl = ViewList(lines, source="<twisterinfo>")
        container = nodes.container()
        self.state.nested_parse(vl, self.content_offset, container)
        return container.children


# ---------------------------------------------------------------------------
# Extension setup
# ---------------------------------------------------------------------------

def setup(app):
    app.add_config_value("testspec_doxygen_url", "", "env")
    app.add_config_value("api_doxygen_url", "", "env")
    app.add_config_value("requirements_url", "", "env")
    app.add_config_value("twister_output_dir", "", "env")
    app.add_directive("testmodule", TestModuleDirective)
    app.add_directive("testreport", TestReportDirective)
    app.add_directive("twisterinfo", TwisterInfoDirective)
    return {"version": "0.2", "parallel_read_safe": True}
