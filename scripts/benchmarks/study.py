#!/usr/bin/env python3
# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Study designs, lab spaces, campaigns and the aggregates of a results tree.

Design (validation/empirical/latencies):
    study.py design lint [FOLDER] [--warn-as-error]
                                          the problems of the design files; exit 1
                                          on an error (or a warning with the flag)
    study.py design scaffold study PARENT/st-NAME
                                          a new study (no experiments yet)
    study.py design scaffold experiment STUDY/ex-NAME --app APP [--board B]
                                          a new experiment of a study

Lab space (a folder with .lab/config, see studylib/lab.py):
    study.py lab init [FOLDER] --repo REPO [--name N] [--trees-root DIR] [--trees-source DIR]
                      [--sdk DIR] [--results DIR] [--hw-map FILE]
                                          make a lab space (default: the current folder);
                                          the venv of the Python that runs it is the
                                          Python of the lab space
    study.py lab status                   the lab space, its trees, boards and campaigns
    study.py lab hwcheck BOARD            the loopback wire check of a board
    study.py lab export [FOLDER] -o FILE [--campaign ID ...] [--all]
                                          the runs of this lab space (or of the campaigns,
                                          or all runs) to FILE and FILE.sha256
    study.py lab import FILE [--dry-run]  the runs of another lab space, after the
                                          consistency checks (studylib/exchange.py)
    study.py lab import --close ID@LAB    end an imported campaign that never gets its end

Campaigns (FOLDER: a design study or experiment folder, or an instance folder):
    study.py campaign prepare FOLDER [--board B] [--only EXP ...] [--skip EXP ...]
                                          build the images of all points (build cache)
    study.py campaign check FOLDER [...] [--no-hwcheck] [--warn-as-error]
                                          the pre-flight check
    study.py campaign run FOLDER [...] [--no-hwcheck] [--detach] [--warn-as-error]
                      [--role R --reason TEXT] [--hwcheck-each]
                                          check, then run each experiment and add each
                                          run to its instance (role R, default evidence);
                                          build the results after each run in the background
    study.py campaign status [ID]         the record of a campaign (default: the latest)
    study.py campaign resume ID [--detach]
                                          run the experiments of a campaign that are not done

Pinned trees (validation/trees/<tree>.yml, west manifests; paths from the lab space):
    study.py trees setup [TREE ...]       make the west workspace of each tree
    study.py trees check [TREE ...]       ok, not set up (information) or wrong (exit 1)
    study.py trees show [TREE ...]

Instances (the run lists in a results tree):
    study.py instance new RESULTS STUDY --board B
                                          make the instance folders of a study
                                          (and of its sub-studies) for a board;
                                          STUDY "." is the top study
    study.py instance add INSTANCE RUN [--role R --reason TEXT] [--copy]
                                          add a run to the run list of an instance;
                                          --copy copies a run from another place
    study.py instance exclude ROOT --campaign ID --reason TEXT
                                          give all runs of a campaign the role excluded
    study.py instance reference INSTANCE OTHER RUN_ID --reason TEXT
                                          add a run of another instance as a reference
    study.py instance verdict INSTANCE --verdict V --by NAME [--text T]
                     (--hypothesis H --check C | --central-result ID)
                                          set a manual verdict (confirmed, wrong);
                                          a proposal says so in --by
    study.py instance merge OTHER ROOT [--origin HOST:PATH]
                                          add the runs of another results tree that
                                          is not a lab space (a copy of it) that
                                          ROOT does not have, with their roles
    study.py instance seal RUN ...        write the seal <UTC>.sha256 of old runs
    study.py instance verify RUN ...      check runs against their seals

