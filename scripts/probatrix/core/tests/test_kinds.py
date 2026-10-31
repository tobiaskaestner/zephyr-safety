# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Unit tests of the registry, kind_of() and the Project roots (no benchmarks import)."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from probatrix.core import config, kinds


@pytest.fixture
def empty(monkeypatch):
    monkeypatch.setattr(kinds, "_KINDS", {})
    monkeypatch.setattr(kinds, "PLUGINS", {})


def fake(name, dirt=()):
    return SimpleNamespace(name=name, dirt_paths=dirt)


def test_register_and_get(empty):
    a = kinds.register(fake("a"))
    assert kinds.get("a") is a and kinds.names() == ["a"]
    kinds.register(a)                                   # the same object twice is fine
    with pytest.raises(kinds.KindError):
        kinds.register(fake("a"))
    with pytest.raises(kinds.KindError, match="unknown kind 'zz'"):
        kinds.get("zz")


def test_get_loads_a_plugin_module_by_name(empty, monkeypatch, tmp_path):
    (tmp_path / "fakekindmod.py").write_text(
        "from probatrix.core import kinds\nfrom types import SimpleNamespace\n"
        "kinds.register(SimpleNamespace(name='p', dirt_paths=('x',)))\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(kinds, "PLUGINS", {"p": "fakekindmod"})
    assert kinds.get("p").name == "p"
    with config.use(config.project().with_(default_kind="p")):
        assert kinds.dirt_paths()[-1] == "x"


def test_kind_of_order(empty):
    for n in ("a", "b", "c", "dflt"):
        kinds.register(fake(n))
    proj = config.project().with_()
    with config.use(proj.with_(default_kind="dflt")):
        assert kinds.kind_of({"name": "x"}).name == "dflt"                       # the Project default
        assert kinds.kind_of({"name": "x"}, {"kind": "b"}).name == "b"            # the parent
        assert kinds.kind_of({"kind": "a"}, {"kind": "b"}).name == "a"            # the design file first
        assert kinds.kind_of({}, {}, {"kind": "c"}).name == "c"                   # the grandparent
        assert kinds.kind_of(SimpleNamespace(data={"kind": "a"})).name == "a"     # an object with .data
        root = config.Root(Path("/r"), "b")
        assert kinds.kind_of({}, {}, root).name == "b"                            # the root
        assert kinds.kind_of({"kind": "a"}, root).name == "a"
        assert kinds.kind_of({}, config.Root(Path("/r"))).name == "dflt"          # a root without a kind
    with config.use(proj.with_(default_kind="nope")):
        with pytest.raises(kinds.KindError):
            kinds.kind_of({})


def test_project_roots(tmp_path):
    p = config.Project.at(tmp_path)
    assert p.design_root == tmp_path / "validation" / "empirical" / "latencies"
    assert p.default_kind == "latbench"
    two = p.with_(roots=(config.Root(tmp_path / "a"), config.Root(tmp_path / "f", "formal")))
    assert two.design_root == tmp_path / "a"
    assert two.root_of(tmp_path / "f" / "st-x" / "ex-y").kind == "formal"
    assert two.root_of(tmp_path / "other") is None
    assert two.with_(design_root=tmp_path / "z").roots[1].kind == "formal"
    assert two.with_(design_root=tmp_path / "z").design_root == tmp_path / "z"


def test_dirt_paths_are_those_of_one_kind(empty, tmp_path):
    """An edit below the path of kind B does not make a build of kind A dirty."""
    import subprocess
    from probatrix.core import design

    def git(*a):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=tmp_path, check=True,
                       capture_output=True)
    a, b = kinds.register(fake("a", ("spec/a",))), kinds.register(fake("b", ("spec/b",)))
    git("init", "-q")
    for d in ("spec/a", "spec/b", "core"):
        (tmp_path / d).mkdir(parents=True)
        (tmp_path / d / "f").write_text("1")
    git("add", "-A")
    git("commit", "-qm", "x")
    proj = config.Project.at(tmp_path, dirt_paths=("core",), default_kind="a")
    with config.use(proj):
        assert kinds.dirt_paths(a) == ("core", "spec/a") and kinds.dirt_paths() == ("core", "spec/a")
        assert design.repo_rev(kind=a)[1] is False and design.repo_rev(kind=b)[1] is False
        (tmp_path / "spec" / "b" / "f").write_text("2")
        assert design.repo_rev(kind=a)[1] is False          # kind B's spec: not dirty for A
        assert design.repo_rev()[1] is False                # default kind is A
        assert design.repo_rev(kind=b)[1] is True
        git("checkout", "--", ".")
        (tmp_path / "core" / "f").write_text("2")
        assert design.repo_rev(kind=a)[1] is True and design.repo_rev(kind=b)[1] is True   # the Project's path


def test_the_default_project_has_a_root_for_each_kind(tmp_path):
    p = config.Project.at(tmp_path)
    assert [(r.path.relative_to(tmp_path).as_posix(), r.kind) for r in p.roots] == [
        ("validation/empirical/latencies", None), ("validation/formal/kernel-spec", "tlaplus")]
    assert p.design_root == tmp_path / "validation" / "empirical" / "latencies"      # the first root stays the default
    assert p.root_of(tmp_path / "validation" / "formal" / "kernel-spec" / "st-x").kind == "tlaplus"
    assert len(config.Project.at(tmp_path, design_root=tmp_path / "d").roots) == 1   # an explicit design root: one root


def test_the_base_kind_hooks_for_lint(tmp_path):
    from probatrix.core.design import Experiment
    import yaml

    class K(kinds.BaseKind):
        name = "k"
        def points(self, experiment):
            if "bad" in experiment:
                raise SystemExit("error: bad list")
            return [{"id": "p"}]

    k = K()
    assert k.stat_needed("verdict") is True
    folder = tmp_path / "ex-a"
    folder.mkdir()
    (folder / "experiment.yaml").write_text(yaml.safe_dump({"name": "a"}))
    e = SimpleNamespace(folder=folder, name="a", data={"name": "a"})
    pts, probs = k.lint_experiment(e)
    assert pts == [{"id": "p"}] and probs == [("error", folder / "experiment.md", "each experiment has a description experiment.md")]
    (folder / "experiment.md").write_text("x")
    assert k.lint_experiment(e) == ([{"id": "p"}], [])
    e2 = SimpleNamespace(folder=tmp_path / "ex-b", name="a", data={"name": "a", "bad": 1})
    pts, probs = k.lint_experiment(e2)
    assert pts is None and [p[0] for p in probs] == ["error", "error", "error"]
    assert probs[0][2] == "the folder must be ex-a" and probs[2][2] == "bad list"
