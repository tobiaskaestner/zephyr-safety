/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @defgroup kernel_unit_event kernel/events.c
 * @ingroup kernel_unit_tests
 * @brief Design specification of kernel/events.c, written as unit tests.
 *
 * @par The event object
 * An event object (@c struct @c k_event) is a set of 32 events. Each bit
 * of the word @c events is one event. The object has these parts:
 * - @c events: the current set of events.
 * - @c lock: the spinlock of the event object. Each event object has its
 *   own lock.
 * - @c wait_q: the wait queue of the threads that wait for events.
 * - @c obj_core: with @kconfig{CONFIG_OBJ_CORE_EVENT}, the object core.
 *
 * A waiting thread keeps its wait request in its own @c struct
 * @c k_thread: @c events is the set of events that it waits for, and
 * @c event_options holds the options of the wait. When a post wakes the
 * thread, the post writes the received events into the same field
 * @c events. Thus this field has two uses: first the request, then the
 * result.
 *
 * @par Operations that change the set
 * All four operations go through one internal function,
 * k_event_post_internal(event, events, mask). It sets the bits of
 * @c events that are in @c mask, clears the other bits of @c mask, and
 * keeps the bits outside of @c mask. It returns the old value of the bits
 * in @c mask.
 * - k_event_post(): mask = events. It adds events to the set.
 * - k_event_set(): mask = all bits. It replaces the set.
 * - k_event_set_masked(): the mask of the caller.
 * - k_event_clear(): events = 0, mask = the events to clear.
 *
 * @par Wait operations
 * All four wait operations go through k_event_wait_internal() with a set
 * of option bits:
 * - K_EVENT_WAIT_ALL: the thread waits for all events of its set. Without
 *   it, any one event of the set is sufficient.
 * - K_EVENT_OPTION_RESET: clear the whole set of the object before the
 *   check (the argument @c reset).
 * - K_EVENT_OPTION_CLEAR: consume the received events, that is, remove
 *   them from the set of the object. The "safe" variants set this option.
 *
 * k_event_wait() (any), k_event_wait_all() (all), k_event_wait_safe() (any,
 * consume) and k_event_wait_all_safe() (all, consume). A wait for an empty
 * set returns 0 at once. If the set already satisfies the condition, the
 * wait returns the matching events. Otherwise the wait returns 0 with
 * K_NO_WAIT, or the thread waits on the wait queue with z_pend_curr().
 *
 * @par Wake of the waiting threads
 * A post can satisfy more than one waiting thread. k_event_post_internal()
 * walks the wait queue with z_sched_waitq_walk() and the callback
 * event_walk_op(). The walk holds the scheduler lock. For each thread
 * whose condition the new set satisfies, the callback writes the matching
 * events into the thread, notes the events to consume, and stops the
 * timeout of the thread. Then the thread is made ready with the return
 * value 0:
 * - With @kconfig{CONFIG_WAITQ_SIMPLE} (default), the callback wakes the
 *   thread at once. The wait queue is a list, and the walk can remove the
 *   current thread.
 * - With @kconfig{CONFIG_WAITQ_SCALABLE}, the wait queue is a red-black
 *   tree. The walk must not change the tree. The callback links the thread
 *   into a list (@c next_event_link), and the post-walk callback
 *   event_post_walk_op() wakes the threads of this list after the walk,
 *   still under the scheduler lock.
 *
 * All threads of one post see the same new set. The events that the
 * threads consume are removed from the set after the walk. Thus the wake
 * of all satisfied threads is one atomic step for the scheduler.
 *
 * @par Locks
 * Each operation, except k_event_init() and a wait for an empty set, locks
 * the spinlock of its event object. k_spin_lock() locks the interrupts
 * with arch_irq_lock() and returns a key. Each path releases the lock
 * exactly once, with the same key, as its last call:
 * - The post operations always release it with z_reschedule(), also if no
 *   thread became ready.
 * - A wait releases it with k_spin_unlock() if it does not wait.
 * - A wait that must wait gives the lock and the key to z_pend_curr().
 *   z_pend_curr() adds the current thread to the wait queue, releases the
 *   lock and switches threads in one step.
 *
 * The walk of the wait queue occurs while the event lock is held. Thus no
 * thread can start or end a wait on this event during the walk, and the
 * wait request in each waiting thread is stable. The time with locked
 * interrupts grows with the number of waiting threads.
 *
 * @par Interfaces below events.c
 * - Scheduler (@c scheduler.h, @c ksched.h): z_sched_waitq_walk(),
 *   z_sched_wake_thread_locked(), z_reschedule(), z_pend_curr().
 * - Scheduler system call: k_sched_current_thread_query() gives the
 *   current thread.
 * - Timeouts (@c timeout_q.h): z_try_abort_thread_timeout().
 * - Architecture (@c kernel_arch_interface.h):
 *   arch_thread_return_value_set(), arch_is_in_isr() (assertions), and
 *   arch_irq_lock() and arch_irq_unlock() through k_spin_lock() and
 *   k_spin_unlock().
 * - Wait queue (@c wait_q.h): z_waitq_init().
 * - Object core: k_obj_core_init_and_link(), K_OBJ_TYPE_DEFINE().
 * - Kernel objects: k_object_init().
 * - System call checks: K_SYSCALL_OBJ(), K_SYSCALL_OBJ_NEVER_INIT(),
 *   K_OOPS().
 *
 * @par Kconfig options that change events.c
 * - @kconfig{CONFIG_WAITQ_SCALABLE}: the wake in two steps (see above).
 * - @kconfig{CONFIG_USERSPACE}: the verification functions
 *   z_vrfy_k_event_*() and the kernel object of the event.
 * - @kconfig{CONFIG_OBJ_CORE_EVENT}: the object core and the object type
 *   descriptor of the event objects.
 * - @kconfig{CONFIG_ASSERT}: the assertions that k_event_init() does not
 *   run in an ISR, and that a wait in an ISR uses K_NO_WAIT. The option
 *   also enables @kconfig{CONFIG_SPIN_VALIDATE} in @c zephyr/spinlock.h.
 *
 * events.c has no CHECKIF(). Thus the options
 * @kconfig{CONFIG_NO_RUNTIME_CHECKS} and @kconfig{CONFIG_ASSERT_ON_ERRORS}
 * do not change it.
 *
 * @par Test method
 * The tests call the functions of events.c directly (z_impl_k_event_*()
 * for the system calls, z_vrfy_k_event_*(), and the static functions). All
 * calls below events.c go to FFF fakes. The fake unit_arch_irq_lock()
 * returns KERNEL_UNIT_IRQ_KEY. Thus a test can follow the key to the call
 * that releases the lock. The FFF call history gives the order of the
 * calls.
 *
 * The tests use these models of the layers below:
 * - Wait queue: an array of threads of the test, in wait queue order. The
 *   fake z_sched_waitq_walk() calls the walk callback for each thread of
 *   the array, as the real function does, and then the post-walk callback.
 * - Wake: the fake z_sched_wake_thread_locked() removes the thread from
 *   the array.
 * - Wait: the fake z_pend_curr() returns a result that the test sets. For
 *   the hand-over tests, it adds the current thread to the array, runs a
 *   post of "another thread", and returns the value that the post gave to
 *   arch_thread_return_value_set(), or -EAGAIN (timeout) if the post did
 *   not wake the thread.
 *
 * @par Structure of the tests
 * Each public function of events.c has one group below this group. A system
 * call has one group for z_impl_k_event_*() and z_vrfy_k_event_*(). The
 * static functions and the data of events.c have the last group. Each test
 * is in the group of the function under test. The static functions
 * k_event_post_internal() and k_event_wait_internal() do the work of the
 * public functions. Thus a test of a public function is also a test of
 * one of these static functions, and the static group describes them. The
 * rules below (locking, system call verification, object core) apply to
 * more than one function. Their tests are in the group of the function
 * that they call.
 *
 * @par Locking
 * Each operation that reads or changes the set locks the spinlock of the
 * event object and releases it exactly once, with its key, as its last
 * call.
 * The lock of the event object protects the set and the wait queue. It
 * also protects the request in each waiting thread: a wait writes the
 * request under the lock, and the post reads it during the walk under the
 * same lock. The walk itself holds also the scheduler lock (inside
 * z_sched_waitq_walk()).
 *
 * The tests of the locking assert the lock invariant: one lock, one
 * release with the key of the lock, and the release is the last call.
 * Before the lock, a wait only reads its context (arch_is_in_isr() for the
 * assertion and k_sched_current_thread_query()).
 *
 * @par System call verification
 * With CONFIG_USERSPACE, each verification function checks the event
 * object before it calls the implementation.
 * A system call from a user thread goes to z_vrfy_k_event_*(). This
 * function checks that the pointer is an event object of the kernel that
 * the thread has access to. z_vrfy_k_event_init() uses
 * K_SYSCALL_OBJ_NEVER_INIT(): the object must not be initialized yet.
 * Thus a user thread cannot initialize an event object again while other
 * threads use it. The other functions use K_SYSCALL_OBJ(): the object must
 * be initialized. If the check fails, K_OOPS() stops the thread. Otherwise
 * the function calls z_impl_k_event_*() with the same arguments and
 * returns its result.
 *
 * In the test, K_OOPS() calls the fake unit_syscall_oops(), and this fake
 * returns. The real K_OOPS() does not return. Thus the tests check that
 * the oops occurs before the implementation locks or changes the event.
 *
 * @par Object core
 * With CONFIG_OBJ_CORE_EVENT, events.c defines the object type of the
 * event objects and links each event object to it.
 * events.c defines the object type @c obj_type_event. K_OBJ_TYPE_DEFINE()
 * puts one descriptor of this type into the iterable section
 * @c k_obj_core_desc. At boot, the object core code initializes the type
 * from the descriptor and links the event objects that K_EVENT_DEFINE()
 * defines (the section @c k_event). k_event_init() links each event
 * object that it initializes.
 */

/**
 * @defgroup kernel_unit_event_k_event_init k_event_init()
 * @ingroup kernel_unit_event
 * @brief k_event_init() makes the set empty and initializes the other parts of the event object.
 *
 * k_event_init() clears the set, sets the lock to its initial value, and
 * initializes the wait queue, the kernel object and the object core. It
 * does not lock the event: until k_event_init() returns, only the caller
 * uses the event object. k_event_init() is not for an ISR. With
 * @kconfig{CONFIG_ASSERT}, it asserts this.
 *
 * @par Functions in kernel/events.c
 * - z_impl_k_event_init()
 * - z_vrfy_k_event_init(), with @kconfig{CONFIG_USERSPACE}
 */

/**
 * @defgroup kernel_unit_event_k_event_post k_event_post()
 * @ingroup kernel_unit_event
 * @brief k_event_post() adds events to the set, wakes the waiting threads that the new set
 * satisfies, and returns the old value of the posted bits.
 *
 * k_event_post() calls k_event_post_internal() with mask = events. The
 * post, the wake of the waiting threads and the consumed events are
 * described in @ref kernel_unit_event_static. Most tests of the wake and of
 * the consumed events use k_event_post(), so they are in this group.
 *
 * @par Functions in kernel/events.c
 * - z_impl_k_event_post()
 * - z_vrfy_k_event_post(), with @kconfig{CONFIG_USERSPACE}
 */

/**
 * @defgroup kernel_unit_event_k_event_set k_event_set()
 * @ingroup kernel_unit_event
 * @brief k_event_set() replaces the set, wakes the waiting threads that the new set satisfies,
 * and returns the old set.
 *
 * k_event_set() calls k_event_post_internal() with mask = all bits (see
 * @ref kernel_unit_event_static).
 *
 * @par Functions in kernel/events.c
 * - z_impl_k_event_set()
 * - z_vrfy_k_event_set(), with @kconfig{CONFIG_USERSPACE}
 */

/**
 * @defgroup kernel_unit_event_k_event_set_masked k_event_set_masked()
 * @ingroup kernel_unit_event
 * @brief k_event_set_masked() changes the bits of the set in the mask of the caller, and returns
 * the old value of these bits.
 *
 * k_event_set_masked() calls k_event_post_internal() with the events and
 * the mask of the caller (see @ref kernel_unit_event_static).
 *
 * @par Functions in kernel/events.c
 * - z_impl_k_event_set_masked()
 * - z_vrfy_k_event_set_masked(), with @kconfig{CONFIG_USERSPACE}
 */

/**
 * @defgroup kernel_unit_event_k_event_clear k_event_clear()
 * @ingroup kernel_unit_event
 * @brief k_event_clear() removes events from the set, and returns the old value of these bits.
 *
 * k_event_clear() calls k_event_post_internal() with events = 0 and
 * mask = the events to clear (see @ref kernel_unit_event_static). It also
 * walks the wait queue.
 *
 * @par Functions in kernel/events.c
 * - z_impl_k_event_clear()
 * - z_vrfy_k_event_clear(), with @kconfig{CONFIG_USERSPACE}
 */

/**
 * @defgroup kernel_unit_event_k_event_wait k_event_wait()
 * @ingroup kernel_unit_event
 * @brief k_event_wait() waits for any one event of a request, and returns the matching events.
 *
 * k_event_wait() calls k_event_wait_internal() without K_EVENT_WAIT_ALL
 * and without K_EVENT_OPTION_CLEAR. The argument @c reset gives
 * K_EVENT_OPTION_RESET. The wait is described in
 * @ref kernel_unit_event_static. Most tests of the wait use k_event_wait(),
 * so they are in this group.
 *
 * @par Functions in kernel/events.c
 * - z_impl_k_event_wait()
 * - z_vrfy_k_event_wait(), with @kconfig{CONFIG_USERSPACE}
 */

/**
 * @defgroup kernel_unit_event_k_event_wait_all k_event_wait_all()
 * @ingroup kernel_unit_event
 * @brief k_event_wait_all() waits for all events of a request, and returns them.
 *
 * k_event_wait_all() calls k_event_wait_internal() with K_EVENT_WAIT_ALL
 * and without K_EVENT_OPTION_CLEAR. The argument @c reset gives
 * K_EVENT_OPTION_RESET (see @ref kernel_unit_event_static).
 *
 * @par Functions in kernel/events.c
 * - z_impl_k_event_wait_all()
 * - z_vrfy_k_event_wait_all(), with @kconfig{CONFIG_USERSPACE}
 */

/**
 * @defgroup kernel_unit_event_k_event_wait_safe k_event_wait_safe()
 * @ingroup kernel_unit_event
 * @brief k_event_wait_safe() waits for any one event of a request, and consumes the events that
 * it receives.
 *
 * k_event_wait_safe() calls k_event_wait_internal() with
 * K_EVENT_OPTION_CLEAR and without K_EVENT_WAIT_ALL. The argument @c reset
 * gives K_EVENT_OPTION_RESET (see @ref kernel_unit_event_static).
 *
 * @par Functions in kernel/events.c
 * - z_impl_k_event_wait_safe()
 * - z_vrfy_k_event_wait_safe(), with @kconfig{CONFIG_USERSPACE}
 */

