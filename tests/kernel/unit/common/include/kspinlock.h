/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Shadow of kernel/include/kspinlock.h.
 *
 * Only the macros that a unit under test uses are here. They are the same
 * as in the real header:
 *
 * - LOCK_SCHED_SPINLOCK: with one CPU (CONFIG_MP_MAX_NUM_CPUS == 1), it is
 *   empty, and the block that follows is a plain block. With more than one
 *   CPU, it locks the scheduler spinlock _sched_spinlock for the block, with
 *   K_SPINLOCK(). The calls of k_spin_lock() and k_spin_unlock() are then
 *   visible in a test as calls of unit_arch_irq_lock() and
 *   unit_arch_irq_unlock().
 * - Z_SCHED_SPINLOCK: locks _sched_spinlock for the block that follows, also
 *   with one CPU.
 *
 * _sched_spinlock is the data of kernel/sched.c. The fake group sched
 * defines it.
 */

#ifndef ZEPHYR_KERNEL_INCLUDE_KSPINLOCK_H_
#define ZEPHYR_KERNEL_INCLUDE_KSPINLOCK_H_

#include <stdbool.h>
#include <zephyr/spinlock.h>

#ifdef __cplusplus
extern "C" {
#endif

extern struct k_spinlock _sched_spinlock;

#if (CONFIG_MP_MAX_NUM_CPUS == 1)
#define LOCK_SCHED_SPINLOCK
#else
#define LOCK_SCHED_SPINLOCK K_SPINLOCK(&_sched_spinlock)
#endif

#define Z_SCHED_SPINLOCK K_SPINLOCK(&_sched_spinlock)

#ifdef __cplusplus
}
#endif

#endif /* ZEPHYR_KERNEL_INCLUDE_KSPINLOCK_H_ */
