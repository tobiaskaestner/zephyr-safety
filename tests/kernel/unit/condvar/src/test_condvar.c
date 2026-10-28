/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @defgroup kernel_unit_condvar kernel/condvar.c
 * @ingroup kernel_unit_tests
 * @brief Design specification of kernel/condvar.c, written as unit tests.
 *
 * @par The condition variable object
 * A condition variable (@c struct @c k_condvar) has these parts:
 * - @c wait_q: the wait queue of the threads that wait in k_condvar_wait().
 * - @c obj_core: with @kconfig{CONFIG_OBJ_CORE_CONDVAR}, the object core of
 *   the condition variable.
 *
 * A condition variable has no other state. It does not count signals. A
 * signal has an effect only on the threads that wait at the time of the
 * signal. The condition itself is data of the application, and a mutex of
 * the application (@c struct @c k_mutex) protects this data.
 *
 * @par Operations
 * - k_condvar_init() initializes the wait queue. It always returns 0.
 * - k_condvar_signal() wakes one waiting thread, if a thread waits. It
 *   always returns 0.
 * - k_condvar_broadcast() wakes all waiting threads and returns their
 *   number.
 * - k_condvar_wait() releases the mutex of the caller, waits on the wait
 *   queue, and locks the mutex again. It returns the result of the wait:
 *   0 after a signal or a broadcast, -EAGAIN after the timeout. With
 *   K_NO_WAIT, it returns -EAGAIN at once and does not release the mutex.
 *
 * A woken thread gets the wait result 0 from the scheduler (argument
 * @c swap_retval of z_sched_wake()), and no data.
 *
 * @par The wait protocol: no lost wake-up
 * The caller of k_condvar_wait() holds the mutex and has found the
 * condition false. A thread that makes the condition true locks the mutex,
 * changes the data and calls k_condvar_signal(). If the waiting thread
 * released the mutex before it was in the wait queue, this signal could
 * come in the gap: it finds no waiting thread, and the wake-up is lost.
 *
 * k_condvar_wait() prevents this. It locks the spinlock @c condvar_lock
 * first. Then it releases the mutex with k_mutex_unlock(). Then it calls
 * z_pend_curr() with the lock and the key. z_pend_curr() adds the current
 * thread to the wait queue and releases the lock in one step. A signal
 * needs @c condvar_lock too. Thus a thread that gets the mutex after
 * k_mutex_unlock() can signal only after the waiting thread is in the wait
 * queue. The release of the mutex and the start of the wait are one atomic
 * step for the other threads.
 *
 * After the wait, k_condvar_wait() locks the mutex again with K_FOREVER,
 * also after a timeout. At this time it does not hold @c condvar_lock,
 * because k_mutex_lock() can block. Thus the caller holds the mutex when
 * k_condvar_wait() returns, as in POSIX pthread_cond_wait().
 *
 * @par Locks
 * All condition variables use one spinlock, @c condvar_lock (static in
 * condvar.c). k_condvar_signal(), k_condvar_broadcast() and
 * k_condvar_wait() lock it before they use the wait queue. k_spin_lock()
 * locks the interrupts with arch_irq_lock() and returns a key. Each path
 * releases the lock exactly once, with the same key:
 * - k_spin_unlock(), if no thread became ready.
 * - z_reschedule(), if a signal or a broadcast woke a thread.
 * - z_pend_curr(), if k_condvar_wait() waits. The only call after the
 *   release is k_mutex_lock().
 *
 * k_condvar_init() does not lock. k_condvar_wait() with K_NO_WAIT does not
 * lock.
 *
 * @par Interfaces below condvar.c
 * - Scheduler (@c ksched.h): z_sched_wake(), z_reschedule(),
 *   z_pend_curr().
 * - Wait queue (@c wait_q.h): z_waitq_init().
 * - Mutex (@c kernel/mutex.c): k_mutex_unlock(), k_mutex_lock(). These are
 *   system calls of the public API. condvar.c ignores their return values.
 * - Object core: k_obj_core_init_and_link(), K_OBJ_TYPE_DEFINE().
 * - Kernel objects: k_object_init().
 * - System call checks: K_SYSCALL_OBJ(), K_SYSCALL_OBJ_INIT(), K_OOPS().
 * - Architecture: arch_irq_lock() and arch_irq_unlock() through
 *   k_spin_lock() and k_spin_unlock().
 * - Tracing: the SYS_PORT_TRACING_OBJ_* hooks. They are empty in the test.
 *
 * @kunit_interfaces
 *
 * @par Kconfig options that change condvar.c
 * - @kconfig{CONFIG_USERSPACE}: the verification functions
 *   z_vrfy_k_condvar_*() and the kernel object of the condition variable.
 * - @kconfig{CONFIG_OBJ_CORE_CONDVAR}: the object type of the condition
 *   variables and the link of each condition variable to it.
 * - @kconfig{CONFIG_ASSERT}: condvar.c has no assertion of its own. The
 *   option enables @kconfig{CONFIG_SPIN_VALIDATE} in @c zephyr/spinlock.h.
 *
 * condvar.c has no CHECKIF(): it does not check its arguments.
 *
 * @par Test method
 * The tests call z_impl_k_condvar_*() and z_vrfy_k_condvar_*() directly.
 * All calls below condvar.c go to FFF fakes. The FFF call history gives
 * the order of the calls. The tests use small models of the layers below,
 * built from custom fakes:
 * - Lock: the fakes arch_irq_lock(), arch_irq_unlock(), z_reschedule() and
 *   z_pend_curr() count the holds of @c condvar_lock. arch_irq_lock()
 *   returns KERNEL_UNIT_IRQ_KEY, so a test can follow the key to the
 *   release.
 * - Mutex: k_mutex_unlock() and k_mutex_lock() record if the caller holds
 *   the mutex.
 * - Wait queue: a number of waiting threads. z_sched_wake() removes the
 *   first one. z_pend_curr() adds the current thread at the end, then
 *   releases the lock, as the real scheduler does.
 * - Other threads: a test can give an action of another thread, for
 *   example a k_condvar_signal(). The action runs when @c condvar_lock is
 *   free. This models a thread on a second CPU that spins on the lock.
 *   z_pend_curr() runs the action after it added the current thread to the
 *   wait queue. If the current thread is not woken, the wait ends as a
 *   timeout with -EAGAIN.
 *
 * The models are small. They show the contract of condvar.c with the
 * layers below. They do not show that the real scheduler and the real
 * mutex keep their side of the contract. The scenarios in
 * @c testcase.yaml build the tests once for each Kconfig option above.
 *
 * @par Structure of the tests
 * Each public function of condvar.c has one group below this group. A
 * system call has one group for z_impl_k_condvar_*() and
 * z_vrfy_k_condvar_*(). The data of condvar.c has the last group. Each test
 * is in the group of the function under test. The rules below (locking,
 * system call verification, object core) apply to more than one function.
 * Their tests are in the group of the function that they call.
 *
 * @par Locking
 * Each path locks condvar_lock once and releases it once with the same key.
 * All condition variables share one spinlock, @c condvar_lock. A path
 * releases it with k_spin_unlock() if no thread became ready, with
 * z_reschedule() if a thread became ready, and with z_pend_curr() if the
 * current thread waits. Each path test asserts the full call sequence and
 * the lock invariant: one lock as the first call, one release with the key
 * of the lock, and the release as the last call (after z_pend_curr(), only
 * k_mutex_lock() follows).
 *
 * @par System call verification
 * With CONFIG_USERSPACE, each verification function checks the objects
 * before it calls the implementation.
 * A system call from a user thread goes to z_vrfy_k_condvar_*(). This
 * function checks that the pointer is a condition variable object of the
 * kernel that the thread has access to. z_vrfy_k_condvar_init() uses
 * K_SYSCALL_OBJ_INIT(): the object can be initialized or not. The other
 * functions use K_SYSCALL_OBJ(): the object must be initialized.
 * z_vrfy_k_condvar_wait() also checks that the mutex pointer is an
 * initialized mutex object. If a check fails, K_OOPS() stops the thread.
 * Otherwise the function calls z_impl_k_condvar_*() with the same
 * arguments and returns its result.
 *
 * In the test, K_OOPS() calls the fake unit_syscall_oops(), and this fake
 * returns. The real K_OOPS() does not return. Thus the tests check that
 * the oops occurs before the implementation locks or changes an object.
 *
 * @par Object core
 * With CONFIG_OBJ_CORE_CONDVAR, condvar.c defines the object type of the
 * condition variables and links each initialized condition variable to it.
 * condvar.c defines the object type @c obj_type_condvar. K_OBJ_TYPE_DEFINE()
 * puts one descriptor of this type into the iterable section
 * @c k_obj_core_desc. At boot, the object core code initializes the type
 * from the descriptor and links the condition variables that
 * K_CONDVAR_DEFINE() defines (the section @c k_condvar). k_condvar_init()
 * links each condition variable that it initializes.
 */

