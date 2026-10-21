/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @defgroup kernel_unit_sem Semaphore unit (kernel/sem.c)
 * @ingroup kernel_unit_tests
 * @brief Design specification of kernel/sem.c, written as unit tests.
 *
 * @par The semaphore object
 * A semaphore (@c struct @c k_sem) is a counting semaphore with these parts:
 * - @c count: the number of times that threads can take the semaphore
 *   without a wait.
 * - @c limit: the maximum count. k_sem_give() does not increment the count
 *   above the limit. The limit is not 0.
 * - @c wait_q: the wait queue of the threads that wait in k_sem_take().
 * - @c poll_events: with @kconfig{CONFIG_POLL}, the k_poll() events on the
 *   semaphore.
 * - @c obj_core: with @kconfig{CONFIG_OBJ_CORE_SEM}, the link of the
 *   semaphore into the object core list of its type.
 *
 * @par Operations
 * - k_sem_init() sets the count and the limit and initializes the other
 *   parts. It rejects a limit of 0 and a count above the limit.
 * - k_sem_give() hands the semaphore to one waiting thread. If no thread
 *   waits, it increments the count (up to the limit) and signals the poll
 *   events.
 * - k_sem_take() decrements the count if the count is not 0. Otherwise it
 *   returns -EBUSY (timeout K_NO_WAIT) or waits on the wait queue.
 * - k_sem_reset() sets the count to 0, wakes all waiting threads with
 *   -EAGAIN and signals the poll events.
 * - k_sem_count_get() returns the count. It is static inline in
 *   @c zephyr/kernel.h. sem.c has only its verification function.
 *
 * A thread waits only if the count is 0, and k_sem_give() does not increment
 * the count if it wakes a thread. Thus, while a thread waits, the count stays
 * 0.
 *
 * @par One lock for all semaphores
 * sem.c has one spinlock for all semaphores, the static @c sem_lock. A lock
 * in each semaphore needs more RAM, and applications use many semaphores.
 * The cost is contention: two CPUs that use different semaphores also wait
 * for each other.
 *
 * k_sem_give(), k_sem_take() and k_sem_reset() lock @c sem_lock before they
 * read the count or use the wait queue. k_spin_lock() locks the interrupts
 * with arch_irq_lock() and returns a key. Each path releases the lock
 * exactly once, with the same key, as its last call to the layers below:
 * - k_spin_unlock(), if no thread became ready.
 * - z_reschedule(), if the operation made a thread ready. z_reschedule()
 *   releases the lock and can switch to the ready thread.
 * - z_pend_curr(), if k_sem_take() must wait. z_pend_curr() adds the current
 *   thread to the wait queue, releases the lock and switches threads in one
 *   step. Thus no k_sem_give() can occur between the decision to wait and
 *   the wait.
 *
 * k_sem_init() and k_sem_count_get() do not lock @c sem_lock.
 *
 * @par Interfaces below sem.c
 * - Scheduler (@c ksched.h): z_sched_wake(), z_reschedule(), z_pend_curr().
 * - Wait queue (@c wait_q.h): z_waitq_init().
 * - Poll (@c kernel_internal.h): z_handle_obj_poll_events().
 * - Object core: k_obj_core_init_and_link(), K_OBJ_TYPE_DEFINE().
 * - Kernel objects: k_object_init().
 * - System call checks: K_SYSCALL_OBJ(), K_SYSCALL_OBJ_INIT(), K_OOPS().
 * - Architecture: arch_irq_lock() and arch_irq_unlock() through
 *   k_spin_lock() and k_spin_unlock(), and arch_is_in_isr() in an
 *   assertion.
 *
 * @par Kconfig options that change sem.c
 * - @kconfig{CONFIG_POLL}: the poll events of the semaphore.
 * - @kconfig{CONFIG_OBJ_CORE_SEM}: the object core link and the object type
 *   descriptor.
 * - @kconfig{CONFIG_USERSPACE}: the verification functions z_vrfy_k_sem_*()
 *   and the kernel object of the semaphore.
 * - The CHECKIF() options for the argument check of k_sem_init():
 *   @kconfig{CONFIG_RUNTIME_ERROR_CHECKS} (default) returns -EINVAL,
 *   @kconfig{CONFIG_NO_RUNTIME_CHECKS} does no check,
 *   @kconfig{CONFIG_ASSERT_ON_ERRORS} asserts.
 * - @kconfig{CONFIG_ASSERT}: the assertion in k_sem_take() that an ISR does
 *   not wait. It also enables @kconfig{CONFIG_SPIN_VALIDATE} in
 *   @c zephyr/spinlock.h.
 *
 * @par Test method
 * The tests call z_impl_k_sem_*() and z_vrfy_k_sem_*() directly. All calls
 * below sem.c go to FFF fakes. The fake unit_arch_irq_lock() returns
 * KERNEL_UNIT_IRQ_KEY. Thus a test can follow the key to the call that
 * releases the lock. The FFF call history gives the order of the calls.
 * The scenarios in @c testcase.yaml build the tests once for each Kconfig
 * option above. A test that applies only to some configurations is in an
 * @c \#ifdef block, or it calls ztest_test_skip().
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

#include <kernel/sem.c>

/* Value that fills a semaphore before a test, to show the fields that the unit writes. */
#define SEM_FILL 0xA5

/* Value of a semaphore field that SEM_FILL gives */
#define SEM_FILL_UINT 0xA5A5A5A5U

/* Timeout that is not K_NO_WAIT and not K_FOREVER */
#define TEST_TIMEOUT K_TICKS(10)

/* Value of a spy record before the spy fake runs */
#define COUNT_UNSET 0xDEADBEEFU

/*
 * The semaphore that the spy fakes read. A spy fake records the count at
 * the time of its call. Thus a test sees the order of the state changes
 * and the calls to the layers below.
 */
static struct k_sem *spied_sem;
static unsigned int count_at_lock;
static unsigned int count_at_release;
static unsigned int count_at_poll;

/* Observers of the lock spies (kernel_unit_spy_on_lock()). */
static void observe_lock(void)
{
	count_at_lock = spied_sem->count;
}

static void observe_release(void)
{
	count_at_release = spied_sem->count;
}

static int pend_spy(struct k_spinlock *lock, k_spinlock_key_t key, _wait_q_t *wait_q,
		    k_timeout_t timeout)
{
	ARG_UNUSED(lock);
	ARG_UNUSED(key);
	ARG_UNUSED(wait_q);
	ARG_UNUSED(timeout);

	count_at_release = spied_sem->count;

	return 0;
}

static __maybe_unused bool poll_spy(sys_dlist_t *events, uint32_t state)
{
	ARG_UNUSED(events);
	ARG_UNUSED(state);

	count_at_poll = spied_sem->count;

	return false;
}

/* Install the spy fakes of the lock and of the three release paths. */
static void spy_on_lock(struct k_sem *sem)
{
	spied_sem = sem;
	count_at_lock = COUNT_UNSET;
	count_at_release = COUNT_UNSET;
	kernel_unit_spy_on_lock(observe_lock, observe_release);
	z_pend_curr_fake.custom_fake = pend_spy;
}

/* Put a semaphore into a known state without k_sem_init(). */
static void sem_prepare(struct k_sem *sem, unsigned int count, unsigned int limit)
{
	memset(sem, 0, sizeof(*sem));
	sem->count = count;
	sem->limit = limit;
}

/*
 * Assert the lock invariant of one operation (kernel_unit_models.h) on
 * sem_lock. The check permits calls before the lock: with CONFIG_ASSERT,
 * k_sem_take() calls arch_is_in_isr() before the lock.
 */
static void assert_lock_released_once(enum kernel_unit_release how)
{
	kernel_unit_assert_lock_rule(&(const struct kernel_unit_lock_rule){
		.lock = &sem_lock, .how = how, .before_lock = kernel_unit_any_call});
}

static void sem_unit_before(void *fixture)
{
	ARG_UNUSED(fixture);

	/* The fake rules reset all fakes before this function. */
	unit_arch_irq_lock_fake.return_val = KERNEL_UNIT_IRQ_KEY;
	spied_sem = NULL;
}

ZTEST_SUITE(sem_unit, NULL, NULL, sem_unit_before, NULL, NULL);

/**
 * @defgroup kernel_unit_sem_init Initialization
 * @ingroup kernel_unit_sem
 * @brief k_sem_init() sets the count and the limit and initializes the parts of the semaphore.
 *
 * k_sem_init() first checks its arguments with CHECKIF(). The Kconfig
 * options of CHECKIF() change what an invalid argument causes. Then
 * k_sem_init() writes the count and the limit. It initializes the wait
 * queue, the poll events and the kernel object. Its last step is the link of
 * the object core. It does not lock @c sem_lock: until k_sem_init()
 * returns, only the caller uses the semaphore.
 */

/**
 * @brief k_sem_init() sets the count to the initial count and the limit to the given limit.
 *
 * @details
 * - Setup: a semaphore filled with a pattern.
 * - Action: z_impl_k_sem_init() with count 2 and limit 5.
 * - Expected: return value 0, count 2, limit 5.
 *
 * @ingroup kernel_unit_sem_init
 * @see z_impl_k_sem_init()
 */
ZTEST(sem_unit, test_init_sets_count_and_limit)
{
	struct k_sem sem;

	memset(&sem, SEM_FILL, sizeof(sem));

	zassert_equal(z_impl_k_sem_init(&sem, 2U, 5U), 0);

	zassert_equal(sem.count, 2U);
	zassert_equal(sem.limit, 5U);
}

/**
 * @brief k_sem_init() accepts a count equal to the limit, and a limit up to K_SEM_MAX_LIMIT.
 *
 * @details
 * - Action: z_impl_k_sem_init() with count 0 and limit 1, with count 1 and
 *   limit 1, and with count and limit K_SEM_MAX_LIMIT.
 * - Expected: return value 0 each time. The count and the limit have the
 *   given values.
 *
 * @ingroup kernel_unit_sem_init
 * @see z_impl_k_sem_init()
 */
