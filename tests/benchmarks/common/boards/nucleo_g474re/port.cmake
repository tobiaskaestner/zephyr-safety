# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

# Board port nucleo_g474re: TIM2 channel 4 on D2 (PA10), response on A3
# (PB0, EXTI line 0). Included by common/latbench_board.cmake before
# find_package(Zephyr).

list(APPEND EXTRA_DTC_OVERLAY_FILE ${CMAKE_CURRENT_LIST_DIR}/stim.overlay)
if(LATBENCH_RESP_IRQ_OWN)
  list(APPEND EXTRA_DTC_OVERLAY_FILE ${CMAKE_CURRENT_LIST_DIR}/resp_irq_own.overlay)
endif()
list(APPEND EXTRA_CONF_FILE ${CMAKE_CURRENT_LIST_DIR}/port.conf)
