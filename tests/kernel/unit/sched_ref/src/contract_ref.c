/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * The adapter of the contract tests (kernel_unit_sched_contract.h) on the
 * reference fake (kernel_unit_sched_ref.h). The contract tests are in
 * common/src/test_sched_contract.c. The application sched has the adapter on
 * the real kernel/sched.c.
 */

#include <zephyr/ztest.h>
#include <zephyr/spinlock.h>
#include <ksched.h>
#include <kernel_unit.h>
#include <kernel_unit_models.h>
#include <kernel_unit_sched_ref.h>
#include <kernel_unit_sched_contract.h>

/* The bits of the contract checks are the bits of the reference fake. */
#define SAME_BIT(name)                                                                             \
	BUILD_ASSERT((unsigned int)KERNEL_UNIT_CONTRACT_##name ==                                  \
		     (unsigned int)KERNEL_UNIT_SCHED_REF_##name)

SAME_BIT(CUR_IS_READY);
SAME_BIT(PENDING_IS_QUEUED);
SAME_BIT(ARMED_ARE_PENDING);
SAME_BIT(DEAD_IS_INERT);
SAME_BIT(RUN_RULE_HOLDS);
SAME_BIT(NO_LOST_THREAD);
SAME_BIT(MISUSE);
SAME_BIT(NO_RETURN);

/* The swap return value of a thread without a wait (NoRet of the contract). */
#define REF_NO_RET 1

/* The lock of the reschedule of k_thread_priority_set(). */
static struct k_spinlock prio_lock;

void kernel_unit_contract_setup(void)
{
	kernel_unit_sched_ref_install();
}

void kernel_unit_contract_thread(struct k_thread *thread, int prio)
{
	kernel_unit_sched_ref_thread(thread, prio);
}

void kernel_unit_contract_start(struct k_thread *thread)
{
	kernel_unit_sched_ref_set_current(thread);
}

void kernel_unit_contract_wait(struct k_thread *thread, _wait_q_t *wait_q, k_timeout_t timeout)
{
	kernel_unit_sched_ref_wait(thread, wait_q, timeout);
}

void kernel_unit_contract_env_thread(struct k_thread *thread, kernel_unit_contract_action_t action)
{
	kernel_unit_sched_ref_env_thread(thread, action);
}

void kernel_unit_contract_env_isr(kernel_unit_contract_action_t action)
{
	kernel_unit_sched_ref_env_isr(action);
}

void kernel_unit_contract_env_timeout(void)
{
	kernel_unit_sched_ref_env_timeout();
}

void kernel_unit_contract_env_abort(struct k_thread *thread)
{
	kernel_unit_sched_ref_env_abort(thread);
}

void kernel_unit_contract_run_isr(kernel_unit_contract_action_t action)
{
	kernel_unit_sched_ref_run_isr(action);
}

void kernel_unit_contract_timeout(void)
{
	kernel_unit_sched_ref_timeout();
}

void kernel_unit_contract_abort(struct k_thread *thread)
{
	kernel_unit_sched_ref_abort(thread);
}

/*
 * k_thread_priority_set(): z_thread_prio_set(), then a reschedule if the
 * thread is ready. The shadow ksched.h has no z_reschedule_unlocked(), so the
 * reschedule is z_reschedule() with a new lock (Release(a, "resched")).
 */
void kernel_unit_contract_set_prio(struct k_thread *thread, int prio)
{
	if (z_thread_prio_set(thread, prio)) {
		k_spinlock_key_t key = k_spin_lock(&prio_lock);

		z_reschedule(&prio_lock, key);
	}
}

/* The reference fake has no z_unpend_all(). */
int kernel_unit_contract_unpend_all(_wait_q_t *wait_q)
{
	ARG_UNUSED(wait_q);

	return -ENOSYS;
}

void kernel_unit_contract_expect_panic(void)
{
	kernel_unit_expect_pend_refusal();
}

struct k_thread *kernel_unit_contract_current(void)
{
	return _current;
}

struct k_thread *kernel_unit_contract_next(void)
{
	return kernel_unit_sched_ref_next();
}

int kernel_unit_contract_ret(struct k_thread *thread)
{
	struct kernel_unit_sched_ref_thread *t = kernel_unit_sched_ref_of(thread);

	if ((t == NULL) || !t->has_ret) {
		return REF_NO_RET;
	}

	return t->ret;
}

size_t kernel_unit_contract_waiters(_wait_q_t *wait_q, struct k_thread **out, size_t max)
{
	return kernel_unit_sched_ref_waiters(wait_q, out, max);
}

void kernel_unit_contract_expect(unsigned int checks)
{
	kernel_unit_sched_ref_expect(checks);
}

unsigned int kernel_unit_contract_found(void)
{
	return kernel_unit_sched_ref.found | kernel_unit_sched_ref_check();
}

void kernel_unit_contract_assert_ok(void)
{
	kernel_unit_sched_ref_assert_ok();
}
