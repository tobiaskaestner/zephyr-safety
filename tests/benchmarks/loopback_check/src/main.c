/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Check the loopback wire between the stimulus and the response pin.
 *
 * 1. Static check: drive the stimulus pin and read the response pin.
 * 2. Interrupt check: raise the stimulus pin and measure, in DWT cycles,
 *    the time until the GPIO callback of the response pin runs.
 */

#include <zephyr/kernel.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/timing/timing.h>
#include <zephyr/sys/printk.h>

#define N_SAMPLES 1000

static const struct gpio_dt_spec stim =
	GPIO_DT_SPEC_GET(DT_PATH(zephyr_user), stim_gpios);
static const struct gpio_dt_spec resp =
	GPIO_DT_SPEC_GET(DT_PATH(zephyr_user), resp_gpios);

static struct gpio_callback resp_cb;
static volatile timing_t t_isr;
static volatile bool fired;

static void resp_handler(const struct device *dev, struct gpio_callback *cb,
			 uint32_t pins)
{
	t_isr = timing_counter_get();
	fired = true;
}

static bool static_check(void)
{
	bool ok = true;

	for (int level = 0; level <= 1; level++) {
		gpio_pin_set_dt(&stim, level);
		k_busy_wait(10);
		int got = gpio_pin_get_dt(&resp);

		printk("static: drive %d, read %d %s\n", level, got,
		       got == level ? "OK" : "FAIL");
		ok = ok && (got == level);
	}
	gpio_pin_set_dt(&stim, 0);
	return ok;
}

int main(void)
{
	uint64_t sum = 0;
	uint64_t min = UINT64_MAX;
	uint64_t max = 0;
	int missed = 0;

	printk("loopback_check: %u Hz core, timing %u MHz\n",
	       sys_clock_hw_cycles_per_sec(), timing_freq_get_mhz());

	if (!gpio_is_ready_dt(&stim) || !gpio_is_ready_dt(&resp)) {
		printk("GPIO not ready\n");
		return 0;
	}
	gpio_pin_configure_dt(&stim, GPIO_OUTPUT_INACTIVE);
	gpio_pin_configure_dt(&resp, GPIO_INPUT);

	if (!static_check()) {
		printk("RESULT: FAIL (wire not connected?)\n");
		return 0;
	}

	gpio_init_callback(&resp_cb, resp_handler, BIT(resp.pin));
	gpio_add_callback_dt(&resp, &resp_cb);
	gpio_pin_interrupt_configure_dt(&resp, GPIO_INT_EDGE_TO_ACTIVE);

	timing_init();
	timing_start();

	for (int i = 0; i < N_SAMPLES; i++) {
		gpio_pin_set_dt(&stim, 0);
		k_msleep(1);
		fired = false;

		timing_t t0 = timing_counter_get();

		gpio_pin_set_dt(&stim, 1);
		for (int spin = 0; !fired && spin < 100000; spin++) {
		}
		if (!fired) {
			missed++;
			continue;
		}

		uint64_t c = timing_cycles_get(&t0, (timing_t *)&t_isr);

		sum += c;
		min = MIN(min, c);
		max = MAX(max, c);
	}
	gpio_pin_set_dt(&stim, 0);

	int n = N_SAMPLES - missed;

	printk("irq: n=%d missed=%d min=%llu avg=%llu max=%llu cycles\n", n,
	       missed, min, n ? sum / n : 0, max);
	printk("RESULT: %s\n", (missed == 0) ? "OK" : "FAIL");
	return 0;
}
