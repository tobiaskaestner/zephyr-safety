/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @defgroup kernel_unit_mem_slab Memory slab unit (kernel/mem_slab.c)
 * @ingroup kernel_unit_tests
 * @brief Design specification of kernel/mem_slab.c, written as unit tests.
 *
 * @par The memory slab object
 * A memory slab (@c struct @c k_mem_slab) gives memory blocks of one fixed
 * size from a buffer of the caller. It has these parts:
 * - @c buffer: the start of the buffer. The buffer holds @c num_blocks
 *   blocks of @c block_size bytes, one after the other.
 * - @c free_list: the list of the free blocks. The list is inside the
 *   buffer: the first word of each free block is the pointer to the next
 *   free block. NULL ends the list.
 * - @c info: the block size, the number of blocks, the number of used
 *   blocks, and, with @kconfig{CONFIG_MEM_SLAB_TRACE_MAX_UTILIZATION}, the
 *   maximum number of used blocks.
 * - @c lock: the spinlock of the slab. Each slab has its own lock.
 * - @c wait_q: the wait queue of the threads that wait for a block.
 * - @c obj_core: with @kconfig{CONFIG_OBJ_CORE_MEM_SLAB}, the object core of
 *   the slab.
 *
 * @par Free list
 * create_free_list() builds the free list. It first checks the block size
 * and the buffer: the block size is not 0, the block size and the buffer
 * address are multiples of the word size, and the end address of the
 * buffer does not overflow. Then it links all blocks in address order. The
 * head of the list is the first block of the buffer. Only the first word of
 * each block changes. k_mem_slab_alloc() removes the head of the list.
 * k_mem_slab_free() puts the block at the head of the list. Thus the next
 * allocation gets the block that was freed last.
 *
 * @par Hand-over to a waiting thread
 * A thread waits in k_mem_slab_alloc() only if the free list is empty.
 * k_mem_slab_free() with an empty free list first tries z_sched_wake() with
 * the block. If a thread waits, the scheduler gives the block to this
 * thread (as @c swap_data, with the return value 0), and the block does not
 * go into the free list. The number of used blocks does not change: the
 * block goes from one user to the next. k_mem_slab_alloc() of the woken
 * thread then returns @c _current->base.swap_data.
 *
 * @par Pointer check
 * With @kconfig{CONFIG_MEM_SLAB_POINTER_VALIDATE} (default with
 * @kconfig{CONFIG_ASSERT}), slab_ptr_is_good() checks that an address is
 * the start of a block in the buffer. k_mem_slab_free() calls k_panic() for
 * an address that is not valid. k_mem_slab_alloc() asserts that the new
 * head of the free list is valid. The check does not find a block that is
 * free already.
 *
 * @par Statistics
 * k_mem_slab_runtime_stats_get() gives the used, free and maximum bytes.
 * With @kconfig{CONFIG_MEM_SLAB_TRACE_MAX_UTILIZATION}, k_mem_slab_alloc()
 * updates the maximum, and k_mem_slab_runtime_stats_reset_max() sets it to
 * the current number of used blocks. With
 * @kconfig{CONFIG_OBJ_CORE_STATS_MEM_SLAB}, the object core framework reads
 * the same data with the static functions k_mem_slab_stats_raw(),
 * k_mem_slab_stats_query() and k_mem_slab_stats_reset().
 *
 * @par Boot-time initialization
 * K_MEM_SLAB_DEFINE() puts a slab into the iterable section @c k_mem_slab.
 * The static initializer sets the wait queue and the block data, but not
 * the free list. K_KERNEL_INIT_PRE() registers init_mem_slab_module() for
 * the boot. This function builds the free list of each slab in the section
 * and initializes its kernel object. It stops at the first slab that is
 * not valid. The object core of the static slabs is the work of the
 * object core descriptor (K_OBJ_TYPE_DEFINE()), not of this function.
 *
 * @par Locks
 * k_mem_slab_alloc(), k_mem_slab_free(), the statistics functions and the
 * object core statistics functions lock the spinlock of the slab before
 * they read or change the free list or the counts. k_spin_lock() locks the
 * interrupts with arch_irq_lock() and returns a key. Each path releases the
 * lock exactly once, with the same key, as its last call to the layers
 * below:
 * - k_spin_unlock(), if no thread became ready.
 * - z_reschedule(), if k_mem_slab_free() gave the block to a waiting
 *   thread.
 * - z_pend_curr(), if k_mem_slab_alloc() must wait. z_pend_curr() adds the
 *   current thread to the wait queue, releases the lock and switches
 *   threads in one step.
 *
 * k_mem_slab_init() and init_mem_slab_module() do not lock the slab. The
 * pointer check of k_mem_slab_free() and the argument checks of the
 * statistics functions occur before the lock.
 *
 * @par Interfaces below mem_slab.c
 * - Scheduler (@c ksched.h): z_sched_wake(), z_reschedule(),
 *   z_pend_curr(), and @c _current (the data of @c kernel/init.c).
 * - Wait queue (@c wait_q.h): z_waitq_init().
 * - Fatal error (@c kernel/fatal.c): z_fatal_error(), through k_panic().
 * - Object core (@c kernel/obj_core.c): k_obj_core_init_and_link(),
 *   k_obj_core_stats_register(), and the descriptor of
 *   K_OBJ_TYPE_DEFINE() or K_OBJ_TYPE_DEFINE_STATS().
 * - Kernel objects: k_object_init().
 * - Boot (@c kernel_internal.h): K_KERNEL_INIT_PRE().
 * - Architecture: arch_irq_lock() and arch_irq_unlock() through
 *   k_spin_lock() and k_spin_unlock().
 * - Overflow checks (@c zephyr/sys/math_extras.h): size_mul_overflow() and
 *   size_add_overflow(). These are static inline. They are not fakes.
 *
 * @par Kconfig options that change mem_slab.c
 * - @kconfig{CONFIG_MEM_SLAB_POINTER_VALIDATE}: the address check of
 *   slab_ptr_is_good().
 * - @kconfig{CONFIG_MEM_SLAB_TRACE_MAX_UTILIZATION}: the maximum number of
 *   used blocks.
 * - @kconfig{CONFIG_OBJ_CORE_MEM_SLAB}: the object type of the slabs and
 *   the object core link in k_mem_slab_init().
 * - @kconfig{CONFIG_OBJ_CORE_STATS_MEM_SLAB}: the statistics descriptor and
 *   the statistics registration in k_mem_slab_init().
 * - @kconfig{CONFIG_MULTITHREADING}: without it, k_mem_slab_alloc() does
 *   not wait and k_mem_slab_free() does not wake a thread.
 * - The CHECKIF() options for the checks of create_free_list():
 *   @kconfig{CONFIG_RUNTIME_ERROR_CHECKS} (default) returns -EINVAL,
 *   @kconfig{CONFIG_NO_RUNTIME_CHECKS} does no check,
 *   @kconfig{CONFIG_ASSERT_ON_ERRORS} asserts. The overflow checks are
 *   plain @c if statements and apply in all configurations.
 * - @kconfig{CONFIG_ASSERT}: the free list check in k_mem_slab_alloc(), the
 *   assertion before k_panic() in k_mem_slab_free(), and the argument checks
 *   of the object core statistics functions.
 *
 * @par Test method
 * The tests call the functions of mem_slab.c directly, also the static
 * functions. All calls below mem_slab.c go to FFF fakes. The fake
 * unit_arch_irq_lock() returns KERNEL_UNIT_IRQ_KEY. Thus a test can follow
 * the key to the call that releases the lock. The FFF call history gives
 * the order of the calls. A test models waiting threads with the fake
 * z_sched_wake(), and the result of a wait with the fake z_pend_curr(),
 * which sets @c _current->base.swap_data. The fake z_fatal_error() returns,
 * so a test sees the code after k_panic(). The scenarios in
 * @c testcase.yaml build the tests once for each Kconfig option above. A
 * test that applies only to some configurations is in an @c \#ifdef block,
 * or it calls ztest_test_skip().
 */

#include <string.h>
#include <zephyr/ztest.h>
#include <kernel_unit.h>
#include <kernel_unit_models.h>
#include <fakes/fatal.h>
#ifdef CONFIG_OBJ_CORE
#include <fakes/obj_core.h>
#endif
#ifdef CONFIG_OBJ_CORE_STATS
#include <fakes/obj_core_stats.h>
#endif
#ifdef CONFIG_USERSPACE
#include <fakes/kobject.h>
#endif
#ifdef CONFIG_ASSERT
#include <fakes/assert.h>
#endif

/*
 * mem_slab.c uses size_mul_overflow() and size_add_overflow() but does not
 * include zephyr/sys/math_extras.h. In a kernel build, the header comes
 * through ksched.h and priority_q.h. The shadow ksched.h does not include
 * it, so the test includes it.
 */
#include <zephyr/sys/math_extras.h>

#include <kernel/mem_slab.c>

/* Value that fills a buffer before a test, to show what the unit writes. */
#define FILL KERNEL_UNIT_FILL

/* Timeout that is not K_NO_WAIT and not K_FOREVER */
#define TEST_TIMEOUT K_TICKS(10)

/* Block size and number of blocks of the slab of a test */
#define BLOCK_SIZE 16U
#define N_BLOCKS   4U

/* A block size that is a power of 2 and that overflows the buffer size with 2 blocks */
#define HUGE_BLOCK_SIZE ((SIZE_MAX / 2U) + 1U)

/* The highest word-aligned address: a buffer at this address overflows its end address. */
#define TOP_ADDRESS ((void *)(UINTPTR_MAX & ~(uintptr_t)(sizeof(void *) - 1U)))

/* The buffer of the slab of a test */
static char slab_buf[N_BLOCKS * BLOCK_SIZE] __aligned(8);

/* A block of memory outside of the slab buffer */
static char foreign_block[BLOCK_SIZE] __aligned(8);

/* Address of block i of slab_buf */
#define BLOCK(i) ((void *)&slab_buf[(i) * BLOCK_SIZE])

/* The current thread of the test, for k_mem_slab_alloc() after a wait. */
static struct k_thread current_thread;

/*
 * Static slabs for the boot-time initialization. The linker sorts the
 * section k_mem_slab by name: a, b, c_bad, d_after. unit_slab_c_bad is not
 * valid (the buffer size overflows), so init_mem_slab_module() stops there.
 * K_MEM_SLAB_DEFINE() rejects such a slab at build time, so the test uses
 * the initializer directly.
 */
K_MEM_SLAB_DEFINE(unit_slab_a, BLOCK_SIZE, N_BLOCKS, 8);
K_MEM_SLAB_DEFINE(unit_slab_b, 12, 3, 4);
static char unit_bad_buf[BLOCK_SIZE] __aligned(8);
STRUCT_SECTION_ITERABLE(k_mem_slab, unit_slab_c_bad) = Z_MEM_SLAB_INITIALIZER(unit_slab_c_bad,
									      unit_bad_buf,
									      HUGE_BLOCK_SIZE, 2);
K_MEM_SLAB_DEFINE(unit_slab_d_after, BLOCK_SIZE, 2, 8);

/* Return the number of blocks in the free list, at most 2 * N_BLOCKS (for a loop). */
static size_t free_list_len(const struct k_mem_slab *slab)
{
	size_t n = 0;

	for (char *p = slab->free_list; (p != NULL) && (n < (2U * N_BLOCKS)); p = *(char **)p) {
		n++;
	}

	return n;
}

/* Assert that the free list has exactly these blocks in this order. */
static void assert_free_list(const struct k_mem_slab *slab, void *const *expected,
			     size_t n_expected)
{
	size_t n = 0;

	for (char *p = slab->free_list; p != NULL; p = *(char **)p) {
		zassert_true(n < n_expected, "the free list has more than %zu blocks", n_expected);
		zassert_equal_ptr(p, expected[n], "block %zu of the free list is not as expected",
				  n);
		n++;
	}
	zassert_equal(n, n_expected, "the free list has %zu blocks, not %zu", n, n_expected);
}

#define zassert_free_list(slab, ...)                                                               \
	do {                                                                                       \
		void *const expected_[] = {__VA_ARGS__};                                           \
		assert_free_list(slab, expected_, ARRAY_SIZE(expected_));                          \
	} while (false)

/* Assert that bytes [from, to) of a block have the fill pattern. */
static void assert_filled(const void *block, size_t from, size_t to)
{
	kernel_unit_assert_filled((const uint8_t *)block + from, to - from);
}

/*
 * The slab that the spy fakes read. A spy fake records the number of free
 * blocks and of used blocks at the time of its call. Thus a test sees the
 * order of the changes and the calls to the layers below.
 */
struct slab_state {
	size_t free_blocks;
	uint32_t num_used;
};

static struct k_mem_slab *spied_slab;
static struct slab_state at_lock;
static struct slab_state at_release;

static struct slab_state slab_state(void)
{
	return (struct slab_state){free_list_len(spied_slab), spied_slab->info.num_used};
}

/* Observers of the lock spies (kernel_unit_spy_on_lock()). */
static void observe_lock(void)
{
	at_lock = slab_state();
}

static void observe_release(void)
{
	at_release = slab_state();
}

/* Install the spy fakes of the lock and of the release paths. */
static void spy_on_lock(struct k_mem_slab *slab)
{
	spied_slab = slab;
	at_lock = (struct slab_state){SIZE_MAX, UINT32_MAX};
	at_release = (struct slab_state){SIZE_MAX, UINT32_MAX};
	kernel_unit_spy_on_lock(observe_lock, observe_release);
}

/* Assert the lock invariant of one operation on the slab (kernel_unit_models.h). */
static void assert_lock_released_once(struct k_mem_slab *slab, enum kernel_unit_release how)
{
	kernel_unit_assert_lock_released_once(&slab->lock, how);
}

/* Forget the calls of the test setup. */
static void reset_history(void)
{
	FFF_RESET_HISTORY();
	RESET_FAKE(unit_arch_irq_lock);
	RESET_FAKE(unit_arch_irq_unlock);
	RESET_FAKE(z_reschedule);
	RESET_FAKE(z_waitq_init);
#ifdef CONFIG_OBJ_CORE
	RESET_FAKE(k_obj_core_init_and_link);
#endif
#ifdef CONFIG_OBJ_CORE_STATS
	RESET_FAKE(k_obj_core_stats_register);
#endif
#ifdef CONFIG_USERSPACE
	RESET_FAKE(k_object_init);
#endif
	unit_arch_irq_lock_fake.return_val = KERNEL_UNIT_IRQ_KEY;
}

