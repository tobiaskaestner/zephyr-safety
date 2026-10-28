/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @defgroup kernel_unit_stack kernel/stack.c
 * @ingroup kernel_unit_tests
 * @brief Design specification of kernel/stack.c, written as unit tests.
 *
 * @par The stack object
 * A stack (@c struct @c k_stack) keeps word-size values (@c stack_data_t)
 * in last-in, first-out order. It has these parts:
 * - @c base, @c next, @c top: three pointers into one array of
 *   @c stack_data_t, the buffer. @c base is the first entry, @c top is the
 *   address after the last entry, and @c next is the free entry above the
 *   last pushed value. The stack is empty if @c next is @c base, and full if
 *   @c next is @c top. The capacity is <tt>top - base</tt>.
 * - @c lock: the spinlock of the stack. Each stack has its own lock.
 * - @c wait_q: the wait queue of the threads that wait in k_stack_pop().
 * - @c flags: the flag @c K_STACK_FLAG_ALLOC marks a buffer that
 *   k_stack_alloc_init() allocated.
 * - @c obj_core: with @kconfig{CONFIG_OBJ_CORE_STACK}, the object core.
 *
 * The stack copies the values. A value is a word, for example a pointer.
 *
 * @par Operations
 * - k_stack_init() makes an empty stack on a buffer of the caller.
 * - k_stack_alloc_init() allocates the buffer from the resource pool of the
 *   thread with z_thread_malloc() and sets @c K_STACK_FLAG_ALLOC. It fails
 *   with -ENOMEM if the size of the buffer does not fit into @c size_t, or
 *   if the allocation fails.
 * - k_stack_cleanup() frees an allocated buffer with k_free(). It fails with
 *   -EAGAIN if a thread waits. z_stack_cleanup() is the same function with
 *   the argument @c locked. The object code of @c CONFIG_USERSPACE calls it
 *   when a stack object loses its last reference, sometimes while it holds
 *   the scheduler lock (@c locked true).
 * - k_stack_push() puts a value on the stack. It fails with -ENOMEM if the
 *   stack is full.
 * - k_stack_pop() takes the last pushed value. If the stack is empty, it
 *   returns -EBUSY (timeout K_NO_WAIT) or waits.
 *
 * @par Hand-over to a waiting thread
 * A thread waits in k_stack_pop() only if the stack is empty. Thus, while a
 * thread waits, the stack is empty. k_stack_push() first checks that the
 * stack is not full. Then it tries z_sched_wake() with the value. If a thread
 * waits, the scheduler gives the value to this thread (as @c swap_data, with
 * the return value 0), and the value does not go into the buffer.
 * k_stack_pop() of the woken thread then returns @c _current->base.swap_data.
 * If the wait times out, z_pend_curr() returns -EAGAIN, and k_stack_pop()
 * returns -EAGAIN.
 *
 * @par Locks
 * Each operation, except k_stack_init() and k_stack_alloc_init(), locks the
 * spinlock of its stack before it reads the pointers or uses the wait
 * queue. k_spin_lock() locks the interrupts with arch_irq_lock() and returns
 * a key. Each path releases the lock exactly once, with the same key, as its
 * last call to the layers below:
 * - k_spin_unlock(), if no thread became ready.
 * - z_reschedule(), if k_stack_push() gave the value to a waiting thread.
 * - z_pend_curr(), if k_stack_pop() must wait. z_pend_curr() adds the
 *   current thread to the wait queue, releases the lock and switches threads
 *   in one step. After the wait, k_stack_pop() does not lock again.
 *
 * k_stack_cleanup() frees the buffer while the lock is held.
 *
 * @par Interfaces below stack.c
 * - Scheduler (@c ksched.h): z_sched_wake(), z_reschedule(), z_pend_curr(),
 *   and @c _current (the data of @c kernel/init.c).
 * - Wait queue (@c wait_q.h): z_waitq_init(), z_waitq_head(),
 *   z_waitq_head_locked().
 * - Memory (@c kernel/mempool.c): z_thread_malloc(), k_free().
 * - Object core: k_obj_core_init_and_link(), K_OBJ_TYPE_DEFINE().
 * - Kernel objects: k_object_init().
 * - System call checks: K_SYSCALL_OBJ(), K_SYSCALL_OBJ_NEVER_INIT(),
 *   K_SYSCALL_VERIFY(), K_SYSCALL_MEMORY_WRITE(), K_OOPS().
 * - Architecture: arch_irq_lock() and arch_irq_unlock() through
 *   k_spin_lock() and k_spin_unlock().
 * - size_mul_overflow() (@c zephyr/sys/math_extras.h): static inline, not a
 *   fake.
 *
 * @par Kconfig options that change stack.c
 * - @kconfig{CONFIG_USERSPACE}: the verification functions
 *   z_vrfy_k_stack_*() and the kernel object of the stack.
 * - @kconfig{CONFIG_OBJ_CORE_STACK}: the object type descriptor of the
 *   stacks and the object core link in k_stack_init().
 * - The CHECKIF() options for the full check of k_stack_push() and for the
 *   wait queue check of k_stack_cleanup():
 *   @kconfig{CONFIG_RUNTIME_ERROR_CHECKS} (default) returns the error,
 *   @kconfig{CONFIG_NO_RUNTIME_CHECKS} does no check,
 *   @kconfig{CONFIG_ASSERT_ON_ERRORS} asserts.
 * - @kconfig{CONFIG_ASSERT}: stack.c has no assertion of its own. The option
 *   enables @kconfig{CONFIG_SPIN_VALIDATE} in @c zephyr/spinlock.h.
 *
 * @par Test method
 * The tests call the functions of stack.c directly (z_impl_k_stack_*() for
 * the system calls) and z_vrfy_k_stack_*(). All calls below stack.c go to
 * FFF fakes. The fake unit_arch_irq_lock() returns KERNEL_UNIT_IRQ_KEY. Thus
 * a test can follow the key to the call that releases the lock. The FFF call
 * history gives the order of the calls. The tests use these models of the
 * layers below:
 * - Waiting threads: the fake z_sched_wake() returns true for the first
 *   @em n calls.
 * - Wait result: the fake z_pend_curr() sets @c _current->base.swap_data and
 *   returns a result, as the scheduler does after a wake or a timeout.
 * - Heap: the fake z_thread_malloc() gives a buffer of the test and asserts
 *   the size.
 *
 * Each buffer of a test has one guard entry after its last entry. Thus a
 * test can show a write after @c top without a memory fault. The scenarios
 * in @c testcase.yaml build the tests once for each Kconfig option above. A
 * test that applies only to some configurations is in an @c \#ifdef block,
 * or it calls ztest_test_skip().
 *
 * @par Structure of the tests
 * Each public function of stack.c has one group below this group. A system
 * call has one group for z_impl_k_stack_*() and z_vrfy_k_stack_*(). The
 * data of stack.c has the last group. Each test is in the group of the
 * function under test. The rules below (locking, system call verification,
 * object core) apply to more than one function. Their tests are in the
 * group of the function that they call.
 *
 * @par Locking
 * The spinlock of the stack protects the pointers and the wait queue. Each
 * path releases it exactly once.
 * Each path of k_stack_push(), k_stack_pop() and k_stack_cleanup() locks
 * the spinlock of its stack once, as its first call to the layers below.
 * Each path releases the lock once, as its last call, with the key of the
 * lock. The release is k_spin_unlock() (seen as arch_irq_unlock()),
 * z_reschedule() or z_pend_curr(). The pointers and the buffer change only
 * while the lock is held. k_free() runs while the lock is held.
 * k_stack_init() and k_stack_alloc_init() do not lock the stack.
 *
 * @par System call verification
 * With CONFIG_USERSPACE, each verification function checks its arguments
 * before it calls the implementation.
 * A system call from a user thread goes to z_vrfy_k_stack_*(). This function
 * checks that the pointer is a stack object of the kernel that the thread
 * has access to:
 * - z_vrfy_k_stack_alloc_init() uses K_SYSCALL_OBJ_NEVER_INIT(): the object
 *   must not be initialized yet. It also checks that the number of entries
 *   is not 0 and that the size of the buffer fits into @c size_t.
 * - z_vrfy_k_stack_push() and z_vrfy_k_stack_pop() use K_SYSCALL_OBJ(): the
 *   object must be initialized. z_vrfy_k_stack_pop() also checks with
 *   K_SYSCALL_MEMORY_WRITE() that the thread can write @c data.
 *
 * If a check fails, K_OOPS() stops the thread. Otherwise the function calls
 * z_impl_k_stack_*() with the same arguments and returns its result.
 * k_stack_init() and k_stack_cleanup() are not system calls.
 *
 * In the test, K_OOPS() calls the fake unit_syscall_oops(), and this fake
 * returns. The real K_OOPS() does not return. Thus the tests check that the
 * oops occurs before the implementation allocates, locks or changes the
 * stack.
 *
 * @par Object core
 * With CONFIG_OBJ_CORE_STACK, stack.c defines the object type of the stacks
 * and links each stack that k_stack_init() initializes.
 * stack.c defines the object type @c obj_type_stack. K_OBJ_TYPE_DEFINE()
 * puts one descriptor of this type into the iterable section
 * @c k_obj_core_desc. At boot, the object core code initializes the type from
 * the descriptor and links the stacks that K_STACK_DEFINE() defines (the
 * section @c k_stack). k_stack_init() links each stack that it initializes
 * with k_obj_core_init_and_link(). k_stack_alloc_init() calls k_stack_init(),
 * so it also links the stack. k_stack_cleanup() does not unlink the stack.
 */

/**
 * @defgroup kernel_unit_stack_k_stack_init k_stack_init()
 * @ingroup kernel_unit_stack
 * @brief k_stack_init() makes an empty stack on the buffer of the caller.
 *
 * k_stack_init() sets the three pointers, the lock and the wait queue. It
 * initializes the kernel object and, with CONFIG_OBJ_CORE_STACK, links the
 * object core. It does not lock the stack: until k_stack_init() returns, only
 * the caller uses the stack. It does not write to the buffer and does not
 * change the flags. K_STACK_DEFINE() in @c zephyr/kernel.h defines a stack
 * with the same initial state and the flags 0. The test of K_STACK_DEFINE()
 * is in this group, because stack.c has no function for it.
 *
 * @par Functions in kernel/stack.c
 * - k_stack_init(). It is not a system call.
 */

/**
 * @defgroup kernel_unit_stack_k_stack_alloc_init k_stack_alloc_init()
 * @ingroup kernel_unit_stack
 * @brief k_stack_alloc_init() allocates the buffer from the resource pool of the thread.
 *
 * k_stack_alloc_init() computes the size of the buffer with
 * size_mul_overflow(). If the size fits into @c size_t, it calls
 * z_thread_malloc(). On success, it initializes the stack with
 * k_stack_init() on the new buffer and sets the flags to
 * @c K_STACK_FLAG_ALLOC. On a failure, it returns -ENOMEM and does not
 * change the stack. It does not lock the stack.
 *
 * @par Functions in kernel/stack.c
 * - z_impl_k_stack_alloc_init()
 * - z_vrfy_k_stack_alloc_init(), static inline, with
 *   @kconfig{CONFIG_USERSPACE}
 */

/**
 * @defgroup kernel_unit_stack_z_stack_cleanup z_stack_cleanup()
 * @ingroup kernel_unit_stack
 * @brief z_stack_cleanup() is k_stack_cleanup() with the argument @c locked.
 *
 * The object code of @c CONFIG_USERSPACE calls z_stack_cleanup() when a
 * stack object loses its last reference, sometimes while it holds the
 * scheduler lock (@c locked true). k_stack_cleanup() calls it with
 * @c locked false. The design text of the cleanup is in the group of
 * k_stack_cleanup(). The tests in this group call z_stack_cleanup() with
 * @c locked true. Some tests of k_stack_cleanup() also call it.
 *
 * @par Functions in kernel/stack.c
 * - z_stack_cleanup(). It is a kernel-internal function, not a system call.
 */

/**
 * @defgroup kernel_unit_stack_k_stack_cleanup k_stack_cleanup()
 * @ingroup kernel_unit_stack
 * @brief k_stack_cleanup() frees an allocated buffer if no thread waits.
 *
 * k_stack_cleanup() and z_stack_cleanup() lock the stack. If a thread waits
 * on the stack, they return -EAGAIN (a CHECKIF()). The argument @c locked of
 * z_stack_cleanup() tells if the caller holds the scheduler lock. With
 * @c locked true, the function reads the wait queue with
 * z_waitq_head_locked(), else with z_waitq_head(), which takes the
 * scheduler lock. If the flag @c K_STACK_FLAG_ALLOC is set, the function
 * frees the buffer with k_free(), sets @c base to NULL and clears the flag.
 * It does not change @c next and @c top. A buffer of the caller (flag not
 * set) stays.
 *
 * @par Functions in kernel/stack.c
 * - k_stack_cleanup(). It calls z_stack_cleanup() with @c locked false. It
 *   is not a system call.
 */

/**
 * @defgroup kernel_unit_stack_k_stack_push k_stack_push()
 * @ingroup kernel_unit_stack
 * @brief k_stack_push() puts a value on the stack, or gives it to a waiting thread.
 *
 * k_stack_push() locks the stack and checks that the stack is not full (a
 * CHECKIF()). If the stack is full, it returns -ENOMEM. Then it tries
 * z_sched_wake() with the value (see "Hand-over to a waiting thread"
 * below). If no
 * thread waits, it writes the value to the entry at @c next and increments
 * @c next. The full check comes before the hand-over.
 *
 * @par Hand-over to a waiting thread
 * If a thread waits, k_stack_push() gives the value to this thread and not
 * to the buffer.
 * k_stack_push() calls z_sched_wake() with the wait queue of the stack, the
 * return value 0 and the value as the swap data. If z_sched_wake() woke a
 * thread, the value does not go into the buffer. The woken thread returns
 * from z_pend_curr() in k_stack_pop() with the result 0 and reads the value
 * from @c _current->base.swap_data.
 *
 * In the tests, the fake z_sched_wake() models the waiting threads, and the
 * fake z_pend_curr() models the result of the wait. One test connects the two
 * fakes: a push in z_pend_curr() gives the value to the waiting thread. This
 * test is in the group of k_stack_pop(), because its action is the pop.
 *
 * @par Functions in kernel/stack.c
 * - z_impl_k_stack_push()
 * - z_vrfy_k_stack_push(), static inline, with @kconfig{CONFIG_USERSPACE}
 */

