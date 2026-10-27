#!/usr/bin/env python3
# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Study designs, lab spaces, campaigns and the aggregates of a results tree.

Design (validation/empirical/latencies):
    study.py lint [FOLDER] [--warn-as-error]
                                          the problems of the design files; exit 1
                                          on an error (or a warning with the flag)
    study.py scaffold PARENT/st-NAME --app APP [--experiment EXP] [--board B]
                                          a new study with a first experiment
                                          (default EXP: NAME-smoke)
    study.py scaffold STUDY/ex-NAME --app APP [--board B]
                                          a new experiment of a study

Lab space (a folder with .lab/config, see studylib/lab.py):
    study.py lab init FOLDER --repo REPO [--trees-source DIR] [--sdk DIR] [--name N]
                                          make a lab space
    study.py lab status                   the lab space, its trees, boards and campaigns
    study.py lab hwcheck BOARD            the loopback wire check of a board

Campaigns (FOLDER: a design study or experiment folder, or an instance folder):
    study.py campaign prepare FOLDER [--board B] [--only EXP ...] [--skip EXP ...]
                                          build the images of all points (build cache)
    study.py campaign check FOLDER [...] [--no-hwcheck]
                                          the pre-flight check
    study.py campaign run FOLDER [...] [--no-hwcheck] [--detach] [--warn-as-error]
                                          check, then run each experiment and add each
                                          run to its instance; build the results after
                                          each run in the background
    study.py campaign status [ID]         the record of a campaign (default: the latest)
    study.py campaign resume ID [--detach]
                                          run the experiments of a campaign that are not done

Pinned trees (validation/trees.yaml, paths from the lab space):
    study.py trees setup [--clone-source] [TREE ...]
    study.py trees check [TREE ...]
    study.py trees show

Instances (the run lists in a results tree):
    study.py instance new RESULTS STUDY --board B
                                          make the instance folders of a study
                                          (and of its sub-studies) for a board;
                                          STUDY "." is the top study
    study.py instance add INSTANCE RUN [--role R --reason TEXT] [--copy]
                                          add a run to the run list of an instance;
                                          --copy copies a run from another place
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

Results tree (ROOT is any folder of a results tree):
    study.py seal RUN ...                 write the seal <UTC>.sha256 of old runs
    study.py verify RUN ...               check runs against their seals
    study.py build ROOT                   write run.json, the app data,
                                          experiment.json and study.json
    study.py check ROOT                   check all seals, build again and compare
    study.py show ROOT                    the verdicts and central results
    study.py html ROOT [--out FILE]       one HTML page with all study.json files
                                          (default ROOT/index.html)

In a lab space, the tools of the design repo of the lab space run: another
study.py starts the study.py of that repo with the same arguments.
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import trees  # noqa: E402
from studylib import build, html, instance, layout, seal  # noqa: E402
from studylib import lab as labmod  # noqa: E402
from studylib import campaign, lint, scaffold  # noqa: E402
from studylib.design import Design, DesignError  # noqa: E402

REEXEC_ENV = "LATBENCH_STUDY_REEXEC"


def reexec_in_lab_repo(argv):
    """Run the study.py of the design repo of the lab space, if this is another one."""
    if os.environ.get(REEXEC_ENV) or (argv[:2] == ["lab", "init"]):
        return
    lab = labmod.find()
    if lab is None:
        return
    target = lab.repo / "scripts" / "benchmarks" / "study.py"
    if target.resolve() == Path(__file__).resolve():
        return
    if not target.is_file():
        sys.exit(f"error: the lab space {lab.folder} has the design repo {lab.repo}, which has no {target}")
    os.environ[REEXEC_ENV] = str(Path(__file__).resolve())
    os.execv(sys.executable, [sys.executable, str(target), *argv])


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
    folder = scaffold.scaffold(args.path, args.app, args.experiment, args.board)
    for f in sorted(folder.rglob("*")):
        if f.is_file():
            print(f"new {f}")
    print("replace the TODO texts; 'study.py lint' lists them")


