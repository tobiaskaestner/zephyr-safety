# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""tla_domain: the directives, the roles, the links and the property needs."""

import json
import re
from pathlib import Path

import pytest

from tla_domain import anchor_id, infer_kind
from tla_extract import parse_file

TLA = pytest.mark.sphinx("html", testroot="tla", freshenv=True)


def html(app, page):
    return (Path(app.outdir) / f"{page}.html").read_text(encoding="utf-8")


def needs(app):
    data = json.loads((Path(app.outdir) / "needs.json").read_text())
    return data["versions"][data["current_version"]]["needs"]


def definition_html(page, anchor):
    """The HTML of the <dl> of one definition."""
    start = page.index(f'id="{anchor}"')
    return page[start : page.index("</dl>", page.index("<pre", start))]


@TLA
def test_the_test_project_builds_without_warnings(app, warning):
    app.build()
    assert warning.getvalue() == ""


@TLA
def test_the_objects_of_the_domain(app):
    app.build()
    domain = app.env.domains["tla"]
    assert set(domain.modules) == {"KSem", "Extra", "MCKSem"}
    assert domain.objects[("KSem", "Give")] == ("ksem", "tla-KSem-Give", "definition")
    assert domain.objects[("KSem", "NoWaitWhileAvailable")][2] == "property"
    assert ("Extra", "++") in domain.objects
    assert ("Extra", "Ghost") not in domain.objects
    inv = {name for name, *_ in domain.get_objects()}
    assert {"KSem", "KSem!Give", "Extra!Sum"} <= inv


@TLA
def test_unicode_is_the_default_and_ascii_an_option(app):
    app.build()
    page = html(app, "ksem")
    give = definition_html(page, "tla-KSem-Give")
    assert "≜" in give and "∧" in give and "/\\" not in give
    take = definition_html(page, "tla-KSem-Take")
    assert "/\\" in take and "∧" not in take


@TLA
def test_names_link_to_their_definitions(app):
    app.build()
    give = definition_html(html(app, "ksem"), "tla-KSem-Give")
    for name in ("CanCall", "Inc", "PollReady", "NoObs", "OK"):
        assert f'href="#tla-KSem-{name}" title="KSem!{name}"' in give, name
    # Not linked: the parameter, the own name, record fields, variables and
    # the operators of the standard modules.
    links = set(re.findall(r'title="KSem!(\w+)"', give))
    assert not links & {"a", "Give", "actor", "op", "waitq", "Head", "Tail"}


@TLA
def test_names_link_through_extends(app):
    app.build()
    page = html(app, "extra")
    mc = definition_html(page, "tla-MCKSem-MCPrioDistinct")
    assert "<pre" in mc
    # MCKSem EXTENDS KSem: the module name links to the KSem module.
    assert 'href="ksem.html#tla-module-KSem"' in page


@TLA
def test_module_body_skips_the_definitions_shown_before(app):
    app.build()
    page = html(app, "ksem")
    assert page.count('id="tla-KSem-Give"') == 1
    assert 'id="tla-KSem-Enqueue"' in page
    assert 'id="tla-KSem-WokenReturns"' in page


@TLA
def test_the_prose_is_rst_without_tags(app):
    app.build()
    page = html(app, "ksem")
    assert '<code class="docutils literal notranslate"><span class="pre">count</span>' in page
    assert "@kind" not in page and "@expresses" not in page
    extra = html(app, "extra")
    assert "<em>RST</em>" in extra


@TLA
def test_the_tags_of_a_definition(app):
    app.build()
    give = definition_html(html(app, "ksem"), "tla-KSem-Give")
    assert "Models" in give and "z_impl_k_sem_give" in give
    assert '<span class="pre">action</span>' in give


@TLA
def test_the_roles(app):
    app.build()
    page = html(app, "refs")
    assert 'href="ksem.html#tla-module-KSem"' in page
    assert 'href="ksem.html#tla-KSem-Give"' in page
    assert 'href="extra.html#tla-Extra--x2b--x2b-"' in page
    assert 'href="ksem.html#tla-KSem-Enqueue"' in page


@TLA
def test_code_blocks_with_the_lexers(app):
    app.build()
    page = html(app, "refs")
    assert '<span class="o">≜</span>' in page
    assert '<span class="o">==</span>' in page


