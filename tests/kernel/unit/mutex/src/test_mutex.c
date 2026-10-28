/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @defgroup kernel_unit_mutex kernel/mutex.c
 * @ingroup kernel_unit_tests
 * @brief Design specification of kernel/mutex.c, written as unit tests.
 *
 * @par The mutex object
 * A mutex (@c struct @c k_mutex) has these parts:
 * - @c owner: the thread that holds the mutex, or NULL.
 * - @c lock_count: the number of locks of the owner. 0 means "free".
 * - @c wait_q: the wait queue of the threads that wait for the mutex. The
 *   scheduler sorts it by priority.
 * - @c held_node: with priority inheritance, the node of the mutex in the
 *   list @c held_mutexes of its owner.
 * - @c obj_core: with @kconfig{CONFIG_OBJ_CORE_MUTEX}, the object core.
 *
 * With priority inheritance, each thread (@c struct @c k_thread) also has:
 * - @c held_mutexes: the list of the mutexes that the thread holds.
 * - @c mutex_pended_on: the mutex that the thread waits for, or NULL.
 * - @c orig_prio: the priority of the thread before the first boost. The
 *   unit records it when the thread gets its first mutex.
 *
 * @par Ownership and recursion
 * Only one thread holds a mutex. k_mutex_lock() of a free mutex makes the
 * current thread the owner, with @c lock_count 1. The owner can lock the
 * mutex again: @c lock_count counts the locks, and the owner must unlock
 * the mutex as many times. Only the owner can unlock the mutex. The last
 * unlock gives the mutex to the first waiting thread, or makes it free.
 * The new owner gets the mutex with @c lock_count 1 and the wait result 0.
 *
 * @par Priority inheritance and its bound
 * A thread that waits for a mutex raises the priority of the owner to its
 * own priority, if this priority is higher. Thus a thread with a middle
 * priority cannot delay the owner, and the waiting thread with the high
 * priority (priority inversion). If the owner waits for a second mutex,
 * the unit also raises the owner of that mutex, and so on along the chain
 * of owners. The chain walk stops at the end of the chain, at a thread that
 * does not wait, at a cycle through the first mutex, or after
 * @c MUTEX_CHAIN_WALK_MAX_HOPS (16) steps.
 *
 * @kconfig{CONFIG_PRIORITY_CEILING} limits each raised priority: the unit
 * never raises a priority above the ceiling. If the ceiling is
 * @kconfig{CONFIG_NUM_PREEMPT_PRIORITIES} or lower, the code of the
 * priority inheritance is not in the build (@c Z_MUTEX_PI_ENABLED is 0).
 *
 * The unit lowers the priority again in two cases. On the last unlock, the
 * owner gets the highest priority of the waiting threads of the mutexes
 * that it still holds, and at least its original priority. After a wait
 * that timed out, the waiting thread does the same calculation for the
 * owner of the mutex. Only the first owner of a chain gets the lower
 * priority after a timeout.
 *
 * @par Locks
 * All mutexes use one spinlock, @c mutex_lock (static in mutex.c). The
 * chain walk and the calculation of the priority read the owners and the
 * wait queues of other mutexes, so one lock for all mutexes is necessary.
 * The unit changes priorities (z_thread_prio_set()) only while it holds
 * @c mutex_lock. Thus no other thread can lock, unlock or wait for a mutex
 * between the calculation of a priority and its change. With more than one
 * CPU, the unit also locks the scheduler spinlock (LOCK_SCHED_SPINLOCK)
 * inside @c mutex_lock, while it reads the wait queues and while it gives the
 * mutex to a new owner. Each path releases @c mutex_lock with the key of
 * the lock:
 * - k_spin_unlock(), if no thread became ready.
 * - z_reschedule(), if the unlock gave the mutex to a waiting thread, or if
 *   a priority change after a timeout needs a reschedule.
 * - z_pend_curr(), if k_mutex_lock() waits. After a timeout,
 *   k_mutex_lock() locks @c mutex_lock a second time.
 *
 * k_mutex_init() does not lock. An unlock of a recursive lock does not lock.
 *
 * @par Interfaces below mutex.c
 * - Scheduler (@c ksched.h): z_pend_curr(), z_reschedule(),
 *   z_unpend_first_thread_locked(), z_sched_ready_locked(),
 *   z_thread_prio_set().
 * - Wait queue (@c wait_q.h): z_waitq_init(), z_waitq_head_locked().
 * - Architecture: arch_thread_return_value_set(), arch_is_in_isr(), and
 *   arch_irq_lock() and arch_irq_unlock() through k_spin_lock() and
 *   k_spin_unlock().
 * - Pure helpers that stay real in the test (see below): z_is_prio_higher(),
 *   z_get_new_prio_with_ceiling() (@c ksched.h), z_is_thread_pending(),
 *   z_is_thread_ready() (@c kthread.h), z_is_inactive_timeout()
 *   (@c timeout_q.h).
 * - Object core: k_obj_core_init_and_link(), K_OBJ_TYPE_DEFINE().
 * - Kernel objects: k_object_init().
 * - System call checks: K_SYSCALL_OBJ(), K_SYSCALL_OBJ_INIT(), K_OOPS().
 * - Logging: LOG_DBG() of the module @c os.
 * - Tracing: the SYS_PORT_TRACING_OBJ_* hooks. They are empty in the test.
 *
 * @kunit_interfaces
 *
 * @par Kconfig options that change mutex.c
 * - @kconfig{CONFIG_PRIORITY_CEILING} and
 *   @kconfig{CONFIG_NUM_PREEMPT_PRIORITIES}: priority inheritance and its
 *   bound (see above).
 * - @kconfig{CONFIG_MUTEX_DEADLOCK_DETECT} (needs @kconfig{CONFIG_ASSERT}):
 *   the chain walk of a K_FOREVER lock asserts if the chain is a cycle back
 *   to the current thread and each thread in it waits forever.
 * - @kconfig{CONFIG_ASSERT}: the ISR checks and the check of the lock count.
 * - CHECKIF() options (@kconfig{CONFIG_RUNTIME_ERROR_CHECKS},
 *   @kconfig{CONFIG_NO_RUNTIME_CHECKS}, @kconfig{CONFIG_ASSERT_ON_ERRORS}):
 *   the owner checks of k_mutex_unlock().
 * - @kconfig{CONFIG_MP_MAX_NUM_CPUS}: the scheduler spinlock inside
 *   @c mutex_lock.
 * - @kconfig{CONFIG_USERSPACE}: the verification functions
 *   z_vrfy_k_mutex_*() and the kernel object of the mutex.
 * - @kconfig{CONFIG_OBJ_CORE_MUTEX}: the object type of the mutexes.
 * - @kconfig{CONFIG_KERNEL_LOG_LEVEL}: only with the level DBG, the
 *   LOG_DBG() calls run. The unittest build (-O0) has their code also with
 *   a lower level, so the test always links the fake group
 *   @c log_minimal.
 *
 * @par Test method
 * The tests call z_impl_k_mutex_*() and z_vrfy_k_mutex_*() directly. The
 * test threads are @c struct @c k_thread objects with a priority; a test
 * makes one of them the current thread (@c _current, fake group @c init).
 * The pure priority and thread state helpers are real copies in the shadow
 * headers (user decision of 2026-10-20), so the tests check the inheritance
 * rules with the real priority semantics. A drift guard keeps the copies
 * equal to the real headers. All functions with side effects are FFF
 * fakes. The tests use these models (see also the group kernel_unit_models
 * in @c kernel_unit_models.h):
 * - Lock: the lock model of kernel_unit_models.h counts the holds of
 *   @c mutex_lock and of the nested scheduler spinlock.
 * - Wait queues: an array of waiting threads for each mutex, sorted by
 *   priority (first in, first out for equal priorities).
 *   z_waitq_head_locked() returns the first thread.
 *   z_unpend_first_thread_locked() removes it and clears its state
 *   "pending". z_pend_curr() adds the current thread, releases the lock,
 *   and runs an action of another thread. If no action wakes the current
 *   thread, the wait is a timeout (-EAGAIN), and the thread leaves the wait
 *   queue.
 * - Wake: arch_thread_return_value_set() of the waiting thread ends its
 *   wait with this value.
 * - Priority: z_thread_prio_set() sets the priority of the thread. It
 *   returns @c return_val of its fake: "the scheduler must reschedule".
 *
 * The models state assumptions about the scheduler. They do not show that
 * the real scheduler meets them.
 *
 * @par Structure of the tests
 * Each public function of mutex.c has one group below this group. A system
 * call has one group for z_impl_k_mutex_*() and z_vrfy_k_mutex_*(). The
 * static functions and the data of mutex.c have the last group. Each test is
 * in the group of the function under test. The rules below (assertions,
 * system call verification, object core, debug logging) apply to more than
 * one function. Their tests are in the group of the function that they call.
 *
 * @par Assertions
 * With CONFIG_ASSERT, k_mutex_lock() and k_mutex_unlock() assert that they
 * do not run in an ISR, and k_mutex_unlock() asserts a lock count above 0.
 * The ISR checks are the first calls of k_mutex_lock() and
 * k_mutex_unlock(). In the test, the assertion hook returns, and the unit
 * continues.
 *
 * @par System call verification
 * With CONFIG_USERSPACE, z_vrfy_k_mutex_*() check the mutex object before
 * the implementation.
 * A system call from a user thread goes to z_vrfy_k_mutex_*(). This
 * function checks that the pointer is a mutex object of the kernel that the
 * thread has access to. z_vrfy_k_mutex_init() uses K_SYSCALL_OBJ_INIT():
 * the object can be initialized or not. The lock and the unlock use
 * K_SYSCALL_OBJ(): the object must be initialized. If the check fails,
 * K_OOPS() stops the thread. Otherwise the function calls
 * z_impl_k_mutex_*() with the same arguments and returns its result.
 *
 * In the test, K_OOPS() calls the fake unit_syscall_oops(). The tests use
 * zassert_stopped_by_oops() (kernel_unit_models.h): the oops jumps back to
 * the test, so the implementation does not run.
 *
 * @par Object core
 * With CONFIG_OBJ_CORE_MUTEX, each mutex has an object core of the mutex
 * type.
 *
 * @par Debug logging
 * The LOG_DBG() calls read the thread state, and they do not change the
 * behavior.
 * With @kconfig{CONFIG_KERNEL_LOG_LEVEL} DBG, mutex.c logs each lock, each
 * priority change and each hand-over. The arguments read the state of the
 * owner (z_is_thread_ready()) and the priority of the new owner. With a
 * lower level, the log calls do not run. The history helpers ignore the
 * log calls, so all tests run in all scenarios: they show the same results
 * with and without the logging.
 */

/**
 * @defgroup kernel_unit_mutex_k_mutex_init k_mutex_init()
 * @ingroup kernel_unit_mutex
 * @brief k_mutex_init() makes a free mutex.
 *
 * k_mutex_init() sets the owner to NULL and the lock count to 0. It
 * initializes the wait queue, the node of the list of held mutexes (with
 * priority inheritance), the kernel object (with
 * @kconfig{CONFIG_USERSPACE}) and the object core (with
 * @kconfig{CONFIG_OBJ_CORE_MUTEX}). It does not lock: until k_mutex_init()
 * returns, only the caller uses the mutex. It has no error path.
 *
 * @par Functions in kernel/mutex.c
 * - z_impl_k_mutex_init()
 * - z_vrfy_k_mutex_init(), static inline, with @kconfig{CONFIG_USERSPACE}
 */

/**
 * @defgroup kernel_unit_mutex_k_mutex_lock k_mutex_lock()
 * @ingroup kernel_unit_mutex
 * @brief k_mutex_lock() takes a free mutex, counts a recursive lock, or waits for the owner and
 * raises its priority.
 *
 * @par Lock without a wait
 * k_mutex_lock() of a free mutex, a recursive lock, and K_NO_WAIT.
 * If the mutex is free (lock count 0) or the current thread holds it,
 * k_mutex_lock() increments the lock count, makes the current thread the
 * owner and returns 0. On the first lock of a mutex, the unit adds the
 * mutex to the list of held mutexes of the thread. If this list was empty,
 * the unit records the priority of the thread as its original priority.
 * If another thread holds the mutex, K_NO_WAIT gives -EBUSY and changes
 * nothing. These paths lock @c mutex_lock and release it with
 * k_spin_unlock().
 *
 * @par Lock with a wait
 * k_mutex_lock() of a mutex that another thread holds.
 * With a timeout other than K_NO_WAIT, k_mutex_lock() waits on the wait
 * queue of the mutex with z_pend_curr(). z_pend_curr() releases
 * @c mutex_lock. If the owner unlocks the mutex, the unlock gives the
 * mutex to the first waiting thread and wakes it with the result 0. Thus
 * the waiting thread is the owner when k_mutex_lock() returns 0: it does
 * not lock again.
 *
 * With priority inheritance, the thread records the mutex in
 * @c mutex_pended_on before the wait and clears it after the wait. After
 * a timeout, k_mutex_lock() locks @c mutex_lock again, lowers the priority
 * of the owner (see "Priority restore" in @ref kernel_unit_mutex_static)
 * and returns -EAGAIN.
 * Without priority inheritance, k_mutex_lock() returns the result of
 * z_pend_curr() without a change.
 *
 * @par Priority inheritance
 * A waiting thread raises the priority of the owners along the chain.
 * Before the wait, k_mutex_lock() computes the boost priority: the higher
 * of the priorities of the current thread and of the owner, limited by
 * @kconfig{CONFIG_PRIORITY_CEILING}. Then it walks the chain of owners:
 * the owner of the mutex, the owner of the mutex that this owner waits for,
 * and so on. It raises each owner with a lower priority to the boost
 * priority with z_thread_prio_set(). The walk stops at an owner that does
 * not wait (no @c mutex_pended_on, or not in the state "pending"), at a
 * cycle back to the first mutex, or after @c MUTEX_CHAIN_WALK_MAX_HOPS
 * steps. All priority changes occur while the unit holds @c mutex_lock.
 *
 * These tests exist only with priority inheritance (@c Z_MUTEX_PI_ENABLED).
 *
 * @par Chain walk and hop limit
 * The boost of a waiting thread follows the chain of owners, with a bound
 * on the steps.
 * If the owner of the mutex waits for a second mutex, k_mutex_lock() also
 * raises the owner of that mutex, and so on. All owners get the same boost
 * priority: the higher of the waiter and the first owner, limited by the
 * ceiling. The walk stops:
 * - at an owner with no @c mutex_pended_on, or that is not in the state
 *   "pending" (a stale @c mutex_pended_on after a timeout),
 * - when the next mutex is the first mutex (a cycle through the first
 *   mutex),
 * - after @c MUTEX_CHAIN_WALK_MAX_HOPS (16) steps. This is a bound of the
 *   time with @c mutex_lock held, not a limit of the chain length: owners
 *   after the limit keep their priority (a documented limit of mutex.c).
 *
 * These tests exist only with priority inheritance.
 *
 * @par Deadlock detection
 * With CONFIG_MUTEX_DEADLOCK_DETECT, a K_FOREVER lock that closes a cycle
 * of waits asserts.
 * The chain walk of k_mutex_lock() also looks for a deadlock. A deadlock
 * is a cycle: an owner in the chain waits for a mutex that the current
 * thread holds. The unit asserts only if the current thread and each
 * owner in the chain up to the cycle wait forever (K_FOREVER, no active
 * timeout). A cycle with a finite timeout ends with -EAGAIN, so it is not a
 * deadlock. After the assertion, the walk stops. In the test, the
 * assertion hook returns, and the unit continues with the wait.
 *
 * These tests exist only with @kconfig{CONFIG_MUTEX_DEADLOCK_DETECT}
 * (scenarios "deadlock_detect" and "all").
 *
 * @par Functions in kernel/mutex.c
 * - z_impl_k_mutex_lock(). The priority inheritance code is in it only if
 *   @c Z_MUTEX_PI_ENABLED is 1. The deadlock detection is in it only with
 *   @kconfig{CONFIG_MUTEX_DEADLOCK_DETECT}.
 * - z_vrfy_k_mutex_lock(), static inline, with @kconfig{CONFIG_USERSPACE}
 */

