/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Shadow of kernel/include/ksched.h.
 *
 * Only the scheduler functions that a unit under test uses are here. Each
 * one is an FFF fake, also z_sched_wake() and z_unpend_first_thread_locked(),
 * which are static inline in the real header.
 *
 * Exception: the pure priority comparisons and the priority ceiling
 * (z_is_prio_higher(), z_get_new_prio_with_ceiling() and the functions
 * next to them) are REAL. They are a copy of the text of the real header,
 * without a change, between the markers KERNEL_UNIT_REAL_COPY_BEGIN and
 * KERNEL_UNIT_REAL_COPY_END. They only compute a result from their
 * arguments and CONFIG_PRIORITY_CEILING. Thus the tests check the priority
 * inheritance of a unit with the real priority semantics (user decision of
 * 2026-10-20). The drift guard (common/check_real_copies.py, called by
 * cmake/kernel_unit.cmake) stops the build if the copy is not the same as
 * the real header.
 */

#ifndef ZEPHYR_KERNEL_INCLUDE_KSCHED_H_
#define ZEPHYR_KERNEL_INCLUDE_KSCHED_H_

#include <errno.h>
#include <stdbool.h>
#include <zephyr/kernel_structs.h>
#include <zephyr/spinlock.h>
#include <zephyr/fff.h>
#include <kspinlock.h>
#include <kernel_internal.h>
#include <timeout_q.h>
#include <wait_q.h>

#ifdef __cplusplus
extern "C" {
#endif

#define KSCHED_FFF_FAKES_LIST(FAKE)                                                                \
	FAKE(z_pend_curr)                                                                          \
	FAKE(z_reschedule)                                                                         \
	FAKE(z_sched_wake)                                                                         \
	FAKE(z_sched_ready_locked)                                                                 \
	FAKE(z_unpend_first_thread_locked)                                                         \
	FAKE(z_thread_prio_set)

DECLARE_FAKE_VALUE_FUNC(int, z_pend_curr, struct k_spinlock *, k_spinlock_key_t, _wait_q_t *,
			k_timeout_t);
DECLARE_FAKE_VOID_FUNC(z_reschedule, struct k_spinlock *, k_spinlock_key_t);
DECLARE_FAKE_VALUE_FUNC(bool, z_sched_wake, _wait_q_t *, int, void *);
DECLARE_FAKE_VOID_FUNC(z_sched_ready_locked, struct k_thread *);
DECLARE_FAKE_VALUE_FUNC(struct k_thread *, z_unpend_first_thread_locked, _wait_q_t *);
DECLARE_FAKE_VALUE_FUNC(bool, z_thread_prio_set, struct k_thread *, int);

/*
 * ISR refusal of the fake z_pend_curr() (fake group sched).
 *
 * The real z_pend_curr() (kernel/sched.c) refuses a call from an ISR in
 * every build, before it does a side effect:
 *
 *   if (arch_is_in_isr()) {
 *           __ASSERT(false, "blocking pend from ISR context");
 *           k_panic();
 *   }
 *
 * The fake does the same, before its custom fake or its return value:
 *
 * 1. It records the call as each FFF fake does (arguments, call count,
 *    call history).
 * 2. It reads the context from the fake arch_is_in_isr() without a call.
 *    Thus the call count and the call history of arch_is_in_isr() show
 *    only the calls of the unit.
 * 3. In an ISR, it increments kernel_unit_pend_refusal.count. Then it does
 *    the assertion hook (with CONFIG_ASSERT) and the panic,
 *    z_fatal_error(K_ERR_KERNEL_PANIC, NULL). On the unit_testing
 *    architecture, k_panic() is this call. The fake does not call the
 *    custom fake, does not lock or release a lock, and does not change a
 *    wait queue or a thread.
 * 4. The fake z_fatal_error() returns. Then the fake z_pend_curr() returns
 *    KERNEL_UNIT_PEND_REFUSED, the result of a timeout. Each unit treats it
 *    as a wait that ended without a wake, so the unit then changes nothing
 *    that a timeout does not change. The real z_pend_curr() does not
 *    return.
 *
 * Guard: if a test did not call kernel_unit_expect_pend_refusal()
 * (kernel_unit_models.h) before the refusal, the fake fails the test. Thus
 * no unit continues after a panic of the scheduler without a test that
 * shows it.
 *
 * The group sched therefore needs the fake groups arch and fatal, and the
 * group assert with CONFIG_ASSERT.
 */

/** Return value of the fake z_pend_curr() after an ISR refusal (a timeout). */
#define KERNEL_UNIT_PEND_REFUSED (-EAGAIN)

/** State of the ISR refusal of the fake z_pend_curr(). The rule of the group resets it. */
struct kernel_unit_pend_refusal {
	/** True if the test expects a refusal. */
	bool expected;
	/** Number of calls of z_pend_curr() that the fake refused. */
	unsigned int count;
};

/** The state of the ISR refusal of the fake z_pend_curr(). */
extern struct kernel_unit_pend_refusal kernel_unit_pend_refusal;

/**
 * Return the value that the fake arch_is_in_isr() gives now, without a call.
 * Thus the call count and the call history of arch_is_in_isr() show only the
 * calls of the unit.
 */
bool kernel_unit_context_is_isr(void);

/* clang-format off */
/* KERNEL_UNIT_REAL_COPY_BEGIN kernel/include/ksched.h */
static inline bool z_is_under_prio_ceiling(int prio)
{
	return prio >= CONFIG_PRIORITY_CEILING;
}

static inline int z_get_new_prio_with_ceiling(int prio)
{
	return z_is_under_prio_ceiling(prio) ? prio : CONFIG_PRIORITY_CEILING;
}

static inline bool z_is_prio1_higher_than_or_equal_to_prio2(int prio1, int prio2)
{
	return prio1 <= prio2;
}

static inline bool z_is_prio_higher_or_equal(int prio1, int prio2)
{
	return z_is_prio1_higher_than_or_equal_to_prio2(prio1, prio2);
}

static inline bool z_is_prio1_lower_than_or_equal_to_prio2(int prio1, int prio2)
{
	return prio1 >= prio2;
}

static inline bool z_is_prio1_higher_than_prio2(int prio1, int prio2)
{
	return prio1 < prio2;
}

static inline bool z_is_prio_higher(int prio, int test_prio)
{
	return z_is_prio1_higher_than_prio2(prio, test_prio);
}

static inline bool z_is_prio_lower_or_equal(int prio1, int prio2)
{
	return z_is_prio1_lower_than_or_equal_to_prio2(prio1, prio2);
}
/* KERNEL_UNIT_REAL_COPY_END */
/* clang-format on */

#ifdef __cplusplus
}
#endif

#endif /* ZEPHYR_KERNEL_INCLUDE_KSCHED_H_ */
