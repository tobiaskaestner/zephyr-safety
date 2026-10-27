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
    (repo / "scripts" / "benchmarks").mkdir(parents=True)
    (repo / "scripts" / "benchmarks" / "study.py").write_text("")
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
    assert added == ["exp1/20260101T000000Z"] and not refused and not warnings
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
    assert added == [] and "experiment.yaml differs between the two labs" in refused[0]
    assert any("hypotheses.yaml differs" in w for w in warnings)


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
