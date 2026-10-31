# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Campaigns: run all experiments below a study folder in a lab space.

    study.py campaign prepare FOLDER   build the images of all points (build cache)
    study.py campaign check FOLDER     the pre-flight check
    study.py campaign run FOLDER       check, then run each experiment and add
                                       each run to its instance
    study.py campaign status [ID]      the record of a campaign (default: the latest)
    study.py campaign resume ID        run the experiments that are not done

FOLDER is a study or experiment folder of the design (st-*, ex-*), or an
instance folder of the results tree of the lab space. The experiments of
a study come in the order of its study.yaml (experiments, then the re-run
imports), then those of its sub-studies, depth first. A sub-study with
"instances: per-board" is left out, unless FOLDER is in it.

The record .lab/campaigns/<id>.json (format latbench-campaign/1) is written
at the start and after each step, so a crash leaves a valid record. A
campaign holds the lock .lab/locks/board-<board>.lock of each board of its
plan: campaigns on different boards run at the same time. The
design repo gets the local ref refs/latbench/campaign/<id> at the commit of
the campaign, so the commit stays reachable (never pushed). Before each
experiment the repo must be clean and at that commit; if not, the campaign
stops. A failed experiment does not stop the campaign: the next one starts.

The engine (record, resume, order, locks, results build) is core/campaign.py; what only the
benchmarks have (the board lock rule, the pre-flight check, the wire check, the command of run.py)
is in campaign_hooks.py. This module keeps the plan and the names that study.py and the tests use.

