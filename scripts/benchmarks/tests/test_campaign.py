# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Unit tests of the campaign plan, the instances it makes and the pending experiments."""

import os
import platform
import sys
from pathlib import Path

import pytest
import yaml

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import trees  # noqa: E402
from studylib import campaign, jsonout  # noqa: E402
from studylib import lab as labmod  # noqa: E402
from studylib.design import Design  # noqa: E402
from test_studylib import make_design  # noqa: E402


@pytest.fixture
def setup(tmp_path, monkeypatch):
    make_design(tmp_path)
    root = tmp_path / "design"
    sub = root / "st-sub"
    (sub / "ex-exp2").mkdir()
    (sub / "ex-exp2" / "experiment.yaml").write_text(yaml.safe_dump({
        "name": "exp2", "app": "wake_latency", "board": "nrf54l15dk/nrf54l15/cpuapp", "trees": ["ws-up"],
        "axes": {"variant": {"a": {}}}}))
    (sub / "ex-exp2" / "experiment.md").write_text("# exp2\n")
    d = yaml.safe_load((sub / "study.yaml").read_text())
    d["experiments"].append("exp2")
    (sub / "study.yaml").write_text(yaml.safe_dump(d))
    monkeypatch.setattr(trees, "STUDIES_DIR", root)
    repo = tmp_path / "safety"
    (repo / "scripts" / "benchmarks").mkdir(parents=True)
    (repo / "scripts" / "benchmarks" / "study.py").write_text("")
    lab = labmod.init(tmp_path / "lab", repo)
    return lab, Design(root), root


def test_plan_order_and_board(setup):
    lab, design, root = setup
    items = campaign.plan(lab, root, design=design, board="nucleo_g474re")
    assert [(e["experiment"], e["state"]) for e in items] == [("exp1", "planned"), ("exp2", "skipped")]
    assert "nrf54l15dk" in items[1]["note"]
    items = campaign.plan(lab, root / "st-sub" / "ex-exp2", design=design)
    assert [(e["experiment"], e["board"]) for e in items] == [("exp2", "nrf54l15dk/nrf54l15/cpuapp")]
    assert [e["state"] for e in campaign.plan(lab, root, design=design, skip=["exp1"])] == ["skipped", "planned"]
    with pytest.raises(campaign.CampaignError):
        campaign.plan(lab, root, design=design, only=["nope"])


def test_ensure_instance_makes_it_once(setup):
    lab, design, root = setup
    f = campaign.ensure_instance(lab, design, "sub", "nucleo_g474re", log=lambda *a: None)
    assert f == lab.results / "top" / "st-sub@nucleo_g474re"
    assert campaign.ensure_instance(lab, design, "sub", "nucleo_g474re", log=lambda *a: None) == f
    # an instance folder resolves to its study and board
    assert campaign.resolve(lab, f, design) == ("sub", None, "nucleo_g474re")
    items = campaign.plan(lab, f / "ex-exp1", design=design)
    assert [e["experiment"] for e in items] == ["exp1"]


