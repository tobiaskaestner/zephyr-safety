# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

# Board port mimxrt1060_evk: GPT2 compare channel 1 drives A3
# (GPIO_AD_B1_05), the response pin is D2 (GPIO1_IO11). The wire is the
# same D2 - A3 wire as on nucleo_g474re, but the edge goes from A3 to D2.
# Included by common/latbench_board.cmake before find_package(Zephyr).

list(APPEND EXTRA_DTC_OVERLAY_FILE ${CMAKE_CURRENT_LIST_DIR}/stim.overlay)
if(LATBENCH_RESP_IRQ_OWN)
  list(APPEND EXTRA_DTC_OVERLAY_FILE ${CMAKE_CURRENT_LIST_DIR}/resp_irq_own.overlay)
endif()
list(APPEND EXTRA_CONF_FILE ${CMAKE_CURRENT_LIST_DIR}/port.conf)
