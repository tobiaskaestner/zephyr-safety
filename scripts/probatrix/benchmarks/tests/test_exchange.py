# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Unit tests of the export and import of runs between two lab spaces."""

import json
import sys
from pathlib import Path

import pytest
import yaml

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import trees  # noqa: E402
from studylib import exchange, instance  # noqa: E402
from studylib import lab as labmod  # noqa: E402
from studylib.design import Design  # noqa: E402
from test_studylib import make_design, make_run  # noqa: E402


def make_lab(tmp_path, name, repo):
    return labmod.init(tmp_path / name, repo, name=name)


@pytest.fixture
def two_labs(tmp_path, monkeypatch):
    design = make_design(tmp_path)
    root = tmp_path / "design"
    monkeypatch.setattr(trees, "STUDIES_DIR", root)
    monkeypatch.setattr(exchange, "Design", lambda: Design(root))
    repo = tmp_path / "safety"
    (repo / "scripts" / "probatrix" / "benchmarks").mkdir(parents=True)
    (repo / "scripts" / "probatrix" / "benchmarks" / "study.py").write_text("")
    a, b = make_lab(tmp_path, "lab-a", repo), make_lab(tmp_path, "lab-b", repo)
    instance.new(design, a.results, "top", "sub", "nucleo_g474re")
    inst = a.results / "top" / "st-sub@nucleo_g474re"
    run = make_run(tmp_path / "flat" / "exp1", {"a": (100, 200)})
    m = json.loads((run / "manifest.json").read_text())
    m["lab"] = a.describe()
    (run / "manifest.json").write_text(json.dumps(m))
    instance.add(design, inst, run, copy=True)
    return a, b, root, tmp_path


def test_export_import_and_checks(two_labs):
    a, b, root, tmp = two_labs
    f = tmp / "a.tar.gz"
    assert exchange.export(a, f, log=lambda *x: None) == 1
    assert Path(f"{f}.sha256").is_file()
    added, skipped, refused, warnings = exchange.import_(b, f, log=lambda *x: None)
    assert added == ["exp1/20260101T000000Z"] and not refused
    assert warnings == ["the export has not the commits r of its runs (the other lab does not have them; "
                        "a rebuild here needs them)"]       # the test run has no real commit
    inst_b = b.results / "top" / "st-sub@nucleo_g474re"
    runs = instance.load(inst_b)["runs"]
    assert runs[0]["digest"] == instance.load(a.results / "top" / "st-sub@nucleo_g474re")["runs"][0]["digest"]
    assert runs[0]["copied_from"] == f"lab {a.id}" and instance.load(inst_b)["board"] == "nucleo_g474re"
    # the same file again: the run is here
    assert exchange.import_(b, f, log=lambda *x: None)[1] == ["exp1/20260101T000000Z"]
    # an import into its own lab space is refused
    with pytest.raises(exchange.ExchangeError):
        exchange.import_(a, f, log=lambda *x: None)
    # a changed file: the digest does not agree
    Path(f"{f}.sha256").write_text("0" * 64 + "  a.tar.gz\n")
    with pytest.raises(exchange.ExchangeError):
        exchange.import_(b, f, log=lambda *x: None)


def test_import_refuses_other_experiment_file_and_collision(two_labs):
    a, b, root, tmp = two_labs
    f = tmp / "a.tar.gz"
    exchange.export(a, f, log=lambda *x: None)
    hyp = root / "st-sub" / "hypotheses.yaml"
    d = yaml.safe_load(hyp.read_text())
    d["hypotheses"][0]["statement"] = "changed"
    hyp.write_text(yaml.safe_dump(d))
    ef = root / "st-sub" / "ex-exp1" / "experiment.yaml"
    d = yaml.safe_load(ef.read_text())
    d["repeat"] = 2
    ef.write_text(yaml.safe_dump(d))
    added, skipped, refused, warnings = exchange.import_(b, f, log=lambda *x: None, dry=True)
    assert added == [] and "experiment.yaml of exp1 differs between the two labs (content)" in refused[0]
    assert any("hypotheses.yaml differs" in w for w in warnings)


