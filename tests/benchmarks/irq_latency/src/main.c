/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * IRQ latency benchmark (measurement point M1 of the latency plan).
 *
 * TIM2 channel 4 sets PA10 high when TIM2->CNT reaches CCR4. A wire takes
 * the edge to PB0 (EXTI line 0). The measurement point reads TIM2->CNT.
 * TIM2 runs at the core clock, so CNT - CCR4 is the time from the edge to
 * the measurement point in core cycles. The time stamp of the edge comes
 * from hardware, and TIM2 counts also while the core sleeps in WFI. See
 * latbench/stim.h.
 *
 * The measurement point schedules the next stimulus (random or fixed
 * rate). A second histogram records the latency by the tick phase of the
 * edge.
 */

#include <zephyr/kernel.h>
#include <zephyr/irq.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/sys/printk.h>

#include <stm32_ll_exti.h>

#include <latbench/hist.h>
#include <latbench/meta.h>
#include <latbench/stim.h>

#if defined(CONFIG_LATBENCH_IRQ_PATH_STOCK)
#define IRQ_PATH "stock"
BUILD_ASSERT(DT_IRQ_HAS_NAME(DT_NODELABEL(exti), line0),
	     "the stock path needs EXTI line 0 in the GPIO interrupt driver");
#else
BUILD_ASSERT(!DT_IRQ_HAS_NAME(DT_NODELABEL(exti), line0),
	     "build with EXTRA_DTC_OVERLAY_FILE=exti_line0_app.overlay");
#if defined(CONFIG_LATBENCH_IRQ_PATH_WRAPPED)
#define IRQ_PATH "wrapped"
#elif defined(CONFIG_LATBENCH_IRQ_PATH_DIRECT)
#define IRQ_PATH "direct"
#else
#define IRQ_PATH "zli"
#endif
#endif

#if defined(CONFIG_LATBENCH_BG_BUSY)
#define BACKGROUND "busy"
#else
#define BACKGROUND "idle"
#endif

#define N_TOTAL (CONFIG_LATBENCH_WARMUP + CONFIG_LATBENCH_SAMPLES)

static LAT_HIST_DEFINE(hist, "irq");
static LAT_PHASE_DEFINE(phase, "irq");

static volatile uint32_t n_seen;
static volatile uint32_t n_spurious;
static volatile bool done;

static inline void on_edge(uint32_t now)
{
	uint32_t n = n_seen;

	/* An edge without a TIM2 compare match did not come from the stimulus. */
	if (!stim_fired()) {
		n_spurious++;
	}
	if (n >= CONFIG_LATBENCH_WARMUP) {
		uint32_t lat = now - stim_edge();

		lat_hist_add(&hist, lat);
		lat_phase_add(&phase, stim_edge_phase(), lat);
	}
	n_seen = ++n;
	if (n < N_TOTAL) {
		stim_arm(now);
	} else {
		stim_stop();
		done = true;
	}
}

#if defined(CONFIG_LATBENCH_IRQ_PATH_STOCK)

static struct gpio_callback resp_cb;

static void resp_handler(const struct device *dev, struct gpio_callback *cb, uint32_t pins)
{
	on_edge(stim_now());
}

static int irq_setup(void)
{
	gpio_init_callback(&resp_cb, resp_handler, BIT(stim_resp.pin));
	gpio_add_callback_dt(&stim_resp, &resp_cb);
	return gpio_pin_interrupt_configure_dt(&stim_resp, GPIO_INT_EDGE_TO_ACTIVE);
}

#else /* own ISR on EXTI0 */

#if defined(CONFIG_LATBENCH_IRQ_PATH_WRAPPED)

static void exti0_isr(const void *arg)
{
	uint32_t now = stim_now();

	ARG_UNUSED(arg);
	LL_EXTI_ClearFlag_0_31(LL_EXTI_LINE_0);
	on_edge(now);
}

#else

ISR_DIRECT_DECLARE(exti0_isr)
{
	uint32_t now = stim_now();

	LL_EXTI_ClearFlag_0_31(LL_EXTI_LINE_0);
	on_edge(now);
	return 0;
}

#endif

static int irq_setup(void)
{
	if (stim_resp.pin != 0) {
		return -EINVAL;
	}

	stim_exti0_init();
#if defined(CONFIG_LATBENCH_IRQ_PATH_WRAPPED)
	IRQ_CONNECT(EXTI0_IRQn, 0, exti0_isr, NULL, 0);
#elif defined(CONFIG_LATBENCH_IRQ_PATH_DIRECT)
	IRQ_DIRECT_CONNECT(EXTI0_IRQn, 0, exti0_isr, 0);
#else
	IRQ_DIRECT_CONNECT(EXTI0_IRQn, 0, exti0_isr, IRQ_ZERO_LATENCY);
#endif
	irq_enable(EXTI0_IRQn);
	return 0;
}

#endif

#if defined(CONFIG_LATBENCH_BG_BUSY)
static void busy_fn(void *a, void *b, void *c)
{
	for (;;) {
		arch_nop();
	}
}

K_THREAD_DEFINE(busy_tid, 512, busy_fn, NULL, NULL, NULL, K_LOWEST_APPLICATION_THREAD_PRIO, 0,
		0);
#endif

int main(void)
{
	char buf[24];

	/*
	 * A debugger session can leave DBGMCU bits set that keep the clocks
	 * on in sleep modes. Clear them, so that WFI behaves as without a
	 * debugger.
	 */
	snprintk(buf, sizeof(buf), "0x%08x", DBGMCU->CR);
	DBGMCU->CR = 0;

	lat_meta_print("irq_latency", IRQ_PATH);
	lat_meta_kv("irq_path", IRQ_PATH);
	lat_meta_kv("background", BACKGROUND);
	lat_meta_kv("dbgmcu_cr_at_boot", buf);
	printk("LAT META poll_ms=%u\n", CONFIG_LATBENCH_POLL_MS);

	if (stim_init() < 0) {
		printk("LAT ERROR setup\n");
		lat_done();
		return 0;
	}
	lat_phase_init(&phase, stim_tick_period());
	if (!stim_static_check()) {
		printk("LAT ERROR static check failed (wire D2 -> A3?)\n");
		lat_done();
		return 0;
	}
	if (irq_setup() < 0) {
		printk("LAT ERROR irq setup\n");
		lat_done();
		return 0;
	}

	stim_arm(stim_now());
	while (!done) {
		k_msleep(CONFIG_LATBENCH_POLL_MS);
	}

	printk("LAT META spurious_edges=%u\n", n_spurious);
	stim_print_stats();
	lat_hist_print(&hist);
	lat_phase_print(&phase);
	lat_done();
	return 0;
}
