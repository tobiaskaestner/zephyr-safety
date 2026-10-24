/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @file
 * @brief Cycle histogram for latency samples.
 *
 * Each value below CONFIG_LATBENCH_HIST_BINS has a bin of its own. If
 * CONFIG_LATBENCH_HIST_COARSE_BINS is not 0, the next values go into
 * coarse bins of 2^CONFIG_LATBENCH_HIST_COARSE_SHIFT cycles. A larger
 * value goes into the log2 overflow bin of its magnitude.
 *
 * A value of 2^31 or more is a negative difference: the event came before
 * its reference time. It is not a latency. lat_hist_add() only counts it
 * in invalid, and lat_phase_add() ignores it.
 *
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
	/** Samples of LAT_INVALID_MIN or more. They are not in count. */
	uint32_t invalid;
	uint32_t min;
	uint32_t max;
	uint64_t sum;
	uint32_t ovf_log2[32];
	uint32_t bins[CONFIG_LATBENCH_HIST_BINS];
#if CONFIG_LATBENCH_HIST_COARSE_BINS > 0
	uint32_t cbins[CONFIG_LATBENCH_HIST_COARSE_BINS];
#endif
};

/** The smallest invalid sample (a negative difference). */
#define LAT_INVALID_MIN 0x80000000U

#define LAT_HIST_COARSE_END                                                                        \
	(CONFIG_LATBENCH_HIST_BINS +                                                               \
	 ((uint32_t)CONFIG_LATBENCH_HIST_COARSE_BINS << CONFIG_LATBENCH_HIST_COARSE_SHIFT))

#define LAT_HIST_DEFINE(_var, _name) \
	struct lat_hist _var = {.name = (_name), .min = UINT32_MAX}

static inline void lat_hist_add(struct lat_hist *h, uint32_t v)
{
	if (v >= LAT_INVALID_MIN) {
		h->invalid++;
		return;
	}
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
#if CONFIG_LATBENCH_HIST_COARSE_BINS > 0
	} else if (v < LAT_HIST_COARSE_END) {
		h->cbins[(v - CONFIG_LATBENCH_HIST_BINS) >> CONFIG_LATBENCH_HIST_COARSE_SHIFT]++;
#endif
	} else {
		h->overflow++;
		h->ovf_log2[31 - __builtin_clz(v)]++;
	}
}

void lat_hist_reset(struct lat_hist *h);

/**
 * Samples by the tick phase of their stimulus edge. Bin b holds the
 * phases [b * period / BINS, (b + 1) * period / BINS). Set period with
 * lat_phase_init() before the first lat_phase_add(). While period is 0,
 * lat_phase_add() does nothing.
 */
struct lat_phase {
	const char *name;
	uint32_t period;
	uint32_t count[CONFIG_LATBENCH_PHASE_BINS];
	uint32_t min[CONFIG_LATBENCH_PHASE_BINS];
	uint32_t max[CONFIG_LATBENCH_PHASE_BINS];
	uint64_t sum[CONFIG_LATBENCH_PHASE_BINS];
};

#define LAT_PHASE_DEFINE(_var, _name) struct lat_phase _var = {.name = (_name)}

/** The largest period for which phase * BINS fits in 32 bits. */
#define LAT_PHASE_PERIOD_MAX ((uint32_t)(UINT32_MAX / CONFIG_LATBENCH_PHASE_BINS))

/**
 * Set the period of the phase histogram. A period larger than
 * LAT_PHASE_PERIOD_MAX prints "LAT ERROR" and sets period to 0, so that
 * the histogram stays empty.
 */
void lat_phase_init(struct lat_phase *p, uint32_t period);

/** Add the sample v at this phase. phase must be less than period. */
static inline void lat_phase_add(struct lat_phase *p, uint32_t phase, uint32_t v)
{
	if (p->period == 0U || v >= LAT_INVALID_MIN) {
		return;
	}

	/* phase < period <= LAT_PHASE_PERIOD_MAX, so phase * BINS fits in 32 bits. */
	uint32_t b = phase * CONFIG_LATBENCH_PHASE_BINS / p->period;

	if (p->count[b] == 0U || v < p->min[b]) {
		p->min[b] = v;
	}
	if (v > p->max[b]) {
		p->max[b] = v;
	}
	p->count[b]++;
	p->sum[b] += v;
}

/** Print the phase histogram in the LAT line format (see scripts/latbench.py). */
void lat_phase_print(const struct lat_phase *p);

/** Print the histogram in the LAT line format (see scripts/latbench.py). */
void lat_hist_print(const struct lat_hist *h);

#endif /* LATBENCH_HIST_H_ */
