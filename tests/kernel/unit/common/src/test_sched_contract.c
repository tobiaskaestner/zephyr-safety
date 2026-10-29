/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @defgroup kernel_unit_sched_contract Contract tests of the scheduler (layer A)
 * @ingroup kernel_unit_tests
 * @brief The same tests against the reference fake and against the real kernel/sched.c.
 *
 * Each test runs the steps of an example of @c mc/SchedulerTest.tla, or of an
 * action of @c lib/Scheduler.tla that the objects use, and checks the same
 * results. Two applications build this source:
 *
 * - @c sched_ref: the scheduler is the reference fake (fake group
 *   @c sched_ref). The calls of layer A are the FFF fakes of the group
 *   @c sched with the reference fake.
 * - @c sched: the scheduler is the real @c kernel/sched.c with its real
 *   headers, on the model of the platform (model group @c platform).
 *
 * The adapter (@c common/include/kernel_unit_sched_contract.h) makes the setup and
 * the queries that differ. A difference between the two schedulers is a
 * failing test. A known difference of the reference fake has
 * ZTEST_EXPECT_FAIL() only in the build of @c sched_ref, with the id of the
 * difference (workspace notes, @c claude/kernel-unit/unit-tests/sched-app.md).
 *
 * Priorities are Zephyr priorities: a lower number is a higher priority, a
 * negative number is a cooperative thread. The run queue order of a test is
 * the order of kernel_unit_contract_thread() for each priority. In the names
 * of SchedulerTest, Z(a, b, c) are the priorities of t1, t2, t3 and Q(a, b, c)
 * their positions in the run queue.
 */

/**
 * @defgroup kernel_unit_sched_contract_choices Selection rule (Choices, CacheOf)
 * @ingroup kernel_unit_sched_contract
 * @brief The thread that the next reschedule point selects, in fixed states.
 *
 * Each test is one check of TestChoicesUp or TestChoicesPreemptOk of
 * @c mc/SchedulerTest.tla, with the same name in the details.
 */

/**
 * @defgroup kernel_unit_sched_contract_release Reschedule points (Release)
 * @ingroup kernel_unit_sched_contract
 * @brief z_reschedule() in a thread, under an outer interrupt lock and in an ISR (TestResched).
 */

/**
 * @defgroup kernel_unit_sched_contract_wait Wait and wakes
 * @ingroup kernel_unit_sched_contract
 * @brief PendCurr, Resume, WakeFirst, WakeFirstWith, WakeAll, UnpendAll, Head, WaitqInit, PrioSet.
 */

/**
 * @defgroup kernel_unit_sched_contract_env Environment
 * @ingroup kernel_unit_sched_contract
 * @brief ThreadTimeout, Abort, Join and SetPrio.
 */

#include <setjmp.h>
#include <string.h>
#include <zephyr/ztest.h>
#include <zephyr/spinlock.h>
#include <ksched.h>
#include <kthread.h>
#include <wait_q.h>
#include <timeout_q.h>
#include <kernel_arch_interface.h>
#include <kernel_unit_sched_contract.h>
#include <fakes/fatal.h>
#ifdef CONFIG_ASSERT
#include <fakes/assert.h>
#endif

/* Timeouts that are not K_NO_WAIT and not K_FOREVER */
#define TEST_TIMEOUT K_TICKS(10)

/* Swap data that a waker gives */
#define DATA(n) ((void *)(uintptr_t)(0x1000U + (n)))

static struct k_thread t1;
static struct k_thread t2;
static struct k_thread t3;
static struct k_thread t4;
static _wait_q_t wq_a;
static _wait_q_t wq_b;

/* The lock of the "object" of the tests. */
static struct k_spinlock lock;

static void contract_before(void *fixture)
{
	ARG_UNUSED(fixture);

	kernel_unit_contract_setup();
	z_waitq_init(&wq_a);
	z_waitq_init(&wq_b);
}

/*
 * A failed __ASSERT() of the scheduler code stops the run (ztest cannot fail
 * a test in the phase "after", it stops). With CONFIG_ASSERT_TEST the hook is
 * a fake that returns, so without this check no test sees the assertion.
 */
static void contract_after(void *fixture)
{
	ARG_UNUSED(fixture);

#ifdef CONFIG_ASSERT
	if (assert_post_action_fake.call_count != 0U) {
		TC_PRINT("%u failed __ASSERT() in the test\n", assert_post_action_fake.call_count);
		ztest_test_fail();
	}
#endif
}

ZTEST_SUITE(sched_contract, NULL, NULL, contract_before, contract_after, NULL);

/* Add three ready threads with these Zephyr priorities, in the order t1, t2, t3. */
static void three_threads(int p1, int p2, int p3)
{
	kernel_unit_contract_thread(&t1, p1);
	kernel_unit_contract_thread(&t2, p2);
	kernel_unit_contract_thread(&t3, p3);
}

/* Assert the waiters of a wait queue, head first. */
static void assert_waiters(_wait_q_t *wait_q, struct k_thread *const *want, size_t n)
{
	struct k_thread *got[8];

	zassert_equal(kernel_unit_contract_waiters(wait_q, got, ARRAY_SIZE(got)), n);
	for (size_t i = 0; i < n; i++) {
		zassert_equal_ptr(got[i], want[i], "waiter %zu", i);
	}
}

/* A give of an object: the wake of the first waiter of wq_a with 0, and the reschedule. */
static void give_a(void)
{
	k_spinlock_key_t key = k_spin_lock(&lock);

	(void)z_sched_wake(&wq_a, 0, DATA(1));
	z_reschedule(&lock, key);
}

/* ------------------------------------------------------------------------- */

/**
 * @brief A ready thread with a higher priority is the choice.
 *
 * @details
 * - Setup: Z(1, 0, 2). t1 runs. ("up: higher preempts")
 * - Expected: the next thread is t2.
 *
 * @ingroup kernel_unit_sched_contract_choices
 */
ZTEST(sched_contract, test_choice_higher_preempts)
{
	three_threads(1, 0, 2);
	kernel_unit_contract_start(&t1);

	zassert_equal_ptr(kernel_unit_contract_next(), &t2);
}