@TLA
def test_the_property_needs(app):
    app.build()
    data = needs(app)
    props = {k: v for k, v in data.items() if v["type"] == "prop"}
    assert set(props) == {
        "PROP-KSem-CountLeLimit",
        "PROP-KSem-NoWaitWhileAvailable",
        "PROP-KSem-PollSignalMeansAvailable",
        "PROP-KSem-ResetWakesAll",
        "PROP-KSem-WaiterServedIfGives",
        "PROP-KSem-TimedWaitEnds",
    }
    nwa = props["PROP-KSem-NoWaitWhileAvailable"]
    assert nwa["expresses"] == ["TEST-REQ-2", "TEST-REQ-3"]
    assert nwa["kind"] == "invariant"  # inferred: no @kind tag
    assert nwa["expected"] == "hold"
    assert nwa["tla_module"] == "KSem"
    assert nwa["source_file"] == "spec/KSem.tla"
    assert nwa["content"].startswith("No thread waits while the semaphore is available.")
    assert props["PROP-KSem-ResetWakesAll"]["kind"] == "action"
    assert props["PROP-KSem-WaiterServedIfGives"]["expected"] == "violation"
    # The options override the tags.
    timed = props["PROP-KSem-TimedWaitEnds"]
    assert timed["expresses"] == ["TEST-REQ-9"]
    assert timed["kind"] == "liveness"
    # The back-link on the requirement.
    assert data["TEST-REQ-2"]["expresses_back"] == ["PROP-KSem-NoWaitWhileAvailable"]
    assert data["TEST-REQ-5"]["expresses_back"] == []


@TLA
def test_a_property_need_holds_the_rendered_definition(app):
    app.build()
    page = html(app, "ksem")
    start = page.index('id="PROP-KSem-NoWaitWhileAvailable"')
    need = page[start : page.index("</table>", start)]
    assert 'id="tla-KSem-NoWaitWhileAvailable"' in need
    assert "≜" in need


@pytest.mark.sphinx("html", testroot="tla", freshenv=True, confoverrides={"tla_unicode": False})
def test_the_ascii_configuration(app, warning):
    app.build()
    give = definition_html(html(app, "ksem"), "tla-KSem-Give")
    assert "/\\" in give and "≜" not in give
    assert warning.getvalue() == ""


@pytest.mark.sphinx("html", testroot="tla", freshenv=True)
def test_the_css_file(app):
    app.build()
    assert (Path(app.outdir) / "_static" / "tla_domain.css").is_file()
    assert "tla_domain.css" in html(app, "index")


@pytest.mark.sphinx("html", testroot="tla-warnings", freshenv=True)
def test_the_warnings(app, warning):
    app.build()
    text = re.sub(r"\x1b\[[0-9;]*m", "", warning.getvalue())
    expected = [
        "index.rst:4: WARNING: no TLA+ module",
        "index.rst:6: WARNING: TLA+ module 'Missing' not found",
        "Bad.tla:2: WARNING: unknown TLA+ tag @foo",
        "Bad.tla:3: WARNING: unknown @kind 'wrong'",
        "Bad.tla:4: WARNING: unknown @expected 'maybe'",
        "WARNING: duplicate TLA+ definition Bad!Ok",
        "WARNING: TLA+ module Bad has no top-level definition 'NoSuch'",
        "WARNING: need type 'prop' is not configured",
        "tla:def reference target not found: Bad!Nope",
    ]
    for message in expected:
        assert message in text, (message, text)
    # A duplicate is not indexed a second time: no docutils "Duplicate ID".
    assert "Duplicate ID" not in text


def test_infer_kind(ksem_copy):
    module = parse_file(ksem_copy)
    assert infer_kind(module.definition("NoWaitWhileAvailable")) == "invariant"
    assert infer_kind(module.definition("TimedWaitEnds")) == "liveness"
    assert infer_kind(module.definition("WaiterServedIfGives")) == "liveness"
    assert infer_kind(module.definition("ResetWakesAll")) == "action"
    assert infer_kind(module.definition("TypeOK")) == "invariant"


def test_anchor_ids():
    assert anchor_id("KSem") == "tla-module-KSem"
    assert anchor_id("KSem", "Give") == "tla-KSem-Give"
    assert anchor_id("Extra", "-.") == "tla-Extra--x2d--x2e-"
