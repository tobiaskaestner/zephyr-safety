# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

cmake_minimum_required(VERSION 3.20.0)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(latbench_irqmask_unit)

# Only the site table of M4 (no hooks, no DWT), so that the test runs on
# native_sim and on any Zephyr tree.
set(LATBENCH_COMMON ${CMAKE_CURRENT_SOURCE_DIR}/../../common)
target_include_directories(app PRIVATE ${LATBENCH_COMMON}/include)
target_sources(app PRIVATE
  src/main.c
  ${LATBENCH_COMMON}/src/irqmask_table.c
)