/**
 * @defgroup kernel_unit_mutex_k_mutex_unlock k_mutex_unlock()
 * @ingroup kernel_unit_mutex
 * @brief k_mutex_unlock() checks the owner, counts down a recursive lock, and gives the mutex to
 * the first waiting thread.
 *
 * k_mutex_unlock() returns -EINVAL if the mutex has no owner and -EPERM if
 * the current thread is not the owner. These checks are CHECKIF():
 * @kconfig{CONFIG_NO_RUNTIME_CHECKS} removes them, and
 * @kconfig{CONFIG_ASSERT_ON_ERRORS} makes them assertions. They occur
 * before the lock. If the lock count is above 1, k_mutex_unlock() only
 * decrements it, without a lock. The last unlock locks @c mutex_lock,
 * removes the mutex from the held list of the owner, lowers the priority
 * of the owner (see "Priority restore" in @ref kernel_unit_mutex_static),
 * and gives the mutex
 * to the first waiting thread. The new owner gets the lock count 1, the
 * wait result 0 and the state "ready". Then the unit releases the lock with
 * z_reschedule(). If no thread waits, the mutex becomes free, and the unit
 * releases the lock with k_spin_unlock().
 *
 * @par Functions in kernel/mutex.c
 * - z_impl_k_mutex_unlock()
 * - z_vrfy_k_mutex_unlock(), static inline, with @kconfig{CONFIG_USERSPACE}
 */

/**
 * @defgroup kernel_unit_mutex_static Static functions and data
 * @ingroup kernel_unit_mutex
 * @brief The static functions of mutex.c, and the data that mutex.c defines.
 *
 * @par Priority restore
 * The unit lowers a raised priority on the last unlock and after a timeout.
 * The new priority of the owner is the highest priority of the first
 * waiting threads of the mutexes that the owner still holds, each limited
 * by @kconfig{CONFIG_PRIORITY_CEILING}, and at least the original priority
 * of the owner. On the last unlock, the released mutex is no longer in the
 * held list, so its waiters do not count. The unit calls
 * z_thread_prio_set() only if the priority changes. After a timeout, the
 * unit reschedules if a priority change of the lock asked for it. The
 * unlock ignores this hint.
 *
 * These tests exist only with priority inheritance. The static function
 * held_mutexes_highest_waiter_prio() does the calculation. The tests call
 * k_mutex_unlock() or k_mutex_lock(), so they are in the groups of these
 * functions.
 *
 * @par Functions in kernel/mutex.c
 * All static functions are in the code only if @c Z_MUTEX_PI_ENABLED is 1.
 * They have no test of their own. The tests of k_mutex_lock() and
 * k_mutex_unlock() call them.
 * - new_prio_for_inheritance(): the boost priority, limited by the ceiling.
 * - adjust_owner_prio(): the priority change of an owner.
 * - held_mutexes_highest_waiter_prio(): the priority restore (see above).
 *
 * @par Data in kernel/mutex.c
 * - @c mutex_lock: the spinlock of all mutexes.
 * - @c obj_type_mutex and its descriptor (K_OBJ_TYPE_DEFINE()), with
 *   @kconfig{CONFIG_OBJ_CORE_MUTEX}. The test of the descriptor is in this
 *   group.
 */

#include <string.h>
#include <zephyr/ztest.h>
#include <kernel_unit.h>
#include <kernel_unit_models.h>
#ifdef CONFIG_OBJ_CORE
#include <fakes/obj_core.h>
#endif
#ifdef CONFIG_USERSPACE
#include <fakes/kobject.h>
#endif
#ifdef CONFIG_ASSERT
#include <fakes/assert.h>
#endif

#include <kernel/mutex.c>

/* Timeout that is not K_NO_WAIT and not K_FOREVER */
#define TEST_TIMEOUT K_TICKS(10)

/* Wait result that is not 0 and not -EAGAIN, to show that it passes unchanged. */
#define OTHER_RESULT (-EINTR)

/* Priorities of the test threads. A lower value is a higher priority. */
#define PRIO_LOW  10
#define PRIO_MID  5
#define PRIO_HIGH 1
#define PRIO_COOP (-5)

/* A priority with the ceiling of CONFIG_PRIORITY_CEILING, as the unit computes it. */
#define CEILED(prio) (((prio) >= CONFIG_PRIORITY_CEILING) ? (prio) : CONFIG_PRIORITY_CEILING)

/* Value of a spy record before the spy fake runs */
#define UNSET (-1000)

/*
 * With more than one CPU, LOCK_SCHED_SPINLOCK locks the scheduler spinlock
 * inside mutex_lock.
 */
#if CONFIG_MP_MAX_NUM_CPUS > 1
#define SCHED_LOCK         1
#define SCHED_LOCK_ENABLED true
#else
#define SCHED_LOCK_ENABLED false
#endif

/* An entry of an expected call history that exists only with the scheduler spinlock */
#define SCHED_LOCK_CALL(fn) KERNEL_UNIT_IF_ENABLED(SCHED_LOCK, fn)

/* The ISR check of the __ASSERT() at the start of k_mutex_lock() and k_mutex_unlock() */
#define ISR_CHECK_CALL KERNEL_UNIT_IF_ENABLED(CONFIG_ASSERT, arch_is_in_isr)

#if Z_MUTEX_PI_ENABLED
/* Number of threads and mutexes of a long ownership chain */
#define CHAIN_LEN (MUTEX_CHAIN_WALK_MAX_HOPS + 2)
#endif

/* The threads of the tests. The name gives the priority. */
static struct k_thread t_low;
static struct k_thread t_mid;
static struct k_thread t_high;
static struct k_thread t_coop;

/* The mutexes of the tests */
static struct k_mutex m1;
static struct k_mutex m2;
static struct k_mutex m3;

#if Z_MUTEX_PI_ENABLED
/* A long ownership chain: chain_threads[i] holds chain_mutexes[i]. */
static struct k_thread chain_threads[CHAIN_LEN];
static struct k_mutex chain_mutexes[CHAIN_LEN];
#endif

/*
 * Wait queue model: for each wait queue, the waiting threads, sorted by
 * priority. Threads with the same priority are in the order of their wait.
 */
#define N_WAITQS    24
#define MAX_WAITERS 4

struct waitq_model {
	_wait_q_t *wait_q;
	struct k_thread *threads[MAX_WAITERS];
	size_t n;
};

static struct waitq_model waitqs[N_WAITQS];

/* The thread that waits in z_pend_curr() now, or NULL. */
static struct k_thread *pending_thread;

/* What the models saw at the time of a call. */
static int depth_at_pend;
static int depth_at_unpend;
static int depth_at_ready;
static unsigned int prio_sets_without_lock;

/* The mutex and the thread of an action of another thread */
static struct k_mutex *other_mutex;
static struct k_thread *other_thread;
static int other_result;

static struct waitq_model *waitq_of(_wait_q_t *wait_q)
{
	for (size_t i = 0; i < N_WAITQS; i++) {
		if (waitqs[i].wait_q == wait_q) {
			return &waitqs[i];
		}
	}
	for (size_t i = 0; i < N_WAITQS; i++) {
		if (waitqs[i].wait_q == NULL) {
			waitqs[i].wait_q = wait_q;
			return &waitqs[i];
		}
	}
	ztest_test_fail();

	return NULL;
}

/* Add a thread to a wait queue, behind the threads with the same or a higher priority. */
static void waitq_add(_wait_q_t *wait_q, struct k_thread *thread)
{
	struct waitq_model *q = waitq_of(wait_q);
	size_t pos = q->n;

	zassert_true(q->n < MAX_WAITERS, "too many waiting threads");
	while ((pos > 0U) && z_is_prio_higher(thread->base.prio, q->threads[pos - 1U]->base.prio)) {
		q->threads[pos] = q->threads[pos - 1U];
		pos--;
	}
	q->threads[pos] = thread;
	q->n++;
	thread->base.thread_state |= _THREAD_PENDING;
}

/* Remove a thread from a wait queue, if it is there. */
static void waitq_remove(_wait_q_t *wait_q, struct k_thread *thread)
{
	struct waitq_model *q = waitq_of(wait_q);

	for (size_t i = 0; i < q->n; i++) {
		if (q->threads[i] == thread) {
			memmove(&q->threads[i], &q->threads[i + 1U],
				(q->n - i - 1U) * sizeof(q->threads[0]));
			q->n--;
			thread->base.thread_state &= ~_THREAD_PENDING;
			return;
		}
	}
}

static size_t waitq_len(struct k_mutex *mutex)
{
	return waitq_of(&mutex->wait_q)->n;
}

/* Fake z_waitq_head_locked(): the first waiting thread, or NULL. */
static struct k_thread *waitq_head_model(_wait_q_t *wait_q)
{
	struct waitq_model *q = waitq_of(wait_q);

	return (q->n > 0U) ? q->threads[0] : NULL;
}

/* Fake z_unpend_first_thread_locked(): remove the first waiting thread and return it. */
static struct k_thread *unpend_model(_wait_q_t *wait_q)
{
	struct k_thread *thread = waitq_head_model(wait_q);

	depth_at_unpend = kernel_unit_lock.depth;
	if (thread != NULL) {
		waitq_remove(wait_q, thread);
	}

	return thread;
}

/*
 * Fake z_pend_curr(): the current thread waits on the wait queue, the lock
 * is released, and another thread runs (kernel_unit_set_other_thread()). If
 * no thread woke the current thread, the wait is a timeout, and the thread
 * leaves the wait queue.
 */
static int pend_model(struct k_spinlock *lock, k_spinlock_key_t key, _wait_q_t *wait_q,
		      k_timeout_t timeout)
{
	struct k_thread *thread = _current;
	int ret;

	depth_at_pend = kernel_unit_lock.depth;
	waitq_add(wait_q, thread);
	pending_thread = thread;
	ret = kernel_unit_pend_other_thread(lock, key, wait_q, timeout);
	pending_thread = NULL;
	if (z_is_thread_pending(thread)) {
		waitq_remove(wait_q, thread);
	}

	return ret;
}

/* Fake arch_thread_return_value_set(): the value ends the wait of the waiting thread. */
static void return_value_model(struct k_thread *thread, unsigned int value)
{
	if (thread == pending_thread) {
		kernel_unit_wake_current((int)value);
	}
}

/* Fake z_thread_prio_set(): set the priority; return_val says "reschedule". */
static bool prio_set_model(struct k_thread *thread, int prio)
{
	if (kernel_unit_lock.depth == 0) {
		prio_sets_without_lock++;
	}
	thread->base.prio = prio;

	return z_thread_prio_set_fake.return_val;
}

/* Spy z_sched_ready_locked(): record the depth of the lock model at the call. */
static void ready_spy(struct k_thread *thread)
{
	ARG_UNUSED(thread);

	depth_at_ready = kernel_unit_lock.depth;
}

/* z_thread_prio_set() model with a reschedule hint for each call: prio_set_returns[n] */
static bool prio_set_returns[3];

/* Fake z_thread_prio_set(): set the priority; return prio_set_returns[n] for call n. */
static __maybe_unused bool prio_set_sequence(struct k_thread *thread, int prio)
{
	unsigned int n = z_thread_prio_set_fake.call_count - 1U;

	thread->base.prio = prio;

	return (n < ARRAY_SIZE(prio_set_returns)) ? prio_set_returns[n] : false;
}

/* Let an action of another thread run while the current thread waits. */
static void set_other_thread(kernel_unit_observer_t action)
{
	kernel_unit_set_other_thread(action, true);
	z_pend_curr_fake.custom_fake = pend_model;
}

/* Make thread the current thread. */
static void set_current(struct k_thread *thread)
{
	_kernel.cpus[0].current = thread;
}

/* Put a thread into a known state with a priority, as the thread creation does. */
static void thread_prepare(struct k_thread *thread, int prio)
{
	memset(thread, 0, sizeof(*thread));
	thread->base.prio = prio;
#if Z_MUTEX_PI_ENABLED
	sys_slist_init(&thread->held_mutexes);
	thread->mutex_pended_on = NULL;
	thread->orig_prio = prio;
#endif
}

/* Give the thread an active timeout: it waits with a finite timeout. */
static __maybe_unused void set_timeout_active(struct k_thread *thread)
{
#if defined(CONFIG_TIMEOUT_BACKEND_MINHEAP)
	thread->base.timeout.heap_handle.idx = 1U;
#else
	thread->base.timeout.node.next = &thread->base.timeout.node;
	thread->base.timeout.node.prev = &thread->base.timeout.node;
#endif
}

/* Put a mutex into a known, free state without k_mutex_init(). */
static void mutex_prepare(struct k_mutex *mutex)
{
	memset(mutex, 0, sizeof(*mutex));
}

/* Let thread hold mutex with this lock count, without the functions of the unit. */
static void give_mutex(struct k_mutex *mutex, struct k_thread *thread, uint32_t count)
{
	mutex->owner = thread;
	mutex->lock_count = count;
#if Z_MUTEX_PI_ENABLED
	if (sys_slist_is_empty(&thread->held_mutexes)) {
		thread->orig_prio = thread->base.prio;
	}
	sys_slist_append(&thread->held_mutexes, &mutex->held_node);
#endif
}

/* Let thread wait for mutex, without the functions of the unit. */
static void let_wait(struct k_thread *thread, struct k_mutex *mutex)
{
	waitq_add(&mutex->wait_q, thread);
#if Z_MUTEX_PI_ENABLED
	thread->mutex_pended_on = mutex;
#endif
}

#if Z_MUTEX_PI_ENABLED
/* Return true if mutex is in the list of the mutexes that thread holds. */
static bool holds(struct k_thread *thread, struct k_mutex *mutex)
{
	sys_snode_t *node;

	SYS_SLIST_FOR_EACH_NODE(&thread->held_mutexes, node) {
		if (node == &mutex->held_node) {
			return true;
		}
	}

	return false;
}
#endif

/* Actions of another thread */
static void unlock_other_mutex(void)
{
	other_result = z_impl_k_mutex_unlock(other_mutex);
}

/* The owner of other_mutex unlocks it while the current thread waits. */
static void owner_unlocks(void)
{
	kernel_unit_run_as(other_thread, unlock_other_mutex);
}

/*
 * The wait of the current thread times out, and the timeout removes it from
 * the wait queue. Then the owner unlocks the mutex: no thread waits for it.
 */
static __maybe_unused void timeout_then_owner_unlocks(void)
{
	waitq_remove(&other_mutex->wait_q, _current);
	kernel_unit_run_as(other_thread, unlock_other_mutex);
}

/* Another thread wakes the current thread with 0, without the unlock code. */
static __maybe_unused void wake_with_zero(void)
{
	kernel_unit_wake_current(0);
	waitq_remove(&other_mutex->wait_q, _current);
}

/* Another thread wakes the current thread with OTHER_RESULT. */
static void wake_with_other_result(void)
{
	kernel_unit_wake_current(OTHER_RESULT);
	waitq_remove(&other_mutex->wait_q, _current);
}

/*
 * Assert the lock invariant of one operation on mutex_lock, with the lock
 * model:
 * - The operation locks mutex_lock @p locks times. Only the ISR check of an
 *   __ASSERT() comes before the first lock.
 * - It releases each lock once, with the key of the lock. The last release
 *   is @p last, and it is the last call.
 * - With more than one CPU, only the scheduler spinlock nests inside
 *   mutex_lock, and the operation releases each nested lock. With one CPU,
 *   no lock nests.
 * - At the end, the operation holds no lock.
 */
static void assert_lock_invariant(unsigned int locks, enum kernel_unit_release last)
{
	fff_function_t calls[FFF_CALL_HISTORY_LEN];
	size_t n = kernel_unit_history(calls, ARRAY_SIZE(calls));
	int first_lock = kernel_unit_history_index(KERNEL_UNIT_FN(unit_arch_irq_lock), 0);
	unsigned int releases = kernel_unit_lock.outer_releases + z_pend_curr_fake.call_count;
	fff_function_t release;

	zassert_equal(kernel_unit_lock.outer_locks, locks, "mutex_lock locked %u times",
		      kernel_unit_lock.outer_locks);
	zassert_equal(releases, locks, "mutex_lock released %u times", releases);
	zassert_equal(kernel_unit_lock.depth, 0, "a lock is still held");
	zassert_equal(kernel_unit_lock.nested_unlocks, kernel_unit_lock.nested_locks);
	zassert_true(kernel_unit_lock.max_depth <= (SCHED_LOCK_ENABLED ? 2 : 1), "lock depth %d",
		     kernel_unit_lock.max_depth);
	zassert_true(first_lock >= 0, "no lock");
	for (int i = 0; i < first_lock; i++) {
		zassert_equal_ptr(calls[i], KERNEL_UNIT_FN(arch_is_in_isr),
				  "call %d comes before the lock", i);
	}

	switch (last) {
	case KERNEL_UNIT_RELEASED_BY_UNLOCK:
		zassert_equal(unit_arch_irq_unlock_fake.arg0_val, KERNEL_UNIT_IRQ_KEY);
		release = KERNEL_UNIT_FN(unit_arch_irq_unlock);
		break;
	case KERNEL_UNIT_RELEASED_BY_RESCHEDULE:
		zassert_equal(z_reschedule_fake.call_count, 1);
		zassert_equal_ptr(z_reschedule_fake.arg0_val, &mutex_lock);
		zassert_equal((unsigned int)z_reschedule_fake.arg1_val.key, KERNEL_UNIT_IRQ_KEY);
		release = KERNEL_UNIT_FN(z_reschedule);
		break;
	case KERNEL_UNIT_RELEASED_BY_PEND:
	default:
		release = KERNEL_UNIT_FN(z_pend_curr);
		break;
	}
	if (z_pend_curr_fake.call_count > 0U) {
		zassert_equal(z_pend_curr_fake.call_count, 1);
		zassert_equal_ptr(z_pend_curr_fake.arg0_val, &mutex_lock);
		zassert_equal((unsigned int)z_pend_curr_fake.arg1_val.key, KERNEL_UNIT_IRQ_KEY);
	}
	zassert_true(n > 0U);
	zassert_equal_ptr(calls[n - 1U], release, "the last call is not the expected release");
}

