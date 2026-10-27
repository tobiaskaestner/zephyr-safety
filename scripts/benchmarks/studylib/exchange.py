# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Export and import of runs between lab spaces (study.py lab export / import).

An export is one tar file and its digest file <file>.sha256. The tar has:

    export.json          format latbench-export/1: the lab space, the host,
                         the design repo commit, the design files of the
                         exporting lab (experiment.yaml of each experiment,
                         study.yaml and hypotheses.yaml of each instance,
                         with sha256), and for each run: the instance path,
                         the run-list entry, the board, the tree pins
    runs/<instance folder>/ex-<experiment>/<UTC>/ and <UTC>.sha256
    campaigns/<id>.json  the campaign records of the runs

The import checks the digest of the file, then for each run:

- the run id is new in the results tree, or the same run (same digest:
  skipped). A run id with another digest is refused (collision);
- experiment.yaml of the exporting lab is the same as here, else the run
  is refused: the two labs work from other design files;
- study.yaml or hypotheses.yaml of the instance differs: a warning (the
  import builds with its own design);
- the tree pins of the run differ from validation/trees.yaml here: a
  warning ("other code"; the build notes it);
- the seal gives the digest of the run list entry.

Then the run is copied into its instance (made, with the board level of the
exporting lab, if there is none) and added with its role and reason;
copied_from names the lab and the campaign. The campaign records go to
.lab/campaigns/<id>@<lab id>.json, so that a run that is still planned in a
running campaign of the other lab makes the verdicts provisional here too.
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

FORMAT = "latbench-export/1"


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
    with tarfile.open(tmp, "w:gz") as tar:
        for f, r, cid in runs:
            data = instance.load(f)
            ipath = data["instance"]
            exp = r["id"].split("/")[0]
            run_dir = f / layout.run_folder(r["id"])
            if seal.verify(run_dir) != r["digest"]:
                raise ExchangeError(f"{run_dir}: the seal does not give the digest of the run list")
            m = json.loads((run_dir / "manifest.json").read_text())
            if exp in design.experiments:
                ef = design.experiment(exp).folder / "experiment.yaml"
                index["experiments"][exp] = {"file": repo_rel(ef), "sha256": file_sha256(ef)}
            index["instances"][ipath] = {"design": data["design"]["folder"],
                                         "files": design.study(study_path(ipath)).files()}
            index["runs"].append({"instance": ipath, "entry": {k: r[k] for k in ("id", "digest", "role", "reason")
                                                               if k in r},
                                  "board": m.get("board"), "campaign": cid,
                                  "trees": {t: {n: v.get("rev") for n, v in c.get("repos", {}).items()}
                                            for t, c in m.get("trees", {}).items()}})
            rel = instance_rel(ipath) / layout.run_folder(r["id"])
            tar.add(run_dir, arcname=f"runs/{rel}")
            tar.add(seal.seal_path(run_dir), arcname=f"runs/{rel.parent}/{run_dir.name}.sha256")
        for c in index["campaigns"]:
            p = lab.campaigns / f"{c}.json"
            if p.is_file():
                tar.add(p, arcname=f"campaigns/{c}.json")
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
        if index.get("format") != FORMAT:
            raise ExchangeError(f"{in_file}: format {index.get('format')}, expected {FORMAT}")
        other = index["lab"]
        if other["id"] == lab.id:
            raise ExchangeError(f"{in_file} comes from this lab space ({lab.id})")
        warnings, refused, added, skipped = [], [], [], []
        # design consistency
        bad_exp = {}
        for exp, ref in index["experiments"].items():
            if exp not in design.experiments:
                bad_exp[exp] = "the experiment is not in the design here"
                continue
            here = file_sha256(design.experiment(exp).folder / "experiment.yaml")
            if here != ref["sha256"]:
                bad_exp[exp] = "experiment.yaml differs between the two labs"
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
                shutil.copy2(p, lab.campaigns / f"{p.stem}@{other['id']}.json")
        pins = trees.load(lab=lab)["trees"]
        root = lab.results / design.top.name
        have = {}
        if root.is_dir():
            for f in layout.instance_folders(root):
                for r in instance.load(f).get("runs", []):
                    have[r["id"]] = (f, r)
        for item in index["runs"]:
            entry, rid = item["entry"], item["entry"]["id"]
            exp = rid.split("/")[0]
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
                    warnings.append(f"{rid}: the tree {t} of the run has other pins than validation/trees.yaml here")
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
        for w in dict.fromkeys(warnings):
            log(f"warning: {w}")
        for r in refused:
            log(f"refused: {r}")
        log(f"{len(added)} runs {'to add' if dry else 'added'}, {len(skipped)} already here, {len(refused)} refused"
            f" (from lab {other['id']} on {index['host']})")
        return added, skipped, refused, list(dict.fromkeys(warnings))
    finally:
        shutil.rmtree(work, ignore_errors=True)
