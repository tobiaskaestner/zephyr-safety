#!/usr/bin/env python3
# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The data of a run of thread_latency as JSON on stdout (format latbench-app-thread_latency/1).

    extract.py RUN_DIR [--binutils PREFIX]

thread_latency prints the common LAT lines (common/scripts/latextract.py); it has
no lines of its own yet. A value that only this app gives goes here.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "common" / "scripts"))

import latextract  # noqa: E402

if __name__ == "__main__":
    latextract.main("thread_latency")
