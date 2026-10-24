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
 * from hardware, and TIM2 counts also while the core sleeps in WFI.
 *
 * The measurement point schedules the next stimulus at a random time, so
 * the stimuli are asynchronous to the threads and to the system timer.
 */

#include <zephyr/kernel.h>
#include <zephyr/irq.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/pinctrl.h>
#include <zephyr/drivers/clock_control.h>
#include <zephyr/drivers/clock_control/stm32_clock_control.h>
#include <zephyr/sys/printk.h>

#include <stm32_ll_bus.h>
#include <stm32_ll_exti.h>
#include <stm32_ll_system.h>
#include <stm32_ll_tim.h>

#include <latbench/hist.h>
#include <latbench/meta.h>

#define USER_NODE DT_PATH(zephyr_user)
#define RCC_NODE  DT_NODELABEL(rcc)
#define TIM       TIM2

/* TIM2 must run at the core clock (APB1 timer clock = HCLK). */
BUILD_ASSERT(DT_PROP(RCC_NODE, ahb_prescaler) == 1 && DT_PROP(RCC_NODE, apb1_prescaler) == 1,
	     "TIM2 must run at the core clock");

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

PINCTRL_DT_DEFINE(USER_NODE);

static const struct gpio_dt_spec resp = GPIO_DT_SPEC_GET(USER_NODE, resp_gpios);

static LAT_HIST_DEFINE(hist, "irq");

static uint32_t next_ccr;
static uint32_t stim_min;
static uint32_t stim_span;
static uint32_t rng_state = 0x2545f491U;
static volatile uint32_t n_seen;
static volatile bool done;

static inline uint32_t rng_next(void)
{
	uint32_t x = rng_state;

	x ^= x << 13;
	x ^= x >> 17;
	x ^= x << 5;
	rng_state = x;
	return x;
}

static inline void stim_arm(uint32_t now)
{
	LL_TIM_OC_SetMode(TIM, LL_TIM_CHANNEL_CH4, LL_TIM_OCMODE_FORCED_INACTIVE);
	next_ccr = now + stim_min + (rng_next() % stim_span);
	LL_TIM_OC_SetCompareCH4(TIM, next_ccr);
	LL_TIM_OC_SetMode(TIM, LL_TIM_CHANNEL_CH4, LL_TIM_OCMODE_ACTIVE);
}

static inline void on_edge(uint32_t now)
{
	uint32_t n = n_seen;

	if (n >= CONFIG_LATBENCH_WARMUP) {
		lat_hist_add(&hist, now - next_ccr);
	}
	n_seen = ++n;
	if (n < N_TOTAL) {
		stim_arm(now);
	} else {
		LL_TIM_OC_SetMode(TIM, LL_TIM_CHANNEL_CH4, LL_TIM_OCMODE_FORCED_INACTIVE);
		done = true;
	}
}

#if defined(CONFIG_LATBENCH_IRQ_PATH_STOCK)

static struct gpio_callback resp_cb;

static void resp_handler(const struct device *dev, struct gpio_callback *cb, uint32_t pins)
{
	on_edge(TIM->CNT);
}

static int irq_setup(void)
{
	gpio_init_callback(&resp_cb, resp_handler, BIT(resp.pin));
	gpio_add_callback_dt(&resp, &resp_cb);
	return gpio_pin_interrupt_configure_dt(&resp, GPIO_INT_EDGE_TO_ACTIVE);
}

#else /* own ISR on EXTI0 */

#if defined(CONFIG_LATBENCH_IRQ_PATH_WRAPPED)

static void exti0_isr(const void *arg)
{
	uint32_t now = TIM->CNT;

	ARG_UNUSED(arg);
	LL_EXTI_ClearFlag_0_31(LL_EXTI_LINE_0);
	on_edge(now);
}

#else

ISR_DIRECT_DECLARE(exti0_isr)
{
	uint32_t now = TIM->CNT;

	LL_EXTI_ClearFlag_0_31(LL_EXTI_LINE_0);
	on_edge(now);
	return 0;
}

#endif

