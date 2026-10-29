/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @defgroup kernel_unit_sched kernel/sched.c
 * @ingroup kernel_unit_tests
 * @brief Design specification of kernel/sched.c, written as unit tests on the platform model.
 *
 * @par The unit and its contracts
 * @c kernel/sched.c is the core of the scheduler. Together with its headers
 * @c ksched.h, @c kswap.h, @c kthread.h, @c metairq.h, @c run_q.h,
 * @c priority_q.h, @c wait_q.h, @c kspinlock.h and @c scheduler.h it keeps
 * one state under one lock (@c _sched_spinlock): the run queue, the current
 * thread, the cache @c _kernel.ready_q.cache and the swap return values. The
 * contract above is layer A of @c safety/spec/tla/lib/Scheduler.tla. The
 * contract below is the world, @c lib/Platform.tla.
 *
 * In this application these headers are real (kernel_unit_real_headers() in
 * @c CMakeLists.txt), also @c kernel_internal.h, @c timeout_q.h,
 * @c timeslicing.h, @c ipi.h and @c usage.h. Only the functions of the
 * @c .c files below sched.c and the arch layer are fakes.
 *
 * @par The cache and the reschedule points
 * Each change of the run queue, of a priority of a ready thread or of a
 * thread state calls update_cache(). On one CPU it writes the decision to the
 * cache: the head of the run queue, or the current thread if it is
 * cooperative and the argument @c preempt_ok is 0. A reschedule point
 * switches to the cache: z_swap() (in z_pend_curr() and in z_reschedule() if
 * the key of the lock is unlocked and the caller is not an ISR), and the exit
 * of an interrupt. Thus between a change and the next reschedule point, the
 * CPU can run a thread that is not the cache. The tests of the findings P2-w,
 * P7-c and F14 show such windows.
 *
 * @par Interfaces below sched.c
 * - Architecture (the model group @c platform, the contract Platform):
 *   arch_irq_lock(), arch_irq_unlock(), arch_irq_unlocked() (through
 *   k_spin_lock() and irq_lock()), arch_is_in_isr(),
 *   arch_thread_return_value_set(), arch_swap() (without
 *   @kconfig{CONFIG_USE_SWITCH}), arch_switch() (with it),
 *   arch_coprocessors_disable(), and the exit of an ISR.
 * - Timeouts (@c kernel/timeout.c, fake group @c timeout with the model of
 *   Timeout): z_add_timeout(), z_try_abort_timeout(),
 *   z_timeout_inflight_superseded().
 * - Time slices (@c kernel/timeslicing.c): z_time_slice_reset().
 * - Threads (@c kernel/thread.c): z_dummy_thread_init().
 * - Fatal errors: z_fatal_error() through k_panic().
 *
 * @par Contract tests
 * The suite @c sched_contract (@ref kernel_unit_sched_contract) runs the same
 * tests against this application and against the reference fake (application
 * @c sched_ref). The adapter of the real code is in this file. The contract
 * Scheduler also has two functions of @c kernel/scheduler.c,
 * z_sched_waitq_walk() and z_sched_wait(). Thus this file also includes
 * @c kernel/scheduler.c (the second kernel source file of this application),
 * and the contract tests of the walk and of the wait run on the real code of
 * both files. The unit test of scheduler.c on fakes is the application
 * @c scheduler (@ref kernel_unit_scheduler). The suite
 * @c sched_unit of this file has the tests of the findings and the tests that
 * only the real code can have (the switch variants, the time slices).
 *
 * @par Kconfig options that change sched.c
 * - @kconfig{CONFIG_USE_SWITCH}: arch_switch() and z_get_next_switch_handle()
 *   in place of arch_swap() and PendSV.
 * - @kconfig{CONFIG_TIMESLICING}: update_cache() and do_swap() reset the time
 *   slice of the new thread. With @kconfig{CONFIG_SWAP_NONATOMIC},
 *   z_pend_curr() writes @c pending_current.
 * - @kconfig{CONFIG_SCHED_MULTIQ}, @kconfig{CONFIG_WAITQ_SCALABLE}: the run
 *   queue and the wait queue backends (@c priority_q.h).
 * - @kconfig{CONFIG_NUM_METAIRQ_PRIORITIES}: the meta-IRQ code of
 *   @c metairq.h.
 * - @kconfig{CONFIG_ASSERT}: the assertions of sched.c, and with
 *   @kconfig{CONFIG_SPIN_VALIDATE} the checks of a switch.
 * - @kconfig{CONFIG_NUM_PREEMPT_PRIORITIES} = 0 (only cooperative threads,
 *   @kconfig{CONFIG_PREEMPT_ENABLED} is n) and
 *   @kconfig{CONFIG_NUM_COOP_PRIORITIES} = 0 (only preemptible threads,
 *   @kconfig{CONFIG_COOP_ENABLED} is n): sched.c has no code for them, but
 *   the priority range changes, and without @kconfig{CONFIG_PREEMPT_ENABLED}
 *   the exit of an interrupt with arch_swap() does not switch
 *   (exc_exit.c:57). A test that needs a kind of thread that the scenario
 *   does not have is skipped.
 * - @kconfig{CONFIG_SMP} is not in this application (level 1 is one CPU).
 */

/**
 * @defgroup kernel_unit_sched_move_current_to_end_of_prio_q move_current_to_end_of_prio_q()
 * @ingroup kernel_unit_sched
 * @brief No unit test covers move_current_to_end_of_prio_q() (k_yield() is not in the model).
 */

/**
 * @defgroup kernel_unit_sched_z_ready_thread z_ready_thread()
 * @ingroup kernel_unit_sched
 * @brief No test of its own. The adapter of the contract tests adds each thread with it.
 */

/**
 * @defgroup kernel_unit_sched_z_sched_ready_locked z_sched_ready_locked()
 * @ingroup kernel_unit_sched
 * @brief No test of its own. The contract test test_wake_first_with_is_one_wake calls it.
 */

/**
 * @defgroup kernel_unit_sched_z_unready_thread z_unready_thread()
 * @ingroup kernel_unit_sched
 * @brief No unit test covers z_unready_thread() (a function for benchmarks).
 */

/**
 * @defgroup kernel_unit_sched_z_sched_unready_locked z_sched_unready_locked()
 * @ingroup kernel_unit_sched
 * @brief No unit test covers z_sched_unready_locked() (sleep.c is not in the model).
 */

/**
 * @defgroup kernel_unit_sched_z_yield_testing_only z_yield_testing_only()
 * @ingroup kernel_unit_sched
 * @brief No unit test covers z_yield_testing_only().
 */

/**
 * @defgroup kernel_unit_sched_z_thread_halt z_thread_halt()
 * @ingroup kernel_unit_sched
 * @brief The shared path of k_thread_abort() and k_thread_suspend() (Abort).
 *
 * halt_thread() marks the thread dead, takes it out of its queue, wakes the
 * threads of its join queue with 0, and calls update_cache(1). For a target
 * that is not the current thread, z_thread_halt() then releases the lock
 * without a reschedule. The contract tests of the abort call it through the
 * adapter.
 */

/**
 * @defgroup kernel_unit_sched_z_sched_lock_reschedule z_sched_lock_reschedule()
 * @ingroup kernel_unit_sched
 * @brief The reschedule point of k_sched_unlock() and k_reschedule() (scheduler.c).
 *
 * update_cache(0), then reschedule() with the key of the scheduler lock: a
 * switch only if the key is unlocked and the caller is not an ISR. The tests
 * call it through k_sched_unlock() and k_reschedule() of the real
 * @c kernel/scheduler.c, which this application also includes.
 */