/**
 * @brief Threads with a lower priority do not preempt.
 *
 * @details
 * - Setup: Z(0, 1, 2). t1 runs. ("up: lower does not preempt")
 * - Expected: the next thread is t1.
 *
 * @ingroup kernel_unit_sched_contract_choices
 */
ZTEST(sched_contract, test_choice_lower_does_not_preempt)
{
	three_threads(0, 1, 2);
	kernel_unit_contract_start(&t1);

	zassert_equal_ptr(kernel_unit_contract_next(), &t1);
	kernel_unit_contract_assert_ok();
}

/**
 * @brief The current thread at the head of the run queue wins a tie.
 *
 * @details
 * - Setup: Z(0, 0, 1), Q(1, 2, 3). t1 runs. ("up: current at the head wins a
 *   tie")
 * - Expected: the next thread is t1.
 *
 * @ingroup kernel_unit_sched_contract_choices
 */
ZTEST(sched_contract, test_choice_current_at_head_wins_tie)
{
	three_threads(0, 0, 1);
	kernel_unit_contract_start(&t1);

	zassert_equal_ptr(kernel_unit_contract_next(), &t1);
	kernel_unit_contract_assert_ok();
}

#ifdef KERNEL_UNIT_FAKE_GROUP_sched_ref
/*
 * Difference RF-3 (sched-app.md): the reference fake lets the current thread
 * win each tie (kernel_unit_sched_ref_choices()). The contract (CacheOf) and
 * the code take the head of the run queue.
 */
ZTEST_EXPECT_FAIL(sched_contract, test_choice_current_behind_peer_loses_tie);
#endif

/**
 * @brief A preemptible current thread behind a peer in the run queue loses the tie.
 *
 * @details
 * - Setup: Z(0, 0, 1), Q(2, 1, 3): t2 is ready before t1. t1 runs. ("up:
 *   current behind a peer loses a tie")
 * - Expected: the next thread is t2 (the head of the run queue).
 *
 * @ingroup kernel_unit_sched_contract_choices
 */
ZTEST(sched_contract, test_choice_current_behind_peer_loses_tie)
{
	kernel_unit_contract_thread(&t2, 0);
	kernel_unit_contract_thread(&t1, 0);
	kernel_unit_contract_thread(&t3, 1);
	kernel_unit_contract_start(&t1);

	zassert_equal_ptr(kernel_unit_contract_next(), &t2);
}

/**
 * @brief A ready cooperative current thread keeps the CPU against a higher priority.
 *
 * @details
 * - Setup: Z(-1, -2, 0). t1 runs. ("up: coop keeps the CPU")
 * - Expected: the next thread is t1.
 *
 * @ingroup kernel_unit_sched_contract_choices
 */
ZTEST(sched_contract, test_choice_coop_keeps_cpu)
{
	three_threads(-1, -2, 0);
	kernel_unit_contract_start(&t1);

	zassert_equal_ptr(kernel_unit_contract_next(), &t1);
	kernel_unit_contract_assert_ok();
}

/**
 * @brief A cooperative current thread behind a peer keeps the CPU.
 *
 * @details
 * - Setup: Z(-1, -1, 0), Q(2, 1, 3). t1 runs. ("up: coop behind a peer keeps
 *   the CPU")
 * - Expected: the next thread is t1.
 *
 * @ingroup kernel_unit_sched_contract_choices
 */
ZTEST(sched_contract, test_choice_coop_behind_peer_keeps_cpu)
{
	kernel_unit_contract_thread(&t2, -1);
	kernel_unit_contract_thread(&t1, -1);
	kernel_unit_contract_thread(&t3, 0);
	kernel_unit_contract_start(&t1);

	zassert_equal_ptr(kernel_unit_contract_next(), &t1);
	kernel_unit_contract_assert_ok();
}

/**
 * @brief A cooperative thread preempts a preemptible current thread.
 *
 * @details
 * - Setup: Z(0, -1, 1). t1 runs. ("up: coop preempts a preemptible")
 * - Expected: the next thread is t2.
 *
 * @ingroup kernel_unit_sched_contract_choices
 */
ZTEST(sched_contract, test_choice_coop_preempts_preemptible)
{
	three_threads(0, -1, 1);
	kernel_unit_contract_start(&t1);

	zassert_equal_ptr(kernel_unit_contract_next(), &t2);
}

/**
 * @brief A cooperative current thread that waits leaves the CPU.
 *
 * @details
 * - Setup: Z(-1, 0, 1). t1 runs, then waits on wq_a (the state inside
 *   z_pend_curr() before the switch). ("up: pending coop leaves")
 * - Expected: the next thread is t2.
 *
 * @ingroup kernel_unit_sched_contract_choices
 */
ZTEST(sched_contract, test_choice_pending_coop_leaves)
{
	three_threads(-1, 0, 1);
	kernel_unit_contract_start(&t1);
	kernel_unit_contract_wait(&t1, &wq_a, K_FOREVER);

	zassert_equal_ptr(kernel_unit_contract_next(), &t2);
}

/**
 * @brief After a wait, the head of the run queue wins a tie.
 *
 * @details
 * - Setup: Z(0, 1, 1), Q(0, 2, 1): t3 is ready before t2. t1 runs, then
 *   waits on wq_a. ("up: head of a tie after a wait")
 * - Expected: the next thread is t3.
 *
 * @ingroup kernel_unit_sched_contract_choices
 */
ZTEST(sched_contract, test_choice_head_of_tie_after_wait)
{
	kernel_unit_contract_thread(&t1, 0);
	kernel_unit_contract_thread(&t3, 1);
	kernel_unit_contract_thread(&t2, 1);
	kernel_unit_contract_start(&t1);
	kernel_unit_contract_wait(&t1, &wq_a, K_FOREVER);

	zassert_equal_ptr(kernel_unit_contract_next(), &t3);
}

/**
 * @brief If no thread is ready, the idle thread is the choice.
 *
 * @details
 * - Setup: Z(0, 0, 0). t2 and t3 wait. t1 runs, then waits. ("up: idle if no
 *   thread is ready")
 * - Expected: the next thread is the idle thread (NULL).
 *
 * @ingroup kernel_unit_sched_contract_choices
 */
