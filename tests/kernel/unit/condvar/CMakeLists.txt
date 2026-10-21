# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

cmake_minimum_required(VERSION 3.28.0)

find_package(Zephyr COMPONENTS unittest REQUIRED HINTS $ENV{ZEPHYR_BASE})

project(kernel_unit_condvar)

include(${ZEPHYR_SAFETY_MODULE_DIR}/cmake/kernel_unit.cmake)

kernel_unit_fakes(arch sched fatal mutex init)
kernel_unit_fakes_ifdef(CONFIG_OBJ_CORE obj_core)
kernel_unit_fakes_ifdef(CONFIG_ASSERT assert)
kernel_unit_fakes_ifdef(CONFIG_SPIN_VALIDATE spinlock)
kernel_unit_fakes_ifdef(CONFIG_USERSPACE syscall_handler kobject)

target_sources(testbinary PRIVATE src/test_condvar.c)
