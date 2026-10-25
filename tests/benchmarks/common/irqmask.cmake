# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

# M4 (interrupt mask time per call site): adds common/src/irqmask.c if the
# Zephyr tree and the build have CONFIG_ARM_IRQ_MASK_HOOKS. Include this
# file after common/latbench.cmake. The app sources ../common/Kconfig.irqmask
# from its Kconfig.

if(CONFIG_ARM_IRQ_MASK_HOOKS)
  target_sources(app PRIVATE
    ${CMAKE_CURRENT_LIST_DIR}/src/irqmask.c
    ${CMAKE_CURRENT_LIST_DIR}/src/irqmask_table.c
  )
endif()
