/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Unit tests for the M4 site table (common/include/latbench/irqmask_table.h,
 * common/src/irqmask_table.c). The hooks and the DWT code
 * (common/src/irqmask.c) need the Zephyr branch with the hooks and a
 * Cortex-M CPU; they are not in this test.
 *
 * The expected bin layout comes from the documented formula, written again
 * here, not from the code under test.
 */

#include <stdio.h>
#include <string.h>
#include <zephyr/ztest.h>
#include <zephyr/sys/printk-hooks.h>
#include <latbench/irqmask_table.h>

#define S     ((uint32_t)CONFIG_LATBENCH_IRQMASK_SUB_BITS)
#define TOP   (1U << IRQMASK_TOP_LOG2)

static struct irqmask_table tab;

/* Reference: the lower edge and the width of the bin of v (v < TOP). */
static void ref_bin(uint32_t v, uint32_t *lower, uint32_t *width)
{
	if (v < (2U << S)) {
		*lower = v;
		*width = 1U;
		return;
	}

	uint32_t k = 0;

	while ((v >> (k + 1U)) != 0U) {
		k++;
	}
	*width = 1U << (k - S);
	*lower = v & ~(*width - 1U);
}

static void before(void *f)
{
	ARG_UNUSED(f);
	irqmask_table_reset(&tab);
}

/* ------------------------------------------------------------------ bins */

ZTEST(irqmask_bins, test_layout_literals)
{
	zassert_equal(IRQMASK_EXACT, 2U << S);
	zassert_equal(IRQMASK_BINS, (2U << S) + (15U - S) * (1U << S));
	if (S == 3U) {
		zassert_equal(IRQMASK_BINS, 112U);
	}
}

ZTEST(irqmask_bins, test_every_value)
{
	for (uint32_t v = 0; v < TOP; v++) {
		uint32_t b = irqmask_bin(v);
		uint32_t lo, w;

		ref_bin(v, &lo, &w);
		zassert_true(b < IRQMASK_BINS, "v=%u b=%u", v, b);
		zassert_equal(irqmask_bin_lower(b), lo, "v=%u b=%u", v, b);
		zassert_equal(irqmask_bin_width(b), w, "v=%u b=%u", v, b);
	}
}

ZTEST(irqmask_bins, test_contiguous)
{
	zassert_equal(irqmask_bin_lower(0), 0U);
	for (uint32_t b = 0; b + 1U < IRQMASK_BINS; b++) {
		zassert_equal(irqmask_bin_lower(b + 1U),
			      irqmask_bin_lower(b) + irqmask_bin_width(b), "b=%u", b);
		zassert_true(irqmask_bin_width(b) <= irqmask_bin_width(b + 1U));
	}
	zassert_equal(irqmask_bin_lower(IRQMASK_BINS - 1U) + irqmask_bin_width(IRQMASK_BINS - 1U),
		      TOP);
}

ZTEST(irqmask_bins, test_over)
{
	zassert_equal(irqmask_bin(TOP), IRQMASK_BINS);
	zassert_equal(irqmask_bin(TOP + 12345U), IRQMASK_BINS);
	zassert_equal(irqmask_bin(UINT32_MAX), IRQMASK_BINS);
	zassert_equal(irqmask_bin(TOP - 1U), IRQMASK_BINS - 1U);
}

ZTEST(irqmask_bins, test_resolution)
{
	/* No bin is wider than 1/2^S of its lower edge. */
	for (uint32_t b = IRQMASK_EXACT; b < IRQMASK_BINS; b++) {
		zassert_true(irqmask_bin_width(b) << S <= irqmask_bin_lower(b), "b=%u", b);
	}
}

ZTEST_SUITE(irqmask_bins, NULL, NULL, NULL, NULL, NULL);

/* ----------------------------------------------------------------- table */

ZTEST(irqmask_table, test_new_site)
{
	struct irqmask_site *s = irqmask_find(&tab, 0x08001235U, 0U, IRQMASK_KIND_MASK);

	zassert_not_null(s);
	zassert_equal(s->pc, 0x08001235U);
	zassert_equal(s->count, 0U);
	zassert_equal(s->min, UINT32_MAX);
	zassert_equal(tab.used, 1U);
	zassert_equal_ptr(irqmask_find(&tab, 0x08001235U, 0U, IRQMASK_KIND_MASK), s);
	zassert_equal(tab.used, 1U);
}

