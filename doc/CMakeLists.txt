# SPDX-License-Identifier: Apache-2.0

cmake_minimum_required(VERSION 3.20.0)
project(Zephyr-Kernel-Doc LANGUAGES)

set(MIN_WEST_VERSION 1.0.0)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE} .. COMPONENTS doc)

file(TO_CMAKE_PATH "${ZEPHYR_BASE}" ZEPHYR_BASE)
message(STATUS "Zephyr base: ${ZEPHYR_BASE}")

#-------------------------------------------------------------------------------
# Options

set(SPHINXOPTS "-j auto -W --keep-going -T" CACHE STRING "Default Sphinx Options")
set(SPHINXOPTS_EXTRA "" CACHE STRING "Extra Sphinx Options (added to defaults)")
set(LATEXMKOPTS "-halt-on-error -no-shell-escape" CACHE STRING "Default latexmk options")
set(DT_TURBO_MODE ON CACHE BOOL "Enable DT turbo mode")
set(HW_FEATURES_TURBO_MODE ON CACHE BOOL "Enable HW features turbo mode")
set(DOC_TAG "development" CACHE STRING "Documentation tag")
#set(DTS_ROOTS "${ZEPHYR_BASE}" CACHE STRING "DT bindings root folders")

separate_arguments(SPHINXOPTS)
separate_arguments(SPHINXOPTS_EXTRA)
separate_arguments(LATEXMKOPTS)

#-------------------------------------------------------------------------------
# Dependencies

find_package(Doxygen REQUIRED dot)

find_program(SPHINXBUILD sphinx-build)
if(NOT SPHINXBUILD)
  message(FATAL_ERROR "The 'sphinx-build' command was not found")
endif()
find_program(SPHINXAUTOBUILD sphinx-autobuild)

#-------------------------------------------------------------------------------
# Environment & Paths

set(SPHINX_ENV
  DOXYGEN_EXECUTABLE=${DOXYGEN_EXECUTABLE}
  DOT_EXECUTABLE=${DOXYGEN_DOT_EXECUTABLE}
)

if(WIN32)
set(SEP $<SEMICOLON>)
else()
set(SEP :)
endif()


#-------------------------------------------------------------------------------
# Functions

# Create a custom doc target.
#
# This function has the same signature as `add_custom_target()`
#
# The function will create two targets for the doc build system.
# - Target 1 named: `<name>`
# - Target 2 named: `<name>-nodeps`
#
# Both targets will produce same result, but target 2 must have no dependencies.
# This is useful to, e.g. re-run the Sphinx build without dependencies such as
# devicetree generator.
#
function(add_doc_target name)
add_custom_target(${name} ${ARGN})
add_custom_target(${name}-nodeps ${ARGN})
endfunction()


#-------------------------------------------------------------------------------
# html
set(DOC_SET requirements)
set(DOC_OUT_DIR ${CMAKE_CURRENT_BINARY_DIR}/${DOC_SET})
set(DOCS_CFG_DIR ${CMAKE_CURRENT_LIST_DIR}/${DOC_SET})
set(DOCS_DOCTREE_DIR ${DOC_OUT_DIR}/doctrees)
set(DOCS_BUILD_DIR ${DOC_OUT_DIR}/build)
set(DOCS_SRC_DIR ${DOC_OUT_DIR}/src)
set(DOCS_HTML_DIR ${CMAKE_CURRENT_BINARY_DIR}/deploy/${DOC_SET}/html)
set(DOCS_LINKCHECK_DIR ${DOC_OUT_DIR}/linkcheck)
set(DOCS_LATEX_DIR ${DOC_OUT_DIR}/latex)


#set(SPHINX_TAGS "${DOC_TAG}")
#if(HW_FEATURES_TURBO_MODE)
#  list(APPEND SPHINX_TAGS "hw_features_turbo")
#endif()

set(SPHINX_TAGS_ARGS "")
foreach(tag ${SPHINX_TAGS})
  list(APPEND SPHINX_TAGS_ARGS "-t" "${tag}")
endforeach()

