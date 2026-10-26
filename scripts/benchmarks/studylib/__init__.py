# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Study designs, result instances and their aggregates (see study.py).

Modules:
    layout    names and folders (prefixes ex- and st-), the results tree
    seal      the seal of a raw run folder (<UTC>.sha256 beside it)
    design    the design tree below validation/empirical/latencies
    instance  instance.json: run lists, roles, references, imports
    runfiles  run.json (framework data) and the app data of a run
    stats     values of a histogram, of M4 sites and of META
    checks    the comparison forms of hypotheses and acceptance checks
    central   the central results of a study
    build     the aggregates of a results tree
    jsonout   deterministic JSON output
"""
