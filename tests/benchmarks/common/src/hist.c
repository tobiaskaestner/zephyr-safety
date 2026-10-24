/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <string.h>
#include <zephyr/sys/printk.h>
#include <latbench/hist.h>

void lat_hist_reset(struct lat_hist *h)
{
	const char *name = h->name;

	memset(h, 0, sizeof(*h));
	h->name = name;
	h->min = UINT32_MAX;
}

void lat_hist_print(const struct lat_hist *h)
{
	/* Mean in 1/100 cycles, so that the output needs no float printk. */
	uint64_t mean100 = h->count ? (h->sum * 100U) / h->count : 0U;

	printk("LAT HIST %s n=%u min=%u max=%u mean=%llu.%02llu overflow=%u\n",
	       h->name, h->count, h->count ? h->min : 0U, h->max,
	       mean100 / 100U, mean100 % 100U, h->overflow);
	for (uint32_t v = 0; v < CONFIG_LATBENCH_HIST_BINS; v++) {
		if (h->bins[v] != 0U) {
			printk("LAT BIN %u %u\n", v, h->bins[v]);
		}
	}
#if CONFIG_LATBENCH_HIST_COARSE_BINS > 0
	/* A coarse bin: lower edge, count, width in cycles. */
	for (uint32_t b = 0; b < CONFIG_LATBENCH_HIST_COARSE_BINS; b++) {
		if (h->cbins[b] != 0U) {
			printk("LAT CBIN %u %u %u\n",
			       CONFIG_LATBENCH_HIST_BINS + (b << CONFIG_LATBENCH_HIST_COARSE_SHIFT),
			       h->cbins[b], 1U << CONFIG_LATBENCH_HIST_COARSE_SHIFT);
		}
	}
#endif
	for (uint32_t e = 0; e < 32; e++) {
		if (h->ovf_log2[e] != 0U) {
			printk("LAT OVF %u %u\n", e, h->ovf_log2[e]);
		}
	}
	printk("LAT END %s\n", h->name);
}

void lat_phase_print(const struct lat_phase *p)
{
	printk("LAT PHASE %s bins=%u period=%u\n", p->name, CONFIG_LATBENCH_PHASE_BINS, p->period);
	for (uint32_t b = 0; b < CONFIG_LATBENCH_PHASE_BINS; b++) {
		if (p->count[b] != 0U) {
			printk("LAT PB %u %u %u %u %llu\n", b, p->count[b], p->min[b], p->max[b],
			       p->sum[b]);
		}
	}
	printk("LAT END %s\n", p->name);
}