/**
 * @defgroup kernel_unit_sched_z_sched_yield z_sched_yield()
 * @ingroup kernel_unit_sched
 * @brief No unit test covers z_sched_yield() (k_yield() is not in the model).
 */

/**
 * @defgroup kernel_unit_sched_z_sched_add_to_waitq_locked z_sched_add_to_waitq_locked()
 * @ingroup kernel_unit_sched
 * @brief No test of its own. The adapter makes each wait of the setup with it.
 */

/**
 * @defgroup kernel_unit_sched_z_pend_thread z_pend_thread()
 * @ingroup kernel_unit_sched
 * @brief No unit test covers z_pend_thread().
 */

/**
 * @defgroup kernel_unit_sched_z_unpend_thread_no_timeout z_unpend_thread_no_timeout()
 * @ingroup kernel_unit_sched
 * @brief No unit test covers z_unpend_thread_no_timeout().
 */

/**
 * @defgroup kernel_unit_sched_z_sched_wake_thread_locked z_sched_wake_thread_locked()
 * @ingroup kernel_unit_sched
 * @brief No test of its own. The timeout handler z_thread_timeout() calls it.
 */

/**
 * @defgroup kernel_unit_sched_z_thread_timeout z_thread_timeout()
 * @ingroup kernel_unit_sched
 * @brief No test of its own. The timer ISR of the platform model calls it (ThreadTimeout).
 */

/**
 * @defgroup kernel_unit_sched_z_pend_curr z_pend_curr()
 * @ingroup kernel_unit_sched
 * @brief The wait of the current thread (PendCurr, then Resume).
 *
 * z_pend_curr() adds the current thread to the wait queue, arms its timeout,
 * and switches with the key of the caller. Without
 * @kconfig{CONFIG_USE_SWITCH}, the switch is PendSV: interrupts that are
 * pending at the unlock of arch_swap() run before it (the gap of
 * @kconfig{CONFIG_SWAP_NONATOMIC}).
 */

/**
 * @defgroup kernel_unit_sched_z_unpend1_no_timeout z_unpend1_no_timeout()
 * @ingroup kernel_unit_sched
 * @brief No unit test covers z_unpend1_no_timeout().
 */

/**
 * @defgroup kernel_unit_sched_z_unpend_thread z_unpend_thread()
 * @ingroup kernel_unit_sched
 * @brief No unit test covers z_unpend_thread().
 */

/**
 * @defgroup kernel_unit_sched_z_thread_prio_set z_thread_prio_set()
 * @ingroup kernel_unit_sched
 * @brief The priority change without a reschedule (PrioSet).
 *
 * A ready thread leaves the run queue and comes back at the end of its new
 * priority, also if the priority does not change. Then update_cache(1): the
 * next reschedule point takes the head of the run queue without the rule for
 * cooperative threads. k_thread_priority_set() (thread.c) then reschedules.
 */

/**
 * @defgroup kernel_unit_sched_z_reschedule z_reschedule()
 * @ingroup kernel_unit_sched
 * @brief The end of a critical section that can switch (Release "resched").
 *
 * z_reschedule() switches only if the key of the lock is unlocked and the
 * caller is not an ISR (resched()), and if the cache is not the current
 * thread (need_swap()). Else it only releases the lock.
 */

/**
 * @defgroup kernel_unit_sched_z_reschedule_locked z_reschedule_locked()
 * @ingroup kernel_unit_sched
 * @brief No unit test covers z_reschedule_locked().
 */

/**
 * @defgroup kernel_unit_sched_z_reschedule_irqlock z_reschedule_irqlock()
 * @ingroup kernel_unit_sched
 * @brief No test of its own. k_thread_priority_set() calls it (z_reschedule_unlocked()).
 */

/**
 * @defgroup kernel_unit_sched_z_swap_next_thread z_swap_next_thread()
 * @ingroup kernel_unit_sched
 * @brief No unit test covers z_swap_next_thread() (only SMP calls it).
 */

/**
 * @defgroup kernel_unit_sched_z_get_next_switch_handle z_get_next_switch_handle()
 * @ingroup kernel_unit_sched
 * @brief No test of its own. With CONFIG_USE_SWITCH, the exit of an ISR of the model calls it.
 */

/**
 * @defgroup kernel_unit_sched_z_unpend_all z_unpend_all()
 * @ingroup kernel_unit_sched
 * @brief No test of its own. The contract test of UnpendAll calls it.
 */

/**
 * @defgroup kernel_unit_sched_z_thread_suspend_current z_thread_suspend_current()
 * @ingroup kernel_unit_sched
 * @brief No unit test covers z_thread_suspend_current().
 */

/**
 * @defgroup kernel_unit_sched_static Static functions and data
 * @ingroup kernel_unit_sched
 * @brief Tests of the static functions of sched.c and of the inline code of its headers.
 */

#include <string.h>
#include <zephyr/ztest.h>
#include <kernel_unit.h>
#include <kernel_unit_platform.h>
#include <kernel_unit_sched_contract.h>
#include <fakes/timeout.h>
#include <fakes/timeslicing.h>
#include <fakes/thread.h>
#include <fakes/fatal.h>
#ifdef CONFIG_ASSERT
#include <fakes/assert.h>
#endif

#include <kernel/sched.c>
#include <scheduler.h>
/*
 * kernel/scheduler.c is the second source file of the contract Scheduler
 * (z_sched_waitq_walk(), z_sched_wait()). The contract tests of the walk
 * and of the wait run on it and on the real sched.c. Its unit test on fakes
 * is the application scheduler.
 */
#include <kernel/scheduler.c>

#if defined(CONFIG_WAITQ_SCALABLE) || defined(CONFIG_SCHED_SCALABLE)
/*
 * The red-black queues call z_priq_rb_lessthan() of kernel/priority_queues.c
 * and the tree of lib/utils/rb.c. Both are data structures of the contract
 * Queues below sched.c, without a world below, so they stay real. They need
 * the ztest headers of this file, so they are included here.
 */
#include <kernel/priority_queues.c>
#include <lib/utils/rb.c>
#endif

/* ---------------------------------------------------------------------------
 * The adapter of the contract tests on the real sched.c (see
 * kernel_unit_sched_contract.h). It is in this file because the start of a
 * test calls the static update_cache() of sched.c.
 */

/* Maximum number of threads of one test. */
#define MAX_THREADS 8

/* The threads of the test, for the invariants. */
static struct k_thread *threads[MAX_THREADS];
static size_t n_threads;

/* The checks that the test expects, and the checks that failed. */
static unsigned int expected;
static unsigned int found;

/* The actions of the environment steps, as arguments of the platform steps. */
static kernel_unit_contract_action_t boxes[KERNEL_UNIT_PLATFORM_MAX_STEPS + 4];
static size_t n_boxes;

static struct k_thread *idle_thread(void)
{
	return &z_idle_threads[0];
}

static void run_boxed(void *arg)
{
	kernel_unit_contract_action_t *action = arg;

	if (*action != NULL) {
		(*action)();
	}
}

static void *box(kernel_unit_contract_action_t action)
{
	if (n_boxes >= ARRAY_SIZE(boxes)) {
		ztest_test_fail();
		return NULL;
	}
	boxes[n_boxes] = action;

	return &boxes[n_boxes++];
}

int kernel_unit_contract_ret(struct k_thread *thread)
{
#ifdef CONFIG_USE_SWITCH
	return thread->swap_retval;
#else
	return thread->arch.swap_return_value;
#endif
}