/**
 * @defgroup kernel_unit_event_k_event_wait_all_safe k_event_wait_all_safe()
 * @ingroup kernel_unit_event
 * @brief k_event_wait_all_safe() waits for all events of a request, and consumes them.
 *
 * k_event_wait_all_safe() calls k_event_wait_internal() with
 * K_EVENT_WAIT_ALL and K_EVENT_OPTION_CLEAR. The argument @c reset gives
 * K_EVENT_OPTION_RESET (see @ref kernel_unit_event_static).
 *
 * @par Functions in kernel/events.c
 * - z_impl_k_event_wait_all_safe()
 * - z_vrfy_k_event_wait_all_safe(), with @kconfig{CONFIG_USERSPACE}
 */

/**
 * @defgroup kernel_unit_event_static Static functions and data
 * @ingroup kernel_unit_event
 * @brief The static functions of events.c, and the data that events.c defines.
 *
 * @par Wait conditions
 * are_wait_conditions_met() gives the events of a request that a set
 * satisfies.
 * The function has three inputs: the desired events of a request, the
 * current set, and the wait condition (any or all). It returns the
 * matching events (desired AND current), or 0 if the condition is not met.
 * The result is the value that a wait returns. The post walk and the wait
 * functions both use this function, so both apply the same condition.
 *
 * @par Post, set and clear
 * The four post operations change the bits in a mask and return the old
 * value of these bits.
 * k_event_post(), k_event_set(), k_event_set_masked() and k_event_clear()
 * are calls of k_event_post_internal() with different values of events
 * and mask (see @ref kernel_unit_event). The new set is
 * (old AND NOT mask) OR (events AND mask). Each operation then walks the
 * wait queue, also if the set did not change. The tests of this rule have
 * no waiting thread.
 *
 * @par Wake of waiting threads
 * A post wakes each waiting thread whose condition the new set satisfies,
 * and gives it the matching events.
 * The walk callback event_walk_op() examines one waiting thread. If the
 * new set satisfies the condition of the thread, the callback writes the
 * matching events into @c thread->events and stops the timeout of the
 * thread with z_try_abort_thread_timeout(). Then the thread gets the
 * return value 0 (arch_thread_return_value_set()) and is made ready
 * (z_sched_wake_thread_locked()). With @kconfig{CONFIG_WAITQ_SCALABLE},
 * these two calls occur in event_post_walk_op() after the walk.
 *
 * The callback always returns 0, so the walk examines all waiting
 * threads. A thread whose condition is not met stays in the wait queue
 * without a change.
 *
 * @par Consumed events
 * A thread with the option K_EVENT_OPTION_CLEAR consumes the events that
 * it receives.
 * k_event_wait_safe() and k_event_wait_all_safe() set the option
 * K_EVENT_OPTION_CLEAR. If the set already satisfies the condition, the
 * wait removes the matching events from the set before it releases the
 * lock. If the thread waits, the post that wakes the thread collects the
 * matching events in @c clear_events of the walk data, and removes them
 * from the set after the walk. Thus all threads that one post wakes see
 * the same set. A consumed event can wake more than one thread in the same
 * post.
 *
 * @par Wait
 * A wait returns the matching events at once, returns 0, or lets the
 * current thread wait.
 * k_event_wait_internal() first returns 0 for an empty request. Then it
 * gets the current thread, locks the event, applies the option RESET and
 * checks the condition. If the condition is met, it returns the matching
 * events. If not, and the timeout is K_NO_WAIT, it returns 0. Else it
 * writes the request (@c events, @c event_options) into the current thread
 * and calls z_pend_curr(). After a wake with the result 0, it returns
 * @c thread->events, which the post wrote. After a timeout, it returns 0.
 *
 * A wait in an ISR must use K_NO_WAIT. With @kconfig{CONFIG_ASSERT}, the
 * wait asserts this. In an ISR, a wait with a timeout reaches z_pend_curr(),
 * and the scheduler refuses it with a panic in every build. Without
 * @kconfig{CONFIG_ASSERT}, events.c has no earlier check of its own.
 *
 * @par Functions in kernel/events.c
 * - are_wait_conditions_met()
 * - event_post_walk_op(), with @kconfig{CONFIG_WAITQ_SCALABLE}
 * - event_walk_op()
 * - k_event_post_internal()
 * - k_event_wait_internal()
 *
 * The tests in this group call are_wait_conditions_met(), event_walk_op()
 * or event_post_walk_op() directly, or they call more than one public
 * function to show a rule of k_event_post_internal() or
 * k_event_wait_internal().
 *
 * @par Data in kernel/events.c
 * - @c obj_type_event and its descriptor (K_OBJ_TYPE_DEFINE()), with
 *   @kconfig{CONFIG_OBJ_CORE_EVENT}. The tests of the descriptor are in this
 *   group.
 */

#include <string.h>
#include <zephyr/ztest.h>
#include <kernel_unit.h>
#include <kernel_unit_models.h>
#include <fakes/scheduler.h>
#ifdef CONFIG_OBJ_CORE
#include <fakes/obj_core.h>
#endif
#ifdef CONFIG_USERSPACE
#include <fakes/kobject.h>
#endif
#ifdef CONFIG_ASSERT
#include <fakes/assert.h>
#endif

#include <kernel/events.c>

/* Value that fills an object before a test, to show what the unit writes. */
#define FILL KERNEL_UNIT_FILL

/* Timeout that is not K_NO_WAIT and not K_FOREVER */
#define TEST_TIMEOUT K_TICKS(10)

/* Some events. EV_D is the highest bit, to show that all 32 bits are events. */
#define EV_A BIT(0)
#define EV_B BIT(1)
#define EV_C BIT(4)
#define EV_D BIT(31)

/* Value of a spy record before the spy fake runs */
#define UNSET 0xDEADBEEFU

/* Number of the threads that wait in a test */
#define N_WAITERS 4

/* The current thread of the test: the thread that calls a wait function. */
static struct k_thread current_thread;

/* Threads of the test that wait on the event. */
static struct k_thread waiters[N_WAITERS];
static struct k_thread *const t1 = &waiters[0];
static struct k_thread *const t2 = &waiters[1];
static struct k_thread *const t3 = &waiters[2];

/*
 * Kernel-mode entry point of the system call k_event_wait(). Without
 * CONFIG_USERSPACE, the generated file zephyr/syscalls/kernel.h makes the
 * system call a call of z_impl_k_event_wait(). The unittest build does not
 * generate this file, so the test defines the entry point that
 * k_event_test() in zephyr/kernel.h uses.
 */
uint32_t k_event_wait(struct k_event *event, uint32_t events, bool reset, k_timeout_t timeout)
{
	return z_impl_k_event_wait(event, events, reset, timeout);
}

/*
 * Model of the wait queue: the waiting threads in wait queue order. The
 * fake z_sched_waitq_walk() walks this array.
 */
static struct k_thread *wait_queue[N_WAITERS + 1];
static size_t n_waiting;

/* The event that the spy fakes read, and their records. */
static struct k_event *spied_event;
static uint32_t events_at_lock;
static uint32_t events_at_walk;
static uint32_t events_at_release;
static unsigned int locks_at_walk;
static unsigned int releases_at_walk;

/*
 * Fake z_sched_waitq_walk(), as the real function in kernel/scheduler.c:
 * call walk_func for each waiting thread until it returns a value other
 * than 0, then call post_func (if not NULL) with this value. The walk uses
 * a copy of the array, so a wake can remove the thread (as
 * _WAIT_Q_FOR_EACH_SAFE()).
 */
static int walk_model(_wait_q_t *wait_q, _waitq_walk_cb_t walk_func,
		      _waitq_post_walk_cb_t post_func, void *data)
{
	struct k_thread *snapshot[N_WAITERS + 1];
	size_t n = n_waiting;
	int status = 0;

	ARG_UNUSED(wait_q);

	memcpy(snapshot, wait_queue, sizeof(snapshot));
	locks_at_walk = unit_arch_irq_lock_fake.call_count;
	releases_at_walk = kernel_unit_release_count();
	if (spied_event != NULL) {
		events_at_walk = spied_event->events;
	}

	for (size_t i = 0; i < n; i++) {
		status = walk_func(snapshot[i], data);
		if (status != 0) {
			break;
		}
	}

	if (post_func != NULL) {
		post_func(status, data);
	}

	return status;
}

/* Fake z_sched_wake_thread_locked(): the thread leaves the wait queue. */
static void wake_model(struct k_thread *thread)
{
	for (size_t i = 0; i < n_waiting; i++) {
		if (wait_queue[i] == thread) {
			memmove(&wait_queue[i], &wait_queue[i + 1],
				(n_waiting - i - 1) * sizeof(wait_queue[0]));
			n_waiting--;
			break;
		}
	}
}

/* Let a thread wait on the event for these events, with these options. */
static void add_waiter(struct k_thread *thread, uint32_t events, uint32_t options)
{
	zassert_true(n_waiting < N_WAITERS, "too many waiting threads");
	thread->events = events;
	thread->event_options = options;
	wait_queue[n_waiting++] = thread;
}

/* Return true if the post woke this thread. */
static bool woken(struct k_thread *thread)
{
	for (unsigned int i = 0; i < z_sched_wake_thread_locked_fake.call_count; i++) {
		if (z_sched_wake_thread_locked_fake.arg0_history[i] == thread) {
			return true;
		}
	}

	return false;
}

/*
 * Return the value that the unit gave to arch_thread_return_value_set()
 * for this thread, or UNSET.
 */
static unsigned int return_value_of(struct k_thread *thread)
{
	for (unsigned int i = 0; i < arch_thread_return_value_set_fake.call_count; i++) {
		if (arch_thread_return_value_set_fake.arg0_history[i] == thread) {
			return arch_thread_return_value_set_fake.arg1_history[i];
		}
	}

	return UNSET;
}

/* Put an event object into a known state without k_event_init(). */
static void event_prepare(struct k_event *event, uint32_t events)
{
	memset(event, 0, sizeof(*event));
	event->events = events;
}

/* Observers of the lock spies (kernel_unit_spy_on_lock()). */
static void observe_lock(void)
{
	events_at_lock = spied_event->events;
}

static void observe_release(void)
{
	events_at_release = spied_event->events;
}

/* Install the spy fakes of the lock and of the release paths. */
static void spy_on_lock(struct k_event *event)
{
	spied_event = event;
	events_at_lock = UNSET;
	events_at_walk = UNSET;
	events_at_release = UNSET;
	kernel_unit_spy_on_lock(observe_lock, observe_release);
}

/*
 * Fake z_pend_curr() for a wait with a fixed result: the scheduler wakes
 * the thread with pend_result, and the waker wrote pend_events into the
 * thread. The spy records the wait request of the thread at the call.
 */
static int pend_result;
static uint32_t pend_events;
static uint32_t events_at_pend;
static uint32_t options_at_pend;

static int pend_model(struct k_spinlock *lock, k_spinlock_key_t key, _wait_q_t *wait_q,
		      k_timeout_t timeout)
{
	ARG_UNUSED(lock);
	ARG_UNUSED(key);
	ARG_UNUSED(wait_q);
	ARG_UNUSED(timeout);

	events_at_pend = current_thread.events;
	options_at_pend = current_thread.event_options;
	current_thread.events = pend_events;

	return pend_result;
}

/* Let a wait function wait, and give it this result and these events after the wait. */
static void set_wait_result(int result, uint32_t events)
{
	pend_result = result;
	pend_events = events;
	events_at_pend = UNSET;
	options_at_pend = UNSET;
	z_pend_curr_fake.custom_fake = pend_model;
}

/*
 * Hand-over tests (kernel_unit_set_other_thread()): the current thread waits
 * on the wait queue model, then "another thread" posts handover_events to
 * handover_event. If the post woke the current thread, the wait returns
 * the value that the post gave to arch_thread_return_value_set().
 * Otherwise the wait times out with -EAGAIN.
 */
static struct k_event *handover_event;
static uint32_t handover_events;

static void other_thread_posts(void)
{
	wait_queue[n_waiting++] = &current_thread;
	(void)z_impl_k_event_post(handover_event, handover_events);

	if (woken(&current_thread)) {
		kernel_unit_wake_current((int)return_value_of(&current_thread));
	}
}

static void set_handover(struct k_event *event, uint32_t events)
{
	handover_event = event;
	handover_events = events;
	kernel_unit_set_other_thread(other_thread_posts, false);
}

/* Return true if fn is a call that a wait function makes before the lock. */
static bool call_before_lock(fff_function_t fn)
{
	return (fn == KERNEL_UNIT_FN(arch_is_in_isr)) ||
	       (fn == KERNEL_UNIT_FN(k_sched_current_thread_query));
}

/*
 * Assert the lock invariant of one operation on the event
 * (kernel_unit_models.h). Before the lock, the operation only reads the
 * context (arch_is_in_isr() for an assertion,
 * k_sched_current_thread_query()).
 */
static void assert_lock_released_once(struct k_event *event, enum kernel_unit_release how)
{
	kernel_unit_assert_lock_rule(&(const struct kernel_unit_lock_rule){
		.lock = &event->lock, .how = how, .before_lock = call_before_lock});
}

static void event_unit_before(void *fixture)
{
	ARG_UNUSED(fixture);

	/* The fake rules reset all fakes before this function. */
	unit_arch_irq_lock_fake.return_val = KERNEL_UNIT_IRQ_KEY;
	z_sched_waitq_walk_fake.custom_fake = walk_model;
	z_sched_wake_thread_locked_fake.custom_fake = wake_model;
	k_sched_current_thread_query_fake.return_val = &current_thread;

	memset(&current_thread, 0, sizeof(current_thread));
	memset(waiters, 0, sizeof(waiters));
	memset(wait_queue, 0, sizeof(wait_queue));
	n_waiting = 0;
	spied_event = NULL;
	locks_at_walk = UNSET;
	releases_at_walk = UNSET;
	events_at_walk = UNSET;
}

ZTEST_SUITE(event_unit, NULL, NULL, event_unit_before, NULL, NULL);

/*
 * Tests: Initialization. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_event, at the top of this file.
 */

/**
 * @brief k_event_init() makes the set of events empty.
 *
 * @details
 * - Setup: an event object filled with a pattern.
 * - Action: z_impl_k_event_init().
 * - Expected: the set of events is 0.
 *
 * @ingroup kernel_unit_event_k_event_init
 * @see z_impl_k_event_init()
 */
ZTEST(event_unit, test_init_clears_events)
{
	struct k_event event;

	memset(&event, FILL, sizeof(event));

	z_impl_k_event_init(&event);

	zassert_equal(event.events, 0U);
}

/**
 * @brief k_event_init() sets the lock of the event object to its initial value.
 *
 * @details
 * - Setup: an event object filled with a pattern.
 * - Action: z_impl_k_event_init().
 * - Expected: all bytes of the lock are 0 (the value of an unlocked
 *   spinlock).
 *
 * @ingroup kernel_unit_event_k_event_init
 * @see z_impl_k_event_init()
 */
ZTEST(event_unit, test_init_resets_lock)
{
	struct k_event event;
	const struct k_spinlock unlocked = {};

	memset(&event, FILL, sizeof(event));

	z_impl_k_event_init(&event);

	zassert_mem_equal(&event.lock, &unlocked, sizeof(unlocked));
}

