#!/usr/bin/env python3
# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Study instances and their aggregates (design: validation/empirical/latencies).

    study.py seal RUN ...                 write the seal <UTC>.sha256 of old runs
    study.py verify RUN ...               check runs against their seals
    study.py new RESULTS STUDY --board B  make the instance folders of a study
                                          (and of its sub-studies) for a board;
                                          STUDY "." is the top study
    study.py add INSTANCE RUN [--role R --reason TEXT] [--copy]
                                          add a run to the run list of an instance;
                                          --copy copies a run from another place
    study.py reference INSTANCE OTHER RUN_ID --reason TEXT
                                          add a run of another instance as a reference
    study.py verdict INSTANCE --verdict V --by NAME [--text T]
                     (--hypothesis H --check C | --central-result ID)
                                          set a manual verdict (confirmed, wrong);
                                          a proposal says so in --by
    study.py build ROOT                   write run.json, the app data,
                                          experiment.json and study.json
    study.py check ROOT                   check all seals, build again and compare
    study.py show ROOT                    the verdicts and central results

RESULTS is the results folder (it holds the top instance folder, named
after the top study). ROOT is any folder of a results tree. A run made
with "run.py <experiment> --out <instance folder>" is in the instance
folder already; add it with "study.py add <instance folder> <run folder>".
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from studylib import build, instance, layout, seal  # noqa: E402
from studylib.design import Design, DesignError  # noqa: E402


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


def cmd_new(args):
    d = Design()
    path = "" if args.study in (".", "") else args.study
    folder = instance.new(d, args.results, d.top.name, path, args.board)
    print(folder)


def cmd_add(args):
    d = Design()
    rid = instance.add(d, args.instance, args.run, args.role, args.reason, args.copy)
    print(f"added {rid} to {args.instance}")


def cmd_reference(args):
    instance.add_reference(args.instance, args.other, args.run_id, args.reason)
    print(f"reference {args.run_id} added to {args.instance}")


def cmd_verdict(args):
    instance.add_verdict(args.instance, args.verdict, args.by, args.text, args.hypothesis, args.check,
                         args.central_result)
    print(f"verdict set in {args.instance}")


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
        for h in hyps:
            print(f"   {h['id']} {h['verdict']} ({h['checks_confirmed']})")
            if not brief:
                for c in h["checks"]:
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


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("seal")
    s.add_argument("runs", nargs="+")
    s.set_defaults(func=cmd_seal)
    s = sub.add_parser("verify")
    s.add_argument("runs", nargs="+")
    s.set_defaults(func=cmd_verify)
    s = sub.add_parser("new")
    s.add_argument("results")
    s.add_argument("study")
    s.add_argument("--board")
    s.set_defaults(func=cmd_new)
    s = sub.add_parser("add")
    s.add_argument("instance")
    s.add_argument("run")
    s.add_argument("--role", default="evidence")
    s.add_argument("--reason")
    s.add_argument("--copy", action="store_true")
    s.set_defaults(func=cmd_add)
    s = sub.add_parser("reference")
    s.add_argument("instance")
    s.add_argument("other")
    s.add_argument("run_id")
    s.add_argument("--reason", required=True)
    s.set_defaults(func=cmd_reference)
    s = sub.add_parser("verdict")
    s.add_argument("instance")
    s.add_argument("--verdict", required=True)
    s.add_argument("--by", required=True)
    s.add_argument("--text")
    s.add_argument("--hypothesis")
    s.add_argument("--check")
    s.add_argument("--central-result")
    s.set_defaults(func=cmd_verdict)
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
    args = p.parse_args()
    try:
        sys.exit(args.func(args) or 0)
    except (DesignError, instance.InstanceError, seal.SealError, build.BuildError, ValueError) as e:
        sys.exit(f"error: {e}")


if __name__ == "__main__":
    main()
