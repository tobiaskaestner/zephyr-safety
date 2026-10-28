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
    # graphviz: the diagram of explanation/architecture.rst (the build host needs "dot").
    extensions=["timeline_viz", "sphinx.ext.graphviz"],
)

# All timing diagrams of the guide get the same width, so they have the
# same scale. It is the width of the widest diagram (thread-latency-preempt).
timeline_viz_width = 1032
graphviz_output_format = "svg"
# The diagrams of the apps (beside their code) include diagrams/apps.tdc.
timeline_viz_include_path = ["diagrams"]

# The pages of the apps and of the board ports are beside their code, as
# the samples and the boards of Zephyr: tests/benchmarks/<app>/doc/ and
# tests/benchmarks/common/boards/<board>/doc/. external_content copies them
# into the Sphinx source tree, below benchmarks/. zdocs loads
# zephyr.external_content when ZEPHYR_BASE is set; else the guide loads its
# copy of it (same config values, so never both).
_DOC_DIR = Path(__file__).resolve().parent
_TESTS = _DOC_DIR.parents[1] / "tests"
if "zephyr.external_content" not in extensions:
    extensions.append("external_content")
external_content_contents += [
    (_TESTS, "benchmarks/*/doc"),
    (_TESTS, "benchmarks/common/boards/*/doc"),
]


def setup(app):
    # external_content writes into the source tree and removes the files that
    # it did not copy: never build in the authored folder.
    if Path(app.srcdir).resolve() == _DOC_DIR:
        raise RuntimeError(
            "build the benchmark guide from a copy: "
            "sphinx-build -c doc/benchmark-guide <empty folder> <output folder> "
            "(zdocs does this)"
        )
