# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The subject of a run: which files its result depends on, and where the code of the run is kept.

An experiment names its `subject` (the models and the list file) and its `tools` (the runner, the pin of
the jar, the selftest) as repo paths. The subject tree of a run is the git object id of each path at the
revision of the run: `git rev-parse <rev>:<path>`. Two runs have the same subject tree if each path has the
same object id. A run on another revision counts for the experiment if its subject tree is the tree of the
current design (the revision itself does not matter: a commit that changes other files leaves the
trees as they are). This is the same idea as the firmware hash of the benchmarks.

The importer and the runner write the record of a run as the file `subject.json` into the run folder, before
the seal (the adapter tlc.py reads it; it never runs git). The record also holds the pin of the TLC jar of that
revision, which the evidence rule needs.

    subject_tree(rev, paths, repo)   {path: object id} of the subject paths at rev
    tool_tree(rev, paths, repo)      the same for the tool paths
    digest(tree)                     one sha256 over a tree (for a short comparison)
    record(rev, experiment, repo)    the dict of subject.json
    ref(experiment, utc)             refs/tlaplus/run/<experiment>/<UTC>
    pin(repo, rev, experiment, utc)  make that ref point to rev (keeps the commit alive)
"""

import hashlib
import subprocess
from pathlib import Path

from probatrix.core import config, runner

FILE = "subject.json"
# The pin of the TLC jar (the sha256 that run_tlc.sh and the lab job check).
JAR_PIN = "spec/tla/tools/tla2tools.sha256"


class SubjectError(Exception):
    """A subject path that does not exist at the revision, or a git error."""


def _git(repo, *args):
    r = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)
    if r.returncode != 0:
        raise SubjectError(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


def _repo(repo):
    return config.project().repo if repo is None else Path(repo)


def tree(rev, paths, repo=None):
    """{path: object id} for each path at rev (a tree id for a folder, a blob id for a file)."""
    repo = _repo(repo)
    out = {}
    for p in paths:
        try:
            out[p] = _git(repo, "rev-parse", "--verify", "--quiet", f"{rev}:{p}").strip()
        except SubjectError:
            raise SubjectError(f"{p} does not exist at the revision {rev}") from None
    return out


subject_tree = tree
tool_tree = tree


def digest(t):
    """"sha256:" + the sha256 over the lines "<path> <object id>" of the tree, sorted by path."""
    text = "".join(f"{p} {oid}\n" for p, oid in sorted(t.items()))
    return "sha256:" + hashlib.sha256(text.encode()).hexdigest()


def blob(rev, path, repo=None):
    """The text of a file at rev."""
    return _git(_repo(repo), "show", f"{rev}:{path}")


def record(rev, experiment, repo=None):
    """The content of subject.json for a run of the experiment (the dict of experiment.yaml) at rev."""
    repo = _repo(repo)
    full = _git(repo, "rev-parse", "--verify", f"{rev}^{{commit}}").strip()
    subj, tools = subject_tree(full, experiment["subject"], repo), tool_tree(full, experiment["tools"], repo)
    try:
        pin = blob(full, JAR_PIN, repo).split()[0]
    except (SubjectError, IndexError):
        pin = None
    return {"revision": full, "subject": subj, "tools": tools, "subject_tree": digest(subj),
            "tool_tree": digest(tools), "jar_pin": pin}


def ref(experiment, utc):
    """The git ref that keeps the commit of a run: refs/tlaplus/run/<experiment>/<UTC> (never pushed)."""
    from probatrix.tlaplus import kind
    return kind.KIND.ref("run", experiment, utc)


def pin(repo, rev, experiment, utc):
    """Make the ref of the run point to rev. Return the ref."""
    from probatrix.tlaplus import kind
    return runner.pin_run(kind.KIND, _repo(repo), rev, experiment, utc)
