# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The schemas of the hand-written YAML files.

    register(prefix, folder, default=True)   make the schema folder of a kind known (its $id prefix)
    problems(kind, data)           all violations, as "<key path>: <text>"
    check(kind, data, file)        raise SchemaError at the first violation

A kind of study brings a folder of <name>.schema.yaml files. The $id of each file is
"<prefix>/<name>.schema.yaml" (for the benchmarks: latbench/study.schema.yaml). "kind" in the
calls below is the name of a file ("experiment", "study", "hypotheses", "boards"); the prefix is
the first one registered that is not marked default=False, or the one given with prefix=. A kind that is
not the main kind of the tools registers with default=False, so the order of the imports cannot change what
the calls without a prefix read. A schema gives the
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

from probatrix.core.errors import SchemaError  # noqa: F401  (schema.SchemaError)

_FOLDERS = {}          # $id prefix -> schema folder
_NOT_DEFAULT = set()   # the prefixes that registered with default=False


def register(prefix, folder, default=True):
    """Make the schema folder of a kind known. The first prefix registered with default=True is the default one
    (the first prefix of all if no prefix is a default)."""
    folder = Path(folder)
    if _FOLDERS.get(prefix, folder) != folder:
        raise ValueError(f"the schema prefix {prefix!r} is registered for {_FOLDERS[prefix]}")
    _FOLDERS[prefix] = folder
    (_NOT_DEFAULT.discard if default else _NOT_DEFAULT.add)(prefix)
    validator.cache_clear()


def prefixes():
    return list(_FOLDERS)


@functools.cache
def validator(kind, prefix=None):
    import jsonschema
    from referencing import Registry, Resource

    if not _FOLDERS:
        raise SchemaError("no schema folder is registered (a kind registers its folder when it is imported)")
    prefix = prefix or next((p for p in _FOLDERS if p not in _NOT_DEFAULT), next(iter(_FOLDERS)))
    resources = []
    for folder in _FOLDERS.values():
        for f in sorted(folder.glob("*.schema.yaml")):
            s = yaml.safe_load(f.read_text())
            resources.append((s["$id"], Resource.from_contents(s)))
    registry = Registry().with_resources(resources)
    schema = dict(registry.contents(f"{prefix}/{kind}.schema.yaml"))
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


def problems(kind, data, prefix=None):
    v = validator(kind, prefix)
    errs = sorted(v.iter_errors(plain(data)), key=lambda e: [str(p) for p in e.absolute_path])
    return [f"{where(e)}: {text(e)}" for e in errs]


def check(kind, data, file, prefix=None):
    p = problems(kind, data, prefix)
    if p:
        more = f" (and {len(p) - 1} more; 'study.py design lint' lists all)" if len(p) > 1 else ""
        raise SchemaError(f"{file}: {p[0]}{more}")
    return data
