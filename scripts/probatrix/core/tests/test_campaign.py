# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Unit tests of core/campaign.py with a fake kind: no board, no resource, then a resource with a lock."""

import json
import sys
from types import SimpleNamespace

import pytest

from probatrix.core import campaign as eng
from probatrix.core.errors import CampaignError
from probatrix.core.kinds import BaseKind


class FakeKind(BaseKind):
    name = "fake"
    schema_prefix = "fake"
    schema_folder = None
    format_prefix = "fake"
    ref_prefix = "refs/fake"


SCRIPT = '''
import sys
name = sys.argv[1]
if name == "bad":
    sys.exit("error: it does not work")
print("run folder /x/ex-" + name + "/20260101T000000Z")
print("results in /x/ex-" + name + "/20260101T000000Z  (sha256:aa)")
print("run " + name + "/20260101T000000Z added to the instance /x")
'''


class NoPost(eng.Post):
    def command(self):
        return "true"


class Hooks(eng.Hooks):
    kind = FakeKind()

    def __init__(self, tmp_path, resource=None):
        self.resource = resource
        self.state = ("r" * 40, "")
        self.refs = []
        self.script = tmp_path / "tool.py"
        self.script.write_text(SCRIPT)

    def repo(self):
        return "/the/repo"

    def repo_state(self):
        return self.state

    def update_ref(self, ref, rev):
        self.refs.append((ref, rev))

    def resource_keys(self, data):
        return [e["slot"] for e in data["experiments"] if e["state"] != eng.SKIPPED]

    def ensure_instance(self, lab, design, e, log):
        f = lab.results / "top" / e["study"]
        f.mkdir(parents=True, exist_ok=True)
        return f

    def run_command(self, rec, e, folder, warn_as_error):
        return [sys.executable, self.script, e["experiment"]]

    def run_note(self, folder, run_id):
        return "a note"

    def post(self, rec, root):
        return NoPost(rec, root)


@pytest.fixture
def lab(tmp_path):
    f = tmp_path / "lab"
    for d in ("results", "campaigns", "locks"):
        (f / d).mkdir(parents=True)
    return SimpleNamespace(folder=f, results=f / "results", campaigns=f / "campaigns", locks=f / "locks",
                           id="lab1", describe=lambda: {"id": "lab1"})


DESIGN = SimpleNamespace(top=SimpleNamespace(name="top"))


def items():
    return [{"experiment": n, "state": "planned", "study": "s", "slot": "s1"} for n in ("e1", "bad", "e3")]


def test_a_campaign_without_a_resource(lab, tmp_path):
    hooks = Hooks(tmp_path)
    rec = eng.new_record(lab, tmp_path, None, items(), ["x"], hooks)
    assert rec.data["format"] == "fake-campaign/1" and rec.data["ref"] == f"refs/fake/campaign/{rec.id}"
    lines = []
    failed = eng.run_campaign(rec, hooks, design=DESIGN, log=lines.append)
    assert failed == 1
    data = eng.Record(lab, rec.id).data
    assert [(e["experiment"], e["state"]) for e in data["experiments"]] == [
        ("e1", "done"), ("bad", "failed"), ("e3", "done")]
    assert data["experiments"][0]["run"] == "e1/20260101T000000Z"
    assert data["experiments"][1]["note"] == "run.py stopped before it made a run folder (see the log)"
    assert data["status"] == "done" and not list(lab.locks.iterdir())
    assert hooks.refs == [(rec.data["ref"], "r" * 40)]
    assert any(ln.startswith("    done (rc 0) in ") and ", a note, run e1/20260101T000000Z" in ln for ln in lines)
    assert any(ln.startswith("    failed (rc 1)") for ln in lines)


def test_resume_runs_the_failed_experiment_again(lab, tmp_path):
    hooks = Hooks(tmp_path)
    rec = eng.new_record(lab, tmp_path, None, items(), ["x"], hooks)
    eng.run_campaign(rec, hooks, design=DESIGN, log=lambda m: None)
    rec = eng.Record(lab, rec.id)
    hooks.script.write_text(SCRIPT.replace('"bad"', '"never"'))
    assert eng.run_campaign(rec, hooks, design=DESIGN, log=lambda m: None) == 0
    bad = eng.Record(lab, rec.id).data["experiments"][1]
    assert bad["state"] == "done" and bad["attempts"] == 2


def test_a_changed_repo_stops_the_campaign(lab, tmp_path):
    hooks = Hooks(tmp_path)
    rec = eng.new_record(lab, tmp_path, None, items(), ["x"], hooks)
    hooks.state = ("r" * 40, " M x")
    with pytest.raises(CampaignError, match="the design repo is at rrrrrrrrrrrr \\(dirty\\)"):
        eng.run_campaign(rec, hooks, design=DESIGN, log=lambda m: None)
    with pytest.raises(CampaignError, match="is dirty, commit first"):
        eng.new_record(lab, tmp_path, None, items(), ["x"], hooks)


def test_the_preflight_check_can_stop_the_campaign(lab, tmp_path):
    hooks = Hooks(tmp_path)
    hooks.preflight = lambda *a: [("ok", "a", ""), ("fail", "b", "no")]
    rec = eng.new_record(lab, tmp_path, None, items(), ["x"], hooks)
    assert eng.run_campaign(rec, hooks, design=DESIGN, log=lambda m: None) == 3
    data = eng.Record(lab, rec.id).data
    assert data["status"] == "failed" and data["stopped"] == "the pre-flight check failed"
    assert data["preflight"][1] == {"status": "fail", "what": "b", "text": "no"}
    assert [e["state"] for e in data["experiments"]] == ["planned"] * 3


def test_a_resource_lock_file_and_its_text(lab):
    res = eng.Resource("slot", lambda k: k.replace("/", "_"))
    eng.take_lock(lab, "c1", ["a/b", "c"], res)
    assert sorted(p.name for p in lab.locks.iterdir()) == ["slot-a_b.lock", "slot-c.lock"]
    assert json.loads((lab.locks / "slot-c.lock").read_text())["slot"] == "c"
    assert eng.lock_holders(lab, res) == {"a_b": "c1", "c": "c1"}
    with pytest.raises(CampaignError, match="the campaign c1 runs on c "):
        eng.take_lock(lab, "c2", ["c"], res)
    assert len(eng.lock_fds("c1")) == 2
    eng.drop_lock(lab, "c1")
    assert eng.lock_fds("c1") == [] and eng.lock_holder(lab, res) is None


def test_no_resource_no_lock(lab):
    eng.take_lock(lab, "c1", ["a"], None)
    assert eng.lock_holders(lab, None) == {} and eng.lock_holder(lab, None, "a") is None
    assert not any(lab.locks.iterdir())


def test_read_run_log():
    text = "x\nrun folder /a/ex-e/1\nresults in /a/ex-e/1  (sha256:aa)\nrun e/1 added to the instance /a\n"
    assert eng.read_run_log(text) == ("e/1", eng.Path("/a/ex-e/1"))
    assert eng.read_run_log("nothing\n") == (None, None)
