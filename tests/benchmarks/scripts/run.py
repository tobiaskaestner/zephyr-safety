#!/usr/bin/env python3
# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Run a latency experiment from pinned, clean trees and record its provenance.

    run.py experiments/<name>.yaml --out <dir> [--only ID ...] [--dry-run]

Rules (a run stops before it builds anything if one is broken):

- The safety repo that holds this script and the experiment file is clean.
- Each tree of the experiment is at its pinned rev in trees.yaml and clean
  (scripts/trees.py setup creates the trees).
- The Zephyr SDK has the pinned version.
- The build uses only the modules of the tree (ZEPHYR_MODULES), not the
  modules of a west workspace.

Output: <out>/<experiment>/<UTC time>/ with manifest.json (all revs, tool
versions, commands) and <tree>/<point>/ with rep<N>.log, the .config, the
devicetree, zephyr.elf and build.log. summary.txt has the percentiles.
src/ is the snapshot of the committed sources (git archive) that the run
built from.

Experiment file:

    name: irq-smoke
    app: irq_latency                    # folder in tests/benchmarks
    board: nucleo_g474re                # optional, a key of boards.yaml
    trees: [ws-safety]
    repeat: 1
    timeout: 600                        # s per repetition
    common:                             # added to every point
      kconfig: {LATBENCH_SAMPLES: 100000}
      conf_files: [common/conf/lean.conf]       # relative to tests/benchmarks
    axes:                               # cartesian product, id = values joined by '-'
      path:
        stock: {kconfig: {LATBENCH_IRQ_PATH_STOCK: y}}
        direct: {...}
      anchor:
        default: {}
    points:                             # or explicit points (also allowed together)
      - id: direct-busy
        kconfig: {...}
