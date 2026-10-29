/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @defgroup kernel_unit_sched_ref_tests Self-test of the reference fake of the scheduler
 * @ingroup kernel_unit_tests
 * @brief The reference fake (fake group sched_ref) follows the scheduler contract of layer A.
 *
 * This application includes no kernel source file. The tests call the
 * layer-A functions (z_pend_curr(), z_sched_wake(), z_reschedule(), ...)
 * directly, with the reference fake installed (see @ref kernel_unit_sched_ref).
 * They check the fake against the contract in
 * @c safety/spec/tla/lib/Scheduler.tla:
 *
 * - The selection rule @c Choices, with the example values of
 *   @c mc/SchedulerTest.tla (TestChoicesUp).
 * - The order of the wait queue (@c WaitQueue!Before): a higher priority
 *   first, then the order of arrival.
 * - The wait: the -EAGAIN preset, the wake, the timeout, the ISR refusal and a
 *   wait that never ends.
 * - The reschedule decision for a higher, a lower and an equal priority, and
 *   for a cooperative current thread.
 * - The checks of the invariants: the fake finds a wake without the
 *   cancellation of the timeout (mutant @c wake_no_cancel), a missed
 *   reschedule (mutant @c missed_resched) and a lost thread.
 *
 * Priorities in this file are Zephyr priorities: a lower number is a higher
 * priority, and a negative number is a cooperative thread. The contract uses
 * the reverse (@c ToZephyr).
 *
 * A later contract test runs the same tests against the real
 * @c kernel/sched.c (roadmap step 2, item 3).
 */

#include <string.h>
#include <zephyr/ztest.h>
#include <kernel_unit.h>
#include <kernel_unit_models.h>
#include <kernel_unit_sched_ref.h>
#include <scheduler.h>
#ifdef CONFIG_ASSERT
#include <fakes/assert.h>
#endif

/* Timeouts that are not K_NO_WAIT and not K_FOREVER */
#define SHORT_TIMEOUT K_TICKS(5)
#define TEST_TIMEOUT  K_TICKS(10)
#define LONG_TIMEOUT  K_TICKS(20)

/* Swap data that a waker gives */
#define DATA(n) ((void *)(uintptr_t)(0x1000U + (n)))

/* The threads and wait queues of the tests. */
static struct k_thread t1;
static struct k_thread t2;
static struct k_thread t3;
static struct k_thread t4;
static _wait_q_t wq_a;
static _wait_q_t wq_b;

/* The lock that the tests give to z_pend_curr() and z_reschedule(). */
static struct k_spinlock test_lock;
static const k_spinlock_key_t test_key = {.key = KERNEL_UNIT_IRQ_KEY};

/* The fake state of a thread. */
static struct kernel_unit_sched_ref_thread *ref(const struct k_thread *thread)
{
	return kernel_unit_sched_ref_of(thread);
}

/* Install the fake with three ready threads with these Zephyr priorities. */
static void three_threads(int p1, int p2, int p3)
{
	kernel_unit_sched_ref_install();
	kernel_unit_sched_ref_thread(&t1, p1);
	kernel_unit_sched_ref_thread(&t2, p2);
	kernel_unit_sched_ref_thread(&t3, p3);
}

/* Assert the waiters of a wait queue, head first. */
static void assert_waiters(_wait_q_t *wait_q, struct k_thread *const *expected, size_t n)
{
	struct k_thread *got[KERNEL_UNIT_SCHED_REF_MAX_THREADS];

	zassert_equal(kernel_unit_sched_ref_waiters(wait_q, got, ARRAY_SIZE(got)), n);
	for (size_t i = 0; i < n; i++) {
		zassert_equal_ptr(got[i], expected[i], "waiter %zu", i);
	}
}

/* A wake of the first waiter of wq_a with 0, and the reschedule. */
static void give_a(void)
{
	(void)z_sched_wake(&wq_a, 0, DATA(1));
	z_reschedule(&test_lock, test_key);
}

ZTEST_SUITE(sched_ref_unit, NULL, NULL, NULL, NULL, NULL);

/**
 * @defgroup kernel_unit_sched_ref_choices Selection rule
 * @ingroup kernel_unit_sched_ref_tests
 * @brief kernel_unit_sched_ref_choices() gives the set Choices(c1, ...) of the contract.
 *
 * The rule of next_up() and should_preempt(): a ready cooperative thread keeps
 * the CPU. Else the ready threads with the highest priority are the choices,
 * and the current thread wins a tie. If no thread is ready, the idle thread
 * runs. Each test is one check of TestChoicesUp in @c mc/SchedulerTest.tla.
 */

/**
 * @brief A ready thread with a higher priority than the current thread is the only choice.
 *
 * @details
 * - Setup: priorities t1 1, t2 0, t3 2. t1 runs. ("up: higher preempts")
 * - Expected: Choices is {t2}.
 *
 * @ingroup kernel_unit_sched_ref_choices
 */
ZTEST(sched_ref_unit, test_choices_higher_priority_preempts)
{
	three_threads(1, 0, 2);
	kernel_unit_sched_ref_set_current(&t1);

	zassert_equal(kernel_unit_sched_ref_choices(), kernel_unit_sched_ref_bit(&t2));
}

/**
 * @brief Threads with a lower priority do not preempt the current thread.
 *
 * @details
 * - Setup: priorities t1 0, t2 1, t3 2. t1 runs. ("up: lower does not preempt")
 * - Expected: Choices is {t1}.
 *
 * @ingroup kernel_unit_sched_ref_choices
 */
ZTEST(sched_ref_unit, test_choices_lower_priority_does_not_preempt)
{
	three_threads(0, 1, 2);
	kernel_unit_sched_ref_set_current(&t1);

	zassert_equal(kernel_unit_sched_ref_choices(), kernel_unit_sched_ref_bit(&t1));
}

/**
 * @brief The current thread wins a tie with a ready thread of the same priority.
 *
 * @details
 * - Setup: priorities t1 0, t2 0, t3 1. t1 runs. ("up: current wins a tie")
 * - Expected: Choices is {t1}.
 *
 * @ingroup kernel_unit_sched_ref_choices
 */