/**
 * @defgroup kernel_unit_stack_k_stack_pop k_stack_pop()
 * @ingroup kernel_unit_stack
 * @brief k_stack_pop() takes the last pushed value, or waits for a value.
 *
 * k_stack_pop() locks the stack. If the stack is not empty, it decrements
 * @c next, writes the entry at @c next to @c *data, and returns 0. It does
 * not wait in this case, also not with a timeout. If the stack is empty, it
 * returns -EBUSY for K_NO_WAIT. Else it waits with z_pend_curr(). After the
 * wait, -EAGAIN from z_pend_curr() is a timeout: k_stack_pop() returns
 * -EAGAIN and does not write @c *data. Each other result is a wake by
 * k_stack_push(): k_stack_pop() writes @c _current->base.swap_data to
 * @c *data and returns 0.
 *
 * The API says that an ISR must use K_NO_WAIT. stack.c has no check of this
 * rule. In an ISR, a wait reaches z_pend_curr(), and the scheduler refuses
 * it with a panic in every build.
 *
 * @par Functions in kernel/stack.c
 * - z_impl_k_stack_pop()
 * - z_vrfy_k_stack_pop(), static inline, with @kconfig{CONFIG_USERSPACE}
 */

/**
 * @defgroup kernel_unit_stack_static Static functions and data
 * @ingroup kernel_unit_stack
 * @brief The static functions of stack.c, and the data that stack.c defines.
 *
 * @par Functions in kernel/stack.c
 * stack.c has no static functions.
 *
 * @par Data in kernel/stack.c
 * - @c obj_type_stack and its descriptor (K_OBJ_TYPE_DEFINE()), with
 *   @kconfig{CONFIG_OBJ_CORE_STACK}. The tests of the descriptor are in this
 *   group.
 */

#include <stdint.h>
#include <string.h>
#include <zephyr/ztest.h>
#include <kernel_unit.h>
#include <kernel_unit_models.h>
#include <fakes/mempool.h>
#ifdef CONFIG_OBJ_CORE
#include <fakes/obj_core.h>
#endif
#ifdef CONFIG_USERSPACE
#include <fakes/kobject.h>
#endif
#ifdef CONFIG_ASSERT
#include <fakes/assert.h>
#endif

#include <kernel/stack.c>

/* Value that fills a stack object before a test, to show what the unit writes. */
#define FILL KERNEL_UNIT_FILL

/* Value that fills each buffer entry before a test */
#define FILL_DATA ((stack_data_t)0xA5A5A5A5U)

/* Value number i that a test pushes */
#define VALUE(i) ((stack_data_t)0x5A5A0000U + (stack_data_t)(i))

/* Timeout that is not K_NO_WAIT and not K_FOREVER */
#define TEST_TIMEOUT K_TICKS(10)

/*
 * Entry of an expected call history that exists only if CHECKIF() runs its
 * check: with CONFIG_NO_RUNTIME_CHECKS, CHECKIF() does not read the wait
 * queue.
 */
#ifdef CONFIG_NO_RUNTIME_CHECKS
#define IF_CHECKED(fn) NULL
#else
#define IF_CHECKED(fn) fn
#endif

/* Number of entries of the stacks of the tests */
#define N_ENTRIES 4

/*
 * Buffers of the tests. Each buffer has N_ENTRIES entries and one guard
 * entry after them (index N_ENTRIES).
 */
static stack_data_t buffer[N_ENTRIES + 1];
static stack_data_t buffer2[N_ENTRIES + 1];

/* The heap of the test: z_thread_malloc() gives this buffer once. */
static stack_data_t heap_buffer[N_ENTRIES + 1];
static size_t heap_expected_size;
static bool heap_used;

/* The current thread of the test, for k_stack_pop() after a wait. */
static struct k_thread current_thread;

/* A thread that waits, for the wait queue fakes z_waitq_head() and z_waitq_head_locked(). */
static struct k_thread waiting_thread;

static void *malloc_from_heap(size_t size)
{
	zassert_equal(size, heap_expected_size, "z_thread_malloc() size %zu", size);

	if (heap_used) {
		return NULL;
	}
	heap_used = true;

	return heap_buffer;
}

/* Let z_thread_malloc() give heap_buffer for a stack of n entries. */
static void set_heap(uint32_t n)
{
	heap_expected_size = n * sizeof(stack_data_t);
	z_thread_malloc_fake.custom_fake = malloc_from_heap;
}

/* Let a thread wait on the stack, as z_waitq_head() and z_waitq_head_locked() see it. */
static void set_wait_queue_not_empty(void)
{
	z_waitq_head_fake.return_val = &waiting_thread;
	z_waitq_head_locked_fake.return_val = &waiting_thread;
}

/* Fill a buffer with FILL_DATA, also the guard entry. */
static void buffer_fill(stack_data_t *buf)
{
	for (size_t i = 0; i <= N_ENTRIES; i++) {
		buf[i] = FILL_DATA;
	}
}

/* Put a stack into a known, empty state on buf with n entries, without k_stack_init(). */
static void stack_prepare(struct k_stack *stack, stack_data_t *buf, uint32_t n)
{
	memset(stack, 0, sizeof(*stack));
	stack->base = buf;
	stack->next = buf;
	stack->top = buf + n;
}

/* Put values 0 to n - 1 on the stack, without the functions of the unit. */
static void stack_preload(struct k_stack *stack, size_t n)
{
	for (size_t i = 0; i < n; i++) {
		*stack->next = VALUE(i);
		stack->next++;
	}
}

/* Return the number of values on the stack. */
static size_t stack_len(struct k_stack *stack)
{
	return (size_t)(stack->next - stack->base);
}

/*
 * The stack and the data pointer that the spy fakes read. A spy fake records
 * the state at the time of its call. Thus a test sees the order of the
 * changes and the calls to the layers below.
 */
static struct k_stack *spied_stack;
static stack_data_t *spied_data;
static size_t len_at_lock;
static size_t len_at_release;
static stack_data_t data_at_release;

#define LEN_UNSET ((size_t)-1)

/* Observers of the lock spies (kernel_unit_spy_on_lock()). */
static void observe_lock(void)
{
	len_at_lock = stack_len(spied_stack);
}

static void observe_release(void)
{
	len_at_release = stack_len(spied_stack);
	if (spied_data != NULL) {
		data_at_release = *spied_data;
	}
}

/* Install the spy fakes of the lock and of the release. */
static void spy_on_lock(struct k_stack *stack, stack_data_t *data)
{
	spied_stack = stack;
	spied_data = data;
	len_at_lock = LEN_UNSET;
	len_at_release = LEN_UNSET;
	data_at_release = FILL_DATA;
	kernel_unit_spy_on_lock(observe_lock, observe_release);
	/* The stack tests observe only the release with k_spin_unlock(). */
	z_reschedule_fake.custom_fake = NULL;
}

/* Assert the lock invariant of one operation on the stack (kernel_unit_models.h). */
static void assert_lock_released_once(struct k_stack *stack, enum kernel_unit_release how)
{
	kernel_unit_assert_lock_released_once(&stack->lock, how);
}

static void stack_unit_before(void *fixture)
{
	ARG_UNUSED(fixture);

	/* The fake rules reset all fakes and _kernel before this function. */
	unit_arch_irq_lock_fake.return_val = KERNEL_UNIT_IRQ_KEY;

	buffer_fill(buffer);
	buffer_fill(buffer2);
	buffer_fill(heap_buffer);
	heap_expected_size = 0;
	heap_used = false;
	kernel_unit_waiting_threads = 0;
	spied_stack = NULL;
	spied_data = NULL;
	memset(&current_thread, 0, sizeof(current_thread));
	_kernel.cpus[0].current = &current_thread;
}

ZTEST_SUITE(stack_unit, NULL, NULL, stack_unit_before, NULL, NULL);

/*
 * Tests: Initialization. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_stack, at the top of this file.
 */

/**
 * @brief k_stack_init() makes the stack empty, with the capacity num_entries.
 *
 * @details
 * - Setup: a stack object filled with a pattern.
 * - Action: k_stack_init() with a buffer of 4 entries.
 * - Expected: base and next are the buffer. top is the buffer plus 4
 *   entries.
 *
 * @ingroup kernel_unit_stack_k_stack_init
 * @see k_stack_init()
 */
ZTEST(stack_unit, test_init_sets_pointers)
{
	struct k_stack stack;

	memset(&stack, FILL, sizeof(stack));

	k_stack_init(&stack, buffer, N_ENTRIES);

	zassert_equal_ptr(stack.base, buffer);
	zassert_equal_ptr(stack.next, buffer);
	zassert_equal_ptr(stack.top, &buffer[N_ENTRIES]);
}

/**
 * @brief k_stack_init() sets the lock of the stack to its initial value.
 *
 * @details
 * - Setup: a stack object filled with a pattern.
 * - Action: k_stack_init().
 * - Expected: all bytes of the lock are 0 (the value of an unlocked
 *   spinlock).
 *
 * @ingroup kernel_unit_stack_k_stack_init
 * @see k_stack_init()
 */
ZTEST(stack_unit, test_init_resets_lock)
{
	struct k_stack stack;
	const struct k_spinlock unlocked = {};

	memset(&stack, FILL, sizeof(stack));

	k_stack_init(&stack, buffer, N_ENTRIES);

	zassert_mem_equal(&stack.lock, &unlocked, sizeof(unlocked));
}

/**
 * @brief k_stack_init() initializes the wait queue of the stack.
 *
 * @details
 * - Action: k_stack_init().
 * - Expected: one call of z_waitq_init() with the wait queue of the stack.
 *
 * @ingroup kernel_unit_stack_k_stack_init
 * @see k_stack_init()
 */
ZTEST(stack_unit, test_init_initializes_wait_queue)
{
	struct k_stack stack;

	k_stack_init(&stack, buffer, N_ENTRIES);

	zassert_equal(z_waitq_init_fake.call_count, 1);
	zassert_equal_ptr(z_waitq_init_fake.arg0_val, &stack.wait_q);
}

#ifdef CONFIG_USERSPACE
/**
 * @brief With CONFIG_USERSPACE, k_stack_init() marks the stack as an initialized kernel object.
 *
 * @details
 * - Action: k_stack_init().
 * - Expected: one call of k_object_init() with the stack.
 *
 * @ingroup kernel_unit_stack_k_stack_init
 * @see k_stack_init()
 */
ZTEST(stack_unit, test_init_initializes_kernel_object)
{
	struct k_stack stack;

	k_stack_init(&stack, buffer, N_ENTRIES);

	zassert_equal(k_object_init_fake.call_count, 1);
	zassert_equal_ptr(k_object_init_fake.arg0_val, &stack);
}
#endif /* CONFIG_USERSPACE */

/**
 * @brief k_stack_init() initializes the wait queue, then the kernel object, then the object core,
 * and calls nothing else.
 *
 * @details
 * - Action: k_stack_init().
 * - Expected calls: z_waitq_init(), k_object_init() (with CONFIG_USERSPACE),
 *   k_obj_core_init_and_link() (with CONFIG_OBJ_CORE_STACK). No lock.
 *
 * @ingroup kernel_unit_stack_k_stack_init
 * @see k_stack_init()
 */
ZTEST(stack_unit, test_init_call_order)
{
	struct k_stack stack;

	k_stack_init(&stack, buffer, N_ENTRIES);

	zassert_call_history(
		z_waitq_init, KERNEL_UNIT_IF_ENABLED(CONFIG_USERSPACE, k_object_init),
		KERNEL_UNIT_IF_ENABLED(CONFIG_OBJ_CORE_STACK, k_obj_core_init_and_link));
}

/**
 * @brief k_stack_init() does not write to the buffer.
 *
 * @details
 * - Setup: a buffer filled with a pattern.
 * - Action: k_stack_init() with this buffer.
 * - Expected: all entries and the guard entry keep the pattern.
 *
 * @ingroup kernel_unit_stack_k_stack_init
 * @see k_stack_init()
 */
ZTEST(stack_unit, test_init_does_not_write_buffer)
{
	struct k_stack stack;

	k_stack_init(&stack, buffer, N_ENTRIES);

	for (size_t i = 0; i <= N_ENTRIES; i++) {
		zassert_equal(buffer[i], FILL_DATA, "entry %zu changed", i);
	}
}

/**
 * @brief k_stack_init() does not change the flags of the stack.
 *
 * @details
 * The caller must give a stack object with the flags 0, for example a
 * zeroed object. A stack object with @c K_STACK_FLAG_ALLOC set keeps it, and
 * a later k_stack_cleanup() frees the buffer of the caller with k_free().
 * - Setup: a stack object filled with a pattern (flags 0xA5, which includes
 *   K_STACK_FLAG_ALLOC).
 * - Action: k_stack_init().
 * - Expected: the flags are 0xA5.
 *
 * @ingroup kernel_unit_stack_k_stack_init
 * @see k_stack_init()
 */
ZTEST(stack_unit, test_init_does_not_change_flags)
{
	struct k_stack stack;

	memset(&stack, FILL, sizeof(stack));

	k_stack_init(&stack, buffer, N_ENTRIES);

	zassert_equal(stack.flags, FILL);
	zassert_true((stack.flags & K_STACK_FLAG_ALLOC) != 0U);
}

/**
 * @brief k_stack_init() with 0 entries makes a stack that is empty and full.
 *
 * @details
 * - Action: k_stack_init() with 0 entries.
 * - Expected: base, next and top are the buffer.
 *
 * @ingroup kernel_unit_stack_k_stack_init
 * @see k_stack_init()
 */
