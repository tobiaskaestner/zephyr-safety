/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @file
 * @brief Cycle histogram for latency samples.
 *
 * Each value below CONFIG_LATBENCH_HIST_BINS has a bin of its own. A
 * larger value goes into the log2 overflow bin of its magnitude.
 * lat_hist_add() is safe to call from an ISR, but not from two contexts
 * at the same time for the same histogram.
 */

#ifndef LATBENCH_HIST_H_
#define LATBENCH_HIST_H_

#include <stdint.h>

struct lat_hist {
	const char *name;
	uint32_t count;
	uint32_t overflow;
	uint32_t min;
	uint32_t max;
	uint64_t sum;
	uint32_t ovf_log2[32];
	uint32_t bins[CONFIG_LATBENCH_HIST_BINS];
};

#define LAT_HIST_DEFINE(_var, _name) \
	struct lat_hist _var = {.name = (_name), .min = UINT32_MAX}

static inline void lat_hist_add(struct lat_hist *h, uint32_t v)
{
	h->count++;
	h->sum += v;
	if (v < h->min) {
		h->min = v;
	}
	if (v > h->max) {
		h->max = v;
	}
	if (v < CONFIG_LATBENCH_HIST_BINS) {
		h->bins[v]++;
	} else {
		h->overflow++;
		h->ovf_log2[31 - __builtin_clz(v)]++;
	}
}

void lat_hist_reset(struct lat_hist *h);

/** Print the histogram in the LAT line format (see scripts/latbench.py). */
void lat_hist_print(const struct lat_hist *h);

#endif /* LATBENCH_HIST_H_ */
