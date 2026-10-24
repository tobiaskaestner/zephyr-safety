# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

# Board port nrf54l15dk: TIMER00 compare -> DPPI (through a PPIB bridge)
# -> GPIOTE20 SET task drives P1.11. The response pin is P1.12, on
# GPIOTE20. The code is in common/boards/nordic. Included by
# common/latbench_board.cmake before find_package(Zephyr).

list(APPEND EXTRA_DTC_OVERLAY_FILE ${CMAKE_CURRENT_LIST_DIR}/stim.overlay)
if(LATBENCH_RESP_IRQ_OWN)
  list(APPEND EXTRA_DTC_OVERLAY_FILE ${CMAKE_CURRENT_LIST_DIR}/resp_irq_own.overlay)
endif()
list(APPEND EXTRA_CONF_FILE ${CMAKE_CURRENT_LIST_DIR}/port.conf)