Analysis (ROOT is any folder of a results tree):
    study.py analysis build ROOT          write run.json, the app data,
                                          experiment.json and study.json
    study.py analysis check ROOT          check all seals, build again and compare
    study.py analysis show FOLDER [--details]
                                          the verdicts of the instances at and below
                                          FOLDER: one line each, or each check
    study.py analysis missing [FOLDER]    the experiments without an evidence run, and
                                          the checks and central results that wait
    study.py analysis show ROOT --explain [ID ...]
                                          how each central result is made: its
                                          definition, the rows and the sentences
    study.py analysis notebooks FOLDER [--force]
                                          run the notebooks of the studies (*.ipynb of the
                                          design) against the instances: notebooks/*.html
    study.py analysis html FOLDER        index.html in each instance folder (with links to
                                          the parents and the sub-studies) and in each
                                          experiment folder (plots, runs) at and below FOLDER

In a lab space, the tools of the design repo of the lab space run: another
study.py starts the study.py of that repo with the same arguments.
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# The lab space and the restart come first: studylib.lab needs no package outside the standard
# library, so a study.py that the system Python starts can restart with the Python of the lab
# space before it imports PyYAML and the other packages.
from studylib import lab as labmod  # noqa: E402

REEXEC_ENV = "LATBENCH_STUDY_REEXEC"


def reexec_in_lab_repo(argv):
    """Run the study.py of the design repo of the lab space with the Python of the lab space (its
    venv, [python] of .lab/config), if this is another study.py or another Python."""
    if os.environ.get(REEXEC_ENV) or (argv[:2] == ["lab", "init"]):
        return
    lab = labmod.find()
    if lab is None:
        return
    target = lab.repo / "scripts" / "benchmarks" / "study.py"
    python = lab.python
    same_script = target.resolve() == Path(__file__).resolve()
    # a venv Python is a link to the base Python: compare the environments, not the files
    same_python = python is None or (lab.venv is not None and Path(sys.prefix).resolve() == lab.venv.resolve())
    if same_script and same_python:
        return
    if not target.is_file():
        sys.exit(f"error: the lab space {lab.folder} has the design repo {lab.repo}, which has no {target}")
    if python is not None and not python.exists():
        sys.exit(f"error: the lab space {lab.folder} has the Python environment {lab.venv}, which has no {python}")
    exe = str(python) if python is not None else sys.executable
    os.environ[REEXEC_ENV] = str(Path(__file__).resolve())
    os.execv(exe, [exe, str(target), *argv])


if __name__ == "__main__":
    reexec_in_lab_repo(sys.argv[1:])

import trees  # noqa: E402
from studylib import build, html, instance, layout, seal  # noqa: E402
from studylib import campaign, lint, scaffold  # noqa: E402
from studylib.design import Design, DesignError  # noqa: E402

# ------------------------------------------------------------ design
def cmd_lint(args):
    problems = lint.lint(only=args.folder)
    for p in problems:
        print(p)
    errors = sum(p.severity == lint.ERROR for p in problems)
    warnings = len(problems) - errors
    print(f"{errors} errors, {warnings} warnings")
    return 1 if errors or (warnings and args.warn_as_error) else 0


def cmd_scaffold(args):
    if args.kind == "study":
        folder = scaffold.scaffold_study(args.path)
    else:
        folder = scaffold.scaffold_experiment(args.path, args.app, args.board)
    for f in sorted(folder.rglob("*")):
        if f.is_file():
            print(f"new {f}")
    print("replace the TODO texts; 'study.py design lint' lists them")


# ------------------------------------------------------------ lab
def cmd_lab_init(args):
    lab = labmod.init(args.folder, args.repo, name=args.name, trees_root=args.trees_root,
                      trees_source=args.trees_source, sdk=args.sdk, results=args.results, hw_map=args.hw_map)
    print(f"lab space {lab.id} in {lab.folder}")
    print(f"  design repo  {lab.repo}")
    if lab.venv is not None:
        print(f"  python       {lab.venv} (the Python of lab init)")
    else:
        print(f"  python       WARNING: lab init runs without a virtual environment ({sys.executable}); "
              f"make one with {lab.repo}/scripts/benchmarks/requirements.txt and run lab init with its Python")
    for p in labmod.package_problems(lab.repo):
        print(f"  WARNING      {p}")
    print(f"  trees        {lab.trees_root}" + (f" (clone from {lab.trees_source})" if lab.trees_source else ""))
    print(f"  results      {lab.results}")
    print(f"  hardware map {lab.hw_map}" + ("" if lab.hw_map.is_file() else " (missing: make it with twister)"))
    print(f"next: cd {lab.folder} && {lab.repo}/scripts/benchmarks/study.py trees setup <tree>")


def cmd_lab_status(args):
    import hwmap
    lab = labmod.require()
    rev, dirty = trees.repo_state(lab.repo)
    print(f"lab space {lab.id} in {lab.folder}")
    print(f"  design repo  {lab.repo} at {rev[:12]}{' (dirty)' if dirty else ''}")
    print(f"  python       {sys.executable} ({lab.venv or 'no venv in .lab/config'})")
    for p in labmod.package_problems(lab.repo):
        print(f"  WARNING      {p}")
    cfg = trees.load(lab=lab)
    try:
        sdk = trees.check_toolchain(cfg)
        print(f"  zephyr sdk   {sdk} ({cfg['toolchain']['zephyr_sdk']['version']})")
    except trees.TreeError as e:
        print(f"  zephyr sdk   {e}")
    for t in cfg["trees"]:
        state, text = trees.tree_state(cfg, t)
        print(f"  tree {t:20} {state}" + (f": {text}" if state == "wrong" else ""))
    print(f"  results      {lab.results}")
    if lab.hw_map.is_file():
        try:
            for e in hwmap.load(lab.hw_map):
                print(f"  board        {' '.join(hwmap.platforms(e))}: {'connected' if e.get('connected') else 'not connected'}"
                      f", fixtures {', '.join(hwmap.fixture_names(e)) or '-'}")
        except hwmap.HwMapError as e:
            print(f"  hardware map {e}")
    else:
        print(f"  hardware map {lab.hw_map} is missing")
    recs = campaign.records(lab)
    open_imports = [r for r in recs if "@" in r.id and (r.data or {}).get("status") in ("planned", "running")]
    for rec in [r for r in recs if "@" not in r.id][-3:] + open_imports:
        print("  " + campaign.status_lines(rec)[0])


def cmd_lab_hwcheck(args):
    from studylib import hwcheck
    lab = labmod.require()
    try:
        ok, lines = hwcheck.check(lab, args.board, tree=args.tree)
    except hwcheck.HwCheckError as e:
        print(f"error: {e}")
        return 2
    for ln in lines:
        print("  " + ln)
    print(f"{args.board}: loopback wire {'ok' if ok else 'FAILED'}")
    return 0 if ok else 1


def cmd_lab_export(args):
    from studylib import exchange
    exchange.export(labmod.require(), args.out, args.folder, args.campaign, args.all)


def cmd_lab_import(args):
    from studylib import exchange
    lab = labmod.require()
    if args.close:
        exchange.close_import(lab, args.close)
        print(f"{args.close}: closed (its experiments do not make verdicts provisional any more)")
        return 0
    if not args.file:
        raise exchange.ExchangeError("give the export file (or --close <id>@<lab id>)")
    added, skipped, refused, warnings = exchange.import_(lab, args.file, dry=args.dry_run)
    if added and not args.dry_run:
        print(f"next: study.py analysis build {lab.results / Design().top.name}")
    return 1 if refused else 0


# ------------------------------------------------------------ campaign
def cmd_campaign_prepare(args):
    lab = labmod.require()
    items = [e for e in campaign.plan(lab, args.folder, args.board, args.only, args.skip) if e["state"] != "skipped"]
    log = lab.folder / ".lab" / "prepare.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    bad = 0
    for e in items:
        print(f"=== {e['experiment']}", flush=True)
        rc = campaign.run_subprocess([sys.executable, campaign.run_py(), trees.REPO_DIR / e["design"], "--build-only"],
                                     log, cwd=lab.folder)
        print(f"    {'ok' if rc == 0 else f'FAILED (rc {rc}, see {log})'}", flush=True)
        bad += rc != 0
    print(f"{len(items) - bad} of {len(items)} experiments build")
    return 1 if bad else 0


def cmd_campaign_check(args):
    lab = labmod.require()
    items = campaign.plan(lab, args.folder, args.board, args.only, args.skip)
    design = Design()
    for e in items:
        where = ""
        if e["state"] != "skipped":
            f, exists = campaign.planned_instance(lab, design, e["study"], e["board"])
            where = f" -> {f.relative_to(lab.results)} ({'exists' if exists else 'will be made'})"
        print(f"  {e['state']:8} {e['experiment']} ({e['study']}, {e['board']}){where}"
              + (f": {e['note']}" if e.get("note") else ""))
    res = campaign.preflight(lab, items, design, hwcheck=not args.no_hwcheck, warn_as_error=args.warn_as_error)
    bad = [w for st, w, _ in res if st == "fail"]
    print("pre-flight check: " + ("ok" if not bad else f"FAILED ({', '.join(bad)})"))
    return 1 if bad else 0


def campaign_extra(args):
    return [*(["--no-hwcheck"] if args.no_hwcheck else []), *(["--warn-as-error"] if args.warn_as_error else [])]


def cmd_campaign_run(args):
    lab = labmod.require()
    items = campaign.plan(lab, args.folder, args.board, args.only, args.skip)
    rec = campaign.new_record(lab, args.folder, args.board, items, ["study.py", *sys.argv[1:]],
                              role=args.role, reason=args.reason, hwcheck_each=args.hwcheck_each)
    print(f"campaign {rec.id}: {sum(e['state'] == 'planned' for e in items)} experiments, record {rec.path}")
    if args.detach:
        pid, log = campaign.detach(rec, campaign_extra(args))
        print(f"runs in the background (pid {pid}); log {log}; 'study.py campaign status {rec.id}'")
        return 0
    return 1 if campaign.run_campaign(rec, hwcheck=not args.no_hwcheck, warn_as_error=args.warn_as_error) else 0


def cmd_campaign_resume(args):
    lab = labmod.require()
    rec = campaign.Record(lab, args.id)
    if rec.data is None:
        raise campaign.CampaignError(f"no campaign {args.id} in {lab.campaigns}")
    if args.detach:
        pid, log = campaign.detach(rec, campaign_extra(args))
        print(f"runs in the background (pid {pid}); log {log}")
        return 0
    return 1 if campaign.run_campaign(rec, hwcheck=not args.no_hwcheck, warn_as_error=args.warn_as_error) else 0


def cmd_campaign_status(args):
    lab = labmod.require()
    rec = campaign.Record(lab, args.id) if args.id else campaign.latest(lab)
    if rec is None or rec.data is None:
        print(f"no campaign in {lab.campaigns}")
        return 1
    for ln in campaign.status_lines(rec):
        print(ln)
    root = lab.results / Design().top.name
    if root.is_dir() and args.verdicts:
        res = {}
        for e in rec.data["experiments"]:
            if e.get("instance"):
                f = lab.results / e["instance"]
                if (f / "study.json").is_file():
                    res[f] = build.load_json(f / "study.json")
        show(res, root)
    return 0


# ------------------------------------------------------------ trees
def cmd_trees(args):
    return trees.main(args)


# ------------------------------------------------------------ instance
def cmd_instance_new(args):
    d = Design()
    path = "" if args.study in (".", "") else args.study
    folder = instance.new(d, args.results, d.top.name, path, args.board)
    print(folder)


def cmd_instance_add(args):
    d = Design()
    rid = instance.add(d, args.instance, args.run, args.role, args.reason, args.copy)
    print(f"added {rid} to {args.instance}")


def cmd_instance_exclude(args):
    changed = instance.exclude_campaign(layout.find_root(args.root), args.campaign, args.reason)
    for folder, rid in changed:
        print(f"excluded {rid} in {folder}")
    print(f"{len(changed)} runs of the campaign {args.campaign} excluded")
    return 0 if changed else 1


def cmd_instance_reference(args):
    instance.add_reference(args.instance, args.other, args.run_id, args.reason)
    print(f"reference {args.run_id} added to {args.instance}")


def cmd_instance_verdict(args):
    instance.add_verdict(args.instance, args.verdict, args.by, args.text, args.hypothesis, args.check,
                         args.central_result)
    print(f"verdict set in {args.instance}")


def cmd_instance_merge(args):
    added = instance.merge(Design(), layout.find_root(args.other), layout.find_root(args.root),
                           origin=args.origin)
    print(f"{len(added)} runs added")


# ------------------------------------------------------------ seals and analysis
def cmd_seal(args):
    for r in args.runs:
        print(seal.write(r), r)


def cmd_verify(args):
    bad = 0
    for r in args.runs:
        try:
            print(seal.verify(r), r)
        except seal.SealError as e:
            print(f"FAIL {e}")
            bad += 1
    return 1 if bad else 0


def results_lock(root):
    """The lock of the results build of the lab space that owns root (a no-op outside a lab space)."""
    import contextlib
    owner = labmod.owner(root)
    return campaign.results_lock(owner) if owner else contextlib.nullcontext()


def cmd_build(args):
    root = layout.find_root(args.root)
    with results_lock(root):
        t, w = build.build(root)
    print(f"built {len(t.results)} instances, {len(t.loaded)} runs; {w.written} files written")
    if t.made_by.get("dirty"):
        print("WARNING: the safety repo has changes that are not committed: the aggregates are not reproducible")
    show(t.results, root)


def cmd_check(args):
    root = layout.find_root(args.root)
    t, w = build.build(root, dry=True)
    if w.differ:
        print(f"FAIL: {len(w.differ)} files differ from a new build:")
        for p in w.differ[:50]:
            print("  ", p)
        return 1
    print(f"ok: {len(t.loaded)} runs agree with their seals; the build gives the same {len(t.results)} study.json files")
    return 0


def failed_runs(folder):
    """[(run id, step, error)] of the runs of an instance that stopped before their seal."""
    out = []
    for f in sorted(Path(folder).glob(f"{layout.EXPERIMENT_PREFIX}*/*.failed.json")):
        try:
            d = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        out.append((f"{f.parent.name[len(layout.EXPERIMENT_PREFIX):]}/{f.name.split('.')[0]}", d.get("step"),
                    d.get("error")))
    return out


