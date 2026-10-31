# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The import of a lab folder (importer.py) into a results tree.

The lab folder is the fixture lab-c20993e (a trimmed copy of the lab run 20261031-023823-c20993ed8) with the
files that a real lab folder has more: job.log, job.sh, rss.txt (small, made here), pid and state (which the
import leaves out), and the folders out/states and out/tmp (the same). A small git repo has the models, the
list and the design; the job.json of the run names the first commit of that repo as its revision.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

from probatrix.core import build, cli, config, layout, seal
from probatrix.tlaplus import importer, kind, subject, tlc

FIX = Path(__file__).resolve().parent / "fixtures" / "lab-c20993e"
UTC = "20261031T013824Z"
PIN = "5bd7b64db99ae4c6c35f290de5e809c0ee41af43f8699cf696099ffb6452b1e2"
EXP = {"name": "mc", "tool": "tlc", "list": "spec/tla/mc/expected.txt", "subject": ["spec/tla/lib", "spec/tla/mc"],
       "tools": ["spec/tla/tools/run_tlc.sh", "spec/tla/tools/tla2tools.sha256"]}
RAW = ["job.json", "job.log", "job.sh", "meta.env", "out/KSemTest_default.log", "out/MCKSem_default.log",
       "out/MCKSem_isr_waits.log", "out/MCKSem_live.log", "out/results.tsv", "results.txt", "rss.txt",
       "selftest/SelfRepro_default.log", "selftest/SelfRepro_default.r2.log", "selftest/results.tsv", "subject.json"]


def git(repo, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=repo, check=True,
                          capture_output=True, text=True).stdout.strip()


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


@pytest.fixture
def world(tmp_path):
    """(repo, design folder, the Project in use). Two commits: HEAD~1 has no spec/tla/mc/extra.txt."""
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    write(repo / "spec/tla/lib/A.tla", "a")
    write(repo / "spec/tla/mc/expected.txt", (FIX / "expected.txt").read_text())
    write(repo / "spec/tla/tools/run_tlc.sh", "run")
    write(repo / "spec/tla/tools/tla2tools.sha256", f"{PIN}  tla2tools.jar\n")
    design = repo / "design"
    write(design / "study.yaml", yaml.safe_dump({"name": "top", "kind": "tlaplus", "question": "q",
                                                 "substudies": ["sub", "again"]}))
    write(design / "st-sub/study.yaml", yaml.safe_dump({"name": "sub", "kind": "tlaplus", "question": "q",
                                                        "experiments": ["mc"]}))
    write(design / "st-again/study.yaml", yaml.safe_dump({"name": "again", "kind": "tlaplus", "question": "q",
                                                          "imports": [{"study": "sub", "experiment": "mc",
                                                                       "mode": "rerun"}]}))
    write(design / "st-sub/ex-mc/experiment.yaml", yaml.safe_dump(EXP))
    write(design / "st-sub/ex-mc/experiment.md", "x")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "one")
    write(repo / "spec/tla/mc/extra.txt", "x")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "two")
    project = config.Project.at(repo, design_root=design, roots=(config.Root(design, "tlaplus"),))
    with config.use(project):
        yield repo, design, project


def lab_folder(tmp_path, repo, revision="HEAD", name="lab", **job):
    """A lab folder: the fixture, the extra files of a real lab folder, and the revision of the repo."""
    lab = tmp_path / name
    import shutil
    shutil.copytree(FIX, lab)
    (lab / "expected.txt").unlink()
    (lab / "subject.json").unlink()
    data = json.loads((lab / "job.json").read_text())
    data.update(revision=git(repo, "rev-parse", revision), **job)
    (lab / "job.json").write_text(json.dumps(data))
    write(lab / "job.log", "log\n")
    write(lab / "job.sh", "#!/bin/sh\n")
    write(lab / "rss.txt", "1793410709 MCKSem_default 1\n")
    write(lab / "pid", "123\n")
    write(lab / "state", "done\n")
    write(lab / "out/states/MCKSem_default/x.fp", "big")
    write(lab / "out/tmp/MCKSem_default/y", "tmp")
    return lab


def run_import(lab, results, **kw):
    out = []
    kw.setdefault("pin", False)
    res = importer.import_lab(lab, results, say=out.append, **kw)
    return res, out


