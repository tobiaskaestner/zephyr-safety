/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Fakes of kernel/timeslicing.c (fake group timeslicing).
 *
 * kernel/sched.c and kernel/include/kswap.h call z_time_slice_reset() when
 * a new thread gets the CPU (with CONFIG_TIMESLICING). The fake records the
 * calls, so a test can count the resets of a wake (roadmap step 7, points 1
 * and 2). The group also defines the data pending_current
 * (CONFIG_TIMESLICING with CONFIG_SWAP_NONATOMIC): z_pend_curr() writes it.
 * The reset rule sets it to NULL.
 */

#ifndef KERNEL_UNIT_FAKES_TIMESLICING_H_
#define KERNEL_UNIT_FAKES_TIMESLICING_H_

#include <zephyr/kernel.h>
#include <zephyr/fff.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TIMESLICING_FFF_FAKES_LIST(FAKE) FAKE(z_time_slice_reset)

DECLARE_FAKE_VOID_FUNC(z_time_slice_reset, struct k_thread *);

/* Data of kernel/timeslicing.c. */
extern struct k_thread *pending_current;

#ifdef __cplusplus
}
#endif

#endif /* KERNEL_UNIT_FAKES_TIMESLICING_H_ */