ZTEST(sem_unit, test_init_accepts_boundary_values)
{
	struct k_sem sem;

	zassert_equal(z_impl_k_sem_init(&sem, 0U, 1U), 0);
	zassert_equal(sem.count, 0U);
	zassert_equal(sem.limit, 1U);

	zassert_equal(z_impl_k_sem_init(&sem, 1U, 1U), 0);
	zassert_equal(sem.count, 1U);
	zassert_equal(sem.limit, 1U);

	zassert_equal(z_impl_k_sem_init(&sem, K_SEM_MAX_LIMIT, K_SEM_MAX_LIMIT), 0);
	zassert_equal(sem.count, K_SEM_MAX_LIMIT);
	zassert_equal(sem.limit, K_SEM_MAX_LIMIT);
}

/**
 * @brief k_sem_init() initializes the wait queue of the semaphore.
 *
 * @details
 * - Action: z_impl_k_sem_init() with count 0 and limit 1.
 * - Expected: one call of z_waitq_init() with the wait queue of the
 *   semaphore.
 *
 * @ingroup kernel_unit_sem_init
 * @see z_impl_k_sem_init()
 */
ZTEST(sem_unit, test_init_initializes_wait_queue)
{
	struct k_sem sem;

	zassert_equal(z_impl_k_sem_init(&sem, 0U, 1U), 0);

	zassert_equal(z_waitq_init_fake.call_count, 1);
	zassert_equal_ptr(z_waitq_init_fake.arg0_val, &sem.wait_q);
}

#ifdef CONFIG_POLL
/**
 * @brief With CONFIG_POLL, k_sem_init() makes the list of poll events empty.
 *
 * @details
 * - Setup: a semaphore filled with a pattern.
 * - Action: z_impl_k_sem_init() with count 0 and limit 1.
 * - Expected: the list @c poll_events is a valid, empty list.
 *
 * @ingroup kernel_unit_sem_init
 * @see z_impl_k_sem_init()
 */
ZTEST(sem_unit, test_init_empties_poll_events)
{
	struct k_sem sem;

	memset(&sem, SEM_FILL, sizeof(sem));

	zassert_equal(z_impl_k_sem_init(&sem, 0U, 1U), 0);

	zassert_true(sys_dlist_is_empty(&sem.poll_events));
}
#endif /* CONFIG_POLL */

#ifdef CONFIG_USERSPACE
/**
 * @brief With CONFIG_USERSPACE, k_sem_init() marks the semaphore as an initialized kernel object.
 *
 * @details
 * - Action: z_impl_k_sem_init() with count 0 and limit 1.
 * - Expected: one call of k_object_init() with the semaphore. After this
 *   call, the object checks of the other system calls accept the
 *   semaphore.
 *
 * @ingroup kernel_unit_sem_init
 * @see z_impl_k_sem_init()
 */
ZTEST(sem_unit, test_init_initializes_kernel_object)
{
	struct k_sem sem;

	zassert_equal(z_impl_k_sem_init(&sem, 0U, 1U), 0);

	zassert_equal(k_object_init_fake.call_count, 1);
	zassert_equal_ptr(k_object_init_fake.arg0_val, &sem);
}
#endif /* CONFIG_USERSPACE */

/**
 * @brief k_sem_init() initializes the wait queue, then the kernel object, then the object core.
 *
 * @details
 * - Action: z_impl_k_sem_init() with count 0 and limit 1.
 * - Expected calls, in this order: z_waitq_init(), k_object_init() (with
 *   CONFIG_USERSPACE), k_obj_core_init_and_link() (with
 *   CONFIG_OBJ_CORE_SEM). There are no other calls. The object core link
 *   makes the semaphore visible to other code, so it is the last step.
 *
 * @ingroup kernel_unit_sem_init
 * @see z_impl_k_sem_init()
 */
ZTEST(sem_unit, test_init_call_order)
{
	struct k_sem sem;

	zassert_equal(z_impl_k_sem_init(&sem, 0U, 1U), 0);

	zassert_call_history(z_waitq_init, KERNEL_UNIT_IF_ENABLED(CONFIG_USERSPACE, k_object_init),
			     KERNEL_UNIT_IF_ENABLED(CONFIG_OBJ_CORE_SEM, k_obj_core_init_and_link));
}

/**
 * @brief k_sem_init() returns -EINVAL and changes nothing if the limit is 0.
 *
 * @details
 * Applies with CONFIG_RUNTIME_ERROR_CHECKS (the default CHECKIF() option).
 * - Setup: a semaphore filled with a pattern.
 * - Action: z_impl_k_sem_init() with count 0 and limit 0.
 * - Expected: return value -EINVAL. The semaphore has the pattern. No
 *   calls to the layers below.
 *
 * @ingroup kernel_unit_sem_init
 * @see z_impl_k_sem_init()
 */
ZTEST(sem_unit, test_init_rejects_zero_limit)
{
	struct k_sem sem;
	struct k_sem before;

	if (!IS_ENABLED(CONFIG_RUNTIME_ERROR_CHECKS)) {
		ztest_test_skip();
	}

	memset(&sem, SEM_FILL, sizeof(sem));
	before = sem;

	zassert_equal(z_impl_k_sem_init(&sem, 0U, 0U), -EINVAL);

	zassert_mem_equal(&sem, &before, sizeof(sem));
	zassert_equal(kernel_unit_history_len(), 0);
}

/**
 * @brief k_sem_init() returns -EINVAL and changes nothing if the count is above the limit.
 *
 * @details
 * Applies with CONFIG_RUNTIME_ERROR_CHECKS (the default CHECKIF() option).
 * - Setup: a semaphore filled with a pattern.
 * - Action: z_impl_k_sem_init() with count 3 and limit 2.
 * - Expected: return value -EINVAL. The semaphore has the pattern. No
 *   calls to the layers below.
 *
 * @ingroup kernel_unit_sem_init
 * @see z_impl_k_sem_init()
 */
ZTEST(sem_unit, test_init_rejects_count_above_limit)
{
	struct k_sem sem;
	struct k_sem before;

	if (!IS_ENABLED(CONFIG_RUNTIME_ERROR_CHECKS)) {
		ztest_test_skip();
	}

	memset(&sem, SEM_FILL, sizeof(sem));
	before = sem;

	zassert_equal(z_impl_k_sem_init(&sem, 3U, 2U), -EINVAL);

	zassert_mem_equal(&sem, &before, sizeof(sem));
	zassert_equal(kernel_unit_history_len(), 0);
}

/**
 * @brief With CONFIG_NO_RUNTIME_CHECKS, k_sem_init() accepts a limit of 0 and a count above the
 * limit.
 *
 * @details
 * CHECKIF() is empty, so the caller must give valid arguments.
 * - Action: z_impl_k_sem_init() with count 0 and limit 0, then with count
 *   3 and limit 2.
 * - Expected: return value 0 each time. The semaphore has the invalid
 *   count and limit. See test_give_count_above_limit_grows() for the
 *   result.
 *
 * @ingroup kernel_unit_sem_init
 * @see z_impl_k_sem_init()
 */
ZTEST(sem_unit, test_init_no_runtime_checks_accepts_invalid)
{
	struct k_sem sem;

	if (!IS_ENABLED(CONFIG_NO_RUNTIME_CHECKS)) {
		ztest_test_skip();
	}

	zassert_equal(z_impl_k_sem_init(&sem, 0U, 0U), 0);
	zassert_equal(sem.count, 0U);
	zassert_equal(sem.limit, 0U);

	zassert_equal(z_impl_k_sem_init(&sem, 3U, 2U), 0);
	zassert_equal(sem.count, 3U);
	zassert_equal(sem.limit, 2U);
}

#ifdef CONFIG_ASSERT_ON_ERRORS
/**
 * @brief With CONFIG_ASSERT_ON_ERRORS, k_sem_init() asserts that the limit is not 0 and that the
 * count is not above the limit.
 *
 * @details
 * - Action: z_impl_k_sem_init() with count 0 and limit 0, with count 3 and
 *   limit 2, and with count 1 and limit 2.
 * - Expected: one failed assertion for each of the two invalid calls, and
 *   no failed assertion for the valid call. The assertion comes before
 *   the first change of the semaphore (z_waitq_init()).
 *
 * In the test, the assertion hook assert_post_action() returns
 * (CONFIG_ASSERT_TEST). Then k_sem_init() continues and returns 0. In a
 * real build, the hook does not return.
 *
 * @ingroup kernel_unit_sem_init
 * @see z_impl_k_sem_init()
 */
ZTEST(sem_unit, test_init_assert_on_errors)
{
	struct k_sem sem;

	(void)z_impl_k_sem_init(&sem, 0U, 0U);
	zassert_equal(assert_post_action_fake.call_count, 1);
	zassert_called_before(assert_post_action, z_waitq_init);

	(void)z_impl_k_sem_init(&sem, 3U, 2U);
	zassert_equal(assert_post_action_fake.call_count, 2);

	zassert_equal(z_impl_k_sem_init(&sem, 1U, 2U), 0);
	zassert_equal(assert_post_action_fake.call_count, 2);
}
#endif /* CONFIG_ASSERT_ON_ERRORS */

/**
 * @defgroup kernel_unit_sem_give Give
 * @ingroup kernel_unit_sem
 * @brief k_sem_give() hands the semaphore to a waiting thread, or increments the count.
 *
 * k_sem_give() first tries to wake one thread from the wait queue with
 * z_sched_wake(). If a thread wakes, the semaphore goes to this thread: its
 * k_sem_take() returns 0, and the count does not change. If no thread
 * wakes, k_sem_give() increments the count, but not above the limit, and
 * signals the poll events (see @ref kernel_unit_sem_poll).
 */

