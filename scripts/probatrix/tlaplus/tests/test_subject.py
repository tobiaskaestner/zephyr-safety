# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The subject tree of a run (subject.py) in a small git repo."""

import subprocess

import pytest

from probatrix.core import config
from probatrix.tlaplus import kind, subject


def git(repo, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=repo, check=True,
                          capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q")
    for path, text in {"spec/tla/lib/A.tla": "a", "spec/tla/mc/expected.txt": "x\n", "spec/tla/mc/M.cfg": "c",
                       "spec/tla/tools/run_tlc.sh": "run", "spec/tla/other/O.tla": "o",
                       "spec/tla/tools/tla2tools.sha256": "ab12  tla2tools.jar\n"}.items():
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).write_text(text)
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "one")
    return tmp_path


EXP = {"subject": ["spec/tla/lib", "spec/tla/mc"], "tools": ["spec/tla/tools/run_tlc.sh"]}


def test_the_tree_is_git_rev_parse_of_each_path(repo):
    t = subject.subject_tree("HEAD", EXP["subject"], repo)
    assert t == {p: git(repo, "rev-parse", f"HEAD:{p}") for p in EXP["subject"]}
    assert subject.tool_tree("HEAD", ["spec/tla/tools/run_tlc.sh"], repo) == {
        "spec/tla/tools/run_tlc.sh": git(repo, "rev-parse", "HEAD:spec/tla/tools/run_tlc.sh")}


def test_a_commit_outside_the_subject_leaves_the_tree_as_it_is(repo):
    before = subject.subject_tree("HEAD", EXP["subject"], repo)
    (repo / "spec/tla/other/O.tla").write_text("changed")
    git(repo, "commit", "-qam", "two")
    assert subject.subject_tree("HEAD", EXP["subject"], repo) == before
    assert subject.digest(subject.subject_tree("HEAD", EXP["subject"], repo)) == subject.digest(before)
    (repo / "spec/tla/mc/M.cfg").write_text("changed")
    git(repo, "commit", "-qam", "three")
    after = subject.subject_tree("HEAD", EXP["subject"], repo)
    assert after["spec/tla/mc"] != before["spec/tla/mc"] and after["spec/tla/lib"] == before["spec/tla/lib"]
    assert subject.digest(after) != subject.digest(before)


def test_the_digest_does_not_depend_on_the_order():
    assert subject.digest({"a": "1", "b": "2"}) == subject.digest({"b": "2", "a": "1"})
    assert subject.digest({"a": "1"}).startswith("sha256:")


def test_a_path_that_is_not_in_the_revision(repo):
    with pytest.raises(subject.SubjectError, match="spec/tla/nope does not exist at the revision HEAD"):
        subject.subject_tree("HEAD", ["spec/tla/nope"], repo)
    with pytest.raises(subject.SubjectError):
        subject.subject_tree("nonexistent-rev", ["spec/tla/lib"], repo)


def test_the_record_has_the_trees_and_the_pin_of_the_jar(repo):
    rec = subject.record("HEAD", EXP, repo)
    assert rec["revision"] == git(repo, "rev-parse", "HEAD")
    assert rec["subject"] == subject.subject_tree("HEAD", EXP["subject"], repo)
    assert rec["tools"] == subject.tool_tree("HEAD", EXP["tools"], repo)
    assert rec["subject_tree"] == subject.digest(rec["subject"]) and rec["tool_tree"] == subject.digest(rec["tools"])
    assert rec["jar_pin"] == "ab12"
    git(repo, "rm", "-q", "spec/tla/tools/tla2tools.sha256")
    git(repo, "commit", "-qm", "no pin")
    assert subject.record("HEAD", EXP, repo)["jar_pin"] is None


def test_the_default_repo_is_the_one_of_the_project(repo):
    with config.use(config.Project.at(repo)):
        assert subject.subject_tree("HEAD", ["spec/tla/lib"]) == subject.subject_tree("HEAD", ["spec/tla/lib"], repo)


