/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @defgroup kernel_unit_scheduler kernel/scheduler.c
 * @ingroup kernel_unit_tests
 * @brief Design specification of kernel/scheduler.c, written as unit tests on the fakes of
 * kernel/sched.c.
 *
 * @par The unit and its contracts
 * @c kernel/scheduler.c has two parts (unit map, section 4):
 *
 * - Contract Scheduler (layer A of @c safety/spec/tla/lib/Scheduler.tla):
 *   z_sched_init(), z_sched_waitq_walk() (operator WakeWalk, with
 *   WaitQueue!Walked and WaitQueue!WalkStop) and z_sched_wait() (PendCurr,
 *   then Resume).
 * - Contract SchedApi (the public API): k_sched_lock(), k_sched_unlock(),
 *   k_reschedule() and k_sched_current_thread_query(). The model has no
 *   scheduler lock.
 *
 * Each function is short. It takes the scheduler lock and calls
 * @c kernel/sched.c, or it walks a wait queue. This application tests what
 * the code of scheduler.c does with the layer below: the arguments, the order
 * of the calls and the lock. The contract tests of z_sched_waitq_walk() and
 * z_sched_wait() on the real @c kernel/sched.c are in the suite
 * @c sched_contract (@ref kernel_unit_sched_contract_walk), which the
 * applications @c sched and @c sched_ref build.
 *
 * In this application, @c kthread.h, @c run_q.h, @c priority_q.h,
 * @c kspinlock.h and @c ipi.h are real (kernel_unit_real_headers() in
 * @c CMakeLists.txt). A test builds a wait queue with the real
 * _priq_wait_add() of @c priority_q.h, and the walk reads it with the real
 * macros of @c wait_q.h (a real copy in the shadow header).
 *
 * @par Interfaces below scheduler.c
 * - Scheduler (@c kernel/sched.c, fake group @c sched): z_pend_curr(),
 *   z_sched_lock_reschedule().
 * - Data of @c kernel/sched.c: @c _sched_spinlock (group @c sched).
 * - Architecture (group @c arch): arch_irq_lock(), arch_irq_unlock() (through
 *   k_spin_lock()), arch_is_in_isr() (in the assertions).
 *
 * @par Kconfig options that change scheduler.c
 * - @kconfig{CONFIG_WAITQ_SCALABLE}: the walk uses _WAIT_Q_FOR_EACH() on the
 *   red-black tree, else _WAIT_Q_FOR_EACH_SAFE() on the list.
 * - @kconfig{CONFIG_SCHED_SIMPLE}, @kconfig{CONFIG_SCHED_SCALABLE},
 *   @kconfig{CONFIG_SCHED_MULTIQ}: the init function of the run queue in
 *   z_sched_init().
 * - @kconfig{CONFIG_ASSERT}: the assertions of k_sched_lock() and
 *   k_sched_unlock().
 * - @kconfig{CONFIG_SCHED_CPU_MASK_PIN_ONLY} (one run queue for each CPU) and
 *   @kconfig{CONFIG_USERSPACE} (the verification functions) are not in this
 *   application.
 */

/**
 * @defgroup kernel_unit_scheduler_z_sched_init z_sched_init()
 * @ingroup kernel_unit_scheduler
 * @brief The init of the run queue at boot.
 */

/**
 * @defgroup kernel_unit_scheduler_k_sched_lock k_sched_lock()
 * @ingroup kernel_unit_scheduler
 * @brief The scheduler lock of the current thread: a nesting count in @c sched_locked.
 *
 * k_sched_lock() decrements @c _current->base.sched_locked under the scheduler
 * lock. A value other than 0 makes the thread not preemptible
 * (thread_is_preemptible() of @c kthread.h). The count goes down from 0 to
 * 255, 254 and so on: one nesting level for each call.
 */

/**
 * @defgroup kernel_unit_scheduler_k_sched_unlock k_sched_unlock()
 * @ingroup kernel_unit_scheduler
 * @brief The end of one level of the scheduler lock, and a reschedule.
 *
 * k_sched_unlock() increments @c sched_locked and calls
 * z_sched_lock_reschedule() with the key of the scheduler lock. Thus each
 * call is a reschedule point, also if the lock is still nested.
 */

