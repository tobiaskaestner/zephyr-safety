/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @defgroup kernel_unit_tests Kernel unit tests
 * @brief Unit tests of single kernel source files, as executable design specifications.
 *
 * Each test application builds one kernel source file, for example
 * @c kernel/sem.c, for the @c unit_testing board. The kernel does not start.
 * The test source includes the kernel source file. Thus a test can call the
 * static functions of the unit and read its static data.
 *
 * Each function that the unit calls outside of its file is an FFF fake. The
 * fakes are the boundary of the unit: the scheduler, the wait queue, the
 * poll and object core subsystems, the system call checks and the
 * architecture layer. A test sets the return values of the fakes and
 * examines their calls. Thus each test states one design rule of the unit
 * as a fact about its state and about its calls into the layers below it.
 *
 * Each application of a kernel source file has a Doxygen group below this
 * group, with the kernel source file as its title. The introduction of that group describes the
 * design of its unit as a whole. Below it, each public function of the file
 * has one group, and the static functions of the file have the last group.
 * Each test is in the group of the function under test.
 *
 * See @c tests/kernel/unit/README.rst for the design of the harness.
 */

/*
 * Shared helpers of the kernel unit tests.
 *
 * - KERNEL_UNIT_IRQ_KEY: a distinctive interrupt lock key. A test makes
 *   unit_arch_irq_lock() return it. Then the test can follow the key to
 *   the call that releases the lock.
 * - Call history: FFF records the address of each fake that the unit calls
 *   in fff.call_history[]. The helpers below read this history without the
 *   calls of the spinlock validation (CONFIG_SPIN_VALIDATE) and of the
 *   minimal log backend (fake group log_minimal). The validation calls come
 *   from k_spin_lock() and k_spin_unlock() in zephyr/spinlock.h, not from
 *   the unit. The log calls are not calls into a layer below.
 */

#ifndef KERNEL_UNIT_H_
#define KERNEL_UNIT_H_

#include <stdbool.h>
#include <stddef.h>
#include <zephyr/ztest.h>
#include <zephyr/fff.h>
#include <zephyr/sys/util.h>
#ifdef CONFIG_SPIN_VALIDATE
#include <fakes/spinlock.h>
#endif
#ifdef KERNEL_UNIT_FAKE_GROUP_log_minimal
#include <fakes/log_minimal.h>
#endif