static void mutex_unit_before(void *fixture)
{
	ARG_UNUSED(fixture);

	/* The fake rules reset all fakes and _kernel before this function. */
	kernel_unit_lock_model_install();
	z_waitq_head_locked_fake.custom_fake = waitq_head_model;
	z_unpend_first_thread_locked_fake.custom_fake = unpend_model;
	arch_thread_return_value_set_fake.custom_fake = return_value_model;
	z_thread_prio_set_fake.custom_fake = prio_set_model;
	z_sched_ready_locked_fake.custom_fake = ready_spy;
	set_other_thread(NULL);

	memset(waitqs, 0, sizeof(waitqs));
	pending_thread = NULL;
	depth_at_pend = UNSET;
	depth_at_unpend = UNSET;
	depth_at_ready = UNSET;
	prio_sets_without_lock = 0U;
	other_mutex = NULL;
	other_thread = NULL;
	other_result = UNSET;

	thread_prepare(&t_low, PRIO_LOW);
	thread_prepare(&t_mid, PRIO_MID);
	thread_prepare(&t_high, PRIO_HIGH);
	thread_prepare(&t_coop, PRIO_COOP);
	mutex_prepare(&m1);
	mutex_prepare(&m2);
	mutex_prepare(&m3);
	set_current(&t_high);
}

ZTEST_SUITE(mutex_unit, NULL, NULL, mutex_unit_before, NULL, NULL);

/*
 * Tests: Initialization. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_mutex, at the top of this file.
 */

/**
 * @brief k_mutex_init() makes the mutex free: no owner and the lock count 0.
 *
 * @details
 * - Setup: a mutex filled with a pattern.
 * - Action: z_impl_k_mutex_init().
 * - Expected: return value 0. The owner is NULL, and the lock count is 0.
 *
 * @ingroup kernel_unit_mutex_k_mutex_init
 * @see z_impl_k_mutex_init()
 */
ZTEST(mutex_unit, test_init_makes_mutex_free)
{
	memset(&m1, KERNEL_UNIT_FILL, sizeof(m1));

	zassert_equal(z_impl_k_mutex_init(&m1), 0);

	zassert_is_null(m1.owner);
	zassert_equal(m1.lock_count, 0U);
}

/**
 * @brief k_mutex_init() initializes the wait queue of the mutex.
 *
 * @details
 * - Setup: a mutex filled with a pattern.
 * - Action: z_impl_k_mutex_init().
 * - Expected: one call of z_waitq_init() with the wait queue of the mutex.
 *
 * @ingroup kernel_unit_mutex_k_mutex_init
 * @see z_impl_k_mutex_init()
 */
ZTEST(mutex_unit, test_init_initializes_wait_queue)
{
	memset(&m1, KERNEL_UNIT_FILL, sizeof(m1));

	(void)z_impl_k_mutex_init(&m1);

	zassert_equal(z_waitq_init_fake.call_count, 1);
	zassert_equal_ptr(z_waitq_init_fake.arg0_val, &m1.wait_q);
}

#if Z_MUTEX_PI_ENABLED
/**
 * @brief With priority inheritance, k_mutex_init() clears the node of the mutex in the list of
 * held mutexes.
 *
 * @details
 * - Setup: a mutex filled with a pattern.
 * - Action: z_impl_k_mutex_init().
 * - Expected: @c held_node.next is NULL.
 *
 * @ingroup kernel_unit_mutex_k_mutex_init
 * @see z_impl_k_mutex_init()
 */
ZTEST(mutex_unit, test_init_clears_held_node)
{
	memset(&m1, KERNEL_UNIT_FILL, sizeof(m1));

	(void)z_impl_k_mutex_init(&m1);

	zassert_is_null(m1.held_node.next);
}
#endif

/**
 * @brief k_mutex_init() initializes the wait queue, then the kernel object, then the object core,
 * and calls nothing else. It does not lock.
 *
 * @details
 * - Setup: a mutex filled with a pattern.
 * - Action: z_impl_k_mutex_init().
 * - Expected: the call history is z_waitq_init(), k_object_init() (with
 *   CONFIG_USERSPACE), k_obj_core_init_and_link() (with
 *   CONFIG_OBJ_CORE_MUTEX). No lock.
 *
 * @ingroup kernel_unit_mutex_k_mutex_init
 * @see z_impl_k_mutex_init()
 */
ZTEST(mutex_unit, test_init_call_sequence)
{
	memset(&m1, KERNEL_UNIT_FILL, sizeof(m1));

	(void)z_impl_k_mutex_init(&m1);

	zassert_call_history(
		z_waitq_init, KERNEL_UNIT_IF_ENABLED(CONFIG_USERSPACE, k_object_init),
		KERNEL_UNIT_IF_ENABLED(CONFIG_OBJ_CORE_MUTEX, k_obj_core_init_and_link));
	zassert_equal(unit_arch_irq_lock_fake.call_count, 0);
}

#ifdef CONFIG_USERSPACE
/**
 * @brief With CONFIG_USERSPACE, k_mutex_init() marks the mutex as an initialized kernel object.
 *
 * @details
 * - Setup: a mutex.
 * - Action: z_impl_k_mutex_init().
 * - Expected: one call of k_object_init() with the mutex.
 *
 * @ingroup kernel_unit_mutex_k_mutex_init
 * @see z_impl_k_mutex_init()
 */
ZTEST(mutex_unit, test_init_marks_kernel_object)
{
	(void)z_impl_k_mutex_init(&m1);

	zassert_equal(k_object_init_fake.call_count, 1);
	zassert_equal_ptr(k_object_init_fake.arg0_val, &m1);
}
#endif

/*
 * Tests: Lock without a wait. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_mutex, at the top of this file.
 */

/**
 * @brief k_mutex_lock() of a free mutex makes the current thread the owner with the lock count 1
 * and returns 0.
 *
 * @details
 * - Setup: a free mutex. The current thread has the high priority.
 * - Action: z_impl_k_mutex_lock() with K_FOREVER.
 * - Expected: return value 0. The owner is the current thread, the lock
 *   count is 1. No wait, no priority change.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock()
 */
ZTEST(mutex_unit, test_lock_free_mutex_takes_ownership)
{
	zassert_equal(z_impl_k_mutex_lock(&m1, K_FOREVER), 0);

	zassert_equal_ptr(m1.owner, &t_high);
	zassert_equal(m1.lock_count, 1U);
	zassert_equal(z_pend_curr_fake.call_count, 0);
	zassert_equal(z_thread_prio_set_fake.call_count, 0);
}

/**
 * @brief k_mutex_lock() of a free mutex does not wait, also with K_NO_WAIT.
 *
 * @details
 * - Setup: a free mutex.
 * - Action: z_impl_k_mutex_lock() with K_NO_WAIT.
 * - Expected: return value 0. The current thread is the owner.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock()
 */
ZTEST(mutex_unit, test_lock_free_mutex_with_no_wait)
{
	zassert_equal(z_impl_k_mutex_lock(&m1, K_NO_WAIT), 0);

	zassert_equal_ptr(m1.owner, &t_high);
	zassert_equal(m1.lock_count, 1U);
}

/**
 * @brief A mutex with the lock count 0 is free, also if its owner field names another thread.
 *
 * @details
 * - Setup: a mutex with the lock count 0 and the owner field set to another
 *   thread (a value that the unit does not make, but a free mutex can have
 *   any owner value for this check).
 * - Action: z_impl_k_mutex_lock() with K_NO_WAIT.
 * - Expected: return value 0. The current thread is the owner, with the
 *   lock count 1.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock()
 */
ZTEST(mutex_unit, test_lock_count_zero_means_free)
{
	m1.owner = &t_low;
	m1.lock_count = 0U;

	zassert_equal(z_impl_k_mutex_lock(&m1, K_NO_WAIT), 0);

	zassert_equal_ptr(m1.owner, &t_high);
	zassert_equal(m1.lock_count, 1U);
}

/**
 * @brief The owner can lock its mutex again: k_mutex_lock() increments the lock count and does
 * not wait.
 *
 * @details
 * - Setup: the current thread holds the mutex with the lock count 1.
 * - Action: z_impl_k_mutex_lock() two times, with K_NO_WAIT and K_FOREVER.
 * - Expected: return value 0 each time. The lock count is 3. The owner did
 *   not change. No wait.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock()
 */
ZTEST(mutex_unit, test_lock_recursive_increments_count)
{
	give_mutex(&m1, &t_high, 1U);

	zassert_equal(z_impl_k_mutex_lock(&m1, K_NO_WAIT), 0);
	zassert_equal(z_impl_k_mutex_lock(&m1, K_FOREVER), 0);

	zassert_equal(m1.lock_count, 3U);
	zassert_equal_ptr(m1.owner, &t_high);
	zassert_equal(z_pend_curr_fake.call_count, 0);
}

/**
 * @brief k_mutex_lock() without a wait locks mutex_lock once and releases it with k_spin_unlock()
 * as its last call.
 *
 * @details
 * - Setup: a free mutex.
 * - Action: z_impl_k_mutex_lock() with K_FOREVER.
 * - Expected: the call history is the ISR check (with CONFIG_ASSERT), the
 *   lock and the unlock. The lock invariant holds.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock()
 */
ZTEST(mutex_unit, test_lock_free_mutex_lock_sequence)
{
	(void)z_impl_k_mutex_lock(&m1, K_FOREVER);

	zassert_call_history(ISR_CHECK_CALL, unit_arch_irq_lock, unit_arch_irq_unlock);
	assert_lock_invariant(1U, KERNEL_UNIT_RELEASED_BY_UNLOCK);
}

/**
 * @brief A recursive k_mutex_lock() also locks mutex_lock once and releases it with
 * k_spin_unlock().
 *
 * @details
 * - Setup: the current thread holds the mutex.
 * - Action: z_impl_k_mutex_lock() with K_FOREVER.
 * - Expected: the lock invariant holds, with the release by k_spin_unlock().
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock()
 */
ZTEST(mutex_unit, test_lock_recursive_lock_sequence)
{
	give_mutex(&m1, &t_high, 1U);

	(void)z_impl_k_mutex_lock(&m1, K_FOREVER);

	assert_lock_invariant(1U, KERNEL_UNIT_RELEASED_BY_UNLOCK);
}

/**
 * @brief If another thread holds the mutex, k_mutex_lock() with K_NO_WAIT returns -EBUSY and
 * changes nothing.
 *
 * @details
 * - Setup: the low priority thread holds the mutex. The current thread has
 *   the high priority.
 * - Action: z_impl_k_mutex_lock() with K_NO_WAIT.
 * - Expected: return value -EBUSY. Owner and lock count did not change. No
 *   wait and no priority change: K_NO_WAIT does not raise the owner. The
 *   lock invariant holds, with the release by k_spin_unlock().
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock()
 */
ZTEST(mutex_unit, test_lock_busy_no_wait_returns_ebusy)
{
	give_mutex(&m1, &t_low, 2U);

	zassert_equal(z_impl_k_mutex_lock(&m1, K_NO_WAIT), -EBUSY);

	zassert_equal_ptr(m1.owner, &t_low);
	zassert_equal(m1.lock_count, 2U);
	zassert_equal(t_low.base.prio, PRIO_LOW);
	zassert_equal(z_pend_curr_fake.call_count, 0);
	zassert_equal(z_thread_prio_set_fake.call_count, 0);
	assert_lock_invariant(1U, KERNEL_UNIT_RELEASED_BY_UNLOCK);
}

#if Z_MUTEX_PI_ENABLED
/**
 * @brief On the first lock of any mutex, k_mutex_lock() records the priority of the thread as its
 * original priority.
 *
 * @details
 * - Setup: the current thread holds no mutex. Its original priority field
 *   has another value.
 * - Action: z_impl_k_mutex_lock() of a free mutex.
 * - Expected: @c orig_prio is the priority of the thread.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock()
 */
ZTEST(mutex_unit, test_lock_first_mutex_records_orig_prio)
{
	t_high.orig_prio = PRIO_LOW;

	(void)z_impl_k_mutex_lock(&m1, K_FOREVER);

	zassert_equal(t_high.orig_prio, PRIO_HIGH);
}

/**
 * @brief If the thread holds other mutexes, k_mutex_lock() keeps its original priority.
 *
 * @details
 * The thread can have a raised priority now. The original priority is the
 * priority before the first raise.
 * - Setup: the current thread holds m1, with the original priority low and
 *   the raised priority high.
 * - Action: z_impl_k_mutex_lock() of the free mutex m2.
 * - Expected: @c orig_prio stays low. The thread holds m1 and m2.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock()
 */
ZTEST(mutex_unit, test_lock_second_mutex_keeps_orig_prio)
{
	give_mutex(&m1, &t_high, 1U);
	t_high.orig_prio = PRIO_LOW;

	(void)z_impl_k_mutex_lock(&m2, K_FOREVER);

	zassert_equal(t_high.orig_prio, PRIO_LOW);
	zassert_true(holds(&t_high, &m1));
	zassert_true(holds(&t_high, &m2));
}

/**
 * @brief On the first lock of a mutex, k_mutex_lock() adds the mutex to the list of held mutexes
 * of the owner, and a recursive lock does not add it again.
 *
 * @details
 * - Setup: a free mutex.
 * - Action: z_impl_k_mutex_lock() two times.
 * - Expected: after the first lock, the list has the mutex. After the
 *   second lock, the list has exactly one node.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock()
 */
ZTEST(mutex_unit, test_lock_adds_mutex_to_held_list_once)
{
	(void)z_impl_k_mutex_lock(&m1, K_FOREVER);
	zassert_true(holds(&t_high, &m1));

	(void)z_impl_k_mutex_lock(&m1, K_FOREVER);

	zassert_equal(sys_slist_len(&t_high.held_mutexes), 1U);
}
#endif /* Z_MUTEX_PI_ENABLED */

/*
 * Tests: Lock with a wait. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_mutex, at the top of this file.
 */

/**
 * @brief If another thread holds the mutex, k_mutex_lock() waits on the wait queue of the mutex
 * with the timeout of the caller and releases mutex_lock with the wait.
 *
 * @details
 * - Setup: the low priority thread holds the mutex.
 * - Action: z_impl_k_mutex_lock() with TEST_TIMEOUT. No thread wakes the
 *   current thread.
 * - Expected: one call of z_pend_curr() with mutex_lock, the key of the
 *   lock, the wait queue of the mutex and TEST_TIMEOUT. At the call, the
 *   lock model has one hold.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock()
 */
ZTEST(mutex_unit, test_wait_pends_on_mutex_wait_queue)
{
	give_mutex(&m1, &t_low, 1U);

	(void)z_impl_k_mutex_lock(&m1, TEST_TIMEOUT);

	zassert_equal(z_pend_curr_fake.call_count, 1);
	zassert_equal_ptr(z_pend_curr_fake.arg0_val, &mutex_lock);
	zassert_equal((unsigned int)z_pend_curr_fake.arg1_val.key, KERNEL_UNIT_IRQ_KEY);
	zassert_equal_ptr(z_pend_curr_fake.arg2_val, &m1.wait_q);
	zassert_true(K_TIMEOUT_EQ(z_pend_curr_fake.arg3_val, TEST_TIMEOUT));
	zassert_equal(depth_at_pend, 1);
}

/**
 * @brief If the owner unlocks the mutex while the current thread waits, k_mutex_lock() returns 0,
 * and the current thread holds the mutex with the lock count 1.
 *
 * @details
 * The test connects the two sides of the hand-over through the models.
 * - Setup: the low priority thread holds the mutex. While the current
 *   thread waits, the low priority thread unlocks the mutex.
 * - Action: z_impl_k_mutex_lock() with K_FOREVER.
 * - Expected: return value 0. The owner is the current thread, the lock
 *   count is 1. The unlock of the other thread returned 0. The wait queue
 *   is empty.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock(), z_impl_k_mutex_unlock()
 */
