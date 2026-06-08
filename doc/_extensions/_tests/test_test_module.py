"""Tests for test_module.py — helper functions and Sphinx directive integration."""
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

import test_module as tm
from conftest import FIXTURES

_ROOTS = Path(__file__).parent / "roots"

DOXYGEN = FIXTURES / "doxygen"
TWISTER = FIXTURES / "twister"
NEEDS   = FIXTURES / "needs"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_result(**kwargs):
    defaults = {
        "platform": "qemu_cortex_m3/ti_lm3s6965",
        "scenario": "kernel.queue",
        "suite": "kernel.queue",
        "function": "queue_put",
        "twister_id": "kernel.queue.kernel.queue.test_queue_put",
        "time": "0.123",
        "status": "passed",
        "reason": "",
    }
    defaults.update(kwargs)
    return defaults


def _spec_lookup():
    return {
        "test_queue_put": {
            "id": "TSPEC-QUEUE-API-001",
            "test_module": "tests/kernel/queue",
            "suite": "kernel.queue",
            "suite_title": "Queue API ZTest suite",
            "req_ids": ["zep-srs-20-1"],
        },
        "test_queue_get": {
            "id": "TSPEC-QUEUE-API-002",
            "test_module": "tests/kernel/queue",
            "suite": "kernel.queue",
            "suite_title": "Queue API ZTest suite",
            "req_ids": [],
        },
    }


# ---------------------------------------------------------------------------
# _group_results
# ---------------------------------------------------------------------------

def test_group_results_suite_order():
    results = [
        _make_result(suite="suite_b", function="fn1"),
        _make_result(suite="suite_a", function="fn2"),
    ]
    suite_order, _, _ = tm._group_results(results)
    assert suite_order == ["suite_b", "suite_a"]


def test_group_results_function_dedup():
    results = [
        _make_result(suite="s", function="fn", platform="qemu_a"),
        _make_result(suite="s", function="fn", platform="qemu_b"),
    ]
    _, func_order, _ = tm._group_results(results)
    assert func_order["s"] == ["fn"]


def test_group_results_grouped_by_suite_and_function():
    r1 = _make_result(suite="s", function="f", platform="p1", scenario="sc")
    r2 = _make_result(suite="s", function="f", platform="p2", scenario="sc")
    _, _, grouped = tm._group_results([r1, r2])
    assert len(grouped[("s", "f")]) == 2


def test_group_results_sorted_by_platform_scenario():
    results = [
        _make_result(suite="s", function="f", platform="zzz", scenario="sc"),
        _make_result(suite="s", function="f", platform="aaa", scenario="sc"),
    ]
    _, _, grouped = tm._group_results(results)
    platforms = [r["platform"] for r in grouped[("s", "f")]]
    assert platforms == ["aaa", "zzz"]


# ---------------------------------------------------------------------------
# _build_results_rst
# ---------------------------------------------------------------------------

def test_build_results_rst_suite_heading_from_suite_title():
    suite_order = ["kernel.queue"]
    func_order = {"kernel.queue": ["queue_put"]}
    grouped = {("kernel.queue", "queue_put"): [_make_result()]}
    lines = tm._build_results_rst(suite_order, func_order, grouped, _spec_lookup())
    assert any("Queue API ZTest suite" in l for l in lines)


def test_build_results_rst_suite_heading_titlecase_fallback():
    suite_order = ["queue_api_1cpu"]
    func_order = {"queue_api_1cpu": ["queue_put"]}
    grouped = {("queue_api_1cpu", "queue_put"): [_make_result(suite="queue_api_1cpu")]}
    lookup = {"test_queue_put": {**_spec_lookup()["test_queue_put"], "suite_title": ""}}
    lines = tm._build_results_rst(suite_order, func_order, grouped, lookup)
    assert any("Queue Api 1Cpu" in l for l in lines)


def test_build_results_rst_unknown_function_skipped():
    suite_order = ["s"]
    func_order = {"s": ["unknown_fn"]}
    grouped = {("s", "unknown_fn"): [_make_result(function="unknown_fn")]}
    lines = tm._build_results_rst(suite_order, func_order, grouped, _spec_lookup())
    assert not any("TR-" in l for l in lines)


def test_build_results_rst_test_prefix_lookup_fallback():
    # spec_lookup keyed as "test_queue_put"; result function is "queue_put" (prefix stripped)
    suite_order = ["s"]
    func_order = {"s": ["queue_put"]}
    grouped = {("s", "queue_put"): [_make_result()]}
    lines = tm._build_results_rst(suite_order, func_order, grouped, _spec_lookup())
    assert any("TSPEC-QUEUE-API-001" in l for l in lines)


# ---------------------------------------------------------------------------
# _build_summary_table_rst
# ---------------------------------------------------------------------------

