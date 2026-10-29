# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

cmake_minimum_required(VERSION 3.28.0)

find_package(Zephyr COMPONENTS unittest REQUIRED HINTS $ENV{ZEPHYR_BASE})

project(kernel_unit_scheduler)

include(${ZEPHYR_SAFETY_MODULE_DIR}/cmake/kernel_unit.cmake)

# The unit boundary of kernel/scheduler.c (unit map, contracts Scheduler and
# SchedApi). These kernel-internal headers are real: the run queue code of
# run_q.h and priority_q.h (z_sched_init()), the thread state of kthread.h,
# the scheduler lock of kspinlock.h, and ipi.h (run_q.h includes it). The
# other headers stay shadows: ksched.h and scheduler.h have the fakes of
# kernel/sched.c, and wait_q.h has fakes and a real copy of the walk macros.
kernel_unit_real_headers(kthread run_q priority_q kspinlock ipi)

# Below scheduler.c: kernel/sched.c (group sched: z_pend_curr(),
# z_sched_lock_reschedule() and more), the arch layer, the fatal errors and
# the data of init.c. The group scheduler is not linked: it fakes functions of
# scheduler.c.
kernel_unit_fakes(arch sched fatal init)
kernel_unit_fakes_ifdef(CONFIG_ASSERT assert)
kernel_unit_fakes_ifdef(CONFIG_SPIN_VALIDATE spinlock)

target_sources(testbinary PRIVATE src/test_scheduler.c)