def test_import_accepts_comments_and_a_rename(two_labs):
    a, b, root, tmp = two_labs
    f = tmp / "a.tar.gz"
    exchange.export(a, f, log=lambda *x: None)
    ef = root / "st-sub" / "ex-exp1" / "experiment.yaml"
    ef.write_text("# a new comment: the content stays\n" + ef.read_text())
    assert exchange.import_(b, f, log=lambda *x: None, dry=True)[0] == ["exp1/20260101T000000Z"]
    # the rename exp1 -> irq-exp1: the run keeps its id and goes into the renamed experiment
    d = yaml.safe_load(ef.read_text())
    d.update(name="irq-exp1", renamed_from=["exp1"])
    (root / "st-sub" / "ex-exp1").rename(root / "st-sub" / "ex-irq-exp1")
    (root / "st-sub" / "ex-irq-exp1" / "experiment.yaml").write_text(yaml.safe_dump(d))
    st = root / "st-sub" / "study.yaml"
    sd = yaml.safe_load(st.read_text())
    sd["experiments"] = ["irq-exp1"]
    sd["central_results"][0]["from"]["experiment"] = "irq-exp1"
    st.write_text(yaml.safe_dump(sd))
    hy = root / "st-sub" / "hypotheses.yaml"
    hd = yaml.safe_load(hy.read_text())
    hd["hypotheses"][0]["checks"][0]["experiment"] = "irq-exp1"
    hy.write_text(yaml.safe_dump(hd))
    design = Design(root)
    assert design.canonical("exp1") == "irq-exp1" and design.run_experiment("exp1/20260101T000000Z") == "irq-exp1"
    added, skipped, refused, warnings = exchange.import_(b, f, log=lambda *x: None)
    assert added == ["exp1/20260101T000000Z"] and not refused


def test_bundle_carries_the_commits(tmp_path):
    import subprocess
    def git(*a, cwd):
        return subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()
    src, dst = tmp_path / "src", tmp_path / "dst"
    for r in (src, dst):
        r.mkdir()
        git("init", "-q", cwd=r)
    (src / "f").write_text("1\n")
    git("add", "f", cwd=src)
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "one", cwd=src)
    rev = git("rev-parse", "HEAD", cwd=src)
    out = exchange.make_bundle(src, [rev, "f" * 40], tmp_path / "b.bundle")
    assert out == {"revs": [rev], "missing": ["f" * 40]}
    assert git("for-each-ref", "refs/latbench", cwd=src) == ""          # the temporary refs are gone

    class L:
        repo = dst
    assert exchange.fetch_bundle(L, tmp_path / "b.bundle", "lab-x", log=lambda *a: None) == [rev]
    assert git("rev-parse", f"refs/latbench/import/lab-x/{rev}", cwd=dst) == rev


def test_import_refuses_a_run_id_with_another_digest(two_labs):
    a, b, root, tmp = two_labs
    f = tmp / "a.tar.gz"
    exchange.export(a, f, log=lambda *x: None)
    design = Design(root)
    instance.new(design, b.results, "top", "sub", "nucleo_g474re")
    instance.add(design, b.results / "top" / "st-sub@nucleo_g474re",
                 make_run(tmp / "flat-b" / "exp1", {"a": (111, 222)}), copy=True)
    added, skipped, refused, warnings = exchange.import_(b, f, log=lambda *x: None)
    assert added == [] and "collision" in refused[0]


