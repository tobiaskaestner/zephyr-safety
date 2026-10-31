#!/usr/bin/env python3
# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Run a latency experiment from pinned, clean trees and record its provenance.

    run.py validation/empirical/latencies/st-<study>/ex-<name>/experiment.yaml --out <dir> [--only ID ...] [--dry-run]

Rules (a run stops before it builds anything if one is broken):

- The safety repo that holds this script and the experiment file is clean,
  and it stays at the same commit while the run builds (checked before each
  point).
- Each tree of the experiment is at its pinned rev in validation/trees/<tree>.yml
  and clean (study.py trees setup creates the trees).
- The Zephyr SDK has the pinned version.
- The build uses only the modules of the tree (ZEPHYR_MODULES), not the
  modules of a west workspace.
- The hardware map of the host (hw-map.yml, twister format, not checked in)
  has one connected entry for the board, with the fixture
  "latbench_loopback". It gives the probe and the console (scripts/probatrix/benchmarks/hwmap.py).

Output: <out>/<experiment>/<UTC time>/ with manifest.json (all revs, tool
versions, commands) and <tree>/<point>/ with rep<N>.log, the .config, the
devicetree, the images <app>-<tree>-<point>.elf/.hex and build.log.
summary.txt has the percentiles, one column per axis. At the end, run.py
writes the seal <UTC time>.sha256 beside the run folder (see
studylib/seal.py). If <out> is the folder of a study instance (it has
instance.json), the run goes to <out>/ex-<experiment>/<UTC time>/ and
run.py adds it to the run list (--role, --reason; --campaign names the
campaign in the entry). A run that stops before its seal (an error, Ctrl-C,
SIGTERM) leaves <UTC time>.failed.json beside its folder: the step, the
error and the end of the last log. Such a run is not in a run list.
--rebuild writes its result to <UTC time>.rebuild-<UTC time of the check>.json
beside the run folder.

The build reads the app from the safety repo, and the repo is the Zephyr
module "safety" of each build. The app gets LATBENCH_SRC_REV = a content
hash of the firmware files of tests/benchmarks (manifest: safety.bench_tree,
kind firmware/1; no scripts, Python or Markdown), so the same firmware
gives the same image at any commit. In a lab space, the images go
to the build cache (studylib/buildcache.py); a point with an image in the
cache is not built again (manifest: point build {key, from, built_by}). --build-only fills
the cache (or builds in a temporary folder outside a lab space).

Experiment file:

    name: irq-smoke
    app: irq_latency                    # folder in tests/benchmarks
    board: nucleo_g474re                # optional, a key of boards.yaml
    trees: [ws-up]
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
        t16: {value: 16, kconfig: {...}}   # value: the number of the value on a plot
    extra_axes: {load: none}            # axes that only the explicit points change,
                                        # with the value of all cube points
    points:                             # or explicit points (also allowed together)
      - id: direct-busy
        axes: {path: direct, anchor: default, load: busy}   # a value on each axis
        kconfig: {...}

Each point has a value on each axis. The axes of a point go into the
manifest, so that the analysis can group and plot the points.
"""

import argparse
import atexit
import datetime
import hashlib
import itertools
import json
import os
import platform
import re
import shlex
import shutil
import signal
import subprocess
import sys
from pathlib import Path

# A launcher: the folder scripts/ holds the package probatrix.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
if __name__ == "__main__":
    # in a lab space: the Python of the lab space (before PyYAML and the other packages)
    from probatrix.benchmarks.studylib import lab as _lab  # noqa: E402
    _lab.restart_with_lab_python(Path(__file__).resolve(), sys.argv[1:])

import yaml  # noqa: E402

from probatrix.benchmarks import hwmap  # noqa: E402
from probatrix.benchmarks import latbench  # noqa: E402
from probatrix.benchmarks import trees  # noqa: E402
from probatrix.core import config
from probatrix.benchmarks.studylib import lab as labmod  # noqa: E402
from probatrix.benchmarks.studylib import lint, schema, seal  # noqa: E402

BENCH_DIR = config.project().bench_dir


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
    extra = {n: str(v) for n, v in (exp.get("extra_axes") or {}).items()}
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
            spec["axes"] = {**{n: k for n, (k, _) in zip(names, combo)}, **extra}
            points.append(spec)
    for p in exp.get("points", []):
        spec = merge(common, p)
        spec["id"] = p["id"]
        spec["axes"] = dict(p.get("axes", {}))
        missing = [n for n in [*axes, *extra] if n not in spec["axes"]]
        if missing:
            fail(f"point '{p['id']}': no value on the axes {missing}")
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


def check_repo_unchanged(repo_root, rev):
    """Stop if the safety repo is not clean at rev any more (a change during the run)."""
    now, dirty = trees.repo_state(repo_root)
    if now != rev or dirty:
        fail(f"the safety repo {repo_root} changed during the run (was {rev[:12]}, now {now[:12]}"
             f"{', dirty' if dirty else ''})")


def tree_hash(repo_root, rev, path):
    """The git tree hash of a folder of the repo at rev."""
    return trees.git("rev-parse", f"{rev}:{path}", cwd=repo_root)


# Files of tests/benchmarks that do not go into an image: the host scripts (extractors), Python,
# Markdown, the documentation of the apps and the board ports (doc/), the twister test files and
# the board list of the host tools (its modules are in the cache key through the tree pins).
# No commit before the doc/ folders had one, so the hash of each older run stays the same.
NOT_FIRMWARE = ("/scripts/", "/doc/", ".py", ".md", "/.gitignore", "/testcase.yaml", "/boards.yaml")
FIRMWARE_HASH = "firmware/1"


def firmware_hash(repo_root, rev):
    """A content hash (40 hex) of the files of tests/benchmarks at rev that can go into an image.

    A change of an extractor or of a document does not change it, so it does not change the
    image (LATBENCH_SRC_REV) or the build cache key.
    """
    out = trees.git("ls-tree", "-r", "--full-tree", rev, "--", str(BENCH_DIR.relative_to(repo_root)), cwd=repo_root)
    lines = []
    for ln in out.splitlines():
        meta, path = ln.split("\t", 1)
        if not any(x in "/" + path if x.startswith("/") else path.endswith(x) for x in NOT_FIRMWARE):
            lines.append(f"{meta} {path}")
    return hashlib.sha1("\n".join(sorted(lines)).encode()).hexdigest()


def bench_hash(repo_root, rev, kind):
    """The bench hash of a run: firmware_hash, or the git tree hash of tests/benchmarks (runs before it)."""
    if kind == FIRMWARE_HASH:
        return firmware_hash(repo_root, rev)
    return tree_hash(repo_root, rev, BENCH_DIR.relative_to(repo_root))


def flash_command(board_cfg, zephyr, pdir, probe):
    """Return one command that runs the flash commands of the board in order."""
    from probatrix.benchmarks.studylib import images
    fields = {"zephyr": str(zephyr), "elf": str(images.find(pdir, ".elf") or pdir / "zephyr.elf"),
              "hex": str(images.find(pdir, ".hex") or pdir / "zephyr.hex"), "probe": probe}
    cmds = [[arg.format(**fields) for arg in cmd] for cmd in board_cfg["flash"]]
    if len(cmds) == 1:
        return cmds[0]
    return ["sh", "-c", " && ".join(shlex.join(c) for c in cmds)]


def export_rev(repo_root, rev, dest):
    """Export the whole repo at rev to dest (git archive exports only the subfolder it runs in)."""
    dest.mkdir(parents=True, exist_ok=True)
    archive = subprocess.Popen(["git", "archive", "--format=tar", rev], cwd=repo_root, stdout=subprocess.PIPE)
    subprocess.run(["tar", "-x", "-C", str(dest)], stdin=archive.stdout, check=True)
    if archive.wait() != 0:
        fail(f"git archive {rev} failed")


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


def build_env(zephyr, sdk):
    """Return the environment of a build: no ZEPHYR_* variable of the caller, the tree and the SDK."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("ZEPHYR_")}
    env.update(
        ZEPHYR_BASE=str(zephyr),
        ZEPHYR_TOOLCHAIN_VARIANT="zephyr",
        ZEPHYR_SDK_INSTALL_DIR=str(sdk),
    )
    return env


