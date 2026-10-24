/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <zephyr/kernel.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/pinctrl.h>
#include <zephyr/drivers/clock_control.h>
#include <zephyr/drivers/clock_control/stm32_clock_control.h>
#include <zephyr/sys/printk.h>

#include <stm32_ll_bus.h>
#include <stm32_ll_exti.h>
#include <stm32_ll_system.h>

#include <latbench/stim.h>

#define USER_NODE DT_PATH(zephyr_user)
#define RCC_NODE  DT_NODELABEL(rcc)

/* TIM2 must run at the core clock (APB1 timer clock = HCLK). */
BUILD_ASSERT(DT_PROP(RCC_NODE, ahb_prescaler) == 1 && DT_PROP(RCC_NODE, apb1_prescaler) == 1,
	     "TIM2 must run at the core clock");

/*
 * The tick phase needs the system timer and TIM2 to count the same clock,
 * and a cycle counter with the tick grid of the timer driver.
 */
BUILD_ASSERT(IS_ENABLED(CONFIG_CORTEX_M_SYSTICK) && IS_ENABLED(CONFIG_TIMER_HAS_64BIT_CYCLE_COUNTER),
	     "the tick phase needs SysTick and k_cycle_get_64()");

/* A fixed-rate edge needs at least this many cycles between arm and edge. */
#define STIM_ARM_MARGIN 1000U

PINCTRL_DT_DEFINE(USER_NODE);

const struct gpio_dt_spec stim_resp = GPIO_DT_SPEC_GET(USER_NODE, resp_gpios);

uint32_t stim_next_ccr;
uint32_t stim_next_phase;
static uint32_t tick_period;
static uint32_t n_overruns;
/* TIM2 and k_cycle_get_64() at stim_init(), for the clock drift check. */
static uint32_t ref_cnt;
static uint64_t ref_cyc;

#if defined(CONFIG_LATBENCH_STIM_RANDOM)
static uint32_t stim_min;
static uint32_t stim_span;
static uint32_t rng_state = 0x2545f491U;

static inline uint32_t rng_next(void)
{
	uint32_t x = rng_state;

	x ^= x << 13;
	x ^= x >> 17;
	x ^= x << 5;
	rng_state = x;
	return x;
}
#else
static uint32_t stim_period;
static bool started;
#endif

uint32_t stim_tick_period(void)
{
	return tick_period;
}

/*
 * The tick phase of a future TIM2 time. The tick grid is in the count of
 * k_cycle_get_64(), and that count loses cycles against TIM2 (each SysTick
 * reprogram loses a few, see the clock_drift_cyc output). So take the
 * phase from a pair of fresh readings, not from a reference of the past.
 */
static uint32_t phase_of(uint32_t t)
{
	unsigned int key = irq_lock();
	uint32_t cnt = TIM2->CNT;
	uint64_t cyc = k_cycle_get_64();

	irq_unlock(key);
	/* t is less than 2^31 cycles after cnt. */
	return (uint32_t)((cyc + (uint32_t)(t - cnt)) % tick_period);
}

void stim_arm(uint32_t now)
{
	uint32_t next;

	LL_TIM_OC_SetMode(TIM2, LL_TIM_CHANNEL_CH4, LL_TIM_OCMODE_FORCED_INACTIVE);
#if defined(CONFIG_LATBENCH_STIM_RANDOM)
	next = now + stim_min + (rng_next() % stim_span);
#else
	next = stim_next_ccr + stim_period;
	if (!started) {
		/* The first edge: there is no previous edge yet. */
		started = true;
		next = now + stim_period;
	} else if ((int32_t)(next - now) < (int32_t)STIM_ARM_MARGIN) {
		/* Too late for this edge: start a new period from now. */
		n_overruns++;
		next = now + stim_period;
	}
#endif
	stim_next_phase = phase_of(next);
	stim_next_ccr = next;
	LL_TIM_OC_SetCompareCH4(TIM2, next);
	LL_TIM_ClearFlag_CC4(TIM2);
	LL_TIM_OC_SetMode(TIM2, LL_TIM_CHANNEL_CH4, LL_TIM_OCMODE_ACTIVE);
}

/*
 * The timer driver keeps its tick boundaries at multiples of the tick
 * period in the count of k_cycle_get_64(). Set the first reference, for
 * phase_check() before the first stim_arm().
 */
static void phase_init(void)
{
	unsigned int key = irq_lock();
	uint32_t cnt = TIM2->CNT;
	uint64_t cyc = k_cycle_get_64();

	irq_unlock(key);
	ref_cnt = cnt;
	ref_cyc = cyc;
	stim_next_ccr = cnt;
	stim_next_phase = (uint32_t)(cyc % tick_period);
}

/*
 * TIM2 and the system timer count the same clock. Print how many cycles
 * k_cycle_get_64() fell behind TIM2 since stim_init() (negative: it ran
 * ahead). TIM2 wraps every 25 s, so the 32-bit difference is exact only
 * while the drift is less than 2^31 cycles.
 */
static void drift_check(void)
{
	unsigned int key = irq_lock();
	uint32_t cnt = TIM2->CNT;
	uint64_t cyc = k_cycle_get_64();

	irq_unlock(key);
	printk("LAT META clock_elapsed_cyc=%llu\n", cyc - ref_cyc);
	printk("LAT META clock_drift_cyc=%d\n", (int32_t)((cnt - ref_cnt) - (uint32_t)(cyc - ref_cyc)));
}

