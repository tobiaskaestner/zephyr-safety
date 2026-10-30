#!/usr/bin/env python3
# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Run tools/run_tlc.sh on the lab host and copy the results back.

Usage::

    run_tlc_remote.py [options] [<module>[:<config>] ...]

The arguments select lines of mc/expected.txt, as for run_tlc.sh. Without
arguments, all lines run.

Modes:

- pinned (default): the worktree must be clean. The script sends the
  current commit to the lab clone in a git bundle, updates the branch of
  the clone with ``git merge --ff-only``, and runs run_tlc.sh of this
  commit there. The run record names a commit that exists in both clones.
- unpinned (``--unpinned``): for development. The script copies the
  working tree of spec/tla/ (tracked and untracked files, without ignored
  files) to a new directory on the lab host, and runs there. The record
  has the base commit, the mark "unpinned" and the SHA-256 of the diff
  against the base commit. The output has the diff (diff.patch).

Evidence runs (tools/TOOLS.rst, "The one-worker rule"):

- Each TLC process has one worker (``--workers 1``, the default). The
  pinned jar does not have the fix of tlaplus issue #1445: with more than
  one worker in one process, TLC can miss states and violations.
- Several TLC processes run at the same time (``--jobs``, default 6).
  Each process has its own -metadir and java.io.tmpdir. Each line has
  its own Java heap (the field heap= of expected.txt, else ``--mem``). A
  line starts only if its heap fits in ``--mem-budget`` with the heaps of
  the lines that run, so the large lines do not all run at the same time.
- Before the models, the job runs the selftest of TLC
  (selftest/expected.txt) with one worker. If the selftest fails, no
  model runs.
- The record has ``evidence: true`` only for a pinned run of the pinned
  jar with one worker and a selftest that passed. ``--workers <n>`` with
  n > 1 is for experiments: its record has ``evidence: false``.

On the lab host, each job runs under the lock <lab-root>/.lock (flock),
with ``nice -n 10``. A job waits until the lock is free. The job runs in
the background on the lab host: if the connection stops, the job
continues, and ``--collect <run-id>`` gets the results later. After each
run, the job deletes the TLC state directories. The job uses the jar of
the pin of the commit (tools/tla2tools.sha256) from the read-only archive
<lab-root>/archive/tla2tools/sha256-<hash>/.

The local output directory (default: spec/tla/build/lab/<run-id>) gets
the logs, selftest/ (the logs of the selftest), summary.md (the selftest
and all lines, with the counts, the collision estimate of TLC, the heap
and the peak memory of each line), results.txt (the result lines of
run_tlc.sh), rss.txt (the samples of the peak memory) and record.json.

Exit status: 0 if each result is as expected, 1 if not, 2 on a setup
error, 3 if the job continues on the lab host (--detach, or an
interrupt).
"""

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path

DEFAULT_HOST = "tobias@cos-workstation"
DEFAULT_ROOT = "/wrk/z/lab-tla"
DEFAULT_MEM = "2g"       # heap of a line without heap=
DEFAULT_BUDGET = "20g"   # sum of the heaps of the lines that run together
DEFAULT_JOBS = 6         # the lab host has 6 cores, 12 hardware threads
MAX_JOBS = 8             # lab rule: at most 8 of the 12 hardware threads
MAX_WORKERS = 8
GC_THREADS = 2           # ParallelGC threads of each TLC process
POLL_SECONDS = 20

SPEC = Path(__file__).resolve().parent.parent

# The columns of results.tsv (written by run_tlc.sh).
TSV_COLUMNS = ["module", "config", "expected", "result", "verdict", "violated", "distinct",
               "depth", "trace", "lasso", "collision_calculated", "collision_actual",
               "seconds", "workers", "heap"]

# The job on the lab host. The script writes the variables of the job in
# front of this text. The paths on the lab host have no spaces.
JOB_BODY = r"""
set -u
run=$root/runs/$id
cd "${run:?}" || exit 2
echo $$ > pid
echo waiting-for-lock > state
exec 9> "$root/.lock"
flock 9
echo running > state

export PATH=$root/jdk/current/bin:$PATH
# user.home: TLC reads ~/.tlaplus/esc.txt (NO_STATISTICS) from there.
# java.io.tmpdir: TLC writes the standard modules there. run_tlc.sh gives
# each TLC process its own directory below its output directory. This
# one is for the other Java calls.
mkdir -p "$run/tmp"
export JAVA_TOOL_OPTIONS="-Duser.home=$root/home -Djava.io.tmpdir=$run/tmp -XX:ParallelGCThreads=$gc"