def test_import_refuses_only_a_damaged_run(two_labs, monkeypatch):
    a, b, root, tmp = two_labs
    design = Design(root)
    inst = a.results / "top" / "st-sub@nucleo_g474re"
    run2 = make_run(tmp / "flat2" / "exp1", {"a": (100, 200)}).rename(tmp / "flat2" / "exp1" / "20260102T000000Z")
    m = json.loads((run2 / "manifest.json").read_text())
    m["lab"] = a.describe()
    (run2 / "manifest.json").write_text(json.dumps(m))
    instance.add(design, inst, run2, copy=True)
    f = tmp / "a.tar.gz"
    assert exchange.export(a, f, log=lambda *x: None) == 2
    real = exchange.seal.verify

    def verify(path):
        if Path(path).name == "20260101T000000Z" and ".lab" in str(path):
            raise exchange.seal.SealError(f"{path}: a file differs from the seal")
        return real(path)
    monkeypatch.setattr(exchange.seal, "verify", verify)
    added, skipped, refused, warnings = exchange.import_(b, f, log=lambda *x: None)
    assert added == ["exp1/20260102T000000Z"] and "differs from the seal" in refused[0]


def test_an_imported_running_campaign_can_be_closed(two_labs):
    from studylib import campaign, jsonout
    a, b, root, tmp = two_labs
    rid = instance.load(a.results / "top" / "st-sub@nucleo_g474re")["runs"][0]["id"]
    jsonout.write(a.campaigns / "20260101T000000Z.json", {
        "id": "20260101T000000Z", "status": "running", "lab": a.describe(), "host": "h",
        "repo": {"rev": "r"}, "folder": "x",
        "experiments": [{"experiment": "exp1", "state": "done", "run": rid,
                         "instance": "top/st-sub@nucleo_g474re"}]})
    f = tmp / "a.tar.gz"
    exchange.export(a, f, campaigns=["20260101T000000Z"], log=lambda *x: None)
    exchange.import_(b, f, log=lambda *x: None)
    name = f"20260101T000000Z@{a.id}"
    rec = campaign.Record(b, name)
    assert rec.data["running_at_export"] and campaign.status_lines(rec)[0].startswith(
        f"campaign {name}: imported, not complete (running at the export of")
    exchange.close_import(b, name)
    assert campaign.Record(b, name).data["status"] == "closed"
    exchange.import_(b, f, log=lambda *x: None)                       # the old export does not open it again
    assert campaign.Record(b, name).data["status"] == "closed"


def test_manual_verdicts_and_references_go_along(two_labs):
    a, b, root, tmp = two_labs
    inst_a = a.results / "top" / "st-sub@nucleo_g474re"
    instance.add_verdict(inst_a, "confirmed", "tester", hypothesis="H1", check="b")
    d = instance.load(inst_a)
    d["references"].append({"instance": "top/other@nucleo_g474re", "id": "x/20260101T000000Z", "digest": "sha256:0",
                            "role": "reference", "reason": "a fixed value"})
    instance.save(inst_a, d)
    f = tmp / "a.tar.gz"
    exchange.export(a, f, log=lambda *x: None)
    exchange.import_(b, f, log=lambda *x: None)
    db = instance.load(b.results / "top" / "st-sub@nucleo_g474re")
    assert [(m["hypothesis"], m["check"], m["verdict"], m["copied_from"]) for m in db["manual_verdicts"]] == [
        ("H1", "b", "confirmed", f"lab {a.id}")]
    assert [r["id"] for r in db["references"]] == ["x/20260101T000000Z"]
    exchange.import_(b, f, log=lambda *x: None)                     # again: nothing twice
    db = instance.load(b.results / "top" / "st-sub@nucleo_g474re")
    assert len(db["manual_verdicts"]) == 1 and len(db["references"]) == 1
    # instance merge (a results tree that is not a lab space) brings them too
    c = labmod.init(tmp / "lab-c", tmp / "safety", name="lab-c")
    design = Design(root)
    instance.new(design, c.results, "top", "sub", "nucleo_g474re")
    instance.merge(design, a.results / "top", c.results / "top", log=lambda *x: None)
    dc = instance.load(c.results / "top" / "st-sub@nucleo_g474re")
    assert len(dc["manual_verdicts"]) == 1 and len(dc["references"]) == 1 and len(dc["runs"]) == 1
