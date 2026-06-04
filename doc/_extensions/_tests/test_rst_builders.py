import pytest
import yaml

import rst_builders as rb
from conftest import FIXTURES


def _base_info(**kwargs):
    defaults = {
        "name": "test_queue_put",
        "brief": "Test queue put operation.",
        "test_id": "TSPEC-QUEUE-API-001",
        "req_ids": ["zep-srs-20-1"],
        "status": "active",
        "source_file": "test_queue.c (line 42)",
        "doxygen_url": "/testspec/html/group.html#abc",
        "see_rst": "",
        "body_sections": [],
    }
    defaults.update(kwargs)
    return defaults


def _base_result(**kwargs):
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


# ---------------------------------------------------------------------------
# slugify
# ---------------------------------------------------------------------------

def test_slugify_replaces_slashes():
    assert rb.slugify("a/b") == "a-b"


def test_slugify_strips_edges():
    assert rb.slugify("_hello_") == "hello"
    assert rb.slugify("-foo-") == "foo"


# ---------------------------------------------------------------------------
# build_need_rst
# ---------------------------------------------------------------------------

def test_build_need_rst_id_from_testid():
    rst = rb.build_need_rst(_base_info(), "kernel.queue")
    assert ":id: TSPEC-QUEUE-API-001" in rst


def test_build_need_rst_fallback_id():
    rst = rb.build_need_rst(_base_info(test_id=""), "kernel.queue")
    assert ":id: testspec-kernel.queue-test_queue_put" in rst


def test_build_need_rst_verifies_field():
    rst = rb.build_need_rst(_base_info(req_ids=["zep-srs-20-1", "zep-srs-20-2"]), "kernel.queue")
    assert ":verifies: zep-srs-20-1; zep-srs-20-2" in rst


def test_build_need_rst_no_verifies_when_empty():
    rst = rb.build_need_rst(_base_info(req_ids=[]), "kernel.queue")
    assert ":verifies:" not in rst


# ---------------------------------------------------------------------------
# build_result_rst
# ---------------------------------------------------------------------------

def test_build_result_rst_id_scheme():
    rst = rb.build_result_rst(_base_result(), "TSPEC-QUEUE-API-001", "tests/kernel/queue")
    assert "TR-qemu-cortex-m3-ti-lm3s6965-kernel-queue-TSPEC-QUEUE-API-001" in rst


def test_build_result_rst_covers_field():
    rst = rb.build_result_rst(_base_result(), "TSPEC-QUEUE-API-001", "tests/kernel/queue",
                               req_ids=["zep-srs-20-1"])
    assert ":covers: zep-srs-20-1" in rst


def test_build_result_rst_no_reason_when_passed():
    rst = rb.build_result_rst(_base_result(status="passed", reason=""), "SPEC-001", "mod")
    assert ":reason:" not in rst


def test_build_result_rst_reason_on_failure():
    rst = rb.build_result_rst(
        _base_result(status="failed", reason="assertion failed"), "SPEC-001", "mod"
    )
    assert ":reason: assertion failed" in rst


# ---------------------------------------------------------------------------
# build_procedure_need_rst
# ---------------------------------------------------------------------------

def test_build_procedure_need_rst_id_scheme():
    import xml.etree.ElementTree as ET
    memberdef = ET.fromstring(
        "<memberdef kind='function' id='group__queue__procedures_1b001'>"
        "<name>setup_queue</name>"
        "<briefdescription><para>Set up queue.</para></briefdescription>"
        "<detaileddescription></detaileddescription>"
        "<location file='helpers.c' line='10' bodyfile='helpers.c' bodystart='10'/>"
        "</memberdef>"
    )
    rst = rb.build_procedure_need_rst(
        memberdef, "group__queue__procedures", "queue_procedures",
        "/testspec/html", "/api/html"
    )
    assert ":id: test-proc-queue_procedures-setup_queue" in rst


# ---------------------------------------------------------------------------
# build_scenario_table
# ---------------------------------------------------------------------------

def test_build_scenario_table_renders_list_table(tmp_path):
    yaml_content = {
        "tests": {
            "kernel.queue": {"tags": ["kernel", "queue"], "extra_configs": []},
            "kernel.queue.minimallibc": {"tags": ["kernel"], "extra_configs": ["CONFIG_MINIMAL_LIBC=y"]},
        }
    }
    p = tmp_path / "testcase.yaml"
    p.write_text(yaml.dump(yaml_content))
    lines = rb.build_scenario_table(p)
    assert any(".. list-table::" in line for line in lines)
    assert any("kernel.queue" in line for line in lines)


def test_build_scenario_table_missing_yaml():
    lines = rb.build_scenario_table(FIXTURES / "nonexistent.yaml")
    assert lines == []
