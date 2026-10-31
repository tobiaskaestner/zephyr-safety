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
    LATBENCH_REPO       the safety repo (the design and scripts/probatrix/benchmarks/data.py)

and the safety repo as the current folder, and writes
<instance>/notebooks/<name>.html (nbconvert), the executed notebook
<instance>/notebooks/<name>.ipynb (with its outputs; JupyterLab opens it
there and can run it again, as the notebook finds its instance and the
lab space from its folder) and notebooks.json: for each
notebook the digest of its inputs (the notebook file, the study.json of
the instance and the helper modules data.py and nbfig.py). With the same
digest, the notebook does not run again (--force runs it). The output of a notebook is not byte-stable (time
stamps, ids), so "analysis check" does not compare it. The packages are
in scripts/probatrix/benchmarks/requirements-notebooks.lock (not needed for the other
commands).
"""

import hashlib
import json
import os
import re
from pathlib import Path


from probatrix.core import config
import yaml

from probatrix.core import layout

FORMAT = "latbench-notebooks/1"
TIMEOUT = 900


class NotebookError(Exception):
    pass


def notebooks_of(design_folder):
    d = Path(design_folder)
    return sorted(d.glob("*.ipynb")) + sorted((d / "notebooks").glob("*.ipynb"))


# The helper modules of the notebooks and this module (it adds the study text): a change of them
# changes the output too.
HELPERS = ("scripts/probatrix/benchmarks/data.py", "scripts/probatrix/benchmarks/nbfig.py", "scripts/probatrix/benchmarks/studylib/notebooks.py")


def inputs_digest(nb, study_json, repo=None, extra=()):
    h = hashlib.sha256()
    for f in (nb, study_json, *extra):
        h.update(hashlib.sha256(Path(f).read_bytes() if Path(f).is_file() else b"").digest())
    for rel in HELPERS:
        f = Path(repo or config.project().repo) / rel
        h.update(hashlib.sha256(f.read_bytes() if f.is_file() else b"").digest())
    return h.hexdigest()


# ------------------------------------------------------------ the study text in the executed copy
def _md_body(text, level):
    """A Markdown file without its first "# " heading; its "## " headings become headings of level."""
    lines = text.strip("\n").splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    out = [("#" * (level - 2) + l) if re.match(r"^#+ ", l) else l for l in lines]
    return "\n".join(out).strip("\n")


def _report_of(folder):
    """(name of the first notebook, its instance folder) of an instance folder, or None."""
    sj = folder / "study.json"
    if not sj.is_file():
        return None
    nbs = notebooks_of(config.project().repo / json.loads(sj.read_text())["design"]["folder"])
    return nbs[0].stem if nbs else None


def _verdicts(sj):
    hs, cr = sj.get("hypotheses") or [], sj.get("central_results") or []
    n = {v: sum(1 for h in hs if h.get("verdict") == v) for v in ("confirmed", "wrong")}
    out = [f"H {n['confirmed']} confirmed, {n['wrong']} wrong, {len(hs) - n['confirmed'] - n['wrong']} open"] if hs else []
    if cr:
        out.append(f"{sum(1 for c in cr if not c.get('not_evaluated'))} of {len(cr)} central results")
    return "; ".join(out) or "no hypotheses and no central results"


def _link(inst, target, name):
    """Markdown links from <inst>/notebooks/ to the report of another instance (notebook and HTML)."""
    rel = os.path.relpath(target / "notebooks", inst / "notebooks")
    return f"[{name}]({rel}/{name}.ipynb) ([HTML]({rel}/{name}.html))"


def study_cells(inst, root):
    """The Markdown cells that the executed copy gets from the design: (after the title, at the end).

    After the title: the place of the study in the tree (the report of the parent study and of each
    sub-study, with its question and verdicts) and the text of study.md. At the end: the experiment.md
    of each experiment of the study, and the reports of the studies that own the imported experiments.
    Also returns the files that the text comes from (they are inputs of the notebook)."""
    sj = json.loads((inst / "study.json").read_text())
    design = config.project().repo / sj["design"]["folder"]
    files, head, tail = [], [], []
    nav = []
    parent = inst.parent
    if inst != root and (parent / "study.json").is_file() and _report_of(parent):
        psj = json.loads((parent / "study.json").read_text())
        pname = parent.name[len(layout.STUDY_PREFIX):].split("@")[0] if parent != root else parent.name
        nav.append(f"Part of **{pname}** ({_link(inst, parent, _report_of(parent))}): {psj['question'].strip()}\n")
        files.append(parent / "study.json")
    subs = sorted(d for d in inst.iterdir() if d.is_dir() and d.name.startswith(layout.STUDY_PREFIX)
                  and (d / "study.json").is_file())
    if subs:
        nav.append("Sub-studies:\n")
        for d in subs:
            dsj = json.loads((d / "study.json").read_text())
            name = d.name[len(layout.STUDY_PREFIX):].split("@")[0]
            report = _report_of(d)
            ref = f"**{name}** ({_link(inst, d, report)})" if report else f"**{name}**"
            nav.append(f"- {ref}: {dsj['question'].strip()} *{_verdicts(dsj)}.*")
            files.append(d / "study.json")
    if nav:
        head.append("## The study in the tree\n\n" + "\n".join(nav))
    md = design / "study.md"
    if md.is_file():
        head.append("## The study (study.md)\n\n" + _md_body(md.read_text(), 3))
        files.append(md)
    exps = []
    for e in sj.get("experiments", []):
        f = design / f"{layout.EXPERIMENT_PREFIX}{e['name']}" / "experiment.md"
        if f.is_file():
            exps.append(f"### {e['name']}\n\n" + _md_body(f.read_text(), 4))
            files.append(f)
    if exps:
        tail.append("## The experiments (experiment.md)\n\n" + "\n\n".join(exps))
    sy = design / "study.yaml"
    imports = (yaml.safe_load(sy.read_text()) or {}).get("imports") or [] if sy.is_file() else []
    if imports:
        board = sj.get("board")
        owners = {layout.strip_board(layout.instance_path_of(f, root)): f for f in layout.instance_folders(root)
                  if f != root and json.loads((f / "instance.json").read_text()).get("board") in (None, board)}
        lines = []
        for imp in imports:
            owner = owners.get(imp["study"])
            report = _report_of(owner) if owner else None
            where = f"{imp['study']} ({_link(inst, owner, report)})" if report else imp["study"]
            lines.append(f"- `{imp['experiment']}` from {where}, mode `{imp.get('mode', 'reuse')}`")
        tail.append("## Imported experiments\n\nThe experiment.md of these experiments is in the report of "
                    "the study that owns them.\n\n" + "\n".join(lines))
    return head, tail, files


HIDE_INPUT = "hide-input"


def compose(nb, inst, root):
    """Put the study cells into a notebook node: after its first Markdown cell, and at the end."""
    import nbformat
    head, tail, _ = study_cells(inst, root)
    cells = lambda texts: [nbformat.v4.new_markdown_cell(t, metadata={"latbench": "from the design"})
                           for t in texts]
    first = next((i for i, c in enumerate(nb.cells) if c.cell_type == "markdown"), -1)
    nb.cells[first + 1:first + 1] = cells(head)
    nb.cells += cells(tail)
    # the parameter and import cells of the standard head: their code is folded (JupyterLab) and not in
    # the HTML; their output stays
    for c in [c for c in nb.cells if c.cell_type == "code"][:2]:
        c.metadata.setdefault("jupyter", {})["source_hidden"] = True
        c.metadata.setdefault("tags", []).append(HIDE_INPUT)
    return nb


def execute(nb_file, instance_folder, repo):
    """Run a notebook; return (its HTML, the executed notebook as text) (nbclient, nbconvert)."""
    try:
        import nbclient
        import nbformat
        from nbconvert import HTMLExporter
    except ImportError as e:
        raise NotebookError(f"{e}: install scripts/probatrix/benchmarks/requirements-notebooks.lock into the venv "
                            "of the lab space") from None
    nb = nbformat.read(str(nb_file), as_version=4)
    compose(nb, Path(instance_folder), layout.find_root(instance_folder))
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
    from nbconvert.preprocessors import TagRemovePreprocessor
    exporter = HTMLExporter()
    exporter.register_preprocessor(TagRemovePreprocessor(remove_input_tags={HIDE_INPUT}), enabled=True)
    body, _ = exporter.from_notebook_node(nb)
    return body, nbformat.writes(nb)


def run(folder, force=False, log=print, executor=execute):
    """Run the notebooks of the instances at and below folder; return [(instance, notebook, status)]."""
    root = layout.find_root(folder)
    below = Path(folder).resolve()
    out = []
    for inst in layout.instance_folders(root):
        sj = inst / "study.json"
        if not sj.is_file() or not inst.resolve().is_relative_to(below):
            continue
        design = config.project().repo / json.loads(sj.read_text())["design"]["folder"]
        nbs = notebooks_of(design)
        if not nbs:
            continue
        odir = inst / "notebooks"
        odir.mkdir(exist_ok=True)
        index_f = odir / "notebooks.json"
        index = json.loads(index_f.read_text()) if index_f.is_file() else {"format": FORMAT, "notebooks": {}}
        for nb in nbs:
            name = nb.stem
            digest = inputs_digest(nb, sj, extra=study_cells(inst, root)[2])
            have = index["notebooks"].get(name, {})
            done = [have.get("html"), have.get("ipynb")]
            if not force and have.get("inputs") == digest and all((odir / f).is_file() for f in done if f) and done[0]:
                out.append((inst, name, "the same inputs"))
                continue
            try:
                html = executor(nb, inst, config.project().repo)
                html, ipynb = html if isinstance(html, tuple) else (html, None)
            except NotebookError as e:
                index["notebooks"][name] = {"inputs": digest, "notebook": str(nb.relative_to(config.project().repo)),
                                            "error": str(e)}
                out.append((inst, name, f"FAILED: {e}"))
                log(f"{layout.instance_path_of(inst, root) or '(top)'}: {name}: FAILED: {e}")
                continue
            (odir / f"{name}.html").write_text(html)
            index["notebooks"][name] = {"inputs": digest, "notebook": str(nb.relative_to(config.project().repo)),
                                        "html": f"{name}.html"}
            if ipynb is not None:
                # the executed notebook beside its HTML: JupyterLab opens it in the results tree, and it
                # finds its instance from its folder
                (odir / f"{name}.ipynb").write_text(ipynb)
                index["notebooks"][name]["ipynb"] = f"{name}.ipynb"
            out.append((inst, name, "ran"))
            log(f"{layout.instance_path_of(inst, root) or '(top)'}: {name}: notebooks/{name}.html")
        index_f.write_text(json.dumps(index, indent=1, sort_keys=True) + "\n")
    return out
