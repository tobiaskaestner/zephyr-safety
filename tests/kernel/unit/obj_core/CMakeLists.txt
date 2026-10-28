# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

cmake_minimum_required(VERSION 3.28.0)

find_package(Zephyr COMPONENTS unittest REQUIRED HINTS $ENV{ZEPHYR_BASE})

project(kernel_unit_obj_core)

include(${ZEPHYR_SAFETY_MODULE_DIR}/cmake/kernel_unit.cmake)

# Do not link the groups obj_core and obj_core_stats: they fake the
# functions of kernel/obj_core.c, the unit under test.
#
# The second test source includes kernel/sem.c. It calls the real object
# core code, so it needs the groups of sem.c (arch, sched,
# kernel_internal). obj_core.c reads _kernel (group init). With
# CONFIG_OBJ_CORE_STATS_SYSTEM, obj_core.c refers to the statistics
# functions of kernel/usage.c (group usage).
kernel_unit_fakes(arch sched fatal kernel_internal init)
kernel_unit_fakes_ifdef(CONFIG_OBJ_CORE_STATS_SYSTEM usage)
kernel_unit_fakes_ifdef(CONFIG_ASSERT assert)
kernel_unit_fakes_ifdef(CONFIG_SPIN_VALIDATE spinlock)
kernel_unit_fakes_ifdef(CONFIG_USERSPACE syscall_handler kobject)

target_sources(testbinary PRIVATE src/test_obj_core.c src/test_obj_core_sem.c)