/**
 * @defgroup kernel_unit_scheduler_k_reschedule k_reschedule()
 * @ingroup kernel_unit_scheduler
 * @brief A reschedule point on request (z_impl_k_reschedule()).
 */

/**
 * @defgroup kernel_unit_scheduler_k_sched_current_thread_query k_sched_current_thread_query()
 * @ingroup kernel_unit_scheduler
 * @brief The current thread (z_impl_k_sched_current_thread_query()).
 */

/**
 * @defgroup kernel_unit_scheduler_z_sched_waitq_walk z_sched_waitq_walk()
 * @ingroup kernel_unit_scheduler
 * @brief The walk of a wait queue under the scheduler lock (WaitQueue!Walked, WalkStop).
 *
 * The walk calls @c walk_func for each waiter in wait queue order until the
 * callback returns a value other than 0. Then it calls @c post_func once with
 * this value, still under the scheduler lock. The return value is the value
 * of the last call of @c walk_func, or 0. The walk itself wakes no thread:
 * the callbacks do (WakeWalk, contract tests).
 */

/**
 * @defgroup kernel_unit_scheduler_z_sched_wait z_sched_wait()
 * @ingroup kernel_unit_scheduler
 * @brief The wait of the current thread with the data of the waker (PendCurr, Resume).
 */

#include <string.h>
#include <zephyr/ztest.h>
#include <kernel_unit.h>
#include <fakes/fatal.h>
#ifdef CONFIG_ASSERT
#include <fakes/assert.h>
#endif

#include <kernel/scheduler.c>

#if defined(CONFIG_WAITQ_SCALABLE) || defined(CONFIG_SCHED_SCALABLE)
/*
 * The red-black queues call z_priq_rb_lessthan() of kernel/priority_queues.c
 * and the tree of lib/utils/rb.c. Both are data structures without a world
 * below, so they stay real (as in the application sched).
 */
#include <kernel/priority_queues.c>
#include <lib/utils/rb.c>
#endif

/* Swap data that a waker gives */
#define DATA(n) ((void *)(uintptr_t)(0x2000U + (n)))

static struct k_thread t1;
static struct k_thread t2;
static struct k_thread t3;
static _wait_q_t wq;
static struct k_spinlock obj_lock;

/*
 * The init of a wait queue: the code of the real z_waitq_init()
 * (wait_q.h:41-47 and 88-91). The shadow wait_q.h has a fake of it.
 */
static void waitq_init_real(_wait_q_t *w)
{
#ifdef CONFIG_WAITQ_SCALABLE
	w->waitq = (struct _priq_rb){
		.tree = {
			.lessthan_fn = z_priq_rb_lessthan,
		},
	};
#else
	sys_dlist_init(&w->waitq);
#endif
}

/* A new thread with the Zephyr priority prio. */
static void thread_init(struct k_thread *thread, int prio)
{
	memset(thread, 0, sizeof(*thread));
	thread->base.prio = (int8_t)prio;
}

/*
 * The thread waits on w: the wait queue part of add_to_waitq_locked()
 * (sched.c), with the real _priq_wait_add() of priority_q.h.
 */
static void wait_on(struct k_thread *thread, _wait_q_t *w)
{
	z_mark_thread_as_pending(thread);
	thread->base.pended_on = w;
	_priq_wait_add(&w->waitq, thread);
}

/* True if the scheduler lock is held now: one arch_irq_lock() without its unlock. */
static bool sched_lock_held(void)
{
	bool held = (unit_arch_irq_lock_fake.call_count == 1U) &&
		    (unit_arch_irq_unlock_fake.call_count == 0U);

#ifdef CONFIG_SPIN_VALIDATE
	held = held && (z_spin_lock_set_owner_fake.call_count == 1U) &&
	       (z_spin_lock_set_owner_fake.arg0_val == &_sched_spinlock);
#endif

	return held;
}

