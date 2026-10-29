/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Fakes of the timeout functions of kernel/timeout.c (fake group timeout).
 *
 * An application that makes kernel/include/timeout_q.h real
 * (kernel_unit_real_headers(timeout_q)) links this group. The inline helpers
 * of the real header (z_add_thread_timeout(), z_try_abort_thread_timeout(),
 * z_is_inactive_timeout()) then run, and they call these fakes. An
 * application with the shadow timeout_q.h does not link this group: there,
 * z_try_abort_thread_timeout() is a fake of the group sched.
 *
 * After the reset, each fake returns 0. The opt-in model
 * (kernel_unit_timeout_model_install()) is the C form of the module Timeout
 * (safety/spec/tla/lib/Timeout.tla) for one CPU:
 *
 * - z_add_timeout(): Timeout!InsertAny. It arms the timeout with a deadline
 *   on a fake clock and keeps its handler. K_FOREVER arms nothing, as in the
 *   real function. A relative timeout expires ticks after now, an absolute
 *   timeout at its tick, but at least one tick after now. The fake clock has
 *   no round-up of a relative timeout by one tick (the same rule as the
 *   reference fake).
 * - z_try_abort_timeout(): Timeout!Cancel. 0 for an armed timeout, else
 *   -EINVAL. With one CPU no handler is in flight on another CPU, so the
 *   fake never returns -EAGAIN.
 * - z_timeout_inflight_superseded(): true only if the handler of this
 *   timeout runs now and a call of z_try_abort_timeout() for it came after
 *   its start.
 * - kernel_unit_timeout_expire_first(): Timeout!Expire. The first armed
 *   timeout (the earliest deadline, then the order of arming) expires: the
 *   clock moves to its deadline, the timeout is not armed, and its handler
 *   runs. The caller is the timer ISR of the model group platform.
 *
 * The model keeps the state of z_is_inactive_timeout() in the timeout
 * structure: the node of the list backends, the heap index of MINHEAP.
 */

#ifndef KERNEL_UNIT_FAKES_TIMEOUT_H_
#define KERNEL_UNIT_FAKES_TIMEOUT_H_

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <zephyr/kernel.h>
#include <zephyr/fff.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TIMEOUT_FFF_FAKES_LIST(FAKE)                                                               \
	FAKE(z_add_timeout)                                                                        \
	FAKE(z_try_abort_timeout)                                                                  \
	FAKE(z_timeout_inflight_superseded)

DECLARE_FAKE_VALUE_FUNC(k_ticks_t, z_add_timeout, struct _timeout *, _timeout_func_t, k_timeout_t);
DECLARE_FAKE_VALUE_FUNC(int, z_try_abort_timeout, struct _timeout *);
DECLARE_FAKE_VALUE_FUNC(bool, z_timeout_inflight_superseded, const struct _timeout *);

/** Maximum number of armed timeouts of the model. */
#define KERNEL_UNIT_TIMEOUT_MAX 8

/** One armed timeout of the model. */
struct kernel_unit_timeout_entry {
	/** The timeout. */
	struct _timeout *to;
	/** The deadline on the fake clock. */
	int64_t deadline;
	/** The order of arming, for equal deadlines. */
	uint32_t seq;
};

/** The state of the model. The reset rule of the group sets it to zeros. */
struct kernel_unit_timeout_model {
	/** True after kernel_unit_timeout_model_install(). */
	bool installed;
	/** The armed timeouts, in the order of arming. */
	struct kernel_unit_timeout_entry armed[KERNEL_UNIT_TIMEOUT_MAX];
	/** The number of armed timeouts. */
	size_t n_armed;
	/** The fake clock in ticks. It moves only at an expiry. */
	int64_t clock;
	/** The next order of arming. */
	uint32_t next_seq;
	/** The timeout whose handler runs now, or NULL. */
	struct _timeout *inflight;
	/** True if z_try_abort_timeout() of the timeout in flight came after its start. */
	bool superseded;
	/** The number of expiries. */
	unsigned int expiries;
};

/** The state of the timeout model. */
extern struct kernel_unit_timeout_model kernel_unit_timeout;

/** Install the model: set the custom fakes of the three functions. */
void kernel_unit_timeout_model_install(void);

/** Return true if @p to is armed in the model. */
bool kernel_unit_timeout_is_armed(const struct _timeout *to);

/**
 * Let the first armed timeout expire, and run its handler (Timeout!Expire).
 *
 * @return false if no timeout is armed.
 */
bool kernel_unit_timeout_expire_first(void);

#ifdef __cplusplus
}
#endif

#endif /* KERNEL_UNIT_FAKES_TIMEOUT_H_ */
