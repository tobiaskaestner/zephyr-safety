# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Export and import of runs between lab spaces (study.py lab export / import).

An export is one tar file and its digest file <file>.sha256. The tar has:

    export.json          format latbench-export/2: the lab space, the host,
                         the design repo commit, the design files of the
                         exporting lab (each experiment: its file, sha256,
                         parsed content and earlier names; study.yaml and
                         hypotheses.yaml of each instance, with sha256),
                         the references and the manual verdicts of each
                         instance (the import adds those it does not have), and
                         for each run: the instance path, the run-list entry,
                         the experiment, the board, the tree pins
    runs/<instance folder>/ex-<experiment>/<UTC>/ and <UTC>.sha256
    campaigns/<id>.json  the campaign records of the runs
    repo.bundle          a git bundle of the design repo commits of the runs
                         and campaigns (with their history)

The import checks the digest of the file, then for each run:

- the run id is new in the results tree, or the same run (same digest:
  skipped). A run id with another digest is refused (collision);
- the experiment of the exporting lab has the same content as here: the
  parsed YAML without comments, name and renamed_from (an earlier name
  maps to the current one). Else the run is refused: the two labs work
  from other design files. An export of format 1 has only the sha256 of
  the file: then the bytes are compared;
- study.yaml or hypotheses.yaml of the instance differs: a warning (the
  import builds with its own design);
- the tree pins of the run differ from validation/trees/ here: a
  warning ("other code"; the build notes it);
- the seal gives the digest of the run list entry.

