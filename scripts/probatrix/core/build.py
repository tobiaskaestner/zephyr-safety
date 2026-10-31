# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The aggregates of a results tree.

For each instance (the deepest first):
    each run of its run list: the seal is checked, run.json and the app
    data are written beside the run folder;
    the acceptance checks of each run;
    ex-<experiment>/experiment.json for each experiment of the instance;
    study.json: the hypotheses with their checks, the central results.

The generic part of the build: everything that the Kind does not know. The Kind gives the values of a run
(run_json, app_json, value), the experiment.json and the plots (experiment_json, plot), the central results
(central_result), the pending runs of a lab (pending) and the rules of the instance axis. This module
does not import a kind.

The build reads instance.json and the raw runs and does not change them.
The same inputs and the same tools give the same bytes, so `check` can
build again and compare. A build (not `check`) takes the run.json and the
app data of a run from the files of an earlier build if they come from
the same run digest and the same clean tool commit, so a build after a new
run is fast.

In a lab space, a check (and its hypothesis) or a central result that
reads an experiment that a running campaign has still to run is
provisional: study.json says so in the entry and in "state".
"""

import hashlib
import json
from pathlib import Path

from probatrix.core import checks, config, jsonout, kinds, layout, seal
from probatrix.core.design import Design, repo_rel, repo_rev
from probatrix.core.errors import MissingRun, NoValue

# Errors of the tools (not of the data): the check gets the verdict "tool error".
TOOL_ERRORS = (KeyError, IndexError, TypeError, ZeroDivisionError, StopIteration, ValueError,
               AttributeError, RuntimeError, FileNotFoundError)


def safe_limit(check, kind=None):
    try:
        return checks.limit_text(check.get("expect") or {}, kind)
    except NoValue:
        return str(check.get("expect"))


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
        return hashlib.sha256(data).hexdigest()


class Tree:
    def __init__(self, root, design=None, writer=None, log=print, pending=None, kind=None, design_root=None):
        """design_root: the folder of the design (a root of the Project). Without it, the results tree
        names it (design_root_of)."""
        self.root = Path(root).resolve()
        if design is None:
            wanted = design_root or design_root_of(self.root)
            if wanted == config.project().design_root:
                design = Design(kind=kind) if kind else Design()           # the first root: as before
            else:
                design = Design(wanted, kind=kind)
        self.design = design
        self.kind = kind or kinds.kind_of(self.design.top, config.project().root_of(self.design.root))
        self.axis = self.kind.instance_axis
        self.writer = writer or Writer()
        self.log = log
        rev, dirty = repo_rev(kind=self.kind)
        self.made_by = {"tool": self.kind.tool, "safety_rev": rev}
        if dirty:
            self.made_by["dirty"] = True
        self.folders = layout.instance_folders(self.root)
        self.data = {f: layout.load_instance(f) for f in self.folders}
        self.ipath = {f: layout.instance_path_of(f, self.root) for f in self.folders}
        self.runs = {}        # run id -> (folder, entry)
        self.loaded = {}      # (folder, run id) -> (run.json, app.json, run sha, app sha)
        self.obs = {}         # (folder, run id) -> [Obs]
        self.acceptance = {}  # (folder, run id) -> [results]
        self.results = {}     # folder -> study.json object
        self.pending = self.find_pending() if pending is None else pending
        for f in self.folders:
            for r in self.data[f].get("runs", []):
                if r["id"] in self.runs:
                    raise BuildError(f"run {r['id']} is in two instances: {self.runs[r['id']][0]} and {f}")
                self.runs[r["id"]] = (f, r)

    def find_pending(self):
        """{(instance folder, experiment): campaign id} of the running campaigns of the lab space."""
        return self.kind.pending(self.root, self.design)

    def generated_hypotheses(self, study):
        """One hypothesis for each experiment of the study (or rerun import) whose kind generates checks
        (kind.generated_checks, e.g. the expected verdict of each line of a list file). Its id is "<experiment>-generated"; a check
        without an experiment reads the experiment it comes from."""
        out = []
        # the own experiments, and the experiments that the study runs again (mode rerun: its own runs, so the
        # checks of the list apply to them; the data of a reuse import is checked in the owner study)
        reruns = [i["experiment"] for i in study.imports if i.get("mode") == "rerun"]
        for exp in [*study.experiments, *(r for r in reruns if r not in study.experiments)]:
            chks = self.kind.generated_checks(self.design.experiment(exp).data)
            if chks:
                out.append({"id": f"{exp}-generated", "type": "generated",
                            "statement": f"The checks that the kind {self.kind.name!r} generates for {exp} hold.",
                            "checks": [{"experiment": exp, **c} for c in chks]})
        return out

    def waits_for(self, folder, experiments):
        """The reason why a result of the instance that reads these experiments is provisional, or None."""
        if not self.pending:
            return None
        study = self.study(folder)
        out = []
        for exp in sorted({e for e in experiments if e}):
            places = [folder]
            imp = next((i for i in study.imports if i["experiment"] == exp and i.get("mode") != "rerun"), None)
            if imp is not None:
                try:
                    places.append(self.find_instance(imp["study"], self.board(folder)))
                except NoValue:
                    pass
            for f in places:
                c = self.pending.get((Path(f).resolve(), exp))
                if c:
                    out.append(f"waits for {exp} of the campaign {c}")
        return "; ".join(dict.fromkeys(out)) or None

    # ------------------------------------------------------------ lookups
    def strip(self, instance_path):
        """The study path of an instance path (the kind's instance axis; no axis: the path itself)."""
        return self.axis.strip(instance_path) if self.axis else instance_path

    def study(self, folder):
        return self.design.study(self.strip(self.ipath[folder]))

    def board(self, folder):
        """The value of the instance axis that the instance fixes (the board), or None."""
        return self.axis.of(folder) if self.axis else None

    def find_instance(self, study_path, board):
        hits = [f for f in self.folders if self.strip(self.ipath[f]) == study_path
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
        if not want_digest:
            raise BuildError(f"{run_dir}: the run list has no digest for {run_id}")
        if digest != want_digest:
            raise BuildError(f"{run_dir}: digest {digest}, the run list has {want_digest}")
        exp = self.design.run_experiment(run_id)
        efile = None
        if exp in self.design.experiments:
            efile = self.design.experiment(exp).folder / "experiment.yaml"
        rj, aj = self.earlier_files(run_dir, digest)
        if rj is None:
            rj = self.kind.run_json(run_dir, run_id, digest, self.made_by, efile)
            aj = self.kind.app_json(run_dir, rj["run"]["app"], run_id, digest, self.made_by)
        app = rj["run"]["app"]
        rsha = self.writer.write(run_dir.parent / f"{run_dir.name}.run.json", rj)
        asha = self.writer.write(run_dir.parent / f"{run_dir.name}.{app}.json", aj)
        self.loaded[key] = (rj, aj, rsha, asha)
        obs = []
        for p, ap in zip(rj["points"], aj["points"]):
            if not ap["reps"]:
                continue
            obs.append(checks.Obs(run_id, p["tree"], p["point"], p["axes"], ap["reps"][0], len(ap["reps"]),
                                  rj["run"].get("safety_rev")))
        self.obs[key] = obs
        return obs

    def earlier_files(self, run_dir, digest):
        """(run.json, app data) of an earlier build of the same run and the same clean tool commit, or (None, None)."""
        if self.writer.dry or self.made_by.get("dirty"):
            return None, None
        try:
            rj = load_json(run_dir.parent / f"{run_dir.name}.run.json")
            aj = load_json(run_dir.parent / f"{run_dir.name}.{rj['run']['app']}.json")
        except (OSError, ValueError, KeyError):
            return None, None
        for x in (rj, aj):
            mb = x.get("made_by", {})
            if mb.get("safety_rev") != self.made_by["safety_rev"] or mb.get("dirty") or x["run"]["digest"] != digest:
                return None, None
        return rj, aj

    def own_runs(self, folder, exp=None, roles=("evidence",)):
        out = []
        for r in self.data[folder].get("runs", []):
            if exp is not None and self.design.run_experiment(r["id"]) != self.design.canonical(exp):
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
                        raise BuildError(f"{layout.ipath_display(self.ipath[f])}: {r['id']}: {e}") from e
                    self.log(f"  note: excluded run {r['id']} does not parse: {e}")
            self.run_acceptance(f)
        self.check_references()
        for f in order:
            self.build_instance(f)
        return self.results

    def check_references(self):
        """The digest that a reference records must be the digest of the run in its owner instance."""
        for f in self.folders:
            for ref in self.data[f].get("references", []):
                owner = self.runs.get(ref["id"])
                if owner is None:
                    raise BuildError(f"{layout.ipath_display(self.ipath[f])}: reference {ref['id']} is in no run list")
                if owner[1].get("digest") != ref.get("digest"):
                    raise BuildError(f"{layout.ipath_display(self.ipath[f])}: reference {ref['id']} has digest {ref.get('digest')}, "
                                     f"its owner has {owner[1].get('digest')}")

    def run_acceptance(self, folder):
        for r in self.data[folder].get("runs", []):
            if r["role"] == "excluded" or (folder, r["id"]) not in self.obs:
                continue
            exp = self.design.run_experiment(r["id"])
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
                    out = checks.evaluate(chk, src, self.kind)
                except NoValue as e:
                    out = {"verdict": "not evaluated", "measured": str(e), "limit": safe_limit(a, self.kind)}
                except TOOL_ERRORS as e:
                    out = {"verdict": "tool error", "measured": f"{type(e).__name__}: {e}", "limit": safe_limit(a, self.kind)}
                res.append({"id": a["id"], **{k: out[k] for k in ("verdict", "measured", "limit")}})
            self.acceptance[(folder, r["id"])] = res

    def build_instance(self, folder):
        data = self.data[folder]
        study = self.study(folder)
        src = Source(self, folder)
        manual = {(m.get("hypothesis"), m.get("check")): m for m in data.get("manual_verdicts", []) if m.get("hypothesis")}

        # experiments of the instance
        experiments, notes = [], []
        for exp in sorted({self.design.run_experiment(r["id"]) for r in data.get("runs", [])}):
            runs = [r for r in data["runs"] if self.design.run_experiment(r["id"]) == exp
                    and (folder, r["id"]) in self.loaded]
            if not runs:
                continue
            ej = self.kind.experiment_json(self, folder, exp, runs)
            sha = self.writer.write(folder / f"{layout.EXPERIMENT_PREFIX}{exp}" / "experiment.json", ej)
            experiments.append({"name": exp, "file": f"{layout.EXPERIMENT_PREFIX}{exp}/experiment.json", "sha256": sha})
            if not self.writer.dry:
                # not a note of study.json: "analysis check" (a dry build without plots) must give the
                # same bytes; the experiment page shows the error (plots/plots.json)
                why = self.kind.plot(self, folder, exp, runs)
                if why:
                    self.log(f"warning: {layout.ipath_display(self.ipath[folder])}: {exp}: the plots failed: {why}")
            if ej.get("code_differs"):
                notes.append(f"{exp}: the evidence runs have different code at {len(ej['code_differs'])} points "
                             f"({', '.join(ej['code_differs'][:4])}); a check over these runs mixes two code versions")

        # hypotheses
        hyps = []
        for h in [*study.hypotheses, *self.generated_hypotheses(study)]:
            out_checks = []
            for c in h.get("checks") or []:
                entry = {"id": c["id"]}
                if c.get("formerly"):
                    entry["formerly"] = c["formerly"]
                m = manual.get((h["id"], c["id"]))
                if has_todo(c) or has_todo(h.get("statement")):
                    entry.update(verdict=DRAFT, by=None, limit=safe_limit(c, self.kind),
                                 measured="the check or its hypothesis has a TODO text of a template")
                elif c.get("manual"):
                    if m and m["verdict"] not in ("confirmed", "wrong"):
                        notes.append(f"{h['id']} {c['id']}: manual verdict {m['verdict']!r} is not confirmed or wrong")
                        m = None
                    if m:
                        entry.update(verdict=m["verdict"], by=m.get("by"), measured=m.get("text", ""), limit="manual")
                    else:
                        entry.update(verdict="open (manual)", by=None, measured="", limit="manual",
                                     statement=" ".join(str(c.get("statement", "")).split()))
                else:
                    try:
                        out = checks.evaluate(c, src, self.kind)
                        entry.update(verdict=out["verdict"], by="auto", measured=out["measured"],
                                     limit=out["limit"], values=out["values"],
                                     **({"measured_lines": out["measured_lines"]} if "measured_lines" in out else {}))
                    except NoValue as e:
                        entry.update(verdict="not evaluated", by="auto", measured=str(e), limit=safe_limit(c, self.kind))
                        if isinstance(e, MissingRun):
                            entry["missing_run"] = {"experiment": e.experiment, "in": e.where}
                    except TOOL_ERRORS as e:
                        entry.update(verdict="tool error", by="auto", measured=f"{type(e).__name__}: {e}",
                                     limit=safe_limit(c, self.kind))
                    if m:
                        notes.append(f"{h['id']} {c['id']}: the manual verdict is not used, the check is automatic")
                why = self.waits_for(folder, [c.get("experiment")] + reads_experiments(c))
                if why:
                    entry["provisional"] = why
                out_checks.append(entry)
            hyps.append(hypothesis_entry(h, out_checks))
        self._hyps = {h["id"]: h["verdict"] for h in hyps}

        # central results
        ctx = Context(self, folder, data, hyps)
        results = []
        for cr in study.central_results:
            try:
                results.append(self.kind.central_result(cr, src, ctx))
            except NoValue as e:
                results.append({"id": cr["id"], "stat": cr.get("stat"), "texts": [], "rows": [],
                                "by": "auto", "not_evaluated": str(e),
                                **({"missing_run": {"experiment": e.experiment, "in": e.where}}
                                   if isinstance(e, MissingRun) else {})})
            except TOOL_ERRORS as e:
                results.append({"id": cr["id"], "stat": cr.get("stat"), "texts": [], "rows": [], "by": "auto",
                                "not_evaluated": f"tool error: {type(e).__name__}: {e}"})
        notes.extend(dict.fromkeys(src.notes))
        for cr, res in zip(study.central_results, results):
            frm = cr.get("from") or {}
            why = self.waits_for(folder, checks.as_list(frm.get("experiment")))
            if why:
                res["provisional"] = why
        waits = sorted({w for h in hyps for c in h["checks"] if c.get("provisional") for w in [c["provisional"]]}
                       | {r["provisional"] for r in results if r.get("provisional")})

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
        sj = {"format": self.kind.format_id("study", 2), "made_by": self.made_by,
              "instance": data["instance"],
              "design": {"folder": repo_rel(study.folder),
                         "safety_rev": self.made_by["safety_rev"], "files": study.files()},
              "board": self.board(folder),
              "instance_json_sha256": hashlib.sha256((ishas + "\n").encode()).hexdigest(),
              "question": " ".join(study.data.get("question", "").split()),
              "experiments": experiments,
              "acceptance": acceptance,
              "rebuild_checks": rebuilds,
              "state": {"final": not waits, "waits": waits},
              "hypotheses": hyps,
              "central_results": results,
              "notes": notes,
              "substudies": [{"instance": self.data[c]["instance"],
                              "study_json": str((c / "study.json").relative_to(folder))}
                             for c in self.folders if c.parent == folder]}
        self.results[folder] = sj
        self.writer.write(folder / "study.json", sj)

def reads_experiments(check):
    """The other experiments that a check reads (diff_to, within)."""
    out = []
    for v in (check.get("expect") or {}).values():
        if isinstance(v, dict) and v.get("experiment"):
            out.append(v["experiment"])
    return out


DRAFT = "draft"


def has_todo(x):
    """A TODO text that a template left, in a string of x (a check or a text)."""
    if isinstance(x, str):
        return "TODO" in x
    if isinstance(x, dict):
        return any(has_todo(v) for v in x.values())
    if isinstance(x, list):
        return any(has_todo(v) for v in x)
    return False


def hypothesis_entry(h, out_checks):
    verdicts = [c["verdict"] for c in out_checks]
    if not verdicts:
        verdicts = ["open (no checks)"]
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
    if any(c.get("provisional") for c in out_checks):
        out["provisional"] = True
    out["checks"] = out_checks
    return out


class Source:
    """The points that the checks of an instance can read."""

    def __init__(self, tree, folder, only_run=None):
        self.tree, self.folder, self.only_run = tree, folder, only_run
        self.kind = tree.kind
        self.notes = []

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
            if imp is None or imp.get("mode") == "rerun":
                # a re-run study reads its own runs only, never those of the owner
                raise MissingRun(exp, layout.ipath_display(t.ipath[self.folder]))
            folder = t.find_instance(imp["study"], t.board(self.folder))
            runs = t.own_runs(folder, exp)
            if not runs:
                raise MissingRun(exp, layout.ipath_display(t.ipath[folder]))
        return [o for r in runs for o in t.obs[(folder, r["id"])]]

    def run_obs(self, ref):
        """The points of a run, by "<study path>/<experiment>/<UTC>" (any role)."""
        parts = ref.split("/")
        study_path, run_id = "/".join(parts[:-2]), "/".join(parts[-2:])
        t = self.tree
        folder = t.find_instance(study_path, t.board(self.folder))
        entry = next((r for r in t.data[folder].get("runs", []) if r["id"] == run_id), None)
        if entry is None:
            raise NoValue(f"{layout.ipath_display(t.ipath[folder])} has no run {run_id}")
        if entry["role"] == "excluded" or t.failed_acceptance(folder, run_id):
            raise NoValue(f"reference run {run_id} is excluded or failed its acceptance checks")
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
        """The central result cr_id of the instance of the sub-study name below this instance; NoValue
        if this results tree has no such instance (often: no run of it on this board yet)."""
        for c in self.tree.folders:
            if c.parent == self.folder and self.tree.strip(self.tree.ipath[c]).rsplit("/", 1)[-1] == name:
                sj = self.tree.results.get(c)
                if sj:
                    r = next((r for r in sj["central_results"] if r["id"] == cr_id), None)
                    if r is None:
                        raise NoValue(f"the sub-study {name} has no central result {cr_id}")
                    return r
        raise NoValue(f"no instance of the sub-study {name} below {layout.ipath_display(self.tree.ipath[self.folder])} "
                      "in this results tree (no run of it here yet)")

    def axis_number(self, o, axis):
        exp = self.tree.design.run_experiment(o.run)
        e = self.tree.design.experiments.get(exp)
        if e is None:
            return None
        v = (e.data.get("axes") or {}).get(axis, {}).get(o.axes.get(axis))
        return v.get("value") if isinstance(v, dict) else None

    def owner_point(self, o):
        """The same point of the run of the owner study (for a re-run)."""
        exp = self.tree.design.run_experiment(o.run)
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


def design_root_of(results_root):
    """The design root of a results tree: the root of the Project that the field design.folder of the top
    instance.json names (a path below the repo). If the file has no such field, or the Project has no such
    root, the first root of the Project (the latency design)."""
    project = config.project()
    try:
        folder = load_json(Path(results_root) / "instance.json")["design"]["folder"]
    except (OSError, ValueError, KeyError, TypeError):
        return project.design_root
    wanted = (project.repo / folder).resolve()
    for r in project.roots:
        if r.path.resolve() == wanted:
            return r.path
    return project.design_root


def build(root, dry=False, log=print, pending=None, design_root=None):
    writer = Writer(dry=dry)
    t = Tree(root, writer=writer, log=log, pending=pending, design_root=design_root)
    t.build()
    return t, writer


def load_json(path):
    return json.loads(Path(path).read_text())
