# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The adapter for TLC: a raw TLC run folder -> <UTC>.run.json and <UTC>.tlc.json.

The raw run folder is what spec/tla/tools/run_tlc_remote.py leaves on the lab host (and, in a sealed run,
what the importer copies):

    job.json      the job: mode (pinned or unpinned), revision, workers, selftest, list, ...  (run_tlc_remote.py)
                  + for a simulation run: "tool": "tlc-simulate" and "simulate": {"<module>:<name>": {depth,
                  traces, seed}}, the parameters of each line after the defaults of the experiment
    meta.env      host, start, jar, jar_sha256, java, selftest_status, end, status
    results.txt   the result lines of run_tlc.sh
    out/results.tsv, out/<module>_<name>.log      the result row and the TLC log of each line
    selftest/results.tsv, selftest/*.log          the selftest of TLC that runs before the models
    subject.json  the subject record (subject.py): revision, subject tree, tool tree, jar pin

A copy that run_tlc_remote.py collect made on the local host has no out/ folder: the files of out/ are in
the run folder itself. Both layouts are read.

The files this module makes (formats tlaplus-run/1 and tlaplus-app-tlc/1):

    run.json  made_by, run (identity, provenance, evidence), points (tree = the tool, point = <module>:<name>,
              the log of each repetition with its sha256)
    tlc.json  points: [{point, params, reps: [{rep, values}]}]. values is what a check reads:
              verdict (str), expected (str), states, depth (int), seconds (float), evidence (bool), and
              violated, trace_len, lasso, collision_calculated, collision_actual, workers, heap, runner_verdict.
              A value that the row does not have ("-" or "?") is left out.

The evidence rule (evidence_reasons) is the rule of run_tlc_remote.py collect (see there).
"""

import json
import re
from pathlib import Path

from probatrix.core import seal

APP = "tlc"
TOOLS = ("tlc", "tlc-simulate")
RUN_FORMAT, APP_FORMAT = ("run", 1), ("app-tlc", 1)
ADAPTER = "scripts/probatrix/tlaplus/tlc.py"

# The columns of results.tsv that run_tlc.sh writes (the same list as TSV_COLUMNS of run_tlc_remote.py).
TSV_COLUMNS = ["module", "config", "expected", "result", "verdict", "violated", "distinct",
               "depth", "trace", "lasso", "collision_calculated", "collision_actual",
               "seconds", "workers", "heap"]

# ------------------------------------------------------------ reading the raw files
def read_meta(text):
    """{key: value} of meta.env. (Moved from run_tlc_remote.py collect: lines with "=", split at the first.)"""
    return dict(ln.split("=", 1) for ln in text.splitlines() if "=" in ln)


def read_rows(path):
    """The rows of a results.tsv of run_tlc.sh as dicts ([] if the file is missing).
    (Moved from read_rows of run_tlc_remote.py: a row with another number of columns is ignored.)"""
    path = Path(path)
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines()[1:]:
        c = line.split("\t")
        if len(c) == len(TSV_COLUMNS):
            rows.append(dict(zip(TSV_COLUMNS, c)))
    return rows


class Raw:
    """The files of a raw TLC run, read."""

    def __init__(self, run_dir):
        self.dir = Path(run_dir)
        self.job = json.loads((self.dir / "job.json").read_text())
        self.meta = read_meta((self.dir / "meta.env").read_text())
        self.tool = self.job.get("tool", "tlc")
        if self.tool not in TOOLS:
            raise ValueError(f"{self.dir}: the tool {self.tool!r} has no adapter in tlc.py (tools: {', '.join(TOOLS)})")
        self.out = self.dir / "out" if (self.dir / "out" / "results.tsv").is_file() else self.dir
        self.prefix = "" if self.out == self.dir else "out/"
        if not (self.out / "results.tsv").is_file():
            raise FileNotFoundError(f"{self.dir}: no results.tsv")
        self.rows = read_rows(self.out / "results.tsv")
        self.self_rows = read_rows(self.dir / "selftest" / "results.tsv")
        sj = self.dir / "subject.json"
        self.subject = json.loads(sj.read_text()) if sj.is_file() else None

    def log(self, row):
        """The path of the log of a row, relative to the run folder."""
        return f"{self.prefix}{row['module']}_{row['config']}.log"


# ------------------------------------------------------------ the evidence rule
def evidence_reasons(job, meta, pinned_jar):
    """Why a run is not evidence: a list of texts, empty for an evidence run (tools/TOOLS.rst, "The
    one-worker rule"). Moved from run_tlc_remote.py collect (the block "The conditions of an evidence run"),
    with one new text: pinned_jar None (the record of the run has no pin) gives "the pin of the jar is not
    known", where the original always read the pin from the working tree of the collecting host.

    job: job.json. meta: meta.env. pinned_jar: the sha256 in tools/tla2tools.sha256 at the revision of the run.
    The rule does not look at the results of the lines: a violated property does not exclude a run.
    """
    selftest_status = meta.get("selftest_status")
    reasons = []
    if job["mode"] != "pinned":
        reasons.append("unpinned: the code is not a commit")
    if int(job["workers"]) != 1:
        reasons.append(f"{job['workers']} workers in one TLC process (tlaplus issue #1445)")
    if not job.get("selftest", False):
        reasons.append("no selftest")
    elif selftest_status != "0":
        reasons.append(f"the selftest failed (status {selftest_status})")
    if pinned_jar is None:
        reasons.append("the pin of the jar is not known")
    elif meta.get("jar_sha256") != pinned_jar:
        reasons.append("the jar is not the pinned jar")
    return reasons


def evidence_of(raw):
    """(evidence, reasons) of a raw run. The pin comes from subject.json (written at the import or the run)."""
    pin = (raw.subject or {}).get("jar_pin")
    reasons = evidence_reasons(raw.job, raw.meta, pin)
    return not reasons, reasons


# ------------------------------------------------------------ simulation logs
STATES_GENERATED = re.compile(r"The number of states generated: ([0-9,]+)")


def simulation_states(log_text):
    """The number of states that TLC generated in a simulation run ("The number of states generated: N"), or None.
    This line comes from the message catalogue of TLC; there is no real simulation log in the repo yet
    (tests/fixtures/simulate is synthetic)."""
    m = STATES_GENERATED.findall(log_text)
    return int(m[-1].replace(",", "")) if m else None


# ------------------------------------------------------------ values
def _num(text, cast):
    """The number in a cell of results.tsv, or None for "-", "?" and an empty cell."""
    if text in ("", "-", "?"):
        return None
    try:
        return cast(text)
    except ValueError:
        return None


def point_id(row):
    return f"{row['module']}:{row['config']}"


def params_of(raw, row):
    """The point parameters of a row: depth, traces and seed of a simulation line, {} for a model check."""
    if raw.tool != "tlc-simulate":
        return {}
    got = raw.job.get("simulate", {}).get(point_id(row))
    if not isinstance(got, dict) or set(got) != {"depth", "traces", "seed"}:
        raise ValueError(f"{raw.dir}: job.json has no simulate parameters (depth, traces, seed) for {point_id(row)}")
    return {k: got[k] for k in ("depth", "traces", "seed")}


def values_of(raw, row, evidence):
    """The values of one row (see the module text)."""
    v = {"verdict": row["result"], "expected": row["expected"], "evidence": evidence,
         "runner_verdict": row["verdict"]}
    states, depth = _num(row["distinct"], int), _num(row["depth"], int)
    if raw.tool == "tlc-simulate":
        log = raw.dir / raw.log(row)
        states = simulation_states(log.read_text(errors="replace")) if log.is_file() else None
        depth = None            # TLC reports no depth of the state graph in simulation mode
    for k, x in (("states", states), ("depth", depth), ("seconds", _num(row["seconds"], float)),
                 ("trace_len", _num(row["trace"], int)), ("workers", _num(row["workers"], int)),
                 ("collision_calculated", _num(row["collision_calculated"], float)),
                 ("collision_actual", _num(row["collision_actual"], float))):
        if x is not None:
            v[k] = x
    for k, cell in (("violated", row["violated"]), ("lasso", row["lasso"]), ("heap", row["heap"])):
        if cell not in ("", "-", "?"):
            v[k] = cell
    return v


# ------------------------------------------------------------ the derived files
def selftest_summary(raw):
    """The selftest of the run: its status and the lines that did not give the expected result."""
    if not raw.job.get("selftest"):
        return None
    return {"status": raw.meta.get("selftest_status"), "lines": len(raw.self_rows),
            "unexpected": [point_id(r) for r in raw.self_rows if r["verdict"] != "as expected"]}


def copied_from(run_dir, run_id):
    """Where an imported run comes from: the field copied_from of its entry in the run list (the instance.json
    two folders above the run folder, <instance>/ex-<experiment>/<UTC>), or None."""
    try:
        data = json.loads((Path(run_dir).resolve().parent.parent / "instance.json").read_text())
    except (OSError, ValueError):
        return None
    entry = next((r for r in data.get("runs", []) if r.get("id") == run_id), None)
    return entry.get("copied_from") if entry else None


def run_json(run_dir, run_id, digest, made_by, experiment_file=None):
    """The data of <UTC>.run.json (the arguments are those of Kind.run_json)."""
    from probatrix.tlaplus import kind
    raw = Raw(run_dir)
    ev, reasons = evidence_of(raw)
    files = seal.files(run_dir)
    points = []
    for row in raw.rows:
        log = raw.log(row)
        points.append({"tree": raw.tool, "point": point_id(row), "axes": {},
                       "reps": [{"rep": 1, "log": log if log in files else None, "log_sha256": files.get(log)}]})
    job, meta = raw.job, raw.meta
    run = {"id": run_id, "digest": digest, "experiment": run_id.split("/")[0], "app": APP, "tool": raw.tool,
           "lab_id": job.get("run_id"), "mode": job["mode"], "revision": job["revision"],
           "branch": job.get("branch"), "safety_rev": job["revision"], "diff_sha256": job.get("diff_sha256"),
           "list": job.get("list", "expected"), "selection": job.get("selection"),
           "workers": int(job["workers"]), "jobs": job.get("jobs"), "memory": job.get("memory"),
           "mem_budget": job.get("mem_budget"), "gc_threads": job.get("gc_threads"), "nice": job.get("nice"),
           "host": meta.get("host"), "started": meta.get("start"), "finished": meta.get("end"),
           "status": int(meta.get("status", 2)), "jar": meta.get("jar"), "jar_sha256": meta.get("jar_sha256"),
           "java_version": meta.get("java_version"), "java_runtime": meta.get("java_runtime"),
           "mem_total_kb": meta.get("mem_total_kb"), "mem_available_kb": meta.get("mem_available_kb"),
           "evidence": ev, "not_evidence_reasons": reasons, "selftest": selftest_summary(raw),
           "subject": raw.subject}
    copied = copied_from(run_dir, run_id)
    if copied is not None:
        run["copied_from"] = copied
    if experiment_file is not None and Path(experiment_file).is_file():
        run["experiment_sha256"] = seal.file_sha256(experiment_file)
    return {"format": kind.KIND.format_id(*RUN_FORMAT), "made_by": made_by, "run": run, "points": points}


def app_json(run_dir, app, run_id, digest, made_by):
    """The data of <UTC>.tlc.json (the arguments are those of Kind.app_json)."""
    from probatrix.tlaplus import kind
    raw = Raw(run_dir)
    ev, reasons = evidence_of(raw)
    points = [{"point": point_id(row), "params": params_of(raw, row),
               "reps": [{"rep": 1, "values": values_of(raw, row, ev)}]} for row in raw.rows]
    return {"format": kind.KIND.format_id(*APP_FORMAT), "made_by": {**made_by, "adapter": ADAPTER},
            "run": {"id": run_id, "digest": digest}, "app": app, "tool": raw.tool,
            "evidence": ev, "not_evidence_reasons": reasons, "selftest": selftest_summary(raw),
            "points": points}