ZTEST(mutex_unit, test_wait_handover_gives_ownership)
{
	give_mutex(&m1, &t_low, 1U);
	other_mutex = &m1;
	other_thread = &t_low;
	set_other_thread(owner_unlocks);

	zassert_equal(z_impl_k_mutex_lock(&m1, K_FOREVER), 0);

	zassert_equal(other_result, 0);
	zassert_equal_ptr(m1.owner, &t_high);
	zassert_equal(m1.lock_count, 1U);
	zassert_equal(waitq_len(&m1), 0U);
}

/**
 * @brief After the hand-over, k_mutex_lock() does not lock mutex_lock again.
 *
 * @details
 * - Setup: as in the hand-over test.
 * - Action: z_impl_k_mutex_lock() with K_FOREVER.
 * - Expected: z_pend_curr() is the last call of k_mutex_lock() itself: the
 *   other calls after it come from the unlock of the other thread (lock,
 *   unpend, ready, reschedule). The current thread locked mutex_lock once.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock()
 */
ZTEST(mutex_unit, test_wait_handover_no_relock)
{
	give_mutex(&m1, &t_low, 1U);
	other_mutex = &m1;
	other_thread = &t_low;
	set_other_thread(owner_unlocks);

	(void)z_impl_k_mutex_lock(&m1, K_FOREVER);

	/* One lock of the current thread, one lock of the unlock of the other thread. */
	zassert_equal(kernel_unit_lock.outer_locks, 2U);
	zassert_equal(z_reschedule_fake.call_count, 1);
	zassert_equal(kernel_unit_history_index(KERNEL_UNIT_FN(z_reschedule), 0),
		      (int)kernel_unit_history_len() - 1,
		      "the last call is not the reschedule of the unlock of the other thread");
	zassert_equal(kernel_unit_lock.depth, 0);
}

/**
 * @brief After a timeout, k_mutex_lock() returns -EAGAIN, and the owner keeps the mutex.
 *
 * @details
 * - Setup: the low priority thread holds the mutex. No thread wakes the
 *   current thread.
 * - Action: z_impl_k_mutex_lock() with TEST_TIMEOUT.
 * - Expected: return value -EAGAIN. Owner and lock count did not change.
 *   The current thread is not in the wait queue.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock()
 */
ZTEST(mutex_unit, test_wait_timeout_returns_eagain)
{
	give_mutex(&m1, &t_low, 1U);

	zassert_equal(z_impl_k_mutex_lock(&m1, TEST_TIMEOUT), -EAGAIN);

	zassert_equal_ptr(m1.owner, &t_low);
	zassert_equal(m1.lock_count, 1U);
	zassert_equal(waitq_len(&m1), 0U);
}

#if Z_MUTEX_PI_ENABLED
static struct k_mutex *pended_on_at_pend;

static void record_pended_on(void)
{
	pended_on_at_pend = pending_thread->mutex_pended_on;
}

/**
 * @brief With priority inheritance, the waiting thread records the mutex in mutex_pended_on before
 * the wait.
 *
 * @details
 * - Setup: the low priority thread holds the mutex. A spy reads
 *   @c mutex_pended_on of the current thread at z_pend_curr().
 * - Action: z_impl_k_mutex_lock() with TEST_TIMEOUT.
 * - Expected: at z_pend_curr(), @c mutex_pended_on is the mutex.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock()
 */
ZTEST(mutex_unit, test_wait_records_mutex_pended_on)
{
	give_mutex(&m1, &t_low, 1U);
	pended_on_at_pend = NULL;
	set_other_thread(record_pended_on);

	(void)z_impl_k_mutex_lock(&m1, TEST_TIMEOUT);

	zassert_equal_ptr(pended_on_at_pend, &m1);
}

/**
 * @brief With priority inheritance, k_mutex_lock() clears mutex_pended_on after the hand-over.
 *
 * @details
 * - Setup: as in the hand-over test.
 * - Action: z_impl_k_mutex_lock() with K_FOREVER.
 * - Expected: @c mutex_pended_on of the current thread is NULL. The current
 *   thread holds the mutex in its list of held mutexes.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock()
 */
ZTEST(mutex_unit, test_wait_handover_clears_pended_on)
{
	give_mutex(&m1, &t_low, 1U);
	other_mutex = &m1;
	other_thread = &t_low;
	set_other_thread(owner_unlocks);

	(void)z_impl_k_mutex_lock(&m1, K_FOREVER);

	zassert_is_null(t_high.mutex_pended_on);
	zassert_true(holds(&t_high, &m1));
	zassert_false(holds(&t_low, &m1));
}

/**
 * @brief With priority inheritance, k_mutex_lock() itself clears mutex_pended_on after a
 * successful wait, also if the waker did not clear it.
 *
 * @details
 * The unlock of the owner also clears the field of the new owner. The
 * lock does not depend on it.
 * - Setup: the low priority thread holds the mutex. Another thread wakes
 *   the current thread with 0, without the code of the unlock.
 * - Action: z_impl_k_mutex_lock() with K_FOREVER.
 * - Expected: return value 0. @c mutex_pended_on of the current thread is
 *   NULL.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock()
 */
ZTEST(mutex_unit, test_wait_success_clears_pended_on)
{
	give_mutex(&m1, &t_low, 1U);
	other_mutex = &m1;
	set_other_thread(wake_with_zero);

	zassert_equal(z_impl_k_mutex_lock(&m1, K_FOREVER), 0);

	zassert_is_null(t_high.mutex_pended_on);
}

/**
 * @brief With priority inheritance, k_mutex_lock() clears mutex_pended_on after a timeout, while
 * it holds mutex_lock.
 *
 * @details
 * - Setup: the low priority thread holds the mutex. No thread wakes the
 *   current thread.
 * - Action: z_impl_k_mutex_lock() with TEST_TIMEOUT.
 * - Expected: @c mutex_pended_on of the current thread is NULL. After the
 *   wait, the current thread locked mutex_lock a second time: the lock
 *   invariant holds with 2 locks.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock()
 */
ZTEST(mutex_unit, test_wait_timeout_clears_pended_on)
{
	give_mutex(&m1, &t_low, 1U);

	(void)z_impl_k_mutex_lock(&m1, TEST_TIMEOUT);

	zassert_is_null(t_high.mutex_pended_on);
	assert_lock_invariant(2U, KERNEL_UNIT_RELEASED_BY_UNLOCK);
}

/**
 * @brief With priority inheritance, a wake with a result other than 0 is a timeout:
 * k_mutex_lock() returns -EAGAIN.
 *
 * @details
 * The real unlock wakes the new owner only with 0. The test shows that
 * k_mutex_lock() does not pass another wait result to the caller.
 * - Setup: the low priority thread holds the mutex. Another thread wakes the
 *   current thread with -EINTR.
 * - Action: z_impl_k_mutex_lock() with K_FOREVER.
 * - Expected: return value -EAGAIN.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock()
 */
ZTEST(mutex_unit, test_wait_other_result_is_eagain)
{
	give_mutex(&m1, &t_low, 1U);
	other_mutex = &m1;
	set_other_thread(wake_with_other_result);

	zassert_equal(z_impl_k_mutex_lock(&m1, K_FOREVER), -EAGAIN);
}
#else
/**
 * @brief Without priority inheritance, k_mutex_lock() returns the result of z_pend_curr() without a
 * change.
 *
 * @details
 * - Setup: the low priority thread holds the mutex. Another thread wakes the
 *   current thread with -EINTR. In a second call, no thread wakes it.
 * - Action: z_impl_k_mutex_lock() with K_FOREVER, then with TEST_TIMEOUT.
 * - Expected: return values -EINTR and -EAGAIN. After the wait, the unit
 *   does not lock mutex_lock again: the lock invariant holds with 1 lock
 *   and the release by z_pend_curr().
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock()
 */
ZTEST(mutex_unit, test_wait_without_pi_returns_pend_result)
{
	give_mutex(&m1, &t_low, 1U);
	other_mutex = &m1;
	set_other_thread(wake_with_other_result);

	zassert_equal(z_impl_k_mutex_lock(&m1, K_FOREVER), OTHER_RESULT);
	assert_lock_invariant(1U, KERNEL_UNIT_RELEASED_BY_PEND);

	set_other_thread(NULL);
	zassert_equal(z_impl_k_mutex_lock(&m1, TEST_TIMEOUT), -EAGAIN);
}

/**
 * @brief Without priority inheritance, a waiting thread does not change the priority of the owner.
 *
 * @details
 * - Setup: the low priority thread holds the mutex. The current thread has
 *   the high priority.
 * - Action: z_impl_k_mutex_lock() with TEST_TIMEOUT.
 * - Expected: no call of z_thread_prio_set(). The owner keeps the low
 *   priority.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock()
 */
ZTEST(mutex_unit, test_wait_without_pi_no_boost)
{
	give_mutex(&m1, &t_low, 1U);

	(void)z_impl_k_mutex_lock(&m1, TEST_TIMEOUT);

	zassert_equal(z_thread_prio_set_fake.call_count, 0);
	zassert_equal(t_low.base.prio, PRIO_LOW);
}
#endif /* Z_MUTEX_PI_ENABLED */

#if Z_MUTEX_PI_ENABLED
/*
 * Tests: Priority inheritance. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_mutex, at the top of this file.
 */

static int owner_prio_at_pend;

static void record_owner_prio(void)
{
	owner_prio_at_pend = t_low.base.prio;
}

/**
 * @brief A waiting thread with a higher priority raises the owner to its priority before the wait.
 *
 * @details
 * - Setup: the low priority thread holds the mutex. The current thread has
 *   the high priority.
 * - Action: z_impl_k_mutex_lock() with TEST_TIMEOUT.
 * - Expected: one call of z_thread_prio_set() with the owner and the high
 *   priority, before z_pend_curr(). The original priority of the owner
 *   stays low.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock()
 */
ZTEST(mutex_unit, test_pi_raises_owner_to_waiter_prio)
{
	give_mutex(&m1, &t_low, 1U);
	owner_prio_at_pend = UNSET;
	set_other_thread(record_owner_prio);

	(void)z_impl_k_mutex_lock(&m1, TEST_TIMEOUT);

	zassert_true(z_thread_prio_set_fake.call_count >= 1U);
	zassert_equal_ptr(z_thread_prio_set_fake.arg0_history[0], &t_low);
	zassert_equal(z_thread_prio_set_fake.arg1_history[0], CEILED(PRIO_HIGH));
	zassert_equal(owner_prio_at_pend, CEILED(PRIO_HIGH));
	zassert_equal(t_low.orig_prio, PRIO_LOW);
	zassert_called_before(z_thread_prio_set, z_pend_curr);
}

/**
 * @brief A waiting thread with a lower or the same priority does not change the priority of the
 * owner.
 *
 * @details
 * - Setup: the high priority thread holds m1, the middle priority thread
 *   holds m2. The current thread has the middle priority.
 * - Action: z_impl_k_mutex_lock() of m1 and of m2 with TEST_TIMEOUT.
 * - Expected: no call of z_thread_prio_set(). The owners keep their
 *   priorities.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock()
 */
ZTEST(mutex_unit, test_pi_no_change_for_lower_or_equal_waiter)
{
	struct k_thread other_mid;

	thread_prepare(&other_mid, PRIO_MID);
	give_mutex(&m1, &t_high, 1U);
	give_mutex(&m2, &other_mid, 1U);
	set_current(&t_mid);

	(void)z_impl_k_mutex_lock(&m1, TEST_TIMEOUT);
	(void)z_impl_k_mutex_lock(&m2, TEST_TIMEOUT);

	zassert_equal(z_thread_prio_set_fake.call_count, 0);
	zassert_equal(t_high.base.prio, PRIO_HIGH);
	zassert_equal(other_mid.base.prio, PRIO_MID);
}

/**
 * @brief Each priority change of a lock occurs while the unit holds mutex_lock.
 *
 * @details
 * - Setup: the low priority thread holds the mutex. No thread wakes the
 *   current thread, so the timeout path also changes the priority.
 * - Action: z_impl_k_mutex_lock() with TEST_TIMEOUT.
 * - Expected: two calls of z_thread_prio_set() (raise and lower). The lock
 *   model held mutex_lock at each call.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock()
 */
ZTEST(mutex_unit, test_pi_prio_changes_under_lock)
{
	give_mutex(&m1, &t_low, 1U);

	(void)z_impl_k_mutex_lock(&m1, TEST_TIMEOUT);

	zassert_equal(z_thread_prio_set_fake.call_count, 2);
	zassert_equal(prio_sets_without_lock, 0U);
}

/**
 * @brief The boost is limited by CONFIG_PRIORITY_CEILING: a waiter with a priority above the
 * ceiling raises the owner only to the ceiling.
 *
 * @details
 * Applies if the ceiling is lower (a higher value) than the cooperative
 * priority of the test, for example in the scenario "ceiling" (0).
 * - Setup: the low priority thread holds the mutex. The current thread has
 *   the cooperative priority -5.
 * - Action: z_impl_k_mutex_lock() with TEST_TIMEOUT.
 * - Expected: z_thread_prio_set() with the owner and
 *   CONFIG_PRIORITY_CEILING.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock(), new_prio_for_inheritance()
 */
ZTEST(mutex_unit, test_pi_boost_limited_by_ceiling)
{
	if (CONFIG_PRIORITY_CEILING <= PRIO_COOP) {
		ztest_test_skip();
	}
	give_mutex(&m1, &t_low, 1U);
	set_current(&t_coop);

	(void)z_impl_k_mutex_lock(&m1, TEST_TIMEOUT);

	zassert_equal(z_thread_prio_set_fake.arg1_history[0], CONFIG_PRIORITY_CEILING);
}

/**
 * @brief A waiter with a priority below the ceiling raises the owner to its own priority.
 *
 * @details
 * - Setup: the low priority thread holds the mutex. The current thread has
 *   the cooperative priority -5.
 * - Action: z_impl_k_mutex_lock() with TEST_TIMEOUT.
 * - Expected: z_thread_prio_set() with the owner and the priority -5,
 *   limited by the ceiling.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock(), new_prio_for_inheritance()
 */
ZTEST(mutex_unit, test_pi_boost_to_coop_prio)
{
	give_mutex(&m1, &t_low, 1U);
	set_current(&t_coop);

	(void)z_impl_k_mutex_lock(&m1, TEST_TIMEOUT);

	zassert_equal_ptr(z_thread_prio_set_fake.arg0_history[0], &t_low);
	zassert_equal(z_thread_prio_set_fake.arg1_history[0], CEILED(PRIO_COOP));
}

/**
 * @brief The ceiling never lowers the priority of an owner that has a priority above the ceiling.
 *
 * @details
 * Applies if the ceiling is lower (a higher value) than the cooperative
 * priority of the test.
 * - Setup: a thread with the priority -3 holds the mutex. The current thread
 *   has the priority -5.
 * - Action: z_impl_k_mutex_lock() with TEST_TIMEOUT.
 * - Expected: no priority change before the wait. The owner keeps -3.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock(), new_prio_for_inheritance()
 */
ZTEST(mutex_unit, test_pi_ceiling_never_lowers_owner)
{
	struct k_thread owner;

	if (CONFIG_PRIORITY_CEILING <= PRIO_COOP) {
		ztest_test_skip();
	}
	thread_prepare(&owner, PRIO_COOP + 2);
	give_mutex(&m1, &owner, 1U);
	set_current(&t_coop);

	(void)z_impl_k_mutex_lock(&m1, TEST_TIMEOUT);

	zassert_equal(z_thread_prio_set_fake.call_count, 0);
	zassert_equal(owner.base.prio, PRIO_COOP + 2);
}

/*
 * Tests: Chain walk and hop limit. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_mutex, at the top of this file.
 */

/**
 * @brief k_mutex_lock() raises the owner of the next mutex in the chain: an owner that waits for a
 * second mutex passes the boost to the owner of that mutex.
 *
 * @details
 * - Setup: the middle priority thread holds m1 and waits for m2. The low
 *   priority thread holds m2. The current thread has the high priority.
 * - Action: z_impl_k_mutex_lock() of m1 with TEST_TIMEOUT.
 * - Expected: z_thread_prio_set() with the middle priority thread, then with
 *   the low priority thread, each with the high priority, before the wait.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock()
 */
