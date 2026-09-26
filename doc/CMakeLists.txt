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
# Documents

set(DOC_REGISTRY ${CMAKE_CURRENT_LIST_DIR}/documents.yaml)

add_docs_from_registry(REGISTRY ${DOC_REGISTRY})
add_doc_check(REGISTRY ${DOC_REGISTRY})

add_custom_target(
  pristine
  COMMAND ${CMAKE_COMMAND} -P ${ZEPHYR_BASE}/cmake/pristine.cmake
)