static void scheduler_unit_before(void *fixture)
{
	ARG_UNUSED(fixture);

	thread_init(&t1, 5);
	thread_init(&t2, 4);
	thread_init(&t3, 4);
	waitq_init_real(&wq);
	_kernel.cpus[0].current = &t1;
	unit_arch_irq_lock_fake.return_val = KERNEL_UNIT_IRQ_KEY;
}

/*
 * A failed __ASSERT() that a test does not expect stops the run (see the
 * application sched). A test that expects one resets the count.
 */
static void scheduler_unit_after(void *fixture)
{
	ARG_UNUSED(fixture);

#ifdef CONFIG_ASSERT
	if (assert_post_action_fake.call_count != 0U) {
		TC_PRINT("%u failed __ASSERT() in the test\n", assert_post_action_fake.call_count);
		ztest_test_fail();
	}
#endif
}

ZTEST_SUITE(scheduler_unit, NULL, NULL, scheduler_unit_before, scheduler_unit_after, NULL);

/* ------------------------------------------------------------------------- */

/**
 * @brief z_sched_init() gives an empty run queue that the backend can use.
 *
 * @details
 * - Setup: @c _kernel is all zeros (the run queue is not a valid list or
 *   tree).
 * - Action: z_sched_init().
 * - Expected: the run queue is empty (_priq_run_best() gives NULL). A thread
 *   added with _priq_run_add() is then the best thread, and after its removal
 *   the run queue is empty again. This is true for each run queue backend
 *   (@kconfig{CONFIG_SCHED_SIMPLE}, @kconfig{CONFIG_SCHED_SCALABLE},
 *   @kconfig{CONFIG_SCHED_MULTIQ}).
 *
 * @ingroup kernel_unit_scheduler_z_sched_init
 * @see z_sched_init()
 */
ZTEST(scheduler_unit, test_init_gives_empty_usable_run_queue)
{
	z_sched_init();

	zassert_is_null(_priq_run_best(&_kernel.ready_q.runq));
	_priq_run_add(&_kernel.ready_q.runq, &t2);
	zassert_equal_ptr(_priq_run_best(&_kernel.ready_q.runq), &t2);
	_priq_run_remove(&_kernel.ready_q.runq, &t2);
	zassert_is_null(_priq_run_best(&_kernel.ready_q.runq));
}

/* ------------------------------------------------------------------------- */

/**
 * @brief k_sched_lock() adds one nesting level, and the thread is not preemptible.
 *
 * @details
 * - Setup: t1 (Zephyr priority 5, preemptible) runs, without a scheduler
 *   lock.
 * - Action: k_sched_lock(), then k_sched_lock() again.
 * - Expected: @c sched_locked is 255 after the first call and 254 after the
 *   second. t1 is not preemptible. Each call takes and releases the
 *   scheduler lock once (with its key) and does not reschedule.
 *
 * @ingroup kernel_unit_scheduler_k_sched_lock
 * @see k_sched_lock()
 */
ZTEST(scheduler_unit, test_lock_nests_and_stops_preemption)
{
	zassert_true(thread_is_preemptible(&t1));

	k_sched_lock();
	zassert_equal(t1.base.sched_locked, 255U);
	zassert_false(thread_is_preemptible(&t1));
	k_sched_lock();
	zassert_equal(t1.base.sched_locked, 254U);

	zassert_equal(unit_arch_irq_lock_fake.call_count, 2U);
	zassert_equal(unit_arch_irq_unlock_fake.call_count, 2U);
	zassert_equal(unit_arch_irq_unlock_fake.arg0_val, KERNEL_UNIT_IRQ_KEY);
	zassert_equal(z_sched_lock_reschedule_fake.call_count, 0U);
}

