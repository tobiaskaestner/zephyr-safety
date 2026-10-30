/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <zephyr/ztest.h>
#include <ksched.h>
#include <scheduler.h>
#include <timeout_q.h>
#include <wait_q.h>
#include <kspinlock.h>
#include <kernel_arch_interface.h>
#include <zephyr/sys/__assert.h>
#include <zephyr/sys/util.h>
#include <fakes/fatal.h>
#include <kernel_unit_trace.h>

/*
 * Data of kernel/sched.c: the scheduler spinlock. A unit locks it with
 * LOCK_SCHED_SPINLOCK (shadow kspinlock.h) if CONFIG_MP_MAX_NUM_CPUS > 1.
 */
struct k_spinlock _sched_spinlock;

/*
 * See the ISR refusal in the shadow ksched.h. The refusal is here, in the fake
 * itself, so that each custom fake of z_pend_curr() (the models of
 * kernel_unit_models.h and of the test sources) gets it without a copy.
 */
struct kernel_unit_pend_refusal kernel_unit_pend_refusal;

/*
 * Return the value that a call of the fake arch_is_in_isr() gives now, but
 * do not call it. The order is the order of FFF: custom fake sequence,
 * custom fake, return value sequence, return value. The reference fake
 * (fake group sched_ref) also reads the context with this function.
 */
bool kernel_unit_context_is_isr(void)
{
	const arch_is_in_isr_Fake *isr = &arch_is_in_isr_fake;

	if (isr->custom_fake_seq_len > 0) {
		int i = MIN(isr->custom_fake_seq_idx, isr->custom_fake_seq_len - 1);

		return isr->custom_fake_seq[i]();
	}
	if (isr->custom_fake != NULL) {
		return isr->custom_fake();
	}
	if (isr->return_val_seq_len > 0) {
		int i = MIN(isr->return_val_seq_idx, isr->return_val_seq_len - 1);

		return isr->return_val_seq[i];
	}

	return isr->return_val;
}

/*
 * The ISR refusal of the real z_pend_curr() (kernel/sched.c). Return true if
 * the call is refused.
 */
static bool pend_refused_in_isr(void)
{
	if (!kernel_unit_context_is_isr()) {
		return false;
	}

	kernel_unit_pend_refusal.count++;
	if (!kernel_unit_pend_refusal.expected) {
		TC_PRINT("z_pend_curr() from an ISR: the real scheduler panics here. "
			 "The test does not expect it (kernel_unit_expect_pend_refusal()).\n");
		ztest_test_fail();
	}

	__ASSERT(false, "blocking pend from ISR context");
	/* k_panic() without CODE_UNREACHABLE: the fake z_fatal_error() returns. */
	z_fatal_error(K_ERR_KERNEL_PANIC, NULL);

	return true;
}

/*
 * The fake z_pend_curr(). It is DEFINE_FAKE_VALUE_FUNC() of FFF with one
 * addition: the ISR refusal comes after the record of the call and before
 * the custom fake and the return value.
 */
z_pend_curr_Fake z_pend_curr_fake;

