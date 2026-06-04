"""Sphinx extension: testmodule and testreport directives (Route B — sphinx-needs)."""
import json
import os
from collections import Counter, defaultdict
from pathlib import Path

from docutils import nodes
from docutils.parsers.rst import Directive, directives
from docutils.statemachine import ViewList
from sphinx.util import logging
import xml.etree.ElementTree as ET

from doxygen_parser import load_group_index, parse_memberdef
from rst_builders import (
    build_need_rst,
    build_procedure_need_rst,
    build_result_rst,
    build_scenario_table,
)
from twister_reader import (
    find_handler_log,
    load_spec_lookup,
    load_twister_meta,
    parse_twister_results,
)

logger = logging.getLogger(__name__)


def _check_no_ztest_members(proc_cdef: ET.Element) -> None:
    """Warn if a procedure group contains ZTEST-annotated functions."""
    proc_name = proc_cdef.findtext("compoundname", "")
    for md in proc_cdef.findall("sectiondef/memberdef[@kind='function']"):
        fn_name = md.findtext("name", "")
        dd = md.find("detaileddescription")
        if dd is not None:
            for x in dd.findall("para/xrefsect"):
                if "testids" in x.get("id", ""):
                    logger.warning(
                        f"testmodule: procedure group '{proc_name}' contains "
                        f"ZTEST-annotated function '{fn_name}' — check @ingroup annotations"
                    )


# ---------------------------------------------------------------------------
# TestModuleDirective
# ---------------------------------------------------------------------------

class TestModuleDirective(Directive):
    """
    Emit sphinx-needs test_case nodes for all ZTEST functions in a module group.

    Usage::

        .. testmodule:: kernel_queue_module
           :module: tests/kernel/queue
    """

    required_arguments = 1
    optional_arguments = 0
    has_content = False
    option_spec = {
        "module": directives.unchanged,
    }

    def run(self):
        group_name = self.arguments[0].strip()
        module_path = self.options.get("module", "").strip("/")
        env = self.state.document.settings.env
        app = env.app

        breathe_projects = getattr(app.config, "breathe_projects", {})
        xml_dir = Path(breathe_projects.get("testspec", ""))
        if not xml_dir.is_dir():
            err = self.state_machine.reporter.error(
                f"testmodule: breathe_projects['testspec'] XML dir not found: {xml_dir}",
                nodes.literal_block(group_name, group_name),
                line=self.lineno,
            )
            return [err]

        page_depth = len(Path(env.docname).parts) - 1
        page_prefix = "../" * page_depth
        testspec_html_dir = page_prefix + app.config.testspec_doxygen_url
        api_html_dir = page_prefix + app.config.api_doxygen_url

        zephyr_base = Path(os.environ.get("ZEPHYR_BASE", ""))

        # Cache the group index on env so parallel workers parse it at most once.
        if not hasattr(env, "_testmodule_group_index"):
            try:
                env._testmodule_group_index = load_group_index(xml_dir)
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

        testcase_yaml = zephyr_base / module_path / "testcase.yaml"
        scenario_lines = build_scenario_table(testcase_yaml)

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
                info = parse_memberdef(memberdef, compound_id, testspec_html_dir, api_html_dir)
                if not info["name"]:
                    continue
                need_rst = build_need_rst(info, suite_name, module_path)
                all_rst_lines.extend(need_rst.splitlines())
                all_rst_lines.append("")

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
                proc_rst = build_procedure_need_rst(
                    md, proc_compound_id, proc_group_name, testspec_html_dir, api_html_dir
                )
                all_rst_lines.extend(proc_rst.splitlines())
                all_rst_lines.append("")

        rst_text = "\n".join(all_rst_lines)
        vl = ViewList(rst_text.splitlines(), source="<testmodule>")
        container = nodes.container()
        self.state.nested_parse(vl, self.content_offset, container, match_titles=True)
        return container.children


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

    required_arguments = 1
    optional_arguments = 0
    has_content = False
    option_spec = {
        "module": directives.unchanged,
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
            spec_lookup = load_spec_lookup(spec_json)
        except Exception as exc:
            logger.warning(str(exc))
            return [nodes.paragraph(text=str(exc))]

        if not Path(xml_path).exists():
            msg = f"[testreport: twister XML not found: {xml_path}]"
            logger.warning(f"testreport: {msg}")
            return [nodes.paragraph(text=msg)]

        try:
            results = parse_twister_results(xml_path, module_filter)
        except Exception as exc:
            logger.warning(str(exc))
            return [nodes.paragraph(text=str(exc))]

        if not results:
            return [nodes.paragraph(text="[testreport: no matching results]")]

        suite_order = []
        func_order = {}
        grouped = {}
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
                info = spec_lookup.get(fn) or spec_lookup.get("test_" + fn)
                if info is None:
                    logger.warning(f"testreport: '{fn}' not in spec needs.json — skipped")
                    continue
                for r in grouped[(suite, fn)]:
                    all_rst += build_result_rst(
                        r, info["id"], info["test_module"], info.get("req_ids")
                    ).splitlines()
                    all_rst.append("")

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

        twister_out_dir = getattr(app.config, "twister_output_dir", "")
        twister_json = Path(twister_out_dir) / "twister.json" if twister_out_dir else None
        if twister_json and twister_json.exists():
            try:
                tw = load_twister_meta(twister_json)
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
                        log_file = find_handler_log(
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
# TwisterInfoDirective
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
            data = load_twister_meta(json_path)
        except Exception as exc:
            logger.warning(f"twisterinfo: cannot read {json_path}: {exc}")
            return [nodes.paragraph(text=str(exc))]

        tw_env = data.get("environment", {})
        suites = data.get("testsuites", [])

        run_date_raw = tw_env.get("run_date", "")
        try:
            from datetime import datetime, timezone
            dt = datetime.fromisoformat(run_date_raw)
            run_date = dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        except Exception:
            run_date = run_date_raw

        zephyr_version = tw_env.get("zephyr_version", "—")
        toolchain = tw_env.get("toolchain", "—")
        host_os = tw_env.get("os", "—")

        scenarios = sorted({s["name"] for s in suites})
        platforms = sorted({s["platform"] for s in suites})

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

        lines = []
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
