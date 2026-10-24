# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

cmake_minimum_required(VERSION 3.20.0)

# The stock path (the default) uses the GPIO driver. The other paths
# connect their own ISR, so the port must take the response interrupt
# away from the GPIO driver. This needs the path on the command line
# (-DCONFIG_LATBENCH_IRQ_PATH_...=y); main.c checks that both agree.
set(LATBENCH_RESP_IRQ_OWN_IF
  CONFIG_LATBENCH_IRQ_PATH_WRAPPED CONFIG_LATBENCH_IRQ_PATH_DIRECT CONFIG_LATBENCH_IRQ_PATH_ZLI)
include(${CMAKE_CURRENT_SOURCE_DIR}/../common/latbench_board.cmake)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(irq_latency)

set(LATBENCH_STIM ON)
include(${CMAKE_CURRENT_SOURCE_DIR}/../common/latbench.cmake)
target_sources(app PRIVATE src/main.c)