def summary_line(sj, folder):
    """One line of an instance: the verdicts in numbers."""
    hv = [h["verdict"].split(" ")[0] for h in sj["hypotheses"]]
    checks = [c["verdict"] for h in sj["hypotheses"] for c in h["checks"]]
    crs = sj["central_results"]
    parts = []
    if hv:
        parts.append(f"H {hv.count('confirmed')} confirmed, {hv.count('wrong')} wrong, "
                     f"{len(hv) - hv.count('confirmed') - hv.count('wrong')} open"
                     + (f" ({checks.count(build.DRAFT)} draft checks)" if build.DRAFT in checks else ""))
    if crs:
        parts.append(f"central {sum(1 for c in crs if not c.get('not_evaluated'))} of {len(crs)}")
    bad_acc = sum(1 for a in sj.get("acceptance", []) for c in a["checks"] if c["verdict"] != "confirmed")
    if bad_acc:
        parts.append(f"{bad_acc} acceptance checks not confirmed")
    if sj.get("notes"):
        parts.append(f"{len(sj['notes'])} notes")
    nf = len(failed_runs(folder))
    if nf:
        parts.append(f"{nf} failed runs")
    if not sj.get("state", {}).get("final", True):
        parts.append("PROVISIONAL")
    return f"{layout.display(sj['instance'])}: " + ("; ".join(parts) if parts else "no hypotheses, no central results")


