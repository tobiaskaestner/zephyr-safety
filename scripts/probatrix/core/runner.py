# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The generic part of a run: provenance, the run folder, the failed record, the seal, the run list.

A kind has its own run tool (for the benchmarks: benchmarks/run.py with build, flash and
capture). The tool calls this module for the parts that every run shares, in this order:

1. provenance: check_clean, check_inside (the repo has no change; the experiment file is in it),
   check_unchanged (before each build step; the repo stays at the pinned rev);
2. run_folder: <out>/[ex-]<experiment>/<UTC>/, and the line "run folder <path>" (a campaign reads it);
3. pin_run: the local ref <kind.ref("run", experiment, UTC)> at the pinned rev (never pushed);
4. guarded: the tool body. A stop before the seal leaves <UTC>.failed.json beside the run folder;
5. finish: the seal (core/seal.py) and the line "results in <path>  (<digest>)";
6. add_to_run_list: for the run folder of an instance, the run goes to its run list
   (the line "run <id> added to the instance <folder>").

The three lines are the protocol with core/campaign.py: it reads them from the log of the tool.
Errors are RunError. The tool of the kind turns them into its own stop (benchmarks/run.py: fail()).
The names of the ref and of the failed record come from the kind (ref_prefix, format_prefix).
"""

import datetime
import json
import platform
import signal
import subprocess
import sys
from pathlib import Path

from probatrix.core import config, seal
from probatrix.core.errors import RunError

RUN_FOLDER_LINE = "run folder "
RESULTS_LINE = "results in "
ADDED_WORD = " added to the instance "
UTC_FORMAT = "%Y%m%dT%H%M%SZ"


def git(*args, cwd=None):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RunError(f"git {' '.join(args)} ({cwd}): {r.stderr.strip()}")
    return r.stdout.strip()


def repo_state(path):
    """Return (rev, dirty lines) of a git checkout."""
    rev = git("rev-parse", "HEAD", cwd=path)
    dirty = git("status", "--porcelain", "--untracked-files=all", cwd=path)
    return rev, dirty


# ------------------------------------------------------------ 1. provenance
def check_clean(repo_root, dirty, what="safety repo"):
    """RunError if the repo has changes (dirty: the lines of git status)."""
    if dirty:
        raise RunError(f"{what} {repo_root} is dirty, commit first:\n{dirty}")


def check_inside(path, repo_root, what="safety repo"):
    """RunError if the experiment file is not in the repo."""
    if not Path(path).is_relative_to(repo_root):
        raise RunError(f"{path} is not in the {what} {repo_root}")


def check_unchanged(repo_root, rev, what="safety repo", state=repo_state):
    """RunError if the repo is not clean at rev any more (a change during the run)."""
    now, dirty = state(repo_root)
    if now != rev or dirty:
        raise RunError(f"the {what} {repo_root} changed during the run (was {rev[:12]}, now {now[:12]}"
                       f"{', dirty' if dirty else ''})")


# ------------------------------------------------------------ 2. run folder, 3. pinned ref
def run_folder(out, name, started, say=print):
    """Make <out>/<experiment>/<UTC>/ (in an instance: <out>/ex-<experiment>/<UTC>/) and return it."""
    out = Path(out).resolve()
    folder = config.project().experiment_prefix + name if (out / "instance.json").is_file() else name
    run_dir = out / folder / started.strftime(UTC_FORMAT)
    run_dir.mkdir(parents=True)
    say(f"{RUN_FOLDER_LINE}{run_dir}", flush=True)       # the campaign reads this line
    return run_dir


def pin_run(kind, repo_root, rev, name, run_name):
    """The commit of the run stays reachable (a rebuild exports it), also after a rebase: a local
    ref of the kind, never pushed. Return the ref."""
    ref = kind.ref("run", name, run_name)
    git("update-ref", ref, rev, cwd=repo_root)
    return ref


# ------------------------------------------------------------ 4. guarded body, failed record
def write_failed(kind, run_dir, name, state, x):
    """<UTC>.failed.json beside a run folder that has no seal."""
    if isinstance(x, SystemExit):
        error = str(x.code).removeprefix("error: ") if x.code not in (None, 0) else "exit"
    elif isinstance(x, KeyboardInterrupt):
        error = "interrupt"
    else:
        error = f"{type(x).__name__}: {x}"
    if state.get("log") is None and state.get("builder") is not None:
        state["log"] = state["builder"].last_log          # a build failure: the build log
    tail = []
    if state.get("log") and Path(state["log"]).is_file():
        tail = Path(state["log"]).read_text(errors="replace").splitlines()[-20:]
    rec = {"format": kind.format_id("failed", 1), "run": f"{name}/{run_dir.name}", "step": state["step"],
           "error": error, "time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
           "host": platform.node(),
           "log": state.get("log") and (str(Path(state["log"]).relative_to(run_dir))
                                        if Path(state["log"]).is_relative_to(run_dir) else str(state["log"])),
           "log_tail": tail}
    f = run_dir.parent / f"{run_dir.name}.failed.json"
    f.write_text(json.dumps(rec, indent=2) + "\n")
    print(f"the run failed ({error}); record {f}", file=sys.stderr)


def guarded(kind, run_dir, name, state, body):
    """Run body(); on a stop before the seal (an error, Ctrl-C, SIGTERM) write the failed record, then raise
    again. state: {"step", "log"[, "builder"]}, updated by the body."""
    def on_term(signum, frame):
        raise SystemExit(f"error: stopped by signal {signum}")

    signal.signal(signal.SIGTERM, on_term)
    try:
        body()
    except BaseException as x:
        if not seal.seal_path(run_dir).exists():
            write_failed(kind, run_dir, name, state, x)
        raise


# ------------------------------------------------------------ 5. seal, 6. run list
def finish(run_dir, say=print):
    """Seal the run folder; return the digest."""
    digest = seal.write(run_dir)
    say(f"{RESULTS_LINE}{run_dir}  ({digest})")
    return digest


def in_instance(out):
    return (Path(out) / "instance.json").is_file()


def add_to_run_list(out, run_dir, add, errors, say=print, **entry):
    """Add the run to the run list of the instance folder out: add(out, run_dir, **entry) returns the run id.

    errors: the exception class(es) of add; RunError with the text of the stop. entry: role, reason, campaign.
    """
    try:
        rid = add(out, run_dir, **entry)
    except errors as e:
        raise RunError(f"the run is sealed, but not in the run list of {out}: {e}") from e
    say(f"run {rid}{ADDED_WORD}{out}")
    return rid
