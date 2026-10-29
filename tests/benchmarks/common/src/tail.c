/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Tail witnesses (CONFIG_LATBENCH_TAIL, see latbench/tail.h).
 * latbench.cmake adds this file only with the option.
 */

#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>

#include <latbench/hist.h>
#include <latbench/tail.h>

void lat_tail_init(void)
{
	CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
	DWT->CTRL |= DWT_CTRL_EXCEVTENA_Msk;
}

/* The row with the smallest lat of a full table. */
static void find_low(struct lat_tail *t)
{
	uint32_t low = UINT32_MAX;
	uint32_t low_i = 0U;

	for (uint32_t i = 0U; i < t->n; i++) {
		if (t->rows[i].lat < low) {
			low = t->rows[i].lat;
			low_i = i;
		}
	}
	t->low = low;
	t->low_i = low_i;
}

__noinline void lat_tail_add(struct lat_tail *t, const struct lat_tail_mark *m, uint32_t seq,
			     uint32_t lat, uint32_t aux, uint32_t phase, int ctx)
{
	uint32_t cnt = stim_now();
	uint32_t exc = (DWT->EXCCNT - m->exc) & 0xffU;
	uint32_t st = SysTick->VAL;
	struct lat_tail_row *r;

	if (exc < t->exc_min) {
		t->exc_min = exc;
	}
	if (exc > t->exc_max) {
		t->exc_max = exc;
	}
	if (lat >= LAT_INVALID_MIN || lat < CONFIG_LATBENCH_TAIL_MIN_CYC) {
		return;
	}
	t->seen++;
	if (t->n < CONFIG_LATBENCH_TAIL_N) {
		r = &t->rows[t->n++];
	} else if (lat > t->low) {
		r = &t->rows[t->low_i];
	} else {
		return;
	}
	r->seq = seq;
	r->lat = lat;
	r->aux = aux;
	r->phase = phase;
	r->win = cnt - m->cnt;
	r->exc = exc;
	r->st0 = m->st;
	r->st1 = st;
	r->ld = SysTick->LOAD;
	r->tmr = load_timer_count() - m->tmr;
	r->wake = load_wake_count() - m->wake;
	r->pc = 0U;
	r->icsr = 0U;
	if (ctx == LAT_TAIL_ISR_CTX) {
		uint32_t icsr = SCB->ICSR;

		r->icsr = icsr;
		if ((icsr & SCB_ICSR_RETTOBASE_Msk) != 0U) {
			/* Thread mode was interrupted: its frame is on PSP, the PC is word 6. */
			r->pc = ((const uint32_t *)__get_PSP())[6];
		}
	}
	if (t->n == CONFIG_LATBENCH_TAIL_N) {
		find_low(t);
	}
}

void lat_tail_print(const struct lat_tail *t)
{
	printk("LAT TAIL %s n=%u seen=%u min_cyc=%u exc_min=%u exc_max=%u "
	       "fields=seq,lat,aux,phase,win,exc,st0,st1,ld,tmr,wake,pc,icsr\n",
	       t->name, t->n, t->seen, CONFIG_LATBENCH_TAIL_MIN_CYC,
	       t->exc_min == UINT32_MAX ? 0U : t->exc_min, t->exc_max);
	for (uint32_t i = 0U; i < t->n; i++) {
		const struct lat_tail_row *r = &t->rows[i];

		printk("LAT TW %u %u %u %u %u %u %u %u %u %u %u 0x%08x 0x%08x\n", r->seq, r->lat,
		       r->aux, r->phase, r->win, r->exc, r->st0, r->st1, r->ld, r->tmr, r->wake, r->pc,
		       r->icsr);
	}
	printk("LAT END %s\n", t->name);
}

/*
 * The cost of the calls, from the stimulus timer, with the interrupts
 * locked: the smallest value of 64 tries, minus nothing (the empty pair of
 * two time stamps is printed too). The add is measured in its three paths:
 * rejected (fast), stored, and stored with the scan of a full table.
 */
static struct lat_tail scratch;

void lat_tail_print_setup(void)
{
	uint32_t c_empty = UINT32_MAX;
	uint32_t c_mark = UINT32_MAX;
	uint32_t c_reject = UINT32_MAX;
	uint32_t c_store = UINT32_MAX;
	uint32_t c_full = UINT32_MAX;
	struct lat_tail_mark m;

	for (uint32_t i = 0U; i < CONFIG_LATBENCH_TAIL_N; i++) {
		scratch.rows[i].lat = CONFIG_LATBENCH_TAIL_MIN_CYC + 1000U;
	}
	for (int i = 0; i < 64; i++) {
		unsigned int key = irq_lock();
		uint32_t a;
		uint32_t b;

		a = stim_now();
		b = stim_now();
		c_empty = MIN(c_empty, b - a);

		a = stim_now();
		lat_tail_mark(&m);
		b = stim_now();
		c_mark = MIN(c_mark, b - a);

		/* A table with one free row: the add stores the row. */
		scratch.n = CONFIG_LATBENCH_TAIL_N - 1U;
		a = stim_now();
		lat_tail_add(&scratch, &m, 0U, CONFIG_LATBENCH_TAIL_MIN_CYC + 1000U, 0U, 0U,
			     LAT_TAIL_NO_CTX);
		b = stim_now();
		c_store = MIN(c_store, b - a);

		/* Full table with low = MIN_CYC + 1000: a smaller sample is rejected. */
		a = stim_now();
		lat_tail_add(&scratch, &m, 0U, CONFIG_LATBENCH_TAIL_MIN_CYC, 0U, 0U,
			     LAT_TAIL_NO_CTX);
		b = stim_now();
		c_reject = MIN(c_reject, b - a);

		/* Full table, larger sample: replace a row and scan the table. */
		a = stim_now();
		lat_tail_add(&scratch, &m, 0U, CONFIG_LATBENCH_TAIL_MIN_CYC + 2000U, 0U, 0U,
			     LAT_TAIL_NO_CTX);
		b = stim_now();
		c_full = MIN(c_full, b - a);
		irq_unlock(key);
	}
	printk("LAT META tail_n=%u\n", CONFIG_LATBENCH_TAIL_N);
	printk("LAT META tail_min_cyc=%u\n", CONFIG_LATBENCH_TAIL_MIN_CYC);
	printk("LAT META tail_cost_empty_cyc=%u\n", c_empty);
	printk("LAT META tail_cost_mark_cyc=%u\n", c_mark);
	printk("LAT META tail_cost_reject_cyc=%u\n", c_reject);
	printk("LAT META tail_cost_store_cyc=%u\n", c_store);
	printk("LAT META tail_cost_full_cyc=%u\n", c_full);
}