/* The invariants of Scheduler on the real state, for the threads of the test. */
static unsigned int invariants(void)
{
	unsigned int bad = 0U;
	struct k_thread *cur = _current;
	bool pendsv = kernel_unit_platform.pendsv;

	if ((cur != idle_thread()) && !pendsv && !z_is_thread_ready(cur)) {
		bad |= KERNEL_UNIT_CONTRACT_CUR_IS_READY;
	}
	for (size_t i = 0; i < n_threads; i++) {
		struct k_thread *t = threads[i];
		bool pending = z_is_thread_pending(t);

		if ((pending != (t->base.pended_on != NULL)) ||
		    (pending && (kernel_unit_contract_ret(t) != -EAGAIN))) {
			bad |= KERNEL_UNIT_CONTRACT_PENDING_IS_QUEUED;
		}
		if (z_is_thread_timeout_active(t) && !pending) {
			bad |= KERNEL_UNIT_CONTRACT_ARMED_ARE_PENDING;
		}
		if (z_is_thread_dead(t) &&
		    ((t->base.pended_on != NULL) || ((t == cur) && !pendsv))) {
			bad |= KERNEL_UNIT_CONTRACT_DEAD_IS_INERT;
		}
		if (z_is_thread_ready(t) && !z_is_thread_queued(t)) {
			bad |= KERNEL_UNIT_CONTRACT_NO_LOST_THREAD;
		}
	}
	if (!kernel_unit_platform_locked() && !pendsv && (cur != _kernel.ready_q.cache)) {
		bad |= KERNEL_UNIT_CONTRACT_RUN_RULE_HOLDS;
	}

	return bad;
}

/* The checks of the platform model, as checks of the contract. */
static unsigned int platform_found(void)
{
	unsigned int f = kernel_unit_platform.found;
	unsigned int bad = 0U;

	if ((f & (KERNEL_UNIT_PLATFORM_MISUSE | KERNEL_UNIT_PLATFORM_SWITCH_LOCKED)) != 0U) {
		bad |= KERNEL_UNIT_CONTRACT_MISUSE;
	}
	if ((f & KERNEL_UNIT_PLATFORM_NO_RETURN) != 0U) {
		bad |= KERNEL_UNIT_CONTRACT_NO_RETURN;
	}

	return bad;
}

/* A check point: the end of an environment step or of an adapter action. */
static void check_point(void)
{
	unsigned int bad;

	if (kernel_unit_platform.halted) {
		return;
	}
	bad = invariants();
	found |= bad;
	if ((bad & ~expected) != 0U) {
		TC_PRINT("sched: invariants 0x%x false at a check point\n", bad & ~expected);
		ztest_test_fail();
	}
}

void kernel_unit_contract_setup(void)
{
	struct k_thread *idle = idle_thread();

	memset(idle, 0, sizeof(*idle));
	idle->base.prio = K_IDLE_PRIO;
	z_init_thread_timeout(&idle->base);
#ifdef CONFIG_USE_SWITCH
	idle->switch_handle = idle;
#endif
	_kernel.cpus[0].idle_thread = idle;
	_kernel.cpus[0].current = idle;
	_priq_run_init(&_kernel.ready_q.runq);
	_kernel.ready_q.cache = idle;
	kernel_unit_platform_install();
	kernel_unit_platform.check_point = check_point;
	n_threads = 0U;
	n_boxes = 0U;
	expected = 0U;
	found = 0U;
}

/* A new thread: the fields that z_init_thread_base() and arch_new_thread() set. */
void kernel_unit_contract_thread(struct k_thread *thread, int prio)
{
	memset(thread, 0, sizeof(*thread));
	thread->base.prio = (int8_t)prio;
	z_init_thread_timeout(&thread->base);
	z_waitq_init(&thread->join_queue);
#ifdef CONFIG_USE_SWITCH
	/* A thread that does not run has a switch handle (arch_new_thread()). */
	thread->switch_handle = thread;
#endif
	if (n_threads < ARRAY_SIZE(threads)) {
		threads[n_threads++] = thread;
	} else {
		ztest_test_fail();
	}
	z_ready_thread(thread);
}

void kernel_unit_contract_start(struct k_thread *thread)
{
	struct k_thread *cur = (thread != NULL) ? thread : idle_thread();

#ifdef CONFIG_USE_SWITCH
	_current->switch_handle = _current;
	cur->switch_handle = NULL;
#endif
	_kernel.cpus[0].current = cur;
	K_SPINLOCK(&_sched_spinlock) {
		update_cache(0);
	}
	/* The test sees only the calls of its action. */
	RESET_FAKE(z_time_slice_reset);
	FFF_RESET_HISTORY();
	kernel_unit_platform.n_switches = 0U;
	kernel_unit_platform.pendsv_requests = 0U;
}

/* The state after PendCurr of the thread and its switch (arch_swap() writes -EAGAIN). */
void kernel_unit_contract_wait(struct k_thread *thread, _wait_q_t *wait_q, k_timeout_t timeout)
{
	K_SPINLOCK(&_sched_spinlock) {
		z_sched_add_to_waitq_locked(thread, wait_q);
		(void)z_add_thread_timeout(thread, timeout);
	}
	thread->arch.swap_return_value = -EAGAIN;
#ifdef CONFIG_USE_SWITCH
	thread->swap_retval = -EAGAIN;
#endif
}

void kernel_unit_contract_env_thread(struct k_thread *thread, kernel_unit_contract_action_t action)
{
	kernel_unit_platform_env_thread(thread, run_boxed, box(action));
}

void kernel_unit_contract_env_isr(kernel_unit_contract_action_t action)
{
	kernel_unit_platform_env_isr(run_boxed, box(action));
}

void kernel_unit_contract_env_timeout(void)
{
	kernel_unit_platform_env_timeout();
}

/*
 * z_thread_abort() of kernel/thread.c (thread.c:1751-1766), without the
 * essential thread: the scheduler lock, then z_thread_halt(). An abort of the
 * current thread by itself does not return (z_swap_locked() of a dead thread).
 */
static void thread_abort(void *arg)
{
	struct k_thread *thread = arg;
	k_spinlock_key_t key = z_sched_spinlock_lock();

	if (z_is_thread_dead(thread)) {
		z_sched_spinlock_unlock(key);
		return;
	}
	if ((thread == _current) && !kernel_unit_platform.in_isr) {
		kernel_unit_contract_expect(KERNEL_UNIT_CONTRACT_NO_RETURN);
		z_thread_halt(thread, key, true);
#ifdef CONFIG_ASSERT
		/*
		 * The real switch does not return. The harness returns, and
		 * z_thread_halt() then asserts "aborted _current back from dead":
		 * an assertion of the harness, not of the code.
		 */
		if (assert_post_action_fake.call_count > 0U) {
			assert_post_action_fake.call_count--;
		}
#endif
		return;
	}
	z_thread_halt(thread, key, true);
}

void kernel_unit_contract_env_abort(struct k_thread *thread)
{
	kernel_unit_platform_env_running(thread_abort, thread);
}

void kernel_unit_contract_run_isr(kernel_unit_contract_action_t action)
{
	kernel_unit_platform_run_isr(run_boxed, box(action));
	check_point();
}

void kernel_unit_contract_timeout(void)
{
	if (!kernel_unit_platform_timer_isr()) {
		TC_PRINT("sched: a timeout without an armed timeout\n");
		ztest_test_fail();
	}
	check_point();
}

void kernel_unit_contract_abort(struct k_thread *thread)
{
	if (_current == idle_thread()) {
		kernel_unit_platform_run_isr(thread_abort, thread);
	} else {
		thread_abort(thread);
	}
	check_point();
}

/*
 * z_impl_k_thread_priority_set() of kernel/thread.c (thread.c:1628-1642),
 * without the check of the priority.
 */
