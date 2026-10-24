/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Unit tests for the cycle histogram and the phase histogram of the
 * latency benchmarks (common/include/latbench/hist.h, common/src/hist.c).
 *
 * The expected values come from closed forms and from a reference model in
 * this file, not from the code under test. A test for a known defect or a
 * precondition gap asserts the correct behaviour and uses KNOWN_GAP(): it
 * skips while the defect is there, and it fails when the result becomes
 * correct, so that the marker is removed (a strict expected failure).
 */

#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <zephyr/ztest.h>
#include <zephyr/sys/printk-hooks.h>
#include <latbench/hist.h>

#define BINS   ((uint32_t)CONFIG_LATBENCH_HIST_BINS)
#define CBINS  ((uint32_t)CONFIG_LATBENCH_HIST_COARSE_BINS)
#define PBINS  ((uint32_t)CONFIG_LATBENCH_PHASE_BINS)
#define CWIDTH (1U << CONFIG_LATBENCH_HIST_COARSE_SHIFT)
/* The first value after the coarse region (BINS if there are no coarse bins). */
#define CEND   (BINS + CBINS * CWIDTH)

#define KNOWN_GAP(ok, ...)                                                                         \
	do {                                                                                       \
		if (!(ok)) {                                                                       \
			TC_PRINT("KNOWN GAP: " __VA_ARGS__);                                       \
			TC_PRINT("\n");                                                            \
			ztest_test_skip();                                                         \
		} else {                                                                           \
			zassert_unreachable("known gap is fixed, remove KNOWN_GAP: " __VA_ARGS__); \
		}                                                                                  \
	} while (0)

/* Reference model of the bin of a value. */
enum region {
	FINE,
	COARSE,
	OVF,
	INVALID, /* a negative difference: 2^31 or more */
};

struct loc {
	enum region r;
	uint32_t idx;
};

static uint32_t log2_floor(uint32_t v)
{
	uint32_t e = 0;

	while ((v >> e) > 1U) {
		e++;
	}
	return e;
}

static struct loc expect_loc(uint32_t v)
{
	if (v >= 0x80000000U) {
		return (struct loc){INVALID, 0};
	}
	if (v < BINS) {
		return (struct loc){FINE, v};
	}
	if (v < CEND) {
		return (struct loc){COARSE, (v - BINS) / CWIDTH};
	}
	return (struct loc){OVF, log2_floor(v)};
}

static LAT_HIST_DEFINE(h, "t");

/* An empty histogram, made without lat_hist_reset() (it has its own test). */
static void fresh(struct lat_hist *x, const char *name)
{
	memset(x, 0, sizeof(*x));
	x->name = name;
	x->min = UINT32_MAX;
}

static uint32_t cbin(const struct lat_hist *x, uint32_t i)
{
#if CONFIG_LATBENCH_HIST_COARSE_BINS > 0
	return x->cbins[i];
#else
	ARG_UNUSED(x);
	ARG_UNUSED(i);
	return 0;
#endif
}

/* Check that the histogram holds n samples of v and nothing else. */
static void check_only(const struct lat_hist *x, uint32_t v, uint32_t n)
{
	struct loc l = expect_loc(v);

	for (uint32_t i = 0; i < BINS; i++) {
		zassert_equal(x->bins[i], (l.r == FINE && l.idx == i) ? n : 0U,
			      "v=%u: bins[%u]=%u", v, i, x->bins[i]);
	}
	for (uint32_t i = 0; i < CBINS; i++) {
		zassert_equal(cbin(x, i), (l.r == COARSE && l.idx == i) ? n : 0U,
			      "v=%u: cbins[%u]=%u", v, i, cbin(x, i));
	}
	for (uint32_t e = 0; e < 32; e++) {
		zassert_equal(x->ovf_log2[e], (l.r == OVF && l.idx == e) ? n : 0U,
			      "v=%u: ovf_log2[%u]=%u", v, e, x->ovf_log2[e]);
	}
	zassert_equal(x->overflow, l.r == OVF ? n : 0U, "v=%u: overflow=%u", v, x->overflow);
	zassert_equal(x->count, l.r == INVALID ? 0U : n, "v=%u: count=%u", v, x->count);
	zassert_equal(x->invalid, l.r == INVALID ? n : 0U, "v=%u: invalid=%u", v, x->invalid);
}

static void add_one_check(uint32_t v)
{
	fresh(&h, "t");
	lat_hist_add(&h, v);
	check_only(&h, v, 1);
	if (expect_loc(v).r == INVALID) {
		/* An invalid sample does not change the stats. */
		zassert_equal(h.min, UINT32_MAX, "v=0x%x", v);
		zassert_equal(h.max, 0, "v=0x%x", v);
		zassert_equal(h.sum, 0, "v=0x%x", v);
	} else {
		zassert_equal(h.min, v);
		zassert_equal(h.max, v);
		zassert_equal(h.sum, (uint64_t)v);
	}
}

/* ---------------------------------------------------------------- lat_hist */

