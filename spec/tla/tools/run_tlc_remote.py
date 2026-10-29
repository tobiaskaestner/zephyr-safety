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

Workers (``--workers``):

- auto (default): the worker rule. Lines with the expected result "pass"
  run with AUTO_WORKERS workers. All other lines (fail:<Name>, probes) run
  with 1 worker, so that TLC reports the shortest trace and the state
  counts stay comparable.
- <n>: all selected lines run with n workers (1 to MAX_WORKERS).

On the lab host, each job runs under the lock <lab-root>/.lock (flock),
with ``nice -n 10``. A job waits until the lock is free. The job runs in
the background on the lab host: if the connection stops, the job
continues, and ``--collect <run-id>`` gets the results later. After each
run, the job deletes the TLC state directories.

The local output directory (default: spec/tla/build/lab/<run-id>) gets
the logs, summary.md (all lines, with a column for the workers), one
summary.w<n>.md for each worker group, results.txt (the result lines of
run_tlc.sh) and record.json.

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
DEFAULT_MEM = "4g"
AUTO_WORKERS = 8
MAX_WORKERS = 8  # lab rule: at most 8 of the 12 cores
POLL_SECONDS = 20

SPEC = Path(__file__).resolve().parent.parent

# The job on the lab host. The script writes the variables of the job in
# front of this text. The paths on the lab host have no spaces.
JOB_BODY = r"""
set -u
run=$root/runs/$id
cd "$run" || exit 2
echo $$ > pid
echo waiting-for-lock > state
exec 9> "$root/.lock"
flock 9
echo running > state

export PATH=$root/jdk/current/bin:$PATH
export TLA2TOOLS=$root/tla2tools-1.8.0/tla2tools.jar
# user.home: TLC reads ~/.tlaplus/esc.txt (NO_STATISTICS) from there.
# java.io.tmpdir: TLC writes the standard modules there.
mkdir -p "$root/tmp"
export JAVA_TOOL_OPTIONS="-Xmx$mem -Duser.home=$root/home -Djava.io.tmpdir=$root/tmp"

finish() { # <status>
	rm -rf "$run/out/states"
	[ "$mode" = unpinned ] && rm -rf "$root/snapshots/$id"
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
	echo "java_version=$(java -version 2>&1 | grep -v JAVA_TOOL_OPTIONS | head -1)"
	echo "java_runtime=$(java -version 2>&1 | grep -v JAVA_TOOL_OPTIONS | sed -n 2p)"
	echo "jar_sha256=$(sha256sum "$TLA2TOOLS" | cut -d' ' -f1)"
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

status=0
for group in "${groups[@]}"; do
	w=${group%% *}
	args=${group#* }
	mkdir -p out
	# shellcheck disable=SC2086 # the selection is a list of words
	TLC_WORKERS=$w TLC_OUT=$run/out nice -n 10 "$spec/tools/run_tlc.sh" $args >> results.txt 2>&1
	s=$?
	[ -f out/summary.md ] && mv out/summary.md "out/summary.w$w.md"
	rm -rf out/states
	[ $s -gt $status ] && status=$s
done
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

    def rsync(self, *args):
        ssh = "ssh " + " ".join(shlex.quote(o) for o in self.opts)
        r = subprocess.run(["rsync", "-a", "-e", ssh, *args], check=False)
        if r.returncode != 0:
            die(f"rsync {' '.join(args)} failed")

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


def worker_groups(lines, workers):
    """Return [(workers, [module:config, ...]), ...]."""
    if workers != "auto":
        return [(int(workers), [f"{m}:{c}" for m, c, _ in lines])]
    one = [f"{m}:{c}" for m, c, e in lines if e != "pass"]
    many = [f"{m}:{c}" for m, c, e in lines if e == "pass"]
    return [(w, g) for w, g in ((1, one), (AUTO_WORKERS, many)) if g]


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

    lines = select(read_expected(expected), a.models)
    if not lines:
        die("no model selected")
    groups = worker_groups(lines, a.workers)

    run_id = time.strftime("%Y%m%d-%H%M%S-") + commit[:9] + ("-u" if diff is not None else "")
    run = f"{lab.root}/runs/{run_id}"
    lab.sh(f"mkdir -p {run} {lab.root}/bundles {lab.root}/snapshots")

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

    job = {
        "run_id": run_id, "mode": mode, "revision": commit, "branch": branch or None,
        "diff_sha256": hashlib.sha256(diff).hexdigest() if diff is not None else None,
        "workers": a.workers, "memory": a.mem, "nice": 10,
        "selection": a.models, "order": [f"{m}:{c}" for m, c, _ in lines],
        "groups": [{"workers": w, "lines": g} for w, g in groups],
        "submitted": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    head = "\n".join([
        "#!/usr/bin/env bash",
        f"root={shlex.quote(lab.root)}", f"id={run_id}", f"mode={mode}",
        f"commit={commit}", f"branch={shlex.quote(branch)}",
        f"bundle={shlex.quote(bundle)}", f"mem={shlex.quote(a.mem)}",
        "groups=(" + " ".join(shlex.quote(f"{w} {' '.join(g)}") for w, g in groups) + ")",
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


def parse_summary(path, workers):
    rows = []
    for line in path.read_text().splitlines()[2:]:
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(c) != 7:
            continue
        module, config = c[0].split()
        rows.append({"module": module, "config": config, "expected": c[1],
                     "verdict": c[2], "violated": c[3], "distinct_states": c[4],
                     "depth": c[5], "time": c[6], "workers": workers})
    return rows


def collect(lab, run_id, out):
    run = f"{lab.root}/runs/{run_id}"
    out.mkdir(parents=True, exist_ok=True)
    lab.rsync("--exclude", "states/", f"{lab.host}:{run}/out/", f"{out}/")
    for f in ("results.txt", "meta.env", "job.json", "job.log", "job.sh"):
        lab.rsync(f"{lab.host}:{run}/{f}", f"{out}/")
    job = json.loads((out / "job.json").read_text())
    meta = dict(ln.split("=", 1) for ln in (out / "meta.env").read_text().splitlines()
                if "=" in ln)

    order = job["order"]
    rows = []
    for g in job["groups"]:
        s = out / f"summary.w{g['workers']}.md"
        if s.exists():
            rows += parse_summary(s, g["workers"])
    rows.sort(key=lambda r: order.index(f"{r['module']}:{r['config']}")
              if f"{r['module']}:{r['config']}" in order else len(order))
    with open(out / "summary.md", "w") as f:
        f.write("| Model | Expected | Result | Violated | Distinct states | Depth | Time | Workers |\n")
        f.write("|---|---|---|---|---|---|---|---|\n")
        for r in rows:
            f.write(f"| {r['module']} {r['config']} | {r['expected']} | {r['verdict']} | "
                    f"{r['violated']} | {r['distinct_states']} | {r['depth']} | {r['time']} | "
                    f"{r['workers']} |\n")

    status = int(meta.get("status", 2))
    record = {
        "run_id": run_id,
        "mode": job["mode"],
        "revision": job["revision"],
        "branch": job["branch"],
        "diff_sha256": job["diff_sha256"],
        "jar_sha256": meta.get("jar_sha256"),
        "java_version": meta.get("java_version"),
        "java_runtime": meta.get("java_runtime"),
        "workers": job["workers"],
        "memory": job["memory"],
        "nice": job["nice"],
        "host": meta.get("host"),
        "start": meta.get("start"),
        "end": meta.get("end"),
        "status": status,
        "selection": job["selection"],
        "result_lines": [ln for ln in (out / "results.txt").read_text().splitlines()
                         if " expected " in ln],
        "results": rows,
    }
    (out / "record.json").write_text(json.dumps(record, indent=2) + "\n")
    print(f"run_tlc_remote: results in {out}")
    return status


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("models", nargs="*", metavar="<module>[:<config>]")
    p.add_argument("--workers", default="auto",
                   help=f"auto (default: pass lines {AUTO_WORKERS}, others 1) or 1..{MAX_WORKERS}")
    p.add_argument("--mem", default=DEFAULT_MEM, help=f"Java heap, -Xmx (default {DEFAULT_MEM})")
    p.add_argument("--unpinned", action="store_true",
                   help="run a copy of the working tree of spec/tla/")
    p.add_argument("--host", default=os.environ.get("TLC_LAB_HOST", DEFAULT_HOST))
    p.add_argument("--lab-root", default=os.environ.get("TLC_LAB_ROOT", DEFAULT_ROOT))
    p.add_argument("--out", help="local output directory (default build/lab/<run-id>)")
    p.add_argument("--detach", action="store_true",
                   help="start the job and stop; get the results with --collect")
    p.add_argument("--collect", metavar="RUN_ID",
                   help="wait for the job RUN_ID and copy its results")
    a = p.parse_args()

    if a.workers != "auto":
        if not a.workers.isdigit() or not 1 <= int(a.workers) <= MAX_WORKERS:
            die(f"--workers must be auto or 1..{MAX_WORKERS}")
    if not a.mem[:-1].isdigit() or a.mem[-1].lower() not in "mg":
        die("--mem must be like 4g or 512m")

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
