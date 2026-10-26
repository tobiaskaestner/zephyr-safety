# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The aggregates of a results tree.

For each instance (the deepest first):
    each run of its run list: the seal is checked, run.json and the app
    data are written beside the run folder;
    the acceptance checks of each run;
    ex-<experiment>/experiment.json for each experiment of the instance;
    study.json: the hypotheses with their checks, the central results.

The build reads instance.json and the raw runs and does not change them.
The same inputs and the same tools give the same bytes, so `check` can
build again and compare.
"""

import json
from pathlib import Path

from . import central, checks, instance, jsonout, layout, runfiles, seal, stats
from .design import Design, repo_rel, repo_rev
from .stats import NoValue

STATS = ["n", "invalid", "min", "p50", "p90", "p99", "p99.9", "p99.99", "max", "mean"]


class BuildError(Exception):
    pass


class Writer:
    """Writes the JSON files, or (dry) compares them with the files on disk."""

    def __init__(self, dry=False):
        self.dry = dry
        self.differ = []
        self.written = 0

    def write(self, path, obj):
        data = (jsonout.dumps(obj) + "\n").encode()
        if self.dry:
            if not path.is_file() or path.read_bytes() != data:
                self.differ.append(str(path))
        else:
            jsonout.write(path, obj)
            self.written += 1
        import hashlib
        return hashlib.sha256(data).hexdigest()


class Tree:
    def __init__(self, root, design=None, writer=None, log=print):
        self.root = Path(root).resolve()
        self.design = design or Design()
        self.writer = writer or Writer()
        self.log = log
        rev, dirty = repo_rev()
        self.made_by = {"tool": "scripts/benchmarks/study.py", "safety_rev": rev}
        if dirty:
            self.made_by["dirty"] = True
        self.folders = layout.instance_folders(self.root)
        self.data = {f: instance.load(f) for f in self.folders}
        self.ipath = {f: layout.instance_path_of(f, self.root) for f in self.folders}
        self.runs = {}        # run id -> (folder, entry)
        self.loaded = {}      # (folder, run id) -> (run.json, app.json, run sha, app sha)
        self.obs = {}         # (folder, run id) -> [Obs]
        self.acceptance = {}  # (folder, run id) -> [results]
        self.results = {}     # folder -> study.json object
        for f in self.folders:
            for r in self.data[f].get("runs", []):
                if r["id"] in self.runs:
                    raise BuildError(f"run {r['id']} is in two instances: {self.runs[r['id']][0]} and {f}")
                self.runs[r["id"]] = (f, r)

    # ------------------------------------------------------------ lookups
    def study(self, folder):
        return self.design.study(layout.strip_board(self.ipath[folder]))

    def board(self, folder):
        return instance.board_of(folder)

    def find_instance(self, study_path, board):
        hits = [f for f in self.folders if layout.strip_board(self.ipath[f]) == study_path
                and (board is None or self.board(f) == board)]
        if len(hits) != 1:
            raise NoValue(f"instance of study {study_path} for board {board}: {len(hits)} found")
        return hits[0]

    # ------------------------------------------------------------ runs
    def load_run(self, folder, run_id, want_digest=None):
        key = (folder, run_id)
        if key in self.loaded:
            return self.obs[key]
        run_dir = folder / layout.run_folder(run_id)
        digest = seal.verify(run_dir)
        if want_digest and digest != want_digest:
            raise BuildError(f"{run_dir}: digest {digest}, the run list has {want_digest}")
        exp = run_id.split("/")[0]
        efile = None
        if exp in self.design.experiments:
            efile = self.design.experiment(exp).folder / "experiment.yaml"
        rj = runfiles.run_json(run_dir, run_id, digest, self.made_by, efile)
        app = rj["run"]["app"]
        aj = runfiles.app_json(run_dir, app, run_id, digest, self.made_by)
        rsha = self.writer.write(run_dir.parent / f"{run_dir.name}.run.json", rj)
        asha = self.writer.write(run_dir.parent / f"{run_dir.name}.{app}.json", aj)
        self.loaded[key] = (rj, aj, rsha, asha)
        obs = []
        for p, ap in zip(rj["points"], aj["points"]):
            if not ap["reps"]:
                continue
            obs.append(checks.Obs(run_id, p["tree"], p["point"], p["axes"], ap["reps"][0], len(ap["reps"])))
        self.obs[key] = obs
        return obs

    def own_runs(self, folder, exp=None, roles=("evidence",)):
        out = []
        for r in self.data[folder].get("runs", []):
            if exp is not None and r["id"].split("/")[0] != exp:
                continue
            if r["role"] not in roles:
                continue
            if roles == ("evidence",) and self.failed_acceptance(folder, r["id"]):
                continue
            out.append(r)
        return out

    def failed_acceptance(self, folder, run_id):
        return any(a["verdict"] == "wrong" for a in self.acceptance.get((folder, run_id), []))

    # ------------------------------------------------------------ build
    def build(self):
        order = sorted(self.folders, key=lambda f: -len(f.relative_to(self.root).parts))
        for f in order:
            for r in self.data[f].get("runs", []):
                try:
                    self.load_run(f, r["id"], r.get("digest"))
                except (NoValue, RuntimeError, FileNotFoundError, KeyError, ValueError) as e:
                    if r["role"] != "excluded":
                        raise BuildError(f"{self.ipath[f] or '(top)'}: {r['id']}: {e}") from e
                    self.log(f"  note: excluded run {r['id']} does not parse: {e}")
            self.run_acceptance(f)
        for f in order:
            self.build_instance(f)
        return self.results

    def run_acceptance(self, folder):
        for r in self.data[folder].get("runs", []):
            if r["role"] == "excluded" or (folder, r["id"]) not in self.obs:
                continue
            exp = r["id"].split("/")[0]
            if exp not in self.design.experiments:
                continue
            res = []
            for a in self.design.experiment(exp).acceptance:
                src = Source(self, folder, only_run=(folder, r["id"]))
                chk = {**a, "experiment": a.get("experiment", exp)}
                if a.get("manual"):
                    res.append({"id": a["id"], "verdict": "open (manual)", "statement": a.get("statement")})
                    continue
                try:
                    out = checks.evaluate(chk, src)
                except NoValue as e:
                    out = {"verdict": "not evaluated", "measured": str(e), "limit": checks.limit_text(a.get("expect", {}))}
                res.append({"id": a["id"], **{k: out[k] for k in ("verdict", "measured", "limit")}})
            self.acceptance[(folder, r["id"])] = res

    def build_instance(self, folder):
        data = self.data[folder]
        study = self.study(folder)
        src = Source(self, folder)
        manual = {(m.get("hypothesis"), m.get("check")): m for m in data.get("manual_verdicts", []) if m.get("hypothesis")}

        # experiments of the instance
        experiments = []
        for exp in sorted({r["id"].split("/")[0] for r in data.get("runs", [])}):
            runs = [r for r in data["runs"] if r["id"].split("/")[0] == exp and (folder, r["id"]) in self.loaded]
            if not runs:
                continue
            sha = self.writer.write(folder / f"{layout.EXPERIMENT_PREFIX}{exp}" / "experiment.json",
                                    self.experiment_json(folder, exp, runs))
            experiments.append({"name": exp, "file": f"{layout.EXPERIMENT_PREFIX}{exp}/experiment.json", "sha256": sha})

        # hypotheses
        hyps = []
        for h in study.hypotheses:
            out_checks = []
            for c in h["checks"]:
                entry = {"id": c["id"]}
                if c.get("formerly"):
                    entry["formerly"] = c["formerly"]
                m = manual.get((h["id"], c["id"]))
                if c.get("manual"):
                    if m:
                        entry.update(verdict=m["verdict"], by=m.get("by"), measured=m.get("text", ""), limit="manual")
                    else:
                        entry.update(verdict="open (manual)", by=None, measured="", limit="manual")
                else:
                    try:
                        out = checks.evaluate(c, src)
                        entry.update(verdict=out["verdict"], by="auto", measured=out["measured"],
                                     limit=out["limit"], values=out["values"])
                    except NoValue as e:
                        entry.update(verdict="not evaluated", by="auto", measured=str(e),
                                     limit=checks.limit_text(c.get("expect", {})))
                    except (KeyError, IndexError, TypeError, ZeroDivisionError, StopIteration) as e:
                        entry.update(verdict="not evaluated", by="auto",
                                     measured=f"tool error: {type(e).__name__}: {e}",
                                     limit=checks.limit_text(c.get("expect", {})))
                out_checks.append(entry)
            hyps.append(hypothesis_entry(h, out_checks))
        self._hyps = {h["id"]: h["verdict"] for h in hyps}

        # central results
        ctx = Context(self, folder, data, hyps)
        results = []
        for cr in study.central_results:
            try:
                results.append(central.evaluate(cr, src, ctx))
            except NoValue as e:
                results.append({"id": cr["id"], "stat": cr.get("stat"), "texts": [], "rows": [],
                                "by": "auto", "not_evaluated": str(e)})
            except (KeyError, IndexError, TypeError, ZeroDivisionError, StopIteration) as e:
                results.append({"id": cr["id"], "stat": cr.get("stat"), "texts": [], "rows": [], "by": "auto",
                                "not_evaluated": f"tool error: {type(e).__name__}: {e}"})

        acceptance = [{"run": rid, "checks": res} for (f, rid), res in sorted(self.acceptance.items()) if f == folder and res]
        rebuilds = []
        for r in data.get("runs", []):
            run_dir = folder / layout.run_folder(r["id"])
            for rec in sorted(run_dir.parent.glob(f"{run_dir.name}.rebuild-*.json")):
                d = json.loads(rec.read_text())
                rebuilds.append({"run": r["id"], "record": rec.name, "host": d.get("host"),
                                 "tool_rev": d.get("tool", {}).get("safety_rev"), "summary": d.get("summary"),
                                 "different": [f"{p['tree']}/{p['point']}" for p in d.get("points", [])
                                               if p.get("verdict") != "same"]})
        ishas = jsonout.dumps(data)
        import hashlib
        sj = {"format": "latbench-study/2", "made_by": self.made_by,
              "instance": data["instance"],
              "design": {"folder": repo_rel(study.folder),
                         "safety_rev": self.made_by["safety_rev"], "files": study.files()},
              "board": self.board(folder),
              "instance_json_sha256": hashlib.sha256((ishas + "\n").encode()).hexdigest(),
              "question": " ".join(study.data.get("question", "").split()),
              "experiments": experiments,
              "acceptance": acceptance,
              "rebuild_checks": rebuilds,
              "hypotheses": hyps,
              "central_results": results,
              "substudies": [{"instance": self.data[c]["instance"],
                              "study_json": str((c / "study.json").relative_to(folder))}
                             for c in self.folders if c.parent == folder]}
        self.results[folder] = sj
        self.writer.write(folder / "study.json", sj)

    def experiment_json(self, folder, exp, runs):
        rows, axes_all, core = [], set(), set()
        for r in runs:
            rj, aj, _, _ = self.loaded[(folder, r["id"])]
            for p in rj["points"]:
                axes_all |= set(p["axes"])
        axes_all = sorted(axes_all)
        out_runs = []
        for r in runs:
            rj, aj, rsha, asha = self.loaded[(folder, r["id"])]
            core.add(aj.get("core_hz"))
            utc = r["id"].split("/")[1]
            out_runs.append({"id": r["id"], "digest": r["digest"], "role": r["role"],
                             "excluded_by_acceptance": self.failed_acceptance(folder, r["id"]),
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
        efile = self.design.experiments.get(exp)
        return {"format": "latbench-experiment/2", "made_by": self.made_by, "experiment": exp,
                "design": efile.file_ref() if efile else None,
                "runs": out_runs, "unit": "cycles", "core_hz": sorted(c for c in core if c)[0] if any(core) else None,
                "columns": ["run", "role", "tree", "point", "rep", *[f"axis.{a}" for a in axes_all], "metric", *STATS,
                            "coarse_from", "coarse_width", "image_sha256", "code_sha256"],
                "rows": rows}


def hypothesis_entry(h, out_checks):
    verdicts = [c["verdict"] for c in out_checks]
    if any(v.startswith("wrong") for v in verdicts):
        verdict = "wrong"
    elif all(v == "confirmed" for v in verdicts):
        verdict = "confirmed"
    else:
        verdict = "open"
    if any("proposal" in v for v in verdicts):
        verdict += " (a check has a proposal that needs sign-off)"
    open_reasons = sorted({v for v in verdicts if v != "confirmed" and not v.startswith("wrong")})
    out = {"id": h["id"], "type": h.get("type"), "statement": " ".join(h["statement"].split()),
           "verdict": verdict, "checks_confirmed": f"{verdicts.count('confirmed')} of {len(verdicts)}"}
    if open_reasons:
        out["open"] = open_reasons
    out["checks"] = out_checks
    return out


class Source:
    """The points that the checks of an instance can read."""

    def __init__(self, tree, folder, only_run=None):
        self.tree, self.folder, self.only_run = tree, folder, only_run

    def observations(self, exp, series=None):
        t = self.tree
        if self.only_run:
            obs = t.obs[self.only_run]
            return [o for o in obs if series is None or o.series == series]
        if series is not None:
            run_id = series[0]
            f, _ = t.runs[run_id]
            return [o for o in t.obs[(f, run_id)] if o.series == series]
        study = t.study(self.folder)
        if exp not in study.readable():
            raise NoValue(f"study {study.path} does not own or import {exp}")
        runs = t.own_runs(self.folder, exp)
        folder = self.folder
        if not runs:
            imp = next((i for i in study.imports if i["experiment"] == exp), None)
            if imp is None:
                raise NoValue(f"no evidence run of {exp} in {t.ipath[self.folder] or '(top)'}")
            folder = t.find_instance(imp["study"], t.board(self.folder))
            runs = t.own_runs(folder, exp)
            if not runs:
                raise NoValue(f"no evidence run of {exp} in {t.ipath[folder]}")
        return [o for r in runs for o in t.obs[(folder, r["id"])]]

    def run_obs(self, ref):
        """The points of a run, by "<study path>/<experiment>/<UTC>" (any role)."""
        parts = ref.split("/")
        study_path, run_id = "/".join(parts[:-2]), "/".join(parts[-2:])
        t = self.tree
        folder = t.find_instance(study_path, t.board(self.folder))
        entry = next((r for r in t.data[folder].get("runs", []) if r["id"] == run_id), None)
        if entry is None:
            raise NoValue(f"{t.ipath[folder]} has no run {run_id}")
        return t.load_run(folder, run_id, entry.get("digest"))


class Context:
    """What a central result needs besides the points."""

    def __init__(self, tree, folder, data, hyps):
        self.tree, self.folder, self.data, self.hyps = tree, folder, data, {h["id"]: h for h in hyps}

    def defaults(self):
        """Values that each row of a central result can use."""
        return {"board": self.tree.board(self.folder), "instance": self.data["instance"]}

    def hypothesis_verdict(self, hid):
        h = self.hyps.get(hid)
        return h["verdict"] if h else "no such hypothesis"

    def manual_verdict(self, cr_id):
        return next((m for m in self.data.get("manual_verdicts", []) if m.get("central_result") == cr_id), None)

    def substudy_result(self, name, cr_id):
        for c in self.tree.folders:
            if c.parent == self.folder and layout.strip_board(self.tree.ipath[c]).rsplit("/", 1)[-1] == name:
                sj = self.tree.results.get(c)
                if sj:
                    return next((r for r in sj["central_results"] if r["id"] == cr_id), None)
        return None

    def axis_number(self, o, axis):
        exp = o.run.split("/")[0]
        e = self.tree.design.experiments.get(exp)
        if e is None:
            return None
        v = (e.data.get("axes") or {}).get(axis, {}).get(o.axes.get(axis))
        return v.get("value") if isinstance(v, dict) else None

    def owner_point(self, o):
        """The same point of the run of the owner study (for a re-run)."""
        exp = o.run.split("/")[0]
        owner = self.tree.design.experiments.get(exp)
        if owner is None:
            return None
        try:
            folder = self.tree.find_instance(owner.study, self.tree.board(self.folder))
        except NoValue:
            return None
        for r in self.tree.own_runs(folder, exp):
            for x in self.tree.obs[(folder, r["id"])]:
                if x.point == o.point and x.tree == o.tree:
                    return x
        return None


def build(root, dry=False, log=print):
    writer = Writer(dry=dry)
    t = Tree(root, writer=writer, log=log)
    t.build()
    return t, writer


def load_json(path):
    return json.loads(Path(path).read_text())