void kernel_unit_contract_set_prio(struct k_thread *thread, int prio)
{
	bool need_sched = z_thread_prio_set(thread, prio);

	if (need_sched && (_current->base.sched_locked == 0U)) {
		z_reschedule_unlocked();
	}
	check_point();
}

int kernel_unit_contract_unpend_all(_wait_q_t *wait_q)
{
	return z_unpend_all(wait_q);
}

void kernel_unit_contract_expect_panic(void)
{
}

struct k_thread *kernel_unit_contract_current(void)
{
	return (_current == idle_thread()) ? NULL : _current;
}

struct k_thread *kernel_unit_contract_next(void)
{
	return (_kernel.ready_q.cache == idle_thread()) ? NULL : _kernel.ready_q.cache;
}

bool kernel_unit_contract_irq_locked(void)
{
	return kernel_unit_platform_locked();
}

size_t kernel_unit_contract_waiters(_wait_q_t *wait_q, struct k_thread **out, size_t max)
{
	struct k_thread *t;
	size_t count = 0U;

	_WAIT_Q_FOR_EACH(wait_q, t) {
		if (count < max) {
			out[count] = t;
		}
		count++;
	}

	return count;
}

void kernel_unit_contract_expect(unsigned int checks)
{
	expected |= checks;
	if ((checks & KERNEL_UNIT_CONTRACT_MISUSE) != 0U) {
		kernel_unit_platform_expect(KERNEL_UNIT_PLATFORM_MISUSE |
					    KERNEL_UNIT_PLATFORM_SWITCH_LOCKED);
	}
	if ((checks & KERNEL_UNIT_CONTRACT_NO_RETURN) != 0U) {
		kernel_unit_platform_expect(KERNEL_UNIT_PLATFORM_NO_RETURN);
	}
}

unsigned int kernel_unit_contract_found(void)
{
	unsigned int now = kernel_unit_platform.halted ? 0U : invariants();

	return found | now | platform_found();
}

void kernel_unit_contract_assert_ok(void)
{
	unsigned int unexpected;

	check_point();
	kernel_unit_platform_assert_ok();
	unexpected = (found | platform_found()) & ~expected;
	if (unexpected != 0U) {
		TC_PRINT("sched: unexpected failed checks 0x%x\n", unexpected);
		ztest_test_fail();
	}
}

/* ---------------------------------------------------------------------------
 * The tests of the findings and of the platform variants (suite sched_unit).
 */

/* A priority of the rank n in a test that also runs with only cooperative threads. */
#define PRIO(n) KERNEL_UNIT_CONTRACT_PRIO(n)

static struct k_thread t1;
static struct k_thread t2;
static struct k_thread t3;
static _wait_q_t wq_a;
static struct k_spinlock test_lock;

static void sched_unit_before(void *fixture)
{
	ARG_UNUSED(fixture);

	kernel_unit_contract_setup();
	z_waitq_init(&wq_a);
}

/*
 * A failed __ASSERT() of the scheduler code stops the run (ztest cannot fail
 * a test in the phase "after", it stops). With CONFIG_ASSERT_TEST the hook is
 * a fake that returns, so without this check no test sees the assertion.
 */
static void sched_unit_after(void *fixture)
{
	ARG_UNUSED(fixture);

#ifdef CONFIG_ASSERT
	if (assert_post_action_fake.call_count != 0U) {
		TC_PRINT("%u failed __ASSERT() in the test\n", assert_post_action_fake.call_count);
		ztest_test_fail();
	}
#endif
}

ZTEST_SUITE(sched_unit, NULL, NULL, sched_unit_before, sched_unit_after, NULL);

/* A give: the wake of the first waiter of wq_a with 0, and the reschedule. */
static void give_a(void)
{
	k_spinlock_key_t key = k_spin_lock(&test_lock);

	(void)z_sched_wake(&wq_a, 0, NULL);
	z_reschedule(&test_lock, key);
}

/* A give of wq_a in an ISR (an action of the platform model). */
static void isr_give_a(void *arg)
{
	ARG_UNUSED(arg);
	give_a();
}

/* A give to all waiters of wq_a with 0 (z_sched_wake_all()), in the gap of arch_swap(). */
static void give_all_a(void *arg)
{
	k_spinlock_key_t key = k_spin_lock(&test_lock);

	ARG_UNUSED(arg);
	(void)z_sched_wake_all(&wq_a, 0, NULL);
	z_reschedule(&test_lock, key);
}

/*
 * Finding P2-w (claude/kernel-unit/tla/findings.md): an outer irq_lock()
 * delays a preemption past its irq_unlock(). Expected failure until the
 * finding has a decision: the test asserts the requirement.
 */
#ifdef CONFIG_PREEMPT_ENABLED
ZTEST_EXPECT_FAIL(sched_unit, test_p2w_irq_unlock_gives_cpu_to_woken_thread);
#endif

/**
 * @brief The end of an outer interrupt lock gives the CPU to a higher thread that the lock woke.
 *
 * @details
 * Finding P2-w (property UnlockPreempts, @c @@source ZEP-SRS-2-9). Reading L1:
 * while the thread holds an outer irq_lock(), the selection can wait. At the
 * end of the lock the requirement applies again.
 * - Setup: Zephyr priorities t1 1, t3 0 (both preemptible). t3 waits on
 *   wq_a. t1 runs.
 * - Action: t1 calls irq_lock(). Then a give: k_spin_lock(), z_sched_wake()
 *   of wq_a, z_reschedule(). Then irq_unlock().
 * - Expected by the code (asserted first): z_reschedule() does not switch,
 *   because resched() sees the locked key (the contract test
 *   test_reschedule_under_outer_lock_does_not_switch). After irq_unlock()
 *   the CPU is unlocked and the cache is t3.
 * - Expected by the requirement (asserted last, fails): t3 runs after
 *   irq_unlock(). The code has no reschedule point there. The test has
 *   ZTEST_EXPECT_FAIL().
 *
 * @ingroup kernel_unit_sched_z_reschedule
 * @see z_reschedule()
 */
ZTEST(sched_unit, test_p2w_irq_unlock_gives_cpu_to_woken_thread)
{
	unsigned int outer;
	k_spinlock_key_t key;

	/* The test needs preemptible threads (CONFIG_NUM_PREEMPT_PRIORITIES > 0). */
	if (!IS_ENABLED(CONFIG_PREEMPT_ENABLED)) {
		ztest_test_skip();
	}

	kernel_unit_contract_thread(&t1, 1);
	kernel_unit_contract_thread(&t3, 0);
	kernel_unit_contract_wait(&t3, &wq_a, K_FOREVER);
	kernel_unit_contract_start(&t1);

	outer = irq_lock();
	key = k_spin_lock(&test_lock);
	zassert_true(z_sched_wake(&wq_a, 0, NULL));
	z_reschedule(&test_lock, key);
	zassert_equal_ptr(_current, &t1, "z_reschedule() switched under the outer lock");
	irq_unlock(outer);

	zassert_false(kernel_unit_platform_locked());
	zassert_equal_ptr(_kernel.ready_q.cache, &t3);
	/* ZEP-SRS-2-9, reading L1: t3 runs at the end of the lock. */
	zassert_equal_ptr(_current, &t3, "P2-w: t1 keeps the CPU after irq_unlock()");
}

/*
 * Finding P7-a: a priority change of the current thread to its own priority
 * acts as a yield. Expected failure: the test asserts the requirement.
 */
ZTEST_EXPECT_FAIL(sched_unit, test_p7a_priority_set_to_same_priority_keeps_cpu);