/*
 * Check the phase: a thread that sleeps for one tick wakes shortly after
 * a tick boundary, so its phase must be small (the timer ISR and one
 * switch, about 1000 to 3000 cycles at 170 MHz).
 */
static void phase_check(const char *key)
{
	uint32_t now;

	k_sleep(K_TICKS(1));
	now = TIM2->CNT;
	printk("LAT META %s=%u\n", key, (stim_next_phase + (now - stim_next_ccr)) % tick_period);
}

int stim_init(void)
{
	const struct device *clk = DEVICE_DT_GET(STM32_CLOCK_CONTROL_NODE);
	const struct stm32_pclken pclken = STM32_CLOCK_INFO(0, DT_NODELABEL(timers2));
	uint32_t cyc_per_us = sys_clock_hw_cycles_per_sec() / 1000000U;
	int ret;

	tick_period = sys_clock_hw_cycles_per_sec() / CONFIG_SYS_CLOCK_TICKS_PER_SEC;
#if defined(CONFIG_LATBENCH_STIM_RANDOM)
	stim_min = CONFIG_LATBENCH_STIM_MIN_US * cyc_per_us;
	stim_span = (CONFIG_LATBENCH_STIM_MAX_US - CONFIG_LATBENCH_STIM_MIN_US) * cyc_per_us;
	printk("LAT META stim_mode=random\n");
	printk("LAT META stim_us=%u..%u\n", CONFIG_LATBENCH_STIM_MIN_US,
	       CONFIG_LATBENCH_STIM_MAX_US);
#else
	stim_period = CONFIG_LATBENCH_STIM_PERIOD_US * cyc_per_us + CONFIG_LATBENCH_STIM_PERIOD_ADJ_CYC;
	printk("LAT META stim_mode=fixed\n");
	printk("LAT META stim_period_cyc=%u\n", stim_period);
#endif
	printk("LAT META tick_period_cyc=%u\n", tick_period);

	if (!gpio_is_ready_dt(&stim_resp)) {
		return -ENODEV;
	}
	ret = gpio_pin_configure_dt(&stim_resp, GPIO_INPUT);
	if (ret < 0) {
		return ret;
	}
	ret = clock_control_on(clk, (clock_control_subsys_t)&pclken);
	if (ret < 0) {
		return ret;
	}
	ret = pinctrl_apply_state(PINCTRL_DT_DEV_CONFIG_GET(USER_NODE), PINCTRL_STATE_DEFAULT);
	if (ret < 0) {
		return ret;
	}

	LL_TIM_DisableCounter(TIM2);
	LL_TIM_SetPrescaler(TIM2, 0);
	LL_TIM_SetAutoReload(TIM2, UINT32_MAX);
	LL_TIM_OC_DisablePreload(TIM2, LL_TIM_CHANNEL_CH4);
	LL_TIM_OC_SetPolarity(TIM2, LL_TIM_CHANNEL_CH4, LL_TIM_OCPOLARITY_HIGH);
	LL_TIM_OC_SetMode(TIM2, LL_TIM_CHANNEL_CH4, LL_TIM_OCMODE_FORCED_INACTIVE);
	LL_TIM_CC_EnableChannel(TIM2, LL_TIM_CHANNEL_CH4);
	LL_TIM_GenerateEvent_UPDATE(TIM2);
	LL_TIM_EnableCounter(TIM2);

	phase_init();
	phase_check("tick_phase_check");
	return 0;
}

void stim_print_stats(void)
{
	printk("LAT META stim_overruns=%u\n", n_overruns);
	drift_check();
	/* The same check after the run: a clock drift shows here. */
	phase_check("tick_phase_check_end");
}

bool stim_static_check(void)
{
	int lo;
	int hi;

	LL_TIM_OC_SetMode(TIM2, LL_TIM_CHANNEL_CH4, LL_TIM_OCMODE_FORCED_INACTIVE);
	k_busy_wait(10);
	lo = gpio_pin_get_dt(&stim_resp);
	LL_TIM_OC_SetMode(TIM2, LL_TIM_CHANNEL_CH4, LL_TIM_OCMODE_FORCED_ACTIVE);
	k_busy_wait(10);
	hi = gpio_pin_get_dt(&stim_resp);
	LL_TIM_OC_SetMode(TIM2, LL_TIM_CHANNEL_CH4, LL_TIM_OCMODE_FORCED_INACTIVE);
	k_busy_wait(10);

	printk("LAT META static_check=%s\n", (lo == 0 && hi == 1) ? "ok" : "fail");
	return lo == 0 && hi == 1;
}

void stim_exti0_init(void)
{
	LL_APB2_GRP1_EnableClock(LL_APB2_GRP1_PERIPH_SYSCFG);
	LL_SYSCFG_SetEXTISource(LL_SYSCFG_EXTI_PORTB, LL_SYSCFG_EXTI_LINE0);
	LL_EXTI_EnableRisingTrig_0_31(LL_EXTI_LINE_0);
	LL_EXTI_DisableFallingTrig_0_31(LL_EXTI_LINE_0);
	LL_EXTI_ClearFlag_0_31(LL_EXTI_LINE_0);
	LL_EXTI_EnableIT_0_31(LL_EXTI_LINE_0);
}
