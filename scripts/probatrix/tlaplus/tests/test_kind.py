# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The kind tlaplus: registration, schemas, points, generated checks, the value provider, the dirt paths."""

import subprocess

import pytest
import yaml

from probatrix.core import checks, config, design, kinds, schema
from probatrix.core.errors import NoValue
from probatrix.tlaplus import kind

K = kind.KIND
LIST = """# comment
MCKSem default pass states=10 depth=4
MCKSem live fail:Live_X
MCKSem reach probes
"""
SIM_LIST = """MCKSem default pass
MCKSem live fail:Inv_X depth=20 seed=5
MCKSem reach pass traces=7
"""


def experiment(**kw):
    return {"name": "e", "tool": "tlc", "list": "spec/tla/mc/l.txt", "subject": ["spec/tla/mc"],
            "tools": ["spec/tla/tools/run_tlc.sh"], **kw}


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "spec/tla/mc").mkdir(parents=True)
    (tmp_path / "spec/tla/mc/l.txt").write_text(LIST)
    (tmp_path / "spec/tla/mc/s.txt").write_text(SIM_LIST)
    with config.use(config.Project.at(tmp_path)):
        yield tmp_path


def test_the_kind_is_registered_by_name():
    assert kinds.get("tlaplus") is K
    assert kinds.PLUGINS["tlaplus"] == "probatrix.tlaplus.kind" and "tlaplus" in kinds.names()
    assert (K.schema_prefix, K.format_prefix, K.ref_prefix) == ("tlaplus", "tlaplus", "refs/tlaplus")
    assert K.format_id("app-tlc", 1) == "tlaplus-app-tlc/1" and K.ref("run", "x", "y") == "refs/tlaplus/run/x/y"
    assert K.instance_axis is None and "tlaplus" in schema.prefixes()
    kinds.get("latbench")
    assert schema.validator("study").schema["$id"] == "latbench/study.schema.yaml"      # the default prefix stays latbench
    assert K.dirt_paths == ("spec/tla",)


def test_the_schemas_of_the_kind_have_the_id_prefix():
    for f in K.schema_folder.glob("*.schema.yaml"):
        assert yaml.safe_load(f.read_text())["$id"] == f"tlaplus/{f.name}"
    assert len(list(K.schema_folder.glob("*.schema.yaml"))) == 4


def problems(name, data):
    return schema.problems(name, data, "tlaplus")


def test_the_experiment_schema():
    assert problems("experiment", experiment()) == []
    assert problems("experiment", experiment(tool="tlc-simulate", simulate={"depth": 10, "traces": 5, "seed": 1})) == []
    assert problems("experiment", experiment(kind="tlaplus", renamed_from=["old"], acceptance=[
        {"id": "a", "metric": "evidence", "expect": {"equals": True}}])) == []
    assert "tool" in problems("experiment", experiment(tool="cbmc"))[0]
    assert "missing key" in problems("experiment", {"name": "e", "tool": "tlc"})[0]
    assert "unknown key 'app'" in problems("experiment", experiment(app="x"))[0]
    assert problems("experiment", experiment(subject=[]))
    assert problems("experiment", experiment(simulate={"depth": 10}))              # all three or none
    assert problems("experiment", experiment(simulate={"depth": 0, "traces": 1, "seed": 1}))
    assert problems("experiment", experiment(name="Bad Name"))


def test_the_study_and_hypotheses_schemas():
    assert problems("study", {"name": "s", "kind": "tlaplus", "question": "q", "experiments": ["a"],
                              "imports": [{"study": "x", "experiment": "a", "mode": "rerun"}],
                              "substudies": ["b"]}) == []
    assert problems("study", {"name": "s", "board": None})                           # no board in this kind
    assert problems("study", {"name": "s", "substudies": [{"use": "b"}]})            # names only
    assert problems("hypotheses", {"hypotheses": [{"id": "H1", "statement": "s", "checks": [
        {"id": "a", "experiment": "e", "metric": "verdict", "expect": {"equals": "pass"}}]}]}) == []
    assert problems("hypotheses", {"hypotheses": [{"id": "H1"}]})


def test_points_are_the_lines_of_the_list(repo):
    pts = K.points(experiment())
    assert [p["id"] for p in pts] == ["MCKSem:default", "MCKSem:live", "MCKSem:reach"]
    assert pts[0]["fields"] == {"states": "10", "depth": "4"} and pts[0]["axes"] == {} and pts[0]["params"] == {}
    assert pts[1]["expected"] == "fail:Live_X"


def test_the_errors_of_the_list_stop_the_points(repo):
    (repo / "spec/tla/mc/bad.txt").write_text("M c pass nokey=1\n")
    with pytest.raises(SystemExit, match=r"error: .*bad.txt:1: M c: unknown field nokey=1"):
        K.points(experiment(list="spec/tla/mc/bad.txt"))
    with pytest.raises(SystemExit, match="error: .*no.txt"):
        K.points(experiment(list="spec/tla/mc/no.txt"))
    (repo / "spec/tla/mc/bad.txt").write_text("M c passed\n")
    with pytest.raises(SystemExit, match="the expected result 'passed'"):
        K.points(experiment(list="spec/tla/mc/bad.txt"))
    assert K.generated_checks(experiment(list="spec/tla/mc/bad.txt")) == []