def show(results, root, details=False):
    """The verdicts of the instances: one line each, or (details) each check and central result."""
    for folder, sj in sorted(results.items(), key=lambda x: str(x[0])):
        if not details:
            print(summary_line(sj, folder))
            continue
        hyps = sj["hypotheses"]
        crs = sj["central_results"]
        print(f"\n== {layout.display(sj['instance'])}")
        for n in sj.get("notes", []):
            print(f"   NOTE {n}")
        for rid, step, error in failed_runs(folder):
            print(f"   FAILED RUN {rid} at '{step}': {error} (not in the run list)")
        for a in sj.get("acceptance", []):
            bad = [c for c in a["checks"] if c["verdict"] != "confirmed"]
            if bad:
                print(f"   acceptance {a['run']}: " + ", ".join(f"{c['id']} {c['verdict']}" for c in bad))
        if not sj.get("state", {}).get("final", True):
            print(f"   PROVISIONAL: {'; '.join(sj['state']['waits'])}")
        for h in hyps:
            print(f"   {h['id']} {h['verdict']}{' (provisional)' if h.get('provisional') else ''} ({h['checks_confirmed']})")
            for c in h["checks"]:
                if c["verdict"] == "open (manual)":
                    print(f"      {c['id']} open (manual): {c.get('statement') or '(no statement)'}")
                    print(f"         give the verdict: study.py instance verdict {folder} --hypothesis {h['id']} "
                          f"--check {c['id']} --verdict confirmed|wrong --by NAME --text WHY")
                else:
                    print(f"      {c['id']} {c['verdict']}: {c.get('measured', '')[:160]}")
        for c in crs:
            if c.get("not_evaluated"):
                print(f"   [{c['id']}] not evaluated: {c['not_evaluated'][:160]}")
            else:
                for t in c.get("texts", [])[:50]:
                    print(f"   [{c['id']}] {t}")