ZTEST(lat_hist, test_model_literals)
{
	/* Pin the reference model to literal values, so that a fault in the
	 * model cannot hide a fault in the code.
	 */
	zassert_equal(log2_floor(1), 0);
	zassert_equal(log2_floor(2), 1);
	zassert_equal(log2_floor(3), 1);
	zassert_equal(log2_floor(4096), 12);
	zassert_equal(log2_floor(67584), 16);
	zassert_equal(log2_floor(0x7fffffffU), 30);
	zassert_equal(log2_floor(0x80000000U), 31);
	zassert_equal(log2_floor(UINT32_MAX), 31);
}

ZTEST(lat_hist, test_boundaries)
{
	const uint32_t vals[] = {
		0, 1, BINS - 1, BINS, BINS + 1, CEND - 1, CEND, CEND + 1,
		BINS + CWIDTH - 1, BINS + CWIDTH,
		0x7fffffffU, 0x80000000U, 0x80000001U, UINT32_MAX - 1, UINT32_MAX,
	};

	for (size_t i = 0; i < ARRAY_SIZE(vals); i++) {
		add_one_check(vals[i]);
	}

	/* The same, with literal bins. */
	add_one_check(0);
	zassert_equal(h.bins[0], 1);
	add_one_check(BINS - 1);
	zassert_equal(h.bins[BINS - 1], 1);
	add_one_check(UINT32_MAX);
	zassert_equal(h.invalid, 1);
	zassert_equal(h.count, 0);
	zassert_equal(h.ovf_log2[31], 0);
	add_one_check(0x80000000U);
	zassert_equal(h.invalid, 1);
	zassert_equal(h.count, 0);
	zassert_equal(h.ovf_log2[31], 0);
	add_one_check(0x7fffffffU);
	zassert_equal(h.invalid, 0);
	zassert_equal(h.count, 1);
	zassert_equal(h.ovf_log2[30], 1);
#if CONFIG_LATBENCH_HIST_COARSE_BINS > 0
	add_one_check(BINS);
	zassert_equal(h.cbins[0], 1);
	add_one_check(BINS + CWIDTH - 1);
	zassert_equal(h.cbins[0], 1);
	add_one_check(BINS + CWIDTH);
	zassert_equal(h.cbins[1], 1);
	add_one_check(CEND - 1);
	zassert_equal(h.cbins[CBINS - 1], 1);
	add_one_check(CEND);
	zassert_equal(h.overflow, 1);
	zassert_equal(h.ovf_log2[log2_floor(CEND)], 1);
#else
	add_one_check(BINS);
	zassert_equal(h.overflow, 1);
	zassert_equal(h.ovf_log2[log2_floor(BINS)], 1);
#endif
}

ZTEST(lat_hist, test_config_literals)
{
	/* The first overflow bin of the configurations in testcase.yaml. */
	if (BINS == 4096 && CBINS == 0) {
		add_one_check(4096);
		zassert_equal(h.ovf_log2[12], 1);
	} else if (BINS == 16 && CBINS == 4 && CWIDTH == 4) {
		/* 16 fine bins, coarse bins [16,20) [20,24) [24,28) [28,32). */
		add_one_check(19);
		zassert_equal(cbin(&h, 0), 1);
		add_one_check(20);
		zassert_equal(cbin(&h, 1), 1);
		add_one_check(31);
		zassert_equal(cbin(&h, 3), 1);
		add_one_check(32);
		zassert_equal(h.ovf_log2[5], 1);
	} else if (BINS == 2048 && CBINS == 2048 && CWIDTH == 32) {
		/* The Kconfig help: 0 to 67583 cycles. */
		add_one_check(67583);
		zassert_equal(cbin(&h, 2047), 1);
		add_one_check(67584);
		zassert_equal(h.ovf_log2[16], 1);
	} else {
		ztest_test_skip();
	}
}

ZTEST(lat_hist, test_log2_index)
{
	for (uint32_t e = 0; e < 32; e++) {
		uint32_t lo = 1U << e;
		uint32_t hi = (e == 31) ? UINT32_MAX : (2U << e) - 1U;
		const uint32_t vals[] = {lo, lo + (hi - lo) / 2U, hi};

		for (size_t i = 0; i < ARRAY_SIZE(vals); i++) {
			if (vals[i] < CEND) {
				continue;
			}
			fresh(&h, "t");
			lat_hist_add(&h, vals[i]);
			if (e == 31) {
				/* 2^31 and more: invalid, not in ovf_log2[31]. */
				zassert_equal(h.ovf_log2[31], 0, "v=0x%x", vals[i]);
				zassert_equal(h.overflow, 0);
				zassert_equal(h.invalid, 1);
				continue;
			}
			zassert_equal(h.ovf_log2[e], 1, "v=0x%x e=%u", vals[i], e);
			zassert_equal(h.overflow, 1);
			zassert_equal(h.invalid, 0);
		}
	}
}

