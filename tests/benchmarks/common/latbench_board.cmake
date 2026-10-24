# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

# Selects the board port. An app includes this file BEFORE
# find_package(Zephyr), because the port adds devicetree overlays. The
# port folder is common/boards/<board>, where <board> is BOARD without
# qualifiers and revision (nrf54l15dk/nrf54l15/cpuapp -> nrf54l15dk).
#
# Set LATBENCH_RESP_IRQ_OWN before the include if the app connects the
# interrupt of the response pin itself (not through the GPIO driver). Or
# set LATBENCH_RESP_IRQ_OWN_IF to a list of Kconfig symbols (with the
# CONFIG_ prefix): if one of them is y on the cmake command line, the app
# owns the response IRQ.

# The value of a cache variable. A sysbuild image (for example from
# twister) gets the command line values only through the sysbuild cache,
# which find_package(Zephyr) reads later.
function(latbench_cache_get name out)
  set(value "${${name}}")
  if("${value}" STREQUAL "" AND SYSBUILD_CACHE)
    file(STRINGS "${SYSBUILD_CACHE}" line REGEX "^${name}:[A-Z]+=")
    string(REGEX REPLACE "^${name}:[A-Z]+=" "" value "${line}")
  endif()
  set(${out} "${value}" PARENT_SCOPE)
endfunction()

latbench_cache_get(BOARD LATBENCH_BOARD_TARGET)
if(NOT LATBENCH_BOARD_TARGET)
  message(FATAL_ERROR "latbench: set BOARD on the command line (-DBOARD=...)")
endif()
string(REGEX REPLACE "[@/].*" "" LATBENCH_BOARD "${LATBENCH_BOARD_TARGET}")
set(LATBENCH_PORT_DIR ${CMAKE_CURRENT_LIST_DIR}/boards/${LATBENCH_BOARD})
if(NOT EXISTS ${LATBENCH_PORT_DIR}/port.cmake)
  message(FATAL_ERROR "latbench: no board port for ${LATBENCH_BOARD} (${LATBENCH_PORT_DIR})")
endif()
foreach(sym ${LATBENCH_RESP_IRQ_OWN_IF})
  latbench_cache_get(${sym} value)
  if(value)
    set(LATBENCH_RESP_IRQ_OWN ON)
  endif()
endforeach()
include(${LATBENCH_PORT_DIR}/port.cmake)
