# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""A results tree of the formal design builds with the default Project, which has the latency design first."""

import json

from probatrix.core import build, config
from probatrix.tlaplus import kind

FOLDER = "validation/formal/kernel-spec"


def make(tmp_path, design):
    root = tmp_path / "kernel-formal"
    root.mkdir()
    data = {"format": "tlaplus-instance/1", "instance": "kernel-formal", "design": design, "runs": [],
            "references": [], "substudies": [], "manual_verdicts": [], "notes": []}
    (root / "instance.json").write_text(json.dumps(data))
    return root


def test_the_tree_builds_with_the_design_that_it_names(tmp_path):
    root = make(tmp_path, {"folder": FOLDER})
    t, _ = build.build(root, log=lambda *a: None)
    assert t.design.root == config.project().repo / FOLDER and t.kind is kind.KIND
    assert json.loads((root / "study.json").read_text())["format"] == "tlaplus-study/2"


def test_the_option_names_the_design(tmp_path):
    root = make(tmp_path, {})
    t, _ = build.build(root, log=lambda *a: None, design_root=config.project().repo / FOLDER)
    assert t.kind is kind.KIND

