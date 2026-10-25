/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <string.h>
#include <zephyr/sys/printk.h>
#include <latbench/irqmask_table.h>

void irqmask_table_reset(struct irqmask_table *t)
{
	memset(t, 0, sizeof(*t));
}

static void site_name(const struct irqmask_site *s, char *buf, size_t len)
{
	const char *kind = s->kind == IRQMASK_KIND_ISR ? "isr" : "mask";

	if (s->ipsr == 0U) {
		snprintk(buf, len, "m4.%s.t.%08x", kind, s->pc);
	} else {
		snprintk(buf, len, "m4.%s.e%u.%08x", kind, s->ipsr, s->pc);
	}
}

static void site_print(const struct irqmask_site *s)
{
	char name[40];
	/* Mean in 1/100 cycles, as in lat_hist_print(). */
	uint64_t mean100 = s->count ? (s->sum * 100U) / s->count : 0U;

	site_name(s, name, sizeof(name));
	printk("LAT M4SITE %s kind=%s ipsr=%u pc=0x%08x end_pc=0x%08x n=%u sum=%llu min=%u max=%u\n",
	       name, s->kind == IRQMASK_KIND_ISR ? "isr" : "mask", s->ipsr, s->pc, s->max_end_pc,
	       s->count, s->sum, s->count ? s->min : 0U, s->max);
	printk("LAT HIST %s n=%u min=%u max=%u mean=%llu.%02llu overflow=%u invalid=0\n", name,
	       s->count, s->count ? s->min : 0U, s->max, mean100 / 100U, mean100 % 100U, s->over);
	for (uint32_t b = 0; b < IRQMASK_BINS; b++) {
		if (s->bins[b] == 0U) {
			continue;
		}
		if (irqmask_bin_width(b) == 1U) {
			printk("LAT BIN %u %u\n", irqmask_bin_lower(b), s->bins[b]);
		} else {
			printk("LAT CBIN %u %u %u\n", irqmask_bin_lower(b), s->bins[b],
			       irqmask_bin_width(b));
		}
	}
	if (s->over != 0U) {
		printk("LAT OVF %u %u\n", IRQMASK_TOP_LOG2, s->over);
	}
	printk("LAT END %s\n", name);
}

void irqmask_table_print(const struct irqmask_table *t)
{
	printk("LAT M4 BEGIN sites=%u used=%u dropped=%u bins=%u sub_bits=%u\n", IRQMASK_SITES,
	       t->used, t->dropped, IRQMASK_BINS, IRQMASK_SUB_BITS);
	for (uint32_t i = 0; i < IRQMASK_SITES; i++) {
		if (t->site[i].pc != 0U) {
			site_print(&t->site[i]);
		}
	}
	printk("LAT M4 END\n");
}
