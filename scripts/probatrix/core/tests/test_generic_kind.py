# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The proof that core is generic: a build over a fake kind that is not the benchmarks.

The fake kind (a subclass of BaseKind) has no instance axis. Its experiment is a list of lines
"<point>: <expected verdict>"; its run folder has one file result.txt with the lines
"<point> <verdict> <n>". value() returns a text (verdict) and an integer (n); generated_checks() gives one
`equals` check per line. The test makes a design tree and a results tree, runs core.build.build and reads
study.json. Nothing here imports probatrix.benchmarks.
"""

import json
from pathlib import Path

import pytest
import yaml

from probatrix.core import build, config, kinds, schema, seal
from probatrix.core.errors import NoValue

SCHEMAS = Path(__file__).resolve().parent / "fixtures" / "fake_kind"
RUN = "mc/20260101T000000Z"


class FakeKind(kinds.BaseKind):
    name = "fake"
    schema_prefix = "fake"
    schema_folder = SCHEMAS
    format_prefix = "fake"
    ref_prefix = "refs/fake"
    tool = "fake-tool"

    def points(self, experiment):
        return [{"id": line.split(":")[0].strip()} for line in experiment["list"]]

    def generated_checks(self, experiment):
        out = []
        for line in experiment["list"]:
            point, want = (x.strip() for x in line.split(":"))
            out.append({"id": f"{point}-verdict", "metric": "verdict", "select": {"point": point},
                        "expect": {"equals": want}})
        return out

    def run_json(self, run_dir, run_id, digest, made_by, experiment_file):
        lines = (run_dir / "result.txt").read_text().split("\n")
        return {"format": "fake-run/1", "made_by": made_by,
                "run": {"id": run_id, "app": "fake", "digest": digest, "safety_rev": made_by["safety_rev"]},
                "points": [{"tree": "t", "point": ln.split()[0], "axes": {}} for ln in lines if ln]}

    def app_json(self, run_dir, app, run_id, digest, made_by):
        rows = [ln.split() for ln in (run_dir / "result.txt").read_text().split("\n") if ln]
        return {"format": "fake-app-fake/1", "made_by": made_by, "run": {"digest": digest}, "app": app,
                "points": [{"reps": [{"rep": 1, "verdict": v, "n": int(n)}]} for _, v, n in rows]}

    def value(self, rep, metric, stat):
        if metric in ("verdict", "n"):
            return rep[metric]
        raise NoValue(f"no metric {metric!r}")

    def known(self, metric, stat):
        return metric in ("verdict", "n")


@pytest.fixture
def fake():
    schema.register("fake", SCHEMAS)
    kind = kinds.register(FakeKind())
    yield kind
    kinds._KINDS.pop("fake")


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text if isinstance(text, str) else yaml.safe_dump(text))


@pytest.fixture
def trees(tmp_path, fake):
    design, results = tmp_path / "design", tmp_path / "results" / "top"
    write(design / "study.yaml", {"name": "top", "question": "q", "experiments": ["mc"]})
    write(design / "ex-mc" / "experiment.yaml",
          {"name": "mc", "list": ["p1: pass", "p2: fail", "p3: pass"]})
    write(design / "hypotheses.yaml", {"hypotheses": [{
        "id": "H1", "statement": "p1 has 3 states",
        "checks": [{"id": "n", "experiment": "mc", "metric": "n", "select": {"point": "p1"},
                    "expect": {"range": [3, 3]}}]}]})
    run_dir = results / "ex-mc" / "20260101T000000Z"
    write(run_dir / "result.txt", "p1 pass 3\np2 fail 7\np3 fail 2\n")
    digest = seal.write(run_dir)
    write(results / "instance.json", json.dumps({
        "format": "fake-instance/1", "instance": "top", "runs": [{"id": RUN, "digest": digest, "role": "evidence"}],
        "references": [], "substudies": [], "manual_verdicts": [], "notes": []}))
    project = config.Project.at(tmp_path, design_root=design, roots=(config.Root(design, "fake"),))
    with config.use(project):
        yield results


def test_the_core_builds_a_kind_without_an_axis(trees, fake):
    tree, writer = build.build(trees, log=lambda *a: None)
    assert tree.kind is fake and tree.axis is None
    sj = json.loads((trees / "study.json").read_text())
    assert sj["format"] == "fake-study/2" and sj["made_by"]["tool"] == "fake-tool"
    verdicts = {h["id"]: h["verdict"] for h in sj["hypotheses"]}
    # H1: a number check (int) of the file; mc-generated: p3 is "fail" but the list expects "pass"
    assert verdicts == {"H1": "confirmed", "mc-generated": "wrong"}
    gen = next(h for h in sj["hypotheses"] if h["id"] == "mc-generated")
    assert {c["id"]: c["verdict"] for c in gen["checks"]} == {
        "p1-verdict": "confirmed", "p2-verdict": "confirmed", "p3-verdict": "wrong"}
    assert gen["checks_confirmed"] == "2 of 3"
    assert sj["experiments"][0]["name"] == "mc"
    ej = json.loads((trees / "ex-mc" / "experiment.json").read_text())
    assert ej["format"] == "fake-experiment/2" and ej["runs"][0]["app_json"] == "20260101T000000Z.fake.json"


def test_the_defaults_of_the_base_kind(trees, fake):
    assert fake.plot(None, None, "mc", []) is None and fake.pending(None, None) == {}
    assert fake.extra_forms() == {} and fake.commands() == {} and fake.instance_axis is None
    assert fake.seen({}, "m") is True and fake.is_point_agg("n", "max(p99)") is False and fake.width({}, "n", None) == 1
    with pytest.raises(NoValue):
        fake.central_result({}, None, None)
    build.build(trees, log=lambda *a: None)
    sj = json.loads((trees / "study.json").read_text())
    assert sj["central_results"] == []
