import xml.etree.ElementTree as ET

import pytest

import doxygen_parser as dp
from conftest import FIXTURES


# ---------------------------------------------------------------------------
# elem_text
# ---------------------------------------------------------------------------

def test_elem_text_simple():
    el = ET.fromstring("<root>hello</root>")
    assert dp.elem_text(el) == "hello"


def test_elem_text_nested():
    el = ET.fromstring("<root>foo <child>bar</child> baz</root>")
    assert dp.elem_text(el) == "foo bar baz"


# ---------------------------------------------------------------------------
# para_text
# ---------------------------------------------------------------------------

def test_para_text_computeroutput_func_ref():
    para = ET.fromstring(
        "<para>Call <computeroutput>"
        "<ref kindref='member'>foo()</ref>"
        "</computeroutput> here.</para>"
    )
    result = dp.para_text(para)
    assert ":c:func:`foo`" in result


def test_para_text_computeroutput_macro():
    # A macro ending in () must NOT become :c:func: — no <ref> child means plain code
    para = ET.fromstring("<para>Use <computeroutput>K_FIFO_DEFINE()</computeroutput>.</para>")
    result = dp.para_text(para)
    assert "``K_FIFO_DEFINE()``" in result
    assert ":c:func:" not in result


def test_para_text_computeroutput_plain():
    para = ET.fromstring("<para>Use <computeroutput>CONFIG_FOO</computeroutput>.</para>")
    result = dp.para_text(para)
    assert "``CONFIG_FOO``" in result


def test_para_text_skips_parameterlist():
    para = ET.fromstring(
        "<para>Brief text."
        "<parameterlist kind='param'>"
        "<parameteritem>"
        "<parameternamelist><parametername>x</parametername></parameternamelist>"
        "<parameterdescription><para>an integer</para></parameterdescription>"
        "</parameteritem>"
        "</parameterlist>"
        "</para>"
    )
    result = dp.para_text(para)
    assert "Brief text" in result
    assert "integer" not in result


# ---------------------------------------------------------------------------
# list_to_rst_lines
# ---------------------------------------------------------------------------

def test_list_to_rst_lines_continuation_indent_ordered():
    ol = ET.fromstring(
        "<orderedlist>"
        "<listitem><para>first</para><para>continuation</para></listitem>"
        "</orderedlist>"
    )
    lines = dp.list_to_rst_lines(ol, "#.")
    assert lines[0] == "#. first"
    assert lines[1] == "   continuation"  # 3 spaces: len("#.") + 1


def test_list_to_rst_lines_continuation_indent_unordered():
    il = ET.fromstring(
        "<itemizedlist>"
        "<listitem><para>first</para><para>continuation</para></listitem>"
        "</itemizedlist>"
    )
    lines = dp.list_to_rst_lines(il, "-")
    assert lines[0] == "- first"
    assert lines[1] == "  continuation"  # 2 spaces: len("-") + 1


# ---------------------------------------------------------------------------
# see_to_rst
# ---------------------------------------------------------------------------

def test_see_to_rst_ref_resolved():
    see = ET.fromstring(
        "<simplesect kind='see'><para>"
        "<ref refid='group__queue__api_1abc' external='path/to/tagfile.xml' kindref='member'>"
        "k_queue_init"
        "</ref>"
        "</para></simplesect>"
    )
    result = dp.see_to_rst(see, "/api/html")
    assert "k_queue_init" in result
    assert "/api/html/group__queue__api.html#abc" in result


def test_see_to_rst_ref_unresolved():
    see = ET.fromstring(
        "<simplesect kind='see'><para>"
        "<ref refid='group__queue__api_1abc' kindref='member'>k_queue_init</ref>"
        "</para></simplesect>"
    )
    result = dp.see_to_rst(see, "/api/html")
    assert ":c:func:`k_queue_init`" in result


# ---------------------------------------------------------------------------
# parse_memberdef
# ---------------------------------------------------------------------------

def _make_memberdef(extra_xrefsects="", inbody=""):
    return ET.fromstring(
        f"<memberdef kind='function' id='group__queue__api_1a001'>"
        f"<name>test_queue_put</name>"
        f"<briefdescription><para>Test queue put.</para></briefdescription>"
        f"<detaileddescription><para>{extra_xrefsects}</para></detaileddescription>"
        f"<inbodydescription>{inbody}</inbodydescription>"
        f"<location file='test_queue.c' line='42' bodyfile='test_queue.c' bodystart='42'/>"
        f"</memberdef>"
    )