/**
 * @defgroup kernel_unit_condvar_k_condvar_init k_condvar_init()
 * @ingroup kernel_unit_condvar
 * @brief k_condvar_init() initializes the wait queue and the object data.
 *
 * k_condvar_init() initializes the wait queue, the kernel object (with
 * @kconfig{CONFIG_USERSPACE}) and the object core (with
 * @kconfig{CONFIG_OBJ_CORE_CONDVAR}). It does not lock: until
 * k_condvar_init() returns, only the caller uses the condition variable.
 * It has no error path.
 *
 * @par Functions in kernel/condvar.c
 * - z_impl_k_condvar_init()
 * - z_vrfy_k_condvar_init(), with @kconfig{CONFIG_USERSPACE}
 */

/**
 * @defgroup kernel_unit_condvar_k_condvar_signal k_condvar_signal()
 * @ingroup kernel_unit_condvar
 * @brief k_condvar_signal() wakes at most one waiting thread.
 *
 * k_condvar_signal() calls z_sched_wake() once, with the wait result 0 and
 * no data. If a thread waits, the scheduler makes it ready, and its
 * k_condvar_wait() returns 0. If no thread waits, the signal has no effect:
 * the condition variable does not remember it.
 *
 * @par Functions in kernel/condvar.c
 * - z_impl_k_condvar_signal()
 * - z_vrfy_k_condvar_signal(), with @kconfig{CONFIG_USERSPACE}
 */

/**
 * @defgroup kernel_unit_condvar_k_condvar_broadcast k_condvar_broadcast()
 * @ingroup kernel_unit_condvar
 * @brief k_condvar_broadcast() wakes all waiting threads and returns their number.
 *
 * k_condvar_broadcast() calls z_sched_wake() until it returns false. Each
 * call has the wait result 0 and no data. The return value is the number of
 * calls that returned true.
 *
 * @par Functions in kernel/condvar.c
 * - z_impl_k_condvar_broadcast()
 * - z_vrfy_k_condvar_broadcast(), with @kconfig{CONFIG_USERSPACE}
 */

/**
 * @defgroup kernel_unit_condvar_k_condvar_wait k_condvar_wait()
 * @ingroup kernel_unit_condvar
 * @brief k_condvar_wait() releases the mutex, waits, and locks the mutex again.
 *
 * The caller holds the mutex. k_condvar_wait() releases it, waits on the
 * wait queue with the timeout of the caller, and locks the mutex again
 * with K_FOREVER. It returns the result of z_pend_curr() without a change.
 * With K_NO_WAIT, it does nothing and returns -EAGAIN: the caller keeps
 * the mutex. For the order of the steps, see "Wait protocol" below.
 *
 * condvar.c has no check that k_condvar_wait() runs in a thread. In an ISR,
 * a wait reaches z_pend_curr(), and the scheduler refuses it with a panic
 * in every build. At this time, k_condvar_wait() has already released the
 * mutex.
 *
 * @par Wait protocol (no lost wake-up)
 * k_condvar_wait() releases the mutex and starts the wait as one step for
 * the other threads.
 * k_condvar_wait() locks @c condvar_lock, releases the mutex, and hands the
 * lock to z_pend_curr(). It does not release @c condvar_lock between
 * k_mutex_unlock() and z_pend_curr(). A thread that gets the mutex after
 * the release must lock @c condvar_lock to signal. It gets the lock only
 * after z_pend_curr() has put the waiting thread into the wait queue. Thus
 * the signal finds the waiting thread. After the wait, k_mutex_lock() runs
 * without @c condvar_lock, because it can block.
 *
 * @par Functions in kernel/condvar.c
 * - z_impl_k_condvar_wait()
 * - z_vrfy_k_condvar_wait(), with @kconfig{CONFIG_USERSPACE}
 */

/**
 * @defgroup kernel_unit_condvar_static Static functions and data
 * @ingroup kernel_unit_condvar
 * @brief The static functions of condvar.c, and the data that condvar.c defines.
 *
 * @par Functions in kernel/condvar.c
 * condvar.c has no static functions.
 *
 * @par Data in kernel/condvar.c
 * - @c obj_type_condvar and its descriptor (K_OBJ_TYPE_DEFINE()), with
 *   @kconfig{CONFIG_OBJ_CORE_CONDVAR}. The tests of the descriptor are in
 *   this group.
 */

#include <string.h>
#include <zephyr/ztest.h>
#include <kernel_unit.h>
#include <kernel_unit_models.h>
#include <fakes/mutex.h>
#ifdef CONFIG_OBJ_CORE
#include <fakes/obj_core.h>
#endif
#ifdef CONFIG_USERSPACE
#include <fakes/kobject.h>
#endif

#include <kernel/condvar.c>

/* Value that fills an object before a test, to show what the unit writes. */
#define FILL KERNEL_UNIT_FILL

/* Timeout that is not K_NO_WAIT and not K_FOREVER */
#define TEST_TIMEOUT K_TICKS(10)

/* Wait result that is not 0 and not -EAGAIN, to show that it passes unchanged. */
#define OTHER_RESULT (-EINTR)

/* The condition variable and the mutex of the tests. */
static struct k_condvar cv;
static struct k_mutex mutex;

/*
 * Lock model (kernel_unit_models.h): kernel_unit_lock.depth is the number of
 * holds of condvar_lock. An action of another thread waits until the lock is
 * free.
 */

/* Mutex model: true if the current thread holds the mutex. */
static bool mutex_held;

/* An action of another thread that waits for the mutex. */
static void (*mutex_waiter)(void);

/*
 * Wait queue model: the number of waiting threads, the current thread
 * included. If the current thread waits, current_pos threads are before it.
 */
static unsigned int waiting_threads;
static bool current_waits;
static unsigned int current_pos;
static bool current_woken;
static int current_result;

/* What the models saw at the time of a call. */
struct observation {
	unsigned int calls;
	int lock_depth;
	bool mutex_held;
	unsigned int waiting_threads;
};

static struct observation at_pend;
static struct observation at_mutex_unlock;
static struct observation at_mutex_lock;
static struct observation at_wake;

static void observe(struct observation *obs)
{
	obs->calls++;
	obs->lock_depth = kernel_unit_lock.depth;
	obs->mutex_held = mutex_held;
	obs->waiting_threads = waiting_threads;
}

/*
 * Fake z_sched_wake() with the wait queue model: record what the models see
 * (at_wake). If no thread waits, return false. Else the first thread of the
 * wait queue wakes with swap_retval, and the fake returns true. If this thread
 * is the current thread, swap_retval becomes the result of its wait.
 * Assumption: the wait queue is in FIFO order (all waiting threads have the
 * same priority), and the waiting threads are the threads of the model only.
 */
static bool wake_model(_wait_q_t *wait_q, int swap_retval, void *swap_data)
{
	ARG_UNUSED(wait_q);
	ARG_UNUSED(swap_data);

	observe(&at_wake);

	if (waiting_threads == 0U) {
		return false;
	}
	waiting_threads--;

	if (current_waits) {
		if (current_pos == 0U) {
			current_waits = false;
			current_woken = true;
			current_result = swap_retval;
		} else {
			current_pos--;
		}
	}

	return true;
}

/*
 * The scheduler adds the current thread to the end of the wait queue and
 * releases the lock. Other threads run. If none of them wakes the current
 * thread, the wait ends as a timeout.
 */
static int pend_model(struct k_spinlock *lock, k_spinlock_key_t key, _wait_q_t *wait_q,
		      k_timeout_t timeout)
{
	ARG_UNUSED(lock);
	ARG_UNUSED(key);
	ARG_UNUSED(wait_q);
	ARG_UNUSED(timeout);

	observe(&at_pend);

	current_pos = waiting_threads;
	waiting_threads++;
	current_waits = true;
	current_woken = false;

	kernel_unit_lock_released();

	if (current_woken) {
		return current_result;
	}

	current_waits = false;
	waiting_threads--;

	return -EAGAIN;
}

/*
 * Fake k_mutex_unlock() with the mutex model: record what the models see
 * (at_mutex_unlock), and set the mutex to free. If an action of another thread
 * waits for the mutex (mutex_waiter), it runs when the lock model is free.
 * Return k_mutex_unlock_fake.return_val. Assumption: the current thread holds
 * the mutex. The fake does not examine the owner and does not switch threads.
 */
static int mutex_unlock_model(struct k_mutex *m)
{
	ARG_UNUSED(m);

	observe(&at_mutex_unlock);
	mutex_held = false;

	if (mutex_waiter != NULL) {
		void (*action)(void) = mutex_waiter;

		mutex_waiter = NULL;
		kernel_unit_run_when_free(action);
	}

	return k_mutex_unlock_fake.return_val;
}

/*
 * Fake k_mutex_lock() with the mutex model: record what the models see
 * (at_mutex_lock), and set the mutex to held by the current thread. Return
 * k_mutex_lock_fake.return_val. Assumption: the mutex is free, thus the call
 * does not wait. The fake sets the mutex to held also for a return value
 * that is not 0.
 */