def listing(folder):
    """{path: (sha256, mtime_ns)} of all files below folder."""
    return {p.relative_to(folder).as_posix(): (seal.file_sha256(p), p.stat().st_mtime_ns)
            for p in sorted(folder.rglob("*")) if p.is_file()}


def sealed_names(run_dir):
    return sorted(seal.files(run_dir))


# ------------------------------------------------------------ the file set and the digest
def test_the_raw_file_set_leaves_out_pid_state_states_and_tmp(world, tmp_path):
    repo, _, _ = world
    lab = lab_folder(tmp_path, repo)
    assert [p.as_posix() for p in importer.raw_files(lab)] == [n for n in RAW if n != "subject.json"]
    assert importer.not_copied(lab) == ["out/states/MCKSem_default/x.fp", "out/tmp/MCKSem_default/y", "pid", "state"]


def test_two_imports_of_one_lab_folder_give_one_digest(world, tmp_path):
    repo, _, _ = world
    lab = lab_folder(tmp_path, repo)
    a, _ = run_import(lab, tmp_path / "r1" / "kernel-formal")
    os.utime(lab / "job.json", (1, 1))                          # another time stamp, same content
    b, _ = run_import(lab, tmp_path / "r2" / "other-name", copied_from="host:/runs/x")
    assert a["id"] == b["id"] == f"mc/{UTC}"
    assert a["digest"] == b["digest"] == seal.digest(a["run_dir"]) == seal.digest(b["run_dir"])
    assert sealed_names(a["run_dir"]) == RAW and sealed_names(b["run_dir"]) == RAW
    assert seal.seal_path(a["run_dir"]).read_bytes() == seal.seal_path(b["run_dir"]).read_bytes()


def test_a_copy_of_the_lab_folder_gives_the_same_digest(world, tmp_path):
    repo, _, _ = world
    a, _ = run_import(lab_folder(tmp_path, repo, name="one"), tmp_path / "r1" / "t")
    b, _ = run_import(lab_folder(tmp_path, repo, name="two"), tmp_path / "r2" / "t")
    assert a["digest"] == b["digest"]


def test_the_import_never_changes_the_lab_folder(world, tmp_path):
    repo, _, _ = world
    lab = lab_folder(tmp_path, repo)
    before = listing(lab)
    run_import(lab, tmp_path / "r" / "t")
    run_import(lab, tmp_path / "r" / "t")                       # the second one: already imported
    assert listing(lab) == before                               # content and time stamps
    assert sorted(p.name for p in lab.iterdir()) == sorted({"job.json", "job.log", "job.sh", "meta.env", "out",
                                                           "pid", "results.txt", "rss.txt", "selftest", "state"})


def test_a_read_only_lab_folder_can_be_imported(world, tmp_path):
    repo, _, _ = world
    lab = lab_folder(tmp_path, repo)
    for p in [*lab.rglob("*"), lab]:
        p.chmod(0o555 if p.is_dir() else 0o444)
    try:
        res, _ = run_import(lab, tmp_path / "r" / "t")
    finally:
        for p in [lab, *lab.rglob("*")]:
            p.chmod(0o755 if p.is_dir() else 0o644)
    assert res["digest"].startswith("sha256:")


# ------------------------------------------------------------ the results tree
def test_the_instance_files_run_json_and_the_run_list(world, tmp_path):
    repo, design, _ = world
    results = tmp_path / "r" / "kernel-formal"
    res, out = run_import(lab_folder(tmp_path, repo), results, copied_from="cos:/runs/20261031-023823-c20993ed8")
    top = json.loads((results / "instance.json").read_text())
    sub = json.loads((results / "st-sub" / "instance.json").read_text())
    assert top["format"] == sub["format"] == "tlaplus-instance/1"
    assert top["instance"] == "kernel-formal" and sub["instance"] == "kernel-formal/sub"
    assert top["substudies"] == ["kernel-formal/sub"] and top["design"]["folder"] == "design"
    assert sub["runs"] == [{"id": f"mc/{UTC}", "digest": res["digest"], "role": "evidence",
                            "copied_from": "cos:/runs/20261031-023823-c20993ed8",
                            "lab_id": "20261031-023823-c20993ed8"}]
    assert res["run_dir"] == results / "st-sub" / "ex-mc" / UTC
    assert any(line.startswith("results in ") for line in out) and any(" added to the instance " in x for x in out)
    rj = json.loads((results / "st-sub" / "ex-mc" / f"{UTC}.run.json").read_text())["run"]
    assert (rj["id"], rj["lab_id"], rj["copied_from"]) == (f"mc/{UTC}", "20261031-023823-c20993ed8",
                                                           "cos:/runs/20261031-023823-c20993ed8")
    assert rj["digest"] == res["digest"] and rj["evidence"] is True