/**
 * @brief k_event_init() initializes the wait queue of the event object.
 *
 * @details
 * - Action: z_impl_k_event_init().
 * - Expected: one call of z_waitq_init() with the wait queue of the event.
 *
 * @ingroup kernel_unit_event_k_event_init
 * @see z_impl_k_event_init()
 */
ZTEST(event_unit, test_init_initializes_wait_queue)
{
	struct k_event event;

	z_impl_k_event_init(&event);

	zassert_equal(z_waitq_init_fake.call_count, 1);
	zassert_equal_ptr(z_waitq_init_fake.arg0_val, &event.wait_q);
}

#ifdef CONFIG_USERSPACE
/**
 * @brief With CONFIG_USERSPACE, k_event_init() marks the event object as an initialized kernel
 * object.
 *
 * @details
 * - Action: z_impl_k_event_init().
 * - Expected: one call of k_object_init() with the event object.
 *
 * @ingroup kernel_unit_event_k_event_init
 * @see z_impl_k_event_init()
 */
ZTEST(event_unit, test_init_initializes_kernel_object)
{
	struct k_event event;

	z_impl_k_event_init(&event);

	zassert_equal(k_object_init_fake.call_count, 1);
	zassert_equal_ptr(k_object_init_fake.arg0_val, &event);
}
#endif /* CONFIG_USERSPACE */

/**
 * @brief k_event_init() initializes the wait queue, then the kernel object, then the object core,
 * and does not lock the event.
 *
 * @details
 * - Action: z_impl_k_event_init() in a thread.
 * - Expected calls, in this order: arch_is_in_isr() (with CONFIG_ASSERT),
 *   z_waitq_init(), k_object_init() (with CONFIG_USERSPACE),
 *   k_obj_core_init_and_link() (with CONFIG_OBJ_CORE_EVENT). No other
 *   call, in particular no lock.
 *
 * @ingroup kernel_unit_event_k_event_init
 * @see z_impl_k_event_init()
 */
ZTEST(event_unit, test_init_call_order)
{
	struct k_event event;

	z_impl_k_event_init(&event);

	zassert_call_history(
		KERNEL_UNIT_IF_ENABLED(CONFIG_ASSERT, arch_is_in_isr), z_waitq_init,
		KERNEL_UNIT_IF_ENABLED(CONFIG_USERSPACE, k_object_init),
		KERNEL_UNIT_IF_ENABLED(CONFIG_OBJ_CORE_EVENT, k_obj_core_init_and_link));
	zassert_equal(unit_arch_irq_lock_fake.call_count, 0);
}

#ifdef CONFIG_ASSERT
/**
 * @brief With CONFIG_ASSERT, k_event_init() asserts that it does not run in an ISR.
 *
 * @details
 * - Setup: arch_is_in_isr() returns true.
 * - Action: z_impl_k_event_init().
 * - Expected: one failed assertion, before z_waitq_init(). In a thread
 *   (arch_is_in_isr() returns false), no failed assertion.
 *
 * @ingroup kernel_unit_event_k_event_init
 * @see z_impl_k_event_init()
 */
ZTEST(event_unit, test_init_asserts_not_in_isr)
{
	struct k_event event;

	z_impl_k_event_init(&event);
	zassert_equal(assert_post_action_fake.call_count, 0);

	RESET_FAKE(z_waitq_init);
	FFF_RESET_HISTORY();
	arch_is_in_isr_fake.return_val = true;

	z_impl_k_event_init(&event);

	zassert_equal(assert_post_action_fake.call_count, 1);
	zassert_called_before(assert_post_action, z_waitq_init);
}
#endif /* CONFIG_ASSERT */

/*
 * Tests: Wait conditions. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_event, at the top of this file.
 */

/**
 * @brief For the condition "any", the result is the set of desired events that are in the set,
 * and no other event.
 *
 * @details
 * - Action: are_wait_conditions_met(A|B|C, A|C|D, K_EVENT_WAIT_ANY).
 * - Expected: A|C. D is in the set, but not desired.
 *
 * @ingroup kernel_unit_event_static
 * @see are_wait_conditions_met()
 */
ZTEST(event_unit, test_match_any_returns_matching_events)
{
	zassert_equal(
		are_wait_conditions_met(EV_A | EV_B | EV_C, EV_A | EV_C | EV_D, K_EVENT_WAIT_ANY),
		EV_A | EV_C);
}

/**
 * @brief For the condition "any", the result is 0 if no desired event is in the set.
 *
 * @details
 * - Action: are_wait_conditions_met(A|B, C|D, K_EVENT_WAIT_ANY).
 * - Expected: 0.
 *
 * @ingroup kernel_unit_event_static
 * @see are_wait_conditions_met()
 */
ZTEST(event_unit, test_match_any_without_overlap_is_zero)
{
	zassert_equal(are_wait_conditions_met(EV_A | EV_B, EV_C | EV_D, K_EVENT_WAIT_ANY), 0U);
}

/**
 * @brief For the condition "all", the result is the desired set if all desired events are in the
 * set.
 *
 * @details
 * - Action: are_wait_conditions_met(A|D, A|C|D, K_EVENT_WAIT_ALL).
 * - Expected: A|D. C is in the set, but not desired.
 *
 * @ingroup kernel_unit_event_static
 * @see are_wait_conditions_met()
 */
ZTEST(event_unit, test_match_all_returns_desired_events)
{
	zassert_equal(are_wait_conditions_met(EV_A | EV_D, EV_A | EV_C | EV_D, K_EVENT_WAIT_ALL),
		      EV_A | EV_D);
}

/**
 * @brief For the condition "all", the result is 0 if one desired event is not in the set, also if
 * other desired events are in it.
 *
 * @details
 * - Action: are_wait_conditions_met(A|B|D, A|D, K_EVENT_WAIT_ALL).
 * - Expected: 0 (B is missing), not A|D.
 *
 * @ingroup kernel_unit_event_static
 * @see are_wait_conditions_met()
 */
ZTEST(event_unit, test_match_all_partial_is_zero)
{
	zassert_equal(are_wait_conditions_met(EV_A | EV_B | EV_D, EV_A | EV_D, K_EVENT_WAIT_ALL),
		      0U);
}

/**
 * @brief An empty desired set never satisfies a condition.
 *
 * @details
 * - Action: are_wait_conditions_met(0, all events, any) and
 *   are_wait_conditions_met(0, all events, all).
 * - Expected: 0 in both cases. For "all", the match (0) is equal to the
 *   desired set, but the result is the match, so it is 0.
 *
 * @ingroup kernel_unit_event_static
 * @see are_wait_conditions_met()
 */
ZTEST(event_unit, test_match_empty_request_is_zero)
{
	zassert_equal(are_wait_conditions_met(0U, UINT32_MAX, K_EVENT_WAIT_ANY), 0U);
	zassert_equal(are_wait_conditions_met(0U, UINT32_MAX, K_EVENT_WAIT_ALL), 0U);
}

/*
 * Tests: Post, set and clear. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_event, at the top of this file.
 */

/**
 * @brief k_event_post() adds the events to the set and returns the old value of the posted
 * events.
 *
 * @details
 * - Setup: an event object with the set A|C.
 * - Action: z_impl_k_event_post(B|C).
 * - Expected: return value C (of B|C, only C was set). The set is A|B|C.
 *
 * @ingroup kernel_unit_event_k_event_post
 * @see z_impl_k_event_post()
 */
ZTEST(event_unit, test_post_adds_events)
{
	struct k_event event;

	event_prepare(&event, EV_A | EV_C);

	zassert_equal(z_impl_k_event_post(&event, EV_B | EV_C), EV_C);
	zassert_equal(event.events, EV_A | EV_B | EV_C);
}

/**
 * @brief k_event_set() replaces the set and returns the old set.
 *
 * @details
 * - Setup: an event object with the set A|C.
 * - Action: z_impl_k_event_set(B|D).
 * - Expected: return value A|C. The set is B|D.
 *
 * @ingroup kernel_unit_event_k_event_set
 * @see z_impl_k_event_set()
 */
ZTEST(event_unit, test_set_replaces_events)
{
	struct k_event event;

	event_prepare(&event, EV_A | EV_C);

	zassert_equal(z_impl_k_event_set(&event, EV_B | EV_D), EV_A | EV_C);
	zassert_equal(event.events, EV_B | EV_D);
}

/**
 * @brief k_event_set_masked() changes only the events in the mask and returns the old value of
 * these events.
 *
 * @details
 * - Setup: an event object with the set A|C.
 * - Action: z_impl_k_event_set_masked(events B|D, mask A|B).
 * - Expected: return value A (of A|B, only A was set). A is cleared and B
 *   is set (both in the mask). C stays (not in the mask). D is not set (not
 *   in the mask). The set is B|C.
 *
 * @ingroup kernel_unit_event_k_event_set_masked
 * @see z_impl_k_event_set_masked()
 */
ZTEST(event_unit, test_set_masked_changes_only_masked_events)
{
	struct k_event event;

	event_prepare(&event, EV_A | EV_C);

	zassert_equal(z_impl_k_event_set_masked(&event, EV_B | EV_D, EV_A | EV_B), EV_A);
	zassert_equal(event.events, EV_B | EV_C);
}

/**
 * @brief k_event_clear() removes the events from the set and returns the old value of these
 * events.
 *
 * @details
 * - Setup: an event object with the set A|C|D.
 * - Action: z_impl_k_event_clear(B|C).
 * - Expected: return value C. The set is A|D.
 *
 * @ingroup kernel_unit_event_k_event_clear
 * @see z_impl_k_event_clear()
 */
ZTEST(event_unit, test_clear_removes_events)
{
	struct k_event event;

	event_prepare(&event, EV_A | EV_C | EV_D);

	zassert_equal(z_impl_k_event_clear(&event, EV_B | EV_C), EV_C);
	zassert_equal(event.events, EV_A | EV_D);
}

/**
 * @brief Each post operation walks the wait queue of its event object, also if the set does not
 * change.
 *
 * @details
 * - Setup: an event object with the set A. No thread waits.
 * - Action: z_impl_k_event_post(A), z_impl_k_event_set(A),
 *   z_impl_k_event_set_masked(0, B), z_impl_k_event_clear(B). Not one of
 *   them changes the set.
 * - Expected: 4 calls of z_sched_waitq_walk(), each with the wait queue of
 *   the event and the walk callback event_walk_op(). The post-walk callback
 *   is event_post_walk_op() with CONFIG_WAITQ_SCALABLE, else NULL. The set
 *   is A.
 *
 * @ingroup kernel_unit_event_static
 * @see k_event_post_internal()
 */
ZTEST(event_unit, test_post_always_walks_wait_queue)
{
	struct k_event event;

	event_prepare(&event, EV_A);

	(void)z_impl_k_event_post(&event, EV_A);
	(void)z_impl_k_event_set(&event, EV_A);
	(void)z_impl_k_event_set_masked(&event, 0U, EV_B);
	(void)z_impl_k_event_clear(&event, EV_B);

	zassert_equal(z_sched_waitq_walk_fake.call_count, 4);
	for (unsigned int i = 0; i < 4; i++) {
		zassert_equal_ptr(z_sched_waitq_walk_fake.arg0_history[i], &event.wait_q);
		zassert_equal_ptr(z_sched_waitq_walk_fake.arg1_history[i], event_walk_op);
#ifdef CONFIG_WAITQ_SCALABLE
		zassert_equal_ptr(z_sched_waitq_walk_fake.arg2_history[i], event_post_walk_op);
#else
		zassert_is_null(z_sched_waitq_walk_fake.arg2_history[i]);
#endif
	}
	zassert_equal(event.events, EV_A);
}

/**
 * @brief k_event_post() and k_event_set() use all 32 bits of the set.
 *
 * @details
 * - Setup: an empty event object.
 * - Action: z_impl_k_event_post(D) (bit 31), then z_impl_k_event_set(all
 *   bits), then z_impl_k_event_clear(all bits).
 * - Expected: the set is D, then all bits (return value D), then 0
 *   (return value all bits).
 *
 * @ingroup kernel_unit_event_k_event_post
 * @see z_impl_k_event_post()
 * @see z_impl_k_event_set()
 * @see z_impl_k_event_clear()
 */
ZTEST(event_unit, test_post_uses_all_32_bits)
{
	struct k_event event;

	event_prepare(&event, 0U);

	zassert_equal(z_impl_k_event_post(&event, EV_D), 0U);
	zassert_equal(event.events, EV_D);
	zassert_equal(z_impl_k_event_set(&event, UINT32_MAX), EV_D);
	zassert_equal(event.events, UINT32_MAX);
	zassert_equal(z_impl_k_event_clear(&event, UINT32_MAX), UINT32_MAX);
	zassert_equal(event.events, 0U);
}

/*
 * Tests: Wake of waiting threads. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_event, at the top of this file.
 */

/**
 * @brief A post wakes a waiting thread whose "any" condition the new set satisfies, and gives it
 * only the matching events.
 *
 * @details
 * - Setup: an empty event object. Thread t1 waits for A|B (any).
 * - Action: z_impl_k_event_post(B|C).
 * - Expected: t1->events is B. Calls for t1, in this order:
 *   z_try_abort_thread_timeout(), arch_thread_return_value_set() with 0,
 *   z_sched_wake_thread_locked(). The set is B|C.
 *
 * @ingroup kernel_unit_event_k_event_post
 * @see z_impl_k_event_post()
 * @see k_event_post_internal()
 * @see event_walk_op()
 */
ZTEST(event_unit, test_wake_any_gives_matching_events)
{
	struct k_event event;

	event_prepare(&event, 0U);
	add_waiter(t1, EV_A | EV_B, K_EVENT_WAIT_ANY);

	(void)z_impl_k_event_post(&event, EV_B | EV_C);

	zassert_equal(t1->events, EV_B);
	zassert_call_history(unit_arch_irq_lock, z_sched_waitq_walk, z_try_abort_thread_timeout,
			     arch_thread_return_value_set, z_sched_wake_thread_locked,
			     z_reschedule);
	zassert_equal_ptr(z_try_abort_thread_timeout_fake.arg0_val, t1);
	zassert_equal_ptr(arch_thread_return_value_set_fake.arg0_val, t1);
	zassert_equal(arch_thread_return_value_set_fake.arg1_val, 0U);
	zassert_equal_ptr(z_sched_wake_thread_locked_fake.arg0_val, t1);
	zassert_equal(event.events, EV_B | EV_C);
}

/**
 * @brief A post does not wake a waiting thread whose condition the new set does not satisfy, and
 * does not change this thread.
 *
 * @details
 * - Setup: an empty event object. Thread t1 waits for A|B (any).
 * - Action: z_impl_k_event_post(C).
 * - Expected: no call of z_try_abort_thread_timeout(),
 *   arch_thread_return_value_set() or z_sched_wake_thread_locked().
 *   t1->events is A|B and t1->event_options is unchanged. The set is C.
 *
 * @ingroup kernel_unit_event_k_event_post
 * @see z_impl_k_event_post()
 * @see event_walk_op()
 */
