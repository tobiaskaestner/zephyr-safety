# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The import of a TLC run from a lab folder into a results tree: `probatrix import-lab`.

A lab folder is what spec/tla/tools/run_tlc_remote.py leaves on the lab host (see tlc.py). The import never
changes it. It copies the raw files, and then does these steps in this order:

1. subject.json: the record of the revision of the run (subject.record), written into the copy.
2. The seal (core/seal.py) and the digest.
3. The role. A run is an evidence run if its subject tree and its tool tree are the trees of the current
   design (the design at the revision --rev, default HEAD), the conditions of an evidence run hold
   (tlc.evidence_reasons), and its lines are the lines of the design. Any other run is "historical", with a reason.
4. The git ref of the commit of the run (subject.pin), unless --no-pin.
5. The entry in the run list of the instance (instance.json): id <experiment>/<UTC>, digest, role,
   reason, copied_from. The lab id stays in run.json (lab_id).
6. run.json beside the run folder (the adapter tlc.run_json). The other aggregates come with `analysis build`.

The raw file set is fixed here (RAW_TOP, RAW_DIRS, SKIP_DIRS). Two imports of one lab folder give one digest:
the seal depends on the content of these files only (not on the time of the import, not on the name of the
results tree). The run id is the start time of the run in UTC.