Then the run is copied into its instance (made, with the board level of the
exporting lab, if there is none) and added with its role and reason;
copied_from names the lab and the campaign. The campaign records go to
.lab/campaigns/<id>@<lab id>.json, so that a run that is still planned in a
running campaign of the other lab makes the verdicts provisional here too;
such a record gets running_at_export, until a later import brings its end
or "lab import --close <id>@<lab id>" ends it. The commits of the bundle go
to refs/latbench/import/<lab id>/<rev> of the design repo, so that
run.py --rebuild works here.
"""

import datetime
import hashlib
import json
import platform
import shutil
import subprocess
import tarfile
from pathlib import Path

import trees

from . import instance, jsonout, layout, seal
from .design import Design, repo_rel
from .seal import file_sha256

FORMAT = "latbench-export/2"
FORMATS = ("latbench-export/1", FORMAT)     # format 1: no parsed experiments, no bundle
BUNDLE_NS = "refs/latbench/export"


def comparable(exp_data):
    """The content of an experiment file that the two labs must share: the parsed YAML (no
    comments) without its name and earlier names (a rename is not a change of the experiment)."""
    from . import schema
    d = schema.plain(dict(exp_data or {}))
    d.pop("name", None)
    d.pop("renamed_from", None)
    return d


class ExchangeError(Exception):
    pass


def file_digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def instance_rel(ipath):
    """The folder of an instance path below the results folder: <top>/st-<a@b>/st-<c>."""
    top, *names = ipath.split("/")
    return Path(top, *(layout.STUDY_PREFIX + n for n in names))


def study_path(ipath):
    """The study path of an instance path with the top name ("kernel-latency/a@b/c" gives "a/c")."""
    return layout.strip_board(ipath.split("/", 1)[1]) if "/" in ipath else ""


def runs_to_export(lab, root, campaigns=None, all_runs=False):
    """[(instance folder, run-list entry, campaign id or None)] of a results tree."""
    from . import campaign as cmod
    by_run = {}
    for rec in cmod.records(lab):
        for e in rec.data.get("experiments", []):
            if e.get("run"):
                by_run[e["run"]] = rec.data["id"]
    out = []
    for f in layout.instance_folders(root):
        for r in instance.load(f).get("runs", []):
            cid = by_run.get(r["id"])
            if campaigns is not None:
                if cid not in campaigns:
                    continue
            elif not all_runs:
                m = json.loads((f / layout.run_folder(r["id"]) / "manifest.json").read_text())
                if (m.get("lab") or {}).get("id") != lab.id:
                    continue
            out.append((f, r, cid))
    return out


def export(lab, out_file, folder=None, campaigns=None, all_runs=False, log=print):
    """Write the export file and its digest file; return the number of runs."""
    from . import campaign as cmod
    design = Design()
    root = Path(folder).resolve() if folder else lab.results / design.top.name
    root_top = layout.find_root(root)
    runs = [x for x in runs_to_export(lab, root_top, campaigns, all_runs) if x[0].resolve().is_relative_to(root)]
    if not runs:
        raise ExchangeError("no runs to export (runs of this lab space; --all for all runs, --campaign ID)")
    rev, dirty = trees.repo_state(trees.REPO_DIR)
    index = {"format": FORMAT, "lab": lab.describe(), "host": platform.node(),
             "created": datetime.datetime.now(datetime.timezone.utc).isoformat(),
             "design_repo": {"rev": rev, "dirty": bool(dirty)}, "experiments": {}, "instances": {}, "runs": [],
             "campaigns": sorted({c for _, _, c in runs if c})}
    out_file = Path(out_file).resolve()
    tmp = out_file.with_name(out_file.name + ".part")
    revs = set()
    with tarfile.open(tmp, "w:gz") as tar:
        for f, r, cid in runs:
            data = instance.load(f)
            ipath = data["instance"]
            exp = r["id"].split("/")[0]
            run_dir = f / layout.run_folder(r["id"])
            if seal.verify(run_dir) != r["digest"]:
                raise ExchangeError(f"{run_dir}: the seal does not give the digest of the run list")
            m = json.loads((run_dir / "manifest.json").read_text())
            exp = design.canonical(exp)
            if exp in design.experiments:
                e = design.experiment(exp)
                ef = e.folder / "experiment.yaml"
                index["experiments"][exp] = {"file": repo_rel(ef), "sha256": file_sha256(ef),
                                             "content": comparable(e.data), "renamed_from": e.renamed_from}
            if (m.get("safety") or {}).get("rev"):
                revs.add(m["safety"]["rev"])
            index["instances"][ipath] = {"design": data["design"]["folder"],
                                         "files": design.study(study_path(ipath)).files(),
                                         # hand-made data of the instance, like the run list
                                         "references": data.get("references", []),
                                         "manual_verdicts": data.get("manual_verdicts", [])}
            index["runs"].append({"instance": ipath, "entry": {k: r[k] for k in ("id", "digest", "role", "reason",
                                                                                "campaign") if k in r},
                                  "board": m.get("board"), "campaign": cid, "experiment": exp,
                                  "trees": {t: {n: v.get("rev") for n, v in c.get("repos", {}).items()}
                                            for t, c in m.get("trees", {}).items()}})
            rel = instance_rel(ipath) / layout.run_folder(r["id"])
            tar.add(run_dir, arcname=f"runs/{rel}")
            tar.add(seal.seal_path(run_dir), arcname=f"runs/{rel.parent}/{run_dir.name}.sha256")
        for c in index["campaigns"]:
            p = lab.campaigns / f"{c}.json"
            if p.is_file():
                tar.add(p, arcname=f"campaigns/{c}.json")
                rev_c = (json.loads(p.read_text()).get("repo") or {}).get("rev")
                if rev_c:
                    revs.add(rev_c)
        bundle = out_file.with_name(out_file.name + ".bundle.part")
        index["bundle"] = make_bundle(trees.REPO_DIR, sorted(revs), bundle)
        if index["bundle"]["revs"]:
            tar.add(bundle, arcname="repo.bundle")
        bundle.unlink(missing_ok=True)
        blob = (jsonout.dumps(index) + "\n").encode()
        info = tarfile.TarInfo("export.json")
        info.size = len(blob)
        import io
        tar.addfile(info, io.BytesIO(blob))
    tmp.rename(out_file)
    digest = file_digest(out_file)
    Path(f"{out_file}.sha256").write_text(f"{digest}  {out_file.name}\n")
    log(f"{len(runs)} runs of {len(index['instances'])} instances to {out_file} (sha256 {digest[:12]})")
    return len(runs)


def make_bundle(repo, revs, out):
    """A git bundle of the commits revs (with their history) of the design repo; return
    {revs, missing}. Each commit gets the temporary ref refs/latbench/export/<rev> for the bundle."""
    have = [r for r in revs if trees.git("cat-file", "-t", r, cwd=repo, check=False) == "commit"]
    missing = [r for r in revs if r not in have]
    if have:
        refs = [f"{BUNDLE_NS}/{r}" for r in have]
        try:
            for ref, r in zip(refs, have):
                trees.git("update-ref", ref, r, cwd=repo)
            trees.git("bundle", "create", "-q", str(out), *refs, cwd=repo)
        finally:
            for ref in refs:
                trees.git("update-ref", "-d", ref, cwd=repo, check=False)
    return {"revs": have, "missing": missing}


def fetch_bundle(lab, bundle, other_id, log=print):
    """Fetch the commits of the bundle of an export into the design repo of the lab space, as
    refs/latbench/import/<other lab>/<rev> (local refs; never pushed). Return the revs."""
    repo = lab.repo
    r = subprocess.run(["git", "bundle", "verify", "-q", str(bundle)], cwd=repo, capture_output=True, text=True)
    if r.returncode != 0:
        raise ExchangeError(f"the bundle of the export does not verify: {r.stderr.strip()}")
    trees.git("fetch", "-q", str(bundle), f"+{BUNDLE_NS}/*:refs/latbench/import/{other_id}/*", cwd=repo)
    revs = [ln.split()[0] for ln in trees.git("bundle", "list-heads", str(bundle), cwd=repo).splitlines() if ln]
    log(f"{len(revs)} commits of the runs in refs/latbench/import/{other_id}/ of {repo}")
    return revs


def close_import(lab, name):
    """End an imported campaign record that will never get its end (the other lab exports no more)."""
    p = lab.campaigns / f"{name}.json"
    if "@" not in name or not p.is_file():
        raise ExchangeError(f"no imported campaign record {p} (the name is <id>@<lab id>)")
    d = json.loads(p.read_text())
    d["status_at_import"] = d.get("status")
    d["status"] = "closed"
    d["closed"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    jsonout.write(p, d)
    return d


def import_(lab, in_file, log=print, dry=False):
    """Import the runs of an export file; return (added, skipped, refused, warnings)."""
    from . import campaign as cmod
    in_file = Path(in_file).resolve()
    dfile = Path(f"{in_file}.sha256")
    if not dfile.is_file():
        raise ExchangeError(f"no digest file {dfile}")
    if dfile.read_text().split()[0] != file_digest(in_file):
        raise ExchangeError(f"{in_file}: the digest does not agree with {dfile}")
    design = Design()
    work = lab.folder / ".lab" / "import" / in_file.name
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    try:
        with tarfile.open(in_file) as tar:
            tar.extractall(work, filter="data")
        index = json.loads((work / "export.json").read_text())
        if index.get("format") not in FORMATS:
            raise ExchangeError(f"{in_file}: format {index.get('format')}, expected one of {', '.join(FORMATS)}")
        other = index["lab"]
        if other["id"] == lab.id:
            raise ExchangeError(f"{in_file} comes from this lab space ({lab.id})")
        warnings, refused, added, skipped = [], [], [], []
        # design consistency
        # an experiment: the parsed content (no comments, no name), with the earlier names of a
        # rename; an export of format 1 has only the sha256 of the file
        bad_exp = {}
        for exp, ref in index["experiments"].items():
            here_name = design.canonical(exp)
            if here_name not in design.experiments:
                bad_exp[exp] = "the experiment is not in the design here"
                continue
            e = design.experiment(here_name)
            if "content" in ref:
                if comparable(e.data) != ref["content"]:
                    bad_exp[exp] = f"experiment.yaml of {here_name} differs between the two labs (content)"
            elif file_sha256(e.folder / "experiment.yaml") != ref["sha256"]:
                bad_exp[exp] = (f"experiment.yaml of {here_name} differs between the two labs (an export of format 1: "
                                "the bytes are compared)")
        for ipath, ref in index["instances"].items():
            try:
                files = design.study(study_path(ipath)).files()
            except Exception:
                warnings.append(f"{ipath}: the study is not in the design here")
                continue
            for name, sha in ref["files"].items():
                if files.get(name) != sha:
                    warnings.append(f"{ipath}: {name} differs between the two labs (the build uses the file here)")
        if not dry:
            # the campaign records first: a run of a running campaign is provisional at once
            lab.campaigns.mkdir(parents=True, exist_ok=True)
            for p in sorted((work / "campaigns").glob("*.json")) if (work / "campaigns").is_dir() else []:
                d = json.loads(p.read_text())
                if d.get("status") in ("running", "planned"):
                    # its end comes with a later export (or "lab import --close")
                    d["running_at_export"] = index["created"]
                target = lab.campaigns / f"{p.stem}@{other['id']}.json"
                if target.is_file() and json.loads(target.read_text()).get("status") not in ("running", "planned") \
                        and d.get("status") in ("running", "planned"):
                    continue        # ended or closed here: an older export does not open it again
                jsonout.write(target, d)
            if (work / "repo.bundle").is_file():
                try:
                    fetch_bundle(lab, work / "repo.bundle", other["id"], log=log)
                except (ExchangeError, trees.TreeError) as x:
                    warnings.append(f"the commits of the runs are not here: {x} (a rebuild here needs them)")
            missing = (index.get("bundle") or {}).get("missing", [])
            if missing:
                warnings.append(f"the export has not the commits {', '.join(m[:12] for m in missing)} of its runs "
                                "(the other lab does not have them; a rebuild here needs them)")
        pins = trees.load(lab=lab)["trees"]
        root = lab.results / design.top.name
        have = {}
        if root.is_dir():
            for f in layout.instance_folders(root):
                for r in instance.load(f).get("runs", []):
                    have[r["id"]] = (f, r)
        for item in index["runs"]:
            entry, rid = item["entry"], item["entry"]["id"]
            exp = item.get("experiment") or rid.split("/")[0]      # the name in the export
            if exp in bad_exp or exp not in index["experiments"]:
                refused.append(f"{rid}: {bad_exp.get(exp, 'the experiment is not in the design of the other lab')}")
                continue
            if rid in have:
                if have[rid][1]["digest"] == entry["digest"]:
                    skipped.append(rid)
                else:
                    refused.append(f"{rid}: the run id is in {have[rid][0]} with another digest (collision)")
                continue
            src = work / "runs" / instance_rel(item["instance"]) / layout.run_folder(rid)
            try:
                ok = seal.verify(src) == entry["digest"]
            except (seal.SealError, OSError) as x:
                refused.append(f"{rid}: {x}")
                continue
            if not ok:
                refused.append(f"{rid}: the seal does not give the digest of the export")
                continue
            for t, repos in item.get("trees", {}).items():
                here = {n: v["rev"] for n, v in pins.get(t, {}).get("repos", {}).items()}
                if any(here.get(n) not in (None, v) for n, v in repos.items()) or t not in pins:
                    warnings.append(f"{rid}: the tree {t} of the run has other pins than validation/trees/ here")
            if dry:
                added.append(rid)
                continue
            folder = lab.results / instance_rel(item["instance"])
            if not (folder / "instance.json").is_file():
                names = item["instance"].split("/")[1:]
                level = next((i for i, n in enumerate(names) if "@" in n), None)
                if level is None:
                    raise ExchangeError(f"{item['instance']}: no level of the instance path fixes the board")
                instance.new(design, lab.results, design.top.name, layout.strip_board("/".join(names[:level + 1])),
                             item["board"])
                if not (folder / "instance.json").is_file():
                    raise ExchangeError(f"the instance {item['instance']} was not made here")
            target = folder / layout.run_folder(rid)
            if target.exists():
                refused.append(f"{rid}: {target} exists, but it is not in the run list")
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                subprocess.run(["cp", "-a", str(src), str(target)], check=True)
                shutil.copy2(seal.seal_path(src), seal.seal_path(target))
                if seal.verify(target) != entry["digest"]:
                    raise seal.SealError(f"{target}: the copy does not agree with its seal")
            except (seal.SealError, OSError, subprocess.CalledProcessError) as x:
                shutil.rmtree(target, ignore_errors=True)
                seal.seal_path(target).unlink(missing_ok=True)
                refused.append(f"{rid}: the copy failed: {x}")
                continue
            new = dict(entry)
            new["copied_from"] = f"lab {other['id']}" + (f", campaign {item['campaign']}" if item.get("campaign") else "")
            with instance.locked(folder):
                data = instance.load(folder)
                data["runs"].append(new)
                instance.save(folder, data)
            added.append(rid)
            have[rid] = (folder, new)
        if not dry:
            for ipath, ref in index["instances"].items():
                folder = lab.results / instance_rel(ipath)
                if (folder / "instance.json").is_file() and (ref.get("references") or ref.get("manual_verdicts")):
                    n = instance.merge_hand_data(folder, ref, f"lab {other['id']}",
                                                 log=lambda m: warnings.append(m.removeprefix("warning: ")))
                    if n:
                        log(f"{ipath}: {n} references and manual verdicts added")
        for w in dict.fromkeys(warnings):
            log(f"warning: {w}")
        for r in refused:
            log(f"refused: {r}")
        log(f"{len(added)} runs {'to add' if dry else 'added'}, {len(skipped)} already here, {len(refused)} refused"
            f" (from lab {other['id']} on {index['host']})")
        return added, skipped, refused, list(dict.fromkeys(warnings))
    finally:
        shutil.rmtree(work, ignore_errors=True)
