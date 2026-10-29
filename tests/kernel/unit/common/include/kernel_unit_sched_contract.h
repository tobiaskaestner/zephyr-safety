/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @defgroup kernel_unit_sched_contract_adapter Adapter of the scheduler contract tests
 * @ingroup kernel_unit_models
 * @brief The setup and the queries that the contract tests need from a scheduler.
 *
 * The contract tests (@c common/src/test_sched_contract.c, suite
 * @c sched_contract) check layer A of @c safety/spec/tla/lib/Scheduler.tla.
 * The same tests run against two schedulers:
 *
 * - the reference fake (application @c sched_ref, adapter
 *   @c sched_ref/src/contract_ref.c),
 * - the real @c kernel/sched.c and @c kernel/scheduler.c on the platform
 *   model (application @c sched, adapter in @c sched/src/test_sched.c).
 *
 * The actions of the tests call the C functions of layer A directly
 * (z_pend_curr(), z_sched_wake(), z_reschedule(), z_thread_prio_set(),
 * z_waitq_head(), z_waitq_init(), and z_sched_waitq_walk() and
 * z_sched_wait() of @c kernel/scheduler.c). This adapter does only what the two
 * schedulers do in a different way: the setup of a state, the environment of a
 * wait, the calls of @c kernel/thread.c (abort, priority change) and the
 * queries of the state. A difference between the two schedulers is a failing
 * test.
 *
 * Priorities are Zephyr priorities: a lower number is a higher priority, a
 * negative number is a cooperative thread. NULL is the idle thread in each
 * query.
 *
 * @{
 */

#ifndef KERNEL_UNIT_SCHED_CONTRACT_H_
#define KERNEL_UNIT_SCHED_CONTRACT_H_

#include <stdbool.h>
#include <stddef.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/util.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * The checks of the contract. The bits are the bits of the reference fake
 * (enum kernel_unit_sched_ref_check).
 */
enum kernel_unit_contract_check {
	/** Invariant CurIsReady. */
	KERNEL_UNIT_CONTRACT_CUR_IS_READY = BIT(0),
	/** Invariant PendingIsQueued. */
	KERNEL_UNIT_CONTRACT_PENDING_IS_QUEUED = BIT(1),
	/** Invariant ArmedArePending. */
	KERNEL_UNIT_CONTRACT_ARMED_ARE_PENDING = BIT(2),
	/** Invariant DeadIsInert. */
	KERNEL_UNIT_CONTRACT_DEAD_IS_INERT = BIT(3),
	/** Invariant RunRuleHolds: the CPU runs the thread of the rule (on one CPU, the cache). */
	KERNEL_UNIT_CONTRACT_RUN_RULE_HOLDS = BIT(4),
	/** No lost thread (out of its wait queue and not ready). */
	KERNEL_UNIT_CONTRACT_NO_LOST_THREAD = BIT(5),
	/** A misuse of the contract or of the environment. */
	KERNEL_UNIT_CONTRACT_MISUSE = BIT(6),
	/** A waiting thread never runs again. */
	KERNEL_UNIT_CONTRACT_NO_RETURN = BIT(7),
};

/**
 * The Zephyr priority of the rank @p n (0 or more) in a test whose result is
 * the same for preemptible and for cooperative threads: @p n if the scenario
 * has preemptible priorities, else the cooperative priority
 * K_PRIO_COOP(@p n) (@c CONFIG_NUM_PREEMPT_PRIORITIES = 0). Both keep the
 * order of the ranks. @p n must be less than the number of priorities of
 * each kind.
 */
#define KERNEL_UNIT_CONTRACT_PRIO(n) (IS_ENABLED(CONFIG_PREEMPT_ENABLED) ? (n) : K_PRIO_COOP(n))

/** An action of the environment. */
typedef void (*kernel_unit_contract_action_t)(void);

/** @brief Start a test: no thread, the idle thread runs. */
void kernel_unit_contract_setup(void);

/**
 * @brief Add a ready thread with the Zephyr priority @p prio.
 *
 * The thread goes to the end of the threads of its priority in the run queue
 * (the run queue order of the contract, rqStamp).
 */
void kernel_unit_contract_thread(struct k_thread *thread, int prio);

/**
 * @brief Let the CPU run @p thread (NULL: the idle thread).
 *
 * The state is the state after update_cache(0) with this current thread: the
 * next reschedule point selects kernel_unit_contract_next(). The function does
 * not check the rule, so a test can make each state for a query.
 */
void kernel_unit_contract_start(struct k_thread *thread);

/**
 * @brief Let @p thread wait on @p wait_q (a wait in the past, PendCurr).
 *
 * The thread has the return value -EAGAIN. If it is the current thread, the
 * state is the state inside z_pend_curr() before the switch: use it only for
 * queries.
 */
void kernel_unit_contract_wait(struct k_thread *thread, _wait_q_t *wait_q, k_timeout_t timeout);

/** @brief Add an environment step: @p thread runs @p action. */
void kernel_unit_contract_env_thread(struct k_thread *thread, kernel_unit_contract_action_t action);

/** @brief Add an environment step: an ISR runs @p action. */
void kernel_unit_contract_env_isr(kernel_unit_contract_action_t action);

/** @brief Add an environment step: the first armed timeout expires. */
void kernel_unit_contract_env_timeout(void);

/** @brief Add an environment step: the thread that runs aborts @p thread. */
void kernel_unit_contract_env_abort(struct k_thread *thread);

/** @brief Run @p action in an ISR now. The exit of the ISR is a reschedule point. */
void kernel_unit_contract_run_isr(kernel_unit_contract_action_t action);

/** @brief Let the first armed timeout expire now (ThreadTimeout, in the timer ISR). */
void kernel_unit_contract_timeout(void);

/**
 * @brief The thread that runs calls k_thread_abort(@p thread) (Abort).
 *
 * If the idle thread runs, an ISR does it. An abort of the current thread does
 * not return in the real kernel: the adapter expects the check NO_RETURN then.
 */
void kernel_unit_contract_abort(struct k_thread *thread);

/** @brief The thread that runs calls k_thread_priority_set(@p thread, @p prio) (SetPrio). */
void kernel_unit_contract_set_prio(struct k_thread *thread, int prio);

/**
 * @brief Call z_unpend_all(@p wait_q) (UnpendAll).
 *
 * @return The return value, or -ENOSYS if the scheduler has no such function.
 */
int kernel_unit_contract_unpend_all(_wait_q_t *wait_q);

/**
 * @brief The next call of z_pend_curr() comes from an ISR, and the test expects the panic.
 *
 * The reference fake fails a test with an ISR refusal that the test does not
 * expect. The real z_pend_curr() needs no preparation.
 */
void kernel_unit_contract_expect_panic(void);

/** @brief Return the thread that runs, or NULL for the idle thread. */
struct k_thread *kernel_unit_contract_current(void);

/** @brief Return the thread that the next reschedule point selects (NULL: idle). */
struct k_thread *kernel_unit_contract_next(void);

/** @brief Return the swap return value of @p thread (swapRet). */
int kernel_unit_contract_ret(struct k_thread *thread);

/**
 * @brief Return true if the CPU is locked now (Platform!Locked).
 *
 * The scheduler lock and irq_lock() lock the CPU. The reference fake has no
 * interrupt lock state: its adapter counts the calls of the arch fakes.
 */
bool kernel_unit_contract_irq_locked(void);

/** @brief Copy the waiters of @p wait_q, head first. Return their number. */
size_t kernel_unit_contract_waiters(_wait_q_t *wait_q, struct k_thread **out, size_t max);

/** @brief Let the checks in @p checks fail without a failed test. */
void kernel_unit_contract_expect(unsigned int checks);

/** @brief Evaluate the invariants now. Return the set of the checks that failed so far. */
unsigned int kernel_unit_contract_found(void);

/** @brief Assert the invariants now, and that no unexpected check failed. */
void kernel_unit_contract_assert_ok(void);

#ifdef __cplusplus
}
#endif

/** @} */

#endif /* KERNEL_UNIT_SCHED_CONTRACT_H_ */
