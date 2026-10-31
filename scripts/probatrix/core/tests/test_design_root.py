# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Which design root a results tree is built with (build.design_root_of)."""

import json

from probatrix.core import build, config


def project(tmp_path):
    repo = tmp_path / "repo"
    a, b = repo / "design" / "a", repo / "design" / "b"
    a.mkdir(parents=True)
    b.mkdir(parents=True)
    return repo, config.Project(repo=repo, roots=(config.Root(a), config.Root(b, "other")))


def tree_with(tmp_path, data):
    root = tmp_path / "results" / "top"
    root.mkdir(parents=True)
    (root / "instance.json").write_text(json.dumps(data))
    return root


def test_the_folder_of_the_top_instance_names_the_root(tmp_path):
    repo, p = project(tmp_path)
    root = tree_with(tmp_path, {"design": {"folder": "design/b"}})
    with config.use(p):
        assert build.design_root_of(root) == p.roots[1].path


def test_no_design_field_or_an_unknown_folder_gives_the_first_root(tmp_path):
    repo, p = project(tmp_path)
    with config.use(p):
        assert build.design_root_of(tree_with(tmp_path, {"runs": []})) == p.roots[0].path
        root = tmp_path / "results" / "top"
        (root / "instance.json").write_text(json.dumps({"design": {"folder": "design/c"}}))
        assert build.design_root_of(root) == p.roots[0].path
        assert build.design_root_of(tmp_path / "nothing") == p.roots[0].path


def test_the_latency_tree_keeps_the_first_root():
    p = config.Project.default()
    root_folder = p.design_root.relative_to(p.repo)
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as d, config.use(p):
        (Path(d) / "instance.json").write_text(json.dumps({"design": {"folder": str(root_folder)}}))
        assert build.design_root_of(d) == p.design_root