ZTEST(stack_unit, test_init_zero_entries)
{
	struct k_stack stack;

	k_stack_init(&stack, buffer, 0);

	zassert_equal_ptr(stack.base, buffer);
	zassert_equal_ptr(stack.next, buffer);
	zassert_equal_ptr(stack.top, buffer);
}

K_STACK_DEFINE(unit_static_stack, N_ENTRIES);

/**
 * @brief K_STACK_DEFINE() defines an empty stack with the capacity stack_num_entries and the flags
 * 0.
 *
 * @details
 * The macro is in @c zephyr/kernel.h. It defines the buffer and the stack
 * object in the iterable section @c k_stack.
 * - Setup: K_STACK_DEFINE() of a stack with 4 entries in the test.
 * - Expected: base and next are the same address. top is base plus 4
 *   entries. The flags are 0.
 *
 * @ingroup kernel_unit_stack_k_stack_init
 */
ZTEST(stack_unit, test_init_static_definition)
{
	zassert_equal_ptr(unit_static_stack.next, unit_static_stack.base);
	zassert_equal_ptr(unit_static_stack.top, unit_static_stack.base + N_ENTRIES);
	zassert_equal(unit_static_stack.flags, 0);
}

/*
 * Tests: Allocated buffer. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_stack, at the top of this file.
 */

/**
 * @brief k_stack_alloc_init() allocates num_entries values with z_thread_malloc(), makes an empty
 * stack on this buffer, and returns 0.
 *
 * @details
 * - Setup: a stack object filled with a pattern. z_thread_malloc() gives a
 *   buffer of the test.
 * - Action: z_impl_k_stack_alloc_init() with 4 entries.
 * - Expected: return value 0. One call of z_thread_malloc() with
 *   4 * sizeof(stack_data_t). base and next are the buffer. top is the
 *   buffer plus 4 entries. One call of z_waitq_init() with the wait queue.
 *
 * @ingroup kernel_unit_stack_k_stack_alloc_init
 * @see z_impl_k_stack_alloc_init()
 */
ZTEST(stack_unit, test_alloc_init_allocates_buffer)
{
	struct k_stack stack;

	memset(&stack, FILL, sizeof(stack));
	set_heap(N_ENTRIES);

	zassert_equal(z_impl_k_stack_alloc_init(&stack, N_ENTRIES), 0);

	zassert_equal(z_thread_malloc_fake.call_count, 1);
	zassert_equal_ptr(stack.base, heap_buffer);
	zassert_equal_ptr(stack.next, heap_buffer);
	zassert_equal_ptr(stack.top, &heap_buffer[N_ENTRIES]);
	zassert_equal(z_waitq_init_fake.call_count, 1);
	zassert_equal_ptr(z_waitq_init_fake.arg0_val, &stack.wait_q);
}

/**
 * @brief k_stack_alloc_init() sets the flags to K_STACK_FLAG_ALLOC.
 *
 * @details
 * - Setup: a stack object filled with a pattern (flags 0xA5).
 * - Action: z_impl_k_stack_alloc_init().
 * - Expected: the flags are exactly K_STACK_FLAG_ALLOC. The other bits are
 *   0.
 *
 * @ingroup kernel_unit_stack_k_stack_alloc_init
 * @see z_impl_k_stack_alloc_init()
 */
ZTEST(stack_unit, test_alloc_init_sets_alloc_flag)
{
	struct k_stack stack;

	memset(&stack, FILL, sizeof(stack));
	set_heap(N_ENTRIES);

	zassert_equal(z_impl_k_stack_alloc_init(&stack, N_ENTRIES), 0);

	zassert_equal(stack.flags, K_STACK_FLAG_ALLOC);
}

/**
 * @brief k_stack_alloc_init() initializes the stack after the allocation, and does not lock it.
 *
 * @details
 * - Action: z_impl_k_stack_alloc_init().
 * - Expected calls: z_thread_malloc(), z_waitq_init(), k_object_init() (with
 *   CONFIG_USERSPACE), k_obj_core_init_and_link() (with
 *   CONFIG_OBJ_CORE_STACK).
 *
 * @ingroup kernel_unit_stack_k_stack_alloc_init
 * @see z_impl_k_stack_alloc_init()
 */
ZTEST(stack_unit, test_alloc_init_call_order)
{
	struct k_stack stack;

	set_heap(N_ENTRIES);

	zassert_equal(z_impl_k_stack_alloc_init(&stack, N_ENTRIES), 0);

	zassert_call_history(
		z_thread_malloc, z_waitq_init,
		KERNEL_UNIT_IF_ENABLED(CONFIG_USERSPACE, k_object_init),
		KERNEL_UNIT_IF_ENABLED(CONFIG_OBJ_CORE_STACK, k_obj_core_init_and_link));
}

/**
 * @brief If z_thread_malloc() fails, k_stack_alloc_init() returns -ENOMEM and does not change the
 * stack.
 *
 * @details
 * - Setup: a stack object filled with a pattern. z_thread_malloc() returns
 *   NULL.
 * - Action: z_impl_k_stack_alloc_init() with 4 entries.
 * - Expected: return value -ENOMEM. All bytes of the stack object keep the
 *   pattern. The only call is z_thread_malloc().
 *
 * @ingroup kernel_unit_stack_k_stack_alloc_init
 * @see z_impl_k_stack_alloc_init()
 */
ZTEST(stack_unit, test_alloc_init_no_memory_returns_enomem)
{
	struct k_stack stack;
	struct k_stack expected;

	memset(&stack, FILL, sizeof(stack));
	memset(&expected, FILL, sizeof(expected));

	zassert_equal(z_impl_k_stack_alloc_init(&stack, N_ENTRIES), -ENOMEM);

	zassert_mem_equal(&stack, &expected, sizeof(stack));
	zassert_call_history(z_thread_malloc);
}

/**
 * @brief If the size of the buffer does not fit into size_t, k_stack_alloc_init() returns -ENOMEM
 * and does not allocate.
 *
 * @details
 * This applies only if a @c uint32_t number of entries can overflow
 * @c size_t, for example on a 32-bit build. On a 64-bit build the test
 * skips itself.
 * - Setup: a stack object filled with a pattern.
 * - Action: z_impl_k_stack_alloc_init() with SIZE_MAX / sizeof(stack_data_t)
 *   + 1 entries.
 * - Expected: return value -ENOMEM. No call of z_thread_malloc(). The stack
 *   object keeps the pattern.
 *
 * @ingroup kernel_unit_stack_k_stack_alloc_init
 * @see z_impl_k_stack_alloc_init()
 */
ZTEST(stack_unit, test_alloc_init_size_overflow_returns_enomem)
{
	struct k_stack stack;
	struct k_stack expected;
	uint32_t n = (uint32_t)(SIZE_MAX / sizeof(stack_data_t)) + 1U;

	if ((uint64_t)UINT32_MAX * sizeof(stack_data_t) <= (uint64_t)SIZE_MAX) {
		ztest_test_skip();
	}

	memset(&stack, FILL, sizeof(stack));
	memset(&expected, FILL, sizeof(expected));

	zassert_equal(z_impl_k_stack_alloc_init(&stack, n), -ENOMEM);

	zassert_equal(z_thread_malloc_fake.call_count, 0);
	zassert_mem_equal(&stack, &expected, sizeof(stack));
}

/**
 * @brief k_stack_alloc_init() with the largest number of entries that does not overflow asks
 * z_thread_malloc() for the exact size.
 *
 * @details
 * - Action: z_impl_k_stack_alloc_init() with UINT32_MAX entries on a
 *   64-bit build, or SIZE_MAX / sizeof(stack_data_t) entries on a 32-bit
 *   build. z_thread_malloc() returns NULL.
 * - Expected: return value -ENOMEM. One call of z_thread_malloc() with the
 *   number of entries times sizeof(stack_data_t).
 *
 * @ingroup kernel_unit_stack_k_stack_alloc_init
 * @see z_impl_k_stack_alloc_init()
 */
ZTEST(stack_unit, test_alloc_init_largest_size)
{
	struct k_stack stack;
	uint32_t n = UINT32_MAX;

	if ((uint64_t)UINT32_MAX * sizeof(stack_data_t) > (uint64_t)SIZE_MAX) {
		n = (uint32_t)(SIZE_MAX / sizeof(stack_data_t));
	}

	zassert_equal(z_impl_k_stack_alloc_init(&stack, n), -ENOMEM);

	zassert_equal(z_thread_malloc_fake.call_count, 1);
	zassert_equal(z_thread_malloc_fake.arg0_val, (size_t)n * sizeof(stack_data_t));
}

/*
 * Tests: Cleanup. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_stack, at the top of this file.
 */

/**
 * @brief k_stack_cleanup() of a stack with an allocated buffer frees the buffer, sets base to NULL,
 * clears K_STACK_FLAG_ALLOC, and returns 0.
 *
 * @details
 * - Setup: a stack from k_stack_alloc_init(). No thread waits.
 * - Action: k_stack_cleanup().
 * - Expected: return value 0. One call of k_free() with the buffer. base is
 *   NULL. The flags are 0.
 *
 * @ingroup kernel_unit_stack_k_stack_cleanup
 * @see k_stack_cleanup(), z_stack_cleanup()
 */
ZTEST(stack_unit, test_cleanup_frees_allocated_buffer)
{
	struct k_stack stack;

	set_heap(N_ENTRIES);
	zassert_equal(z_impl_k_stack_alloc_init(&stack, N_ENTRIES), 0);

	zassert_equal(k_stack_cleanup(&stack), 0);

	zassert_equal(k_free_fake.call_count, 1);
	zassert_equal_ptr(k_free_fake.arg0_val, heap_buffer);
	zassert_is_null(stack.base);
	zassert_equal(stack.flags, 0);
}

/**
 * @brief k_stack_cleanup() does not change next and top.
 *
 * @details
 * After the cleanup, next and top point into the freed buffer. The caller
 * must not use the stack after k_stack_cleanup().
 * - Setup: a stack from k_stack_alloc_init() with 2 values.
 * - Action: k_stack_cleanup().
 * - Expected: next is the buffer plus 2 entries. top is the buffer plus 4
 *   entries.
 *
 * @ingroup kernel_unit_stack_k_stack_cleanup
 * @see k_stack_cleanup(), z_stack_cleanup()
 */
ZTEST(stack_unit, test_cleanup_keeps_next_and_top)
{
	struct k_stack stack;

	set_heap(N_ENTRIES);
	zassert_equal(z_impl_k_stack_alloc_init(&stack, N_ENTRIES), 0);
	stack_preload(&stack, 2);

	zassert_equal(k_stack_cleanup(&stack), 0);

	zassert_equal_ptr(stack.next, &heap_buffer[2]);
	zassert_equal_ptr(stack.top, &heap_buffer[N_ENTRIES]);
}

/**
 * @brief k_stack_cleanup() of a stack with a buffer of the caller does not free the buffer and
 * returns 0.
 *
 * @details
 * - Setup: a stack from k_stack_init() with the flags 0.
 * - Action: k_stack_cleanup().
 * - Expected: return value 0. No call of k_free(). base, next and top do
 *   not change.
 *
 * @ingroup kernel_unit_stack_k_stack_cleanup
 * @see k_stack_cleanup(), z_stack_cleanup()
 */
ZTEST(stack_unit, test_cleanup_keeps_caller_buffer)
{
	struct k_stack stack;

	memset(&stack, 0, sizeof(stack));
	k_stack_init(&stack, buffer, N_ENTRIES);

	zassert_equal(k_stack_cleanup(&stack), 0);

	zassert_equal(k_free_fake.call_count, 0);
	zassert_equal_ptr(stack.base, buffer);
	zassert_equal_ptr(stack.next, buffer);
	zassert_equal_ptr(stack.top, &buffer[N_ENTRIES]);
}

/**
 * @brief A second k_stack_cleanup() does not free the buffer again.
 *
 * @details
 * - Setup: a stack from k_stack_alloc_init().
 * - Action: k_stack_cleanup() two times.
 * - Expected: both return 0. One call of k_free().
 *
 * @ingroup kernel_unit_stack_k_stack_cleanup
 * @see k_stack_cleanup(), z_stack_cleanup()
 */
ZTEST(stack_unit, test_cleanup_twice_frees_once)
{
	struct k_stack stack;

	set_heap(N_ENTRIES);
	zassert_equal(z_impl_k_stack_alloc_init(&stack, N_ENTRIES), 0);

	zassert_equal(k_stack_cleanup(&stack), 0);
	zassert_equal(k_stack_cleanup(&stack), 0);

	zassert_equal(k_free_fake.call_count, 1);
}

/**
 * @brief k_stack_cleanup() clears only K_STACK_FLAG_ALLOC and keeps the other flags.
 *
 * @details
 * - Setup: a stack with an allocated buffer and the flags 0xFF.
 * - Action: k_stack_cleanup().
 * - Expected: the flags are 0xFF without K_STACK_FLAG_ALLOC.
 *
 * @ingroup kernel_unit_stack_k_stack_cleanup
 * @see k_stack_cleanup(), z_stack_cleanup()
 */
ZTEST(stack_unit, test_cleanup_clears_only_alloc_flag)
{
	struct k_stack stack;

	stack_prepare(&stack, heap_buffer, N_ENTRIES);
	stack.flags = 0xFFU;

	zassert_equal(k_stack_cleanup(&stack), 0);

	zassert_equal(stack.flags, (uint8_t)(0xFFU & ~K_STACK_FLAG_ALLOC));
}

#ifndef CONFIG_NO_RUNTIME_CHECKS
/**
 * @brief k_stack_cleanup() reads the wait queue with z_waitq_head(), not with
 * z_waitq_head_locked().
 *
 * @details
 * k_stack_cleanup() is z_stack_cleanup() with @c locked false: the caller
 * does not hold the scheduler lock.
 * - Setup: a stack with an allocated buffer. No thread waits.
 * - Action: k_stack_cleanup().
 * - Expected (with CHECKIF() active): one call of z_waitq_head() with the
 *   wait queue of the stack. No call of z_waitq_head_locked().
 *
 * @ingroup kernel_unit_stack_k_stack_cleanup
 * @see k_stack_cleanup(), z_stack_cleanup()
 */