The line check (check_lines) compares the lines of the run with the points of the experiment (kind.points):
lines that the run lacks, lines that the design lacks, and other expected results. It reports each difference.
"""

import datetime
import fcntl
import json
import shutil
import subprocess
from pathlib import Path

from probatrix.core import build, config, jsonout, layout, runner, seal
from probatrix.core.design import Design, repo_rel, repo_rev
from probatrix.tlaplus import kind as kindmod
from probatrix.tlaplus import subject, tlc

FORMAT = "tlaplus-instance/1"
ROLES = ("evidence", "historical", "excluded")
# The files of a lab folder that the import copies. pid and state are left out. So are the folders of
# model states and the temporary folders of TLC (SKIP_DIRS), which a failed or cancelled line can leave.
RAW_TOP = ("job.json", "meta.env", "results.txt", "job.log", "job.sh", "rss.txt")
RAW_DIRS = ("out", "selftest")
SKIP_DIRS = ("states", "tmp")
REQUIRED = ("job.json", "meta.env", "out/results.tsv")


class ImportLabError(Exception):
    """The lab folder cannot be imported (the text says why). Nothing is changed in the results tree."""


# ------------------------------------------------------------ the raw files
def raw_files(src):
    """The files of the lab folder that the import copies: a sorted list of paths relative to src."""
    src = Path(src)
    out = [Path(n) for n in RAW_TOP if (src / n).is_file()]
    for d in RAW_DIRS:
        for p in sorted((src / d).rglob("*")) if (src / d).is_dir() else []:
            rel = p.relative_to(src)
            if p.is_file() and not any(part in SKIP_DIRS for part in rel.parts[1:-1]):
                out.append(rel)
    return sorted(out)


def not_copied(src):
    """The files of the lab folder (top level and below) that the import leaves out, as relative path texts."""
    src = Path(src)
    copied = set(raw_files(src))
    return sorted(p.relative_to(src).as_posix() for p in src.rglob("*") if p.is_file()
                  and p.relative_to(src) not in copied)


def copy_raw(src, dst):
    """Copy the raw files of src into the new folder dst. Return the list of the relative paths."""
    files = raw_files(src)
    for rel in files:
        (dst / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src / rel, dst / rel)
    return files


def utc_id(meta, job):
    """The run name <UTC> from the start time of the run (meta.env start, else job.json submitted)."""
    text = meta.get("start") or job.get("submitted")
    if not text:
        raise ImportLabError("meta.env has no start time and job.json has no submitted time")
    try:
        t = datetime.datetime.fromisoformat(text)
    except ValueError:
        raise ImportLabError(f"the start time {text!r} is not an ISO time") from None
    if t.tzinfo is None:
        raise ImportLabError(f"the start time {text!r} has no time zone")
    return t.astimezone(datetime.timezone.utc).strftime(runner.UTC_FORMAT)


# ------------------------------------------------------------ the design
def formal_root(results):
    """The design root for a results tree: the one its top instance.json names, else the root of the kind tlaplus."""
    project = config.project()
    if (Path(results) / "instance.json").is_file():
        return build.design_root_of(results)
    for r in project.roots:
        if r.kind == kindmod.KIND.name:
            return r.path
    raise ImportLabError("the Project has no design root of the kind tlaplus")


def experiment_of(design, job, name=None):
    """The experiment of a lab run: the name that is given, else the one whose list file is the list that the
    run used (job.json list: the file name without .txt)."""
    if name is not None:
        try:
            return design.experiment(name)
        except Exception:
            raise ImportLabError(f"the design has no experiment {name!r} "
                                 f"(it has: {', '.join(sorted(design.experiments))})") from None
    want = job.get("list", "expected")
    hits = [e for e in design.experiments.values() if Path(e.data["list"]).stem == want]
    if len(hits) != 1:
        raise ImportLabError(f"the run used the list {want!r}; {len(hits)} experiments of the design have it: "
                             "give the experiment with --experiment")
    return hits[0]


def check_study(design, experiment, study_path):
    """The study for the run: the given one (it owns the experiment or runs it again), else the owner."""
    if study_path is None:
        return experiment.study
    study = design.studies.get(study_path)
    if study is None:
        raise ImportLabError(f"the design has no study {study_path!r}")
    rerun = {i["experiment"] for i in study.imports if i.get("mode") == "rerun"}
    if experiment.name not in study.experiments and experiment.name not in rerun:
        raise ImportLabError(f"the study {study_path!r} has not the experiment {experiment.name!r}, "
                             "and it does not run it again")
    return study_path


# ------------------------------------------------------------ the instance folders
def design_ref(study):
    rev, _ = repo_rev()
    return {"folder": repo_rel(study.folder), "safety_rev": rev, "files": study.files()}


def ensure_instances(design, results, study_path):
    """Make the instance folders (instance.json) from the top down to the study. Return the folder of the study."""
    results = Path(results)
    top = results.name
    names = [n for n in study_path.split("/") if n]
    folder, spath, ipath = results, "", ""
    chain = [(folder, spath, ipath)]
    for n in names:
        spath = f"{spath}/{n}" if spath else n
        ipath = f"{ipath}/{n}" if ipath else n
        folder = folder / (layout.STUDY_PREFIX + n)
        chain.append((folder, spath, ipath))
    for folder, spath, ipath in chain:
        folder.mkdir(parents=True, exist_ok=True)
        if not (folder / "instance.json").exists():
            save(folder, {"format": FORMAT, "instance": f"{top}/{ipath}" if ipath else top,
                          "design": design_ref(design.study(spath)), "runs": [], "references": [],
                          "substudies": [], "manual_verdicts": [], "notes": []})
    for f in layout.instance_folders(results):
        subs = sorted(layout.load_instance(c)["instance"] for c in f.iterdir()
                      if c.is_dir() and (c / "instance.json").is_file())
        data = layout.load_instance(f)
        if subs != data["substudies"]:
            data["substudies"] = subs
            save(f, data)
    return chain[-1][0]


def save(folder, data):
    return jsonout.write(Path(folder) / "instance.json", data)


def locked(folder):
    """An flock on the instance folder for a read-change-write of instance.json."""
    import contextlib

    @contextlib.contextmanager
    def lock():
        f = open(Path(folder) / ".instance.lock", "a")
        try:
            fcntl.flock(f, fcntl.LOCK_EX)
            yield
        finally:
            f.close()
    return lock()


# ------------------------------------------------------------ the line check and the role
def check_lines(raw, experiment):
    """Compare the lines of the run (the rows of results.tsv) with the points of the experiment.

    Return {"run_list": the list that the run used, "missing": [ids of the design that the run lacks],
    "extra": [ids of the run that the design lacks], "expected": [(id, expected in the run, expected in the
    design)], "same": True if there is no difference}. The order of the lines does not count.
    """
    design = {p["id"]: p["expected"] for p in kindmod.KIND.points(experiment)}
    ran = {tlc.point_id(r): r["expected"] for r in raw.rows}
    got = {"run_list": raw.job.get("list", "expected"),
           "missing": [i for i in design if i not in ran],
           "extra": [i for i in ran if i not in design],
           "expected": [(i, ran[i], design[i]) for i in ran if i in design and ran[i] != design[i]]}
    got["same"] = not (got["missing"] or got["extra"] or got["expected"]
                       or got["run_list"] != Path(experiment["list"]).stem)
    return got


def describe_lines(lines, experiment, detail=True):
    """The lines of the report for a line check: one text for each difference (detail: with the first ids)."""
    out = []
    stem = Path(experiment["list"]).stem
    if lines["run_list"] != stem:
        out.append(f"the run used the list {lines['run_list']!r}, the experiment has {stem!r}")
    for key, text in (("missing", "lines of the design that the run lacks"),
                      ("extra", "lines of the run that the design lacks")):
        if lines[key]:
            names = f": {', '.join(lines[key][:5])}{' ...' if len(lines[key]) > 5 else ''}" if detail else ""
            out.append(f"{len(lines[key])} {text}{names}")
    if lines["expected"]:
        i, was, now = lines["expected"][0]
        first = f" (first: {i}: run {was}, design {now})" if detail else ""
        out.append(f"{len(lines['expected'])} lines with another expected result{first}")
    return out


def differing(run, now):
    """The paths whose object ids differ between the tree of the run and the current tree, as texts (a path that
    the revision of the run lacks is marked)."""
    return sorted(p.removeprefix("spec/tla/") + (" (not in the revision of the run)" if run.get(p) is None else "")
                  for p in {*run, *now} if run.get(p) != now.get(p))


# ------------------------------------------------------------ the import
def import_lab(src, results, experiment=None, study=None, rev="HEAD", copied_from=None, pin=True, say=print):
    """Import the lab folder src into the results tree results. Return a dict: id, digest, role, reason,
    run_dir, lines (the result of check_lines), notes. ImportLabError if the folder cannot be imported."""
    src, results = Path(src).resolve(), Path(results).resolve()
    if not src.is_dir():
        raise ImportLabError(f"{src}: no such folder")
    for need in REQUIRED:
        if not (src / need).is_file():
            raise ImportLabError(f"{src}: no {need} (is the lab run finished?)")
    try:
        job = json.loads((src / "job.json").read_text())
    except ValueError as e:
        raise ImportLabError(f"{src}/job.json: {e}") from None
    meta = tlc.read_meta((src / "meta.env").read_text())
    if "end" not in meta:
        raise ImportLabError(f"{src}: meta.env has no end time: the lab run is not finished")
    if job.get("tool", "tlc") not in tlc.TOOLS:
        raise ImportLabError(f"{src}: the tool {job.get('tool')!r} has no adapter (tlc.py: {', '.join(tlc.TOOLS)})")
    utc = utc_id(meta, job)
    design = Design(formal_root(results))
    exp = experiment_of(design, job, experiment)
    if exp.data["tool"] != job.get("tool", "tlc"):
        raise ImportLabError(f"the run has the tool {job.get('tool', 'tlc')!r}, the experiment {exp.name!r} "
                             f"has {exp.data['tool']!r}")
    study_path = check_study(design, exp, study)
    run_id = f"{exp.name}/{utc}"
    repo = config.project().repo
    copied_from = copied_from or str(src)

    # the records of the revision of the run and of the current design (before any change)
    try:
        record = subject.record(job["revision"], exp.data, repo, missing_ok=True)
        current = subject.record(rev, exp.data, repo)
    except (subject.SubjectError, KeyError) as e:
        raise ImportLabError(f"the subject of the run cannot be read: {e}") from None
    notes = []
    dirty = subprocess.run(["git", "status", "--porcelain", "--", *exp.data["subject"], *exp.data["tools"]],
                           cwd=repo, capture_output=True, text=True).stdout.strip()
    if dirty and rev == "HEAD":
        notes.append("the files of the subject have changes that are not committed: "
                     "the line check reads the working tree, the trees are those of HEAD")

    folder = ensure_instances(design, results, study_path)
    data = layout.load_instance(folder)
    run_dir = folder / layout.run_folder(run_id)
    for r in data["runs"]:
        if r["id"] == run_id:
            if r.get("copied_from") == copied_from or r.get("lab_id") == job.get("run_id"):
                say(f"already imported: {run_id}  ({r['digest']})")
                return {"id": run_id, "digest": r["digest"], "role": r["role"], "reason": r.get("reason"),
                        "run_dir": run_dir, "lines": None, "notes": notes, "already": True,
                        "experiment": exp.data}
            raise ImportLabError(f"{run_id} is in the run list from another lab folder ({r.get('copied_from')})")
    if run_dir.exists():
        raise ImportLabError(f"{run_dir} exists and is not in the run list")

    # copy, subject.json, seal: a failure before the seal leaves no folder
    stage = run_dir.parent / f".{utc}.import"
    if stage.exists():
        shutil.rmtree(stage)
    try:
        copy_raw(src, stage)
        jsonout.write(stage / subject.FILE, record)
        raw = tlc.Raw(stage)
        lines = check_lines(raw, exp.data)
        stage.rename(run_dir)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    say(f"{runner.RUN_FOLDER_LINE}{run_dir}")
    digest = runner.finish(run_dir, say=say)
    raw = tlc.Raw(run_dir)

    role, reason = assign_role(record, current, raw, lines, exp.data)
    if pin:
        say(f"commit {record['revision'][:12]} kept by {subject.pin(repo, record['revision'], exp.name, utc)}")
    entry = {"id": run_id, "digest": digest, "role": role}
    if reason:
        entry["reason"] = reason
    entry["copied_from"] = copied_from
    entry["lab_id"] = job.get("run_id")
    with locked(folder):
        data = layout.load_instance(folder)
        data["runs"].append(entry)
        save(folder, data)
    say(f"run {run_id} added to the instance {folder}")
    rj = tlc.run_json(run_dir, run_id, digest, {"tool": kindmod.KIND.tool, "safety_rev": repo_rev(kind=kindmod.KIND)[0]},
                      exp.folder / "experiment.yaml")
    jsonout.write(run_dir.parent / f"{run_dir.name}.run.json", rj)
    return {"id": run_id, "digest": digest, "role": role, "reason": reason, "run_dir": run_dir, "lines": lines,
            "notes": notes, "already": False, "experiment": exp.data}


def assign_role(record, current, raw, lines, experiment):
    """(role, reason or None): see the module text."""
    why = []
    if record["subject_tree"] != current["subject_tree"]:
        why.append(f"the subject tree differs from the design at {current['revision'][:9]}: "
                   + ", ".join(differing(record["subject"], current["subject"])))
    if record["tool_tree"] != current["tool_tree"]:
        why.append(f"the tool tree differs from the design at {current['revision'][:9]}: "
                   + ", ".join(differing(record["tools"], current["tools"])))
    ev, reasons = tlc.evidence_of(raw)
    if not ev:
        why.append("not an evidence run: " + "; ".join(reasons))
    why += describe_lines(lines, experiment, detail=False)
    return ("historical", "; ".join(why)) if why else ("evidence", None)


# ------------------------------------------------------------ the command
def report(res, say=print):
    """The lines of the report of an import (the result of import_lab)."""
    if res.get("already"):
        return
    say(f"role {res['role']}" + (f": {res['reason']}" if res["reason"] else ""))
    diffs = describe_lines(res["lines"], res["experiment"])
    say("line check: " + ("the lines of the run are the lines of the design" if not diffs else
                          f"{len(diffs)} difference(s)"))
    for d in diffs:
        say(f"  {d}")
    for n in res["notes"]:
        say(f"note: {n}")


def cmd_import_lab(args):
    res = import_lab(args.lab_run, args.results, experiment=args.experiment, study=args.study, rev=args.rev,
                     copied_from=args.copied_from, pin=not args.no_pin)
    if not res["already"]:
        report(res)
        skipped = not_copied(args.lab_run)
        print(f"not copied: {', '.join(skipped) if skipped else 'nothing'}")
        print(f"next: probatrix analysis build {Path(args.results)}")
    return 0


def add_import_lab(sub):
    """Add the command import-lab to the subparsers sub."""
    s = sub.add_parser("import-lab", help="copy a TLC run of a lab folder into a results tree (the folder stays as it is)")
    s.add_argument("lab_run", metavar="LAB-RUN-FOLDER", help="runs/<lab id> of the lab host (or a copy of it)")
    s.add_argument("--results", required=True, metavar="DIR",
                   help="the results tree (its folder name is the name of the top instance); it is made if missing")
    s.add_argument("--experiment", help="the experiment (default: the one whose list the run used)")
    s.add_argument("--study", help="the study path for the run (default: the study that owns the experiment)")
    s.add_argument("--rev", default="HEAD", help="the revision of the current design (default HEAD)")
    s.add_argument("--copied-from", metavar="TEXT", help="what the run list records as the source "
                   "(default: the path of the folder; use host:path for a lab folder)")
    s.add_argument("--no-pin", action="store_true", help="do not make the git ref of the commit of the run")
    s.set_defaults(func=cmd_import_lab)


COMMANDS = {"import-lab": add_import_lab}
ERRORS = (ImportLabError, subject.SubjectError)