/**
 * @brief k_sched_unlock() removes one level and gives the held lock to z_sched_lock_reschedule().
 *
 * @details
 * - Setup: t1 runs. It called k_sched_lock() twice.
 * - Action: k_sched_unlock(), then k_sched_unlock() again.
 * - Expected: @c sched_locked is 255 after the first call (t1 is still not
 *   preemptible) and 0 after the second (t1 is preemptible again). Each call
 *   takes the scheduler lock and calls z_sched_lock_reschedule() with its
 *   key. k_sched_unlock() itself does not release the lock:
 *   z_sched_lock_reschedule() does (update_cache(0), then reschedule(), in
 *   @c sched.c). Thus also an unlock of an inner level is a reschedule
 *   point.
 *
 * @ingroup kernel_unit_scheduler_k_sched_unlock
 * @see k_sched_unlock()
 */
ZTEST(scheduler_unit, test_unlock_reschedules_with_the_held_lock)
{
	t1.base.sched_locked = 254U;

	k_sched_unlock();
	zassert_equal(t1.base.sched_locked, 255U);
	zassert_false(thread_is_preemptible(&t1));
	zassert_equal(z_sched_lock_reschedule_fake.call_count, 1U);
	zassert_equal(z_sched_lock_reschedule_fake.arg0_val.key, KERNEL_UNIT_IRQ_KEY);
	zassert_equal(unit_arch_irq_unlock_fake.call_count, 0U);

	k_sched_unlock();
	zassert_equal(t1.base.sched_locked, 0U);
	zassert_true(thread_is_preemptible(&t1));
	zassert_equal(z_sched_lock_reschedule_fake.call_count, 2U);
	/* With CONFIG_ASSERT, the assertion "!arch_is_in_isr()" calls the arch fake. */
	zassert_call_history(unit_arch_irq_lock,
			     KERNEL_UNIT_IF_ENABLED(CONFIG_ASSERT, arch_is_in_isr),
			     z_sched_lock_reschedule, unit_arch_irq_lock,
			     KERNEL_UNIT_IF_ENABLED(CONFIG_ASSERT, arch_is_in_isr),
			     z_sched_lock_reschedule);
}

/**
 * @brief An unlock without a lock leaves the thread not preemptible (observation, no check).
 *
 * @details
 * Design observation (sched-app.md, part 2): no requirement states the
 * behavior of an unbalanced k_sched_unlock(). The API documentation says
 * that it "reverses the effect of a previous call to k_sched_lock()".
 * - Setup: t1 (Zephyr priority 5) runs, without a scheduler lock.
 * - Action: k_sched_unlock().
 * - Expected by the code: with @kconfig{CONFIG_ASSERT}, the assertion
 *   "sched_locked != 0" fails. Then (and without @kconfig{CONFIG_ASSERT}
 *   without a diagnostic) @c sched_locked is 1, the value of 255 nested
 *   locks. t1 is not preemptible until 255 more unlocks.
 *
 * @ingroup kernel_unit_scheduler_k_sched_unlock
 * @see k_sched_unlock()
 */
ZTEST(scheduler_unit, test_unlock_without_lock_leaves_thread_not_preemptible)
{
	k_sched_unlock();

#ifdef CONFIG_ASSERT
	zassert_equal(assert_post_action_fake.call_count, 1U);
	assert_post_action_fake.call_count = 0U;
#endif
	zassert_equal(t1.base.sched_locked, 1U);
	zassert_false(thread_is_preemptible(&t1));
	zassert_equal(z_sched_lock_reschedule_fake.call_count, 1U);
}

/**
 * @brief The 256th nested k_sched_lock() unlocks the thread (observation, no check).
 *
 * @details
 * Design observation (sched-app.md, part 2): the nesting count has 8 bits.
 * - Setup: t1 runs with 255 nested locks (@c sched_locked is 1).
 * - Action: k_sched_lock().
 * - Expected by the code: with @kconfig{CONFIG_ASSERT}, the assertion
 *   "sched_locked != 1" fails. Then (and without @kconfig{CONFIG_ASSERT}
 *   without a diagnostic) @c sched_locked is 0, and t1 is preemptible
 *   inside 256 nested locks.
 *
 * @ingroup kernel_unit_scheduler_k_sched_lock
 * @see k_sched_lock()
 */
