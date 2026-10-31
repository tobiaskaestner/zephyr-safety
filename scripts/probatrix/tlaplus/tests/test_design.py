# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The design tree validation/formal/kernel-spec (first slice) and its place in the Project."""

import shutil

import yaml

from probatrix.benchmarks import cli
from probatrix.benchmarks.studylib import lint
from probatrix.core import config, kinds
from probatrix.core.design import Design
from probatrix.tlaplus import kind

K = kind.KIND
REPO = config.project().repo
ROOT = REPO / "validation" / "formal" / "kernel-spec"


def test_the_design_tree_passes_the_lint_without_a_warning():
    assert [str(p) for p in lint.lint(ROOT)] == []


def test_the_formal_root_resolves_to_tlaplus_and_the_latency_root_stays_the_default():
    project = config.project()
    assert project.design_root == REPO / "validation" / "empirical" / "latencies"
    assert project.default_kind == "latbench"
    root = project.root_of(ROOT / "st-design-properties")
    assert root.path == ROOT and root.kind == "tlaplus"
    d = Design(ROOT)
    assert kinds.kind_of(d.top, root) is K
    assert lint.kind_of_root(ROOT) is K and lint.kind_of_root(project.design_root).name == "latbench"
    assert d.prefix == "tlaplus"


def test_design_lint_takes_both_roots_of_the_real_project():
    assert cli.lint_roots(None) == [REPO / "validation" / "empirical" / "latencies", ROOT]
    assert cli.lint_roots(ROOT / "st-reproducibility") == [ROOT]


def test_the_first_slice_has_the_two_studies():
    d = Design(ROOT)
    assert sorted(d.studies) == ["", "design-properties", "reproducibility"]
    assert d.top.data["question"].strip() == "Is the kernel spec consistent, and does the code conform?"
    assert d.top.data["kind"] == "tlaplus" and sorted(d.experiments) == ["mc-expected"]
    assert d.experiments["mc-expected"].study == "design-properties"
    assert d.studies["reproducibility"].imports == [
        {"study": "design-properties", "experiment": "mc-expected", "mode": "rerun"}]


def test_the_experiment_reads_the_73_lines_of_the_list():
    e = Design(ROOT).experiment("mc-expected")
    pts = K.points(e.data)
    assert len(pts) == 73 and pts[0]["id"] == "WaitQueueTest:default"
    got = K.generated_checks(e.data)
    assert sum(c["metric"] == "verdict" for c in got) == 73
    assert {c["metric"] for c in got} == {"verdict", "states", "depth"}
    for p in [*e.data["subject"], *e.data["tools"]]:
        assert (REPO / p).exists()


def test_the_checks_of_the_hypotheses_are_known_to_the_kind():
    d = Design(ROOT)
    for st in d.studies.values():
        for h in st.hypotheses:
            for c in h["checks"]:
                assert c.get("manual") or K.known(c["metric"], c.get("stat"))


def copy_tree(tmp_path):
    shutil.copytree(ROOT, tmp_path / "kernel-spec")
    return tmp_path / "kernel-spec"


def edited(root, rel, change):
    path = root / rel
    data = yaml.safe_load(path.read_text())
    change(data)
    path.write_text(yaml.safe_dump(data))


def errors(root):
    with config.use(config.project().with_(roots=(config.Root(root, "tlaplus"),))):
        return [p.text for p in lint.lint(root)]


def test_the_lint_reports_errors_of_the_kind(tmp_path):
    root = copy_tree(tmp_path)
    assert errors(root) == []
    exp = "st-design-properties/ex-mc-expected/experiment.yaml"
    edited(root, exp, lambda d: d.update(tool="apalache"))
    assert any("has no adapter yet" in t for t in errors(root))
    edited(root, exp, lambda d: d.update(tool="tlc", list="spec/tla/selftest/expected.txt"))
    assert any("is not inside a path of subject" in t for t in errors(root))
    edited(root, exp, lambda d: d.update(list="spec/tla/mc/expected.txt", tools=["spec/tla/tools/missing.sh"]))
    assert any("tools: spec/tla/tools/missing.sh does not exist" in t for t in errors(root))
    edited(root, exp, lambda d: d.update(tools=["spec/tla/tools/run_tlc.sh"], simulate={"depth": 1, "traces": 1, "seed": 1}))
    assert any("simulate is for the tool tlc-simulate" in t for t in errors(root))
    edited(root, exp, lambda d: d.update(subject_exclude=["spec/tla/tools/other.txt"]))
    assert any("subject_exclude: spec/tla/tools/other.txt is not inside a path of subject" in t for t in errors(root))
    edited(root, exp, lambda d: d.update(subject_exclude=["spec/tla/mc/*.txt"]))
    assert any("the list spec/tla/mc/expected.txt of the experiment must stay in the subject" in t for t in errors(root))
    edited(root, exp, lambda d: d.update(subject_exclude=["spec/tla/mc/kconfig.txt"]))
    assert not any("subject_exclude" in t for t in errors(root))
    edited(root, exp, lambda d: (d.pop("simulate"), d.update(tool="tlc-simulate")))
    assert any("needs the defaults simulate" in t for t in errors(root))
    edited(root, exp, lambda d: d.update(tool="tlc"))
    assert errors(root) == []
    edited(root, "st-design-properties/hypotheses.yaml",
           lambda d: d["hypotheses"][0]["checks"][0].update(metric="p99"))
    assert any("metric 'p99' with stat None" in t for t in errors(root))


def test_a_study_with_an_unknown_key_is_a_schema_error(tmp_path):
    root = copy_tree(tmp_path)
    edited(root, "study.yaml", lambda d: d.update(board=None))
    assert any("unknown key 'board'" in t for t in errors(root))