/* Each value from 0 to 4 * CEND + 64, then 2^k - 1, 2^k, 2^k + 1 for all k. */
static uint32_t exp_bins[CONFIG_LATBENCH_HIST_BINS];
#if CONFIG_LATBENCH_HIST_COARSE_BINS > 0
static uint32_t exp_cbins[CONFIG_LATBENCH_HIST_COARSE_BINS];
#endif
static uint32_t exp_ovf[32];
static uint32_t exp_invalid;

static void sweep_add(uint32_t v, uint64_t *sum, uint32_t *n)
{
	struct loc l = expect_loc(v);

	lat_hist_add(&h, v);
	if (l.r == INVALID) {
		exp_invalid++;
		return;
	}
	*sum += v;
	(*n)++;
	if (l.r == FINE) {
		exp_bins[l.idx]++;
#if CONFIG_LATBENCH_HIST_COARSE_BINS > 0
	} else if (l.r == COARSE) {
		exp_cbins[l.idx]++;
#endif
	} else {
		exp_ovf[l.idx]++;
	}
}

ZTEST(lat_hist, test_sweep)
{
	uint64_t sum = 0;
	uint32_t n = 0;
	uint64_t total = 0;
	uint32_t ovf = 0;

	fresh(&h, "t");
	memset(exp_bins, 0, sizeof(exp_bins));
#if CONFIG_LATBENCH_HIST_COARSE_BINS > 0
	memset(exp_cbins, 0, sizeof(exp_cbins));
#endif
	memset(exp_ovf, 0, sizeof(exp_ovf));
	exp_invalid = 0;

	for (uint32_t v = 0; v <= 4U * CEND + 64U; v++) {
		sweep_add(v, &sum, &n);
	}
	for (uint32_t k = 1; k < 32; k++) {
		sweep_add((1U << k) - 1U, &sum, &n);
		sweep_add(1U << k, &sum, &n);
		sweep_add((1U << k) + 1U, &sum, &n);
	}
	sweep_add(UINT32_MAX, &sum, &n);
	zassert_equal(exp_invalid, 3, "2^31, 2^31 + 1, UINT32_MAX");

	for (uint32_t i = 0; i < BINS; i++) {
		zassert_equal(h.bins[i], exp_bins[i], "bins[%u]", i);
		total += h.bins[i];
	}
#if CONFIG_LATBENCH_HIST_COARSE_BINS > 0
	for (uint32_t i = 0; i < CBINS; i++) {
		zassert_equal(h.cbins[i], exp_cbins[i], "cbins[%u]", i);
		/* A full coarse bin has CWIDTH values of the linear sweep. */
		zassert_true(h.cbins[i] >= CWIDTH, "cbins[%u]=%u", i, h.cbins[i]);
		total += h.cbins[i];
	}
#endif
	for (uint32_t e = 0; e < 32; e++) {
		zassert_equal(h.ovf_log2[e], exp_ovf[e], "ovf_log2[%u]", e);
		ovf += h.ovf_log2[e];
	}
	/* No overflow bin below the coarse region has a sample. */
	for (uint32_t e = 0; e < log2_floor(CEND); e++) {
		zassert_equal(h.ovf_log2[e], 0, "ovf_log2[%u]", e);
	}
	zassert_equal(h.overflow, ovf);
	zassert_equal(h.count, n);
	zassert_equal(h.invalid, exp_invalid);
	zassert_equal(total + ovf, (uint64_t)n, "each valid sample is in exactly one bin");
	zassert_equal(h.sum, sum);
	zassert_equal(h.min, 0);
	zassert_equal(h.max, 0x7fffffffU, "the largest valid sample");
}

ZTEST(lat_hist, test_count_sum_min_max)
{
	fresh(&h, "t");
	lat_hist_add(&h, 7);
	zassert_equal(h.count, 1);
	zassert_equal(h.min, 7, "min after the first sample");
	zassert_equal(h.max, 7);
	zassert_equal(h.sum, 7);

	lat_hist_add(&h, 3);
	zassert_equal(h.min, 3);
	zassert_equal(h.max, 7);

	lat_hist_add(&h, 100000);
	zassert_equal(h.min, 3);
	zassert_equal(h.max, 100000);

	/* The sum is 64 bits wide and does not wrap at 2^32. */
	lat_hist_add(&h, 0x7fffffffU);
	lat_hist_add(&h, 0x7fffffffU);
	lat_hist_add(&h, 0x7fffffffU);
	zassert_equal(h.count, 6);
	zassert_equal(h.sum, 7ULL + 3ULL + 100000ULL + 3ULL * 0x7fffffffU);
	zassert_equal(h.max, 0x7fffffffU);
	zassert_equal(h.min, 3);
	zassert_equal(h.invalid, 0);
}