/* Initialize a slab with N_BLOCKS blocks of BLOCK_SIZE bytes in slab_buf. */
static void slab_prepare(struct k_mem_slab *slab)
{
	memset(slab, 0, sizeof(*slab));
	zassert_equal(k_mem_slab_init(slab, slab_buf, BLOCK_SIZE, N_BLOCKS), 0);
	reset_history();
}

/*
 * Allocate one block without a wait. Without CONFIG_MULTITHREADING, a
 * zassert returns from the function, so this function, which returns a
 * value, uses ztest_test_fail().
 */
static void *alloc_block(struct k_mem_slab *slab)
{
	void *mem = NULL;

	if (k_mem_slab_alloc(slab, &mem, K_NO_WAIT) != 0) {
		TC_PRINT("k_mem_slab_alloc() failed in the test setup\n");
		ztest_test_fail();
	}

	return mem;
}

/* Allocate all blocks of the slab of slab_prepare(). */
static void alloc_all_blocks(struct k_mem_slab *slab)
{
	for (unsigned int i = 0; i < N_BLOCKS; i++) {
		zassert_equal_ptr(alloc_block(slab), BLOCK(i));
	}
}

static void mem_slab_unit_before(void *fixture)
{
	ARG_UNUSED(fixture);

	/* The fake rules reset all fakes and _kernel before this function. */
	unit_arch_irq_lock_fake.return_val = KERNEL_UNIT_IRQ_KEY;

	memset(slab_buf, FILL, sizeof(slab_buf));
	memset(foreign_block, FILL, sizeof(foreign_block));
	kernel_unit_waiting_threads = 0;
	spied_slab = NULL;
	memset(&current_thread, 0, sizeof(current_thread));
	_kernel.cpus[0].current = &current_thread;

	STRUCT_SECTION_FOREACH(k_mem_slab, slab) {
		slab->free_list = NULL;
	}
	unit_slab_c_bad.info.block_size = HUGE_BLOCK_SIZE;
	unit_slab_c_bad.info.num_blocks = 2;
}

ZTEST_SUITE(mem_slab_unit, NULL, NULL, mem_slab_unit_before, NULL, NULL);

/**
 * @defgroup kernel_unit_mem_slab_init Initialization
 * @ingroup kernel_unit_mem_slab
 * @brief k_mem_slab_init() checks the block size and the buffer, builds the free list and
 * initializes the other parts.
 *
 * k_mem_slab_init() first writes the block data, the buffer, the count 0
 * and the initial lock. Then create_free_list() checks the data and links
 * the blocks. Only if the check passes, k_mem_slab_init() links the object
 * core, registers the statistics, and initializes the wait queue and the
 * kernel object. It does not lock the slab: until k_mem_slab_init()
 * returns, only the caller uses the slab.
 */

/**
 * @brief k_mem_slab_init() sets the buffer, the block size, the number of blocks and the count 0,
 * and returns 0.
 *
 * @details
 * - Setup: a slab filled with a pattern.
 * - Action: k_mem_slab_init() with 4 blocks of 16 bytes.
 * - Expected: return value 0. The buffer, the block size and the number of
 *   blocks are the arguments. The number of used blocks is 0.
 *
 * @ingroup kernel_unit_mem_slab_init
 * @see k_mem_slab_init()
 */
ZTEST(mem_slab_unit, test_init_sets_slab_data)
{
	struct k_mem_slab slab;

	memset(&slab, FILL, sizeof(slab));

	zassert_equal(k_mem_slab_init(&slab, slab_buf, BLOCK_SIZE, N_BLOCKS), 0);

	zassert_equal_ptr(slab.buffer, slab_buf);
	zassert_equal(slab.info.block_size, BLOCK_SIZE);
	zassert_equal(slab.info.num_blocks, N_BLOCKS);
	zassert_equal(slab.info.num_used, 0U);
	zassert_equal(k_mem_slab_num_used_get(&slab), 0U);
	zassert_equal(k_mem_slab_num_free_get(&slab), N_BLOCKS);
}

/**
 * @brief k_mem_slab_init() links all blocks into the free list in address order, with the first
 * block of the buffer at the head.
 *
 * @details
 * - Action: k_mem_slab_init() with 4 blocks of 16 bytes.
 * - Expected: the free list is block 0, 1, 2, 3. The first word of each
 *   block points to the next block, and the first word of block 3 is
 *   NULL.
 *
 * @ingroup kernel_unit_mem_slab_init
 * @see k_mem_slab_init(), create_free_list()
 */
ZTEST(mem_slab_unit, test_init_links_blocks_in_address_order)
{
	struct k_mem_slab slab;

	zassert_equal(k_mem_slab_init(&slab, slab_buf, BLOCK_SIZE, N_BLOCKS), 0);

	zassert_free_list(&slab, BLOCK(0), BLOCK(1), BLOCK(2), BLOCK(3));
	zassert_equal_ptr(*(char **)BLOCK(0), BLOCK(1));
	zassert_is_null(*(char **)BLOCK(3));
}

/**
 * @brief k_mem_slab_init() writes only the first word of each block.
 *
 * @details
 * - Setup: the buffer is filled with a pattern.
 * - Action: k_mem_slab_init() with 4 blocks of 16 bytes.
 * - Expected: in each block, the bytes after the first word keep the
 *   pattern.
 *
 * @ingroup kernel_unit_mem_slab_init
 * @see create_free_list()
 */
ZTEST(mem_slab_unit, test_init_writes_only_first_word)
{
	struct k_mem_slab slab;

	zassert_equal(k_mem_slab_init(&slab, slab_buf, BLOCK_SIZE, N_BLOCKS), 0);

	for (unsigned int i = 0; i < N_BLOCKS; i++) {
		assert_filled(BLOCK(i), sizeof(void *), BLOCK_SIZE);
	}
}

/**
 * @brief k_mem_slab_init() sets the lock of the slab to its initial value.
 *
 * @details
 * - Setup: a slab filled with a pattern.
 * - Action: k_mem_slab_init().
 * - Expected: all bytes of the lock are 0 (the value of an unlocked
 *   spinlock).
 *
 * @ingroup kernel_unit_mem_slab_init
 * @see k_mem_slab_init()
 */
ZTEST(mem_slab_unit, test_init_resets_lock)
{
	struct k_mem_slab slab;
	const struct k_spinlock unlocked = {};

	memset(&slab, FILL, sizeof(slab));

	zassert_equal(k_mem_slab_init(&slab, slab_buf, BLOCK_SIZE, N_BLOCKS), 0);

	zassert_mem_equal(&slab.lock, &unlocked, sizeof(unlocked));
}

/**
 * @brief k_mem_slab_init() initializes the wait queue of the slab.
 *
 * @details
 * - Action: k_mem_slab_init().
 * - Expected: one call of z_waitq_init() with the wait queue of the slab.
 *
 * @ingroup kernel_unit_mem_slab_init
 * @see k_mem_slab_init()
 */
ZTEST(mem_slab_unit, test_init_initializes_wait_queue)
{
	struct k_mem_slab slab;

	zassert_equal(k_mem_slab_init(&slab, slab_buf, BLOCK_SIZE, N_BLOCKS), 0);

	zassert_equal(z_waitq_init_fake.call_count, 1);
	zassert_equal_ptr(z_waitq_init_fake.arg0_val, &slab.wait_q);
}

#ifdef CONFIG_USERSPACE
/**
 * @brief With CONFIG_USERSPACE, k_mem_slab_init() marks the slab as an initialized kernel object.
 *
 * @details
 * - Action: k_mem_slab_init().
 * - Expected: one call of k_object_init() with the slab.
 *
 * @ingroup kernel_unit_mem_slab_init
 * @see k_mem_slab_init()
 */
ZTEST(mem_slab_unit, test_init_initializes_kernel_object)
{
	struct k_mem_slab slab;

	zassert_equal(k_mem_slab_init(&slab, slab_buf, BLOCK_SIZE, N_BLOCKS), 0);

	zassert_equal(k_object_init_fake.call_count, 1);
	zassert_equal_ptr(k_object_init_fake.arg0_val, &slab);
}
#endif /* CONFIG_USERSPACE */

/**
 * @brief k_mem_slab_init() links the object core, registers the statistics, initializes the wait
 * queue and then the kernel object, and calls nothing else.
 *
 * @details
 * - Action: k_mem_slab_init().
 * - Expected calls, in this order: k_obj_core_init_and_link() (with
 *   CONFIG_OBJ_CORE_MEM_SLAB), k_obj_core_stats_register() (with
 *   CONFIG_OBJ_CORE_STATS_MEM_SLAB), z_waitq_init(), k_object_init() (with
 *   CONFIG_USERSPACE). No lock.
 *
 * @ingroup kernel_unit_mem_slab_init
 * @see k_mem_slab_init()
 */
ZTEST(mem_slab_unit, test_init_call_order)
{
	struct k_mem_slab slab;

	zassert_equal(k_mem_slab_init(&slab, slab_buf, BLOCK_SIZE, N_BLOCKS), 0);

	zassert_call_history(
		KERNEL_UNIT_IF_ENABLED(CONFIG_OBJ_CORE_MEM_SLAB, k_obj_core_init_and_link),
		KERNEL_UNIT_IF_ENABLED(CONFIG_OBJ_CORE_STATS_MEM_SLAB, k_obj_core_stats_register),
		z_waitq_init, KERNEL_UNIT_IF_ENABLED(CONFIG_USERSPACE, k_object_init));
}

/**
 * @brief k_mem_slab_init() with 0 blocks gives an empty free list and returns 0.
 *
 * @details
 * - Action: k_mem_slab_init() with 0 blocks of 16 bytes.
 * - Expected: return value 0. The free list is empty. The buffer does not
 *   change. k_mem_slab_alloc() with K_NO_WAIT returns -ENOMEM.
 *
 * @ingroup kernel_unit_mem_slab_init
 * @see k_mem_slab_init(), create_free_list()
 */
ZTEST(mem_slab_unit, test_init_zero_blocks_gives_empty_free_list)
{
	struct k_mem_slab slab;
	void *mem;

	zassert_equal(k_mem_slab_init(&slab, slab_buf, BLOCK_SIZE, 0), 0);

	zassert_is_null(slab.free_list);
	assert_filled(slab_buf, 0, sizeof(slab_buf));
	zassert_equal(k_mem_slab_alloc(&slab, &mem, K_NO_WAIT), -ENOMEM);
}

/**
 * @brief k_mem_slab_init() returns -EINVAL if the block size is 0.
 *
 * @details
 * Applies with CONFIG_RUNTIME_ERROR_CHECKS (the default CHECKIF() option).
 * - Action: k_mem_slab_init() with the block size 0.
 * - Expected: return value -EINVAL. The buffer does not change. No call of
 *   z_waitq_init().
 *
 * @ingroup kernel_unit_mem_slab_init
 * @see k_mem_slab_init(), create_free_list()
 */
ZTEST(mem_slab_unit, test_init_rejects_zero_block_size)
{
	struct k_mem_slab slab;

	if (!IS_ENABLED(CONFIG_RUNTIME_ERROR_CHECKS)) {
		ztest_test_skip();
	}

	zassert_equal(k_mem_slab_init(&slab, slab_buf, 0, N_BLOCKS), -EINVAL);

	assert_filled(slab_buf, 0, sizeof(slab_buf));
	zassert_equal(z_waitq_init_fake.call_count, 0);
}

/**
 * @brief k_mem_slab_init() returns -EINVAL if the block size is not a multiple of the word size.
 *
 * @details
 * Applies with CONFIG_RUNTIME_ERROR_CHECKS.
 * - Action: k_mem_slab_init() with the block size 17.
 * - Expected: return value -EINVAL. The buffer does not change.
 *
 * @ingroup kernel_unit_mem_slab_init
 * @see k_mem_slab_init(), create_free_list()
 */
ZTEST(mem_slab_unit, test_init_rejects_unaligned_block_size)
{
	struct k_mem_slab slab;

	if (!IS_ENABLED(CONFIG_RUNTIME_ERROR_CHECKS)) {
		ztest_test_skip();
	}

	zassert_equal(k_mem_slab_init(&slab, slab_buf, BLOCK_SIZE + 1U, 2), -EINVAL);

	assert_filled(slab_buf, 0, sizeof(slab_buf));
}

/**
 * @brief k_mem_slab_init() returns -EINVAL if the buffer address is not a multiple of the word
 * size.
 *
 * @details
 * Applies with CONFIG_RUNTIME_ERROR_CHECKS.
 * - Action: k_mem_slab_init() with the buffer at slab_buf + 1.
 * - Expected: return value -EINVAL. The buffer does not change.
 *
 * @ingroup kernel_unit_mem_slab_init
 * @see k_mem_slab_init(), create_free_list()
 */
ZTEST(mem_slab_unit, test_init_rejects_unaligned_buffer)
{
	struct k_mem_slab slab;

	if (!IS_ENABLED(CONFIG_RUNTIME_ERROR_CHECKS)) {
		ztest_test_skip();
	}

	zassert_equal(k_mem_slab_init(&slab, &slab_buf[1], BLOCK_SIZE, 2), -EINVAL);

	assert_filled(slab_buf, 0, sizeof(slab_buf));
}

/**
 * @brief k_mem_slab_init() returns -EINVAL if the size of the buffer (block size times number of
 * blocks) overflows, in all configurations.
 *
 * @details
 * The check is a plain @c if, not CHECKIF().
 * - Action: k_mem_slab_init() with 2 blocks of SIZE_MAX / 2 + 1 bytes.
 * - Expected: return value -EINVAL. The buffer does not change. No call of
 *   z_waitq_init().
 *
 * @ingroup kernel_unit_mem_slab_init
 * @see k_mem_slab_init(), create_free_list()
 */
ZTEST(mem_slab_unit, test_init_rejects_size_overflow)
{
	struct k_mem_slab slab;

	zassert_equal(k_mem_slab_init(&slab, slab_buf, HUGE_BLOCK_SIZE, 2), -EINVAL);

	assert_filled(slab_buf, 0, sizeof(slab_buf));
	zassert_equal(z_waitq_init_fake.call_count, 0);
}

/**
 * @brief k_mem_slab_init() returns -EINVAL if the end address of the buffer overflows, in all
 * configurations.
 *
 * @details
 * The check is a plain @c if, not CHECKIF(). The buffer is not written, so
 * the test can give an address without memory.
 * - Action: k_mem_slab_init() with 2 blocks of 16 bytes at the highest
 *   word-aligned address.
 * - Expected: return value -EINVAL. No call of z_waitq_init().
 *
 * @ingroup kernel_unit_mem_slab_init
 * @see k_mem_slab_init(), create_free_list()
 */
ZTEST(mem_slab_unit, test_init_rejects_address_overflow)
{
	struct k_mem_slab slab;

	zassert_equal(k_mem_slab_init(&slab, TOP_ADDRESS, BLOCK_SIZE, 2), -EINVAL);

	zassert_equal(z_waitq_init_fake.call_count, 0);
}

