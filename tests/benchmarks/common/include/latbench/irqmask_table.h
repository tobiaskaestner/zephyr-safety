/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @file
 * @brief Site table of the M4 measurement (interrupt mask time per call site).
 *
 * The table has one entry for each site. A site is a call site address
 * (pc), the exception number at the start (ipsr, 0 in a thread) and a
 * kind: a mask section (IRQMASK_KIND_MASK) or an ISR body
 * (IRQMASK_KIND_ISR). Each entry has count, sum, min, max, the end
 * address of the longest section and a histogram.
 *
 * Histogram bins (s = CONFIG_LATBENCH_IRQMASK_SUB_BITS):
 *
 * - values below 2^(s+1) have a bin of 1 cycle each;
 * - each octave [2^k, 2^(k+1)), k = s+1 .. 15, has 2^s bins of
 *   2^(k-s) cycles;
 * - values of 2^16 cycles or more only count in "over" (and in max).
 *
 * With s = 3: 16 bins of 1 cycle, then 8 bins in each octave up to 65535
 * cycles (12.5 % of the value or less), 112 bins in total.
 *
 * The code here has no hardware access, so that the unit test can run
 * it on native_sim. The caller must make sure that no two contexts
 * change the table at the same time (the hooks call it with the
 * interrupts masked).
 */

#ifndef LATBENCH_IRQMASK_TABLE_H_
#define LATBENCH_IRQMASK_TABLE_H_

#include <stdbool.h>
#include <stdint.h>

#define IRQMASK_SUB_BITS  CONFIG_LATBENCH_IRQMASK_SUB_BITS
#define IRQMASK_SUB       (1U << IRQMASK_SUB_BITS)
/** Values below this have a bin of 1 cycle each. */
#define IRQMASK_EXACT     (2U << IRQMASK_SUB_BITS)
/** Values of 2^IRQMASK_TOP_LOG2 or more go to "over". */
#define IRQMASK_TOP_LOG2  16U
#define IRQMASK_BINS      (IRQMASK_EXACT + (IRQMASK_TOP_LOG2 - IRQMASK_SUB_BITS - 1U) * IRQMASK_SUB)
#define IRQMASK_SITES     (1U << CONFIG_LATBENCH_IRQMASK_SITES_LOG2)

enum irqmask_kind {
	IRQMASK_KIND_MASK = 0,
	IRQMASK_KIND_ISR = 1,
};

struct irqmask_site {
	/** Start site (return address of the hook call); 0: entry not used. */
	uint32_t pc;
	/** Exception number at the start (IPSR), 0 in a thread. */
	uint16_t ipsr;
	uint8_t kind;
	uint8_t reserved;
	uint32_t count;
	uint32_t min;
	uint32_t max;
	/** End site of the longest section (0 for an ISR body). */
	uint32_t max_end_pc;
	/** Number of values of 2^IRQMASK_TOP_LOG2 or more. */
	uint32_t over;
	uint64_t sum;
	uint32_t bins[IRQMASK_BINS];
};

struct irqmask_table {
	/** Number of sites in use. */
	uint32_t used;
	/** Values that had no entry, because the table was full. */
	uint32_t dropped;
	struct irqmask_site site[IRQMASK_SITES];
};

/** The bin of the value v, or IRQMASK_BINS if v is 2^IRQMASK_TOP_LOG2 or more. */
static inline uint32_t irqmask_bin(uint32_t v)
{
	if (v < IRQMASK_EXACT) {
		return v;
	}

	uint32_t k = 31U - (uint32_t)__builtin_clz(v);

	if (k >= IRQMASK_TOP_LOG2) {
		return IRQMASK_BINS;
	}
	return IRQMASK_EXACT + (k - IRQMASK_SUB_BITS - 1U) * IRQMASK_SUB +
	       ((v >> (k - IRQMASK_SUB_BITS)) & (IRQMASK_SUB - 1U));
}

/** The smallest value of bin b (b < IRQMASK_BINS). */
static inline uint32_t irqmask_bin_lower(uint32_t b)
{
	if (b < IRQMASK_EXACT) {
		return b;
	}

	uint32_t o = (b - IRQMASK_EXACT) / IRQMASK_SUB;
	uint32_t sub = (b - IRQMASK_EXACT) % IRQMASK_SUB;

	return (IRQMASK_SUB + sub) << (o + 1U);
}

/** The width of bin b in cycles (b < IRQMASK_BINS). */
static inline uint32_t irqmask_bin_width(uint32_t b)
{
	if (b < IRQMASK_EXACT) {
		return 1U;
	}
	return 1U << ((b - IRQMASK_EXACT) / IRQMASK_SUB + 1U);
}

/**
 * The entry of a site. A new site gets a free entry. Return NULL if the
 * site is new and the table is full.
 */
static inline struct irqmask_site *irqmask_find(struct irqmask_table *t, uint32_t pc,
						uint32_t ipsr, uint32_t kind)
{
	/* Knuth multiplicative hash of the address; open addressing. */
	uint32_t key = pc ^ (ipsr << 20) ^ (kind << 31);
	uint32_t i = (key * 2654435761U) >> (32U - CONFIG_LATBENCH_IRQMASK_SITES_LOG2);

	for (uint32_t n = 0; n < IRQMASK_SITES; n++) {
		struct irqmask_site *s = &t->site[i];

		if (s->pc == pc && s->ipsr == ipsr && s->kind == kind) {
			return s;
		}
		if (s->pc == 0U) {
			s->pc = pc;
			s->ipsr = (uint16_t)ipsr;
			s->kind = (uint8_t)kind;
			s->min = UINT32_MAX;
			t->used++;
			return s;
		}
		i = (i + 1U) & (IRQMASK_SITES - 1U);
	}
	return NULL;
}

/** Add the value v (cycles) to a site. pc must not be 0. */
static inline void irqmask_add(struct irqmask_table *t, uint32_t pc, uint32_t ipsr, uint32_t kind,
			       uint32_t end_pc, uint32_t v)
{
	struct irqmask_site *s = irqmask_find(t, pc, ipsr, kind);

	if (s == NULL) {
		t->dropped++;
		return;
	}
	s->count++;
	s->sum += v;
	if (v < s->min) {
		s->min = v;
	}
	if (v > s->max) {
		s->max = v;
		s->max_end_pc = end_pc;
	}

	uint32_t b = irqmask_bin(v);

	if (b < IRQMASK_BINS) {
		s->bins[b]++;
	} else {
		s->over++;
	}
}

void irqmask_table_reset(struct irqmask_table *t);

/**
 * Print each used site in the LAT line format (see scripts/m4.py):
 *
 *   LAT M4 BEGIN sites=.. used=.. dropped=.. bins=.. sub_bits=..
 *   LAT M4SITE <name> kind=mask|isr ipsr=.. pc=0x.. end_pc=0x.. n=.. sum=.. min=.. max=..
 *   LAT HIST <name> n=.. min=.. max=.. mean=.. overflow=.. invalid=0
 *   LAT BIN <cycles> <count>            (bins of 1 cycle)
 *   LAT CBIN <lower> <count> <width>    (wider bins)
 *   LAT OVF 16 <count>                  (values of 2^16 or more)
 *   LAT END <name>
 *   LAT M4 END
 *
 * <name> is m4.<kind>.<ctx>.<pc>, with ctx "t" for a thread or e<ipsr>.
 */
void irqmask_table_print(const struct irqmask_table *t);

#endif /* LATBENCH_IRQMASK_TABLE_H_ */