ZTEST(stack_unit, test_cleanup_unlocked_reads_wait_queue)
{
	struct k_stack stack;

	stack_prepare(&stack, heap_buffer, N_ENTRIES);
	stack.flags = K_STACK_FLAG_ALLOC;

	zassert_equal(k_stack_cleanup(&stack), 0);

	zassert_equal(z_waitq_head_fake.call_count, 1);
	zassert_equal_ptr(z_waitq_head_fake.arg0_val, &stack.wait_q);
	zassert_equal(z_waitq_head_locked_fake.call_count, 0);
}
#endif /* !CONFIG_NO_RUNTIME_CHECKS */

/**
 * @brief z_stack_cleanup() with locked true reads the wait queue with z_waitq_head_locked(), not
 * with z_waitq_head().
 *
 * @details
 * The caller holds the scheduler lock. z_waitq_head() takes this lock, so
 * the function must not call it.
 * - Setup: a stack with an allocated buffer. No thread waits.
 * - Action: z_stack_cleanup() with locked true.
 * - Expected: return value 0. One call of k_free(). With CHECKIF() active:
 *   one call of z_waitq_head_locked() with the wait queue of the stack. No
 *   call of z_waitq_head().
 *
 * @ingroup kernel_unit_stack_z_stack_cleanup
 * @see z_stack_cleanup()
 */
ZTEST(stack_unit, test_cleanup_locked_reads_wait_queue_locked)
{
	struct k_stack stack;

	stack_prepare(&stack, heap_buffer, N_ENTRIES);
	stack.flags = K_STACK_FLAG_ALLOC;

	zassert_equal(z_stack_cleanup(&stack, true), 0);

	zassert_equal(k_free_fake.call_count, 1);
	zassert_equal(z_waitq_head_fake.call_count, 0);
	if (!IS_ENABLED(CONFIG_NO_RUNTIME_CHECKS)) {
		zassert_equal(z_waitq_head_locked_fake.call_count, 1);
		zassert_equal_ptr(z_waitq_head_locked_fake.arg0_val, &stack.wait_q);
	}
}

/**
 * @brief If a thread waits, k_stack_cleanup() returns -EAGAIN and does not free the buffer.
 *
 * @details
 * Applies with CONFIG_RUNTIME_ERROR_CHECKS (the default CHECKIF() option).
 * - Setup: a stack with an allocated buffer. z_waitq_head() returns a
 *   thread.
 * - Action: k_stack_cleanup().
 * - Expected: return value -EAGAIN. No call of k_free(). base and the flags
 *   do not change.
 *
 * @ingroup kernel_unit_stack_k_stack_cleanup
 * @see k_stack_cleanup(), z_stack_cleanup()
 */
ZTEST(stack_unit, test_cleanup_unlocked_thread_waits_returns_eagain)
{
	struct k_stack stack;

	if (!IS_ENABLED(CONFIG_RUNTIME_ERROR_CHECKS)) {
		ztest_test_skip();
	}

	stack_prepare(&stack, heap_buffer, N_ENTRIES);
	stack.flags = K_STACK_FLAG_ALLOC;
	set_wait_queue_not_empty();

	zassert_equal(k_stack_cleanup(&stack), -EAGAIN);

	zassert_equal(k_free_fake.call_count, 0);
	zassert_equal_ptr(stack.base, heap_buffer);
	zassert_equal(stack.flags, K_STACK_FLAG_ALLOC);
}

/**
 * @brief If a thread waits, z_stack_cleanup() with locked true returns -EAGAIN and does not free
 * the buffer.
 *
 * @details
 * Applies with CONFIG_RUNTIME_ERROR_CHECKS (the default CHECKIF() option).
 * - Setup: a stack with an allocated buffer. z_waitq_head_locked() returns
 *   a thread.
 * - Action: z_stack_cleanup() with locked true.
 * - Expected: return value -EAGAIN. No call of k_free() and of
 *   z_waitq_head(). base and the flags do not change.
 *
 * @ingroup kernel_unit_stack_z_stack_cleanup
 * @see z_stack_cleanup()
 */
ZTEST(stack_unit, test_cleanup_locked_thread_waits_returns_eagain)
{
	struct k_stack stack;

	if (!IS_ENABLED(CONFIG_RUNTIME_ERROR_CHECKS)) {
		ztest_test_skip();
	}

	stack_prepare(&stack, heap_buffer, N_ENTRIES);
	stack.flags = K_STACK_FLAG_ALLOC;
	set_wait_queue_not_empty();

	zassert_equal(z_stack_cleanup(&stack, true), -EAGAIN);

	zassert_equal(k_free_fake.call_count, 0);
	zassert_equal(z_waitq_head_fake.call_count, 0);
	zassert_equal_ptr(stack.base, heap_buffer);
	zassert_equal(stack.flags, K_STACK_FLAG_ALLOC);
}

/**
 * @brief With CONFIG_NO_RUNTIME_CHECKS, k_stack_cleanup() does not read the wait queue and frees
 * the buffer also if a thread waits.
 *
 * @details
 * CHECKIF() is empty, so the caller must make sure that no thread waits.
 * - Setup: a stack with an allocated buffer. A thread waits.
 * - Action: k_stack_cleanup(), then z_stack_cleanup() with locked true on a
 *   second allocated stack.
 * - Expected: both return 0. Two calls of k_free(). No call of
 *   z_waitq_head() or z_waitq_head_locked().
 *
 * @ingroup kernel_unit_stack_k_stack_cleanup
 * @see k_stack_cleanup(), z_stack_cleanup()
 */
ZTEST(stack_unit, test_cleanup_no_runtime_checks_frees_with_waiter)
{
	struct k_stack stack;
	struct k_stack stack2;

	if (!IS_ENABLED(CONFIG_NO_RUNTIME_CHECKS)) {
		ztest_test_skip();
	}

	stack_prepare(&stack, heap_buffer, N_ENTRIES);
	stack.flags = K_STACK_FLAG_ALLOC;
	stack_prepare(&stack2, buffer2, N_ENTRIES);
	stack2.flags = K_STACK_FLAG_ALLOC;
	set_wait_queue_not_empty();

	zassert_equal(k_stack_cleanup(&stack), 0);
	zassert_equal(z_stack_cleanup(&stack2, true), 0);

	zassert_equal(k_free_fake.call_count, 2);
	zassert_equal(z_waitq_head_fake.call_count, 0);
	zassert_equal(z_waitq_head_locked_fake.call_count, 0);
}

#ifdef CONFIG_ASSERT_ON_ERRORS
/**
 * @brief With CONFIG_ASSERT_ON_ERRORS, k_stack_cleanup() and z_stack_cleanup() assert that no
 * thread waits.
 *
 * @details
 * - Setup: a stack with an allocated buffer. A thread waits.
 * - Action: k_stack_cleanup(), then z_stack_cleanup() with locked true on a
 *   second allocated stack.
 * - Expected: one failed assertion for each call, after the lock and before
 *   k_free(). The fake assertion hook returns, so each call continues,
 *   frees the buffer and returns 0.
 *
 * @ingroup kernel_unit_stack_k_stack_cleanup
 * @see k_stack_cleanup(), z_stack_cleanup()
 */
ZTEST(stack_unit, test_cleanup_assert_on_errors)
{
	struct k_stack stack;
	struct k_stack stack2;

	stack_prepare(&stack, heap_buffer, N_ENTRIES);
	stack.flags = K_STACK_FLAG_ALLOC;
	stack_prepare(&stack2, buffer2, N_ENTRIES);
	stack2.flags = K_STACK_FLAG_ALLOC;
	set_wait_queue_not_empty();

	zassert_equal(k_stack_cleanup(&stack), 0);
	zassert_equal(assert_post_action_fake.call_count, 1);
	zassert_called_before(unit_arch_irq_lock, assert_post_action);
	zassert_called_before(assert_post_action, k_free);

	zassert_equal(z_stack_cleanup(&stack2, true), 0);
	zassert_equal(assert_post_action_fake.call_count, 2);
	zassert_equal(k_free_fake.call_count, 2);
}

/**
 * @brief With CONFIG_ASSERT_ON_ERRORS, k_stack_cleanup() does not assert if no thread waits.
 *
 * @details
 * - Setup: a stack with an allocated buffer. No thread waits.
 * - Action: k_stack_cleanup() and z_stack_cleanup() with locked true.
 * - Expected: no failed assertion.
 *
 * @ingroup kernel_unit_stack_k_stack_cleanup
 * @see k_stack_cleanup(), z_stack_cleanup()
 */
ZTEST(stack_unit, test_cleanup_assert_on_errors_no_waiter)
{
	struct k_stack stack;

	stack_prepare(&stack, heap_buffer, N_ENTRIES);
	stack.flags = K_STACK_FLAG_ALLOC;

	zassert_equal(k_stack_cleanup(&stack), 0);
	zassert_equal(z_stack_cleanup(&stack, true), 0);

	zassert_equal(assert_post_action_fake.call_count, 0);
}
#endif /* CONFIG_ASSERT_ON_ERRORS */

/*
 * Tests: Push. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_stack, at the top of this file.
 */

/**
 * @brief k_stack_push() writes the value to the entry at next, increments next, and returns 0.
 *
 * @details
 * - Setup: an empty stack of 4 entries on a buffer filled with a pattern. No
 *   thread waits.
 * - Action: z_impl_k_stack_push() of value 0.
 * - Expected: return value 0. Entry 0 is value 0. next is the buffer plus 1
 *   entry. The other entries keep the pattern.
 *
 * @ingroup kernel_unit_stack_k_stack_push
 * @see z_impl_k_stack_push()
 */
ZTEST(stack_unit, test_push_stores_value)
{
	struct k_stack stack;

	stack_prepare(&stack, buffer, N_ENTRIES);

	zassert_equal(z_impl_k_stack_push(&stack, VALUE(0)), 0);

	zassert_equal(buffer[0], VALUE(0));
	zassert_equal_ptr(stack.next, &buffer[1]);
	for (size_t i = 1; i <= N_ENTRIES; i++) {
		zassert_equal(buffer[i], FILL_DATA, "entry %zu changed", i);
	}
}

/**
 * @brief k_stack_push() fills the buffer from base up to top, in the order of the calls.
 *
 * @details
 * - Setup: an empty stack of 4 entries. No thread waits.
 * - Action: z_impl_k_stack_push() of values 0 to 3.
 * - Expected: each call returns 0. Entry i is value i. next is top. The
 *   guard entry keeps the pattern.
 *
 * @ingroup kernel_unit_stack_k_stack_push
 * @see z_impl_k_stack_push()
 */
ZTEST(stack_unit, test_push_fills_buffer_in_order)
{
	struct k_stack stack;

	stack_prepare(&stack, buffer, N_ENTRIES);

	for (size_t i = 0; i < N_ENTRIES; i++) {
		zassert_equal(z_impl_k_stack_push(&stack, VALUE(i)), 0);
	}

	for (size_t i = 0; i < N_ENTRIES; i++) {
		zassert_equal(buffer[i], VALUE(i), "entry %zu", i);
	}
	zassert_equal_ptr(stack.next, stack.top);
	zassert_equal(buffer[N_ENTRIES], FILL_DATA);
}

/**
 * @brief k_stack_push() to a full stack returns -ENOMEM and does not change the stack.
 *
 * @details
 * Applies with CONFIG_RUNTIME_ERROR_CHECKS (the default CHECKIF() option).
 * - Setup: a full stack of 4 entries.
 * - Action: z_impl_k_stack_push() of value 9.
 * - Expected: return value -ENOMEM. next is top. The entries and the guard
 *   entry do not change. No call of z_sched_wake().
 *
 * @ingroup kernel_unit_stack_k_stack_push
 * @see z_impl_k_stack_push()
 */
ZTEST(stack_unit, test_push_full_returns_enomem)
{
	struct k_stack stack;

	if (!IS_ENABLED(CONFIG_RUNTIME_ERROR_CHECKS)) {
		ztest_test_skip();
	}

	stack_prepare(&stack, buffer, N_ENTRIES);
	stack_preload(&stack, N_ENTRIES);

	zassert_equal(z_impl_k_stack_push(&stack, VALUE(9)), -ENOMEM);

	zassert_equal_ptr(stack.next, stack.top);
	for (size_t i = 0; i < N_ENTRIES; i++) {
		zassert_equal(buffer[i], VALUE(i), "entry %zu", i);
	}
	zassert_equal(buffer[N_ENTRIES], FILL_DATA);
	zassert_equal(z_sched_wake_fake.call_count, 0);
}

/**
 * @brief k_stack_push() checks for a full stack before the hand-over: a stack with 0 entries
 * returns -ENOMEM also if a thread waits.
 *
 * @details
 * Applies with CONFIG_RUNTIME_ERROR_CHECKS (the default CHECKIF() option).
 * A stack with 0 entries is always full and always empty. A thread that
 * waits in k_stack_pop() on it can only time out.
 * - Setup: a stack with 0 entries. One thread waits.
 * - Action: z_impl_k_stack_push() of value 0.
 * - Expected: return value -ENOMEM. No call of z_sched_wake(). The thread
 *   still waits.
 *
 * @ingroup kernel_unit_stack_k_stack_push
 * @see z_impl_k_stack_push()
 */
ZTEST(stack_unit, test_push_zero_entries_no_handover)
{
	struct k_stack stack;

	if (!IS_ENABLED(CONFIG_RUNTIME_ERROR_CHECKS)) {
		ztest_test_skip();
	}

	stack_prepare(&stack, buffer, 0);
	kernel_unit_set_waiting_threads(1);

	zassert_equal(z_impl_k_stack_push(&stack, VALUE(0)), -ENOMEM);

	zassert_equal(z_sched_wake_fake.call_count, 0);
	zassert_equal(kernel_unit_waiting_threads, 1U);
	zassert_equal(buffer[0], FILL_DATA);
}