int z_pend_curr(struct k_spinlock *arg0, k_spinlock_key_t arg1, _wait_q_t *arg2,
		k_timeout_t arg3)
{
	int ret;

	SAVE_ARG(z_pend_curr, 0);
	SAVE_ARG(z_pend_curr, 1);
	SAVE_ARG(z_pend_curr, 2);
	SAVE_ARG(z_pend_curr, 3);
	if (ROOM_FOR_MORE_HISTORY(z_pend_curr)) {
		SAVE_ARG_HISTORY(z_pend_curr, 0);
		SAVE_ARG_HISTORY(z_pend_curr, 1);
		SAVE_ARG_HISTORY(z_pend_curr, 2);
		SAVE_ARG_HISTORY(z_pend_curr, 3);
	} else {
		HISTORY_DROPPED(z_pend_curr);
	}
	INCREMENT_CALL_COUNT(z_pend_curr);
	REGISTER_CALL(z_pend_curr);

	if (pend_refused_in_isr()) {
#ifdef CONFIG_KERNEL_UNIT_TRACE
		kernel_unit_trace_pend_refused();
#endif
		ret = KERNEL_UNIT_PEND_REFUSED;
		SAVE_RET_HISTORY(z_pend_curr, ret);
		return ret;
	}

	if (z_pend_curr_fake.custom_fake_seq_len > 0) {
		int i = MIN(z_pend_curr_fake.custom_fake_seq_idx,
			    z_pend_curr_fake.custom_fake_seq_len - 1);

		if (z_pend_curr_fake.custom_fake_seq_idx < z_pend_curr_fake.custom_fake_seq_len) {
			z_pend_curr_fake.custom_fake_seq_idx++;
		}
		ret = z_pend_curr_fake.custom_fake_seq[i](arg0, arg1, arg2, arg3);
	} else if (z_pend_curr_fake.custom_fake != NULL) {
		ret = z_pend_curr_fake.custom_fake(arg0, arg1, arg2, arg3);
	} else if (z_pend_curr_fake.return_val_seq_len > 0) {
		/* RETURN_FAKE_RESULT of FFF, with the value kept for the trace hook */
		if (z_pend_curr_fake.return_val_seq_idx < z_pend_curr_fake.return_val_seq_len) {
			ret = z_pend_curr_fake.return_val_seq[z_pend_curr_fake.return_val_seq_idx++];
		} else {
			ret = z_pend_curr_fake.return_val_seq[z_pend_curr_fake.return_val_seq_len - 1];
		}
	} else {
		ret = z_pend_curr_fake.return_val;
	}
	SAVE_RET_HISTORY(z_pend_curr, ret);
#ifdef CONFIG_KERNEL_UNIT_TRACE
	kernel_unit_trace_pend_return(ret);
#endif
	return ret;
}
DEFINE_RESET_FUNCTION(z_pend_curr)

DEFINE_FAKE_VOID_FUNC(z_reschedule, struct k_spinlock *, k_spinlock_key_t);
DEFINE_FAKE_VALUE_FUNC(bool, z_sched_wake, _wait_q_t *, int, void *);
DEFINE_FAKE_VOID_FUNC(z_sched_ready_locked, struct k_thread *);
DEFINE_FAKE_VALUE_FUNC(struct k_thread *, z_unpend_first_thread_locked, _wait_q_t *);
DEFINE_FAKE_VALUE_FUNC(bool, z_thread_prio_set, struct k_thread *, int);

/* z_sched_waitq_walk() and z_sched_wait() are in kernel/scheduler.c: fake group scheduler. */
DEFINE_FAKE_VOID_FUNC(z_sched_wake_thread_locked, struct k_thread *);
DEFINE_FAKE_VOID_FUNC(z_sched_lock_reschedule, k_spinlock_key_t);

DEFINE_FAKE_VALUE_FUNC(int, z_try_abort_thread_timeout, struct k_thread *);
DEFINE_FAKE_VALUE_FUNC(k_ticks_t, z_add_thread_timeout, struct k_thread *, k_timeout_t);

DEFINE_FAKE_VOID_FUNC(z_waitq_init, _wait_q_t *);
DEFINE_FAKE_VALUE_FUNC(struct k_thread *, z_waitq_head, _wait_q_t *);
DEFINE_FAKE_VALUE_FUNC(struct k_thread *, z_waitq_head_locked, _wait_q_t *);

static void sched_fakes_reset(const struct ztest_unit_test *test, void *fixture)
{
	ARG_UNUSED(test);
	ARG_UNUSED(fixture);

	KSCHED_FFF_FAKES_LIST(RESET_FAKE);
	SCHEDULER_FFF_FAKES_LIST(RESET_FAKE);
	TIMEOUT_Q_FFF_FAKES_LIST(RESET_FAKE);
	WAIT_Q_FFF_FAKES_LIST(RESET_FAKE);
	kernel_unit_pend_refusal = (struct kernel_unit_pend_refusal){0};
}

ZTEST_RULE(sched_fakes_reset, sched_fakes_reset, NULL);