ZTEST(event_unit, test_wake_not_for_unmatched_thread)
{
	struct k_event event;

	event_prepare(&event, 0U);
	add_waiter(t1, EV_A | EV_B, K_EVENT_WAIT_ANY);

	(void)z_impl_k_event_post(&event, EV_C);

	zassert_equal(z_try_abort_thread_timeout_fake.call_count, 0);
	zassert_equal(arch_thread_return_value_set_fake.call_count, 0);
	zassert_equal(z_sched_wake_thread_locked_fake.call_count, 0);
	zassert_equal(t1->events, EV_A | EV_B);
	zassert_equal(t1->event_options, K_EVENT_WAIT_ANY);
	zassert_equal(event.events, EV_C);
}

/**
 * @brief A post wakes a thread with the condition "all" only when the new set has all events of
 * the thread, and then gives it the desired set.
 *
 * @details
 * - Setup: an empty event object. Thread t1 waits for A|B (all).
 * - Action: z_impl_k_event_post(A), then z_impl_k_event_post(B|C).
 * - Expected: after the first post, t1 is not woken and t1->events is
 *   A|B. After the second post (the set is A|B|C), t1 is woken and
 *   t1->events is A|B, without C.
 *
 * @ingroup kernel_unit_event_k_event_post
 * @see z_impl_k_event_post()
 * @see event_walk_op()
 */
ZTEST(event_unit, test_wake_all_needs_all_events)
{
	struct k_event event;

	event_prepare(&event, 0U);
	add_waiter(t1, EV_A | EV_B, K_EVENT_WAIT_ALL);

	(void)z_impl_k_event_post(&event, EV_A);

	zassert_false(woken(t1));
	zassert_equal(t1->events, EV_A | EV_B);

	(void)z_impl_k_event_post(&event, EV_B | EV_C);

	zassert_true(woken(t1));
	zassert_equal(t1->events, EV_A | EV_B);
}

/**
 * @brief One post wakes all waiting threads whose conditions the new set satisfies, and only
 * these.
 *
 * @details
 * - Setup: an empty event object. t1 waits for A (any), t2 waits for A|B
 *   (all), t3 waits for C|D (any).
 * - Action: z_impl_k_event_set(A|D).
 * - Expected: t1 is woken with A, t3 is woken with D. t2 is not woken and
 *   stays in the wait queue. One walk and one z_reschedule().
 *
 * @ingroup kernel_unit_event_k_event_set
 * @see z_impl_k_event_set()
 * @see k_event_post_internal()
 * @see event_walk_op()
 */
ZTEST(event_unit, test_wake_all_satisfied_threads)
{
	struct k_event event;

	event_prepare(&event, 0U);
	add_waiter(t1, EV_A, K_EVENT_WAIT_ANY);
	add_waiter(t2, EV_A | EV_B, K_EVENT_WAIT_ALL);
	add_waiter(t3, EV_C | EV_D, K_EVENT_WAIT_ANY);

	(void)z_impl_k_event_set(&event, EV_A | EV_D);

	zassert_true(woken(t1));
	zassert_equal(t1->events, EV_A);
	zassert_false(woken(t2));
	zassert_equal(t2->events, EV_A | EV_B);
	zassert_true(woken(t3));
	zassert_equal(t3->events, EV_D);
	zassert_equal(z_sched_wake_thread_locked_fake.call_count, 2);
	zassert_equal(n_waiting, 1);
	zassert_equal_ptr(wait_queue[0], t2);
	zassert_equal(z_sched_waitq_walk_fake.call_count, 1);
	zassert_equal(z_reschedule_fake.call_count, 1);
}

/**
 * @brief The walk callback returns 0 for each thread, so the walk examines all waiting threads.
 *
 * @details
 * - Setup: t1 waits for A (any), t2 waits for B (any). Walk data with the
 *   set A.
 * - Action: event_walk_op() for t1 (match) and for t2 (no match).
 * - Expected: both calls return 0.
 *
 * @ingroup kernel_unit_event_static
 * @see event_walk_op()
 */
ZTEST(event_unit, test_wake_walk_never_stops)
{
	struct event_walk_data data = {.events = EV_A};

	t1->events = EV_A;
	t2->events = EV_B;

	zassert_equal(event_walk_op(t1, &data), 0);
	zassert_equal(event_walk_op(t2, &data), 0);
}

/**
 * @brief The walk callback wakes a thread also if the timeout of the thread cannot be stopped.
 *
 * @details
 * - Setup: an empty event object. t1 waits for A (any).
 *   z_try_abort_thread_timeout() returns -EINVAL (the timeout has already
 *   expired).
 * - Action: z_impl_k_event_post(A).
 * - Expected: t1 is woken with the return value 0 and the events A.
 *
 * @ingroup kernel_unit_event_k_event_post
 * @see z_impl_k_event_post()
 * @see event_walk_op()
 */
ZTEST(event_unit, test_wake_ignores_timeout_abort_result)
{
	struct k_event event;

	event_prepare(&event, 0U);
	add_waiter(t1, EV_A, K_EVENT_WAIT_ANY);
	z_try_abort_thread_timeout_fake.return_val = -EINVAL;

	(void)z_impl_k_event_post(&event, EV_A);

	zassert_true(woken(t1));
	zassert_equal(return_value_of(t1), 0U);
	zassert_equal(t1->events, EV_A);
}

/**
 * @brief The walk callback reads the condition from bit 0 of the thread options only.
 *
 * @details
 * - Setup: t1 waits for A|B with the options CLEAR|RESET (any). t2 waits
 *   for A|B with the options CLEAR|RESET|WAIT_ALL. Walk data with the set
 *   A.
 * - Action: event_walk_op() for t1 and t2.
 * - Expected: t1 matches with A ("any"). t2 does not match ("all").
 *
 * @ingroup kernel_unit_event_static
 * @see event_walk_op()
 */
ZTEST(event_unit, test_wake_condition_from_option_bit)
{
	struct event_walk_data data = {.events = EV_A};

	t1->events = EV_A | EV_B;
	t1->event_options = K_EVENT_OPTION_CLEAR | K_EVENT_OPTION_RESET;
	t2->events = EV_A | EV_B;
	t2->event_options = K_EVENT_OPTION_CLEAR | K_EVENT_OPTION_RESET | K_EVENT_WAIT_ALL;

	(void)event_walk_op(t1, &data);
	(void)event_walk_op(t2, &data);

	zassert_equal(t1->events, EV_A);
	zassert_equal(t2->events, EV_A | EV_B);
	zassert_equal(z_try_abort_thread_timeout_fake.call_count, 1);
	zassert_equal_ptr(z_try_abort_thread_timeout_fake.arg0_val, t1);
}

#ifndef CONFIG_WAITQ_SCALABLE
/**
 * @brief Without CONFIG_WAITQ_SCALABLE, the walk callback wakes each satisfied thread at once, in
 * the order of the wait queue.
 *
 * @details
 * - Setup: an empty event object. t1, t2 and t3 wait for A (any), in this
 *   order.
 * - Action: z_impl_k_event_post(A).
 * - Expected calls: for t1, then t2, then t3, each
 *   z_try_abort_thread_timeout(), arch_thread_return_value_set(),
 *   z_sched_wake_thread_locked(). All between the walk and
 *   z_reschedule().
 *
 * @ingroup kernel_unit_event_k_event_post
 * @see z_impl_k_event_post()
 * @see event_walk_op()
 */
ZTEST(event_unit, test_wake_simple_in_wait_queue_order)
{
	struct k_event event;

	event_prepare(&event, 0U);
	add_waiter(t1, EV_A, K_EVENT_WAIT_ANY);
	add_waiter(t2, EV_A, K_EVENT_WAIT_ANY);
	add_waiter(t3, EV_A, K_EVENT_WAIT_ANY);

	(void)z_impl_k_event_post(&event, EV_A);

	zassert_call_history(unit_arch_irq_lock, z_sched_waitq_walk, z_try_abort_thread_timeout,
			     arch_thread_return_value_set, z_sched_wake_thread_locked,
			     z_try_abort_thread_timeout, arch_thread_return_value_set,
			     z_sched_wake_thread_locked, z_try_abort_thread_timeout,
			     arch_thread_return_value_set, z_sched_wake_thread_locked,
			     z_reschedule);
	zassert_equal_ptr(z_sched_wake_thread_locked_fake.arg0_history[0], t1);
	zassert_equal_ptr(z_sched_wake_thread_locked_fake.arg0_history[1], t2);
	zassert_equal_ptr(z_sched_wake_thread_locked_fake.arg0_history[2], t3);
}
#endif /* !CONFIG_WAITQ_SCALABLE */

#ifdef CONFIG_WAITQ_SCALABLE
/**
 * @brief With CONFIG_WAITQ_SCALABLE, the walk callback only collects the satisfied threads, and
 * the post-walk callback wakes them in the reverse order of the wait queue.
 *
 * @details
 * - Setup: an empty event object. t1, t2 and t3 wait for A (any), in this
 *   order.
 * - Action: z_impl_k_event_post(A).
 * - Expected calls: z_try_abort_thread_timeout() for t1, t2, t3 (in the
 *   walk), then arch_thread_return_value_set() and
 *   z_sched_wake_thread_locked() for t3, then t2, then t1 (in the
 *   post-walk callback). Then z_reschedule().
 *
 * @ingroup kernel_unit_event_k_event_post
 * @see z_impl_k_event_post()
 * @see event_walk_op()
 * @see event_post_walk_op()
 */
ZTEST(event_unit, test_wake_scalable_in_reverse_order)
{
	struct k_event event;

	event_prepare(&event, 0U);
	add_waiter(t1, EV_A, K_EVENT_WAIT_ANY);
	add_waiter(t2, EV_A, K_EVENT_WAIT_ANY);
	add_waiter(t3, EV_A, K_EVENT_WAIT_ANY);

	(void)z_impl_k_event_post(&event, EV_A);

	zassert_call_history(unit_arch_irq_lock, z_sched_waitq_walk, z_try_abort_thread_timeout,
			     z_try_abort_thread_timeout, z_try_abort_thread_timeout,
			     arch_thread_return_value_set, z_sched_wake_thread_locked,
			     arch_thread_return_value_set, z_sched_wake_thread_locked,
			     arch_thread_return_value_set, z_sched_wake_thread_locked,
			     z_reschedule);
	zassert_equal_ptr(z_try_abort_thread_timeout_fake.arg0_history[0], t1);
	zassert_equal_ptr(z_try_abort_thread_timeout_fake.arg0_history[2], t3);
	zassert_equal_ptr(z_sched_wake_thread_locked_fake.arg0_history[0], t3);
	zassert_equal_ptr(z_sched_wake_thread_locked_fake.arg0_history[1], t2);
	zassert_equal_ptr(z_sched_wake_thread_locked_fake.arg0_history[2], t1);
}

/**
 * @brief With CONFIG_WAITQ_SCALABLE, the walk callback links a satisfied thread at the head of the
 * wake list and does not wake it.
 *
 * @details
 * - Setup: walk data with the set A and an empty wake list. t1 and t2 wait
 *   for A (any). t3 waits for B.
 * - Action: event_walk_op() for t1, t3, t2.
 * - Expected: the wake list is t2, t1 (head t2, t2->next_event_link t1,
 *   t1->next_event_link NULL). No call of arch_thread_return_value_set()
 *   or z_sched_wake_thread_locked().
 *
 * @ingroup kernel_unit_event_static
 * @see event_walk_op()
 */
ZTEST(event_unit, test_wake_scalable_walk_builds_list)
{
	struct event_walk_data data = {.head = NULL, .events = EV_A};

	t1->events = EV_A;
	t2->events = EV_A;
	t3->events = EV_B;
	t1->next_event_link = t3;

	(void)event_walk_op(t1, &data);
	(void)event_walk_op(t3, &data);
	(void)event_walk_op(t2, &data);

	zassert_equal_ptr(data.head, t2);
	zassert_equal_ptr(t2->next_event_link, t1);
	zassert_is_null(t1->next_event_link);
	zassert_equal(arch_thread_return_value_set_fake.call_count, 0);
	zassert_equal(z_sched_wake_thread_locked_fake.call_count, 0);
}

/**
 * @brief With CONFIG_WAITQ_SCALABLE, the post-walk callback wakes each thread of the wake list
 * with the return value 0, and ignores the walk status.
 *
 * @details
 * - Setup: walk data with the wake list t2, t1.
 * - Action: event_post_walk_op() with the status 1, then with an empty
 *   list.
 * - Expected: arch_thread_return_value_set(t2, 0),
 *   z_sched_wake_thread_locked(t2), then the same for t1. The empty list
 *   gives no call.
 *
 * @ingroup kernel_unit_event_static
 * @see event_post_walk_op()
 */
ZTEST(event_unit, test_wake_scalable_post_walk_wakes_list)
{
	struct event_walk_data data = {.head = t2};
	struct event_walk_data empty = {.head = NULL};

	t2->next_event_link = t1;
	t1->next_event_link = NULL;

	event_post_walk_op(1, &data);

	zassert_call_history(arch_thread_return_value_set, z_sched_wake_thread_locked,
			     arch_thread_return_value_set, z_sched_wake_thread_locked);
	zassert_equal_ptr(arch_thread_return_value_set_fake.arg0_history[0], t2);
	zassert_equal(arch_thread_return_value_set_fake.arg1_history[0], 0U);
	zassert_equal_ptr(arch_thread_return_value_set_fake.arg0_history[1], t1);
	zassert_equal(arch_thread_return_value_set_fake.arg1_history[1], 0U);
	zassert_equal_ptr(z_sched_wake_thread_locked_fake.arg0_history[0], t2);
	zassert_equal_ptr(z_sched_wake_thread_locked_fake.arg0_history[1], t1);

	FFF_RESET_HISTORY();
	event_post_walk_op(0, &empty);

	zassert_equal(kernel_unit_history_len(), 0);
}
#endif /* CONFIG_WAITQ_SCALABLE */

/*
 * Tests: Consumed events. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_event, at the top of this file.
 */

/**
 * @brief A post removes the events that a woken thread with the option CLEAR received, and keeps
 * the other events.
 *
 * @details
 * - Setup: an empty event object. t1 waits for A|B (any, CLEAR).
 * - Action: z_impl_k_event_post(A|C).
 * - Expected: t1 is woken with A. Return value 0 (no posted event was set
 *   before). The set is C: A is consumed, C stays.
 *
 * @ingroup kernel_unit_event_k_event_post
 * @see z_impl_k_event_post()
 * @see k_event_post_internal()
 * @see event_walk_op()
 */
ZTEST(event_unit, test_consume_by_woken_thread)
{
	struct k_event event;

	event_prepare(&event, 0U);
	add_waiter(t1, EV_A | EV_B, K_EVENT_OPTION_CLEAR);

	zassert_equal(z_impl_k_event_post(&event, EV_A | EV_C), 0U);

	zassert_true(woken(t1));
	zassert_equal(t1->events, EV_A);
	zassert_equal(event.events, EV_C);
}

