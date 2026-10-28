#!/usr/bin/env python3
# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The standard plots of an experiment of irq_latency (common/scripts/latplot.py).

    plot.py OUT_DIR RUN_ID=APP_JSON ...

The metric of the plots is irq. A plot that only this app needs goes here.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "common" / "scripts"))

import latplot  # noqa: E402

if __name__ == "__main__":
    latplot.main("irq_latency", ["irq"])