# The peak memory (VmHWM, kB) of each TLC process of this job, every 5 s.
# The state directory (-metadir) names the line.
sample_rss() {
	while :; do
		for p in $(pgrep -f -- "-metadir $run/"); do
			m=$(tr '\0' '\n' < "/proc/$p/cmdline" 2>/dev/null | grep -A1 -x -- -metadir | tail -1)
			h=$(awk '/^VmHWM/ { print $2 }' "/proc/$p/status" 2>/dev/null)
			[ -n "$m" ] && [ -n "$h" ] && echo "$(date +%s) ${m##*/} $h"
		done
		sleep 5
	done
}
rss_pid=

finish() { # <status>
	[ -n "$rss_pid" ] && kill "$rss_pid" 2> /dev/null
	rm -rf "${run:?}/out/states" "${run:?}/out/tmp" "${run:?}/selftest/states" \
		"${run:?}/selftest/tmp" "${run:?}/tmp"
	[ "$mode" = unpinned ] && rm -rf "${root:?}/snapshots/${id:?}"
	{
		echo "end=$(date -Iseconds)"
		echo "status=$1"
	} >> meta.env
	echo done > state
	exit "$1"
}
fail() { echo "job: $*" >&2; finish 2; }

{
	echo "host=$(hostname)"
	echo "start=$(date -Iseconds)"
} > meta.env

if [ "$mode" = pinned ]; then
	clone=$root/safety
	[ -d "$clone/.git" ] || git init -q "$clone" || fail "git init"
	cd "$clone" || fail "no clone"
	if [ -n "$bundle" ]; then
		git fetch -q "$bundle" "refs/heads/$branch" || fail "git fetch of the bundle"
		if git show-ref --verify -q "refs/heads/$branch"; then
			git checkout -q "$branch" || fail "git checkout $branch"
			git merge -q --ff-only FETCH_HEAD || fail "no fast-forward of $branch"
		else
			git checkout -q -b "$branch" FETCH_HEAD || fail "git checkout -b $branch"
		fi
		rm -f "$bundle"
	fi
	git checkout -q --detach "$commit" || fail "no commit $commit"
	[ "$(git rev-parse HEAD)" = "$commit" ] || fail "HEAD is not $commit"
	[ -z "$(git status --porcelain)" ] || fail "the lab clone is not clean"
	spec=$clone/spec/tla
else
	spec=$root/snapshots/$id/spec/tla
fi
cd "$run" || fail "no run directory"

# The jar of the pin of this commit, from the archive (tools/TOOLS.rst).
jar_hash=$(cut -d' ' -f1 "$spec/tools/tla2tools.sha256")
export TLA2TOOLS=$root/archive/tla2tools/sha256-$jar_hash/tla2tools.jar
[ -f "$TLA2TOOLS" ] || fail "no archived jar with the hash $jar_hash"
{
	echo "jar=$TLA2TOOLS"
	echo "jar_sha256=$(sha256sum "$TLA2TOOLS" | cut -d' ' -f1)"
	echo "java_version=$(java -version 2>&1 | grep -v JAVA_TOOL_OPTIONS | head -1)"
	echo "java_runtime=$(java -version 2>&1 | grep -v JAVA_TOOL_OPTIONS | sed -n 2p)"
	echo "mem_total_kb=$(awk '/^MemTotal/ { print $2 }' /proc/meminfo)"
	echo "mem_available_kb=$(awk '/^MemAvailable/ { print $2 }' /proc/meminfo)"
} >> meta.env
sample_rss >> rss.txt &
rss_pid=$!

status=0
if [ "$selftest" = yes ]; then
	echo "== selftest" >> results.txt
	TLC_SUITE=selftest TLC_WORKERS=1 TLC_JOBS=1 TLC_HEAP=512m TLC_OUT=$run/selftest \
		nice -n 10 "$spec/tools/run_tlc.sh" >> results.txt 2>&1
	s=$?
	echo "selftest_status=$s" >> meta.env
	if [ $s -ne 0 ]; then
		echo "job: the selftest of TLC failed, no model runs" >> results.txt
		finish 1
	fi
