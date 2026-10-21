/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Shadow of kernel/include/wait_q.h.
 *
 * In the real header the wait queue helpers are static inline. Here each
 * one is an FFF fake, so a unit test sees how the unit uses its wait queue.
 */

#ifndef ZEPHYR_KERNEL_INCLUDE_WAIT_Q_H_
#define ZEPHYR_KERNEL_INCLUDE_WAIT_Q_H_

#include <zephyr/kernel_structs.h>
#include <zephyr/fff.h>

#ifdef __cplusplus
extern "C" {
#endif

#define WAIT_Q_FFF_FAKES_LIST(FAKE)                                                                \
	FAKE(z_waitq_init)                                                                         \
	FAKE(z_waitq_head)                                                                         \
	FAKE(z_waitq_head_locked)

DECLARE_FAKE_VOID_FUNC(z_waitq_init, _wait_q_t *);
DECLARE_FAKE_VALUE_FUNC(struct k_thread *, z_waitq_head, _wait_q_t *);
DECLARE_FAKE_VALUE_FUNC(struct k_thread *, z_waitq_head_locked, _wait_q_t *);

#ifdef __cplusplus
}
#endif

#endif /* ZEPHYR_KERNEL_INCLUDE_WAIT_Q_H_ */