ZTEST(sched_contract, test_choice_idle_if_no_thread_ready)
{
	three_threads(0, 0, 0);
	kernel_unit_contract_start(&t1);
	kernel_unit_contract_wait(&t2, &wq_a, K_FOREVER);
	kernel_unit_contract_wait(&t3, &wq_a, K_FOREVER);
	kernel_unit_contract_wait(&t1, &wq_a, K_FOREVER);

	zassert_is_null(kernel_unit_contract_next());
}

/**
 * @brief The idle thread leaves the CPU to the highest ready thread.
 *
 * @details
 * - Setup: Z(2, 1, 0). The idle thread runs. ("up: idle leaves")
 * - Expected: the next thread is t3.
 *
 * @ingroup kernel_unit_sched_contract_choices
 */
ZTEST(sched_contract, test_choice_idle_leaves)
{
	three_threads(2, 1, 0);
	kernel_unit_contract_start(NULL);

	zassert_equal_ptr(kernel_unit_contract_next(), &t3);
}

/**
 * @brief A priority change of the current thread to its own priority puts it behind its peer.
 *
 * @details
 * The descriptive side of finding P7-a.
 * - Setup: Z(5, 9, 5), Q(1, 3, 2). t1 runs.
 * - Action: z_thread_prio_set(t1, 5) (no reschedule).
 * - Expected: the return value is true (t1 is ready). t1 still runs. The next
 *   thread is t3. ("preempt_ok: same prio on itself switches")
 *
 * @ingroup kernel_unit_sched_contract_choices
 */
ZTEST(sched_contract, test_prio_set_same_prio_on_itself_switches)
{
	kernel_unit_contract_thread(&t1, 5);
	kernel_unit_contract_thread(&t3, 5);
	kernel_unit_contract_thread(&t2, 9);
	kernel_unit_contract_start(&t1);

	zassert_true(z_thread_prio_set(&t1, 5));

	zassert_equal_ptr(kernel_unit_contract_current(), &t1);
	zassert_equal_ptr(kernel_unit_contract_next(), &t3);
}

/**
 * @brief A priority change of another thread lets a higher thread preempt a cooperative thread.
 *
 * @details
 * The descriptive side of finding P7-b.
 * - Setup: Z(-1, -2, 3). t1 runs (it keeps the CPU against t2).
 * - Action: z_thread_prio_set(t3, 3).
 * - Expected: t1 still runs. The next thread is t2 (update_cache(1) skips
 *   the rule for cooperative threads). ("preempt_ok: coop loses the CPU to
 *   a higher thread")
 *
 * @ingroup kernel_unit_sched_contract_choices
 */
ZTEST(sched_contract, test_prio_set_of_other_lets_higher_preempt_coop)
{
	three_threads(-1, -2, 3);
	kernel_unit_contract_start(&t1);
	zassert_equal_ptr(kernel_unit_contract_next(), &t1);

	zassert_true(z_thread_prio_set(&t3, 3));

	zassert_equal_ptr(kernel_unit_contract_current(), &t1);
	zassert_equal_ptr(kernel_unit_contract_next(), &t2);
}

/**
 * @brief A priority change of a peer keeps the current thread at the head.
 *
 * @details
 * - Setup: Z(5, 5, 9). t1 runs.
 * - Action: z_thread_prio_set(t2, 5).
 * - Expected: the next thread is t1. ("preempt_ok: requeue of a peer keeps
 *   the current thread")
 *
 * @ingroup kernel_unit_sched_contract_choices
 */
ZTEST(sched_contract, test_prio_set_of_peer_keeps_current)
{
	three_threads(5, 5, 9);
	kernel_unit_contract_start(&t1);

	zassert_true(z_thread_prio_set(&t2, 5));

	zassert_equal_ptr(kernel_unit_contract_next(), &t1);
	kernel_unit_contract_assert_ok();
}

/* ------------------------------------------------------------------------- */

/* The state of the reschedule tests: t1 (5) runs, t2 (3) waits on wq_a. */
static void t1_runs_t2_waits(void)
{
	kernel_unit_contract_thread(&t1, 5);
	kernel_unit_contract_thread(&t2, 3);
	kernel_unit_contract_wait(&t2, &wq_a, K_FOREVER);
	kernel_unit_contract_start(&t1);
}

/**
 * @brief A wake and z_reschedule() in a thread switch to the woken higher thread.
 *
 * @details
 * WakeFirst, then Release(a, "resched") with ReschedOk ("resched: thread, no
 * outer lock").
 * - Setup: t1 (5) runs. t2 (3) waits on wq_a.
 * - Action: t1 locks, z_sched_wake(wq_a, 0, data), z_reschedule().
 * - Expected: z_sched_wake() returns true. t2 runs, with the return value 0
 *   and the data.
 *
 * @ingroup kernel_unit_sched_contract_release
 */
ZTEST(sched_contract, test_reschedule_switches_to_woken_higher_thread)
{
	k_spinlock_key_t key;

	t1_runs_t2_waits();
	kernel_unit_contract_assert_ok();

	key = k_spin_lock(&lock);
	zassert_true(z_sched_wake(&wq_a, 0, DATA(1)));
	z_reschedule(&lock, key);

	zassert_equal_ptr(kernel_unit_contract_current(), &t2);
	zassert_equal(kernel_unit_contract_ret(&t2), 0);
	zassert_equal_ptr(t2.base.swap_data, DATA(1));
	zassert_false(z_is_thread_pending(&t2));
	kernel_unit_contract_assert_ok();
}

#ifdef KERNEL_UNIT_FAKE_GROUP_sched_ref
/*
 * Difference RF-2 (findings.md, sched-app.md): ref_reschedule() does not read
 * the key, so the reference fake switches under the outer lock. The contract
 * (ReschedOk) and the code do not.
 */
ZTEST_EXPECT_FAIL(sched_contract, test_reschedule_under_outer_lock_does_not_switch);
#endif

/**
 * @brief Under an outer interrupt lock, z_reschedule() does not switch.
 *
 * @details
 * ReschedOk ("resched: thread, outer lock"): resched() of z_reschedule()
 * reads the key of the lock. Under an outer irq_lock() the key is locked.
 * - Setup: t1 (5) runs. t2 (3) waits on wq_a.
 * - Action: t1 calls irq_lock(), then locks, wakes wq_a and calls
 *   z_reschedule(). Then irq_unlock().
 * - Expected: t1 still runs after z_reschedule(). The next thread is t2.
 *
 * @ingroup kernel_unit_sched_contract_release
 */