# ------------------------------------------------------------ lab
def cmd_lab_init(args):
    lab = labmod.init(args.folder, args.repo, name=args.name, trees_root=args.trees_root,
                      trees_source=args.trees_source, sdk=args.sdk, results=args.results, hw_map=args.hw_map)
    print(f"lab space {lab.id} in {lab.folder}")
    print(f"  design repo  {lab.repo}")
    print(f"  trees        {lab.trees_root}" + (f" (clone from {lab.trees_source})" if lab.trees_source else ""))
    print(f"  results      {lab.results}")
    print(f"  hardware map {lab.hw_map}" + ("" if lab.hw_map.is_file() else " (missing: make it with twister)"))
    print(f"next: cd {lab.folder} && {lab.repo}/scripts/benchmarks/study.py trees setup --clone-source")


def cmd_lab_status(args):
    import hwmap
    lab = labmod.require()
    rev, dirty = trees.repo_state(lab.repo)
    print(f"lab space {lab.id} in {lab.folder}")
    print(f"  design repo  {lab.repo} at {rev[:12]}{' (dirty)' if dirty else ''}")
    cfg = trees.load(lab=lab)
    try:
        sdk = trees.check_toolchain(cfg)
        print(f"  zephyr sdk   {sdk} ({cfg['toolchain']['zephyr_sdk']['version']})")
    except trees.TreeError as e:
        print(f"  zephyr sdk   {e}")
    for t in cfg["trees"]:
        try:
            trees.check_tree(cfg, t)
            state = "ok"
        except trees.TreeError as e:
            state = str(e).splitlines()[0]
        print(f"  tree {t:20} {state}")
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
    for rec in campaign.records(lab)[-3:]:
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
    for e in items:
        print(f"  {e['state']:8} {e['experiment']} ({e['study']}, {e['board']})" + (f": {e['note']}" if e.get("note") else ""))
    res = campaign.preflight(lab, items, Design(), hwcheck=not args.no_hwcheck, warn_as_error=args.warn_as_error)
    bad = [w for st, w, _ in res if st == "fail"]
    print("pre-flight check: " + ("ok" if not bad else f"FAILED ({', '.join(bad)})"))
    return 1 if bad else 0


def campaign_extra(args):
    return [*(["--no-hwcheck"] if args.no_hwcheck else []), *(["--warn-as-error"] if args.warn_as_error else [])]


def cmd_campaign_run(args):
    lab = labmod.require()
    items = campaign.plan(lab, args.folder, args.board, args.only, args.skip)
    rec = campaign.new_record(lab, args.folder, args.board, items, ["study.py", *sys.argv[1:]])
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
        show(res, root, brief=True)
    return 0


# ------------------------------------------------------------ trees
def cmd_trees(args):
    trees.main(args)


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


# ------------------------------------------------------------ results tree
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


def cmd_build(args):
    root = layout.find_root(args.root)
    t, w = build.build(root)
    print(f"built {len(t.results)} instances, {len(t.loaded)} runs; {w.written} files written")
    if t.made_by.get("dirty"):
        print("WARNING: the safety repo has changes that are not committed: the aggregates are not reproducible")
    show(t.results, root, brief=True)


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


def show(results, root, brief=False):
    for folder, sj in sorted(results.items(), key=lambda x: str(x[0])):
        hyps = sj["hypotheses"]
        crs = sj["central_results"]
        if brief and not hyps and not any(c.get("texts") for c in crs):
            continue
        print(f"\n== {sj['instance']}")
        for n in sj.get("notes", []):
            print(f"   NOTE {n}")
        for a in sj.get("acceptance", []):
            bad = [c for c in a["checks"] if c["verdict"] != "confirmed"]
            if bad:
                print(f"   acceptance {a['run']}: " + ", ".join(f"{c['id']} {c['verdict']}" for c in bad))
        if not sj.get("state", {}).get("final", True):
            print(f"   PROVISIONAL: {'; '.join(sj['state']['waits'])}")
        for h in hyps:
            print(f"   {h['id']} {h['verdict']}{' (provisional)' if h.get('provisional') else ''} ({h['checks_confirmed']})")
            for c in h["checks"]:
                if not brief or c["verdict"] in ("tool error", "not evaluated"):
                    print(f"      {c['id']} {c['verdict']}: {c.get('measured', '')[:140]}")
        for c in crs:
            if c.get("not_evaluated"):
                print(f"   [{c['id']}] not evaluated: {c['not_evaluated'][:120]}")
            elif not brief or c.get("stat") == "conclusion":
                for t in c.get("texts", [])[: (3 if brief else 50)]:
                    print(f"   [{c['id']}] {t}")


