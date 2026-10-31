# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Make the files of a new study or of a new experiment from templates.

    study.py design scaffold study PARENT/st-NAME
        st-<name>/ with study.yaml (no experiments), study.md and
        hypotheses.yaml (one template hypothesis without checks); the parent
        study.yaml gets the sub-study.
    study.py design scaffold experiment STUDY/ex-NAME --app APP [--board B]
        ex-<name>/ with experiment.yaml and experiment.md; the study.yaml of
        the study gets the experiment, and study.md a line for it.

The templates pass the design lint without errors. Their TODO texts give
lint warnings until the author replaces them. A study gets no first
experiment and its hypothesis no check: a template check would give a
verdict from a limit that nobody wrote.
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
# The experiment {name}. Keys: scripts/probatrix/benchmarks/schemas/experiment.schema.yaml
# and the benchmark guide ("Experiment file"). experiment.md describes what
# it measures and what each axis is for.

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
    add_to_md(study_folder / "study.md", name)
    return exp


def add_to_md(study_md, name):
    """Add the line of a new experiment to the section Experiments of study.md, if there is one."""
    if not study_md.is_file():
        return
    lines = study_md.read_text().splitlines(keepends=True)
    head = next((i for i, ln in enumerate(lines) if ln.strip() == "## Experiments"), None)
    if head is None:
        return
    end = next((i for i in range(head + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    while end > head + 1 and not lines[end - 1].strip():
        end -= 1
    new = f"- `{name}`: TODO: why the experiment is there and how it connects to the others.\n"
    body = [i for i in range(head + 1, end) if lines[i].strip()]
    if len(body) == 1 and lines[body[0]].startswith("TODO: the experiments"):
        lines[body[0]] = new          # the template line of a study without experiments
    else:
        lines.insert(end, new)
    study_md.write_text("".join(lines))


def new_study(parent_folder, name):
    parent_folder = Path(parent_folder).resolve()
    check_name(name)
    if not (parent_folder / "study.yaml").is_file():
        raise ScaffoldError(f"{parent_folder} is not a study folder (no study.yaml)")
    folder = parent_folder / f"{layout.STUDY_PREFIX}{name}"
    if folder.exists():
        raise ScaffoldError(f"{folder} exists")
    folder.mkdir()
    (folder / "study.yaml").write_text(f"""{header()}
# The study {name}. study.md has the background and why each experiment
# is there; hypotheses.yaml has the claims and their checks. Add the
# experiments with 'study.py design scaffold experiment'.

name: {name}
question: >
  TODO: the question of the study, in one or two sentences.

experiments: []

central_results: []
""")
    (folder / "study.md").write_text(f"""# {name}

## Background

TODO: what the study is about and why; the mechanisms that the experiments test.

## Experiments

TODO: the experiments, one line each: why it is there and how it connects to the others.

## References

TODO: the sources of the background and of the predictions.
""")
    (folder / "hypotheses.yaml").write_text(f"""{header()}
# Hypotheses of the study {name}: 1-4 claims about a mechanism. A
# hypothesis is wrong if one of its checks is wrong. Write each statement
# and each limit before the run of its experiment. The check forms are in
# doc/benchmark-guide/reference/check-forms.rst.
#
# Keys of a hypothesis: id, type (method | model), statement, basis,
# wrong_if, checks. Keys of a check: id, written, experiment, select,
# metric, stat, expect, basis (manual: true and statement for a person).
# A check with a TODO text gets the verdict "draft".

hypotheses:
  - id: H1
    type: model
    statement: >
      TODO: the claim, one or two sentences.
    basis: >
      TODO: the mechanism and its sources.
    wrong_if: "TODO: what a wrong hypothesis means for the study."
    checks: []
""")
    add_to_list(parent_folder / "study.yaml", "substudies", name, f"use: {name}")
    return folder


def split(path, prefix):
    """(parent folder, name) of a path whose last part must start with prefix."""
    path = Path(path).resolve()
    if not path.name.startswith(prefix):
        raise ScaffoldError(f"{path.name}: the folder name must start with {prefix}")
    return path.parent, path.name[len(prefix):]


def scaffold_study(path):
    """Make the study PARENT/st-<name>; return its folder."""
    return new_study(*split(path, layout.STUDY_PREFIX))


def scaffold_experiment(path, app, board=None):
    """Make the experiment STUDY/ex-<name>; return its folder."""
    parent, name = split(path, layout.EXPERIMENT_PREFIX)
    return new_experiment(parent, name, app, board)
