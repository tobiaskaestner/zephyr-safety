/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Fake of the minimal logging backend of subsys/logging/log_minimal.c
 * (zephyr/logging/log_core.h).
 *
 * The unit_testing board uses CONFIG_LOG_MODE_MINIMAL. A LOG_DBG() of a
 * unit is in the code only if the log level of its module is DBG, for
 * example CONFIG_KERNEL_LOG_LEVEL_DBG. Then it calls
 * z_log_minimal_printk(). The unittest build does not build the logging
 * subsystem, so this fake replaces the function. It prints nothing. A test
 * can examine z_log_minimal_printk_fake.call_count and arg0_val (the
 * format).
 *
 * Link the fake group log_minimal if a scenario enables the log level DBG
 * of the unit.
 */

#ifndef KERNEL_UNIT_FAKES_LOG_MINIMAL_H_
#define KERNEL_UNIT_FAKES_LOG_MINIMAL_H_

#include <zephyr/logging/log_core.h>
#include <zephyr/fff.h>

#ifdef __cplusplus
extern "C" {
#endif

#define LOG_MINIMAL_FFF_FAKES_LIST(FAKE) FAKE(z_log_minimal_printk)

DECLARE_FAKE_VOID_FUNC_VARARG(z_log_minimal_printk, const char *, ...);

#ifdef __cplusplus
}
#endif

#endif /* KERNEL_UNIT_FAKES_LOG_MINIMAL_H_ */
