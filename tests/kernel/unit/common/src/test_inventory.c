/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Test inventory check of the kernel unit tests.
 *
 * A change outside of a test can remove a test without a diagnostic. For
 * example, a renamed Kconfig symbol in "#ifdef CONFIG_X" removes the test,
 * and a renamed symbol in IS_ENABLED(CONFIG_X) changes the test into a
 * skip. The run then passes with fewer tests.
 *
 * This file replaces the weak test_main() of ztest. After all suites ran,
 * it compares the tests of the binary and their state with the expected
 * set of the twister scenario. The state of a test is "run" or "skip":
 *
 * - "skip": each run of the test was a skip, or the test did not run (for
 *   example, the predicate of its suite was false).
 * - "run": all other cases. A test that failed also ran: ztest reports the
 *   failure itself. A test with ZTEST_EXPECT_FAIL() or ZTEST_EXPECT_SKIP()
 *   passes, so its state is "run".
 *
 * If a test is missing, extra, or has a different state, the binary prints
 * the tests, prints "PROJECT EXECUTION FAILED" and exits with status 1.
 * Then twister reports the configuration as failed.
 *
 * The binary always writes the actual set to KERNEL_UNIT_INVENTORY_ACTUAL.
 * "common/test_inventory.py update" copies the actual sets into the
 * expected sets of the applications.
 *
 * common/test_inventory.py generates kernel_unit_inventory.h from the
 * expected set (<application>/inventory/<scenario>.txt) when the
 * application is configured.
 */

#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <zephyr/ztest.h>

enum kernel_unit_inventory_state {
	KERNEL_UNIT_INVENTORY_RUN,
	KERNEL_UNIT_INVENTORY_SKIP,
};

struct kernel_unit_inventory_entry {
	const char *suite;
	const char *test;
	enum kernel_unit_inventory_state state;
};

/*
 * Defines KERNEL_UNIT_INVENTORY_SCENARIO, KERNEL_UNIT_INVENTORY_EXPECTED,
 * KERNEL_UNIT_INVENTORY_ACTUAL, KERNEL_UNIT_INVENTORY_MODE and the array
 * kernel_unit_inventory_expected[] (with a NULL entry at the end).
 */
#include <kernel_unit_inventory.h>

/* KERNEL_UNIT_INVENTORY_MODE */
#define KERNEL_UNIT_INVENTORY_MODE_OFF     0 /* The application has no expected sets. */
#define KERNEL_UNIT_INVENTORY_MODE_NO_FILE 1 /* The scenario has no expected set. */
#define KERNEL_UNIT_INVENTORY_MODE_CHECK   2

/* The same repeat counts as the weak test_main() in ztest.c. */
#if defined(CONFIG_ZTEST_REPEAT)
#define KERNEL_UNIT_ITER_PER_SUITE CONFIG_ZTEST_SUITE_REPEAT_COUNT
#define KERNEL_UNIT_ITER_PER_TEST  CONFIG_ZTEST_TEST_REPEAT_COUNT
#elif defined(CONFIG_ZTEST_SHUFFLE)
#define KERNEL_UNIT_ITER_PER_SUITE CONFIG_ZTEST_SHUFFLE_SUITE_REPEAT_COUNT
#define KERNEL_UNIT_ITER_PER_TEST  CONFIG_ZTEST_SHUFFLE_TEST_REPEAT_COUNT
#else
#define KERNEL_UNIT_ITER_PER_SUITE 1
#define KERNEL_UNIT_ITER_PER_TEST  1
#endif

static const char *state_name(enum kernel_unit_inventory_state state)
{
	return state == KERNEL_UNIT_INVENTORY_SKIP ? "skip" : "run";
}

static enum kernel_unit_inventory_state actual_state(const struct ztest_unit_test *test)
{
	if (test->stats->skip_count == test->stats->run_count) {
		return KERNEL_UNIT_INVENTORY_SKIP;
	}

	return KERNEL_UNIT_INVENTORY_RUN;
}

static void write_actual(void)
{
	FILE *out = fopen(KERNEL_UNIT_INVENTORY_ACTUAL, "w");

	if (out == NULL) {
		printf("kernel_unit inventory: WARNING: cannot write %s\n",
		       KERNEL_UNIT_INVENTORY_ACTUAL);
		return;
	}

	for (struct ztest_unit_test *test = _ztest_unit_test_list_start;
	     test < _ztest_unit_test_list_end; ++test) {
		fprintf(out, "%s %s.%s\n", state_name(actual_state(test)), test->test_suite_name,
			test->name);
	}

	fclose(out);
}

