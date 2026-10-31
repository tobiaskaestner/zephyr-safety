# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the rebuild helpers of run.py (no build, no board)."""

import hashlib
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent

from probatrix.benchmarks import run  # noqa: E402


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


def test_old_west_topdir(tmp_path):
    """A run before -DWEST_TOPDIR: the west workspace of the old trees root, moved with the trees."""
    (tmp_path / "ws" / ".west").mkdir(parents=True)
    old_root = tmp_path / "ws" / "latency-trees"
    assert run.old_west_topdir(["cmake"], str(old_root), "/x/lab/latency-trees") == ["-DWEST_TOPDIR=/x/lab"]
    assert run.old_west_topdir(["cmake", "-DWEST_TOPDIR=/y"], str(old_root), "/x/lab/latency-trees") == []
    assert run.old_west_topdir(["cmake"], str(old_root), "/x/lab/trees") == []
    assert run.old_west_topdir(["cmake"], str(tmp_path / "no-ws" / "latency-trees"), "/x/lab/latency-trees") == [
        f"-DWEST_TOPDIR={run.NO_WEST_TOPDIR}"]      # no workspace then: no prefix map now either


def test_firmware_hash_leaves_out_the_documentation(tmp_path, monkeypatch):
    """A page in doc/ (or a Markdown file) does not change the firmware hash; a source file does."""
    import subprocess

    def git(*args):
        return subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True,
                              text=True).stdout.strip()

    bench = tmp_path / "tests" / "benchmarks"
    (bench / "app" / "src").mkdir(parents=True)
    (bench / "app" / "src" / "main.c").write_text("int main(void) { return 0; }\n")
    git("init", "-q")
    git("-c", "user.name=t", "-c", "user.email=t@t", "add", "-A")
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "a")
    monkeypatch.setattr(run, "BENCH_DIR", bench)
    first = run.firmware_hash(tmp_path, "HEAD")
    for f in (bench / "app" / "doc" / "index.rst", bench / "common" / "boards" / "b" / "doc" / "index.rst",
              bench / "app" / "doc" / "app.tdl"):
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("page\n")
    git("add", "-A")
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "b")
    assert run.firmware_hash(tmp_path, "HEAD") == first
    (bench / "app" / "src" / "main.c").write_text("int main(void) { return 1; }\n")
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "c")
    assert run.firmware_hash(tmp_path, "HEAD") != first


def _build_point_call(tmp_path, monkeypatch, builder):
    """Call build_point() for one point with subprocess.run mocked; return (args, the commands run, env, cwd)."""
    from probatrix.benchmarks import trees

    root = tmp_path / "trees"
    tree_cfg = {"root": root, "trees": {"ws": {"repos": {"zephyr": {"path": "zephyr"}, "hal": {"path": "mods/hal"}}}}}
    bench = tmp_path / "safety" / "tests" / "benchmarks"
    bdir = tmp_path / "bdir"
    (bdir / "zephyr").mkdir(parents=True)
    (bdir / "zephyr" / ".config").write_text("CONFIG_LATBENCH_SAMPLES=100\n# CONFIG_LATBENCH_X is not set\n")
    log = tmp_path / "build.log"
    point = {"id": "p1", "axes": {}, "kconfig": {"LATBENCH_SAMPLES": 100, "LATBENCH_X": False},
             "conf_files": ["common/conf/a.conf", "common/conf/b.conf"], "dtc_overlays": ["common/o.overlay"]}
    calls = []

    def fake_run(cmd, **kw):
        calls.append((cmd, kw))
        return type("R", (), {"returncode": 0})()

    monkeypatch.setattr(run.subprocess, "run", fake_run)
    monkeypatch.setattr(trees, "west_topdir", lambda cwd: None)
    monkeypatch.setattr(trees, "west_config_problems", lambda cwd: [])
    monkeypatch.setenv("ZEPHYR_BASE", "/caller/zephyr")
    monkeypatch.setenv("KEEP_ME", "1")
    args = run.build_point(tree_cfg, "ws", point, bench, "irq_latency", "a" * 40, "nucleo_g474re",
                           {"modules": ["hal"]}, Path("/opt/sdk"), bdir, log, build_version="v4.2.0-1-gabc",
                           builder=builder)
    return args, calls, bench, root, bdir


def test_build_point_command_line_cmake(tmp_path, monkeypatch):
    """The CMake argument list of one point is pinned: same args, same order, same env."""
    args, calls, bench, root, bdir = _build_point_call(tmp_path, monkeypatch, "cmake")
    assert args == [
        "cmake", "-GNinja", "-S", str(bench / "irq_latency"), "-B", str(bdir), "-DBOARD=nucleo_g474re",
        f"-DZEPHYR_MODULES={root / 'ws' / 'mods/hal'};{bench.parents[1]}",
        f"-DWEST_TOPDIR={root / 'ws'}",
        f"-DEXTRA_CONF_FILE={bench / 'common/conf/a.conf'};{bench / 'common/conf/b.conf'}",
        f"-DEXTRA_DTC_OVERLAY_FILE={bench / 'common/o.overlay'}",
        "-DLATBENCH_SRC_REV=" + "a" * 40,
        "-DBUILD_VERSION=v4.2.0-1-gabc",
        "-DCONFIG_LATBENCH_SAMPLES=100",
        "-DCONFIG_LATBENCH_X=n",
    ]
    assert [c for c, _ in calls] == [args, ["ninja", "-C", str(bdir)]]
    for _, kw in calls:
        assert kw["cwd"] == root / "ws"
        assert kw["env"]["ZEPHYR_BASE"] == str(root / "ws" / "zephyr")
        assert kw["env"]["ZEPHYR_TOOLCHAIN_VARIANT"] == "zephyr"
        assert kw["env"]["ZEPHYR_SDK_INSTALL_DIR"] == "/opt/sdk"
        assert kw["env"]["KEEP_ME"] == "1"


def test_build_point_command_line_west(tmp_path, monkeypatch):
    """The west head of the argument list, and the command that runs (python -m west, no user config)."""
    args, calls, bench, root, bdir = _build_point_call(tmp_path, monkeypatch, "west")
    assert args[:10] == ["west", "build", "--no-sysbuild", "-d", str(bdir), "-b", "nucleo_g474re",
                         str(bench / "irq_latency"), "--",
                         f"-DZEPHYR_MODULES={root / 'ws' / 'mods/hal'};{bench.parents[1]}"]
    assert args[10] == f"-DWEST_TOPDIR={root / 'ws'}"
    assert args[11:] == [
        f"-DEXTRA_CONF_FILE={bench / 'common/conf/a.conf'};{bench / 'common/conf/b.conf'}",
        f"-DEXTRA_DTC_OVERLAY_FILE={bench / 'common/o.overlay'}",
        "-DLATBENCH_SRC_REV=" + "a" * 40,
        "-DBUILD_VERSION=v4.2.0-1-gabc",
        "-DCONFIG_LATBENCH_SAMPLES=100",
        "-DCONFIG_LATBENCH_X=n",
    ]
    assert [c for c, _ in calls] == [[sys.executable, "-m", "west", *args[1:]]]
    env = calls[0][1]["env"]
    assert env["WEST_CONFIG_GLOBAL"] == env["WEST_CONFIG_SYSTEM"] == "/dev/null"
    assert env["ZEPHYR_BASE"] == str(root / "ws" / "zephyr")
