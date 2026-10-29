# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

cmake_minimum_required(VERSION 3.28.0)

find_package(Zephyr COMPONENTS unittest REQUIRED HINTS $ENV{ZEPHYR_BASE})

project(kernel_unit_sched)

include(${ZEPHYR_SAFETY_MODULE_DIR}/cmake/kernel_unit.cmake)

# The unit boundary of kernel/sched.c (unit map, contract Scheduler). These
# kernel-internal headers are real. The other headers stay shadows:
# kernel_arch_interface.h and kernel_arch_func.h (the arch fakes).
kernel_unit_real_headers(
  kswap ksched kthread metairq run_q priority_q wait_q kspinlock scheduler
  kernel_internal timeout_q timeslicing ipi usage
)

# Below sched.c: the arch layer with the platform model, timeout.c,
# timeslicing.c and thread.c. The groups sched and sched_ref are not linked:
# they fake functions of sched.c.
kernel_unit_fakes(arch fatal init timeout timeslicing thread platform)
kernel_unit_fakes_ifdef(CONFIG_ASSERT assert)
kernel_unit_fakes_ifdef(CONFIG_SPIN_VALIDATE spinlock)

target_sources(testbinary PRIVATE
  src/test_sched.c
  ${KERNEL_UNIT_COMMON_DIR}/src/test_sched_contract.c
)