def test_the_ref_of_a_run_comes_from_the_kind(repo):
    assert subject.ref("mc-expected", "20261031T013824Z") == "refs/tlaplus/run/mc-expected/20261031T013824Z"
    assert subject.ref("a", "b") == kind.KIND.ref("run", "a", "b")
    rev = git(repo, "rev-parse", "HEAD")
    ref = subject.pin(repo, rev, "mc-expected", "20261031T013824Z")
    assert ref == "refs/tlaplus/run/mc-expected/20261031T013824Z"
    assert git(repo, "rev-parse", ref) == rev


def test_a_missing_path_is_an_error_or_with_missing_ok_the_id_none(repo):
    paths = ["spec/tla/lib", "spec/tla/objects"]
    with pytest.raises(subject.SubjectError, match="objects does not exist at the revision"):
        subject.tree("HEAD", paths, repo)
    t = subject.tree("HEAD", paths, repo, missing_ok=True)
    assert t["spec/tla/objects"] is None and t["spec/tla/lib"] == git(repo, "rev-parse", "HEAD:spec/tla/lib")
    assert subject.digest(t) != subject.digest({"spec/tla/lib": t["spec/tla/lib"]})
    exp = {"subject": paths, "tools": EXP["tools"]}
    assert subject.record("HEAD", exp, repo, missing_ok=True)["subject"]["spec/tla/objects"] is None


# ---- subject_exclude (the case of commit a07cd0c: a comment in another list file of the same folder)

EXCL = ["spec/tla/mc/sensitivity.txt"]


def _with_other_list(repo):
    (repo / "spec/tla/mc/sensitivity.txt").write_text("# one\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "list")


def test_a_change_only_in_an_excluded_file_keeps_the_tree(repo):
    _with_other_list(repo)
    before = subject.subject_tree("HEAD", EXP["subject"], repo, exclude=EXCL)
    plain = subject.subject_tree("HEAD", EXP["subject"], repo)
    assert before["spec/tla/mc"].startswith("x-") and before["spec/tla/lib"] == plain["spec/tla/lib"]
    (repo / "spec/tla/mc/sensitivity.txt").write_text("# two, a comment only\n")
    git(repo, "commit", "-qam", "comment")
    after = subject.subject_tree("HEAD", EXP["subject"], repo, exclude=EXCL)
    assert after == before and subject.digest(after) == subject.digest(before)
    assert subject.subject_tree("HEAD", EXP["subject"], repo) != plain


def test_a_change_in_another_file_of_the_folder_changes_the_tree(repo):
    _with_other_list(repo)
    before = subject.subject_tree("HEAD", EXP["subject"], repo, exclude=EXCL)
    (repo / "spec/tla/mc/M.cfg").write_text("changed")
    git(repo, "commit", "-qam", "cfg")
    after = subject.subject_tree("HEAD", EXP["subject"], repo, exclude=EXCL)
    assert after["spec/tla/mc"] != before["spec/tla/mc"] and after["spec/tla/lib"] == before["spec/tla/lib"]


def test_a_path_without_an_excluded_file_keeps_the_git_id(repo):
    assert subject.subject_tree("HEAD", EXP["subject"], repo, exclude=EXCL) == subject.subject_tree(
        "HEAD", EXP["subject"], repo)


def test_exclude_takes_globs_and_folders():
    assert subject.excluded("spec/tla/mc/sensitivity.txt", ["spec/tla/mc/sens*.txt"])
    assert subject.excluded("spec/tla/mc/x/y.txt", ["spec/tla/mc/x"])
    assert not subject.excluded("spec/tla/mc/xy.txt", ["spec/tla/mc/x"])
    assert not subject.excluded("spec/tla/mc/expected.txt", EXCL)


def test_the_record_states_what_was_excluded(repo):
    _with_other_list(repo)
    assert subject.record("HEAD", {**EXP, "subject_exclude": EXCL}, repo)["subject_exclude"] == EXCL
    assert subject.record("HEAD", EXP, repo)["subject_exclude"] == []