static const struct kernel_unit_inventory_entry *find_expected(const struct ztest_unit_test *test)
{
	for (const struct kernel_unit_inventory_entry *entry = kernel_unit_inventory_expected;
	     entry->suite != NULL; ++entry) {
		if (strcmp(entry->suite, test->test_suite_name) == 0 &&
		    strcmp(entry->test, test->name) == 0) {
			return entry;
		}
	}

	return NULL;
}

static bool in_binary(const struct kernel_unit_inventory_entry *entry)
{
	for (struct ztest_unit_test *test = _ztest_unit_test_list_start;
	     test < _ztest_unit_test_list_end; ++test) {
		if (strcmp(entry->suite, test->test_suite_name) == 0 &&
		    strcmp(entry->test, test->name) == 0) {
			return true;
		}
	}

	return false;
}

/* Prints each difference and returns the number of differences. */
static int compare(void)
{
	int differences = 0;

	for (const struct kernel_unit_inventory_entry *entry = kernel_unit_inventory_expected;
	     entry->suite != NULL; ++entry) {
		if (!in_binary(entry)) {
			printf("kernel_unit inventory: MISSING %s.%s (expected %s)\n", entry->suite,
			       entry->test, state_name(entry->state));
			differences++;
		}
	}

	for (struct ztest_unit_test *test = _ztest_unit_test_list_start;
	     test < _ztest_unit_test_list_end; ++test) {
		const struct kernel_unit_inventory_entry *entry = find_expected(test);
		enum kernel_unit_inventory_state state = actual_state(test);

		if (entry == NULL) {
			printf("kernel_unit inventory: EXTRA %s.%s (actual %s)\n",
			       test->test_suite_name, test->name, state_name(state));
			differences++;
		} else if (entry->state != state) {
			printf("kernel_unit inventory: CHANGED %s.%s (expected %s, actual %s)\n",
			       test->test_suite_name, test->name, state_name(entry->state),
			       state_name(state));
			differences++;
		}
	}

	return differences;
}

static void inventory_check(void)
{
	int differences;

	write_actual();

	if (KERNEL_UNIT_INVENTORY_MODE == KERNEL_UNIT_INVENTORY_MODE_OFF) {
		printf("kernel_unit inventory: WARNING: no expected sets for this application, "
		       "the check is off (scenario %s)\n",
		       KERNEL_UNIT_INVENTORY_SCENARIO);
		return;
	}

	if (KERNEL_UNIT_INVENTORY_MODE == KERNEL_UNIT_INVENTORY_MODE_NO_FILE) {
		printf("kernel_unit inventory: no expected set for scenario %s (%s)\n",
		       KERNEL_UNIT_INVENTORY_SCENARIO, KERNEL_UNIT_INVENTORY_EXPECTED);
	}

	differences = compare();
	if (differences == 0) {
		printf("kernel_unit inventory: %d tests as expected (scenario %s)\n",
		       (int)ZTEST_TEST_COUNT, KERNEL_UNIT_INVENTORY_SCENARIO);
		return;
	}

	printf("kernel_unit inventory: %d differences in scenario %s\n"
	       "kernel_unit inventory: expected set: %s\n"
	       "kernel_unit inventory: actual set: %s\n"
	       "kernel_unit inventory: If the change is deliberate, regenerate the expected "
	       "set and review the diff (see \"Test inventory\" in README.rst). "
	       "If not, the change is a finding.\n",
	       differences, KERNEL_UNIT_INVENTORY_SCENARIO, KERNEL_UNIT_INVENTORY_EXPECTED,
	       KERNEL_UNIT_INVENTORY_ACTUAL);
	TC_END_REPORT(TC_FAIL);
	exit(1);
}

void test_main(void)
{
	ztest_run_all(NULL, IS_ENABLED(CONFIG_ZTEST_SHUFFLE), KERNEL_UNIT_ITER_PER_SUITE,
		      KERNEL_UNIT_ITER_PER_TEST);
	ztest_verify_all_test_suites_ran();
	inventory_check();
}
