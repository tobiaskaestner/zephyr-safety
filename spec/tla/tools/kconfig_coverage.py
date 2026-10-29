#!/usr/bin/env python3
# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Report the Kconfig coverage of the TLA+ model configurations.

The script reads:

- the ``@kconfig`` tags of ``lib/*.tla``, with the parser of the doc
  extension (``doc/_extensions/tla_extract.py``). A tag on a constant names
  the symbols that the constant models. A tag on a property names the
  symbols under which the property applies.
- ``mc/kconfig.txt``: for each symbol, its relevant values and the value of
  the library constant that gives each one (with an optional condition on
  a second constant), or a reason why no configuration checks a value.
- ``mc/expected.txt``: the model configurations that run. Only the models
  ``mc/MC*.tla`` count; the example tests (``*Test``) evaluate single states.
- ``mc/<Module>.tla`` and ``mc/<Module>_<config>.cfg``: the value of each
  library constant in each configuration. The script finds the constant by
  its name in the ``INSTANCE ... WITH`` substitutions of the model (or in a
  definition or constant of the model with the same name), and reads the
  value from the ``CONSTANTS`` section of the configuration.

It reports each symbol and value with the configurations that check it,
and each guarded property with the configurations that check it. A gap is
a value without a configuration and without a reason, a symbol without
lines in ``mc/kconfig.txt``, or a tagged property that no configuration
checks.

Exit status: 0 without a gap, 1 with a gap, 2 on a setup error.

Usage: kconfig_coverage.py [-v]   (-v lists all configurations)
"""

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

SPEC = Path(__file__).resolve().parent.parent
REPO = SPEC.parent.parent
sys.path.insert(0, str(REPO / "doc" / "_extensions"))

try:
    import tla_extract  # noqa: E402
except ImportError as err:  # pygments is missing
    sys.exit(f"kconfig_coverage: cannot import the doc extension parser: {err}\n"
             "Run the script with the Python of the doc build (it needs pygments).")

PROPERTY_KINDS = ("invariant", "action-property", "liveness", "probe")


def norm(text):
    """The text with one space between tokens, and no space inside brackets."""
    text = re.sub(r"\s+", " ", text.strip())
    return re.sub(r"\s*,\s*", ", ", text)


def library_tags():
    """The @kconfig tags of lib/*.tla.

    Returns (constants, properties): constants maps a symbol to the set of
    constant names, properties maps a symbol to a list of (module, name).
    """
    constants = defaultdict(set)
    properties = defaultdict(list)
    for path in sorted((SPEC / "lib").glob("*.tla")):
        module = tla_extract.parse_file(path)
        for unit in module.units:
            symbols = [s for v in unit.tags.get("kconfig", []) for s in re.split(r"[\s,]+", v) if s]
            if not symbols:
                continue
            if unit.kind == "constants":
                for symbol in symbols:
                    constants[symbol].update(unit.names)
            elif unit.kind == "definition":
                kind = (unit.tags.get("kind") or ["definition"])[0]
                for symbol in symbols:
                    properties[symbol].append((module.name, unit.name, kind))
    return constants, properties


def value_map():
    """mc/kconfig.txt: symbol -> list of (value, constant or None, TLA+ value or reason).

    A TLA+ value can have a condition: "<value> if <constant> <value>".
    """
    values = defaultdict(list)
    for no, line in enumerate((SPEC / "mc" / "kconfig.txt").read_text().splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = line.split(None, 3)
        if len(parts) < 4:
            sys.exit(f"kconfig_coverage: mc/kconfig.txt:{no}: four fields expected")
        symbol, value, constant, rest = parts
        values[symbol].append((value, None if constant == "-" else constant, rest.strip()))
    return values


def runs():
    """The (module, config) pairs of mc/expected.txt for the models MC*."""
    result = []
    for line in (SPEC / "mc" / "expected.txt").read_text().splitlines():
        fields = line.split()
        if len(fields) >= 3 and not fields[0].startswith("#") and fields[0].startswith("MC"):
            result.append((fields[0], fields[1]))
    return result


def split_top(text):
    """Split text at the commas that are not inside brackets."""
    parts, depth, cur, i = [], 0, "", 0
    while i < len(text):
        two = text[i:i + 2]
        if two in ("<<", ">>"):
            depth += 1 if two == "<<" else -1
            cur += two
            i += 2
            continue
        ch = text[i]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
        i += 1
    parts.append(cur)
    return parts


_MODEL_CACHE = {}


def model(module):
    """Substitutions, definitions and constants of mc/<module>.tla."""
    if module in _MODEL_CACHE:
        return _MODEL_CACHE[module]
    text = (SPEC / "mc" / f"{module}.tla").read_text()
    text = re.sub(r"\\\*[^\n]*", "", text)
    subst = {}
    for m in re.finditer(r"INSTANCE\s+\w+\s+WITH\s+(.*?)(?=\n\S|\Z)", text, re.S):
        for part in split_top(m.group(1)):
            if "<-" in part:
                name, expr = part.split("<-", 1)
                subst.setdefault(name.strip(), norm(expr))
    defs = {}
    for m in re.finditer(r"^(\w+)\s*==\s*(.*?)(?=\n\S|\Z)", text, re.M | re.S):
        defs[m.group(1)] = norm(m.group(2))
    consts = set()
    for m in re.finditer(r"^CONSTANTS?\s+(.*?)(?=\n\S|\Z)", text, re.M | re.S):
        consts.update(n.strip() for n in m.group(1).split(",") if n.strip())
    _MODEL_CACHE[module] = (subst, defs, consts)
    return _MODEL_CACHE[module]


def cfg(module, config):
    """The CONSTANTS assignments and the checked names of a configuration."""
    text = (SPEC / "mc" / f"{module}_{config}.cfg").read_text()
    text = re.sub(r"\\\*[^\n]*", "", text)
    assign, checked, section = {}, set(), None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        head = stripped.split()[0]
        if head in ("CONSTANT", "CONSTANTS", "INVARIANT", "INVARIANTS", "PROPERTY", "PROPERTIES",
                    "SPECIFICATION", "INIT", "NEXT", "SYMMETRY", "VIEW", "CHECK_DEADLOCK", "ALIAS"):
            section = head.rstrip("S")
            rest = stripped[len(head):].strip()
            if section in ("INVARIANT", "PROPERTIE", "PROPERTY") and rest:
                checked.update(rest.split())
            continue
        if section == "CONSTANT":
            m = re.match(r"(\w+)\s*(=|<-)\s*(.*)", stripped)
            if m:
                assign[m.group(1)] = norm(m.group(3))
        elif section in ("INVARIANT", "PROPERTIE", "PROPERTY"):
            checked.update(stripped.split())
    return assign, checked


def constant_value(module, config, constant):
    """The value of the library constant in the configuration, or None."""
    subst, defs, consts = model(module)
    assign, _ = cfg(module, config)
    if constant in subst:
        expr = subst[constant]
    elif constant in defs:
        expr = defs[constant]
    elif constant in consts:
        expr = constant
    else:
        return None
    for _ in range(3):  # resolve a model constant or a short chain of definitions
        if expr in assign:
            expr = assign[expr]
        elif re.fullmatch(r"\w+", expr) and expr in defs:
            expr = defs[expr]
        else:
            break
    return expr


def matches(module, config, constant, rest):
    """The configuration gives the constant the value of a kconfig.txt line."""
    want, _, cond = rest.partition(" if ")
    if constant_value(module, config, constant) != norm(want):
        return False
    if cond:
        cconst, _, cval = cond.strip().partition(" ")
        return constant_value(module, config, cconst) == norm(cval)
    return True


def checks_property(module, config, prop):
    """The configuration checks the library property prop (by an alias)."""
    _, defs, _ = model(module)
    _, checked = cfg(module, config)
    for name in checked:
        body = defs.get(name, "")
        if name == prop or re.fullmatch(rf"(\w+!)*{re.escape(prop)}", body):
            return True
    return False


def short(names, verbose):
    if verbose or len(names) <= 4:
        return ", ".join(names)
    return ", ".join(names[:4]) + f", ... ({len(names) - 4} more)"


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("-v", "--verbose", action="store_true", help="list all configurations")
    args = parser.parse_args()

    constants, properties = library_tags()
    values = value_map()
    model_runs = runs()
    gaps = 0

    print("Kconfig coverage of the model configurations")
    print(f"({len(model_runs)} model runs in mc/expected.txt)\n")

    symbols = sorted(set(constants) | set(properties))
    for symbol in symbols:
        consts = sorted(constants.get(symbol, ()))
        print(f"{symbol}  (constants: {', '.join(consts) or '-'})")
        if symbol not in values:
            print("  GAP: no line in mc/kconfig.txt")
            gaps += 1
        for value, constant, rest in values.get(symbol, []):
            if constant is None:
                print(f"  {value:10} reason: {rest}")
                continue
            hits = [f"{m} {c}" for m, c in model_runs if matches(m, c, constant, rest)]
            if hits:
                print(f"  {value:10} {constant} = {rest}: {len(hits)} run{"s" if len(hits) != 1 else ""}: {short(hits, args.verbose)}")
            else:
                print(f"  {value:10} {constant} = {rest}: GAP, no configuration and no reason")
                gaps += 1
        for module, name, kind in properties.get(symbol, []):
            hits = [f"{m} {c}" for m, c in model_runs if checks_property(m, c, name)]
            if not hits:
                print(f"  property {module}!{name} ({kind}): GAP, no configuration checks it")
                gaps += 1
                continue
            seen = defaultdict(list)
            for value, constant, rest in values.get(symbol, []):
                if constant is None:
                    continue
                for hit in hits:
                    m, c = hit.split()
                    if matches(m, c, constant, rest):
                        seen[value].append(hit)
            detail = "; ".join(f"{v}: {len(h)}" for v, h in seen.items()) or "no mapped value"
            print(f"  property {module}!{name} ({kind}): {len(hits)} runs ({detail})")
        print()

    for symbol in sorted(set(values) - set(symbols)):
        print(f"{symbol}: WARNING, lines in mc/kconfig.txt, but no @kconfig tag in lib/*.tla\n")

    print(f"Result: {gaps} gap(s)")
    return 1 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