ZTEST(sched_ref_unit, test_choices_current_wins_a_tie)
{
	three_threads(0, 0, 1);
	kernel_unit_sched_ref_set_current(&t1);

	zassert_equal(kernel_unit_sched_ref_choices(), kernel_unit_sched_ref_bit(&t1));
}

/**
 * @brief A ready cooperative thread keeps the CPU, also against a higher cooperative priority.
 *
 * @details
 * - Setup: priorities t1 -1, t2 -2, t3 0. t1 runs. ("up: coop keeps the CPU")
 * - Expected: Choices is {t1}.
 *
 * @ingroup kernel_unit_sched_ref_choices
 */
ZTEST(sched_ref_unit, test_choices_cooperative_keeps_the_cpu)
{
	three_threads(-1, -2, 0);
	kernel_unit_sched_ref_set_current(&t1);

	zassert_equal(kernel_unit_sched_ref_choices(), kernel_unit_sched_ref_bit(&t1));
}

/**
 * @brief A cooperative thread preempts a preemptible current thread.
 *
 * @details
 * - Setup: priorities t1 0, t2 -1, t3 1. t1 runs. ("up: coop preempts a
 *   preemptible")
 * - Expected: Choices is {t2}.
 *
 * @ingroup kernel_unit_sched_ref_choices
 */
ZTEST(sched_ref_unit, test_choices_cooperative_preempts_preemptible)
{
	three_threads(0, -1, 1);
	kernel_unit_sched_ref_set_current(&t1);

	zassert_equal(kernel_unit_sched_ref_choices(), kernel_unit_sched_ref_bit(&t2));
}

/**
 * @brief A cooperative current thread that waits leaves the CPU.
 *
 * @details
 * - Setup: priorities t1 -1, t2 0, t3 1. t1 runs and waits (the state inside
 *   PendCurr, before the selection). ("up: pending coop leaves")
 * - Expected: Choices is {t2}.
 *
 * @ingroup kernel_unit_sched_ref_choices
 */
ZTEST(sched_ref_unit, test_choices_pending_cooperative_leaves)
{
	three_threads(-1, 0, 1);
	kernel_unit_sched_ref_set_current(&t1);
	kernel_unit_sched_ref_wait(&t1, &wq_a, K_FOREVER);

	zassert_equal(kernel_unit_sched_ref_choices(), kernel_unit_sched_ref_bit(&t2));
}

/**
 * @brief After a wait of the current thread, each thread of a tie is a choice.
 *
 * @details
 * - Setup: priorities t1 0, t2 1, t3 1. t1 runs and waits. ("up: any of a
 *   tie after a wait")
 * - Expected: Choices is {t2, t3}.
 *
 * @ingroup kernel_unit_sched_ref_choices
 */
ZTEST(sched_ref_unit, test_choices_any_of_a_tie_after_a_wait)
{
	three_threads(0, 1, 1);
	kernel_unit_sched_ref_set_current(&t1);
	kernel_unit_sched_ref_wait(&t1, &wq_a, K_FOREVER);

	zassert_equal(kernel_unit_sched_ref_choices(),
		      kernel_unit_sched_ref_bit(&t2) | kernel_unit_sched_ref_bit(&t3));
}

/**
 * @brief If no thread is ready, the idle thread is the only choice.
 *
 * @details
 * - Setup: priorities 0, 0, 0. t1 runs. All three threads wait. ("up: idle if
 *   no thread is ready")
 * - Expected: Choices is {idle}.
 *
 * @ingroup kernel_unit_sched_ref_choices
 */
ZTEST(sched_ref_unit, test_choices_idle_if_no_thread_is_ready)
{
	three_threads(0, 0, 0);
	kernel_unit_sched_ref_set_current(&t1);
	kernel_unit_sched_ref_wait(&t1, &wq_a, K_FOREVER);
	kernel_unit_sched_ref_wait(&t2, &wq_a, K_FOREVER);
	kernel_unit_sched_ref_wait(&t3, &wq_a, K_FOREVER);

	zassert_equal(kernel_unit_sched_ref_choices(), KERNEL_UNIT_SCHED_REF_IDLE);
}

/**
 * @brief The idle thread leaves the CPU for the ready thread with the highest priority.
 *
 * @details
 * - Setup: priorities t1 2, t2 1, t3 0. The idle thread runs. ("up: idle
 *   leaves")
 * - Expected: Choices is {t3}.
 *
 * @ingroup kernel_unit_sched_ref_choices
 */
ZTEST(sched_ref_unit, test_choices_idle_leaves)
{
	three_threads(2, 1, 0);
	kernel_unit_sched_ref_set_current(NULL);

	zassert_equal(kernel_unit_sched_ref_choices(), kernel_unit_sched_ref_bit(&t3));
}

/**
 * @defgroup kernel_unit_sched_ref_waitq Wait queue order
 * @ingroup kernel_unit_sched_ref_tests
 * @brief The wait queue is in the order WaitQueue!Before: a higher priority first, then arrival.
 */

/**
 * @brief z_sched_wake() wakes the waiters in the order of priority, then of arrival.
 *
 * @details
 * - Setup: t1 runs with priority 0. t2 (5), t3 (3), t4 (5) wait on wq_a in
 *   this order.
 * - Action: z_sched_wake() four times, each time with the value 0 and other
 *   data.
 * - Expected: the wakes take t3, then t2, then t4. The fourth call returns
 *   false. Each woken thread is ready, has the value 0 and the data of its
 *   wake. t1 keeps the CPU.
 *
 * @ingroup kernel_unit_sched_ref_waitq
 */
