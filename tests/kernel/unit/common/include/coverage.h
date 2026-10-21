/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Shadow of subsys/testsuite/coverage/coverage.h.
 *
 * The real header is the gcov backend of a target build
 * (CONFIG_COVERAGE_GCOV). The per-test coverage rule of ztest
 * (ztest_rules.c) uses only gcov_reset_all_counts() of it. In a unit test,
 * common/src/gcov_native.c implements this function with libgcov.
 */

#ifndef _COVERAGE_H_
#define _COVERAGE_H_

void gcov_reset_all_counts(void);

#endif /* _COVERAGE_H_ */