ZTEST(sched_contract, test_reschedule_under_outer_lock_does_not_switch)
{
	unsigned int outer;
	k_spinlock_key_t key;

	t1_runs_t2_waits();

	outer = irq_lock();
	key = k_spin_lock(&lock);
	zassert_true(z_sched_wake(&wq_a, 0, DATA(1)));
	z_reschedule(&lock, key);
	zassert_equal_ptr(kernel_unit_contract_current(), &t1);
	zassert_equal_ptr(kernel_unit_contract_next(), &t2);
	irq_unlock(outer);
}

/* The thread that ran in the ISR of the last test. */
static struct k_thread *current_in_isr;

static void isr_give_a(void)
{
	give_a();
	current_in_isr = kernel_unit_contract_current();
}

/**
 * @brief In an ISR, z_reschedule() does not switch. The exit of the ISR does.
 *
 * @details
 * Release of an ISR ("resched: isr"): the exit of the ISR is the reschedule
 * point.
 * - Setup: t1 (5) runs. t2 (3) waits on wq_a.
 * - Action: an ISR wakes wq_a and calls z_reschedule().
 * - Expected: in the ISR, t1 is still the current thread. After the exit of
 *   the ISR, t2 runs.
 *
 * @ingroup kernel_unit_sched_contract_release
 */
ZTEST(sched_contract, test_reschedule_in_isr_selects_at_exit)
{
	t1_runs_t2_waits();
	current_in_isr = NULL;

	kernel_unit_contract_run_isr(isr_give_a);

	zassert_equal_ptr(current_in_isr, &t1);
	zassert_equal_ptr(kernel_unit_contract_current(), &t2);
	kernel_unit_contract_assert_ok();
}

/* ------------------------------------------------------------------------- */

/* The state of t1 that an environment action saw. */
static bool t1_was_pending;
static bool t1_had_preset;

static void observe_t1_then_give(void)
{
	t1_was_pending = z_is_thread_pending(&t1) && (z_waitq_head(&wq_a) == &t1);
	t1_had_preset = (kernel_unit_contract_ret(&t1) == -EAGAIN);
	give_a();
}

/**
 * @brief While a thread waits, it is the head of its wait queue with -EAGAIN; a wake ends the wait.
 *
 * @details
 * PendCurr, PendingIsQueued, WakeFirst and Resume.
 * - Setup: t1 (5) runs, t2 (7) is ready. The environment: t2 records the
 *   state of t1, then gives wq_a.
 * - Action: t1 calls z_pend_curr() on wq_a with K_FOREVER.
 * - Expected: during the wait, t1 is pending, the head of wq_a, and has the
 *   return value -EAGAIN. z_pend_curr() returns 0, the swap data is the data
 *   of the wake, and t1 runs.
 *
 * @ingroup kernel_unit_sched_contract_wait
 */
ZTEST(sched_contract, test_pend_presets_eagain_until_wake)
{
	k_spinlock_key_t key;

	kernel_unit_contract_thread(&t1, 5);
	kernel_unit_contract_thread(&t2, 7);
	kernel_unit_contract_start(&t1);
	kernel_unit_contract_env_thread(&t2, observe_t1_then_give);
	t1_was_pending = false;
	t1_had_preset = false;

	key = k_spin_lock(&lock);
	zassert_equal(z_pend_curr(&lock, key, &wq_a, K_FOREVER), 0);

	zassert_true(t1_was_pending);
	zassert_true(t1_had_preset);
	zassert_equal_ptr(t1.base.swap_data, DATA(1));
	zassert_equal_ptr(kernel_unit_contract_current(), &t1);
	zassert_is_null(t1.base.pended_on);
	kernel_unit_contract_assert_ok();
}

/**
 * @brief The wakes take the waiters by priority, then by the order of arrival.
 *
 * @details
 * WakeFirst and the order rule WaitQueue!Before.
 * - Setup: t1 (5) runs. t2 (6), t3 (4) and t4 (4) wait on wq_a, in this
 *   order.
 * - Action: three z_sched_wake() on wq_a, then z_reschedule().
 * - Expected: the waiters are t3, t4, t2. Each wake takes the head. Then t3
 *   runs (t3 became ready before t4).
 *
 * @ingroup kernel_unit_sched_contract_wait
 */
ZTEST(sched_contract, test_wake_order_priority_then_arrival)
{
	static struct k_thread *const order[] = {&t3, &t4, &t2};
	k_spinlock_key_t key;

	kernel_unit_contract_thread(&t1, 5);
	kernel_unit_contract_thread(&t2, 6);
	kernel_unit_contract_thread(&t3, 4);
	kernel_unit_contract_thread(&t4, 4);
	kernel_unit_contract_wait(&t2, &wq_a, K_FOREVER);
	kernel_unit_contract_wait(&t3, &wq_a, K_FOREVER);
	kernel_unit_contract_wait(&t4, &wq_a, K_FOREVER);
	kernel_unit_contract_start(&t1);
	assert_waiters(&wq_a, order, ARRAY_SIZE(order));

	key = k_spin_lock(&lock);
	for (size_t i = 0; i < ARRAY_SIZE(order); i++) {
		zassert_true(z_sched_wake(&wq_a, 0, NULL));
		zassert_false(z_is_thread_pending(order[i]), "wake %zu", i);
		for (size_t j = i + 1U; j < ARRAY_SIZE(order); j++) {
			zassert_true(z_is_thread_pending(order[j]), "wake %zu", i);
		}
	}
	z_reschedule(&lock, key);

	zassert_equal_ptr(kernel_unit_contract_current(), &t3);
	kernel_unit_contract_assert_ok();
}

/**
 * @brief A wake on an empty wait queue returns false and changes nothing.
 *
 * @details
 * WakeFirst is enabled only if HasWaiters(o).
 * - Setup: t1 (5) runs, t2 (6) is ready. wq_a is empty.
 * - Action: z_sched_wake() on wq_a, then z_reschedule().
 * - Expected: false. t1 runs, t2 is ready.
 *
 * @ingroup kernel_unit_sched_contract_wait
 */