/**
 * @brief A priority change to the same priority does not give the CPU to a peer.
 *
 * @details
 * Finding P7-a (property TieGoesToLongestReady, @c @@source ZEP-SRS-2-13,
 * reading R1: a priority change does not restart "ready").
 * - Setup: t1 and t3 with Zephyr priority 5, t1 ready first. t1 runs. With
 *   only cooperative priorities, both have the same cooperative priority,
 *   and ZEP-SRS-2-14 also asks that t1 keeps the CPU.
 * - Action: t1 calls k_thread_priority_set(t1, 5): the code of thread.c,
 *   z_thread_prio_set(), then z_reschedule_unlocked().
 * - Expected by the requirement (fails): t1 runs, because it has been ready
 *   longer than t3. The code puts t1 behind t3 and switches (the contract
 *   test test_prio_set_same_prio_on_itself_switches).
 *
 * @ingroup kernel_unit_sched_z_thread_prio_set
 * @see z_thread_prio_set(), z_reschedule_irqlock()
 */
ZTEST(sched_unit, test_p7a_priority_set_to_same_priority_keeps_cpu)
{
	kernel_unit_contract_thread(&t1, PRIO(5));
	kernel_unit_contract_thread(&t3, PRIO(5));
	kernel_unit_contract_start(&t1);
	zassert_equal_ptr(_kernel.ready_q.cache, &t1);

	kernel_unit_contract_set_prio(&t1, PRIO(5));

	/* ZEP-SRS-2-13, reading R1: t1 keeps the CPU. */
	zassert_equal_ptr(_current, &t1, "P7-a: the priority change acted as a yield");
}

/*
 * Finding P7-b: a priority change of another thread preempts a cooperative
 * thread. Expected failure: the test asserts the requirement.
 */
#ifdef CONFIG_COOP_ENABLED
ZTEST_EXPECT_FAIL(sched_unit, test_p7b_priority_change_of_other_thread_keeps_cooperative);
#endif

/**
 * @brief A priority change of another thread does not preempt a cooperative current thread.
 *
 * @details
 * Finding P7-b (property CoopKeepsCpu, @c @@source ZEP-SRS-2-14), the trace
 * of @c MCScheduler_p7_coop.
 * - Setup: Zephyr priorities t1 0, t2 -1, t3 -2 (t2 and t3 cooperative). With
 *   only cooperative priorities: t1 -1, t2 -2, t3 -3. t3 waits on wq_a. t2
 *   runs.
 * - Action: t2 gives wq_a (t3 is ready, t2 keeps the CPU: update_cache(0)
 *   keeps a cooperative current thread). Then t2 calls
 *   k_thread_priority_set(t1) with the priority of t1.
 * - Expected by the code (asserted first): after the give, t2 runs and the
 *   cache is t2.
 * - Expected by the requirement (fails): t2 still runs after the priority
 *   change. The code switches to t3: update_cache(1) skips the cooperative
 *   rule.
 *
 * @ingroup kernel_unit_sched_z_thread_prio_set
 * @see z_thread_prio_set(), z_sched_wake(), z_reschedule()
 */
ZTEST(sched_unit, test_p7b_priority_change_of_other_thread_keeps_cooperative)
{
	/* t1 is the lowest thread: preemptible, or cooperative without preemptible priorities. */
	int low = IS_ENABLED(CONFIG_PREEMPT_ENABLED) ? 0 : -1;

	/* The test needs cooperative threads (CONFIG_NUM_COOP_PRIORITIES > 0). */
	if (!IS_ENABLED(CONFIG_COOP_ENABLED)) {
		ztest_test_skip();
	}

	kernel_unit_contract_thread(&t1, low);
	kernel_unit_contract_thread(&t2, low - 1);
	kernel_unit_contract_thread(&t3, low - 2);
	kernel_unit_contract_wait(&t3, &wq_a, K_FOREVER);
	kernel_unit_contract_start(&t2);

	give_a();
	zassert_equal_ptr(_current, &t2);
	zassert_equal_ptr(_kernel.ready_q.cache, &t2);
	zassert_true(z_is_thread_ready(&t3));

	kernel_unit_contract_set_prio(&t1, low);

	/* ZEP-SRS-2-14: a cooperative thread runs until it yields or blocks. */
	zassert_equal_ptr(_current, &t2, "P7-b: the priority change of t1 preempted t2");
}

/*
 * Finding P7-c: an abort of another thread preempts a cooperative thread at
 * the next interrupt exit. Expected failure: the test asserts the requirement.
 * Not with arch_swap() and only cooperative priorities: then the interrupt
 * exit does not switch (exc_exit.c:57), and the test passes (see
 * test_isr_exit_switch_needs_preempt_enabled_or_use_switch).
 */
#if defined(CONFIG_COOP_ENABLED) && (defined(CONFIG_PREEMPT_ENABLED) || defined(CONFIG_USE_SWITCH))
ZTEST_EXPECT_FAIL(sched_unit, test_p7c_abort_of_other_thread_keeps_cooperative);
#endif

/**
 * @brief An abort of another thread does not preempt a cooperative current thread.
 *
 * @details
 * Finding P7-c (properties CoopKeepsCpu and RunRuleHolds,
 * @c @@source ZEP-SRS-2-14), the traces of @c MCScheduler_coop_rule and
 * @c MCScheduler_p7_abort.
 * - Setup: Zephyr priorities t1 0, t2 -1, t3 -2. With only cooperative
 *   priorities: t1 -1, t2 -2, t3 -3. t3 waits on wq_a. t2 runs and gives
 *   wq_a: t3 is ready, t2 keeps the CPU.
 * - Action: t2 calls k_thread_abort(t1). Then an interrupt without a kernel
 *   call comes (its exit is a reschedule point).
 * - Expected by the code (asserted first): after the abort, t1 is dead and t2
 *   still runs. The cache is t3 (update_cache(1) in halt_thread(), no
 *   reschedule; the contract test
 *   test_abort_of_other_thread_selects_head_at_next_point), so the invariant
 *   RunRuleHolds can be false until the interrupt.
 * - Expected by the requirement (fails): t2 still runs after the interrupt.
 *   With arch_swap() and only cooperative priorities the test passes: the
 *   exit of the interrupt does not switch (exc_exit.c:57).
 *
 * @ingroup kernel_unit_sched_z_thread_halt
 * @see z_thread_halt()
 */
ZTEST(sched_unit, test_p7c_abort_of_other_thread_keeps_cooperative)
{
	/* t1 is the lowest thread: preemptible, or cooperative without preemptible priorities. */
	int low = IS_ENABLED(CONFIG_PREEMPT_ENABLED) ? 0 : -1;

	/* The test needs cooperative threads (CONFIG_NUM_COOP_PRIORITIES > 0). */
	if (!IS_ENABLED(CONFIG_COOP_ENABLED)) {
		ztest_test_skip();
	}

	kernel_unit_contract_thread(&t1, low);
	kernel_unit_contract_thread(&t2, low - 1);
	kernel_unit_contract_thread(&t3, low - 2);
	kernel_unit_contract_wait(&t3, &wq_a, K_FOREVER);
	kernel_unit_contract_start(&t2);
	give_a();
	zassert_equal_ptr(_current, &t2);
	kernel_unit_contract_expect(KERNEL_UNIT_CONTRACT_RUN_RULE_HOLDS);

	kernel_unit_contract_abort(&t1);
	zassert_true(z_is_thread_dead(&t1));
	zassert_equal_ptr(_current, &t2);
	kernel_unit_contract_run_isr(NULL);

	/* ZEP-SRS-2-14: a cooperative thread runs until it yields or blocks. */
	zassert_equal_ptr(_current, &t2, "P7-c: the abort of t1 preempted t2");
}

