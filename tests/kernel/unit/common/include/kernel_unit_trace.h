/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @defgroup kernel_unit_trace Trace hook of the unit tests
 * @ingroup kernel_unit_models
 * @brief One NDJSON line for each call of an object API and for each call into the layers below.
 *
 * With @kconfig{CONFIG_KERNEL_UNIT_TRACE}, the fake group @c trace writes a
 * trace of each test to the standard output. Each line starts with
 * @c "KTRACE " and has one JSON object. A trace module of the TLA+ library
 * (@c spec/tla/trace/) reads the lines of one test and checks that the run
 * is a behavior of the contract module of the object (a trace check, roadmap
 * step 2).
 *
 * The sources of the lines:
 *
 * - The test source calls kernel_unit_trace_api_enter() and
 *   kernel_unit_trace_api_exit() around each call of the object API (for
 *   k_sem: wrappers of z_impl_k_sem_*() in the test source).
 * - The fakes of the groups @c sched, @c arch and @c kernel_internal call
 *   kernel_unit_trace_call() when FFF records a call (this header replaces
 *   the macro REGISTER_CALL of FFF in these sources). The hook writes the
 *   line of a call when the next line comes, because the return value of the
 *   fake is known only then.
 * - The fake z_pend_curr() calls kernel_unit_trace_pend_return() when it
 *   returns, and kernel_unit_trace_pend_refused() when it refuses a call in
 *   an ISR (the real scheduler panics; the hook then stops the trace).
 * - With the reference fake of the scheduler, the trace hook of the
 *   reference fake calls kernel_unit_trace_sched_ref(): the woken thread of a
 *   wake, the expiry of a timeout and the abort of a thread.
 *
 * The schema of the lines is in @c spec/tla/trace/README.rst.
 *
 * @{
 */

#ifndef KERNEL_UNIT_TRACE_H_
#define KERNEL_UNIT_TRACE_H_

#include <stdbool.h>
#include <stddef.h>
#include <zephyr/fff.h>

#ifdef __cplusplus
extern "C" {
#endif

/** An object of the unit for the trace: the fields that the hook reads. */
struct kernel_unit_trace_obj {
	/** The object (the key of the object in the trace). */
	const void *obj;
	/** Its wait queue: a scheduler call with this queue is a call on the object. */
	const void *wait_q;
	/** Its poll events, or NULL. */
	const void *poll_events;
	/** The measure of the resource (the count of a semaphore), or NULL. */
	const unsigned int *count;
	/** The limit of the resource, or NULL. */
	const unsigned int *limit;
};

/**
 * @brief Write the line of the start of an API call.
 *
 * @param op The operation: "init", "give", "take" or "flush".
 * @param o The object.
 * @param lock The spinlock of the unit (for the check of the release).
 * @param timeout "NO_WAIT", "FOREVER", "TICKS", or NULL for a call without timeout.
 * @param args The integer arguments, or NULL.
 * @param n_args The number of arguments.
 */
void kernel_unit_trace_api_enter(const char *op, const struct kernel_unit_trace_obj *o,
				 const void *lock, const char *timeout, const unsigned int *args,
				 size_t n_args);

/**
 * @brief Write the line of the end of an API call.
 *
 * @param op The operation of kernel_unit_trace_api_enter().
 * @param obj The object.
 * @param has_ret False for a function without a return value.
 * @param ret The return value.
 */
void kernel_unit_trace_api_exit(const char *op, const void *obj, bool has_ret, int ret);

/** @brief A fake recorded a call (FFF REGISTER_CALL). */
void kernel_unit_trace_call(fff_function_t fn);

/** @brief The fake z_pend_curr() returns @p ret to the waiting thread. */
void kernel_unit_trace_pend_return(int ret);

/** @brief The fake z_pend_curr() refused a call in an ISR: the real scheduler panics. */
void kernel_unit_trace_pend_refused(void);

struct kernel_unit_sched_ref_record;

/** @brief A record of the trace hook of the reference fake of the scheduler. */
void kernel_unit_trace_sched_ref(const struct kernel_unit_sched_ref_record *rec);

#ifdef CONFIG_KERNEL_UNIT_TRACE
/*
 * FFF records each call with REGISTER_CALL. In the sources of the fakes that
 * include this header after <zephyr/fff.h>, the macro also calls the hook.
 */
#undef REGISTER_CALL
#define REGISTER_CALL(function)                                                                    \
	do {                                                                                       \
		if (fff.call_history_idx < FFF_CALL_HISTORY_LEN) {                                 \
			fff.call_history[fff.call_history_idx++] = (fff_function_t)function;       \
		}                                                                                  \
		kernel_unit_trace_call((fff_function_t)function);                                  \
	} while (false)
#endif /* CONFIG_KERNEL_UNIT_TRACE */

#ifdef __cplusplus
}
#endif

/** @} */

#endif /* KERNEL_UNIT_TRACE_H_ */
