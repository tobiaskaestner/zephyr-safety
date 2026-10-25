# Benchmark Guide — zdocs conf.py shim.
#
# A plain Sphinx document: no sphinx-needs content of its own, no Doxygen
# input. The engine still loads its standard extensions (see zdocs_conf).
import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ["ZDOCS_CONF_DIR"])

from zdocs_conf import configure

# timeline_viz is a downstream extension (see _extensions/README.rst): appended
# after zdocs_conf, never before, so it cannot shadow an engine module.
sys.path.append(os.environ["SAFETY_EXTENSIONS_DIR"])

configure(
    globals(),
    doc_dir=Path(__file__).resolve().parent,
    project="Zephyr Latency Benchmark Guide",
    author="Zephyr Project Contributors",
    copyright_holder="Zephyr Project Contributors",
    extensions=["timeline_viz"],
)

# All timing diagrams of the guide get the same width, so they have the
# same scale. It is the width of the widest diagram (thread-latency-preempt).
timeline_viz_width = 1032