/*
 * Finding F14: k_thread_abort() makes the joiners ready without a reschedule
 * point. Expected failure: the test asserts the requirement.
 */
#ifdef CONFIG_PREEMPT_ENABLED
ZTEST_EXPECT_FAIL(sched_unit, test_f14_abort_gives_cpu_to_higher_joiner);
#endif

/**
 * @brief An abort that makes a higher joiner ready gives it the CPU.
 *
 * @details
 * Finding F14 (property PreemptibleRunsHighest, @c @@source ZEP-SRS-2-9,
 * @c @@source ZEP-SRS-2-12), the trace of @c MCScheduler_f14_join.
 * - Setup: Zephyr priorities t1 1, t2 1, t3 0 (all preemptible). t3 waits on
 *   the join queue of t2 (k_thread_join(t2, K_FOREVER) in the past). t1 runs.
 * - Action: t1 calls k_thread_abort(t2).
 * - Expected by the code (asserted first): t2 is dead. t3 is ready with the
 *   return value 0 (unpend_all() of halt_thread()). The cache is t3, but
 *   z_thread_halt() releases the lock without a reschedule: RunRuleHolds is
 *   false.
 * - Expected by the requirement (fails): t3 runs at the end of the abort.
 *
 * @ingroup kernel_unit_sched_z_thread_halt
 * @see z_thread_halt()
 */
ZTEST(sched_unit, test_f14_abort_gives_cpu_to_higher_joiner)
{
	/* The test needs preemptible threads (CONFIG_NUM_PREEMPT_PRIORITIES > 0). */
	if (!IS_ENABLED(CONFIG_PREEMPT_ENABLED)) {
		ztest_test_skip();
	}

	kernel_unit_contract_thread(&t1, 1);
	kernel_unit_contract_thread(&t2, 1);
	kernel_unit_contract_thread(&t3, 0);
	kernel_unit_contract_wait(&t3, &t2.join_queue, K_FOREVER);
	kernel_unit_contract_start(&t1);
	kernel_unit_contract_expect(KERNEL_UNIT_CONTRACT_RUN_RULE_HOLDS);

	kernel_unit_contract_abort(&t2);

	zassert_true(z_is_thread_dead(&t2));
	zassert_true(z_is_thread_ready(&t3));
	zassert_equal(kernel_unit_contract_ret(&t3), 0);
	zassert_equal_ptr(_kernel.ready_q.cache, &t3);
	/* ZEP-SRS-2-9: a higher thread that becomes ready preempts t1. */
	zassert_equal_ptr(_current, &t3, "F14: t1 keeps the CPU after the abort");
}

#if !defined(CONFIG_USE_SWITCH) && defined(CONFIG_PREEMPT_ENABLED) && defined(CONFIG_COOP_ENABLED)
/*
 * Candidate finding SW-1: with arch_swap(), an ISR before PendSV gives the
 * CPU back to a cooperative thread that waits. Expected failure without
 * CONFIG_USE_SWITCH: the test asserts the requirement. With
 * CONFIG_USE_SWITCH, the switch has no gap and the test passes (the control).
 * The test needs a preemptible t1 and cooperative t2, t3: it is skipped in the
 * scenarios with one kind of priority.
 */
ZTEST_EXPECT_FAIL(sched_unit, test_sw1_blocked_cooperative_thread_loses_cpu);
#endif

/**
 * @brief A cooperative thread that waits loses the CPU to a higher ready thread.
 *
 * @details
 * Candidate finding SW-1 (property BlockedLosesCpu, @c @@source ZEP-SRS-2-12,
 * @c @@source ZEP-SRS-2-14), the trace of @c MCScheduler_gap_coop_pendsv.
 * - Setup: Zephyr priorities t1 0, t2 -1, t3 -2 (t2 and t3 cooperative). t3
 *   waits on wq_a. t2 runs. The environment: an interrupt that is pending
 *   when the switch of t2 unlocks the interrupts. Its ISR wakes all waiters
 *   of wq_a (t3, then t2) and calls z_reschedule().
 * - Action: t2 calls z_pend_curr() on wq_a with K_FOREVER.
 * - Expected by the requirement: t2 has blocked, so the next decision gives
 *   the CPU to the highest ready thread, t3. t3 runs before t2 runs again.
 * - Without @kconfig{CONFIG_USE_SWITCH} (fails): the ISR runs in the gap
 *   before PendSV. The wake of t2 makes t2 ready and cooperative again, so
 *   update_cache(0) keeps the cache at t2, and PendSV gives the CPU back to
 *   t2. z_pend_curr() returns 0 and t3 did not run.
 * - With @kconfig{CONFIG_USE_SWITCH} (passes, the control): the switch to t1
 *   comes at once, the ISR runs later, and its exit switches to t3. t2 then
 *   does not run again in the test (the check NO_RETURN is expected).
 *
 * @ingroup kernel_unit_sched_z_pend_curr
 * @see z_pend_curr()
 */
ZTEST(sched_unit, test_sw1_blocked_cooperative_thread_loses_cpu)
{
	k_spinlock_key_t key;
	bool t3_ran_first = false;

	/* The test needs preemptible threads (CONFIG_NUM_PREEMPT_PRIORITIES > 0). */
	if (!IS_ENABLED(CONFIG_PREEMPT_ENABLED)) {
		ztest_test_skip();
	}
	/* The test needs cooperative threads (CONFIG_NUM_COOP_PRIORITIES > 0). */
	if (!IS_ENABLED(CONFIG_COOP_ENABLED)) {
		ztest_test_skip();
	}

	kernel_unit_contract_thread(&t1, 0);
	kernel_unit_contract_thread(&t2, -1);
	kernel_unit_contract_thread(&t3, -2);
	kernel_unit_contract_wait(&t3, &wq_a, K_FOREVER);
	kernel_unit_contract_start(&t2);
	kernel_unit_platform_env_gap_isr(give_all_a, NULL);
	if (IS_ENABLED(CONFIG_USE_SWITCH)) {
		kernel_unit_contract_expect(KERNEL_UNIT_CONTRACT_NO_RETURN);
	}

	key = k_spin_lock(&test_lock);
	(void)z_pend_curr(&test_lock, key, &wq_a, K_FOREVER);

	for (size_t i = 0; i < kernel_unit_platform.n_switches; i++) {
		if (kernel_unit_platform.switches[i].to == &t2) {
			break;
		}
		if (kernel_unit_platform.switches[i].to == &t3) {
			t3_ran_first = true;
			break;
		}
	}
	/* ZEP-SRS-2-12 with 2-14: t2 blocked, so t3 runs before t2 runs again. */
	zassert_true(t3_ran_first, "SW-1: t2 got the CPU back before t3 ran");
}

/**
 * @brief An init of a wait queue with a waiter loses the waiter (undefined behavior).
 *
 * @details
 * Finding P6-u (fault model, property NoUndefined). No requirement or
 * document states the rule, so the test shows only the behavior of the
 * code, the first effect of the finding.
 * - Setup: t2 waits on wq_a. t1 runs.
 * - Action: z_waitq_init() of wq_a (the init function of an object, for
 *   example k_sem_init()).
 * - Expected: z_waitq_init() does not look at the waiters. The wait queue is
 *   empty, but t2 is still pending with @c pended_on set to wq_a. A wake of
 *   wq_a does not find t2: z_sched_wake() returns false.
 *
 * @ingroup kernel_unit_sched_static
 * @see z_waitq_init(), z_sched_wake()
 */