/**
 * @brief If no thread waits, k_sem_give() increments the count by one.
 *
 * @details
 * - Setup: count 0, limit 3. z_sched_wake() wakes no thread.
 * - Action: z_impl_k_sem_give() two times.
 * - Expected: count 1, then count 2. The limit does not change.
 *
 * @ingroup kernel_unit_sem_give
 * @see z_impl_k_sem_give()
 */
ZTEST(sem_unit, test_give_increments_count)
{
	struct k_sem sem;

	sem_prepare(&sem, 0U, 3U);

	z_impl_k_sem_give(&sem);
	zassert_equal(sem.count, 1U);

	z_impl_k_sem_give(&sem);
	zassert_equal(sem.count, 2U);
	zassert_equal(sem.limit, 3U);
}

/**
 * @brief k_sem_give() does not increment the count above the limit.
 *
 * @details
 * - Setup: count 3, limit 3. z_sched_wake() wakes no thread.
 * - Action: z_impl_k_sem_give().
 * - Expected: count 3. k_sem_give() has no error return, so the extra give
 *   is lost without a report.
 *
 * @ingroup kernel_unit_sem_give
 * @see z_impl_k_sem_give()
 */
ZTEST(sem_unit, test_give_saturates_at_limit)
{
	struct k_sem sem;

	sem_prepare(&sem, 3U, 3U);

	z_impl_k_sem_give(&sem);

	zassert_equal(sem.count, 3U);
}

/**
 * @brief If a thread waits, k_sem_give() hands the semaphore to this thread and does not change the
 * count.
 *
 * @details
 * - Setup: count 0, limit 3. z_sched_wake() wakes a thread.
 * - Action: z_impl_k_sem_give().
 * - Expected: one call of z_sched_wake() with the wait queue of the
 *   semaphore, the return value 0 for the woken thread and no swap data.
 *   Thus the k_sem_take() of the woken thread returns 0. The count stays 0.
 *
 * @ingroup kernel_unit_sem_give
 * @see z_impl_k_sem_give()
 */
ZTEST(sem_unit, test_give_hands_over_to_waiting_thread)
{
	struct k_sem sem;

	sem_prepare(&sem, 0U, 3U);
	z_sched_wake_fake.return_val = true;

	z_impl_k_sem_give(&sem);

	zassert_equal(z_sched_wake_fake.call_count, 1);
	zassert_equal_ptr(z_sched_wake_fake.arg0_val, &sem.wait_q);
	zassert_equal(z_sched_wake_fake.arg1_val, 0);
	zassert_is_null(z_sched_wake_fake.arg2_val);
	zassert_equal(sem.count, 0U);
}

/**
 * @brief k_sem_give() wakes at most one thread.
 *
 * @details
 * - Setup: count 0, limit 3. z_sched_wake() wakes a thread each time
 *   (more threads wait).
 * - Action: z_impl_k_sem_give().
 * - Expected: one call of z_sched_wake().
 *
 * @ingroup kernel_unit_sem_give
 * @see z_impl_k_sem_give()
 */
ZTEST(sem_unit, test_give_wakes_one_thread_only)
{
	struct k_sem sem;

	sem_prepare(&sem, 0U, 3U);
	z_sched_wake_fake.return_val = true;

	z_impl_k_sem_give(&sem);

	zassert_equal(z_sched_wake_fake.call_count, 1);
}

/**
 * @brief Without runtime checks, k_sem_give() increments a count that is above the limit.
 *
 * @details
 * Applies with CONFIG_NO_RUNTIME_CHECKS. Only then can k_sem_init() make a
 * count above the limit (see test_init_no_runtime_checks_accepts_invalid()).
 * k_sem_give() compares the count with the limit for equality, not for
 * "less than".
 * - Setup: count 3, limit 2.
 * - Action: z_impl_k_sem_give().
 * - Expected: count 4.
 *
 * @ingroup kernel_unit_sem_give
 * @see z_impl_k_sem_give()
 */
ZTEST(sem_unit, test_give_count_above_limit_grows)
{
	struct k_sem sem;

	if (!IS_ENABLED(CONFIG_NO_RUNTIME_CHECKS)) {
		ztest_test_skip();
	}

	zassert_equal(z_impl_k_sem_init(&sem, 3U, 2U), 0);

	z_impl_k_sem_give(&sem);

	zassert_equal(sem.count, 4U);
}

/**
 * @defgroup kernel_unit_sem_take Take
 * @ingroup kernel_unit_sem
 * @brief k_sem_take() decrements the count, returns -EBUSY, or waits.
 *
 * If the count is not 0, k_sem_take() decrements it and returns 0 at once,
 * for each timeout. If the count is 0 and the timeout is K_NO_WAIT, it
 * returns -EBUSY. Otherwise it waits on the wait queue with z_pend_curr()
 * and returns the result of the wait: 0 if k_sem_give() woke the thread,
 * -EAGAIN at the timeout or after k_sem_reset(). An ISR must not wait, so
 * with CONFIG_ASSERT, k_sem_take() asserts that an ISR gives K_NO_WAIT. In an
 * ISR, a wait reaches z_pend_curr(), and the scheduler refuses it with a
 * panic in every build. Without CONFIG_ASSERT, k_sem_take() has no earlier
 * check of its own.
 */

/**
 * @brief If the count is not 0, k_sem_take() decrements the count and returns 0.
 *
 * @details
 * - Setup: count 2, limit 3.
 * - Action: z_impl_k_sem_take() with K_NO_WAIT, two times.
 * - Expected: return value 0, count 1, then return value 0, count 0.
 *
 * @ingroup kernel_unit_sem_take
 * @see z_impl_k_sem_take()
 */
ZTEST(sem_unit, test_take_decrements_count)
{
	struct k_sem sem;

	sem_prepare(&sem, 2U, 3U);

	zassert_equal(z_impl_k_sem_take(&sem, K_NO_WAIT), 0);
	zassert_equal(sem.count, 1U);

	zassert_equal(z_impl_k_sem_take(&sem, K_NO_WAIT), 0);
	zassert_equal(sem.count, 0U);
}

/**
 * @brief If the count is not 0, k_sem_take() does not wait, also if the timeout permits a wait.
 *
 * @details
 * - Setup: count 1, limit 1.
 * - Action: z_impl_k_sem_take() with K_FOREVER.
 * - Expected: return value 0, count 0. No call of z_pend_curr().
 *
 * @ingroup kernel_unit_sem_take
 * @see z_impl_k_sem_take()
 */
ZTEST(sem_unit, test_take_available_does_not_wait)
{
	struct k_sem sem;

	sem_prepare(&sem, 1U, 1U);

	zassert_equal(z_impl_k_sem_take(&sem, K_FOREVER), 0);

	zassert_equal(sem.count, 0U);
	zassert_equal(z_pend_curr_fake.call_count, 0);
}

/**
 * @brief If the count is 0 and the timeout is K_NO_WAIT, k_sem_take() returns -EBUSY.
 *
 * @details
 * - Setup: count 0, limit 1.
 * - Action: z_impl_k_sem_take() with K_NO_WAIT.
 * - Expected: return value -EBUSY, count 0. No call of z_pend_curr().
 *
 * @ingroup kernel_unit_sem_take
 * @see z_impl_k_sem_take()
 */
ZTEST(sem_unit, test_take_unavailable_no_wait_returns_ebusy)
{
	struct k_sem sem;

	sem_prepare(&sem, 0U, 1U);

	zassert_equal(z_impl_k_sem_take(&sem, K_NO_WAIT), -EBUSY);

	zassert_equal(sem.count, 0U);
	zassert_equal(z_pend_curr_fake.call_count, 0);
}

/**
 * @brief If the count is 0 and the timeout is not K_NO_WAIT, k_sem_take() waits on the wait queue
 * with this timeout.
 *
 * @details
 * - Setup: count 0, limit 1.
 * - Action: z_impl_k_sem_take() with a timeout of 10 ticks, then with
 *   K_FOREVER.
 * - Expected: each time, one call of z_pend_curr() with the wait queue of
 *   the semaphore and the given timeout. The count stays 0.
 *
 * @ingroup kernel_unit_sem_take
 * @see z_impl_k_sem_take()
 */
ZTEST(sem_unit, test_take_unavailable_waits)
{
	struct k_sem sem;

	sem_prepare(&sem, 0U, 1U);

	(void)z_impl_k_sem_take(&sem, TEST_TIMEOUT);

	zassert_equal(z_pend_curr_fake.call_count, 1);
	zassert_equal_ptr(z_pend_curr_fake.arg2_val, &sem.wait_q);
	zassert_true(K_TIMEOUT_EQ(z_pend_curr_fake.arg3_val, TEST_TIMEOUT));

	(void)z_impl_k_sem_take(&sem, K_FOREVER);

	zassert_equal(z_pend_curr_fake.call_count, 2);
	zassert_true(K_TIMEOUT_EQ(z_pend_curr_fake.arg3_val, K_FOREVER));
	zassert_equal(sem.count, 0U);
}

/**
 * @brief After a wait, k_sem_take() returns the result of the wait without a change.
 *
 * @details
 * - Setup: count 0, limit 1. z_pend_curr() returns 0 (a k_sem_give()
 *   woke the thread), then -EAGAIN (timeout or k_sem_reset()).
 * - Action: z_impl_k_sem_take() with K_FOREVER, two times.
 * - Expected: return value 0, then -EAGAIN. The count stays 0: k_sem_give()
 *   handed the semaphore over without the count.
 *
 * @ingroup kernel_unit_sem_take
 * @see z_impl_k_sem_take()
 */
ZTEST(sem_unit, test_take_returns_wait_result)
{
	struct k_sem sem;
	int results[] = {0, -EAGAIN};

	sem_prepare(&sem, 0U, 1U);
	SET_RETURN_SEQ(z_pend_curr, results, ARRAY_SIZE(results));

	zassert_equal(z_impl_k_sem_take(&sem, K_FOREVER), 0);
	zassert_equal(z_impl_k_sem_take(&sem, K_FOREVER), -EAGAIN);

	zassert_equal(sem.count, 0U);
}