ZTEST(sched_contract, test_wake_on_empty_queue_returns_false)
{
	k_spinlock_key_t key;

	kernel_unit_contract_thread(&t1, 5);
	kernel_unit_contract_thread(&t2, 6);
	kernel_unit_contract_start(&t1);

	key = k_spin_lock(&lock);
	zassert_false(z_sched_wake(&wq_a, 0, NULL));
	z_reschedule(&lock, key);

	zassert_equal_ptr(kernel_unit_contract_current(), &t1);
	zassert_true(z_is_thread_ready(&t2));
	kernel_unit_contract_assert_ok();
}

/**
 * @brief A wake in a loop wakes each waiter with the same value and data.
 *
 * @details
 * WakeAll (the loop of z_sched_wake_all()).
 * - Setup: t1 (5) runs. t2 (3) and t3 (3) wait on wq_a.
 * - Action: z_sched_wake() until it returns false, then z_reschedule().
 * - Expected: two wakes. t2 and t3 are ready with 0 and the data. t2 runs
 *   (it became ready first).
 *
 * @ingroup kernel_unit_sched_contract_wait
 */
ZTEST(sched_contract, test_wake_all_wakes_each_waiter)
{
	k_spinlock_key_t key;
	unsigned int woken = 0U;

	kernel_unit_contract_thread(&t1, 5);
	kernel_unit_contract_thread(&t2, 3);
	kernel_unit_contract_thread(&t3, 3);
	kernel_unit_contract_wait(&t2, &wq_a, K_FOREVER);
	kernel_unit_contract_wait(&t3, &wq_a, K_FOREVER);
	kernel_unit_contract_start(&t1);

	key = k_spin_lock(&lock);
	while (z_sched_wake(&wq_a, 0, DATA(2))) {
		woken++;
	}
	z_reschedule(&lock, key);

	zassert_equal(woken, 2U);
	zassert_equal(kernel_unit_contract_ret(&t3), 0);
	zassert_equal_ptr(t2.base.swap_data, DATA(2));
	zassert_equal_ptr(t3.base.swap_data, DATA(2));
	zassert_equal_ptr(kernel_unit_contract_current(), &t2);
	kernel_unit_contract_assert_ok();
}

/**
 * @brief z_unpend_all() makes all waiters ready with -EAGAIN and cancels their timeouts.
 *
 * @details
 * UnpendAll (proposal P4 of the review of the reference fake).
 * - Setup: t1 (5) runs. t2 (3) waits on wq_a with a timeout, t3 (4) without.
 * - Action: z_unpend_all() on wq_a.
 * - Expected: the return value is 1. t2 and t3 are ready, keep the return
 *   value -EAGAIN, and have no armed timeout. The next thread is t2. Skip if
 *   the scheduler has no z_unpend_all() (the reference fake).
 *
 * @ingroup kernel_unit_sched_contract_wait
 */
ZTEST(sched_contract, test_unpend_all_keeps_eagain_and_cancels_timeouts)
{
	int ret;

	kernel_unit_contract_thread(&t1, 5);
	kernel_unit_contract_thread(&t2, 3);
	kernel_unit_contract_thread(&t3, 4);
	kernel_unit_contract_wait(&t2, &wq_a, TEST_TIMEOUT);
	kernel_unit_contract_wait(&t3, &wq_a, K_FOREVER);
	kernel_unit_contract_start(&t1);
	zassert_false(z_is_inactive_timeout(&t2.base.timeout));

	ret = kernel_unit_contract_unpend_all(&wq_a);
	if (ret == -ENOSYS) {
		ztest_test_skip();
	}

	zassert_equal(ret, 1);
	zassert_true(z_is_thread_ready(&t2));
	zassert_true(z_is_thread_ready(&t3));
	zassert_equal(kernel_unit_contract_ret(&t2), -EAGAIN);
	zassert_equal(kernel_unit_contract_ret(&t3), -EAGAIN);
	zassert_true(z_is_inactive_timeout(&t2.base.timeout));
	zassert_equal_ptr(kernel_unit_contract_next(), &t2);
}

/**
 * @brief z_waitq_head() gives the best waiter, or NULL.
 *
 * @details
 * The query WaitQueue!Head.
 * - Setup: t1 (5) runs. t2 (6) and t3 (4) wait on wq_a, in this order. wq_b
 *   is empty.
 * - Expected: the head of wq_a is t3, the head of wq_b is NULL.
 *
 * @ingroup kernel_unit_sched_contract_wait
 */
ZTEST(sched_contract, test_waitq_head_is_best_waiter)
{
	kernel_unit_contract_thread(&t1, 5);
	kernel_unit_contract_thread(&t2, 6);
	kernel_unit_contract_thread(&t3, 4);
	kernel_unit_contract_wait(&t2, &wq_a, K_FOREVER);
	kernel_unit_contract_wait(&t3, &wq_a, K_FOREVER);
	kernel_unit_contract_start(&t1);

	zassert_equal_ptr(z_waitq_head(&wq_a), &t3);
	zassert_is_null(z_waitq_head(&wq_b));
	kernel_unit_contract_assert_ok();
}

/**
 * @brief An init of an empty wait queue changes nothing.
 *
 * @details
 * WaitqInit on an empty wait queue (on a wait queue with waiters, finding
 * P6-u).
 * - Setup: t1 (5) runs. t2 (6) waits on wq_a. wq_b is empty.
 * - Action: z_waitq_init() of wq_b.
 * - Expected: wq_b is empty, t2 still waits on wq_a. No check fails.
 *
 * @ingroup kernel_unit_sched_contract_wait
 */
ZTEST(sched_contract, test_waitq_init_of_empty_queue_changes_nothing)
{
	kernel_unit_contract_thread(&t1, 5);
	kernel_unit_contract_thread(&t2, 6);
	kernel_unit_contract_wait(&t2, &wq_a, K_FOREVER);
	kernel_unit_contract_start(&t1);

	z_waitq_init(&wq_b);

	zassert_is_null(z_waitq_head(&wq_b));
	zassert_equal_ptr(z_waitq_head(&wq_a), &t2);
	kernel_unit_contract_assert_ok();
}