ZTEST(scheduler_unit, test_lock_nesting_wraps_after_255_levels)
{
	t1.base.sched_locked = 1U;

	k_sched_lock();

#ifdef CONFIG_ASSERT
	zassert_equal(assert_post_action_fake.call_count, 1U);
	assert_post_action_fake.call_count = 0U;
#endif
	zassert_equal(t1.base.sched_locked, 0U);
	zassert_true(thread_is_preemptible(&t1));
}

/**
 * @brief k_sched_lock() and k_sched_unlock() in an ISR fail an assertion.
 *
 * @details
 * - Setup: @kconfig{CONFIG_ASSERT}. arch_is_in_isr() returns true. t1 is the
 *   interrupted thread, with one lock level for the unlock.
 * - Action: k_sched_lock(), then k_sched_unlock().
 * - Expected: each call fails its assertion "!arch_is_in_isr()" once. The
 *   code then continues (CONFIG_ASSERT_TEST) and changes the count of the
 *   interrupted thread.
 *
 * @ingroup kernel_unit_scheduler_k_sched_lock
 * @see k_sched_lock(), k_sched_unlock()
 */
ZTEST(scheduler_unit, test_lock_and_unlock_in_isr_assert)
{
	if (!IS_ENABLED(CONFIG_ASSERT)) {
		ztest_test_skip();
	}
#ifdef CONFIG_ASSERT
	arch_is_in_isr_fake.return_val = true;

	k_sched_lock();
	zassert_equal(assert_post_action_fake.call_count, 1U);
	zassert_equal(t1.base.sched_locked, 255U);
	k_sched_unlock();
	zassert_equal(assert_post_action_fake.call_count, 2U);
	zassert_equal(t1.base.sched_locked, 0U);
	assert_post_action_fake.call_count = 0U;
#endif
}

/* ------------------------------------------------------------------------- */

/**
 * @brief k_reschedule() gives the key of its scheduler lock to z_sched_lock_reschedule().
 *
 * @details
 * The key decides if sched.c can switch (resched(): an unlocked key, not in
 * an ISR). The API documentation of k_reschedule() (ZEP-SRS-2-19) says
 * "provided interrupts were not locked when invoked".
 * - Setup: t1 runs. arch_irq_lock() returns 0 (no outer lock), then
 *   KERNEL_UNIT_IRQ_KEY (an outer irq_lock()).
 * - Action: k_reschedule() two times.
 * - Expected: each call takes the scheduler lock and calls
 *   z_sched_lock_reschedule() with the key of this lock: 0, then
 *   KERNEL_UNIT_IRQ_KEY. k_reschedule() does not release the lock itself.
 *
 * @ingroup kernel_unit_scheduler_k_reschedule
 * @see z_impl_k_reschedule()
 */
ZTEST(scheduler_unit, test_reschedule_gives_its_key_to_sched_lock_reschedule)
{
	static unsigned int keys[] = {0U, KERNEL_UNIT_IRQ_KEY};

	SET_RETURN_SEQ(unit_arch_irq_lock, keys, ARRAY_SIZE(keys));

	z_impl_k_reschedule();
	z_impl_k_reschedule();

	zassert_equal(z_sched_lock_reschedule_fake.call_count, 2U);
	zassert_equal(z_sched_lock_reschedule_fake.arg0_history[0].key, 0U);
	zassert_equal(z_sched_lock_reschedule_fake.arg0_history[1].key, KERNEL_UNIT_IRQ_KEY);
	zassert_equal(unit_arch_irq_unlock_fake.call_count, 0U);
}

/**
 * @brief k_sched_current_thread_query() returns the current thread.
 *
 * @details
 * - Setup: t1 runs, then t2.
 * - Action: z_impl_k_sched_current_thread_query().
 * - Expected: t1, then t2. No lock and no call below.
 *
 * @ingroup kernel_unit_scheduler_k_sched_current_thread_query
 * @see z_impl_k_sched_current_thread_query()
 */