def test_build_summary_table_single_module_filter():
    grouped = {("s", "queue_put"): [_make_result()]}
    lines = tm._build_summary_table_rst(grouped, _spec_lookup())
    assert any('test_module == "tests/kernel/queue"' in l for l in lines)


def test_build_summary_table_multi_module_generic_filter():
    lookup = {
        **_spec_lookup(),
        "test_other": {
            "id": "TSPEC-OTHER-001",
            "test_module": "tests/kernel/other",
            "suite": "s",
            "suite_title": "",
            "req_ids": [],
        },
    }
    grouped = {
        ("s", "queue_put"): [_make_result()],
        ("s", "other"): [_make_result(function="other")],
    }
    lines = tm._build_summary_table_rst(grouped, lookup)
    assert any('type == "test_result"' in l and "test_module" not in l for l in lines)


# ---------------------------------------------------------------------------
# _build_exec_logs_rst
# ---------------------------------------------------------------------------

def test_build_exec_logs_rst_empty_dir_returns_empty():
    assert tm._build_exec_logs_rst("", "kernel.queue") == []


def test_build_exec_logs_rst_missing_json_returns_empty(tmp_path):
    assert tm._build_exec_logs_rst(str(tmp_path), "kernel.queue") == []


def test_build_exec_logs_rst_returns_heading():
    lines = tm._build_exec_logs_rst(str(TWISTER), "kernel.queue")
    assert any("Execution Logs" in l for l in lines)


def test_build_exec_logs_rst_includes_scenario_entries():
    lines = tm._build_exec_logs_rst(str(TWISTER), "kernel.queue")
    text = "\n".join(lines)
    assert "kernel.queue" in text
    assert "qemu_cortex_m3/ti_lm3s6965" in text


def test_build_exec_logs_rst_module_filter_excludes_unrelated(tmp_path):
    import json, shutil
    shutil.copy(TWISTER / "twister.json", tmp_path / "twister.json")
    lines = tm._build_exec_logs_rst(str(tmp_path), "kernel.other")
    assert lines == []


# ---------------------------------------------------------------------------
# _compute_platform_stats
# ---------------------------------------------------------------------------

def test_compute_platform_stats_counts():
    suites = [
        {"platform": "plat_a", "testcases": [
            {"status": "passed"}, {"status": "passed"}, {"status": "failed"},
        ]},
        {"platform": "plat_b", "testcases": [
            {"status": "skipped"},
        ]},
    ]
    platforms, stats, totals = tm._compute_platform_stats(suites)
    assert platforms == ["plat_a", "plat_b"]
    a = next(s for s in stats if s[0] == "plat_a")
    assert a[1] == 2  # passed
    assert a[2] == 1  # failed


def test_compute_platform_stats_totals():
    suites = [{"platform": "p", "testcases": [
        {"status": "passed"}, {"status": "failed"}, {"status": "error"}, {"status": "skipped"},
    ]}]
    _, _, totals = tm._compute_platform_stats(suites)
    assert totals == (1, 1, 1, 1)


def test_compute_platform_stats_empty():
    platforms, stats, totals = tm._compute_platform_stats([])
    assert platforms == []
    assert stats == []
    assert totals == (0, 0, 0, 0)


# ---------------------------------------------------------------------------
# _build_twisterinfo_rst
# ---------------------------------------------------------------------------

def test_build_twisterinfo_rst_metadata_rows():
    tw_env = {
        "run_date": "2026-06-01T10:00:00+00:00",
        "zephyr_version": "3.7.0",
        "toolchain": "zephyr-sdk-0.17.0",
        "os": "linux",
    }
    suites = [{"platform": "plat", "name": "kernel.queue", "testcases": [{"status": "passed"}]}]
    lines = tm._build_twisterinfo_rst(tw_env, suites)
    text = "\n".join(lines)
    assert "2026-06-01 10:00:00 UTC" in text
    assert "3.7.0" in text
    assert "zephyr-sdk-0.17.0" in text
    assert "linux" in text


def test_build_twisterinfo_rst_platform_table():
    tw_env = {"run_date": "", "zephyr_version": "", "toolchain": "", "os": ""}
    suites = [{"platform": "qemu_a", "name": "sc", "testcases": [
        {"status": "passed"}, {"status": "failed"},
    ]}]
    lines = tm._build_twisterinfo_rst(tw_env, suites)
    text = "\n".join(lines)
    assert "qemu_a" in text
    assert "Results per Platform" in text


def test_build_twisterinfo_rst_invalid_date_passthrough():
    tw_env = {"run_date": "not-a-date", "zephyr_version": "", "toolchain": "", "os": ""}
    lines = tm._build_twisterinfo_rst(tw_env, [])
    assert any("not-a-date" in l for l in lines)


# ---------------------------------------------------------------------------
# _classify_inner_groups
# ---------------------------------------------------------------------------