ZTEST(sched_unit, test_p6u_init_of_wait_queue_with_waiter_loses_it)
{
	kernel_unit_contract_thread(&t1, PRIO(5));
	kernel_unit_contract_thread(&t2, PRIO(6));
	kernel_unit_contract_wait(&t2, &wq_a, K_FOREVER);
	kernel_unit_contract_start(&t1);

	z_waitq_init(&wq_a);

	zassert_is_null(z_waitq_head(&wq_a));
	zassert_true(z_is_thread_pending(&t2));
	zassert_equal_ptr(t2.base.pended_on, &wq_a);
	zassert_false(z_sched_wake(&wq_a, 0, NULL));
	zassert_true(z_is_thread_pending(&t2));
}

/**
 * @brief A wake with a switch resets the time slice once with arch_swap() and twice with
 * CONFIG_USE_SWITCH.
 *
 * @details
 * Roadmap step 7, point 2 (the latency study: "do_swap() resets the slice
 * again, after update_cache()").
 * - Setup: t1 (Zephyr priority 5) runs. t2 (priority 3) waits on wq_a.
 * - Action: t1 gives wq_a: z_sched_wake(), then z_reschedule().
 * - Expected: t2 runs. The calls of z_time_slice_reset() with t2: 0 without
 *   @kconfig{CONFIG_TIMESLICING}; else 1 (update_cache() in ready_thread())
 *   without @kconfig{CONFIG_USE_SWITCH}, and 2 (also do_swap()) with it.
 *
 * @ingroup kernel_unit_sched_z_reschedule
 * @see z_reschedule(), z_sched_wake()
 */
ZTEST(sched_unit, test_wake_resets_time_slice_once_per_decision)
{
	unsigned int resets;

	/* The test needs preemptible threads (CONFIG_NUM_PREEMPT_PRIORITIES > 0). */
	if (!IS_ENABLED(CONFIG_PREEMPT_ENABLED)) {
		ztest_test_skip();
	}

	kernel_unit_contract_thread(&t1, 5);
	kernel_unit_contract_thread(&t2, 3);
	kernel_unit_contract_wait(&t2, &wq_a, K_FOREVER);
	kernel_unit_contract_start(&t1);

	give_a();

	zassert_equal_ptr(_current, &t2);
	if (!IS_ENABLED(CONFIG_TIMESLICING)) {
		resets = 0U;
	} else if (IS_ENABLED(CONFIG_USE_SWITCH)) {
		resets = 2U;
	} else {
		resets = 1U;
	}
	zassert_equal(z_time_slice_reset_fake.call_count, resets);
	for (unsigned int i = 0; i < resets; i++) {
		zassert_equal_ptr(z_time_slice_reset_fake.arg0_history[i], &t2);
	}
}

/**
 * @brief z_reschedule() switches with PendSV, or with arch_switch() with CONFIG_USE_SWITCH.
 *
 * @details
 * The two variants of the switch of Platform (UseSwitch).
 * - Setup: t1 (Zephyr priority 5) runs. t2 (priority 3) waits on wq_a.
 * - Action: t1 gives wq_a.
 * - Expected: one switch from t1 to t2. Without @kconfig{CONFIG_USE_SWITCH}
 *   z_reschedule() calls arch_swap() with the unlocked key, PendSV is
 *   pending once, and the switch is in PendSV. With it, z_reschedule() calls
 *   arch_switch() with the decision of do_swap(), and PendSV is never
 *   pending (NoPendSVWithSwitch).
 *
 * @ingroup kernel_unit_sched_z_reschedule
 * @see z_reschedule()
 */
ZTEST(sched_unit, test_reschedule_switch_follows_the_variant)
{
	/* The test needs preemptible threads (CONFIG_NUM_PREEMPT_PRIORITIES > 0). */
	if (!IS_ENABLED(CONFIG_PREEMPT_ENABLED)) {
		ztest_test_skip();
	}

	kernel_unit_contract_thread(&t1, 5);
	kernel_unit_contract_thread(&t2, 3);
	kernel_unit_contract_wait(&t2, &wq_a, K_FOREVER);
	kernel_unit_contract_start(&t1);

	give_a();

	zassert_equal_ptr(_current, &t2);
	zassert_equal(kernel_unit_platform.n_switches, 1U);
	zassert_equal_ptr(kernel_unit_platform.switches[0].from, &t1);
	zassert_equal_ptr(kernel_unit_platform.switches[0].to, &t2);
	if (IS_ENABLED(CONFIG_USE_SWITCH)) {
		zassert_equal(arch_switch_fake.call_count, 1U);
		zassert_equal(arch_swap_fake.call_count, 0U);
		zassert_equal(kernel_unit_platform.pendsv_requests, 0U);
		zassert_str_equal(kernel_unit_platform.switches[0].where, "arch_switch");
	} else {
		zassert_equal(arch_swap_fake.call_count, 1U);
		zassert_equal(arch_swap_fake.arg0_val, 0U);
		zassert_equal(kernel_unit_platform.pendsv_requests, 1U);
		zassert_str_equal(kernel_unit_platform.switches[0].where, "pendsv");
	}
	kernel_unit_contract_assert_ok();
}

/**
 * @brief k_sched_unlock() is a reschedule point: a thread that the lock kept out runs at once.
 *
 * @details
 * The contrast of finding P2-w (findings.md: "k_sched_unlock() reschedules,
 * scheduler.c:50, sched.c:413-417"). The other half, irq_unlock() is not a
 * reschedule point, is test_p2w_irq_unlock_gives_cpu_to_woken_thread.
 * - Setup: as P2-w: Zephyr priorities t1 1, t3 0 (both preemptible). t3
 *   waits on wq_a. t1 runs.
 * - Action: t1 calls k_sched_lock(). Then a give: k_spin_lock(),
 *   z_sched_wake() of wq_a, z_reschedule(). Then k_sched_unlock().
 * - Expected: under the scheduler lock, t1 is not preemptible: the give does
 *   not switch and the cache stays t1. k_sched_unlock() calls
 *   z_sched_lock_reschedule(): update_cache(0) sets the cache to t3, and
 *   reschedule() switches with the unlocked key. t3 runs after
 *   k_sched_unlock(), with the return value 0.
 *
 * @ingroup kernel_unit_sched_z_sched_lock_reschedule
 * @see k_sched_unlock(), z_sched_lock_reschedule()
 */
ZTEST(sched_unit, test_p2w_contrast_sched_unlock_reschedules_at_once)
{
	/* The test needs preemptible threads (CONFIG_NUM_PREEMPT_PRIORITIES > 0). */
	if (!IS_ENABLED(CONFIG_PREEMPT_ENABLED)) {
		ztest_test_skip();
	}

	kernel_unit_contract_thread(&t1, 1);
	kernel_unit_contract_thread(&t3, 0);
	kernel_unit_contract_wait(&t3, &wq_a, K_FOREVER);
	kernel_unit_contract_start(&t1);

	k_sched_lock();
	give_a();
	zassert_equal_ptr(_current, &t1, "the give switched under k_sched_lock()");
	zassert_equal_ptr(_kernel.ready_q.cache, &t1);
	zassert_true(z_is_thread_ready(&t3));
	k_sched_unlock();

	zassert_equal_ptr(_current, &t3, "k_sched_unlock() did not switch to t3");
	zassert_equal(kernel_unit_contract_ret(&t3), 0);
	zassert_equal(t1.base.sched_locked, 0U);
	kernel_unit_contract_assert_ok();
}