ZTEST(scheduler_unit, test_current_thread_query_returns_current)
{
	zassert_equal_ptr(z_impl_k_sched_current_thread_query(), &t1);
	_kernel.cpus[0].current = &t2;
	zassert_equal_ptr(z_impl_k_sched_current_thread_query(), &t2);
	zassert_equal(kernel_unit_history_len(), 0U);
}

/* ------------------------------------------------------------------------- */

/* What the callbacks of a walk saw. */
struct walk_log {
	/* walk_func returns stop_value at its call number stop_at (1 is the first). */
	size_t stop_at;
	int stop_value;
	/* walk_func removes each thread from the wait queue (list backend only). */
	bool remove;
	struct k_thread *seen[4];
	size_t n_seen;
	bool walk_locked;
	unsigned int post_calls;
	int post_status;
	size_t post_seen;
	bool post_locked;
};

static int walk_record(struct k_thread *thread, void *data)
{
	struct walk_log *log = data;

	log->walk_locked = log->walk_locked && sched_lock_held();
	if (log->n_seen < ARRAY_SIZE(log->seen)) {
		log->seen[log->n_seen] = thread;
	}
	log->n_seen++;
#ifndef CONFIG_WAITQ_SCALABLE
	if (log->remove) {
		sys_dlist_remove(&thread->base.qnode_dlist);
	}
#endif

	return (log->n_seen == log->stop_at) ? log->stop_value : 0;
}

static void post_record(int status, void *data)
{
	struct walk_log *log = data;

	log->post_calls++;
	log->post_status = status;
	log->post_seen = log->n_seen;
	log->post_locked = sched_lock_held();
}

/* t1 (6), t2 (4) and t3 (4) wait on wq, in this order. The wait queue order is t2, t3, t1. */
static void three_waiters(void)
{
	thread_init(&t1, 6);
	wait_on(&t1, &wq);
	wait_on(&t2, &wq);
	wait_on(&t3, &wq);
}

/**
 * @brief The walk visits each waiter in wait queue order, then post_func once, all under the lock.
 *
 * @details
 * WaitQueue!Walked(o, Stop) with Stop always FALSE: all waiters.
 * - Setup: t1 (Zephyr priority 6), t2 (4) and t3 (4) wait on wq, in this
 *   order of arrival.
 * - Action: z_sched_waitq_walk() with walk_func and post_func that record
 *   their calls, both return or give 0.
 * - Expected: walk_func sees t2, t3, t1 (a higher priority first, then the
 *   order of arrival). post_func is called once, after the last walk_func,
 *   with the status 0. Both callbacks run with the scheduler lock held (one
 *   k_spin_lock() of @c _sched_spinlock). The walk returns 0, releases the
 *   lock with its key, and changes no thread: the waiters are still
 *   pending, and no wake and no reschedule is called.
 *
 * @ingroup kernel_unit_scheduler_z_sched_waitq_walk
 * @see z_sched_waitq_walk()
 */
ZTEST(scheduler_unit, test_walk_visits_waiters_in_order_then_post_under_lock)
{
	struct walk_log log = {.walk_locked = true};

	three_waiters();

	zassert_equal(z_sched_waitq_walk(&wq, walk_record, post_record, &log), 0);

	zassert_equal(log.n_seen, 3U);
	zassert_equal_ptr(log.seen[0], &t2);
	zassert_equal_ptr(log.seen[1], &t3);
	zassert_equal_ptr(log.seen[2], &t1);
	zassert_true(log.walk_locked);
	zassert_equal(log.post_calls, 1U);
	zassert_equal(log.post_status, 0);
	zassert_equal(log.post_seen, 3U);
	zassert_true(log.post_locked);
	zassert_equal(unit_arch_irq_unlock_fake.call_count, 1U);
	zassert_equal(unit_arch_irq_unlock_fake.arg0_val, KERNEL_UNIT_IRQ_KEY);
	zassert_true(z_is_thread_pending(&t1));
	zassert_true(z_is_thread_pending(&t2));
	zassert_true(z_is_thread_pending(&t3));
	zassert_equal(z_sched_wake_thread_locked_fake.call_count, 0U);
	zassert_equal(z_sched_lock_reschedule_fake.call_count, 0U);
}