/**
 * @brief If the check fails, k_mem_slab_init() does not link the object core, does not register
 * the statistics, and does not initialize the wait queue and the kernel object.
 *
 * @details
 * - Action: k_mem_slab_init() with a buffer size that overflows.
 * - Expected: return value -EINVAL. No call to the layers below.
 *
 * @ingroup kernel_unit_mem_slab_init
 * @see k_mem_slab_init()
 */
ZTEST(mem_slab_unit, test_init_error_calls_nothing)
{
	struct k_mem_slab slab;

	zassert_equal(k_mem_slab_init(&slab, slab_buf, HUGE_BLOCK_SIZE, 2), -EINVAL);

	zassert_equal(kernel_unit_history_len(), 0);
}

/**
 * @brief If the check fails, k_mem_slab_init() keeps the new block data but does not change the
 * free list.
 *
 * @details
 * k_mem_slab_init() writes the block data before the check. The free list
 * keeps the value from before the call.
 * - Setup: a slab with the free list at block 2 of slab_buf.
 * - Action: k_mem_slab_init() with a buffer size that overflows.
 * - Expected: return value -EINVAL. The block size, the number of blocks,
 *   the buffer and the count 0 are set. The free list is still block 2.
 *
 * @ingroup kernel_unit_mem_slab_init
 * @see k_mem_slab_init()
 */
ZTEST(mem_slab_unit, test_init_error_keeps_old_free_list)
{
	struct k_mem_slab slab;

	memset(&slab, 0, sizeof(slab));
	slab.free_list = BLOCK(2);
	slab.info.num_used = 3;

	zassert_equal(k_mem_slab_init(&slab, unit_bad_buf, HUGE_BLOCK_SIZE, 2), -EINVAL);

	zassert_equal(slab.info.block_size, HUGE_BLOCK_SIZE);
	zassert_equal(slab.info.num_blocks, 2U);
	zassert_equal_ptr(slab.buffer, unit_bad_buf);
	zassert_equal(slab.info.num_used, 0U);
	zassert_equal_ptr(slab.free_list, BLOCK(2));
}

/**
 * @brief With CONFIG_NO_RUNTIME_CHECKS, k_mem_slab_init() accepts the block size 0, and the free
 * list then has one block that points to itself.
 *
 * @details
 * CHECKIF() is empty, so the caller must give valid arguments.
 * - Action: k_mem_slab_init() with 2 blocks of 0 bytes, then three
 *   k_mem_slab_alloc() with K_NO_WAIT.
 * - Expected: k_mem_slab_init() returns 0. Each allocation returns 0 and
 *   the start of the buffer. The number of used blocks is 3, more than the
 *   number of blocks.
 *
 * @ingroup kernel_unit_mem_slab_init
 * @see k_mem_slab_init(), create_free_list()
 */
ZTEST(mem_slab_unit, test_init_no_runtime_checks_accepts_zero_block_size)
{
	struct k_mem_slab slab;

	if (!IS_ENABLED(CONFIG_NO_RUNTIME_CHECKS)) {
		ztest_test_skip();
	}

	zassert_equal(k_mem_slab_init(&slab, slab_buf, 0, 2), 0);

	zassert_equal_ptr(slab.free_list, slab_buf);
	zassert_equal_ptr(*(char **)slab_buf, slab_buf);
	for (unsigned int i = 0; i < 3U; i++) {
		zassert_equal_ptr(alloc_block(&slab), slab_buf);
	}
	zassert_equal(slab.info.num_used, 3U);
}

#ifdef CONFIG_ASSERT_ON_ERRORS
/**
 * @brief With CONFIG_ASSERT_ON_ERRORS, k_mem_slab_init() asserts that the block size is not 0 and
 * that the block size and the buffer address are multiples of the word size.
 *
 * @details
 * - Action: k_mem_slab_init() with the block size 0, then with the block
 *   size 17, then with the buffer at slab_buf + 1, then with valid
 *   arguments. The first three calls have 0 blocks, so that the unit
 *   writes nothing after the assertion.
 * - Expected: one failed assertion for each of the first three calls. No
 *   failed assertion for the fourth call. The fake assertion hook returns,
 *   so each call continues and returns 0.
 *
 * @ingroup kernel_unit_mem_slab_init
 * @see k_mem_slab_init(), create_free_list()
 */
ZTEST(mem_slab_unit, test_init_assert_on_errors)
{
	struct k_mem_slab slab;

	zassert_equal(k_mem_slab_init(&slab, slab_buf, 0, 0), 0);
	zassert_equal(assert_post_action_fake.call_count, 1);

	zassert_equal(k_mem_slab_init(&slab, slab_buf, BLOCK_SIZE + 1U, 0), 0);
	zassert_equal(assert_post_action_fake.call_count, 2);

	zassert_equal(k_mem_slab_init(&slab, &slab_buf[1], BLOCK_SIZE, 0), 0);
	zassert_equal(assert_post_action_fake.call_count, 3);

	zassert_equal(k_mem_slab_init(&slab, slab_buf, BLOCK_SIZE, N_BLOCKS), 0);
	zassert_equal(assert_post_action_fake.call_count, 3);
}
#endif /* CONFIG_ASSERT_ON_ERRORS */

/**
 * @defgroup kernel_unit_mem_slab_boot Boot-time initialization
 * @ingroup kernel_unit_mem_slab
 * @brief init_mem_slab_module() builds the free list of each slab of K_MEM_SLAB_DEFINE() at boot.
 *
 * The static initializer of K_MEM_SLAB_DEFINE() sets the buffer, the block
 * data and the wait queue, and leaves the free list NULL. The boot runs
 * init_mem_slab_module() in the PRE_KERNEL phase, through the entry of
 * K_KERNEL_INIT_PRE(). The function walks the section @c k_mem_slab in
 * order. For each slab, it builds the free list and initializes the kernel
 * object. It stops at the first slab that is not valid. The function
 * returns nothing, so the boot does not see the error.
 *
 * The test defines four static slabs: a and b are valid, c_bad has a buffer
 * size that overflows, d_after is valid and comes after c_bad.
 */

/**
 * @brief mem_slab.c registers init_mem_slab_module() as a kernel init function of the PRE_KERNEL
 * phase.
 *
 * @details
 * - Action: read the entry of K_KERNEL_INIT_PRE() in mem_slab.c.
 * - Expected: the init function of the entry is init_mem_slab_module().
 *
 * @ingroup kernel_unit_mem_slab_boot
 * @see init_mem_slab_module()
 */
ZTEST(mem_slab_unit, test_boot_registers_pre_kernel_init)
{
	zassert_equal_ptr(_kernel_init_pre_init_mem_slab_module.init_fn, init_mem_slab_module);
}

/**
 * @brief init_mem_slab_module() builds the free list of each valid static slab before the first
 * slab that is not valid.
 *
 * @details
 * - Setup: the free lists of the static slabs are NULL.
 * - Action: init_mem_slab_module().
 * - Expected: the free list of slab a has 4 blocks, from the start of its
 *   buffer. The free list of slab b has 3 blocks, from the start of its
 *   buffer.
 *
 * @ingroup kernel_unit_mem_slab_boot
 * @see init_mem_slab_module(), create_free_list()
 */
ZTEST(mem_slab_unit, test_boot_builds_free_lists)
{
	init_mem_slab_module();

	zassert_equal_ptr(unit_slab_a.free_list, unit_slab_a.buffer);
	zassert_equal(free_list_len(&unit_slab_a), N_BLOCKS);
	zassert_equal_ptr(unit_slab_b.free_list, unit_slab_b.buffer);
	zassert_equal(free_list_len(&unit_slab_b), 3U);
}

/**
 * @brief init_mem_slab_module() stops at the first slab that is not valid, and the slabs after it
 * keep an empty free list.
 *
 * @details
 * - Setup: the free lists of the static slabs are NULL.
 * - Action: init_mem_slab_module().
 * - Expected: the free lists of slab c_bad and slab d_after are NULL.
 *   k_mem_slab_alloc() on slab d_after with K_NO_WAIT returns -ENOMEM.
 *
 * @ingroup kernel_unit_mem_slab_boot
 * @see init_mem_slab_module()
 */
ZTEST(mem_slab_unit, test_boot_stops_at_invalid_slab)
{
	void *mem;

	init_mem_slab_module();

	zassert_is_null(unit_slab_c_bad.free_list);
	zassert_is_null(unit_slab_d_after.free_list);
	zassert_equal(k_mem_slab_alloc(&unit_slab_d_after, &mem, K_NO_WAIT), -ENOMEM);
}

/**
 * @brief If all static slabs are valid, init_mem_slab_module() builds the free list of each slab
 * in the section, up to the end of the section.
 *
 * @details
 * - Setup: slab c_bad gets a valid block size (16) and 1 block, so all
 *   four static slabs are valid.
 * - Action: init_mem_slab_module().
 * - Expected: the free lists of slab a, b, c_bad and d_after have 4, 3, 1
 *   and 2 blocks.
 *
 * @ingroup kernel_unit_mem_slab_boot
 * @see init_mem_slab_module()
 */
ZTEST(mem_slab_unit, test_boot_walks_whole_section)
{
	unit_slab_c_bad.info.block_size = BLOCK_SIZE;
	unit_slab_c_bad.info.num_blocks = 1;

	init_mem_slab_module();

	zassert_equal(free_list_len(&unit_slab_a), N_BLOCKS);
	zassert_equal(free_list_len(&unit_slab_b), 3U);
	zassert_equal(free_list_len(&unit_slab_c_bad), 1U);
	zassert_equal(free_list_len(&unit_slab_d_after), 2U);
}

/**
 * @brief init_mem_slab_module() initializes only the kernel object of each valid slab, and does
 * not lock, initialize the wait queue or link the object core.
 *
 * @details
 * - Action: init_mem_slab_module().
 * - Expected calls: k_object_init() for slab a and for slab b (with
 *   CONFIG_USERSPACE), and nothing else.
 *
 * @ingroup kernel_unit_mem_slab_boot
 * @see init_mem_slab_module()
 */
ZTEST(mem_slab_unit, test_boot_call_history)
{
	init_mem_slab_module();

	zassert_call_history(KERNEL_UNIT_IF_ENABLED(CONFIG_USERSPACE, k_object_init),
			     KERNEL_UNIT_IF_ENABLED(CONFIG_USERSPACE, k_object_init));
#ifdef CONFIG_USERSPACE
	zassert_equal_ptr(k_object_init_fake.arg0_history[0], &unit_slab_a);
	zassert_equal_ptr(k_object_init_fake.arg0_history[1], &unit_slab_b);
#endif
}

/**
 * @brief K_MEM_SLAB_DEFINE() rounds the block size up to a multiple of the word size, so the
 * boot-time check accepts a block size that is a multiple of a smaller alignment.
 *
 * @details
 * - Setup: slab b has K_MEM_SLAB_DEFINE() with the block size 12 and the
 *   alignment 4.
 * - Action: init_mem_slab_module().
 * - Expected: the block size of slab b is WB_UP(12). Its buffer address is
 *   a multiple of the word size. The free list has 3 blocks.
 *
 * @ingroup kernel_unit_mem_slab_boot
 * @see init_mem_slab_module(), K_MEM_SLAB_DEFINE()
 */
ZTEST(mem_slab_unit, test_boot_static_block_size_is_word_aligned)
{
	init_mem_slab_module();

	zassert_equal(unit_slab_b.info.block_size, WB_UP(12));
	zassert_equal((uintptr_t)unit_slab_b.buffer % sizeof(void *), 0U);
	zassert_equal(free_list_len(&unit_slab_b), 3U);
}

/**
 * @defgroup kernel_unit_mem_slab_alloc Allocation
 * @ingroup kernel_unit_mem_slab
 * @brief k_mem_slab_alloc() takes the head of the free list, or fails, or waits.
 *
 * If the free list is not empty, k_mem_slab_alloc() takes its head and
 * increments the number of used blocks. If the list is empty and the
 * timeout is K_NO_WAIT (or without CONFIG_MULTITHREADING), it writes NULL to
 * @p mem and returns -ENOMEM. Else the current thread waits in
 * z_pend_curr() on the wait queue of the slab. After a wait with the result
 * 0, the block is @c _current->base.swap_data.
 */

/**
 * @brief k_mem_slab_alloc() takes the head of the free list, increments the count and returns 0.
 *
 * @details
 * - Setup: a slab with 4 free blocks.
 * - Action: k_mem_slab_alloc() with K_NO_WAIT.
 * - Expected: return value 0. @p mem is block 0. The free list is block 1,
 *   2, 3. The number of used blocks is 1.
 *
 * @ingroup kernel_unit_mem_slab_alloc
 * @see k_mem_slab_alloc()
 */
ZTEST(mem_slab_unit, test_alloc_takes_head_of_free_list)
{
	struct k_mem_slab slab;
	void *mem = NULL;

	slab_prepare(&slab);

	zassert_equal(k_mem_slab_alloc(&slab, &mem, K_NO_WAIT), 0);

	zassert_equal_ptr(mem, BLOCK(0));
	zassert_free_list(&slab, BLOCK(1), BLOCK(2), BLOCK(3));
	zassert_equal(slab.info.num_used, 1U);
}

/**
 * @brief k_mem_slab_alloc() gives the blocks in address order until the free list is empty.
 *
 * @details
 * - Setup: a slab with 4 free blocks.
 * - Action: k_mem_slab_alloc() with K_NO_WAIT, 4 times.
 * - Expected: the blocks 0, 1, 2, 3. Then the free list is empty and the
 *   number of used blocks is 4. No call of z_pend_curr().
 *
 * @ingroup kernel_unit_mem_slab_alloc
 * @see k_mem_slab_alloc()
 */
ZTEST(mem_slab_unit, test_alloc_gives_blocks_until_empty)
{
	struct k_mem_slab slab;

	slab_prepare(&slab);

	alloc_all_blocks(&slab);

	zassert_is_null(slab.free_list);
	zassert_equal(slab.info.num_used, N_BLOCKS);
	zassert_equal(k_mem_slab_num_free_get(&slab), 0U);
	zassert_equal(z_pend_curr_fake.call_count, 0);
}

/**
 * @brief If a block is free, k_mem_slab_alloc() does not wait, also if the timeout permits a wait.
 *
 * @details
 * - Setup: a slab with 4 free blocks.
 * - Action: k_mem_slab_alloc() with K_FOREVER, then with a timeout of 10
 *   ticks.
 * - Expected: each call returns 0 and the next block. No call of
 *   z_pend_curr().
 *
 * @ingroup kernel_unit_mem_slab_alloc
 * @see k_mem_slab_alloc()
 */
