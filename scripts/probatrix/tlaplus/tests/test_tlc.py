# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The TLC adapter (tlc.py) on a copy of a real lab run and on a synthetic simulation run.

fixtures/lab-c20993e   a trimmed copy of the lab run 20261031-023823-c20993ed8 (the evidence run of the 67 lines
                       of mc/expected.txt): job.json, meta.env, results.txt, out/results.tsv, 4 of the 67 logs,
                       the selftest (results.tsv and the 2 logs of SelfRepro), and subject.json, which the importer
                       will write (made with subject.record at that revision). expected.txt is the list of that
                       revision.
fixtures/simulate      SYNTHETIC. No TLC simulation run exists yet. See fixtures/simulate/SYNTHETIC.txt.
"""

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from probatrix.core import build, config, seal
from probatrix.tlaplus import kind, lists, tlc

K = kind.KIND
FIX = Path(__file__).resolve().parent / "fixtures"
LAB, SIM = FIX / "lab-c20993e", FIX / "simulate"
REPO = config.project().repo
UTC = "20261031T013824Z"
PIN = "5bd7b64db99ae4c6c35f290de5e809c0ee41af43f8699cf696099ffb6452b1e2"


def copy_run(src, dst):
    shutil.copytree(src, dst)
    return dst


def edit_json(path, **kw):
    data = json.loads(path.read_text())
    data.update(kw)
    path.write_text(json.dumps(data))


def edit_meta(path, **kw):
    meta = tlc.read_meta(path.read_text())
    meta.update(kw)
    path.write_text("".join(f"{k}={v}\n" for k, v in meta.items()))


# ------------------------------------------------------------ the files of a raw run
def test_meta_and_rows():
    assert tlc.read_meta("a=1\nb=x=y\nnoequals\n") == {"a": "1", "b": "x=y"}
    rows = tlc.read_rows(LAB / "out" / "results.tsv")
    assert len(rows) == 67 and rows[0]["module"] == "WaitQueueTest" and set(rows[0]) == set(tlc.TSV_COLUMNS)
    assert tlc.read_rows(LAB / "nothing.tsv") == []
    assert len(tlc.read_rows(LAB / "selftest" / "results.tsv")) == 13


def test_both_layouts_are_read(tmp_path):
    """A run of the lab has out/; the copy of run_tlc_remote.py collect has the files of out/ in the run folder."""
    flat = copy_run(LAB, tmp_path / "flat")
    for f in (flat / "out").iterdir():
        shutil.move(f, flat / f.name)
    (flat / "out").rmdir()
    a, b = tlc.Raw(LAB), tlc.Raw(flat)
    assert a.rows == b.rows and a.prefix == "out/" and b.prefix == ""
    assert a.log(a.rows[0]) == "out/WaitQueueTest_default.log" and b.log(b.rows[0]) == "WaitQueueTest_default.log"


def test_a_run_without_results_is_an_error(tmp_path):
    run = copy_run(LAB, tmp_path / "r")
    (run / "out" / "results.tsv").unlink()
    with pytest.raises(FileNotFoundError, match="no results.tsv"):
        tlc.Raw(run)


# ------------------------------------------------------------ the evidence rule
JOB = {"mode": "pinned", "workers": 1, "selftest": True}
META = {"selftest_status": "0", "jar_sha256": PIN}


def test_the_evidence_rule_one_reason_at_a_time():
    assert tlc.evidence_reasons(JOB, META, PIN) == []
    assert tlc.evidence_reasons({**JOB, "mode": "unpinned"}, META, PIN) == ["unpinned: the code is not a commit"]
    assert tlc.evidence_reasons({**JOB, "workers": 2}, META, PIN) == [
        "2 workers in one TLC process (tlaplus issue #1445)"]
    assert tlc.evidence_reasons({**JOB, "selftest": False}, META, PIN) == ["no selftest"]
    assert tlc.evidence_reasons(JOB, {**META, "selftest_status": "1"}, PIN) == ["the selftest failed (status 1)"]
    assert tlc.evidence_reasons(JOB, {**META, "selftest_status": None}, PIN) == [
        "the selftest failed (status None)"]
    assert tlc.evidence_reasons(JOB, {**META, "jar_sha256": "ff"}, PIN) == ["the jar is not the pinned jar"]
    assert tlc.evidence_reasons(JOB, {"selftest_status": "0"}, PIN) == ["the jar is not the pinned jar"]
    assert tlc.evidence_reasons(JOB, META, None) == ["the pin of the jar is not known"]
    assert len(tlc.evidence_reasons({"mode": "unpinned", "workers": 3}, {}, PIN)) == 4      # all of them, in order


def load_rtr(monkeypatch, tmp_path):
    """run_tlc_remote.py as a module, with SPEC pointed at a folder that has the pin of the fixture."""
    spec = importlib.util.spec_from_file_location("run_tlc_remote", REPO / "spec/tla/tools/run_tlc_remote.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    (tmp_path / "spec" / "tools").mkdir(parents=True)
    (tmp_path / "spec" / "tools" / "tla2tools.sha256").write_text(PIN + "  tla2tools.jar\n")
    monkeypatch.setattr(mod, "SPEC", tmp_path / "spec")
    return mod


class FakeLab:
    """The lab host of run_tlc_remote.py collect: rsync copies from a folder, in the layout of the lab."""
    host, root = "lab", "/LAB"

    def __init__(self, run_dir):
        self.run_dir = Path(run_dir)

    def rsync(self, *args, check=True):
        src, dest = args[-2].split(":", 1)[1], Path(args[-1])
        rel = src.split("/runs/", 1)[1].split("/", 1)[1]
        origin = self.run_dir / rel
        if src.endswith("/"):
            if origin.is_dir():
                shutil.copytree(origin, dest, dirs_exist_ok=True,
                                ignore=shutil.ignore_patterns("states", "tmp"))
        elif origin.is_file():
            shutil.copy(origin, dest)
        elif check:
            raise RuntimeError(f"rsync: no {rel}")


VARIANTS = {
    "evidence": lambda run: None,
    "unpinned": lambda run: edit_json(run / "job.json", mode="unpinned"),
    "two-workers": lambda run: edit_json(run / "job.json", workers=2),
    "no-selftest": lambda run: edit_json(run / "job.json", selftest=False),
    "selftest-failed": lambda run: edit_meta(run / "meta.env", selftest_status="1"),
    "other-jar": lambda run: edit_meta(run / "meta.env", jar_sha256="ab" * 32),
    "several": lambda run: (edit_json(run / "job.json", mode="unpinned", workers=4),
                            edit_meta(run / "meta.env", selftest_status="2")),
}


@pytest.mark.parametrize("variant", VARIANTS)
def test_the_evidence_of_the_adapter_is_the_evidence_of_the_original_collect(variant, monkeypatch, tmp_path):
    """Run the original collect() of run_tlc_remote.py (unchanged in this step) on a copy of the lab run, and compare its
    record.json with the adapter: evidence, reasons and the result of each line."""
    rtr = load_rtr(monkeypatch, tmp_path / "pin")
    lab_run = copy_run(LAB, tmp_path / "lab" / "runs" / "ID")
    for f in ("job.log", "job.sh"):
        (lab_run / f).write_text("")
    VARIANTS[variant](lab_run)
    out = tmp_path / "out"
    rtr.collect(FakeLab(lab_run), "ID", out)
    record = json.loads((out / "record.json").read_text())
    # the adapter reads the run folder as the importer will leave it: lab layout + subject.json
    run = lab_run
    raw = tlc.Raw(run)
    ev, reasons = tlc.evidence_of(raw)
    assert (ev, reasons) == (record["evidence"], record["not_evidence_reasons"])
    assert ev is (variant == "evidence")
    app = tlc.app_json(run, "tlc", "mc-expected/" + UTC, "sha256:x", {"tool": "t", "safety_rev": "r"})
    got = [(p["point"], p["reps"][0]["values"]) for p in app["points"]]
    assert [g[0] for g in got] == [f"{r['module']}:{r['config']}" for r in record["results"]]
    for (_, v), r in zip(got, record["results"]):
        assert (v["verdict"], v["expected"], v["evidence"]) == (r["result"], r["expected"], record["evidence"])
        assert v.get("states") == (int(r["distinct"]) if r["distinct"].isdigit() else None)
        assert v.get("depth") == (int(r["depth"]) if r["depth"].isdigit() else None)
        assert v["seconds"] == float(r["seconds"]) and v["runner_verdict"] == r["verdict"]
    if record["selftest"] is None:                  # a run without selftest (the original records None too)
        assert app["selftest"] is None
    else:
        assert app["selftest"]["status"] == record["selftest"]["status"] and len(record["selftest"]["results"]) == 13
        assert app["selftest"]["lines"] == 13 and app["selftest"]["unexpected"] == []


def test_the_fixture_is_the_evidence_run_of_the_notes():
    raw = tlc.Raw(LAB)
    assert tlc.evidence_of(raw) == (True, [])
    assert raw.job["revision"] == "c20993ed8e7a61e1da23f3f9316802608a461445" and raw.job["workers"] == 1
    assert raw.subject["jar_pin"] == PIN and raw.meta["jar_sha256"] == PIN
    assert raw.tool == "tlc" and raw.meta["status"] == "0"


def test_no_subject_record_means_no_evidence(tmp_path):
    run = copy_run(LAB, tmp_path / "r")
    (run / "subject.json").unlink()
    assert tlc.evidence_of(tlc.Raw(run)) == (False, ["the pin of the jar is not known"])


# ------------------------------------------------------------ run.json and the app data
MADE_BY = {"tool": "scripts/probatrix/study.py", "safety_rev": "abc"}


def test_run_json_of_the_lab_run(tmp_path):
    run = copy_run(LAB, tmp_path / "run")
    digest = seal.write(run)
    rj = tlc.run_json(run, "mc-expected/" + UTC, digest, MADE_BY)
    assert rj["format"] == "tlaplus-run/1" and rj["made_by"] == MADE_BY
    r = rj["run"]
    assert (r["id"], r["digest"], r["experiment"], r["app"], r["tool"]) == ("mc-expected/" + UTC, digest, "mc-expected", "tlc", "tlc")
    assert r["lab_id"] == "20261031-023823-c20993ed8" and r["mode"] == "pinned" and r["workers"] == 1
    assert r["safety_rev"] == "c20993ed8e7a61e1da23f3f9316802608a461445" == r["revision"]
    assert r["evidence"] is True and r["not_evidence_reasons"] == [] and r["status"] == 0
    assert r["jar_sha256"] == PIN and r["host"] == "cos-workstation" and r["selftest"] == {
        "status": "0", "lines": 13, "unexpected": []}
    assert r["subject"]["subject_tree"].startswith("sha256:")
    assert len(rj["points"]) == 67
    p = rj["points"][0]
    assert p["tree"] == "tlc" and p["point"] == "WaitQueueTest:default" and p["axes"] == {}
    # 4 of the 67 logs are in the fixture: the others have no log in the run folder
    logged = {p["point"]: p["reps"][0] for p in rj["points"] if p["reps"][0]["log"]}
    assert sorted(logged) == ["KSemTest:default", "MCKSem:default", "MCKSem:isr_waits", "MCKSem:live"]
    assert logged["MCKSem:live"]["log"] == "out/MCKSem_live.log"
    assert logged["MCKSem:live"]["log_sha256"] == seal.files(run)["out/MCKSem_live.log"]
    assert rj["points"][-1]["reps"][0] == {"rep": 1, "log": None, "log_sha256": None}


def values(app, point):
    return next(p for p in app["points"] if p["point"] == point)["reps"][0]["values"]


def test_app_data_of_the_lab_run(tmp_path):
    run = copy_run(LAB, tmp_path / "run")
    app = tlc.app_json(run, "tlc", "mc-expected/" + UTC, seal.write(run), MADE_BY)
    assert app["format"] == "tlaplus-app-tlc/1" and app["app"] == "tlc" and app["tool"] == "tlc"
    assert app["made_by"] == {**MADE_BY, "adapter": "scripts/probatrix/tlaplus/tlc.py"}
    assert app["evidence"] is True and len(app["points"]) == 67
    assert app["points"][0]["params"] == {} and app["points"][0]["reps"][0]["rep"] == 1
    # a pass line with counts
    v = values(app, "MCKSem:default")
    assert v["verdict"] == "pass" and v["expected"] == "pass" and v["evidence"] is True
    assert isinstance(v["states"], int) and isinstance(v["depth"], int) and isinstance(v["seconds"], float)
    assert v["workers"] == 1 and v["heap"] == "2g" and v["runner_verdict"] == "as expected"
    assert "violated" not in v and "trace_len" not in v
    # a fail line: the violated property and the length of the trace, and no counts for lines that have none "?"
    f = values(app, "MCKSem:live_prio")
    assert f["verdict"] == "fail:Live_WaiterServedIfGives" and f["violated"] == "Live_WaiterServedIfGives"
    assert isinstance(f["trace_len"], int) and f["lasso"] not in ("-", "?")
    # the types of all values are the types that the kind names
    for p in app["points"]:
        for k, x in p["reps"][0]["values"].items():
            assert isinstance(x, kind.VALUES[k]) and (k == "evidence" or not isinstance(x, bool)), (p["point"], k)


def test_the_states_and_depth_are_those_of_the_list():
    """Each count that expected.txt records is the count of the run (the lab run gave status 0)."""
    app = tlc.app_json(LAB, "tlc", "mc-expected/" + UTC, "sha256:x", MADE_BY)
    by = {p["point"]: p["reps"][0]["values"] for p in app["points"]}
    counted = 0
    for ln in lists.read(FIX / "lab-c20993e" / "expected.txt", lists.TLC_KEYS):
        v = by[ln.id]
        assert v["verdict"] == v["expected"] == ln.expected
        for key in ("states", "depth"):
            if key in ln.fields:
                assert v[key] == int(ln.fields[key])
                counted += 1
    assert counted == 50 and len(by) == 67


def test_the_tool_without_an_adapter_is_an_error(tmp_path):
    run = copy_run(LAB, tmp_path / "r")
    edit_json(run / "job.json", tool="apalache")
    with pytest.raises(ValueError, match="no adapter in tlc.py"):
        tlc.Raw(run)


# ------------------------------------------------------------ simulation (a synthetic run)
def test_the_simulation_log():
    assert tlc.simulation_states("a\nThe number of states generated: 48,210\nSimulation finished.\n") == 48210
    assert tlc.simulation_states("The number of states generated: 3\nThe number of states generated: 9\n") == 9
    assert tlc.simulation_states("no such line\n") is None


def test_the_simulation_run_has_parameters_and_the_generated_states(tmp_path):
    run = copy_run(SIM, tmp_path / "run")
    assert "synthetic" in (run / "SYNTHETIC.txt").read_text()
    rj = tlc.run_json(run, "sim/" + UTC, seal.write(run), MADE_BY)
    assert rj["run"]["tool"] == "tlc-simulate" and rj["run"]["app"] == "tlc" and rj["run"]["evidence"] is True
    assert [p["tree"] for p in rj["points"]] == ["tlc-simulate"] * 3
    app = tlc.app_json(run, "tlc", "sim/" + UTC, "sha256:x", MADE_BY)
    assert app["tool"] == "tlc-simulate"
    assert [p["params"] for p in app["points"]] == [{"depth": 100, "traces": 500, "seed": 7},
                                                    {"depth": 20, "traces": 500, "seed": 7},
                                                    {"depth": 100, "traces": 50, "seed": -3}]
    assert [values(app, p)["states"] for p in ("MCKSem:default", "MCKSem:live", "MCKSem:poll")] == [48210, 1203, 87]
    v = values(app, "MCKSem:live")
    assert v["verdict"] == "fail:Inv_NoPanic" and v["violated"] == "Inv_NoPanic" and v["trace_len"] == 5
    assert "depth" not in v                       # no depth of the state graph in simulation mode
    assert values(app, "MCKSem:poll")["runner_verdict"].startswith("UNEXPECTED")


def test_a_simulation_run_needs_the_parameters_of_each_line(tmp_path):
    run = copy_run(SIM, tmp_path / "run")
    job = json.loads((run / "job.json").read_text())
    del job["simulate"]["MCKSem:poll"]
    (run / "job.json").write_text(json.dumps(job))
    with pytest.raises(ValueError, match="no simulate parameters .* for MCKSem:poll"):
        tlc.app_json(run, "tlc", "sim/" + UTC, "sha256:x", MADE_BY)


def test_a_simulation_run_without_a_log_has_no_states(tmp_path):
    run = copy_run(SIM, tmp_path / "run")
    (run / "out" / "MCKSem_poll.log").unlink()
    app = tlc.app_json(run, "tlc", "sim/" + UTC, "sha256:x", MADE_BY)
    assert "states" not in values(app, "MCKSem:poll")


# ------------------------------------------------------------ the core build over the adapter
def make_tree(tmp_path, run_src, experiment, list_text, hypotheses, runs_tool_dir=None):
    """A design (one study, one experiment, kind tlaplus), a repo folder with the list, a results tree with one
    sealed run (a copy of run_src), as in core/tests/test_generic_kind.py."""
    repo = tmp_path / "repo"
    (repo / "spec/tla/mc").mkdir(parents=True)
    (repo / "spec/tla/mc/l.txt").write_text(list_text)
    design, results = repo / "design", tmp_path / "results" / "top"
    (design / "ex-mc").mkdir(parents=True)
    (design / "study.yaml").write_text(yaml.safe_dump({"name": "top", "kind": "tlaplus", "question": "q", "experiments": ["mc"]}))
    (design / "ex-mc" / "experiment.yaml").write_text(yaml.safe_dump({
        "name": "mc", "tool": "tlc", "list": "spec/tla/mc/l.txt", "subject": ["spec/tla/mc"],
        "tools": ["spec/tla/mc"], **experiment}))
    (design / "ex-mc" / "experiment.md").write_text("x")
    (design / "hypotheses.yaml").write_text(yaml.safe_dump({"hypotheses": hypotheses}))
    run = copy_run(run_src, results / "ex-mc" / UTC)
    return repo, design, results, run


def finish(repo, design, results, run):
    digest = seal.write(run)
    (results / "instance.json").write_text(json.dumps({
        "format": K.format_id("instance", 1), "instance": "top", "runs": [{"id": f"mc/{UTC}", "digest": digest, "role": "evidence"}],
        "references": [], "substudies": [], "manual_verdicts": [], "notes": []}))
    project = config.Project.at(repo, design_root=design, roots=(config.Root(design, "tlaplus"),))
    with config.use(project):
        tree, _ = build.build(results, log=lambda *a: None)
    return tree, json.loads((results / "study.json").read_text())


H1 = [{"id": "H1", "statement": "The run is evidence.", "checks": [
    {"id": "a", "experiment": "mc", "metric": "evidence", "expect": {"equals": True}}]}]


def test_the_core_builds_the_lab_run(tmp_path):
    list_text = (LAB / "expected.txt").read_text()
    repo, design, results, run = make_tree(tmp_path, LAB, {}, list_text, H1)
    tree, sj = finish(repo, design, results, run)
    assert tree.kind is K and tree.axis is None
    assert sj["format"] == "tlaplus-study/2" and sj["made_by"]["tool"] == "scripts/probatrix/study.py"
    verdicts = {h["id"]: h["verdict"] for h in sj["hypotheses"]}
    assert verdicts == {"H1": "confirmed", "mc-generated": "confirmed"}
    gen = next(h for h in sj["hypotheses"] if h["id"] == "mc-generated")
    assert gen["checks_confirmed"] == "117 of 117"            # 67 verdicts + 25 states + 25 depths
    assert len(gen["checks"]) == 117
    ej = json.loads((results / "ex-mc" / "experiment.json").read_text())
    assert ej["format"] == "tlaplus-experiment/2" and ej["runs"][0]["app_json"] == f"{UTC}.tlc.json"
    assert (results / "ex-mc" / f"{UTC}.run.json").is_file() and (results / "ex-mc" / f"{UTC}.tlc.json").is_file()
    assert json.loads((results / "ex-mc" / f"{UTC}.tlc.json").read_text())["format"] == "tlaplus-app-tlc/1"


def test_a_wrong_verdict_and_a_wrong_count_make_the_generated_hypothesis_wrong(tmp_path):
    list_text = (LAB / "expected.txt").read_text()
    repo, design, results, run = make_tree(tmp_path, LAB, {}, list_text, H1)
    rows = (run / "out" / "results.tsv").read_text().splitlines()
    out = []
    for ln in rows:
        c = ln.split("\t")
        if c[:2] == ["MCKSem", "default"]:
            c[3] = "fail:Inv_X"                                   # another verdict
        if c[:2] == ["MCKSem", "live"]:
            c[6] = "1"                                            # another count (if the line has one)
        out.append("\t".join(c))
    (run / "out" / "results.tsv").write_text("\n".join(out) + "\n")
    tree, sj = finish(repo, design, results, run)
    gen = next(h for h in sj["hypotheses"] if h["id"] == "mc-generated")
    assert gen["verdict"] == "wrong"
    wrong = [c["id"] for c in gen["checks"] if c["verdict"] != "confirmed"]
    assert wrong == ["MCKSem:default-verdict"] or "MCKSem:default-verdict" in wrong
    assert next(h for h in sj["hypotheses"] if h["id"] == "H1")["verdict"] == "confirmed"      # a violated property is not a non-evidence run


def test_an_unpinned_run_is_not_evidence_but_its_results_are_still_checked(tmp_path):
    list_text = (LAB / "expected.txt").read_text()
    repo, design, results, run = make_tree(tmp_path, LAB, {}, list_text, H1)
    edit_json(run / "job.json", mode="unpinned")
    tree, sj = finish(repo, design, results, run)
    verdicts = {h["id"]: h["verdict"] for h in sj["hypotheses"]}
    assert verdicts == {"H1": "wrong", "mc-generated": "confirmed"}


def test_the_core_builds_the_simulation_run(tmp_path):
    list_text = "MCKSem default pass\nMCKSem live fail:Inv_NoPanic depth=20\nMCKSem poll pass seed=-3 traces=50\n"
    repo, design, results, run = make_tree(
        tmp_path, SIM, {"tool": "tlc-simulate", "simulate": {"depth": 100, "traces": 500, "seed": 7}}, list_text, H1)
    tree, sj = finish(repo, design, results, run)
    gen = next(h for h in sj["hypotheses"] if h["id"] == "mc-generated")
    assert {c["id"]: c["verdict"] for c in gen["checks"]} == {
        "MCKSem:default-verdict": "confirmed", "MCKSem:live-verdict": "confirmed", "MCKSem:poll-verdict": "wrong"}
    assert gen["verdict"] == "wrong" and gen["checks_confirmed"] == "2 of 3"
    # the parameters of the points agree with the job of the run
    with config.use(config.Project.at(repo)):
        exp = yaml.safe_load((design / "ex-mc" / "experiment.yaml").read_text())
        params = {p["id"]: p["params"] for p in K.points(exp)}
    app = json.loads((results / "ex-mc" / f"{UTC}.tlc.json").read_text())
    assert params == {p["point"]: p["params"] for p in app["points"]}


def test_two_imports_of_the_same_raw_files_give_the_same_digest(tmp_path):
    """The seal depends on the file set only: the raw files of the fixture give one digest."""
    a, b = copy_run(LAB, tmp_path / "a" / "x"), copy_run(LAB, tmp_path / "b" / "x")
    assert seal.write(a) == seal.write(b)


def test_git_is_not_run_by_the_adapter(tmp_path, monkeypatch):
    """The adapter reads files only: it works in a folder that is not in a git repo."""
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("a subprocess ran"))
    run = copy_run(LAB, tmp_path / "run")
    tlc.app_json(run, "tlc", "x/" + UTC, "sha256:x", MADE_BY)