ZTEST(mutex_unit, test_pi_chain_raises_next_owner)
{
	give_mutex(&m1, &t_mid, 1U);
	give_mutex(&m2, &t_low, 1U);
	let_wait(&t_mid, &m2);
	set_other_thread(record_owner_prio);
	owner_prio_at_pend = UNSET;

	(void)z_impl_k_mutex_lock(&m1, TEST_TIMEOUT);

	zassert_equal_ptr(z_thread_prio_set_fake.arg0_history[0], &t_mid);
	zassert_equal(z_thread_prio_set_fake.arg1_history[0], CEILED(PRIO_HIGH));
	zassert_equal_ptr(z_thread_prio_set_fake.arg0_history[1], &t_low);
	zassert_equal(z_thread_prio_set_fake.arg1_history[1], CEILED(PRIO_HIGH));
	zassert_equal(owner_prio_at_pend, CEILED(PRIO_HIGH));
}

/**
 * @brief The chain walk raises a later owner to the boost priority also if the first owner had a
 * higher priority than the waiter.
 *
 * @details
 * The boost priority is the higher of the waiter and the first owner. The
 * first owner waits for the second mutex, so the second owner needs at
 * least the priority of the first owner.
 * - Setup: the high priority thread holds m1 and waits for m2. The low
 *   priority thread holds m2. The current thread has the middle priority.
 * - Action: z_impl_k_mutex_lock() of m1 with TEST_TIMEOUT.
 * - Expected: no change of the first owner. z_thread_prio_set() with the
 *   low priority thread and the high priority.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock(), new_prio_for_inheritance()
 */
ZTEST(mutex_unit, test_pi_chain_uses_higher_of_waiter_and_owner)
{
	give_mutex(&m1, &t_high, 1U);
	give_mutex(&m2, &t_low, 1U);
	let_wait(&t_high, &m2);
	set_current(&t_mid);

	(void)z_impl_k_mutex_lock(&m1, TEST_TIMEOUT);

	zassert_equal_ptr(z_thread_prio_set_fake.arg0_history[0], &t_low);
	zassert_equal(z_thread_prio_set_fake.arg1_history[0], CEILED(PRIO_HIGH));
	zassert_equal(t_high.base.prio, PRIO_HIGH);
}

/**
 * @brief The chain walk stops at an owner that is not in the state "pending", also if its
 * mutex_pended_on is set.
 *
 * @details
 * A thread that timed out has a stale @c mutex_pended_on until it locks
 * @c mutex_lock again.
 * - Setup: the middle priority thread holds m1. Its @c mutex_pended_on is
 *   m2, but it is not pending. The low priority thread holds m2.
 * - Action: z_impl_k_mutex_lock() of m1 with TEST_TIMEOUT.
 * - Expected: z_thread_prio_set() only with the middle priority thread
 *   before the wait. The low priority thread keeps its priority.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock()
 */
ZTEST(mutex_unit, test_pi_chain_stops_at_stale_pended_on)
{
	give_mutex(&m1, &t_mid, 1U);
	give_mutex(&m2, &t_low, 1U);
	t_mid.mutex_pended_on = &m2;
	set_other_thread(record_owner_prio);
	owner_prio_at_pend = UNSET;

	(void)z_impl_k_mutex_lock(&m1, TEST_TIMEOUT);

	zassert_equal_ptr(z_thread_prio_set_fake.arg0_history[0], &t_mid);
	zassert_equal(owner_prio_at_pend, PRIO_LOW);
}

static unsigned int prio_sets_at_pend;

static void record_prio_sets(void)
{
	prio_sets_at_pend = z_thread_prio_set_fake.call_count;
}

/**
 * @brief The chain walk stops at an owner that waits for no mutex.
 *
 * @details
 * - Setup: the middle priority thread holds m1. It is pending (for example
 *   on a semaphore), but @c mutex_pended_on is NULL.
 * - Action: z_impl_k_mutex_lock() of m1 with TEST_TIMEOUT.
 * - Expected: one z_thread_prio_set() before the wait, with the middle
 *   priority thread.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock()
 */
ZTEST(mutex_unit, test_pi_chain_stops_at_owner_without_mutex)
{
	give_mutex(&m1, &t_mid, 1U);
	t_mid.base.thread_state |= _THREAD_PENDING;
	prio_sets_at_pend = 0U;
	set_other_thread(record_prio_sets);

	(void)z_impl_k_mutex_lock(&m1, TEST_TIMEOUT);

	zassert_equal(prio_sets_at_pend, 1U);
	zassert_equal_ptr(z_thread_prio_set_fake.arg0_history[0], &t_mid);
}

/**
 * @brief The chain walk stops when the chain comes back to the first mutex.
 *
 * @details
 * Without the stop, a cycle that does not contain the current thread
 * would make the walk run until the hop limit.
 * - Setup: the middle priority thread holds m1 and waits for m2. The low
 *   priority thread holds m2 and waits for m1. Both wait with a timeout.
 * - Action: z_impl_k_mutex_lock() of m1 with TEST_TIMEOUT.
 * - Expected: exactly two priority raises before the wait (middle, then
 *   low). No assertion.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock()
 */
ZTEST(mutex_unit, test_pi_chain_stops_at_cycle_to_first_mutex)
{
	give_mutex(&m1, &t_mid, 1U);
	give_mutex(&m2, &t_low, 1U);
	let_wait(&t_mid, &m2);
	let_wait(&t_low, &m1);
	prio_sets_at_pend = 0U;
	set_other_thread(record_prio_sets);

	(void)z_impl_k_mutex_lock(&m1, TEST_TIMEOUT);

	zassert_equal(prio_sets_at_pend, 2U);
	zassert_equal_ptr(z_thread_prio_set_fake.arg0_history[0], &t_mid);
	zassert_equal_ptr(z_thread_prio_set_fake.arg0_history[1], &t_low);
#ifdef CONFIG_ASSERT
	zassert_equal(assert_post_action_fake.call_count, 0);
#endif
}

/**
 * @brief The chain walk never lowers the priority of an owner: a later owner with a higher
 * priority than the boost keeps it.
 *
 * @details
 * - Setup: the low priority thread holds m1 and waits for m2. The
 *   cooperative thread (-5) holds m2. The current thread has the middle
 *   priority.
 * - Action: z_impl_k_mutex_lock() of m1 with TEST_TIMEOUT.
 * - Expected: z_thread_prio_set() only for the low priority thread (to the
 *   middle priority). The cooperative thread keeps -5.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock()
 */
ZTEST(mutex_unit, test_pi_chain_never_lowers_owner)
{
	give_mutex(&m1, &t_low, 1U);
	give_mutex(&m2, &t_coop, 1U);
	let_wait(&t_low, &m2);
	set_current(&t_mid);
	prio_sets_at_pend = 0U;
	set_other_thread(record_prio_sets);

	(void)z_impl_k_mutex_lock(&m1, TEST_TIMEOUT);

	zassert_equal(prio_sets_at_pend, 1U);
	zassert_equal_ptr(z_thread_prio_set_fake.arg0_history[0], &t_low);
	zassert_equal(z_thread_prio_set_fake.arg1_history[0], CEILED(PRIO_MID));
	zassert_equal(t_coop.base.prio, PRIO_COOP);
}

/**
 * @brief The chain walk ends at a mutex without an owner.
 *
 * @details
 * A consistent kernel state has no such mutex: a mutex with a waiting
 * thread has an owner. The check of mutex.c is defensive, and the test
 * builds the state directly.
 * - Setup: the middle priority thread holds m1 and waits for m2. m2 has no
 *   owner.
 * - Action: z_impl_k_mutex_lock() of m1 with TEST_TIMEOUT.
 * - Expected: one priority raise before the wait (the middle priority
 *   thread). No crash.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock()
 */
ZTEST(mutex_unit, test_pi_chain_ends_at_mutex_without_owner)
{
	give_mutex(&m1, &t_mid, 1U);
	let_wait(&t_mid, &m2);
	prio_sets_at_pend = 0U;
	set_other_thread(record_prio_sets);

	(void)z_impl_k_mutex_lock(&m1, TEST_TIMEOUT);

	zassert_equal(prio_sets_at_pend, 1U);
	zassert_equal_ptr(z_thread_prio_set_fake.arg0_history[0], &t_mid);
}

/**
 * @brief The reschedule hint of any owner in the chain counts: a later raise without the hint
 * does not clear it.
 *
 * @details
 * - Setup: the middle priority thread holds m1 and waits for m2. The low
 *   priority thread holds m2. z_thread_prio_set() returns true for the
 *   first owner and false for the second owner and for the restore after
 *   the timeout. No thread wakes the current thread.
 * - Action: z_impl_k_mutex_lock() of m1 with TEST_TIMEOUT.
 * - Expected: after the timeout, the unit releases mutex_lock with
 *   z_reschedule().
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock()
 */
ZTEST(mutex_unit, test_pi_chain_resched_hint_of_any_owner)
{
	give_mutex(&m1, &t_mid, 1U);
	give_mutex(&m2, &t_low, 1U);
	let_wait(&t_mid, &m2);
	prio_set_returns[0] = true;
	prio_set_returns[1] = false;
	prio_set_returns[2] = false;
	z_thread_prio_set_fake.custom_fake = prio_set_sequence;

	(void)z_impl_k_mutex_lock(&m1, TEST_TIMEOUT);

	zassert_equal(z_thread_prio_set_fake.call_count, 3);
	zassert_equal(z_reschedule_fake.call_count, 1);
}

/**
 * @brief The chain walk raises at most MUTEX_CHAIN_WALK_MAX_HOPS (16) owners.
 *
 * @details
 * - Setup: a chain of 18 threads with the low priority. Thread i holds
 *   mutex i, and each thread except the last waits for the mutex of the
 *   next thread.
 * - Action: z_impl_k_mutex_lock() of mutex 0 with TEST_TIMEOUT.
 * - Expected: before the wait, z_thread_prio_set() raises the threads 0 to
 *   15, in this order. Threads 16 and 17 keep the low priority.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock()
 */
ZTEST(mutex_unit, test_pi_chain_walk_hop_limit)
{
	for (size_t i = 0; i < CHAIN_LEN; i++) {
		thread_prepare(&chain_threads[i], PRIO_LOW);
		mutex_prepare(&chain_mutexes[i]);
		give_mutex(&chain_mutexes[i], &chain_threads[i], 1U);
	}
	for (size_t i = 0; i + 1U < CHAIN_LEN; i++) {
		let_wait(&chain_threads[i], &chain_mutexes[i + 1U]);
	}
	prio_sets_at_pend = 0U;
	set_other_thread(record_prio_sets);

	(void)z_impl_k_mutex_lock(&chain_mutexes[0], TEST_TIMEOUT);

	/* The design value of the hop limit is 16, not only the macro. */
	zassert_equal(prio_sets_at_pend, 16U);
	for (size_t i = 0; i < 16U; i++) {
		zassert_equal_ptr(z_thread_prio_set_fake.arg0_history[i], &chain_threads[i]);
		zassert_equal(z_thread_prio_set_fake.arg1_history[i], CEILED(PRIO_HIGH));
	}
	/* After the timeout, only the first owner has its original priority again. */
	zassert_equal(chain_threads[1].base.prio, CEILED(PRIO_HIGH));
	zassert_equal(chain_threads[15].base.prio, CEILED(PRIO_HIGH));
	zassert_equal(chain_threads[16].base.prio, PRIO_LOW);
	zassert_equal(chain_threads[17].base.prio, PRIO_LOW);
}

/**
 * @brief The boost of a lock needs no reschedule if the wait succeeds: k_mutex_lock() ignores the
 * reschedule hint of z_thread_prio_set() after a hand-over.
 *
 * @details
 * z_pend_curr() already switched to another thread.
 * - Setup: the low priority thread holds the mutex. z_thread_prio_set()
 *   returns true. The owner unlocks the mutex while the current thread
 *   waits.
 * - Action: z_impl_k_mutex_lock() with K_FOREVER.
 * - Expected: return value 0. The only z_reschedule() is the one of the
 *   unlock of the other thread.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock()
 */
ZTEST(mutex_unit, test_pi_boost_no_reschedule_after_handover)
{
	give_mutex(&m1, &t_low, 1U);
	z_thread_prio_set_fake.return_val = true;
	other_mutex = &m1;
	other_thread = &t_low;
	set_other_thread(owner_unlocks);

	zassert_equal(z_impl_k_mutex_lock(&m1, K_FOREVER), 0);

	zassert_equal(z_reschedule_fake.call_count, 1);
}
#endif /* Z_MUTEX_PI_ENABLED */

#ifdef CONFIG_MUTEX_DEADLOCK_DETECT
/*
 * Tests: Deadlock detection. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_mutex, at the top of this file.
 */

/**
 * @brief A K_FOREVER lock asserts if the owner waits forever for a mutex of the current thread.
 *
 * @details
 * - Setup: the current thread holds m2. The low priority thread holds m1
 *   and waits forever for m2.
 * - Action: z_impl_k_mutex_lock() of m1 with K_FOREVER.
 * - Expected: one failed assertion, before z_pend_curr(). The walk stops at
 *   the assertion: the owner keeps the low priority.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock()
 */
ZTEST(mutex_unit, test_deadlock_two_threads_asserts)
{
	give_mutex(&m2, &t_high, 1U);
	give_mutex(&m1, &t_low, 1U);
	let_wait(&t_low, &m2);
	set_other_thread(record_owner_prio);
	owner_prio_at_pend = UNSET;

	(void)z_impl_k_mutex_lock(&m1, K_FOREVER);

	zassert_equal(assert_post_action_fake.call_count, 1);
	zassert_called_before(assert_post_action, z_pend_curr);
	zassert_equal(owner_prio_at_pend, PRIO_LOW);
}

/**
 * @brief The deadlock check finds a cycle through more than one owner.
 *
 * @details
 * - Setup: the current thread holds m3. The low priority thread holds m1
 *   and waits forever for m2. The middle priority thread holds m2 and waits
 *   forever for m3.
 * - Action: z_impl_k_mutex_lock() of m1 with K_FOREVER.
 * - Expected: one failed assertion. Before it, the walk raised the low
 *   priority thread. It did not raise the middle priority thread.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock()
 */
ZTEST(mutex_unit, test_deadlock_three_threads_asserts)
{
	give_mutex(&m3, &t_high, 1U);
	give_mutex(&m1, &t_low, 1U);
	give_mutex(&m2, &t_mid, 1U);
	let_wait(&t_low, &m2);
	let_wait(&t_mid, &m3);

	(void)z_impl_k_mutex_lock(&m1, K_FOREVER);

	zassert_equal(assert_post_action_fake.call_count, 1);
	zassert_equal(z_thread_prio_set_fake.arg0_history[0], &t_low);
	zassert_equal(t_mid.base.prio, PRIO_MID);
}

/**
 * @brief A cycle is not a deadlock if the current thread waits with a finite timeout.
 *
 * @details
 * - Setup: as in the two-thread deadlock test.
 * - Action: z_impl_k_mutex_lock() of m1 with TEST_TIMEOUT.
 * - Expected: no assertion. The owner gets the boost.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock()
 */
ZTEST(mutex_unit, test_deadlock_finite_timeout_of_current_no_assert)
{
	give_mutex(&m2, &t_high, 1U);
	give_mutex(&m1, &t_low, 1U);
	let_wait(&t_low, &m2);

	(void)z_impl_k_mutex_lock(&m1, TEST_TIMEOUT);

	zassert_equal(assert_post_action_fake.call_count, 0);
	zassert_equal_ptr(z_thread_prio_set_fake.arg0_history[0], &t_low);
}

/**
 * @brief A cycle is not a deadlock if an owner in the chain waits with a finite timeout.
 *
 * @details
 * - Setup: as in the three-thread deadlock test, but the middle priority
 *   thread has an active timeout.
 * - Action: z_impl_k_mutex_lock() of m1 with K_FOREVER.
 * - Expected: no assertion.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock()
 */
ZTEST(mutex_unit, test_deadlock_finite_timeout_in_chain_no_assert)
{
	give_mutex(&m3, &t_high, 1U);
	give_mutex(&m1, &t_low, 1U);
	give_mutex(&m2, &t_mid, 1U);
	let_wait(&t_low, &m2);
	let_wait(&t_mid, &m3);
	set_timeout_active(&t_mid);

	(void)z_impl_k_mutex_lock(&m1, K_FOREVER);

	zassert_equal(assert_post_action_fake.call_count, 0);
}

/**
 * @brief A cycle is not a deadlock if the owner that closes it is not pending.
 *
 * @details
 * A thread that timed out can still have a stale @c mutex_pended_on.
 * - Setup: as in the two-thread deadlock test, but the low priority thread
 *   is not in the state "pending".
 * - Action: z_impl_k_mutex_lock() of m1 with K_FOREVER.
 * - Expected: no assertion.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock()
 */