ZTEST(sched_ref_unit, test_wake_order_priority_then_arrival)
{
	struct k_thread *const before_wakes[] = {&t3, &t2, &t4};

	kernel_unit_sched_ref_install();
	kernel_unit_sched_ref_thread(&t1, 0);
	kernel_unit_sched_ref_thread(&t2, 5);
	kernel_unit_sched_ref_thread(&t3, 3);
	kernel_unit_sched_ref_thread(&t4, 5);
	kernel_unit_sched_ref_set_current(&t1);
	kernel_unit_sched_ref_wait(&t2, &wq_a, K_FOREVER);
	kernel_unit_sched_ref_wait(&t3, &wq_a, K_FOREVER);
	kernel_unit_sched_ref_wait(&t4, &wq_a, K_FOREVER);
	assert_waiters(&wq_a, before_wakes, ARRAY_SIZE(before_wakes));
	zassert_equal_ptr(z_waitq_head(&wq_a), &t3);

	zassert_true(z_sched_wake(&wq_a, 0, DATA(1)));
	zassert_true(z_sched_wake(&wq_a, 0, DATA(2)));
	zassert_true(z_sched_wake(&wq_a, 0, DATA(3)));
	zassert_false(z_sched_wake(&wq_a, 0, DATA(4)));
	z_reschedule(&test_lock, test_key);

	zassert_equal_ptr(t3.base.swap_data, DATA(1));
	zassert_equal_ptr(t2.base.swap_data, DATA(2));
	zassert_equal_ptr(t4.base.swap_data, DATA(3));
	zassert_equal(ref(&t2)->state, KERNEL_UNIT_SCHED_REF_READY);
	zassert_equal(ref(&t3)->ret, 0);
	zassert_is_null(z_waitq_head(&wq_a));
	zassert_equal_ptr(_current, &t1);
	kernel_unit_sched_ref_assert_ok();
}

/**
 * @brief z_thread_prio_set() moves a waiter behind the waiters with its new priority.
 *
 * @details
 * - Setup: t1 runs with priority 0. t2 (5), t3 (5), t4 (3) wait on wq_a.
 * - Action: z_thread_prio_set() gives t2 the priority 3. Then it gives the
 *   ready thread t1 the priority 1.
 * - Expected: the order is t4, t2, t3 (PrioChangeGoesLast). The return value
 *   is false for the waiter and true for the ready thread (z_is_thread_ready()
 *   in sched.c). No call selects a thread.
 *
 * @ingroup kernel_unit_sched_ref_waitq
 */
ZTEST(sched_ref_unit, test_prio_set_moves_waiter_behind_equal_priority)
{
	struct k_thread *const expected[] = {&t4, &t2, &t3};

	kernel_unit_sched_ref_install();
	kernel_unit_sched_ref_thread(&t1, 0);
	kernel_unit_sched_ref_thread(&t2, 5);
	kernel_unit_sched_ref_thread(&t3, 5);
	kernel_unit_sched_ref_thread(&t4, 3);
	kernel_unit_sched_ref_set_current(&t1);
	kernel_unit_sched_ref_wait(&t2, &wq_a, K_FOREVER);
	kernel_unit_sched_ref_wait(&t3, &wq_a, K_FOREVER);
	kernel_unit_sched_ref_wait(&t4, &wq_a, K_FOREVER);

	zassert_false(z_thread_prio_set(&t2, 3));
	zassert_true(z_thread_prio_set(&t1, 1));

	assert_waiters(&wq_a, expected, ARRAY_SIZE(expected));
	zassert_equal(t2.base.prio, 3);
	zassert_equal_ptr(_current, &t1);
	kernel_unit_sched_ref_assert_ok();
}

/* Walk callback: record the thread, stop at the second thread. */
static struct k_thread *walked[KERNEL_UNIT_SCHED_REF_MAX_THREADS];
static size_t n_walked;
static int post_status;

static int walk_record(struct k_thread *thread, void *data)
{
	ARG_UNUSED(data);

	walked[n_walked++] = thread;

	return (n_walked == 2U) ? 1 : 0;
}

static void post_record(int status, void *data)
{
	ARG_UNUSED(data);

	post_status = status;
}

/**
 * @brief z_sched_waitq_walk() walks the waiters in wait queue order until a callback stops it.
 *
 * @details
 * - Setup: t1 runs. t2 (5), t3 (3), t4 (5) wait on wq_a.
 * - Action: z_sched_waitq_walk() with a callback that returns 1 at the second
 *   thread.
 * - Expected: the walk visits t3, then t2, and stops. The post-walk callback
 *   gets 1, and the walk returns 1. The walk wakes no thread.
 *
 * @ingroup kernel_unit_sched_ref_waitq
 */
ZTEST(sched_ref_unit, test_waitq_walk_in_order_until_stop)
{
	kernel_unit_sched_ref_install();
	kernel_unit_sched_ref_thread(&t1, 0);
	kernel_unit_sched_ref_thread(&t2, 5);
	kernel_unit_sched_ref_thread(&t3, 3);
	kernel_unit_sched_ref_thread(&t4, 5);
	kernel_unit_sched_ref_set_current(&t1);
	kernel_unit_sched_ref_wait(&t2, &wq_a, K_FOREVER);
	kernel_unit_sched_ref_wait(&t3, &wq_a, K_FOREVER);
	kernel_unit_sched_ref_wait(&t4, &wq_a, K_FOREVER);
	n_walked = 0U;
	post_status = 0;

	zassert_equal(z_sched_waitq_walk(&wq_a, walk_record, post_record, NULL), 1);

	zassert_equal(n_walked, 2U);
	zassert_equal_ptr(walked[0], &t3);
	zassert_equal_ptr(walked[1], &t2);
	zassert_equal(post_status, 1);
	zassert_equal(ref(&t3)->state, KERNEL_UNIT_SCHED_REF_PENDING);
	kernel_unit_sched_ref_assert_ok();
}

/**
 * @defgroup kernel_unit_sched_ref_wait Wait and wake
 * @ingroup kernel_unit_sched_ref_tests
 * @brief z_pend_curr() is PendCurr, the environment, then Resume.
 */

/* The state of t1 that an environment action saw. */
static bool t1_was_pending;
static bool t1_had_preset;

static void observe_t1_then_give(void)
{
	struct k_thread *head = z_waitq_head(&wq_a);

	t1_was_pending = (ref(&t1)->state == KERNEL_UNIT_SCHED_REF_PENDING) && (head == &t1);
	t1_had_preset = ref(&t1)->has_ret && (ref(&t1)->ret == -EAGAIN);
	give_a();
}

