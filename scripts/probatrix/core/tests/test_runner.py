# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Unit tests of core/runner.py with a fake kind (no board, no build)."""

import datetime
import json
import subprocess

import pytest

from probatrix.core import runner, seal
from probatrix.core.kinds import BaseKind


class FakeKind(BaseKind):
    name = "fake"
    schema_prefix = "fake"
    schema_folder = None
    format_prefix = "fake"
    ref_prefix = "refs/fake"


def git(repo, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=repo, check=True,
                          capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    git(r, "init", "-q")
    (r / "a.txt").write_text("a\n")
    git(r, "add", "-A")
    git(r, "commit", "-qm", "a")
    return r


def test_repo_checks(repo):
    rev, dirty = runner.repo_state(repo)
    assert len(rev) == 40 and dirty == ""
    runner.check_clean(repo, dirty)
    runner.check_unchanged(repo, rev)
    (repo / "b.txt").write_text("b\n")
    rev2, dirty = runner.repo_state(repo)
    assert "b.txt" in dirty
    with pytest.raises(runner.RunError, match=f"safety repo {repo} is dirty, commit first:\n.*b.txt"):
        runner.check_clean(repo, dirty)
    with pytest.raises(runner.RunError, match=f"the safety repo {repo} changed during the run .*, dirty"):
        runner.check_unchanged(repo, rev)


def test_check_inside(repo, tmp_path):
    runner.check_inside(repo / "a.txt", repo)
    with pytest.raises(runner.RunError, match="is not in the safety repo"):
        runner.check_inside(tmp_path / "x", repo)
    with pytest.raises(runner.RunError, match="is not in the design repo"):
        runner.check_inside(tmp_path / "x", repo, what="design repo")


def test_run_folder_flat_and_in_an_instance(tmp_path, capsys):
    t = datetime.datetime(2026, 1, 2, 3, 4, 5, tzinfo=datetime.timezone.utc)
    flat = runner.run_folder(tmp_path / "flat", "e1", t)
    assert flat == tmp_path / "flat" / "e1" / "20260102T030405Z" and flat.is_dir()
    assert capsys.readouterr().out == f"run folder {flat}\n"
    inst = tmp_path / "inst"
    inst.mkdir()
    (inst / "instance.json").write_text("{}")
    run = runner.run_folder(inst, "e1", t)
    assert run == inst / "ex-e1" / "20260102T030405Z"


def test_pin_run_makes_the_ref_of_the_kind(repo):
    rev, _ = runner.repo_state(repo)
    ref = runner.pin_run(FakeKind(), repo, rev, "e1", "20260102T030405Z")
    assert ref == "refs/fake/run/e1/20260102T030405Z"
    assert git(repo, "rev-parse", ref) == rev


def test_guarded_writes_the_failed_record_before_the_seal(tmp_path):
    run = tmp_path / "ex-e1" / "20260102T030405Z"
    run.mkdir(parents=True)
    log = run / "t" / "rep1.log"
    log.parent.mkdir()
    log.write_text("\n".join(f"line {i}" for i in range(30)) + "\n")
    state = {"step": "capture", "log": str(log)}

    def body():
        raise SystemExit("error: the board did not answer")

    with pytest.raises(SystemExit):
        runner.guarded(FakeKind(), run, "e1", state, body)
    rec = json.loads((run.parent / f"{run.name}.failed.json").read_text())
    assert rec["format"] == "fake-failed/1" and rec["run"] == "e1/20260102T030405Z"
    assert rec["step"] == "capture" and rec["error"] == "the board did not answer"
    assert rec["log"] == "t/rep1.log" and rec["log_tail"][-1] == "line 29" and len(rec["log_tail"]) == 20


def test_guarded_writes_no_record_for_a_sealed_run_or_a_good_body(tmp_path):
    run = tmp_path / "ex-e1" / "20260102T030405Z"
    run.mkdir(parents=True)
    (run / "manifest.json").write_text("{}")
    runner.guarded(FakeKind(), run, "e1", {"step": "x", "log": None}, lambda: None)
    seal.write(run)

    def body():
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        runner.guarded(FakeKind(), run, "e1", {"step": "x", "log": None}, body)
    assert not (run.parent / f"{run.name}.failed.json").exists()


def test_finish_seals_and_prints_the_line(tmp_path, capsys):
    run = tmp_path / "ex-e1" / "20260102T030405Z"
    run.mkdir(parents=True)
    (run / "manifest.json").write_text("{}")
    digest = runner.finish(run)
    assert seal.verify(run) == digest
    assert capsys.readouterr().out == f"results in {run}  ({digest})\n"


def test_add_to_run_list(tmp_path, capsys):
    class Refuse(Exception):
        pass

    def add(out, run_dir, **entry):
        assert entry == {"role": "evidence", "reason": None, "campaign": "c1"}
        return "e1/20260102T030405Z"

    rid = runner.add_to_run_list(tmp_path, tmp_path / "r", add, Refuse, role="evidence", reason=None, campaign="c1")
    assert rid == "e1/20260102T030405Z"
    assert capsys.readouterr().out == f"run e1/20260102T030405Z added to the instance {tmp_path}\n"

    def refuse(out, run_dir, **entry):
        raise Refuse("already in the run list")

    with pytest.raises(runner.RunError, match=f"the run is sealed, but not in the run list of {tmp_path}: already"):
        runner.add_to_run_list(tmp_path, tmp_path / "r", refuse, Refuse)