# The build of a point: "west build" in the west workspace of the tree (default), or CMake and
# Ninja (LATBENCH_BUILDER=cmake; the runs before 2026-10-28 built so). Both give the same image.
BUILDERS = ("west", "cmake")


def builder_name():
    b = os.environ.get("LATBENCH_BUILDER", "west")
    if b not in BUILDERS:
        fail(f"LATBENCH_BUILDER={b}: use one of {', '.join(BUILDERS)}")
    return b


def builder_id(builder):
    """The builder and its version, for the cache key and the manifest: 'west 1.5.0' or 'cmake'."""
    return f"west {trees.west_version()}" if builder == "west" else "cmake"


def run_build(args, env, bdir, log, name, cwd=None):
    """Run the build command of one point (west build, or CMake then Ninja); the output goes to log.

    A west build runs in cwd, the west workspace of the tree, after a check that west finds that
    workspace; the user and system west configuration do not count.
    """
    with open(log, "w") as f:
        f.write("$ " + shlex.join(args) + "\n")
        f.flush()
        if args[0] == "west":
            trees.west_topdir(cwd)
            extra = trees.west_config_problems(cwd)
            if extra:
                fail(f"{cwd}/.west/config has {', '.join(extra)}: it would change the build of {name}")
            env = {**env, "WEST_CONFIG_GLOBAL": os.devnull, "WEST_CONFIG_SYSTEM": os.devnull}
            env.pop("WEST_CONFIG_LOCAL", None)
            cmds = [[sys.executable, "-m", "west", *args[1:]]]
        else:
            cmds = [args, ["ninja", "-C", str(bdir)]]
        for cmd in cmds:
            r = subprocess.run(cmd, env=env, stdout=f, stderr=subprocess.STDOUT, cwd=cwd)
            if r.returncode != 0:
                fail(f"build failed for {name}, see {log}")


def build_point(tree_cfg, tree, point, src_bench, app, src_rev, board, board_cfg, sdk, bdir, log, build_version=None,
                builder="west"):
    """Build one point. src_bench is tests/benchmarks of a safety repo (or of an export of it).

    The modules are those of the board from the tree, plus the safety repo
    (two folders above src_bench) as the module "safety": ZEPHYR_MODULES is
    explicit also for west build, else Zephyr takes all modules of the
    workspace (hal_nordic in a build for the G474).
    """
    app_dir = src_bench / app
    zephyr = trees.repo_dir(tree_cfg, tree, "zephyr")
    modules = [str(trees.repo_dir(tree_cfg, tree, name)) for name in board_cfg["modules"]]
    modules.append(str(src_bench.parents[1]))
    if builder == "west":
        head = ["west", "build", "--no-sysbuild", "-d", str(bdir), "-b", board, str(app_dir), "--"]
    else:
        head = ["cmake", "-GNinja", "-S", str(app_dir), "-B", str(bdir), f"-DBOARD={board}"]
    args = [
        *head,
        f"-DZEPHYR_MODULES={';'.join(modules)}",
        # Zephyr maps __FILE__ (ASSERT messages) and the paths in zephyr.dts
        # relative to WEST_TOPDIR. Without this, it finds a west workspace
        # around the trees (if there is one), and the image depends on it.
        f"-DWEST_TOPDIR={tree_cfg['root'] / tree}",
    ]
    if point["conf_files"]:
        args.append("-DEXTRA_CONF_FILE=" + ";".join(str(src_bench / f) for f in point["conf_files"]))
    if point["dtc_overlays"]:
        args.append("-DEXTRA_DTC_OVERLAY_FILE=" + ";".join(str(src_bench / f) for f in point["dtc_overlays"]))
    args.append(f"-DLATBENCH_SRC_REV={src_rev}")
    if build_version:
        args.append(f"-DBUILD_VERSION={build_version}")
    for sym, value in point["kconfig"].items():
        args.append(f"-DCONFIG_{sym}={kconfig_value(value)}")

    run_build(args, build_env(zephyr, sdk), bdir, log, f"{tree}/{point['id']}", cwd=tree_cfg["root"] / tree)
    bad = check_config(bdir / "zephyr" / ".config", point["kconfig"])
    if bad:
        fail(f"Kconfig values not applied for {tree}/{point['id']}:\n  " + "\n  ".join(bad))
    return args