ZTEST(mem_slab_unit, test_alloc_with_free_block_does_not_wait)
{
	struct k_mem_slab slab;
	void *mem = NULL;

	slab_prepare(&slab);

	zassert_equal(k_mem_slab_alloc(&slab, &mem, K_FOREVER), 0);
	zassert_equal_ptr(mem, BLOCK(0));
	zassert_equal(k_mem_slab_alloc(&slab, &mem, TEST_TIMEOUT), 0);
	zassert_equal_ptr(mem, BLOCK(1));

	zassert_equal(z_pend_curr_fake.call_count, 0);
}

/**
 * @brief If the free list is empty and the timeout is K_NO_WAIT, k_mem_slab_alloc() writes NULL to
 * mem and returns -ENOMEM.
 *
 * @details
 * - Setup: a slab with all blocks used.
 * - Action: k_mem_slab_alloc() with K_NO_WAIT.
 * - Expected: return value -ENOMEM. @p mem is NULL. The number of used
 *   blocks is 4. No call of z_pend_curr().
 *
 * @ingroup kernel_unit_mem_slab_alloc
 * @see k_mem_slab_alloc()
 */
ZTEST(mem_slab_unit, test_alloc_empty_no_wait_returns_enomem)
{
	struct k_mem_slab slab;
	void *mem = foreign_block;

	slab_prepare(&slab);
	alloc_all_blocks(&slab);

	zassert_equal(k_mem_slab_alloc(&slab, &mem, K_NO_WAIT), -ENOMEM);

	zassert_is_null(mem);
	zassert_equal(slab.info.num_used, N_BLOCKS);
	zassert_equal(z_pend_curr_fake.call_count, 0);
}

/**
 * @brief If the free list is empty and the timeout is not K_NO_WAIT, k_mem_slab_alloc() waits on
 * the wait queue of the slab with this timeout.
 *
 * @details
 * Applies with CONFIG_MULTITHREADING.
 * - Setup: a slab with all blocks used. The wait gives block 2.
 * - Action: k_mem_slab_alloc() with a timeout of 10 ticks.
 * - Expected: one call of z_pend_curr() with the lock of the slab, the
 *   wait queue of the slab and the timeout.
 *
 * @ingroup kernel_unit_mem_slab_alloc
 * @see k_mem_slab_alloc()
 */
ZTEST(mem_slab_unit, test_alloc_empty_waits_with_timeout)
{
	struct k_mem_slab slab;
	void *mem = NULL;

	if (!IS_ENABLED(CONFIG_MULTITHREADING)) {
		ztest_test_skip();
	}

	slab_prepare(&slab);
	alloc_all_blocks(&slab);
	kernel_unit_set_wait_result(BLOCK(2), 0);

	(void)k_mem_slab_alloc(&slab, &mem, TEST_TIMEOUT);

	zassert_equal(z_pend_curr_fake.call_count, 1);
	zassert_equal_ptr(z_pend_curr_fake.arg0_val, &slab.lock);
	zassert_equal_ptr(z_pend_curr_fake.arg2_val, &slab.wait_q);
	zassert_true(K_TIMEOUT_EQ(z_pend_curr_fake.arg3_val, TEST_TIMEOUT));
}

/**
 * @brief After a wait with the result 0, k_mem_slab_alloc() returns 0 and the block that the
 * scheduler gave to the current thread, and does not change the count.
 *
 * @details
 * Applies with CONFIG_MULTITHREADING.
 * - Setup: a slab with all blocks used. The wait gives block 2 with the
 *   result 0.
 * - Action: k_mem_slab_alloc() with K_FOREVER.
 * - Expected: return value 0. @p mem is block 2. The free list is empty.
 *   The number of used blocks is 4.
 *
 * @ingroup kernel_unit_mem_slab_alloc
 * @see k_mem_slab_alloc()
 */
ZTEST(mem_slab_unit, test_alloc_after_wait_returns_handed_block)
{
	struct k_mem_slab slab;
	void *mem = NULL;

	if (!IS_ENABLED(CONFIG_MULTITHREADING)) {
		ztest_test_skip();
	}

	slab_prepare(&slab);
	alloc_all_blocks(&slab);
	kernel_unit_set_wait_result(BLOCK(2), 0);

	zassert_equal(k_mem_slab_alloc(&slab, &mem, K_FOREVER), 0);

	zassert_equal_ptr(mem, BLOCK(2));
	zassert_is_null(slab.free_list);
	zassert_equal(slab.info.num_used, N_BLOCKS);
}

/**
 * @brief After a wait with a result other than 0, k_mem_slab_alloc() returns this result and does
 * not write mem.
 *
 * @details
 * Applies with CONFIG_MULTITHREADING. On -ENOMEM, k_mem_slab_alloc() writes
 * NULL to @p mem. After a timeout, it does not.
 * - Setup: a slab with all blocks used. @p mem has a marker value. The
 *   wait gives the result -EAGAIN (and a swap_data that is set).
 * - Action: k_mem_slab_alloc() with a timeout of 10 ticks.
 * - Expected: return value -EAGAIN. @p mem still has the marker value.
 *
 * @ingroup kernel_unit_mem_slab_alloc
 * @see k_mem_slab_alloc()
 */
ZTEST(mem_slab_unit, test_alloc_after_timeout_keeps_mem)
{
	struct k_mem_slab slab;
	void *mem = foreign_block;

	if (!IS_ENABLED(CONFIG_MULTITHREADING)) {
		ztest_test_skip();
	}

	slab_prepare(&slab);
	alloc_all_blocks(&slab);
	kernel_unit_set_wait_result(BLOCK(2), -EAGAIN);

	zassert_equal(k_mem_slab_alloc(&slab, &mem, TEST_TIMEOUT), -EAGAIN);

	zassert_equal_ptr(mem, foreign_block);
	zassert_equal(slab.info.num_used, N_BLOCKS);
}

#ifndef CONFIG_MULTITHREADING
/**
 * @brief Without CONFIG_MULTITHREADING, k_mem_slab_alloc() does not wait: an empty free list gives
 * -ENOMEM for each timeout.
 *
 * @details
 * - Setup: a slab with all blocks used.
 * - Action: k_mem_slab_alloc() with K_FOREVER, then with a timeout of 10
 *   ticks.
 * - Expected: each call returns -ENOMEM and writes NULL to @p mem. No call
 *   of z_pend_curr().
 *
 * @ingroup kernel_unit_mem_slab_alloc
 * @see k_mem_slab_alloc()
 */
ZTEST(mem_slab_unit, test_alloc_single_thread_does_not_wait)
{
	struct k_mem_slab slab;
	void *mem = foreign_block;

	slab_prepare(&slab);
	alloc_all_blocks(&slab);

	zassert_equal(k_mem_slab_alloc(&slab, &mem, K_FOREVER), -ENOMEM);
	zassert_is_null(mem);
	mem = foreign_block;
	zassert_equal(k_mem_slab_alloc(&slab, &mem, TEST_TIMEOUT), -ENOMEM);
	zassert_is_null(mem);

	zassert_equal(z_pend_curr_fake.call_count, 0);
}
#endif /* !CONFIG_MULTITHREADING */

#ifdef CONFIG_ASSERT
/**
 * @brief With CONFIG_ASSERT and CONFIG_MEM_SLAB_POINTER_VALIDATE, k_mem_slab_alloc() asserts that
 * the new head of the free list is a valid block.
 *
 * @details
 * - Setup: a slab with 4 free blocks. The first word of block 0 (the link
 *   to the next free block) is slab_buf + 1.
 * - Action: k_mem_slab_alloc() with K_NO_WAIT.
 * - Expected: one failed assertion, before the release of the lock. The
 *   fake assertion hook returns, so the call returns 0 and block 0.
 *
 * @ingroup kernel_unit_mem_slab_alloc
 * @see k_mem_slab_alloc(), slab_ptr_is_good()
 */
ZTEST(mem_slab_unit, test_alloc_asserts_corrupt_free_list)
{
	struct k_mem_slab slab;

	if (!IS_ENABLED(CONFIG_MEM_SLAB_POINTER_VALIDATE)) {
		ztest_test_skip();
	}

	slab_prepare(&slab);
	*(char **)BLOCK(0) = &slab_buf[1];

	zassert_equal_ptr(alloc_block(&slab), BLOCK(0));

	zassert_equal(assert_post_action_fake.call_count, 1);
	zassert_called_before(assert_post_action, unit_arch_irq_unlock);
}

/**
 * @brief With CONFIG_ASSERT and CONFIG_MEM_SLAB_POINTER_VALIDATE, k_mem_slab_alloc() asserts that
 * the free list is empty only when all blocks are used.
 *
 * @details
 * - Setup: a slab with 4 free blocks. The first word of block 0 is NULL,
 *   so the free list ends after block 0.
 * - Action: k_mem_slab_alloc() with K_NO_WAIT.
 * - Expected: one failed assertion: the free list is empty, but only 1 of
 *   4 blocks is used.
 *
 * @ingroup kernel_unit_mem_slab_alloc
 * @see k_mem_slab_alloc(), slab_ptr_is_good()
 */
ZTEST(mem_slab_unit, test_alloc_asserts_count_of_empty_free_list)
{
	struct k_mem_slab slab;

	if (!IS_ENABLED(CONFIG_MEM_SLAB_POINTER_VALIDATE)) {
		ztest_test_skip();
	}

	slab_prepare(&slab);
	*(char **)BLOCK(0) = NULL;

	zassert_equal_ptr(alloc_block(&slab), BLOCK(0));

	zassert_equal(assert_post_action_fake.call_count, 1);
}

/**
 * @brief With CONFIG_ASSERT, k_mem_slab_alloc() of each block of a valid slab, also of the last
 * block, does not fail an assertion.
 *
 * @details
 * - Setup: a slab with 4 free blocks.
 * - Action: k_mem_slab_alloc() with K_NO_WAIT, 4 times.
 * - Expected: no failed assertion.
 *
 * @ingroup kernel_unit_mem_slab_alloc
 * @see k_mem_slab_alloc(), slab_ptr_is_good()
 */
ZTEST(mem_slab_unit, test_alloc_valid_slab_passes_assertion)
{
	struct k_mem_slab slab;

	slab_prepare(&slab);

	alloc_all_blocks(&slab);

	zassert_equal(assert_post_action_fake.call_count, 0);
}
#endif /* CONFIG_ASSERT */

/**
 * @defgroup kernel_unit_mem_slab_free Free
 * @ingroup kernel_unit_mem_slab
 * @brief k_mem_slab_free() gives the block to a waiting thread, or puts it at the head of the free
 * list.
 *
 * k_mem_slab_free() tries a hand-over only if the free list is empty (a
 * thread can wait only then) and with CONFIG_MULTITHREADING. In the
 * hand-over, z_sched_wake() gives the block to the thread as swap data with
 * the return value 0. The free list and the count do not change. Else the
 * first word of the block becomes the link to the old head of the free
 * list, the block becomes the head, and the count decrements.
 */

/**
 * @brief k_mem_slab_free() puts the block at the head of the free list and decrements the count.
 *
 * @details
 * - Setup: a slab with blocks 0 and 1 used.
 * - Action: k_mem_slab_free() of block 0.
 * - Expected: the free list is block 0, 2, 3. The first word of block 0
 *   points to block 2. The number of used blocks is 1.
 *
 * @ingroup kernel_unit_mem_slab_free
 * @see k_mem_slab_free()
 */
ZTEST(mem_slab_unit, test_free_puts_block_at_head)
{
	struct k_mem_slab slab;

	slab_prepare(&slab);
	zassert_equal_ptr(alloc_block(&slab), BLOCK(0));
	zassert_equal_ptr(alloc_block(&slab), BLOCK(1));

	k_mem_slab_free(&slab, BLOCK(0));

	zassert_free_list(&slab, BLOCK(0), BLOCK(2), BLOCK(3));
	zassert_equal_ptr(*(char **)BLOCK(0), BLOCK(2));
	zassert_equal(slab.info.num_used, 1U);
}

/**
 * @brief The next k_mem_slab_alloc() gives the block that k_mem_slab_free() freed last.
 *
 * @details
 * - Setup: a slab with all blocks used.
 * - Action: k_mem_slab_free() of block 1, then of block 3, then
 *   k_mem_slab_alloc() two times.
 * - Expected: the allocations give block 3, then block 1.
 *
 * @ingroup kernel_unit_mem_slab_free
 * @see k_mem_slab_free(), k_mem_slab_alloc()
 */
ZTEST(mem_slab_unit, test_free_last_freed_is_next_allocated)
{
	struct k_mem_slab slab;

	slab_prepare(&slab);
	alloc_all_blocks(&slab);

	k_mem_slab_free(&slab, BLOCK(1));
	k_mem_slab_free(&slab, BLOCK(3));

	zassert_equal_ptr(alloc_block(&slab), BLOCK(3));
	zassert_equal_ptr(alloc_block(&slab), BLOCK(1));
}

/**
 * @brief If a thread waits, k_mem_slab_free() gives the block to this thread with the return value
 * 0, and the free list, the count and the block do not change.
 *
 * @details
 * Applies with CONFIG_MULTITHREADING.
 * - Setup: a slab with all blocks used. One thread waits. Block 2 has the
 *   pattern.
 * - Action: k_mem_slab_free() of block 2.
 * - Expected: one call of z_sched_wake() with the wait queue of the slab,
 *   the return value 0 and block 2. The free list is empty. The number of
 *   used blocks is 4. Block 2 keeps the pattern.
 *
 * @ingroup kernel_unit_mem_slab_free
 * @see k_mem_slab_free()
 */
ZTEST(mem_slab_unit, test_free_hands_block_to_waiting_thread)
{
	struct k_mem_slab slab;

	if (!IS_ENABLED(CONFIG_MULTITHREADING)) {
		ztest_test_skip();
	}

	slab_prepare(&slab);
	alloc_all_blocks(&slab);
	memset(BLOCK(2), FILL, BLOCK_SIZE);
	kernel_unit_set_waiting_threads(1);

	k_mem_slab_free(&slab, BLOCK(2));

	zassert_equal(z_sched_wake_fake.call_count, 1);
	zassert_equal_ptr(z_sched_wake_fake.arg0_val, &slab.wait_q);
	zassert_equal(z_sched_wake_fake.arg1_val, 0);
	zassert_equal_ptr(z_sched_wake_fake.arg2_val, BLOCK(2));
	zassert_is_null(slab.free_list);
	zassert_equal(slab.info.num_used, N_BLOCKS);
	assert_filled(BLOCK(2), 0, BLOCK_SIZE);
}

