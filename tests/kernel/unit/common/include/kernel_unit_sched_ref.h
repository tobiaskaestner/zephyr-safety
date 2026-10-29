/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @defgroup kernel_unit_sched_ref Reference fake of the scheduler contract
 * @ingroup kernel_unit_models
 * @brief A fake of the scheduler interface with the state and the rules of layer A.
 *
 * The reference fake is the C form of the scheduler contract in
 * @c safety/spec/tla/lib/Scheduler.tla (layer A), for one CPU. Each scheduler
 * function that the kernel objects call has one fake function. Its comment
 * names the operator of the contract. The fake keeps the state of the
 * contract:
 *
 * - The threads of the test, each with a state (ready, pending, dead), a
 *   priority (@c base.prio), a swap return value and swap data.
 * - One wait queue for each @c _wait_q_t: the threads with this
 *   @c base.pended_on. The order is the rule @c Before of
 *   @c lib/WaitQueue.tla: a higher priority first, then the order of arrival.
 * - The current thread (@c _current), or the idle thread (NULL).
 * - The armed timeouts, with a deadline on a fake clock.
 *
 * The fake is opt-in. kernel_unit_sched_ref_install() sets the @c custom_fake
 * of the FFF fakes of the group @c sched and of arch_thread_return_value_set().
 * FFF records each call before the fake runs, so the call history stays
 * complete. A test that does not install the fake keeps the plain FFF fakes.
 *
 * A wait in a harness with one thread: the fake z_pend_curr() records the wait
 * (@c PendCurr), selects the next thread, and runs the environment steps that
 * the test installed (another thread, an ISR, a timeout, an abort). When the
 * CPU selects the waiting thread again, z_pend_curr() returns its swap return
 * value (@c Resume).
 *
 * The checks come from the invariants and the preconditions of the contract
 * (see enum kernel_unit_sched_ref_check). A failed check prints a message and
 * fails the test, unless the test expects it (kernel_unit_sched_ref_expect()).
 *
 * Fake group @c sched_ref. It needs the groups @c sched, @c arch, @c fatal and
 * @c init. The design note is in the workspace
 * (@c claude/kernel-unit/reffake/design.md).
 *
 * @{
 */

#ifndef KERNEL_UNIT_SCHED_REF_H_
#define KERNEL_UNIT_SCHED_REF_H_

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/util.h>
#include <ksched.h>

#ifdef __cplusplus
extern "C" {
#endif

/** Maximum number of threads of one test. */
#define KERNEL_UNIT_SCHED_REF_MAX_THREADS 8

/** Maximum number of environment steps of one test. */
#define KERNEL_UNIT_SCHED_REF_MAX_STEPS 8

/** Bit of the idle thread in the set of kernel_unit_sched_ref_choices(). */
#define KERNEL_UNIT_SCHED_REF_IDLE BIT(31)

/** The checks of the fake. Each check is one bit. */
enum kernel_unit_sched_ref_check {
	/** Invariant CurIsReady: the current thread is ready. */
	KERNEL_UNIT_SCHED_REF_CUR_IS_READY = BIT(0),
	/** Invariant PendingIsQueued: pending if and only if in a wait queue, with -EAGAIN. */
	KERNEL_UNIT_SCHED_REF_PENDING_IS_QUEUED = BIT(1),
	/** Invariant ArmedArePending: only a pending thread has an armed timeout. */
	KERNEL_UNIT_SCHED_REF_ARMED_ARE_PENDING = BIT(2),
	/** Invariant DeadIsInert: a dead thread has no wait, no return value and no CPU. */
	KERNEL_UNIT_SCHED_REF_DEAD_IS_INERT = BIT(3),
	/** Invariant RunRuleHolds: the CPU runs a thread that the rule Choices selects. */
	KERNEL_UNIT_SCHED_REF_RUN_RULE_HOLDS = BIT(4),
	/** TypeOK: no thread is out of its wait queue and not ready (a lost thread). */
	KERNEL_UNIT_SCHED_REF_NO_LOST_THREAD = BIT(5),
	/** A precondition of an operator is false: a misuse of the contract. */
	KERNEL_UNIT_SCHED_REF_MISUSE = BIT(6),
	/** The waiting thread never runs again: z_pend_curr() does not return. */
	KERNEL_UNIT_SCHED_REF_NO_RETURN = BIT(7),
};

/** The state of a thread (tstate of the contract, and one transient state). */
enum kernel_unit_sched_ref_tstate {
	/** Ready to run, or running. */
	KERNEL_UNIT_SCHED_REF_READY,
	/** In a wait queue. */
	KERNEL_UNIT_SCHED_REF_PENDING,
	/**
	 * Out of its wait queue, not yet ready: between
	 * z_unpend_first_thread_locked() and z_sched_ready_locked(). The contract
	 * does not have this state: WakeFirstWith is one step.
	 */
	KERNEL_UNIT_SCHED_REF_UNPENDED,
	/** Aborted. */
	KERNEL_UNIT_SCHED_REF_DEAD,
};

/** The fake state of one thread of the test. */
struct kernel_unit_sched_ref_thread {
	/** The thread. */
	struct k_thread *thread;
	/** The state (tstate). */
	enum kernel_unit_sched_ref_tstate state;
	/** False: swapRet is NoRet (the thread has no wait to return from). */
	bool has_ret;
	/** The swap return value (swapRet), if has_ret. */
	int ret;
	/** The order of arrival in the wait queue (stamp). */
	uint32_t stamp;
	/**
	 * The run queue order: the order in which the thread became ready, or
	 * got a new priority while ready.
	 */
	uint32_t ready_seq;
	/** True if the thread has an armed timeout. */
	bool armed;
	/** The deadline of the armed timeout on the fake clock. */
	int64_t deadline;
	/** The order of the arming, for equal deadlines. */
	uint32_t armed_seq;
};

/** Action of an environment step. */
typedef void (*kernel_unit_sched_ref_action_t)(void);

/** The kinds of environment steps. */
enum kernel_unit_sched_ref_step_kind {
	/** An action of a thread that runs. */
	KERNEL_UNIT_SCHED_REF_STEP_THREAD,
	/** An action of an ISR. The exit of the ISR selects a thread. */
	KERNEL_UNIT_SCHED_REF_STEP_ISR,
	/** The expiry of the first armed timeout (ThreadTimeout). */
	KERNEL_UNIT_SCHED_REF_STEP_TIMEOUT,
	/** The abort of a thread by the thread that runs (Abort). */
	KERNEL_UNIT_SCHED_REF_STEP_ABORT,
};

/** One environment step. */
struct kernel_unit_sched_ref_step {
	/** The kind of the step. */
	enum kernel_unit_sched_ref_step_kind kind;
	/** The thread of the action, or the thread to abort. */
	struct k_thread *thread;
	/** The action, or NULL. */
	kernel_unit_sched_ref_action_t action;
};

/** One record of a layer-A call, for a trace hook. */
struct kernel_unit_sched_ref_record {
	/** The name of the operator in Scheduler.tla, for example "WakeFirst". */
	const char *op;
	/** The C function. */
	const char *c_function;
	/** The thread that calls, or NULL for an ISR or the idle thread. */
	struct k_thread *actor;
	/** True if the caller is an ISR. */
	bool isr;
	/** The wait queue, or NULL. */
	_wait_q_t *wait_q;
	/** The thread that the call changes, or NULL. */
	struct k_thread *thread;
	/** The value of the call (a return value or a swap return value). */
	int value;
};

/** A trace hook: the fake calls it once for each layer-A call. */
typedef void (*kernel_unit_sched_ref_trace_t)(const struct kernel_unit_sched_ref_record *rec);

/** The state of the reference fake. The reset rule of the group sets it to zeros. */
struct kernel_unit_sched_ref {
	/** True after kernel_unit_sched_ref_install(). */
	bool installed;
	/** The threads of the test. */
	struct kernel_unit_sched_ref_thread threads[KERNEL_UNIT_SCHED_REF_MAX_THREADS];
	/** The number of threads. */
	size_t n_threads;
	/** The environment steps. */
	struct kernel_unit_sched_ref_step steps[KERNEL_UNIT_SCHED_REF_MAX_STEPS];
	/** The number of environment steps. */
	size_t n_steps;
	/** The next environment step. */
	size_t next_step;
	/** The next stamp, ready number and arming number. */
	uint32_t next_stamp;
	uint32_t next_ready;
	uint32_t next_armed;
	/** The fake clock in ticks. It advances only at an expiry. */
	int64_t clock;
	/**
	 * True after z_thread_prio_set() of a ready thread and after an abort,
	 * until the next selection. Then the rule is runq_best() of the code: no
	 * tie win and no cooperative rule for the current thread (update_cache(1)
	 * in sched.c: z_thread_prio_set() and halt_thread()).
	 */
	bool preempt_ok;
	/** True while an environment action runs. */
	bool in_env;
	/** True after NO_RETURN: the waiting thread stopped for ever. */
	bool halted;
	/** The checks that the test expects to fail. */
	unsigned int expected;
	/** The checks that failed since the install. */
	unsigned int found;
	/** The trace hook, or NULL. */
	kernel_unit_sched_ref_trace_t trace;
};

/** The state of the reference fake. */
extern struct kernel_unit_sched_ref kernel_unit_sched_ref;

/**
 * @brief Install the reference fake.
 *
 * Sets the @c custom_fake of z_pend_curr(), z_reschedule(), z_sched_wake(),
 * z_sched_ready_locked(), z_unpend_first_thread_locked(), z_thread_prio_set(),
 * z_sched_wake_thread_locked(), z_try_abort_thread_timeout(), z_waitq_init(),
 * z_waitq_head(), z_waitq_head_locked() and arch_thread_return_value_set().
 * With the group @c scheduler (the fakes of kernel/scheduler.c), also of
 * k_sched_current_thread_query(), z_sched_waitq_walk() and z_sched_wait().
 * The CPU runs the idle thread until kernel_unit_sched_ref_set_current().
 */
void kernel_unit_sched_ref_install(void);

/**
 * @brief Add a ready thread to the fake.
 *
 * The fake sets the fields of @p thread that it uses: @c base.prio,
 * @c base.thread_state, @c base.pended_on, @c base.swap_data and the timeout.
 *
 * @param thread The thread.
 * @param prio The Zephyr priority. A negative value is a cooperative thread.
 */
void kernel_unit_sched_ref_thread(struct k_thread *thread, int prio);

/**
 * @brief Let the CPU run @p thread.
 *
 * The function does not check the rule Choices, so that a test can make each
 * state for a query. For an initial state (InitState), the test calls
 * kernel_unit_sched_ref_assert_ok() before the action: it checks RunRuleHolds.
 *
 * @param thread A ready thread of the fake, or NULL for the idle thread.
 */
void kernel_unit_sched_ref_set_current(struct k_thread *thread);

/**
 * @brief Let @p thread wait on @p wait_q before the action (PendCurr in the past).
 *
 * No thread is selected. If @p thread is the current thread, the state is the
 * state inside PendCurr before the selection: use it only for queries.
 *
 * @param thread A ready thread of the fake.
 * @param wait_q The wait queue.
 * @param timeout K_FOREVER, or a finite timeout that arms a timeout.
 */
void kernel_unit_sched_ref_wait(struct k_thread *thread, _wait_q_t *wait_q, k_timeout_t timeout);

/**
 * @brief Add an environment step: @p thread runs @p action while the current thread waits.
 *
 * When the step comes, @p thread must run. Otherwise the check MISUSE fails.
 */
void kernel_unit_sched_ref_env_thread(struct k_thread *thread,
				      kernel_unit_sched_ref_action_t action);

/** @brief Add an environment step: an ISR runs @p action (NULL: an interrupt without a call). */
void kernel_unit_sched_ref_env_isr(kernel_unit_sched_ref_action_t action);

/** @brief Add an environment step: the first armed timeout expires. */
void kernel_unit_sched_ref_env_timeout(void);

/** @brief Add an environment step: the thread that runs aborts @p thread. */
void kernel_unit_sched_ref_env_abort(struct k_thread *thread);

/**
 * @brief Run @p action in ISR context now. At the exit of the ISR, the CPU selects a thread.
 *
 * @param action The action, or NULL (an interrupt without a kernel call).
 */
void kernel_unit_sched_ref_run_isr(kernel_unit_sched_ref_action_t action);

/** @brief Let the first armed timeout expire now (ThreadTimeout, in the timer ISR). */
void kernel_unit_sched_ref_timeout(void);

/**
 * @brief Let the current thread abort @p thread now (Abort).
 *
 * If the CPU runs the idle thread, an ISR aborts the thread. As
 * halt_thread() of the code, the abort permits a switch at the next
 * selection without the cooperative rule (@c preempt_ok). A thread that
 * aborts another thread does not select: the check RUN_RULE_HOLDS can fail
 * (finding P7-c).
 */
void kernel_unit_sched_ref_abort(struct k_thread *thread);

/** @brief Let the checks in @p checks fail without a failed test. */
void kernel_unit_sched_ref_expect(unsigned int checks);

/**
 * @brief Evaluate the invariants now, without a failure.
 *
 * @return The set of the invariant checks that are false now.
 */
unsigned int kernel_unit_sched_ref_check(void);

/**
 * @brief Assert the invariants now, and assert that no unexpected check failed.
 *
 * Call it after the action of the test. A critical section that ends with
 * k_spin_unlock() has no check point in the fake.
 */
void kernel_unit_sched_ref_assert_ok(void);

/**
 * @brief Return the set of threads that the rule Choices permits now.
 *
 * @return One bit for each thread (kernel_unit_sched_ref_bit()), and
 *         KERNEL_UNIT_SCHED_REF_IDLE for the idle thread.
 */
uint32_t kernel_unit_sched_ref_choices(void);

/**
 * @brief Return the thread that the next selection takes, without a change (NULL: idle).
 *
 * This is the thread of kernel_unit_sched_ref_choices() that is first in the
 * run queue order: the thread that the fake selects at the next reschedule
 * point.
 */
struct k_thread *kernel_unit_sched_ref_next(void);

/** @brief Return the bit of @p thread in a set of threads (NULL: the idle thread). */
uint32_t kernel_unit_sched_ref_bit(const struct k_thread *thread);

/** @brief Return the fake state of @p thread, or NULL if the fake does not know it. */
struct kernel_unit_sched_ref_thread *kernel_unit_sched_ref_of(const struct k_thread *thread);

/**
 * @brief Copy the waiters of @p wait_q, head first (WQ!Ordered).
 *
 * @param wait_q The wait queue.
 * @param out The array for the waiters.
 * @param max The size of @p out.
 * @return The number of waiters.
 */
size_t kernel_unit_sched_ref_waiters(_wait_q_t *wait_q, struct k_thread **out, size_t max);

#ifdef __cplusplus
}
#endif

/** @} */

#endif /* KERNEL_UNIT_SCHED_REF_H_ */
