# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the rebuild helpers of run.py (no build, no board)."""

import hashlib
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))

import run  # noqa: E402


def make_run(tmp_path, points):
    run_dir = tmp_path / "exp" / "20261025T000000Z"
    for tree, pid in points:
        (run_dir / tree / pid).mkdir(parents=True)
    manifest = {"points": [{"tree": t, "id": p, "cmake": []} for t, p in points]}
    (run_dir / "manifest.json").write_text(json.dumps(manifest))
    return run_dir


def test_find_points_of_a_run_folder(tmp_path):
    run_dir = make_run(tmp_path, [("ws-safety", "a"), ("ws-safety", "b"), ("ws-up", "a")])
    found, _, entries = run.find_points(run_dir)
    assert found == run_dir
    assert [(e["tree"], e["id"]) for e in entries] == [("ws-safety", "a"), ("ws-safety", "b"), ("ws-up", "a")]
    _, _, entries = run.find_points(run_dir, only=["a"])
    assert [(e["tree"], e["id"]) for e in entries] == [("ws-safety", "a"), ("ws-up", "a")]


def test_find_points_of_a_point_folder(tmp_path):
    run_dir = make_run(tmp_path, [("ws-safety", "a"), ("ws-up", "a")])
    found, _, entries = run.find_points(run_dir / "ws-up" / "a")
    assert found == run_dir
    assert [(e["tree"], e["id"]) for e in entries] == [("ws-up", "a")]


@pytest.mark.parametrize("sub, only", [("nothing", None), (".", ["c"])])
def test_find_points_errors(tmp_path, sub, only):
    run_dir = make_run(tmp_path, [("ws-safety", "a")])
    with pytest.raises(SystemExit):
        run.find_points(run_dir / sub, only)


def test_move_paths():
    cmake = [
        "cmake", "-GNinja", "-S", "/old/run/src/tests/benchmarks/wake_latency",
        "-B", "/old/run/ws-safety/p/build",
        "-DZEPHYR_MODULES=/trees/ws-safety/modules/hal/cmsis_6;/old/run/src",
        "-DEXTRA_CONF_FILE=/old/run/src/tests/benchmarks/common/conf/lean.conf",
        "-DCONFIG_FOO=/old/runx",  # not in the folder /old/run
    ]
    out = run.move_paths(cmake, {"/old/run": "/new/run"}, Path("/tmp/b"))
    assert out == [
        "cmake", "-GNinja", "-S", "/new/run/src/tests/benchmarks/wake_latency",
        "-B", "/tmp/b",
        "-DZEPHYR_MODULES=/trees/ws-safety/modules/hal/cmsis_6;/new/run/src",
        "-DEXTRA_CONF_FILE=/new/run/src/tests/benchmarks/common/conf/lean.conf",
        "-DCONFIG_FOO=/old/runx",
    ]
    assert run.move_paths(["-S", "/old/run"], {"/old/run": "/new"}, Path("/b")) == ["-S", "/new"]


def test_compare_point(tmp_path):
    pdir, bdir = tmp_path / "p", tmp_path / "b"
    (bdir / "zephyr").mkdir(parents=True)
    pdir.mkdir()
    for name, old, new in [("zephyr.hex", b"hex", b"hex"), (".config", b"A=y\n", b"A=n\n")]:
        (pdir / name).write_bytes(old)
        (bdir / "zephyr" / name).write_bytes(new)
    (bdir / "zephyr" / "zephyr.elf").write_bytes(b"elf")
    same, diff = run.compare_point(pdir, bdir, hashlib.sha256(b"elf").hexdigest())
    assert same == ["zephyr.elf", "zephyr.hex"]
    assert diff == [".config"]  # zephyr.dts is not stored, so it is not compared
    _, diff = run.compare_point(pdir, bdir, "0" * 64)
    assert diff == ["zephyr.elf", ".config"]