class Builder:
    """Builds the points of an experiment, with the build cache of the lab space if there is one."""

    def __init__(self, exp, tree_cfg, repos, board, board_cfg, sdk, repo_root, repo_rev, cache=None, log=print):
        self.exp, self.tree_cfg, self.repos = exp, tree_cfg, repos
        self.board, self.board_cfg, self.sdk = board, board_cfg, sdk
        self.repo_root, self.repo_rev, self.cache, self.log = repo_root, repo_rev, cache, log
        self.bench_tree = firmware_hash(repo_root, repo_rev)
        self.module_tree = tree_hash(repo_root, repo_rev, "zephyr")
        self.build_versions = {}
        self.run_id = None          # <experiment>/<UTC> of the run, once its folder exists
        self.last_log = None        # the log of the newest build (for <UTC>.failed.json)
        self.builder = builder_name()
        self.builder_id = builder_id(self.builder)

    def build_version(self, tree):
        """The BUILD_VERSION of the Zephyr tree: git describe, as Zephyr makes it (it depends on the tags)."""
        if tree not in self.build_versions:
            self.build_versions[tree] = trees.git("describe", "--abbrev=12", "--always",
                                                  cwd=trees.repo_dir(self.tree_cfg, tree, "zephyr"))
        return self.build_versions[tree]

    def paths(self):
        return {"repo": str(self.repo_root), "trees_root": str(self.tree_cfg["root"])}

    def key(self, tree, pt):
        from probatrix.benchmarks.studylib import buildcache
        pins = {r: self.tree_cfg["trees"][tree]["repos"][r]["rev"] for r in self.repos}
        inputs = buildcache.key_inputs(self.board, self.exp["app"], pins,
                                       self.tree_cfg["toolchain"]["zephyr_sdk"]["version"],
                                       self.bench_tree, self.module_tree, pt, self.build_version(tree),
                                       self.builder_id)
        return buildcache.key_of(inputs), inputs

    def use(self, tree, pt, source):
        """The line of uses.jsonl of a cache entry for this run (or for a build without a run)."""
        return {"run": self.run_id, "experiment": self.exp["name"], "point": f"{tree}/{pt['id']}", "from": source,
                "host": platform.node(), "time": datetime.datetime.now(datetime.timezone.utc).isoformat()}

    def build(self, tree, pt, pdir=None):
        """Build one point (or take it from the cache); copy its files to pdir; return the manifest data.

        The images get the names <app>-<tree>-<point>.elf/.hex in pdir (studylib/images.py).
        """
        from probatrix.benchmarks.studylib import images
        check_repo_unchanged(self.repo_root, self.repo_rev)
        name = f"{tree}/{pt['id']}"
        rename = images.names(self.exp["app"], tree, pt["id"])
        key, inputs = self.key(tree, pt) if self.cache else (None, None)
        entry = self.cache.get(key) if self.cache else None
        if entry is not None:
            by = entry.get("built_by")
            self.log(f"[{name}] image from the build cache ({key[:12]}" + (f", built by {by})" if by else ")"))
            if pdir is not None:
                self.cache.copy_to(key, pdir, rename)
            self.cache.note_use(key, self.use(tree, pt, "cache"))
            # the command with the paths of this place (the image does not depend on them)
            here = self.paths()
            moves = {old: here[k] for k, old in (entry.get("paths") or {}).items() if k in here and old != here[k]}
            cmake = [a for a in move_paths(entry["cmake"], moves, None)] if moves else entry["cmake"]
            return {"cmake": cmake, "elf_sha256": entry["elf_sha256"],
                    "build": {"key": key, "from": "cache", **({"built_by": by} if by else {})}}
        self.log(f"[{name}] build", )
        if self.cache:
            bdir = self.cache.work_dir(key)
            log = bdir.parent / f"{key}.log"
        else:
            bdir, log = pdir / "build", pdir / "build.log"
        self.last_log = log
        cmake = build_point(self.tree_cfg, tree, pt, BENCH_DIR, self.exp["app"], self.bench_tree, self.board,
                            self.board_cfg, self.sdk, bdir, log, self.build_version(tree), self.builder)
        # CMake and Ninja read the worktree: a change during the build stops the run before the
        # image goes into the run or the cache.
        check_repo_unchanged(self.repo_root, self.repo_rev)
        elf = bdir / "zephyr" / "zephyr.elf"
        out = {"cmake": cmake, "elf_sha256": hashlib.sha256(elf.read_bytes()).hexdigest()}
        if self.cache:
            by = self.run_id or f"{self.exp['name']} (build only, {datetime.datetime.now(datetime.timezone.utc):%Y%m%dT%H%M%SZ})"
            entry = self.cache.put(key, inputs, bdir, cmake, log, self.paths(), built_by=by)
            shutil.rmtree(bdir)
            log.unlink()
            if pdir is not None:
                self.cache.copy_to(key, pdir, rename)
            mine = entry.get("built_by") == by
            # another process may have stored the key in the meantime: its entry stays, and the run
            # gets its image (and its ELF digest)
            self.cache.note_use(key, self.use(tree, pt, "build" if mine else "cache"))
            out["elf_sha256"] = entry["elf_sha256"]
            out["build"] = {"key": key, "from": "build" if mine else "cache",
                            **({} if mine else {"built_by": entry.get("built_by")})}
        elif pdir is not None:
            for f in (elf, bdir / "zephyr" / "zephyr.hex", bdir / "zephyr" / ".config", bdir / "zephyr" / "zephyr.dts"):
                if f.exists():
                    shutil.copy2(f, pdir / rename.get(f.name, f.name))
        return out


