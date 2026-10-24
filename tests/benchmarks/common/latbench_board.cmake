# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

# Selects the board port. An app includes this file BEFORE
# find_package(Zephyr), because the port adds devicetree overlays. The
# port folder is common/boards/<board>, where <board> is BOARD without
# qualifiers and revision (nrf54l15dk/nrf54l15/cpuapp -> nrf54l15dk).
#
# Set LATBENCH_RESP_IRQ_OWN before the include if the app connects the
# interrupt of the response pin itself (not through the GPIO driver).

if(NOT BOARD)
  message(FATAL_ERROR "latbench: set BOARD on the command line (-DBOARD=...)")
endif()
string(REGEX REPLACE "[@/].*" "" LATBENCH_BOARD "${BOARD}")
set(LATBENCH_PORT_DIR ${CMAKE_CURRENT_LIST_DIR}/boards/${LATBENCH_BOARD})
if(NOT EXISTS ${LATBENCH_PORT_DIR}/port.cmake)
  message(FATAL_ERROR "latbench: no board port for ${LATBENCH_BOARD} (${LATBENCH_PORT_DIR})")
endif()
include(${LATBENCH_PORT_DIR}/port.cmake)