/**
 * @brief While a thread waits, it is in the wait queue with the return value -EAGAIN.
 *
 * @details
 * - Setup: t1 (priority 5) runs, t2 (priority 7) is ready. t2 is the
 *   environment: it records the state of t1, then wakes t1 with 0 and
 *   reschedules.
 * - Action: z_pend_curr() of t1 on wq_a with K_FOREVER.
 * - Expected: during the wait, t1 is pending, the head of wq_a, and has the
 *   preset -EAGAIN (PendingIsQueued). The wake gives 0 and the data. t1 runs
 *   again, and z_pend_curr() returns 0.
 *
 * @ingroup kernel_unit_sched_ref_wait
 */
ZTEST(sched_ref_unit, test_pend_presets_eagain_until_wake)
{
	kernel_unit_sched_ref_install();
	kernel_unit_sched_ref_thread(&t1, 5);
	kernel_unit_sched_ref_thread(&t2, 7);
	kernel_unit_sched_ref_set_current(&t1);
	kernel_unit_sched_ref_env_thread(&t2, observe_t1_then_give);

	zassert_equal(z_pend_curr(&test_lock, test_key, &wq_a, K_FOREVER), 0);

	zassert_true(t1_was_pending);
	zassert_true(t1_had_preset);
	zassert_equal_ptr(t1.base.swap_data, DATA(1));
	zassert_equal_ptr(_current, &t1);
	zassert_false(ref(&t1)->has_ret);
	kernel_unit_sched_ref_assert_ok();
}

/**
 * @brief If no thread wakes a timed wait, the timeout ends it with -EAGAIN.
 *
 * @details
 * - Setup: t1 runs alone. No environment step.
 * - Action: z_pend_curr() of t1 on wq_a with a timeout of 10 ticks.
 * - Expected: the CPU runs the idle thread during the wait. The timeout
 *   expires at tick 10 (ThreadTimeout). z_pend_curr() returns -EAGAIN. t1 is
 *   not in the wait queue and has no armed timeout.
 *
 * @ingroup kernel_unit_sched_ref_wait
 */
ZTEST(sched_ref_unit, test_timeout_ends_wait_with_eagain)
{
	kernel_unit_sched_ref_install();
	kernel_unit_sched_ref_thread(&t1, 5);
	kernel_unit_sched_ref_set_current(&t1);

	zassert_equal(z_pend_curr(&test_lock, test_key, &wq_a, TEST_TIMEOUT), -EAGAIN);

	zassert_equal(kernel_unit_sched_ref.clock, 10);
	zassert_is_null(t1.base.pended_on);
	zassert_false(ref(&t1)->armed);
	zassert_true(z_is_inactive_timeout(&t1.base.timeout));
	kernel_unit_sched_ref_assert_ok();
}

#ifdef CONFIG_TIMEOUT_64BIT
/**
 * @brief An absolute timeout expires at its tick, and at least one tick after now.
 *
 * @details
 * - Setup: t1 runs alone. The fake clock is at tick 0.
 * - Action: z_pend_curr() with K_TIMEOUT_ABS_TICKS(25). Then z_pend_curr()
 *   with K_TIMEOUT_ABS_TICKS(10), a tick in the past.
 * - Expected: the first wait ends at tick 25, the second at tick 26
 *   (z_add_timeout() uses at least one tick). Both return -EAGAIN.
 *
 * @ingroup kernel_unit_sched_ref_wait
 */
ZTEST(sched_ref_unit, test_absolute_timeout_expires_at_its_tick)
{
	kernel_unit_sched_ref_install();
	kernel_unit_sched_ref_thread(&t1, 5);
	kernel_unit_sched_ref_set_current(&t1);

	zassert_equal(z_pend_curr(&test_lock, test_key, &wq_a, K_TIMEOUT_ABS_TICKS(25)), -EAGAIN);
	zassert_equal(kernel_unit_sched_ref.clock, 25);

	zassert_equal(z_pend_curr(&test_lock, test_key, &wq_a, K_TIMEOUT_ABS_TICKS(10)), -EAGAIN);
	zassert_equal(kernel_unit_sched_ref.clock, 26);
	kernel_unit_sched_ref_assert_ok();
}
#endif /* CONFIG_TIMEOUT_64BIT */

/**
 * @brief The timeouts expire in the order of their deadlines.
 *
 * @details
 * - Setup: t1 runs. t2 waits with 20 ticks, then t3 with 5 ticks.
 * - Action: kernel_unit_sched_ref_timeout() two times.
 * - Expected: the first expiry ends the wait of t3 (tick 5), the second the
 *   wait of t2 (tick 20). Each one keeps -EAGAIN.
 *
 * @ingroup kernel_unit_sched_ref_wait
 */
ZTEST(sched_ref_unit, test_timeouts_expire_by_deadline)
{
	three_threads(0, 5, 5);
	kernel_unit_sched_ref_set_current(&t1);
	kernel_unit_sched_ref_wait(&t2, &wq_a, LONG_TIMEOUT);
	kernel_unit_sched_ref_wait(&t3, &wq_b, SHORT_TIMEOUT);

	kernel_unit_sched_ref_timeout();
	zassert_equal(ref(&t3)->state, KERNEL_UNIT_SCHED_REF_READY);
	zassert_equal(ref(&t2)->state, KERNEL_UNIT_SCHED_REF_PENDING);
	zassert_equal(kernel_unit_sched_ref.clock, 5);

	kernel_unit_sched_ref_timeout();
	zassert_equal(ref(&t2)->state, KERNEL_UNIT_SCHED_REF_READY);
	zassert_equal(kernel_unit_sched_ref.clock, 20);
	zassert_equal(ref(&t2)->ret, -EAGAIN);
	zassert_equal(ref(&t3)->ret, -EAGAIN);
	kernel_unit_sched_ref_assert_ok();
}

/**
 * @brief A wake cancels the timeout of the woken thread.
 *
 * @details
 * - Setup: t1 runs. t2 waits on wq_a with 10 ticks.
 * - Action: z_sched_wake() on wq_a, then z_reschedule().
 * - Expected: t2 is ready and has no armed timeout (ArmedArePending). A later
 *   expiry has no timeout to expire.
 *
 * @ingroup kernel_unit_sched_ref_wait
 */
