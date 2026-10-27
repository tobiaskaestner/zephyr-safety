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
    record("20260101T000001Z", "running", 99999999, [("exp1", "planned")])     # its process is gone
    record("20260101T000002Z", "done", os.getpid(), [("exp1", "planned")])
    assert campaign.pending(lab, design) == {(str(f), "exp2"): "20260101T000000Z"}
    # a campaign in its pre-flight check: the experiments have no instance yet
    jsonout.write(lab.campaigns / "20260101T000003Z.json", {
        "id": "20260101T000003Z", "status": "planned", "pid": os.getpid(), "host": platform.node(),
        "lab": lab.describe(), "experiments": [{"experiment": "exp1", "study": "sub", "board": "nucleo_g474re",
                                                 "state": "planned"}]})
    assert campaign.pending(lab, design)[(str(f), "exp1")] == "20260101T000003Z"


def test_lock_allows_one_campaign(setup):
    lab, design, root = setup
    campaign.take_lock(lab, "a")
    with pytest.raises(campaign.CampaignError):
        campaign.take_lock(lab, "b")
    campaign.drop_lock(lab, "a")
    campaign.take_lock(lab, "b")
    campaign.drop_lock(lab, "b")
    assert not lab.lock.exists()


FAKE_RUN = '''
import json, sys, time
from pathlib import Path
sys.path.insert(0, {scripts!r})
from studylib import seal
exp = Path(sys.argv[1]).parent.name[3:]
out = Path(sys.argv[sys.argv.index("--out") + 1])
if exp == "exp-fail":
    sys.exit("error: the board did not answer")
run = out / ("ex-" + exp) / time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
while run.exists():
    time.sleep(0.2)
    run = out / ("ex-" + exp) / time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
run.mkdir(parents=True)
(run / "manifest.json").write_text(json.dumps({{"experiment": exp, "board": "nucleo_g474re", "points": []}}))
seal.write(run)
print("results in", run)
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
    fake.write_text(FAKE_RUN.format(scripts=str(SCRIPTS)))
    monkeypatch.setattr(campaign, "run_py", lambda: fake)
    monkeypatch.setattr(campaign, "preflight", lambda *a, **k: [("ok", "fake", "")])
    monkeypatch.setattr(campaign.Post, "kick", lambda self: None)
    monkeypatch.setattr(trees, "repo_state", lambda path: ("r" * 40, ""))
    monkeypatch.setattr(trees, "git", lambda *a, **k: "")
    monkeypatch.chdir(lab.folder)
    items = campaign.plan(lab, root, design=design, board="nucleo_g474re")
    rec = campaign.new_record(lab, root, "nucleo_g474re", items, ["study.py", "campaign", "run"])
    failed = campaign.run_campaign(rec, design=design, log=lambda *a: None)
    assert failed == 1
    data = campaign.Record(lab, rec.id).data
    states = [(e["experiment"], e["state"]) for e in data["experiments"]]
    assert states == [("exp-fail", "failed"), ("exp1", "done"), ("exp2", "skipped")]
    assert data["status"] == "done" and not lab.lock.exists()
    from studylib import instance
    folder = lab.results / data["experiments"][1]["instance"]
    assert [r["id"] for r in instance.load(folder)["runs"]] == [data["experiments"][1]["run"]]
    assert "board did not answer" in (lab.folder / data["experiments"][0]["log"]).read_text()
    # resume: only the failed experiment runs again; a changed repo stops the campaign
    monkeypatch.setattr(trees, "repo_state", lambda path: ("r" * 40, " M x"))
    with pytest.raises(campaign.CampaignError):
        campaign.run_campaign(campaign.Record(lab, rec.id), design=design, log=lambda *a: None)
