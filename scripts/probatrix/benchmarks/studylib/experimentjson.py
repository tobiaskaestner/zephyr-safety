# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The latency side of a build: experiment.json, the plots and the pending runs of the lab.

core/build.py (the generic build loop) calls these through the latbench Kind (experiment_json, plot,
pending). The code is moved from studylib/build.py; `self` of the Tree is the argument `tree`.
"""

import subprocess
import sys

from probatrix.benchmarks import kind as benchkind
from probatrix.core import config, layout
from probatrix.core.errors import NoValue

from . import stats

STATS = ["n", "invalid", "min", "p50", "p90", "p99", "p99.9", "p99.99", "max", "mean"]


def pending(root, design):
    """{(instance folder, experiment): campaign id} of the running campaigns of the lab space of root."""
    from pathlib import Path
    from . import campaign
    from . import lab as labmod
    lab = labmod.owner(root)
    if lab is None:
        return {}
    return {(Path(f).resolve(), e): c for (f, e), c in campaign.pending(lab, design).items()}


def plot(tree, folder, exp, runs):
    """The standard plots of an experiment of an instance (the plot.py of its app), from the app data
    of the runs that are not excluded (evidence and adjustment: a smoke campaign shows its graphs
    too), in ex-<exp>/plots/; None, or the reason why they failed."""
    ev = sorted((r for r in runs if r["role"] != "excluded"), key=lambda r: r["id"].split("/")[-1])
    if not ev:
        return None
    app = tree.loaded[(folder, ev[0]["id"])][0]["run"]["app"]
    script = plot_script(app)
    if not script.is_file():
        return None
    args = []
    for r in ev:
        run_dir = folder / layout.run_folder(r["id"])
        tags = ([] if r["role"] == "evidence" else [r["role"]]) + \
            (["acceptance failed"] if tree.failed_acceptance(folder, r["id"]) else [])
        label = r["id"] + (f" ({', '.join(tags)})" if tags else "")
        args.append(f"{label}={run_dir.parent / f'{run_dir.name}.{app}.json'}")
    out = folder / f"{layout.EXPERIMENT_PREFIX}{exp}" / "plots"
    res = subprocess.run([sys.executable, str(script), str(out), *args], capture_output=True, text=True)
    err = out / "error.txt"
    if res.returncode == 0:
        err.unlink(missing_ok=True)
        return None
    why = (res.stderr.strip().splitlines() or ["?"])[-1][:300]
    out.mkdir(parents=True, exist_ok=True)
    err.write_text(f"{script.relative_to(config.project().repo)}: {why}\n")
    return why



def experiment_json(tree, folder, exp, runs):
    rows, axes_all, core = [], set(), set()
    for r in runs:
        rj, aj, _, _ = tree.loaded[(folder, r["id"])]
        for p in rj["points"]:
            axes_all |= set(p["axes"])
    axes_all = sorted(axes_all)
    out_runs = []
    for r in runs:
        rj, aj, rsha, asha = tree.loaded[(folder, r["id"])]
        core.add(aj.get("core_hz"))
        utc = r["id"].split("/")[1]
        out_runs.append({"id": r["id"], "digest": r["digest"], "role": r["role"],
                         "excluded_by_acceptance": tree.failed_acceptance(folder, r["id"]),
                         "run_json": f"{utc}.run.json", "run_json_sha256": rsha,
                         "app_json": f"{utc}.{aj['app']}.json", "app_json_sha256": asha})
        for p, ap in zip(rj["points"], aj["points"]):
            for rep in ap["reps"]:
                for metric, h in rep["hists"].items():
                    vals = []
                    for s in STATS:
                        try:
                            vals.append(stats.hist_value(h, s))
                        except NoValue:
                            vals.append(None)
                    coarse = (h["coarse"][0][0], h["coarse"][0][2]) if h["coarse"] else (None, None)
                    rows.append([r["id"], r["role"], p["tree"], p["point"], rep["rep"],
                                 *[p["axes"].get(a) for a in axes_all], metric, *vals, *coarse,
                                 p["image_sha256"], p.get("code_sha256")])
    # points whose code differs between the evidence runs (other app or kernel code)
    codes = {}
    for r in runs:
        if r["role"] != "evidence":
            continue
        for p in tree.loaded[(folder, r["id"])][0]["points"]:
            codes.setdefault((p["tree"], p["point"]), set()).add(p.get("code_sha256"))
    differ = sorted(f"{t}/{pt}" for (t, pt), c in codes.items() if len(c) > 1)
    efile = tree.design.experiments.get(exp)
    out = {"format": benchkind.KIND.format_id("experiment", 2), "made_by": tree.made_by, "experiment": exp,
           "design": efile.file_ref() if efile else None,
           "runs": out_runs, "unit": "cycles", "core_hz": sorted(c for c in core if c)[0] if any(core) else None,
           "columns": ["run", "role", "tree", "point", "rep", *[f"axis.{a}" for a in axes_all], "metric", *STATS,
                       "coarse_from", "coarse_width", "image_sha256", "code_sha256"],
           "rows": rows}
    if differ:
        out["code_differs"] = differ
    return out




def plot_script(app):
    return benchkind.KIND.bench_dir / app / "scripts" / "plot.py"