/**
 * @brief A priority change of a waiter moves it behind the waiters of its new priority.
 *
 * @details
 * PrioSet of a waiter (WaitQueue!Restamp).
 * - Setup: t1 (5) runs. t2 (5), t3 (4) and t4 (6) wait on wq_a, in this
 *   order. The waiters are t3, t2, t4.
 * - Action: z_thread_prio_set(t3, 5).
 * - Expected: the return value is false (t3 is not ready). The waiters are
 *   t2, t3, t4.
 *
 * @ingroup kernel_unit_sched_contract_wait
 */
ZTEST(sched_contract, test_prio_set_of_waiter_moves_it_behind_equal_priority)
{
	static struct k_thread *const before[] = {&t3, &t2, &t4};
	static struct k_thread *const after[] = {&t2, &t3, &t4};

	kernel_unit_contract_thread(&t1, 5);
	kernel_unit_contract_thread(&t2, 5);
	kernel_unit_contract_thread(&t3, 4);
	kernel_unit_contract_thread(&t4, 6);
	kernel_unit_contract_wait(&t2, &wq_a, K_FOREVER);
	kernel_unit_contract_wait(&t3, &wq_a, K_FOREVER);
	kernel_unit_contract_wait(&t4, &wq_a, K_FOREVER);
	kernel_unit_contract_start(&t1);
	assert_waiters(&wq_a, before, ARRAY_SIZE(before));

	zassert_false(z_thread_prio_set(&t3, 5));

	assert_waiters(&wq_a, after, ARRAY_SIZE(after));
	kernel_unit_contract_assert_ok();
}

/**
 * @brief z_unpend_first_thread_locked() and z_sched_ready_locked() are one wake.
 *
 * @details
 * WakeFirstWith(o, F) with object code between the two calls.
 * - Setup: t1 (5) runs. t2 (3) waits on wq_a with a timeout.
 * - Action: t1 locks, z_unpend_first_thread_locked(wq_a), sets the return
 *   value 5 and the data, z_sched_ready_locked(), z_reschedule().
 * - Expected: the first call gives t2 and cancels its timeout. t2 runs with
 *   the return value 5 and the data.
 *
 * @ingroup kernel_unit_sched_contract_wait
 */
ZTEST(sched_contract, test_wake_first_with_is_one_wake)
{
	k_spinlock_key_t key;
	struct k_thread *thread;

	kernel_unit_contract_thread(&t1, 5);
	kernel_unit_contract_thread(&t2, 3);
	kernel_unit_contract_wait(&t2, &wq_a, TEST_TIMEOUT);
	kernel_unit_contract_start(&t1);

	key = k_spin_lock(&lock);
	thread = z_unpend_first_thread_locked(&wq_a);
	zassert_equal_ptr(thread, &t2);
	zassert_true(z_is_inactive_timeout(&t2.base.timeout));
	arch_thread_return_value_set(thread, 5);
	thread->base.swap_data = DATA(3);
	z_sched_ready_locked(thread);
	z_reschedule(&lock, key);

	zassert_equal_ptr(kernel_unit_contract_current(), &t2);
	zassert_equal(kernel_unit_contract_ret(&t2), 5);
	zassert_equal_ptr(t2.base.swap_data, DATA(3));
	kernel_unit_contract_assert_ok();
}

/**
 * @brief An ISR that wakes a waiter selects the woken thread at the exit of the ISR.
 *
 * @details
 * PendCurr, an ISR in the environment, Resume.
 * - Setup: t1 (5) runs, t2 (7) is ready. The environment: an ISR gives wq_a.
 * - Action: t1 calls z_pend_curr() on wq_a with K_FOREVER.
 * - Expected: z_pend_curr() returns 0 and t1 runs.
 *
 * @ingroup kernel_unit_sched_contract_wait
 */
ZTEST(sched_contract, test_isr_wake_selects_at_isr_exit)
{
	k_spinlock_key_t key;

	kernel_unit_contract_thread(&t1, 5);
	kernel_unit_contract_thread(&t2, 7);
	kernel_unit_contract_start(&t1);
	kernel_unit_contract_env_isr(give_a);

	key = k_spin_lock(&lock);
	zassert_equal(z_pend_curr(&lock, key, &wq_a, K_FOREVER), 0);

	zassert_equal_ptr(kernel_unit_contract_current(), &t1);
	kernel_unit_contract_assert_ok();
}

/**
 * @brief A K_FOREVER wait that no event ends does not return.
 *
 * @details
 * - Setup: t1 (5) runs alone. No environment step. The test expects the
 *   check NO_RETURN.
 * - Action: t1 calls z_pend_curr() on wq_a with K_FOREVER.
 * - Expected: the check NO_RETURN fails (the real z_pend_curr() does not
 *   return; the harness continues).
 *
 * @ingroup kernel_unit_sched_contract_wait
 */
ZTEST(sched_contract, test_wait_without_waker_does_not_return)
{
	k_spinlock_key_t key;

	kernel_unit_contract_thread(&t1, 5);
	kernel_unit_contract_start(&t1);
	kernel_unit_contract_expect(KERNEL_UNIT_CONTRACT_NO_RETURN);

	key = k_spin_lock(&lock);
	(void)z_pend_curr(&lock, key, &wq_a, K_FOREVER);

	zassert_true((kernel_unit_contract_found() & KERNEL_UNIT_CONTRACT_NO_RETURN) != 0U);
}

/* The panic of the ISR refusal stops the call: a jump back into the ISR action. */
static jmp_buf panic_env;
static bool stopped_by_panic;

static void panic_jump(unsigned int reason, const struct arch_esf *esf)
{
	ARG_UNUSED(reason);
	ARG_UNUSED(esf);

	longjmp(panic_env, 1);
}

/* An ISR calls z_pend_curr() on wq_a. The panic stops the call. */
static void isr_pend_a(void)
{
	k_spinlock_key_t key = k_spin_lock(&lock);

	stopped_by_panic = false;
	z_fatal_error_fake.custom_fake = panic_jump;
	if (setjmp(panic_env) == 0) {
		(void)z_pend_curr(&lock, key, &wq_a, K_FOREVER);
	} else {
		stopped_by_panic = true;
	}
	z_fatal_error_fake.custom_fake = NULL;
	/* The real call does not return: the test ends the lock of the ISR. */
	k_spin_unlock(&lock, key);
}

