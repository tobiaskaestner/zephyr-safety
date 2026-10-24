/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * IRQ latency benchmark (measurement point M1 of the latency plan).
 *
 * The stimulus timer of the board port sets the stimulus pin high when
 * its counter reaches the compare value. A wire takes the edge to the
 * response pin. The measurement point reads the counter, so counter -
 * compare value is the time from the edge to the measurement point (in
 * core cycles, if the timer runs at the core clock, as on nucleo_g474re).
 * The time stamp of the edge comes from hardware, and the timer counts
 * also while the core sleeps in WFI. See latbench/stim.h and
 * latbench/port.h.
 *
 * The measurement point schedules the next stimulus (random or fixed
 * rate). A second histogram records the latency by the tick phase of the
 * edge.
 */

#include <zephyr/kernel.h>
#include <zephyr/irq.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/sys/printk.h>

#include <latbench/hist.h>
#include <latbench/load.h>
#include <latbench/meta.h>
#include <latbench/stim.h>

#if defined(CONFIG_LATBENCH_IRQ_PATH_STOCK)
#define IRQ_PATH "stock"
BUILD_ASSERT(!PORT_RESP_IRQ_OWNED, "the stock path needs the response IRQ in the GPIO driver");
#else
BUILD_ASSERT(PORT_RESP_IRQ_OWNED,
	     "the own ISR paths need -DCONFIG_LATBENCH_IRQ_PATH_<path>=y on the cmake command line");
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

/*
 * Note for the ZLI path: stim_arm() takes the tick phase of the next edge
 * from k_cycle_get_64(). BASEPRI does not mask a zero-latency IRQ, so the
 * read can interrupt the timer driver in its locked section and see an
 * inconsistent count. Only the phase histogram is at risk, not the
 * latency.
 */
static inline void on_edge(uint32_t now)
{
	uint32_t n = n_seen;

	/* An edge without a timer compare match did not come from the stimulus. */
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

#else /* own ISR on the response IRQ */

#if defined(CONFIG_LATBENCH_IRQ_PATH_WRAPPED)

static void resp_isr(const void *arg)
{
	uint32_t now = stim_now();

	ARG_UNUSED(arg);
	stim_resp_ack();
	on_edge(now);
}

#else

ISR_DIRECT_DECLARE(resp_isr)
{
	uint32_t now = stim_now();

	stim_resp_ack();
	on_edge(now);
	return 0;
}

#endif

static int irq_setup(void)
{
#if defined(PORT_RESP_PIN)
	/* The own ISR serves only the pin that the port sets up. */
	if (stim_resp.pin != PORT_RESP_PIN) {
		return -EINVAL;
	}
#endif

	stim_resp_irq_init();
#if defined(CONFIG_LATBENCH_IRQ_PATH_WRAPPED)
	IRQ_CONNECT(STIM_RESP_IRQN, 0, resp_isr, NULL, 0);
#elif defined(CONFIG_LATBENCH_IRQ_PATH_DIRECT)
	IRQ_DIRECT_CONNECT(STIM_RESP_IRQN, 0, resp_isr, 0);
#else
	IRQ_DIRECT_CONNECT(STIM_RESP_IRQN, 0, resp_isr, IRQ_ZERO_LATENCY);
#endif
	irq_enable(STIM_RESP_IRQN);
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

	/* Undo debugger settings that keep clocks on in sleep (see the port). */
	port_debug_reset(buf, sizeof(buf));

	lat_meta_print("irq_latency", IRQ_PATH);
	lat_meta_kv("irq_path", IRQ_PATH);
	lat_meta_kv("background", BACKGROUND);
	lat_meta_kv("debug_reg_at_boot", buf);
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

	load_start();
	stim_arm(stim_now());
	while (!done) {
		k_msleep(CONFIG_LATBENCH_POLL_MS);
	}

	printk("LAT META spurious_edges=%u\n", n_spurious);
	stim_print_stats();
	load_print();
	lat_hist_print(&hist);
	lat_phase_print(&phase);
	lat_done();
	return 0;
}
