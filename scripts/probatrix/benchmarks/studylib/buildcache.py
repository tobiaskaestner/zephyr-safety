# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The build cache of a lab space (.lab/build-cache/<key[:2]>/<key>/).

An entry holds the files of one built point: zephyr.elf, zephyr.hex,
.config, zephyr.dts, build.log and entry.json (the key inputs, the CMake
command, the ELF digest, built_by: the run or the step that built it), and
uses.jsonl: one line for each run that took the image (also the run that
built it). A run gives the images their names when it copies them into its
point folder (studylib/images.py). The key is the sha256 of everything
that goes into the image:

    the board, the app, the revs of the tree repos that the board needs,
    the BUILD_VERSION string of the Zephyr tree (git describe: it depends
    on the tags, not only on the rev), the builder ("west <version>" or
    "cmake"), the SDK version, the content hash of the firmware files of
    tests/benchmarks (firmware/1) and the git tree hash of the module
    folder zephyr/ of the safety repo, and the point (Kconfig values, conf
    files, overlays).

It has no host path, no experiment name and no safety commit: the same
content at another commit (a change of the design only) or a repeat of
the experiment gives the same key. This is correct because the build of
a point does not depend on the host paths (the cross-host rebuilds give
the same image) and the app gets the firmware hash as LATBENCH_SRC_REV,
not the commit.
"""

import hashlib
import json
import os
import shutil
from pathlib import Path

FILES = ("zephyr.elf", "zephyr.hex", ".config", "zephyr.dts")
FORMAT = "latbench-build/1"


def key_inputs(board, app, tree_repos, sdk_version, bench_tree, module_tree, point, build_version, builder="cmake"):
    return {"format": FORMAT, "board": board, "app": app, "repos": dict(sorted(tree_repos.items())),
            "build_version": build_version, "builder": builder,
            "sdk": str(sdk_version), "bench_tree": bench_tree, "module_tree": module_tree,
            "kconfig": {k: str(v) for k, v in sorted(point["kconfig"].items())},
            "conf_files": list(point["conf_files"]), "dtc_overlays": list(point["dtc_overlays"])}


def key_of(inputs):
    return hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()


class Cache:
    def __init__(self, folder):
        self.folder = Path(folder)

    def entry_dir(self, key):
        return self.folder / key[:2] / key

    def get(self, key):
        """The entry.json of a complete entry, or None."""
        d = self.entry_dir(key)
        f = d / "entry.json"
        if not f.is_file():
            return None
        entry = json.loads(f.read_text())
        if not (d / "zephyr.elf").is_file() or not (d / ".config").is_file():
            return None
        if hashlib.sha256((d / "zephyr.elf").read_bytes()).hexdigest() != entry.get("elf_sha256"):
            return None
        return entry

    def work_dir(self, key):
        """A fresh build folder for the key and this process (the CMake build folder of the point)."""
        d = self.folder / "work" / f"{key}.{os.getpid()}"
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
        return d

    def put(self, key, inputs, bdir, cmake, log, paths=None, built_by=None):
        """Store the files of a build; return the entry. The entry appears at once (rename).

        If another process stored the key in the meantime, its entry stays (the same inputs give
        the same image) and this build is dropped. paths: the host paths in the CMake command
        (repo, trees root), so that a hit in another place can name its own paths.
        """
        tmp = self.folder / "tmp" / f"{key}.{os.getpid()}"
        if tmp.exists():
            shutil.rmtree(tmp)
        tmp.mkdir(parents=True)
        for name in FILES:
            src = Path(bdir) / "zephyr" / name
            if src.exists():
                shutil.copy2(src, tmp / name)
        shutil.copy2(log, tmp / "build.log")
        entry = {"key": key, "inputs": inputs, "cmake": cmake, "paths": paths or {}, "built_by": built_by,
                 "elf_sha256": hashlib.sha256((tmp / "zephyr.elf").read_bytes()).hexdigest()}
        (tmp / "entry.json").write_text(json.dumps(entry, indent=2) + "\n")
        final = self.entry_dir(key)
        final.parent.mkdir(parents=True, exist_ok=True)
        # one put of a key at a time: else a second process could take a complete entry that
        # came in after its get() for a broken one and move it away
        import fcntl
        with open(final.parent / f"{key}.lock", "a") as lk:
            fcntl.flock(lk, fcntl.LOCK_EX)
            have = self.get(key)
            if have is not None:
                shutil.rmtree(tmp)
                return have
            if final.exists():
                # an incomplete entry (a crash during an old put): move it away first
                final.rename(final.with_name(f"{key}.broken.{os.getpid()}"))
            tmp.rename(final)
        return entry

    def copy_to(self, key, pdir, rename=None):
        """Copy the files of an entry into a point folder of a run; rename: {entry name: name there}."""
        d = self.entry_dir(key)
        rename = rename or {}
        for name in (*FILES, "build.log"):
            if (d / name).exists():
                shutil.copy2(d / name, Path(pdir) / rename.get(name, name))

    def note_use(self, key, use):
        """Add one line to uses.jsonl of an entry: a run that took the image."""
        with open(self.entry_dir(key) / "uses.jsonl", "a") as f:
            f.write(json.dumps(use, sort_keys=True) + "\n")

    def uses(self, key):
        f = self.entry_dir(key) / "uses.jsonl"
        return [json.loads(ln) for ln in f.read_text().splitlines() if ln.strip()] if f.is_file() else []