fi
if [ -n "$lines" ]; then
	echo "== mc" >> results.txt
	# shellcheck disable=SC2086 # the selection is a list of words
	TLC_SUITE=mc TLC_WORKERS=$workers TLC_JOBS=$jobs TLC_HEAP=$mem TLC_MEM_BUDGET=$budget \
		TLC_OUT=$run/out nice -n 10 "$spec/tools/run_tlc.sh" $lines >> results.txt 2>&1
	status=$?
fi
finish $status
"""


def die(msg):
    print(f"run_tlc_remote: {msg}", file=sys.stderr)
    sys.exit(2)


def git(*args, env=None, check=True):
    r = subprocess.run(["git", "-C", str(SPEC), *args], capture_output=True,
                       env=env, check=False)
    if check and r.returncode != 0:
        die(f"git {' '.join(args)}: {r.stderr.decode().strip()}")
    return r.stdout


class Lab:
    """ssh and rsync to the lab host over one shared connection."""

    def __init__(self, host, root):
        self.host = host
        self.root = root
        self.tmp = tempfile.TemporaryDirectory(prefix="tlc-remote-")
        self.opts = ["-o", "BatchMode=yes", "-o", "ControlMaster=auto",
                     "-o", f"ControlPath={self.tmp.name}/cm",
                     "-o", "ControlPersist=120", "-o", "ServerAliveInterval=30"]

    def sh(self, cmd, stdin=None, check=True):
        r = subprocess.run(["ssh", *self.opts, self.host, cmd], input=stdin,
                           capture_output=True, check=False)
        if check and r.returncode != 0:
            die(f"ssh {self.host} {cmd!r}: {r.stderr.decode().strip()}")
        return r.stdout.decode()

    def rsync(self, *args, check=True):
        ssh = "ssh " + " ".join(shlex.quote(o) for o in self.opts)
        r = subprocess.run(["rsync", "-a", "-e", ssh, *args], check=False)
        if check and r.returncode != 0:
            die(f"rsync {' '.join(args)} failed")
        return r.returncode == 0

    def close(self):
        subprocess.run(["ssh", *self.opts, "-O", "exit", self.host],
                       capture_output=True, check=False)
        self.tmp.cleanup()


def read_expected(text):
    """Return the lines of expected.txt as (module, config, expected)."""
    lines = []
    for line in text.splitlines():
        f = line.split()
        if len(f) >= 3 and not f[0].startswith("#"):
            lines.append((f[0], f[1], f[2]))
    return lines


def select(lines, args):
    if not args:
        return lines
    return [ln for ln in lines if ln[0] in args or f"{ln[0]}:{ln[1]}" in args]


def unpinned_diff():
    """Return the diff of spec/tla against HEAD, with untracked files."""
    with tempfile.TemporaryDirectory() as d:
        env = dict(os.environ, GIT_INDEX_FILE=f"{d}/index")
        git("read-tree", "HEAD", env=env)
        git("add", "-A", "--", ".", env=env)
        return git("diff", "--cached", "--binary", "HEAD", "--", ".", env=env)


def submit(a, lab):
    top = Path(git("rev-parse", "--show-toplevel").decode().strip())
    commit = git("rev-parse", "HEAD").decode().strip()
    branch = git("symbolic-ref", "-q", "--short", "HEAD", check=False).decode().strip()
    mode = "unpinned" if a.unpinned else "pinned"
    diff = None
    if mode == "pinned":
        if git("status", "--porcelain").strip():
            die("the worktree is not clean (commit first, or use --unpinned)")
        if not branch:
            die("HEAD is detached: check out a branch")
        expected = git("show", f"{commit}:spec/tla/mc/expected.txt").decode()
    else:
        diff = unpinned_diff()
        expected = (SPEC / "mc" / "expected.txt").read_text()

    lines = [] if a.selftest_only else select(read_expected(expected), a.models)
    if not lines and not a.selftest_only:
        die("no model selected")

    run_id = time.strftime("%Y%m%d-%H%M%S-") + commit[:9] + ("-u" if diff is not None else "")
    run = f"{lab.root}/runs/{run_id}"
    # mkdir without -p for the run: two runs with the same id stop here.
    lab.sh(f"mkdir -p {lab.root}/runs {lab.root}/bundles {lab.root}/snapshots && mkdir {run}")

    bundle = ""
    if mode == "pinned":
        have = lab.sh(f"cd {lab.root}/safety 2>/dev/null && "
                      f"git cat-file -e {commit}^{{commit}} 2>/dev/null && echo yes; "
                      f"git -C {lab.root}/safety for-each-ref --format='%(objectname)' "
                      f"refs/heads 2>/dev/null", check=False).split()
        if "yes" not in have:
            # The heads of the lab clone that exist here: the bundle
            # leaves out the history below them.
            basis = [f"^{h}" for h in have
                     if subprocess.run(["git", "-C", str(SPEC), "cat-file", "-e",
                                        f"{h}^{{commit}}"], capture_output=True).returncode == 0]
            with tempfile.TemporaryDirectory() as d:
                local = f"{d}/{run_id}.bundle"
                git("bundle", "create", "-q", local, f"refs/heads/{branch}", *basis)
                bundle = f"{lab.root}/bundles/{run_id}.bundle"
                with open(local, "rb") as f:
                    lab.sh(f"cat > {bundle}", stdin=f.read())
    else:
        files = [p for p in git("ls-files", "-co", "--exclude-standard", "--deduplicate",
                                "--", ".").decode().splitlines()
                 if (SPEC / p).is_file()]
        rel = [str((SPEC / p).relative_to(top)) for p in files]
        with tempfile.NamedTemporaryFile("w", suffix=".lst") as f:
            f.write("\n".join(rel) + "\n")
            f.flush()
            lab.rsync("--files-from", f.name, f"{top}/",
                      f"{lab.host}:{lab.root}/snapshots/{run_id}/")

    order = [f"{m}:{c}" for m, c, _ in lines]
    job = {
        "run_id": run_id, "mode": mode, "revision": commit, "branch": branch or None,
        "diff_sha256": hashlib.sha256(diff).hexdigest() if diff is not None else None,
        "workers": a.workers, "jobs": a.jobs, "memory": a.mem, "mem_budget": a.mem_budget,
        "gc_threads": GC_THREADS, "nice": 10, "selftest": not a.no_selftest,
        "selection": a.models, "order": order,
        "submitted": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    head = "\n".join([
        "#!/usr/bin/env bash",
        f"root={shlex.quote(lab.root)}", f"id={run_id}", f"mode={mode}",
        f"commit={commit}", f"branch={shlex.quote(branch)}",
        f"bundle={shlex.quote(bundle)}", f"mem={shlex.quote(a.mem)}",
        f"budget={shlex.quote(a.mem_budget)}", f"workers={a.workers}", f"jobs={a.jobs}",
        f"gc={GC_THREADS}", f"selftest={'no' if a.no_selftest else 'yes'}",
        f"lines={shlex.quote(' '.join(order))}",
    ])
    lab.sh(f"cat > {run}/job.sh", stdin=(head + JOB_BODY).encode())
    lab.sh(f"cat > {run}/job.json", stdin=json.dumps(job, indent=2).encode())
    lab.sh(f"cd {run} && echo queued > state && "
           f"setsid nohup bash job.sh > job.log 2>&1 < /dev/null &")
    out = Path(a.out) if a.out else SPEC / "build" / "lab" / run_id
    out.mkdir(parents=True, exist_ok=True)
    if diff is not None:
        (out / "diff.patch").write_bytes(diff)
    print(f"run_tlc_remote: run {run_id} ({mode}) started on {lab.host}")
    return run_id, out


def wait(lab, run_id):
    """Show the result lines until the job ends. False on an interrupt."""
    run = f"{lab.root}/runs/{run_id}"
    seen = 0
    last_state = ""
    try:
        while True:
            r = lab.sh(f"cd {run} && cat state && echo --- && "
                       f"tail -c +{seen + 1} results.txt 2>/dev/null", check=False)
            state, _, new = r.partition("---\n")
            state = state.strip()
            if new:
                sys.stdout.write(new)
                sys.stdout.flush()
                seen += len(new.encode())
            if state != last_state and state in ("waiting-for-lock",):
                print("run_tlc_remote: the lab host runs another job, waiting for the lock")
            last_state = state
            if state == "done":
                return True
            time.sleep(POLL_SECONDS)
    except KeyboardInterrupt:
        print(f"\nrun_tlc_remote: the job continues on the lab host. "
              f"Get the results with --collect {run_id}")
        return False


def read_rows(path):
    """Return the rows of a results.tsv of run_tlc.sh as dicts."""
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines()[1:]:
        c = line.split("\t")
        if len(c) == len(TSV_COLUMNS):
            rows.append(dict(zip(TSV_COLUMNS, c)))
    return rows


def peak_rss(path):
    """Return {state directory name: peak VmHWM in MB} from rss.txt."""
    peak = {}
    if path.exists():
        for line in path.read_text().splitlines():
            f = line.split()
            if len(f) == 3 and f[2].isdigit():
                peak[f[1]] = max(peak.get(f[1], 0), int(f[2]) // 1024)
    return peak


def table(rows):
    head = ("| Model | Expected | Result | Violated | Distinct states | Depth | Trace | "
            "Collision (calc. / actual) | Time | Workers | Heap | Peak RSS |\n"
            "|---|---|---|---|---|---|---|---|---|---|---|---|\n")
    body = ""
    for r in rows:
        trace = r["trace"] if r["lasso"] == "-" else f"{r['trace']} (lasso {r['lasso']})"
        rss = f"{r['peak_rss_mb']} MB" if r["peak_rss_mb"] is not None else "-"
        body += (f"| {r['module']} {r['config']} | {r['expected']} | {r['verdict']} | "
                 f"{r['violated']} | {r['distinct']} | {r['depth']} | {trace} | "
                 f"{r['collision_calculated']} / {r['collision_actual']} | {r['seconds']} s | "
                 f"{r['workers']} | {r['heap']} | {rss} |\n")
    return head + body


def collect(lab, run_id, out):
    run = f"{lab.root}/runs/{run_id}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "selftest").mkdir(exist_ok=True)
    lab.rsync("--exclude", "states/", "--exclude", "tmp/",
              f"{lab.host}:{run}/out/", f"{out}/", check=False)
    lab.rsync("--exclude", "states/", "--exclude", "tmp/",
              f"{lab.host}:{run}/selftest/", f"{out}/selftest/", check=False)
    for f in ("results.txt", "meta.env", "job.json", "job.log", "job.sh", "rss.txt"):
        lab.rsync(f"{lab.host}:{run}/{f}", f"{out}/", check=f != "rss.txt")
    job = json.loads((out / "job.json").read_text())
    meta = dict(ln.split("=", 1) for ln in (out / "meta.env").read_text().splitlines()
                if "=" in ln)
    rss = peak_rss(out / "rss.txt")

    def with_rss(rows):
        for r in rows:
            name = f"{r['module']}_{r['config']}"
            vals = [v for k, v in rss.items() if k == name or k.startswith(name + ".r")]
            r["peak_rss_mb"] = max(vals) if vals else None
        return rows

    rows = with_rss(read_rows(out / "results.tsv"))
    self_rows = with_rss(read_rows(out / "selftest" / "results.tsv"))
    status = int(meta.get("status", 2))
    selftest_status = meta.get("selftest_status")

    # The conditions of an evidence run (tools/TOOLS.rst).
    pinned_jar = (SPEC / "tools" / "tla2tools.sha256").read_text().split()[0]
    reasons = []
    if job["mode"] != "pinned":
        reasons.append("unpinned: the code is not a commit")
    if int(job["workers"]) != 1:
        reasons.append(f"{job['workers']} workers in one TLC process (tlaplus issue #1445)")
    if not job.get("selftest", False):
        reasons.append("no selftest")
    elif selftest_status != "0":
        reasons.append(f"the selftest failed (status {selftest_status})")
    if meta.get("jar_sha256") != pinned_jar:
        reasons.append("the jar is not the pinned jar")
    evidence = not reasons

    with open(out / "summary.md", "w") as f:
        f.write(f"# TLC run {run_id}\n\n")
        f.write(f"- Evidence: {'yes' if evidence else 'NO (' + '; '.join(reasons) + ')'}\n")
        f.write(f"- Status: {status}\n")
        f.write(f"- Mode: {job['mode']}, revision {job['revision']}, branch {job['branch']}\n")
        f.write(f"- Jar: {meta.get('jar_sha256')}\n")
        f.write(f"- Java: {meta.get('java_runtime')}\n")
        f.write(f"- Workers per process: {job['workers']}, processes: {job['jobs']}, "
                f"heap: {job['memory']} (default), budget: {job['mem_budget']}\n")
        f.write(f"- Host: {meta.get('host')}, {meta.get('start')} to {meta.get('end')}\n\n")
        if self_rows:
            f.write("## Selftest\n\n" + table(self_rows) + "\n")
        if rows:
            f.write("## Models\n\n" + table(rows))

    record = {
        "run_id": run_id,
        "mode": job["mode"],
        "revision": job["revision"],
        "branch": job["branch"],
        "diff_sha256": job["diff_sha256"],
        "evidence": evidence,
        "not_evidence_reasons": reasons,
        "jar": meta.get("jar"),
        "jar_sha256": meta.get("jar_sha256"),
        "java_version": meta.get("java_version"),
        "java_runtime": meta.get("java_runtime"),
        "workers": int(job["workers"]),
        "jobs": job["jobs"],
        "memory": job["memory"],
        "mem_budget": job["mem_budget"],
        "gc_threads": job["gc_threads"],
        "nice": job["nice"],
        "host": meta.get("host"),
        "mem_total_kb": meta.get("mem_total_kb"),
        "mem_available_kb": meta.get("mem_available_kb"),
        "start": meta.get("start"),
        "end": meta.get("end"),
        "status": status,
        "selftest": ({"status": selftest_status, "results": self_rows}
                     if job.get("selftest") else None),
        "selection": job["selection"],
        "result_lines": [ln for ln in (out / "results.txt").read_text().splitlines()
                         if " expected " in ln or ln.startswith("job:")],
        "results": rows,
    }
    (out / "record.json").write_text(json.dumps(record, indent=2) + "\n")
    print(f"run_tlc_remote: results in {out}")
    if not evidence:
        print("run_tlc_remote: this run is NOT evidence: " + "; ".join(reasons))
    return status


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("models", nargs="*", metavar="<module>[:<config>]")
    p.add_argument("--workers", type=int, default=1,
                   help=f"TLC workers in each process (default 1). More than 1 (up to "
                        f"{MAX_WORKERS}) is not evidence")
    p.add_argument("--jobs", type=int, default=DEFAULT_JOBS,
                   help=f"TLC processes at the same time, 1..{MAX_JOBS} (default {DEFAULT_JOBS})")
    p.add_argument("--mem", default=DEFAULT_MEM,
                   help=f"Java heap of a line without heap= (default {DEFAULT_MEM})")
    p.add_argument("--mem-budget", default=DEFAULT_BUDGET,
                   help=f"sum of the heaps of the lines that run together "
                        f"(default {DEFAULT_BUDGET})")
    p.add_argument("--no-selftest", action="store_true",
                   help="do not run the selftest of TLC first (not evidence)")
    p.add_argument("--selftest-only", action="store_true",
                   help="run only the selftest of TLC")
    p.add_argument("--unpinned", action="store_true",
                   help="run a copy of the working tree of spec/tla/ (not evidence)")
    p.add_argument("--host", default=os.environ.get("TLC_LAB_HOST", DEFAULT_HOST))
    p.add_argument("--lab-root", default=os.environ.get("TLC_LAB_ROOT", DEFAULT_ROOT))
    p.add_argument("--out", help="local output directory (default build/lab/<run-id>)")
    p.add_argument("--detach", action="store_true",
                   help="start the job and stop; get the results with --collect")
    p.add_argument("--collect", metavar="RUN_ID",
                   help="wait for the job RUN_ID and copy its results")
    a = p.parse_args()

    if not 1 <= a.workers <= MAX_WORKERS:
        die(f"--workers must be 1..{MAX_WORKERS}")
    if not 1 <= a.jobs <= MAX_JOBS:
        die(f"--jobs must be 1..{MAX_JOBS}")
    for opt in (a.mem, a.mem_budget):
        if not opt[:-1].isdigit() or opt[-1].lower() not in "mg":
            die("--mem and --mem-budget must be like 4g or 512m")
    if a.selftest_only and (a.no_selftest or a.models):
        die("--selftest-only takes no models and no --no-selftest")
    if a.workers > 1 and not a.collect:
        print(f"run_tlc_remote: {a.workers} workers in one TLC process: "
              f"the results are not evidence (tlaplus issue #1445)")

    lab = Lab(a.host, a.lab_root)
    try:
        if a.collect:
            run_id = a.collect
            out = Path(a.out) if a.out else SPEC / "build" / "lab" / run_id
        else:
            run_id, out = submit(a, lab)
            if a.detach:
                print(f"run_tlc_remote: get the results with --collect {run_id}")
                return 3
        if not wait(lab, run_id):
            return 3
        return collect(lab, run_id, out)
    finally:
        lab.close()


if __name__ == "__main__":
    sys.exit(main())