def test_pending_counts_running_campaigns_only(setup):
    lab, design, root = setup
    f = campaign.ensure_instance(lab, design, "sub", "nucleo_g474re", log=lambda *a: None)
    inst = str(f.relative_to(lab.results))

    def record(cid, status, pid, states):
        jsonout.write(lab.campaigns / f"{cid}.json", {
            "id": cid, "status": status, "pid": pid, "host": platform.node(), "lab": lab.describe(),
            "experiments": [{"experiment": e, "instance": inst, "state": s} for e, s in states]})

    record("20260101T000000Z", "running", os.getpid(), [("exp1", "done"), ("exp2", "planned")])
    record("20260101T000001Z", "running", 99999999, [("exp1", "planned")])     # it does not hold the lock
    record("20260101T000002Z", "done", os.getpid(), [("exp1", "planned")])
    assert campaign.pending(lab, design) == {}                                  # no campaign holds the lock
    campaign.take_lock(lab, "20260101T000000Z")
    assert campaign.pending(lab, design) == {(str(f), "exp2"): "20260101T000000Z"}
    campaign.drop_lock(lab, "20260101T000000Z")
    # a campaign in its pre-flight check: the experiments have no instance yet
    jsonout.write(lab.campaigns / "20260101T000003Z.json", {
        "id": "20260101T000003Z", "status": "planned", "pid": os.getpid(), "host": platform.node(),
        "lab": lab.describe(), "experiments": [{"experiment": "exp1", "study": "sub", "board": "nucleo_g474re",
                                                 "state": "planned"}]})
    campaign.take_lock(lab, "20260101T000003Z")
    assert campaign.pending(lab, design)[(str(f), "exp1")] == "20260101T000003Z"
    campaign.drop_lock(lab, "20260101T000003Z")
    # an imported running record (of another lab space) counts without a lock here
    jsonout.write(lab.campaigns / "20260101T000004Z@other.json", {
        "id": "20260101T000004Z", "status": "running", "host": "elsewhere", "lab": {"id": "other"},
        "experiments": [{"experiment": "exp1", "instance": inst, "state": "planned"}]})
    assert campaign.pending(lab, design) == {(str(f), "exp1"): "20260101T000004Z@other"}


def test_lock_allows_one_campaign(setup):
    lab, design, root = setup
    campaign.take_lock(lab, "a")
    with pytest.raises(campaign.CampaignError):
        campaign.take_lock(lab, "b")
    campaign.drop_lock(lab, "a")
    campaign.take_lock(lab, "b")
    assert campaign.lock_holder(lab) == "b"
    campaign.drop_lock(lab, "b")
    assert campaign.lock_holder(lab) is None


FAKE_RUN = '''
import json, sys, time
from pathlib import Path
sys.path.insert(0, {scripts!r})
from studylib import instance, seal
from studylib.design import Design
exp = Path(sys.argv[1]).parent.name[3:]
arg = lambda k: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else None
out = Path(arg("--out"))
run = out / ("ex-" + exp) / time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
while run.exists():
    time.sleep(0.2)
    run = out / ("ex-" + exp) / time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
run.mkdir(parents=True)
if exp == "exp-fail":
    (run.parent / (run.name + ".failed.json")).write_text(json.dumps({{"step": "flash", "error": "no answer"}}))
    sys.exit("error: the board did not answer")
(run / "manifest.json").write_text(json.dumps({{"experiment": exp, "board": "nucleo_g474re",
                                                "points": [{{"build": {{"from": "cache"}}}}, {{"build": {{"from": "build"}}}}]}}))
seal.write(run)
print("results in", run)
rid = instance.add(Design({root!r}), out, run, role=arg("--role"), reason=arg("--reason"), campaign=arg("--campaign"))
print(f"run {{rid}} added to the instance {{out}}")
'''


