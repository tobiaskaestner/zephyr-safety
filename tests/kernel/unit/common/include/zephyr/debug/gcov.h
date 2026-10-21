/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Shadow of include/zephyr/debug/gcov.h.
 *
 * The real header declares the dump functions only for a target build
 * (CONFIG_COVERAGE_GCOV). For CONFIG_COVERAGE_NATIVE_GCOV it gives empty
 * inline functions. With CONFIG_ZTEST_COVERAGE_PER_TEST, a unit test
 * declares the dump functions here, and common/src/gcov_native.c
 * implements them with libgcov.
 */

#ifndef ZEPHYR_INCLUDE_DEBUG_GCOV_H_
#define ZEPHYR_INCLUDE_DEBUG_GCOV_H_

#ifdef CONFIG_ZTEST_COVERAGE_PER_TEST

void gcov_coverage_dump(void);

void gcov_coverage_dump_tagged(const char *tag);

#else

static inline void gcov_coverage_dump(void)
{
}

static inline void gcov_coverage_dump_tagged(const char *tag)
{
	(void)tag;
}

#endif /* CONFIG_ZTEST_COVERAGE_PER_TEST */

static inline void gcov_static_init(void)
{
}

#endif /* ZEPHYR_INCLUDE_DEBUG_GCOV_H_ */