def test_subject_json_is_written_before_the_seal(world, tmp_path):
    repo, _, _ = world
    res, _ = run_import(lab_folder(tmp_path, repo), tmp_path / "r" / "t")
    sj = json.loads((res["run_dir"] / "subject.json").read_text())
    assert sj == subject.record("HEAD", EXP, repo)
    assert seal.verify(res["run_dir"]) == res["digest"] and "subject.json" in seal.files(res["run_dir"])


def test_the_core_builds_the_imported_tree_with_its_design(world, tmp_path):
    repo, _, _ = world
    results = tmp_path / "r" / "kernel-formal"
    run_import(lab_folder(tmp_path, repo), results)
    tree, _ = build.build(results, log=lambda *a: None)
    assert tree.kind is kind.KIND
    sj = json.loads((results / "st-sub" / "study.json").read_text())
    gen = next(h for h in sj["hypotheses"] if h["id"] == "mc-generated")
    assert gen["verdict"] in ("confirmed", "open", "wrong")           # the trimmed fixture has all 67 rows
    assert json.loads((results / "st-sub" / "ex-mc" / "experiment.json").read_text())["runs"][0]["role"] == "evidence"


def test_the_second_import_into_the_same_tree_changes_nothing(world, tmp_path):
    repo, _, _ = world
    lab, results = lab_folder(tmp_path, repo), tmp_path / "r" / "t"
    first, _ = run_import(lab, results)
    before = listing(results)
    again, out = run_import(lab, results)
    assert again["already"] is True and again["digest"] == first["digest"]
    assert out == [f"already imported: mc/{UTC}  ({first['digest']})"]
    assert listing(results) == before


def test_another_lab_folder_with_the_same_start_is_refused(world, tmp_path):
    repo, _, _ = world
    results = tmp_path / "r" / "t"
    run_import(lab_folder(tmp_path, repo, name="one"), results, copied_from="a")
    other = lab_folder(tmp_path, repo, name="two", run_id="other")
    with pytest.raises(importer.ImportLabError, match="from another lab folder"):
        run_import(other, results, copied_from="b")


def test_the_run_can_go_into_a_study_that_runs_the_experiment_again(world, tmp_path):
    repo, _, _ = world
    results = tmp_path / "r" / "t"
    res, _ = run_import(lab_folder(tmp_path, repo), results, study="again")
    assert res["run_dir"] == results / "st-again" / "ex-mc" / UTC
    with pytest.raises(importer.ImportLabError, match="has not the experiment"):
        run_import(lab_folder(tmp_path, repo, name="x"), tmp_path / "r2" / "t", study="")
    with pytest.raises(importer.ImportLabError, match="no study"):
        run_import(lab_folder(tmp_path, repo, name="y"), tmp_path / "r3" / "t", study="nope")


def test_the_pin_keeps_the_commit_of_the_run(world, tmp_path):
    repo, _, _ = world
    lab = lab_folder(tmp_path, repo, revision="HEAD~1")
    _, out = run_import(lab, tmp_path / "r" / "t", pin=True)
    ref = f"refs/tlaplus/run/mc/{UTC}"
    assert git(repo, "rev-parse", ref) == git(repo, "rev-parse", "HEAD~1")
    assert any(ref in line for line in out)
    run_import(lab_folder(tmp_path, repo, name="n", run_id="n"), tmp_path / "r2" / "t", pin=False)
    assert git(repo, "for-each-ref", "refs/tlaplus/lab") == ""            # no ref of the lab is touched


# ------------------------------------------------------------ the role
def test_the_role_is_evidence_for_the_trees_of_the_design(world, tmp_path):
    repo, _, _ = world
    res, _ = run_import(lab_folder(tmp_path, repo), tmp_path / "r" / "t")
    assert (res["role"], res["reason"]) == ("evidence", None)


def test_a_run_of_an_older_revision_with_the_same_trees_is_evidence(world, tmp_path):
    """HEAD adds a file below spec/tla/mc: the trees of the subject differ at HEAD~1, so check the other way:
    the run is of HEAD~1 and the design is HEAD~1 (--rev). A change of another folder does not matter."""
    repo, _, _ = world
    write(repo / "README.md", "x")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "three")
    res, _ = run_import(lab_folder(tmp_path, repo, revision="HEAD~1"), tmp_path / "r" / "t")
    assert res["role"] == "evidence"