ZTEST(sched_ref_unit, test_wake_cancels_timeout)
{
	three_threads(0, 5, 5);
	kernel_unit_sched_ref_set_current(&t1);
	kernel_unit_sched_ref_wait(&t2, &wq_a, TEST_TIMEOUT);
	zassert_false(z_is_inactive_timeout(&t2.base.timeout));

	give_a();

	zassert_false(ref(&t2)->armed);
	zassert_true(z_is_inactive_timeout(&t2.base.timeout));
	kernel_unit_sched_ref_assert_ok();
}

/**
 * @brief A K_FOREVER wait that no thread ends does not return.
 *
 * @details
 * - Setup: t1 runs alone. No environment step. The test expects the check
 *   NO_RETURN.
 * - Action: z_pend_curr() of t1 on wq_a with K_FOREVER.
 * - Expected: the check NO_RETURN fails, and the fake returns -EAGAIN (the
 *   real z_pend_curr() does not return). t1 is still in the wait queue. A
 *   plain model would show a timeout here.
 *
 * @ingroup kernel_unit_sched_ref_wait
 */
ZTEST(sched_ref_unit, test_forever_wait_without_waker_does_not_return)
{
	kernel_unit_sched_ref_install();
	kernel_unit_sched_ref_thread(&t1, 5);
	kernel_unit_sched_ref_set_current(&t1);
	kernel_unit_sched_ref_expect(KERNEL_UNIT_SCHED_REF_NO_RETURN);

	zassert_equal(z_pend_curr(&test_lock, test_key, &wq_a, K_FOREVER), -EAGAIN);

	zassert_equal(kernel_unit_sched_ref.found, KERNEL_UNIT_SCHED_REF_NO_RETURN);
	zassert_equal(ref(&t1)->state, KERNEL_UNIT_SCHED_REF_PENDING);
	zassert_equal_ptr(t1.base.pended_on, &wq_a);
}

/**
 * @brief An abort of the waiting thread ends the wait without a return.
 *
 * @details
 * - Setup: t1 (5) runs, t2 (7) is ready. The environment: t2 aborts t1.
 * - Action: z_pend_curr() of t1 on wq_a with a timeout of 10 ticks.
 * - Expected: t1 is dead, out of the wait queue and has no armed timeout
 *   (DeadIsInert). The check NO_RETURN fails as expected.
 *
 * @ingroup kernel_unit_sched_ref_wait
 */
ZTEST(sched_ref_unit, test_abort_of_waiting_thread_does_not_return)
{
	kernel_unit_sched_ref_install();
	kernel_unit_sched_ref_thread(&t1, 5);
	kernel_unit_sched_ref_thread(&t2, 7);
	kernel_unit_sched_ref_set_current(&t1);
	kernel_unit_sched_ref_env_abort(&t1);
	kernel_unit_sched_ref_expect(KERNEL_UNIT_SCHED_REF_NO_RETURN);

	(void)z_pend_curr(&test_lock, test_key, &wq_a, TEST_TIMEOUT);

	zassert_equal(kernel_unit_sched_ref.found, KERNEL_UNIT_SCHED_REF_NO_RETURN);
	zassert_equal(ref(&t1)->state, KERNEL_UNIT_SCHED_REF_DEAD);
	zassert_is_null(t1.base.pended_on);
	zassert_false(ref(&t1)->armed);
	zassert_false(ref(&t1)->has_ret);
}

/**
 * @brief An ISR that wakes a waiter selects the woken thread at the exit of the ISR.
 *
 * @details
 * - Setup: t1 (5) runs, t2 (7) is ready. The environment: an ISR wakes the
 *   first waiter of wq_a and calls z_reschedule().
 * - Action: z_pend_curr() of t1 on wq_a with K_FOREVER.
 * - Expected: in the ISR, z_reschedule() does not select. At the exit of the
 *   ISR, the CPU selects t1 (priority 5 is higher than 7). z_pend_curr()
 *   returns 0.
 *
 * @ingroup kernel_unit_sched_ref_wait
 */
ZTEST(sched_ref_unit, test_isr_wake_selects_at_isr_exit)
{
	kernel_unit_sched_ref_install();
	kernel_unit_sched_ref_thread(&t1, 5);
	kernel_unit_sched_ref_thread(&t2, 7);
	kernel_unit_sched_ref_set_current(&t1);
	kernel_unit_sched_ref_env_isr(give_a);

	zassert_equal(z_pend_curr(&test_lock, test_key, &wq_a, K_FOREVER), 0);

	zassert_equal_ptr(_current, &t1);
	zassert_false(arch_is_in_isr_fake.return_val);
	kernel_unit_sched_ref_assert_ok();
}

/**
 * @brief In an ISR, z_pend_curr() panics and changes no thread and no wait queue.
 *
 * @details
 * - Setup: t1 runs. arch_is_in_isr() returns true. The test expects the
 *   refusal and the check MISUSE.
 * - Action: z_pend_curr() on wq_a with K_FOREVER. Then z_sched_wake() on wq_a.
 * - Expected: one refusal with a panic (fake group sched). t1 is ready, has no
 *   return value, and wq_a has no waiter. The z_sched_wake() after the panic is
 *   a MISUSE: a panic stops the system.
 *
 * @ingroup kernel_unit_sched_ref_wait
 */
ZTEST(sched_ref_unit, test_isr_refusal_changes_nothing)
{
	kernel_unit_sched_ref_install();
	kernel_unit_sched_ref_thread(&t1, 5);
	kernel_unit_sched_ref_set_current(&t1);
	arch_is_in_isr_fake.return_val = true;
	kernel_unit_expect_pend_refusal();
	kernel_unit_sched_ref_expect(KERNEL_UNIT_SCHED_REF_MISUSE);

	zassert_equal(z_pend_curr(&test_lock, test_key, &wq_a, K_FOREVER),
		      KERNEL_UNIT_PEND_REFUSED);
	kernel_unit_assert_pend_refused();
	zassert_equal(ref(&t1)->state, KERNEL_UNIT_SCHED_REF_READY);
	zassert_false(ref(&t1)->has_ret);
	zassert_is_null(z_waitq_head(&wq_a));
	zassert_equal(kernel_unit_sched_ref.found, 0U);

	(void)z_sched_wake(&wq_a, 0, NULL);
	zassert_equal(kernel_unit_sched_ref.found, KERNEL_UNIT_SCHED_REF_MISUSE);
}

