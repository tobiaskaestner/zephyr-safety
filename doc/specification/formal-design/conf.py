# Zephyr Kernel Formal Design Specification — zdocs conf.py shim.
#
# ZDOCS_CONF_DIR is exported into every sphinx-build by zdocs' sphinx.cmake and
# equals <engine>/sphinx. Deriving the engine root from it rather than from
# __file__ arithmetic is deliberate: external_content builds from a COPY of this
# directory, so relative paths out of the source tree do not survive.
import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ["ZDOCS_CONF_DIR"])

from zdocs_conf import configure, need_layout

# tla_domain is a downstream extension (see _extensions/README.rst): appended
# after zdocs_conf, never before, so it cannot shadow an engine module.
sys.path.append(os.environ["SAFETY_EXTENSIONS_DIR"])

configure(
    globals(),
    doc_dir=Path(__file__).resolve().parent,
    project="Zephyr Kernel Formal Design Specification",
    author="Zephyr Project Contributors",
    copyright_holder="Zephyr Project Contributors",
    extensions=[
        "tla_domain",
    ],
)

# The Safety Committee document is left out of a build without its sources
# (SAFETY_DOC_COMMITTEE in doc/CMakeLists.txt). The tag lets xref-test.rst
# link to it only when the registry has it.
if "committee" in intersphinx_mapping:
    tags.add("committee")

# The TLA+ spec library (formal-model.rst). The source_file field of a model
# property is relative to the safety repository, the repository of the spec.
tla_spec_dir = Path(os.environ["SAFETY_TLA_SPEC_DIR"])
tla_spec_paths = [str(tla_spec_dir / "lib")]
tla_source_root = str(tla_spec_dir.parents[1])

# The zdocs card for the model properties: the needtable of formal-model.rst
# shows their fields, so the card shows only the text and the links.
needs_layouts = {"zdocs_prop": need_layout(fields=[])}
needs_default_layout = "zdocs_prop"
