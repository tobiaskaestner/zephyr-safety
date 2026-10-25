/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * M4: the time with the interrupts masked, per call site.
 *
 * This file supplies the hooks of CONFIG_ARM_IRQ_MASK_HOOKS and
 * CONFIG_ARM_IRQ_MASK_HOOKS_ISR (Zephyr branch
 * tkaestner/latency-irqoff-hook). The clock is the DWT cycle counter.
 *
 * A mask section starts when the CPU starts to mask the interrupts of
 * irq_lock() (z_arm_irq_mask_hook_begin()) and ends when it stops
 * (z_arm_irq_mask_hook_end()). Two sections never overlap: while a
 * section is open, no interrupt that can start a section can occur. So one
 * set of start values is sufficient.
 *
 * Rules for the code in the hooks: no irq_lock(), no spinlock, no kernel
 * call. arch_irq_lock() calls the hooks, so these calls would recurse.
 * The ISR exit hook masks the interrupts with a direct BASEPRI write.
 *
 * The DWT counter stops while the CPU sleeps (WFI). The idle hooks end the
 * section before the sleep, so no section contains a sleep. The length of
 * the measurement window comes from k_cycle_get_64().
 */

#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>
#include <cmsis_core.h>

#include <latbench/irqmask.h>
#include <latbench/irqmask_table.h>

#define CAL_ROUNDS 256U

static struct irqmask_table table;

/* The state of the open section. */
static struct {
	uint32_t t0;
	uint32_t pc;
	uint32_t ipsr;
	bool open;
	bool enabled;
	/* The last value of a section and of an ISR body, for the calibration. */
	uint32_t last;
	uint32_t last_isr;
	/* An end without an open section. */
	uint32_t unmatched_end;
	/* A start while a section is open. The new start replaces the old one. */
	uint32_t begin_open;
	uint64_t masked_cyc;
	uint64_t isr_cyc;
} st;

static uint64_t window_start;
static uint64_t window_end;
static uint32_t floor_cyc;
static uint32_t pair_cost_cyc;
static uint32_t isr_floor_cyc;

static ALWAYS_INLINE uint32_t now(void)
{
	return DWT->CYCCNT;
}

void z_arm_irq_mask_hook_begin(void)
{
	uint32_t t = now();

	if (st.open) {
		st.begin_open++;
	}
	st.t0 = t;
	st.pc = (uint32_t)(uintptr_t)__builtin_return_address(0);
	st.ipsr = __get_IPSR();
	st.open = true;
}

void z_arm_irq_mask_hook_end(void)
{
	uint32_t t = now();

	if (!st.open) {
		st.unmatched_end++;
		return;
	}
	st.open = false;

	uint32_t d = t - st.t0;

	st.last = d;
	if (st.enabled) {
		st.masked_cyc += d;
		irqmask_add(&table, st.pc, st.ipsr, IRQMASK_KIND_MASK,
			    (uint32_t)(uintptr_t)__builtin_return_address(0), d);
	}
}

#if defined(CONFIG_ARM_IRQ_MASK_HOOKS_ISR)

uint32_t z_arm_isr_hook_enter(void)
{
	return now();
}

void z_arm_isr_hook_exit(uint32_t token, const void *isr)
{
	uint32_t d = now() - token;
	/* Not arch_irq_lock(): that calls the mask hooks. */
	uint32_t key = __get_BASEPRI();

	__set_BASEPRI_MAX(_EXC_IRQ_DEFAULT_PRIO);
	st.last_isr = d;
	if (st.enabled) {
		st.isr_cyc += d;
		irqmask_add(&table, (uint32_t)(uintptr_t)isr, __get_IPSR(), IRQMASK_KIND_ISR, 0U,
			    d);
	}
	__set_BASEPRI(key);
}

#endif

static int dwt_start(void)
{
	CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
	if ((DWT->CTRL & DWT_CTRL_NOCYCCNT_Msk) != 0U) {
		return -ENOTSUP;
	}
	DWT->CYCCNT = 0U;
	DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;

	uint32_t a = now();

	for (volatile int i = 0; i < 10; i++) {
	}
	return now() != a ? 0 : -EIO;
}

/*
 * Calibration with the hooks on, before the run:
 *
 * floor_cyc      the smallest value of an empty section,
 *                irq_unlock(irq_lock()). All section values contain it.
 * pair_cost_cyc  the extra time of an empty section with hooks, against
 *                the same BASEPRI writes without hooks: the time that the
 *                hooks add to each section and to the CPU load.
 * isr_floor_cyc  the smallest value of an empty ISR body measurement.
 *
 * Each value is the minimum of CAL_ROUNDS tries, so that an interrupt
 * between the time stamps has no effect.
 */