/**
 * @brief A woken thread without the option CLEAR does not consume its events.
 *
 * @details
 * - Setup: an empty event object. t1 waits for A (any, no CLEAR).
 * - Action: z_impl_k_event_post(A).
 * - Expected: t1 is woken with A. The set is A.
 *
 * @ingroup kernel_unit_event_k_event_post
 * @see z_impl_k_event_post()
 * @see event_walk_op()
 */
ZTEST(event_unit, test_consume_not_without_clear_option)
{
	struct k_event event;

	event_prepare(&event, 0U);
	add_waiter(t1, EV_A, K_EVENT_WAIT_ANY);

	(void)z_impl_k_event_post(&event, EV_A);

	zassert_true(woken(t1));
	zassert_equal(event.events, EV_A);
}

/**
 * @brief One post gives a consumed event to all waiting threads that it satisfies; the event is
 * removed only after the walk.
 *
 * @details
 * - Setup: an empty event object. t1 and t2 wait for A (any, CLEAR). t3
 *   waits for A|B (all, no CLEAR).
 * - Action: z_impl_k_event_post(A|B).
 * - Expected: t1 and t2 are woken with A. t3 is woken with A|B, also if
 *   t1 consumed A before t3 in the walk. The set is B.
 *
 * @ingroup kernel_unit_event_k_event_post
 * @see z_impl_k_event_post()
 * @see k_event_post_internal()
 */
ZTEST(event_unit, test_consume_after_walk_for_all_threads)
{
	struct k_event event;

	event_prepare(&event, 0U);
	add_waiter(t1, EV_A, K_EVENT_OPTION_CLEAR);
	add_waiter(t2, EV_A, K_EVENT_OPTION_CLEAR);
	add_waiter(t3, EV_A | EV_B, K_EVENT_WAIT_ALL);

	(void)z_impl_k_event_post(&event, EV_A | EV_B);

	zassert_true(woken(t1));
	zassert_equal(t1->events, EV_A);
	zassert_true(woken(t2));
	zassert_equal(t2->events, EV_A);
	zassert_true(woken(t3));
	zassert_equal(t3->events, EV_A | EV_B);
	zassert_equal(event.events, EV_B);
}

/**
 * @brief k_event_post() writes the set of the event object once, after the walk, without the
 * consumed events.
 *
 * @details
 * - Setup: an event object with the set C. t1 waits for A (any, CLEAR).
 * - Action: z_impl_k_event_post(A|B).
 * - Expected: during the walk, the set of the object is still C. The walk
 *   callback reads the new set A|B|C from the walk data. After the post,
 *   the set is B|C.
 *
 * @ingroup kernel_unit_event_k_event_post
 * @see z_impl_k_event_post()
 * @see k_event_post_internal()
 */
ZTEST(event_unit, test_consume_set_written_after_walk)
{
	struct k_event event;

	event_prepare(&event, EV_C);
	add_waiter(t1, EV_A, K_EVENT_OPTION_CLEAR);
	spied_event = &event;

	(void)z_impl_k_event_post(&event, EV_A | EV_B);

	zassert_equal(events_at_walk, EV_C);
	zassert_true(woken(t1));
	zassert_equal(event.events, EV_B | EV_C);
}

/**
 * @brief k_event_wait_safe() removes the matching events from the set if the set already
 * satisfies the condition, and keeps the other events.
 *
 * @details
 * - Setup: an event object with the set A|C.
 * - Action: z_impl_k_event_wait_safe(A|B, no reset, K_NO_WAIT).
 * - Expected: return value A. The set is C.
 *
 * @ingroup kernel_unit_event_k_event_wait_safe
 * @see z_impl_k_event_wait_safe()
 */
ZTEST(event_unit, test_consume_by_wait_safe_without_wait)
{
	struct k_event event;

	event_prepare(&event, EV_A | EV_C);

	zassert_equal(z_impl_k_event_wait_safe(&event, EV_A | EV_B, false, K_NO_WAIT), EV_A);
	zassert_equal(event.events, EV_C);
}

/**
 * @brief k_event_wait_all_safe() removes the desired events from the set if the set has all of
 * them.
 *
 * @details
 * - Setup: an event object with the set A|B|C.
 * - Action: z_impl_k_event_wait_all_safe(A|B, no reset, K_NO_WAIT).
 * - Expected: return value A|B. The set is C.
 *
 * @ingroup kernel_unit_event_k_event_wait_all_safe
 * @see z_impl_k_event_wait_all_safe()
 */
ZTEST(event_unit, test_consume_by_wait_all_safe_without_wait)
{
	struct k_event event;

	event_prepare(&event, EV_A | EV_B | EV_C);

	zassert_equal(z_impl_k_event_wait_all_safe(&event, EV_A | EV_B, false, K_NO_WAIT),
		      EV_A | EV_B);
	zassert_equal(event.events, EV_C);
}

/**
 * @brief A safe wait that does not get its events does not change the set.
 *
 * @details
 * - Setup: an event object with the set A.
 * - Action: z_impl_k_event_wait_all_safe(A|B, no reset, K_NO_WAIT).
 * - Expected: return value 0. The set is A: the partial match is not
 *   consumed.
 *
 * @ingroup kernel_unit_event_k_event_wait_all_safe
 * @see z_impl_k_event_wait_all_safe()
 */
ZTEST(event_unit, test_consume_not_on_failed_wait)
{
	struct k_event event;

	event_prepare(&event, EV_A);

	zassert_equal(z_impl_k_event_wait_all_safe(&event, EV_A | EV_B, false, K_NO_WAIT), 0U);
	zassert_equal(event.events, EV_A);
}

/*
 * Tests: Wait. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_event, at the top of this file.
 */

/**
 * @brief A wait for an empty set returns 0 at once, does not lock the event and ignores the reset
 * option.
 *
 * @details
 * - Setup: an event object with the set A.
 * - Action: z_impl_k_event_wait(0, reset, K_FOREVER) and the same with
 *   the other three wait functions.
 * - Expected: each one returns 0. No call except arch_is_in_isr() (with
 *   CONFIG_ASSERT): no current thread query, no lock, no wait. The set is
 *   still A.
 *
 * @ingroup kernel_unit_event_static
 * @see k_event_wait_internal()
 */
ZTEST(event_unit, test_wait_empty_request_returns_zero)
{
	struct k_event event;

	event_prepare(&event, EV_A);

	zassert_equal(z_impl_k_event_wait(&event, 0U, true, K_FOREVER), 0U);
	zassert_equal(z_impl_k_event_wait_all(&event, 0U, true, K_FOREVER), 0U);
	zassert_equal(z_impl_k_event_wait_safe(&event, 0U, true, K_FOREVER), 0U);
	zassert_equal(z_impl_k_event_wait_all_safe(&event, 0U, true, K_FOREVER), 0U);

	zassert_call_history(KERNEL_UNIT_IF_ENABLED(CONFIG_ASSERT, arch_is_in_isr),
			     KERNEL_UNIT_IF_ENABLED(CONFIG_ASSERT, arch_is_in_isr),
			     KERNEL_UNIT_IF_ENABLED(CONFIG_ASSERT, arch_is_in_isr),
			     KERNEL_UNIT_IF_ENABLED(CONFIG_ASSERT, arch_is_in_isr));
	zassert_equal(event.events, EV_A);
}

/**
 * @brief If the set already has a desired event, k_event_wait() returns the matching events and
 * does not wait, also if the timeout permits a wait.
 *
 * @details
 * - Setup: an event object with the set A|C.
 * - Action: z_impl_k_event_wait(A|B, no reset, K_FOREVER).
 * - Expected: return value A. No call of z_pend_curr(). The set is A|C
 *   (not consumed).
 *
 * @ingroup kernel_unit_event_k_event_wait
 * @see z_impl_k_event_wait()
 */
ZTEST(event_unit, test_wait_any_met_returns_at_once)
{
	struct k_event event;

	event_prepare(&event, EV_A | EV_C);

	zassert_equal(z_impl_k_event_wait(&event, EV_A | EV_B, false, K_FOREVER), EV_A);
	zassert_equal(z_pend_curr_fake.call_count, 0);
	zassert_equal(event.events, EV_A | EV_C);
}

/**
 * @brief If the set has all desired events, k_event_wait_all() returns the desired set and does
 * not wait.
 *
 * @details
 * - Setup: an event object with the set A|B|C.
 * - Action: z_impl_k_event_wait_all(A|B, no reset, K_FOREVER).
 * - Expected: return value A|B. No call of z_pend_curr(). The set is
 *   A|B|C.
 *
 * @ingroup kernel_unit_event_k_event_wait_all
 * @see z_impl_k_event_wait_all()
 */
ZTEST(event_unit, test_wait_all_met_returns_at_once)
{
	struct k_event event;

	event_prepare(&event, EV_A | EV_B | EV_C);

	zassert_equal(z_impl_k_event_wait_all(&event, EV_A | EV_B, false, K_FOREVER), EV_A | EV_B);
	zassert_equal(z_pend_curr_fake.call_count, 0);
	zassert_equal(event.events, EV_A | EV_B | EV_C);
}

/**
 * @brief If the condition is not met and the timeout is K_NO_WAIT, a wait returns 0, does not wait
 * and does not change the current thread.
 *
 * @details
 * - Setup: an event object with the set A. The current thread has
 *   events and options filled with a pattern.
 * - Action: z_impl_k_event_wait(B, no reset, K_NO_WAIT), then
 *   z_impl_k_event_wait_all(A|B, no reset, K_NO_WAIT).
 * - Expected: both return 0. The "all" wait does not return the partial
 *   match A. No call of z_pend_curr(). The fields of the current thread
 *   are unchanged. The set is A.
 *
 * @ingroup kernel_unit_event_static
 * @see k_event_wait_internal()
 */
ZTEST(event_unit, test_wait_no_wait_returns_zero)
{
	struct k_event event;

	event_prepare(&event, EV_A);
	current_thread.events = UNSET;
	current_thread.event_options = UNSET;

	zassert_equal(z_impl_k_event_wait(&event, EV_B, false, K_NO_WAIT), 0U);
	zassert_equal(z_impl_k_event_wait_all(&event, EV_A | EV_B, false, K_NO_WAIT), 0U);

	zassert_equal(z_pend_curr_fake.call_count, 0);
	zassert_equal(current_thread.events, UNSET);
	zassert_equal(current_thread.event_options, UNSET);
	zassert_equal(event.events, EV_A);
}

/**
 * @brief If the condition is not met and the timeout is not K_NO_WAIT, a wait writes the request
 * into the current thread and waits on the wait queue with this timeout.
 *
 * @details
 * - Setup: an event object with the set A. The current thread is the
 *   result of k_sched_current_thread_query(). The wait times out.
 * - Action: z_impl_k_event_wait_all(A|B, no reset, TEST_TIMEOUT).
 * - Expected: one call of z_pend_curr() with the wait queue of the event
 *   and TEST_TIMEOUT. At this call, current_thread.events is A|B and
 *   current_thread.event_options is K_EVENT_WAIT_ALL.
 *
 * @ingroup kernel_unit_event_k_event_wait_all
 * @see z_impl_k_event_wait_all()
 * @see k_event_wait_internal()
 */
ZTEST(event_unit, test_wait_pends_with_request)
{
	struct k_event event;

	event_prepare(&event, EV_A);
	set_wait_result(-EAGAIN, 0U);

	(void)z_impl_k_event_wait_all(&event, EV_A | EV_B, false, TEST_TIMEOUT);

	zassert_equal(z_pend_curr_fake.call_count, 1);
	zassert_equal_ptr(z_pend_curr_fake.arg2_val, &event.wait_q);
	zassert_true(K_TIMEOUT_EQ(z_pend_curr_fake.arg3_val, TEST_TIMEOUT));
	zassert_equal(events_at_pend, EV_A | EV_B);
	zassert_equal(options_at_pend, K_EVENT_WAIT_ALL);
}

/**
 * @brief After a wait with the result 0, a wait returns the events that the waker wrote into the
 * current thread.
 *
 * @details
 * - Setup: an empty event object. After the wait, the result is 0 and
 *   current_thread.events is A|C.
 * - Action: z_impl_k_event_wait(A|B|C, no reset, K_FOREVER).
 * - Expected: return value A|C.
 *
 * @ingroup kernel_unit_event_k_event_wait
 * @see z_impl_k_event_wait()
 * @see k_event_wait_internal()
 */
ZTEST(event_unit, test_wait_returns_events_from_waker)
{
	struct k_event event;

	event_prepare(&event, 0U);
	set_wait_result(0, EV_A | EV_C);

	zassert_equal(z_impl_k_event_wait(&event, EV_A | EV_B | EV_C, false, K_FOREVER),
		      EV_A | EV_C);
}

/**
 * @brief After a wait with a result other than 0 (timeout), a wait returns 0, also if the thread
 * holds events.
 *
 * @details
 * - Setup: an empty event object. After the wait, the result is -EAGAIN
 *   and current_thread.events is A (the request).
 * - Action: z_impl_k_event_wait(A, no reset, TEST_TIMEOUT).
 * - Expected: return value 0.
 *
 * @ingroup kernel_unit_event_k_event_wait
 * @see z_impl_k_event_wait()
 * @see k_event_wait_internal()
 */
ZTEST(event_unit, test_wait_timeout_returns_zero)
{
	struct k_event event;

	event_prepare(&event, 0U);
	set_wait_result(-EAGAIN, EV_A);

	zassert_equal(z_impl_k_event_wait(&event, EV_A, false, TEST_TIMEOUT), 0U);
}

/**
 * @brief With reset, a wait clears the whole set before it checks the condition.
 *
 * @details
 * - Setup: an event object with the set A|C.
 * - Action: z_impl_k_event_wait(A, reset, K_NO_WAIT).
 * - Expected: return value 0, although A was in the set. The set is 0,
 *   also without C, which the wait did not request.
 *
 * @ingroup kernel_unit_event_k_event_wait
 * @see z_impl_k_event_wait()
 * @see k_event_wait_internal()
 */
ZTEST(event_unit, test_wait_reset_clears_set_before_check)
{
	struct k_event event;

	event_prepare(&event, EV_A | EV_C);

	zassert_equal(z_impl_k_event_wait(&event, EV_A, true, K_NO_WAIT), 0U);
	zassert_equal(event.events, 0U);
}

/**
 * @brief The four wait functions differ only in the options that they give to the wait: any or
 * all, consume or not, and reset or not.
 *
 * @details
 * - Setup: an empty event object. Each wait times out.
 * - Action: each wait function with reset false and true, with the
 *   desired set A and TEST_TIMEOUT.
 * - Expected: the options in the current thread at z_pend_curr():
 *   k_event_wait(): 0 and RESET. k_event_wait_all(): WAIT_ALL and
 *   WAIT_ALL|RESET. k_event_wait_safe(): CLEAR and CLEAR|RESET.
 *   k_event_wait_all_safe(): CLEAR|WAIT_ALL and CLEAR|RESET|WAIT_ALL.
 *
 * @ingroup kernel_unit_event_k_event_wait
 * @see z_impl_k_event_wait()
 * @see z_impl_k_event_wait_all()
 * @see z_impl_k_event_wait_safe()
 * @see z_impl_k_event_wait_all_safe()
 */