static int mutex_lock_model(struct k_mutex *m, k_timeout_t timeout)
{
	ARG_UNUSED(m);
	ARG_UNUSED(timeout);

	observe(&at_mutex_lock);
	mutex_held = true;

	return k_mutex_lock_fake.return_val;
}

/* Let n other threads wait on the condition variable. */
static void set_waiting_threads(unsigned int n)
{
	waiting_threads = n;
}

/* Actions of another thread */
static void other_thread_signals(void)
{
	zassert_equal(z_impl_k_condvar_signal(&cv), 0);
}

static int broadcast_result;

static void other_thread_broadcasts(void)
{
	broadcast_result = z_impl_k_condvar_broadcast(&cv);
}

/* Install the models. */
static void install_models(void)
{
	kernel_unit_lock_model_install();
	z_sched_wake_fake.custom_fake = wake_model;
	z_pend_curr_fake.custom_fake = pend_model;
	k_mutex_unlock_fake.custom_fake = mutex_unlock_model;
	k_mutex_lock_fake.custom_fake = mutex_lock_model;
}

/*
 * Assert the lock invariant of one operation (kernel_unit_models.h) on
 * condvar_lock. After z_pend_curr(), the only call is k_mutex_lock(). At the
 * end, the lock model has no hold of condvar_lock.
 */
static void assert_lock_released_once(enum kernel_unit_release how)
{
	kernel_unit_assert_lock_rule(&(const struct kernel_unit_lock_rule){
		.lock = &condvar_lock, .how = how, .after_pend = KERNEL_UNIT_FN(k_mutex_lock)});
	zassert_equal(kernel_unit_lock.depth, 0, "condvar_lock is still held");
}

static void condvar_unit_before(void *fixture)
{
	ARG_UNUSED(fixture);

	/* The fake rules reset all fakes before this function. */
	unit_arch_irq_lock_fake.return_val = KERNEL_UNIT_IRQ_KEY;
	install_models();

	memset(&cv, 0, sizeof(cv));
	memset(&mutex, 0, sizeof(mutex));
	mutex_held = true;
	mutex_waiter = NULL;
	waiting_threads = 0U;
	current_waits = false;
	current_pos = 0U;
	current_woken = false;
	current_result = 0;
	broadcast_result = -1;
	memset(&at_pend, 0, sizeof(at_pend));
	memset(&at_mutex_unlock, 0, sizeof(at_mutex_unlock));
	memset(&at_mutex_lock, 0, sizeof(at_mutex_lock));
	memset(&at_wake, 0, sizeof(at_wake));
}

ZTEST_SUITE(condvar_unit, NULL, NULL, condvar_unit_before, NULL, NULL);

/*
 * Tests: Initialization. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_condvar, at the top of this file.
 */

/**
 * @brief k_condvar_init() initializes the wait queue of the condition variable.
 *
 * @details
 * - Setup: a condition variable filled with a pattern.
 * - Action: z_impl_k_condvar_init().
 * - Expected: one call of z_waitq_init() with the wait queue of the
 *   condition variable.
 *
 * @ingroup kernel_unit_condvar_k_condvar_init
 * @see z_impl_k_condvar_init()
 */
ZTEST(condvar_unit, test_init_initializes_wait_queue)
{
	memset(&cv, FILL, sizeof(cv));

	(void)z_impl_k_condvar_init(&cv);

	zassert_equal(z_waitq_init_fake.call_count, 1);
	zassert_equal_ptr(z_waitq_init_fake.arg0_val, &cv.wait_q);
}

/**
 * @brief k_condvar_init() returns 0.
 *
 * @details
 * - Action: z_impl_k_condvar_init().
 * - Expected: return value 0.
 *
 * @ingroup kernel_unit_condvar_k_condvar_init
 * @see z_impl_k_condvar_init()
 */
ZTEST(condvar_unit, test_init_returns_zero)
{
	zassert_equal(z_impl_k_condvar_init(&cv), 0);
}

#ifdef CONFIG_USERSPACE
/**
 * @brief With CONFIG_USERSPACE, k_condvar_init() marks the condition variable as an initialized
 * kernel object.
 *
 * @details
 * - Action: z_impl_k_condvar_init().
 * - Expected: one call of k_object_init() with the condition variable.
 *
 * @ingroup kernel_unit_condvar_k_condvar_init
 * @see z_impl_k_condvar_init()
 */
ZTEST(condvar_unit, test_init_initializes_kernel_object)
{
	(void)z_impl_k_condvar_init(&cv);

	zassert_equal(k_object_init_fake.call_count, 1);
	zassert_equal_ptr(k_object_init_fake.arg0_val, &cv);
}
#endif /* CONFIG_USERSPACE */

/**
 * @brief k_condvar_init() initializes the wait queue, then the kernel object, then the object
 * core, and calls nothing else.
 *
 * @details
 * - Action: z_impl_k_condvar_init().
 * - Expected calls, in this order: z_waitq_init(), k_object_init() (with
 *   CONFIG_USERSPACE), k_obj_core_init_and_link() (with
 *   CONFIG_OBJ_CORE_CONDVAR). No lock, no call to the scheduler or to a
 *   mutex.
 *
 * @ingroup kernel_unit_condvar_k_condvar_init
 * @see z_impl_k_condvar_init()
 */
ZTEST(condvar_unit, test_init_call_order)
{
	(void)z_impl_k_condvar_init(&cv);

	zassert_call_history(
		z_waitq_init, KERNEL_UNIT_IF_ENABLED(CONFIG_USERSPACE, k_object_init),
		KERNEL_UNIT_IF_ENABLED(CONFIG_OBJ_CORE_CONDVAR, k_obj_core_init_and_link));
}

/*
 * Tests: Signal. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_condvar, at the top of this file.
 */

/**
 * @brief If no thread waits, k_condvar_signal() wakes no thread and returns 0.
 *
 * @details
 * - Setup: no thread waits.
 * - Action: z_impl_k_condvar_signal().
 * - Expected: return value 0. One call of z_sched_wake() with the wait
 *   queue of the condition variable, and it returns false.
 *
 * @ingroup kernel_unit_condvar_k_condvar_signal
 * @see z_impl_k_condvar_signal()
 */
ZTEST(condvar_unit, test_signal_no_waiter_returns_zero)
{
	zassert_equal(z_impl_k_condvar_signal(&cv), 0);

	zassert_equal(z_sched_wake_fake.call_count, 1);
	zassert_equal_ptr(z_sched_wake_fake.arg0_val, &cv.wait_q);
	zassert_false(z_sched_wake_fake.return_val_history[0]);
}

/**
 * @brief If a thread waits, k_condvar_signal() wakes it with the wait result 0 and no data, and
 * returns 0.
 *
 * @details
 * - Setup: one thread waits.
 * - Action: z_impl_k_condvar_signal().
 * - Expected: return value 0. One call of z_sched_wake() with the wait
 *   queue, the wait result 0 and the data NULL. No thread waits after the
 *   call.
 *
 * @ingroup kernel_unit_condvar_k_condvar_signal
 * @see z_impl_k_condvar_signal()
 */
ZTEST(condvar_unit, test_signal_wakes_waiter_with_result_zero)
{
	set_waiting_threads(1);

	zassert_equal(z_impl_k_condvar_signal(&cv), 0);

	zassert_equal(z_sched_wake_fake.call_count, 1);
	zassert_equal_ptr(z_sched_wake_fake.arg0_val, &cv.wait_q);
	zassert_equal(z_sched_wake_fake.arg1_val, 0);
	zassert_is_null(z_sched_wake_fake.arg2_val);
	zassert_equal(waiting_threads, 0U);
}

/**
 * @brief k_condvar_signal() wakes at most one thread.
 *
 * @details
 * - Setup: three threads wait.
 * - Action: z_impl_k_condvar_signal().
 * - Expected: one call of z_sched_wake(). Two threads still wait.
 *
 * @ingroup kernel_unit_condvar_k_condvar_signal
 * @see z_impl_k_condvar_signal()
 */
ZTEST(condvar_unit, test_signal_wakes_one_thread_only)
{
	set_waiting_threads(3);

	zassert_equal(z_impl_k_condvar_signal(&cv), 0);

	zassert_equal(z_sched_wake_fake.call_count, 1);
	zassert_equal(waiting_threads, 2U);
}

/**
 * @brief A signal with no waiting thread has no effect on a later k_condvar_wait(): the condition
 * variable does not remember signals.
 *
 * @details
 * - Setup: no thread waits. The mutex is held.
 * - Action: z_impl_k_condvar_signal(), then z_impl_k_condvar_wait() with a
 *   timeout. No other thread signals during the wait.
 * - Expected: the wait calls z_pend_curr(), and it returns -EAGAIN (the
 *   timeout).
 *
 * @ingroup kernel_unit_condvar_k_condvar_signal
 * @see z_impl_k_condvar_signal(), z_impl_k_condvar_wait()
 */
