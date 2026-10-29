# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The notebooks of the studies, run against the instances of a results tree.

    study.py analysis notebooks FOLDER [--force]

A study can have notebooks in its design folder: <study>/*.ipynb and
<study>/notebooks/*.ipynb, committed without outputs. They answer the
questions that the standard plots of the apps cannot: comparisons over
experiments, trees and boards. For each instance at and below FOLDER whose
study has notebooks, this module runs each notebook (nbclient) with the
environment

    LATBENCH_INSTANCE   the instance folder
    LATBENCH_REPO       the safety repo (the design and scripts/benchmarks/data.py)

and the safety repo as the current folder, and writes
<instance>/notebooks/<name>.html (nbconvert) and notebooks.json: for each
notebook the digest of its inputs (the notebook file, the study.json of
the instance and the helper modules data.py and nbfig.py). With the same digest, the notebook does not run again
(--force runs it). The output of a notebook is not byte-stable (time
stamps, ids), so "analysis check" does not compare it. The packages are
in scripts/benchmarks/requirements-notebooks.lock (not needed for the other
commands).
"""

import hashlib
import json
import os
from pathlib import Path

import trees

from . import layout

FORMAT = "latbench-notebooks/1"
TIMEOUT = 900


class NotebookError(Exception):
    pass


def notebooks_of(design_folder):
    d = Path(design_folder)
    return sorted(d.glob("*.ipynb")) + sorted((d / "notebooks").glob("*.ipynb"))


# The helper modules of the notebooks: a change of them changes the output too.
HELPERS = ("scripts/benchmarks/data.py", "scripts/benchmarks/nbfig.py")


def inputs_digest(nb, study_json, repo=None):
    h = hashlib.sha256()
    for f in (nb, study_json):
        h.update(hashlib.sha256(Path(f).read_bytes()).digest())
    for rel in HELPERS:
        f = Path(repo or trees.REPO_DIR) / rel
        h.update(hashlib.sha256(f.read_bytes() if f.is_file() else b"").digest())
    return h.hexdigest()


def execute(nb_file, instance_folder, repo):
    """Run a notebook; return its HTML (nbclient, nbconvert)."""
    try:
        import nbclient
        import nbformat
        from nbconvert import HTMLExporter
    except ImportError as e:
        raise NotebookError(f"{e}: install scripts/benchmarks/requirements-notebooks.lock into the venv "
                            "of the lab space") from None
    nb = nbformat.read(str(nb_file), as_version=4)
    old = {k: os.environ.get(k) for k in ("LATBENCH_INSTANCE", "LATBENCH_REPO")}
    os.environ.update(LATBENCH_INSTANCE=str(instance_folder), LATBENCH_REPO=str(repo))
    try:
        nbclient.NotebookClient(nb, timeout=TIMEOUT, kernel_name="python3",
                                resources={"metadata": {"path": str(repo)}}).execute()
    except Exception as e:      # a cell error: nbclient names the cell
        import re
        text = re.sub(r"\x1b\[[0-9;]*m", "", str(e)).strip().splitlines()
        raise NotebookError(f"{nb_file.name}: {type(e).__name__}: {(text or [''])[-1][:300]}") from None
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    body, _ = HTMLExporter().from_notebook_node(nb)
    return body


def run(folder, force=False, log=print, executor=execute):
    """Run the notebooks of the instances at and below folder; return [(instance, notebook, status)]."""
    root = layout.find_root(folder)
    below = Path(folder).resolve()
    out = []
    for inst in layout.instance_folders(root):
        sj = inst / "study.json"
        if not sj.is_file() or not inst.resolve().is_relative_to(below):
            continue
        design = trees.REPO_DIR / json.loads(sj.read_text())["design"]["folder"]
        nbs = notebooks_of(design)
        if not nbs:
            continue
        odir = inst / "notebooks"
        odir.mkdir(exist_ok=True)
        index_f = odir / "notebooks.json"
        index = json.loads(index_f.read_text()) if index_f.is_file() else {"format": FORMAT, "notebooks": {}}
        for nb in nbs:
            name = nb.stem
            digest = inputs_digest(nb, sj)
            have = index["notebooks"].get(name, {})
            if not force and have.get("inputs") == digest and (odir / f"{name}.html").is_file():
                out.append((inst, name, "the same inputs"))
                continue
            try:
                html = executor(nb, inst, trees.REPO_DIR)
            except NotebookError as e:
                index["notebooks"][name] = {"inputs": digest, "notebook": str(nb.relative_to(trees.REPO_DIR)),
                                            "error": str(e)}
                out.append((inst, name, f"FAILED: {e}"))
                log(f"{layout.instance_path_of(inst, root) or '(top)'}: {name}: FAILED: {e}")
                continue
            (odir / f"{name}.html").write_text(html)
            index["notebooks"][name] = {"inputs": digest, "notebook": str(nb.relative_to(trees.REPO_DIR)),
                                        "html": f"{name}.html"}
            out.append((inst, name, "ran"))
            log(f"{layout.instance_path_of(inst, root) or '(top)'}: {name}: notebooks/{name}.html")
        index_f.write_text(json.dumps(index, indent=1, sort_keys=True) + "\n")
    return out