ZTEST(mutex_unit, test_deadlock_stale_pended_on_no_assert)
{
	give_mutex(&m2, &t_high, 1U);
	give_mutex(&m1, &t_low, 1U);
	t_low.mutex_pended_on = &m2;

	(void)z_impl_k_mutex_lock(&m1, K_FOREVER);

	zassert_equal(assert_post_action_fake.call_count, 0);
}

/**
 * @brief The deadlock check asserts only for a cycle back to the current thread.
 *
 * @details
 * - Setup: the low priority thread holds m1 and waits forever for m2. The
 *   middle priority thread holds m2 and waits forever for m1. The current
 *   thread holds no mutex.
 * - Action: z_impl_k_mutex_lock() of m1 with K_FOREVER.
 * - Expected: no assertion. The walk stops at the cycle to m1.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock()
 */
ZTEST(mutex_unit, test_deadlock_cycle_without_current_no_assert)
{
	give_mutex(&m1, &t_low, 1U);
	give_mutex(&m2, &t_mid, 1U);
	let_wait(&t_low, &m2);
	let_wait(&t_mid, &m1);

	(void)z_impl_k_mutex_lock(&m1, K_FOREVER);

	zassert_equal(assert_post_action_fake.call_count, 0);
}
#endif /* CONFIG_MUTEX_DEADLOCK_DETECT */

#if Z_MUTEX_PI_ENABLED && !defined(CONFIG_MUTEX_DEADLOCK_DETECT)
/**
 * @brief Without CONFIG_MUTEX_DEADLOCK_DETECT, a K_FOREVER lock that closes a cycle raises the
 * owner and waits, without an assertion.
 *
 * @details
 * - Setup: the current thread holds m2. The low priority thread holds m1
 *   and waits forever for m2.
 * - Action: z_impl_k_mutex_lock() of m1 with K_FOREVER.
 * - Expected: z_thread_prio_set() with the low priority thread, then
 *   z_pend_curr(). No assertion (with CONFIG_ASSERT).
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock()
 */
ZTEST(mutex_unit, test_deadlock_not_detected_without_option)
{
	give_mutex(&m2, &t_high, 1U);
	give_mutex(&m1, &t_low, 1U);
	let_wait(&t_low, &m2);

	(void)z_impl_k_mutex_lock(&m1, K_FOREVER);

	zassert_equal_ptr(z_thread_prio_set_fake.arg0_history[0], &t_low);
	zassert_called_before(z_thread_prio_set, z_pend_curr);
#ifdef CONFIG_ASSERT
	zassert_equal(assert_post_action_fake.call_count, 0);
#endif
}
#endif

/*
 * Tests: Unlock. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_mutex, at the top of this file.
 */

/**
 * @brief k_mutex_unlock() of a mutex without an owner returns -EINVAL and does not lock.
 *
 * @details
 * Applies with CONFIG_RUNTIME_ERROR_CHECKS (the default CHECKIF() option).
 * - Setup: a free mutex.
 * - Action: z_impl_k_mutex_unlock().
 * - Expected: return value -EINVAL. No lock, no change of the mutex.
 *
 * @ingroup kernel_unit_mutex_k_mutex_unlock
 * @see z_impl_k_mutex_unlock()
 */
ZTEST(mutex_unit, test_unlock_free_mutex_returns_einval)
{
	if (!IS_ENABLED(CONFIG_RUNTIME_ERROR_CHECKS)) {
		ztest_test_skip();
	}

	zassert_equal(z_impl_k_mutex_unlock(&m1), -EINVAL);

	zassert_equal(unit_arch_irq_lock_fake.call_count, 0);
	zassert_is_null(m1.owner);
	zassert_equal(m1.lock_count, 0U);
}

/**
 * @brief k_mutex_unlock() by a thread that is not the owner returns -EPERM and changes nothing.
 *
 * @details
 * Applies with CONFIG_RUNTIME_ERROR_CHECKS.
 * - Setup: the low priority thread holds the mutex, and a thread waits for
 *   it.
 * - Action: z_impl_k_mutex_unlock() by the current thread.
 * - Expected: return value -EPERM. No lock. Owner, lock count and wait
 *   queue did not change.
 *
 * @ingroup kernel_unit_mutex_k_mutex_unlock
 * @see z_impl_k_mutex_unlock()
 */
ZTEST(mutex_unit, test_unlock_not_owner_returns_eperm)
{
	if (!IS_ENABLED(CONFIG_RUNTIME_ERROR_CHECKS)) {
		ztest_test_skip();
	}
	give_mutex(&m1, &t_low, 1U);
	let_wait(&t_mid, &m1);

	zassert_equal(z_impl_k_mutex_unlock(&m1), -EPERM);

	zassert_equal(unit_arch_irq_lock_fake.call_count, 0);
	zassert_equal_ptr(m1.owner, &t_low);
	zassert_equal(m1.lock_count, 1U);
	zassert_equal(waitq_len(&m1), 1U);
}

#ifdef CONFIG_NO_RUNTIME_CHECKS
/**
 * @brief With CONFIG_NO_RUNTIME_CHECKS, k_mutex_unlock() does not check the owner: a thread that
 * is not the owner releases the mutex of another thread.
 *
 * @details
 * This is the behavior without the CHECKIF() checks. The caller must
 * guarantee the ownership.
 * - Setup: the low priority thread holds the mutex with the lock count 1.
 * - Action: z_impl_k_mutex_unlock() by the current thread.
 * - Expected: return value 0. The mutex is free.
 *
 * @ingroup kernel_unit_mutex_k_mutex_unlock
 * @see z_impl_k_mutex_unlock()
 */
ZTEST(mutex_unit, test_unlock_no_checks_releases_other_owner)
{
	give_mutex(&m1, &t_low, 1U);

	zassert_equal(z_impl_k_mutex_unlock(&m1), 0);

	zassert_is_null(m1.owner);
	zassert_equal(m1.lock_count, 0U);
}
#endif

#ifdef CONFIG_ASSERT_ON_ERRORS
/**
 * @brief With CONFIG_ASSERT_ON_ERRORS, k_mutex_unlock() asserts if the mutex has no owner or the
 * current thread is not the owner.
 *
 * @details
 * - Setup: a free mutex, then a mutex of the low priority thread.
 * - Action: z_impl_k_mutex_unlock() of each.
 * - Expected: one failed assertion for each call, before the lock.
 *
 * @ingroup kernel_unit_mutex_k_mutex_unlock
 * @see z_impl_k_mutex_unlock()
 */
ZTEST(mutex_unit, test_unlock_checks_assert_on_errors)
{
	(void)z_impl_k_mutex_unlock(&m1);
	zassert_true(assert_post_action_fake.call_count >= 1U);
	zassert_called_before(assert_post_action, unit_arch_irq_lock);

	RESET_FAKE(assert_post_action);
	FFF_RESET_HISTORY();
	mutex_prepare(&m2);
	give_mutex(&m2, &t_low, 1U);
	(void)z_impl_k_mutex_unlock(&m2);
	zassert_true(assert_post_action_fake.call_count >= 1U);
}
#endif

/**
 * @brief An unlock of a recursive lock decrements the lock count, keeps the owner and does not
 * lock.
 *
 * @details
 * - Setup: the current thread holds the mutex with the lock count 3, and a
 *   thread waits for it.
 * - Action: z_impl_k_mutex_unlock().
 * - Expected: return value 0. The lock count is 2, the owner did not
 *   change. No lock, no hand-over, no priority change.
 *
 * @ingroup kernel_unit_mutex_k_mutex_unlock
 * @see z_impl_k_mutex_unlock()
 */
ZTEST(mutex_unit, test_unlock_recursive_decrements_count)
{
	give_mutex(&m1, &t_high, 3U);
	let_wait(&t_mid, &m1);

	zassert_equal(z_impl_k_mutex_unlock(&m1), 0);

	zassert_equal(m1.lock_count, 2U);
	zassert_equal_ptr(m1.owner, &t_high);
	zassert_equal(unit_arch_irq_lock_fake.call_count, 0);
	zassert_equal(z_unpend_first_thread_locked_fake.call_count, 0);
	zassert_equal(z_thread_prio_set_fake.call_count, 0);
	zassert_call_history(ISR_CHECK_CALL);
}

/**
 * @brief The last unlock of a mutex without waiting threads makes the mutex free.
 *
 * @details
 * - Setup: the current thread holds the mutex with the lock count 1. No
 *   thread waits.
 * - Action: z_impl_k_mutex_unlock().
 * - Expected: return value 0. The owner is NULL, the lock count is 0. No
 *   thread became ready.
 *
 * @ingroup kernel_unit_mutex_k_mutex_unlock
 * @see z_impl_k_mutex_unlock()
 */
ZTEST(mutex_unit, test_unlock_last_without_waiter_frees_mutex)
{
	give_mutex(&m1, &t_high, 1U);

	zassert_equal(z_impl_k_mutex_unlock(&m1), 0);

	zassert_is_null(m1.owner);
	zassert_equal(m1.lock_count, 0U);
	zassert_equal(z_sched_ready_locked_fake.call_count, 0);
	zassert_equal(arch_thread_return_value_set_fake.call_count, 0);
}

/**
 * @brief The last unlock without waiting threads releases mutex_lock with k_spin_unlock().
 *
 * @details
 * - Setup: as in the test before.
 * - Action: z_impl_k_mutex_unlock().
 * - Expected: the lock invariant holds, with one lock and the release by
 *   k_spin_unlock(). One z_unpend_first_thread_locked() with the wait queue
 *   of the mutex.
 *
 * @ingroup kernel_unit_mutex_k_mutex_unlock
 * @see z_impl_k_mutex_unlock()
 */
ZTEST(mutex_unit, test_unlock_last_without_waiter_lock_sequence)
{
	give_mutex(&m1, &t_high, 1U);

	(void)z_impl_k_mutex_unlock(&m1);

	zassert_equal(z_unpend_first_thread_locked_fake.call_count, 1);
	zassert_equal_ptr(z_unpend_first_thread_locked_fake.arg0_val, &m1.wait_q);
	assert_lock_invariant(1U, KERNEL_UNIT_RELEASED_BY_UNLOCK);
}

/**
 * @brief The last unlock gives the mutex to the first waiting thread with the lock count 1.
 *
 * @details
 * - Setup: the current thread holds the mutex. The middle and the low
 *   priority threads wait for it.
 * - Action: z_impl_k_mutex_unlock().
 * - Expected: return value 0. The owner is the middle priority thread, the
 *   lock count is 1. The low priority thread still waits.
 *
 * @ingroup kernel_unit_mutex_k_mutex_unlock
 * @see z_impl_k_mutex_unlock()
 */
ZTEST(mutex_unit, test_unlock_hands_over_to_first_waiter)
{
	give_mutex(&m1, &t_high, 1U);
	let_wait(&t_low, &m1);
	let_wait(&t_mid, &m1);

	zassert_equal(z_impl_k_mutex_unlock(&m1), 0);

	zassert_equal_ptr(m1.owner, &t_mid);
	zassert_equal(m1.lock_count, 1U);
	zassert_equal(waitq_len(&m1), 1U);
	zassert_true(z_is_thread_pending(&t_low));
	zassert_false(z_is_thread_pending(&t_mid));
}

/**
 * @brief The hand-over wakes the new owner with the wait result 0 and makes it ready.
 *
 * @details
 * - Setup: the current thread holds the mutex. The middle priority thread
 *   waits.
 * - Action: z_impl_k_mutex_unlock().
 * - Expected: arch_thread_return_value_set() with the new owner and 0, then
 *   z_sched_ready_locked() with the new owner, both while the unit holds
 *   mutex_lock (and the scheduler spinlock with more than one CPU).
 *
 * @ingroup kernel_unit_mutex_k_mutex_unlock
 * @see z_impl_k_mutex_unlock()
 */
ZTEST(mutex_unit, test_unlock_handover_wakes_new_owner)
{
	give_mutex(&m1, &t_high, 1U);
	let_wait(&t_mid, &m1);

	(void)z_impl_k_mutex_unlock(&m1);

	zassert_equal(arch_thread_return_value_set_fake.call_count, 1);
	zassert_equal_ptr(arch_thread_return_value_set_fake.arg0_val, &t_mid);
	zassert_equal(arch_thread_return_value_set_fake.arg1_val, 0U);
	zassert_equal(z_sched_ready_locked_fake.call_count, 1);
	zassert_equal_ptr(z_sched_ready_locked_fake.arg0_val, &t_mid);
	zassert_called_before(arch_thread_return_value_set, z_sched_ready_locked);
	zassert_equal(depth_at_unpend, SCHED_LOCK_ENABLED ? 2 : 1);
	zassert_equal(depth_at_ready, SCHED_LOCK_ENABLED ? 2 : 1);
}

/**
 * @brief The hand-over releases mutex_lock with z_reschedule() as the last call.
 *
 * @details
 * - Setup: the current thread holds the mutex. The middle priority thread
 *   waits.
 * - Action: z_impl_k_mutex_unlock().
 * - Expected: the call history is the ISR check (with CONFIG_ASSERT), the
 *   lock, the unpend, the wake, the ready and the reschedule, with the
 *   scheduler spinlock around unpend and ready if there is more than one
 *   CPU. The lock invariant holds.
 *
 * @ingroup kernel_unit_mutex_k_mutex_unlock
 * @see z_impl_k_mutex_unlock()
 */
ZTEST(mutex_unit, test_unlock_handover_lock_sequence)
{
	give_mutex(&m1, &t_high, 1U);
	let_wait(&t_mid, &m1);

	(void)z_impl_k_mutex_unlock(&m1);

	zassert_call_history(ISR_CHECK_CALL, unit_arch_irq_lock,
			     SCHED_LOCK_CALL(unit_arch_irq_lock), z_unpend_first_thread_locked,
			     arch_thread_return_value_set, z_sched_ready_locked,
			     SCHED_LOCK_CALL(unit_arch_irq_unlock), z_reschedule);
	assert_lock_invariant(1U, KERNEL_UNIT_RELEASED_BY_RESCHEDULE);
}

#if Z_MUTEX_PI_ENABLED
/**
 * @brief With priority inheritance, the last unlock removes the mutex from the held list of the
 * owner and adds it to the held list of the new owner.
 *
 * @details
 * - Setup: the current thread holds m1 and m2. The middle priority thread
 *   waits for m1.
 * - Action: z_impl_k_mutex_unlock() of m1.
 * - Expected: the current thread holds only m2. The middle priority thread
 *   holds m1. Its @c mutex_pended_on is NULL.
 *
 * @ingroup kernel_unit_mutex_k_mutex_unlock
 * @see z_impl_k_mutex_unlock()
 */
ZTEST(mutex_unit, test_unlock_moves_held_node_to_new_owner)
{
	give_mutex(&m1, &t_high, 1U);
	give_mutex(&m2, &t_high, 1U);
	let_wait(&t_mid, &m1);

	(void)z_impl_k_mutex_unlock(&m1);

	zassert_false(holds(&t_high, &m1));
	zassert_true(holds(&t_high, &m2));
	zassert_true(holds(&t_mid, &m1));
	zassert_is_null(t_mid.mutex_pended_on);
}

/**
 * @brief The new owner records its original priority if it held no mutex before.
 *
 * @details
 * - Setup: the current thread holds m1. The middle priority thread waits
 *   for m1, holds no mutex, and has another value in @c orig_prio.
 * - Action: z_impl_k_mutex_unlock() of m1.
 * - Expected: @c orig_prio of the new owner is its priority.
 *
 * @ingroup kernel_unit_mutex_k_mutex_unlock
 * @see z_impl_k_mutex_unlock()
 */
ZTEST(mutex_unit, test_unlock_new_owner_records_orig_prio)
{
	give_mutex(&m1, &t_high, 1U);
	let_wait(&t_mid, &m1);
	t_mid.orig_prio = PRIO_LOW;

	(void)z_impl_k_mutex_unlock(&m1);

	zassert_equal(t_mid.orig_prio, PRIO_MID);
}

/**
 * @brief A new owner that holds other mutexes keeps its original priority.
 *
 * @details
 * - Setup: the current thread holds m1. The middle priority thread holds m2,
 *   with the original priority low, and waits for m1.
 * - Action: z_impl_k_mutex_unlock() of m1.
 * - Expected: @c orig_prio of the new owner stays low. It holds m1 and m2.
 *
 * @ingroup kernel_unit_mutex_k_mutex_unlock
 * @see z_impl_k_mutex_unlock()
 */
ZTEST(mutex_unit, test_unlock_new_owner_keeps_orig_prio)
{
	give_mutex(&m1, &t_high, 1U);
	give_mutex(&m2, &t_mid, 1U);
	t_mid.orig_prio = PRIO_LOW;
	let_wait(&t_mid, &m1);

	(void)z_impl_k_mutex_unlock(&m1);

	zassert_equal(t_mid.orig_prio, PRIO_LOW);
	zassert_true(holds(&t_mid, &m1));
	zassert_true(holds(&t_mid, &m2));
}
#endif /* Z_MUTEX_PI_ENABLED */