"""

import argparse
import datetime
import hashlib
import itertools
import json
import os
import platform
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import latbench  # noqa: E402
import trees  # noqa: E402

BENCH_DIR = trees.BENCH_DIR


def fail(msg):
    sys.exit(f"error: {msg}")


def tool_version(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        return None
    return (r.stdout or r.stderr).strip().splitlines()[0]


def merge(a, b):
    out = {
        "kconfig": {**a.get("kconfig", {}), **b.get("kconfig", {})},
        "conf_files": a.get("conf_files", []) + b.get("conf_files", []),
        "dtc_overlays": a.get("dtc_overlays", []) + b.get("dtc_overlays", []),
    }
    return out


def expand_points(exp):
    common = exp.get("common", {})
    points = []
    axes = exp.get("axes", {})
    if axes:
        for axis, values in axes.items():
            bad = [k for k in values if not isinstance(k, str)]
            if bad:
                # YAML reads on/off/yes/no/true/false as booleans.
                fail(f"axis '{axis}': value names must be strings, not {bad} (quote them or rename them)")
        names = list(axes)
        for combo in itertools.product(*(axes[n].items() for n in names)):
            spec = common
            for _, value in combo:
                spec = merge(spec, value or {})
            spec["id"] = "-".join(k for k, _ in combo)
            spec["axes"] = {n: k for n, (k, _) in zip(names, combo)}
            points.append(spec)
    for p in exp.get("points", []):
        spec = merge(common, p)
        spec["id"] = p["id"]
        spec["axes"] = {}
        points.append(spec)
    ids = [p["id"] for p in points]
    if len(ids) != len(set(ids)):
        fail(f"duplicate point ids: {ids}")
    return points


def kconfig_value(v):
    if v is True:
        return "y"
    if v is False:
        return "n"
    return str(v)


def safety_repo_state():
    root = Path(trees.git("rev-parse", "--show-toplevel", cwd=BENCH_DIR))
    rev, dirty = trees.repo_state(root)
    return root, rev, dirty


def flash_command(board_cfg, zephyr, pdir):
    """Return one command that runs the flash commands of the board in order."""
    images = {"zephyr": str(zephyr), "elf": str(pdir / "zephyr.elf"), "hex": str(pdir / "zephyr.hex")}
    cmds = [[arg.format(**images) for arg in cmd] for cmd in board_cfg["flash"]]
    if len(cmds) == 1:
        return cmds[0]
    return ["sh", "-c", " && ".join(shlex.join(c) for c in cmds)]


def export_snapshot(repo_root, rev, dest):
    """Export the committed benchmark sources at rev to dest; return the bench folder in dest.

    A run builds from this snapshot, not from the worktree, so that work in
    the worktree during a long run cannot change what the run builds.
    """
    rel = BENCH_DIR.relative_to(repo_root)
    dest.mkdir(parents=True, exist_ok=True)
    archive = subprocess.Popen(["git", "archive", "--format=tar", rev, "--", str(rel)], cwd=repo_root,
                               stdout=subprocess.PIPE)
    subprocess.run(["tar", "-x", "-C", str(dest)], stdin=archive.stdout, check=True)
    if archive.wait() != 0:
        fail(f"git archive {rev} failed")
    return dest / rel


def check_config(config_file, kconfig):
    """Return the requested symbols that do not have their value in the .config.

    Kconfig only warns about a symbol that the tree does not have or whose
    dependencies are not met, and then builds with the default. This check
    makes that an error.
    """
    have = {}
    for line in Path(config_file).read_text().splitlines():
        if line.startswith("CONFIG_") and "=" in line:
            key, _, value = line.partition("=")
            have[key[len("CONFIG_"):]] = value.strip('"')
        elif line.startswith("# CONFIG_") and line.endswith(" is not set"):
            have[line[len("# CONFIG_"):-len(" is not set")]] = "n"
    bad = []
    for sym, value in kconfig.items():
        want = kconfig_value(value)
        got = have.get(sym, "n")
        if got != want:
            bad.append(f"{sym}: requested {want}, .config has {got}")
    return bad


def build_point(tree_cfg, tree, point, src_bench, app, src_rev, board, board_cfg, sdk, bdir, log):
    app_dir = src_bench / app
    zephyr = trees.repo_dir(tree_cfg, tree, "zephyr")
    modules = [str(trees.repo_dir(tree_cfg, tree, name)) for name in board_cfg["modules"]]
    args = [
        "cmake",
        "-GNinja",
        "-S",
        str(app_dir),
        "-B",
        str(bdir),
        f"-DBOARD={board}",
        f"-DZEPHYR_MODULES={';'.join(modules)}",
    ]
    if point["conf_files"]:
        args.append("-DEXTRA_CONF_FILE=" + ";".join(str(src_bench / f) for f in point["conf_files"]))
    if point["dtc_overlays"]:
        args.append("-DEXTRA_DTC_OVERLAY_FILE=" + ";".join(str(src_bench / f) for f in point["dtc_overlays"]))
    args.append(f"-DLATBENCH_SRC_REV={src_rev}")
    for sym, value in point["kconfig"].items():
        args.append(f"-DCONFIG_{sym}={kconfig_value(value)}")

    env = {k: v for k, v in os.environ.items() if not k.startswith("ZEPHYR_")}
    env.update(
        ZEPHYR_BASE=str(zephyr),
        ZEPHYR_TOOLCHAIN_VARIANT="zephyr",
        ZEPHYR_SDK_INSTALL_DIR=str(sdk),
    )
    with open(log, "w") as f:
        f.write("$ " + shlex.join(args) + "\n")
        f.flush()
        for cmd in (args, ["ninja", "-C", str(bdir)]):
            r = subprocess.run(cmd, env=env, stdout=f, stderr=subprocess.STDOUT)
            if r.returncode != 0:
                fail(f"build failed for {tree}/{point['id']}, see {log}")
    bad = check_config(bdir / "zephyr" / ".config", point["kconfig"])
    if bad:
        fail(f"Kconfig values not applied for {tree}/{point['id']}:\n  " + "\n  ".join(bad))
    return args


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("experiment")
    p.add_argument("--out", required=True)
    p.add_argument("--trees-root")
    p.add_argument("--port", help="serial port of the console (default: console of the board in boards.yaml)")
    p.add_argument("--only", nargs="*", help="run only these point ids")
    p.add_argument("--dry-run", action="store_true", help="check and list the points, do not build")
    p.add_argument("--build-only", action="store_true", help="build each point in a temporary folder, do not flash")
    p.add_argument("--keep-build", action="store_true")
    args = p.parse_args()

    exp_path = Path(args.experiment).resolve()
    exp_text = exp_path.read_text()
    exp = yaml.safe_load(exp_text)

    # 1. Provenance checks, before anything is built.
    repo_root, repo_rev, repo_dirty = safety_repo_state()
    if repo_dirty:
        fail(f"safety repo {repo_root} is dirty, commit first:\n{repo_dirty}")
    if not exp_path.is_relative_to(repo_root):
        fail(f"{exp_path} is not in the safety repo {repo_root}")

    tree_cfg = trees.load(args.trees_root)
    boards = trees.load_boards()
    board = exp.get("board", boards["default"])
    try:
        repos = trees.board_repos(boards, board)
        sdk = trees.check_toolchain(tree_cfg)
        for t in exp["trees"]:
            if t not in tree_cfg["trees"]:
                raise trees.TreeError(f"unknown tree '{t}'")
            trees.check_tree_has(tree_cfg, t, repos)
            trees.check_tree(tree_cfg, t, repos)
    except trees.TreeError as e:
        fail(str(e))
    board_cfg = boards["boards"][board]
    port = args.port or board_cfg["console"]
    if not (BENCH_DIR / exp["app"]).is_dir():
        fail(f"no app folder {exp['app']}")
    points = expand_points(exp)
    if args.only:
        points = [pt for pt in points if pt["id"] in args.only]
    if not points:
        fail("no points to run")

    print(f"safety {repo_rev[:12]}  trees {', '.join(exp['trees'])}  {len(points)} points x {exp.get('repeat', 1)}")
    for pt in points:
        print(f"  {pt['id']}: {pt['kconfig']} {pt['conf_files']} {pt['dtc_overlays']}")
    if args.dry_run:
        return
    if args.build_only:
        import tempfile

        with tempfile.TemporaryDirectory(prefix="latbench-build-") as tmp:
            src_bench = export_snapshot(repo_root, repo_rev, Path(tmp) / "src")
            for tree in exp["trees"]:
                for pt in points:
                    bdir = Path(tmp) / tree / pt["id"]
                    bdir.mkdir(parents=True)
                    print(f"[{tree}/{pt['id']}] build", flush=True)
                    build_point(tree_cfg, tree, pt, src_bench, exp["app"], repo_rev, board, board_cfg, sdk,
                                bdir / "build", bdir / "build.log")
        print("all points build")
        return

    # 2. Output folder and manifest.
    started = datetime.datetime.now(datetime.timezone.utc)
    run_dir = Path(args.out).resolve() / exp["name"] / started.strftime("%Y%m%dT%H%M%SZ")
    run_dir.mkdir(parents=True)
    src_bench = export_snapshot(repo_root, repo_rev, run_dir / "src")
    probe = subprocess.run(
        ["udevadm", "info", "--query=property", port], capture_output=True, text=True
    ).stdout
    probe_serial = next((ln.split("=", 1)[1] for ln in probe.splitlines() if ln.startswith("ID_SERIAL_SHORT=")), None)

    import serial

    manifest = {
        "experiment": exp["name"],
        "experiment_file": str(exp_path.relative_to(repo_root)),
        "experiment_yaml": exp_text,
        "command": shlex.join(sys.argv),
        "started": started.isoformat(),
        "host": platform.node(),
        "safety": {"path": str(repo_root), "rev": repo_rev, "snapshot": str(src_bench.relative_to(run_dir))},
        "trees": {
            t: {**tree_cfg["trees"][t], "repos": {r: tree_cfg["trees"][t]["repos"][r] for r in repos}}
            for t in exp["trees"]
        },
        "trees_root": str(tree_cfg["root"]),
        "toolchain": {"zephyr_sdk": str(tree_cfg["toolchain"]["zephyr_sdk"]["version"]), "path": str(sdk)},
        "tools": {
            "cmake": tool_version(["cmake", "--version"]),
            "ninja": tool_version(["ninja", "--version"]),
            # The tools that flash this board (first word of each flash command).
            **{cmd[0]: tool_version([cmd[0], "--version"]) for cmd in board_cfg["flash"]},
            "python": sys.version.split()[0],
            "pyserial": serial.__version__,
        },
        "board": board,
        "board_cfg": board_cfg,
        "console": port,
        "probe_serial": probe_serial,
        "points": [],
    }
    manifest_file = run_dir / "manifest.json"

    def save_manifest():
        manifest_file.write_text(json.dumps(manifest, indent=2) + "\n")

    save_manifest()

    # 3. Build, flash and capture each point.
    logs = []
    for tree in exp["trees"]:
        zephyr = trees.repo_dir(tree_cfg, tree, "zephyr")
        for pt in points:
            pdir = run_dir / tree / pt["id"]
            bdir = pdir / "build"
            pdir.mkdir(parents=True)
            print(f"[{tree}/{pt['id']}] build", flush=True)
            cmake_args = build_point(tree_cfg, tree, pt, src_bench, exp["app"], repo_rev, board, board_cfg, sdk,
                                     bdir, pdir / "build.log")
            elf = bdir / "zephyr" / "zephyr.elf"
            for f in (elf, bdir / "zephyr" / "zephyr.hex", bdir / "zephyr" / ".config", bdir / "zephyr" / "zephyr.dts"):
                if f.exists():
                    shutil.copy2(f, pdir / f.name)
            entry = {
                "tree": tree,
                "id": pt["id"],
                "axes": pt["axes"],
                "kconfig": pt["kconfig"],
                "conf_files": pt["conf_files"],
                "dtc_overlays": pt["dtc_overlays"],
                "cmake": cmake_args,
                "elf_sha256": hashlib.sha256(elf.read_bytes()).hexdigest(),
                "logs": [],
            }
            manifest["points"].append(entry)
            flash_cmd = flash_command(board_cfg, zephyr, pdir)
            for rep in range(1, exp.get("repeat", 1) + 1):
                log = pdir / f"rep{rep}.log"
                print(f"[{tree}/{pt['id']}] rep {rep}", flush=True)
                try:
                    latbench.run_capture(log, flash_cmd, port, timeout=exp.get("timeout", 600))
                except latbench.CaptureError as e:
                    entry["error"] = str(e)
                    save_manifest()
                    fail(f"{tree}/{pt['id']} rep {rep}: {e}")
                entry["logs"].append(str(log.relative_to(run_dir)))
                logs.append(log)
                save_manifest()
            if not args.keep_build:
                shutil.rmtree(bdir)

    manifest["finished"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    save_manifest()

    # 4. Summary.
    with open(run_dir / "summary.txt", "w") as f:
        sys.stdout = f
        try:
            latbench.summary(argparse.Namespace(logs=[str(x) for x in logs], json=False))
        finally:
            sys.stdout = sys.__stdout__
    print((run_dir / "summary.txt").read_text())
    print(f"results in {run_dir}")


if __name__ == "__main__":
    main()
