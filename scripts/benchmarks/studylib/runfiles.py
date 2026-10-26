# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The derived files of a raw run, beside its folder <UTC>/:

    <UTC>.run.json      framework data (format latbench-run/2): the run
                        identity and provenance, and for each point its
                        axes, the digests of its files and of its image,
                        and its logs. No app data and no Kconfig copy.
    <UTC>.<app>.json    app data (format latbench-app-<app>/1), from
                        tests/benchmarks/<app>/scripts/extract.py
"""

import hashlib
import json
import struct
import subprocess
import sys
from pathlib import Path

import yaml

import run as runpy
import trees

from . import seal
from .design import repo_rel

POINT_FILES = (".config", "zephyr.dts", "zephyr.elf", "zephyr.hex", "build.log")


def image_sha256(elf, mask=None):
    """sha256 over (paddr, filesz, bytes) of the PT_LOAD segments of an ELF32, sorted by paddr.

    This is the image that the probe writes: it does not change with the
    debug information or the build folder. It has the bench_rev string of
    the app (LATBENCH_SRC_REV), so the same code at two safety revisions
    gives two digests; with mask (the bench_rev bytes) these bytes count as
    zeros (code_sha256).
    """
    data = Path(elf).read_bytes()
    if data[:4] != b"\x7fELF" or data[4] != 1 or data[5] != 1:
        raise ValueError(f"{elf}: not a little-endian ELF32")
    phoff, = struct.unpack_from("<I", data, 0x1C)
    phentsize, phnum = struct.unpack_from("<HH", data, 0x2A)
    segs = []
    for i in range(phnum):
        p_type, p_offset, _vaddr, p_paddr, p_filesz = struct.unpack_from("<IIIII", data, phoff + i * phentsize)
        if p_type == 1 and p_filesz > 0:
            segs.append((p_paddr, p_filesz, p_offset))
    h = hashlib.sha256()
    for paddr, filesz, offset in sorted(segs):
        seg = data[offset:offset + filesz]
        if mask:
            seg = seg.replace(mask, b"0" * len(mask))
        h.update(struct.pack("<II", paddr, filesz))
        h.update(seg)
    return h.hexdigest()


def code_sha256(elf, bench_rev):
    """image_sha256 with the bench_rev string set to zeros: the same code at two revisions gives one digest."""
    return image_sha256(elf, bench_rev.encode()) if bench_rev else None


def design_axes(experiment_file):
    """{point id: axes} of the current design of an experiment, or {} if there is no design file."""
    if experiment_file is None or not Path(experiment_file).is_file():
        return {}
    try:
        return {p["id"]: p["axes"] for p in runpy.expand_points(yaml.safe_load(Path(experiment_file).read_text()))}
    except SystemExit:
        return {}


def bench_rev(entry):
    """The LATBENCH_SRC_REV of the build of a point (from its CMake command), or None."""
    for a in entry.get("cmake", []):
        if a.startswith("-DLATBENCH_SRC_REV="):
            return a.split("=", 1)[1]
    return None


def run_json(run_dir, run_id, digest, made_by, experiment_file=None):
    run_dir = Path(run_dir)
    m = json.loads((run_dir / "manifest.json").read_text())
    files = seal.files(run_dir)
    daxes = design_axes(experiment_file)
    points, sources = [], set()
    for e in m["points"]:
        rel = f"{e['tree']}/{e['id']}"
        manifest_axes = e.get("axes") or {}
        design = daxes.get(e["id"], {})
        if any(design.get(a, v) != v for a, v in manifest_axes.items()):
            design = {}  # the design gives other values: it is not the design of this run
        axes = {**design, **manifest_axes}
        if manifest_axes and set(axes) == set(manifest_axes):
            src = "manifest"
        elif design:
            src = "design"
        else:
            src = "none"
        sources.add(src)
        elf = run_dir / rel / "zephyr.elf"
        points.append({
            "tree": e["tree"], "point": e["id"], "axes": axes,
            "files": {n: files[f"{rel}/{n}"] for n in POINT_FILES if f"{rel}/{n}" in files},
            "image_sha256": image_sha256(elf) if elf.is_file() else None,
            "code_sha256": code_sha256(elf, bench_rev(e)) if elf.is_file() else None,
            "reps": [{"rep": i, "log": log, "log_sha256": files.get(log)} for i, log in enumerate(e["logs"], 1)],
        })
    note = {"manifest": "manifest"}.get("/".join(sorted(sources)))
    if note is None:
        note = ", ".join(sorted(sources))
        if "design" in sources:
            note += (f" (the run did not record all axes; the others come from the design "
                     f"{repo_rel(experiment_file)}, which expands to the same point ids)")
    exp_yaml = m.get("experiment_yaml", "")
    return {
        "format": "latbench-run/2", "made_by": made_by,
        "run": {"id": run_id, "digest": digest, "experiment": m["experiment"],
                "app": yaml.safe_load(exp_yaml).get("app") if exp_yaml else None,
                "experiment_file": m.get("experiment_file"),
                "experiment_sha256": hashlib.sha256(exp_yaml.encode()).hexdigest() if exp_yaml else None,
                "host": m.get("host"), "board": m.get("board"), "safety_rev": m.get("safety", {}).get("rev"),
                "trees": {t: {r: v.get("rev") for r, v in cfg.get("repos", {}).items()}
                          for t, cfg in m.get("trees", {}).items()},
                "started": m.get("started"), "finished": m.get("finished"), "axes_source": note},
        "points": points,
    }


def extractor(app):
    path = trees.BENCH_DIR / app / "scripts" / "extract.py"
    if not path.is_file():
        raise FileNotFoundError(f"app {app} has no extractor {path.relative_to(trees.REPO_DIR)}")
    return path


def app_json(run_dir, app, run_id, digest, made_by):
    """Run the extractor of the app on the run folder; return its data with the run identity."""
    path = extractor(app)
    r = subprocess.run([sys.executable, str(path), str(run_dir)], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{path.relative_to(trees.REPO_DIR)} {run_dir}: {r.stderr.strip()[-2000:]}")
    data = json.loads(r.stdout)
    extractor_ref = {"file": str(path.relative_to(trees.REPO_DIR))}
    return {"format": f"latbench-app-{app}/1", "made_by": {**made_by, "extractor": extractor_ref["file"]},
            "run": {"id": run_id, "digest": digest}, **data}