ZTEST(event_unit, test_wait_functions_set_options)
{
	typedef uint32_t (*wait_fn_t)(struct k_event *, uint32_t, bool, k_timeout_t);
	static const struct {
		wait_fn_t fn;
		bool reset;
		uint32_t options;
	} cases[] = {
		{z_impl_k_event_wait, false, K_EVENT_WAIT_ANY},
		{z_impl_k_event_wait, true, K_EVENT_OPTION_RESET},
		{z_impl_k_event_wait_all, false, K_EVENT_WAIT_ALL},
		{z_impl_k_event_wait_all, true, K_EVENT_WAIT_ALL | K_EVENT_OPTION_RESET},
		{z_impl_k_event_wait_safe, false, K_EVENT_OPTION_CLEAR},
		{z_impl_k_event_wait_safe, true, K_EVENT_OPTION_CLEAR | K_EVENT_OPTION_RESET},
		{z_impl_k_event_wait_all_safe, false, K_EVENT_OPTION_CLEAR | K_EVENT_WAIT_ALL},
		{z_impl_k_event_wait_all_safe, true,
		 K_EVENT_OPTION_CLEAR | K_EVENT_OPTION_RESET | K_EVENT_WAIT_ALL},
	};
	struct k_event event;

	for (size_t i = 0; i < ARRAY_SIZE(cases); i++) {
		event_prepare(&event, 0U);
		set_wait_result(-EAGAIN, 0U);

		zassert_equal(cases[i].fn(&event, EV_A, cases[i].reset, TEST_TIMEOUT), 0U);
		zassert_equal(options_at_pend, cases[i].options, "case %zu: options 0x%x", i,
			      options_at_pend);
	}
}

/**
 * @brief A wait gets the current thread with k_sched_current_thread_query() before it locks the
 * event.
 *
 * @details
 * - Setup: an empty event object. The wait times out.
 * - Action: z_impl_k_event_wait(A, no reset, TEST_TIMEOUT).
 * - Expected: one call of k_sched_current_thread_query(), before
 *   arch_irq_lock(). The request is in the thread that the query returned.
 *
 * @ingroup kernel_unit_event_k_event_wait
 * @see z_impl_k_event_wait()
 * @see k_event_wait_internal()
 */
ZTEST(event_unit, test_wait_queries_current_thread_before_lock)
{
	struct k_event event;

	event_prepare(&event, 0U);
	set_wait_result(-EAGAIN, 0U);

	(void)z_impl_k_event_wait(&event, EV_A, false, TEST_TIMEOUT);

	zassert_equal(k_sched_current_thread_query_fake.call_count, 1);
	zassert_called_before(k_sched_current_thread_query, unit_arch_irq_lock);
	zassert_equal(events_at_pend, EV_A);
}

/**
 * @brief k_event_test() returns the events of the mask that are in the set, does not wait and
 * does not change the set.
 *
 * @details
 * - Setup: an event object with the set A|C.
 * - Action: k_event_test(A|B) (zephyr/kernel.h, a call of k_event_wait()
 *   with K_NO_WAIT).
 * - Expected: return value A. No call of z_pend_curr(). The set is A|C.
 *
 * @ingroup kernel_unit_event_k_event_wait
 * @see z_impl_k_event_wait()
 */
ZTEST(event_unit, test_wait_event_test_reads_set)
{
	struct k_event event;

	event_prepare(&event, EV_A | EV_C);

	zassert_equal(k_event_test(&event, EV_A | EV_B), EV_A);
	zassert_equal(z_pend_curr_fake.call_count, 0);
	zassert_equal(event.events, EV_A | EV_C);
}

/**
 * @brief The events that a post gives to a waiting thread are the return value of the wait of
 * this thread.
 *
 * @details
 * - Setup: an event object with the set C. The current thread waits, and
 *   then another thread posts A|B|D (model in the fake z_pend_curr()).
 * - Action: z_impl_k_event_wait(A|B, no reset, K_FOREVER).
 * - Expected: the post wakes the current thread with the return value 0.
 *   The wait returns A|B. The set is A|B|C|D.
 *
 * @ingroup kernel_unit_event_k_event_wait
 * @see z_impl_k_event_wait()
 * @see k_event_wait_internal()
 * @see k_event_post_internal()
 */
ZTEST(event_unit, test_wait_handover_from_post)
{
	struct k_event event;

	event_prepare(&event, EV_C);
	set_handover(&event, EV_A | EV_B | EV_D);

	zassert_equal(z_impl_k_event_wait(&event, EV_A | EV_B, false, K_FOREVER), EV_A | EV_B);
	zassert_true(woken(&current_thread));
	zassert_equal(event.events, EV_A | EV_B | EV_C | EV_D);
}

/**
 * @brief A safe wait that a post wakes returns the received events, and the post removes them
 * from the set.
 *
 * @details
 * - Setup: an empty event object. The current thread waits, and then
 *   another thread posts A|C.
 * - Action: z_impl_k_event_wait_all_safe(A|C, no reset, K_FOREVER).
 * - Expected: return value A|C. The set is 0.
 *
 * @ingroup kernel_unit_event_k_event_wait_all_safe
 * @see z_impl_k_event_wait_all_safe()
 * @see k_event_post_internal()
 */
ZTEST(event_unit, test_wait_handover_consumes_for_safe_wait)
{
	struct k_event event;

	event_prepare(&event, 0U);
	set_handover(&event, EV_A | EV_C);

	zassert_equal(z_impl_k_event_wait_all_safe(&event, EV_A | EV_C, false, K_FOREVER),
		      EV_A | EV_C);
	zassert_equal(event.events, 0U);
}

/**
 * @brief A post that does not satisfy the condition of a waiting thread does not end the wait of
 * this thread; the wait returns 0 after the timeout.
 *
 * @details
 * - Setup: an empty event object. The current thread waits, and then
 *   another thread posts A. The model ends the wait with -EAGAIN because
 *   the post did not wake the thread.
 * - Action: z_impl_k_event_wait_all(A|B, no reset, TEST_TIMEOUT).
 * - Expected: return value 0. The current thread is not woken. The set
 *   is A.
 *
 * @ingroup kernel_unit_event_k_event_wait_all
 * @see z_impl_k_event_wait_all()
 * @see k_event_wait_internal()
 */
ZTEST(event_unit, test_wait_handover_not_for_unmet_condition)
{
	struct k_event event;

	event_prepare(&event, 0U);
	set_handover(&event, EV_A);

	zassert_equal(z_impl_k_event_wait_all(&event, EV_A | EV_B, false, TEST_TIMEOUT), 0U);
	zassert_false(woken(&current_thread));
	zassert_equal(event.events, EV_A);
}

#ifdef CONFIG_ASSERT
/**
 * @brief With CONFIG_ASSERT, a wait in an ISR with a timeout other than K_NO_WAIT is a failed
 * assertion, before the wait locks the event.
 *
 * @details
 * - Setup: an empty event object. arch_is_in_isr() returns true. The test
 *   expects the refusal of z_pend_curr().
 * - Action: z_impl_k_event_wait(A, no reset, TEST_TIMEOUT).
 * - Expected: one failed assertion of events.c, before arch_irq_lock().
 *
 * In the test, the assertion hook returns. Then the wait continues to
 * z_pend_curr(), and the scheduler refuses it with a second failed
 * assertion and a panic (see test_wait_isr_with_timeout_refused_by_scheduler).
 *
 * @ingroup kernel_unit_event_k_event_wait
 * @see z_impl_k_event_wait()
 * @see k_event_wait_internal()
 */
ZTEST(event_unit, test_wait_isr_with_timeout_asserts)
{
	struct k_event event;

	event_prepare(&event, 0U);
	set_wait_result(-EAGAIN, 0U);
	arch_is_in_isr_fake.return_val = true;
	kernel_unit_expect_pend_refusal();

	(void)z_impl_k_event_wait(&event, EV_A, false, TEST_TIMEOUT);

	zassert_equal(assert_post_action_fake.call_count, 2);
	zassert_called_before(assert_post_action, unit_arch_irq_lock);
	kernel_unit_assert_pend_refused();
}

/**
 * @brief An ISR can wait with K_NO_WAIT, and a thread can wait with a timeout, without a failed
 * assertion.
 *
 * @details
 * - Setup: an event object with the set A.
 * - Action: z_impl_k_event_wait(A, no reset, K_NO_WAIT) in an ISR
 *   (arch_is_in_isr() returns true), then z_impl_k_event_wait(B, no reset,
 *   TEST_TIMEOUT) in a thread.
 * - Expected: no failed assertion. The ISR wait returns A.
 *
 * @ingroup kernel_unit_event_k_event_wait
 * @see z_impl_k_event_wait()
 * @see k_event_wait_internal()
 */
ZTEST(event_unit, test_wait_isr_no_wait_allowed)
{
	struct k_event event;

	event_prepare(&event, EV_A);
	set_wait_result(-EAGAIN, 0U);
	arch_is_in_isr_fake.return_val = true;

	zassert_equal(z_impl_k_event_wait(&event, EV_A, false, K_NO_WAIT), EV_A);

	arch_is_in_isr_fake.return_val = false;
	(void)z_impl_k_event_wait(&event, EV_B, false, TEST_TIMEOUT);

	zassert_equal(assert_post_action_fake.call_count, 0);
}
#endif /* CONFIG_ASSERT */

/**
 * @brief In an ISR, a wait with a timeout reaches z_pend_curr(), and the scheduler refuses it with
 * a panic.
 *
 * @details
 * The real z_pend_curr() refuses a call from an ISR in every build, before
 * it changes a thread or a wait queue. events.c has an earlier check only
 * with CONFIG_ASSERT (see test_wait_isr_with_timeout_asserts).
 * - Setup: an empty event object. arch_is_in_isr() returns true. The
 *   scheduler model would wake the thread with A. The test expects the
 *   refusal of z_pend_curr().
 * - Action: z_impl_k_event_wait(A, no reset, TEST_TIMEOUT).
 * - Expected: one call of z_pend_curr() with the lock of the event. The
 *   scheduler refuses it with a failed assertion (with CONFIG_ASSERT) and a
 *   panic. The model does not run. The lock stays locked, and the set stays
 *   empty. Before the call, the wait wrote its request (A, no options) into
 *   the interrupted thread. After the panic, the fake returns
 *   KERNEL_UNIT_PEND_REFUSED (a timeout), and the wait returns 0.
 *
 * @ingroup kernel_unit_event_k_event_wait
 * @see z_impl_k_event_wait()
 * @see k_event_wait_internal()
 */
ZTEST(event_unit, test_wait_isr_with_timeout_refused_by_scheduler)
{
	struct k_event event;

	event_prepare(&event, 0U);
	set_wait_result(0, EV_A);
	arch_is_in_isr_fake.return_val = true;
	kernel_unit_expect_pend_refusal();

	zassert_equal(z_impl_k_event_wait(&event, EV_A, false, TEST_TIMEOUT), 0U);

	kernel_unit_assert_pend_refused();
	zassert_equal(z_pend_curr_fake.call_count, 1);
	zassert_equal_ptr(z_pend_curr_fake.arg0_val, &event.lock);
	zassert_equal(events_at_pend, UNSET, "the scheduler model ran");
	zassert_equal(unit_arch_irq_unlock_fake.call_count, 0);
	zassert_equal(event.events, 0U);
	zassert_equal(current_thread.events, EV_A);
	zassert_equal(current_thread.event_options, 0U);
#ifdef CONFIG_ASSERT
	zassert_equal(assert_post_action_fake.call_count, 2);
#endif
}

/*
 * Tests: Locking. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_event, at the top of this file.
 */

/**
 * @brief If a post wakes no thread, it still releases the lock with z_reschedule().
 *
 * @details
 * - Setup: an empty event object. No thread waits.
 * - Action: z_impl_k_event_post(A).
 * - Expected calls: arch_irq_lock(), z_sched_waitq_walk(), z_reschedule()
 *   with the lock of the event and the key. The lock invariant holds.
 *
 * @ingroup kernel_unit_event_k_event_post
 * @see z_impl_k_event_post()
 * @see k_event_post_internal()
 */
ZTEST(event_unit, test_lock_post_without_waiters_reschedules)
{
	struct k_event event;

	event_prepare(&event, 0U);

	(void)z_impl_k_event_post(&event, EV_A);

	zassert_call_history(unit_arch_irq_lock, z_sched_waitq_walk, z_reschedule);
	assert_lock_released_once(&event, KERNEL_UNIT_RELEASED_BY_RESCHEDULE);
}

/**
 * @brief If a post wakes a thread, the wake occurs while the lock is held, and the post releases
 * the lock with z_reschedule() after the walk.
 *
 * @details
 * - Setup: an empty event object. t1 waits for A.
 * - Action: z_impl_k_event_post(A).
 * - Expected: at the walk, the lock is held (one lock, no release).
 *   Calls: arch_irq_lock(), z_sched_waitq_walk(), the wake calls,
 *   z_reschedule(). The lock invariant holds.
 *
 * @ingroup kernel_unit_event_k_event_post
 * @see z_impl_k_event_post()
 * @see k_event_post_internal()
 */
ZTEST(event_unit, test_lock_post_wakes_under_lock)
{
	struct k_event event;

	event_prepare(&event, 0U);
	add_waiter(t1, EV_A, K_EVENT_WAIT_ANY);

	(void)z_impl_k_event_post(&event, EV_A);

	zassert_equal(locks_at_walk, 1);
	zassert_equal(releases_at_walk, 0);
	zassert_true(woken(t1));
	zassert_called_before(z_sched_wake_thread_locked, z_reschedule);
	assert_lock_released_once(&event, KERNEL_UNIT_RELEASED_BY_RESCHEDULE);
}

/**
 * @brief k_event_set(), k_event_set_masked() and k_event_clear() use the same lock path as
 * k_event_post().
 *
 * @details
 * - Setup: an event object with the set A. No thread waits.
 * - Action: each of z_impl_k_event_set(B), z_impl_k_event_set_masked(B,
 *   A|B) and z_impl_k_event_clear(A), with a reset of the fakes before
 *   each.
 * - Expected for each: calls arch_irq_lock(), z_sched_waitq_walk(),
 *   z_reschedule(). The lock invariant holds.
 *
 * @ingroup kernel_unit_event_k_event_set
 * @see z_impl_k_event_set()
 * @see z_impl_k_event_set_masked()
 * @see z_impl_k_event_clear()
 */
