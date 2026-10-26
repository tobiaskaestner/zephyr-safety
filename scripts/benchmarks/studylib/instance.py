# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""instance.json: one instance of a study design in a results tree.

    format      latbench-instance/2
    instance    the instance path ("" for the top instance) with the top name
    design      {folder, safety_rev, files: {study.yaml: sha256, ...}}
    board       the board target, where this level fixes it
    board_from  "parent instance", where a level above fixes it
    runs        [{id, digest, role, reason, copied_from}]   the runs of this instance
    references  [{instance, id, digest, role: reference, reason}]
    substudies  [instance paths of the sub-instances]
    manual_verdicts [{hypothesis, check, verdict, by, date, text}]
    notes       [text]

Roles: evidence (the hypotheses and central results read it), adjustment
(a run to adjust the method, for example the histogram size), reference
(a fixed value of a run of another instance), excluded (with a reason).
The run list is hand-made data: the tools add to it, the build only reads it.
"""

import json
import shutil
import subprocess
from pathlib import Path

import trees

from . import jsonout, layout, seal
from .design import repo_rel, repo_rev

FORMAT = "latbench-instance/2"
ROLES = ("evidence", "adjustment", "excluded")


class InstanceError(Exception):
    pass


def load(folder):
    return json.loads((Path(folder) / "instance.json").read_text())


def save(folder, data):
    return jsonout.write(Path(folder) / "instance.json", data)


def board_port(board):
    """The folder name part of a board target: the port of boards.yaml (nucleo_g474re, nrf54l15dk, ...)."""
    boards = trees.load_boards()["boards"]
    if board not in boards:
        raise InstanceError(f"board {board!r} is not in boards.yaml")
    return boards[board]["port"]


def design_ref(study):
    rev, _ = repo_rev()
    return {"folder": repo_rel(study.folder), "safety_rev": rev, "files": study.files()}


def new(design, results, top_name, study_path, board=None):
    """Create the instance folders of a study (and of its sub-studies) for a board; return the folder.

    The parents are created without a board if they do not exist. The board
    is fixed at the level of study_path; the sub-studies inherit it, except
    those that the design marks "instances: per-board" (they get their own).
    """
    results = Path(results)
    root = results / top_name
    names = [n for n in study_path.split("/") if n]
    if board is None and names:
        raise InstanceError("a board is necessary below the top study")
    port = board_port(board) if board else None

    def make(folder, spath, ipath, board_here, inherited):
        folder.mkdir(parents=True, exist_ok=True)
        f = folder / "instance.json"
        if f.exists():
            return load(folder)
        study = design.study(spath)
        data = {"format": FORMAT, "instance": f"{top_name}/{ipath}" if ipath else top_name,
                "design": design_ref(study)}
        if board_here:
            data["board"] = board_here
        elif inherited:
            data["board_from"] = "parent instance"
        data.update({"runs": [], "references": [], "substudies": [], "manual_verdicts": [], "notes": []})
        save(folder, data)
        return data

    # parents without a board
    folder, ipath, spath = root, "", ""
    make(root, "", "", board if not names else None, False)
    for i, n in enumerate(names[:-1]):
        spath = f"{spath}/{n}" if spath else n
        ipath = f"{ipath}/{n}" if ipath else n
        folder = folder / (layout.STUDY_PREFIX + n)
        make(folder, spath, ipath, None, False)
    if names:
        n = names[-1]
        spath = f"{spath}/{n}" if spath else n
        ipath = f"{ipath}/{n}@{port}" if ipath else f"{n}@{port}"
        folder = folder / f"{layout.STUDY_PREFIX}{n}@{port}"
        make(folder, spath, ipath, board, False)
    top_folder = folder

    def children(folder, spath, ipath):
        study = design.study(spath)
        subs = []
        for s in study.data.get("substudies") or []:
            name = s["use"] if isinstance(s, dict) else s
            if isinstance(s, dict) and s.get("instances") == "per-board":
                continue
            sp = f"{spath}/{name}" if spath else name
            ip = f"{ipath}/{name}"
            sf = folder / (layout.STUDY_PREFIX + name)
            make(sf, sp, ip, None, True)
            subs.append(ip)
            children(sf, sp, ip)
        if subs:
            data = load(folder)
            data["substudies"] = sorted(set(data.get("substudies", [])) | {f"{top_name}/{x}" for x in subs})
            save(folder, data)

    if board:
        children(top_folder, study_path, ipath if names else "")
    # link each new folder into its parent's substudies
    link_parents(root)
    return top_folder


def link_parents(root):
    """Set the substudies list of each instance to its sub-instance folders."""
    root = Path(root)
    for f in layout.instance_folders(root):
        data = load(f)
        subs = sorted(load(c)["instance"] for c in f.iterdir() if c.is_dir() and (c / "instance.json").is_file())
        if subs != data.get("substudies", []):
            data["substudies"] = subs
            save(f, data)


def board_of(folder):
    """The board that this instance or a parent instance fixes, or None."""
    folder = Path(folder).resolve()
    for p in [folder, *folder.parents]:
        f = p / "instance.json"
        if not f.is_file():
            break
        b = json.loads(f.read_text()).get("board")
        if b:
            return b
    return None


def add(design, folder, run_dir, role="evidence", reason=None, copy=False):
    """Add a raw run to the run list of an instance; return the run id.

    A run in the instance folder (ex-<experiment>/<UTC>) is added as it is.
    With copy, a run from another place (for example an old flat results
    folder <experiment>/<UTC>) is copied into the instance first, with its
    seal; the original stays. The run is sealed if it has no seal yet.
    """
    folder = Path(folder).resolve()
    run_dir = Path(run_dir).resolve()
    if role not in ROLES:
        raise InstanceError(f"role {role!r}: use one of {', '.join(ROLES)} (a reference is not a run of this instance)")
    if role != "evidence" and not reason:
        raise InstanceError(f"role {role} needs a reason")
    manifest = json.loads((run_dir / "manifest.json").read_text())
    exp = manifest["experiment"]
    data = load(folder)
    root = layout.find_root(folder)
    study = design.study(layout.strip_board(layout.instance_path_of(folder, root)))
    rerun = {i["experiment"] for i in study.imports if i.get("mode") == "rerun"}
    if exp not in study.experiments and exp not in rerun:
        raise InstanceError(f"study {study.path}: {exp} is not one of its experiments, and it does not re-run it")
    board = board_of(folder)
    if board and manifest.get("board") != board:
        raise InstanceError(f"the run is for board {manifest.get('board')}, the instance for {board}")
    run_id = f"{exp}/{run_dir.name}"
    target = folder / layout.run_folder(run_id)
    copied_from = None
    if run_dir != target:
        if not copy:
            raise InstanceError(f"{run_dir} is not in the instance folder; use --copy")
        if target.exists():
            raise InstanceError(f"{target} exists")
        if seal.seal_path(run_dir).exists():
            seal.verify(run_dir)
        else:
            seal.write(run_dir)
        target.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["cp", "-a", str(run_dir), str(target)], check=True)
        shutil.copy2(seal.seal_path(run_dir), seal.seal_path(target))
        copied_from = str(run_dir)
    digest = seal.verify(target) if seal.seal_path(target).exists() else seal.write(target)
    if any(r["id"] == run_id for r in data["runs"]):
        raise InstanceError(f"{run_id} is already in the run list")
    entry = {"id": run_id, "digest": digest, "role": role}
    if reason:
        entry["reason"] = reason
    if copied_from:
        entry["copied_from"] = copied_from
    data["runs"].append(entry)
    save(folder, data)
    return run_id


def add_reference(folder, other_folder, run_id, reason):
    """Add a run of another instance as a reference (a fixed value that a check reads)."""
    other = load(other_folder)
    run = next((r for r in other["runs"] if r["id"] == run_id), None)
    if run is None:
        raise InstanceError(f"{other['instance']} has no run {run_id}")
    data = load(folder)
    data.setdefault("references", []).append(
        {"instance": other["instance"], "id": run_id, "digest": run["digest"], "role": "reference", "reason": reason})
    save(folder, data)


def add_verdict(folder, verdict, by, text=None, hypothesis=None, check=None, central_result=None, date=None):
    """Set the manual verdict of a check (hypothesis + check) or of a conclusion (central_result)."""
    import datetime
    if not by:
        raise InstanceError("a manual verdict needs the name of the person (--by)")
    if bool(hypothesis and check) == bool(central_result):
        raise InstanceError("give --hypothesis and --check, or --central-result")
    data = load(folder)
    keep = [m for m in data.get("manual_verdicts", [])
            if not ((hypothesis and m.get("hypothesis") == hypothesis and m.get("check") == check)
                    or (central_result and m.get("central_result") == central_result))]
    entry = {"hypothesis": hypothesis, "check": check} if hypothesis else {"central_result": central_result}
    entry.update({"verdict": verdict, "by": by, "date": date or datetime.date.today().isoformat()})
    if text:
        entry["text"] = text
    data["manual_verdicts"] = keep + [entry]
    save(folder, data)