ZTEST(irqmask_table, test_key_parts)
{
	struct irqmask_site *a = irqmask_find(&tab, 0x08001235U, 0U, IRQMASK_KIND_MASK);
	struct irqmask_site *b = irqmask_find(&tab, 0x08001235U, 15U, IRQMASK_KIND_MASK);
	struct irqmask_site *c = irqmask_find(&tab, 0x08001235U, 0U, IRQMASK_KIND_ISR);

	zassert_true(a != b && a != c && b != c);
	zassert_equal(tab.used, 3U);
}

ZTEST(irqmask_table, test_stats)
{
	static const uint32_t v[] = {40, 17, 900, 70000, 33};
	uint64_t sum = 0;

	for (size_t i = 0; i < ARRAY_SIZE(v); i++) {
		irqmask_add(&tab, 0x0800abcdU, 0U, IRQMASK_KIND_MASK, 0x0800ab00U + i, v[i]);
		sum += v[i];
	}

	struct irqmask_site *s = irqmask_find(&tab, 0x0800abcdU, 0U, IRQMASK_KIND_MASK);

	zassert_equal(s->count, ARRAY_SIZE(v));
	zassert_equal(s->sum, sum);
	zassert_equal(s->min, 17U);
	zassert_equal(s->max, 70000U);
	zassert_equal(s->max_end_pc, 0x0800ab03U);
	zassert_equal(s->over, 1U);

	uint32_t in_bins = 0;

	for (uint32_t b = 0; b < IRQMASK_BINS; b++) {
		in_bins += s->bins[b];
	}
	zassert_equal(in_bins, ARRAY_SIZE(v) - 1U);
	zassert_equal(s->bins[irqmask_bin(900U)], 1U);
}

ZTEST(irqmask_table, test_full)
{
	/* Fill all entries, then a new site counts only in dropped. */
	for (uint32_t i = 0; i < IRQMASK_SITES; i++) {
		irqmask_add(&tab, 0x08000001U + 2U * i, 0U, IRQMASK_KIND_MASK, 0U, 10U);
	}
	zassert_equal(tab.used, IRQMASK_SITES);
	zassert_equal(tab.dropped, 0U);
	zassert_is_null(irqmask_find(&tab, 0x09000001U, 0U, IRQMASK_KIND_MASK));
	irqmask_add(&tab, 0x09000001U, 0U, IRQMASK_KIND_MASK, 0U, 10U);
	zassert_equal(tab.dropped, 1U);
	/* A known site still works. */
	irqmask_add(&tab, 0x08000001U, 0U, IRQMASK_KIND_MASK, 0U, 20U);
	zassert_equal(irqmask_find(&tab, 0x08000001U, 0U, IRQMASK_KIND_MASK)->count, 2U);
	zassert_equal(tab.dropped, 1U);
}

ZTEST(irqmask_table, test_reset)
{
	irqmask_add(&tab, 0x08000001U, 0U, IRQMASK_KIND_MASK, 0U, 10U);
	irqmask_table_reset(&tab);
	zassert_equal(tab.used, 0U);
	for (uint32_t i = 0; i < IRQMASK_SITES; i++) {
		zassert_equal(tab.site[i].pc, 0U);
	}
}

ZTEST_SUITE(irqmask_table, NULL, NULL, before, NULL, NULL);

/* ----------------------------------------------------- printk capture */

static char cap[8192];
static size_t cap_len;
static bool cap_full;
static printk_hook_fn_t cap_prev;

static int cap_hook(int c)
{
	if (cap_len < sizeof(cap) - 1U) {
		cap[cap_len++] = (char)c;
	} else {
		cap_full = true;
	}
	return c;
}

static void cap_begin(void)
{
	cap_len = 0;
	cap_full = false;
	cap_prev = __printk_get_hook();
	__printk_hook_install(cap_hook);
}

static const char *cap_end(void)
{
	__printk_hook_install(cap_prev);
	cap[cap_len] = '\0';
	zassert_false(cap_full, "capture buffer full");
	return cap;
}

ZTEST(irqmask_print, test_empty)
{
	char want[96];

	cap_begin();
	irqmask_table_print(&tab);

	const char *out = cap_end();

	snprintf(want, sizeof(want), "LAT M4 BEGIN sites=%u used=0 dropped=0 bins=%u sub_bits=%u\n"
		 "LAT M4 END\n", IRQMASK_SITES, IRQMASK_BINS, S);
	zassert_str_equal(out, want);
}