ZTEST(event_unit, test_lock_set_and_clear_reschedule)
{
	struct k_event event;

	for (int i = 0; i < 3; i++) {
		event_prepare(&event, EV_A);
		FFF_RESET_HISTORY();
		RESET_FAKE(unit_arch_irq_lock);
		RESET_FAKE(unit_arch_irq_unlock);
		RESET_FAKE(z_reschedule);
		RESET_FAKE(z_sched_waitq_walk);
		unit_arch_irq_lock_fake.return_val = KERNEL_UNIT_IRQ_KEY;
		z_sched_waitq_walk_fake.custom_fake = walk_model;

		switch (i) {
		case 0:
			(void)z_impl_k_event_set(&event, EV_B);
			break;
		case 1:
			(void)z_impl_k_event_set_masked(&event, EV_B, EV_A | EV_B);
			break;
		default:
			(void)z_impl_k_event_clear(&event, EV_A);
			break;
		}

		zassert_call_history(unit_arch_irq_lock, z_sched_waitq_walk, z_reschedule);
		assert_lock_released_once(&event, KERNEL_UNIT_RELEASED_BY_RESCHEDULE);
	}
}

/**
 * @brief If the condition is met at once, a wait releases the lock with k_spin_unlock().
 *
 * @details
 * - Setup: an event object with the set A.
 * - Action: z_impl_k_event_wait_safe(A, no reset, K_FOREVER).
 * - Expected calls: arch_is_in_isr() (with CONFIG_ASSERT),
 *   k_sched_current_thread_query(), arch_irq_lock(), arch_irq_unlock()
 *   with the key. The lock invariant holds.
 *
 * @ingroup kernel_unit_event_k_event_wait_safe
 * @see z_impl_k_event_wait_safe()
 * @see k_event_wait_internal()
 */
ZTEST(event_unit, test_lock_wait_met_unlocks)
{
	struct k_event event;

	event_prepare(&event, EV_A);

	(void)z_impl_k_event_wait_safe(&event, EV_A, false, K_FOREVER);

	zassert_call_history(KERNEL_UNIT_IF_ENABLED(CONFIG_ASSERT, arch_is_in_isr),
			     k_sched_current_thread_query, unit_arch_irq_lock,
			     unit_arch_irq_unlock);
	assert_lock_released_once(&event, KERNEL_UNIT_RELEASED_BY_UNLOCK);
}

/**
 * @brief If a wait returns 0 with K_NO_WAIT, it releases the lock with k_spin_unlock().
 *
 * @details
 * - Setup: an empty event object.
 * - Action: z_impl_k_event_wait(A, reset, K_NO_WAIT).
 * - Expected calls: arch_is_in_isr() (with CONFIG_ASSERT),
 *   k_sched_current_thread_query(), arch_irq_lock(), arch_irq_unlock()
 *   with the key. The lock invariant holds.
 *
 * @ingroup kernel_unit_event_k_event_wait
 * @see z_impl_k_event_wait()
 * @see k_event_wait_internal()
 */
ZTEST(event_unit, test_lock_wait_no_wait_unlocks)
{
	struct k_event event;

	event_prepare(&event, 0U);

	(void)z_impl_k_event_wait(&event, EV_A, true, K_NO_WAIT);

	zassert_call_history(KERNEL_UNIT_IF_ENABLED(CONFIG_ASSERT, arch_is_in_isr),
			     k_sched_current_thread_query, unit_arch_irq_lock,
			     unit_arch_irq_unlock);
	assert_lock_released_once(&event, KERNEL_UNIT_RELEASED_BY_UNLOCK);
}

/**
 * @brief If a wait must wait, z_pend_curr() releases the lock, and the wait does not release it
 * again.
 *
 * @details
 * - Setup: an empty event object. The wait times out.
 * - Action: z_impl_k_event_wait_all(A, no reset, TEST_TIMEOUT).
 * - Expected calls: arch_is_in_isr() (with CONFIG_ASSERT),
 *   k_sched_current_thread_query(), arch_irq_lock(), z_pend_curr() with
 *   the lock of the event and the key. No arch_irq_unlock(). The lock
 *   invariant holds.
 *
 * @ingroup kernel_unit_event_k_event_wait_all
 * @see z_impl_k_event_wait_all()
 * @see k_event_wait_internal()
 */
ZTEST(event_unit, test_lock_wait_pend_releases)
{
	struct k_event event;

	event_prepare(&event, 0U);
	set_wait_result(-EAGAIN, 0U);

	(void)z_impl_k_event_wait_all(&event, EV_A, false, TEST_TIMEOUT);

	zassert_call_history(KERNEL_UNIT_IF_ENABLED(CONFIG_ASSERT, arch_is_in_isr),
			     k_sched_current_thread_query, unit_arch_irq_lock, z_pend_curr);
	assert_lock_released_once(&event, KERNEL_UNIT_RELEASED_BY_PEND);
}

/**
 * @brief A post changes the set only while it holds the lock.
 *
 * @details
 * - Setup: an event object with the set A. Spy fakes record the set at
 *   the lock and at the release.
 * - Action: z_impl_k_event_set(B).
 * - Expected: at the lock, the set is A. At the release, the set is B.
 *
 * @ingroup kernel_unit_event_k_event_set
 * @see z_impl_k_event_set()
 * @see k_event_post_internal()
 */
ZTEST(event_unit, test_lock_post_changes_set_under_lock)
{
	struct k_event event;

	event_prepare(&event, EV_A);
	spy_on_lock(&event);

	(void)z_impl_k_event_set(&event, EV_B);

	zassert_equal(events_at_lock, EV_A);
	zassert_equal(events_at_release, EV_B);
}

/**
 * @brief A wait applies the reset and consumes events only while it holds the lock.
 *
 * @details
 * - Setup: an event object with the set A|B. Spy fakes record the set at
 *   the lock and at the release.
 * - Action: z_impl_k_event_wait_safe(A, no reset, K_NO_WAIT), then
 *   z_impl_k_event_wait(C, reset, K_NO_WAIT).
 * - Expected: first wait: at the lock A|B, at the release B. Second wait:
 *   at the lock B, at the release 0.
 *
 * @ingroup kernel_unit_event_static
 * @see k_event_wait_internal()
 */
ZTEST(event_unit, test_lock_wait_changes_set_under_lock)
{
	struct k_event event;

	event_prepare(&event, EV_A | EV_B);
	spy_on_lock(&event);

	(void)z_impl_k_event_wait_safe(&event, EV_A, false, K_NO_WAIT);

	zassert_equal(events_at_lock, EV_A | EV_B);
	zassert_equal(events_at_release, EV_B);

	(void)z_impl_k_event_wait(&event, EV_C, true, K_NO_WAIT);

	zassert_equal(events_at_lock, EV_B);
	zassert_equal(events_at_release, 0U);
}

/**
 * @brief Each event object has its own lock.
 *
 * @details
 * - Setup: two event objects.
 * - Action: z_impl_k_event_post() on each.
 * - Expected: the two calls of z_reschedule() have the lock of the
 *   respective event object.
 *
 * @ingroup kernel_unit_event_k_event_post
 * @see z_impl_k_event_post()
 * @see k_event_post_internal()
 */
ZTEST(event_unit, test_lock_per_event_object)
{
	struct k_event e1;
	struct k_event e2;

	event_prepare(&e1, 0U);
	event_prepare(&e2, 0U);

	(void)z_impl_k_event_post(&e1, EV_A);
	(void)z_impl_k_event_post(&e2, EV_A);

	zassert_equal(z_reschedule_fake.call_count, 2);
	zassert_equal_ptr(z_reschedule_fake.arg0_history[0], &e1.lock);
	zassert_equal_ptr(z_reschedule_fake.arg0_history[1], &e2.lock);
}

#ifdef CONFIG_SPIN_VALIDATE
/**
 * @brief With CONFIG_SPIN_VALIDATE, the spinlock validation sees the lock of the event object on
 * lock and on unlock.
 *
 * @details
 * - Setup: an event object with the set A.
 * - Action: z_impl_k_event_wait(A, no reset, K_NO_WAIT).
 * - Expected: one call of z_spin_lock_valid() and one call of
 *   z_spin_unlock_valid(), each with the lock of the event object.
 *
 * @ingroup kernel_unit_event_k_event_wait
 * @see z_impl_k_event_wait()
 * @see k_event_wait_internal()
 */
ZTEST(event_unit, test_lock_validation_sees_event_lock)
{
	struct k_event event;

	event_prepare(&event, EV_A);

	(void)z_impl_k_event_wait(&event, EV_A, false, K_NO_WAIT);

	zassert_equal(z_spin_lock_valid_fake.call_count, 1);
	zassert_equal_ptr(z_spin_lock_valid_fake.arg0_val, &event.lock);
	zassert_equal(z_spin_unlock_valid_fake.call_count, 1);
	zassert_equal_ptr(z_spin_unlock_valid_fake.arg0_val, &event.lock);
}
#endif /* CONFIG_SPIN_VALIDATE */

#ifdef CONFIG_USERSPACE
/*
 * Tests: System call verification. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_event, at the top of this file.
 */

/* Assert one object check of event with the type K_OBJ_EVENT and init state, and no oops. */
static void assert_object_check(struct k_event *event, enum _obj_init_check init)
{
	kernel_unit_assert_object_check(event, K_OBJ_EVENT, init);
}

/* Assert one oops, before the first call of fn (the first change of the event). */
#define zassert_oops_before(fn)                                                                    \
	do {                                                                                       \
		zassert_equal(unit_syscall_oops_fake.call_count, 1);                               \
		zassert_called_before(unit_syscall_oops, fn);                                      \
	} while (false)

/**
 * @brief z_vrfy_k_event_init() checks that the pointer is an event object that is not
 * initialized, and then calls z_impl_k_event_init().
 *
 * @details
 * - Setup: an event object filled with a pattern. The object check
 *   passes.
 * - Action: z_vrfy_k_event_init().
 * - Expected: the object check with K_OBJ_EVENT and _OBJ_INIT_FALSE,
 *   before z_waitq_init(). No oops. The set is 0.
 *
 * @ingroup kernel_unit_event_k_event_init
 * @see z_vrfy_k_event_init()
 */
ZTEST(event_unit, test_syscall_init_checks_new_object)
{
	struct k_event event;

	memset(&event, FILL, sizeof(event));
	kernel_unit_pass_object_check();

	z_vrfy_k_event_init(&event);

	assert_object_check(&event, _OBJ_INIT_FALSE);
	zassert_called_before(k_object_validation_check, z_waitq_init);
	zassert_equal(event.events, 0U);
}

/**
 * @brief If the object check fails, z_vrfy_k_event_init() raises an oops before it changes the
 * event object.
 *
 * @details
 * - Setup: the object check fails (for example, the event object is
 *   already initialized).
 * - Action: z_vrfy_k_event_init().
 * - Expected: one oops, before z_waitq_init().
 *
 * @ingroup kernel_unit_event_k_event_init
 * @see z_vrfy_k_event_init()
 */
ZTEST(event_unit, test_syscall_init_oops_on_bad_object)
{
	struct k_event event;

	kernel_unit_fail_object_check();

	z_vrfy_k_event_init(&event);

	zassert_oops_before(z_waitq_init);
}

/**
 * @brief z_vrfy_k_event_post() checks that the pointer is an initialized event object, and then
 * returns the result of z_impl_k_event_post().
 *
 * @details
 * - Setup: an event object with the set A. The object check passes.
 * - Action: z_vrfy_k_event_post(A|B).
 * - Expected: the object check with K_OBJ_EVENT and _OBJ_INIT_TRUE, before
 *   the lock. No oops. Return value A. The set is A|B.
 *
 * @ingroup kernel_unit_event_k_event_post
 * @see z_vrfy_k_event_post()
 */
ZTEST(event_unit, test_syscall_post_checks_initialized_object)
{
	struct k_event event;

	event_prepare(&event, EV_A);
	kernel_unit_pass_object_check();

	zassert_equal(z_vrfy_k_event_post(&event, EV_A | EV_B), EV_A);

	assert_object_check(&event, _OBJ_INIT_TRUE);
	zassert_called_before(k_object_validation_check, unit_arch_irq_lock);
	zassert_equal(event.events, EV_A | EV_B);
}

/**
 * @brief If the object check fails, z_vrfy_k_event_post() raises an oops before it locks the
 * event object.
 *
 * @details
 * - Setup: an empty event object. The object check fails.
 * - Action: z_vrfy_k_event_post(A).
 * - Expected: one oops, before arch_irq_lock().
 *
 * @ingroup kernel_unit_event_k_event_post
 * @see z_vrfy_k_event_post()
 */
ZTEST(event_unit, test_syscall_post_oops_on_bad_object)
{
	struct k_event event;

	event_prepare(&event, 0U);
	kernel_unit_fail_object_check();

	(void)z_vrfy_k_event_post(&event, EV_A);

	zassert_oops_before(unit_arch_irq_lock);
}

/**
 * @brief z_vrfy_k_event_set() checks that the pointer is an initialized event object, and then
 * returns the result of z_impl_k_event_set().
 *
 * @details
 * - Setup: an event object with the set A. The object check passes.
 * - Action: z_vrfy_k_event_set(B).
 * - Expected: the object check with K_OBJ_EVENT and _OBJ_INIT_TRUE, before
 *   the lock. No oops. Return value A. The set is B.
 *
 * @ingroup kernel_unit_event_k_event_set
 * @see z_vrfy_k_event_set()
 */
ZTEST(event_unit, test_syscall_set_checks_initialized_object)
{
	struct k_event event;

	event_prepare(&event, EV_A);
	kernel_unit_pass_object_check();

	zassert_equal(z_vrfy_k_event_set(&event, EV_B), EV_A);

	assert_object_check(&event, _OBJ_INIT_TRUE);
	zassert_called_before(k_object_validation_check, unit_arch_irq_lock);
	zassert_equal(event.events, EV_B);
}

/**
 * @brief If the object check fails, z_vrfy_k_event_set() raises an oops before it locks the event
 * object.
 *
 * @details
 * - Setup: an empty event object. The object check fails.
 * - Action: z_vrfy_k_event_set(A).
 * - Expected: one oops, before arch_irq_lock().
 *
 * @ingroup kernel_unit_event_k_event_set
 * @see z_vrfy_k_event_set()
 */
ZTEST(event_unit, test_syscall_set_oops_on_bad_object)
{
	struct k_event event;

	event_prepare(&event, 0U);
	kernel_unit_fail_object_check();

	(void)z_vrfy_k_event_set(&event, EV_A);

	zassert_oops_before(unit_arch_irq_lock);
}

/**
 * @brief z_vrfy_k_event_set_masked() checks that the pointer is an initialized event object, and
 * then returns the result of z_impl_k_event_set_masked().
 *
 * @details
 * - Setup: an event object with the set A|C. The object check passes.
 * - Action: z_vrfy_k_event_set_masked(B, A|B).
 * - Expected: the object check with K_OBJ_EVENT and _OBJ_INIT_TRUE, before
 *   the lock. No oops. Return value A. The set is B|C.
 *
 * @ingroup kernel_unit_event_k_event_set_masked
 * @see z_vrfy_k_event_set_masked()
 */
ZTEST(event_unit, test_syscall_set_masked_checks_initialized_object)
{
	struct k_event event;

	event_prepare(&event, EV_A | EV_C);
	kernel_unit_pass_object_check();

	zassert_equal(z_vrfy_k_event_set_masked(&event, EV_B, EV_A | EV_B), EV_A);

	assert_object_check(&event, _OBJ_INIT_TRUE);
	zassert_called_before(k_object_validation_check, unit_arch_irq_lock);
	zassert_equal(event.events, EV_B | EV_C);
}