ZTEST(lat_hist, test_invalid_samples)
{
	/* A first invalid sample does not set min or max. */
	fresh(&h, "t");
	lat_hist_add(&h, UINT32_MAX);
	zassert_equal(h.invalid, 1);
	zassert_equal(h.count, 0);
	zassert_equal(h.min, UINT32_MAX);
	zassert_equal(h.max, 0);

	/* Invalid samples between valid ones change only invalid. */
	lat_hist_add(&h, 2);
	lat_hist_add(&h, 0x80000000U);
	lat_hist_add(&h, 1);
	lat_hist_add(&h, 0x80000001U);
	lat_hist_add(&h, 0x7fffffffU);
	zassert_equal(h.invalid, 3);
	zassert_equal(h.count, 3);
	zassert_equal(h.sum, 3ULL + 0x7fffffffU);
	zassert_equal(h.min, 1);
	zassert_equal(h.max, 0x7fffffffU);
	zassert_equal(h.bins[1], 1);
	zassert_equal(h.bins[2], 1);
	/* 2^31 - 1 is the largest valid sample: it is in ovf_log2[30]. */
	zassert_equal(h.overflow, 1);
	zassert_equal(h.ovf_log2[30], 1);
	zassert_equal(h.ovf_log2[31], 0);
}

ZTEST(lat_hist, test_first_sample_extremes)
{
	/* A first sample of the largest valid value is the min. */
	fresh(&h, "t");
	lat_hist_add(&h, 0x7fffffffU);
	zassert_equal(h.min, 0x7fffffffU);
	zassert_equal(h.max, 0x7fffffffU);
	lat_hist_add(&h, 0);
	zassert_equal(h.min, 0);
	zassert_equal(h.max, 0x7fffffffU);

	/* A first sample of 0 is the max. */
	fresh(&h, "t");
	lat_hist_add(&h, 0);
	zassert_equal(h.min, 0);
	zassert_equal(h.max, 0);
}

ZTEST(lat_hist, test_define)
{
	static LAT_HIST_DEFINE(d, "defined");

	zassert_str_equal(d.name, "defined");
	zassert_equal(d.min, UINT32_MAX);
	zassert_equal(d.count, 0);
	lat_hist_add(&d, 42);
	zassert_equal(d.min, 42);
}

ZTEST(lat_hist, test_reset_keeps_name)
{
	static const char name[] = "keep";

	fresh(&h, name);
	lat_hist_add(&h, 0);
	lat_hist_add(&h, BINS - 1);
	lat_hist_add(&h, CEND - 1);
	lat_hist_add(&h, 0x7fffffffU);
	lat_hist_add(&h, UINT32_MAX);
	zassert_equal(h.invalid, 1);

	lat_hist_reset(&h);

	zassert_equal_ptr(h.name, name, "reset keeps the name pointer");
	zassert_equal(h.count, 0);
	zassert_equal(h.invalid, 0);
	zassert_equal(h.overflow, 0);
	zassert_equal(h.sum, 0);
	zassert_equal(h.max, 0);
	zassert_equal(h.min, UINT32_MAX);
	for (uint32_t i = 0; i < BINS; i++) {
		zassert_equal(h.bins[i], 0);
	}
	for (uint32_t i = 0; i < CBINS; i++) {
		zassert_equal(cbin(&h, i), 0);
	}
	for (uint32_t e = 0; e < 32; e++) {
		zassert_equal(h.ovf_log2[e], 0);
	}

	lat_hist_add(&h, 9);
	zassert_equal(h.min, 9, "min after reset and one sample");
	zassert_equal(h.max, 9);
	check_only(&h, 9, 1);
}

ZTEST_SUITE(lat_hist, NULL, NULL, NULL, NULL, NULL);

/* ----------------------------------------------------- printk capture */

static char cap[16384];
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

/* Expected text, built in parts. */
static char want[16384];
static size_t want_len;

static void want_reset(void)
{
	want_len = 0;
	want[0] = '\0';
}

static void want_add(const char *fmt, ...)
{
	va_list ap;

	va_start(ap, fmt);
	want_len += vsnprintf(want + want_len, sizeof(want) - want_len, fmt, ap);
	va_end(ap);
	zassert_true(want_len < sizeof(want));
}

static void assert_text(const char *got, const char *exp)
{
	if (strcmp(got, exp) != 0) {
		TC_PRINT("got:\n%s\nexpected:\n%s\n", got, exp);
	}
	zassert_str_equal(got, exp);
}

/* --------------------------------------------------------------- lat_phase */

/* A guard after the phase histogram detects a write after its end. */
static struct {
	struct lat_phase p;
	uint64_t guard[4];
} ph;

static void phase_fresh(uint32_t period)
{
	memset(&ph, 0, sizeof(ph));
	ph.p.name = "ph";
	lat_phase_init(&ph.p, period);
}

static uint32_t ceil_div(uint64_t a, uint64_t b)
{
	return (uint32_t)((a + b - 1U) / b);
}

/*
 * Add each phase of [0, period) with the phase as the value. Then bin b
 * must hold the phases from ceil(b * P / BINS) to ceil((b + 1) * P / BINS) - 1.
 */
