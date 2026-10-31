# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The schemas of the hand-written YAML files (scripts/probatrix/benchmarks/schemas/).

    problems(kind, data)    all violations, as "<key path>: <text>"
    check(kind, data, file) raise SchemaError at the first violation

kind is "experiment", "study", "hypotheses" or "boards". A schema gives the
keys and their types (an unknown key is an error, with the nearest known
key as a hint); the meaning of a check, a point or a central result is
checked by checks.py, run.py and lint.py. The copies of experiment.yaml in
sealed runs are history: the tools do not check them against the current
schemas.
"""

import datetime
import difflib
import functools
from pathlib import Path

import yaml

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"
KINDS = ("experiment", "study", "hypotheses", "boards")


class SchemaError(ValueError):
    pass


@functools.cache
def validator(kind):
    import jsonschema
    from referencing import Registry, Resource

    resources = []
    for f in sorted(SCHEMA_DIR.glob("*.schema.yaml")):
        s = yaml.safe_load(f.read_text())
        resources.append((s["$id"], Resource.from_contents(s)))
    registry = Registry().with_resources(resources)
    schema = dict(registry.contents(f"latbench/{kind}.schema.yaml"))
    cls = jsonschema.validators.validator_for(schema)
    return cls(schema, registry=registry)


def plain(o):
    """YAML dates as text, as the tools read them."""
    if isinstance(o, (datetime.date, datetime.datetime)):
        return o.isoformat()
    if isinstance(o, dict):
        return {k: plain(v) for k, v in o.items()}
    if isinstance(o, list):
        return [plain(v) for v in o]
    return o


def where(err):
    return ".".join(str(p) for p in err.absolute_path) or "(top)"


def text(err):
    if err.validator == "additionalProperties" and isinstance(err.instance, dict):
        known = list(err.schema.get("properties", {}))
        out = []
        for k in sorted(set(err.instance) - set(known)):
            near = difflib.get_close_matches(str(k), known, n=1)
            out.append(f"unknown key {k!r}" + (f" (did you mean {near[0]!r}?)" if near else
                                               f" (known keys: {', '.join(known)})"))
        return "; ".join(out)
    if err.validator == "required":
        return f"missing key {err.message.split(' ')[0]}"
    if err.validator in ("oneOf", "anyOf") and err.context:
        # the branch that went deepest names the problem; "is not of type 'null'" never does
        ctx = [e for e in err.context if not (e.validator == "type" and e.validator_value == "null")] or err.context
        best = max(ctx, key=lambda e: len(list(e.absolute_path)))
        return (f"{where(best)}: " if best.absolute_path != err.absolute_path else "") + text(best)
    return err.message


def problems(kind, data):
    v = validator(kind)
    errs = sorted(v.iter_errors(plain(data)), key=lambda e: [str(p) for p in e.absolute_path])
    return [f"{where(e)}: {text(e)}" for e in errs]


def check(kind, data, file):
    p = problems(kind, data)
    if p:
        more = f" (and {len(p) - 1} more; 'study.py design lint' lists all)" if len(p) > 1 else ""
        raise SchemaError(f"{file}: {p[0]}{more}")
    return data