/**
 * @brief A return value other than 0 stops the walk, and post_func and the caller get it.
 *
 * @details
 * WaitQueue!Walked and WaitQueue!WalkStop: the walk stops after the first
 * waiter with Stop, this waiter included.
 * - Setup: as above (wait queue order t2, t3, t1).
 * - Action: z_sched_waitq_walk() with a walk_func that returns 7 at its
 *   second call.
 * - Expected: walk_func sees t2 and t3, not t1. post_func gets the status
 *   7, and the walk returns 7.
 *
 * @ingroup kernel_unit_scheduler_z_sched_waitq_walk
 * @see z_sched_waitq_walk()
 */
ZTEST(scheduler_unit, test_walk_stops_at_nonzero_return)
{
	struct walk_log log = {.walk_locked = true, .stop_at = 2U, .stop_value = 7};

	three_waiters();

	zassert_equal(z_sched_waitq_walk(&wq, walk_record, post_record, &log), 7);

	zassert_equal(log.n_seen, 2U);
	zassert_equal_ptr(log.seen[0], &t2);
	zassert_equal_ptr(log.seen[1], &t3);
	zassert_equal(log.post_calls, 1U);
	zassert_equal(log.post_status, 7);
	zassert_equal(log.post_seen, 2U);
}

/**
 * @brief Without post_func, the walk only calls walk_func and returns its value.
 *
 * @details
 * - Setup: as above.
 * - Action: z_sched_waitq_walk() with post_func NULL and a walk_func that
 *   returns -3 at its first call.
 * - Expected: walk_func sees t2 only. The walk returns -3 (a negative value
 *   also stops it) and releases the lock.
 *
 * @ingroup kernel_unit_scheduler_z_sched_waitq_walk
 * @see z_sched_waitq_walk()
 */
ZTEST(scheduler_unit, test_walk_without_post_func_returns_walk_value)
{
	struct walk_log log = {.walk_locked = true, .stop_at = 1U, .stop_value = -3};

	three_waiters();

	zassert_equal(z_sched_waitq_walk(&wq, walk_record, NULL, &log), -3);

	zassert_equal(log.n_seen, 1U);
	zassert_equal_ptr(log.seen[0], &t2);
	zassert_equal(unit_arch_irq_unlock_fake.call_count, 1U);
}

/**
 * @brief The walk of an empty wait queue calls only post_func, with 0.
 *
 * @details
 * - Setup: wq has no waiter.
 * - Action: z_sched_waitq_walk() with the recording callbacks.
 * - Expected: no call of walk_func, one call of post_func with 0 under the
 *   lock. The walk returns 0.
 *
 * @ingroup kernel_unit_scheduler_z_sched_waitq_walk
 * @see z_sched_waitq_walk()
 */
ZTEST(scheduler_unit, test_walk_of_empty_queue_calls_post_func_with_zero)
{
	struct walk_log log = {.walk_locked = true};

	zassert_equal(z_sched_waitq_walk(&wq, walk_record, post_record, &log), 0);

	zassert_equal(log.n_seen, 0U);
	zassert_equal(log.post_calls, 1U);
	zassert_equal(log.post_status, 0);
	zassert_true(log.post_locked);
}

/**
 * @brief With the list backend, walk_func can remove each visited thread.
 *
 * @details
 * The rule of scheduler.h:71-74: walk_func can remove the thread that it
 * gets only with @kconfig{CONFIG_WAITQ_SCALABLE} off, or on the last step of
 * the walk. Without the option the walk uses _WAIT_Q_FOR_EACH_SAFE().
 * - Setup: as above. The test runs only without
 *   @kconfig{CONFIG_WAITQ_SCALABLE}.
 * - Action: z_sched_waitq_walk() with a walk_func that removes each thread
 *   from the list (as event_walk_op() does with z_sched_wake_thread_locked()).
 * - Expected: walk_func sees t2, t3 and t1, and the wait queue is empty.
 *
 * @ingroup kernel_unit_scheduler_z_sched_waitq_walk
 * @see z_sched_waitq_walk()
 */