def missing(results):
    """{(instance display, experiment): [waiting items]} of the checks and central results that wait
    for an evidence run (the lowest level only: a parent that takes a result over is not counted)."""
    out = {}
    for folder, sj in sorted(results.items(), key=lambda x: str(x[0])):
        top = layout.display(sj["instance"]).split("/", 1)[0]
        for h in sj["hypotheses"]:
            for c in h["checks"]:
                m = c.get("missing_run")
                if m:
                    key = (f"{top}/{m['in']}" if m["in"] != "(top)" else top, m["experiment"])
                    out.setdefault(key, []).append(f"{h['id']} {c['id']}")
        for c in sj["central_results"]:
            m = c.get("missing_run")
            if m:
                key = (f"{top}/{m['in']}" if m["in"] != "(top)" else top, m["experiment"])
                out.setdefault(key, []).append(f"[{c['id']}]")
    # a parent that takes a central result over has the same entry: count it once
    return {k: list(dict.fromkeys(v)) for k, v in out.items()}


def explain(results, design, only=None):
    """For each central result: its definition, the rows of the build and the sentence of each row."""
    for folder, sj in sorted(results.items(), key=lambda x: str(x[0])):
        try:
            study = design.study(layout.strip_board(sj["instance"].split("/", 1)[1]) if "/" in sj["instance"] else "")
        except DesignError:
            continue
        defs = {c["id"]: c for c in study.central_results}
        for c in sj["central_results"]:
            if only and c["id"] not in only:
                continue
            d = defs.get(c["id"], {})
            print(f"\n== {layout.display(sj['instance'])} [{c['id']}]")
            for k in ("statement", "from", "stat", "group_by"):
                if k in d:
                    v = " ".join(d[k].split()) if isinstance(d[k], str) else d[k]
                    print(f"   {k}: {v}")
            if c.get("not_evaluated"):
                print(f"   not evaluated: {c['not_evaluated']}")
                continue
            rows = c.get("rows", [])
            for i, t in enumerate(c.get("texts", [])):
                if i < len(rows):
                    print("   row: " + ", ".join(f"{k}={v:.4g}" if isinstance(v, float) else f"{k}={v}"
                                               for k, v in rows[i].items()))
                print(f"     -> {t}")
            if c.get("unfilled"):
                print(f"   unfilled placeholders: {c['unfilled']} (no such value in the rows)")


