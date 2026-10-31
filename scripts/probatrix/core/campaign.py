# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The campaign engine: a list of runs, in order, with a record, a resume and a resource lock.

A campaign runs the experiments of a plan one after the other. Each experiment is a run of the
run tool of the kind (a subprocess; its lines are read as core/runner.py writes them). The engine
holds:

- the record <lab>/.lab/campaigns/<id>.json (written at the start and after each step, so a crash
  leaves a valid record), its states (planned, running, done, failed, skipped), the resume, the
  stop on a change of the repo, the local ref of the campaign;
- the resource lock: one flock file for each resource key of the plan
  (<lab>/.lab/locks/<label>-<key>.lock). A Resource says the label and the key rule (the board
  of the benchmarks). A kind without a resource (hooks.resource is None, for example the formal
  kinds) takes no lock;
- the background build of the results after each run (Post);
- the subprocess of a run: its own session, one stop of the whole process group on an interrupt.

What depends on the kind comes from a Hooks object (the defaults suit a kind with no resource and no
pre-flight check): the repo state and its ref, the keys, the pre-flight check, the instance of an
experiment, the check before a run, the command of the run tool, a note on a finished run, the
results build. benchmarks/campaign_hooks.py is the hooks object of the benchmarks.

"lab" is a duck type: a folder (.folder), the results tree (.results), .campaigns, .locks, .id and
describe(). The plan (which experiments, which instance) stays with the kind.
"""

import datetime
import fcntl
import json
import os
import platform
import signal
import subprocess
import sys
import time
from pathlib import Path

from probatrix.core import config, jsonout, runner, seal
from probatrix.core.design import Design
from probatrix.core.errors import CampaignError

DONE, FAILED, PLANNED, RUNNING, SKIPPED = "done", "failed", "planned", "running", "skipped"


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


def utc_id(t=None):
    return (t or utc_now()).strftime("%Y%m%dT%H%M%SZ")


def minutes(secs):
    return f"{secs / 60:.0f} min" if secs >= 90 else f"{secs:.0f} s"


# ------------------------------------------------------------ hooks
class Resource:
    """The thing that one campaign at a time uses (a board): the label of the lock file and the key rule."""

    def __init__(self, label, lock_key):
        self.label, self.lock_key = label, lock_key

    def lock_file(self, lab, key):
        return lab.locks / f"{self.label}-{self.lock_key(key)}.lock"


class Hooks:
    """What the engine takes from the kind. A subclass overrides what its kind has."""

    kind = None             # the Kind (names of the format and of the ref)
    resource = None         # a Resource, or None: no lock

    def repo(self):
        return config.project().repo

    def repo_state(self):
        """(rev, dirty lines) of the design repo."""
        return runner.repo_state(self.repo())

    def update_ref(self, ref, rev):
        runner.git("update-ref", ref, rev, cwd=self.repo())

    def python_info(self):
        """Packages of the Python that runs the campaign (the record keeps them)."""
        return None

    def resource_keys(self, data):
        """The resource keys of the plan (data: the record): what the locks are taken for."""
        return []

    def preflight(self, lab, items, design, hwcheck, warn_as_error, log, locked):
        """[(status, what, text)], status ok / warn / fail."""
        return []

    def run_of_campaign(self, lab, e, cid):
        """The id of a run that the campaign cid added for the experiment e after e started, or None."""
        return None

    def ensure_instance(self, lab, design, e, log):
        """The instance folder (below lab.results) of the experiment e; make it if it is missing."""
        raise NotImplementedError

    def before_run(self, rec, e, hwcheck):
        """None, or the reason why the experiment e must not run (a check of the resource before the run)."""
        return None

    def run_command(self, rec, e, folder, warn_as_error):
        """The command (a list) of the run tool for the experiment e into the instance folder."""
        raise NotImplementedError

    def run_note(self, folder, run_id):
        """Text for the log line of a finished run, or None."""
        return None

    def post(self, rec, root):
        """The Post of the campaign (the build of the results after each run)."""
        raise NotImplementedError


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


def new_record(lab, folder, board, items, argv, hooks, role="evidence", reason=None, extra=None):
    """Write the record of a new campaign (status planned). extra: more keys after the reason."""
    cid = utc_id()
    while (lab.campaigns / f"{cid}.json").exists():
        time.sleep(1)
        cid = utc_id()
    rev, dirty = hooks.repo_state()
    if dirty:
        raise CampaignError(f"the design repo {hooks.repo()} is dirty, commit first:\n{dirty}")
    rec = Record(lab, cid)
    rec.data = {"format": hooks.kind.format_id("campaign", 1), "id": cid, "lab": lab.describe(),
                "host": platform.node(),
                "command": argv, "cwd": os.getcwd(), "folder": str(Path(folder).resolve()), "board": board,
                "repo": {"path": str(hooks.repo()), "rev": rev}, "ref": hooks.kind.ref("campaign", cid),
                "python": {"executable": sys.executable, "prefix": sys.prefix,
                           "version": platform.python_version(), "packages": hooks.python_info()},
                "role": role, **({"reason": reason} if reason else {}),
                **(extra or {}),
                "status": PLANNED, "created": utc_now().isoformat(), "experiments": items}
    if role != "evidence" and not reason:
        raise CampaignError(f"role {role} needs a reason (--reason)")
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


def status_lines(rec):
    d = rec.data
    status = d["status"]
    if "@" in rec.id and status in (PLANNED, RUNNING):
        status = f"imported, not complete ({status} at the export of {d.get('running_at_export', '?')})"
    elif status in (PLANNED, RUNNING) and d.get("host") == platform.node() and d.get("pid") and not alive(d["pid"]):
        status = f"{status}, but its process {d['pid']} is gone ('campaign resume {rec.id}' goes on)"
    elif "@" in rec.id and status == "closed":
        status = f"imported, closed here at {d.get('closed', '?')} (it was {d.get('status_at_import')})"
    out = [f"campaign {rec.id}: {status}" + (f" ({d['stopped']})" if d.get("stopped") else ""),
           f"  lab {d['lab']['id']} on {d['host']}, repo {d['repo']['rev'][:12]}, folder {d['folder']}"]
    for e in d["experiments"]:
        extra = f"run {e['run']}" if e.get("run") else e.get("note", "")
        out.append(f"  {e['state']:8} {e['experiment']:28} {e.get('instance', '-'):60} {extra}")
    for p in d.get("post", [])[-1:]:
        out.append(f"  last results build: rc {p['rc']} (seen at {p.get('noticed', p.get('finished'))})")
    return out


# ------------------------------------------------------------ lock
# A campaign holds one lock for each key of its plan: .lab/locks/<label>-<key>.lock, an flock
# (the kernel drops it when the process ends, so a crash or a kill leaves no stale lock). Two
# campaigns on different keys run at the same time; two on one key do not. The file has the
# id and pid of the holder (information). The results build has a lock of its own
# (results_lock), so the builds of two campaigns run one after the other.
_LOCKS = {}


def _holder(path):
    if not path.exists():
        return None
    with open(path) as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            try:
                return json.loads(f.read() or "{}").get("id") or "?"
            except ValueError:
                return "?"
        fcntl.flock(f, fcntl.LOCK_UN)
    return None


def lock_holders(lab, resource):
    """{lock file name without the label: campaign id} of the locks that a campaign holds now."""
    out = {}
    if resource is None:
        return out
    for f in sorted(lab.locks.glob(f"{resource.label}-*.lock")) if lab.locks.is_dir() else []:
        h = _holder(f)
        if h:
            out[f.stem[len(resource.label) + 1:]] = h
    return out


def lock_holder(lab, resource, key=None):
    """The campaign that holds the lock of the key (any key: None), or None."""
    if resource is None:
        return None
    if key is not None:
        return _holder(resource.lock_file(lab, key))
    return next(iter(lock_holders(lab, resource).values()), None)


def take_lock(lab, cid, keys, resource):
    """Take the locks of the keys (all or none); CampaignError if a campaign holds one."""
    if resource is None:
        return
    lab.locks.mkdir(parents=True, exist_ok=True)
    taken = []
    for b in sorted(set(keys)):
        path = resource.lock_file(lab, b)
        f = open(path, "a+")
        d = None
        for _ in range(20):
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                d = None
                break
            except BlockingIOError:
                f.seek(0)
                text = f.read()
                try:
                    d = json.loads(text or "{}")
                except ValueError:
                    d = {}
                if text:
                    break                   # a holder (it writes its id at once)
                time.sleep(0.05)            # no holder text: a short probe of lock_holder()
        if d is not None:
            f.close()
            for t in taken:
                drop_one(t)
            raise CampaignError(f"the campaign {d.get('id', '?')} runs on {b} (pid {d.get('pid', '?')}, "
                                f"lock {path})") from None
        f.seek(0)
        f.truncate()
        json.dump({"id": cid, "pid": os.getpid(), "host": platform.node(), resource.label: b}, f)
        f.flush()
        _LOCKS[(str(path), cid)] = f
        taken.append((str(path), cid))


def lock_fds(cid):
    """The file descriptors of the locks that the campaign cid holds."""
    return [f.fileno() for (path, c), f in _LOCKS.items() if c == cid]


def drop_one(key):
    f = _LOCKS.pop(key, None)
    if f is not None:
        f.seek(0)
        f.truncate()
        f.close()


def drop_lock(lab, cid):
    for key in [k for k in _LOCKS if k[1] == cid]:
        drop_one(key)


class results_lock:
    """The lock of the results build of a lab space (with: wait for it)."""

    def __init__(self, lab):
        self.path = lab.locks / "results.lock"

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.f = open(self.path, "a+")
        fcntl.flock(self.f, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        self.f.close()


# ------------------------------------------------------------ run
def run_subprocess(cmd, log, cwd, nice=False, pass_fds=()):
    """Run cmd in a session of its own; on an interrupt, stop its whole process group (the run tool and
    its flash tools, which hold the probe), then raise again. pass_fds: the locks of the
    campaign: the child holds them too, so a resource stays locked while a run tool of a dead campaign
    still runs."""
    with open(log, "a") as f:
        f.write(f"$ {' '.join(map(str, cmd))}\n")
        f.flush()
        p = subprocess.Popen([str(c) for c in cmd], cwd=cwd, stdout=f, stderr=subprocess.STDOUT,
                             start_new_session=True, preexec_fn=(lambda: os.nice(10)) if nice else None,
                             pass_fds=tuple(pass_fds))
        try:
            return p.wait()
        except BaseException:
            stop_group(p)
            raise


def stop_group(p, grace=20):
    for sig, wait in ((signal.SIGTERM, grace), (signal.SIGKILL, 5)):
        try:
            os.killpg(p.pid, sig)
        except ProcessLookupError:
            return
        try:
            p.wait(timeout=wait)
            return
        except subprocess.TimeoutExpired:
            continue


class Post:
    """The background build of the results tree after each run: one process at a time, low priority.

    kick() asks for a build; if one runs, the next build starts after it (only one more, however
    many runs end in the meantime). poll() notes an ended build and starts the next one.
    command() is the shell command of one build (the kind gives it in a subclass).
    """

    def __init__(self, rec, root):
        self.rec, self.root, self.proc, self.again, self.n = rec, root, None, False, 0

    def command(self):
        raise NotImplementedError

    def _start(self):
        self.n += 1
        log = self.rec.log_dir / "post.log"
        with open(log, "a") as f:
            f.write(f"=== build {self.n} at {utc_now().isoformat()}\n")
            f.flush()
            self.proc = subprocess.Popen(["sh", "-c", self.command()], stdout=f, stderr=subprocess.STDOUT,
                                         cwd=self.rec.lab.folder, preexec_fn=lambda: os.nice(10))
        self.again = False

    def poll(self):
        if self.proc is not None and self.proc.poll() is not None:
            # "noticed": the time when the campaign saw the end (after a run), not the end itself
            self.rec.data.setdefault("post", []).append({"n": self.n, "rc": self.proc.returncode,
                                                         "noticed": utc_now().isoformat()})
            self.rec.save()
            self.proc = None
        if self.proc is None and self.again:
            self._start()

    def kick(self):
        self.poll()
        if self.proc is None:
            self._start()
        else:
            self.again = True

    def wait(self):
        while self.proc is not None or self.again:
            if self.proc is not None:
                self.proc.wait()
            self.poll()


def final_build(post, log):
    """After an abort: one more results build, so that no verdict stays provisional."""
    if post is None:
        return
    try:
        log("one more build of the results (the campaign is aborted: the verdicts become final)")
        post.kick()
        post.wait()
    except BaseException as x:          # a second Ctrl-C: the next build does it
        log(f"no final build ({type(x).__name__})")


def read_run_log(text):
    """(run id that the tool added or None, run folder or None) from the lines of a run tool (core/runner.py)."""
    added, run_dir = None, None
    for line in text.splitlines():
        if line.startswith(runner.RUN_FOLDER_LINE):         # printed when the tool makes the folder
            run_dir = Path(line.split(maxsplit=2)[2])
        elif line.startswith(runner.RESULTS_LINE):
            run_dir = Path(line.split()[2])
        elif line.startswith("run ") and runner.ADDED_WORD in line:
            added = line.split()[1]
    return added, run_dir


def failed_note(folder, exp, run_dir, lab):
    """Why an experiment failed: the <UTC>.failed.json of its run, or the newest run folder without a seal."""
    if run_dir is None:
        return "run.py stopped before it made a run folder (see the log)"
    rel = run_dir.relative_to(lab.results) if run_dir.is_relative_to(lab.results) else run_dir
    f = run_dir.parent / f"{run_dir.name}.failed.json"
    if f.is_file():
        rec = json.loads(f.read_text())
        return f"the run {rel} failed at '{rec.get('step')}': {rec.get('error')} (not in the run list)"
    if seal.seal_path(run_dir).exists():
        return f"the run {rel} is sealed, but not in the run list (see the log)"
    return f"a part of a run is left in {rel} (not in the run list)"


def run_campaign(rec, hooks, design=None, hwcheck=True, warn_as_error=False, log=print):
    """Run the experiments of a record that are not done; return the number of failed experiments."""
    lab = rec.lab
    design = design or Design()
    d = rec.data
    rev, dirty = hooks.repo_state()
    if rev != d["repo"]["rev"] or dirty:
        raise CampaignError(f"the design repo is at {rev[:12]}{' (dirty)' if dirty else ''}, the campaign "
                            f"{rec.id} at {d['repo']['rev'][:12]}: check out its commit (ref {d['ref']})")
    try:
        take_lock(lab, rec.id, hooks.resource_keys(d), hooks.resource)
    except CampaignError as x:
        if d.get("status") == PLANNED and not d.get("started"):
            rec.set(status=FAILED, finished=utc_now().isoformat(), stopped=f"not started: {x}")
        raise
    # a resume runs the failed experiments again (and one that a crash left in running), unless
    # the run tool of the dead campaign ended and added its run (it holds the lock to its end)
    for e in d["experiments"]:
        if e["state"] in (FAILED, RUNNING):
            done = hooks.run_of_campaign(lab, e, rec.id)
            if done:
                e.update(state=DONE, run=done, note="the run.py of the stopped campaign added this run")
            else:
                e.update(state=PLANNED, attempts=e.get("attempts", 1) + 1)
    rec.set(pid=os.getpid())
    rec.log_dir.mkdir(parents=True, exist_ok=True)
    stop = {"why": None}
    post = None

    def on_term(signum, frame):
        stop["why"] = f"signal {signum}"
        raise KeyboardInterrupt

    old = signal.signal(signal.SIGTERM, on_term)
    old_hup = signal.signal(signal.SIGHUP, on_term)      # the ssh connection of a campaign without --detach
    try:
        hooks.update_ref(d["ref"], d["repo"]["rev"])
        log(f"campaign {rec.id}: pre-flight check")
        res = hooks.preflight(lab, d["experiments"], design, hwcheck, warn_as_error, log, True)
        d["preflight"] = [{"status": s, "what": w, "text": t} for s, w, t in res]
        if any(s == "fail" for s, _, _ in res):
            rec.set(status=FAILED, finished=utc_now().isoformat(), stopped="the pre-flight check failed")
            log("the pre-flight check failed; nothing runs")
            return len([e for e in d["experiments"] if e["state"] != SKIPPED])
        rec.set(status=RUNNING, pid=os.getpid(), started=d.get("started") or utc_now().isoformat())
        root = lab.results / design.top.name
        post = hooks.post(rec, root)
        failed = 0
        for e in d["experiments"]:
            if e["state"] in (DONE, SKIPPED):
                continue
            now, dirty = hooks.repo_state()
            if now != d["repo"]["rev"] or dirty:
                rec.set(stopped=f"the design repo changed before {e['experiment']} ({now[:12]}"
                                f"{', dirty' if dirty else ''})")
                log(d["stopped"])
                break
            folder = hooks.ensure_instance(lab, design, e, log)
            e.update(instance=str(folder.relative_to(lab.results)), state=RUNNING, started=utc_now().isoformat(),
                     log=str((rec.log_dir / f"{e['experiment']}.log").relative_to(lab.folder)))
            e.pop("note", None)
            rec.save()
            log(f"=== {e['experiment']} ({e['instance']})")
            why = hooks.before_run(rec, e, hwcheck)
            if why:
                e.update(state=FAILED, finished=utc_now().isoformat(), note=why)
                failed += 1
                rec.save()
                log(f"    {e['state']}: {why}")
                continue
            # the run tool adds the run to the run list of the instance, with the role and the campaign
            cmd = hooks.run_command(rec, e, folder, warn_as_error)
            t0 = time.monotonic()
            rc = run_subprocess(cmd, lab.folder / e["log"], cwd=lab.folder, pass_fds=lock_fds(rec.id))
            e.update(rc=rc, finished=utc_now().isoformat())
            added, run_dir = read_run_log((lab.folder / e["log"]).read_text())
            if rc == 0 and added is not None:
                e.update(run=added, state=DONE)
            else:
                e["state"] = FAILED
                e["note"] = failed_note(folder, e["experiment"], run_dir, lab)
            failed += e["state"] == FAILED
            rec.save()
            ran = ""
            if e.get("run"):
                note = hooks.run_note(folder, e["run"])
                ran = (f", {note}" if note else "") + f", run {e['run']}"
            log(f"    {e['state']} (rc {rc}) in {minutes(time.monotonic() - t0)}{ran}"
                + (f": {e['note']}" if e.get("note") else ""))
            if e["state"] == DONE:
                post.kick()
            post.poll()
        rec.set(status=DONE if not d.get("stopped") else FAILED, finished=utc_now().isoformat())
        # A build that started while the campaign ran marks its verdicts provisional: one more
        # build after the end makes them final (kick: after the build that runs now, if any).
        log("waiting for the last build of the results (it makes the verdicts final)")
        post.kick()
        post.wait()
        log(f"campaign {rec.id}: {d['status']}, {failed} experiments failed; results {root}/index.html")
        return failed
    except KeyboardInterrupt:
        for e in d["experiments"]:
            if e["state"] == RUNNING:
                e.update(state=FAILED, note=f"stopped ({stop['why'] or 'interrupt'})")
        rec.set(status="aborted", finished=utc_now().isoformat(), stopped=stop["why"] or "interrupt")
        final_build(post, log)
        raise CampaignError(f"campaign {rec.id} aborted") from None
    except Exception as x:
        for e in d["experiments"]:
            if e["state"] == RUNNING:
                e.update(state=FAILED, note=f"stopped ({type(x).__name__})")
        rec.set(status="aborted", finished=utc_now().isoformat(), stopped=f"{type(x).__name__}: {x}")
        final_build(post, log)
        raise
    finally:
        signal.signal(signal.SIGTERM, old)
        signal.signal(signal.SIGHUP, old_hup)
        drop_lock(lab, rec.id)