/**
 * @brief An ISR can take a semaphore with K_NO_WAIT.
 *
 * @details
 * - Setup: arch_is_in_isr() returns true. Count 1, limit 1.
 * - Action: z_impl_k_sem_take() with K_NO_WAIT, two times.
 * - Expected: return value 0, then -EBUSY. No failed assertion (with
 *   CONFIG_ASSERT). No call of z_pend_curr().
 *
 * @ingroup kernel_unit_sem_take
 * @see z_impl_k_sem_take()
 */
ZTEST(sem_unit, test_take_in_isr_without_wait)
{
	struct k_sem sem;

	sem_prepare(&sem, 1U, 1U);
	arch_is_in_isr_fake.return_val = true;

	zassert_equal(z_impl_k_sem_take(&sem, K_NO_WAIT), 0);
	zassert_equal(z_impl_k_sem_take(&sem, K_NO_WAIT), -EBUSY);

	zassert_equal(z_pend_curr_fake.call_count, 0);
#ifdef CONFIG_ASSERT
	zassert_equal(assert_post_action_fake.call_count, 0);
#endif
}

#ifdef CONFIG_ASSERT
/**
 * @brief With CONFIG_ASSERT, k_sem_take() asserts that only a thread gives a timeout other than
 * K_NO_WAIT.
 *
 * @details
 * - Action and expected result:
 *   - A thread calls z_impl_k_sem_take() with K_FOREVER: no failed
 *     assertion.
 *   - An ISR calls z_impl_k_sem_take() with K_NO_WAIT: no failed
 *     assertion.
 *   - An ISR calls z_impl_k_sem_take() with K_FOREVER: one failed
 *     assertion of k_sem_take(). The assertion comes before the lock of
 *     @c sem_lock.
 * - Setup of each call: count 0, limit 1.
 *
 * In the test, the assertion hook assert_post_action() returns
 * (CONFIG_ASSERT_TEST). Then k_sem_take() continues and calls
 * z_pend_curr() in the ISR. The scheduler refuses the wait with a second
 * failed assertion and a panic (see
 * test_take_in_isr_with_wait_refused_by_scheduler). In a real build, the
 * first hook does not return. Without CONFIG_ASSERT, k_sem_take() has no
 * check of its own, and only the panic of the scheduler stops the wait.
 *
 * @ingroup kernel_unit_sem_take
 * @see z_impl_k_sem_take()
 */
ZTEST(sem_unit, test_take_asserts_isr_does_not_wait)
{
	struct k_sem sem;

	sem_prepare(&sem, 0U, 1U);

	arch_is_in_isr_fake.return_val = false;
	(void)z_impl_k_sem_take(&sem, K_FOREVER);
	zassert_equal(assert_post_action_fake.call_count, 0);

	arch_is_in_isr_fake.return_val = true;
	(void)z_impl_k_sem_take(&sem, K_NO_WAIT);
	zassert_equal(assert_post_action_fake.call_count, 0);

	FFF_RESET_HISTORY();
	kernel_unit_expect_pend_refusal();
	(void)z_impl_k_sem_take(&sem, K_FOREVER);
	zassert_equal(assert_post_action_fake.call_count, 2);
	zassert_called_before(arch_is_in_isr, assert_post_action);
	zassert_called_before(assert_post_action, unit_arch_irq_lock);
	kernel_unit_assert_pend_refused();
}
#endif /* CONFIG_ASSERT */

/**
 * @brief In an ISR, a k_sem_take() that must wait reaches z_pend_curr(), and the scheduler
 * refuses it with a panic.
 *
 * @details
 * The real z_pend_curr() refuses a call from an ISR in every build, before
 * it changes a thread or a wait queue. k_sem_take() has an earlier check only
 * with CONFIG_ASSERT (see test_take_asserts_isr_does_not_wait).
 * - Setup: arch_is_in_isr() returns true. Count 0, limit 1. The test
 *   expects the refusal of z_pend_curr().
 * - Action: z_impl_k_sem_take() with K_FOREVER.
 * - Expected: one call of z_pend_curr() with @c sem_lock and the key. The
 *   scheduler refuses it with a failed assertion (with CONFIG_ASSERT) and a
 *   panic. With CONFIG_ASSERT, the assertion of k_sem_take() comes first,
 *   before the lock. The lock stays locked, no thread is woken, and the
 *   count stays 0. After the panic, the fake returns
 *   KERNEL_UNIT_PEND_REFUSED, and k_sem_take() gives this value to the
 *   caller.
 *
 * @ingroup kernel_unit_sem_take
 * @see z_impl_k_sem_take()
 */
ZTEST(sem_unit, test_take_in_isr_with_wait_refused_by_scheduler)
{
	struct k_sem sem;

	sem_prepare(&sem, 0U, 1U);
	arch_is_in_isr_fake.return_val = true;
	kernel_unit_expect_pend_refusal();

	zassert_equal(z_impl_k_sem_take(&sem, K_FOREVER), KERNEL_UNIT_PEND_REFUSED);

	kernel_unit_assert_pend_refused();
	zassert_equal(z_pend_curr_fake.call_count, 1);
	zassert_equal_ptr(z_pend_curr_fake.arg0_val, &sem_lock);
	zassert_equal((unsigned int)z_pend_curr_fake.arg1_val.key, KERNEL_UNIT_IRQ_KEY);
	zassert_equal(unit_arch_irq_unlock_fake.call_count, 0);
	zassert_equal(z_reschedule_fake.call_count, 0);
	zassert_equal(z_sched_wake_fake.call_count, 0);
	zassert_equal(sem.count, 0U);
#ifdef CONFIG_ASSERT
	zassert_equal(assert_post_action_fake.call_count, 2);
	zassert_called_before(assert_post_action, unit_arch_irq_lock);
#endif
}

/**
 * @defgroup kernel_unit_sem_reset Reset
 * @ingroup kernel_unit_sem
 * @brief k_sem_reset() sets the count to 0 and makes all waiting threads stop their wait with
 * -EAGAIN.
 *
 * k_sem_reset() wakes the threads of the wait queue one by one with
 * z_sched_wake() until the queue is empty. Each woken thread gets the
 * return value -EAGAIN. Then k_sem_reset() sets the count to 0 and signals
 * the poll events (see @ref kernel_unit_sem_poll). It reschedules once if
 * it woke a thread or if the poll subsystem made a thread ready.
 */

/**
 * @brief k_sem_reset() sets the count to 0.
 *
 * @details
 * - Setup: count 3, limit 5. No thread waits.
 * - Action: z_impl_k_sem_reset().
 * - Expected: count 0, limit 5.
 *
 * @ingroup kernel_unit_sem_reset
 * @see z_impl_k_sem_reset()
 */
ZTEST(sem_unit, test_reset_sets_count_to_zero)
{
	struct k_sem sem;

	sem_prepare(&sem, 3U, 5U);

	z_impl_k_sem_reset(&sem);

	zassert_equal(sem.count, 0U);
	zassert_equal(sem.limit, 5U);
}

/**
 * @brief k_sem_reset() wakes all waiting threads, and the k_sem_take() of each one returns -EAGAIN.
 *
 * @details
 * - Setup: count 0, limit 1. Three threads wait: z_sched_wake() returns
 *   true three times, then false.
 * - Action: z_impl_k_sem_reset().
 * - Expected: four calls of z_sched_wake(), each one with the wait queue of
 *   the semaphore, the return value -EAGAIN and no swap data. The count is
 *   0.
 *
 * @ingroup kernel_unit_sem_reset
 * @see z_impl_k_sem_reset()
 */
ZTEST(sem_unit, test_reset_wakes_all_waiting_threads)
{
	struct k_sem sem;
	bool woken[] = {true, true, true, false};

	sem_prepare(&sem, 0U, 1U);
	SET_RETURN_SEQ(z_sched_wake, woken, ARRAY_SIZE(woken));

	z_impl_k_sem_reset(&sem);

	zassert_equal(z_sched_wake_fake.call_count, ARRAY_SIZE(woken));
	for (size_t i = 0; i < ARRAY_SIZE(woken); i++) {
		zassert_equal_ptr(z_sched_wake_fake.arg0_history[i], &sem.wait_q, "call %zu", i);
		zassert_equal(z_sched_wake_fake.arg1_history[i], -EAGAIN, "call %zu", i);
		zassert_is_null(z_sched_wake_fake.arg2_history[i], "call %zu", i);
	}
	zassert_equal(sem.count, 0U);
}

/**
 * @defgroup kernel_unit_sem_count Count query
 * @ingroup kernel_unit_sem
 * @brief k_sem_count_get() returns the count without a lock.
 *
 * z_impl_k_sem_count_get() is static inline in @c zephyr/kernel.h. It reads
 * one word, so it needs no lock. The value can be old when the caller uses
 * it.
 */

/**
 * @brief k_sem_count_get() returns the count and does not lock sem_lock.
 *
 * @details
 * - Setup: count 4, limit 5.
 * - Action: z_impl_k_sem_count_get().
 * - Expected: return value 4. No calls to the layers below.
 *
 * @ingroup kernel_unit_sem_count
 * @see z_impl_k_sem_count_get()
 */
ZTEST(sem_unit, test_count_get_returns_count_without_lock)
{
	struct k_sem sem;

	sem_prepare(&sem, 4U, 5U);

	zassert_equal(z_impl_k_sem_count_get(&sem), 4U);

	zassert_equal(kernel_unit_history_len(), 0);
}

/**
 * @defgroup kernel_unit_sem_poll Poll events
 * @ingroup kernel_unit_sem
 * @brief With CONFIG_POLL, k_sem_give() and k_sem_reset() signal K_POLL_STATE_SEM_AVAILABLE to the
 * poll events.
 *
 * The static function sem_handle_poll_events() calls
 * z_handle_obj_poll_events() with the list @c poll_events and the state
 * K_POLL_STATE_SEM_AVAILABLE. It returns true if a polling thread became
 * ready. Then the caller reschedules. Without CONFIG_POLL, the function
 * returns false.
 *
 * k_sem_give() signals the poll events only if it did not wake a waiting
 * thread. k_sem_reset() always signals them, also after it set the count
 * to 0.
 */

