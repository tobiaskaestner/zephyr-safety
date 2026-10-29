/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * The software trigger (CONFIG_LATBENCH_SWTRIG, see latbench/swtrig.h).
 * latbench.cmake adds this file only with the option, so the images
 * without it do not change.
 */

#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>
#include <cmsis_core.h>

#include <latbench/stim.h>
#include <latbench/swtrig.h>

volatile bool swtrig_pending;
volatile uint32_t swtrig_t0;
volatile uint32_t swtrig_isr;

static K_SEM_DEFINE(go, 0, 1);
static K_THREAD_STACK_DEFINE(trig_stack, 768);
static struct k_thread trig_thread;
static swtrig_done_fn done_fn;
static int trig_prio;
static uint32_t n_triggers;

static void trig_fn(void *a, void *b, void *c)
{
	ARG_UNUSED(a);
	ARG_UNUSED(b);
	ARG_UNUSED(c);

	for (;;) {
		uint32_t start;
		uint32_t gap;
		uint32_t t0;

		(void)k_sem_take(&go, K_FOREVER);
		/* A random gap, so that the trigger has a random tick phase. The CPU spins. */
		start = stim_now();
		gap = stim_gap();
		while ((uint32_t)(stim_now() - start) < gap) {
		}

		swtrig_pending = true;
		t0 = stim_now();
		swtrig_t0 = t0;
		NVIC->STIR = PORT_RESP_IRQN;
		/*
		 * The ISR takes the sample before the next instructions, or a
		 * higher priority thread that it woke runs first. Wait for it.
		 */
		while (swtrig_pending) {
		}
		n_triggers++;
		if (done_fn != NULL) {
			done_fn(t0, swtrig_isr);
		}
	}
}

void swtrig_start(int prio, swtrig_done_fn done)
{
	done_fn = done;
	trig_prio = prio;
	k_thread_create(&trig_thread, trig_stack, K_THREAD_STACK_SIZEOF(trig_stack), trig_fn, NULL,
			NULL, NULL, prio, 0, K_NO_WAIT);
}

void swtrig_request(void)
{
	k_sem_give(&go);
}

void swtrig_print_setup(void)
{
	printk("LAT META stim_trigger=gpio+sw\n");
	printk("LAT META sw_trigger=nvic-stir\n");
	printk("LAT META sw_trigger_irqn=%d\n", (int)PORT_RESP_IRQN);
	printk("LAT META sw_trigger_prio=%d\n", trig_prio);
	printk("LAT META sw_read_cyc=%u\n", stim_read_cyc());
}

void swtrig_print_stats(void)
{
	printk("LAT META sw_triggers=%u\n", n_triggers);
}