def load_results(folder):
    """{instance folder: study.json} of the instances at and below folder (a folder of a results tree)."""
    root = layout.find_root(folder)
    below = Path(folder).resolve()
    res = {}
    for f in layout.instance_folders(root):
        p = f / "study.json"
        if p.is_file() and f.resolve().is_relative_to(below):
            res[f] = build.load_json(p)
    return root, res


def cmd_show(args):
    root, res = load_results(args.root)
    if args.explain is not None:
        explain(res, Design(), args.explain)
        return
    show(res, root, details=args.details)


def cmd_missing(args):
    root, res = load_results(args.root)
    m = missing(res)
    if not m:
        print("no check and no central result waits for a run")
        return 0
    for (where, exp), items in sorted(m.items()):
        checks_ = [i for i in items if not i.startswith("[")]
        crs = [i for i in items if i.startswith("[")]
        print(f"{where}: {exp}: no evidence run; waits: "
              + ", ".join(x for x in (f"{len(checks_)} checks ({', '.join(checks_)})" if checks_ else "",
                                      f"{len(crs)} central results ({', '.join(crs)})" if crs else "") if x))
    print(f"{len({e for _, e in m})} experiments to run; 'study.py campaign check <folder> --only EXP ...'")
    return 0


def cmd_notebooks(args):
    from studylib import notebooks
    res = notebooks.run(args.root, force=args.force)
    bad = [r for r in res if r[2].startswith("FAILED")]
    print(f"{len(res)} notebooks: {sum(r[2] == 'ran' for r in res)} ran, "
          f"{sum(r[2] == 'the same inputs' for r in res)} with the same inputs, {len(bad)} failed")
    return 1 if bad else 0


def cmd_html(args):
    root = layout.find_root(args.root)
    with results_lock(root):
        written = html.write_pages(root, args.root, Design())
    print(f"{len(written)} pages, top: {root / 'index.html'}")


