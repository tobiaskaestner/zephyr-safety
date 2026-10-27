# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

cmake_minimum_required(VERSION 3.28.0)

find_package(Zephyr COMPONENTS unittest REQUIRED HINTS $ENV{ZEPHYR_BASE})

project(kernel_unit_sched_ref)

include(${ZEPHYR_SAFETY_MODULE_DIR}/cmake/kernel_unit.cmake)

# The self-test of the reference fake includes no kernel source file. It
# calls the layer-A functions of the fake group sched directly.
kernel_unit_fakes(arch sched fatal init sched_ref)
kernel_unit_fakes_ifdef(CONFIG_ASSERT assert)
kernel_unit_fakes_ifdef(CONFIG_SPIN_VALIDATE spinlock)

target_sources(testbinary PRIVATE src/test_sched_ref.c)