static void check_all_phases(uint32_t period)
{
	uint64_t total = 0;

	phase_fresh(period);
	for (uint32_t phase = 0; phase < period; phase++) {
		lat_phase_add(&ph.p, phase, phase);
	}
	for (uint32_t b = 0; b < PBINS; b++) {
		uint32_t lo = ceil_div((uint64_t)b * period, PBINS);
		uint32_t end = ceil_div((uint64_t)(b + 1U) * period, PBINS);
		uint32_t n = end - lo;

		zassert_equal(ph.p.count[b], n, "P=%u b=%u count=%u", period, b, ph.p.count[b]);
		total += ph.p.count[b];
		if (n == 0U) {
			continue;
		}
		zassert_equal(ph.p.min[b], lo, "P=%u b=%u min=%u", period, b, ph.p.min[b]);
		zassert_equal(ph.p.max[b], end - 1U, "P=%u b=%u max=%u", period, b, ph.p.max[b]);
		zassert_equal(ph.p.sum[b], ((uint64_t)lo + end - 1U) * n / 2U, "P=%u b=%u sum", period,
			      b);
	}
	zassert_equal(total, period, "P=%u: each phase is in exactly one bin", period);
	for (size_t i = 0; i < ARRAY_SIZE(ph.guard); i++) {
		zassert_equal(ph.guard[i], 0);
	}
}

/* Return the bin that one sample at this phase goes to. */
static uint32_t bin_of(uint32_t period, uint32_t phase)
{
	uint32_t found = UINT32_MAX;

	phase_fresh(period);
	lat_phase_add(&ph.p, phase, 1);
	for (uint32_t b = 0; b < PBINS; b++) {
		if (ph.p.count[b] != 0U) {
			zassert_equal(found, UINT32_MAX, "two bins changed");
			found = b;
		}
	}
	return found;
}

ZTEST(lat_phase, test_all_phases)
{
	/* Tick periods of the targets at 10000 ticks/s and 1000 ticks/s, odd
	 * periods and periods near the bin count.
	 */
	const uint32_t periods[] = {
		17000,  /* STM32G474, 170 MHz */
		6400,   /* nRF52840, 64 MHz */
		12800,  /* nRF54L15, 128 MHz */
		60000,  /* i.MX RT1060, 600 MHz */
		170000, 600000, 17001, 16999, 1, 2, 3,
		PBINS - 1U, PBINS, PBINS + 1U, 2U * PBINS - 1U,
	};

	for (size_t i = 0; i < ARRAY_SIZE(periods); i++) {
		if (periods[i] > 0U) {
			check_all_phases(periods[i]);
		}
	}
}

ZTEST(lat_phase, test_bin_edges)
{
	const uint32_t periods[] = {17000, 600000, 6000000, 60000000};

	for (size_t i = 0; i < ARRAY_SIZE(periods); i++) {
		uint32_t P = periods[i];

		zassert_equal(bin_of(P, 0), 0, "P=%u phase 0", P);
		zassert_equal(bin_of(P, P - 1U), PBINS - 1U, "P=%u phase P-1", P);
		for (uint32_t b = 1; b < PBINS; b++) {
			uint32_t edge = ceil_div((uint64_t)b * P, PBINS);

			zassert_equal(bin_of(P, edge), b, "P=%u phase %u", P, edge);
			zassert_equal(bin_of(P, edge - 1U), b - 1U, "P=%u phase %u", P, edge - 1U);
		}
	}
	/* Literal edges: 17000 cycles in 64 bins are 265.625 cycles wide. */
	if (PBINS == 64) {
		zassert_equal(bin_of(17000, 265), 0);
		zassert_equal(bin_of(17000, 266), 1);
		zassert_equal(bin_of(17000, 16734), 62);
		zassert_equal(bin_of(17000, 16735), 63);
		/* 600000 cycles in 64 bins are 9375 cycles wide. */
		zassert_equal(bin_of(600000, 9374), 0);
		zassert_equal(bin_of(600000, 9375), 1);
		zassert_equal(bin_of(600000, 599999), 63);
	}
}

ZTEST(lat_phase, test_period_limit)
{
	/* phase * BINS fits in 32 bits up to period UINT32_MAX / BINS. */
	uint32_t pmax = UINT32_MAX / PBINS;

	if (PBINS == 64U) {
		zassert_equal(pmax, 67108863);
	}

	/* The largest period: no error, and its last phase is in the last bin. */
	cap_begin();
	phase_fresh(pmax);
	assert_text(cap_end(), "");
	zassert_equal(ph.p.period, pmax);
	zassert_equal(bin_of(pmax, pmax - 1U), PBINS - 1U);
	zassert_equal(bin_of(pmax, 0), 0);

	/* A larger period prints LAT ERROR and leaves the histogram empty. */
	cap_begin();
	phase_fresh(pmax + 1U);
	cap_end();
	want_reset();
	want_add("LAT ERROR phase ph period=%u is larger than %u\n", pmax + 1U, pmax);
	assert_text(cap, want);
	zassert_equal(ph.p.period, 0);
	lat_phase_add(&ph.p, 0, 5);
	lat_phase_add(&ph.p, pmax, 5);
	for (uint32_t b = 0; b < PBINS; b++) {
		zassert_equal(ph.p.count[b], 0, "bin %u", b);
	}
	for (size_t i = 0; i < ARRAY_SIZE(ph.guard); i++) {
		zassert_equal(ph.guard[i], 0);
	}

	cap_begin();
	phase_fresh(UINT32_MAX);
	cap_end();
	zassert_equal(ph.p.period, 0);
	zassert_not_null(strstr(cap, "LAT ERROR phase ph period=4294967295 "));
}