/**
 * @defgroup kernel_unit_sched_ref_resched Reschedule decision
 * @ingroup kernel_unit_sched_ref_tests
 * @brief z_reschedule() is Release(a, "resched"): the CPU selects with the rule Choices.
 */

/* Install the fake: t1 runs with priority cur_prio, t2 waits on wq_a with waiter_prio. */
static void waiter_and_current(int cur_prio, int waiter_prio)
{
	kernel_unit_sched_ref_install();
	kernel_unit_sched_ref_thread(&t1, cur_prio);
	kernel_unit_sched_ref_thread(&t2, waiter_prio);
	kernel_unit_sched_ref_set_current(&t1);
	kernel_unit_sched_ref_wait(&t2, &wq_a, K_FOREVER);
}

/**
 * @brief After a wake of a thread with a higher priority, z_reschedule() switches to it.
 *
 * @details
 * - Setup: t1 runs with priority 5. t2 waits with priority 1.
 * - Action: z_sched_wake() and z_reschedule().
 * - Expected: t2 runs.
 *
 * @ingroup kernel_unit_sched_ref_resched
 */
ZTEST(sched_ref_unit, test_reschedule_switches_to_higher_priority)
{
	waiter_and_current(5, 1);

	give_a();

	zassert_equal_ptr(_current, &t2);
	kernel_unit_sched_ref_assert_ok();
}

/**
 * @brief After a wake of a thread with a lower priority, the current thread keeps the CPU.
 *
 * @details
 * - Setup: t1 runs with priority 5. t2 waits with priority 7.
 * - Action: z_sched_wake() and z_reschedule().
 * - Expected: t1 runs. t2 is ready.
 *
 * @ingroup kernel_unit_sched_ref_resched
 */
ZTEST(sched_ref_unit, test_reschedule_keeps_current_for_lower_priority)
{
	waiter_and_current(5, 7);

	give_a();

	zassert_equal_ptr(_current, &t1);
	zassert_equal(ref(&t2)->state, KERNEL_UNIT_SCHED_REF_READY);
	kernel_unit_sched_ref_assert_ok();
}

/**
 * @brief After a wake of a thread with the same priority, the current thread keeps the CPU.
 *
 * @details
 * - Setup: t1 runs with priority 5. t2 waits with priority 5.
 * - Action: z_sched_wake() and z_reschedule().
 * - Expected: t1 runs (the current thread wins a tie).
 *
 * @ingroup kernel_unit_sched_ref_resched
 */
ZTEST(sched_ref_unit, test_reschedule_keeps_current_for_equal_priority)
{
	waiter_and_current(5, 5);

	give_a();

	zassert_equal_ptr(_current, &t1);
	kernel_unit_sched_ref_assert_ok();
}

/**
 * @brief A cooperative current thread keeps the CPU after a wake of a higher priority.
 *
 * @details
 * - Setup: t1 runs with the cooperative priority -1. t2 waits with -2.
 * - Action: z_sched_wake() and z_reschedule().
 * - Expected: t1 runs.
 *
 * @ingroup kernel_unit_sched_ref_resched
 */
ZTEST(sched_ref_unit, test_reschedule_keeps_cooperative_current)
{
	waiter_and_current(-1, -2);

	give_a();

	zassert_equal_ptr(_current, &t1);
	kernel_unit_sched_ref_assert_ok();
}

/**
 * @brief Without a priority change, the current thread keeps the CPU in a tie.
 *
 * @details
 * - Setup: t1 runs with priority 5. t2 is ready with priority 5.
 * - Action: z_reschedule().
 * - Expected: t1 runs (the current thread wins a tie).
 *
 * @ingroup kernel_unit_sched_ref_resched
 */
ZTEST(sched_ref_unit, test_current_keeps_cpu_in_tie_without_prio_set)
{
	kernel_unit_sched_ref_install();
	kernel_unit_sched_ref_thread(&t1, 5);
	kernel_unit_sched_ref_thread(&t2, 5);
	kernel_unit_sched_ref_set_current(&t1);

	z_reschedule(&test_lock, test_key);

	zassert_equal_ptr(_current, &t1);
	kernel_unit_sched_ref_assert_ok();
}

/**
 * @brief After a priority change of the current thread, it loses a tie at the next selection.
 *
 * @details
 * This is the code, not the contract (finding R15 of the review). On one CPU,
 * z_thread_prio_set() of a ready thread moves it to the end of its new
 * priority in the run queue, also the current thread, and calls
 * update_cache(1). An example is the de-boost of the mutex owner in
 * k_mutex_unlock().
 * - Setup: t1 runs with priority 3. t2 is ready with priority 5.
 * - Action: z_thread_prio_set() gives t1 the priority 5. Then z_reschedule().
 * - Expected: z_thread_prio_set() returns true. t2 runs, because it is first
 *   in the run queue of priority 5. No check fails.
 *
 * @ingroup kernel_unit_sched_ref_resched
 */
ZTEST(sched_ref_unit, test_prio_set_of_current_loses_tie)
{
	kernel_unit_sched_ref_install();
	kernel_unit_sched_ref_thread(&t1, 3);
	kernel_unit_sched_ref_thread(&t2, 5);
	kernel_unit_sched_ref_set_current(&t1);

	zassert_true(z_thread_prio_set(&t1, 5));
	z_reschedule(&test_lock, test_key);

	zassert_equal_ptr(_current, &t2);
	zassert_false(kernel_unit_sched_ref.preempt_ok);
	kernel_unit_sched_ref_assert_ok();
}

/**
 * @brief A priority change of a ready thread moves it to the end of its priority.
 *
 * @details
 * - Setup: t1 runs with priority 1. t2, then t3 are ready with priority 5.
 * - Action: z_thread_prio_set() gives t2 the priority 5 again. Then t1 gets
 *   the priority 7, and z_reschedule().
 * - Expected: t3 runs: after the change of t2, t3 is first in the run queue
 *   of priority 5.
 *
 * @ingroup kernel_unit_sched_ref_resched
 */
