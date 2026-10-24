# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

# Adds the common latency benchmark code to the app target.

target_include_directories(app PRIVATE ${CMAKE_CURRENT_LIST_DIR}/include)
target_sources(app PRIVATE
  ${CMAKE_CURRENT_LIST_DIR}/src/hist.c
  ${CMAKE_CURRENT_LIST_DIR}/src/meta.c
)

# Put the rev of the benchmark sources into the output, so that each log
# names the code that produced it. run.py passes LATBENCH_SRC_REV, because
# it builds from a snapshot without .git. A manual build asks git; a dirty
# tree gets "-dirty".
if(NOT DEFINED LATBENCH_SRC_REV)
  execute_process(
    COMMAND git describe --always --abbrev=12 --dirty
    WORKING_DIRECTORY ${CMAKE_CURRENT_LIST_DIR}
    OUTPUT_VARIABLE LATBENCH_SRC_REV
    OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_QUIET
  )
endif()
if(NOT LATBENCH_SRC_REV)
  set(LATBENCH_SRC_REV unknown)
endif()
target_compile_definitions(app PRIVATE LATBENCH_SRC_REV="${LATBENCH_SRC_REV}")

# The TIM2 stimulus (common/src/stim.c) needs the zephyr,user node of the
# app overlay. An app that uses it sets LATBENCH_STIM before the include.
if(LATBENCH_STIM)
  target_sources(app PRIVATE
    ${CMAKE_CURRENT_LIST_DIR}/src/stim.c
    # The load timers take their tick phase from the stimulus.
    ${CMAKE_CURRENT_LIST_DIR}/src/load.c
  )
endif()