ZTEST(condvar_unit, test_signal_without_waiter_is_not_remembered)
{
	zassert_equal(z_impl_k_condvar_signal(&cv), 0);

	zassert_equal(z_impl_k_condvar_wait(&cv, &mutex, TEST_TIMEOUT), -EAGAIN);

	zassert_equal(z_pend_curr_fake.call_count, 1);
}

/*
 * Tests: Broadcast. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_condvar, at the top of this file.
 */

/**
 * @brief If no thread waits, k_condvar_broadcast() returns 0.
 *
 * @details
 * - Setup: no thread waits.
 * - Action: z_impl_k_condvar_broadcast().
 * - Expected: return value 0. One call of z_sched_wake() with the wait
 *   queue of the condition variable.
 *
 * @ingroup kernel_unit_condvar_k_condvar_broadcast
 * @see z_impl_k_condvar_broadcast()
 */
ZTEST(condvar_unit, test_broadcast_no_waiter_returns_zero)
{
	zassert_equal(z_impl_k_condvar_broadcast(&cv), 0);

	zassert_equal(z_sched_wake_fake.call_count, 1);
	zassert_equal_ptr(z_sched_wake_fake.arg0_val, &cv.wait_q);
}

/**
 * @brief k_condvar_broadcast() wakes all waiting threads, each with the wait result 0 and no data.
 *
 * @details
 * - Setup: three threads wait.
 * - Action: z_impl_k_condvar_broadcast().
 * - Expected: four calls of z_sched_wake(), each with the wait queue, the
 *   wait result 0 and the data NULL. The last call returns false. No
 *   thread waits after the call.
 *
 * @ingroup kernel_unit_condvar_k_condvar_broadcast
 * @see z_impl_k_condvar_broadcast()
 */
ZTEST(condvar_unit, test_broadcast_wakes_all_threads)
{
	set_waiting_threads(3);

	(void)z_impl_k_condvar_broadcast(&cv);

	zassert_equal(z_sched_wake_fake.call_count, 4);
	for (unsigned int i = 0; i < 4U; i++) {
		zassert_equal_ptr(z_sched_wake_fake.arg0_history[i], &cv.wait_q);
		zassert_equal(z_sched_wake_fake.arg1_history[i], 0);
		zassert_is_null(z_sched_wake_fake.arg2_history[i]);
	}
	zassert_false(z_sched_wake_fake.return_val_history[3]);
	zassert_equal(waiting_threads, 0U);
}

/**
 * @brief k_condvar_broadcast() returns the number of threads that it woke.
 *
 * @details
 * - Setup: n threads wait, for n = 1, 2 and 7.
 * - Action: z_impl_k_condvar_broadcast() for each n.
 * - Expected: return value n.
 *
 * @ingroup kernel_unit_condvar_k_condvar_broadcast
 * @see z_impl_k_condvar_broadcast()
 */
ZTEST(condvar_unit, test_broadcast_returns_number_of_woken_threads)
{
	const unsigned int counts[] = {1U, 2U, 7U};

	ARRAY_FOR_EACH(counts, i) {
		set_waiting_threads(counts[i]);

		zassert_equal(z_impl_k_condvar_broadcast(&cv), (int)counts[i]);
	}
}

/*
 * Tests: Wait. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_condvar, at the top of this file.
 */

/**
 * @brief With K_NO_WAIT, k_condvar_wait() returns -EAGAIN and calls nothing.
 *
 * @details
 * - Setup: the mutex is held.
 * - Action: z_impl_k_condvar_wait() with K_NO_WAIT.
 * - Expected: return value -EAGAIN. The call history is empty: no lock, no
 *   mutex call, no wait.
 *
 * @ingroup kernel_unit_condvar_k_condvar_wait
 * @see z_impl_k_condvar_wait()
 */
ZTEST(condvar_unit, test_wait_no_wait_returns_eagain)
{
	zassert_equal(z_impl_k_condvar_wait(&cv, &mutex, K_NO_WAIT), -EAGAIN);

	zassert_equal(kernel_unit_history_len(), 0U);
}

/**
 * @brief With K_NO_WAIT, the caller of k_condvar_wait() keeps the mutex.
 *
 * @details
 * - Setup: the mutex is held.
 * - Action: z_impl_k_condvar_wait() with K_NO_WAIT.
 * - Expected: no call of k_mutex_unlock() and of k_mutex_lock(). The mutex
 *   is held.
 *
 * @ingroup kernel_unit_condvar_k_condvar_wait
 * @see z_impl_k_condvar_wait()
 */
ZTEST(condvar_unit, test_wait_no_wait_keeps_mutex)
{
	(void)z_impl_k_condvar_wait(&cv, &mutex, K_NO_WAIT);

	zassert_equal(k_mutex_unlock_fake.call_count, 0);
	zassert_equal(k_mutex_lock_fake.call_count, 0);
	zassert_true(mutex_held);
}

/**
 * @brief k_condvar_wait() waits on the wait queue of the condition variable with the timeout of
 * the caller.
 *
 * @details
 * - Action: z_impl_k_condvar_wait() with TEST_TIMEOUT, then with
 *   K_FOREVER.
 * - Expected: two calls of z_pend_curr(), each with the wait queue of the
 *   condition variable, the first with TEST_TIMEOUT, the second with
 *   K_FOREVER.
 *
 * @ingroup kernel_unit_condvar_k_condvar_wait
 * @see z_impl_k_condvar_wait()
 */
ZTEST(condvar_unit, test_wait_pends_with_timeout)
{
	(void)z_impl_k_condvar_wait(&cv, &mutex, TEST_TIMEOUT);
	(void)z_impl_k_condvar_wait(&cv, &mutex, K_FOREVER);

	zassert_equal(z_pend_curr_fake.call_count, 2);
	zassert_equal_ptr(z_pend_curr_fake.arg2_history[0], &cv.wait_q);
	zassert_true(K_TIMEOUT_EQ(z_pend_curr_fake.arg3_history[0], TEST_TIMEOUT));
	zassert_equal_ptr(z_pend_curr_fake.arg2_history[1], &cv.wait_q);
	zassert_true(K_TIMEOUT_EQ(z_pend_curr_fake.arg3_history[1], K_FOREVER));
}

/**
 * @brief k_condvar_wait() releases the mutex of the caller before it waits.
 *
 * @details
 * - Setup: the mutex is held.
 * - Action: z_impl_k_condvar_wait() with TEST_TIMEOUT.
 * - Expected: one call of k_mutex_unlock() with the mutex, before
 *   z_pend_curr(). At z_pend_curr(), the mutex is not held.
 *
 * @ingroup kernel_unit_condvar_k_condvar_wait
 * @see z_impl_k_condvar_wait()
 */
ZTEST(condvar_unit, test_wait_releases_mutex_before_wait)
{
	(void)z_impl_k_condvar_wait(&cv, &mutex, TEST_TIMEOUT);

	zassert_equal(k_mutex_unlock_fake.call_count, 1);
	zassert_equal_ptr(k_mutex_unlock_fake.arg0_val, &mutex);
	zassert_called_before(k_mutex_unlock, z_pend_curr);
	zassert_equal(at_pend.calls, 1U);
	zassert_false(at_pend.mutex_held);
}

/**
 * @brief In an ISR, k_condvar_wait() with a timeout reaches z_pend_curr(), and the scheduler
 * refuses it with a panic. condvar.c has no earlier check.
 *
 * @details
 * The real z_pend_curr() refuses a call from an ISR in every build, before
 * it changes a thread or a wait queue, and does not return.
 * zassert_stopped_by_panic() stops the unit at the panic. Thus the test
 * shows the state at the panic.
 * - Setup: the mutex is held. arch_is_in_isr() returns true. The test
 *   expects the refusal of z_pend_curr().
 * - Action: z_impl_k_condvar_wait() with K_FOREVER.
 * - Expected: one call of z_pend_curr() with @c condvar_lock. The scheduler
 *   refuses it with a failed assertion (with CONFIG_ASSERT, the only one) and
 *   a panic. The wait queue model does not run, and no thread waits.
 *   @c condvar_lock stays locked. Before the call, k_condvar_wait() released
 *   the mutex. There is no k_mutex_lock() after the panic.
 *
 * @ingroup kernel_unit_condvar_k_condvar_wait
 * @see z_impl_k_condvar_wait()
 */
ZTEST(condvar_unit, test_wait_in_isr_refused_by_scheduler)
{
	arch_is_in_isr_fake.return_val = true;
	kernel_unit_expect_pend_refusal();

	zassert_stopped_by_panic(z_impl_k_condvar_wait(&cv, &mutex, K_FOREVER));

	kernel_unit_assert_pend_refused();
	zassert_equal(z_pend_curr_fake.call_count, 1);
	zassert_equal_ptr(z_pend_curr_fake.arg0_val, &condvar_lock);
	zassert_equal(at_pend.calls, 0U, "the wait queue model ran");
	zassert_equal(waiting_threads, 0U);
	zassert_equal(kernel_unit_lock.depth, 1, "condvar_lock was released");
	zassert_equal(k_mutex_unlock_fake.call_count, 1);
	zassert_false(mutex_held);
	zassert_equal(k_mutex_lock_fake.call_count, 0);
#ifdef CONFIG_ASSERT
	zassert_equal(assert_post_action_fake.call_count, 1);
#endif
}