/**
 * @brief With CONFIG_NO_RUNTIME_CHECKS, k_stack_push() to a full stack writes the value after top
 * and returns 0.
 *
 * @details
 * CHECKIF() is empty, so the full check does not exist. The caller must not
 * push to a full stack. A push to a full stack writes outside of the buffer.
 * - Setup: a full stack of 4 entries. No thread waits.
 * - Action: z_impl_k_stack_push() of value 9.
 * - Expected: return value 0. The guard entry after the buffer is value 9.
 *   next is top plus 1 entry.
 *
 * @ingroup kernel_unit_stack_k_stack_push
 * @see z_impl_k_stack_push()
 */
ZTEST(stack_unit, test_push_no_runtime_checks_writes_after_top)
{
	struct k_stack stack;

	if (!IS_ENABLED(CONFIG_NO_RUNTIME_CHECKS)) {
		ztest_test_skip();
	}

	stack_prepare(&stack, buffer, N_ENTRIES);
	stack_preload(&stack, N_ENTRIES);

	zassert_equal(z_impl_k_stack_push(&stack, VALUE(9)), 0);

	zassert_equal(buffer[N_ENTRIES], VALUE(9));
	zassert_equal_ptr(stack.next, stack.top + 1);
}

#ifdef CONFIG_ASSERT_ON_ERRORS
/**
 * @brief With CONFIG_ASSERT_ON_ERRORS, k_stack_push() asserts that the stack is not full.
 *
 * @details
 * - Setup: a full stack of 4 entries. No thread waits.
 * - Action: z_impl_k_stack_push() of value 9, then a push to a stack that is
 *   not full.
 * - Expected: one failed assertion for the first call, after the lock and
 *   before z_sched_wake(). The fake assertion hook returns, so the call
 *   continues, writes value 9 to the guard entry and returns 0. No failed
 *   assertion for the second call.
 *
 * @ingroup kernel_unit_stack_k_stack_push
 * @see z_impl_k_stack_push()
 */
ZTEST(stack_unit, test_push_assert_on_errors)
{
	struct k_stack stack;
	struct k_stack stack2;

	stack_prepare(&stack, buffer, N_ENTRIES);
	stack_preload(&stack, N_ENTRIES);

	zassert_equal(z_impl_k_stack_push(&stack, VALUE(9)), 0);
	zassert_equal(assert_post_action_fake.call_count, 1);
	zassert_called_before(unit_arch_irq_lock, assert_post_action);
	zassert_called_before(assert_post_action, z_sched_wake);
	zassert_equal(buffer[N_ENTRIES], VALUE(9));

	stack_prepare(&stack2, buffer2, N_ENTRIES);
	zassert_equal(z_impl_k_stack_push(&stack2, VALUE(0)), 0);
	zassert_equal(assert_post_action_fake.call_count, 1);
}
#endif /* CONFIG_ASSERT_ON_ERRORS */

/**
 * @brief k_stack_push() accepts each value of stack_data_t, also 0 and the largest value.
 *
 * @details
 * - Setup: an empty stack. No thread waits.
 * - Action: z_impl_k_stack_push() of 0, then of UINTPTR_MAX.
 * - Expected: both return 0. Entry 0 is 0, entry 1 is UINTPTR_MAX.
 *
 * @ingroup kernel_unit_stack_k_stack_push
 * @see z_impl_k_stack_push()
 */
ZTEST(stack_unit, test_push_any_value)
{
	struct k_stack stack;

	stack_prepare(&stack, buffer, N_ENTRIES);

	zassert_equal(z_impl_k_stack_push(&stack, 0), 0);
	zassert_equal(z_impl_k_stack_push(&stack, UINTPTR_MAX), 0);

	zassert_equal(buffer[0], 0);
	zassert_equal(buffer[1], UINTPTR_MAX);
}

/*
 * Tests: Hand-over to a waiting thread. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_stack, at the top of this file.
 */

/**
 * @brief If a thread waits, k_stack_push() gives the value to this thread with the return value 0
 * and does not change the buffer.
 *
 * @details
 * - Setup: an empty stack. One thread waits.
 * - Action: z_impl_k_stack_push() of value 0.
 * - Expected: return value 0. One call of z_sched_wake() with the wait queue
 *   of the stack, the return value 0 and value 0. next is base. Entry 0
 *   keeps the pattern.
 *
 * @ingroup kernel_unit_stack_k_stack_push
 * @see z_impl_k_stack_push()
 */
ZTEST(stack_unit, test_handover_push_gives_value_to_thread)
{
	struct k_stack stack;

	stack_prepare(&stack, buffer, N_ENTRIES);
	kernel_unit_set_waiting_threads(1);

	zassert_equal(z_impl_k_stack_push(&stack, VALUE(0)), 0);

	zassert_equal(z_sched_wake_fake.call_count, 1);
	zassert_equal_ptr(z_sched_wake_fake.arg0_val, &stack.wait_q);
	zassert_equal(z_sched_wake_fake.arg1_val, 0);
	zassert_equal((stack_data_t)z_sched_wake_fake.arg2_val, VALUE(0));
	zassert_equal_ptr(stack.next, stack.base);
	zassert_equal(buffer[0], FILL_DATA);
	zassert_equal(kernel_unit_waiting_threads, 0U);
}

/**
 * @brief k_stack_push() wakes at most one thread.
 *
 * @details
 * - Setup: an empty stack. Two threads wait.
 * - Action: z_impl_k_stack_push() of value 0.
 * - Expected: one call of z_sched_wake(). One thread still waits. The stack
 *   is empty.
 *
 * @ingroup kernel_unit_stack_k_stack_push
 * @see z_impl_k_stack_push()
 */
ZTEST(stack_unit, test_handover_wakes_one_thread_only)
{
	struct k_stack stack;

	stack_prepare(&stack, buffer, N_ENTRIES);
	kernel_unit_set_waiting_threads(2);

	zassert_equal(z_impl_k_stack_push(&stack, VALUE(0)), 0);

	zassert_equal(z_sched_wake_fake.call_count, 1);
	zassert_equal(kernel_unit_waiting_threads, 1U);
	zassert_equal(stack_len(&stack), 0U);
}

/**
 * @brief If no thread waits, k_stack_push() tries the hand-over once and then stores the value.
 *
 * @details
 * - Setup: an empty stack. No thread waits.
 * - Action: z_impl_k_stack_push() of value 0.
 * - Expected: one call of z_sched_wake() with the wait queue, 0 and value 0.
 *   Entry 0 is value 0.
 *
 * @ingroup kernel_unit_stack_k_stack_push
 * @see z_impl_k_stack_push()
 */
ZTEST(stack_unit, test_handover_no_thread_stores_value)
{
	struct k_stack stack;

	stack_prepare(&stack, buffer, N_ENTRIES);

	zassert_equal(z_impl_k_stack_push(&stack, VALUE(0)), 0);

	zassert_equal(z_sched_wake_fake.call_count, 1);
	zassert_equal_ptr(z_sched_wake_fake.arg0_val, &stack.wait_q);
	zassert_equal(z_sched_wake_fake.arg1_val, 0);
	zassert_equal((stack_data_t)z_sched_wake_fake.arg2_val, VALUE(0));
	zassert_equal(buffer[0], VALUE(0));
}

/* The stack of the push in other_thread_pushes(). */
static struct k_stack *push_stack;

/*
 * Fake z_sched_wake(): the scheduler gives swap_data to the waiting thread
 * (_current) and wakes it with the return value swap_retval.
 */
static bool wake_current_thread(_wait_q_t *wait_q, int swap_retval, void *swap_data)
{
	ARG_UNUSED(wait_q);

	_current->base.swap_data = swap_data;
	kernel_unit_wake_current(swap_retval);

	return true;
}

/*
 * Action of another thread while the current thread waits in z_pend_curr()
 * (kernel_unit_set_other_thread()): it pushes VALUE(7) to the stack. The wait
 * ends with the return value that the push gave to the thread.
 */
static void other_thread_pushes(void)
{
	z_sched_wake_fake.custom_fake = wake_current_thread;
	zassert_equal(z_impl_k_stack_push(push_stack, VALUE(7)), 0);
}

/**
 * @brief The value of k_stack_push() reaches the thread that waits in k_stack_pop().
 *
 * @details
 * The test connects the two sides of the hand-over through the fakes.
 * - Setup: an empty stack. z_pend_curr() runs a push of value 7 while the
 *   thread waits. z_sched_wake() gives the swap data and the return value
 *   to the current thread.
 * - Action: z_impl_k_stack_pop() with K_FOREVER.
 * - Expected: return value 0. The data is value 7. The stack is empty, and
 *   the buffer did not change.
 *
 * @ingroup kernel_unit_stack_k_stack_pop
 * @see z_impl_k_stack_pop(), z_impl_k_stack_push()
 */
ZTEST(stack_unit, test_handover_push_reaches_waiting_pop)
{
	struct k_stack stack;
	stack_data_t data = FILL_DATA;

	stack_prepare(&stack, buffer, N_ENTRIES);
	push_stack = &stack;
	kernel_unit_set_other_thread(other_thread_pushes, false);

	zassert_equal(z_impl_k_stack_pop(&stack, &data, K_FOREVER), 0);

	zassert_equal(data, VALUE(7));
	zassert_equal(stack_len(&stack), 0U);
	zassert_equal(buffer[0], FILL_DATA);
}

/*
 * Tests: Pop. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_stack, at the top of this file.
 */

/**
 * @brief k_stack_pop() of a stack with values decrements next, gives the value of the entry at
 * next, and returns 0.
 *
 * @details
 * - Setup: a stack with values 0 and 1.
 * - Action: z_impl_k_stack_pop() with K_NO_WAIT.
 * - Expected: return value 0. The data is value 1. next is the buffer plus
 *   1 entry. The entries do not change.
 *
 * @ingroup kernel_unit_stack_k_stack_pop
 * @see z_impl_k_stack_pop()
 */
ZTEST(stack_unit, test_pop_takes_last_value)
{
	struct k_stack stack;
	stack_data_t data = FILL_DATA;

	stack_prepare(&stack, buffer, N_ENTRIES);
	stack_preload(&stack, 2);

	zassert_equal(z_impl_k_stack_pop(&stack, &data, K_NO_WAIT), 0);

	zassert_equal(data, VALUE(1));
	zassert_equal_ptr(stack.next, &buffer[1]);
	zassert_equal(buffer[0], VALUE(0));
	zassert_equal(buffer[1], VALUE(1));
}

/**
 * @brief k_stack_pop() gives the values in the reverse order of k_stack_push(): last in, first
 * out.
 *
 * @details
 * - Setup: an empty stack. No thread waits.
 * - Action: z_impl_k_stack_push() of values 0 to 3, then
 *   z_impl_k_stack_pop() 4 times.
 * - Expected: the pops give values 3, 2, 1, 0. The stack is empty.
 *
 * @ingroup kernel_unit_stack_k_stack_pop
 * @see z_impl_k_stack_pop(), z_impl_k_stack_push()
 */
ZTEST(stack_unit, test_pop_last_in_first_out)
{
	struct k_stack stack;
	stack_data_t data;

	stack_prepare(&stack, buffer, N_ENTRIES);

	for (size_t i = 0; i < N_ENTRIES; i++) {
		zassert_equal(z_impl_k_stack_push(&stack, VALUE(i)), 0);
	}
	for (size_t i = N_ENTRIES; i > 0; i--) {
		zassert_equal(z_impl_k_stack_pop(&stack, &data, K_NO_WAIT), 0);
		zassert_equal(data, VALUE(i - 1U), "pop %zu", N_ENTRIES - i);
	}

	zassert_equal_ptr(stack.next, stack.base);
}

/**
 * @brief k_stack_pop() of a stack with values does not wait, also with a timeout.
 *
 * @details
 * - Setup: a stack with value 0.
 * - Action: z_impl_k_stack_pop() with K_FOREVER.
 * - Expected: return value 0. The data is value 0. No call of z_pend_curr().
 *
 * @ingroup kernel_unit_stack_k_stack_pop
 * @see z_impl_k_stack_pop()
 */
ZTEST(stack_unit, test_pop_with_values_does_not_wait)
{
	struct k_stack stack;
	stack_data_t data = FILL_DATA;

	stack_prepare(&stack, buffer, N_ENTRIES);
	stack_preload(&stack, 1);

	zassert_equal(z_impl_k_stack_pop(&stack, &data, K_FOREVER), 0);

	zassert_equal(data, VALUE(0));
	zassert_equal(z_pend_curr_fake.call_count, 0);
}

/**
 * @brief k_stack_pop() of an empty stack with K_NO_WAIT returns -EBUSY and does not write the
 * data.
 *
 * @details
 * - Setup: an empty stack.
 * - Action: z_impl_k_stack_pop() with K_NO_WAIT.
 * - Expected: return value -EBUSY. The data keeps the pattern. next is
 *   base. No call of z_pend_curr().
 *
 * @ingroup kernel_unit_stack_k_stack_pop
 * @see z_impl_k_stack_pop()
 */
ZTEST(stack_unit, test_pop_empty_no_wait_returns_ebusy)
{
	struct k_stack stack;
	stack_data_t data = FILL_DATA;

	stack_prepare(&stack, buffer, N_ENTRIES);

	zassert_equal(z_impl_k_stack_pop(&stack, &data, K_NO_WAIT), -EBUSY);

	zassert_equal(data, FILL_DATA);
	zassert_equal_ptr(stack.next, stack.base);
	zassert_equal(z_pend_curr_fake.call_count, 0);
}

/**
 * @brief k_stack_pop() of an empty stack with a timeout waits on the wait queue of the stack with
 * the same timeout.
 *
 * @details
 * - Setup: an empty stack. The wait ends with result 0.
 * - Action: z_impl_k_stack_pop() with a timeout of 10 ticks, then with
 *   K_FOREVER.
 * - Expected: two calls of z_pend_curr() with the lock of the stack, the
 *   wait queue of the stack and the timeout of the call.
 *
 * @ingroup kernel_unit_stack_k_stack_pop
 * @see z_impl_k_stack_pop()
 */