After each run, a background process (low priority) builds the results
tree (extractors, run.json, experiment.json, study.json) and writes
index.html, while the next experiment runs. study.json marks the verdicts
that wait for an experiment of a running campaign as provisional.
"""

import platform
import shlex
import subprocess
import sys
from pathlib import Path

from probatrix.benchmarks import kind as benchkind
from probatrix.benchmarks import trees
from probatrix.core import campaign as engine
from probatrix.core import config, layout
from probatrix.core.design import Design, repo_rel

from . import instance
from .campaign_hooks import (BOARD, CampaignHooks, estimate, images_note,  # noqa: F401  (the names of the tools)
                             preflight, run_of_campaign, wire_check)

# The engine is core/campaign.py; these names are the ones that study.py, hwcheck.py and the tests use.
from probatrix.core.campaign import (DONE, FAILED, PLANNED, RUNNING, SKIPPED, CampaignError, Record,  # noqa: F401
                                     alive, drop_lock, drop_one, failed_note, final_build, latest, lock_fds,
                                     minutes, records, results_lock, run_subprocess, status_lines, stop_group,
                                     utc_id, utc_now)

FORMAT = "latbench-campaign/1"

AXIS = benchkind.KIND.instance_axis      # the instance axis (the board) of the kind


def study_py():
    return config.project().repo / "scripts" / "probatrix" / "benchmarks" / "study.py"


def run_py():
    return config.project().repo / "scripts" / "probatrix" / "benchmarks" / "run.py"


# ------------------------------------------------------------ plan
def resolve(lab, folder, design):
    """(study path, experiment name or None, board of an instance or None) of FOLDER."""
    folder = Path(folder).resolve()
    exp = None
    if folder.name.startswith(layout.EXPERIMENT_PREFIX):
        exp = folder.name[len(layout.EXPERIMENT_PREFIX):]
        folder = folder.parent
    if folder.is_relative_to(config.project().design_root):
        rel = folder.relative_to(config.project().design_root)
        path = "/".join(p[len(layout.STUDY_PREFIX):] for p in rel.parts)
        design.study(path)
        return path, exp, None
    root = lab.results / design.top.name
    if folder.is_relative_to(root) and (folder / "instance.json").is_file():
        ipath = layout.instance_path_of(folder, root)
        return AXIS.strip(ipath), exp, instance.board_of(folder)
    raise CampaignError(f"{folder} is not a study or experiment folder of the design {config.project().design_root}, "
                        f"and not an instance folder of {root}")


def experiments_of(design, path, inside):
    """[(study path, experiment)] of a study and its sub-studies, in the order of the design."""
    st = design.study(path)
    out = [(path, e) for e in st.experiments]
    out += [(path, i["experiment"]) for i in st.imports if i.get("mode") == "rerun"]
    for s in st.data.get("substudies") or []:
        name = s["use"] if isinstance(s, dict) else s
        sub = f"{path}/{name}" if path else name
        if isinstance(s, dict) and s.get("instances") == "per-board" and not inside.startswith(sub):
            continue
        out += experiments_of(design, sub, inside)
    return out


def plan(lab, folder, board=None, only=None, skip=None, design=None):
    """The experiments of a campaign: [{experiment, study, design, board, ...}]."""
    design = design or Design()
    path, one, inst_board = resolve(lab, folder, design)
    if board and inst_board and board != inst_board:
        raise CampaignError(f"--board {board}, but the instance is for {inst_board}")
    board = board or inst_board
    default_board = trees.load_boards()["default"]
    # an earlier name of a renamed experiment (folder ex-<old>, --only, --skip) means the current one
    one = design.canonical(one) if one else one
    only = [design.canonical(x) for x in only] if only else only
    skip = [design.canonical(x) for x in skip] if skip else skip
    items = [(p, e) for p, e in experiments_of(design, path, path) if one is None or e == one]
    if one is not None and not items:
        raise CampaignError(f"experiment {one} is not an experiment of the study {path}")
    out = []
    for p, e in items:
        if only and e not in only:
            continue
        ex = design.experiment(e)
        b = ex.data.get("board", default_board)
        item = {"experiment": e, "study": p, "design": repo_rel(ex.folder / "experiment.yaml"),
                "board": b, "state": PLANNED}
        if skip and e in skip:
            item.update(state=SKIPPED, note="--skip")
        elif board and b != board:
            item.update(state=SKIPPED, note=f"the experiment is for the board {b}, the campaign for {board}")
        out.append(item)
    if not out:
        raise CampaignError("no experiments to run")
    return out


def find_instance(lab, design, study_path, board):
    root = lab.results / design.top.name
    if not root.is_dir():
        return None
    for f in layout.instance_folders(root):
        if AXIS.strip(layout.instance_path_of(f, root)) == study_path and instance.board_of(f) == board:
            return f
    return None


def board_level(design, study_path):
    """The study path whose instance fixes the board: the first level below the top study (as
    in the results of the night of 2026-10-26), or the level of a per-board sub-study."""
    names = study_path.split("/")
    level = names[0]
    for i in range(1, len(names)):
        parent = design.study("/".join(names[:i]))
        for s in parent.data.get("substudies") or []:
            if isinstance(s, dict) and s.get("use") == names[i] and s.get("instances") == "per-board":
                level = "/".join(names[:i + 1])
    return level


def planned_instance(lab, design, study_path, board):
    """(folder, exists) of the instance of a study for a board: the one there, or the one that
    ensure_instance would make."""
    f = find_instance(lab, design, study_path, board)
    if f is not None:
        return f, True
    level = board_level(design, study_path)
    names = study_path.split("/")
    k = len(level.split("/"))
    rel = layout.study_folder("/".join(names[:k]))
    rel = rel.parent / AXIS.folder_name(rel.name, instance.board_port(board))
    return lab.results / design.top.name / rel / layout.study_folder("/".join(names[k:])), False


def ensure_instance(lab, design, study_path, board, log=print):
    """The instance folder of a study for a board; made (instance new) if there is none."""
    f = find_instance(lab, design, study_path, board)
    if f is not None:
        return f
    level = board_level(design, study_path)
    instance.new(design, lab.results, design.top.name, level, board)
    log(f"made the instances of {level} for {board}")
    f = find_instance(lab, design, study_path, board)
    if f is None:
        raise CampaignError(f"no instance of {study_path} for {board} after 'instance new {level}'")
    return f


def pending(lab, design=None):
    """{(instance folder, experiment)} that a running campaign of the lab space has still to run.

    A campaign counts from its start (also during its pre-flight check) to its
    end, while it holds the locks of its boards; a campaign whose process
    is gone does not count (aborted). A campaign of another lab space (imported) counts while its
    record says running. An experiment that has no instance yet counts for
    the instance of its study and board, if there is one.
    """
    out = {}
    for rec in records(lab):
        d = rec.data or {}
        own = d.get("lab", {}).get("id") == lab.id and d.get("host") == platform.node()
        if own and (d.get("status") not in (PLANNED, RUNNING) or rec.id not in lock_holders(lab).values()):
            continue
        if not own and d.get("status") != RUNNING:
            continue
        for e in d.get("experiments", []):
            if e.get("state") not in (PLANNED, RUNNING):
                continue
            folder = lab.results / e["instance"] if e.get("instance") else None
            if folder is None and e.get("study") and e.get("board"):
                design = design or Design()
                folder = find_instance(lab, design, e["study"], e["board"])
            if folder is not None:
                out[(str(folder), e["experiment"])] = rec.id
    return out


# ------------------------------------------------------------ board lock
# A campaign holds one lock for each board of its plan: .lab/locks/board-<key>.lock (core/campaign.py;
# the key rule is the lock_key of the instance axis, BOARD in campaign_hooks.py).
def lock_file(lab, board):
    return BOARD.lock_file(lab, board)


def lock_holders(lab):
    """{board lock file name: campaign id} of the locks that a campaign holds now."""
    return engine.lock_holders(lab, BOARD)


def lock_holder(lab, board=None):
    """The campaign that holds the lock of the board (any board: None), or None."""
    return engine.lock_holder(lab, BOARD, board)


def take_lock(lab, cid, boards):
    """Take the locks of the boards (all or none); CampaignError if a campaign holds one."""
    engine.take_lock(lab, cid, boards, BOARD)


# ------------------------------------------------------------ record, run
def new_record(lab, folder, board, items, argv, role="evidence", reason=None, hwcheck_each=False):
    return engine.new_record(lab, folder, board, items, argv, CampaignHooks(), role=role, reason=reason,
                             extra={"hwcheck_each": True} if hwcheck_each else None)


class Post(engine.Post):
    """The results build after each run: study.py analysis build, then html."""

    def command(self):
        return " && ".join(shlex.join([sys.executable, str(study_py()), "analysis", step, str(self.root)])
                           for step in ("build", "html"))


def run_campaign(rec, design=None, hwcheck=True, warn_as_error=False, log=print):
    """Run the experiments of a record that are not done; return the number of failed experiments."""
    return engine.run_campaign(rec, CampaignHooks(), design=design, hwcheck=hwcheck,
                               warn_as_error=warn_as_error, log=log)


def detach(rec, extra):
    """Start 'campaign resume <id>' in a new session; its output goes to <id>/campaign.log."""
    rec.log_dir.mkdir(parents=True, exist_ok=True)
    log = rec.log_dir / "campaign.log"
    with open(log, "a") as f:
        p = subprocess.Popen([sys.executable, "-u", str(study_py()), "campaign", "resume", rec.id, *extra],
                             stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, cwd=rec.lab.folder,
                             start_new_session=True)
    return p.pid, log