/**
 * @brief In an ISR, z_pend_curr() panics before a change.
 *
 * @details
 * PendCurr of an ISR: panic "pend_in_isr", no other change. The first
 * statement of z_pend_curr() is the check.
 * - Setup: t1 (5) runs, t2 (6) is ready. The test expects the panic.
 * - Action: an ISR locks and calls z_pend_curr() on wq_a with K_FOREVER.
 * - Expected: the call stops at z_fatal_error(K_ERR_KERNEL_PANIC). t1 runs
 *   and is ready, wq_a has no waiter, t2 is ready.
 *
 * @ingroup kernel_unit_sched_contract_wait
 */
ZTEST(sched_contract, test_pend_in_isr_panics_before_a_change)
{
	kernel_unit_contract_thread(&t1, 5);
	kernel_unit_contract_thread(&t2, 6);
	kernel_unit_contract_start(&t1);
	kernel_unit_contract_expect_panic();

	kernel_unit_contract_run_isr(isr_pend_a);

	zassert_true(stopped_by_panic);
	zassert_equal(z_fatal_error_fake.call_count, 1U);
	zassert_equal(z_fatal_error_fake.arg0_val, K_ERR_KERNEL_PANIC);
	zassert_equal_ptr(kernel_unit_contract_current(), &t1);
	zassert_true(z_is_thread_ready(&t1));
	zassert_is_null(z_waitq_head(&wq_a));
	zassert_true(z_is_thread_ready(&t2));
#ifdef CONFIG_ASSERT
	/* The __ASSERT(false) before k_panic() is expected. */
	zassert_equal(assert_post_action_fake.call_count, 1U);
	assert_post_action_fake.call_count = 0U;
#endif
}

/* ------------------------------------------------------------------------- */

/**
 * @brief If no thread wakes a timed wait, the timeout ends it with -EAGAIN.
 *
 * @details
 * ThreadTimeout, then Resume.
 * - Setup: t1 (5) runs alone. No environment step.
 * - Action: t1 calls z_pend_curr() on wq_a with a timeout of 10 ticks.
 * - Expected: z_pend_curr() returns -EAGAIN. t1 runs, is not in a wait queue
 *   and has no armed timeout.
 *
 * @ingroup kernel_unit_sched_contract_env
 */
ZTEST(sched_contract, test_timeout_ends_wait_with_eagain)
{
	k_spinlock_key_t key;

	kernel_unit_contract_thread(&t1, 5);
	kernel_unit_contract_start(&t1);

	key = k_spin_lock(&lock);
	zassert_equal(z_pend_curr(&lock, key, &wq_a, TEST_TIMEOUT), -EAGAIN);

	zassert_equal_ptr(kernel_unit_contract_current(), &t1);
	zassert_is_null(t1.base.pended_on);
	zassert_true(z_is_inactive_timeout(&t1.base.timeout));
	kernel_unit_contract_assert_ok();
}

/**
 * @brief A wake cancels the timeout of the woken thread.
 *
 * @details
 * WakeFirst cancels the timeout (ArmedArePending).
 * - Setup: t1 (5) runs. t2 (3) waits on wq_a with a timeout.
 * - Action: t1 gives wq_a.
 * - Expected: t2 runs with 0, and has no armed timeout.
 *
 * @ingroup kernel_unit_sched_contract_env
 */
ZTEST(sched_contract, test_wake_cancels_timeout)
{
	kernel_unit_contract_thread(&t1, 5);
	kernel_unit_contract_thread(&t2, 3);
	kernel_unit_contract_wait(&t2, &wq_a, TEST_TIMEOUT);
	kernel_unit_contract_start(&t1);
	zassert_false(z_is_inactive_timeout(&t2.base.timeout));

	give_a();

	zassert_equal_ptr(kernel_unit_contract_current(), &t2);
	zassert_equal(kernel_unit_contract_ret(&t2), 0);
	zassert_true(z_is_inactive_timeout(&t2.base.timeout));
	kernel_unit_contract_assert_ok();
}

/**
 * @brief The expiry of a timeout makes its thread ready with -EAGAIN, and the timer ISR exit
 * selects it.
 *
 * @details
 * ThreadTimeout(c): the exit of the timer ISR is a reschedule point.
 * - Setup: t1 (5) runs. t2 (3) waits on wq_a with a timeout.
 * - Action: the timeout expires.
 * - Expected: t2 runs with -EAGAIN. It is not in wq_a.
 *
 * @ingroup kernel_unit_sched_contract_env
 */
ZTEST(sched_contract, test_timeout_of_waiter_selects_it)
{
	kernel_unit_contract_thread(&t1, 5);
	kernel_unit_contract_thread(&t2, 3);
	kernel_unit_contract_wait(&t2, &wq_a, TEST_TIMEOUT);
	kernel_unit_contract_start(&t1);

	kernel_unit_contract_timeout();

	zassert_equal_ptr(kernel_unit_contract_current(), &t2);
	zassert_equal(kernel_unit_contract_ret(&t2), -EAGAIN);
	zassert_is_null(z_waitq_head(&wq_a));
	kernel_unit_contract_assert_ok();
}

/**
 * @brief An abort of a waiter takes it out of its wait queue and cancels its timeout.
 *
 * @details
 * Abort(a, t) of a waiting thread.
 * - Setup: t1 (5) runs. t2 (6) waits on wq_a with a timeout.
 * - Action: t1 calls k_thread_abort(t2).
 * - Expected: t2 is dead, not in wq_a, and has no armed timeout. t1 runs.
 *
 * @ingroup kernel_unit_sched_contract_env
 */
ZTEST(sched_contract, test_abort_of_waiter_leaves_wait_queue)
{
	kernel_unit_contract_thread(&t1, 5);
	kernel_unit_contract_thread(&t2, 6);
	kernel_unit_contract_wait(&t2, &wq_a, TEST_TIMEOUT);
	kernel_unit_contract_start(&t1);

	kernel_unit_contract_abort(&t2);

	zassert_true((t2.base.thread_state & _THREAD_DEAD) != 0U);
	zassert_is_null(t2.base.pended_on);
	zassert_is_null(z_waitq_head(&wq_a));
	zassert_true(z_is_inactive_timeout(&t2.base.timeout));
	zassert_equal_ptr(kernel_unit_contract_current(), &t1);
	kernel_unit_contract_assert_ok();
}

