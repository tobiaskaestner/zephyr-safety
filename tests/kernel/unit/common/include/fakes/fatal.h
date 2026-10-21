/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Fake of the fatal error handler of kernel/fatal.c (zephyr/fatal.h).
 *
 * The unit_testing architecture does not define ARCH_EXCEPT(). Thus
 * k_panic() and k_oops() in zephyr/kernel.h expand to
 * z_fatal_error(reason, NULL). The real function does not return for
 * K_ERR_KERNEL_PANIC. The fake returns, so the unit continues after the
 * k_panic() in the test. A test checks z_fatal_error_fake.call_count and
 * arg0_val (the reason), or sets a custom_fake that does a longjmp() back
 * into the test.
 *
 * Link the fake group fatal if the unit calls k_panic() or k_oops(), and
 * with the group sched: the fake z_pend_curr() panics in an ISR (see the
 * shadow ksched.h).
 */

#ifndef KERNEL_UNIT_FAKES_FATAL_H_
#define KERNEL_UNIT_FAKES_FATAL_H_

#include <zephyr/fatal.h>
#include <zephyr/fff.h>

#ifdef __cplusplus
extern "C" {
#endif

#define FATAL_FFF_FAKES_LIST(FAKE) FAKE(z_fatal_error)

DECLARE_FAKE_VOID_FUNC(z_fatal_error, unsigned int, const struct arch_esf *);

#ifdef __cplusplus
}
#endif

#endif /* KERNEL_UNIT_FAKES_FATAL_H_ */
