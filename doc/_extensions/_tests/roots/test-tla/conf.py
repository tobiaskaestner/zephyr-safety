# Test project of tla_domain. conftest.py puts doc/_extensions on sys.path.

project = "tla_domain test"
extensions = ["sphinx_needs", "tla_domain"]
exclude_patterns = ["_build"]

tla_spec_paths = ["spec"]
tla_source_root = "."

# The need type and the link of the model properties, as proposed for
# doc/needs_config.toml (see doc/_extensions/README.rst).
needs_id_regex = "^[A-Za-z][A-Za-z0-9_-]+"
needs_build_json = True
needs_reproducible_json = True
needs_types = [
    {"directive": "req", "title": "Requirement", "prefix": "REQ_", "color": "#FDEBD0", "style": "node"},
    {"directive": "prop", "title": "Model Property", "prefix": "PROP_", "color": "#E8F4E4", "style": "node"},
]
needs_links = {
    "expresses": {
        "description": "Model property expresses a requirement",
        "incoming": "Expressed by",
        "outgoing": "Expresses",
    },
}
needs_fields = {
    name: {"description": text, "nullable": True, "schema": {"type": "string"}}
    for name, text in {
        "kind": "Kind of a model property (invariant / action / liveness / probe)",
        "expected": "Expected TLC result of a model property (hold / violation)",
        "tla_module": "TLA+ module of a model property",
        "source_file": "Source file of the need",
        "source_line": "Line of the need in its source file",
        "c_function": "C functions that a TLA+ action models, joined with '; '",
    }.items()
}
