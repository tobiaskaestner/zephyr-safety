# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Make the files of a new study or of a new experiment from templates.

    new_study(parent folder, name, app, experiment name)
        st-<name>/ with study.yaml, study.md, hypotheses.yaml (one template
        hypothesis) and a first experiment ex-<experiment>/; the parent
        study.yaml gets the sub-study.
    new_experiment(study folder, name, app)
        ex-<name>/ with experiment.yaml and experiment.md; the study.yaml of
        the study gets the experiment.

The templates pass the design lint without errors. Their TODO texts give
lint warnings until the author replaces them.
"""

import datetime
import re
from pathlib import Path

import yaml

import trees

from . import layout

HEADER = "# Copyright (c) {year} inovex GmbH\n# SPDX-License-Identifier: Apache-2.0\n"
# The main metric of each app, for the template check and the acceptance check.
APP_METRIC = {"irq_latency": "irq", "wake_latency": "isr2thr", "thread_latency": "t2t"}


class ScaffoldError(Exception):
    pass


def header():
    return HEADER.format(year=datetime.date.today().year)


def check_name(name):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name):
        raise ScaffoldError(f"name {name!r}: use lower case letters, digits and '-'")


def app_metric(app):
    if not (trees.BENCH_DIR / app).is_dir():
        raise ScaffoldError(f"app {app!r} is not a folder of tests/benchmarks")
    return APP_METRIC.get(app, "irq")


def add_to_list(study_yaml, key, item, entry):
    """Add a list entry to key of a study.yaml as text (the comments stay)."""
    text = study_yaml.read_text()
    data = yaml.safe_load(text) or {}
    have = [x["use"] if isinstance(x, dict) else x for x in data.get(key) or []]
    if item in have:
        raise ScaffoldError(f"{study_yaml}: {key} has {item} already")
    lines = text.splitlines(keepends=True)
    head = next((i for i, ln in enumerate(lines) if re.match(rf"^{key}:", ln)), None)
    if head is None:
        if not text.endswith("\n"):
            text += "\n"
        study_yaml.write_text(f"{text}\n{key}:\n  - {entry}\n")
        return
    if re.match(rf"^{key}:\s*(\[\s*\])?\s*(#.*)?$", lines[head]) and "[" in lines[head]:
        lines[head] = f"{key}:\n"
    # the items: "- x" at the indent of the first item (none or some spaces), with their continuation lines
    end, last, indent = head + 1, head, None
    while end < len(lines):
        ln = lines[end]
        item = re.match(r"^( *)- ", ln)
        if item and (indent is None or item.group(1) == indent):
            indent = item.group(1)
            last = end
        elif not ln.strip() or ln.lstrip().startswith("#"):
            pass
        elif indent is not None and ln.startswith(indent + " "):
            last = end
        else:
            break
        end += 1
    lines.insert(last + 1, f"{'  ' if indent is None else indent}- {entry}\n")
    study_yaml.write_text("".join(lines))
    if yaml.safe_load(study_yaml.read_text()).get(key) is None:
        raise ScaffoldError(f"{study_yaml}: the edit of {key} failed")


def design_root(folder):
    """The top study folder above folder: the highest folder with study.yaml."""
    top = None
    for p in [Path(folder), *Path(folder).parents]:
        if (p / "study.yaml").is_file():
            top = p
        elif top is not None:
            break
    return top


def experiment_exists(folder, name):
    return any(p.parent.name == layout.EXPERIMENT_PREFIX + name
               for p in design_root(folder).rglob("experiment.yaml"))


def experiment_files(folder, name, app, board=None):
    metric = app_metric(app)
    tree = next(iter(trees.load()["trees"]))
    exp = folder / f"{layout.EXPERIMENT_PREFIX}{name}"
    if exp.exists():
        raise ScaffoldError(f"{exp} exists")
    exp.mkdir(parents=True)
    board_line = f"board: {board}\n" if board else ""
    (exp / "experiment.yaml").write_text(f"""{header()}
# The experiment {name}. Keys: tests/benchmarks/README.md and
# doc/benchmark-guide/studies.rst. experiment.md describes what it measures
# and what each axis is for.

name: {name}
app: {app}
{board_line}trees: [{tree}]
repeat: 1
timeout: 900
common:
  kconfig:
    LATBENCH_SAMPLES: 100000
axes:
  variant:              # TODO: the axes of the experiment
    default: {{}}
