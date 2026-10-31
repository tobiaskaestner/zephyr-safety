# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The kind "latbench": the latency benchmarks of the kernel (see study.py and run.py)."""

from pathlib import Path

from probatrix.core import schema

# The schema folder of this kind ($id prefix latbench). Importing the package registers it.
schema.register("latbench", Path(__file__).resolve().parent / "schemas")