def cache_state(exp_path, lab):
    """(points, points with an image in the build cache of the lab space) of an experiment."""
    from probatrix.benchmarks.studylib import buildcache
    exp = yaml.safe_load(Path(exp_path).read_text())
    tree_cfg = trees.load(lab=lab)
    boards = trees.load_boards()
    board = exp.get("board", boards["default"])
    repos = trees.board_repos(boards, board)
    repo_root, repo_rev, _ = safety_repo_state()
    cache = buildcache.Cache(lab.build_cache)
    b = Builder(exp, tree_cfg, repos, board, boards["boards"][board], None, repo_root, repo_rev, cache)
    keys = [b.key(t, pt)[0] for t in exp["trees"] for pt in expand_points(exp)]
    return len(keys), sum(cache.get(k) is not None for k in keys)


def find_points(path, only=None):
    """Return (run folder, manifest, entries) for a run folder or a point folder <run>/<tree>/<point>."""
    path = Path(path).resolve()
    if (path / "manifest.json").is_file():
        run_dir, want = path, None
    elif len(path.parents) > 1 and (path.parents[1] / "manifest.json").is_file():
        run_dir, want = path.parents[1], (path.parent.name, path.name)
    else:
        fail(f"{path} is not a run folder or a point folder of a run")
    manifest = json.loads((run_dir / "manifest.json").read_text())
    entries = [
        e for e in manifest["points"]
        if (want is None or (e["tree"], e["id"]) == want) and (not only or e["id"] in only)
    ]
    if not entries:
        fail(f"no points to rebuild in {path}")
    return run_dir, manifest, entries


def build_dir_flag(cmd):
    """The option before the build folder: -d (west build) or -B (CMake)."""
    return "-d" if cmd[0] == "west" else "-B"


def move_paths(cmake, moves, bdir):
    """Return the CMake command of a point with the build folder bdir (None: keep it) and each old
    folder of moves replaced."""
    out = []
    for i, arg in enumerate(cmake):
        if i > 0 and cmake[i - 1] == build_dir_flag(cmake) and bdir is not None:
            out.append(str(bdir))
            continue
        for old, new in moves.items():
            arg = new if arg == old else arg.replace(old + "/", new + "/")
        out.append(arg)
    return out


def cmake_cache_value(bdir, key):
    """Return the value of key in the CMakeCache.txt of a build, or None."""
    cache = bdir / "CMakeCache.txt"
    if cache.exists():
        for line in cache.read_text().splitlines():
            if line.startswith(key + ":"):
                return line.partition("=")[2]
    return None


def elf_image(elf, objcopy, tmp):
    """Return the loadable sections of an ELF as Intel HEX: the flashed image, without debug information."""
    out = tmp / "image.hex"
    subprocess.run([objcopy, "-O", "ihex", str(elf), str(out)], check=True)
    image = out.read_bytes()
    out.unlink()
    return image


def without_comments(name, data):
    """Return .config or zephyr.dts text without comments; they have the paths of the host."""
    text = data.decode()
    if name == ".config":
        return [ln for ln in text.splitlines() if not ln.startswith("#") or ln.endswith(" is not set")]
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return [ln.rstrip() for ln in text.splitlines() if ln.strip()]


def compare_point(pdir, bdir, elf_sha256, objcopy=None, tmp=None):
    """Return (same, different) file names of the stored files of a point and a new build.

    If the ELF hashes differ (the debug information has the build folder) and
    objcopy is given, "ELF image" compares the loadable sections of the two ELFs.
    .config and zephyr.dts are compared without their comments (paths of the host).
    """
    from probatrix.benchmarks.studylib import images
    same, diff = [], []
    elf = bdir / "zephyr" / "zephyr.elf"
    old_elf = images.find(pdir, ".elf")
    sha = hashlib.sha256(elf.read_bytes()).hexdigest() if elf.exists() else None
    (same if sha == elf_sha256 else diff).append("zephyr.elf")
    if sha and sha != elf_sha256 and objcopy and old_elf is not None:
        old = elf_image(old_elf, objcopy, tmp)
        (same if old == elf_image(elf, objcopy, tmp) else diff).append("ELF image")
    # the names in same/different are those of the build (the run may have <app>-<tree>-<point>.hex)
    for name in ("zephyr.hex", ".config", "zephyr.dts"):
        old = images.find(pdir, ".hex") if name == "zephyr.hex" else pdir / name
        new = bdir / "zephyr" / name
        if old is not None and old.exists():
            if not new.exists():
                ok = False
            elif name == "zephyr.hex":
                ok = new.read_bytes() == old.read_bytes()
            else:
                ok = without_comments(name, new.read_bytes()) == without_comments(name, old.read_bytes())
            (same if ok else diff).append(name)
    return same, diff


def west_topdir(path):
    """Return the west workspace folder (with .west) that contains path, or None."""
    for d in Path(path).parents:
        if (d / ".west").is_dir():
            return d
    return None


