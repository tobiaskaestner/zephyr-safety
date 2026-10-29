/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Data of kernel/init.c that a unit under test reads.
 *
 * - _kernel: the kernel state. Without SMP, _current is
 *   _kernel.cpus[0].current (zephyr/kernel_structs.h). A test sets this
 *   pointer to a thread of the test to give the unit a current thread.
 *
 * - The log module "os" (LOG_MODULE_REGISTER(os) in kernel/init.c). A unit
 *   with LOG_MODULE_DECLARE(os, ...), for example kernel/mutex.c, refers
 *   to its constant data log_const_os.
 *
 * - z_idle_threads: the idle thread of each CPU. kernel/include/kthread.h
 *   declares it, and z_is_idle_thread_object() compares a thread with it.
 *   The kernel does not start, so no code initializes it. A test that needs
 *   an idle thread sets its fields and _kernel.cpus[0].idle_thread.
 *
 * Before each test, the rule sets _kernel and z_idle_threads to all zeros,
 * so _current is NULL. Link the fake group init only if the unit under test is not
 * kernel/init.c.
 */

#include <string.h>
#include <zephyr/ztest.h>
#include <zephyr/kernel.h>
#include <zephyr/kernel_structs.h>
#include <zephyr/logging/log.h>

LOG_MODULE_REGISTER(os, CONFIG_KERNEL_LOG_LEVEL);

struct z_kernel _kernel;

#ifdef CONFIG_MULTITHREADING
struct k_thread z_idle_threads[CONFIG_MP_MAX_NUM_CPUS];
#endif

static void init_fakes_reset(const struct ztest_unit_test *test, void *fixture)
{
	ARG_UNUSED(test);
	ARG_UNUSED(fixture);

	memset(&_kernel, 0, sizeof(_kernel));
#ifdef CONFIG_MULTITHREADING
	memset(z_idle_threads, 0, sizeof(z_idle_threads));
#endif
}

ZTEST_RULE(init_fakes_reset, init_fakes_reset, NULL);