def test_parse_memberdef_extracts_testid():
    xref = (
        "<xrefsect id='testids_1testids'>"
        "<xreftitle>Test ID</xreftitle>"
        "<xrefdescription><para>TSPEC-QUEUE-API-001</para></xrefdescription>"
        "</xrefsect>"
    )
    md = _make_memberdef(extra_xrefsects=xref)
    info = dp.parse_memberdef(md, "group__queue__api", "/testspec/html", "/api/html")
    assert info["test_id"] == "TSPEC-QUEUE-API-001"


def test_parse_memberdef_extracts_reqrefs():
    xref = (
        "<xrefsect id='reqrefs_1reqrefs'>"
        "<xreftitle>Requirement Refs</xreftitle>"
        "<xrefdescription><para>zep-srs-20-1</para></xrefdescription>"
        "</xrefsect>"
    )
    md = _make_memberdef(extra_xrefsects=xref)
    info = dp.parse_memberdef(md, "group__queue__api", "/testspec/html", "/api/html")
    assert "zep-srs-20-1" in info["req_ids"]


def test_parse_memberdef_active_status():
    xref = (
        "<xrefsect id='test_active_1test_active'>"
        "<xreftitle>Active</xreftitle>"
        "<xrefdescription><para></para></xrefdescription>"
        "</xrefsect>"
    )
    md = _make_memberdef(extra_xrefsects=xref)
    info = dp.parse_memberdef(md, "group__queue__api", "/testspec/html", "/api/html")
    assert info["status"] == "active"


def test_parse_memberdef_no_testid():
    md = _make_memberdef()
    info = dp.parse_memberdef(md, "group__queue__api", "/testspec/html", "/api/html")
    assert info["test_id"] == ""


def test_parse_memberdef_extracts_detail_paras():
    xml = ET.fromstring(
        "<memberdef kind='function' id='group__queue__api_1a001'>"
        "<name>test_queue_put</name>"
        "<briefdescription><para>Brief line.</para></briefdescription>"
        "<detaileddescription>"
        "<para>First detail paragraph.</para>"
        "<para>Second detail paragraph.</para>"
        "<para><xrefsect id='testids_1testids'><xreftitle>Test ID</xreftitle>"
        "<xrefdescription><para>TSPEC-QUEUE-API-001</para></xrefdescription>"
        "</xrefsect></para>"
        "</detaileddescription>"
        "<inbodydescription/>"
        "<location file='f.c' line='1' bodyfile='f.c' bodystart='1'/>"
        "</memberdef>"
    )
    info = dp.parse_memberdef(xml, "group__queue__api", "/testspec/html", "/api/html")
    assert info["detail_paras"] == ["First detail paragraph.", "Second detail paragraph."]
    assert info["test_id"] == "TSPEC-QUEUE-API-001"


def test_parse_memberdef_arrange_sections():
    inbody = (
        "<para>"
        "<simplesect kind='par'>"
        "<title>Arrange</title>"
        "<para>Set up the queue.</para>"
        "</simplesect>"
        "</para>"
    )
    md = _make_memberdef(inbody=inbody)
    info = dp.parse_memberdef(md, "group__queue__api", "/testspec/html", "/api/html")
    assert len(info["body_sections"]) == 1
    assert any("Arrange" in line for line in info["body_sections"][0])


# ---------------------------------------------------------------------------
# load_group_index
# ---------------------------------------------------------------------------

def test_load_group_index_maps_names():
    idx = dp.load_group_index(FIXTURES / "doxygen")
    assert idx.get("queue_api") == "group__queue__api"
    assert idx.get("queue_procedures") == "group__queue__procedures"


def test_load_group_index_missing_file_raises():
    with pytest.raises(RuntimeError):
        dp.load_group_index(FIXTURES / "doxygen" / "nonexistent")


# ---------------------------------------------------------------------------
# extract_params
# ---------------------------------------------------------------------------

def test_extract_params_basic():
    dd = ET.fromstring(
        "<detaileddescription><para>"
        "<parameterlist kind='param'>"
        "<parameteritem>"
        "<parameternamelist><parametername>queue</parametername></parameternamelist>"
        "<parameterdescription><para>the queue pointer</para></parameterdescription>"
        "</parameteritem>"
        "</parameterlist>"
        "</para></detaileddescription>"
    )
    params = dp.extract_params(dd)
    assert len(params) == 1
    assert params[0][0] == "queue"
    assert "queue pointer" in params[0][1]
