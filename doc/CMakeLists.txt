# SPDX-License-Identifier: Apache-2.0

cmake_minimum_required(VERSION 3.20.0)
project(Zephyr-Kernel-Doc LANGUAGES)

set(MIN_WEST_VERSION 1.0.0)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE} .. COMPONENTS doc)

file(TO_CMAKE_PATH "${ZEPHYR_BASE}" ZEPHYR_BASE)
message(STATUS "Zephyr base: ${ZEPHYR_BASE}")

file(TO_CMAKE_PATH "${CMAKE_CURRENT_LIST_DIR}" SAFETY_BASE)
message(STATUS "Safety base: ${SAFETY_BASE}")
#-------------------------------------------------------------------------------
# Options

set(SPHINXOPTS "-j auto -T" CACHE STRING "Default Sphinx Options")
set(SPHINXOPTS_EXTRA "" CACHE STRING "Extra Sphinx Options (added to defaults)")
set(LATEXMKOPTS "-pdf -halt-on-error -no-shell-escape" CACHE STRING "Default latexmk options")
set(DT_TURBO_MODE ON CACHE BOOL "Enable DT turbo mode")
set(HW_FEATURES_TURBO_MODE ON CACHE BOOL "Enable HW features turbo mode")
set(DOC_TAG "development" CACHE STRING "Documentation tag")

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
  message(STATUS "Created doc target: ${name} and ${name}-nodeps")
endfunction()

#
# Create Sphinx build targets for a given documentation set.
#
# add_sphinx_target(<doc_name>
#                   BUILDERS <b1> [<b2> ...]
#                   [TAGS <t1> [<t2> ...]])
#
function(add_sphinx_target doc_name)
  # Use the standard CMake module to parse keyword arguments
  cmake_parse_arguments(
    ARGS # prefix for output variables
    "" # list of options (boolean flags)
    "" # list of one-value keywords
    "BUILDERS;TAGS" # list of multi-value keywords
    ${ARGN}
  )

  if(NOT ARGS_BUILDERS)
    message(FATAL_ERROR "add_sphinx_target for '${doc_name}' requires a BUILDERS argument.")
  endif()

  # Per-documentation set paths
  set(DOC_OUT_DIR ${CMAKE_CURRENT_BINARY_DIR}/${doc_name})
  set(DOCS_CFG_DIR ${CMAKE_CURRENT_LIST_DIR}/${doc_name})
  set(DOCS_DOCTREE_DIR ${DOC_OUT_DIR}/doctrees)
  set(DOCS_BUILD_DIR ${DOC_OUT_DIR}/build)
  set(DOCS_SRC_DIR ${DOC_OUT_DIR}/src) # Generated sources

  # SPHINX TAGS: Combine global tags with function-specific tags
  set(SPHINX_TAGS "${DOC_TAG}")
  if(HW_FEATURES_TURBO_MODE)
    list(APPEND SPHINX_TAGS "hw_features_turbo")
  endif()
  list(APPEND SPHINX_TAGS ${ARGS_TAGS})

  set(SPHINX_TAGS_ARGS "")
  foreach(tag ${SPHINX_TAGS})
    list(APPEND SPHINX_TAGS_ARGS "-t" "${tag}")
  endforeach()

  # Create a target for each requested builder
  foreach(builder ${ARGS_BUILDERS})
    set(target_name "${doc_name}-${builder}")
    set(builder_out_dir "${CMAKE_CURRENT_BINARY_DIR}/deploy/${doc_name}/${builder}")
    set(extra_commands "")
    set(sphinx_executable ${SPHINXBUILD})
    set(extra_sphinx_args "")

    if(builder STREQUAL "html")
      set(builder_arg "html")
    elseif(builder STREQUAL "html-live")
      if(NOT SPHINXAUTOBUILD)
        message(WARNING "sphinx-autobuild not found, skipping '${target_name}' target.")
        continue()
      endif()
      set(sphinx_executable ${SPHINXAUTOBUILD})
      set(builder_arg "html")
      set(extra_sphinx_args --watch ${DOCS_CFG_DIR} --ignore ${DOCS_BUILD_DIR})
      set(target_name "${doc_name}-html-live")
    elseif(builder STREQUAL "linkcheck")
      set(builder_arg "linkcheck")
    elseif(builder STREQUAL "latex")
      set(builder_arg "latex")
      set(LATEXMKOPTS "-pdf")
      set(extra_commands
          COMMAND ${CMAKE_COMMAND} -E chdir ${builder_out_dir}
                  latexmk ${LATEXMKOPTS} ${doc_name}.tex
          COMMENT "Running latexmk to build PDF..."
        )
    else()
      # Generic builder
      set(builder_arg ${builder})
    endif()

    add_doc_target(
      ${target_name}
      COMMAND ${CMAKE_COMMAND} -E make_directory ${DOCS_SRC_DIR}
      COMMAND ${CMAKE_COMMAND} -E env ${SPHINX_ENV} OUTPUT_DIR=${builder_out_dir} LATEX_DOC=${doc_name}.tex
      ${sphinx_executable}
      -b ${builder_arg}
      -c ${DOCS_CFG_DIR}
      -d ${DOCS_DOCTREE_DIR}
      -w ${DOCS_BUILD_DIR}/${builder}.log
      ${SPHINX_TAGS_ARGS}
      ${extra_sphinx_args}
      ${SPHINXOPTS}
      ${SPHINXOPTS_EXTRA}
      ${DOCS_SRC_DIR}
      ${builder_out_dir}
      ${extra_commands}
      USES_TERMINAL
      COMMENT "Running Sphinx ${builder} build for ${doc_name}..."
    )

    set_target_properties(
      ${target_name} ${target_name}-nodeps
      PROPERTIES
      ADDITIONAL_CLEAN_FILES "${DOCS_SRC_DIR};${builder_out_dir};${DOCS_DOCTREE_DIR}"
    )

  endforeach()
endfunction()


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

  add_doc_target(
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

add_custom_target(
  pristine
  COMMAND ${CMAKE_COMMAND} -P ${ZEPHYR_BASE}/cmake/pristine.cmake
)

add_sphinx_target(
  safety-committee
  BUILDERS html latex
  TAGS draft
)

add_sphinx_target(
  requirements
  BUILDERS html latex
  TAGS draft
)

add_sphinx_target(
  architecture
  BUILDERS html latex
  TAGS draft
)

add_sphinx_target(
  api-documentation
  BUILDERS html html-live latex
  TAGS draft
)

add_doxygen_target(zephyr)
add_doxygen_target(zephyr-safety-api)
add_doxygen_target(zephyr-safety-detailed-design)
add_doxygen_target(zephyr-safety-testspec)