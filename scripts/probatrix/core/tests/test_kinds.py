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