def test_a_changed_subject_tree_makes_the_run_historical_with_the_paths(world, tmp_path):
    repo, _, _ = world
    res, _ = run_import(lab_folder(tmp_path, repo, revision="HEAD~1"), tmp_path / "r" / "t")
    assert res["role"] == "historical"
    assert res["reason"].startswith("the subject tree differs from the design at ")
    assert res["reason"].endswith("mc") and "tool tree" not in res["reason"]


def test_a_changed_tool_tree_makes_the_run_historical(world, tmp_path):
    repo, _, _ = world
    lab = lab_folder(tmp_path, repo)
    write(repo / "spec/tla/tools/run_tlc.sh", "run two")
    git(repo, "commit", "-qam", "tool")
    res, _ = run_import(lab, tmp_path / "r" / "t")
    assert res["role"] == "historical" and "the tool tree differs" in res["reason"]
    assert "run_tlc.sh" in res["reason"] and "the subject tree" not in res["reason"]


def test_a_path_that_the_old_revision_lacks_is_marked(world, tmp_path):
    repo, _, _ = world
    write(repo / "spec/tla/objects/O.tla", "o")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "objects")
    config.project()                                               # the Project of the world
    exp = {**EXP, "subject": [*EXP["subject"], "spec/tla/objects"]}
    design_file = repo / "design/st-sub/ex-mc/experiment.yaml"
    write(design_file, yaml.safe_dump(exp))
    git(repo, "commit", "-qam", "design")
    res, _ = run_import(lab_folder(tmp_path, repo, revision="HEAD~2"), tmp_path / "r" / "t")
    assert res["role"] == "historical" and "objects (not in the revision of the run)" in res["reason"]
    rec = json.loads((res["run_dir"] / "subject.json").read_text())
    assert rec["subject"]["spec/tla/objects"] is None


def test_an_unpinned_run_with_the_trees_of_the_design_is_historical(world, tmp_path):
    repo, _, _ = world
    res, _ = run_import(lab_folder(tmp_path, repo, mode="unpinned"), tmp_path / "r" / "t")
    assert res["role"] == "historical"
    assert res["reason"] == "not an evidence run: unpinned: the code is not a commit"


def test_the_reasons_are_joined(world, tmp_path):
    repo, _, _ = world
    res, _ = run_import(lab_folder(tmp_path, repo, revision="HEAD~1", workers=2), tmp_path / "r" / "t")
    assert res["reason"].count("; ") == 1 and "2 workers" in res["reason"]


# ------------------------------------------------------------ the line check
def test_the_lines_of_the_run_are_the_lines_of_the_design(world, tmp_path):
    repo, _, _ = world
    res, _ = run_import(lab_folder(tmp_path, repo), tmp_path / "r" / "t")
    assert res["lines"] == {"run_list": "expected", "missing": [], "extra": [], "expected": [], "same": True}


def test_the_line_check_reports_each_kind_of_difference(world, tmp_path):
    repo, _, _ = world
    text = (repo / "spec/tla/mc/expected.txt").read_text().splitlines()
    out = []
    for ln in text:
        if ln.startswith("MCKSem live "):
            continue                                                 # a line that the run has, the design not
        if ln.startswith("MCKSem default "):
            ln = ln.replace(" pass", " probes", 1)                    # another expected result
        out.append(ln)
    out.append("MCNew default pass")                                  # a line that the run lacks
    write(repo / "spec/tla/mc/expected.txt", "\n".join(out) + "\n")
    git(repo, "commit", "-qam", "list")
    res, report = run_import(lab_folder(tmp_path, repo, revision="HEAD~1"), tmp_path / "r" / "t", rev="HEAD")
    got = res["lines"]
    assert got["missing"] == ["MCNew:default"] and got["extra"] == ["MCKSem:live"]
    assert got["expected"] == [("MCKSem:default", "pass", "probes")] and got["same"] is False
    assert res["role"] == "historical" and "1 lines of the design that the run lacks" in res["reason"]
    importer.report(res, say=report.append)
    text = "\n".join(report)
    assert "line check: 3 difference(s)" in text and "MCNew:default" in text and "MCKSem:live" in text
    assert "run pass, design probes" in text


