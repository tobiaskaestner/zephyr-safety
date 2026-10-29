/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Fakes of kernel/timeout.c (fake group timeout), with an opt-in model of
 * the module Timeout. See fakes/timeout.h.
 */

#include <string.h>
#include <zephyr/ztest.h>
#include <zephyr/sys/util.h>
#include <fakes/timeout.h>

DEFINE_FAKE_VALUE_FUNC(k_ticks_t, z_add_timeout, struct _timeout *, _timeout_func_t, k_timeout_t);
DEFINE_FAKE_VALUE_FUNC(int, z_try_abort_timeout, struct _timeout *);
DEFINE_FAKE_VALUE_FUNC(bool, z_timeout_inflight_superseded, const struct _timeout *);

struct kernel_unit_timeout_model kernel_unit_timeout;

/* Short name of the state in this file. */
#define TM kernel_unit_timeout

/*
 * Keep the state of z_is_inactive_timeout() of the real timeout_q.h in the
 * structure: a linked node (list backends) or a heap index other than 0
 * (MINHEAP) for an armed timeout.
 */
static void mirror(struct _timeout *to, bool armed)
{
#if defined(CONFIG_TIMEOUT_BACKEND_MINHEAP)
	to->heap_handle.idx = armed ? 1U : 0U;
#else
	to->node.next = armed ? &to->node : NULL;
	to->node.prev = armed ? &to->node : NULL;
#endif
}

static int find(const struct _timeout *to)
{
	for (size_t i = 0; i < TM.n_armed; i++) {
		if (TM.armed[i].to == to) {
			return (int)i;
		}
	}

	return -1;
}

static void remove_at(size_t i)
{
	mirror(TM.armed[i].to, false);
	for (size_t j = i + 1U; j < TM.n_armed; j++) {
		TM.armed[j - 1U] = TM.armed[j];
	}
	TM.n_armed--;
}

bool kernel_unit_timeout_is_armed(const struct _timeout *to)
{
	return find(to) >= 0;
}

/* Timeout!InsertAny(t): z_add_timeout() of kernel/timeout.c, on the fake clock. */
static k_ticks_t model_add_timeout(struct _timeout *to, _timeout_func_t fn, k_timeout_t timeout)
{
	k_ticks_t ticks = timeout.ticks;
	struct kernel_unit_timeout_entry *e;

	if (K_TIMEOUT_EQ(timeout, K_FOREVER)) {
		return 0;
	}
	if ((find(to) >= 0) || (TM.n_armed >= ARRAY_SIZE(TM.armed))) {
		/* The real function asserts z_is_inactive_timeout(to). */
		TC_PRINT("timeout model: z_add_timeout() of an armed timeout, or too many\n");
		ztest_test_fail();
		return 0;
	}
	to->fn = fn;
	e = &TM.armed[TM.n_armed++];
	e->to = to;
	e->seq = TM.next_seq++;
	if (Z_IS_TIMEOUT_RELATIVE(timeout)) {
		e->deadline = TM.clock + ticks;
	} else {
		e->deadline = MAX((int64_t)Z_TICK_ABS(ticks), TM.clock + 1);
	}
	mirror(to, true);

	return (k_ticks_t)e->deadline;
}

/* Timeout!Cancel(t): z_try_abort_timeout() for one CPU. */
static int model_try_abort_timeout(struct _timeout *to)
{
	int i = find(to);
	int ret = -EINVAL;

	if (i >= 0) {
		remove_at((size_t)i);
		ret = 0;
	}
	if (TM.inflight == to) {
		TM.superseded = true;
	}

	return ret;
}

static bool model_inflight_superseded(const struct _timeout *to)
{
	return (TM.inflight == to) && TM.superseded;
}

bool kernel_unit_timeout_expire_first(void)
{
	size_t first = 0;
	struct _timeout *to;

	if (TM.n_armed == 0U) {
		return false;
	}
	for (size_t i = 1; i < TM.n_armed; i++) {
		const struct kernel_unit_timeout_entry *e = &TM.armed[i];
		const struct kernel_unit_timeout_entry *f = &TM.armed[first];

		if ((e->deadline < f->deadline) ||
		    ((e->deadline == f->deadline) && (e->seq < f->seq))) {
			first = i;
		}
	}
	to = TM.armed[first].to;
	TM.clock = TM.armed[first].deadline;
	/* sys_clock_announce() removes the timeout, then calls its handler. */
	remove_at(first);
	TM.expiries++;
	TM.inflight = to;
	TM.superseded = false;
	to->fn(to);
	TM.inflight = NULL;
	TM.superseded = false;

	return true;
}

void kernel_unit_timeout_model_install(void)
{
	TM.installed = true;
	z_add_timeout_fake.custom_fake = model_add_timeout;
	z_try_abort_timeout_fake.custom_fake = model_try_abort_timeout;
	z_timeout_inflight_superseded_fake.custom_fake = model_inflight_superseded;
}

static void timeout_fakes_reset(const struct ztest_unit_test *test, void *fixture)
{
	ARG_UNUSED(test);
	ARG_UNUSED(fixture);

	TIMEOUT_FFF_FAKES_LIST(RESET_FAKE);
	memset(&kernel_unit_timeout, 0, sizeof(kernel_unit_timeout));
}

ZTEST_RULE(timeout_fakes_reset, timeout_fakes_reset, NULL);
