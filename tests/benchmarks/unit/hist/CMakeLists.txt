# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

cmake_minimum_required(VERSION 3.20.0)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(latbench_hist_unit)

# Only the histogram code. common/latbench.cmake also adds meta.c and asks
# git for the source rev, which this test does not need.
set(LATBENCH_COMMON ${CMAKE_CURRENT_SOURCE_DIR}/../../common)
target_include_directories(app PRIVATE ${LATBENCH_COMMON}/include)
target_sources(app PRIVATE
  src/main.c
  ${LATBENCH_COMMON}/src/hist.c
)