#if Z_MUTEX_PI_ENABLED
/*
 * Tests: Priority restore. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_mutex, at the top of this file.
 */

/**
 * @brief The last unlock gives a raised owner its original priority if it holds no other mutex.
 *
 * @details
 * - Setup: the current thread has the original priority low and the raised
 *   priority high. It holds the mutex, and the middle priority thread waits.
 * - Action: z_impl_k_mutex_unlock().
 * - Expected: z_thread_prio_set() with the current thread and the low
 *   priority, before the hand-over, while the unit holds mutex_lock.
 *
 * @ingroup kernel_unit_mutex_k_mutex_unlock
 * @see z_impl_k_mutex_unlock(), held_mutexes_highest_waiter_prio()
 */
ZTEST(mutex_unit, test_restore_unlock_to_orig_prio)
{
	give_mutex(&m1, &t_high, 1U);
	t_high.orig_prio = PRIO_LOW;
	let_wait(&t_mid, &m1);

	(void)z_impl_k_mutex_unlock(&m1);

	zassert_equal(z_thread_prio_set_fake.call_count, 1);
	zassert_equal_ptr(z_thread_prio_set_fake.arg0_val, &t_high);
	zassert_equal(z_thread_prio_set_fake.arg1_val, PRIO_LOW);
	zassert_equal(t_high.base.prio, PRIO_LOW);
	zassert_called_before(z_thread_prio_set, z_unpend_first_thread_locked);
	zassert_equal(prio_sets_without_lock, 0U);
}

/**
 * @brief The last unlock keeps the boost that another held mutex needs.
 *
 * @details
 * - Setup: the current thread has the original priority low and the raised
 *   priority high. It holds m1 and m2. The middle priority thread waits for
 *   m2. No thread waits for m1.
 * - Action: z_impl_k_mutex_unlock() of m1.
 * - Expected: z_thread_prio_set() with the middle priority (limited by the
 *   ceiling).
 *
 * @ingroup kernel_unit_mutex_k_mutex_unlock
 * @see z_impl_k_mutex_unlock(), held_mutexes_highest_waiter_prio()
 */
ZTEST(mutex_unit, test_restore_unlock_keeps_boost_of_other_mutex)
{
	give_mutex(&m1, &t_high, 1U);
	give_mutex(&m2, &t_high, 1U);
	t_high.orig_prio = PRIO_LOW;
	let_wait(&t_mid, &m2);

	(void)z_impl_k_mutex_unlock(&m1);

	zassert_equal(z_thread_prio_set_fake.arg1_val, CEILED(PRIO_MID));
}

/**
 * @brief The released mutex does not count for the new priority: its waiters do not keep the boost.
 *
 * @details
 * - Setup: the current thread has the original priority low and the raised
 *   priority high. It holds m1, and the high priority thread t_coop waits
 *   for m1.
 * - Action: z_impl_k_mutex_unlock() of m1.
 * - Expected: z_thread_prio_set() with the low priority.
 *
 * @ingroup kernel_unit_mutex_k_mutex_unlock
 * @see z_impl_k_mutex_unlock(), held_mutexes_highest_waiter_prio()
 */
ZTEST(mutex_unit, test_restore_unlock_ignores_released_mutex)
{
	give_mutex(&m1, &t_high, 1U);
	t_high.orig_prio = PRIO_LOW;
	let_wait(&t_coop, &m1);

	(void)z_impl_k_mutex_unlock(&m1);

	zassert_equal(z_thread_prio_set_fake.arg1_val, PRIO_LOW);
}

/**
 * @brief The new priority is the highest of the waiters of all held mutexes.
 *
 * @details
 * - Setup: the current thread has the original priority low and holds m1,
 *   m2 and m3. The middle priority thread waits for m2, the cooperative
 *   thread waits for m3. Its raised priority is the cooperative priority.
 * - Action: z_impl_k_mutex_unlock() of m1.
 * - Expected: no priority change: the cooperative waiter (limited by the
 *   ceiling) keeps the current priority.
 *
 * @ingroup kernel_unit_mutex_k_mutex_unlock
 * @see z_impl_k_mutex_unlock(), held_mutexes_highest_waiter_prio()
 */
ZTEST(mutex_unit, test_restore_unlock_highest_of_all_held)
{
	give_mutex(&m1, &t_high, 1U);
	give_mutex(&m2, &t_high, 1U);
	give_mutex(&m3, &t_high, 1U);
	t_high.orig_prio = PRIO_LOW;
	t_high.base.prio = CEILED(PRIO_COOP);
	let_wait(&t_mid, &m2);
	let_wait(&t_coop, &m3);

	(void)z_impl_k_mutex_unlock(&m1);

	zassert_equal(z_thread_prio_set_fake.call_count, 0);
	zassert_equal(t_high.base.prio, CEILED(PRIO_COOP));
}

/**
 * @brief The original priority is the floor of the new priority: a waiter with a lower priority
 * does not lower the owner below it.
 *
 * @details
 * - Setup: the current thread has the original priority high and the raised
 *   priority -5. It holds m1 and m2. The low priority thread waits for m2.
 * - Action: z_impl_k_mutex_unlock() of m1.
 * - Expected: z_thread_prio_set() with the high priority, not the low
 *   priority.
 *
 * @ingroup kernel_unit_mutex_k_mutex_unlock
 * @see z_impl_k_mutex_unlock()
 * @see held_mutexes_highest_waiter_prio()
 */
ZTEST(mutex_unit, test_restore_orig_prio_is_floor)
{
	give_mutex(&m1, &t_high, 1U);
	give_mutex(&m2, &t_high, 1U);
	t_high.base.prio = CEILED(PRIO_COOP);
	let_wait(&t_low, &m2);

	(void)z_impl_k_mutex_unlock(&m1);

	zassert_equal(z_thread_prio_set_fake.call_count, 1);
	zassert_equal(z_thread_prio_set_fake.arg1_val, PRIO_HIGH);
}

/**
 * @brief The last unlock does not compute a new priority if the priority of the owner is its
 * original priority.
 *
 * @details
 * - Setup: the current thread holds m1 and m2 with its original priority.
 *   The cooperative thread waits for m2.
 * - Action: z_impl_k_mutex_unlock() of m1.
 * - Expected: no z_waitq_head_locked() and no z_thread_prio_set().
 *
 * @ingroup kernel_unit_mutex_k_mutex_unlock
 * @see z_impl_k_mutex_unlock()
 */
ZTEST(mutex_unit, test_restore_unlock_skips_unboosted_owner)
{
	give_mutex(&m1, &t_high, 1U);
	give_mutex(&m2, &t_high, 1U);
	let_wait(&t_coop, &m2);

	(void)z_impl_k_mutex_unlock(&m1);

	zassert_equal(z_waitq_head_locked_fake.call_count, 0);
	zassert_equal(z_thread_prio_set_fake.call_count, 0);
}

/**
 * @brief The last unlock ignores the reschedule hint of z_thread_prio_set(): without a waiter, it
 * releases mutex_lock with k_spin_unlock().
 *
 * @details
 * - Setup: the current thread has the original priority low and the raised
 *   priority high. It holds m1, and no thread waits. z_thread_prio_set()
 *   returns true.
 * - Action: z_impl_k_mutex_unlock() of m1.
 * - Expected: z_thread_prio_set() with the low priority. No z_reschedule():
 *   the lock invariant holds with the release by k_spin_unlock().
 *
 * @ingroup kernel_unit_mutex_k_mutex_unlock
 * @see z_impl_k_mutex_unlock()
 */
ZTEST(mutex_unit, test_restore_unlock_ignores_resched_hint)
{
	give_mutex(&m1, &t_high, 1U);
	t_high.orig_prio = PRIO_LOW;
	z_thread_prio_set_fake.return_val = true;

	(void)z_impl_k_mutex_unlock(&m1);

	zassert_equal(z_thread_prio_set_fake.arg1_val, PRIO_LOW);
	zassert_equal(z_reschedule_fake.call_count, 0);
	assert_lock_invariant(1U, KERNEL_UNIT_RELEASED_BY_UNLOCK);
}

/**
 * @brief The computation of the new priority reads each wait queue with the scheduler spinlock
 * (more than one CPU) inside mutex_lock, and limits each waiter by the ceiling.
 *
 * @details
 * - Setup: the current thread has the original priority low and holds m1
 *   and m2. The cooperative thread waits for m2. The raised priority is
 *   high.
 * - Action: z_impl_k_mutex_unlock() of m1.
 * - Expected: one z_waitq_head_locked() with the wait queue of m2. Then
 *   z_thread_prio_set() with the cooperative priority, limited by the
 *   ceiling. With more than one CPU, the scheduler spinlock nests twice:
 *   for the scan and for the hand-over.
 *
 * @ingroup kernel_unit_mutex_k_mutex_unlock
 * @see z_impl_k_mutex_unlock()
 * @see held_mutexes_highest_waiter_prio()
 */
ZTEST(mutex_unit, test_restore_scan_under_sched_lock)
{
	give_mutex(&m1, &t_high, 1U);
	give_mutex(&m2, &t_high, 1U);
	t_high.orig_prio = PRIO_LOW;
	let_wait(&t_coop, &m2);

	(void)z_impl_k_mutex_unlock(&m1);

	zassert_equal(z_waitq_head_locked_fake.call_count, 1);
	zassert_equal_ptr(z_waitq_head_locked_fake.arg0_val, &m2.wait_q);
	zassert_equal(z_thread_prio_set_fake.arg1_val, CEILED(PRIO_COOP));
	zassert_equal(kernel_unit_lock.nested_locks, SCHED_LOCK_ENABLED ? 2U : 0U);
	assert_lock_invariant(1U, KERNEL_UNIT_RELEASED_BY_UNLOCK);
}

/**
 * @brief After a timeout, k_mutex_lock() gives the owner its original priority if no other thread
 * waits for its mutexes.
 *
 * @details
 * - Setup: the low priority thread holds the mutex. No thread wakes the
 *   current thread.
 * - Action: z_impl_k_mutex_lock() with TEST_TIMEOUT.
 * - Expected: return value -EAGAIN. The second z_thread_prio_set() gives the
 *   owner the low priority. The owner has the low priority at the end.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock(), held_mutexes_highest_waiter_prio()
 */
ZTEST(mutex_unit, test_restore_timeout_to_orig_prio)
{
	give_mutex(&m1, &t_low, 1U);

	zassert_equal(z_impl_k_mutex_lock(&m1, TEST_TIMEOUT), -EAGAIN);

	zassert_equal(z_thread_prio_set_fake.call_count, 2);
	zassert_equal_ptr(z_thread_prio_set_fake.arg0_history[1], &t_low);
	zassert_equal(z_thread_prio_set_fake.arg1_history[1], PRIO_LOW);
	zassert_equal(t_low.base.prio, PRIO_LOW);
}

/**
 * @brief After a timeout, the owner keeps the boost that the waiters of its other mutexes need.
 *
 * @details
 * - Setup: the low priority thread holds m1 and m2. The middle priority
 *   thread waits for m2 (the owner already has the middle priority). No
 *   thread wakes the current thread.
 * - Action: z_impl_k_mutex_lock() of m1 with TEST_TIMEOUT.
 * - Expected: the owner gets the high priority, and after the timeout the
 *   middle priority (limited by the ceiling).
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock(), held_mutexes_highest_waiter_prio()
 */
ZTEST(mutex_unit, test_restore_timeout_keeps_partial_boost)
{
	give_mutex(&m1, &t_low, 1U);
	give_mutex(&m2, &t_low, 1U);
	let_wait(&t_mid, &m2);
	t_low.base.prio = CEILED(PRIO_MID);

	(void)z_impl_k_mutex_lock(&m1, TEST_TIMEOUT);

	zassert_equal(z_thread_prio_set_fake.arg1_history[0], CEILED(PRIO_HIGH));
	zassert_equal(t_low.base.prio, CEILED(PRIO_MID));
}

/**
 * @brief After a timeout, k_mutex_lock() reschedules if a priority change asked for it.
 *
 * @details
 * - Setup: the low priority thread holds the mutex. z_thread_prio_set()
 *   returns true. No thread wakes the current thread.
 * - Action: z_impl_k_mutex_lock() with TEST_TIMEOUT.
 * - Expected: return value -EAGAIN. The second lock is released with
 *   z_reschedule(): the lock invariant holds with 2 locks.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock()
 */
ZTEST(mutex_unit, test_restore_timeout_reschedules_on_hint)
{
	give_mutex(&m1, &t_low, 1U);
	z_thread_prio_set_fake.return_val = true;

	zassert_equal(z_impl_k_mutex_lock(&m1, TEST_TIMEOUT), -EAGAIN);

	assert_lock_invariant(2U, KERNEL_UNIT_RELEASED_BY_RESCHEDULE);
}

/**
 * @brief The reschedule hint of the boost before the wait also counts after the timeout.
 *
 * @details
 * - Setup: the low priority thread holds m1 and m2, and the high priority
 *   thread waits for m2 (so the boost after the timeout keeps the high
 *   priority and changes nothing). The first z_thread_prio_set() returns
 *   true.
 * - Action: z_impl_k_mutex_lock() of m1 by the middle priority thread with
 *   TEST_TIMEOUT.
 * - Expected: the second lock is released with z_reschedule().
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock()
 */
ZTEST(mutex_unit, test_restore_timeout_keeps_boost_hint)
{
	struct k_thread waiter;

	thread_prepare(&waiter, PRIO_COOP);
	give_mutex(&m1, &t_low, 1U);
	give_mutex(&m2, &t_low, 1U);
	let_wait(&waiter, &m2);
	set_current(&t_mid);
	prio_set_returns[0] = true;
	prio_set_returns[1] = false;
	prio_set_returns[2] = false;
	z_thread_prio_set_fake.custom_fake = prio_set_sequence;

	(void)z_impl_k_mutex_lock(&m1, TEST_TIMEOUT);

	zassert_equal(z_thread_prio_set_fake.call_count, 2);
	assert_lock_invariant(2U, KERNEL_UNIT_RELEASED_BY_RESCHEDULE);
}

/**
 * @brief After a timeout, k_mutex_lock() changes no priority if the mutex became free.
 *
 * @details
 * The timeout removed the thread from the wait queue. Then the owner
 * unlocked the mutex before the thread locked mutex_lock again.
 * - Setup: the low priority thread holds the mutex. While the current
 *   thread waits, the timeout removes it from the wait queue, and then the
 *   owner unlocks the mutex.
 * - Action: z_impl_k_mutex_lock() with TEST_TIMEOUT.
 * - Expected: return value -EAGAIN. The mutex is free. Only two priority
 *   changes: the boost of the lock and the restore of the unlock of the
 *   other thread.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock()
 */
ZTEST(mutex_unit, test_restore_timeout_after_unlock_no_change)
{
	give_mutex(&m1, &t_low, 1U);
	other_mutex = &m1;
	other_thread = &t_low;
	set_other_thread(timeout_then_owner_unlocks);

	zassert_equal(z_impl_k_mutex_lock(&m1, TEST_TIMEOUT), -EAGAIN);

	zassert_is_null(m1.owner);
	zassert_equal(z_thread_prio_set_fake.call_count, 2);
	zassert_equal(t_low.base.prio, PRIO_LOW);
}

/**
 * @brief After a timeout, only the first owner of a chain gets a lower priority.
 *
 * @details
 * A known limit of mutex.c: the deeper owners keep the boost until they
 * release their mutexes.
 * - Setup: the middle priority thread holds m1 and waits for m2. The low
 *   priority thread holds m2. No thread wakes the current thread.
 * - Action: z_impl_k_mutex_lock() of m1 with TEST_TIMEOUT.
 * - Expected: the middle priority thread has its original priority again.
 *   The low priority thread keeps the high priority.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock()
 */
ZTEST(mutex_unit, test_restore_timeout_only_first_owner)
{
	give_mutex(&m1, &t_mid, 1U);
	give_mutex(&m2, &t_low, 1U);
	let_wait(&t_mid, &m2);

	(void)z_impl_k_mutex_lock(&m1, TEST_TIMEOUT);

	zassert_equal(t_mid.base.prio, PRIO_MID);
	zassert_equal(t_low.base.prio, CEILED(PRIO_HIGH));
}

static void record_prio_then_unlock(void)
{
	owner_prio_at_pend = t_low.base.prio;
	owner_unlocks();
}