/**
 * @brief After a wake, k_condvar_wait() locks the mutex again and returns 0.
 *
 * @details
 * - Setup: the mutex is held. Another thread signals while the current
 *   thread waits.
 * - Action: z_impl_k_condvar_wait() with K_FOREVER.
 * - Expected: return value 0. One call of k_mutex_lock() with the mutex and
 *   K_FOREVER, after z_pend_curr(). The mutex is held.
 *
 * @ingroup kernel_unit_condvar_k_condvar_wait
 * @see z_impl_k_condvar_wait()
 */
ZTEST(condvar_unit, test_wait_relocks_mutex_after_wake)
{
	kernel_unit_run_at_next_release(other_thread_signals);

	zassert_equal(z_impl_k_condvar_wait(&cv, &mutex, K_FOREVER), 0);

	zassert_equal(k_mutex_lock_fake.call_count, 1);
	zassert_equal_ptr(k_mutex_lock_fake.arg0_val, &mutex);
	zassert_true(K_TIMEOUT_EQ(k_mutex_lock_fake.arg1_val, K_FOREVER));
	zassert_called_before(z_pend_curr, k_mutex_lock);
	zassert_true(mutex_held);
}

/**
 * @brief After a timeout, k_condvar_wait() also locks the mutex again and returns -EAGAIN.
 *
 * @details
 * - Setup: the mutex is held. No thread signals.
 * - Action: z_impl_k_condvar_wait() with TEST_TIMEOUT.
 * - Expected: return value -EAGAIN. One call of k_mutex_lock() with the
 *   mutex, after z_pend_curr(). The mutex is held.
 *
 * @ingroup kernel_unit_condvar_k_condvar_wait
 * @see z_impl_k_condvar_wait()
 */
ZTEST(condvar_unit, test_wait_relocks_mutex_after_timeout)
{
	zassert_equal(z_impl_k_condvar_wait(&cv, &mutex, TEST_TIMEOUT), -EAGAIN);

	zassert_equal(k_mutex_lock_fake.call_count, 1);
	zassert_equal_ptr(k_mutex_lock_fake.arg0_val, &mutex);
	zassert_called_before(z_pend_curr, k_mutex_lock);
	zassert_true(mutex_held);
}

/**
 * @brief The timeout of k_condvar_wait() applies only to the wait on the condition variable: the
 * mutex lock after the wait uses K_FOREVER.
 *
 * @details
 * - Action: z_impl_k_condvar_wait() with TEST_TIMEOUT.
 * - Expected: z_pend_curr() gets TEST_TIMEOUT. k_mutex_lock() gets
 *   K_FOREVER.
 *
 * @ingroup kernel_unit_condvar_k_condvar_wait
 * @see z_impl_k_condvar_wait()
 */
ZTEST(condvar_unit, test_wait_timeout_does_not_limit_mutex_lock)
{
	(void)z_impl_k_condvar_wait(&cv, &mutex, TEST_TIMEOUT);

	zassert_true(K_TIMEOUT_EQ(z_pend_curr_fake.arg3_val, TEST_TIMEOUT));
	zassert_true(K_TIMEOUT_EQ(k_mutex_lock_fake.arg1_val, K_FOREVER));
}

/**
 * @brief k_condvar_wait() returns the result of z_pend_curr() without a change.
 *
 * @details
 * - Setup: z_pend_curr() returns 0, then -EAGAIN, then another error code
 *   (no model).
 * - Action: z_impl_k_condvar_wait() with K_FOREVER for each result.
 * - Expected: the return value is the result of z_pend_curr() each time.
 *
 * @ingroup kernel_unit_condvar_k_condvar_wait
 * @see z_impl_k_condvar_wait()
 */
ZTEST(condvar_unit, test_wait_returns_wait_result)
{
	const int results[] = {0, -EAGAIN, OTHER_RESULT};

	z_pend_curr_fake.custom_fake = NULL;

	ARRAY_FOR_EACH(results, i) {
		z_pend_curr_fake.return_val = results[i];

		zassert_equal(z_impl_k_condvar_wait(&cv, &mutex, K_FOREVER), results[i]);
	}
}

/**
 * @brief k_condvar_wait() ignores the result of k_mutex_unlock(): it waits also if the release of
 * the mutex fails.
 *
 * @details
 * - Setup: k_mutex_unlock() returns -EPERM (the caller does not hold the
 *   mutex). No thread signals.
 * - Action: z_impl_k_condvar_wait() with TEST_TIMEOUT.
 * - Expected: z_pend_curr() and k_mutex_lock() are called. The return
 *   value is the wait result -EAGAIN, not -EPERM.
 *
 * @ingroup kernel_unit_condvar_k_condvar_wait
 * @see z_impl_k_condvar_wait()
 */
ZTEST(condvar_unit, test_wait_ignores_mutex_unlock_result)
{
	k_mutex_unlock_fake.return_val = -EPERM;

	zassert_equal(z_impl_k_condvar_wait(&cv, &mutex, TEST_TIMEOUT), -EAGAIN);

	zassert_equal(z_pend_curr_fake.call_count, 1);
	zassert_equal(k_mutex_lock_fake.call_count, 1);
}

/**
 * @brief k_condvar_wait() ignores the result of k_mutex_lock() and returns the wait result.
 *
 * @details
 * - Setup: k_mutex_lock() returns -EINVAL. Another thread signals while
 *   the current thread waits.
 * - Action: z_impl_k_condvar_wait() with K_FOREVER.
 * - Expected: return value 0, the result of the wait.
 *
 * @ingroup kernel_unit_condvar_k_condvar_wait
 * @see z_impl_k_condvar_wait()
 */
ZTEST(condvar_unit, test_wait_ignores_mutex_lock_result)
{
	k_mutex_lock_fake.return_val = -EINVAL;
	kernel_unit_run_at_next_release(other_thread_signals);

	zassert_equal(z_impl_k_condvar_wait(&cv, &mutex, K_FOREVER), 0);
}

/**
 * @brief A k_condvar_broadcast() of another thread wakes the waiting thread together with the other
 * waiting threads.
 *
 * @details
 * - Setup: two other threads wait. Another thread broadcasts while the
 *   current thread waits.
 * - Action: z_impl_k_condvar_wait() with K_FOREVER.
 * - Expected: return value 0. The broadcast returns 3. No thread waits.
 *
 * @ingroup kernel_unit_condvar_k_condvar_wait
 * @see z_impl_k_condvar_wait(), z_impl_k_condvar_broadcast()
 */
ZTEST(condvar_unit, test_wait_woken_by_broadcast)
{
	set_waiting_threads(2);
	kernel_unit_run_at_next_release(other_thread_broadcasts);

	zassert_equal(z_impl_k_condvar_wait(&cv, &mutex, K_FOREVER), 0);

	zassert_equal(broadcast_result, 3);
	zassert_equal(waiting_threads, 0U);
}

/**
 * @brief A k_condvar_signal() wakes the threads in the order of the wait queue: a thread that
 * waits behind another thread needs a second signal.
 *
 * @details
 * - Setup: one other thread waits. Another thread signals once while the
 *   current thread waits.
 * - Action: z_impl_k_condvar_wait() with TEST_TIMEOUT.
 * - Expected: return value -EAGAIN (the model ends the wait as a timeout).
 *   The signal woke the other thread. The scheduler sets the order of the
 *   wait queue (priority, then time of arrival); condvar.c does not change
 *   it.
 *
 * @ingroup kernel_unit_condvar_k_condvar_wait
 * @see z_impl_k_condvar_wait(), z_impl_k_condvar_signal()
 */
ZTEST(condvar_unit, test_wait_signal_wakes_first_waiter)
{
	set_waiting_threads(1);
	kernel_unit_run_at_next_release(other_thread_signals);

	zassert_equal(z_impl_k_condvar_wait(&cv, &mutex, TEST_TIMEOUT), -EAGAIN);

	zassert_equal(z_sched_wake_fake.call_count, 1);
	zassert_true(z_sched_wake_fake.return_val_history[0]);
}

/*
 * Tests: Wait protocol (no lost wake-up). Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_condvar, at the top of this file.
 */

/**
 * @brief k_condvar_wait() locks condvar_lock before it releases the mutex.
 *
 * @details
 * - Setup: the mutex is held.
 * - Action: z_impl_k_condvar_wait() with TEST_TIMEOUT.
 * - Expected: arch_irq_lock() comes before k_mutex_unlock(). At
 *   k_mutex_unlock(), condvar_lock is held.
 *
 * @ingroup kernel_unit_condvar_k_condvar_wait
 * @see z_impl_k_condvar_wait()
 */
ZTEST(condvar_unit, test_protocol_lock_before_mutex_unlock)
{
	(void)z_impl_k_condvar_wait(&cv, &mutex, TEST_TIMEOUT);

	zassert_called_before(unit_arch_irq_lock, k_mutex_unlock);
	zassert_equal(at_mutex_unlock.calls, 1U);
	zassert_equal(at_mutex_unlock.lock_depth, 1);
}