ZTEST(sched_ref_unit, test_prio_set_of_ready_thread_moves_it_to_end)
{
	three_threads(1, 5, 5);
	kernel_unit_sched_ref_set_current(&t1);

	zassert_true(z_thread_prio_set(&t2, 5));
	zassert_true(z_thread_prio_set(&t1, 7));
	z_reschedule(&test_lock, test_key);

	zassert_equal_ptr(_current, &t3);
	kernel_unit_sched_ref_assert_ok();
}

/**
 * @brief After a priority change, a cooperative current thread does not keep the CPU.
 *
 * @details
 * This is the code, not the contract (finding R15 of the review).
 * update_cache(1) gives should_preempt() the value preempt_ok 1, so the rule
 * for cooperative threads does not apply at the next selection.
 * - Setup: t1 runs with the cooperative priority -1. t2 is ready with -2.
 * - Action: z_thread_prio_set() gives t1 the priority -1 again. Then
 *   z_reschedule().
 * - Expected: t2 runs. Without the priority change, t1 keeps the CPU (see
 *   test_reschedule_keeps_cooperative_current()).
 *
 * @ingroup kernel_unit_sched_ref_resched
 */
ZTEST(sched_ref_unit, test_prio_set_of_cooperative_current_yields_to_higher)
{
	kernel_unit_sched_ref_install();
	kernel_unit_sched_ref_thread(&t1, -1);
	kernel_unit_sched_ref_thread(&t2, -2);
	kernel_unit_sched_ref_set_current(&t1);

	zassert_true(z_thread_prio_set(&t1, -1));
	z_reschedule(&test_lock, test_key);

	zassert_equal_ptr(_current, &t2);
	kernel_unit_sched_ref_assert_ok();
}

/**
 * @brief An abort of another thread lets a higher thread take the CPU of a cooperative thread.
 *
 * @details
 * This is the code, not the requirement (finding P7-c, reference fake gap
 * RF-1). halt_thread() calls update_cache(1) for each target (sched.c:914),
 * so the rule for cooperative threads does not apply at the next selection.
 * A thread that aborts another thread does not reschedule.
 * - Setup: t1 runs with the cooperative priority -1. t2 is ready with -2
 *   (higher). t3 is ready with 5.
 * - Action: t1 aborts t3. Then z_reschedule() by t1.
 * - Expected: after the abort t1 still runs, but the selection rule gives
 *   t2: the check RUN_RULE_HOLDS fails as expected (Scheduler: RunRuleHolds,
 *   configuration coop_rule). At the reschedule, t2 runs. Without the abort,
 *   t1 keeps the CPU (see test_reschedule_keeps_cooperative_current()).
 *
 * @ingroup kernel_unit_sched_ref_resched
 */
ZTEST(sched_ref_unit, test_abort_of_other_thread_preempts_cooperative)
{
	three_threads(-1, -2, 5);
	kernel_unit_sched_ref_set_current(&t1);
	zassert_equal(kernel_unit_sched_ref_choices(), kernel_unit_sched_ref_bit(&t1));
	kernel_unit_sched_ref_expect(KERNEL_UNIT_SCHED_REF_RUN_RULE_HOLDS);

	kernel_unit_sched_ref_abort(&t3);

	zassert_equal(ref(&t3)->state, KERNEL_UNIT_SCHED_REF_DEAD);
	zassert_equal_ptr(_current, &t1);
	zassert_equal(kernel_unit_sched_ref_choices(), kernel_unit_sched_ref_bit(&t2));
	zassert_equal(kernel_unit_sched_ref.found, KERNEL_UNIT_SCHED_REF_RUN_RULE_HOLDS);

	z_reschedule(&test_lock, test_key);

	zassert_equal_ptr(_current, &t2);
	kernel_unit_sched_ref_assert_ok();
}

/**
 * @defgroup kernel_unit_sched_ref_misuse Misuse of the contract
 * @ingroup kernel_unit_sched_ref_tests
 * @brief The checks of the fake find the misuses that the invariants of MCScheduler find.
 */

/**
 * @brief The fake finds a wake with z_sched_wake_thread_locked() without the timeout abort.
 *
 * @details
 * This is the mutant @c wake_no_cancel of @c mc/MCScheduler.tla.
 * - Setup: t1 runs. t2 (7) waits on wq_a with 10 ticks. The test expects the
 *   check ArmedArePending.
 * - Action: arch_thread_return_value_set() of t2 with 0,
 *   z_sched_wake_thread_locked() of t2, z_reschedule(). No
 *   z_try_abort_thread_timeout().
 * - Expected: at the end of the critical section, the check ArmedArePending
 *   fails: t2 is ready with an armed timeout.
 *
 * @ingroup kernel_unit_sched_ref_misuse
 */
ZTEST(sched_ref_unit, test_detects_wake_without_timeout_abort)
{
	three_threads(0, 7, 7);
	kernel_unit_sched_ref_set_current(&t1);
	kernel_unit_sched_ref_wait(&t2, &wq_a, TEST_TIMEOUT);
	kernel_unit_sched_ref_expect(KERNEL_UNIT_SCHED_REF_ARMED_ARE_PENDING);

	arch_thread_return_value_set(&t2, 0);
	z_sched_wake_thread_locked(&t2);
	z_reschedule(&test_lock, test_key);

	zassert_equal(kernel_unit_sched_ref.found, KERNEL_UNIT_SCHED_REF_ARMED_ARE_PENDING);
}

/**
 * @brief With the timeout abort first, the same wake passes all checks.
 *
 * @details
 * - Setup: as in test_detects_wake_without_timeout_abort(), without an
 *   expected check.
 * - Action: z_try_abort_thread_timeout() of t2, then the same calls.
 * - Expected: t2 is ready with the value 0 and no armed timeout. No check
 *   fails.
 *
 * @ingroup kernel_unit_sched_ref_misuse
 */
ZTEST(sched_ref_unit, test_wake_after_timeout_abort_passes)
{
	three_threads(0, 7, 7);
	kernel_unit_sched_ref_set_current(&t1);
	kernel_unit_sched_ref_wait(&t2, &wq_a, TEST_TIMEOUT);

	(void)z_try_abort_thread_timeout(&t2);
	arch_thread_return_value_set(&t2, 0);
	z_sched_wake_thread_locked(&t2);
	z_reschedule(&test_lock, test_key);

	zassert_equal(ref(&t2)->state, KERNEL_UNIT_SCHED_REF_READY);
	zassert_equal(ref(&t2)->ret, 0);
	kernel_unit_sched_ref_assert_ok();
}