add_doc_target(
  html
  COMMAND ${CMAKE_COMMAND} -E make_directory ${DOCS_SRC_DIR}
  COMMAND ${CMAKE_COMMAND} -E env ${SPHINX_ENV} OUTPUT_DIR=${DOCS_HTML_DIR}
  ${SPHINXBUILD}
  -b html
  -c ${DOCS_CFG_DIR}
  -d ${DOCS_DOCTREE_DIR}
  -w ${DOCS_BUILD_DIR}/html.log
  ${SPHINX_TAGS_ARGS}
  ${SPHINXOPTS}
  ${SPHINXOPTS_EXTRA}
  ${DOCS_SRC_DIR}
  ${DOCS_HTML_DIR}
  USES_TERMINAL
  COMMENT "Running Sphinx HTML build..."
)

set_target_properties(
  html html-nodeps
  PROPERTIES
  ADDITIONAL_CLEAN_FILES "${DOCS_SRC_DIR};${DOCS_HTML_DIR};${DOCS_DOCTREE_DIR}"
)


#-------------------------------------------------------------------------------
# html-live

add_doc_target(
  html-live
  COMMAND ${CMAKE_COMMAND} -E env ${SPHINX_ENV} OUTPUT_DIR=${DOCS_HTML_DIR}
  ${SPHINXAUTOBUILD}
  --watch ${DOCS_CFG_DIR}
  --ignore ${DOCS_BUILD_DIR}
  -b html
  -c ${DOCS_CFG_DIR}
  -d ${DOCS_DOCTREE_DIR}
  -w ${DOCS_BUILD_DIR}/html.log
  ${SPHINX_TAGS_ARGS}
  ${SPHINXOPTS}
  ${SPHINXOPTS_EXTRA}
  ${DOCS_SRC_DIR}
  ${DOCS_HTML_DIR}
  USES_TERMINAL
  COMMENT "Running Sphinx HTML autobuild..."
)

set_target_properties(
  html-live html-live-nodeps
  PROPERTIES
  ADDITIONAL_CLEAN_FILES "${DOCS_SRC_DIR};${DOCS_HTML_DIR};${DOCS_DOCTREE_DIR}"
)


#-------------------------------------------------------------------------------
# linkcheck

add_doc_target(
  linkcheck
  COMMAND ${CMAKE_COMMAND} -E env ${SPHINX_ENV} OUTPUT_DIR=${DOCS_LINKCHECK_DIR}
  ${SPHINXBUILD}
  -b linkcheck
  -c ${DOCS_CFG_DIR}
  -d ${DOCS_DOCTREE_DIR}
  -w ${DOCS_BUILD_DIR}/linkcheck.log
  ${SPHINX_TAGS_ARGS}
  ${SPHINXOPTS}
  ${SPHINXOPTS_EXTRA}
  ${DOCS_SRC_DIR}
  ${DOCS_LINKCHECK_DIR}
  USES_TERMINAL
  COMMENT "Running Sphinx link check..."
)

set_target_properties(
  linkcheck linkcheck-nodeps
  PROPERTIES
  ADDITIONAL_CLEAN_FILES "${DOCS_SRC_DIR};${DOCS_LINKCHECK_DIR};${DOCS_DOCTREE_DIR}"
)

add_custom_target(
  pristine
  COMMAND ${CMAKE_COMMAND} -P ${ZEPHYR_BASE}/cmake/pristine.cmake
)




#-------------------------------------------------------------------------------
# Doxygen (standalone)
function(add_doxygen_target name)
  set(DOXY_DOC ${name})
  set(DOXY_OUT ${CMAKE_CURRENT_BINARY_DIR}/deploy/doxygen-${DOXY_DOC})
  make_directory(${DOXY_OUT})

  set(DOXYFILE_IN ${CMAKE_CURRENT_LIST_DIR}/${DOXY_DOC}.doxyfile.in)
  set(DOXYFILE_OUT ${CMAKE_CURRENT_BINARY_DIR}/${DOXY_DOC}.doxyfile)
  set(DOC_BASE ${CMAKE_CURRENT_LIST_DIR})

  configure_file(${DOXYFILE_IN} ${DOXYFILE_OUT} @ONLY)

  add_custom_target(
    doxygen-${DOXY_DOC}
    COMMAND
    ${DOXYGEN_EXECUTABLE} ${DOXYFILE_OUT}
    COMMENT "Running Doxygen for ${DOXY_DOC}..."
  )

  set_target_properties(
    doxygen-${DOXY_DOC}
    PROPERTIES
    ADDITIONAL_CLEAN_FILES "${DOXY_OUT}"
  )
endfunction()

add_doxygen_target(zephyr)
add_doxygen_target(zephyr-safety-api)
add_doxygen_target(zephyr-safety-detailed-design)