def test_a_run_of_another_list_is_reported(world, tmp_path):
    repo, _, _ = world
    res, _ = run_import(lab_folder(tmp_path, repo, list="sensitivity"), tmp_path / "r" / "t", experiment="mc")
    assert res["lines"]["run_list"] == "sensitivity" and res["lines"]["same"] is False
    assert "the run used the list 'sensitivity', the experiment has 'expected'" in res["reason"]


def test_a_report_without_a_difference_says_so(world, tmp_path):
    repo, _, _ = world
    res, out = run_import(lab_folder(tmp_path, repo), tmp_path / "r" / "t")
    lines = []
    importer.report(res, say=lines.append)
    assert lines == ["role evidence", "line check: the lines of the run are the lines of the design"]


# ------------------------------------------------------------ errors change nothing
def test_the_experiment_is_found_by_the_list_or_given(world, tmp_path):
    repo, _, _ = world
    with pytest.raises(importer.ImportLabError, match="the run used the list 'sensitivity'; 0 experiments"):
        run_import(lab_folder(tmp_path, repo, list="sensitivity"), tmp_path / "r" / "t")
    with pytest.raises(importer.ImportLabError, match="no experiment 'zz'"):
        run_import(lab_folder(tmp_path, repo, name="z"), tmp_path / "r" / "t", experiment="zz")
    assert not (tmp_path / "r").exists()


def test_a_folder_that_is_not_finished_or_not_a_run_is_refused(world, tmp_path):
    repo, _, _ = world
    lab = lab_folder(tmp_path, repo)
    meta = (lab / "meta.env").read_text().replace("end=", "endx=")
    (lab / "meta.env").write_text(meta)
    with pytest.raises(importer.ImportLabError, match="not finished"):
        run_import(lab, tmp_path / "r" / "t")
    (lab / "out" / "results.tsv").unlink()
    with pytest.raises(importer.ImportLabError, match="no out/results.tsv"):
        run_import(lab, tmp_path / "r" / "t")
    with pytest.raises(importer.ImportLabError, match="no such folder"):
        run_import(tmp_path / "nothing", tmp_path / "r" / "t")
    assert not (tmp_path / "r").exists()


def test_a_revision_that_is_not_in_the_repo_is_refused(world, tmp_path):
    repo, _, _ = world
    lab = lab_folder(tmp_path, repo)
    data = json.loads((lab / "job.json").read_text())
    data["revision"] = "0" * 40
    (lab / "job.json").write_text(json.dumps(data))
    with pytest.raises(importer.ImportLabError, match="the subject of the run cannot be read"):
        run_import(lab, tmp_path / "r" / "t")
    assert not (tmp_path / "r").exists()


def test_a_tool_without_an_adapter_is_refused(world, tmp_path):
    repo, _, _ = world
    with pytest.raises(importer.ImportLabError, match="no adapter"):
        run_import(lab_folder(tmp_path, repo, tool="apalache"), tmp_path / "r" / "t")


def test_a_failed_copy_leaves_no_run_folder(world, tmp_path, monkeypatch):
    repo, _, _ = world
    monkeypatch.setattr(tlc, "Raw", lambda d: (_ for _ in ()).throw(ValueError("broken")))
    with pytest.raises(ValueError):
        run_import(lab_folder(tmp_path, repo), tmp_path / "r" / "t")
    ex = tmp_path / "r" / "t" / "st-sub" / "ex-mc"
    assert list(ex.iterdir()) == []


# ------------------------------------------------------------ the command
def test_the_kind_has_the_command_import_lab(world, tmp_path, capsys):
    repo, _, _ = world
    assert "import-lab" in cli.commands() and cli.commands()["import-lab"][0] is kind.KIND
    lab, results = lab_folder(tmp_path, repo), tmp_path / "r" / "kernel-formal"
    args = cli.parser("probatrix").parse_args(["import-lab", str(lab), "--results", str(results), "--no-pin",
                                               "--copied-from", "cos:x"])
    assert args.func(args) == 0
    text = capsys.readouterr().out
    assert "role evidence" in text and "not copied: out/states/MCKSem_default/x.fp, " in text
    assert f"next: probatrix analysis build {results}" in text
    assert json.loads((results / "st-sub" / "instance.json").read_text())["runs"][0]["copied_from"] == "cos:x"
    assert layout.find_root(results / "st-sub") == results