acceptance:
  - id: A1
    metric: {metric}
    stat: invalid
    expect: {{equals: 0}}
    basis: No negative differences, so the stimulus and the time stamps work.
""")
    (exp / "experiment.md").write_text(f"""# {name}

## What it measures

TODO: app `{app}`, metric `{metric}`: what the experiment measures.

## Method

TODO: the stimulus, the samples, the load, the clock.

## Axes

- **variant**: TODO: what the axis varies and why.
""")
    return exp


def new_experiment(study_folder, name, app, board=None):
    study_folder = Path(study_folder).resolve()
    check_name(name)
    if not (study_folder / "study.yaml").is_file():
        raise ScaffoldError(f"{study_folder} is not a study folder (no study.yaml)")
    if experiment_exists(study_folder, name):
        raise ScaffoldError(f"an experiment {name} exists (names are unique over all studies)")
    exp = experiment_files(study_folder, name, app, board)
    add_to_list(study_folder / "study.yaml", "experiments", name, name)
    return exp


def new_study(parent_folder, name, app, experiment=None, board=None):
    parent_folder = Path(parent_folder).resolve()
    check_name(name)
    experiment = experiment or f"{name}-smoke"
    check_name(experiment)
    if not (parent_folder / "study.yaml").is_file():
        raise ScaffoldError(f"{parent_folder} is not a study folder (no study.yaml)")
    folder = parent_folder / f"{layout.STUDY_PREFIX}{name}"
    if folder.exists():
        raise ScaffoldError(f"{folder} exists")
    if experiment_exists(parent_folder, experiment):
        raise ScaffoldError(f"an experiment {experiment} exists (names are unique over all studies)")
    metric = app_metric(app)
    folder.mkdir()
    today = datetime.date.today().isoformat()
    (folder / "study.yaml").write_text(f"""{header()}
# The study {name}. study.md has the background and why each experiment
# is there; hypotheses.yaml has the claims and their checks.

name: {name}
question: >
  TODO: the question of the study, in one or two sentences.

experiments:
  - {experiment}

central_results: []
""")
    (folder / "study.md").write_text(f"""# {name}

## Background

TODO: what the study is about and why; the mechanisms that the experiments test.

## Experiments

- `{experiment}`: TODO: why the experiment is there and how it connects to the others.

## References

TODO: the sources of the background and of the predictions.
""")
    (folder / "hypotheses.yaml").write_text(f"""{header()}
# Hypotheses of the study {name}: 1-4 claims about a mechanism. A
# hypothesis is wrong if one of its checks is wrong. Write each statement
# and each limit before the run of its experiment. The check forms are in
# doc/benchmark-guide/studies.rst.
#
# Keys of a hypothesis: id, type (method | model), statement, basis,
# wrong_if, checks. Keys of a check: id, written, experiment, select,
# metric, stat, expect, basis (manual: true and statement for a person).

hypotheses:
  - id: H1
    type: model
    statement: >
      TODO: the claim, one or two sentences.
    basis: >
      TODO: the mechanism and its sources.
    wrong_if: "TODO: what a wrong hypothesis means for the study."
    checks:
      - id: a
        written: {today}, before the first run of {experiment}
        experiment: {experiment}
        metric: {metric}
        stat: p50
        expect: {{range: [0, 1000000]}}      # TODO: the limit
        basis: "TODO: where the number of the check comes from."
""")
    experiment_files(folder, experiment, app, board)
    add_to_list(parent_folder / "study.yaml", "substudies", name, f"use: {name}")
    return folder


def scaffold(path, app, experiment=None, board=None):
    """Make the study (st-<name>) or the experiment (ex-<name>) that path names; return its folder."""
    path = Path(path).resolve()
    if path.name.startswith(layout.STUDY_PREFIX):
        return new_study(path.parent, path.name[len(layout.STUDY_PREFIX):], app, experiment, board)
    if path.name.startswith(layout.EXPERIMENT_PREFIX):
        if experiment:
            raise ScaffoldError("--experiment is for a new study only")
        return new_experiment(path.parent, path.name[len(layout.EXPERIMENT_PREFIX):], app, board)
    raise ScaffoldError(f"{path.name}: the folder name must start with {layout.STUDY_PREFIX} (a study) "
                        f"or {layout.EXPERIMENT_PREFIX} (an experiment)")