/**
 * @brief k_condvar_wait() holds condvar_lock from the release of the mutex until z_pend_curr().
 *
 * @details
 * - Setup: the mutex is held.
 * - Action: z_impl_k_condvar_wait() with TEST_TIMEOUT.
 * - Expected calls, in this order: arch_irq_lock(), k_mutex_unlock(),
 *   z_pend_curr(), k_mutex_lock(). At z_pend_curr(), condvar_lock is held
 *   and the mutex is not held. No release of condvar_lock comes between
 *   k_mutex_unlock() and z_pend_curr().
 *
 * @ingroup kernel_unit_condvar_k_condvar_wait
 * @see z_impl_k_condvar_wait()
 */
ZTEST(condvar_unit, test_protocol_no_release_between_unlock_and_pend)
{
	(void)z_impl_k_condvar_wait(&cv, &mutex, TEST_TIMEOUT);

	zassert_call_history(unit_arch_irq_lock, k_mutex_unlock, z_pend_curr, k_mutex_lock);
	zassert_equal(at_pend.lock_depth, 1);
	zassert_false(at_pend.mutex_held);
}

/**
 * @brief A thread that gets the mutex from k_condvar_wait() and signals at once wakes the waiting
 * thread: the signal is not lost.
 *
 * @details
 * - Setup: the mutex is held. Another thread waits for the mutex. When it
 *   gets the mutex, it calls k_condvar_signal(). It must lock
 *   condvar_lock for this; if the lock is held, it spins until the lock is
 *   free.
 * - Action: z_impl_k_condvar_wait() with TEST_TIMEOUT.
 * - Expected: the signal wakes the current thread, and the return value
 *   is 0 (not the timeout -EAGAIN). The signal found one waiting thread.
 *
 * @ingroup kernel_unit_condvar_k_condvar_wait
 * @see z_impl_k_condvar_wait(), z_impl_k_condvar_signal()
 */
ZTEST(condvar_unit, test_protocol_signal_after_mutex_unlock_is_not_lost)
{
	mutex_waiter = other_thread_signals;

	zassert_equal(z_impl_k_condvar_wait(&cv, &mutex, TEST_TIMEOUT), 0);

	zassert_equal(at_wake.calls, 1U);
	zassert_equal(at_wake.waiting_threads, 1U);
}

/**
 * @brief k_condvar_wait() locks the mutex again only after z_pend_curr() released condvar_lock.
 *
 * @details
 * - Setup: the mutex is held. Another thread signals while the current
 *   thread waits.
 * - Action: z_impl_k_condvar_wait() with K_FOREVER.
 * - Expected: at k_mutex_lock(), condvar_lock is not held. k_mutex_lock()
 *   can block, so it must not run with the interrupts locked.
 *
 * @ingroup kernel_unit_condvar_k_condvar_wait
 * @see z_impl_k_condvar_wait()
 */
ZTEST(condvar_unit, test_protocol_mutex_lock_without_condvar_lock)
{
	kernel_unit_run_at_next_release(other_thread_signals);

	(void)z_impl_k_condvar_wait(&cv, &mutex, K_FOREVER);

	zassert_equal(at_mutex_lock.calls, 1U);
	zassert_equal(at_mutex_lock.lock_depth, 0);
}

/*
 * Tests: Locking. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_condvar, at the top of this file.
 */

/**
 * @brief If k_condvar_signal() wakes no thread, it releases condvar_lock with k_spin_unlock().
 *
 * @details
 * - Setup: no thread waits.
 * - Action: z_impl_k_condvar_signal().
 * - Expected calls: arch_irq_lock(), z_sched_wake(), arch_irq_unlock()
 *   with the key.
 *
 * @ingroup kernel_unit_condvar_k_condvar_signal
 * @see z_impl_k_condvar_signal()
 */
ZTEST(condvar_unit, test_lock_signal_no_waiter_unlocks)
{
	(void)z_impl_k_condvar_signal(&cv);

	zassert_call_history(unit_arch_irq_lock, z_sched_wake, unit_arch_irq_unlock);
	assert_lock_released_once(KERNEL_UNIT_RELEASED_BY_UNLOCK);
}

/**
 * @brief If k_condvar_signal() wakes a thread, it releases condvar_lock with z_reschedule().
 *
 * @details
 * - Setup: one thread waits.
 * - Action: z_impl_k_condvar_signal().
 * - Expected calls: arch_irq_lock(), z_sched_wake(), z_reschedule() with
 *   condvar_lock and the key.
 *
 * @ingroup kernel_unit_condvar_k_condvar_signal
 * @see z_impl_k_condvar_signal()
 */
ZTEST(condvar_unit, test_lock_signal_wake_reschedules)
{
	set_waiting_threads(1);

	(void)z_impl_k_condvar_signal(&cv);

	zassert_call_history(unit_arch_irq_lock, z_sched_wake, z_reschedule);
	assert_lock_released_once(KERNEL_UNIT_RELEASED_BY_RESCHEDULE);
}

/**
 * @brief If k_condvar_broadcast() wakes no thread, it releases condvar_lock with k_spin_unlock().
 *
 * @details
 * - Setup: no thread waits.
 * - Action: z_impl_k_condvar_broadcast().
 * - Expected calls: arch_irq_lock(), z_sched_wake(), arch_irq_unlock()
 *   with the key.
 *
 * @ingroup kernel_unit_condvar_k_condvar_broadcast
 * @see z_impl_k_condvar_broadcast()
 */
ZTEST(condvar_unit, test_lock_broadcast_no_waiter_unlocks)
{
	(void)z_impl_k_condvar_broadcast(&cv);

	zassert_call_history(unit_arch_irq_lock, z_sched_wake, unit_arch_irq_unlock);
	assert_lock_released_once(KERNEL_UNIT_RELEASED_BY_UNLOCK);
}

/**
 * @brief If k_condvar_broadcast() wakes threads, it releases condvar_lock once with z_reschedule()
 * after the last wake.
 *
 * @details
 * - Setup: three threads wait.
 * - Action: z_impl_k_condvar_broadcast().
 * - Expected calls: arch_irq_lock(), four times z_sched_wake(),
 *   z_reschedule() with condvar_lock and the key.
 *
 * @ingroup kernel_unit_condvar_k_condvar_broadcast
 * @see z_impl_k_condvar_broadcast()
 */
ZTEST(condvar_unit, test_lock_broadcast_reschedules_once_after_last_wake)
{
	set_waiting_threads(3);

	(void)z_impl_k_condvar_broadcast(&cv);

	zassert_call_history(unit_arch_irq_lock, z_sched_wake, z_sched_wake, z_sched_wake,
			     z_sched_wake, z_reschedule);
	assert_lock_released_once(KERNEL_UNIT_RELEASED_BY_RESCHEDULE);
}

/**
 * @brief k_condvar_signal() and k_condvar_broadcast() call z_sched_wake() only while they hold
 * condvar_lock.
 *
 * @details
 * - Setup: two threads wait.
 * - Action: z_impl_k_condvar_signal(), then z_impl_k_condvar_broadcast().
 * - Expected: at each call of z_sched_wake(), condvar_lock is held.
 *
 * @ingroup kernel_unit_condvar_k_condvar_signal
 * @see z_impl_k_condvar_signal(), z_impl_k_condvar_broadcast()
 */
ZTEST(condvar_unit, test_lock_wake_under_lock)
{
	set_waiting_threads(2);

	(void)z_impl_k_condvar_signal(&cv);
	zassert_equal(at_wake.lock_depth, 1);

	at_wake.lock_depth = 0;
	(void)z_impl_k_condvar_broadcast(&cv);
	zassert_equal(at_wake.calls, 3U);
	zassert_equal(at_wake.lock_depth, 1);
}

/**
 * @brief If k_condvar_wait() waits, z_pend_curr() releases condvar_lock, and k_condvar_wait() does
 * not release it again.
 *
 * @details
 * - Setup: the mutex is held.
 * - Action: z_impl_k_condvar_wait() with TEST_TIMEOUT.
 * - Expected calls: arch_irq_lock(), k_mutex_unlock(), z_pend_curr() with
 *   condvar_lock and the key, k_mutex_lock(). No arch_irq_unlock().
 *
 * @ingroup kernel_unit_condvar_k_condvar_wait
 * @see z_impl_k_condvar_wait()
 */
ZTEST(condvar_unit, test_lock_wait_hands_lock_to_pend)
{
	(void)z_impl_k_condvar_wait(&cv, &mutex, TEST_TIMEOUT);

	zassert_call_history(unit_arch_irq_lock, k_mutex_unlock, z_pend_curr, k_mutex_lock);
	assert_lock_released_once(KERNEL_UNIT_RELEASED_BY_PEND);
}