ZTEST(lat_phase, test_add_before_init)
{
	/* period is 0 before lat_phase_init(): lat_phase_add() does nothing. */
	static LAT_PHASE_DEFINE(d, "noinit");

	lat_phase_add(&d, 0, 5);
	lat_phase_add(&d, 100, 5);
	for (uint32_t b = 0; b < PBINS; b++) {
		zassert_equal(d.count[b], 0, "bin %u", b);
		zassert_equal(d.sum[b], 0, "bin %u", b);
	}
}

ZTEST(lat_phase, test_invalid_samples)
{
	phase_fresh(17000);
	lat_phase_add(&ph.p, 0, 0x80000000U);
	lat_phase_add(&ph.p, 0, UINT32_MAX);
	zassert_equal(ph.p.count[0], 0, "an invalid sample is not in the phase histogram");
	zassert_equal(ph.p.max[0], 0);
	zassert_equal(ph.p.sum[0], 0);

	/* 2^31 - 1 is valid; a later invalid sample changes nothing. */
	lat_phase_add(&ph.p, 0, 0x7fffffffU);
	lat_phase_add(&ph.p, 0, 0xffffff00U);
	zassert_equal(ph.p.count[0], 1);
	zassert_equal(ph.p.min[0], 0x7fffffffU);
	zassert_equal(ph.p.max[0], 0x7fffffffU);
	zassert_equal(ph.p.sum[0], 0x7fffffffU);
}

ZTEST(lat_phase, test_stats_per_bin)
{
	uint32_t P = 17000;
	uint32_t b3 = ceil_div(3ULL * P, PBINS); /* first phase of bin 3 */

	if (PBINS < 4U) {
		ztest_test_skip();
	}
	phase_fresh(P);

	/* The first sample sets min, also if it is larger than a later one. */
	lat_phase_add(&ph.p, b3, 50);
	zassert_equal(ph.p.min[3], 50, "min after the first sample");
	zassert_equal(ph.p.max[3], 50);
	lat_phase_add(&ph.p, b3 + 1U, 20);
	lat_phase_add(&ph.p, b3, 90);
	zassert_equal(ph.p.count[3], 3);
	zassert_equal(ph.p.min[3], 20);
	zassert_equal(ph.p.max[3], 90);
	zassert_equal(ph.p.sum[3], 160);

	/* A first sample of 0: min stays 0. */
	lat_phase_add(&ph.p, 0, 0);
	lat_phase_add(&ph.p, 1, 5);
	zassert_equal(ph.p.count[0], 2);
	zassert_equal(ph.p.min[0], 0);
	zassert_equal(ph.p.max[0], 5);
	zassert_equal(ph.p.sum[0], 5);

	/* A first sample of 2^31 - 1, the largest valid value; the 64-bit sum does not wrap. */
	lat_phase_add(&ph.p, P - 1U, 0x7fffffffU);
	zassert_equal(ph.p.min[PBINS - 1U], 0x7fffffffU);
	zassert_equal(ph.p.max[PBINS - 1U], 0x7fffffffU);
	lat_phase_add(&ph.p, P - 1U, 0x7fffffffU);
	lat_phase_add(&ph.p, P - 1U, 0x7fffffffU);
	zassert_equal(ph.p.count[PBINS - 1U], 3);
	zassert_equal(ph.p.sum[PBINS - 1U], 3ULL * 0x7fffffffU);

	/* The other bins have no sample. */
	for (uint32_t b = 1; b < PBINS - 1U; b++) {
		if (b != 3U) {
			zassert_equal(ph.p.count[b], 0, "bin %u", b);
			zassert_equal(ph.p.sum[b], 0, "bin %u", b);
		}
	}
}

ZTEST(lat_phase, test_phase_not_below_period)
{
	/*
	 * Precondition gap: lat_phase_add() does not check phase < period.
	 * phase == period gives bin BINS, one after the last. Correct: no
	 * write outside count[], min[], max[] and sum[] of the bins
	 * (drop or clamp the sample).
	 */
	uint32_t P = 17000;
	bool ok;

	phase_fresh(P);
	lat_phase_add(&ph.p, P, 123);

	ok = (ph.p.min[0] == 0U) && (ph.p.max[0] == 0U) && (ph.p.sum[0] == 0U);
	for (size_t i = 0; i < ARRAY_SIZE(ph.guard); i++) {
		ok = ok && (ph.guard[i] == 0U);
	}
	KNOWN_GAP(ok,
		  "lat_phase_add(phase=period=%u) writes bin %u: min[0]=%u max[0]=%u guard[0]=%llu",
		  P, PBINS, ph.p.min[0], ph.p.max[0], (unsigned long long)ph.guard[0]);
}