ZTEST(stack_unit, test_pop_empty_waits_with_timeout)
{
	struct k_stack stack;
	stack_data_t data;

	stack_prepare(&stack, buffer, N_ENTRIES);
	kernel_unit_set_wait_result((void *)VALUE(0), 0);

	zassert_equal(z_impl_k_stack_pop(&stack, &data, TEST_TIMEOUT), 0);
	zassert_equal(z_impl_k_stack_pop(&stack, &data, K_FOREVER), 0);

	zassert_equal(z_pend_curr_fake.call_count, 2);
	zassert_equal_ptr(z_pend_curr_fake.arg0_history[0], &stack.lock);
	zassert_equal_ptr(z_pend_curr_fake.arg2_history[0], &stack.wait_q);
	zassert_true(K_TIMEOUT_EQ(z_pend_curr_fake.arg3_history[0], TEST_TIMEOUT));
	zassert_equal_ptr(z_pend_curr_fake.arg2_history[1], &stack.wait_q);
	zassert_true(K_TIMEOUT_EQ(z_pend_curr_fake.arg3_history[1], K_FOREVER));
}

/**
 * @brief After a wake, k_stack_pop() gives the swap data of the current thread and returns 0.
 *
 * @details
 * - Setup: an empty stack. The wait ends with result 0 and the swap data
 *   value 5.
 * - Action: z_impl_k_stack_pop() with a timeout.
 * - Expected: return value 0. The data is value 5. The stack and the buffer
 *   do not change.
 *
 * @ingroup kernel_unit_stack_k_stack_pop
 * @see z_impl_k_stack_pop()
 */
ZTEST(stack_unit, test_pop_after_wake_gives_swap_data)
{
	struct k_stack stack;
	stack_data_t data = FILL_DATA;

	stack_prepare(&stack, buffer, N_ENTRIES);
	kernel_unit_set_wait_result((void *)VALUE(5), 0);

	zassert_equal(z_impl_k_stack_pop(&stack, &data, TEST_TIMEOUT), 0);

	zassert_equal(data, VALUE(5));
	zassert_equal_ptr(stack.next, stack.base);
	zassert_equal(buffer[0], FILL_DATA);
}

/**
 * @brief If the wait times out, k_stack_pop() returns -EAGAIN and does not write the data.
 *
 * @details
 * - Setup: an empty stack. The wait ends with result -EAGAIN. The swap data
 *   of the current thread is value 5.
 * - Action: z_impl_k_stack_pop() with a timeout.
 * - Expected: return value -EAGAIN. The data keeps the pattern.
 *
 * @ingroup kernel_unit_stack_k_stack_pop
 * @see z_impl_k_stack_pop()
 */
ZTEST(stack_unit, test_pop_timeout_returns_eagain)
{
	struct k_stack stack;
	stack_data_t data = FILL_DATA;

	stack_prepare(&stack, buffer, N_ENTRIES);
	kernel_unit_set_wait_result((void *)VALUE(5), -EAGAIN);

	zassert_equal(z_impl_k_stack_pop(&stack, &data, TEST_TIMEOUT), -EAGAIN);

	zassert_equal(data, FILL_DATA);
}

/**
 * @brief k_stack_pop() handles each wait result other than -EAGAIN as a wake: it gives the swap
 * data and returns 0.
 *
 * @details
 * Only k_stack_push() wakes a thread on the wait queue of a stack, and it
 * gives the result 0. k_stack_pop() does not examine other results.
 * - Setup: an empty stack. The wait ends with result -EINTR and the swap
 *   data value 5.
 * - Action: z_impl_k_stack_pop() with a timeout.
 * - Expected: return value 0. The data is value 5.
 *
 * @ingroup kernel_unit_stack_k_stack_pop
 * @see z_impl_k_stack_pop()
 */
ZTEST(stack_unit, test_pop_other_wait_result_is_wake)
{
	struct k_stack stack;
	stack_data_t data = FILL_DATA;

	stack_prepare(&stack, buffer, N_ENTRIES);
	kernel_unit_set_wait_result((void *)VALUE(5), -EINTR);

	zassert_equal(z_impl_k_stack_pop(&stack, &data, TEST_TIMEOUT), 0);

	zassert_equal(data, VALUE(5));
}

/**
 * @brief In an ISR, a k_stack_pop() that must wait reaches z_pend_curr(), and the scheduler
 * refuses it with a panic. stack.c has no earlier check.
 *
 * @details
 * The real z_pend_curr() refuses a call from an ISR in every build, before
 * it changes a thread or a wait queue.
 * - Setup: an empty stack. arch_is_in_isr() returns true. The scheduler
 *   model would give value 5 with the result 0. The test expects the
 *   refusal of z_pend_curr().
 * - Action: z_impl_k_stack_pop() with K_FOREVER.
 * - Expected: one call of z_pend_curr() with the lock of the stack. The
 *   scheduler refuses the wait with a failed assertion (with CONFIG_ASSERT,
 *   the only one) and a panic. The model does not run. The lock stays
 *   locked, and the stack stays empty. After the panic, the fake returns
 *   KERNEL_UNIT_PEND_REFUSED (-EAGAIN, a timeout). k_stack_pop() returns
 *   -EAGAIN, and the data keeps the pattern. With each other value,
 *   k_stack_pop() writes the swap data (see
 *   test_pop_other_wait_result_is_wake).
 *
 * @ingroup kernel_unit_stack_k_stack_pop
 * @see z_impl_k_stack_pop()
 */
ZTEST(stack_unit, test_pop_in_isr_with_wait_refused_by_scheduler)
{
	struct k_stack stack;
	stack_data_t data = FILL_DATA;

	stack_prepare(&stack, buffer, N_ENTRIES);
	arch_is_in_isr_fake.return_val = true;
	kernel_unit_set_wait_result((void *)VALUE(5), 0);
	kernel_unit_expect_pend_refusal();

	zassert_equal(z_impl_k_stack_pop(&stack, &data, K_FOREVER), -EAGAIN);

	kernel_unit_assert_pend_refused();
	zassert_equal(z_pend_curr_fake.call_count, 1);
	zassert_equal_ptr(z_pend_curr_fake.arg0_val, &stack.lock);
	zassert_equal(unit_arch_irq_unlock_fake.call_count, 0);
	zassert_equal(data, FILL_DATA);
	zassert_equal_ptr(stack.next, stack.base);
#ifdef CONFIG_ASSERT
	zassert_equal(assert_post_action_fake.call_count, 1);
#endif
}

/*
 * Tests: Locking. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_stack, at the top of this file.
 */

/**
 * @brief If k_stack_push() stores the value, it releases the lock with k_spin_unlock().
 *
 * @details
 * - Setup: an empty stack. No thread waits.
 * - Action: z_impl_k_stack_push().
 * - Expected calls: arch_irq_lock(), z_sched_wake(), arch_irq_unlock() with
 *   the key.
 *
 * @ingroup kernel_unit_stack_k_stack_push
 * @see z_impl_k_stack_push()
 */
ZTEST(stack_unit, test_lock_push_store_unlocks)
{
	struct k_stack stack;

	stack_prepare(&stack, buffer, N_ENTRIES);

	zassert_equal(z_impl_k_stack_push(&stack, VALUE(0)), 0);

	zassert_call_history(unit_arch_irq_lock, z_sched_wake, unit_arch_irq_unlock);
	assert_lock_released_once(&stack, KERNEL_UNIT_RELEASED_BY_UNLOCK);
}

/**
 * @brief If k_stack_push() gives the value to a waiting thread, it releases the lock with
 * z_reschedule().
 *
 * @details
 * - Setup: an empty stack. One thread waits.
 * - Action: z_impl_k_stack_push().
 * - Expected calls: arch_irq_lock(), z_sched_wake(), z_reschedule() with the
 *   lock of the stack and the key.
 *
 * @ingroup kernel_unit_stack_k_stack_push
 * @see z_impl_k_stack_push()
 */
ZTEST(stack_unit, test_lock_push_handover_reschedules)
{
	struct k_stack stack;

	stack_prepare(&stack, buffer, N_ENTRIES);
	kernel_unit_set_waiting_threads(1);

	zassert_equal(z_impl_k_stack_push(&stack, VALUE(0)), 0);

	zassert_call_history(unit_arch_irq_lock, z_sched_wake, z_reschedule);
	assert_lock_released_once(&stack, KERNEL_UNIT_RELEASED_BY_RESCHEDULE);
}

/**
 * @brief If the stack is full, k_stack_push() releases the lock with k_spin_unlock().
 *
 * @details
 * Applies with CONFIG_RUNTIME_ERROR_CHECKS (the default CHECKIF() option).
 * - Setup: a full stack.
 * - Action: z_impl_k_stack_push().
 * - Expected calls: arch_irq_lock(), arch_irq_unlock() with the key.
 *
 * @ingroup kernel_unit_stack_k_stack_push
 * @see z_impl_k_stack_push()
 */
ZTEST(stack_unit, test_lock_push_full_unlocks)
{
	struct k_stack stack;

	if (!IS_ENABLED(CONFIG_RUNTIME_ERROR_CHECKS)) {
		ztest_test_skip();
	}

	stack_prepare(&stack, buffer, N_ENTRIES);
	stack_preload(&stack, N_ENTRIES);

	zassert_equal(z_impl_k_stack_push(&stack, VALUE(9)), -ENOMEM);

	zassert_call_history(unit_arch_irq_lock, unit_arch_irq_unlock);
	assert_lock_released_once(&stack, KERNEL_UNIT_RELEASED_BY_UNLOCK);
}

/**
 * @brief k_stack_push() reads and changes next only while it holds the lock.
 *
 * @details
 * - Setup: a stack with 1 value. No thread waits. Spy fakes record the
 *   number of values at the lock and at the release.
 * - Action: z_impl_k_stack_push().
 * - Expected: 1 value at the lock, 2 values at the release.
 *
 * @ingroup kernel_unit_stack_k_stack_push
 * @see z_impl_k_stack_push()
 */
ZTEST(stack_unit, test_lock_push_changes_under_lock)
{
	struct k_stack stack;

	stack_prepare(&stack, buffer, N_ENTRIES);
	stack_preload(&stack, 1);
	spy_on_lock(&stack, NULL);

	zassert_equal(z_impl_k_stack_push(&stack, VALUE(1)), 0);

	zassert_equal(len_at_lock, 1U);
	zassert_equal(len_at_release, 2U);
}

/**
 * @brief If the stack has values, k_stack_pop() writes the data and changes next while it holds the
 * lock, and then releases the lock with k_spin_unlock().
 *
 * @details
 * - Setup: a stack with values 0 and 1. Spy fakes record the number of
 *   values at the lock and the number of values and the data at the
 *   release.
 * - Action: z_impl_k_stack_pop() with K_NO_WAIT.
 * - Expected calls: arch_irq_lock(), arch_irq_unlock() with the key. 2
 *   values at the lock. 1 value and the data value 1 at the release.
 *
 * @ingroup kernel_unit_stack_k_stack_pop
 * @see z_impl_k_stack_pop()
 */
ZTEST(stack_unit, test_lock_pop_value_unlocks)
{
	struct k_stack stack;
	stack_data_t data = FILL_DATA;

	stack_prepare(&stack, buffer, N_ENTRIES);
	stack_preload(&stack, 2);
	spy_on_lock(&stack, &data);

	zassert_equal(z_impl_k_stack_pop(&stack, &data, K_NO_WAIT), 0);

	zassert_call_history(unit_arch_irq_lock, unit_arch_irq_unlock);
	assert_lock_released_once(&stack, KERNEL_UNIT_RELEASED_BY_UNLOCK);
	zassert_equal(len_at_lock, 2U);
	zassert_equal(len_at_release, 1U);
	zassert_equal(data_at_release, VALUE(1));
}

/**
 * @brief If k_stack_pop() returns -EBUSY, it releases the lock with k_spin_unlock().
 *
 * @details
 * - Setup: an empty stack.
 * - Action: z_impl_k_stack_pop() with K_NO_WAIT.
 * - Expected calls: arch_irq_lock(), arch_irq_unlock() with the key.
 *
 * @ingroup kernel_unit_stack_k_stack_pop
 * @see z_impl_k_stack_pop()
 */
ZTEST(stack_unit, test_lock_pop_no_wait_unlocks)
{
	struct k_stack stack;
	stack_data_t data;

	stack_prepare(&stack, buffer, N_ENTRIES);

	zassert_equal(z_impl_k_stack_pop(&stack, &data, K_NO_WAIT), -EBUSY);

	zassert_call_history(unit_arch_irq_lock, unit_arch_irq_unlock);
	assert_lock_released_once(&stack, KERNEL_UNIT_RELEASED_BY_UNLOCK);
}

/**
 * @brief If k_stack_pop() waits, z_pend_curr() releases the lock, and k_stack_pop() does not lock
 * or release it again after the wake.
 *
 * @details
 * - Setup: an empty stack. The wait ends with result 0.
 * - Action: z_impl_k_stack_pop() with a timeout.
 * - Expected calls: arch_irq_lock(), z_pend_curr() with the lock of the
 *   stack and the key.
 *
 * @ingroup kernel_unit_stack_k_stack_pop
 * @see z_impl_k_stack_pop()
 */
ZTEST(stack_unit, test_lock_pop_wait_pends)
{
	struct k_stack stack;
	stack_data_t data;

	stack_prepare(&stack, buffer, N_ENTRIES);
	kernel_unit_set_wait_result((void *)VALUE(0), 0);

	zassert_equal(z_impl_k_stack_pop(&stack, &data, TEST_TIMEOUT), 0);

	zassert_call_history(unit_arch_irq_lock, z_pend_curr);
	assert_lock_released_once(&stack, KERNEL_UNIT_RELEASED_BY_PEND);
}

/**
 * @brief If the wait of k_stack_pop() times out, k_stack_pop() does not lock or release the lock
 * again.
 *
 * @details
 * - Setup: an empty stack. The wait ends with result -EAGAIN.
 * - Action: z_impl_k_stack_pop() with a timeout.
 * - Expected calls: arch_irq_lock(), z_pend_curr() with the lock of the
 *   stack and the key.
 *
 * @ingroup kernel_unit_stack_k_stack_pop
 * @see z_impl_k_stack_pop()
 */