#ifdef CONFIG_POLL
/**
 * @brief With CONFIG_POLL, k_sem_give() signals the poll events after it increments the count.
 *
 * @details
 * - Setup: count 0, limit 3. No thread waits.
 * - Action: z_impl_k_sem_give().
 * - Expected: one call of z_handle_obj_poll_events() with the poll events
 *   of the semaphore and K_POLL_STATE_SEM_AVAILABLE. At this call, the
 *   count is 1. Thus a polling thread that wakes finds the semaphore
 *   available.
 *
 * @ingroup kernel_unit_sem_poll
 * @see z_impl_k_sem_give()
 * @see sem_handle_poll_events()
 */
ZTEST(sem_unit, test_poll_give_signals_after_increment)
{
	struct k_sem sem;

	sem_prepare(&sem, 0U, 3U);
	spied_sem = &sem;
	count_at_poll = COUNT_UNSET;
	z_handle_obj_poll_events_fake.custom_fake = poll_spy;

	z_impl_k_sem_give(&sem);

	zassert_equal(z_handle_obj_poll_events_fake.call_count, 1);
	zassert_equal_ptr(z_handle_obj_poll_events_fake.arg0_val, &sem.poll_events);
	zassert_equal(z_handle_obj_poll_events_fake.arg1_val, K_POLL_STATE_SEM_AVAILABLE);
	zassert_equal(count_at_poll, 1U);
}

/**
 * @brief With CONFIG_POLL, k_sem_reset() signals the poll events after it sets the count to 0.
 *
 * @details
 * - Setup: count 2, limit 3. No thread waits.
 * - Action: z_impl_k_sem_reset().
 * - Expected: one call of z_handle_obj_poll_events() with the poll events
 *   of the semaphore and K_POLL_STATE_SEM_AVAILABLE. At this call, the
 *   count is 0. Thus a polling thread wakes, but the semaphore is not
 *   available.
 *
 * @ingroup kernel_unit_sem_poll
 * @see z_impl_k_sem_reset()
 * @see sem_handle_poll_events()
 */
ZTEST(sem_unit, test_poll_reset_signals_after_clear)
{
	struct k_sem sem;

	sem_prepare(&sem, 2U, 3U);
	spied_sem = &sem;
	count_at_poll = COUNT_UNSET;
	z_handle_obj_poll_events_fake.custom_fake = poll_spy;

	z_impl_k_sem_reset(&sem);

	zassert_equal(z_handle_obj_poll_events_fake.call_count, 1);
	zassert_equal_ptr(z_handle_obj_poll_events_fake.arg0_val, &sem.poll_events);
	zassert_equal(z_handle_obj_poll_events_fake.arg1_val, K_POLL_STATE_SEM_AVAILABLE);
	zassert_equal(count_at_poll, 0U);
}
#endif /* CONFIG_POLL */

/**
 * @brief With CONFIG_POLL, k_sem_give() signals the poll events also if the count is at the limit.
 *
 * @details
 * - Setup: count 3, limit 3. No thread waits.
 * - Action: z_impl_k_sem_give().
 * - Expected: count 3. One call of z_handle_obj_poll_events(), although
 *   the count did not change.
 *
 * @ingroup kernel_unit_sem_poll
 * @see z_impl_k_sem_give()
 */
ZTEST(sem_unit, test_poll_give_signals_at_limit)
{
	struct k_sem sem;

	if (!IS_ENABLED(CONFIG_POLL)) {
		ztest_test_skip();
	}

	sem_prepare(&sem, 3U, 3U);

	z_impl_k_sem_give(&sem);

	zassert_equal(sem.count, 3U);
	zassert_equal(z_handle_obj_poll_events_fake.call_count, 1);
}

/**
 * @brief If k_sem_give() wakes a waiting thread, it does not signal the poll events.
 *
 * @details
 * The woken thread gets the semaphore, so the semaphore does not become
 * available for a polling thread.
 * - Setup: count 0, limit 3. z_sched_wake() wakes a thread.
 * - Action: z_impl_k_sem_give().
 * - Expected: no call of z_handle_obj_poll_events().
 *
 * @ingroup kernel_unit_sem_poll
 * @see z_impl_k_sem_give()
 */
ZTEST(sem_unit, test_poll_give_no_signal_after_wake)
{
	struct k_sem sem;

	sem_prepare(&sem, 0U, 3U);
	z_sched_wake_fake.return_val = true;

	z_impl_k_sem_give(&sem);

	zassert_equal(z_handle_obj_poll_events_fake.call_count, 0);
}

/**
 * @brief With CONFIG_POLL, k_sem_reset() signals the poll events also if it woke waiting threads.
 *
 * @details
 * This is different from k_sem_give(), see
 * test_poll_give_no_signal_after_wake().
 * - Setup: count 0, limit 1. One thread waits: z_sched_wake() returns
 *   true, then false.
 * - Action: z_impl_k_sem_reset().
 * - Expected: one call of z_handle_obj_poll_events(), after the last call
 *   of z_sched_wake().
 *
 * @ingroup kernel_unit_sem_poll
 * @see z_impl_k_sem_reset()
 */
ZTEST(sem_unit, test_poll_reset_signals_after_wake)
{
	struct k_sem sem;
	bool woken[] = {true, false};

	if (!IS_ENABLED(CONFIG_POLL)) {
		ztest_test_skip();
	}

	sem_prepare(&sem, 0U, 1U);
	SET_RETURN_SEQ(z_sched_wake, woken, ARRAY_SIZE(woken));

	z_impl_k_sem_reset(&sem);

	zassert_equal(z_handle_obj_poll_events_fake.call_count, 1);
	zassert_true(kernel_unit_history_index(KERNEL_UNIT_FN(z_sched_wake), 1) <
		     kernel_unit_history_index(KERNEL_UNIT_FN(z_handle_obj_poll_events), 0));
}

#ifndef CONFIG_POLL
/**
 * @brief Without CONFIG_POLL, k_sem_give() and k_sem_reset() do not call the poll subsystem.
 *
 * @details
 * - Setup: count 0, limit 3. No thread waits.
 * - Action: z_impl_k_sem_give(), then z_impl_k_sem_reset().
 * - Expected: no call of z_handle_obj_poll_events(). The static function
 *   sem_handle_poll_events() returns false.
 *
 * @ingroup kernel_unit_sem_poll
 * @see z_impl_k_sem_give()
 * @see z_impl_k_sem_reset()
 * @see sem_handle_poll_events()
 */
ZTEST(sem_unit, test_poll_not_called_without_config)
{
	struct k_sem sem;

	sem_prepare(&sem, 0U, 3U);

	z_impl_k_sem_give(&sem);
	z_impl_k_sem_reset(&sem);

	zassert_equal(z_handle_obj_poll_events_fake.call_count, 0);
	zassert_false(sem_handle_poll_events(&sem));
}
#endif /* !CONFIG_POLL */

/**
 * @defgroup kernel_unit_sem_locking Locking
 * @ingroup kernel_unit_sem
 * @brief One spinlock, sem_lock, protects all semaphores. Each path releases it exactly once.
 *
 * Each path of k_sem_give(), k_sem_take() and k_sem_reset() locks
 * @c sem_lock once, as its first call to the layers below. The only call
 * before it is arch_is_in_isr() in the assertion of k_sem_take(). Each path
 * releases the lock once, as its last call, with the key of the lock. The
 * release is k_spin_unlock() (seen as arch_irq_unlock()), z_reschedule() or
 * z_pend_curr(). The count changes only while the lock is held.
 */

/**
 * @brief If k_sem_give() makes no thread ready, it releases sem_lock with k_spin_unlock().
 *
 * @details
 * - Setup: count 0, limit 3. No thread waits. No polling thread becomes
 *   ready.
 * - Action: z_impl_k_sem_give().
 * - Expected calls: arch_irq_lock(), z_sched_wake(),
 *   z_handle_obj_poll_events() (with CONFIG_POLL), arch_irq_unlock() with
 *   the key. No reschedule.
 *
 * @ingroup kernel_unit_sem_locking
 * @see z_impl_k_sem_give()
 */
ZTEST(sem_unit, test_lock_give_no_ready_thread_unlocks)
{
	struct k_sem sem;

	sem_prepare(&sem, 0U, 3U);

	z_impl_k_sem_give(&sem);

	zassert_call_history(unit_arch_irq_lock, z_sched_wake,
			     KERNEL_UNIT_IF_ENABLED(CONFIG_POLL, z_handle_obj_poll_events),
			     unit_arch_irq_unlock);
	assert_lock_released_once(KERNEL_UNIT_RELEASED_BY_UNLOCK);
}

/**
 * @brief If k_sem_give() wakes a thread, it releases sem_lock with z_reschedule().
 *
 * @details
 * - Setup: count 0, limit 3. z_sched_wake() wakes a thread.
 * - Action: z_impl_k_sem_give().
 * - Expected calls: arch_irq_lock(), z_sched_wake(), z_reschedule() with
 *   @c sem_lock and the key.
 *
 * @ingroup kernel_unit_sem_locking
 * @see z_impl_k_sem_give()
 */
ZTEST(sem_unit, test_lock_give_wake_reschedules)
{
	struct k_sem sem;

	sem_prepare(&sem, 0U, 3U);
	z_sched_wake_fake.return_val = true;

	z_impl_k_sem_give(&sem);

	zassert_call_history(unit_arch_irq_lock, z_sched_wake, z_reschedule);
	assert_lock_released_once(KERNEL_UNIT_RELEASED_BY_RESCHEDULE);
}