/**
 * @brief All condition variables use the same lock, condvar_lock.
 *
 * @details
 * - Setup: two condition variables. One thread waits on each.
 * - Action: z_impl_k_condvar_signal() of each, then
 *   z_impl_k_condvar_wait() on the second one.
 * - Expected: both calls of z_reschedule() and the call of z_pend_curr()
 *   get the same lock, condvar_lock.
 *
 * @ingroup kernel_unit_condvar_k_condvar_signal
 * @see z_impl_k_condvar_signal(), z_impl_k_condvar_wait()
 */
ZTEST(condvar_unit, test_lock_one_lock_for_all_condvars)
{
	struct k_condvar cv2;

	memset(&cv2, 0, sizeof(cv2));
	set_waiting_threads(2);

	(void)z_impl_k_condvar_signal(&cv);
	(void)z_impl_k_condvar_signal(&cv2);
	(void)z_impl_k_condvar_wait(&cv2, &mutex, TEST_TIMEOUT);

	zassert_equal(z_reschedule_fake.call_count, 2);
	zassert_equal_ptr(z_reschedule_fake.arg0_history[0], &condvar_lock);
	zassert_equal_ptr(z_reschedule_fake.arg0_history[1], &condvar_lock);
	zassert_equal_ptr(z_pend_curr_fake.arg0_val, &condvar_lock);
}

/**
 * @brief k_condvar_init() does not lock condvar_lock.
 *
 * @details
 * - Action: z_impl_k_condvar_init().
 * - Expected: no call of arch_irq_lock().
 *
 * @ingroup kernel_unit_condvar_k_condvar_init
 * @see z_impl_k_condvar_init()
 */
ZTEST(condvar_unit, test_lock_not_used_by_init)
{
	(void)z_impl_k_condvar_init(&cv);

	zassert_equal(unit_arch_irq_lock_fake.call_count, 0);
}

#ifdef CONFIG_SPIN_VALIDATE
/**
 * @brief With CONFIG_SPIN_VALIDATE, the spinlock validation sees condvar_lock on lock and on
 * unlock.
 *
 * @details
 * - Setup: no thread waits.
 * - Action: z_impl_k_condvar_signal().
 * - Expected: one call of z_spin_lock_valid() and one call of
 *   z_spin_unlock_valid(), each with condvar_lock.
 *
 * @ingroup kernel_unit_condvar_k_condvar_signal
 * @see z_impl_k_condvar_signal()
 */
ZTEST(condvar_unit, test_lock_validation_sees_condvar_lock)
{
	(void)z_impl_k_condvar_signal(&cv);

	zassert_equal(z_spin_lock_valid_fake.call_count, 1);
	zassert_equal_ptr(z_spin_lock_valid_fake.arg0_val, &condvar_lock);
	zassert_equal(z_spin_unlock_valid_fake.call_count, 1);
	zassert_equal_ptr(z_spin_unlock_valid_fake.arg0_val, &condvar_lock);
}
#endif /* CONFIG_SPIN_VALIDATE */

#ifdef CONFIG_USERSPACE
/*
 * Tests: System call verification. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_condvar, at the top of this file.
 */

/* Make only the check of the condition variable object fail. */
static int fail_condvar_check(struct k_object *ko, const void *obj, enum k_objects otype,
			      enum _obj_init_check init)
{
	ARG_UNUSED(ko);
	ARG_UNUSED(obj);
	ARG_UNUSED(init);

	return (otype == K_OBJ_CONDVAR) ? -EBADF : 0;
}

/* Make only the check of the mutex object fail. */
static int fail_mutex_check(struct k_object *ko, const void *obj, enum k_objects otype,
			    enum _obj_init_check init)
{
	ARG_UNUSED(ko);
	ARG_UNUSED(obj);
	ARG_UNUSED(init);

	return (otype == K_OBJ_MUTEX) ? -EBADF : 0;
}

/* Assert one object check of the condition variable, and no oops. */
static void assert_object_check(enum _obj_init_check init)
{
	kernel_unit_assert_object_check(&cv, K_OBJ_CONDVAR, init);
}

/* Assert one oops, before the first call of fn (the first change of an object). */
#define zassert_oops_before(fn)                                                                    \
	do {                                                                                       \
		zassert_equal(unit_syscall_oops_fake.call_count, 1);                               \
		zassert_called_before(unit_syscall_oops, fn);                                      \
	} while (false)

/**
 * @brief z_vrfy_k_condvar_init() checks that the pointer is a condition variable object,
 * initialized or not, and then calls z_impl_k_condvar_init().
 *
 * @details
 * - Setup: the object check passes.
 * - Action: z_vrfy_k_condvar_init().
 * - Expected: return value 0. k_object_find() and
 *   k_object_validation_check() with the condition variable, K_OBJ_CONDVAR
 *   and _OBJ_INIT_ANY, before z_waitq_init(). No oops.
 *
 * @ingroup kernel_unit_condvar_k_condvar_init
 * @see z_vrfy_k_condvar_init()
 */
ZTEST(condvar_unit, test_syscall_init_checks_any_object)
{
	kernel_unit_pass_object_check();

	zassert_equal(z_vrfy_k_condvar_init(&cv), 0);

	assert_object_check(_OBJ_INIT_ANY);
	zassert_called_before(k_object_validation_check, z_waitq_init);
}

/**
 * @brief If the object check fails, z_vrfy_k_condvar_init() raises an oops before it changes the
 * condition variable.
 *
 * @details
 * - Setup: the object check fails.
 * - Action: z_vrfy_k_condvar_init().
 * - Expected: one oops, before z_waitq_init().
 *
 * @ingroup kernel_unit_condvar_k_condvar_init
 * @see z_vrfy_k_condvar_init()
 */
ZTEST(condvar_unit, test_syscall_init_oops_on_bad_object)
{
	kernel_unit_fail_object_check();

	(void)z_vrfy_k_condvar_init(&cv);

	zassert_oops_before(z_waitq_init);
}

/**
 * @brief z_vrfy_k_condvar_signal() checks that the pointer is an initialized condition variable
 * object, and then calls z_impl_k_condvar_signal().
 *
 * @details
 * - Setup: the object check passes. One thread waits.
 * - Action: z_vrfy_k_condvar_signal().
 * - Expected: return value 0. The object check with K_OBJ_CONDVAR and
 *   _OBJ_INIT_TRUE, before the lock. No oops. One call of z_sched_wake()
 *   with the wait queue.
 *
 * @ingroup kernel_unit_condvar_k_condvar_signal
 * @see z_vrfy_k_condvar_signal()
 */
ZTEST(condvar_unit, test_syscall_signal_checks_initialized_object)
{
	kernel_unit_pass_object_check();
	set_waiting_threads(1);

	zassert_equal(z_vrfy_k_condvar_signal(&cv), 0);

	assert_object_check(_OBJ_INIT_TRUE);
	zassert_called_before(k_object_validation_check, unit_arch_irq_lock);
	zassert_equal(z_sched_wake_fake.call_count, 1);
	zassert_equal_ptr(z_sched_wake_fake.arg0_val, &cv.wait_q);
}

/**
 * @brief If the object check fails, z_vrfy_k_condvar_signal() raises an oops before it locks
 * condvar_lock.
 *
 * @details
 * - Setup: the object check fails.
 * - Action: z_vrfy_k_condvar_signal().
 * - Expected: one oops, before arch_irq_lock().
 *
 * @ingroup kernel_unit_condvar_k_condvar_signal
 * @see z_vrfy_k_condvar_signal()
 */
ZTEST(condvar_unit, test_syscall_signal_oops_on_bad_object)
{
	kernel_unit_fail_object_check();

	(void)z_vrfy_k_condvar_signal(&cv);

	zassert_oops_before(unit_arch_irq_lock);
}

/**
 * @brief z_vrfy_k_condvar_broadcast() checks that the pointer is an initialized condition variable
 * object, and then returns the result of z_impl_k_condvar_broadcast().
 *
 * @details
 * - Setup: the object check passes. Two threads wait.
 * - Action: z_vrfy_k_condvar_broadcast().
 * - Expected: return value 2. The object check with K_OBJ_CONDVAR and
 *   _OBJ_INIT_TRUE, before the lock. No oops.
 *
 * @ingroup kernel_unit_condvar_k_condvar_broadcast
 * @see z_vrfy_k_condvar_broadcast()
 */
ZTEST(condvar_unit, test_syscall_broadcast_checks_initialized_object)
{
	kernel_unit_pass_object_check();
	set_waiting_threads(2);

	zassert_equal(z_vrfy_k_condvar_broadcast(&cv), 2);

	assert_object_check(_OBJ_INIT_TRUE);
	zassert_called_before(k_object_validation_check, unit_arch_irq_lock);
}

/**
 * @brief If the object check fails, z_vrfy_k_condvar_broadcast() raises an oops before it locks
 * condvar_lock.
 *
 * @details
 * - Setup: the object check fails.
 * - Action: z_vrfy_k_condvar_broadcast().
 * - Expected: one oops, before arch_irq_lock().
 *
 * @ingroup kernel_unit_condvar_k_condvar_broadcast
 * @see z_vrfy_k_condvar_broadcast()
 */
