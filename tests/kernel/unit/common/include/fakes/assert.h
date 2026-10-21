/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Fakes of the assert hooks (zephyr/sys/__assert.h).
 *
 * With CONFIG_ASSERT, a failed __ASSERT() calls assert_print() and
 * assert_post_action(). The fakes return, so the unit continues after a
 * failed assertion. A test checks assert_post_action_fake.call_count.
 *
 * Enable CONFIG_ASSERT_TEST with CONFIG_ASSERT. Without it, __ASSERT()
 * ends in CODE_UNREACHABLE after the hook, and the unit continues into
 * undefined behavior when the fake returns.
 */

#ifndef KERNEL_UNIT_FAKES_ASSERT_H_
#define KERNEL_UNIT_FAKES_ASSERT_H_

#include <zephyr/sys/__assert.h>
#include <zephyr/fff.h>

#ifdef __cplusplus
extern "C" {
#endif

#define ASSERT_FFF_FAKES_LIST(FAKE)                                                                \
	FAKE(assert_print)                                                                         \
	FAKE(assert_post_action)

DECLARE_FAKE_VOID_FUNC_VARARG(assert_print, const char *, ...);
#ifdef CONFIG_ASSERT_NO_FILE_INFO
DECLARE_FAKE_VOID_FUNC(assert_post_action);
#else
DECLARE_FAKE_VOID_FUNC(assert_post_action, const char *, unsigned int);
#endif

#ifdef __cplusplus
}
#endif

#endif /* KERNEL_UNIT_FAKES_ASSERT_H_ */