#ifdef __cplusplus
extern "C" {
#endif

/** Interrupt lock key that the fake unit_arch_irq_lock() returns in a test. */
#define KERNEL_UNIT_IRQ_KEY 0x5EA1C0DEU

/** Cast a fake function to the type of an entry of fff.call_history[]. */
#define KERNEL_UNIT_FN(fn) ((fff_function_t)(fn))

/**
 * Entry of an expected call history that exists only if a Kconfig option is
 * enabled. If the option is not enabled, the entry is NULL, and
 * kernel_unit_history_equal() ignores it.
 */
#define KERNEL_UNIT_IF_ENABLED(_flag, fn) COND_CODE_1(_flag, (fn), (NULL))

/**
 * Return true if the history helpers ignore a call to @p fn: a call of the
 * spinlock validation, or a call of the minimal log backend (fake group
 * log_minimal).
 */
static inline bool kernel_unit_history_ignored(fff_function_t fn)
{
#ifdef CONFIG_SPIN_VALIDATE
	if ((fn == KERNEL_UNIT_FN(z_spin_lock_valid)) ||
	    (fn == KERNEL_UNIT_FN(z_spin_unlock_valid)) ||
	    (fn == KERNEL_UNIT_FN(z_spin_lock_set_owner)) ||
	    (fn == KERNEL_UNIT_FN(z_spin_lock_transfer_owner)) ||
	    (fn == KERNEL_UNIT_FN(z_assert_can_swap)) ||
	    (fn == KERNEL_UNIT_FN(z_spin_validate_reset))) {
		return true;
	}
#endif
#ifdef KERNEL_UNIT_FAKE_GROUP_log_minimal
	if (fn == KERNEL_UNIT_FN(z_log_minimal_printk)) {
		return true;
	}
#endif
	ARG_UNUSED(fn);

	return false;
}

/**
 * Copy the call history without the ignored calls to @p out.
 *
 * @return The number of calls in @p out.
 */
static inline size_t kernel_unit_history(fff_function_t *out, size_t max)
{
	size_t n = 0;

	for (unsigned int i = 0; (i < fff.call_history_idx) && (n < max); i++) {
		if (!kernel_unit_history_ignored(fff.call_history[i])) {
			out[n++] = fff.call_history[i];
		}
	}

	return n;
}

/** Print the call history without the ignored calls. */
static inline void kernel_unit_history_print(void)
{
	fff_function_t calls[FFF_CALL_HISTORY_LEN];
	size_t n = kernel_unit_history(calls, ARRAY_SIZE(calls));

	TC_PRINT("call history (%zu calls):\n", n);
	for (size_t i = 0; i < n; i++) {
		TC_PRINT("  [%zu] %p\n", i, (void *)calls[i]);
	}
}

/**
 * Compare the call history with @p expected. NULL entries of @p expected do
 * not count. If the history differs, print it.
 */
static inline bool kernel_unit_history_equal(const fff_function_t *expected, size_t n_expected)
{
	fff_function_t calls[FFF_CALL_HISTORY_LEN];
	size_t n = kernel_unit_history(calls, ARRAY_SIZE(calls));
	size_t pos = 0;
	bool equal = true;

	for (size_t i = 0; i < n_expected; i++) {
		if (expected[i] == NULL) {
			continue;
		}
		if ((pos >= n) || (calls[pos] != expected[i])) {
			equal = false;
			break;
		}
		pos++;
	}
	if (pos != n) {
		equal = false;
	}

	if (!equal) {
		kernel_unit_history_print();
	}

	return equal;
}

/**
 * Return the position of call number @p nth (0 is the first call) of @p fn
 * in the call history without the ignored calls, or -1.
 */
static inline int kernel_unit_history_index(fff_function_t fn, unsigned int nth)
{
	fff_function_t calls[FFF_CALL_HISTORY_LEN];
	size_t n = kernel_unit_history(calls, ARRAY_SIZE(calls));

	for (size_t i = 0; i < n; i++) {
		if (calls[i] == fn) {
			if (nth == 0U) {
				return (int)i;
			}
			nth--;
		}
	}

	return -1;
}

/** Return the number of calls in the history without the ignored calls. */
static inline size_t kernel_unit_history_len(void)
{
	fff_function_t calls[FFF_CALL_HISTORY_LEN];

	return kernel_unit_history(calls, ARRAY_SIZE(calls));
}

/**
 * Assert that the call history is exactly the list of fakes in the
 * arguments, in this order. Use KERNEL_UNIT_IF_ENABLED() for a call that
 * exists only in some configurations.
 */
#define zassert_call_history(...)                                                                  \
	do {                                                                                       \
		const fff_function_t kernel_unit_expected_[] = {                                   \
			FOR_EACH(KERNEL_UNIT_FN, (, ), __VA_ARGS__)};                              \
		zassert_true(kernel_unit_history_equal(kernel_unit_expected_,                      \
						       ARRAY_SIZE(kernel_unit_expected_)),         \
			     "the call history is not as expected (printed above)");               \
	} while (false)

/** Assert that the first call of @p first comes before the first call of @p second. */
#define zassert_called_before(first, second)                                                       \
	do {                                                                                       \
		int kernel_unit_i1_ = kernel_unit_history_index(KERNEL_UNIT_FN(first), 0);         \
		int kernel_unit_i2_ = kernel_unit_history_index(KERNEL_UNIT_FN(second), 0);        \
		zassert_true(kernel_unit_i1_ >= 0, #first "() was not called");                    \
		zassert_true(kernel_unit_i2_ >= 0, #second "() was not called");                   \
		zassert_true(kernel_unit_i1_ < kernel_unit_i2_,                                    \
			     #first "() was not called before " #second "()");                     \
	} while (false)

#ifdef __cplusplus
}
#endif

#endif /* KERNEL_UNIT_H_ */