/**
 * @brief k_reschedule() after the outer irq_unlock() gives the CPU to the woken thread.
 *
 * @details
 * The condition of use that finding P2-w recommends: "call k_reschedule()
 * after the outer irq_unlock()". The API documentation of k_reschedule()
 * (ZEP-SRS-2-19) says "provided interrupts were not locked when invoked".
 * - Setup: as P2-w: t1 (1) runs, t3 (0) waits on wq_a.
 * - Action: t1 calls irq_lock(), gives wq_a, and calls k_reschedule() under
 *   the outer lock. Then irq_unlock(), then k_reschedule() again.
 * - Expected: the first k_reschedule() does not switch (resched() sees the
 *   locked key). After irq_unlock() t1 still runs (finding P2-w). The second
 *   k_reschedule() switches to t3.
 *
 * @ingroup kernel_unit_sched_z_sched_lock_reschedule
 * @see z_impl_k_reschedule(), z_sched_lock_reschedule()
 */
ZTEST(sched_unit, test_p2w_k_reschedule_after_irq_unlock_switches)
{
	unsigned int outer;

	/* The test needs preemptible threads (CONFIG_NUM_PREEMPT_PRIORITIES > 0). */
	if (!IS_ENABLED(CONFIG_PREEMPT_ENABLED)) {
		ztest_test_skip();
	}

	kernel_unit_contract_thread(&t1, 1);
	kernel_unit_contract_thread(&t3, 0);
	kernel_unit_contract_wait(&t3, &wq_a, K_FOREVER);
	kernel_unit_contract_start(&t1);

	outer = irq_lock();
	give_a();
	z_impl_k_reschedule();
	zassert_equal_ptr(_current, &t1, "k_reschedule() switched under the outer lock");
	irq_unlock(outer);
	zassert_equal_ptr(_current, &t1);
	zassert_equal_ptr(_kernel.ready_q.cache, &t3);

	z_impl_k_reschedule();

	zassert_equal_ptr(_current, &t3, "k_reschedule() did not switch to t3");
	kernel_unit_contract_assert_ok();
}

/**
 * @brief The exit of an interrupt switches a cooperative thread only with PREEMPT_ENABLED or
 * CONFIG_USE_SWITCH.
 *
 * @details
 * Open point 5 of the Platform round A (@c tla/platform-round-a.md). Without
 * @kconfig{CONFIG_PREEMPT_ENABLED} (@kconfig{CONFIG_NUM_PREEMPT_PRIORITIES}
 * = 0), z_arm_exc_exit() does not set PendSV pending (exc_exit.c:57-61).
 * The exit of the @kconfig{CONFIG_USE_SWITCH} variant (arm_m_must_switch(),
 * arm-m-switch.c:510-536) has no such condition.
 * - Setup: Zephyr priorities t1 -1, t2 -2, t3 -1 (all cooperative). t1 runs.
 *   t1 calls z_thread_prio_set(t3, -1): update_cache(1) sets the cache to
 *   t2, the head of the run queue (as in P7-b and P7-c).
 * - Action: an interrupt without a kernel call.
 * - Expected with @kconfig{CONFIG_PREEMPT_ENABLED} or
 *   @kconfig{CONFIG_USE_SWITCH}: the exit switches to t2 (PendSV, or the
 *   exit itself).
 * - Expected with arch_swap() and only cooperative priorities: t1 keeps the
 *   CPU, PendSV is not pending, and the cache stays t2 (RunRuleHolds is
 *   false until t1 blocks or yields).
 *
 * @ingroup kernel_unit_sched_z_thread_prio_set
 * @see z_thread_prio_set()
 */
ZTEST(sched_unit, test_isr_exit_switch_needs_preempt_enabled_or_use_switch)
{
	bool exit_switches = IS_ENABLED(CONFIG_PREEMPT_ENABLED) || IS_ENABLED(CONFIG_USE_SWITCH);

	/* The test needs cooperative threads (CONFIG_NUM_COOP_PRIORITIES > 0). */
	if (!IS_ENABLED(CONFIG_COOP_ENABLED)) {
		ztest_test_skip();
	}

	kernel_unit_contract_thread(&t1, -1);
	kernel_unit_contract_thread(&t2, -2);
	kernel_unit_contract_thread(&t3, -1);
	kernel_unit_contract_start(&t1);
	kernel_unit_contract_expect(KERNEL_UNIT_CONTRACT_RUN_RULE_HOLDS);
	zassert_true(z_thread_prio_set(&t3, -1));
	zassert_equal_ptr(_current, &t1);
	zassert_equal_ptr(_kernel.ready_q.cache, &t2);

	kernel_unit_contract_run_isr(NULL);

	if (exit_switches) {
		zassert_equal_ptr(_current, &t2);
		zassert_equal(kernel_unit_platform.n_switches, 1U);
		zassert_str_equal(kernel_unit_platform.switches[0].where,
				  IS_ENABLED(CONFIG_USE_SWITCH) ? "isr exit" : "pendsv");
	} else {
		zassert_equal_ptr(_current, &t1, "the exit switched without PREEMPT_ENABLED");
		zassert_equal(kernel_unit_platform.n_switches, 0U);
		zassert_equal(kernel_unit_platform.pendsv_requests, 0U);
		zassert_equal_ptr(_kernel.ready_q.cache, &t2);
	}
}

/**
 * @brief A thread that an ISR wakes leaves the idle thread at the exit, or by the idle loop.
 *
 * @details
 * The second effect of exc_exit.c:57: without
 * @kconfig{CONFIG_PREEMPT_ENABLED} and without @kconfig{CONFIG_USE_SWITCH},
 * the exit of an ISR does not leave the idle thread either. The idle loop
 * switches itself (idle.c:90-105, an @c \@assumption of the platform model).
 * - Setup: t1 runs alone (Zephyr priority 5, or a cooperative priority). An
 *   ISR gives wq_a.
 * - Action: t1 waits on wq_a with K_FOREVER (z_pend_curr()).
 * - Expected: z_pend_curr() returns 0, and t1 runs. Two switches: t1 to the
 *   idle thread, then the idle thread to t1. The second switch is at the
 *   exit of the ISR with @kconfig{CONFIG_USE_SWITCH} ("isr exit"), in PendSV
 *   from the exit with @kconfig{CONFIG_PREEMPT_ENABLED} ("pendsv"), else in
 *   PendSV after one yield of the idle loop ("idle").
 *
 * @ingroup kernel_unit_sched_z_pend_curr
 * @see z_pend_curr()
 */
ZTEST(sched_unit, test_isr_wake_leaves_idle_by_exit_or_idle_loop)
{
	k_spinlock_key_t key;
	const char *where;
	unsigned int yields = 0U;

	kernel_unit_contract_thread(&t1, PRIO(5));
	kernel_unit_contract_start(&t1);
	kernel_unit_platform_env_isr(isr_give_a, NULL);

	key = k_spin_lock(&test_lock);
	zassert_equal(z_pend_curr(&test_lock, key, &wq_a, K_FOREVER), 0);

	if (IS_ENABLED(CONFIG_USE_SWITCH)) {
		where = "isr exit";
	} else if (IS_ENABLED(CONFIG_PREEMPT_ENABLED)) {
		where = "pendsv";
	} else {
		where = "idle";
		yields = 1U;
	}
	zassert_equal_ptr(_current, &t1);
	zassert_equal(kernel_unit_platform.n_switches, 2U);
	zassert_equal_ptr(kernel_unit_platform.switches[1].from, idle_thread());
	zassert_equal_ptr(kernel_unit_platform.switches[1].to, &t1);
	zassert_str_equal(kernel_unit_platform.switches[1].where, where);
	zassert_equal(kernel_unit_platform.idle_yields, yields);
	kernel_unit_contract_assert_ok();
}