/**
 * @brief Priority inheritance end to end: the owner runs with the priority of the waiter until it
 * unlocks, then the waiter holds the mutex and the owner has its original priority.
 *
 * @details
 * - Setup: the low priority thread holds the mutex. While the current
 *   (high priority) thread waits, the low priority thread unlocks the
 *   mutex. A spy records the priority of the owner at the start of the
 *   unlock.
 * - Action: z_impl_k_mutex_lock() with K_FOREVER.
 * - Expected: return value 0. At the unlock, the owner had the high
 *   priority. At the end, the owner has the low priority, and the current
 *   thread holds the mutex.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock(), z_impl_k_mutex_unlock()
 */
ZTEST(mutex_unit, test_restore_end_to_end)
{
	give_mutex(&m1, &t_low, 1U);
	other_mutex = &m1;
	other_thread = &t_low;
	owner_prio_at_pend = UNSET;
	set_other_thread(record_prio_then_unlock);

	zassert_equal(z_impl_k_mutex_lock(&m1, K_FOREVER), 0);

	zassert_equal(owner_prio_at_pend, CEILED(PRIO_HIGH));
	zassert_equal(t_low.base.prio, PRIO_LOW);
	zassert_equal_ptr(m1.owner, &t_high);
}
#endif /* Z_MUTEX_PI_ENABLED */

#ifdef CONFIG_ASSERT
/*
 * Tests: Assertions. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_mutex, at the top of this file.
 */

/**
 * @brief k_mutex_lock() and k_mutex_unlock() assert that they do not run in an ISR, before the
 * lock.
 *
 * @details
 * - Setup: arch_is_in_isr() returns true. The current thread holds the
 *   mutex for the unlock.
 * - Action: z_impl_k_mutex_lock() with K_NO_WAIT, then
 *   z_impl_k_mutex_unlock().
 * - Expected: one failed assertion for each call, before the first lock.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock(), z_impl_k_mutex_unlock()
 */
ZTEST(mutex_unit, test_assert_not_in_isr)
{
	arch_is_in_isr_fake.return_val = true;

	(void)z_impl_k_mutex_lock(&m1, K_NO_WAIT);
	zassert_equal(assert_post_action_fake.call_count, 1);
	zassert_called_before(assert_post_action, unit_arch_irq_lock);

	(void)z_impl_k_mutex_unlock(&m1);
	zassert_equal(assert_post_action_fake.call_count, 2);
}

/**
 * @brief Out of an ISR, k_mutex_lock() and k_mutex_unlock() do not assert.
 *
 * @details
 * - Setup: arch_is_in_isr() returns false.
 * - Action: z_impl_k_mutex_lock(), then z_impl_k_mutex_unlock().
 * - Expected: no failed assertion. One ISR check for each call.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock(), z_impl_k_mutex_unlock()
 */
ZTEST(mutex_unit, test_assert_thread_context_ok)
{
	(void)z_impl_k_mutex_lock(&m1, K_NO_WAIT);
	(void)z_impl_k_mutex_unlock(&m1);

	zassert_equal(assert_post_action_fake.call_count, 0);
	zassert_equal(arch_is_in_isr_fake.call_count, 2);
}

/**
 * @brief k_mutex_unlock() asserts if the owner has the lock count 0.
 *
 * @details
 * - Setup: the current thread is the owner, but the lock count is 0.
 * - Action: z_impl_k_mutex_unlock().
 * - Expected: one failed assertion before the lock.
 *
 * @ingroup kernel_unit_mutex_k_mutex_unlock
 * @see z_impl_k_mutex_unlock()
 */
ZTEST(mutex_unit, test_assert_unlock_count_zero)
{
	give_mutex(&m1, &t_high, 0U);

	(void)z_impl_k_mutex_unlock(&m1);

	zassert_equal(assert_post_action_fake.call_count, 1);
	zassert_called_before(assert_post_action, unit_arch_irq_lock);
}
#endif /* CONFIG_ASSERT */

#ifdef CONFIG_USERSPACE
/*
 * Tests: System call verification. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_mutex, at the top of this file.
 */

/**
 * @brief z_vrfy_k_mutex_init() checks that the pointer is a mutex object, initialized or not, and
 * then returns the result of z_impl_k_mutex_init().
 *
 * @details
 * - Setup: the object check passes.
 * - Action: z_vrfy_k_mutex_init().
 * - Expected: return value 0. One object check with the mutex, K_OBJ_MUTEX
 *   and _OBJ_INIT_ANY, before z_waitq_init(). No oops.
 *
 * @ingroup kernel_unit_mutex_k_mutex_init
 * @see z_vrfy_k_mutex_init()
 */
ZTEST(mutex_unit, test_vrfy_init_checks_object)
{
	kernel_unit_pass_object_check();

	zassert_equal(z_vrfy_k_mutex_init(&m1), 0);

	kernel_unit_assert_object_check(&m1, K_OBJ_MUTEX, _OBJ_INIT_ANY);
	zassert_called_before(k_object_validation_check, z_waitq_init);
}

/**
 * @brief If the object check fails, z_vrfy_k_mutex_init() stops with an oops before it changes the
 * mutex.
 *
 * @details
 * - Setup: the object check fails. The mutex is filled with a pattern.
 * - Action: z_vrfy_k_mutex_init().
 * - Expected: an oops stops the call. No z_waitq_init(). The mutex did not
 *   change.
 *
 * @ingroup kernel_unit_mutex_k_mutex_init
 * @see z_vrfy_k_mutex_init()
 */
ZTEST(mutex_unit, test_vrfy_init_oops)
{
	memset(&m1, KERNEL_UNIT_FILL, sizeof(m1));
	kernel_unit_fail_object_check();

	zassert_stopped_by_oops((void)z_vrfy_k_mutex_init(&m1));

	zassert_equal(z_waitq_init_fake.call_count, 0);
	kernel_unit_assert_filled(&m1, sizeof(m1));
}

/**
 * @brief z_vrfy_k_mutex_lock() checks that the pointer is an initialized mutex object, and then
 * returns the result of z_impl_k_mutex_lock() with the same timeout.
 *
 * @details
 * - Setup: the object check passes. The low priority thread holds the
 *   mutex.
 * - Action: z_vrfy_k_mutex_lock() with K_NO_WAIT.
 * - Expected: return value -EBUSY. One object check with the mutex,
 *   K_OBJ_MUTEX and _OBJ_INIT_TRUE, before the lock.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_vrfy_k_mutex_lock()
 */
ZTEST(mutex_unit, test_vrfy_lock_checks_object)
{
	kernel_unit_pass_object_check();
	give_mutex(&m1, &t_low, 1U);

	zassert_equal(z_vrfy_k_mutex_lock(&m1, K_NO_WAIT), -EBUSY);

	kernel_unit_assert_object_check(&m1, K_OBJ_MUTEX, _OBJ_INIT_TRUE);
	zassert_called_before(k_object_validation_check, unit_arch_irq_lock);
}

/**
 * @brief z_vrfy_k_mutex_lock() passes the timeout unchanged.
 *
 * @details
 * - Setup: the object check passes. The low priority thread holds the
 *   mutex.
 * - Action: z_vrfy_k_mutex_lock() with TEST_TIMEOUT.
 * - Expected: z_pend_curr() with TEST_TIMEOUT.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_vrfy_k_mutex_lock()
 */
ZTEST(mutex_unit, test_vrfy_lock_passes_timeout)
{
	kernel_unit_pass_object_check();
	give_mutex(&m1, &t_low, 1U);

	(void)z_vrfy_k_mutex_lock(&m1, TEST_TIMEOUT);

	zassert_true(K_TIMEOUT_EQ(z_pend_curr_fake.arg3_val, TEST_TIMEOUT));
}

/**
 * @brief If the object check fails, z_vrfy_k_mutex_lock() stops with an oops before the lock.
 *
 * @details
 * - Setup: the object check fails. A free mutex.
 * - Action: z_vrfy_k_mutex_lock() with K_FOREVER.
 * - Expected: an oops stops the call. No lock, the mutex is still free.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_vrfy_k_mutex_lock()
 */
ZTEST(mutex_unit, test_vrfy_lock_oops)
{
	kernel_unit_fail_object_check();

	zassert_stopped_by_oops((void)z_vrfy_k_mutex_lock(&m1, K_FOREVER));

	zassert_equal(unit_arch_irq_lock_fake.call_count, 0);
	zassert_is_null(m1.owner);
}

/**
 * @brief z_vrfy_k_mutex_unlock() checks that the pointer is an initialized mutex object, and then
 * returns the result of z_impl_k_mutex_unlock().
 *
 * @details
 * - Setup: the object check passes. The current thread holds the mutex with
 *   the lock count 2.
 * - Action: z_vrfy_k_mutex_unlock().
 * - Expected: return value 0, the lock count is 1. One object check with
 *   the mutex, K_OBJ_MUTEX and _OBJ_INIT_TRUE.
 *
 * @ingroup kernel_unit_mutex_k_mutex_unlock
 * @see z_vrfy_k_mutex_unlock()
 */
ZTEST(mutex_unit, test_vrfy_unlock_checks_object)
{
	kernel_unit_pass_object_check();
	give_mutex(&m1, &t_high, 2U);

	zassert_equal(z_vrfy_k_mutex_unlock(&m1), 0);

	zassert_equal(m1.lock_count, 1U);
	kernel_unit_assert_object_check(&m1, K_OBJ_MUTEX, _OBJ_INIT_TRUE);
}

/**
 * @brief If the object check fails, z_vrfy_k_mutex_unlock() stops with an oops before it changes
 * the mutex.
 *
 * @details
 * - Setup: the object check fails. The current thread holds the mutex with
 *   the lock count 2.
 * - Action: z_vrfy_k_mutex_unlock().
 * - Expected: an oops stops the call. The lock count is still 2.
 *
 * @ingroup kernel_unit_mutex_k_mutex_unlock
 * @see z_vrfy_k_mutex_unlock()
 */
ZTEST(mutex_unit, test_vrfy_unlock_oops)
{
	kernel_unit_fail_object_check();
	give_mutex(&m1, &t_high, 2U);

	zassert_stopped_by_oops((void)z_vrfy_k_mutex_unlock(&m1));

	zassert_equal(m1.lock_count, 2U);
}

/**
 * @brief If the object check returns, z_vrfy_k_mutex_lock() raises the oops before the lock.
 *
 * @details
 * With the plain fake, unit_syscall_oops() returns, as the hook of a test
 * can. The unit then continues. The test shows the order of the oops and
 * the lock.
 * - Setup: the object check fails, the oops returns.
 * - Action: z_vrfy_k_mutex_lock() with K_NO_WAIT.
 * - Expected: the oops comes before the first lock.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_vrfy_k_mutex_lock()
 */
ZTEST(mutex_unit, test_vrfy_lock_oops_before_lock)
{
	kernel_unit_fail_object_check();

	(void)z_vrfy_k_mutex_lock(&m1, K_NO_WAIT);

	zassert_called_before(unit_syscall_oops, unit_arch_irq_lock);
}
#endif /* CONFIG_USERSPACE */

#ifdef CONFIG_OBJ_CORE_MUTEX
/*
 * Tests: Object core. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_mutex, at the top of this file.
 */

/**
 * @brief With CONFIG_OBJ_CORE_MUTEX, k_mutex_init() links the object core of the mutex to the
 * mutex object type.
 *
 * @details
 * - Setup: a mutex.
 * - Action: z_impl_k_mutex_init().
 * - Expected: one k_obj_core_init_and_link() with the object core of the
 *   mutex and the type obj_type_mutex.
 *
 * @ingroup kernel_unit_mutex_k_mutex_init
 * @see z_impl_k_mutex_init()
 */
ZTEST(mutex_unit, test_obj_core_init_links)
{
	(void)z_impl_k_mutex_init(&m1);

	zassert_equal(k_obj_core_init_and_link_fake.call_count, 1);
	zassert_equal_ptr(k_obj_core_init_and_link_fake.arg0_val, K_OBJ_CORE(&m1));
	zassert_equal_ptr(k_obj_core_init_and_link_fake.arg1_val, &obj_type_mutex);
}

/**
 * @brief With CONFIG_OBJ_CORE_MUTEX, mutex.c defines one object type descriptor with the ID
 * K_OBJ_TYPE_MUTEX_ID.
 *
 * @details
 * - Setup: none.
 * - Action: walk the descriptors of the section k_obj_core_desc.
 * - Expected: one descriptor for obj_type_mutex, with the ID
 *   K_OBJ_TYPE_MUTEX_ID.
 *
 * @ingroup kernel_unit_mutex_static
 * @see K_OBJ_TYPE_DEFINE()
 */
ZTEST(mutex_unit, test_obj_core_type_descriptor)
{
	unsigned int found = 0U;

	STRUCT_SECTION_FOREACH(k_obj_core_desc, desc) {
		if (desc->type == &obj_type_mutex) {
			found++;
			zassert_equal(desc->type_id, K_OBJ_TYPE_MUTEX_ID);
		}
	}
	zassert_equal(found, 1U);
}
#endif /* CONFIG_OBJ_CORE_MUTEX */

#if Z_MUTEX_PI_ENABLED
/*
 * Tests: Debug logging. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_mutex, at the top of this file.
 */

/**
 * @brief A priority change of a ready owner and of a pending owner gives the same result.
 *
 * @details
 * The debug log reads the state "ready" of the owner. It must not change
 * the behavior.
 * - Setup: the low priority thread holds m1 and is ready. The middle
 *   priority thread holds m2 and is pending.
 * - Action: z_impl_k_mutex_lock() of m1 and of m2 with TEST_TIMEOUT.
 * - Expected: each owner gets the high priority first.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock()
 * @see adjust_owner_prio()
 */
ZTEST(mutex_unit, test_log_ready_and_pending_owner)
{
	give_mutex(&m1, &t_low, 1U);
	give_mutex(&m2, &t_mid, 1U);
	t_mid.base.thread_state |= _THREAD_PENDING;

	(void)z_impl_k_mutex_lock(&m1, TEST_TIMEOUT);
	(void)z_impl_k_mutex_lock(&m2, TEST_TIMEOUT);

	zassert_equal_ptr(z_thread_prio_set_fake.arg0_history[0], &t_low);
	zassert_equal(z_thread_prio_set_fake.arg1_history[0], CEILED(PRIO_HIGH));
	zassert_equal_ptr(z_thread_prio_set_fake.arg0_history[2], &t_mid);
	zassert_equal(z_thread_prio_set_fake.arg1_history[2], CEILED(PRIO_HIGH));
}
/**
 * @brief With CONFIG_KERNEL_LOG_LEVEL_DBG, a lock, a hand-over and a priority change each write a
 * debug message.
 *
 * @details
 * Applies only with the log level DBG (scenario "logging").
 * - Setup: the current thread holds m1 with the original priority low and
 *   the raised priority high. The middle priority thread waits for m1.
 * - Action: z_impl_k_mutex_lock() of the free mutex m2, then
 *   z_impl_k_mutex_unlock() of m1.
 * - Expected: calls of the log backend for the lock, the unlock, the
 *   priority change and the new owner.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock(), z_impl_k_mutex_unlock(), adjust_owner_prio()
 */
ZTEST(mutex_unit, test_log_debug_messages)
{
	if (!IS_ENABLED(CONFIG_KERNEL_LOG_LEVEL_DBG)) {
		ztest_test_skip();
	}
	give_mutex(&m1, &t_high, 1U);
	t_high.orig_prio = PRIO_LOW;
	let_wait(&t_mid, &m1);

	(void)z_impl_k_mutex_lock(&m2, K_NO_WAIT);
	zassert_equal(z_log_minimal_printk_fake.call_count, 1);

	(void)z_impl_k_mutex_unlock(&m1);
	zassert_equal(z_log_minimal_printk_fake.call_count, 4);
}

/**
 * @brief Below the log level DBG, the unit does not call the log backend.
 *
 * @details
 * - Setup: as in the test before.
 * - Action: z_impl_k_mutex_lock() of m2, then z_impl_k_mutex_unlock() of m1.
 * - Expected: no call of the log backend.
 *
 * @ingroup kernel_unit_mutex_k_mutex_lock
 * @see z_impl_k_mutex_lock(), z_impl_k_mutex_unlock()
 */
ZTEST(mutex_unit, test_log_silent_below_debug)
{
	if (IS_ENABLED(CONFIG_KERNEL_LOG_LEVEL_DBG)) {
		ztest_test_skip();
	}
	give_mutex(&m1, &t_high, 1U);
	t_high.orig_prio = PRIO_LOW;
	let_wait(&t_mid, &m1);

	(void)z_impl_k_mutex_lock(&m2, K_NO_WAIT);
	(void)z_impl_k_mutex_unlock(&m1);

	zassert_equal(z_log_minimal_printk_fake.call_count, 0);
}
#endif /* Z_MUTEX_PI_ENABLED */
