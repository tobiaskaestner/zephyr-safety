/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @defgroup kernel_unit_models Models of the layers below
 * @ingroup kernel_unit_tests
 * @brief Shared custom fakes with state, and shared checks of the unit tests.
 *
 * A model is a custom fake (@c custom_fake of FFF) with a small state. It
 * gives the unit under test the inputs of one design rule. Each model states
 * an assumption about the layer below the unit, for example about the
 * scheduler. The tests of a unit are correct only if the layer below meets
 * this assumption. The real behavior of the layer below is the subject of its
 * own unit test. The section "Assumption" of each model gives the assumption.
 *
 * The header also has the shared checks: the lock invariant, the ISR refusal
 * of the scheduler, the object checks of the system calls and the checks that
 * do not return.
 *
 * Rules for the use:
 *
 * - Include this header in the test source after kernel_unit.h. All functions
 *   are static inline, and the state is static data of the test source. Thus
 *   an application links only the fake groups that its unit needs. A model
 *   of a fake group that the application does not link is not emitted.
 * - A model replaces @c return_val of its fake. A test that needs a plain
 *   return value sets @c custom_fake to NULL.
 * - The fake groups reset the fakes before each test, so each test installs
 *   the models that it needs. The functions that install a model also set
 *   the state of the model.
 * - Without @kconfig{CONFIG_MULTITHREADING}, a failed @c zassert_*() returns
 *   from the function. Thus the checks of this header return no value.
 *
 * @{
 */

#ifndef KERNEL_UNIT_MODELS_H_
#define KERNEL_UNIT_MODELS_H_

#include <errno.h>
#include <setjmp.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include <zephyr/kernel.h>
#include <zephyr/arch/cpu.h>
#include <zephyr/sys/util.h>
#include <kernel_unit.h>
#include <kernel_arch_interface.h>
#include <ksched.h>
#include <fakes/fatal.h>
#ifdef CONFIG_USERSPACE
#include <zephyr/internal/syscall_handler.h>
#endif
#ifdef CONFIG_ASSERT
#include <fakes/assert.h>
#endif

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @name Fill pattern and guard entries
 *
 * A test fills an object or a buffer with KERNEL_UNIT_FILL before the
 * action. Then the test can show which bytes the unit writes. A buffer of a
 * test can have one guard entry after its end, also filled with the pattern.
 * kernel_unit_assert_filled() on the guard entry shows that no operation
 * writes after the end of the buffer.
 * @{
 */

/** Byte value that fills an object or a buffer before a test. */
#define KERNEL_UNIT_FILL 0xA5

/**
 * @brief Assert that each byte of a memory area has the value KERNEL_UNIT_FILL.
 *
 * @param p Start of the area.
 * @param size Number of bytes.
 */
static inline void kernel_unit_assert_filled(const void *p, size_t size)
{
	const uint8_t *b = p;

	for (size_t i = 0; i < size; i++) {
		zassert_equal(b[i], KERNEL_UNIT_FILL, "byte %zu was written", i);
	}
}

/** @} */

/**
 * @name Lock spies
 *
 * The spies replace the fakes of the lock and of two release paths:
 * unit_arch_irq_lock(), unit_arch_irq_unlock() and z_reschedule(). Each spy
 * calls an observer function of the test. The observer records the state of
 * the object at the call. Thus a test sees which changes of the object occur
 * while the unit holds the lock.
 *
 * Assumption: k_spin_lock() calls arch_irq_lock() once and returns its key.
 * k_spin_unlock() and z_reschedule() release the lock. This is true for
 * zephyr/spinlock.h without SMP. The spies do not count the holds of the
 * lock: each lock gives KERNEL_UNIT_IRQ_KEY. For a count, see the lock model.
 * @{
 */

/** Observer function of a model: it records the state of the test object. */
typedef void (*kernel_unit_observer_t)(void);

/** Observer at the lock. NULL: no observer. */
static __maybe_unused kernel_unit_observer_t kernel_unit_spy_at_lock;

/** Observer at a release. NULL: no observer. */
static __maybe_unused kernel_unit_observer_t kernel_unit_spy_at_release;

/** Fake unit_arch_irq_lock(): calls the lock observer and returns KERNEL_UNIT_IRQ_KEY. */
static inline unsigned int kernel_unit_lock_spy(void)
{
	if (kernel_unit_spy_at_lock != NULL) {
		kernel_unit_spy_at_lock();
	}

	return KERNEL_UNIT_IRQ_KEY;
}

/** Fake unit_arch_irq_unlock(): calls the release observer. */
static inline void kernel_unit_unlock_spy(unsigned int key)
{
	ARG_UNUSED(key);

	if (kernel_unit_spy_at_release != NULL) {
		kernel_unit_spy_at_release();
	}
}

/** Fake z_reschedule(): calls the release observer. */
static inline void kernel_unit_reschedule_spy(struct k_spinlock *lock, k_spinlock_key_t key)
{
	ARG_UNUSED(lock);
	ARG_UNUSED(key);

	if (kernel_unit_spy_at_release != NULL) {
		kernel_unit_spy_at_release();
	}
}

/**
 * @brief Install the lock spies.
 *
 * The spies replace the fakes unit_arch_irq_lock(), unit_arch_irq_unlock()
 * and z_reschedule(). A test that does not want to observe z_reschedule()
 * sets @c z_reschedule_fake.custom_fake to NULL after this call.
 *
 * @param at_lock Observer at the lock, or NULL.
 * @param at_release Observer at a release, or NULL.
 */
static inline void kernel_unit_spy_on_lock(kernel_unit_observer_t at_lock,
					   kernel_unit_observer_t at_release)
{
	kernel_unit_spy_at_lock = at_lock;
	kernel_unit_spy_at_release = at_release;
	unit_arch_irq_lock_fake.custom_fake = kernel_unit_lock_spy;
	unit_arch_irq_unlock_fake.custom_fake = kernel_unit_unlock_spy;
	z_reschedule_fake.custom_fake = kernel_unit_reschedule_spy;
}

/** @} */

/**
 * @name Lock model
 *
 * The lock model counts the holds of the lock. It also runs an action of
 * another thread when the lock becomes free. This models a thread on a
 * second CPU that spins on the lock. With the model, a test can show a race
 * that occurs if the unit releases the lock too early.
 *
 * The first lock (depth 0 to 1) is the outer lock. It gives
 * KERNEL_UNIT_IRQ_KEY. A lock inside it (for example the scheduler spinlock
 * with @kconfig{CONFIG_MP_MAX_NUM_CPUS} > 1) is a nested lock. It gives
 * KERNEL_UNIT_NESTED_IRQ_KEY. A release with KERNEL_UNIT_IRQ_KEY is an outer
 * release.
 *
 * Assumptions:
 * - k_spin_lock() calls arch_irq_lock() once, and k_spin_unlock() calls
 *   arch_irq_unlock() once with the key of the lock.
 * - z_reschedule() and z_pend_curr() release the lock that they get. A
 *   z_pend_curr() model of the test calls kernel_unit_lock_released(). In an
 *   ISR, z_pend_curr() refuses the call and does not release the lock (see
 *   the ISR refusal below). The fake then calls no model.
 * - Another thread can run only while no thread holds the lock.
 * @{
 */

/** Interrupt lock key of a nested lock in the lock model. */
#define KERNEL_UNIT_NESTED_IRQ_KEY 0x5EA1C0DFU

/** State of the lock model. */
struct kernel_unit_lock_model {
	/** Number of holds of the lock now. */
	int depth;
	/** Number of outer locks. */
	unsigned int outer_locks;
	/** Number of outer releases. */
	unsigned int outer_releases;
	/** Number of nested locks. */
	unsigned int nested_locks;
	/** Number of releases of a nested lock with arch_irq_unlock(). */
	unsigned int nested_unlocks;
	/** Highest depth since the model was installed. */
	int max_depth;
	/** Observer at an outer lock, or NULL. */
	kernel_unit_observer_t at_lock;
	/** Observer at an outer release, or NULL. */
	kernel_unit_observer_t at_release;
	/** Action of another thread that waits for the lock, or NULL. */
	kernel_unit_observer_t waiter;
};

/** The state of the lock model. kernel_unit_lock_model_install() sets it to zeros. */
static __maybe_unused struct kernel_unit_lock_model kernel_unit_lock;

/**
 * @brief Release one hold of the lock in the model.
 *
 * If the lock becomes free and another thread waits for it, the action of
 * this thread runs now. A z_pend_curr() model calls this function, because
 * z_pend_curr() releases the lock.
 */
static inline void kernel_unit_lock_released(void)
{
	kernel_unit_lock.depth--;
	if ((kernel_unit_lock.depth == 0) && (kernel_unit_lock.waiter != NULL)) {
		kernel_unit_observer_t action = kernel_unit_lock.waiter;

		kernel_unit_lock.waiter = NULL;
		action();
	}
}

/** Fake unit_arch_irq_lock() of the lock model. */
static inline unsigned int kernel_unit_lock_model_lock(void)
{
	kernel_unit_lock.depth++;
	kernel_unit_lock.max_depth = MAX(kernel_unit_lock.max_depth, kernel_unit_lock.depth);
	if (kernel_unit_lock.depth > 1) {
		kernel_unit_lock.nested_locks++;
		return KERNEL_UNIT_NESTED_IRQ_KEY;
	}

	kernel_unit_lock.outer_locks++;
	if (kernel_unit_lock.at_lock != NULL) {
		kernel_unit_lock.at_lock();
	}

	return KERNEL_UNIT_IRQ_KEY;
}

/* An outer release: count it, call the observer, then release the hold. */
static inline void kernel_unit_lock_model_outer_release(void)
{
	kernel_unit_lock.outer_releases++;
	if (kernel_unit_lock.at_release != NULL) {
		kernel_unit_lock.at_release();
	}
	kernel_unit_lock_released();
}

/** Fake unit_arch_irq_unlock() of the lock model. */
static inline void kernel_unit_lock_model_unlock(unsigned int key)
{
	if (key == KERNEL_UNIT_IRQ_KEY) {
		kernel_unit_lock_model_outer_release();
	} else {
		kernel_unit_lock.nested_unlocks++;
		kernel_unit_lock_released();
	}
}

/** Fake z_reschedule() of the lock model: an outer release. */
static inline void kernel_unit_lock_model_reschedule(struct k_spinlock *lock, k_spinlock_key_t key)
{
	ARG_UNUSED(lock);
	ARG_UNUSED(key);

	kernel_unit_lock_model_outer_release();
}

/**
 * @brief Install the lock model.
 *
 * The model replaces the fakes unit_arch_irq_lock(), unit_arch_irq_unlock()
 * and z_reschedule(), and sets its state to zeros. A z_pend_curr() model of
 * the test must call kernel_unit_lock_released().
 */
static inline void kernel_unit_lock_model_install(void)
{
	memset(&kernel_unit_lock, 0, sizeof(kernel_unit_lock));
	unit_arch_irq_lock_fake.custom_fake = kernel_unit_lock_model_lock;
	unit_arch_irq_unlock_fake.custom_fake = kernel_unit_lock_model_unlock;
	z_reschedule_fake.custom_fake = kernel_unit_lock_model_reschedule;
}

/**
 * @brief Let another thread run an action when the lock becomes free.
 *
 * If no thread holds the lock, the action runs now. Otherwise it runs at the
 * release that frees the lock.
 *
 * @param action The action of the other thread.
 */
static inline void kernel_unit_run_when_free(kernel_unit_observer_t action)
{
	if (kernel_unit_lock.depth == 0) {
		action();
	} else {
		kernel_unit_lock.waiter = action;
	}
}

/**
 * @brief Let another thread run an action at the next release that frees the lock.
 *
 * @param action The action of the other thread.
 */
static inline void kernel_unit_run_at_next_release(kernel_unit_observer_t action)
{
	kernel_unit_lock.waiter = action;
}

/** @} */

/**
 * @name Lock invariant
 *
 * The lock invariant of one operation: the operation locks the lock of the
 * object once, as its first call to the layers below. It releases the lock
 * once, with the key of the lock, in one of three ways. The release is its
 * last call to the layers below.
 *
 * The check reads the fakes unit_arch_irq_lock(), unit_arch_irq_unlock(),
 * z_reschedule() and z_pend_curr() and the call history. It works with the
 * lock spies, with the lock model and with plain fakes. It does not work
 * with nested locks: count them in the test. It does not apply to a call of
 * z_pend_curr() that the fake refuses in an ISR: this call does not release
 * the lock.
 * @{
 */

/** The way an operation releases the lock. */
enum kernel_unit_release {
	/** k_spin_unlock(): the operation does not reschedule. */
	KERNEL_UNIT_RELEASED_BY_UNLOCK,
	/** z_reschedule(): the operation woke a thread. */
	KERNEL_UNIT_RELEASED_BY_RESCHEDULE,
	/** z_pend_curr(): the current thread waits. */
	KERNEL_UNIT_RELEASED_BY_PEND,
};

/** Filter of calls: return true if the check permits a call to @p fn. */
typedef bool (*kernel_unit_call_filter_t)(fff_function_t fn);

/** The lock invariant of one operation, with the permitted variations. */
struct kernel_unit_lock_rule {
	/** The lock that z_reschedule() and z_pend_curr() get. */
	const struct k_spinlock *lock;
	/** The way the operation releases the lock. */
	enum kernel_unit_release how;
	/**
	 * Calls before the lock that the check permits, for example the ISR
	 * check of an __ASSERT(). NULL: the lock is the first call.
	 */
	kernel_unit_call_filter_t before_lock;
	/**
	 * The only call after z_pend_curr(), for example k_mutex_lock() in
	 * k_condvar_wait(). NULL: the release is the last call.
	 */
	fff_function_t after_pend;
};

/** Call filter that permits each call. */
static inline bool kernel_unit_any_call(fff_function_t fn)
{
	ARG_UNUSED(fn);

	return true;
}

/** Return the number of releases: calls of unlock, z_reschedule() and z_pend_curr(). */
static inline unsigned int kernel_unit_release_count(void)
{
	return unit_arch_irq_unlock_fake.call_count + z_reschedule_fake.call_count +
	       z_pend_curr_fake.call_count;
}

/**
 * @brief Assert the lock invariant of one operation.
 *
 * @param rule The lock, the way of the release and the permitted variations.
 */
static inline void kernel_unit_assert_lock_rule(const struct kernel_unit_lock_rule *rule)
{
	fff_function_t calls[FFF_CALL_HISTORY_LEN];
	size_t n = kernel_unit_history(calls, ARRAY_SIZE(calls));
	int lock_index = kernel_unit_history_index(KERNEL_UNIT_FN(unit_arch_irq_lock), 0);
	int last = (int)n - 1;
	fff_function_t release;

	zassert_equal(unit_arch_irq_lock_fake.call_count, 1, "the lock was locked %u times",
		      unit_arch_irq_lock_fake.call_count);
	zassert_equal(kernel_unit_release_count(), 1, "the lock was released %u times",
		      kernel_unit_release_count());
	if (rule->before_lock == NULL) {
		zassert_equal(lock_index, 0, "the lock is not the first call");
	} else {
		zassert_true(lock_index >= 0, "no lock");
		for (int i = 0; i < lock_index; i++) {
			zassert_true(rule->before_lock(calls[i]), "call %d comes before the lock",
				     i);
		}
	}

	switch (rule->how) {
	case KERNEL_UNIT_RELEASED_BY_UNLOCK:
		zassert_equal(unit_arch_irq_unlock_fake.call_count, 1);
		zassert_equal(unit_arch_irq_unlock_fake.arg0_val, KERNEL_UNIT_IRQ_KEY);
		release = KERNEL_UNIT_FN(unit_arch_irq_unlock);
		break;
	case KERNEL_UNIT_RELEASED_BY_RESCHEDULE:
		zassert_equal(z_reschedule_fake.call_count, 1);
		zassert_equal_ptr(z_reschedule_fake.arg0_val, rule->lock);
		zassert_equal((unsigned int)z_reschedule_fake.arg1_val.key, KERNEL_UNIT_IRQ_KEY);
		release = KERNEL_UNIT_FN(z_reschedule);
		break;
	case KERNEL_UNIT_RELEASED_BY_PEND:
	default:
		zassert_equal(z_pend_curr_fake.call_count, 1);
		zassert_equal_ptr(z_pend_curr_fake.arg0_val, rule->lock);
		zassert_equal((unsigned int)z_pend_curr_fake.arg1_val.key, KERNEL_UNIT_IRQ_KEY);
		release = KERNEL_UNIT_FN(z_pend_curr);
		if (rule->after_pend != NULL) {
			zassert_equal(kernel_unit_history_index(rule->after_pend, 0), last,
				      "the call after z_pend_curr() is not the last call");
			last--;
		}
		break;
	}

	zassert_equal(kernel_unit_history_index(release, 0), last,
		      "the release of the lock is not at the expected position");
}

/**
 * @brief Assert the lock invariant: the lock is the first call, the release the last call.
 *
 * @param lock_ The lock of the object (a pointer).
 * @param how_ The way of the release (enum kernel_unit_release).
 */
#define kernel_unit_assert_lock_released_once(lock_, how_)                                         \
	kernel_unit_assert_lock_rule(                                                              \
		&(const struct kernel_unit_lock_rule){.lock = (lock_), .how = (how_)})

/** @} */

/**
 * @name Waiting threads
 *
 * The model of the wait queue is a number of waiting threads. The fake
 * z_sched_wake() wakes one thread for each call, until no thread waits.
 *
 * Assumption: z_sched_wake() wakes the first waiting thread and returns
 * true. If no thread waits, it returns false and changes nothing.
 * @{
 */

/** Number of waiting threads of the model. */
static __maybe_unused unsigned int kernel_unit_waiting_threads;

/** Fake z_sched_wake(): wake one waiting thread, if a thread waits. */
static inline bool kernel_unit_wake_waiting_thread(_wait_q_t *wait_q, int swap_retval,
						   void *swap_data)
{
	ARG_UNUSED(wait_q);
	ARG_UNUSED(swap_retval);
	ARG_UNUSED(swap_data);

	if (kernel_unit_waiting_threads == 0U) {
		return false;
	}
	kernel_unit_waiting_threads--;

	return true;
}

/**
 * @brief Let @p n threads wait: z_sched_wake() wakes them, one for each call.
 *
 * @param n The number of waiting threads.
 */
static inline void kernel_unit_set_waiting_threads(unsigned int n)
{
	kernel_unit_waiting_threads = n;
	z_sched_wake_fake.custom_fake = kernel_unit_wake_waiting_thread;
}

/** @} */

/**
 * @name Wait result
 *
 * The fake z_pend_curr() ends the wait at once, with a result that the test
 * gives. The current thread then has the swap data that the test gives.
 *
 * Assumption: z_pend_curr() returns when another thread wakes the current
 * thread or when the timeout expires. Before the wake, the other thread
 * writes the swap data of the waiting thread. z_pend_curr() returns the
 * swap return value of the wake, or -EAGAIN after a timeout.
 * @{
 */

/** Swap data that the current thread has after the wait. */
static __maybe_unused void *kernel_unit_pend_swap_data;

/** Return value of z_pend_curr(). */
static __maybe_unused int kernel_unit_pend_result;

/** Fake z_pend_curr(): give the swap data to the current thread and return the result. */
static inline int kernel_unit_pend_with_result(struct k_spinlock *lock, k_spinlock_key_t key,
					       _wait_q_t *wait_q, k_timeout_t timeout)
{
	ARG_UNUSED(lock);
	ARG_UNUSED(key);
	ARG_UNUSED(wait_q);
	ARG_UNUSED(timeout);

	_current->base.swap_data = kernel_unit_pend_swap_data;

	return kernel_unit_pend_result;
}

/**
 * @brief Let an operation wait, and give it this swap data and result after the wait.
 *
 * @param swap_data The swap data of the current thread after the wait.
 * @param result The return value of z_pend_curr().
 */
static inline void kernel_unit_set_wait_result(void *swap_data, int result)
{
	kernel_unit_pend_swap_data = swap_data;
	kernel_unit_pend_result = result;
	z_pend_curr_fake.custom_fake = kernel_unit_pend_with_result;
}

/** @} */

/**
 * @name Other threads
 *
 * The fake z_pend_curr() runs an action of another thread while the current
 * thread waits. If the action wakes the current thread, the wait ends with
 * the result of the wake. Otherwise the wait ends as a timeout (-EAGAIN).
 * A wake fake of the test (for example z_sched_wake() or
 * arch_thread_return_value_set()) calls kernel_unit_wake_current() when it
 * wakes the current thread.
 *
 * kernel_unit_run_as() runs an action with another current thread. The test
 * gives the threads.
 *
 * Assumptions:
 * - While a thread waits in z_pend_curr(), other threads can run, and one of
 *   them can wake it.
 * - The wait result is the value that the waker gives to the waiting thread
 *   (swap_retval of z_sched_wake(), or arch_thread_return_value_set()).
 * - A wait that no thread ends is a timeout with the result -EAGAIN.
 * - With the lock model, z_pend_curr() releases the lock before other threads
 *   run.
 * @{
 */

/** State of the model of another thread. */
struct kernel_unit_other_thread {
	/** Action of the other thread while the current thread waits. */
	kernel_unit_observer_t while_waiting;
	/** True if the other thread woke the current thread. */
	bool woken;
	/** The wait result that the other thread gave. */
	int result;
	/** True if z_pend_curr() releases the lock model. */
	bool release_lock_model;
};

/** The state of the model of another thread. */
static __maybe_unused struct kernel_unit_other_thread kernel_unit_other;

/**
 * @brief Wake the current thread with a wait result.
 *
 * A wake fake of the test calls this function if it wakes the thread that
 * waits in z_pend_curr().
 *
 * @param result The wait result.
 */
static inline void kernel_unit_wake_current(int result)
{
	kernel_unit_other.woken = true;
	kernel_unit_other.result = result;
}

/** Fake z_pend_curr(): another thread runs while the current thread waits. */
static inline int kernel_unit_pend_other_thread(struct k_spinlock *lock, k_spinlock_key_t key,
						_wait_q_t *wait_q, k_timeout_t timeout)
{
	ARG_UNUSED(lock);
	ARG_UNUSED(key);
	ARG_UNUSED(wait_q);
	ARG_UNUSED(timeout);

	kernel_unit_other.woken = false;
	if (kernel_unit_other.release_lock_model) {
		kernel_unit_lock_released();
	}
	if (kernel_unit_other.while_waiting != NULL) {
		kernel_unit_other.while_waiting();
	}

	return kernel_unit_other.woken ? kernel_unit_other.result : -EAGAIN;
}

/**
 * @brief Let another thread run @p action while the current thread waits in z_pend_curr().
 *
 * @param action The action of the other thread, or NULL: no thread runs, and
 *               the wait is a timeout.
 * @param release_lock_model True if z_pend_curr() releases the lock model
 *                           (kernel_unit_lock_model_install()).
 */
static inline void kernel_unit_set_other_thread(kernel_unit_observer_t action,
						bool release_lock_model)
{
	kernel_unit_other.while_waiting = action;
	kernel_unit_other.woken = false;
	kernel_unit_other.result = -EAGAIN;
	kernel_unit_other.release_lock_model = release_lock_model;
	z_pend_curr_fake.custom_fake = kernel_unit_pend_other_thread;
}

/**
 * @brief Run @p action as the thread @p thread.
 *
 * During the action, _current is @p thread. After the action, _current is
 * the thread before the call. The test needs the fake group @c init.
 *
 * @param thread The thread that runs the action.
 * @param action The action.
 */
static inline void kernel_unit_run_as(struct k_thread *thread, kernel_unit_observer_t action)
{
	struct k_thread *before = _current;

	_kernel.cpus[0].current = thread;
	action();
	_kernel.cpus[0].current = before;
}

/** @} */

/**
 * @name Scheduler refusal in an ISR
 *
 * The fake z_pend_curr() refuses a call from an ISR, as the real function
 * does (kernel/sched.c). The refusal is in the fake itself, before its
 * custom fake. Thus each model of z_pend_curr() in this header and in the
 * test sources gets it. The shadow ksched.h describes the refusal.
 *
 * In an ISR, the fake does the assertion hook (with
 * @kconfig{CONFIG_ASSERT}) and the panic z_fatal_error(K_ERR_KERNEL_PANIC,
 * NULL). It makes no other change. The fake z_fatal_error() returns, and the
 * fake z_pend_curr() returns KERNEL_UNIT_PEND_REFUSED (-EAGAIN, a timeout).
 * The real z_pend_curr() does not return. A test that lets an ISR reach
 * z_pend_curr() calls kernel_unit_expect_pend_refusal() first. Otherwise the
 * fake fails the test. To stop the unit at the panic, use
 * zassert_stopped_by_panic().
 *
 * Assumption: z_pend_curr() reads arch_is_in_isr() first. In an ISR, it
 * asserts, panics and does not return. It does not release the lock and
 * does not pend a thread.
 * @{
 */

/** Let the fake z_pend_curr() refuse a call from an ISR without a failed test. */
static inline void kernel_unit_expect_pend_refusal(void)
{
	kernel_unit_pend_refusal.expected = true;
}

/* Return the position of the last call of @p fn in @p calls before @p end, or -1. */
static inline int kernel_unit_last_call_before(const fff_function_t *calls, int end,
					       fff_function_t fn)
{
	for (int i = end - 1; i >= 0; i--) {
		if (calls[i] == fn) {
			return i;
		}
	}

	return -1;
}

/**
 * @brief Assert that the scheduler refused one call of z_pend_curr() from an ISR with a panic.
 *
 * The check asserts one refusal and one panic, z_fatal_error() with
 * K_ERR_KERNEL_PANIC and NULL. In the call history, the panic comes after
 * the last call of z_pend_curr() before it. With @kconfig{CONFIG_ASSERT}, a
 * failed assertion comes between the two calls.
 */
static inline void kernel_unit_assert_pend_refused(void)
{
	fff_function_t calls[FFF_CALL_HISTORY_LEN];
	int n = (int)kernel_unit_history(calls, ARRAY_SIZE(calls));
	int panic = kernel_unit_last_call_before(calls, n, KERNEL_UNIT_FN(z_fatal_error));
	int pend = kernel_unit_last_call_before(calls, MAX(panic, 0), KERNEL_UNIT_FN(z_pend_curr));

	zassert_equal(kernel_unit_pend_refusal.count, 1, "%u refusals of z_pend_curr()",
		      kernel_unit_pend_refusal.count);
	zassert_equal(z_fatal_error_fake.call_count, 1, "%u fatal errors",
		      z_fatal_error_fake.call_count);
	zassert_equal(z_fatal_error_fake.arg0_val, K_ERR_KERNEL_PANIC);
	zassert_is_null(z_fatal_error_fake.arg1_val);
	zassert_true(panic >= 0, "no panic in the call history");
	zassert_true(pend >= 0, "no z_pend_curr() before the panic");
#ifdef CONFIG_ASSERT
	int hook = kernel_unit_last_call_before(calls, panic, KERNEL_UNIT_FN(assert_post_action));

	zassert_true(hook > pend, "no failed assertion between z_pend_curr() and the panic");
#endif
}

/** @} */

#ifdef CONFIG_USERSPACE
/**
 * @name Object checks of the system calls
 *
 * The system call checks call the fakes k_object_find() and
 * k_object_validation_check() of the shadow
 * zephyr/internal/syscall_handler.h. A failed check calls the fake
 * unit_syscall_oops(). These helpers set the result of the checks and
 * assert their arguments.
 * @{
 */

/** The kernel object that the fake k_object_find() returns. */
static __maybe_unused struct k_object kernel_unit_kobject;

/** Make the object checks pass. */
static inline void kernel_unit_pass_object_check(void)
{
	k_object_find_fake.return_val = &kernel_unit_kobject;
	k_object_validation_check_fake.return_val = 0;
}

/** Make the object checks fail. */
static inline void kernel_unit_fail_object_check(void)
{
	k_object_find_fake.return_val = &kernel_unit_kobject;
	k_object_validation_check_fake.return_val = -EBADF;
}

/**
 * @brief Assert the arguments of object check number @p n (0 is the first check).
 *
 * @param n The number of the check.
 * @param obj The object.
 * @param otype The object type.
 * @param init The expected initialization state.
 */
static inline void kernel_unit_assert_object_check_n(unsigned int n, const void *obj,
						     enum k_objects otype,
						     enum _obj_init_check init)
{
	zassert_equal_ptr(k_object_find_fake.arg0_history[n], obj);
	zassert_equal_ptr(k_object_validation_check_fake.arg0_history[n], &kernel_unit_kobject);
	zassert_equal_ptr(k_object_validation_check_fake.arg1_history[n], obj);
	zassert_equal(k_object_validation_check_fake.arg2_history[n], otype);
	zassert_equal(k_object_validation_check_fake.arg3_history[n], init);
}

/**
 * @brief Assert one object check with these arguments, and no oops.
 *
 * @param obj The object.
 * @param otype The object type.
 * @param init The expected initialization state.
 */
static inline void kernel_unit_assert_object_check(const void *obj, enum k_objects otype,
						   enum _obj_init_check init)
{
	zassert_equal(k_object_find_fake.call_count, 1);
	zassert_equal(k_object_validation_check_fake.call_count, 1);
	kernel_unit_assert_object_check_n(0, obj, otype, init);
	zassert_equal(unit_syscall_oops_fake.call_count, 0);
}

/** @} */
#endif /* CONFIG_USERSPACE */

/**
 * @name Checks that do not return
 *
 * The fakes assert_post_action(), unit_syscall_oops() and z_fatal_error()
 * return, so the unit continues after a failed check or a panic. If the unit
 * then uses an invalid pointer, the test crashes. These macros give the fake
 * a custom fake that calls longjmp() back into the test. Thus the unit stops
 * at the check, as the real function does.
 * @{
 */

/** Jump buffer of the checks that do not return. */
static __maybe_unused jmp_buf kernel_unit_jump_env;

/** Custom fake of unit_syscall_oops() and assert_post_action(): jump back to the test. */
static inline void kernel_unit_jump(void)
{
	longjmp(kernel_unit_jump_env, 1);
}

#if defined(CONFIG_ASSERT) && !defined(CONFIG_ASSERT_NO_FILE_INFO)
/** Custom fake of assert_post_action(): jump back to the test. */
static inline void kernel_unit_assert_jump(const char *file, unsigned int line)
{
	ARG_UNUSED(file);
	ARG_UNUSED(line);

	kernel_unit_jump();
}
#elif defined(CONFIG_ASSERT)
#define kernel_unit_assert_jump kernel_unit_jump
#endif

/**
 * @brief Call @p call and assert that a failed assertion stops it.
 *
 * Needs @kconfig{CONFIG_ASSERT} and the fake group @c assert.
 */
#define zassert_stopped_by_assertion(call)                                                         \
	do {                                                                                       \
		assert_post_action_fake.custom_fake = kernel_unit_assert_jump;                     \
		if (setjmp(kernel_unit_jump_env) == 0) {                                           \
			(void)(call);                                                              \
			zassert_unreachable(#call " did not fail an assertion");                   \
		}                                                                                  \
		assert_post_action_fake.custom_fake = NULL;                                        \
	} while (false)

/**
 * @brief Call @p call and assert that an oops stops it.
 *
 * Needs @kconfig{CONFIG_USERSPACE} and the fake group @c syscall_handler.
 */
#define zassert_stopped_by_oops(call)                                                              \
	do {                                                                                       \
		unit_syscall_oops_fake.custom_fake = kernel_unit_jump;                             \
		if (setjmp(kernel_unit_jump_env) == 0) {                                           \
			call;                                                                      \
			zassert_unreachable(#call " returned without an oops");                    \
		}                                                                                  \
		unit_syscall_oops_fake.custom_fake = NULL;                                         \
	} while (false)

/** Custom fake of z_fatal_error(): jump back to the test. */
static inline void kernel_unit_fatal_jump(unsigned int reason, const struct arch_esf *esf)
{
	ARG_UNUSED(reason);
	ARG_UNUSED(esf);

	kernel_unit_jump();
}

/**
 * @brief Call @p call and assert that a panic or another fatal error stops it.
 *
 * The macro gives the fake z_fatal_error() a custom fake that calls
 * longjmp() back into the test. Thus the unit stops at k_panic(), also at
 * the panic of the ISR refusal in z_pend_curr(). For this refusal, call
 * kernel_unit_expect_pend_refusal() first. Needs the fake group @c fatal.
 */
#define zassert_stopped_by_panic(call)                                                             \
	do {                                                                                       \
		z_fatal_error_fake.custom_fake = kernel_unit_fatal_jump;                           \
		if (setjmp(kernel_unit_jump_env) == 0) {                                           \
			(void)(call);                                                              \
			zassert_unreachable(#call " returned without a fatal error");              \
		}                                                                                  \
		z_fatal_error_fake.custom_fake = NULL;                                             \
	} while (false)

/** @} */

#ifdef __cplusplus
}
#endif

/** @} */

#endif /* KERNEL_UNIT_MODELS_H_ */