def test_run_campaign_with_a_fake_run(setup, monkeypatch, tmp_path):
    lab, design, root = setup
    fail = root / "st-sub" / "ex-exp-fail"
    fail.mkdir()
    (fail / "experiment.yaml").write_text(yaml.safe_dump({"name": "exp-fail", "app": "wake_latency",
                                                          "trees": ["ws-up"], "axes": {"variant": {"a": {}}}}))
    (fail / "experiment.md").write_text("# exp-fail\n")
    d = yaml.safe_load((root / "st-sub" / "study.yaml").read_text())
    d["experiments"].insert(0, "exp-fail")
    (root / "st-sub" / "study.yaml").write_text(yaml.safe_dump(d))
    design = Design(root)
    fake = tmp_path / "fake_run.py"
    fake.write_text(FAKE_RUN.format(scripts=str(SCRIPTS), root=str(root)))
    monkeypatch.setattr(campaign, "run_py", lambda: fake)
    monkeypatch.setattr(campaign, "preflight", lambda *a, **k: [("ok", "fake", "")])
    monkeypatch.setattr(campaign.Post, "kick", lambda self: None)
    monkeypatch.setattr(trees, "repo_state", lambda path: ("r" * 40, ""))
    monkeypatch.setattr(trees, "git", lambda *a, **k: "")
    monkeypatch.chdir(lab.folder)
    items = campaign.plan(lab, root, design=design, board="nucleo_g474re")
    with pytest.raises(campaign.CampaignError):           # a role other than evidence needs a reason
        campaign.new_record(lab, root, "nucleo_g474re", items, ["x"], role="adjustment")
    rec = campaign.new_record(lab, root, "nucleo_g474re", items, ["study.py", "campaign", "run"],
                              role="adjustment", reason="a test of the tools")
    lines = []
    failed = campaign.run_campaign(rec, design=design, log=lines.append)
    assert failed == 1
    assert any(ln.startswith("    done (rc 0) in ") and "1/2 images from the build cache" in ln for ln in lines)
    data = campaign.Record(lab, rec.id).data
    states = [(e["experiment"], e["state"]) for e in data["experiments"]]
    assert states == [("exp-fail", "failed"), ("exp1", "done"), ("exp2", "skipped")]
    assert data["status"] == "done" and campaign.lock_holder(lab) is None
    from studylib import instance
    folder = lab.results / data["experiments"][1]["instance"]
    runs = instance.load(folder)["runs"]
    assert [r["id"] for r in runs] == [data["experiments"][1]["run"]]
    assert (runs[0]["role"], runs[0]["reason"], runs[0]["campaign"]) == ("adjustment", "a test of the tools", rec.id)
    assert "board did not answer" in (lab.folder / data["experiments"][0]["log"]).read_text()
    assert "failed at 'flash': no answer" in data["experiments"][0]["note"]
    # resume: only the failed experiment runs again; a changed repo stops the campaign
    monkeypatch.setattr(trees, "repo_state", lambda path: ("r" * 40, " M x"))
    with pytest.raises(campaign.CampaignError):
        campaign.run_campaign(campaign.Record(lab, rec.id), design=design, log=lambda *a: None)


def test_resume_counts_failed_experiments_as_pending(setup, monkeypatch):
    lab, design, root = setup
    f = campaign.ensure_instance(lab, design, "sub", "nucleo_g474re", log=lambda *a: None)
    items = campaign.plan(lab, root, design=design, board="nucleo_g474re")
    items[0].update(state="failed", instance=str(f.relative_to(lab.results)))
    monkeypatch.setattr(trees, "repo_state", lambda path: ("r" * 40, ""))
    rec = campaign.new_record(lab, root, "nucleo_g474re", items, ["x"])
    seen = {}

    def preflight(*a, **k):
        seen.update(campaign.pending(lab, design))
        return [("fail", "stop here", "")]
    monkeypatch.setattr(campaign, "preflight", preflight)
    monkeypatch.setattr(trees, "git", lambda *a, **k: "")
    campaign.run_campaign(rec, design=design, log=lambda *a: None)
    assert seen == {(str(f), "exp1"): rec.id}


def test_post_runs_one_build_at_a_time(setup, monkeypatch, tmp_path):
    lab, design, root = setup
    rec = campaign.Record(lab, "20260101T000000Z")
    rec.data = {"id": rec.id}
    rec.log_dir.mkdir(parents=True)
    started = []

    class Proc:
        def __init__(self, *a, **k):
            self.done, self.returncode = False, 0
            started.append(self)

        def poll(self):
            return 0 if self.done else None

        def wait(self):
            self.done = True
    monkeypatch.setattr(campaign.subprocess, "Popen", Proc)
    post = campaign.Post(rec, tmp_path)
    post.kick()                     # build 1 starts
    post.kick()                     # build 1 runs: one more later
    post.kick()                     # still only one more
    assert len(started) == 1
    started[0].done = True
    post.poll()                     # build 1 ended: build 2 starts
    assert len(started) == 2 and post.proc is started[1]
    post.wait()
    assert len(started) == 2 and [x["n"] for x in rec.data["post"]] == [1, 2]