def test_compare_point_ignores_path_comments(tmp_path):
    """The comments of .config and zephyr.dts have the paths of the host; the values must be the same."""
    pdir, bdir = tmp_path / "p", tmp_path / "b"
    (bdir / "zephyr").mkdir(parents=True)
    pdir.mkdir()
    (pdir / ".config").write_text("# cmsis_6 (/wrk/a/modules/cmsis_6)\nCONFIG_A=y\n# CONFIG_B is not set\n")
    (bdir / "zephyr" / ".config").write_text("# cmsis_6 (/wrk/b/modules/cmsis_6)\nCONFIG_A=y\n# CONFIG_B is not set\n")
    (pdir / "zephyr.dts").write_text("/ {\n\tmodel = \"x\"; /* in a/zephyr/b.dts:15 */\n};\n")
    (bdir / "zephyr" / "zephyr.dts").write_text("/ {\n\tmodel = \"x\";      /* in zephyr/b.dts:15 */\n};\n")
    (bdir / "zephyr" / "zephyr.elf").write_bytes(b"elf")
    same, diff = run.compare_point(pdir, bdir, hashlib.sha256(b"elf").hexdigest())
    assert (same, diff) == (["zephyr.elf", ".config", "zephyr.dts"], [])
    (bdir / "zephyr" / ".config").write_text("CONFIG_A=y\nCONFIG_B=y\n")
    (bdir / "zephyr" / "zephyr.dts").write_text("/ {\n\tmodel = \"y\";\n};\n")
    _, diff = run.compare_point(pdir, bdir, hashlib.sha256(b"elf").hexdigest())
    assert diff == [".config", "zephyr.dts"]


def test_compare_point_elf_image(tmp_path):
    """Two ELFs with other debug information but the same loadable sections give the same image."""
    objcopy = tmp_path / "objcopy"
    objcopy.write_text('#!/bin/sh\nhead -c 3 "$3" > "$4"\n')  # "-O ihex IN OUT": the first 3 bytes are the image
    objcopy.chmod(0o755)
    pdir, bdir = tmp_path / "p", tmp_path / "b"
    (bdir / "zephyr").mkdir(parents=True)
    pdir.mkdir()
    (pdir / "zephyr.elf").write_bytes(b"IMGdebug-old")
    (bdir / "zephyr" / "zephyr.elf").write_bytes(b"IMGdebug-new")
    old_sha = hashlib.sha256(b"IMGdebug-old").hexdigest()
    same, diff = run.compare_point(pdir, bdir, old_sha, str(objcopy), tmp_path)
    assert (same, diff) == (["ELF image"], ["zephyr.elf"])
    (bdir / "zephyr" / "zephyr.elf").write_bytes(b"XYZdebug-new")
    same, diff = run.compare_point(pdir, bdir, old_sha, str(objcopy), tmp_path)
    assert (same, diff) == ([], ["zephyr.elf", "ELF image"])


def test_cmake_cache_value(tmp_path):
    (tmp_path / "CMakeCache.txt").write_text("# x\nCMAKE_OBJCOPY:FILEPATH=/sdk/bin/objcopy\nOTHER:STRING=a=b\n")
    assert run.cmake_cache_value(tmp_path, "CMAKE_OBJCOPY") == "/sdk/bin/objcopy"
    assert run.cmake_cache_value(tmp_path, "OTHER") == "a=b"
    assert run.cmake_cache_value(tmp_path, "MISSING") is None
    assert run.cmake_cache_value(tmp_path / "none", "CMAKE_OBJCOPY") is None


@pytest.mark.parametrize("argv", [
    ["--rebuild", "x", "exp.yaml"],
    ["--rebuild", "x", "--out", "o"],
    ["exp.yaml"],
    ["--out", "o"],
])
def test_command_line_errors(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["run.py", *argv])
    with pytest.raises(SystemExit) as e:
        run.main()
    assert e.value.code == 2