/**
 * @brief With CONFIG_POLL, if k_sem_give() makes a polling thread ready, it releases sem_lock with
 * z_reschedule().
 *
 * @details
 * - Setup: count 0, limit 3. No thread waits.
 *   z_handle_obj_poll_events() returns true.
 * - Action: z_impl_k_sem_give().
 * - Expected calls: arch_irq_lock(), z_sched_wake(),
 *   z_handle_obj_poll_events(), z_reschedule() with @c sem_lock and the
 *   key. The count is 1.
 *
 * @ingroup kernel_unit_sem_locking
 * @see z_impl_k_sem_give()
 */
ZTEST(sem_unit, test_lock_give_poll_ready_reschedules)
{
	struct k_sem sem;

	if (!IS_ENABLED(CONFIG_POLL)) {
		ztest_test_skip();
	}

	sem_prepare(&sem, 0U, 3U);
	z_handle_obj_poll_events_fake.return_val = true;

	z_impl_k_sem_give(&sem);

	zassert_call_history(unit_arch_irq_lock, z_sched_wake, z_handle_obj_poll_events,
			     z_reschedule);
	assert_lock_released_once(KERNEL_UNIT_RELEASED_BY_RESCHEDULE);
	zassert_equal(sem.count, 1U);
}

/**
 * @brief If the count is not 0, k_sem_take() releases sem_lock with k_spin_unlock().
 *
 * @details
 * - Setup: count 1, limit 1.
 * - Action: z_impl_k_sem_take() with K_FOREVER.
 * - Expected calls: arch_is_in_isr() (with CONFIG_ASSERT), arch_irq_lock(),
 *   arch_irq_unlock() with the key.
 *
 * @ingroup kernel_unit_sem_locking
 * @see z_impl_k_sem_take()
 */
ZTEST(sem_unit, test_lock_take_available_unlocks)
{
	struct k_sem sem;

	sem_prepare(&sem, 1U, 1U);

	zassert_equal(z_impl_k_sem_take(&sem, K_FOREVER), 0);

	zassert_call_history(KERNEL_UNIT_IF_ENABLED(CONFIG_ASSERT, arch_is_in_isr),
			     unit_arch_irq_lock, unit_arch_irq_unlock);
	assert_lock_released_once(KERNEL_UNIT_RELEASED_BY_UNLOCK);
}

/**
 * @brief If k_sem_take() returns -EBUSY, it releases sem_lock with k_spin_unlock().
 *
 * @details
 * - Setup: count 0, limit 1.
 * - Action: z_impl_k_sem_take() with K_NO_WAIT.
 * - Expected calls: arch_is_in_isr() (with CONFIG_ASSERT), arch_irq_lock(),
 *   arch_irq_unlock() with the key.
 *
 * @ingroup kernel_unit_sem_locking
 * @see z_impl_k_sem_take()
 */
ZTEST(sem_unit, test_lock_take_busy_unlocks)
{
	struct k_sem sem;

	sem_prepare(&sem, 0U, 1U);

	zassert_equal(z_impl_k_sem_take(&sem, K_NO_WAIT), -EBUSY);

	zassert_call_history(KERNEL_UNIT_IF_ENABLED(CONFIG_ASSERT, arch_is_in_isr),
			     unit_arch_irq_lock, unit_arch_irq_unlock);
	assert_lock_released_once(KERNEL_UNIT_RELEASED_BY_UNLOCK);
}

/**
 * @brief If k_sem_take() waits, z_pend_curr() releases sem_lock, and k_sem_take() does not release
 * it again.
 *
 * @details
 * - Setup: count 0, limit 1.
 * - Action: z_impl_k_sem_take() with K_FOREVER.
 * - Expected calls: arch_is_in_isr() (with CONFIG_ASSERT), arch_irq_lock(),
 *   z_pend_curr() with @c sem_lock and the key. No arch_irq_unlock() after
 *   the wait.
 *
 * @ingroup kernel_unit_sem_locking
 * @see z_impl_k_sem_take()
 */
ZTEST(sem_unit, test_lock_take_wait_hands_lock_to_pend)
{
	struct k_sem sem;

	sem_prepare(&sem, 0U, 1U);

	(void)z_impl_k_sem_take(&sem, K_FOREVER);

	zassert_call_history(KERNEL_UNIT_IF_ENABLED(CONFIG_ASSERT, arch_is_in_isr),
			     unit_arch_irq_lock, z_pend_curr);
	assert_lock_released_once(KERNEL_UNIT_RELEASED_BY_PEND);
}

/**
 * @brief If k_sem_reset() makes no thread ready, it releases sem_lock with k_spin_unlock().
 *
 * @details
 * - Setup: count 2, limit 3. No thread waits. No polling thread becomes
 *   ready.
 * - Action: z_impl_k_sem_reset().
 * - Expected calls: arch_irq_lock(), z_sched_wake(),
 *   z_handle_obj_poll_events() (with CONFIG_POLL), arch_irq_unlock() with
 *   the key.
 *
 * @ingroup kernel_unit_sem_locking
 * @see z_impl_k_sem_reset()
 */
ZTEST(sem_unit, test_lock_reset_no_ready_thread_unlocks)
{
	struct k_sem sem;

	sem_prepare(&sem, 2U, 3U);

	z_impl_k_sem_reset(&sem);

	zassert_call_history(unit_arch_irq_lock, z_sched_wake,
			     KERNEL_UNIT_IF_ENABLED(CONFIG_POLL, z_handle_obj_poll_events),
			     unit_arch_irq_unlock);
	assert_lock_released_once(KERNEL_UNIT_RELEASED_BY_UNLOCK);
}

/**
 * @brief If k_sem_reset() wakes threads, it releases sem_lock once with z_reschedule() after the
 * last wake.
 *
 * @details
 * - Setup: count 0, limit 1. Two threads wait: z_sched_wake() returns
 *   true two times, then false.
 * - Action: z_impl_k_sem_reset().
 * - Expected calls: arch_irq_lock(), z_sched_wake() three times,
 *   z_handle_obj_poll_events() (with CONFIG_POLL), z_reschedule() with
 *   @c sem_lock and the key. All wakes occur under one lock, so no thread
 *   runs before all threads are woken.
 *
 * @ingroup kernel_unit_sem_locking
 * @see z_impl_k_sem_reset()
 */
ZTEST(sem_unit, test_lock_reset_wake_reschedules)
{
	struct k_sem sem;
	bool woken[] = {true, true, false};

	sem_prepare(&sem, 0U, 1U);
	SET_RETURN_SEQ(z_sched_wake, woken, ARRAY_SIZE(woken));

	z_impl_k_sem_reset(&sem);

	zassert_call_history(unit_arch_irq_lock, z_sched_wake, z_sched_wake, z_sched_wake,
			     KERNEL_UNIT_IF_ENABLED(CONFIG_POLL, z_handle_obj_poll_events),
			     z_reschedule);
	assert_lock_released_once(KERNEL_UNIT_RELEASED_BY_RESCHEDULE);
}

/**
 * @brief With CONFIG_POLL, if k_sem_reset() makes a polling thread ready, it releases sem_lock with
 * z_reschedule().
 *
 * @details
 * - Setup: count 2, limit 3. No thread waits.
 *   z_handle_obj_poll_events() returns true.
 * - Action: z_impl_k_sem_reset().
 * - Expected calls: arch_irq_lock(), z_sched_wake(),
 *   z_handle_obj_poll_events(), z_reschedule() with @c sem_lock and the
 *   key.
 *
 * @ingroup kernel_unit_sem_locking
 * @see z_impl_k_sem_reset()
 */
ZTEST(sem_unit, test_lock_reset_poll_ready_reschedules)
{
	struct k_sem sem;

	if (!IS_ENABLED(CONFIG_POLL)) {
		ztest_test_skip();
	}

	sem_prepare(&sem, 2U, 3U);
	z_handle_obj_poll_events_fake.return_val = true;

	z_impl_k_sem_reset(&sem);

	zassert_call_history(unit_arch_irq_lock, z_sched_wake, z_handle_obj_poll_events,
			     z_reschedule);
	assert_lock_released_once(KERNEL_UNIT_RELEASED_BY_RESCHEDULE);
}

/**
 * @brief k_sem_give(), k_sem_take() and k_sem_reset() change the count only while they hold
 * sem_lock.
 *
 * @details
 * Spy fakes record the count at the lock and at the release of the lock.
 * - k_sem_give(), count 1, limit 3: count 1 at the lock, 2 at the release.
 * - k_sem_take(), count 2, K_NO_WAIT: count 2 at the lock, 1 at the
 *   release.
 * - k_sem_reset(), count 1: count 1 at the lock, 0 at the release.
 * - Expected: the count after the operation is the count at the release.
 *
 * @ingroup kernel_unit_sem_locking
 * @see z_impl_k_sem_give()
 * @see z_impl_k_sem_take()
 * @see z_impl_k_sem_reset()
 */
ZTEST(sem_unit, test_lock_protects_count)
{
	struct k_sem sem;

	sem_prepare(&sem, 1U, 3U);
	spy_on_lock(&sem);

	z_impl_k_sem_give(&sem);
	zassert_equal(count_at_lock, 1U);
	zassert_equal(count_at_release, 2U);
	zassert_equal(sem.count, count_at_release);

	zassert_equal(z_impl_k_sem_take(&sem, K_NO_WAIT), 0);
	zassert_equal(count_at_lock, 2U);
	zassert_equal(count_at_release, 1U);
	zassert_equal(sem.count, count_at_release);

	z_impl_k_sem_reset(&sem);
	zassert_equal(count_at_lock, 1U);
	zassert_equal(count_at_release, 0U);
	zassert_equal(sem.count, count_at_release);
}

/**
 * @brief All semaphores use the same lock, sem_lock.
 *
 * @details
 * - Setup: two semaphores, both with count 0 and limit 1. z_sched_wake()
 *   wakes a thread.
 * - Action: z_impl_k_sem_give() on the first semaphore, then
 *   z_impl_k_sem_take() with K_FOREVER on the second semaphore.
 * - Expected: z_reschedule() and z_pend_curr() get the address of
 *   @c sem_lock both times, and the wait queue of the correct semaphore.
 *
 * @ingroup kernel_unit_sem_locking
 * @see z_impl_k_sem_give()
 * @see z_impl_k_sem_take()
 */