/**
 * @brief If the free list is empty and no thread waits, k_mem_slab_free() puts the block into the
 * free list.
 *
 * @details
 * Applies with CONFIG_MULTITHREADING.
 * - Setup: a slab with all blocks used. No thread waits.
 * - Action: k_mem_slab_free() of block 1.
 * - Expected: one call of z_sched_wake(), which returns false. The free
 *   list is block 1. The first word of block 1 is NULL. The number of used
 *   blocks is 3.
 *
 * @ingroup kernel_unit_mem_slab_free
 * @see k_mem_slab_free()
 */
ZTEST(mem_slab_unit, test_free_empty_list_without_waiter_puts_block)
{
	struct k_mem_slab slab;

	if (!IS_ENABLED(CONFIG_MULTITHREADING)) {
		ztest_test_skip();
	}

	slab_prepare(&slab);
	alloc_all_blocks(&slab);

	k_mem_slab_free(&slab, BLOCK(1));

	zassert_equal(z_sched_wake_fake.call_count, 1);
	zassert_free_list(&slab, BLOCK(1));
	zassert_is_null(*(char **)BLOCK(1));
	zassert_equal(slab.info.num_used, N_BLOCKS - 1U);
}

/**
 * @brief If the free list is not empty, k_mem_slab_free() does not try to wake a thread.
 *
 * @details
 * - Setup: a slab with block 0 used and 3 free blocks. A thread waits
 *   (this cannot occur with free blocks; it shows that no wake is tried).
 * - Action: k_mem_slab_free() of block 0.
 * - Expected: no call of z_sched_wake(). The free list is block 0, 1, 2,
 *   3.
 *
 * @ingroup kernel_unit_mem_slab_free
 * @see k_mem_slab_free()
 */
ZTEST(mem_slab_unit, test_free_with_free_blocks_does_not_wake)
{
	struct k_mem_slab slab;

	slab_prepare(&slab);
	zassert_equal_ptr(alloc_block(&slab), BLOCK(0));
	kernel_unit_set_waiting_threads(1);

	k_mem_slab_free(&slab, BLOCK(0));

	zassert_equal(z_sched_wake_fake.call_count, 0);
	zassert_free_list(&slab, BLOCK(0), BLOCK(1), BLOCK(2), BLOCK(3));
}

/**
 * @brief A block that k_mem_slab_free() gives to a waiting thread is the block of the
 * k_mem_slab_alloc() of this thread.
 *
 * @details
 * Applies with CONFIG_MULTITHREADING. The test connects the two fakes: the
 * return value and the data of z_sched_wake() become the result of
 * z_pend_curr().
 * - Setup: a slab with all blocks used. One thread waits.
 * - Action: k_mem_slab_free() of block 3. Then the woken thread continues
 *   in k_mem_slab_alloc() with K_FOREVER.
 * - Expected: k_mem_slab_alloc() returns 0 and block 3. The number of used
 *   blocks is 4.
 *
 * @ingroup kernel_unit_mem_slab_free
 * @see k_mem_slab_free(), k_mem_slab_alloc()
 */
ZTEST(mem_slab_unit, test_free_handover_reaches_alloc)
{
	struct k_mem_slab slab;
	void *mem = NULL;

	if (!IS_ENABLED(CONFIG_MULTITHREADING)) {
		ztest_test_skip();
	}

	slab_prepare(&slab);
	alloc_all_blocks(&slab);
	kernel_unit_set_waiting_threads(1);

	k_mem_slab_free(&slab, BLOCK(3));
	kernel_unit_set_wait_result(z_sched_wake_fake.arg2_val, z_sched_wake_fake.arg1_val);

	zassert_equal(k_mem_slab_alloc(&slab, &mem, K_FOREVER), 0);
	zassert_equal_ptr(mem, BLOCK(3));
	zassert_equal(slab.info.num_used, N_BLOCKS);
}

#ifndef CONFIG_MULTITHREADING
/**
 * @brief Without CONFIG_MULTITHREADING, k_mem_slab_free() does not try to wake a thread, also if
 * the free list is empty.
 *
 * @details
 * - Setup: a slab with all blocks used.
 * - Action: k_mem_slab_free() of block 0.
 * - Expected: no call of z_sched_wake(). The free list is block 0. The
 *   number of used blocks is 3.
 *
 * @ingroup kernel_unit_mem_slab_free
 * @see k_mem_slab_free()
 */
ZTEST(mem_slab_unit, test_free_single_thread_does_not_wake)
{
	struct k_mem_slab slab;

	slab_prepare(&slab);
	alloc_all_blocks(&slab);
	kernel_unit_set_waiting_threads(1);

	k_mem_slab_free(&slab, BLOCK(0));

	zassert_equal(z_sched_wake_fake.call_count, 0);
	zassert_free_list(&slab, BLOCK(0));
	zassert_equal(slab.info.num_used, N_BLOCKS - 1U);
}
#endif /* !CONFIG_MULTITHREADING */

/**
 * @defgroup kernel_unit_mem_slab_validate Pointer check
 * @ingroup kernel_unit_mem_slab
 * @brief With CONFIG_MEM_SLAB_POINTER_VALIDATE, k_mem_slab_free() calls k_panic() for an address
 * that is not the start of a block in the buffer.
 *
 * slab_ptr_is_good() accepts an address if its offset from the buffer
 * start is not negative, is less than the buffer size, and is a multiple
 * of the block size. Without CONFIG_MEM_SLAB_POINTER_VALIDATE, it accepts
 * each address. k_mem_slab_free() checks the address before it locks the
 * slab. For an address that is not valid, it fails an assertion (with
 * CONFIG_ASSERT), calls k_panic() and returns. On the unit_testing
 * architecture, k_panic() is z_fatal_error(K_ERR_KERNEL_PANIC, NULL).
 */

/* Assert that the last k_mem_slab_free() called k_panic() and changed nothing. */
static void assert_free_panicked(struct k_mem_slab *slab, size_t free_blocks, uint32_t num_used)
{
	zassert_equal(z_fatal_error_fake.call_count, 1);
	zassert_equal(z_fatal_error_fake.arg0_val, K_ERR_KERNEL_PANIC);
	zassert_is_null(z_fatal_error_fake.arg1_val);
	zassert_equal(unit_arch_irq_lock_fake.call_count, 0);
	zassert_equal(free_list_len(slab), free_blocks);
	zassert_equal(slab->info.num_used, num_used);
}

/**
 * @brief With CONFIG_MEM_SLAB_POINTER_VALIDATE, k_mem_slab_free() calls k_panic() for an address
 * before the buffer, and does not lock or change the slab.
 *
 * @details
 * - Setup: a slab with block 0 used.
 * - Action: k_mem_slab_free() of slab_buf - 16 (one block before the
 *   buffer).
 * - Expected: one call of z_fatal_error() with K_ERR_KERNEL_PANIC and NULL.
 *   No lock. The free list has 3 blocks, and 1 block is used.
 *
 * @ingroup kernel_unit_mem_slab_validate
 * @see k_mem_slab_free(), slab_ptr_is_good()
 */
ZTEST(mem_slab_unit, test_validate_free_before_buffer_panics)
{
	struct k_mem_slab slab;

	if (!IS_ENABLED(CONFIG_MEM_SLAB_POINTER_VALIDATE)) {
		ztest_test_skip();
	}

	slab_prepare(&slab);
	(void)alloc_block(&slab);
	reset_history();

	k_mem_slab_free(&slab, slab_buf - BLOCK_SIZE);

	assert_free_panicked(&slab, N_BLOCKS - 1U, 1U);
}

/**
 * @brief With CONFIG_MEM_SLAB_POINTER_VALIDATE, k_mem_slab_free() calls k_panic() for the address
 * of the buffer end.
 *
 * @details
 * - Setup: a slab with block 0 used.
 * - Action: k_mem_slab_free() of slab_buf + 64 (the end of the buffer).
 * - Expected: one call of z_fatal_error() with K_ERR_KERNEL_PANIC. No lock.
 *   The slab does not change.
 *
 * @ingroup kernel_unit_mem_slab_validate
 * @see k_mem_slab_free(), slab_ptr_is_good()
 */
ZTEST(mem_slab_unit, test_validate_free_at_buffer_end_panics)
{
	struct k_mem_slab slab;

	if (!IS_ENABLED(CONFIG_MEM_SLAB_POINTER_VALIDATE)) {
		ztest_test_skip();
	}

	slab_prepare(&slab);
	(void)alloc_block(&slab);
	reset_history();

	k_mem_slab_free(&slab, BLOCK(N_BLOCKS));

	assert_free_panicked(&slab, N_BLOCKS - 1U, 1U);
}

/**
 * @brief With CONFIG_MEM_SLAB_POINTER_VALIDATE, k_mem_slab_free() calls k_panic() for an address
 * in the buffer that is not the start of a block.
 *
 * @details
 * - Setup: a slab with block 0 used.
 * - Action: k_mem_slab_free() of block 0 + 8.
 * - Expected: one call of z_fatal_error() with K_ERR_KERNEL_PANIC. No lock.
 *   The slab does not change.
 *
 * @ingroup kernel_unit_mem_slab_validate
 * @see k_mem_slab_free(), slab_ptr_is_good()
 */
ZTEST(mem_slab_unit, test_validate_free_inside_block_panics)
{
	struct k_mem_slab slab;

	if (!IS_ENABLED(CONFIG_MEM_SLAB_POINTER_VALIDATE)) {
		ztest_test_skip();
	}

	slab_prepare(&slab);
	(void)alloc_block(&slab);
	reset_history();

	k_mem_slab_free(&slab, &slab_buf[BLOCK_SIZE / 2U]);

	assert_free_panicked(&slab, N_BLOCKS - 1U, 1U);
}

/**
 * @brief With CONFIG_MEM_SLAB_POINTER_VALIDATE, k_mem_slab_free() accepts the start of each block,
 * also of the last block.
 *
 * @details
 * - Setup: a slab with all blocks used.
 * - Action: k_mem_slab_free() of block 3, then of block 0.
 * - Expected: no call of z_fatal_error(). The free list is block 0, 3.
 *
 * @ingroup kernel_unit_mem_slab_validate
 * @see k_mem_slab_free(), slab_ptr_is_good()
 */
ZTEST(mem_slab_unit, test_validate_free_accepts_block_start)
{
	struct k_mem_slab slab;

	slab_prepare(&slab);
	alloc_all_blocks(&slab);

	k_mem_slab_free(&slab, BLOCK(N_BLOCKS - 1U));
	k_mem_slab_free(&slab, BLOCK(0));

	zassert_equal(z_fatal_error_fake.call_count, 0);
	zassert_free_list(&slab, BLOCK(0), BLOCK(N_BLOCKS - 1U));
}

#ifdef CONFIG_ASSERT
/**
 * @brief With CONFIG_ASSERT, k_mem_slab_free() fails an assertion before it calls k_panic() for an
 * address that is not valid.
 *
 * @details
 * - Setup: a slab with block 0 used.
 * - Action: k_mem_slab_free() of an address outside of the buffer.
 * - Expected: one failed assertion, then one call of z_fatal_error().
 *
 * @ingroup kernel_unit_mem_slab_validate
 * @see k_mem_slab_free()
 */
ZTEST(mem_slab_unit, test_validate_free_asserts_before_panic)
{
	struct k_mem_slab slab;

	if (!IS_ENABLED(CONFIG_MEM_SLAB_POINTER_VALIDATE)) {
		ztest_test_skip();
	}

	slab_prepare(&slab);
	(void)alloc_block(&slab);

	k_mem_slab_free(&slab, foreign_block);

	zassert_equal(assert_post_action_fake.call_count, 1);
	zassert_called_before(assert_post_action, z_fatal_error);
}
#endif /* CONFIG_ASSERT */

#ifndef CONFIG_MEM_SLAB_POINTER_VALIDATE
/**
 * @brief Without CONFIG_MEM_SLAB_POINTER_VALIDATE, k_mem_slab_free() accepts an address outside of
 * the buffer and puts it into the free list.
 *
 * @details
 * - Setup: a slab with block 0 used.
 * - Action: k_mem_slab_free() of a block of memory outside of the buffer.
 * - Expected: no call of z_fatal_error(). The head of the free list is the
 *   foreign block. The number of used blocks is 0.
 *
 * @ingroup kernel_unit_mem_slab_validate
 * @see k_mem_slab_free(), slab_ptr_is_good()
 */
ZTEST(mem_slab_unit, test_validate_off_accepts_foreign_block)
{
	struct k_mem_slab slab;

	slab_prepare(&slab);
	(void)alloc_block(&slab);

	k_mem_slab_free(&slab, foreign_block);

	zassert_equal(z_fatal_error_fake.call_count, 0);
	zassert_equal_ptr(slab.free_list, foreign_block);
	zassert_equal(slab.info.num_used, 0U);
}
#endif /* !CONFIG_MEM_SLAB_POINTER_VALIDATE */

/**
 * @brief k_mem_slab_free() does not find a block that is free already: a second free of a block
 * makes a loop in the free list and decrements the count below 0.
 *
 * @details
 * This is a limit of the design, in all configurations. The pointer check
 * examines only the address.
 * - Setup: a slab with block 0 used.
 * - Action: k_mem_slab_free() of block 0, two times.
 * - Expected: no call of z_fatal_error(). The head of the free list is
 *   block 0, and the first word of block 0 points to block 0. The number
 *   of used blocks is UINT32_MAX.
 *
 * @ingroup kernel_unit_mem_slab_validate
 * @see k_mem_slab_free()
 */
ZTEST(mem_slab_unit, test_validate_double_free_not_found)
{
	struct k_mem_slab slab;

	slab_prepare(&slab);
	(void)alloc_block(&slab);

	k_mem_slab_free(&slab, BLOCK(0));
	k_mem_slab_free(&slab, BLOCK(0));

	zassert_equal(z_fatal_error_fake.call_count, 0);
	zassert_equal_ptr(slab.free_list, BLOCK(0));
	zassert_equal_ptr(*(char **)BLOCK(0), BLOCK(0));
	zassert_equal(slab.info.num_used, UINT32_MAX);
}

/**
 * @defgroup kernel_unit_mem_slab_stats Statistics
 * @ingroup kernel_unit_mem_slab
 * @brief The statistics functions report the used, free and maximum bytes of the slab.
 *
 * k_mem_slab_runtime_stats_get() computes the bytes from the counts and the
 * block size. With CONFIG_MEM_SLAB_TRACE_MAX_UTILIZATION, @c info.max_used
 * is the maximum of the used blocks since k_mem_slab_init() or since the
 * last k_mem_slab_runtime_stats_reset_max(). Only k_mem_slab_alloc() from
 * the free list increments it. The statistics functions return -EINVAL for
 * a NULL argument in all configurations (plain @c if, not CHECKIF()).
 */