def test_classify_inner_groups_splits_suites_and_procs():
    module_cdef = ET.parse(DOXYGEN / "group__kernel__queue__module.xml").getroot().find("compounddef")
    suite_refids, proc_refids = tm._classify_inner_groups(module_cdef, DOXYGEN)
    assert suite_refids == ["group__queue__api"]
    assert proc_refids == ["group__queue__procedures"]


def test_classify_inner_groups_skips_missing_xml(tmp_path, caplog):
    module_cdef = ET.fromstring(
        "<compounddef><innergroup refid='group__missing'>missing</innergroup></compounddef>"
    )
    suite_refids, proc_refids = tm._classify_inner_groups(module_cdef, tmp_path)
    assert suite_refids == []
    assert proc_refids == []


# ---------------------------------------------------------------------------
# _build_suite_rst
# ---------------------------------------------------------------------------

def test_build_suite_rst_heading_from_doxygen_title():
    lines = tm._build_suite_rst(
        "group__queue__api", DOXYGEN, "../testspec/html", "../api/html", "tests/kernel/queue"
    )
    assert lines[0] == "Queue API Tests"
    assert lines[1] == "-" * len("Queue API Tests")


def test_build_suite_rst_contains_test_case_ids():
    lines = tm._build_suite_rst(
        "group__queue__api", DOXYGEN, "../testspec/html", "../api/html", "tests/kernel/queue"
    )
    text = "\n".join(lines)
    assert "TSPEC-QUEUE-API-001" in text
    assert "TSPEC-QUEUE-API-002" in text


def test_build_suite_rst_missing_xml_returns_empty():
    lines = tm._build_suite_rst(
        "group__nonexistent", DOXYGEN, "../testspec/html", "../api/html", "tests/kernel/queue"
    )
    assert lines == []


# ---------------------------------------------------------------------------
# _build_proc_group_rst
# ---------------------------------------------------------------------------

def test_build_proc_group_rst_heading():
    lines = tm._build_proc_group_rst(
        "group__queue__procedures", DOXYGEN, "../testspec/html", "../api/html"
    )
    assert lines[0] == "Queue Test Procedures"
    assert lines[1] == "-" * len("Queue Test Procedures")


def test_build_proc_group_rst_contains_procedure_ids():
    lines = tm._build_proc_group_rst(
        "group__queue__procedures", DOXYGEN, "../testspec/html", "../api/html"
    )
    text = "\n".join(lines)
    assert "test-proc-queue_procedures-setup_queue" in text
    assert "test-proc-queue_procedures-teardown_queue" in text


# ---------------------------------------------------------------------------
# Sphinx directive integration — testreport
# ---------------------------------------------------------------------------

@pytest.mark.sphinx("html", srcdir=str(_ROOTS / "test-testreport"))
def test_testreport_directive_builds(app, warning):
    app.build()
    assert not warning.getvalue()


@pytest.mark.sphinx("html", srcdir=str(_ROOTS / "test-testreport"))
def test_testreport_directive_generates_result_ids(app):
    app.build()
    html = (Path(app.outdir) / "index.html").read_text()
    assert "TR-qemu-cortex-m3-ti-lm3s6965-kernel-queue-TSPEC-QUEUE-API-001" in html
    assert "TR-qemu-cortex-m3-ti-lm3s6965-kernel-queue-TSPEC-QUEUE-API-002" in html


@pytest.mark.sphinx("html", srcdir=str(_ROOTS / "test-testreport"))
def test_testreport_directive_suite_heading(app):
    app.build()
    html = (Path(app.outdir) / "index.html").read_text()
    assert "Queue API Tests" in html


# ---------------------------------------------------------------------------
# Sphinx directive integration — testmodule
# ---------------------------------------------------------------------------

@pytest.mark.sphinx("html", srcdir=str(_ROOTS / "test-testmodule"))
def test_testmodule_directive_builds(app, warning):
    app.build()
    assert not warning.getvalue()


@pytest.mark.sphinx("html", srcdir=str(_ROOTS / "test-testmodule"))
def test_testmodule_directive_generates_test_case_ids(app):
    app.build()
    html = (Path(app.outdir) / "index.html").read_text()
    assert "TSPEC-QUEUE-API-001" in html
    assert "TSPEC-QUEUE-API-002" in html


@pytest.mark.sphinx("html", srcdir=str(_ROOTS / "test-testmodule"))
def test_testmodule_directive_suite_heading(app):
    app.build()
    html = (Path(app.outdir) / "index.html").read_text()
    assert "Queue API Tests" in html


@pytest.mark.sphinx("html", srcdir=str(_ROOTS / "test-testmodule"))
def test_testmodule_directive_procedure_ids(app):
    app.build()
    html = (Path(app.outdir) / "index.html").read_text()
    assert "test-proc-queue_procedures-setup_queue" in html