ZTEST(sem_unit, test_lock_shared_by_all_semaphores)
{
	struct k_sem sem_a;
	struct k_sem sem_b;

	sem_prepare(&sem_a, 0U, 1U);
	sem_prepare(&sem_b, 0U, 1U);
	z_sched_wake_fake.return_val = true;

	z_impl_k_sem_give(&sem_a);
	(void)z_impl_k_sem_take(&sem_b, K_FOREVER);

	zassert_equal_ptr(z_sched_wake_fake.arg0_val, &sem_a.wait_q);
	zassert_equal_ptr(z_reschedule_fake.arg0_val, &sem_lock);
	zassert_equal_ptr(z_pend_curr_fake.arg0_val, &sem_lock);
	zassert_equal_ptr(z_pend_curr_fake.arg2_val, &sem_b.wait_q);
}

/**
 * @brief k_sem_init() does not lock sem_lock.
 *
 * @details
 * Until k_sem_init() returns, only the caller uses the semaphore. Thus the
 * caller must not initialize a semaphore that other threads use.
 * - Action: z_impl_k_sem_init() with count 0 and limit 1.
 * - Expected: no call of arch_irq_lock() and arch_irq_unlock().
 *
 * @ingroup kernel_unit_sem_locking
 * @see z_impl_k_sem_init()
 */
ZTEST(sem_unit, test_lock_not_used_by_init)
{
	struct k_sem sem;

	zassert_equal(z_impl_k_sem_init(&sem, 0U, 1U), 0);

	zassert_equal(unit_arch_irq_lock_fake.call_count, 0);
	zassert_equal(unit_arch_irq_unlock_fake.call_count, 0);
}

#ifdef CONFIG_SPIN_VALIDATE
/**
 * @brief With CONFIG_SPIN_VALIDATE, the spinlock validation sees sem_lock on lock and on unlock.
 *
 * @details
 * The validation is part of k_spin_lock() and k_spin_unlock()
 * (@c zephyr/spinlock.h). It shows that the lock and the release use the
 * same spinlock.
 * - Setup: count 0, limit 3. No thread waits.
 * - Action: z_impl_k_sem_give().
 * - Expected: z_spin_lock_valid(), z_spin_lock_set_owner() and
 *   z_spin_unlock_valid() each get the address of @c sem_lock once.
 *
 * @ingroup kernel_unit_sem_locking
 * @see z_impl_k_sem_give()
 */
ZTEST(sem_unit, test_lock_validation_sees_sem_lock)
{
	struct k_sem sem;

	sem_prepare(&sem, 0U, 3U);

	z_impl_k_sem_give(&sem);

	zassert_equal(z_spin_lock_valid_fake.call_count, 1);
	zassert_equal_ptr(z_spin_lock_valid_fake.arg0_val, &sem_lock);
	zassert_equal(z_spin_lock_set_owner_fake.call_count, 1);
	zassert_equal_ptr(z_spin_lock_set_owner_fake.arg0_val, &sem_lock);
	zassert_equal(z_spin_unlock_valid_fake.call_count, 1);
	zassert_equal_ptr(z_spin_unlock_valid_fake.arg0_val, &sem_lock);
}
#endif /* CONFIG_SPIN_VALIDATE */

#ifdef CONFIG_USERSPACE
/**
 * @defgroup kernel_unit_sem_syscall System call verification
 * @ingroup kernel_unit_sem
 * @brief With CONFIG_USERSPACE, each verification function checks the semaphore object before it
 * calls the implementation.
 *
 * A system call from a user thread goes to z_vrfy_k_sem_*(). This function
 * checks with K_SYSCALL_OBJ() that the pointer is a semaphore object of the
 * kernel that the thread has access to. z_vrfy_k_sem_init() uses
 * K_SYSCALL_OBJ_INIT(): the object can be initialized or not. The other
 * functions use K_SYSCALL_OBJ(): the object must be initialized. If the
 * check fails, K_OOPS() stops the thread. Otherwise the function calls
 * z_impl_k_sem_*() with the same arguments and returns its result.
 *
 * In the test, K_OOPS() calls the fake unit_syscall_oops(), and this fake
 * returns. The real K_OOPS() does not return. Thus the tests check that the
 * oops occurs before the implementation changes the semaphore, not that
 * the implementation does not run.
 */

static unsigned int count_at_oops;

static void oops_spy(void)
{
	count_at_oops = spied_sem->count;
}

/* Assert one object check of sem with the type K_OBJ_SEM and init state, and no oops. */
static void assert_object_check(struct k_sem *sem, enum _obj_init_check init)
{
	kernel_unit_assert_object_check(sem, K_OBJ_SEM, init);
}

/* Make the object check fail and record the count at the oops. */
static void fail_object_check(struct k_sem *sem)
{
	kernel_unit_fail_object_check();
	spied_sem = sem;
	count_at_oops = COUNT_UNSET;
	unit_syscall_oops_fake.custom_fake = oops_spy;
}

/**
 * @brief z_vrfy_k_sem_init() checks that the pointer is a semaphore object, initialized or not, and
 * then calls z_impl_k_sem_init().
 *
 * @details
 * - Setup: the object check passes.
 * - Action: z_vrfy_k_sem_init() with count 1 and limit 2.
 * - Expected: k_object_find() and k_object_validation_check() with the
 *   semaphore, K_OBJ_SEM and _OBJ_INIT_ANY, before z_waitq_init(). No oops.
 *   Return value 0, count 1, limit 2.
 *
 * @ingroup kernel_unit_sem_syscall
 * @see z_vrfy_k_sem_init()
 */
ZTEST(sem_unit, test_syscall_init_checks_any_object)
{
	struct k_sem sem;

	k_object_find_fake.return_val = &kernel_unit_kobject;

	zassert_equal(z_vrfy_k_sem_init(&sem, 1U, 2U), 0);

	assert_object_check(&sem, _OBJ_INIT_ANY);
	zassert_called_before(k_object_validation_check, z_waitq_init);
	zassert_equal(sem.count, 1U);
	zassert_equal(sem.limit, 2U);
}

/**
 * @brief If the object check fails, z_vrfy_k_sem_init() raises an oops before it changes the
 * semaphore.
 *
 * @details
 * - Setup: a semaphore filled with a pattern. The object check fails.
 * - Action: z_vrfy_k_sem_init() with count 1 and limit 2.
 * - Expected: one oops. At the oops, the count has the pattern. The oops
 *   comes before z_waitq_init().
 *
 * @ingroup kernel_unit_sem_syscall
 * @see z_vrfy_k_sem_init()
 */
ZTEST(sem_unit, test_syscall_init_oops_on_bad_object)
{
	struct k_sem sem;

	memset(&sem, SEM_FILL, sizeof(sem));
	fail_object_check(&sem);

	(void)z_vrfy_k_sem_init(&sem, 1U, 2U);

	zassert_equal(unit_syscall_oops_fake.call_count, 1);
	zassert_equal(count_at_oops, SEM_FILL_UINT);
	zassert_called_before(unit_syscall_oops, z_waitq_init);
}

/**
 * @brief z_vrfy_k_sem_give() checks that the pointer is an initialized semaphore object, and then
 * calls z_impl_k_sem_give().
 *
 * @details
 * - Setup: count 0, limit 1. The object check passes.
 * - Action: z_vrfy_k_sem_give().
 * - Expected: k_object_find() and k_object_validation_check() with the
 *   semaphore, K_OBJ_SEM and _OBJ_INIT_TRUE, before the lock. No oops.
 *   Count 1.
 *
 * @ingroup kernel_unit_sem_syscall
 * @see z_vrfy_k_sem_give()
 */
ZTEST(sem_unit, test_syscall_give_checks_initialized_object)
{
	struct k_sem sem;

	sem_prepare(&sem, 0U, 1U);
	k_object_find_fake.return_val = &kernel_unit_kobject;

	z_vrfy_k_sem_give(&sem);

	assert_object_check(&sem, _OBJ_INIT_TRUE);
	zassert_called_before(k_object_validation_check, unit_arch_irq_lock);
	zassert_equal(sem.count, 1U);
}

/**
 * @brief If the object check fails, z_vrfy_k_sem_give() raises an oops before it locks the
 * semaphore.
 *
 * @details
 * - Setup: count 0, limit 1. The object check fails.
 * - Action: z_vrfy_k_sem_give().
 * - Expected: one oops. At the oops, the count is 0. The oops comes before
 *   the lock of @c sem_lock.
 *
 * @ingroup kernel_unit_sem_syscall
 * @see z_vrfy_k_sem_give()
 */
ZTEST(sem_unit, test_syscall_give_oops_on_bad_object)
{
	struct k_sem sem;

	sem_prepare(&sem, 0U, 1U);
	fail_object_check(&sem);

	z_vrfy_k_sem_give(&sem);

	zassert_equal(unit_syscall_oops_fake.call_count, 1);
	zassert_equal(count_at_oops, 0U);
	zassert_called_before(unit_syscall_oops, unit_arch_irq_lock);
}

/**
 * @brief z_vrfy_k_sem_take() checks that the pointer is an initialized semaphore object, and then
 * calls z_impl_k_sem_take() with the same timeout.
 *
 * @details
 * - Setup: count 0, limit 1. The object check passes. z_pend_curr()
 *   returns -EAGAIN.
 * - Action: z_vrfy_k_sem_take() with a timeout of 10 ticks.
 * - Expected: k_object_find() and k_object_validation_check() with the
 *   semaphore, K_OBJ_SEM and _OBJ_INIT_TRUE, before the lock. No oops.
 *   z_pend_curr() gets the timeout. Return value -EAGAIN.
 *
 * @ingroup kernel_unit_sem_syscall
 * @see z_vrfy_k_sem_take()
 */