/**
 * @brief k_mem_slab_runtime_stats_get() reports the used bytes and the free bytes, and returns 0.
 *
 * @details
 * - Setup: a slab with 4 blocks of 16 bytes, 3 blocks used.
 * - Action: k_mem_slab_runtime_stats_get().
 * - Expected: return value 0. allocated_bytes is 48, free_bytes is 16.
 *
 * @ingroup kernel_unit_mem_slab_stats
 * @see k_mem_slab_runtime_stats_get()
 */
ZTEST(mem_slab_unit, test_stats_get_reports_bytes)
{
	struct k_mem_slab slab;
	struct sys_memory_stats stats;

	slab_prepare(&slab);
	for (unsigned int i = 0; i < 3U; i++) {
		(void)alloc_block(&slab);
	}

	zassert_equal(k_mem_slab_runtime_stats_get(&slab, &stats), 0);

	zassert_equal(stats.allocated_bytes, 3U * BLOCK_SIZE);
	zassert_equal(stats.free_bytes, 1U * BLOCK_SIZE);
}

/**
 * @brief Without CONFIG_MEM_SLAB_TRACE_MAX_UTILIZATION, k_mem_slab_runtime_stats_get() reports 0
 * maximum bytes.
 *
 * @details
 * - Setup: a slab with 2 blocks used.
 * - Action: k_mem_slab_runtime_stats_get().
 * - Expected: max_allocated_bytes is 0.
 *
 * @ingroup kernel_unit_mem_slab_stats
 * @see k_mem_slab_runtime_stats_get()
 */
ZTEST(mem_slab_unit, test_stats_get_max_without_trace)
{
	struct k_mem_slab slab;
	struct sys_memory_stats stats;

	if (IS_ENABLED(CONFIG_MEM_SLAB_TRACE_MAX_UTILIZATION)) {
		ztest_test_skip();
	}

	slab_prepare(&slab);
	(void)alloc_block(&slab);
	(void)alloc_block(&slab);

	zassert_equal(k_mem_slab_runtime_stats_get(&slab, &stats), 0);

	zassert_equal(stats.max_allocated_bytes, 0U);
}

/**
 * @brief k_mem_slab_runtime_stats_get() returns -EINVAL and does not lock the slab if the slab or
 * the statistics pointer is NULL.
 *
 * @details
 * - Action: k_mem_slab_runtime_stats_get() with the slab NULL, then with
 *   the statistics NULL.
 * - Expected: each call returns -EINVAL. No calls to the layers below.
 *
 * @ingroup kernel_unit_mem_slab_stats
 * @see k_mem_slab_runtime_stats_get()
 */
ZTEST(mem_slab_unit, test_stats_get_rejects_null)
{
	struct k_mem_slab slab;
	struct sys_memory_stats stats;

	slab_prepare(&slab);

	zassert_equal(k_mem_slab_runtime_stats_get(NULL, &stats), -EINVAL);
	zassert_equal(k_mem_slab_runtime_stats_get(&slab, NULL), -EINVAL);

	zassert_equal(kernel_unit_history_len(), 0);
}

#ifdef CONFIG_MEM_SLAB_TRACE_MAX_UTILIZATION
/**
 * @brief With CONFIG_MEM_SLAB_TRACE_MAX_UTILIZATION, k_mem_slab_alloc() keeps the maximum number of
 * used blocks, and k_mem_slab_free() does not decrement it.
 *
 * @details
 * - Setup: a slab with 4 free blocks.
 * - Action: 3 allocations, 2 frees, 1 allocation.
 * - Expected: max_used is 1, 2, 3 after the allocations, stays 3 after the
 *   frees and after the last allocation. k_mem_slab_max_used_get() returns
 *   3. k_mem_slab_runtime_stats_get() reports 48 maximum bytes.
 *
 * @ingroup kernel_unit_mem_slab_stats
 * @see k_mem_slab_alloc(), k_mem_slab_free(), k_mem_slab_runtime_stats_get()
 */
ZTEST(mem_slab_unit, test_trace_max_used_keeps_peak)
{
	struct k_mem_slab slab;
	struct sys_memory_stats stats;
	void *blocks[3];

	slab_prepare(&slab);

	for (unsigned int i = 0; i < 3U; i++) {
		blocks[i] = alloc_block(&slab);
		zassert_equal(slab.info.max_used, i + 1U);
	}
	k_mem_slab_free(&slab, blocks[0]);
	k_mem_slab_free(&slab, blocks[1]);
	zassert_equal(slab.info.max_used, 3U);
	(void)alloc_block(&slab);

	zassert_equal(slab.info.max_used, 3U);
	zassert_equal(k_mem_slab_max_used_get(&slab), 3U);
	zassert_equal(k_mem_slab_runtime_stats_get(&slab, &stats), 0);
	zassert_equal(stats.max_allocated_bytes, 3U * BLOCK_SIZE);
}

/**
 * @brief With CONFIG_MEM_SLAB_TRACE_MAX_UTILIZATION, k_mem_slab_init() sets the maximum to 0.
 *
 * @details
 * - Setup: a slab filled with a pattern.
 * - Action: k_mem_slab_init().
 * - Expected: max_used is 0.
 *
 * @ingroup kernel_unit_mem_slab_stats
 * @see k_mem_slab_init()
 */
ZTEST(mem_slab_unit, test_trace_init_resets_max_used)
{
	struct k_mem_slab slab;

	memset(&slab, FILL, sizeof(slab));

	zassert_equal(k_mem_slab_init(&slab, slab_buf, BLOCK_SIZE, N_BLOCKS), 0);

	zassert_equal(slab.info.max_used, 0U);
}

/**
 * @brief With CONFIG_MEM_SLAB_TRACE_MAX_UTILIZATION, a hand-over to a waiting thread does not
 * change the maximum.
 *
 * @details
 * - Setup: a slab with all blocks used. max_used is 4. One thread waits.
 * - Action: k_mem_slab_free() of block 0, then the k_mem_slab_alloc() of
 *   the woken thread.
 * - Expected: max_used is 4.
 *
 * @ingroup kernel_unit_mem_slab_stats
 * @see k_mem_slab_free(), k_mem_slab_alloc()
 */
ZTEST(mem_slab_unit, test_trace_handover_keeps_max_used)
{
	struct k_mem_slab slab;
	void *mem;

	if (!IS_ENABLED(CONFIG_MULTITHREADING)) {
		ztest_test_skip();
	}

	slab_prepare(&slab);
	alloc_all_blocks(&slab);
	kernel_unit_set_waiting_threads(1);

	k_mem_slab_free(&slab, BLOCK(0));
	kernel_unit_set_wait_result(BLOCK(0), 0);
	zassert_equal(k_mem_slab_alloc(&slab, &mem, K_FOREVER), 0);

	zassert_equal(slab.info.max_used, N_BLOCKS);
}

/**
 * @brief k_mem_slab_runtime_stats_reset_max() sets the maximum to the current number of used
 * blocks and returns 0.
 *
 * @details
 * - Setup: a slab with 3 blocks allocated and 2 freed. max_used is 3.
 * - Action: k_mem_slab_runtime_stats_reset_max().
 * - Expected: return value 0. max_used is 1.
 *
 * @ingroup kernel_unit_mem_slab_stats
 * @see k_mem_slab_runtime_stats_reset_max()
 */
ZTEST(mem_slab_unit, test_trace_reset_max_sets_current_count)
{
	struct k_mem_slab slab;

	slab_prepare(&slab);
	alloc_all_blocks(&slab);
	k_mem_slab_free(&slab, BLOCK(0));
	k_mem_slab_free(&slab, BLOCK(1));
	k_mem_slab_free(&slab, BLOCK(2));

	zassert_equal(k_mem_slab_runtime_stats_reset_max(&slab), 0);

	zassert_equal(slab.info.max_used, 1U);
}

/**
 * @brief k_mem_slab_runtime_stats_reset_max() returns -EINVAL and does not lock if the slab is
 * NULL.
 *
 * @details
 * - Action: k_mem_slab_runtime_stats_reset_max() with NULL.
 * - Expected: return value -EINVAL. No calls to the layers below.
 *
 * @ingroup kernel_unit_mem_slab_stats
 * @see k_mem_slab_runtime_stats_reset_max()
 */
ZTEST(mem_slab_unit, test_trace_reset_max_rejects_null)
{
	zassert_equal(k_mem_slab_runtime_stats_reset_max(NULL), -EINVAL);

	zassert_equal(kernel_unit_history_len(), 0);
}
#endif /* CONFIG_MEM_SLAB_TRACE_MAX_UTILIZATION */

/**
 * @defgroup kernel_unit_mem_slab_locking Locking
 * @ingroup kernel_unit_mem_slab
 * @brief The spinlock of the slab protects the free list and the counts. Each path releases it
 * exactly once.
 *
 * Each path of k_mem_slab_alloc(), k_mem_slab_free() and the statistics
 * functions locks the spinlock of its slab once, as its first call to the
 * layers below. Each path releases the lock once, as its last call, with
 * the key of the lock: k_spin_unlock() (seen as arch_irq_unlock()),
 * z_reschedule() or z_pend_curr(). The free list and the counts change only
 * while the lock is held. The pointer check and the NULL checks occur
 * before the lock, and their error paths do not lock.
 */

/**
 * @brief If k_mem_slab_alloc() takes a block from the free list, it releases the lock with
 * k_spin_unlock().
 *
 * @details
 * - Setup: a slab with 4 free blocks.
 * - Action: k_mem_slab_alloc() with K_FOREVER.
 * - Expected calls: arch_irq_lock(), arch_irq_unlock() with the key.
 *
 * @ingroup kernel_unit_mem_slab_locking
 * @see k_mem_slab_alloc()
 */
ZTEST(mem_slab_unit, test_lock_alloc_from_list_unlocks)
{
	struct k_mem_slab slab;
	void *mem;

	slab_prepare(&slab);

	zassert_equal(k_mem_slab_alloc(&slab, &mem, K_FOREVER), 0);

	zassert_call_history(unit_arch_irq_lock, unit_arch_irq_unlock);
	assert_lock_released_once(&slab, KERNEL_UNIT_RELEASED_BY_UNLOCK);
}

/**
 * @brief If k_mem_slab_alloc() returns -ENOMEM, it releases the lock with k_spin_unlock().
 *
 * @details
 * - Setup: a slab with all blocks used.
 * - Action: k_mem_slab_alloc() with K_NO_WAIT.
 * - Expected calls: arch_irq_lock(), arch_irq_unlock() with the key.
 *
 * @ingroup kernel_unit_mem_slab_locking
 * @see k_mem_slab_alloc()
 */
ZTEST(mem_slab_unit, test_lock_alloc_enomem_unlocks)
{
	struct k_mem_slab slab;
	void *mem;

	slab_prepare(&slab);
	alloc_all_blocks(&slab);
	reset_history();

	zassert_equal(k_mem_slab_alloc(&slab, &mem, K_NO_WAIT), -ENOMEM);

	zassert_call_history(unit_arch_irq_lock, unit_arch_irq_unlock);
	assert_lock_released_once(&slab, KERNEL_UNIT_RELEASED_BY_UNLOCK);
}

/**
 * @brief If k_mem_slab_alloc() waits, z_pend_curr() releases the lock, and k_mem_slab_alloc() does
 * not release it again.
 *
 * @details
 * Applies with CONFIG_MULTITHREADING.
 * - Setup: a slab with all blocks used. The wait gives block 1.
 * - Action: k_mem_slab_alloc() with K_FOREVER.
 * - Expected calls: arch_irq_lock(), z_pend_curr() with the lock of the
 *   slab and the key. No call after z_pend_curr().
 *
 * @ingroup kernel_unit_mem_slab_locking
 * @see k_mem_slab_alloc()
 */
ZTEST(mem_slab_unit, test_lock_alloc_wait_hands_lock_to_pend)
{
	struct k_mem_slab slab;
	void *mem;

	if (!IS_ENABLED(CONFIG_MULTITHREADING)) {
		ztest_test_skip();
	}

	slab_prepare(&slab);
	alloc_all_blocks(&slab);
	reset_history();
	kernel_unit_set_wait_result(BLOCK(1), 0);

	zassert_equal(k_mem_slab_alloc(&slab, &mem, K_FOREVER), 0);

	zassert_call_history(unit_arch_irq_lock, z_pend_curr);
	assert_lock_released_once(&slab, KERNEL_UNIT_RELEASED_BY_PEND);
}

/**
 * @brief If k_mem_slab_free() puts the block into a free list that is not empty, it releases the
 * lock with k_spin_unlock().
 *
 * @details
 * - Setup: a slab with block 0 used.
 * - Action: k_mem_slab_free() of block 0.
 * - Expected calls: arch_irq_lock(), arch_irq_unlock() with the key.
 *
 * @ingroup kernel_unit_mem_slab_locking
 * @see k_mem_slab_free()
 */
ZTEST(mem_slab_unit, test_lock_free_to_list_unlocks)
{
	struct k_mem_slab slab;

	slab_prepare(&slab);
	(void)alloc_block(&slab);
	reset_history();

	k_mem_slab_free(&slab, BLOCK(0));

	zassert_call_history(unit_arch_irq_lock, unit_arch_irq_unlock);
	assert_lock_released_once(&slab, KERNEL_UNIT_RELEASED_BY_UNLOCK);
}

/**
 * @brief If the free list is empty and no thread waits, k_mem_slab_free() tries the wake while it
 * holds the lock and releases the lock with k_spin_unlock().
 *
 * @details
 * - Setup: a slab with all blocks used. No thread waits.
 * - Action: k_mem_slab_free() of block 0.
 * - Expected calls: arch_irq_lock(), z_sched_wake() (with
 *   CONFIG_MULTITHREADING), arch_irq_unlock() with the key.
 *
 * @ingroup kernel_unit_mem_slab_locking
 * @see k_mem_slab_free()
 */
ZTEST(mem_slab_unit, test_lock_free_no_waiter_unlocks)
{
	struct k_mem_slab slab;

	slab_prepare(&slab);
	alloc_all_blocks(&slab);
	reset_history();

	k_mem_slab_free(&slab, BLOCK(0));

	zassert_call_history(unit_arch_irq_lock,
			     KERNEL_UNIT_IF_ENABLED(CONFIG_MULTITHREADING, z_sched_wake),
			     unit_arch_irq_unlock);
	assert_lock_released_once(&slab, KERNEL_UNIT_RELEASED_BY_UNLOCK);
}

