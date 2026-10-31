# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The benchmark side of a campaign: the board lock, the pre-flight check and the hooks of the engine.

core/campaign.py is the engine (record, order, resume, lock, results build). This module gives it
what only the latency benchmarks have: the board as the resource (lock file .lab/locks/board-<key>.lock),
the pre-flight check (lint, trees, SDK, images, hardware map, console, loopback wire, disk, duration),
the check of the loopback wire before a run, the build-cache note of a finished run, the command of
run.py and the instance of an experiment. campaign.py (this folder) keeps the plan (which experiments,
which instance) and the names that study.py and the tests use.
"""

import datetime
import json
import shutil
import sys
from pathlib import Path

import yaml

from probatrix.benchmarks import kind as benchkind
from probatrix.benchmarks import trees
from probatrix.core import campaign as engine
from probatrix.core import config, layout
from probatrix.core.campaign import FAILED, PLANNED, RUNNING

from . import instance

BOARD = engine.Resource("board", benchkind.KIND.instance_axis.lock_key)


def estimate(lab, design, exp):
    """(seconds, bytes) of the last run of an experiment in the lab space, or (None, None)."""
    root = lab.results / design.top.name
    best = None
    found = [m for name in design.names(exp) for m in root.glob(f"**/{layout.EXPERIMENT_PREFIX}{name}/*/manifest.json")]
    for m in sorted(found, key=lambda m: m.parent.name) if root.is_dir() else []:
        try:
            d = json.loads(m.read_text())
        except (OSError, ValueError):
            continue
        if d.get("started") and d.get("finished"):
            t = (datetime.datetime.fromisoformat(d["finished"]) - datetime.datetime.fromisoformat(d["started"]))
            size = sum(f.stat().st_size for f in m.parent.rglob("*") if f.is_file())
            best = (t.total_seconds(), size)
    return best or (None, None)


def preflight(lab, items, design, hwcheck=True, warn_as_error=False, log=print, locked=False):
    """The pre-flight check: [(status, what, text)] with status ok / warn / fail."""
    from probatrix.benchmarks import hwmap

    from . import hwcheck as hwc
    from . import kindhooks
    from . import lint as lintmod

    run = kindhooks.run_module()
    out = []

    def add(status, what, text=""):
        out.append((status, what, text))
        log(f"  {status:4} {what}{': ' + text if text else ''}")

    todo = [e for e in items if e["state"] in (PLANNED, FAILED, RUNNING)]
    rev, dirty = trees.repo_state(config.project().repo)
    add("fail" if dirty else "ok", "design repo", f"{config.project().repo} at {rev[:12]}" + (" is dirty" if dirty else ""))
    problems = lintmod.lint()
    mine = list({str(p): p for e in todo
                 for p in lintmod.lint_for_experiment(config.project().repo / e["design"], problems)}.values())
    errors = [p for p in mine if p.severity == lintmod.ERROR]
    if errors:
        add("fail", "lint", f"{len(errors)} errors, first: {errors[0]}")
    elif mine:
        add("fail" if warn_as_error else "warn", "lint", f"{len(mine)} warnings (study.py design lint)")
    else:
        add("ok", "lint")
    cfg = trees.load(lab=lab)
    try:
        add("ok", "zephyr sdk", str(trees.check_toolchain(cfg)))
    except trees.TreeError as e:
        add("fail", "zephyr sdk", str(e))
    need_trees = sorted({t for e in todo for t in yaml.safe_load((config.project().repo / e["design"]).read_text())["trees"]})
    for t in need_trees:
        try:
            trees.check_tree(cfg, t)
            add("ok", f"tree {t}")
        except trees.TreeError as e:
            add("fail", f"tree {t}", str(e).splitlines()[0])
    total = cached = 0
    secs, size, unknown = 0.0, 0, []
    for e in todo:
        try:
            n, c = run.cache_state(config.project().repo / e["design"], lab)
            total, cached = total + n, cached + c
        except (SystemExit, Exception) as x:
            add("fail", f"images of {e['experiment']}", f"{type(x).__name__}: {x}")
        s, b = estimate(lab, design, e["experiment"])
        if s is None:
            unknown.append(e["experiment"])
        else:
            secs, size = secs + s, size + b
    add("ok" if cached == total else "warn", "images",
        f"{cached} of {total} in the build cache" + ("" if cached == total else
                                                     f"; 'campaign prepare' or the run builds {total - cached}"))
    boards = sorted({e["board"] for e in todo})
    try:
        entries = hwmap.load(lab.hw_map)
    except hwmap.HwMapError as x:
        entries = None
        add("fail", "hardware map", str(x))
    for b in boards:
        if entries is None:
            break
        try:
            hw = hwmap.hardware(hwmap.select(entries, b, path=str(lab.hw_map)))
        except hwmap.HwMapError as x:
            add("fail", f"board {b}", str(x))
            continue
        add("ok" if Path(hw["serial"]).exists() else "fail", f"board {b}",
            f"probe {hw['probe']}, console {hw['serial']}" + ("" if Path(hw["serial"]).exists() else " is missing"))
        try:
            import serial
            serial.Serial(hw["serial"], hw["baud"], timeout=0.1, exclusive=True).close()
            add("ok", f"console of {b}", "free")
        except (OSError, ValueError) as x:
            add("fail", f"console of {b}", f"not free: {x}")
        if hwcheck:
            try:
                ok, lines, path = hwc.check(lab, b, log=lambda m: None, locked=locked)
                add("ok" if ok else "fail", f"loopback wire of {b}",
                    (lines[-1] if lines else "") + f" (record {path.relative_to(lab.folder)})")
            except Exception as x:
                where = f" (record {x.record.relative_to(lab.folder)})" if getattr(x, "record", None) else ""
                add("fail", f"loopback wire of {b}", f"{type(x).__name__}: {(str(x).splitlines() or [''])[0]}{where}")
    free = shutil.disk_usage(lab.results if lab.results.exists() else lab.folder).free
    add("ok" if free > 2 * size else "fail", "disk", f"{free / 2**30:.0f} GiB free, the runs need about {size / 2**20:.0f} MiB")
    dur = f"about {secs / 3600:.1f} h" if secs else "unknown"
    add("ok", "duration", dur + (f" (no earlier run of {', '.join(unknown)})" if unknown else ""))
    return out


def wire_check(lab, board, e):
    """None if the loopback wire of the board is good, else the reason (for --hwcheck-each); the
    experiment e gets the record of the check."""
    from . import hwcheck as hwc
    try:
        ok, lines, path = hwc.check(lab, board, log=lambda m: None, locked=True)
    except Exception as x:
        if getattr(x, "record", None):
            e["hwcheck"] = str(x.record.relative_to(lab.folder))
        return f"the loopback wire check could not run: {type(x).__name__}: {(str(x).splitlines() or [''])[0]}"
    e["hwcheck"] = str(path.relative_to(lab.folder))
    return None if ok else f"the loopback wire check failed: {lines[-1] if lines else ''}"


def images_note(folder, run_id):
    """'5/5 images from the build cache' for a run (from its manifest)."""
    try:
        m = json.loads((Path(folder) / layout.run_folder(run_id) / "manifest.json").read_text())
    except (OSError, ValueError):
        return "images: no manifest"
    pts = m.get("points", [])
    n = sum(p.get("build", {}).get("from") == "cache" or p.get("build", {}).get("cached") is True for p in pts)
    return f"{n}/{len(pts)} images from the build cache"


def run_of_campaign(lab, e, cid):
    """The id of a run of the experiment e that the campaign cid added to the run list of its
    instance after e started, or None."""
    if not e.get("instance"):
        return None
    folder = lab.results / e["instance"]
    if not (folder / "instance.json").is_file():
        return None
    started = (e.get("started") or "")[:19].replace("-", "").replace(":", "")
    for r in instance.load(folder).get("runs", []):
        exp, utc = r["id"].split("/")
        if r.get("campaign") == cid and exp == e["experiment"] and utc[:15] >= started[:15]:
            return r["id"]
    return None


class CampaignHooks(engine.Hooks):
    """The hooks of the engine for the latency benchmarks. The calls go through the module campaign (the
    functions that a test or a tool replaces there)."""

    kind = benchkind.KIND
    resource = BOARD

    def repo_state(self):
        return trees.repo_state(config.project().repo)

    def update_ref(self, ref, rev):
        trees.git("update-ref", ref, rev, cwd=config.project().repo)

    def python_info(self):
        from . import lab as labmod
        return labmod.packages(config.project().repo)

    def resource_keys(self, data):
        return [e["board"] for e in data["experiments"] if e["state"] != engine.SKIPPED] or [data.get("board") or "-"]

    def preflight(self, lab, items, design, hwcheck, warn_as_error, log, locked):
        from . import campaign
        return campaign.preflight(lab, items, design, hwcheck=hwcheck, warn_as_error=warn_as_error, log=log,
                                  locked=locked)

    def run_of_campaign(self, lab, e, cid):
        from . import campaign
        return campaign.run_of_campaign(lab, e, cid)

    def ensure_instance(self, lab, design, e, log):
        from . import campaign
        return campaign.ensure_instance(lab, design, e["study"], e["board"], log=log)

    def before_run(self, rec, e, hwcheck):
        from . import campaign
        if rec.data.get("hwcheck_each") and hwcheck:
            return campaign.wire_check(rec.lab, e["board"], e)
        return None

    def run_command(self, rec, e, folder, warn_as_error):
        from . import campaign
        d = rec.data
        cmd = [sys.executable, campaign.run_py(), config.project().repo / e["design"], "--out", folder,
               "--campaign", rec.id, "--role", d.get("role", "evidence"),
               *(["--reason", d["reason"]] if d.get("reason") else [])]
        if warn_as_error:
            cmd.append("--warn-as-error")
        return cmd

    def run_note(self, folder, run_id):
        from . import campaign
        return campaign.images_note(folder, run_id)

    def post(self, rec, root):
        from . import campaign
        return campaign.Post(rec, root)