def test_the_points_of_a_simulation_have_the_parameters(repo):
    exp = experiment(tool="tlc-simulate", list="spec/tla/mc/s.txt", simulate={"depth": 100, "traces": 50, "seed": 1})
    assert [p["params"] for p in K.points(exp)] == [
        {"depth": 100, "traces": 50, "seed": 1}, {"depth": 20, "traces": 50, "seed": 5},
        {"depth": 100, "traces": 7, "seed": 1}]


def test_one_generated_check_for_each_line_and_count(repo):
    got = K.generated_checks(experiment())
    assert [c["id"] for c in got] == ["MCKSem:default-verdict", "MCKSem:default-states", "MCKSem:default-depth",
                                      "MCKSem:live-verdict", "MCKSem:reach-verdict"]
    assert got[0] == {"id": "MCKSem:default-verdict", "metric": "verdict", "select": {"point": "MCKSem:default"},
                      "expect": {"equals": "pass"}}
    assert got[1]["metric"] == "states" and got[1]["expect"] == {"equals": 10}
    assert got[2]["expect"] == {"equals": 4}


def test_a_simulation_checks_the_verdict_only(repo):
    exp = experiment(tool="tlc-simulate", list="spec/tla/mc/s.txt", simulate={"depth": 100, "traces": 50, "seed": 1})
    assert [c["id"] for c in K.generated_checks(exp)] == ["MCKSem:default-verdict", "MCKSem:live-verdict",
                                                          "MCKSem:reach-verdict"]


def rep(**values):
    return {"rep": 1, "values": values}


def test_the_provider_reads_values_by_name_without_a_stat():
    r = rep(verdict="pass", states=10, evidence=True, seconds=1.5)
    assert K.value(r, "verdict", None) == "pass" and K.value(r, "states", None) == 10
    assert K.value(r, "evidence", None) is True and K.value(r, "seconds", None) == 1.5
    with pytest.raises(NoValue, match="no value 'depth'"):
        K.value(r, "depth", None)
    with pytest.raises(NoValue, match="no stats"):
        K.value(r, "states", "p99")
    assert K.known("verdict", None) and K.known("evidence", None) and K.known("depth", None)
    assert not K.known("p99", None) and not K.known("verdict", "p99") and not K.known(None, None)
    assert K.stat_needed("verdict") is False and K.width(r, "states", None) == 1 and K.seen(r, "states") is True


def test_a_check_of_the_kind_needs_no_stat():
    assert checks.problems({"id": "a", "metric": "evidence", "expect": {"equals": True}}, K) == []
    assert checks.problems({"id": "a", "metric": "verdict", "expect": {"equals": "pass"}}, K) == []
    assert checks.problems({"id": "a", "metric": "p99", "expect": {"equals": 1}}, K) == ["metric 'p99' with stat None"]
    assert checks.problems({"id": "a", "metric": "states", "expect": {"range": [1, 5]}}, K) == []
    # a text is not a number: the numeric forms say so (core/checks.py), the kind does not decide it
    obs = [checks.Obs("e/1", "tlc", "p", {}, rep(verdict="pass"))]

    class Src:
        kind = K

        def observations(self, exp, series=None):
            return obs
    with pytest.raises(NoValue, match="not a number|text"):
        checks.evaluate({"experiment": "e", "metric": "verdict", "expect": {"range": [1, 2]}}, Src())


def git(repo, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=repo, check=True,
                   capture_output=True)


def test_an_edit_of_the_spec_does_not_make_a_latbench_build_dirty(tmp_path):
    """The dirt paths are per kind: spec/tla is tlaplus, tests/benchmarks is latbench; validation and scripts/probatrix both."""
    from probatrix.benchmarks import kind as benchkind
    git(tmp_path, "init", "-q")
    for d in ("spec/tla/mc", "tests/benchmarks", "validation", "scripts/probatrix"):
        (tmp_path / d).mkdir(parents=True)
        (tmp_path / d / "f").write_text("1")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "x")
    bench, tla = benchkind.KIND, K
    with config.use(config.Project.at(tmp_path)):
        assert "spec/tla" in kinds.dirt_paths(tla) and "spec/tla" not in kinds.dirt_paths(bench)
        assert "tests/benchmarks" in kinds.dirt_paths(bench) and "tests/benchmarks" not in kinds.dirt_paths(tla)
        assert design.repo_rev(kind=bench)[1] is False and design.repo_rev(kind=tla)[1] is False
        (tmp_path / "spec/tla/mc/f").write_text("2")
        assert design.repo_rev(kind=bench)[1] is False and design.repo_rev(kind=tla)[1] is True
        git(tmp_path, "checkout", "--", ".")
        (tmp_path / "tests/benchmarks/f").write_text("2")
        assert design.repo_rev(kind=bench)[1] is True and design.repo_rev(kind=tla)[1] is False
        git(tmp_path, "checkout", "--", ".")
        for d in ("validation", "scripts/probatrix"):
            (tmp_path / d / "f").write_text("2")
            assert design.repo_rev(kind=bench)[1] is True and design.repo_rev(kind=tla)[1] is True
            git(tmp_path, "checkout", "--", ".")


def test_the_pyproject_lists_the_package_and_its_data():
    import tomllib
    from pathlib import Path
    t = tomllib.loads((Path(__file__).resolve().parents[2] / "pyproject.toml").read_text())["tool"]["setuptools"]
    assert "probatrix.tlaplus" in t["packages"] and "probatrix.tlaplus.tests" in t["packages"]
    assert "schemas/*.schema.yaml" in t["package-data"]["probatrix.tlaplus"]