ZTEST(scheduler_unit, test_walk_with_list_backend_permits_removal)
{
	struct walk_log log = {.walk_locked = true, .remove = true};

	if (IS_ENABLED(CONFIG_WAITQ_SCALABLE)) {
		ztest_test_skip();
	}

	three_waiters();

	zassert_equal(z_sched_waitq_walk(&wq, walk_record, post_record, &log), 0);

	zassert_equal(log.n_seen, 3U);
	zassert_equal_ptr(log.seen[2], &t1);
#ifndef CONFIG_WAITQ_SCALABLE
	zassert_true(sys_dlist_is_empty(&wq.waitq));
#endif
}

/* ------------------------------------------------------------------------- */

/* The custom fake of z_pend_curr(): a waker sets the swap data of the waiting thread. */
static int pend_and_set_data(struct k_spinlock *lock, k_spinlock_key_t key, _wait_q_t *wait_q,
			     k_timeout_t timeout)
{
	ARG_UNUSED(lock);
	ARG_UNUSED(key);
	ARG_UNUSED(wait_q);
	ARG_UNUSED(timeout);

	_current->base.swap_data = DATA(2);

	return 7;
}

/**
 * @brief z_sched_wait() waits with the arguments of the caller, then gives the swap data.
 *
 * @details
 * PendCurr(a, o, to), then Resume(a): the return value is swapRet, and the
 * data is swapData, which the waker writes during the wait.
 * - Setup: t1 runs with the swap data DATA(1). z_pend_curr() is a fake that
 *   writes DATA(2) to the swap data of the current thread (the waker) and
 *   returns 7.
 * - Action: z_sched_wait() with the lock of the object, its key, wq, a
 *   timeout of 10 ticks and a pointer for the data.
 * - Expected: one call of z_pend_curr() with the same lock, key, wait queue
 *   and timeout. z_sched_wait() returns 7, and the data is DATA(2): the code
 *   reads the swap data after the wait.
 *
 * @ingroup kernel_unit_scheduler_z_sched_wait
 * @see z_sched_wait()
 */
ZTEST(scheduler_unit, test_wait_forwards_arguments_and_reads_data_after_wait)
{
	k_spinlock_key_t key = {.key = KERNEL_UNIT_IRQ_KEY};
	void *data = NULL;

	t1.base.swap_data = DATA(1);
	z_pend_curr_fake.custom_fake = pend_and_set_data;

	zassert_equal(z_sched_wait(&obj_lock, key, &wq, K_TICKS(10), &data), 7);

	zassert_equal(z_pend_curr_fake.call_count, 1U);
	zassert_equal_ptr(z_pend_curr_fake.arg0_val, &obj_lock);
	zassert_equal(z_pend_curr_fake.arg1_val.key, KERNEL_UNIT_IRQ_KEY);
	zassert_equal_ptr(z_pend_curr_fake.arg2_val, &wq);
	zassert_true(K_TIMEOUT_EQ(z_pend_curr_fake.arg3_val, K_TICKS(10)));
	zassert_equal_ptr(data, DATA(2));
}

/**
 * @brief z_sched_wait() with data NULL only returns the value of the wait.
 *
 * @details
 * - Setup: as above, z_pend_curr() returns -EAGAIN (a timeout).
 * - Action: z_sched_wait() with data NULL and K_FOREVER.
 * - Expected: z_sched_wait() returns -EAGAIN and writes no data.
 *
 * @ingroup kernel_unit_scheduler_z_sched_wait
 * @see z_sched_wait()
 */
ZTEST(scheduler_unit, test_wait_with_null_data_returns_value)
{
	k_spinlock_key_t key = {.key = 0U};

	z_pend_curr_fake.return_val = -EAGAIN;

	zassert_equal(z_sched_wait(&obj_lock, key, &wq, K_FOREVER, NULL), -EAGAIN);
	zassert_equal(z_pend_curr_fake.call_count, 1U);
	zassert_true(K_TIMEOUT_EQ(z_pend_curr_fake.arg3_val, K_FOREVER));
}