/**
 * @brief An abort of another thread changes the next thread without a switch.
 *
 * @details
 * Abort with update_cache(1) (finding P7-c, descriptive side; the agreement
 * of the reference fake and the code is RF-1).
 * - Setup: Z(-1, -2, 0). t1 runs (cooperative, it keeps the CPU against t2).
 * - Action: t1 calls k_thread_abort(t3). Then t1 calls z_reschedule().
 * - Expected: after the abort, t1 still runs, and the next thread is t2: the
 *   check RunRuleHolds fails (the test expects it). z_reschedule() then
 *   switches to t2.
 *
 * @ingroup kernel_unit_sched_contract_env
 */
ZTEST(sched_contract, test_abort_of_other_thread_selects_head_at_next_point)
{
	k_spinlock_key_t key;

	three_threads(-1, -2, 0);
	kernel_unit_contract_start(&t1);
	kernel_unit_contract_expect(KERNEL_UNIT_CONTRACT_RUN_RULE_HOLDS);

	kernel_unit_contract_abort(&t3);
	zassert_equal_ptr(kernel_unit_contract_current(), &t1);
	zassert_equal_ptr(kernel_unit_contract_next(), &t2);
	zassert_true((kernel_unit_contract_found() & KERNEL_UNIT_CONTRACT_RUN_RULE_HOLDS) != 0U);

	key = k_spin_lock(&lock);
	z_reschedule(&lock, key);

	zassert_equal_ptr(kernel_unit_contract_current(), &t2);
}

/**
 * @brief A thread that aborts itself does not return, and the CPU selects the next thread.
 *
 * @details
 * Abort(a, a) with Release(a, "swap").
 * - Setup: t1 (5) runs, t2 (6) and t3 (7) are ready.
 * - Action: t1 calls k_thread_abort(t1).
 * - Expected: t1 is dead and does not run again (the adapter expects the
 *   check NO_RETURN of the real switch). t2 runs.
 *
 * @ingroup kernel_unit_sched_contract_env
 */
ZTEST(sched_contract, test_abort_of_self_selects_next_thread)
{
	three_threads(5, 6, 7);
	kernel_unit_contract_start(&t1);

	kernel_unit_contract_abort(&t1);

	zassert_true((t1.base.thread_state & _THREAD_DEAD) != 0U);
	zassert_equal_ptr(kernel_unit_contract_current(), &t2);
}

/**
 * @brief The exit of an interrupt without a kernel call switches to the next thread.
 *
 * @details
 * Preempt(c): the exit of an interrupt is a reschedule point, without a new
 * update_cache().
 * - Setup: Z(-1, -2, 3). t1 runs (cooperative). z_thread_prio_set(t3, 3)
 *   makes t2 the next thread without a switch (as in
 *   test_prio_set_of_other_lets_higher_preempt_coop).
 * - Action: an interrupt without a kernel call.
 * - Expected: t2 runs.
 *
 * @ingroup kernel_unit_sched_contract_release
 */
ZTEST(sched_contract, test_isr_exit_switches_to_next_thread)
{
	three_threads(-1, -2, 3);
	kernel_unit_contract_start(&t1);
	zassert_true(z_thread_prio_set(&t3, 3));
	zassert_equal_ptr(kernel_unit_contract_current(), &t1);

	kernel_unit_contract_run_isr(NULL);

	zassert_equal_ptr(kernel_unit_contract_current(), &t2);
	kernel_unit_contract_assert_ok();
}

#ifdef KERNEL_UNIT_FAKE_GROUP_sched_ref
/*
 * Difference RF-4 (sched-app.md): the reference fake has no join queue
 * (finding F14, "Not in the reference fake"). The abort does not wake t3.
 */
ZTEST_EXPECT_FAIL(sched_contract, test_abort_wakes_joiner_with_zero);
#endif

/**
 * @brief An abort wakes the threads that join the aborted thread, with the return value 0.
 *
 * @details
 * Join, then Abort (unpend_all() of halt_thread()). The descriptive side of
 * finding F14.
 * - Setup: Zephyr priorities t1 1, t2 1, t3 0. t3 waits on the join queue of
 *   t2 (k_thread_join(t2, K_FOREVER) in the past). t1 runs.
 * - Action: t1 calls k_thread_abort(t2).
 * - Expected: t2 is dead. t3 is ready with the return value 0. The next
 *   thread is t3, and t1 still runs (no reschedule: RunRuleHolds fails, the
 *   test expects it).
 *
 * @ingroup kernel_unit_sched_contract_env
 */
ZTEST(sched_contract, test_abort_wakes_joiner_with_zero)
{
	three_threads(1, 1, 0);
	kernel_unit_contract_wait(&t3, &t2.join_queue, K_FOREVER);
	kernel_unit_contract_start(&t1);
	kernel_unit_contract_expect(KERNEL_UNIT_CONTRACT_RUN_RULE_HOLDS);

	kernel_unit_contract_abort(&t2);

	zassert_true((t2.base.thread_state & _THREAD_DEAD) != 0U);
	zassert_true(z_is_thread_ready(&t3));
	zassert_equal(kernel_unit_contract_ret(&t3), 0);
	zassert_equal_ptr(kernel_unit_contract_next(), &t3);
	zassert_equal_ptr(kernel_unit_contract_current(), &t1);
}

/**
 * @brief k_thread_priority_set() of a ready thread above the current thread switches to it.
 *
 * @details
 * SetPrio(a, t, p) with Release(a, "resched").
 * - Setup: t1 (5) runs, t2 (7) is ready.
 * - Action: t1 calls k_thread_priority_set(t2, 3).
 * - Expected: t2 runs with the priority 3.
 *
 * @ingroup kernel_unit_sched_contract_env
 */
ZTEST(sched_contract, test_set_prio_above_current_switches)
{
	kernel_unit_contract_thread(&t1, 5);
	kernel_unit_contract_thread(&t2, 7);
	kernel_unit_contract_start(&t1);

	kernel_unit_contract_set_prio(&t2, 3);

	zassert_equal(t2.base.prio, 3);
	zassert_equal_ptr(kernel_unit_contract_current(), &t2);
	kernel_unit_contract_assert_ok();
}
