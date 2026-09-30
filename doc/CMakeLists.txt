# Copyright (c) 2025 TiaC Systems
#
# SPDX-License-Identifier: Apache-2.0
#
# The Zephyr safety docset — a consumer of the zdocs documentation engine.
#
# Every document is declared once in documents.yaml; add_docs_from_registry()
# turns that into build targets. There is deliberately no per-document factory
# call here (zdocs ADR-0004): the kind, builders and source folder the factories
# need already live in the registry, and two sources of that truth is the defect
# this migration removed.

cmake_minimum_required(VERSION 3.20.0)
project(Zephyr-Safety-Doc LANGUAGES)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE} .. COMPONENTS doc)

if(NOT DEFINED ZEPHYR_ZDOCS_MODULE_DIR)
  message(
    FATAL_ERROR
    "zdocs module not found. It is declared in safety/west.yml at tools/zdocs — "
    "run `west update`, or point at a local checkout with:\n"
    "  -DEXTRA_ZEPHYR_MODULES=<path to zdocs>\n"
    "NOTE: EXTRA_ZEPHYR_MODULES, not EXTRA_MODULES — the latter is silently "
    "ignored by the Zephyr module system."
  )
endif()
message(STATUS "zdocs module: ${ZEPHYR_ZDOCS_MODULE_DIR}")

file(TO_CMAKE_PATH "${ZEPHYR_BASE}" ZEPHYR_BASE)
get_filename_component(SAFETY_BASE ${CMAKE_CURRENT_LIST_DIR}/.. ABSOLUTE)
message(STATUS "Zephyr base: ${ZEPHYR_BASE}")
message(STATUS "Safety base: ${SAFETY_BASE}")

execute_process(
  COMMAND west topdir
  OUTPUT_VARIABLE WEST_TOPDIR
  OUTPUT_STRIP_TRAILING_WHITESPACE
  RESULT_VARIABLE west_result
  ERROR_QUIET
)
if(NOT west_result EQUAL 0)
  message(FATAL_ERROR "not inside a west workspace (`west topdir` failed)")
endif()

#-------------------------------------------------------------------------------
# The ZDOCS_* consumer contract. Everything project-specific the engine needs,
# set before include(zdocs).
# See tools/zdocs/doc/manual/reference/consumer-contract.rst

# The consuming repository: its git tags date the documents, and its paths are
# stripped from Doxygen output so artifacts do not carry this host's layout.
set(ZDOCS_PROJECT_BASE ${SAFETY_BASE})

# Most documented sources live in the zephyr project, not under SAFETY_BASE —
# so the workspace root has to be stripped too.
set(ZDOCS_WEST_TOPDIR ${WEST_TOPDIR})

# So a rendered `#include <zephyr/kernel.h>` matches what the compiler sees.
# Not derived from any layout convention: the engine deliberately does not guess.
set(ZDOCS_DOXYGEN_INC_ROOTS ${ZEPHYR_BASE}/include)

# Need types, links and custom fields for the sphinx-needs documents. Project-
# scoped rather than per-document: every document imports every other's needs,
# so they all have to agree on what a need type means.
set(ZDOCS_NEEDS_CONFIG ${CMAKE_CURRENT_LIST_DIR}/needs_config.toml)

set(ZDOCS_PROJECT_LOGO ${ZEPHYR_BASE}/doc/_static/images/logo.svg)

list(APPEND CMAKE_MODULE_PATH ${ZEPHYR_ZDOCS_MODULE_DIR}/cmake)
include(zdocs)
message(STATUS "zdocs version: ${ZDOCS_VERSION}")

#-------------------------------------------------------------------------------
# Requirements, generated from the StrictDoc sources (doc/reqmgmt).
#
# StrictDoc exports JSON; Zephyr's own doc/_scripts/gen_requirements.py — run
# unchanged, from the zephyr tree — turns that into two things:
#   rst/generated/*.rst   `.. req::` needs, copied into the `requirements`
#                         document's sources by its conf.py
#   dox/requirements.dox  `\requirement` blocks, the INPUT of `dox-requirements`,
#                         whose tag file lets every other Doxygen document
#                         resolve `\verifies` / `\satisfies`
# Both consumers depend on this target (see below), so they never read a stale or
# missing export.

