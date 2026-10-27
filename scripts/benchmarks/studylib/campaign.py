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
at the start and after each step, so a crash leaves a valid record. The
lock .lab/campaign.lock allows one campaign at a time in a lab space. The
design repo gets the local ref refs/latbench/campaign/<id> at the commit of
the campaign, so the commit stays reachable (never pushed). Before each
experiment the repo must be clean and at that commit; if not, the campaign
stops. A failed experiment does not stop the campaign: the next one starts.

After each run, a background process (low priority) builds the results
tree (extractors, run.json, experiment.json, study.json) and writes
index.html, while the next experiment runs. study.json marks the verdicts
that wait for an experiment of a running campaign as provisional.
"""

import datetime
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import yaml

import trees

from . import instance, jsonout, layout
from .design import Design, repo_rel

FORMAT = "latbench-campaign/1"
DONE, FAILED, PLANNED, RUNNING, SKIPPED = "done", "failed", "planned", "running", "skipped"


class CampaignError(Exception):
    pass


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


def utc_id(t=None):
    return (t or utc_now()).strftime("%Y%m%dT%H%M%SZ")


def study_py():
    return trees.REPO_DIR / "scripts" / "benchmarks" / "study.py"


def run_py():
    return trees.REPO_DIR / "scripts" / "benchmarks" / "run.py"


# ------------------------------------------------------------ plan
def resolve(lab, folder, design):
    """(study path, experiment name or None, board of an instance or None) of FOLDER."""
    folder = Path(folder).resolve()
    exp = None
    if folder.name.startswith(layout.EXPERIMENT_PREFIX):
        exp = folder.name[len(layout.EXPERIMENT_PREFIX):]
        folder = folder.parent
    if folder.is_relative_to(trees.STUDIES_DIR):
        rel = folder.relative_to(trees.STUDIES_DIR)
        path = "/".join(p[len(layout.STUDY_PREFIX):] for p in rel.parts)
        design.study(path)
        return path, exp, None
    root = lab.results / design.top.name
    if folder.is_relative_to(root) and (folder / "instance.json").is_file():
        ipath = layout.instance_path_of(folder, root)
        return layout.strip_board(ipath), exp, instance.board_of(folder)
    raise CampaignError(f"{folder} is not a study or experiment folder of the design {trees.STUDIES_DIR}, "
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
        if layout.strip_board(layout.instance_path_of(f, root)) == study_path and instance.board_of(f) == board:
            return f
    return None


def ensure_instance(lab, design, study_path, board, log=print):
    """The instance folder of a study for a board; made (instance new) if there is none."""
    f = find_instance(lab, design, study_path, board)
    if f is not None:
        return f
    # The board is fixed at the first level below the top study (as in the results of the
    # night of 2026-10-26), or at the level of a per-board sub-study.
    names = study_path.split("/")
    level = names[0]
    for i in range(1, len(names)):
        parent = design.study("/".join(names[:i]))
        for s in parent.data.get("substudies") or []:
            if isinstance(s, dict) and s.get("use") == names[i] and s.get("instances") == "per-board":
                level = "/".join(names[:i + 1])
    instance.new(design, lab.results, design.top.name, level, board)
    log(f"made the instances of {level} for {board}")
    f = find_instance(lab, design, study_path, board)
    if f is None:
        raise CampaignError(f"no instance of {study_path} for {board} after 'instance new {level}'")
    return f


# ------------------------------------------------------------ record
class Record:
    def __init__(self, lab, cid):
        self.lab, self.id = lab, cid
        self.path = lab.campaigns / f"{cid}.json"
        self.data = json.loads(self.path.read_text()) if self.path.is_file() else None

    @property
    def log_dir(self):
        return self.lab.campaigns / self.id

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        jsonout.write(tmp, self.data)
        tmp.rename(self.path)

    def set(self, **kw):
        self.data.update(kw)
        self.save()


def new_record(lab, folder, board, items, argv):
    cid = utc_id()
    while (lab.campaigns / f"{cid}.json").exists():
        time.sleep(1)
        cid = utc_id()
    rev, dirty = trees.repo_state(trees.REPO_DIR)
    if dirty:
        raise CampaignError(f"the design repo {trees.REPO_DIR} is dirty, commit first:\n{dirty}")
    rec = Record(lab, cid)
    rec.data = {"format": FORMAT, "id": cid, "lab": lab.describe(), "host": platform.node(),
                "command": argv, "cwd": os.getcwd(), "folder": str(Path(folder).resolve()), "board": board,
                "repo": {"path": str(trees.REPO_DIR), "rev": rev}, "ref": f"refs/latbench/campaign/{cid}",
                "status": PLANNED, "created": utc_now().isoformat(), "experiments": items}
    rec.save()
    return rec


def latest(lab):
    """The latest campaign of this lab space (not an imported one, <id>@<lab>)."""
    files = sorted(f for f in lab.campaigns.glob("*.json") if "@" not in f.stem) if lab.campaigns.is_dir() else []
    return Record(lab, files[-1].stem) if files else None


def records(lab):
    return [Record(lab, f.stem) for f in sorted(lab.campaigns.glob("*.json"))] if lab.campaigns.is_dir() else []


def alive(pid):
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, TypeError):
        return False
    except PermissionError:
        return True
    return True


def pending(lab):
    """{(instance folder, experiment)} that a running campaign of the lab space has still to run.

    A campaign of this host whose process is gone is not running (aborted).
    A campaign of another lab space (imported) counts while its record says running.
    """
    out = {}
    for rec in records(lab):
        d = rec.data or {}
        if d.get("status") != RUNNING:
            continue
        if d.get("lab", {}).get("id") == lab.id and d.get("host") == platform.node() and not alive(d.get("pid")):
            continue
        for e in d.get("experiments", []):
            if e.get("state") in (PLANNED, RUNNING) and e.get("instance"):
                out[(str(lab.results / e["instance"]), e["experiment"])] = rec.id
    return out


# ------------------------------------------------------------ lock
def take_lock(lab, cid):
    lab.lock.parent.mkdir(parents=True, exist_ok=True)
    if lab.lock.exists():
        d = json.loads(lab.lock.read_text())
        if d.get("host") == platform.node() and not alive(d.get("pid")):
            lab.lock.unlink()
        else:
            raise CampaignError(f"the campaign {d.get('id')} runs (pid {d.get('pid')}, lock {lab.lock})")
    fd = os.open(lab.lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    with os.fdopen(fd, "w") as f:
        json.dump({"id": cid, "pid": os.getpid(), "host": platform.node()}, f)


def drop_lock(lab, cid):
    if lab.lock.exists() and json.loads(lab.lock.read_text()).get("id") == cid:
        lab.lock.unlink()


# ------------------------------------------------------------ check
def run_subprocess(cmd, log, cwd, nice=False):
    with open(log, "a") as f:
        f.write(f"$ {' '.join(map(str, cmd))}\n")
        f.flush()
        r = subprocess.run([str(c) for c in cmd], cwd=cwd, stdout=f, stderr=subprocess.STDOUT,
                           preexec_fn=(lambda: os.nice(10)) if nice else None)
    return r.returncode


def estimate(lab, design, exp):
    """(seconds, bytes) of the last run of an experiment in the lab space, or (None, None)."""
    root = lab.results / design.top.name
    best = None
    for m in sorted(root.glob(f"**/{layout.EXPERIMENT_PREFIX}{exp}/*/manifest.json")) if root.is_dir() else []:
        d = json.loads(m.read_text())
        if d.get("started") and d.get("finished"):
            t = (datetime.datetime.fromisoformat(d["finished"]) - datetime.datetime.fromisoformat(d["started"]))
            size = sum(f.stat().st_size for f in m.parent.rglob("*") if f.is_file())
            best = (t.total_seconds(), size)
    return best or (None, None)


def preflight(lab, items, design, hwcheck=True, warn_as_error=False, log=print):
    """The pre-flight check: [(status, what, text)] with status ok / warn / fail."""
    import hwmap
    import run

    from . import hwcheck as hwc
    from . import lint as lintmod
    out = []

    def add(status, what, text=""):
        out.append((status, what, text))
        log(f"  {status:4} {what}{': ' + text if text else ''}")

    todo = [e for e in items if e["state"] in (PLANNED, FAILED, RUNNING)]
    rev, dirty = trees.repo_state(trees.REPO_DIR)
    add("fail" if dirty else "ok", "design repo", f"{trees.REPO_DIR} at {rev[:12]}" + (" is dirty" if dirty else ""))
    problems = lintmod.lint()
    mine = list({str(p): p for e in todo
                 for p in lintmod.lint_for_experiment(trees.REPO_DIR / e["design"], problems)}.values())
    errors = [p for p in mine if p.severity == lintmod.ERROR]
    if errors:
        add("fail", "lint", f"{len(errors)} errors, first: {errors[0]}")
    elif mine:
        add("fail" if warn_as_error else "warn", "lint", f"{len(mine)} warnings (study.py lint)")
    else:
        add("ok", "lint")
    cfg = trees.load(lab=lab)
    try:
        add("ok", "zephyr sdk", str(trees.check_toolchain(cfg)))
    except trees.TreeError as e:
        add("fail", "zephyr sdk", str(e))
    need_trees = sorted({t for e in todo for t in yaml.safe_load((trees.REPO_DIR / e["design"]).read_text())["trees"]})
    for t in need_trees:
        try:
            trees.check_tree(cfg, t)
            add("ok", f"tree {t}")
        except trees.TreeError as e:
            add("fail", f"tree {t}", str(e).splitlines()[0])
    total = cached = 0
    secs, size, unknown = 0.0, 0, []
    for e in todo:
        try:
            n, c = run.cache_state(trees.REPO_DIR / e["design"], lab)
            total, cached = total + n, cached + c
        except (SystemExit, trees.TreeError, OSError) as x:
            add("fail", f"images of {e['experiment']}", str(x))
        s, b = estimate(lab, design, e["experiment"])
        if s is None:
            unknown.append(e["experiment"])
        else:
            secs, size = secs + s, size + b
    add("ok" if cached == total else "warn", "images",
        f"{cached} of {total} in the build cache" + ("" if cached == total else
                                                     f"; 'campaign prepare' or the run builds {total - cached}"))
    boards = sorted({e["board"] for e in todo})
    try:
        entries = hwmap.load(lab.hw_map)
    except hwmap.HwMapError as x:
        entries = None
        add("fail", "hardware map", str(x))
    for b in boards:
        if entries is None:
            break
        try:
            hw = hwmap.hardware(hwmap.select(entries, b, path=str(lab.hw_map)))
        except hwmap.HwMapError as x:
            add("fail", f"board {b}", str(x))
            continue
        add("ok" if Path(hw["serial"]).exists() else "fail", f"board {b}",
            f"probe {hw['probe']}, console {hw['serial']}" + ("" if Path(hw["serial"]).exists() else " is missing"))
        try:
            import serial
            serial.Serial(hw["serial"], hw["baud"], timeout=0.1, exclusive=True).close()
            add("ok", f"console of {b}", "free")
        except (OSError, ValueError) as x:
            add("fail", f"console of {b}", f"not free: {x}")
        if hwcheck:
            try:
                ok, lines = hwc.check(lab, b, log=lambda m: None)
                add("ok" if ok else "fail", f"loopback wire of {b}", lines[-1] if lines else "")
            except (hwc.HwCheckError, hwmap.HwMapError, trees.TreeError) as x:
                add("fail", f"loopback wire of {b}", str(x).splitlines()[0])
    free = shutil.disk_usage(lab.results if lab.results.exists() else lab.folder).free
    add("ok" if free > 2 * size else "fail", "disk", f"{free / 2**30:.0f} GiB free, the runs need about {size / 2**20:.0f} MiB")
    dur = f"about {secs / 3600:.1f} h" if secs else "unknown"
    add("ok", "duration", dur + (f" (no earlier run of {', '.join(unknown)})" if unknown else ""))
    return out


# ------------------------------------------------------------ run
class Post:
    """The background build of the results tree after each run (one at a time, low priority)."""

    def __init__(self, rec, root):
        self.rec, self.root, self.proc, self.again, self.n = rec, root, None, False, 0

    def kick(self):
        if self.proc is not None and self.proc.poll() is None:
            self.again = True
            return
        self.finish()
        self.n += 1
        log = self.rec.log_dir / "post.log"
        f = open(log, "a")
        f.write(f"=== build {self.n} at {utc_now().isoformat()}\n")
        f.flush()
        cmd = f"{sys.executable} {study_py()} build {self.root} && {sys.executable} {study_py()} html {self.root}"
        self.proc = subprocess.Popen(["sh", "-c", cmd], stdout=f, stderr=subprocess.STDOUT, cwd=self.rec.lab.folder,
                                     preexec_fn=lambda: os.nice(10))
        self.again = False

    def finish(self):
        if self.proc is not None and self.proc.poll() is not None:
            rc = self.proc.returncode
            self.rec.data.setdefault("post", []).append({"n": self.n, "rc": rc, "finished": utc_now().isoformat()})
            self.rec.save()
            self.proc = None
            if self.again:
                self.kick()

    def wait(self):
        while self.proc is not None:
            self.proc.wait()
            self.finish()


def run_campaign(rec, design=None, hwcheck=True, warn_as_error=False, log=print):
    """Run the experiments of a record that are not done; return the number of failed experiments."""
    lab = rec.lab
    design = design or Design()
    d = rec.data
    rev, dirty = trees.repo_state(trees.REPO_DIR)
    if rev != d["repo"]["rev"] or dirty:
        raise CampaignError(f"the design repo is at {rev[:12]}{' (dirty)' if dirty else ''}, the campaign "
                            f"{rec.id} at {d['repo']['rev'][:12]}: check out its commit (ref {d['ref']})")
    take_lock(lab, rec.id)
    rec.log_dir.mkdir(parents=True, exist_ok=True)
    stop = {"why": None}

    def on_term(signum, frame):
        stop["why"] = f"signal {signum}"
        raise KeyboardInterrupt

    old = signal.signal(signal.SIGTERM, on_term)
    try:
        trees.git("update-ref", d["ref"], d["repo"]["rev"], cwd=trees.REPO_DIR)
        log(f"campaign {rec.id}: pre-flight check")
        res = preflight(lab, d["experiments"], design, hwcheck=hwcheck, warn_as_error=warn_as_error, log=log)
        d["preflight"] = [{"status": s, "what": w, "text": t} for s, w, t in res]
        if any(s == "fail" for s, _, _ in res):
            rec.set(status=FAILED, finished=utc_now().isoformat(), stopped="the pre-flight check failed")
            log("the pre-flight check failed; nothing runs")
            return len([e for e in d["experiments"] if e["state"] != SKIPPED])
        rec.set(status=RUNNING, pid=os.getpid(), started=d.get("started") or utc_now().isoformat())
        root = lab.results / design.top.name
        post = Post(rec, root)
        failed = 0
        for e in d["experiments"]:
            if e["state"] in (DONE, SKIPPED):
                continue
            now, dirty = trees.repo_state(trees.REPO_DIR)
            if now != d["repo"]["rev"] or dirty:
                rec.set(stopped=f"the design repo changed before {e['experiment']} ({now[:12]}"
                                f"{', dirty' if dirty else ''})")
                log(d["stopped"])
                break
            folder = ensure_instance(lab, design, e["study"], e["board"], log=log)
            e.update(instance=str(folder.relative_to(lab.results)), state=RUNNING, started=utc_now().isoformat(),
                     log=str((rec.log_dir / f"{e['experiment']}.log").relative_to(lab.folder)))
            e.pop("note", None)
            rec.save()
            log(f"=== {e['experiment']} ({e['instance']})")
            cmd = [sys.executable, run_py(), trees.REPO_DIR / e["design"], "--out", folder]
            if warn_as_error:
                cmd.append("--warn-as-error")
            rc = run_subprocess(cmd, lab.folder / e["log"], cwd=lab.folder)
            e.update(rc=rc, finished=utc_now().isoformat())
            run_dir = None
            for line in (lab.folder / e["log"]).read_text().splitlines():
                if line.startswith("results in "):
                    run_dir = Path(line.split()[2])
            if rc == 0 and run_dir is not None:
                try:
                    e["run"] = instance.add(design, folder, run_dir)
                    e["state"] = DONE
                except instance.InstanceError as x:
                    e.update(state=FAILED, note=f"instance add: {x}")
            else:
                e["state"] = FAILED
                partial = sorted((folder / f"{layout.EXPERIMENT_PREFIX}{e['experiment']}").glob("2*Z"))
                if partial and not (partial[-1].parent / f"{partial[-1].name}.sha256").exists():
                    e["note"] = f"a part of a run is left in {partial[-1].relative_to(lab.results)} (not in the run list)"
            failed += e["state"] == FAILED
            rec.save()
            log(f"    {e['state']} (rc {rc})" + (f", run {e['run']}" if e.get("run") else ""))
            if e["state"] == DONE:
                post.kick()
            post.finish()
        rec.set(status=DONE if not d.get("stopped") else FAILED, finished=utc_now().isoformat())
        log("waiting for the last build of the results")
        post.wait()
        post.kick()
        post.wait()
        log(f"campaign {rec.id}: {d['status']}, {failed} experiments failed; results {root}/index.html")
        return failed
    except KeyboardInterrupt:
        for e in d["experiments"]:
            if e["state"] == RUNNING:
                e.update(state=FAILED, note=f"stopped ({stop['why'] or 'interrupt'})")
        rec.set(status="aborted", finished=utc_now().isoformat(), stopped=stop["why"] or "interrupt")
        raise CampaignError(f"campaign {rec.id} aborted") from None
    finally:
        signal.signal(signal.SIGTERM, old)
        drop_lock(lab, rec.id)


def detach(rec, extra):
    """Start 'campaign resume <id>' in a new session; its output goes to <id>/campaign.log."""
    rec.log_dir.mkdir(parents=True, exist_ok=True)
    log = rec.log_dir / "campaign.log"
    with open(log, "a") as f:
        p = subprocess.Popen([sys.executable, str(study_py()), "campaign", "resume", rec.id, *extra],
                             stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, cwd=rec.lab.folder,
                             start_new_session=True)
    return p.pid, log


def status_lines(rec):
    d = rec.data
    out = [f"campaign {rec.id}: {d['status']}" + (f" ({d['stopped']})" if d.get("stopped") else ""),
           f"  lab {d['lab']['id']} on {d['host']}, repo {d['repo']['rev'][:12]}, folder {d['folder']}"]
    for e in d["experiments"]:
        extra = f"run {e['run']}" if e.get("run") else e.get("note", "")
        out.append(f"  {e['state']:8} {e['experiment']:28} {e.get('instance', '-'):60} {extra}")
    for p in d.get("post", [])[-1:]:
        out.append(f"  last results build: rc {p['rc']} at {p['finished']}")
    return out