static void calibrate(void)
{
	uint32_t hooked = UINT32_MAX;
	uint32_t raw = UINT32_MAX;

	floor_cyc = UINT32_MAX;
	isr_floor_cyc = UINT32_MAX;
	for (uint32_t n = 0; n < CAL_ROUNDS; n++) {
		uint32_t t0 = now();
		unsigned int key = irq_lock();

		irq_unlock(key);

		uint32_t t1 = now();

		if (key == 0U) {
			hooked = MIN(hooked, t1 - t0);
			floor_cyc = MIN(floor_cyc, st.last);
		}

		t0 = now();
		key = __get_BASEPRI();
		__set_BASEPRI_MAX(_EXC_IRQ_DEFAULT_PRIO);
		__set_BASEPRI(key);
		t1 = now();
		raw = MIN(raw, t1 - t0);

#if defined(CONFIG_ARM_IRQ_MASK_HOOKS_ISR)
		uint32_t tok = z_arm_isr_hook_enter();

		z_arm_isr_hook_exit(tok, (const void *)calibrate);
		isr_floor_cyc = MIN(isr_floor_cyc, st.last_isr);
#endif
	}
	pair_cost_cyc = hooked - raw;
	if (!IS_ENABLED(CONFIG_ARM_IRQ_MASK_HOOKS_ISR)) {
		isr_floor_cyc = 0U;
	}
}

#if CONFIG_LATBENCH_IRQMASK_PROBE_CYC > 0

/*
 * The probe: a mask section of a known length, every
 * CONFIG_LATBENCH_IRQMASK_PROBE_MS. Its site must show this length plus
 * floor_cyc, and the IRQ tail of the same run must show it too.
 */
static void probe_fn(void *a, void *b, void *c)
{
	for (;;) {
		k_msleep(CONFIG_LATBENCH_IRQMASK_PROBE_MS);

		unsigned int key = irq_lock();
		uint32_t t0 = now();

		while (now() - t0 < CONFIG_LATBENCH_IRQMASK_PROBE_CYC) {
		}
		irq_unlock(key);
	}
}

K_THREAD_DEFINE(irqmask_probe, 512, probe_fn, NULL, NULL, NULL, CONFIG_LATBENCH_IRQMASK_PROBE_PRIO,
		0, SYS_FOREVER_MS);

#endif

void irqmask_start(void)
{
	printk("LAT META m4=1\n");
	printk("LAT META m4_note=hooks make each mask section longer: the latency histograms of "
	       "this run are not data\n");
	if (dwt_start() < 0) {
		printk("LAT ERROR m4: the DWT cycle counter does not count\n");
		return;
	}
	st.enabled = true;
	calibrate();
	st.enabled = false;

	/* The hooks do not change the table while enabled is false. */
	irqmask_table_reset(&table);
	st.masked_cyc = 0U;
	st.isr_cyc = 0U;
	st.unmatched_end = 0U;
	st.begin_open = 0U;
	window_start = k_cycle_get_64();
	st.enabled = true;

#if CONFIG_LATBENCH_IRQMASK_PROBE_CYC > 0
	k_thread_start(irqmask_probe);
#endif
}

void irqmask_stop(void)
{
	st.enabled = false;
	window_end = k_cycle_get_64();
#if CONFIG_LATBENCH_IRQMASK_PROBE_CYC > 0
	k_thread_suspend(irqmask_probe);
#endif
}

void irqmask_print(void)
{
	uint32_t sections = table.dropped;

	for (uint32_t i = 0; i < IRQMASK_SITES; i++) {
		if (table.site[i].kind == IRQMASK_KIND_MASK) {
			sections += table.site[i].count;
		}
	}
	printk("LAT META m4_isr_hooks=%d\n", IS_ENABLED(CONFIG_ARM_IRQ_MASK_HOOKS_ISR));
	printk("LAT META m4_floor_cyc=%u\n", floor_cyc);
	printk("LAT META m4_pair_cost_cyc=%u\n", pair_cost_cyc);
	printk("LAT META m4_isr_floor_cyc=%u\n", isr_floor_cyc);
	printk("LAT META m4_window_cyc=%llu\n", window_end - window_start);
	printk("LAT META m4_sections=%u\n", sections);
	printk("LAT META m4_masked_cyc=%llu\n", st.masked_cyc);
	printk("LAT META m4_isr_cyc=%llu\n", st.isr_cyc);
	printk("LAT META m4_unmatched_end=%u\n", st.unmatched_end);
	printk("LAT META m4_begin_open=%u\n", st.begin_open);
	printk("LAT META m4_probe_cyc=%u\n", CONFIG_LATBENCH_IRQMASK_PROBE_CYC);
	printk("LAT META m4_probe_ms=%u\n", CONFIG_LATBENCH_IRQMASK_PROBE_MS);
	irqmask_table_print(&table);
}