/**
 * @brief The fake finds a wake that ends without a reschedule.
 *
 * @details
 * This is the mutant @c missed_resched of @c mc/MCScheduler.tla.
 * - Setup: t1 runs with priority 5. t2 waits with priority 1.
 * - Action: z_sched_wake() on wq_a, then no z_reschedule() (the unit ends
 *   with k_spin_unlock()).
 * - Expected: kernel_unit_sched_ref_check() gives RunRuleHolds. With the
 *   check expected, kernel_unit_sched_ref_assert_ok() records it.
 *
 * @ingroup kernel_unit_sched_ref_misuse
 */
ZTEST(sched_ref_unit, test_detects_missed_reschedule)
{
	waiter_and_current(5, 1);

	zassert_true(z_sched_wake(&wq_a, 0, NULL));

	zassert_equal(kernel_unit_sched_ref_check(), KERNEL_UNIT_SCHED_REF_RUN_RULE_HOLDS);
	kernel_unit_sched_ref_expect(KERNEL_UNIT_SCHED_REF_RUN_RULE_HOLDS);
	kernel_unit_sched_ref_assert_ok();
	zassert_equal(kernel_unit_sched_ref.found, KERNEL_UNIT_SCHED_REF_RUN_RULE_HOLDS);
}

/**
 * @brief The fake finds a thread that leaves its wait queue and does not become ready.
 *
 * @details
 * - Setup: t1 runs. t2 (7) waits on wq_a. The test expects the check
 *   NoLostThread.
 * - Action: z_unpend_first_thread_locked() and arch_thread_return_value_set()
 *   with 0, then z_reschedule(). No z_sched_ready_locked().
 * - Expected: the check NoLostThread fails at the end of the critical
 *   section: t2 is neither pending nor ready.
 *
 * @ingroup kernel_unit_sched_ref_misuse
 */
ZTEST(sched_ref_unit, test_detects_lost_thread)
{
	three_threads(0, 7, 7);
	kernel_unit_sched_ref_set_current(&t1);
	kernel_unit_sched_ref_wait(&t2, &wq_a, K_FOREVER);
	kernel_unit_sched_ref_expect(KERNEL_UNIT_SCHED_REF_NO_LOST_THREAD);

	zassert_equal_ptr(z_unpend_first_thread_locked(&wq_a), &t2);
	arch_thread_return_value_set(&t2, 0);
	z_reschedule(&test_lock, test_key);

	zassert_equal(kernel_unit_sched_ref.found, KERNEL_UNIT_SCHED_REF_NO_LOST_THREAD);
	zassert_equal(ref(&t2)->state, KERNEL_UNIT_SCHED_REF_UNPENDED);
}

/**
 * @brief z_unpend_first_thread_locked(), the value and z_sched_ready_locked() are WakeFirstWith.
 *
 * @details
 * - Setup: t1 runs with priority 5. t2 (1) waits on wq_a.
 * - Action: z_unpend_first_thread_locked() on the empty wq_b, then on wq_a,
 *   arch_thread_return_value_set() with 0, z_sched_ready_locked(),
 *   z_reschedule().
 * - Expected: the call on wq_b returns NULL. t2 runs with the value 0. No
 *   check fails.
 *
 * @ingroup kernel_unit_sched_ref_misuse
 */
ZTEST(sched_ref_unit, test_wake_first_with_is_one_wake)
{
	waiter_and_current(5, 1);

	zassert_is_null(z_unpend_first_thread_locked(&wq_b));
	zassert_equal_ptr(z_unpend_first_thread_locked(&wq_a), &t2);
	arch_thread_return_value_set(&t2, 0);
	z_sched_ready_locked(&t2);
	z_reschedule(&test_lock, test_key);

	zassert_equal_ptr(_current, &t2);
	zassert_equal(ref(&t2)->ret, 0);
	kernel_unit_sched_ref_assert_ok();
}

/**
 * @brief The fake finds an init of a wait queue that has waiters.
 *
 * @details
 * The real z_waitq_init() sets the list to empty, and the waiters are lost.
 * - Setup: t1 runs. t2 waits on wq_a. The test expects the check MISUSE.
 * - Action: z_waitq_init() of wq_a.
 * - Expected: the check MISUSE fails.
 *
 * @ingroup kernel_unit_sched_ref_misuse
 */
ZTEST(sched_ref_unit, test_detects_init_of_wait_queue_with_waiters)
{
	waiter_and_current(5, 7);
	kernel_unit_sched_ref_expect(KERNEL_UNIT_SCHED_REF_MISUSE);

	z_waitq_init(&wq_b);
	zassert_equal(kernel_unit_sched_ref.found, 0U);

	z_waitq_init(&wq_a);
	zassert_equal(kernel_unit_sched_ref.found, KERNEL_UNIT_SCHED_REF_MISUSE);
}

/**
 * @brief An abort of a waiter by the current thread removes it and does not reschedule.
 *
 * @details
 * - Setup: t1 runs with priority 5. t2 (7) waits on wq_a with 10 ticks.
 * - Action: kernel_unit_sched_ref_abort() of t2.
 * - Expected: t2 is dead, out of the wait queue, with no armed timeout and no
 *   return value. t1 runs. No check fails.
 *
 * @ingroup kernel_unit_sched_ref_misuse
 */
ZTEST(sched_ref_unit, test_abort_of_waiter_leaves_wait_queue)
{
	three_threads(5, 7, 7);
	kernel_unit_sched_ref_set_current(&t1);
	kernel_unit_sched_ref_wait(&t2, &wq_a, TEST_TIMEOUT);

	kernel_unit_sched_ref_abort(&t2);

	zassert_equal(ref(&t2)->state, KERNEL_UNIT_SCHED_REF_DEAD);
	zassert_is_null(z_waitq_head(&wq_a));
	zassert_false(ref(&t2)->armed);
	zassert_false(ref(&t2)->has_ret);
	zassert_equal_ptr(_current, &t1);
	kernel_unit_sched_ref_assert_ok();
}