ZTEST(stack_unit, test_lock_pop_timeout_pends)
{
	struct k_stack stack;
	stack_data_t data;

	stack_prepare(&stack, buffer, N_ENTRIES);
	kernel_unit_set_wait_result((void *)VALUE(0), -EAGAIN);

	zassert_equal(z_impl_k_stack_pop(&stack, &data, TEST_TIMEOUT), -EAGAIN);

	zassert_call_history(unit_arch_irq_lock, z_pend_curr);
	assert_lock_released_once(&stack, KERNEL_UNIT_RELEASED_BY_PEND);
}

/**
 * @brief k_stack_cleanup() frees the buffer while it holds the lock, and then releases the lock
 * with k_spin_unlock().
 *
 * @details
 * - Setup: a stack with an allocated buffer. No thread waits.
 * - Action: k_stack_cleanup().
 * - Expected calls: arch_irq_lock(), z_waitq_head() (with CHECKIF()
 *   active), k_free(), arch_irq_unlock() with the key.
 *
 * @ingroup kernel_unit_stack_k_stack_cleanup
 * @see k_stack_cleanup(), z_stack_cleanup()
 */
ZTEST(stack_unit, test_lock_cleanup_frees_under_lock)
{
	struct k_stack stack;

	stack_prepare(&stack, heap_buffer, N_ENTRIES);
	stack.flags = K_STACK_FLAG_ALLOC;

	zassert_equal(k_stack_cleanup(&stack), 0);

	zassert_call_history(unit_arch_irq_lock, IF_CHECKED(z_waitq_head), k_free,
			     unit_arch_irq_unlock);
	assert_lock_released_once(&stack, KERNEL_UNIT_RELEASED_BY_UNLOCK);
}

/**
 * @brief If a thread waits, k_stack_cleanup() releases the lock with k_spin_unlock().
 *
 * @details
 * Applies with CONFIG_RUNTIME_ERROR_CHECKS (the default CHECKIF() option).
 * - Setup: a stack with an allocated buffer. A thread waits.
 * - Action: k_stack_cleanup().
 * - Expected calls: arch_irq_lock(), z_waitq_head(), arch_irq_unlock() with
 *   the key.
 *
 * @ingroup kernel_unit_stack_k_stack_cleanup
 * @see k_stack_cleanup(), z_stack_cleanup()
 */
ZTEST(stack_unit, test_lock_cleanup_thread_waits_unlocks)
{
	struct k_stack stack;

	if (!IS_ENABLED(CONFIG_RUNTIME_ERROR_CHECKS)) {
		ztest_test_skip();
	}

	stack_prepare(&stack, heap_buffer, N_ENTRIES);
	stack.flags = K_STACK_FLAG_ALLOC;
	set_wait_queue_not_empty();

	zassert_equal(k_stack_cleanup(&stack), -EAGAIN);

	zassert_call_history(unit_arch_irq_lock, z_waitq_head, unit_arch_irq_unlock);
	assert_lock_released_once(&stack, KERNEL_UNIT_RELEASED_BY_UNLOCK);
}

/**
 * @brief z_stack_cleanup() with locked true also locks the lock of the stack, and releases it with
 * k_spin_unlock().
 *
 * @details
 * The caller holds the scheduler lock. Thus the lock of the stack nests
 * inside the scheduler lock on this path.
 * - Setup: a stack with an allocated buffer. No thread waits.
 * - Action: z_stack_cleanup() with locked true.
 * - Expected calls: arch_irq_lock(), z_waitq_head_locked() (with CHECKIF()
 *   active), k_free(), arch_irq_unlock() with the key.
 *
 * @ingroup kernel_unit_stack_z_stack_cleanup
 * @see z_stack_cleanup()
 */
ZTEST(stack_unit, test_lock_cleanup_locked_takes_stack_lock)
{
	struct k_stack stack;

	stack_prepare(&stack, heap_buffer, N_ENTRIES);
	stack.flags = K_STACK_FLAG_ALLOC;

	zassert_equal(z_stack_cleanup(&stack, true), 0);

	zassert_call_history(unit_arch_irq_lock, IF_CHECKED(z_waitq_head_locked), k_free,
			     unit_arch_irq_unlock);
	assert_lock_released_once(&stack, KERNEL_UNIT_RELEASED_BY_UNLOCK);
}

/**
 * @brief k_stack_cleanup() of a stack with a buffer of the caller locks and releases the lock once.
 *
 * @details
 * - Setup: a stack with the flags 0. No thread waits.
 * - Action: k_stack_cleanup().
 * - Expected calls: arch_irq_lock(), z_waitq_head() (with CHECKIF()
 *   active), arch_irq_unlock() with the key.
 *
 * @ingroup kernel_unit_stack_k_stack_cleanup
 * @see k_stack_cleanup(), z_stack_cleanup()
 */
ZTEST(stack_unit, test_lock_cleanup_caller_buffer_unlocks)
{
	struct k_stack stack;

	stack_prepare(&stack, buffer, N_ENTRIES);

	zassert_equal(k_stack_cleanup(&stack), 0);

	zassert_call_history(unit_arch_irq_lock, IF_CHECKED(z_waitq_head), unit_arch_irq_unlock);
	assert_lock_released_once(&stack, KERNEL_UNIT_RELEASED_BY_UNLOCK);
}

/**
 * @brief Each stack has its own lock.
 *
 * @details
 * - Setup: two empty stacks. One thread waits on each.
 * - Action: z_impl_k_stack_push() to the first stack, then to the second
 *   stack.
 * - Expected: two calls of z_reschedule(), the first with the lock of the
 *   first stack, the second with the lock of the second stack.
 *
 * @ingroup kernel_unit_stack_k_stack_push
 * @see z_impl_k_stack_push()
 */
ZTEST(stack_unit, test_lock_one_lock_per_stack)
{
	struct k_stack stack1;
	struct k_stack stack2;

	stack_prepare(&stack1, buffer, N_ENTRIES);
	stack_prepare(&stack2, buffer2, N_ENTRIES);
	kernel_unit_set_waiting_threads(2);

	zassert_equal(z_impl_k_stack_push(&stack1, VALUE(0)), 0);
	zassert_equal(z_impl_k_stack_push(&stack2, VALUE(1)), 0);

	zassert_equal(z_reschedule_fake.call_count, 2);
	zassert_equal_ptr(z_reschedule_fake.arg0_history[0], &stack1.lock);
	zassert_equal_ptr(z_reschedule_fake.arg0_history[1], &stack2.lock);
}

/**
 * @brief k_stack_init() and k_stack_alloc_init() do not lock the stack.
 *
 * @details
 * - Action: k_stack_init(), then z_impl_k_stack_alloc_init().
 * - Expected: no call of arch_irq_lock().
 *
 * @ingroup kernel_unit_stack_k_stack_init
 * @see k_stack_init(), z_impl_k_stack_alloc_init()
 */
ZTEST(stack_unit, test_lock_not_used_by_init)
{
	struct k_stack stack;

	set_heap(N_ENTRIES);

	k_stack_init(&stack, buffer, N_ENTRIES);
	zassert_equal(z_impl_k_stack_alloc_init(&stack, N_ENTRIES), 0);

	zassert_equal(unit_arch_irq_lock_fake.call_count, 0);
}

#ifdef CONFIG_SPIN_VALIDATE
/**
 * @brief With CONFIG_SPIN_VALIDATE, the spinlock validation sees the lock of the stack on lock and
 * on unlock.
 *
 * @details
 * - Setup: an empty stack.
 * - Action: z_impl_k_stack_pop() with K_NO_WAIT.
 * - Expected: one call of z_spin_lock_valid() and one call of
 *   z_spin_unlock_valid(), each with the lock of the stack.
 *
 * @ingroup kernel_unit_stack_k_stack_pop
 * @see z_impl_k_stack_pop()
 */
ZTEST(stack_unit, test_lock_validation_sees_stack_lock)
{
	struct k_stack stack;
	stack_data_t data;

	stack_prepare(&stack, buffer, N_ENTRIES);

	zassert_equal(z_impl_k_stack_pop(&stack, &data, K_NO_WAIT), -EBUSY);

	zassert_equal(z_spin_lock_valid_fake.call_count, 1);
	zassert_equal_ptr(z_spin_lock_valid_fake.arg0_val, &stack.lock);
	zassert_equal(z_spin_unlock_valid_fake.call_count, 1);
	zassert_equal_ptr(z_spin_unlock_valid_fake.arg0_val, &stack.lock);
}
#endif /* CONFIG_SPIN_VALIDATE */

#ifdef CONFIG_USERSPACE
/*
 * Tests: System call verification. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_stack, at the top of this file.
 */

/* Assert one object check of stack with the type K_OBJ_STACK and init state, and no oops. */
static void assert_object_check(struct k_stack *stack, enum _obj_init_check init)
{
	kernel_unit_assert_object_check(stack, K_OBJ_STACK, init);
}

/* Assert one oops, before the first call of fn (the first change of the stack). */
#define zassert_oops_before(fn)                                                                    \
	do {                                                                                       \
		zassert_equal(unit_syscall_oops_fake.call_count, 1);                               \
		zassert_called_before(unit_syscall_oops, fn);                                      \
	} while (false)

/**
 * @brief z_vrfy_k_stack_alloc_init() checks that the pointer is a stack object that is not
 * initialized, and then returns the result of z_impl_k_stack_alloc_init().
 *
 * @details
 * - Setup: the object check passes. z_thread_malloc() gives a buffer.
 * - Action: z_vrfy_k_stack_alloc_init() with 4 entries.
 * - Expected: return value 0. k_object_find() and
 *   k_object_validation_check() with the stack, K_OBJ_STACK and
 *   _OBJ_INIT_FALSE, before z_thread_malloc(). No oops. The stack has the
 *   allocated buffer.
 *
 * @ingroup kernel_unit_stack_k_stack_alloc_init
 * @see z_vrfy_k_stack_alloc_init()
 */
ZTEST(stack_unit, test_syscall_alloc_init_checks_new_object)
{
	struct k_stack stack;

	kernel_unit_pass_object_check();
	set_heap(N_ENTRIES);

	zassert_equal(z_vrfy_k_stack_alloc_init(&stack, N_ENTRIES), 0);

	assert_object_check(&stack, _OBJ_INIT_FALSE);
	zassert_called_before(k_object_validation_check, z_thread_malloc);
	zassert_equal_ptr(stack.base, heap_buffer);
}

/**
 * @brief z_vrfy_k_stack_alloc_init() returns the error of z_impl_k_stack_alloc_init().
 *
 * @details
 * - Setup: the object check passes. z_thread_malloc() returns NULL.
 * - Action: z_vrfy_k_stack_alloc_init() with 4 entries.
 * - Expected: return value -ENOMEM. No oops.
 *
 * @ingroup kernel_unit_stack_k_stack_alloc_init
 * @see z_vrfy_k_stack_alloc_init()
 */
ZTEST(stack_unit, test_syscall_alloc_init_returns_error)
{
	struct k_stack stack;

	kernel_unit_pass_object_check();

	zassert_equal(z_vrfy_k_stack_alloc_init(&stack, N_ENTRIES), -ENOMEM);

	zassert_equal(unit_syscall_oops_fake.call_count, 0);
}

/**
 * @brief If the object check fails, z_vrfy_k_stack_alloc_init() raises an oops before it allocates.
 *
 * @details
 * - Setup: the object check fails (for example, the stack is already
 *   initialized).
 * - Action: z_vrfy_k_stack_alloc_init() with 4 entries.
 * - Expected: one oops, before z_thread_malloc().
 *
 * @ingroup kernel_unit_stack_k_stack_alloc_init
 * @see z_vrfy_k_stack_alloc_init()
 */
ZTEST(stack_unit, test_syscall_alloc_init_oops_on_bad_object)
{
	struct k_stack stack;

	kernel_unit_fail_object_check();
	set_heap(N_ENTRIES);

	(void)z_vrfy_k_stack_alloc_init(&stack, N_ENTRIES);

	zassert_oops_before(z_thread_malloc);
}

/**
 * @brief If the number of entries is 0, z_vrfy_k_stack_alloc_init() raises an oops before it
 * allocates.
 *
 * @details
 * - Setup: the object check passes.
 * - Action: z_vrfy_k_stack_alloc_init() with 0 entries.
 * - Expected: one oops, after the object check and before
 *   z_thread_malloc().
 *
 * @ingroup kernel_unit_stack_k_stack_alloc_init
 * @see z_vrfy_k_stack_alloc_init()
 */
ZTEST(stack_unit, test_syscall_alloc_init_oops_on_zero_entries)
{
	struct k_stack stack;

	kernel_unit_pass_object_check();
	set_heap(0);

	(void)z_vrfy_k_stack_alloc_init(&stack, 0);

	zassert_oops_before(z_thread_malloc);
	zassert_called_before(k_object_validation_check, unit_syscall_oops);
}

/**
 * @brief If the size of the buffer does not fit into size_t, z_vrfy_k_stack_alloc_init() raises an
 * oops before it allocates.
 *
 * @details
 * This applies only if a @c uint32_t number of entries can overflow
 * @c size_t, for example on a 32-bit build. On a 64-bit build the test
 * skips itself.
 * - Setup: the object check passes.
 * - Action: z_vrfy_k_stack_alloc_init() with SIZE_MAX /
 *   sizeof(stack_data_t) + 1 entries.
 * - Expected: one oops. No call of z_thread_malloc() (the implementation
 *   also rejects the size).
 *
 * @ingroup kernel_unit_stack_k_stack_alloc_init
 * @see z_vrfy_k_stack_alloc_init()
 */
ZTEST(stack_unit, test_syscall_alloc_init_oops_on_size_overflow)
{
	struct k_stack stack;
	uint32_t n = (uint32_t)(SIZE_MAX / sizeof(stack_data_t)) + 1U;

	if ((uint64_t)UINT32_MAX * sizeof(stack_data_t) <= (uint64_t)SIZE_MAX) {
		ztest_test_skip();
	}

	kernel_unit_pass_object_check();

	zassert_equal(z_vrfy_k_stack_alloc_init(&stack, n), -ENOMEM);

	zassert_equal(unit_syscall_oops_fake.call_count, 1);
	zassert_equal(z_thread_malloc_fake.call_count, 0);
}