NO_WEST_TOPDIR = "/latbench-no-west-topdir"


def old_west_topdir(cmake, old_root, root):
    """Return [-DWEST_TOPDIR=...] for a build of a run before run.py set WEST_TOPDIR.

    Such a build took WEST_TOPDIR from a west workspace around the trees (if
    there was one), and an image with ASSERT has __FILE__ relative to it. The
    same folder above the new trees root gives the same strings.
    """
    if any(a.startswith("-DWEST_TOPDIR=") for a in cmake):
        return []
    top = west_topdir(old_root)
    if top is None:
        # The old build found no workspace (no prefix map). The trees are west workspaces now, so
        # Zephyr would find one and map __FILE__: a folder that does not exist keeps the old strings.
        return [f"-DWEST_TOPDIR={NO_WEST_TOPDIR}"]
    rel = Path(old_root).relative_to(top)
    if Path(root).parts[-len(rel.parts):] != rel.parts:
        print(f"warning: the old trees root {old_root} was in the west workspace {top}; the trees root {root}"
              f" does not end with {rel}, so ASSERT strings can be different", flush=True)
        return []
    return [f"-DWEST_TOPDIR={Path(*Path(root).parts[:-len(rel.parts)])}"]


def rebuild(args):
    """Build the points of an old run again, from its sources and manifest, and compare the images.

    The sources: an export of the commit of the run (safety.rev), or the src/
    snapshot of an old run, or a worktree of the commit of an older run.

    The flashed image (zephyr.hex, or zephyr.elf if the run has no hex) and
    the .config must be the same. The ELF has the build folder in its debug
    information, so the build goes to the original build folder if it is free.
    """
    run_dir, manifest, entries = find_points(args.rebuild, args.only)
    first = entries[0]
    old_bdir = Path(first["cmake"][first["cmake"].index(build_dir_flag(first["cmake"])) + 1])
    # a build in the run folder (<run>/<tree>/<point>/build), or in the build cache
    in_run = old_bdir.parts[-3:] == (first["tree"], first["id"], "build")
    old_run = old_bdir.parents[2] if in_run else None
    moves = {str(old_run): str(run_dir)} if in_run else {}
    # On another host the paths of the manifest do not exist: use the trees
    # root and the SDK path of this host. The revisions and the SDK version
    # stay those of the manifest.
    sdk_path = Path(manifest["toolchain"]["path"])
    if not sdk_path.is_dir():
        sdk_path = trees.load()["toolchain"]["zephyr_sdk"]["path"]
    root = Path(args.trees_root or os.environ.get("LATBENCH_TREES_ROOT") or manifest["trees_root"]).expanduser()
    if not root.is_dir():
        root = trees.load()["root"]
        if root is None:
            fail(f"the trees root {manifest['trees_root']} of the run does not exist here; work in a lab space "
                 "or give --trees-root")
    cfg = {
        "root": root,
        "trees": manifest["trees"],
        "toolchain": {"zephyr_sdk": {"path": str(sdk_path),
                                     "version": manifest["toolchain"]["zephyr_sdk"]}},
    }
    if Path(manifest["trees_root"]) != cfg["root"]:
        moves[manifest["trees_root"]] = str(cfg["root"])
    try:
        sdk = trees.check_toolchain(cfg)
        for t in sorted({e["tree"] for e in entries}):
            trees.check_tree(cfg, t)
    except trees.TreeError as e:
        fail(str(e))

    import tempfile

    # The logs and the builds that cannot go to the original folder. Kept if a point fails.
    tmp = Path(tempfile.mkdtemp(prefix="latbench-rebuild-"))
    safety = manifest["safety"]
    if "bench_tree" in safety:
        # A run that built from the safety repo: export its commit (the repo is at another rev now).
        repo_root, _, _ = safety_repo_state()
        if trees.git("cat-file", "-t", safety["rev"], cwd=repo_root, check=False) != "commit":
            fail(f"the safety revision {safety['rev']} of the run is not in {repo_root} (fetch it from the lab "
                 f"repo of the run: ref {safety.get('ref', 'refs/latbench/run/...')})")
        src = tmp / "src"
        export_rev(repo_root, safety["rev"], src)
        if bench_hash(repo_root, safety["rev"], safety.get("bench_tree_kind")) != safety["bench_tree"]:
            fail(f"the safety revision {safety['rev']} does not have the bench tree {safety['bench_tree']}")
        moves[safety["path"]] = str(src)
    elif "snapshot" not in safety:
        # An old run that built from the worktree. Its build took the revision
        # string from "git describe" and had no -DLATBENCH_SRC_REV, so an export
        # without .git gives another image: use a temporary worktree instead.
        safety = manifest["safety"]
        repo_root, _, _ = safety_repo_state()
        if trees.git("cat-file", "-t", safety["rev"], cwd=repo_root, check=False) != "commit":
            fail(f"the run has no snapshot, and the safety revision {safety['rev']} is not in {repo_root}")
        src = tmp / "src"
        trees.git("worktree", "add", "--detach", str(src), safety["rev"], cwd=repo_root)
        atexit.register(trees.git, "worktree", "remove", "--force", str(src), cwd=repo_root, check=False)
        moves[safety["path"]] = str(src)
    print(f"rebuild {run_dir}  {len(entries)} points")
    started = datetime.datetime.now(datetime.timezone.utc)
    repo_root, repo_rev, repo_dirty = safety_repo_state()
    record = {"format": "latbench-rebuild/1", "run": run_dir.name, "experiment": manifest["experiment"],
              "run_digest": seal.digest(run_dir) if seal.seal_path(run_dir).is_file() else None,
              "host": platform.node(), "started": started.isoformat(),
              "tool": {"safety_rev": repo_rev, "dirty": bool(repo_dirty)},
              "trees_root": str(cfg["root"]), "zephyr_sdk": str(sdk), "points": []}
    failed = 0
    for e in entries:
        name = f"{e['tree']}/{e['id']}"
        pdir = run_dir / e["tree"] / e["id"]
        # never in the sealed run folder: a crash or --keep-build would leave files in it
        bdir = tmp / e["tree"] / e["id"]
        bdir.mkdir(parents=True)
        bad = True
        try:
            cmake = move_paths(e["cmake"], moves, bdir) + old_west_topdir(e["cmake"], manifest["trees_root"], root)
            run_build(cmake, build_env(trees.repo_dir(cfg, e["tree"], "zephyr"), sdk), bdir,
                      tmp / f"{e['tree']}-{e['id']}.log", name, cwd=cfg["root"] / e["tree"])
            same, diff = compare_point(pdir, bdir, e["elf_sha256"], cmake_cache_value(bdir, "CMAKE_OBJCOPY"), tmp)
            from probatrix.benchmarks.studylib import images
            if images.find(pdir, ".hex") is not None:
                image_same = "zephyr.hex" in same
            else:
                image_same = "zephyr.elf" in same or "ELF image" in same
            bad = not image_same or ".config" in diff
        finally:
            # The builds stay in tmp (kept if a point fails or with --keep-build).
            if bdir.exists() and not args.keep_build and not bad:
                shutil.rmtree(bdir)
        failed += bad
        record["points"].append({"tree": e["tree"], "point": e["id"], "verdict": "different" if bad else "same",
                                 "same": same, "different": diff})
        print(f"[{name}] {'DIFFERENT' if bad else 'same'}: same {', '.join(same) or '-'}"
              + (f"; different {', '.join(diff)}" if diff else ""), flush=True)
    print(f"{len(entries) - failed} of {len(entries)} points give the same image and .config")
    record["finished"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    record["summary"] = f"{len(entries) - failed} of {len(entries)} points give the same image and .config"
    rec = run_dir.parent / f"{run_dir.name}.rebuild-{started.strftime('%Y%m%dT%H%M%SZ')}.json"
    rec.write_text(json.dumps(record, indent=2) + "\n")
    print(f"record: {rec}")
    if failed or args.keep_build:
        print(f"logs and builds in {tmp}")
    else:
        shutil.rmtree(tmp)
    if failed:
        sys.exit(1)


def select_hardware(args, board, zephyr):
    """Return the probe and console of the board: from the hardware map, or from --probe and --port."""
    if args.port and args.probe:
        return {"platform": [board], "probe": args.probe, "id": args.probe, "product": None, "runner": None,
                "serial": args.port, "baud": 115200, "fixtures": [], "notes": "from --probe and --port"}
    try:
        schema = zephyr / hwmap.SCHEMA
        entries = hwmap.load(args.hardware_map, schema if schema.is_file() else None)
        hw = hwmap.hardware(hwmap.select(entries, board, args.probe, args.hardware_map))
    except hwmap.HwMapError as e:
        fail(str(e))
    hw["map"] = str(Path(args.hardware_map).resolve())
    if args.port:
        hw["serial"] = args.port
    return hw


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("experiment", nargs="?")
    p.add_argument("--out")
    p.add_argument("--rebuild", metavar="RUN",
                   help="build the points of a run folder (or of one <run>/<tree>/<point> folder) again"
                        " and compare them with the stored images; does not flash")
    p.add_argument("--trees-root")
    p.add_argument("--hardware-map",
                   help="hardware map of the host (default: [hardware] map of the lab space, else "
                        f"{hwmap.DEFAULT.relative_to(config.project().repo)})")
    p.add_argument("--probe", help="probe id: select the entry of the hardware map; with --port, no map is necessary")
    p.add_argument("--port", help="serial port of the console (default: serial of the entry in the hardware map)")
    p.add_argument("--only", nargs="*", help="run only these point ids")
    p.add_argument("--dry-run", action="store_true", help="check and list the points, do not build")
    p.add_argument("--build-only", action="store_true", help="build each point in a temporary folder, do not flash")
    p.add_argument("--keep-build", action="store_true")
    p.add_argument("--no-cache", action="store_true", help="do not use the build cache of the lab space")
    p.add_argument("--role", choices=["evidence", "adjustment", "excluded"],
                   help="the role of the run in the run list of the instance (default evidence; "
                        "with --only it must be given)")
    p.add_argument("--reason", help="the reason of a role other than evidence")
    p.add_argument("--campaign", help="the id of the campaign that starts the run (in the run-list entry)")
    p.add_argument("--warn-as-error", action="store_true",
                   help="stop if the design lint finds a problem in the experiment or its study")
    args = p.parse_args()
    if not args.hardware_map:
        lab = labmod.find()
        args.hardware_map = str(lab.hw_map if lab else hwmap.DEFAULT)
    if args.rebuild:
        if args.experiment or args.out:
            p.error("--rebuild takes no experiment and no --out")
        rebuild(args)
        return
    if not args.experiment or not (args.out or args.build_only or args.dry_run):
        p.error("an experiment and --out are necessary (no --out with --build-only or --dry-run)")

    exp_path = Path(args.experiment).resolve()
    exp_text = exp_path.read_text()
    exp = yaml.safe_load(exp_text)
    try:
        schema.check("experiment", exp, exp_path)
    except schema.SchemaError as e:
        fail(str(e))

    # 1. Provenance checks, before anything is built.
    repo_root, repo_rev, repo_dirty = safety_repo_state()
    if repo_dirty:
        fail(f"safety repo {repo_root} is dirty, commit first:\n{repo_dirty}")
    if not exp_path.is_relative_to(repo_root):
        fail(f"{exp_path} is not in the safety repo {repo_root}")
    lab = labmod.find()
    if lab and lab.repo.resolve() != repo_root.resolve():
        fail(f"this is run.py of {repo_root}; the lab space {lab.folder} uses the design repo {lab.repo}")
    problems = lint.lint_for_experiment(exp_path)
    for pr in problems:
        print(f"lint {pr}", flush=True)
    if problems and args.warn_as_error:
        fail(f"{len(problems)} lint problems (--warn-as-error)")

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
    if not (BENCH_DIR / exp["app"]).is_dir():
        fail(f"no app folder {exp['app']}")
    points = expand_points(exp)
    if args.only:
        points = [pt for pt in points if pt["id"] in args.only]
    if not points:
        fail("no points to run")
    # the run list of an instance: check the role and the target now, not after hours of capture
    if args.out and (Path(args.out) / "instance.json").is_file() and not args.build_only:
        from probatrix.benchmarks.studylib import instance as instmod
        from probatrix.benchmarks.studylib.design import Design
        if args.only and args.role is None:
            fail("a run of some points (--only) into an instance needs --role (adjustment or excluded with "
                 "--reason, or evidence)")
        args.role = args.role or "evidence"
        try:
            instmod.check_role(args.role, args.reason)
            instmod.check_target(Design(), args.out, exp["name"], board)
        except instmod.InstanceError as e:
            fail(str(e))
    args.role = args.role or "evidence"

    print(f"safety {repo_rev[:12]}  trees {', '.join(exp['trees'])}  {len(points)} points x {exp.get('repeat', 1)}")
    for pt in points:
        print(f"  {pt['id']}: {pt['kconfig']} {pt['conf_files']} {pt['dtc_overlays']}")
    if args.dry_run:
        return
    if not args.build_only:
        if lab and not args.campaign:
            # a run by hand takes the board lock (a campaign holds it already and gives it to run.py)
            from probatrix.benchmarks.studylib import campaign as campmod
            try:
                campmod.take_lock(lab, f"run.py-{os.getpid()}", [board])
            except campmod.CampaignError as e:
                fail(str(e))
        hw = select_hardware(args, board, trees.repo_dir(tree_cfg, exp["trees"][0], "zephyr"))
        port = hw["serial"]
        print(f"board {board}: probe {hw['probe']} ({hw['product']}), console {port}")
    from probatrix.benchmarks.studylib import buildcache
    cache = buildcache.Cache(lab.build_cache) if lab and not args.no_cache else None
    builder = Builder(exp, tree_cfg, repos, board, board_cfg, sdk, repo_root, repo_rev, cache,
                      log=lambda m: print(m, flush=True))
    if args.build_only:
        import tempfile

        # Outside a lab space: a temporary folder (with --keep-build it stays, for example to
        # compare the images of two trees).
        tmp = None if cache else Path(tempfile.mkdtemp(prefix="latbench-build-"))
        built = cached = 0
        for tree in exp["trees"]:
            for pt in points:
                pdir = None
                if tmp is not None:
                    pdir = tmp / tree / pt["id"]
                    pdir.mkdir(parents=True)
                r = builder.build(tree, pt, pdir)
                cached += r.get("build", {}).get("from") == "cache"
                built += 1
        print(f"all {built} points build ({cached} from the build cache)")
        if tmp is not None:
            if args.keep_build:
                print(f"builds in {tmp}")
            else:
                shutil.rmtree(tmp)
        return

    # 2. Output folder and manifest.
    started = datetime.datetime.now(datetime.timezone.utc)
    out = Path(args.out).resolve()
    exp_folder = trees.EXPERIMENT_PREFIX + exp["name"] if (out / "instance.json").is_file() else exp["name"]
    run_dir = out / exp_folder / started.strftime("%Y%m%dT%H%M%SZ")
    run_dir.mkdir(parents=True)
    print(f"run folder {run_dir}", flush=True)       # the campaign reads this line
    builder.run_id = f"{exp['name']}/{run_dir.name}"
    # The commit of the run stays reachable (a rebuild exports it), also after a rebase: a local
    # ref, never pushed (a campaign adds refs/latbench/campaign/<id>).
    run_ref = config.project().ref("run", exp["name"], run_dir.name)
    trees.git("update-ref", run_ref, repo_rev, cwd=repo_root)
    probe = subprocess.run(
        ["udevadm", "info", "--query=property", port], capture_output=True, text=True
    ).stdout
    probe_serial = next((ln.split("=", 1)[1] for ln in probe.splitlines() if ln.startswith("ID_SERIAL_SHORT=")), None)

    import serial

    manifest = {
        "experiment": exp["name"],
        "experiment_file": str(exp_path.relative_to(repo_root)),
        "experiment_yaml": exp_text,
        "experiment_sha256": hashlib.sha256(exp_text.encode()).hexdigest(),
        "command": shlex.join(sys.argv),
        "started": started.isoformat(),
        "host": platform.node(),
        "lab": lab.describe() if lab else None,
        "safety": {"path": str(repo_root), "rev": repo_rev, "ref": run_ref, "bench_tree": builder.bench_tree,
                   "bench_tree_kind": FIRMWARE_HASH,
                   "module_tree": builder.module_tree},
        "trees": {
            t: {**tree_cfg["trees"][t], "repos": {r: tree_cfg["trees"][t]["repos"][r] for r in repos}}
            for t in exp["trees"]
        },
        "trees_root": str(tree_cfg["root"]),
        "toolchain": {"zephyr_sdk": str(tree_cfg["toolchain"]["zephyr_sdk"]["version"]), "path": str(sdk)},
        "tools": {
            "cmake": tool_version(["cmake", "--version"]),
            "builder": builder.builder_id,
            # the cmake builder runs the Zephyr scripts with the Python of PATH (west build: its own)
            **({"cmake_python": shutil.which("python3")} if builder.builder == "cmake" else {}),
            "ninja": tool_version(["ninja", "--version"]),
            # The tools that flash this board (first word of each flash command).
            **{cmd[0]: tool_version([cmd[0], "--version"]) for cmd in board_cfg["flash"]},
            "python": sys.version.split()[0],
            "pyserial": serial.__version__,
            "python_packages": labmod.packages(repo_root),
        },
        "board": board,
        "board_cfg": board_cfg,
        "hardware": hw,
        "console": port,
        "probe_serial": probe_serial,
        "points": [],
    }
    manifest_file = run_dir / "manifest.json"

    def save_manifest():
        manifest_file.write_text(json.dumps(manifest, indent=2) + "\n")

    save_manifest()

    # 3. Build, flash and capture each point; 4. summary, seal and run list. A stop before the
    # seal leaves <UTC>.failed.json (the step, the error, the end of the last log).
    state = {"step": "start", "log": None}

    def on_term(signum, frame):
        raise SystemExit(f"error: stopped by signal {signum}")

    signal.signal(signal.SIGTERM, on_term)
    try:
        capture(exp, points, tree_cfg, builder, board_cfg, hw, port, run_dir, manifest, save_manifest, args, state)
    except BaseException as x:
        if not seal.seal_path(run_dir).exists():
            write_failed(run_dir, exp, state, x)
        raise
    digest = seal.write(run_dir)
    print(f"results in {run_dir}  ({digest})")
    if (out / "instance.json").is_file():
        from probatrix.benchmarks.studylib import instance
        from probatrix.benchmarks.studylib.design import Design
        try:
            rid = instance.add(Design(), out, run_dir, role=args.role, reason=args.reason, campaign=args.campaign)
        except instance.InstanceError as e:
            fail(f"the run is sealed, but not in the run list of {out}: {e}")
        print(f"run {rid} added to the instance {out}")


def write_failed(run_dir, exp, state, x):
    """<UTC>.failed.json beside a run folder that has no seal."""
    if isinstance(x, SystemExit):
        error = str(x.code).removeprefix("error: ") if x.code not in (None, 0) else "exit"
    elif isinstance(x, KeyboardInterrupt):
        error = "interrupt"
    else:
        error = f"{type(x).__name__}: {x}"
    if state.get("log") is None and state.get("builder") is not None:
        state["log"] = state["builder"].last_log          # a build failure: the build log
    tail = []
    if state.get("log") and Path(state["log"]).is_file():
        tail = Path(state["log"]).read_text(errors="replace").splitlines()[-20:]
    rec = {"format": "latbench-failed/1", "run": f"{exp['name']}/{run_dir.name}", "step": state["step"],
           "error": error, "time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
           "host": platform.node(),
           "log": state.get("log") and (str(Path(state["log"]).relative_to(run_dir))
                                        if Path(state["log"]).is_relative_to(run_dir) else str(state["log"])),
           "log_tail": tail}
    f = run_dir.parent / f"{run_dir.name}.failed.json"
    f.write_text(json.dumps(rec, indent=2) + "\n")
    print(f"the run failed ({error}); record {f}", file=sys.stderr)


def capture(exp, points, tree_cfg, builder, board_cfg, hw, port, run_dir, manifest, save_manifest, args, state):
    logs = []
    axes = {}
    for tree in exp["trees"]:
        zephyr = trees.repo_dir(tree_cfg, tree, "zephyr")
        for pt in points:
            pdir = run_dir / tree / pt["id"]
            bdir = pdir / "build"
            pdir.mkdir(parents=True)
            state.update(step=f"build {tree}/{pt['id']}", log=None, builder=builder)
            built = builder.build(tree, pt, pdir)
            entry = {
                "tree": tree,
                "id": pt["id"],
                "axes": pt["axes"],
                "kconfig": pt["kconfig"],
                "conf_files": pt["conf_files"],
                "dtc_overlays": pt["dtc_overlays"],
                "cmake": built["cmake"],
                "elf_sha256": built["elf_sha256"],
                **({"build": built["build"]} if "build" in built else {}),
                "logs": [],
            }
            manifest["points"].append(entry)
            flash_cmd = flash_command(board_cfg, zephyr, pdir, hw["probe"])
            for rep in range(1, exp.get("repeat", 1) + 1):
                log = pdir / f"rep{rep}.log"
                state.update(step=f"flash and capture {tree}/{pt['id']} rep {rep}", log=str(log))
                print(f"[{tree}/{pt['id']}] rep {rep}", flush=True)
                try:
                    latbench.run_capture(log, flash_cmd, port, baud=hw["baud"], timeout=exp.get("timeout", 600))
                except latbench.CaptureError as e:
                    entry["error"] = str(e)
                    save_manifest()
                    fail(f"{tree}/{pt['id']} rep {rep}: {e}")
                entry["logs"].append(str(log.relative_to(run_dir)))
                logs.append(log)
                axes[str(log)] = pt["axes"]
                save_manifest()
            if bdir.exists() and not args.keep_build:
                shutil.rmtree(bdir)

    manifest["finished"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    save_manifest()

    state["step"] = "summary"
    with open(run_dir / "summary.txt", "w") as f:
        sys.stdout = f
        try:
            latbench.summary(argparse.Namespace(logs=[str(x) for x in logs], json=False, axes=axes))
        finally:
            sys.stdout = sys.__stdout__
    print((run_dir / "summary.txt").read_text())
    reused = [f"{p['tree']}/{p['id']}" for p in manifest["points"] if p.get("build", {}).get("from") == "cache"]
    print(f"images: {len(reused)} of {len(manifest['points'])} from the build cache", flush=True)
    state["step"] = "seal"


if __name__ == "__main__":
    main()
