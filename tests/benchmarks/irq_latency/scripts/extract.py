#!/usr/bin/env python3
# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The data of a run of irq_latency as JSON on stdout (format latbench-app-irq_latency/1).

    extract.py RUN_DIR [--binutils PREFIX]

irq_latency prints the common LAT lines (common/scripts/latextract.py); it has
no lines of its own yet. A value that only this app gives goes here.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "common" / "scripts"))

import latextract  # noqa: E402

if __name__ == "__main__":
    latextract.main("irq_latency")