ZTEST(condvar_unit, test_syscall_broadcast_oops_on_bad_object)
{
	kernel_unit_fail_object_check();

	(void)z_vrfy_k_condvar_broadcast(&cv);

	zassert_oops_before(unit_arch_irq_lock);
}

/**
 * @brief z_vrfy_k_condvar_wait() checks the condition variable and then the mutex, and then
 * returns the result of z_impl_k_condvar_wait() with the same timeout.
 *
 * @details
 * - Setup: the object checks pass. The mutex is held. No thread signals.
 * - Action: z_vrfy_k_condvar_wait() with TEST_TIMEOUT.
 * - Expected: return value -EAGAIN. Two object checks, the first with the
 *   condition variable and K_OBJ_CONDVAR, the second with the mutex and
 *   K_OBJ_MUTEX, both with _OBJ_INIT_TRUE, before the lock. No oops.
 *   z_pend_curr() gets TEST_TIMEOUT.
 *
 * @ingroup kernel_unit_condvar_k_condvar_wait
 * @see z_vrfy_k_condvar_wait()
 */
ZTEST(condvar_unit, test_syscall_wait_checks_condvar_and_mutex)
{
	kernel_unit_pass_object_check();

	zassert_equal(z_vrfy_k_condvar_wait(&cv, &mutex, TEST_TIMEOUT), -EAGAIN);

	zassert_equal(k_object_validation_check_fake.call_count, 2);
	kernel_unit_assert_object_check_n(0, &cv, K_OBJ_CONDVAR, _OBJ_INIT_TRUE);
	kernel_unit_assert_object_check_n(1, &mutex, K_OBJ_MUTEX, _OBJ_INIT_TRUE);
	zassert_equal(unit_syscall_oops_fake.call_count, 0);
	zassert_called_before(k_object_validation_check, unit_arch_irq_lock);
	zassert_true(K_TIMEOUT_EQ(z_pend_curr_fake.arg3_val, TEST_TIMEOUT));
}

/**
 * @brief If the check of the condition variable fails, z_vrfy_k_condvar_wait() raises an oops
 * before it checks the mutex, locks condvar_lock or releases the mutex.
 *
 * @details
 * - Setup: k_object_find() returns an object. The custom fake
 *   fail_condvar_check() of k_object_validation_check() returns -EBADF for
 *   the condition variable and 0 for the mutex.
 * - Action: z_vrfy_k_condvar_wait() with TEST_TIMEOUT.
 * - Expected: one oops, after the first object check and before the
 *   second object check, arch_irq_lock() and k_mutex_unlock().
 *
 * @ingroup kernel_unit_condvar_k_condvar_wait
 * @see z_vrfy_k_condvar_wait()
 */
ZTEST(condvar_unit, test_syscall_wait_oops_on_bad_condvar)
{
	k_object_find_fake.return_val = &kernel_unit_kobject;
	k_object_validation_check_fake.custom_fake = fail_condvar_check;

	(void)z_vrfy_k_condvar_wait(&cv, &mutex, TEST_TIMEOUT);

	zassert_oops_before(unit_arch_irq_lock);
	zassert_called_before(unit_syscall_oops, k_mutex_unlock);
	zassert_equal(kernel_unit_history_index(KERNEL_UNIT_FN(unit_syscall_oops), 0),
		      kernel_unit_history_index(KERNEL_UNIT_FN(k_object_validation_check), 0) + 1,
		      "the oops does not follow the check of the condition variable");
}

/**
 * @brief If the check of the mutex fails, z_vrfy_k_condvar_wait() raises an oops before it locks
 * condvar_lock or releases the mutex.
 *
 * @details
 * - Setup: k_object_find() returns an object. The custom fake
 *   fail_mutex_check() of k_object_validation_check() returns 0 for the
 *   condition variable and -EBADF for the mutex.
 * - Action: z_vrfy_k_condvar_wait() with TEST_TIMEOUT.
 * - Expected: one oops, after the second object check and before
 *   arch_irq_lock() and k_mutex_unlock().
 *
 * @ingroup kernel_unit_condvar_k_condvar_wait
 * @see z_vrfy_k_condvar_wait()
 */
ZTEST(condvar_unit, test_syscall_wait_oops_on_bad_mutex)
{
	k_object_find_fake.return_val = &kernel_unit_kobject;
	k_object_validation_check_fake.custom_fake = fail_mutex_check;

	(void)z_vrfy_k_condvar_wait(&cv, &mutex, TEST_TIMEOUT);

	zassert_oops_before(unit_arch_irq_lock);
	zassert_called_before(unit_syscall_oops, k_mutex_unlock);
	zassert_equal(kernel_unit_history_index(KERNEL_UNIT_FN(unit_syscall_oops), 0),
		      kernel_unit_history_index(KERNEL_UNIT_FN(k_object_validation_check), 1) + 1,
		      "the oops does not follow the check of the mutex");
}
#endif /* CONFIG_USERSPACE */

#ifdef CONFIG_OBJ_CORE_CONDVAR
/*
 * Tests: Object core. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_condvar, at the top of this file.
 */

/* Return the descriptor of a type, and count the descriptors of this type. */
static const struct k_obj_core_desc *obj_core_desc(struct k_obj_type *type, int *count)
{
	const struct k_obj_core_desc *found = NULL;

	*count = 0;
	STRUCT_SECTION_FOREACH(k_obj_core_desc, desc) {
		if (desc->type == type) {
			found = desc;
			(*count)++;
		}
	}

	return found;
}

K_CONDVAR_DEFINE(unit_static_condvar);

/**
 * @brief With CONFIG_OBJ_CORE_CONDVAR, k_condvar_init() links the object core of the condition
 * variable to the condition variable object type.
 *
 * @details
 * - Action: z_impl_k_condvar_init().
 * - Expected: one call of k_obj_core_init_and_link() with the object core
 *   of the condition variable and @c obj_type_condvar, after
 *   z_waitq_init().
 *
 * @ingroup kernel_unit_condvar_k_condvar_init
 * @see z_impl_k_condvar_init()
 */
ZTEST(condvar_unit, test_obj_core_init_links_condvar)
{
	(void)z_impl_k_condvar_init(&cv);

	zassert_equal(k_obj_core_init_and_link_fake.call_count, 1);
	zassert_equal_ptr(k_obj_core_init_and_link_fake.arg0_val, K_OBJ_CORE(&cv));
	zassert_equal_ptr(k_obj_core_init_and_link_fake.arg1_val, &obj_type_condvar);
	zassert_called_before(z_waitq_init, k_obj_core_init_and_link);
}

/**
 * @brief With CONFIG_OBJ_CORE_CONDVAR, condvar.c defines one object type descriptor with the ID
 * K_OBJ_TYPE_CONDVAR_ID.
 *
 * @details
 * - Action: search the section @c k_obj_core_desc for the descriptor of
 *   @c obj_type_condvar.
 * - Expected: one descriptor. Its type ID is K_OBJ_TYPE_CONDVAR_ID. Its
 *   object size is the size of @c struct @c k_condvar, and its object core
 *   offset is the offset of @c obj_core. Its object range is the section
 *   @c k_condvar.
 *
 * @ingroup kernel_unit_condvar_static
 */
ZTEST(condvar_unit, test_obj_core_type_descriptor)
{
	int count;
	const struct k_obj_core_desc *desc = obj_core_desc(&obj_type_condvar, &count);

	zassert_equal(count, 1);
	zassert_not_null(desc);
	zassert_equal(desc->type_id, K_OBJ_TYPE_CONDVAR_ID);
	zassert_equal(desc->obj_size, sizeof(struct k_condvar));
	zassert_equal(desc->obj_core_offset, offsetof(struct k_condvar, obj_core));
	zassert_equal_ptr(desc->objs_start, STRUCT_SECTION_START(k_condvar));
	zassert_equal_ptr(desc->objs_end, STRUCT_SECTION_END(k_condvar));
}

/**
 * @brief The object range of the descriptor contains the condition variables that
 * K_CONDVAR_DEFINE() defines.
 *
 * @details
 * - Setup: K_CONDVAR_DEFINE() of one condition variable in the test.
 * - Action: compare its address with the object range of the descriptor.
 * - Expected: the condition variable is in the range, at a multiple of the
 *   object size from the start.
 *
 * @ingroup kernel_unit_condvar_static
 */
ZTEST(condvar_unit, test_obj_core_descriptor_covers_static_condvars)
{
	int count;
	const struct k_obj_core_desc *desc = obj_core_desc(&obj_type_condvar, &count);
	uintptr_t obj = (uintptr_t)&unit_static_condvar;

	zassert_not_null(desc);
	zassert_true((obj >= (uintptr_t)desc->objs_start) && (obj < (uintptr_t)desc->objs_end));
	zassert_equal((obj - (uintptr_t)desc->objs_start) % desc->obj_size, 0U);
}
#endif /* CONFIG_OBJ_CORE_CONDVAR */
