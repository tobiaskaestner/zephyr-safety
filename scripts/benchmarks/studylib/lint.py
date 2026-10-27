# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The design lint: problems of the design files, found without a build or a board.

An error makes the design unusable or a check wrong (a folder without its
prefix, a point without a value on an axis, a check form that the tools
do not know, a reference to an experiment that the study cannot read, a
select of a point that the experiment does not have). A warning is a rule
of good practice (study.md, each axis named in experiment.md, 1-4
hypotheses per study). study.py lint fails on an error; run.py and the
campaign only warn, unless --warn-as-error.
"""

from pathlib import Path

import yaml

import trees

from . import checks, layout
from .design import Design, DesignError

ERROR, WARNING = "error", "warning"
PLACES = ("LATBENCH_CODE_FLASH", "LATBENCH_CODE_FLASH_PAD", "LATBENCH_CODE_RAM")
MAX_HYPOTHESES = 4


class Problem:
    def __init__(self, severity, path, text):
        self.severity, self.path, self.text = severity, Path(path), text

    def __str__(self):
        return f"{self.severity}: {self.where()}: {self.text}"

    def where(self):
        return self.path.relative_to(trees.REPO_DIR) if self.path.is_relative_to(trees.REPO_DIR) else self.path


def expand(exp):
    """The points of an experiment, or (None, message) if the file has an error."""
    import run
    try:
        return run.expand_points(exp), None
    except SystemExit as e:
        return None, str(e).removeprefix("error: ")


def is_y(kconfig, sym):
    import run
    return run.kconfig_value(kconfig.get(sym, "n")) == "y"


def lint_folders(root, out):
    for d in sorted(Path(root).rglob("*")):
        if not d.is_dir() or d.name == "__pycache__":
            continue
        if (d / "experiment.yaml").is_file():
            if not d.name.startswith(layout.EXPERIMENT_PREFIX):
                out.append(Problem(ERROR, d, f"an experiment folder must be {layout.EXPERIMENT_PREFIX}<name>"))
        elif (d / "study.yaml").is_file():
            if not d.name.startswith(layout.STUDY_PREFIX):
                out.append(Problem(ERROR, d, f"a study folder must be {layout.STUDY_PREFIX}<name>"))
            else:
                name = (yaml.safe_load((d / "study.yaml").read_text()) or {}).get("name")
                if name != d.name.removeprefix(layout.STUDY_PREFIX):
                    out.append(Problem(ERROR, d / "study.yaml", f"name {name!r} is not the folder name"))
        else:
            out.append(Problem(ERROR, d, "neither experiment.yaml nor study.yaml"))


def lint_experiment(e, out):
    f = e.folder / "experiment.yaml"
    exp = e.data
    if e.folder.name != layout.EXPERIMENT_PREFIX + e.name:
        out.append(Problem(ERROR, f, f"the folder must be {layout.EXPERIMENT_PREFIX}{e.name}"))
    md = e.folder / "experiment.md"
    if not md.is_file():
        out.append(Problem(ERROR, md, "each experiment has a description experiment.md"))
    if not (trees.BENCH_DIR / str(exp.get("app"))).is_dir():
        out.append(Problem(ERROR, f, f"app {exp.get('app')!r} is not a folder of tests/benchmarks"))
    names = [*(exp.get("axes") or {}), *(exp.get("extra_axes") or {})]
    if not names:
        out.append(Problem(ERROR, f, "an experiment has one axis or more"))
    pts, err = expand(exp)
    if err:
        out.append(Problem(ERROR, f, err))
        return []
    for pt in pts:
        if sorted(pt["axes"]) != sorted(names):
            out.append(Problem(ERROR, f, f"point {pt['id']}: axes {sorted(pt['axes'])}, the experiment has {sorted(names)}"))
    for axis, values in (exp.get("axes") or {}).items():
        for name, v in (values or {}).items():
            if v and "value" in v and not isinstance(v["value"], (int, float)):
                out.append(Problem(ERROR, f, f"axis {axis}.{name}: value must be a number"))
    lint_code_place(f, exp, pts, out)
    for a in e.acceptance:
        for p in checks.problems(a):
            out.append(Problem(ERROR, f, f"acceptance {a.get('id')}: {p}"))
        lint_select(f, f"acceptance {a.get('id')}", a.get("select"), pts, out)
    if md.is_file():
        text = md.read_text()
        missing = [a for a in names if a not in text]
        if missing:
            out.append(Problem(WARNING, md, f"the axes {missing} are not named in experiment.md"))
    return pts


def lint_code_place(f, exp, pts, out):
    boards = trees.load_boards()
    board = exp.get("board", boards["default"])
    if board not in boards["boards"]:
        out.append(Problem(ERROR, f, f"board {board!r} is not in boards.yaml"))
        return
    port = trees.BENCH_DIR / "common" / "boards" / boards["boards"][board]["port"]
    for pt in pts:
        k = pt["kconfig"]
        places = [s for s in PLACES if is_y(k, s)]
        if len(places) > 1:
            out.append(Problem(ERROR, f, f"point {pt['id']}: more than one code place: {places}"))
        if "LATBENCH_CODE_PAD_BYTES" in k:
            if not places or places[0] == "LATBENCH_CODE_FLASH":
                out.append(Problem(ERROR, f, f"point {pt['id']}: LATBENCH_CODE_PAD_BYTES needs "
                                             "LATBENCH_CODE_FLASH_PAD or LATBENCH_CODE_RAM"))
            if int(k["LATBENCH_CODE_PAD_BYTES"]) % 4:
                out.append(Problem(ERROR, f, f"point {pt['id']}: the pad must be a multiple of 4"))
        if is_y(k, "LATBENCH_CODE_RAM") and "LATBENCH_CODE_RAM_REGION" not in k and not (port / "Kconfig.port").is_file():
            out.append(Problem(ERROR, f, f"point {pt['id']}: LATBENCH_CODE_RAM, but the port {port.name} gives no RAM region"))


def lint_select(f, what, sel, pts, out):
    """A select must name points and axis values that the experiment has."""
    if not sel or pts is None:
        return
    ids = {p["id"] for p in pts}
    values = {}
    for p in pts:
        for a, v in p["axes"].items():
            values.setdefault(a, set()).add(v)
    for k, v in sel.items():
        if k == "point":
            bad = sorted(set(checks.as_list(v)) - ids)
            if bad:
                out.append(Problem(ERROR, f, f"{what}: select of the points {bad}, the experiment has no such points"))
        else:
            pairs = v.items() if k == "axes" else [(k, v)]
            for a, x in pairs:
                if a not in values:
                    out.append(Problem(ERROR, f, f"{what}: select on the axis {a!r}, the experiment has no such axis"))
                elif set(map(str, checks.as_list(x))) - values[a]:
                    bad = sorted(set(map(str, checks.as_list(x))) - values[a])
                    out.append(Problem(ERROR, f, f"{what}: select of {a} = {bad}, the experiment has no such values"))


def lint_study(d, path, st, points, out):
    f = st.folder / "hypotheses.yaml"
    if not (st.folder / "study.md").is_file():
        out.append(Problem(WARNING, st.folder / "study.md", "a study has a description study.md"))
    if len(st.hypotheses) > MAX_HYPOTHESES:
        out.append(Problem(WARNING, f, f"{len(st.hypotheses)} hypotheses; a study aims for 1-{MAX_HYPOTHESES}"))
    readable = st.readable()
    for h in st.hypotheses:
        for c in h.get("checks") or []:
            what = f"{h.get('id')} {c.get('id')}"
            for p in checks.problems(c):
                out.append(Problem(ERROR, f, f"{what}: {p}"))
            exp = c.get("experiment")
            if c.get("manual") and exp is None:
                continue
            if exp not in readable:
                out.append(Problem(ERROR, f, f"{what}: experiment {exp!r} is not an experiment of the study "
                                             "and not imported"))
                continue
            lint_select(f, what, c.get("select"), points.get(exp), out)
            ref = (c.get("expect") or {}).get("diff_to") or {}
            if isinstance(ref, dict) and ref.get("experiment") and ref["experiment"] not in d.experiments:
                out.append(Problem(ERROR, f, f"{what}: diff_to experiment {ref['experiment']!r} does not exist"))
    sf = st.folder / "study.yaml"
    for cr in st.central_results:
        frm = cr.get("from") or {}
        exp = frm.get("experiment")
        if exp is not None:
            for e in checks.as_list(exp):
                if e not in readable:
                    out.append(Problem(ERROR, sf, f"central result {cr.get('id')}: experiment {e!r} is not an "
                                                  "experiment of the study and not imported"))
            if frm.get("point") and not isinstance(exp, list):
                lint_select(sf, f"central result {cr.get('id')}", {"point": frm["point"]}, points.get(exp), out)
        sub = frm.get("substudy")
        if sub and not any(s.rsplit("/", 1)[-1] == sub for s in st.substudies):
            out.append(Problem(ERROR, sf, f"central result {cr.get('id')}: {sub!r} is not a sub-study"))


def lint(root=None, only=None):
    """All problems of the design tree (root: default validation/empirical/latencies).

    only: a folder; return only the problems of the files below it.
    """
    root = Path(root or trees.STUDIES_DIR)
    out = []
    lint_folders(root, out)
    try:
        d = Design(root)
    except (DesignError, OSError, yaml.YAMLError, KeyError, TypeError) as e:
        out.append(Problem(ERROR, root, f"the design does not load: {e}"))
        d = None
    if d is not None:
        points = {name: lint_experiment(e, out) for name, e in d.experiments.items()}
        for path, st in d.studies.items():
            lint_study(d, path, st, points, out)
    if only is not None:
        only = Path(only).resolve()
        out = [p for p in out if p.path.resolve().is_relative_to(only) or only.is_relative_to(p.path.resolve())]
    return sorted(out, key=lambda p: (p.severity != ERROR, str(p.path), p.text))


def lint_for_experiment(experiment_file):
    """The problems of an experiment and of the study that owns it (for run.py and the campaign)."""
    folder = Path(experiment_file).resolve().parent
    study = folder.parent
    return [p for p in lint() if p.path.resolve().is_relative_to(folder) or p.path.resolve() == study
            or p.path.resolve().parent == study]