ZTEST(irqmask_print, test_one_site)
{
	char want[512];

	irqmask_add(&tab, 0x0800abcdU, 0U, IRQMASK_KIND_MASK, 0x0800ac00U, 5U);
	irqmask_add(&tab, 0x0800abcdU, 0U, IRQMASK_KIND_MASK, 0x0800ac10U, 100U);
	irqmask_add(&tab, 0x0800abcdU, 0U, IRQMASK_KIND_MASK, 0x0800ac20U, 70000U);
	cap_begin();
	irqmask_table_print(&tab);

	const char *out = cap_end();
	uint32_t b = irqmask_bin(100U);

	snprintf(want, sizeof(want),
		 "LAT M4 BEGIN sites=%u used=1 dropped=0 bins=%u sub_bits=%u\n"
		 "LAT M4SITE m4.mask.t.0800abcd kind=mask ipsr=0 pc=0x0800abcd end_pc=0x0800ac20 "
		 "n=3 sum=70105 min=5 max=70000\n"
		 "LAT HIST m4.mask.t.0800abcd n=3 min=5 max=70000 mean=23368.33 overflow=1 "
		 "invalid=0\n"
		 "LAT BIN 5 1\n"
		 "LAT CBIN %u 1 %u\n"
		 "LAT OVF 16 1\n"
		 "LAT END m4.mask.t.0800abcd\n"
		 "LAT M4 END\n",
		 IRQMASK_SITES, IRQMASK_BINS, S, irqmask_bin_lower(b), irqmask_bin_width(b));
	zassert_str_equal(out, want);
}

ZTEST(irqmask_print, test_isr_name)
{
	irqmask_add(&tab, 0x08002001U, 15U, IRQMASK_KIND_ISR, 0U, 3U);
	cap_begin();
	irqmask_table_print(&tab);

	const char *out = cap_end();

	zassert_not_null(strstr(out, "LAT M4SITE m4.isr.e15.08002001 kind=isr ipsr=15 "));
	zassert_not_null(strstr(out, "LAT END m4.isr.e15.08002001\n"));
}

ZTEST_SUITE(irqmask_print, NULL, NULL, before, NULL, NULL);

/* ----------------------------------------------------------------- fixture */

/*
 * Print a run with pseudo-random values for four sites. The Python tests
 * (scripts/tests/test_m4.py) parse a saved copy of this output and compute
 * the same values with the same generator.
 */
#define FIX_SEED    0x9e3779b9U
#define FIX_SAMPLES 20000U

static uint32_t lcg(uint32_t *s)
{
	*s = *s * 1664525U + 1013904223U;
	return *s;
}

/* Sites: pc, ipsr, kind, range of the values. */
static const struct {
	uint32_t pc;
	uint32_t ipsr;
	uint32_t kind;
	uint32_t span;
} fix_site[] = {
	{0x08001001U, 0U, IRQMASK_KIND_MASK, 200U},
	{0x08001101U, 15U, IRQMASK_KIND_MASK, 8000U},
	{0x08002201U, 14U, IRQMASK_KIND_MASK, 40U},
	{0x08003301U, 15U, IRQMASK_KIND_ISR, 80000U},
};

ZTEST(irqmask_zfixture, test_emit_fixture)
{
	uint32_t s = FIX_SEED;

	for (uint32_t i = 0; i < FIX_SAMPLES; i++) {
		uint32_t k = (lcg(&s) >> 24) % ARRAY_SIZE(fix_site);
		uint32_t v = 12U + (lcg(&s) >> 8) % fix_site[k].span;

		irqmask_add(&tab, fix_site[k].pc, fix_site[k].ipsr, fix_site[k].kind,
			    fix_site[k].pc + 0x40U, v);
	}
	printk("LAT BEGIN\n");
	printk("LAT META test=irqmask_unit\n");
	printk("LAT META seed=%u\n", FIX_SEED);
	printk("LAT META samples=%u\n", FIX_SAMPLES);
	printk("LAT META m4=1\n");
	printk("LAT META m4_floor_cyc=12\n");
	printk("LAT META m4_pair_cost_cyc=60\n");
	printk("LAT META m4_isr_floor_cyc=12\n");
	printk("LAT META m4_window_cyc=170000000\n");
	irqmask_table_print(&tab);
	printk("LAT DONE\n");
	zassert_equal(tab.used, ARRAY_SIZE(fix_site));
}

ZTEST_SUITE(irqmask_zfixture, NULL, NULL, before, NULL, NULL);