/**
 * @brief If k_mem_slab_free() gives the block to a waiting thread, it releases the lock with
 * z_reschedule().
 *
 * @details
 * Applies with CONFIG_MULTITHREADING.
 * - Setup: a slab with all blocks used. One thread waits.
 * - Action: k_mem_slab_free() of block 0.
 * - Expected calls: arch_irq_lock(), z_sched_wake(), z_reschedule() with
 *   the lock of the slab and the key.
 *
 * @ingroup kernel_unit_mem_slab_locking
 * @see k_mem_slab_free()
 */
ZTEST(mem_slab_unit, test_lock_free_handover_reschedules)
{
	struct k_mem_slab slab;

	if (!IS_ENABLED(CONFIG_MULTITHREADING)) {
		ztest_test_skip();
	}

	slab_prepare(&slab);
	alloc_all_blocks(&slab);
	reset_history();
	kernel_unit_set_waiting_threads(1);

	k_mem_slab_free(&slab, BLOCK(0));

	zassert_call_history(unit_arch_irq_lock, z_sched_wake, z_reschedule);
	assert_lock_released_once(&slab, KERNEL_UNIT_RELEASED_BY_RESCHEDULE);
}

/**
 * @brief If the address is not valid, k_mem_slab_free() calls k_panic() without a lock.
 *
 * @details
 * Applies with CONFIG_MEM_SLAB_POINTER_VALIDATE.
 * - Setup: a slab with block 0 used.
 * - Action: k_mem_slab_free() of a block outside of the buffer.
 * - Expected: no call of arch_irq_lock(), arch_irq_unlock(),
 *   z_sched_wake() and z_reschedule(). The last call is z_fatal_error().
 *
 * @ingroup kernel_unit_mem_slab_locking
 * @see k_mem_slab_free()
 */
ZTEST(mem_slab_unit, test_lock_free_invalid_does_not_lock)
{
	struct k_mem_slab slab;

	if (!IS_ENABLED(CONFIG_MEM_SLAB_POINTER_VALIDATE)) {
		ztest_test_skip();
	}

	slab_prepare(&slab);
	(void)alloc_block(&slab);
	reset_history();

	k_mem_slab_free(&slab, foreign_block);

	zassert_equal(unit_arch_irq_lock_fake.call_count, 0);
	zassert_equal(unit_arch_irq_unlock_fake.call_count, 0);
	zassert_equal(z_sched_wake_fake.call_count, 0);
	zassert_equal(z_reschedule_fake.call_count, 0);
	zassert_equal(kernel_unit_history_index(KERNEL_UNIT_FN(z_fatal_error), 0),
		      (int)kernel_unit_history_len() - 1);
}

/**
 * @brief k_mem_slab_runtime_stats_get() and k_mem_slab_runtime_stats_reset_max() release the lock
 * with k_spin_unlock().
 *
 * @details
 * - Setup: a slab with 4 free blocks.
 * - Action: k_mem_slab_runtime_stats_get(), then (new history, with
 *   CONFIG_MEM_SLAB_TRACE_MAX_UTILIZATION)
 *   k_mem_slab_runtime_stats_reset_max().
 * - Expected calls each time: arch_irq_lock(), arch_irq_unlock() with the
 *   key.
 *
 * @ingroup kernel_unit_mem_slab_locking
 * @see k_mem_slab_runtime_stats_get(), k_mem_slab_runtime_stats_reset_max()
 */
ZTEST(mem_slab_unit, test_lock_stats_unlock)
{
	struct k_mem_slab slab;
	struct sys_memory_stats stats;

	slab_prepare(&slab);

	zassert_equal(k_mem_slab_runtime_stats_get(&slab, &stats), 0);
	zassert_call_history(unit_arch_irq_lock, unit_arch_irq_unlock);
	assert_lock_released_once(&slab, KERNEL_UNIT_RELEASED_BY_UNLOCK);

#ifdef CONFIG_MEM_SLAB_TRACE_MAX_UTILIZATION
	reset_history();
	zassert_equal(k_mem_slab_runtime_stats_reset_max(&slab), 0);
	zassert_call_history(unit_arch_irq_lock, unit_arch_irq_unlock);
	assert_lock_released_once(&slab, KERNEL_UNIT_RELEASED_BY_UNLOCK);
#endif
}

/**
 * @brief k_mem_slab_alloc() and k_mem_slab_free() change the free list and the count only while
 * they hold the lock.
 *
 * @details
 * - Setup: a slab with 4 free blocks. Spy fakes record the number of free
 *   blocks and of used blocks at the lock and at the release.
 * - Action: k_mem_slab_alloc() with K_NO_WAIT, then k_mem_slab_free() of
 *   the block. The spies are reset before each call.
 * - Expected: at the lock, the old values. At the release, the new values.
 *
 * @ingroup kernel_unit_mem_slab_locking
 * @see k_mem_slab_alloc(), k_mem_slab_free()
 */
ZTEST(mem_slab_unit, test_lock_protects_free_list)
{
	struct k_mem_slab slab;
	void *mem;

	slab_prepare(&slab);

	spy_on_lock(&slab);
	mem = alloc_block(&slab);
	zassert_equal(at_lock.free_blocks, N_BLOCKS);
	zassert_equal(at_lock.num_used, 0U);
	zassert_equal(at_release.free_blocks, N_BLOCKS - 1U);
	zassert_equal(at_release.num_used, 1U);

	spy_on_lock(&slab);
	k_mem_slab_free(&slab, mem);
	zassert_equal(at_lock.free_blocks, N_BLOCKS - 1U);
	zassert_equal(at_lock.num_used, 1U);
	zassert_equal(at_release.free_blocks, N_BLOCKS);
	zassert_equal(at_release.num_used, 0U);
}

/**
 * @brief Each slab has its own lock.
 *
 * @details
 * - Setup: two slabs with 1 block each in different buffers.
 * - Action: k_mem_slab_alloc() from the first slab, then from the second
 *   slab.
 * - Expected: two calls of the spinlock lock path. With
 *   CONFIG_SPIN_VALIDATE, the validation sees the lock of the first slab,
 *   then the lock of the second slab. The lock members are different.
 *
 * @ingroup kernel_unit_mem_slab_locking
 * @see k_mem_slab_alloc()
 */
ZTEST(mem_slab_unit, test_lock_one_lock_per_slab)
{
	struct k_mem_slab slab1;
	struct k_mem_slab slab2;

	zassert_equal(k_mem_slab_init(&slab1, BLOCK(0), BLOCK_SIZE, 1), 0);
	zassert_equal(k_mem_slab_init(&slab2, BLOCK(1), BLOCK_SIZE, 1), 0);
	reset_history();
	kernel_unit_set_waiting_threads(2);

	(void)alloc_block(&slab1);
	(void)alloc_block(&slab2);
	k_mem_slab_free(&slab1, BLOCK(0));
	k_mem_slab_free(&slab2, BLOCK(1));

	zassert_not_equal(&slab1.lock, &slab2.lock);
	if (IS_ENABLED(CONFIG_MULTITHREADING)) {
		zassert_equal(z_reschedule_fake.call_count, 2);
		zassert_equal_ptr(z_reschedule_fake.arg0_history[0], &slab1.lock);
		zassert_equal_ptr(z_reschedule_fake.arg0_history[1], &slab2.lock);
	}
#ifdef CONFIG_SPIN_VALIDATE
	zassert_equal_ptr(z_spin_lock_valid_fake.arg0_history[0], &slab1.lock);
	zassert_equal_ptr(z_spin_lock_valid_fake.arg0_history[1], &slab2.lock);
#endif
}

/**
 * @brief k_mem_slab_init() and init_mem_slab_module() do not lock the slab.
 *
 * @details
 * - Action: k_mem_slab_init(), then init_mem_slab_module().
 * - Expected: no call of arch_irq_lock().
 *
 * @ingroup kernel_unit_mem_slab_locking
 * @see k_mem_slab_init(), init_mem_slab_module()
 */
ZTEST(mem_slab_unit, test_lock_not_used_by_init)
{
	struct k_mem_slab slab;

	zassert_equal(k_mem_slab_init(&slab, slab_buf, BLOCK_SIZE, N_BLOCKS), 0);
	init_mem_slab_module();

	zassert_equal(unit_arch_irq_lock_fake.call_count, 0);
}

#ifdef CONFIG_SPIN_VALIDATE
/**
 * @brief With CONFIG_SPIN_VALIDATE, the spinlock validation sees the lock of the slab on lock and
 * on unlock.
 *
 * @details
 * - Setup: a slab with 4 free blocks.
 * - Action: k_mem_slab_alloc() with K_NO_WAIT.
 * - Expected: one call of z_spin_lock_valid() and one call of
 *   z_spin_unlock_valid(), each with the lock of the slab.
 *
 * @ingroup kernel_unit_mem_slab_locking
 * @see k_mem_slab_alloc()
 */
ZTEST(mem_slab_unit, test_lock_validation_sees_slab_lock)
{
	struct k_mem_slab slab;

	slab_prepare(&slab);

	(void)alloc_block(&slab);

	zassert_equal(z_spin_lock_valid_fake.call_count, 1);
	zassert_equal_ptr(z_spin_lock_valid_fake.arg0_val, &slab.lock);
	zassert_equal(z_spin_unlock_valid_fake.call_count, 1);
	zassert_equal_ptr(z_spin_unlock_valid_fake.arg0_val, &slab.lock);
}
#endif /* CONFIG_SPIN_VALIDATE */

/**
 * @defgroup kernel_unit_mem_slab_limits Limits of the checks
 * @ingroup kernel_unit_mem_slab
 * @brief mem_slab.c relies on the caller and on the scheduler for the context of a wait.
 *
 * The API says that an ISR must use K_NO_WAIT. mem_slab.c has no check of
 * this rule. In an ISR, a wait reaches z_pend_curr(), and the scheduler
 * refuses it with a panic in every build. See also the double free in
 * @ref kernel_unit_mem_slab_validate.
 */

/**
 * @brief k_mem_slab_alloc() does not check the context: in an ISR with a timeout other than
 * K_NO_WAIT, it reaches z_pend_curr(), and the scheduler refuses the wait with a panic.
 *
 * @details
 * Applies with CONFIG_MULTITHREADING.
 * - Setup: a slab with all blocks used. arch_is_in_isr() returns true. The
 *   scheduler model would give block 0. The test expects the refusal of
 *   z_pend_curr().
 * - Action: k_mem_slab_alloc() with K_FOREVER.
 * - Expected: one call of z_pend_curr() with the lock of the slab. No call
 *   of arch_is_in_isr() by mem_slab.c. The scheduler refuses the wait with a
 *   failed assertion (with CONFIG_ASSERT) and a panic. The failed assertion
 *   is the only one: mem_slab.c has no assertion of its own. The scheduler
 *   gives no block, and the slab stays full. After the panic, the fake
 *   returns KERNEL_UNIT_PEND_REFUSED, and k_mem_slab_alloc() gives this
 *   value to the caller.
 *
 * @ingroup kernel_unit_mem_slab_limits
 * @see k_mem_slab_alloc()
 */
ZTEST(mem_slab_unit, test_limits_alloc_does_not_check_isr)
{
	struct k_mem_slab slab;
	void *mem;

	if (!IS_ENABLED(CONFIG_MULTITHREADING)) {
		ztest_test_skip();
	}

	slab_prepare(&slab);
	alloc_all_blocks(&slab);
	arch_is_in_isr_fake.return_val = true;
	kernel_unit_set_wait_result(BLOCK(0), 0);
	kernel_unit_expect_pend_refusal();
	mem = NULL;

	zassert_equal(k_mem_slab_alloc(&slab, &mem, K_FOREVER), KERNEL_UNIT_PEND_REFUSED);

	kernel_unit_assert_pend_refused();
	zassert_equal(z_pend_curr_fake.call_count, 1);
	zassert_equal_ptr(z_pend_curr_fake.arg0_val, &slab.lock);
	zassert_equal(arch_is_in_isr_fake.call_count, 0);
	zassert_is_null(mem);
	zassert_is_null(slab.free_list);
	zassert_equal(slab.info.num_used, slab.info.num_blocks);
#ifdef CONFIG_ASSERT
	zassert_equal(assert_post_action_fake.call_count, 1);
#endif
}

#ifdef CONFIG_OBJ_CORE_MEM_SLAB
/**
 * @defgroup kernel_unit_mem_slab_obj_core Object core
 * @ingroup kernel_unit_mem_slab
 * @brief With CONFIG_OBJ_CORE_MEM_SLAB, mem_slab.c defines the object type of the slabs and links
 * each slab of k_mem_slab_init() to it.
 *
 * mem_slab.c defines the object type @c obj_type_mem_slab.
 * K_OBJ_TYPE_DEFINE() (or K_OBJ_TYPE_DEFINE_STATS() with
 * CONFIG_OBJ_CORE_STATS_MEM_SLAB) puts one descriptor into the iterable
 * section @c k_obj_core_desc. At boot, the object core code initializes the
 * type and links the slabs of K_MEM_SLAB_DEFINE() (the section
 * @c k_mem_slab). With statistics, it also registers @c info of each static
 * slab. k_mem_slab_init() links a slab at run time.
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

/**
 * @brief With CONFIG_OBJ_CORE_MEM_SLAB, mem_slab.c defines one object type descriptor with the ID
 * K_OBJ_TYPE_MEM_SLAB_ID for the slabs.
 *
 * @details
 * - Action: search the section @c k_obj_core_desc for the descriptor of
 *   @c obj_type_mem_slab.
 * - Expected: one descriptor. Its type ID is K_OBJ_TYPE_MEM_SLAB_ID. Its
 *   object size is the size of @c struct @c k_mem_slab, and its object core
 *   offset is the offset of @c obj_core. Its object range is the section
 *   @c k_mem_slab.
 *
 * @ingroup kernel_unit_mem_slab_obj_core
 */
ZTEST(mem_slab_unit, test_obj_core_type_descriptor)
{
	int count;
	const struct k_obj_core_desc *desc = obj_core_desc(&obj_type_mem_slab, &count);

	zassert_equal(count, 1);
	zassert_not_null(desc);
	zassert_equal(desc->type_id, K_OBJ_TYPE_MEM_SLAB_ID);
	zassert_equal(desc->obj_size, sizeof(struct k_mem_slab));
	zassert_equal(desc->obj_core_offset, offsetof(struct k_mem_slab, obj_core));
	zassert_equal_ptr(desc->objs_start, STRUCT_SECTION_START(k_mem_slab));
	zassert_equal_ptr(desc->objs_end, STRUCT_SECTION_END(k_mem_slab));
}