# ------------------------------------------------------------ parser
def parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    des = sub.add_parser("design", help="the study design files").add_subparsers(dest="design_cmd", required=True)
    s = des.add_parser("lint", help="the problems of the design files")
    s.add_argument("folder", nargs="?", help="only the files below this folder")
    s.add_argument("--warn-as-error", action="store_true")
    s.set_defaults(func=cmd_lint)
    scf = des.add_parser("scaffold", help="the files of a new study or experiment").add_subparsers(
        dest="kind", required=True)
    s = scf.add_parser("study", help="a new study PARENT/st-NAME (no experiments yet)")
    s.add_argument("path", help="PARENT_STUDY/st-NAME")
    s.set_defaults(func=cmd_scaffold)
    s = scf.add_parser("experiment", help="a new experiment STUDY/ex-NAME")
    s.add_argument("path", help="STUDY/ex-NAME")
    s.add_argument("--app", required=True, help="the benchmark app (a folder of tests/benchmarks)")
    s.add_argument("--board", help="the board of the experiment (default: the default board of boards.yaml)")
    s.set_defaults(func=cmd_scaffold)

    lab = sub.add_parser("lab", help="the lab space").add_subparsers(dest="lab_cmd", required=True)
    s = lab.add_parser("init", help="make a lab space (run it with the Python of the venv of the lab space)")
    s.add_argument("folder", nargs="?", default=".", help="the lab folder (default: the current folder)")
    s.add_argument("--repo", required=True, help="the safety repo with the study designs and the tools")
    s.add_argument("--name", help="the name of the lab space (default: the folder name)")
    s.add_argument("--trees-root", help="the folder of the pinned trees (default: FOLDER/trees)")
    s.add_argument("--trees-source", help="a folder with <tree>/<path> clones to clone the trees from")
    s.add_argument("--sdk", help="the Zephyr SDK (default: ~/zephyr-sdk-<version of the trees>)")
    s.add_argument("--results", help="the results folder (default: FOLDER/results)")
    s.add_argument("--hw-map", help="the hardware map (default: FOLDER/hw-map.yml)")
    s.set_defaults(func=cmd_lab_init)
    s = lab.add_parser("status", help="the lab space, its trees, boards and campaigns")
    s.set_defaults(func=cmd_lab_status)
    s = lab.add_parser("hwcheck", help="the loopback wire check of a board")
    s.add_argument("board")
    s.add_argument("--tree", help="the tree to build loopback_check from (default: the first that has the board)")
    s.set_defaults(func=cmd_lab_hwcheck)
    s = lab.add_parser("export", help="the runs of this lab space to a file")
    s.add_argument("folder", nargs="?", help="only the instances below this folder of the results tree")
    s.add_argument("-o", "--out", required=True)
    s.add_argument("--campaign", nargs="+", help="only the runs of these campaigns")
    s.add_argument("--all", action="store_true", help="all runs, also those that come from another lab")
    s.set_defaults(func=cmd_lab_export)
    s = lab.add_parser("import", help="the runs of another lab space")
    s.add_argument("file", nargs="?")
    s.add_argument("--dry-run", action="store_true", help="only the checks")
    s.add_argument("--close", metavar="ID@LAB", help="end an imported campaign record that never gets its end")
    s.set_defaults(func=cmd_lab_import)

    camp = sub.add_parser("campaign", help="run the experiments below a folder").add_subparsers(
        dest="campaign_cmd", required=True)
    for name, func in (("prepare", cmd_campaign_prepare), ("check", cmd_campaign_check), ("run", cmd_campaign_run)):
        s = camp.add_parser(name)
        s.add_argument("folder")
        s.add_argument("--board", help="only the experiments for this board (default: the board of the instance)")
        s.add_argument("--only", nargs="+", help="only these experiments")
        s.add_argument("--skip", nargs="+", help="not these experiments")
        if name != "prepare":
            s.add_argument("--no-hwcheck", action="store_true", help="no loopback wire check")
            s.add_argument("--warn-as-error", action="store_true", help="a lint warning fails the check")
        if name == "run":
            s.add_argument("--detach", action="store_true", help="run in the background")
            s.add_argument("--role", default="evidence", choices=instance.ROLES,
                           help="the role of the runs in the run lists (default evidence)")
            s.add_argument("--reason", help="the reason of a role other than evidence")
            s.add_argument("--hwcheck-each", action="store_true",
                           help="the loopback wire check also before each experiment")
        s.set_defaults(func=func)
    s = camp.add_parser("resume")
    s.add_argument("id")
    s.add_argument("--no-hwcheck", action="store_true")
    s.add_argument("--warn-as-error", action="store_true")
    s.add_argument("--detach", action="store_true")
    s.set_defaults(func=cmd_campaign_resume)
    s = camp.add_parser("status")
    s.add_argument("id", nargs="?")
    s.add_argument("--verdicts", action="store_true", help="also the verdicts of the instances of the campaign")
    s.set_defaults(func=cmd_campaign_status)

    s = sub.add_parser("trees", help="the pinned trees of validation/trees/ (west workspaces)")
    s.add_argument("cmd", choices=["setup", "check", "show"])
    s.add_argument("trees", nargs="*")
    s.add_argument("--trees-root", help="override the trees root of the lab space")
    s.set_defaults(func=cmd_trees)

    inst = sub.add_parser("instance", help="the run lists of a results tree").add_subparsers(
        dest="instance_cmd", required=True)
    s = inst.add_parser("new")
    s.add_argument("results")
    s.add_argument("study")
    s.add_argument("--board")
    s.set_defaults(func=cmd_instance_new)
    s = inst.add_parser("add")
    s.add_argument("instance")
    s.add_argument("run")
    s.add_argument("--role", default="evidence")
    s.add_argument("--reason")
    s.add_argument("--copy", action="store_true")
    s.set_defaults(func=cmd_instance_add)
    s = inst.add_parser("exclude", help="give all runs of a campaign the role excluded")
    s.add_argument("root", help="a folder of the results tree")
    s.add_argument("--campaign", required=True)
    s.add_argument("--reason", required=True)
    s.set_defaults(func=cmd_instance_exclude)
    s = inst.add_parser("reference")
    s.add_argument("instance")
    s.add_argument("other")
    s.add_argument("run_id")
    s.add_argument("--reason", required=True)
    s.set_defaults(func=cmd_instance_reference)
    s = inst.add_parser("verdict")
    s.add_argument("instance")
    s.add_argument("--verdict", required=True)
    s.add_argument("--by", required=True)
    s.add_argument("--text")
    s.add_argument("--hypothesis")
    s.add_argument("--check")
    s.add_argument("--central-result")
    s.set_defaults(func=cmd_instance_verdict)
    s = inst.add_parser("merge")
    s.add_argument("other")
    s.add_argument("root")
    s.add_argument("--origin", help="the place of the original tree, for copied_from (HOST:PATH)")
    s.set_defaults(func=cmd_instance_merge)

    s = inst.add_parser("seal", help="write the seal of old runs")
    s.add_argument("runs", nargs="+")
    s.set_defaults(func=cmd_seal)
    s = inst.add_parser("verify", help="check runs against their seals")
    s.add_argument("runs", nargs="+")
    s.set_defaults(func=cmd_verify)

    ana = sub.add_parser("analysis", help="the aggregates of a results tree").add_subparsers(
        dest="analysis_cmd", required=True)
    s = ana.add_parser("build", help="write run.json, the app data, experiment.json and study.json")
    s.add_argument("root")
    s.set_defaults(func=cmd_build)
    s = ana.add_parser("check", help="check all seals, build again and compare")
    s.add_argument("root")
    s.set_defaults(func=cmd_check)
    s = ana.add_parser("show", help="the verdicts: one line for each instance at and below ROOT")
    s.add_argument("root")
    s.add_argument("--details", action="store_true", help="each check and central result")
    s.add_argument("--explain", nargs="*", metavar="ID",
                   help="for each central result (or these ids): its definition, the rows and the sentences")
    s.set_defaults(func=cmd_show)
    s = ana.add_parser("missing", help="the experiments without an evidence run that checks wait for")
    s.add_argument("root", nargs="?", default=".")
    s.set_defaults(func=cmd_missing)
    s = ana.add_parser("notebooks", help="run the notebooks of the studies against the instances at and below ROOT")
    s.add_argument("root")
    s.add_argument("--force", action="store_true", help="run each notebook, also with the same inputs")
    s.set_defaults(func=cmd_notebooks)
    s = ana.add_parser("html", help="index.html in each instance and experiment folder at and below ROOT")
    s.add_argument("root")
    s.set_defaults(func=cmd_html)
    return p


from studylib.exchange import ExchangeError  # noqa: E402

ERRORS = (ExchangeError, campaign.CampaignError, scaffold.ScaffoldError, DesignError, instance.InstanceError, seal.SealError, build.BuildError, labmod.LabError,
          trees.TreeError, ValueError)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    reexec_in_lab_repo(argv)
    args = parser().parse_args(argv)
    try:
        sys.exit(args.func(args) or 0)
    except ERRORS as e:
        sys.exit(f"error: {e}")


if __name__ == "__main__":
    main()