def cmd_show(args):
    root = layout.find_root(args.root)
    res = {}
    for f in layout.instance_folders(root):
        p = f / "study.json"
        if p.is_file():
            res[f] = build.load_json(p)
    show(res, root, brief=args.brief)


def cmd_html(args):
    root = layout.find_root(args.root)
    out = Path(args.out) if args.out else root / "index.html"
    out.write_text(html.page(root))
    print(out)


# ------------------------------------------------------------ parser
def parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("lint", help="the problems of the design files")
    s.add_argument("folder", nargs="?", help="only the files below this folder")
    s.add_argument("--warn-as-error", action="store_true")
    s.set_defaults(func=cmd_lint)
    s = sub.add_parser("scaffold", help="the files of a new study (st-NAME) or experiment (ex-NAME)")
    s.add_argument("path", help="PARENT_STUDY/st-NAME or STUDY/ex-NAME")
    s.add_argument("--app", required=True, help="the benchmark app (a folder of tests/benchmarks)")
    s.add_argument("--experiment", help="the name of the first experiment of a new study (default NAME-smoke)")
    s.add_argument("--board", help="the board of the experiment (default: the default board of boards.yaml)")
    s.set_defaults(func=cmd_scaffold)

    lab = sub.add_parser("lab", help="the lab space").add_subparsers(dest="lab_cmd", required=True)
    s = lab.add_parser("init", help="make a lab space")
    s.add_argument("folder")
    s.add_argument("--repo", required=True, help="the safety repo with the study designs and the tools")
    s.add_argument("--name", help="the name of the lab space (default: the folder name)")
    s.add_argument("--trees-root", help="the folder of the pinned trees (default: FOLDER/trees)")
    s.add_argument("--trees-source", help="a folder with <tree>/<path> clones to clone the trees from")
    s.add_argument("--sdk", help="the Zephyr SDK (default: ~/zephyr-sdk-<version of trees.yaml>)")
    s.add_argument("--results", help="the results folder (default: FOLDER/results)")
    s.add_argument("--hw-map", help="the hardware map (default: FOLDER/hw-map.yml)")
    s.set_defaults(func=cmd_lab_init)
    s = lab.add_parser("status", help="the lab space, its trees, boards and campaigns")
    s.set_defaults(func=cmd_lab_status)
    s = lab.add_parser("hwcheck", help="the loopback wire check of a board")
    s.add_argument("board")
    s.add_argument("--tree", help="the tree to build loopback_check from (default: the first that has the board)")
    s.set_defaults(func=cmd_lab_hwcheck)

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

    s = sub.add_parser("trees", help="the pinned trees of validation/trees.yaml")
    s.add_argument("cmd", choices=["setup", "check", "show"])
    s.add_argument("trees", nargs="*")
    s.add_argument("--trees-root", help="override the trees root of the lab space")
    s.add_argument("--clone-source", action="store_true",
                   help="setup: clone each source repo instead of adding a worktree to it")
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

    s = sub.add_parser("seal")
    s.add_argument("runs", nargs="+")
    s.set_defaults(func=cmd_seal)
    s = sub.add_parser("verify")
    s.add_argument("runs", nargs="+")
    s.set_defaults(func=cmd_verify)
    s = sub.add_parser("build")
    s.add_argument("root")
    s.set_defaults(func=cmd_build)
    s = sub.add_parser("check")
    s.add_argument("root")
    s.set_defaults(func=cmd_check)
    s = sub.add_parser("show")
    s.add_argument("root")
    s.add_argument("--brief", action="store_true")
    s.set_defaults(func=cmd_show)
    s = sub.add_parser("html")
    s.add_argument("root")
    s.add_argument("--out")
    s.set_defaults(func=cmd_html)
    return p


ERRORS = (campaign.CampaignError, scaffold.ScaffoldError, DesignError, instance.InstanceError, seal.SealError, build.BuildError, labmod.LabError,
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