/**
 * @brief If the object check fails, z_vrfy_k_event_set_masked() raises an oops before it locks the
 * event object.
 *
 * @details
 * - Setup: an empty event object. The object check fails.
 * - Action: z_vrfy_k_event_set_masked(A, A).
 * - Expected: one oops, before arch_irq_lock().
 *
 * @ingroup kernel_unit_event_k_event_set_masked
 * @see z_vrfy_k_event_set_masked()
 */
ZTEST(event_unit, test_syscall_set_masked_oops_on_bad_object)
{
	struct k_event event;

	event_prepare(&event, 0U);
	kernel_unit_fail_object_check();

	(void)z_vrfy_k_event_set_masked(&event, EV_A, EV_A);

	zassert_oops_before(unit_arch_irq_lock);
}

/**
 * @brief z_vrfy_k_event_clear() checks that the pointer is an initialized event object, and then
 * returns the result of z_impl_k_event_clear().
 *
 * @details
 * - Setup: an event object with the set A|B. The object check passes.
 * - Action: z_vrfy_k_event_clear(A).
 * - Expected: the object check with K_OBJ_EVENT and _OBJ_INIT_TRUE, before
 *   the lock. No oops. Return value A. The set is B.
 *
 * @ingroup kernel_unit_event_k_event_clear
 * @see z_vrfy_k_event_clear()
 */
ZTEST(event_unit, test_syscall_clear_checks_initialized_object)
{
	struct k_event event;

	event_prepare(&event, EV_A | EV_B);
	kernel_unit_pass_object_check();

	zassert_equal(z_vrfy_k_event_clear(&event, EV_A), EV_A);

	assert_object_check(&event, _OBJ_INIT_TRUE);
	zassert_called_before(k_object_validation_check, unit_arch_irq_lock);
	zassert_equal(event.events, EV_B);
}

/**
 * @brief If the object check fails, z_vrfy_k_event_clear() raises an oops before it locks the
 * event object.
 *
 * @details
 * - Setup: an empty event object. The object check fails.
 * - Action: z_vrfy_k_event_clear(A).
 * - Expected: one oops, before arch_irq_lock().
 *
 * @ingroup kernel_unit_event_k_event_clear
 * @see z_vrfy_k_event_clear()
 */
ZTEST(event_unit, test_syscall_clear_oops_on_bad_object)
{
	struct k_event event;

	event_prepare(&event, 0U);
	kernel_unit_fail_object_check();

	(void)z_vrfy_k_event_clear(&event, EV_A);

	zassert_oops_before(unit_arch_irq_lock);
}

/**
 * @brief z_vrfy_k_event_wait() checks that the pointer is an initialized event object, and then
 * returns the result of z_impl_k_event_wait() with the same arguments.
 *
 * @details
 * - Setup: an event object with the set A. The object check passes. The
 *   wait times out.
 * - Action: z_vrfy_k_event_wait(B, reset, TEST_TIMEOUT).
 * - Expected: the object check with K_OBJ_EVENT and _OBJ_INIT_TRUE, before
 *   the lock. No oops. z_pend_curr() with TEST_TIMEOUT, and the options
 *   RESET in the thread. Return value 0. The set is 0 (reset).
 *
 * @ingroup kernel_unit_event_k_event_wait
 * @see z_vrfy_k_event_wait()
 */
ZTEST(event_unit, test_syscall_wait_checks_initialized_object)
{
	struct k_event event;

	event_prepare(&event, EV_A);
	kernel_unit_pass_object_check();
	set_wait_result(-EAGAIN, 0U);

	zassert_equal(z_vrfy_k_event_wait(&event, EV_B, true, TEST_TIMEOUT), 0U);

	assert_object_check(&event, _OBJ_INIT_TRUE);
	zassert_called_before(k_object_validation_check, unit_arch_irq_lock);
	zassert_true(K_TIMEOUT_EQ(z_pend_curr_fake.arg3_val, TEST_TIMEOUT));
	zassert_equal(events_at_pend, EV_B);
	zassert_equal(options_at_pend, K_EVENT_OPTION_RESET);
	zassert_equal(event.events, 0U);
}

/**
 * @brief If the object check fails, z_vrfy_k_event_wait() raises an oops before it locks the
 * event object.
 *
 * @details
 * - Setup: an event object with the set A. The object check fails.
 * - Action: z_vrfy_k_event_wait(A, no reset, K_NO_WAIT).
 * - Expected: one oops, before arch_irq_lock().
 *
 * @ingroup kernel_unit_event_k_event_wait
 * @see z_vrfy_k_event_wait()
 */
ZTEST(event_unit, test_syscall_wait_oops_on_bad_object)
{
	struct k_event event;

	event_prepare(&event, EV_A);
	kernel_unit_fail_object_check();

	(void)z_vrfy_k_event_wait(&event, EV_A, false, K_NO_WAIT);

	zassert_oops_before(unit_arch_irq_lock);
}

/**
 * @brief z_vrfy_k_event_wait_all() checks that the pointer is an initialized event object, and
 * then returns the result of z_impl_k_event_wait_all() with the same arguments.
 *
 * @details
 * - Setup: an event object with the set A|B. The object check passes.
 * - Action: z_vrfy_k_event_wait_all(A|B, no reset, TEST_TIMEOUT).
 * - Expected: the object check with K_OBJ_EVENT and _OBJ_INIT_TRUE, before
 *   the lock. No oops. Return value A|B.
 *
 * @ingroup kernel_unit_event_k_event_wait_all
 * @see z_vrfy_k_event_wait_all()
 */
ZTEST(event_unit, test_syscall_wait_all_checks_initialized_object)
{
	struct k_event event;

	event_prepare(&event, EV_A | EV_B);
	kernel_unit_pass_object_check();

	zassert_equal(z_vrfy_k_event_wait_all(&event, EV_A | EV_B, false, TEST_TIMEOUT),
		      EV_A | EV_B);

	assert_object_check(&event, _OBJ_INIT_TRUE);
	zassert_called_before(k_object_validation_check, unit_arch_irq_lock);
}

/**
 * @brief If the object check fails, z_vrfy_k_event_wait_all() raises an oops before it locks the
 * event object.
 *
 * @details
 * - Setup: an event object with the set A. The object check fails.
 * - Action: z_vrfy_k_event_wait_all(A, no reset, K_NO_WAIT).
 * - Expected: one oops, before arch_irq_lock().
 *
 * @ingroup kernel_unit_event_k_event_wait_all
 * @see z_vrfy_k_event_wait_all()
 */
ZTEST(event_unit, test_syscall_wait_all_oops_on_bad_object)
{
	struct k_event event;

	event_prepare(&event, EV_A);
	kernel_unit_fail_object_check();

	(void)z_vrfy_k_event_wait_all(&event, EV_A, false, K_NO_WAIT);

	zassert_oops_before(unit_arch_irq_lock);
}

/**
 * @brief z_vrfy_k_event_wait_safe() checks that the pointer is an initialized event object, and
 * then returns the result of z_impl_k_event_wait_safe() with the same arguments.
 *
 * @details
 * - Setup: an event object with the set A|C. The object check passes.
 * - Action: z_vrfy_k_event_wait_safe(A|B, no reset, K_NO_WAIT).
 * - Expected: the object check with K_OBJ_EVENT and _OBJ_INIT_TRUE, before
 *   the lock. No oops. Return value A. The set is C (A consumed).
 *
 * @ingroup kernel_unit_event_k_event_wait_safe
 * @see z_vrfy_k_event_wait_safe()
 */
ZTEST(event_unit, test_syscall_wait_safe_checks_initialized_object)
{
	struct k_event event;

	event_prepare(&event, EV_A | EV_C);
	kernel_unit_pass_object_check();

	zassert_equal(z_vrfy_k_event_wait_safe(&event, EV_A | EV_B, false, K_NO_WAIT), EV_A);

	assert_object_check(&event, _OBJ_INIT_TRUE);
	zassert_called_before(k_object_validation_check, unit_arch_irq_lock);
	zassert_equal(event.events, EV_C);
}

/**
 * @brief If the object check fails, z_vrfy_k_event_wait_safe() raises an oops before it locks the
 * event object.
 *
 * @details
 * - Setup: an event object with the set A. The object check fails.
 * - Action: z_vrfy_k_event_wait_safe(A, no reset, K_NO_WAIT).
 * - Expected: one oops, before arch_irq_lock().
 *
 * @ingroup kernel_unit_event_k_event_wait_safe
 * @see z_vrfy_k_event_wait_safe()
 */
ZTEST(event_unit, test_syscall_wait_safe_oops_on_bad_object)
{
	struct k_event event;

	event_prepare(&event, EV_A);
	kernel_unit_fail_object_check();

	(void)z_vrfy_k_event_wait_safe(&event, EV_A, false, K_NO_WAIT);

	zassert_oops_before(unit_arch_irq_lock);
}

/**
 * @brief z_vrfy_k_event_wait_all_safe() checks that the pointer is an initialized event object,
 * and then returns the result of z_impl_k_event_wait_all_safe() with the same arguments.
 *
 * @details
 * - Setup: an event object with the set A|B|C. The object check passes.
 * - Action: z_vrfy_k_event_wait_all_safe(A|B, reset, K_NO_WAIT).
 * - Expected: the object check with K_OBJ_EVENT and _OBJ_INIT_TRUE, before
 *   the lock. No oops. Return value 0 (the reset cleared the set). The set
 *   is 0.
 *
 * @ingroup kernel_unit_event_k_event_wait_all_safe
 * @see z_vrfy_k_event_wait_all_safe()
 */
ZTEST(event_unit, test_syscall_wait_all_safe_checks_initialized_object)
{
	struct k_event event;

	event_prepare(&event, EV_A | EV_B | EV_C);
	kernel_unit_pass_object_check();

	zassert_equal(z_vrfy_k_event_wait_all_safe(&event, EV_A | EV_B, true, K_NO_WAIT), 0U);

	assert_object_check(&event, _OBJ_INIT_TRUE);
	zassert_called_before(k_object_validation_check, unit_arch_irq_lock);
	zassert_equal(event.events, 0U);
}

/**
 * @brief If the object check fails, z_vrfy_k_event_wait_all_safe() raises an oops before it locks
 * the event object.
 *
 * @details
 * - Setup: an event object with the set A. The object check fails.
 * - Action: z_vrfy_k_event_wait_all_safe(A, no reset, K_NO_WAIT).
 * - Expected: one oops, before arch_irq_lock().
 *
 * @ingroup kernel_unit_event_k_event_wait_all_safe
 * @see z_vrfy_k_event_wait_all_safe()
 */
ZTEST(event_unit, test_syscall_wait_all_safe_oops_on_bad_object)
{
	struct k_event event;

	event_prepare(&event, EV_A);
	kernel_unit_fail_object_check();

	(void)z_vrfy_k_event_wait_all_safe(&event, EV_A, false, K_NO_WAIT);

	zassert_oops_before(unit_arch_irq_lock);
}
#endif /* CONFIG_USERSPACE */

#ifdef CONFIG_OBJ_CORE_EVENT
/*
 * Tests: Object core. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_event, at the top of this file.
 */

#ifdef CONFIG_WAITQ_SCALABLE
/*
 * With CONFIG_WAITQ_SCALABLE, Z_WAIT_Q_INIT() in K_EVENT_DEFINE() puts the
 * address of the compare function of the red-black tree
 * (kernel/priority_queues.c) into the static event object. The unit test
 * never walks the tree, so a stub is sufficient. It must not be called.
 */
bool z_priq_rb_lessthan(struct rbnode *a, struct rbnode *b)
{
	ARG_UNUSED(a);
	ARG_UNUSED(b);

	zassert_unreachable("the unit test does not use the red-black tree");

	return false;
}
#endif /* CONFIG_WAITQ_SCALABLE */

K_EVENT_DEFINE(unit_static_event);

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

/**
 * @brief With CONFIG_OBJ_CORE_EVENT, k_event_init() links the object core of the event object to
 * the event object type.
 *
 * @details
 * - Action: z_impl_k_event_init().
 * - Expected: one call of k_obj_core_init_and_link() with the object core
 *   of the event object and @c obj_type_event, after z_waitq_init().
 *
 * @ingroup kernel_unit_event_k_event_init
 * @see z_impl_k_event_init()
 */
ZTEST(event_unit, test_obj_core_init_links_event)
{
	struct k_event event;

	z_impl_k_event_init(&event);

	zassert_equal(k_obj_core_init_and_link_fake.call_count, 1);
	zassert_equal_ptr(k_obj_core_init_and_link_fake.arg0_val, K_OBJ_CORE(&event));
	zassert_equal_ptr(k_obj_core_init_and_link_fake.arg1_val, &obj_type_event);
	zassert_called_before(z_waitq_init, k_obj_core_init_and_link);
}

/**
 * @brief With CONFIG_OBJ_CORE_EVENT, events.c defines one object type descriptor with the ID
 * K_OBJ_TYPE_EVENT_ID.
 *
 * @details
 * - Action: search the section @c k_obj_core_desc for the descriptor of
 *   @c obj_type_event.
 * - Expected: one descriptor. Its type ID is K_OBJ_TYPE_EVENT_ID. Its
 *   object size is the size of @c struct @c k_event, and its object core
 *   offset is the offset of @c obj_core. Its object range is the section
 *   @c k_event.
 *
 * @ingroup kernel_unit_event_static
 */
ZTEST(event_unit, test_obj_core_type_descriptor)
{
	int count;
	const struct k_obj_core_desc *desc = obj_core_desc(&obj_type_event, &count);

	zassert_equal(count, 1);
	zassert_not_null(desc);
	zassert_equal(desc->type_id, K_OBJ_TYPE_EVENT_ID);
	zassert_equal(desc->obj_size, sizeof(struct k_event));
	zassert_equal(desc->obj_core_offset, offsetof(struct k_event, obj_core));
	zassert_equal_ptr(desc->objs_start, STRUCT_SECTION_START(k_event));
	zassert_equal_ptr(desc->objs_end, STRUCT_SECTION_END(k_event));
}

/**
 * @brief The object range of the descriptor contains the event objects that K_EVENT_DEFINE()
 * defines.
 *
 * @details
 * - Setup: K_EVENT_DEFINE() of one event object in the test.
 * - Action: compare the address of the event object with the object range
 *   of the descriptor.
 * - Expected: the event object is in the range, at a multiple of the
 *   object size from the start.
 *
 * @ingroup kernel_unit_event_static
 */
ZTEST(event_unit, test_obj_core_descriptor_covers_static_events)
{
	int count;
	const struct k_obj_core_desc *desc = obj_core_desc(&obj_type_event, &count);
	uintptr_t obj = (uintptr_t)&unit_static_event;

	zassert_not_null(desc);
	zassert_true((obj >= (uintptr_t)desc->objs_start) && (obj < (uintptr_t)desc->objs_end));
	zassert_equal((obj - (uintptr_t)desc->objs_start) % desc->obj_size, 0U);
}
#endif /* CONFIG_OBJ_CORE_EVENT */