/**
 * @brief z_vrfy_k_stack_push() checks that the pointer is an initialized stack object, and then
 * returns the result of z_impl_k_stack_push().
 *
 * @details
 * - Setup: an empty stack. The object check passes.
 * - Action: z_vrfy_k_stack_push() of value 0, then of values 1 to 4 (the
 *   last push finds the stack full).
 * - Expected: the object check with K_OBJ_STACK and _OBJ_INIT_TRUE, before
 *   the lock. No oops. Entry 0 is value 0. With CONFIG_RUNTIME_ERROR_CHECKS,
 *   the last push returns -ENOMEM.
 *
 * @ingroup kernel_unit_stack_k_stack_push
 * @see z_vrfy_k_stack_push()
 */
ZTEST(stack_unit, test_syscall_push_checks_initialized_object)
{
	struct k_stack stack;

	stack_prepare(&stack, buffer, N_ENTRIES);
	kernel_unit_pass_object_check();

	zassert_equal(z_vrfy_k_stack_push(&stack, VALUE(0)), 0);

	assert_object_check(&stack, _OBJ_INIT_TRUE);
	zassert_called_before(k_object_validation_check, unit_arch_irq_lock);
	zassert_equal(buffer[0], VALUE(0));

	for (size_t i = 1; i < N_ENTRIES; i++) {
		zassert_equal(z_vrfy_k_stack_push(&stack, VALUE(i)), 0);
	}
	if (IS_ENABLED(CONFIG_RUNTIME_ERROR_CHECKS)) {
		zassert_equal(z_vrfy_k_stack_push(&stack, VALUE(9)), -ENOMEM);
	}
}

/**
 * @brief If the object check fails, z_vrfy_k_stack_push() raises an oops before it locks the
 * stack.
 *
 * @details
 * - Setup: an empty stack. The object check fails.
 * - Action: z_vrfy_k_stack_push().
 * - Expected: one oops, before arch_irq_lock().
 *
 * @ingroup kernel_unit_stack_k_stack_push
 * @see z_vrfy_k_stack_push()
 */
ZTEST(stack_unit, test_syscall_push_oops_on_bad_object)
{
	struct k_stack stack;

	stack_prepare(&stack, buffer, N_ENTRIES);
	kernel_unit_fail_object_check();

	(void)z_vrfy_k_stack_push(&stack, VALUE(0));

	zassert_oops_before(unit_arch_irq_lock);
}

/**
 * @brief z_vrfy_k_stack_pop() checks that the pointer is an initialized stack object and that the
 * thread can write the data, and then returns the result of z_impl_k_stack_pop().
 *
 * @details
 * - Setup: a stack with value 3. The object check and the memory check
 *   pass.
 * - Action: z_vrfy_k_stack_pop() with K_NO_WAIT.
 * - Expected: return value 0. The data is value 3. The object check with
 *   K_OBJ_STACK and _OBJ_INIT_TRUE. Then one call of arch_buffer_validate()
 *   with the data, sizeof(stack_data_t) and write access. Both checks come
 *   before the lock. No oops.
 *
 * @ingroup kernel_unit_stack_k_stack_pop
 * @see z_vrfy_k_stack_pop()
 */
ZTEST(stack_unit, test_syscall_pop_checks_object_and_data)
{
	struct k_stack stack;
	stack_data_t data = FILL_DATA;

	stack_prepare(&stack, buffer, N_ENTRIES);
	*stack.next++ = VALUE(3);
	kernel_unit_pass_object_check();

	zassert_equal(z_vrfy_k_stack_pop(&stack, &data, K_NO_WAIT), 0);

	zassert_equal(data, VALUE(3));
	assert_object_check(&stack, _OBJ_INIT_TRUE);
	zassert_equal(arch_buffer_validate_fake.call_count, 1);
	zassert_equal_ptr(arch_buffer_validate_fake.arg0_val, &data);
	zassert_equal(arch_buffer_validate_fake.arg1_val, sizeof(stack_data_t));
	zassert_equal(arch_buffer_validate_fake.arg2_val, 1);
	zassert_called_before(k_object_validation_check, arch_buffer_validate);
	zassert_called_before(arch_buffer_validate, unit_arch_irq_lock);
}

/**
 * @brief z_vrfy_k_stack_pop() gives the timeout to z_impl_k_stack_pop() and returns its result.
 *
 * @details
 * - Setup: an empty stack. The checks pass. The wait ends with result
 *   -EAGAIN.
 * - Action: z_vrfy_k_stack_pop() with a timeout of 10 ticks.
 * - Expected: return value -EAGAIN. One call of z_pend_curr() with the
 *   timeout.
 *
 * @ingroup kernel_unit_stack_k_stack_pop
 * @see z_vrfy_k_stack_pop()
 */
ZTEST(stack_unit, test_syscall_pop_passes_timeout)
{
	struct k_stack stack;
	stack_data_t data;

	stack_prepare(&stack, buffer, N_ENTRIES);
	kernel_unit_pass_object_check();
	kernel_unit_set_wait_result((void *)VALUE(0), -EAGAIN);

	zassert_equal(z_vrfy_k_stack_pop(&stack, &data, TEST_TIMEOUT), -EAGAIN);

	zassert_equal(z_pend_curr_fake.call_count, 1);
	zassert_true(K_TIMEOUT_EQ(z_pend_curr_fake.arg3_val, TEST_TIMEOUT));
}

/**
 * @brief If the object check fails, z_vrfy_k_stack_pop() raises an oops before it locks the stack.
 *
 * @details
 * - Setup: an empty stack. The object check fails.
 * - Action: z_vrfy_k_stack_pop() with K_NO_WAIT.
 * - Expected: one oops, before arch_irq_lock().
 *
 * @ingroup kernel_unit_stack_k_stack_pop
 * @see z_vrfy_k_stack_pop()
 */
ZTEST(stack_unit, test_syscall_pop_oops_on_bad_object)
{
	struct k_stack stack;
	stack_data_t data;

	stack_prepare(&stack, buffer, N_ENTRIES);
	kernel_unit_fail_object_check();

	(void)z_vrfy_k_stack_pop(&stack, &data, K_NO_WAIT);

	zassert_oops_before(unit_arch_irq_lock);
}

/**
 * @brief If the thread cannot write the data, z_vrfy_k_stack_pop() raises an oops before it locks
 * the stack.
 *
 * @details
 * - Setup: an empty stack. The object check passes. arch_buffer_validate()
 *   returns -1.
 * - Action: z_vrfy_k_stack_pop() with K_NO_WAIT.
 * - Expected: one oops, after arch_buffer_validate() and before
 *   arch_irq_lock().
 *
 * @ingroup kernel_unit_stack_k_stack_pop
 * @see z_vrfy_k_stack_pop()
 */
ZTEST(stack_unit, test_syscall_pop_oops_on_bad_data)
{
	struct k_stack stack;
	stack_data_t data;

	stack_prepare(&stack, buffer, N_ENTRIES);
	kernel_unit_pass_object_check();
	arch_buffer_validate_fake.return_val = -1;

	(void)z_vrfy_k_stack_pop(&stack, &data, K_NO_WAIT);

	zassert_oops_before(unit_arch_irq_lock);
	zassert_called_before(arch_buffer_validate, unit_syscall_oops);
}

/**
 * @brief If the data area goes beyond the highest address, z_vrfy_k_stack_pop() raises an oops
 * before it locks the stack.
 *
 * @details
 * K_SYSCALL_MEMORY_WRITE() checks the size of the area before it asks the
 * architecture layer.
 * - Setup: an empty stack. The object check passes. The data pointer is
 *   UINTPTR_MAX - 3, so the area of sizeof(stack_data_t) bytes goes beyond
 *   the highest address.
 * - Action: z_vrfy_k_stack_pop() with K_NO_WAIT.
 * - Expected: one oops, before arch_irq_lock(). No call of
 *   arch_buffer_validate(). (The fake oops returns, and the empty stack
 *   returns -EBUSY without a write to the data.)
 *
 * @ingroup kernel_unit_stack_k_stack_pop
 * @see z_vrfy_k_stack_pop()
 */
ZTEST(stack_unit, test_syscall_pop_oops_on_data_overflow)
{
	struct k_stack stack;
	stack_data_t *data = (stack_data_t *)(UINTPTR_MAX - 3U);

	stack_prepare(&stack, buffer, N_ENTRIES);
	kernel_unit_pass_object_check();

	zassert_equal(z_vrfy_k_stack_pop(&stack, data, K_NO_WAIT), -EBUSY);

	zassert_oops_before(unit_arch_irq_lock);
	zassert_equal(arch_buffer_validate_fake.call_count, 0);
}
#endif /* CONFIG_USERSPACE */

/*
 * Tests: Object core. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_stack, at the top of this file.
 */

#ifdef CONFIG_OBJ_CORE_STACK
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
 * @brief With CONFIG_OBJ_CORE_STACK, stack.c defines one object type descriptor with the ID
 * K_OBJ_TYPE_STACK_ID.
 *
 * @details
 * - Action: search the section @c k_obj_core_desc for the descriptor of
 *   @c obj_type_stack.
 * - Expected: one descriptor. Its type ID is K_OBJ_TYPE_STACK_ID. Its object
 *   size is the size of @c struct @c k_stack, and its object core offset is
 *   the offset of @c obj_core. Its object range is the section @c k_stack.
 *
 * @ingroup kernel_unit_stack_static
 */
ZTEST(stack_unit, test_obj_core_type_descriptor)
{
	int count;
	const struct k_obj_core_desc *desc = obj_core_desc(&obj_type_stack, &count);

	zassert_equal(count, 1);
	zassert_not_null(desc);
	zassert_equal(desc->type_id, K_OBJ_TYPE_STACK_ID);
	zassert_equal(desc->obj_size, sizeof(struct k_stack));
	zassert_equal(desc->obj_core_offset, offsetof(struct k_stack, obj_core));
	zassert_equal_ptr(desc->objs_start, STRUCT_SECTION_START(k_stack));
	zassert_equal_ptr(desc->objs_end, STRUCT_SECTION_END(k_stack));
}

/**
 * @brief The object range of the stack descriptor contains the stacks that K_STACK_DEFINE()
 * defines.
 *
 * @details
 * - Setup: K_STACK_DEFINE() of one stack in the test.
 * - Action: compare the address of the stack with the object range of the
 *   descriptor.
 * - Expected: the stack is in the range, at a multiple of the object size
 *   from the start.
 *
 * @ingroup kernel_unit_stack_static
 */
ZTEST(stack_unit, test_obj_core_descriptor_covers_static_stacks)
{
	int count;
	const struct k_obj_core_desc *desc = obj_core_desc(&obj_type_stack, &count);
	uintptr_t obj = (uintptr_t)&unit_static_stack;

	zassert_not_null(desc);
	zassert_true((obj >= (uintptr_t)desc->objs_start) && (obj < (uintptr_t)desc->objs_end));
	zassert_equal((obj - (uintptr_t)desc->objs_start) % desc->obj_size, 0U);
}

/**
 * @brief With CONFIG_OBJ_CORE_STACK, k_stack_init() links the stack to the stack object type, as
 * its last call.
 *
 * @details
 * - Action: k_stack_init().
 * - Expected: one call of k_obj_core_init_and_link() with the object core of
 *   the stack and @c obj_type_stack. It is the last call.
 *
 * @ingroup kernel_unit_stack_k_stack_init
 * @see k_stack_init()
 */
ZTEST(stack_unit, test_obj_core_init_links_stack)
{
	struct k_stack stack;

	k_stack_init(&stack, buffer, N_ENTRIES);

	zassert_equal(k_obj_core_init_and_link_fake.call_count, 1);
	zassert_equal_ptr(k_obj_core_init_and_link_fake.arg0_val, K_OBJ_CORE(&stack));
	zassert_equal_ptr(k_obj_core_init_and_link_fake.arg1_val, &obj_type_stack);
	zassert_equal(kernel_unit_history_index(KERNEL_UNIT_FN(k_obj_core_init_and_link), 0),
		      (int)kernel_unit_history_len() - 1);
}

/**
 * @brief With CONFIG_OBJ_CORE_STACK, k_stack_alloc_init() links the stack after the allocation.
 *
 * @details
 * - Setup: z_thread_malloc() gives a buffer.
 * - Action: z_impl_k_stack_alloc_init().
 * - Expected: one call of k_obj_core_init_and_link() with the object core of
 *   the stack and @c obj_type_stack, after z_thread_malloc().
 *
 * @ingroup kernel_unit_stack_k_stack_alloc_init
 * @see z_impl_k_stack_alloc_init()
 */
ZTEST(stack_unit, test_obj_core_alloc_init_links_stack)
{
	struct k_stack stack;

	set_heap(N_ENTRIES);

	zassert_equal(z_impl_k_stack_alloc_init(&stack, N_ENTRIES), 0);

	zassert_equal(k_obj_core_init_and_link_fake.call_count, 1);
	zassert_equal_ptr(k_obj_core_init_and_link_fake.arg0_val, K_OBJ_CORE(&stack));
	zassert_called_before(z_thread_malloc, k_obj_core_init_and_link);
}

/**
 * @brief With CONFIG_OBJ_CORE_STACK, k_stack_cleanup() does not unlink the stack.
 *
 * @details
 * - Setup: a stack from k_stack_alloc_init().
 * - Action: k_stack_cleanup().
 * - Expected: no call of k_obj_core_unlink().
 *
 * @ingroup kernel_unit_stack_k_stack_cleanup
 * @see k_stack_cleanup()
 */
ZTEST(stack_unit, test_obj_core_cleanup_does_not_unlink)
{
	struct k_stack stack;

	set_heap(N_ENTRIES);
	zassert_equal(z_impl_k_stack_alloc_init(&stack, N_ENTRIES), 0);

	zassert_equal(k_stack_cleanup(&stack), 0);

	zassert_equal(k_obj_core_unlink_fake.call_count, 0);
}
#endif /* CONFIG_OBJ_CORE_STACK */