static int irq_setup(void)
{
	if (resp.pin != 0) {
		return -EINVAL;
	}

	LL_APB2_GRP1_EnableClock(LL_APB2_GRP1_PERIPH_SYSCFG);
	LL_SYSCFG_SetEXTISource(LL_SYSCFG_EXTI_PORTB, LL_SYSCFG_EXTI_LINE0);
	LL_EXTI_EnableRisingTrig_0_31(LL_EXTI_LINE_0);
	LL_EXTI_DisableFallingTrig_0_31(LL_EXTI_LINE_0);
	LL_EXTI_ClearFlag_0_31(LL_EXTI_LINE_0);
	LL_EXTI_EnableIT_0_31(LL_EXTI_LINE_0);

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

static int tim_setup(void)
{
	const struct device *clk = DEVICE_DT_GET(STM32_CLOCK_CONTROL_NODE);
	const struct stm32_pclken pclken = STM32_CLOCK_INFO(0, DT_NODELABEL(timers2));
	int ret;

	ret = clock_control_on(clk, (clock_control_subsys_t)&pclken);
	if (ret < 0) {
		return ret;
	}
	ret = pinctrl_apply_state(PINCTRL_DT_DEV_CONFIG_GET(USER_NODE), PINCTRL_STATE_DEFAULT);
	if (ret < 0) {
		return ret;
	}

	LL_TIM_DisableCounter(TIM);
	LL_TIM_SetPrescaler(TIM, 0);
	LL_TIM_SetAutoReload(TIM, UINT32_MAX);
	LL_TIM_OC_DisablePreload(TIM, LL_TIM_CHANNEL_CH4);
	LL_TIM_OC_SetPolarity(TIM, LL_TIM_CHANNEL_CH4, LL_TIM_OCPOLARITY_HIGH);
	LL_TIM_OC_SetMode(TIM, LL_TIM_CHANNEL_CH4, LL_TIM_OCMODE_FORCED_INACTIVE);
	LL_TIM_CC_EnableChannel(TIM, LL_TIM_CHANNEL_CH4);
	LL_TIM_GenerateEvent_UPDATE(TIM);
	LL_TIM_EnableCounter(TIM);
	return 0;
}

/* TIM2 drives the pin, the wire takes it to the response pin. */
static bool static_check(void)
{
	int lo;
	int hi;

	LL_TIM_OC_SetMode(TIM, LL_TIM_CHANNEL_CH4, LL_TIM_OCMODE_FORCED_INACTIVE);
	k_busy_wait(10);
	lo = gpio_pin_get_dt(&resp);
	LL_TIM_OC_SetMode(TIM, LL_TIM_CHANNEL_CH4, LL_TIM_OCMODE_FORCED_ACTIVE);
	k_busy_wait(10);
	hi = gpio_pin_get_dt(&resp);
	LL_TIM_OC_SetMode(TIM, LL_TIM_CHANNEL_CH4, LL_TIM_OCMODE_FORCED_INACTIVE);
	k_busy_wait(10);

	printk("LAT META static_check=%s\n", (lo == 0 && hi == 1) ? "ok" : "fail");
	return lo == 0 && hi == 1;
}

int main(void)
{
	uint32_t cyc_per_us = sys_clock_hw_cycles_per_sec() / 1000000U;
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
	printk("LAT META stim_us=%u..%u\n", CONFIG_LATBENCH_STIM_MIN_US,
	       CONFIG_LATBENCH_STIM_MAX_US);
	printk("LAT META poll_ms=%u\n", CONFIG_LATBENCH_POLL_MS);

	stim_min = CONFIG_LATBENCH_STIM_MIN_US * cyc_per_us;
	stim_span = (CONFIG_LATBENCH_STIM_MAX_US - CONFIG_LATBENCH_STIM_MIN_US) * cyc_per_us;

	if (!gpio_is_ready_dt(&resp) || gpio_pin_configure_dt(&resp, GPIO_INPUT) < 0 ||
	    tim_setup() < 0) {
		printk("LAT ERROR setup\n");
		lat_done();
		return 0;
	}
	if (!static_check()) {
		printk("LAT ERROR static check failed (wire D2 -> A3?)\n");
		lat_done();
		return 0;
	}
	if (irq_setup() < 0) {
		printk("LAT ERROR irq setup\n");
		lat_done();
		return 0;
	}

	stim_arm(TIM->CNT);
	while (!done) {
		k_msleep(CONFIG_LATBENCH_POLL_MS);
	}

	lat_hist_print(&hist);
	lat_done();
	return 0;
}