ZTEST(lat_phase, test_define_and_init)
{
	static LAT_PHASE_DEFINE(d, "pd");

	zassert_str_equal(d.name, "pd");
	zassert_equal(d.period, 0);
	lat_phase_init(&d, 17000);
	zassert_equal(d.period, 17000);
}

ZTEST_SUITE(lat_phase, NULL, NULL, NULL, NULL, NULL);

/* --------------------------------------------------------------- lat_print */

ZTEST(lat_print, test_hook_capture)
{
	/* The capture itself works. */
	cap_begin();
	printk("LAT X %u %llu\n", 1U, 1ULL << 40);
	assert_text(cap_end(), "LAT X 1 1099511627776\n");
}

ZTEST(lat_print, test_hist_empty)
{
	fresh(&h, "empty");
	cap_begin();
	lat_hist_print(&h);
	assert_text(cap_end(), "LAT HIST empty n=0 min=0 max=0 mean=0.00 overflow=0 invalid=0\n"
			       "LAT END empty\n");
}

ZTEST(lat_print, test_hist_fine)
{
	fresh(&h, "t");
	lat_hist_add(&h, 5);
	lat_hist_add(&h, 3);
	lat_hist_add(&h, 3);
	cap_begin();
	lat_hist_print(&h);
	/* 11 / 3 = 3.666..: the mean is cut to 1/100 cycle, not rounded. */
	assert_text(cap_end(), "LAT HIST t n=3 min=3 max=5 mean=3.66 overflow=0 invalid=0\n"
			       "LAT BIN 3 2\n"
			       "LAT BIN 5 1\n"
			       "LAT END t\n");
}

ZTEST(lat_print, test_hist_all_regions)
{
	uint64_t sum = 0;
	uint32_t n = 0;
	const uint32_t vals[] = {0, BINS - 1U, BINS, CEND - 1U, CEND, 0x80000000U, UINT32_MAX};

	fresh(&h, "all");
	for (size_t i = 0; i < ARRAY_SIZE(vals); i++) {
		lat_hist_add(&h, vals[i]);
		if (vals[i] < 0x80000000U) {
			sum += vals[i];
			n++;
		}
	}
	cap_begin();
	lat_hist_print(&h);
	cap_end();

	uint64_t m100 = sum * 100U / n;

	want_reset();
	/* The two invalid samples are only in invalid=. */
	want_add("LAT HIST all n=%u min=0 max=%u mean=%llu.%02llu overflow=%u invalid=2\n", n,
		 CEND, (unsigned long long)(m100 / 100U), (unsigned long long)(m100 % 100U),
		 CBINS > 0 ? 1U : 2U);
	want_add("LAT BIN 0 1\n");
	if (CBINS > 0) {
		want_add("LAT BIN %u 1\n", BINS - 1U);
		want_add("LAT CBIN %u 1 %u\n", BINS, CWIDTH);
		want_add("LAT CBIN %u 1 %u\n", BINS + (CBINS - 1U) * CWIDTH, CWIDTH);
		want_add("LAT OVF %u 1\n", log2_floor(CEND));
	} else {
		/* Without coarse bins CEND is BINS: two samples in each bin. */
		want_add("LAT BIN %u 2\n", BINS - 1U);
		want_add("LAT OVF %u 2\n", log2_floor(BINS));
	}
	want_add("LAT END all\n");
	assert_text(cap, want);
}

ZTEST(lat_print, test_hist_mean_large)
{
	/* 1e6 samples of about 1e5 cycles: the largest run of these benchmarks. */
	fresh(&h, "big");
	h.count = 1000000;
	h.sum = 100000ULL * 1000000ULL + 123456ULL;
	h.min = 99000;
	h.max = 101000;
	cap_begin();
	lat_hist_print(&h);
	assert_text(cap_end(), "LAT HIST big n=1000000 min=99000 max=101000 mean=100000.12 "
			       "overflow=0 invalid=0\nLAT END big\n");

	/* 1e6 samples of 2^31 - 1, the largest valid value: sum * 100 still fits in 64 bits. */
	fresh(&h, "top");
	h.count = 1000000;
	h.sum = 1000000ULL * 0x7fffffffU;
	h.min = 0x7fffffffU;
	h.max = 0x7fffffffU;
	h.overflow = 1000000;
	h.ovf_log2[30] = 1000000;
	h.invalid = 7;
	cap_begin();
	lat_hist_print(&h);
	assert_text(cap_end(), "LAT HIST top n=1000000 min=2147483647 max=2147483647 "
			       "mean=2147483647.00 overflow=1000000 invalid=7\n"
			       "LAT OVF 30 1000000\nLAT END top\n");
}