ZTEST(sem_unit, test_syscall_take_checks_initialized_object)
{
	struct k_sem sem;

	sem_prepare(&sem, 0U, 1U);
	k_object_find_fake.return_val = &kernel_unit_kobject;
	z_pend_curr_fake.return_val = -EAGAIN;

	zassert_equal(z_vrfy_k_sem_take(&sem, TEST_TIMEOUT), -EAGAIN);

	assert_object_check(&sem, _OBJ_INIT_TRUE);
	zassert_called_before(k_object_validation_check, unit_arch_irq_lock);
	zassert_true(K_TIMEOUT_EQ(z_pend_curr_fake.arg3_val, TEST_TIMEOUT));
}

/**
 * @brief If the object check fails, z_vrfy_k_sem_take() raises an oops before it locks the
 * semaphore.
 *
 * @details
 * - Setup: count 1, limit 1. The object check fails.
 * - Action: z_vrfy_k_sem_take() with K_NO_WAIT.
 * - Expected: one oops. At the oops, the count is 1. The oops comes before
 *   the lock of @c sem_lock.
 *
 * @ingroup kernel_unit_sem_syscall
 * @see z_vrfy_k_sem_take()
 */
ZTEST(sem_unit, test_syscall_take_oops_on_bad_object)
{
	struct k_sem sem;

	sem_prepare(&sem, 1U, 1U);
	fail_object_check(&sem);

	(void)z_vrfy_k_sem_take(&sem, K_NO_WAIT);

	zassert_equal(unit_syscall_oops_fake.call_count, 1);
	zassert_equal(count_at_oops, 1U);
	zassert_called_before(unit_syscall_oops, unit_arch_irq_lock);
}

/**
 * @brief z_vrfy_k_sem_reset() checks that the pointer is an initialized semaphore object, and then
 * calls z_impl_k_sem_reset().
 *
 * @details
 * - Setup: count 2, limit 3. The object check passes.
 * - Action: z_vrfy_k_sem_reset().
 * - Expected: k_object_find() and k_object_validation_check() with the
 *   semaphore, K_OBJ_SEM and _OBJ_INIT_TRUE, before the lock. No oops.
 *   Count 0.
 *
 * @ingroup kernel_unit_sem_syscall
 * @see z_vrfy_k_sem_reset()
 */
ZTEST(sem_unit, test_syscall_reset_checks_initialized_object)
{
	struct k_sem sem;

	sem_prepare(&sem, 2U, 3U);
	k_object_find_fake.return_val = &kernel_unit_kobject;

	z_vrfy_k_sem_reset(&sem);

	assert_object_check(&sem, _OBJ_INIT_TRUE);
	zassert_called_before(k_object_validation_check, unit_arch_irq_lock);
	zassert_equal(sem.count, 0U);
}

/**
 * @brief If the object check fails, z_vrfy_k_sem_reset() raises an oops before it locks the
 * semaphore.
 *
 * @details
 * - Setup: count 2, limit 3. The object check fails.
 * - Action: z_vrfy_k_sem_reset().
 * - Expected: one oops. At the oops, the count is 2. The oops comes before
 *   the lock of @c sem_lock.
 *
 * @ingroup kernel_unit_sem_syscall
 * @see z_vrfy_k_sem_reset()
 */
ZTEST(sem_unit, test_syscall_reset_oops_on_bad_object)
{
	struct k_sem sem;

	sem_prepare(&sem, 2U, 3U);
	fail_object_check(&sem);

	z_vrfy_k_sem_reset(&sem);

	zassert_equal(unit_syscall_oops_fake.call_count, 1);
	zassert_equal(count_at_oops, 2U);
	zassert_called_before(unit_syscall_oops, unit_arch_irq_lock);
}

/**
 * @brief z_vrfy_k_sem_count_get() checks that the pointer is an initialized semaphore object, and
 * then returns the count.
 *
 * @details
 * - Setup: count 4, limit 5. The object check passes.
 * - Action: z_vrfy_k_sem_count_get().
 * - Expected: k_object_find() and k_object_validation_check() with the
 *   semaphore, K_OBJ_SEM and _OBJ_INIT_TRUE. No oops. Return value 4.
 *
 * @ingroup kernel_unit_sem_syscall
 * @see z_vrfy_k_sem_count_get()
 */
ZTEST(sem_unit, test_syscall_count_get_checks_initialized_object)
{
	struct k_sem sem;

	sem_prepare(&sem, 4U, 5U);
	k_object_find_fake.return_val = &kernel_unit_kobject;

	zassert_equal(z_vrfy_k_sem_count_get(&sem), 4U);

	assert_object_check(&sem, _OBJ_INIT_TRUE);
}

/**
 * @brief If the object check fails, z_vrfy_k_sem_count_get() raises an oops.
 *
 * @details
 * - Setup: count 4, limit 5. The object check fails.
 * - Action: z_vrfy_k_sem_count_get().
 * - Expected: one oops.
 *
 * @ingroup kernel_unit_sem_syscall
 * @see z_vrfy_k_sem_count_get()
 */
ZTEST(sem_unit, test_syscall_count_get_oops_on_bad_object)
{
	struct k_sem sem;

	sem_prepare(&sem, 4U, 5U);
	fail_object_check(&sem);

	(void)z_vrfy_k_sem_count_get(&sem);

	zassert_equal(unit_syscall_oops_fake.call_count, 1);
}
#endif /* CONFIG_USERSPACE */

#ifdef CONFIG_OBJ_CORE_SEM
/**
 * @defgroup kernel_unit_sem_obj_core Object core
 * @ingroup kernel_unit_sem
 * @brief With CONFIG_OBJ_CORE_SEM, sem.c registers the semaphore object type and links each
 * semaphore to it.
 *
 * K_OBJ_TYPE_DEFINE() puts a descriptor of the type @c obj_type_sem into the
 * iterable section @c k_obj_core_desc. At boot, the object core code
 * initializes the type from the descriptor and links the semaphores that
 * K_SEM_DEFINE() defines (the section @c k_sem). k_sem_init() links each
 * semaphore that it initializes.
 */

K_SEM_DEFINE(unit_static_sem, 1, 2);

/* Return the descriptor of obj_type_sem, and count the descriptors of this type. */
static const struct k_obj_core_desc *sem_obj_core_desc(int *count)
{
	const struct k_obj_core_desc *found = NULL;

	*count = 0;
	STRUCT_SECTION_FOREACH(k_obj_core_desc, desc) {
		if (desc->type == &obj_type_sem) {
			found = desc;
			(*count)++;
		}
	}

	return found;
}

/**
 * @brief With CONFIG_OBJ_CORE_SEM, k_sem_init() links the object core of the semaphore to the
 * semaphore object type.
 *
 * @details
 * - Action: z_impl_k_sem_init() with count 0 and limit 1.
 * - Expected: one call of k_obj_core_init_and_link() with the object core
 *   of the semaphore and @c obj_type_sem.
 *
 * @ingroup kernel_unit_sem_obj_core
 * @see z_impl_k_sem_init()
 */
ZTEST(sem_unit, test_obj_core_init_links_semaphore)
{
	struct k_sem sem;

	zassert_equal(z_impl_k_sem_init(&sem, 0U, 1U), 0);

	zassert_equal(k_obj_core_init_and_link_fake.call_count, 1);
	zassert_equal_ptr(k_obj_core_init_and_link_fake.arg0_val, K_OBJ_CORE(&sem));
	zassert_equal_ptr(k_obj_core_init_and_link_fake.arg1_val, &obj_type_sem);
}

/**
 * @brief With CONFIG_OBJ_CORE_SEM, sem.c defines one object type descriptor with the ID
 * K_OBJ_TYPE_SEM_ID.
 *
 * @details
 * - Action: search the section @c k_obj_core_desc for the descriptor of
 *   @c obj_type_sem.
 * - Expected: one descriptor. Its type ID is K_OBJ_TYPE_SEM_ID. Its object
 *   size is the size of @c struct @c k_sem, and its object core offset is
 *   the offset of @c obj_core. Its object range is the section @c k_sem.
 *
 * @ingroup kernel_unit_sem_obj_core
 */
ZTEST(sem_unit, test_obj_core_type_descriptor)
{
	int count;
	const struct k_obj_core_desc *desc = sem_obj_core_desc(&count);

	zassert_equal(count, 1);
	zassert_not_null(desc);
	zassert_equal(desc->type_id, K_OBJ_TYPE_SEM_ID);
	zassert_equal(desc->obj_size, sizeof(struct k_sem));
	zassert_equal(desc->obj_core_offset, offsetof(struct k_sem, obj_core));
	zassert_equal_ptr(desc->objs_start, STRUCT_SECTION_START(k_sem));
	zassert_equal_ptr(desc->objs_end, STRUCT_SECTION_END(k_sem));
}

/**
 * @brief The object range of the descriptor contains the semaphores that K_SEM_DEFINE() defines.
 *
 * @details
 * K_SEM_DEFINE() does not call k_sem_init(). Thus the object core code
 * finds these semaphores only through the descriptor.
 * - Setup: K_SEM_DEFINE() of one semaphore in the test.
 * - Action: compare the address of the semaphore with the object range of
 *   the descriptor.
 * - Expected: the semaphore is in the range, at a multiple of the object
 *   size from the start.
 *
 * @ingroup kernel_unit_sem_obj_core
 */
ZTEST(sem_unit, test_obj_core_descriptor_covers_static_semaphores)
{
	int count;
	const struct k_obj_core_desc *desc = sem_obj_core_desc(&count);
	uintptr_t start;
	uintptr_t end;
	uintptr_t obj = (uintptr_t)&unit_static_sem;

	zassert_not_null(desc);
	start = (uintptr_t)desc->objs_start;
	end = (uintptr_t)desc->objs_end;

	zassert_true((obj >= start) && (obj < end));
	zassert_equal((obj - start) % desc->obj_size, 0U);
}
#endif /* CONFIG_OBJ_CORE_SEM */