/**
 * @brief The object range of the descriptor contains the slabs that K_MEM_SLAB_DEFINE() defines.
 *
 * @details
 * - Setup: K_MEM_SLAB_DEFINE() of slab a and slab d_after in the test.
 * - Action: compare the addresses of the slabs with the object range of
 *   the descriptor.
 * - Expected: each slab is in the range, at a multiple of the object size
 *   from the start.
 *
 * @ingroup kernel_unit_mem_slab_obj_core
 */
ZTEST(mem_slab_unit, test_obj_core_descriptor_covers_static_slabs)
{
	int count;
	const struct k_obj_core_desc *desc = obj_core_desc(&obj_type_mem_slab, &count);
	const uintptr_t objs[] = {(uintptr_t)&unit_slab_a, (uintptr_t)&unit_slab_d_after};

	zassert_not_null(desc);
	for (size_t i = 0; i < ARRAY_SIZE(objs); i++) {
		zassert_true((objs[i] >= (uintptr_t)desc->objs_start) &&
			     (objs[i] < (uintptr_t)desc->objs_end));
		zassert_equal((objs[i] - (uintptr_t)desc->objs_start) % desc->obj_size, 0U);
	}
}

/**
 * @brief With CONFIG_OBJ_CORE_MEM_SLAB, k_mem_slab_init() links the object core of the slab to the
 * slab object type.
 *
 * @details
 * - Action: k_mem_slab_init().
 * - Expected: one call of k_obj_core_init_and_link() with the object core
 *   of the slab and @c obj_type_mem_slab.
 *
 * @ingroup kernel_unit_mem_slab_obj_core
 * @see k_mem_slab_init()
 */
ZTEST(mem_slab_unit, test_obj_core_init_links_slab)
{
	struct k_mem_slab slab;

	zassert_equal(k_mem_slab_init(&slab, slab_buf, BLOCK_SIZE, N_BLOCKS), 0);

	zassert_equal(k_obj_core_init_and_link_fake.call_count, 1);
	zassert_equal_ptr(k_obj_core_init_and_link_fake.arg0_val, K_OBJ_CORE(&slab));
	zassert_equal_ptr(k_obj_core_init_and_link_fake.arg1_val, &obj_type_mem_slab);
}

#ifdef CONFIG_OBJ_CORE_STATS
/**
 * @brief With CONFIG_OBJ_CORE_STATS, the descriptor gives the statistics descriptor and the info
 * of each static slab only with CONFIG_OBJ_CORE_STATS_MEM_SLAB.
 *
 * @details
 * - Action: read the statistics fields of the descriptor of
 *   @c obj_type_mem_slab.
 * - Expected: with CONFIG_OBJ_CORE_STATS_MEM_SLAB, the statistics
 *   descriptor is @c mem_slab_stats_desc, the offset is the offset of
 *   @c info, and the size is the size of @c struct @c k_mem_slab_info.
 *   Else they are NULL, 0 and 0.
 *
 * @ingroup kernel_unit_mem_slab_obj_core
 */
ZTEST(mem_slab_unit, test_obj_core_descriptor_stats_fields)
{
	int count;
	const struct k_obj_core_desc *desc = obj_core_desc(&obj_type_mem_slab, &count);

	zassert_not_null(desc);
#ifdef CONFIG_OBJ_CORE_STATS_MEM_SLAB
	zassert_equal_ptr(desc->stats_desc, &mem_slab_stats_desc);
	zassert_equal(desc->stats_offset, offsetof(struct k_mem_slab, info));
	zassert_equal(desc->stats_size, sizeof(struct k_mem_slab_info));
#else
	zassert_is_null(desc->stats_desc);
	zassert_equal(desc->stats_offset, 0U);
	zassert_equal(desc->stats_size, 0U);
#endif
}
#endif /* CONFIG_OBJ_CORE_STATS */
#endif /* CONFIG_OBJ_CORE_MEM_SLAB */

#ifdef CONFIG_OBJ_CORE_STATS_MEM_SLAB
/**
 * @defgroup kernel_unit_mem_slab_obj_core_stats Object core statistics
 * @ingroup kernel_unit_mem_slab
 * @brief With CONFIG_OBJ_CORE_STATS_MEM_SLAB, the object core framework reads the statistics of a
 * slab through the functions of mem_slab_stats_desc.
 *
 * k_mem_slab_init() registers @c info of the slab as the raw statistics.
 * The descriptor @c mem_slab_stats_desc gives three functions:
 * k_mem_slab_stats_raw() copies @c info, k_mem_slab_stats_query() computes
 * the bytes as k_mem_slab_runtime_stats_get() does, and
 * k_mem_slab_stats_reset() sets the maximum to the current count. There is
 * no enable and no disable function. Each function locks the slab. With
 * CONFIG_ASSERT, each function asserts that its arguments are not NULL,
 * before the lock.
 */

/**
 * @brief With CONFIG_OBJ_CORE_STATS_MEM_SLAB, k_mem_slab_init() registers the info of the slab as
 * its raw statistics, after the object core link.
 *
 * @details
 * - Action: k_mem_slab_init().
 * - Expected: one call of k_obj_core_stats_register() with the object core
 *   of the slab, @c info of the slab and the size of
 *   @c struct @c k_mem_slab_info, after k_obj_core_init_and_link().
 *
 * @ingroup kernel_unit_mem_slab_obj_core_stats
 * @see k_mem_slab_init()
 */
ZTEST(mem_slab_unit, test_obj_core_stats_init_registers_info)
{
	struct k_mem_slab slab;

	zassert_equal(k_mem_slab_init(&slab, slab_buf, BLOCK_SIZE, N_BLOCKS), 0);

	zassert_equal(k_obj_core_stats_register_fake.call_count, 1);
	zassert_equal_ptr(k_obj_core_stats_register_fake.arg0_val, K_OBJ_CORE(&slab));
	zassert_equal_ptr(k_obj_core_stats_register_fake.arg1_val, &slab.info);
	zassert_equal(k_obj_core_stats_register_fake.arg2_val, sizeof(struct k_mem_slab_info));
	zassert_called_before(k_obj_core_init_and_link, k_obj_core_stats_register);
}

/**
 * @brief k_mem_slab_init() ignores an error of k_obj_core_stats_register() and returns 0.
 *
 * @details
 * - Setup: k_obj_core_stats_register() returns -EINVAL.
 * - Action: k_mem_slab_init().
 * - Expected: return value 0. The wait queue is initialized.
 *
 * @ingroup kernel_unit_mem_slab_obj_core_stats
 * @see k_mem_slab_init()
 */
ZTEST(mem_slab_unit, test_obj_core_stats_register_error_ignored)
{
	struct k_mem_slab slab;

	k_obj_core_stats_register_fake.return_val = -EINVAL;

	zassert_equal(k_mem_slab_init(&slab, slab_buf, BLOCK_SIZE, N_BLOCKS), 0);

	zassert_equal(z_waitq_init_fake.call_count, 1);
}

/**
 * @brief The statistics descriptor of the slabs gives the raw, query and reset functions of
 * mem_slab.c, and no enable and disable functions.
 *
 * @details
 * - Action: read @c mem_slab_stats_desc.
 * - Expected: the raw size is the size of @c struct @c k_mem_slab_info,
 *   the query size is the size of @c struct @c sys_memory_stats. The
 *   functions are k_mem_slab_stats_raw(), k_mem_slab_stats_query() and
 *   k_mem_slab_stats_reset(). The enable and disable functions are NULL.
 *
 * @ingroup kernel_unit_mem_slab_obj_core_stats
 */
ZTEST(mem_slab_unit, test_obj_core_stats_descriptor)
{
	zassert_equal(mem_slab_stats_desc.raw_size, sizeof(struct k_mem_slab_info));
	zassert_equal(mem_slab_stats_desc.query_size, sizeof(struct sys_memory_stats));
	zassert_equal_ptr(mem_slab_stats_desc.raw, k_mem_slab_stats_raw);
	zassert_equal_ptr(mem_slab_stats_desc.query, k_mem_slab_stats_query);
	zassert_equal_ptr(mem_slab_stats_desc.reset, k_mem_slab_stats_reset);
	zassert_is_null(mem_slab_stats_desc.disable);
	zassert_is_null(mem_slab_stats_desc.enable);
}

/**
 * @brief k_mem_slab_stats_raw() copies the info of the slab, under the lock of the slab, and
 * returns 0.
 *
 * @details
 * - Setup: a slab with 2 blocks used.
 * - Action: k_mem_slab_stats_raw() with the object core of the slab.
 * - Expected: return value 0. The copy is equal to @c info. Calls:
 *   arch_irq_lock(), arch_irq_unlock() with the key.
 *
 * @ingroup kernel_unit_mem_slab_obj_core_stats
 * @see k_mem_slab_stats_raw()
 */
ZTEST(mem_slab_unit, test_obj_core_stats_raw_copies_info)
{
	struct k_mem_slab slab;
	struct k_mem_slab_info info;

	slab_prepare(&slab);
	(void)alloc_block(&slab);
	(void)alloc_block(&slab);
	reset_history();
	memset(&info, FILL, sizeof(info));

	zassert_equal(k_mem_slab_stats_raw(K_OBJ_CORE(&slab), &info), 0);

	zassert_mem_equal(&info, &slab.info, sizeof(info));
	zassert_call_history(unit_arch_irq_lock, unit_arch_irq_unlock);
	assert_lock_released_once(&slab, KERNEL_UNIT_RELEASED_BY_UNLOCK);
}

/**
 * @brief k_mem_slab_stats_query() reports the free, used and maximum bytes, under the lock of the
 * slab, and returns 0.
 *
 * @details
 * - Setup: a slab with 3 blocks allocated and 1 freed.
 * - Action: k_mem_slab_stats_query() with the object core of the slab.
 * - Expected: return value 0. free_bytes is 32, allocated_bytes is 32.
 *   max_allocated_bytes is 48 with CONFIG_MEM_SLAB_TRACE_MAX_UTILIZATION,
 *   else 0. Calls: arch_irq_lock(), arch_irq_unlock() with the key.
 *
 * @ingroup kernel_unit_mem_slab_obj_core_stats
 * @see k_mem_slab_stats_query()
 */
ZTEST(mem_slab_unit, test_obj_core_stats_query_reports_bytes)
{
	struct k_mem_slab slab;
	struct sys_memory_stats stats;

	slab_prepare(&slab);
	for (unsigned int i = 0; i < 3U; i++) {
		(void)alloc_block(&slab);
	}
	k_mem_slab_free(&slab, BLOCK(0));
	reset_history();

	zassert_equal(k_mem_slab_stats_query(K_OBJ_CORE(&slab), &stats), 0);

	zassert_equal(stats.free_bytes, 2U * BLOCK_SIZE);
	zassert_equal(stats.allocated_bytes, 2U * BLOCK_SIZE);
	zassert_equal(stats.max_allocated_bytes,
		      IS_ENABLED(CONFIG_MEM_SLAB_TRACE_MAX_UTILIZATION) ? 3U * BLOCK_SIZE : 0U);
	zassert_call_history(unit_arch_irq_lock, unit_arch_irq_unlock);
	assert_lock_released_once(&slab, KERNEL_UNIT_RELEASED_BY_UNLOCK);
}

/**
 * @brief k_mem_slab_stats_reset() sets the maximum to the current count (with
 * CONFIG_MEM_SLAB_TRACE_MAX_UTILIZATION), under the lock of the slab, and returns 0.
 *
 * @details
 * Without CONFIG_MEM_SLAB_TRACE_MAX_UTILIZATION, the function changes
 * nothing and also returns 0.
 * - Setup: a slab with 3 blocks allocated and 2 freed.
 * - Action: k_mem_slab_stats_reset() with the object core of the slab.
 * - Expected: return value 0. With the trace option, max_used is 1. The
 *   info of the slab is otherwise unchanged. Calls: arch_irq_lock(),
 *   arch_irq_unlock() with the key.
 *
 * @ingroup kernel_unit_mem_slab_obj_core_stats
 * @see k_mem_slab_stats_reset()
 */
ZTEST(mem_slab_unit, test_obj_core_stats_reset_sets_max_to_count)
{
	struct k_mem_slab slab;
	struct k_mem_slab_info before;

	slab_prepare(&slab);
	for (unsigned int i = 0; i < 3U; i++) {
		(void)alloc_block(&slab);
	}
	k_mem_slab_free(&slab, BLOCK(0));
	k_mem_slab_free(&slab, BLOCK(1));
	reset_history();
	before = slab.info;

	zassert_equal(k_mem_slab_stats_reset(K_OBJ_CORE(&slab)), 0);

#ifdef CONFIG_MEM_SLAB_TRACE_MAX_UTILIZATION
	zassert_equal(slab.info.max_used, 1U);
	before.max_used = 1U;
#endif
	zassert_mem_equal(&slab.info, &before, sizeof(before));
	zassert_call_history(unit_arch_irq_lock, unit_arch_irq_unlock);
	assert_lock_released_once(&slab, KERNEL_UNIT_RELEASED_BY_UNLOCK);
}

#ifdef CONFIG_ASSERT
/**
 * @brief With CONFIG_ASSERT, the object core statistics functions assert that the object core and
 * the statistics buffer are not NULL, before the lock.
 *
 * @details
 * The fake assertion hook does a longjmp() back to the test, so the
 * function does not continue with the NULL pointer.
 * - Setup: a slab with 4 free blocks.
 * - Action: k_mem_slab_stats_raw() and k_mem_slab_stats_query() with the
 *   object core NULL, and with the statistics buffer NULL.
 *   k_mem_slab_stats_reset() with the object core NULL.
 * - Expected: a failed assertion for each of the 5 calls. No lock.
 *
 * @ingroup kernel_unit_mem_slab_obj_core_stats
 * @see k_mem_slab_stats_raw(), k_mem_slab_stats_query(), k_mem_slab_stats_reset()
 */
ZTEST(mem_slab_unit, test_obj_core_stats_assert_null_arguments)
{
	struct k_mem_slab slab;
	struct k_mem_slab_info info;
	struct sys_memory_stats stats;

	slab_prepare(&slab);

	zassert_stopped_by_assertion(k_mem_slab_stats_raw(NULL, &info));
	zassert_stopped_by_assertion(k_mem_slab_stats_raw(K_OBJ_CORE(&slab), NULL));
	zassert_stopped_by_assertion(k_mem_slab_stats_query(NULL, &stats));
	zassert_stopped_by_assertion(k_mem_slab_stats_query(K_OBJ_CORE(&slab), NULL));
	zassert_stopped_by_assertion(k_mem_slab_stats_reset(NULL));

	zassert_equal(assert_post_action_fake.call_count, 5);
	zassert_equal(unit_arch_irq_lock_fake.call_count, 0);
}
#endif /* CONFIG_ASSERT */
#endif /* CONFIG_OBJ_CORE_STATS_MEM_SLAB */