ZTEST(lat_print, test_hist_mean_sum_overflow)
{
	/*
	 * Precondition gap: sum * 100 wraps at 2^64 if sum > 1.8e17. The
	 * largest sum is UINT32_MAX samples of 2^31 - 1 cycles.
	 */
	fresh(&h, "max");
	h.count = UINT32_MAX;
	h.sum = (uint64_t)UINT32_MAX * 0x7fffffffU;
	h.min = 0x7fffffffU;
	h.max = 0x7fffffffU;
	cap_begin();
	lat_hist_print(&h);
	cap_end();
	KNOWN_GAP(strstr(cap, " mean=2147483647.00 ") != NULL,
		  "count=UINT32_MAX, sum=UINT32_MAX * (2^31 - 1): printed %s", cap);
}

ZTEST(lat_print, test_phase_print)
{
	uint32_t P = 17000;

	phase_fresh(P);
	lat_phase_add(&ph.p, 0, 9);
	lat_phase_add(&ph.p, 1, 3);
	lat_phase_add(&ph.p, P - 1U, 0x7fffffffU);
	lat_phase_add(&ph.p, P - 1U, UINT32_MAX); /* invalid: not printed */
	lat_phase_add(&ph.p, P - 1U, 0x7fffffffU);
	lat_phase_add(&ph.p, P - 1U, 0x7fffffffU);
	cap_begin();
	lat_phase_print(&ph.p);
	cap_end();

	want_reset();
	want_add("LAT PHASE ph bins=%u period=17000\n", PBINS);
	want_add("LAT PB 0 2 3 9 12\n");
	want_add("LAT PB %u 3 2147483647 2147483647 6442450941\n", PBINS - 1U);
	want_add("LAT END ph\n");
	assert_text(cap, want);
}

ZTEST(lat_print, test_phase_print_empty)
{
	static LAT_PHASE_DEFINE(e, "none");

	cap_begin();
	lat_phase_print(&e);
	cap_end();
	want_reset();
	want_add("LAT PHASE none bins=%u period=0\nLAT END none\n", PBINS);
	assert_text(cap, want);
}

ZTEST_SUITE(lat_print, NULL, NULL, NULL, NULL, NULL);

/* ----------------------------------------------------------------- fixture */

/*
 * Print a full run of pseudo-random samples to the console. The Python
 * tests (scripts/tests/test_latbench.py) parse a saved copy of this output
 * and compute the same samples with the same generator.
 */
#define FIX_SEED    0x2545f491U
#define FIX_SAMPLES 10000U
#define FIX_PERIOD  17000U

static uint32_t lcg(uint32_t *s)
{
	*s = *s * 1664525U + 1013904223U;
	return *s;
}

static uint32_t fixture_sample(uint32_t *s)
{
	uint32_t r = lcg(s) >> 24;
	uint32_t y = lcg(s) >> 8;
	uint32_t span0 = BINS < 256U ? BINS : 256U;
	uint32_t lo1 = BINS > 8U ? BINS - 8U : 0U;

	if (r < 179U) {
		/* The top of the fine region. */
		return BINS - span0 + y % span0;
	} else if (r < 230U) {
		/* Across the fine, coarse and first overflow edges. */
		return lo1 + y % (CEND - lo1 + 16U);
	} else if (r < 251U) {
		return CEND + y % (4U * CEND);
	}
	/* A negative difference. */
	return 0U - (1U + y % 1000U);
}

static LAT_HIST_DEFINE(fix_h, "fix");
static LAT_PHASE_DEFINE(fix_p, "fixph");

ZTEST(lat_zfixture, test_emit_fixture)
{
	uint32_t s = FIX_SEED;

	lat_phase_init(&fix_p, FIX_PERIOD);
	for (uint32_t i = 0; i < FIX_SAMPLES; i++) {
		uint32_t v = fixture_sample(&s);
		uint32_t phase = lcg(&s) % FIX_PERIOD;

		lat_hist_add(&fix_h, v);
		lat_phase_add(&fix_p, phase, v);
	}
	printk("LAT BEGIN\n");
	printk("LAT META test=hist_unit\n");
	printk("LAT META hist_bins=%u\n", BINS);
	printk("LAT META coarse_bins=%u\n", CBINS);
	printk("LAT META coarse_shift=%u\n", (uint32_t)CONFIG_LATBENCH_HIST_COARSE_SHIFT);
	printk("LAT META phase_bins=%u\n", PBINS);
	printk("LAT META seed=%u\n", FIX_SEED);
	printk("LAT META samples=%u\n", FIX_SAMPLES);
	printk("LAT META period=%u\n", FIX_PERIOD);
	printk("LAT CFG LATBENCH_FIXTURE=1\n");
	lat_hist_print(&fix_h);
	lat_phase_print(&fix_p);
	printk("LAT DONE\n");
	zassert_equal(fix_h.count + fix_h.invalid, FIX_SAMPLES);
	zassert_true(fix_h.invalid > 0U);
}

ZTEST_SUITE(lat_zfixture, NULL, NULL, NULL, NULL, NULL);