set(REQMGMT_DIR ${WEST_TOPDIR}/doc/reqmgmt)
set(REQ_GEN_DIR ${CMAKE_CURRENT_BINARY_DIR}/requirements-gen)
set(REQ_GEN_SCRIPT ${ZEPHYR_BASE}/doc/_scripts/gen_requirements.py)
# Read by the `requirements` conf.py and by dox/requirements/Doxyfile.in.
set(REQ_GEN_RST_DIR ${REQ_GEN_DIR}/rst)
set(REQ_GEN_DOX_DIR ${REQ_GEN_DIR}/dox)
list(APPEND ZDOCS_SPHINX_EXTRA_ENV SAFETY_REQ_GEN_RST_DIR=${REQ_GEN_RST_DIR})

find_program(STRICTDOC strictdoc REQUIRED)
file(GLOB_RECURSE REQ_SOURCES CONFIGURE_DEPENDS ${REQMGMT_DIR}/*.sdoc ${REQMGMT_DIR}/*.sgra)

add_custom_command(
  OUTPUT ${REQ_GEN_DOX_DIR}/requirements.dox
  COMMAND ${CMAKE_COMMAND} -E rm -rf ${REQ_GEN_DIR}/strictdoc
  COMMAND ${STRICTDOC} export ${REQMGMT_DIR} --formats json --output-dir ${REQ_GEN_DIR}/strictdoc
  COMMAND ${PYTHON_EXECUTABLE} ${REQ_GEN_SCRIPT}
    --json ${REQ_GEN_DIR}/strictdoc/json/index.json
    --rst-out ${REQ_GEN_RST_DIR}/generated
    --dox-out ${REQ_GEN_DOX_DIR}
  DEPENDS ${REQ_SOURCES} ${REQMGMT_DIR}/strictdoc_config.py ${REQ_GEN_SCRIPT}
  COMMENT "Generating requirements from StrictDoc (doc/reqmgmt)..."
)
add_custom_target(requirements-gen DEPENDS ${REQ_GEN_DOX_DIR}/requirements.dox)

#-------------------------------------------------------------------------------
# Test scope: the per-module test scaffolding, generated from test-scope.yaml.
#
# _scripts/testspec_scope.py reads the scope and the test sources and derives
#   TESTSPEC_INPUT        each module's src/ directory, the testspec Doxygen INPUT
#                         (configure time: it is part of the Doxyfile)
#   testspec-gen/dox      the area / module / suite groups `testmodule::` walks
#   testspec-gen/suites.json  the per-module groups of a suite name that more
#                         than one module uses; read by the testspec Doxygen
#                         input filter, which points those ZTESTs at them
#   testspec-gen/spec     the test-specification page tree   } copied in by
#   testspec-gen/report   the test-report page tree          } their conf.py
# Test ids are not generated here: _scripts/assign_testids.py writes them into
# the sources, once, and is run by hand (see its docstring).

set(TESTSPEC_SCOPE ${CMAKE_CURRENT_LIST_DIR}/test-scope.yaml)
set(TESTSPEC_SCOPE_SCRIPT ${CMAKE_CURRENT_LIST_DIR}/_scripts/testspec_scope.py)
set(TESTSPEC_GEN_DIR ${CMAKE_CURRENT_BINARY_DIR}/testspec-gen)
# Read by dox/zephyr-safety-testspec/Doxyfile.in.
set(TESTSPEC_GEN_DOX ${TESTSPEC_GEN_DIR}/dox/groups.dox)
set(TESTSPEC_GEN_SUITES ${TESTSPEC_GEN_DIR}/suites.json)
list(APPEND ZDOCS_SPHINX_EXTRA_ENV SAFETY_TESTSPEC_GEN_DIR=${TESTSPEC_GEN_DIR})
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS ${TESTSPEC_SCOPE} ${TESTSPEC_SCOPE_SCRIPT})

execute_process(
  COMMAND ${PYTHON_EXECUTABLE} ${TESTSPEC_SCOPE_SCRIPT}
    --scope ${TESTSPEC_SCOPE} --zephyr-base ${ZEPHYR_BASE} input
  OUTPUT_VARIABLE TESTSPEC_INPUT
  OUTPUT_STRIP_TRAILING_WHITESPACE
  RESULT_VARIABLE testspec_input_result
)
if(NOT testspec_input_result EQUAL 0)
  message(FATAL_ERROR "testspec_scope.py input failed for ${TESTSPEC_SCOPE}")
endif()

# Always runs — it is cheap, and a new ZTEST_SUITE in a source file must reach
# the groups without a reconfigure. Unchanged files are not rewritten, so
# Doxygen and Sphinx see no change when there is none.
add_custom_target(
  testspec-gen
  COMMAND ${PYTHON_EXECUTABLE} ${TESTSPEC_SCOPE_SCRIPT}
    --scope ${TESTSPEC_SCOPE} --zephyr-base ${ZEPHYR_BASE} generate
    --dox-out ${TESTSPEC_GEN_DOX}
    --spec-out ${TESTSPEC_GEN_DIR}/spec
    --report-out ${TESTSPEC_GEN_DIR}/report
    --suites-out ${TESTSPEC_GEN_SUITES}
  COMMENT "Generating test scope scaffolding (test-scope.yaml)..."
)

#-------------------------------------------------------------------------------
# Design layer, generated from the `.. design::` blocks in Zephyr's own docs.
#
# _scripts/design_gen.py scans ${ZEPHYR_BASE}/doc/kernel and writes one `design`
# need per block (link `fulfills` to the requirements it names) into
#   design-gen/rst/generated/design_elements.rst   copied into the
#                         `architecture` document by its conf.py
#   design-gen/manifest.json   the expected ids, read by design-check
# It fails on a `fulfills` target the StrictDoc export does not define, so it
# runs after requirements-gen. Always runs, like testspec-gen: the page links to
# the zephyr HEAD, which can move without any .rst changing; unchanged output is
# not rewritten.

set(DESIGN_GEN_SCRIPT ${CMAKE_CURRENT_LIST_DIR}/_scripts/design_gen.py)
set(DESIGN_GEN_DIR ${CMAKE_CURRENT_BINARY_DIR}/design-gen)
list(APPEND ZDOCS_SPHINX_EXTRA_ENV SAFETY_DESIGN_GEN_RST_DIR=${DESIGN_GEN_DIR}/rst)

add_custom_target(
  design-gen
  COMMAND ${PYTHON_EXECUTABLE} ${DESIGN_GEN_SCRIPT} generate
    --zephyr-base ${ZEPHYR_BASE}
    --requirements-json ${REQ_GEN_DIR}/strictdoc/json/index.json
    --rst-out ${DESIGN_GEN_DIR}/rst
    --manifest ${DESIGN_GEN_DIR}/manifest.json
  COMMENT "Generating design needs (zephyr doc/kernel)..."
)
add_dependencies(design-gen requirements-gen)

#-------------------------------------------------------------------------------
# Documents

set(DOC_REGISTRY ${CMAKE_CURRENT_LIST_DIR}/documents.yaml)

add_docs_from_registry(REGISTRY ${DOC_REGISTRY})
add_doc_check(REGISTRY ${DOC_REGISTRY})

# Stage 1 of each consumer is the first thing to read the generated files.
# dox-zephyr is a stand-alone reference (crossref: false) that imports no tag
# file, so it reads requirements.dox itself — as Zephyr's own doxyfile does —
# to resolve the `\satisfies` in the full API.
add_dependencies(requirements-index requirements-gen)
add_dependencies(dox-requirements-tag requirements-gen)
add_dependencies(dox-zephyr-tag requirements-gen)
add_dependencies(dox-zephyr-safety-testspec-tag testspec-gen)
add_dependencies(test-specification-index testspec-gen)
add_dependencies(test-report-index testspec-gen)
add_dependencies(architecture-index design-gen)

# Every ZTEST in scope must be in the built test specification. A test behind a
# conditional that the documentation build evaluates false, or in a group nothing
# walks, drops out without a warning; _scripts/testspec_check.py compares the
# ZTEST sites in the sources with the test cases in its needs.json. Like
# doc-check: a standalone `testspec-check` target that re-checks the existing
# deploy tree, and a POST_BUILD step of `all-docs` — after
# test-specification-html — so a full build fails on a missing test.
set(
  testspec_check_cmd
  ${PYTHON_EXECUTABLE} ${CMAKE_CURRENT_LIST_DIR}/_scripts/testspec_check.py
    --scope ${TESTSPEC_SCOPE} --zephyr-base ${ZEPHYR_BASE}
    --needs ${CMAKE_CURRENT_BINARY_DIR}/deploy/html/test-specification/needs.json
)
add_custom_target(
  testspec-check
  COMMAND ${testspec_check_cmd}
  COMMENT "Checking that every ZTEST in scope is in the test specification..."
  USES_TERMINAL
)
add_custom_command(
  TARGET all-docs
  POST_BUILD
  COMMAND ${testspec_check_cmd}
  COMMENT "Checking that every ZTEST in scope is in the test specification..."
  USES_TERMINAL
)

# Every design block yields exactly one `design` need, none dangles; also prints
# the gap-view numbers (requirements x design x verification).
set(
  design_check_cmd
  ${PYTHON_EXECUTABLE} ${DESIGN_GEN_SCRIPT} check
    --manifest ${DESIGN_GEN_DIR}/manifest.json
    --deploy ${CMAKE_CURRENT_BINARY_DIR}/deploy/html
)
add_custom_target(
  design-check
  COMMAND ${design_check_cmd}
  COMMENT "Checking the design needs against the design blocks..."
  USES_TERMINAL
)
add_custom_command(
  TARGET all-docs
  POST_BUILD
  COMMAND ${design_check_cmd}
  COMMENT "Checking the design needs against the design blocks..."
  USES_TERMINAL
)

# Every @satisfies in the documented sources must land on exactly one impl need.
# One on a symbol a Doxyfile excludes, a static a project does not extract or a
# comment Doxygen attaches to nothing drops out of the implementation layer
# without a warning; _scripts/satisfies_check.py compares the @satisfies sites in
# the INPUT of the two Doxygen projects the impl needs come from with their XML
# and the impl needs in the needs.json of the two documents that make them.
# Findings let through on purpose are in satisfies-accepted.yaml, each with its
# reason. A standalone `satisfies-check` target and a POST_BUILD step of
# `all-docs`, like testspec-check.
set(SATISFIES_DOXYGEN dox-zephyr-safety-api dox-zephyr-safety-detailed-design)
set(SATISFIES_NEEDS api-documentation architecture)
set(satisfies_check_cmd
  ${PYTHON_EXECUTABLE} ${CMAKE_CURRENT_LIST_DIR}/_scripts/satisfies_check.py
    --zephyr-base ${ZEPHYR_BASE}
    --accepted ${CMAKE_CURRENT_LIST_DIR}/satisfies-accepted.yaml
)
foreach(dox ${SATISFIES_DOXYGEN})
  list(APPEND satisfies_check_cmd --doxygen
    ${CMAKE_CURRENT_BINARY_DIR}/${dox}.doxyfile
    ${CMAKE_CURRENT_BINARY_DIR}/deploy/xml/${dox}
  )
endforeach()
foreach(doc ${SATISFIES_NEEDS})
  list(APPEND satisfies_check_cmd
    --needs ${CMAKE_CURRENT_BINARY_DIR}/deploy/html/${doc}/needs.json
  )
endforeach()
foreach(dir include kernel arch lib subsys)
  list(APPEND satisfies_check_cmd --unscanned ${ZEPHYR_BASE}/${dir})
endforeach()
add_custom_target(
  satisfies-check
  COMMAND ${satisfies_check_cmd}
  COMMENT "Checking that every @satisfies lands on one impl need..."
  USES_TERMINAL
)
add_custom_command(
  TARGET all-docs
  POST_BUILD
  COMMAND ${satisfies_check_cmd}
  COMMENT "Checking that every @satisfies lands on one impl need..."
  USES_TERMINAL
)

add_custom_target(
  pristine
  COMMAND ${CMAKE_COMMAND} -P ${ZEPHYR_BASE}/cmake/pristine.cmake
)
