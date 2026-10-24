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

PINCTRL_DT_DEFINE(USER_NODE);

static const struct gpio_dt_spec resp = GPIO_DT_SPEC_GET(USER_NODE, resp_gpios);

uint32_t stim_next_ccr;
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

void stim_arm(uint32_t now)
{
	LL_TIM_OC_SetMode(TIM2, LL_TIM_CHANNEL_CH4, LL_TIM_OCMODE_FORCED_INACTIVE);
	stim_next_ccr = now + stim_min + (rng_next() % stim_span);
	LL_TIM_OC_SetCompareCH4(TIM2, stim_next_ccr);
	LL_TIM_ClearFlag_CC4(TIM2);
	LL_TIM_OC_SetMode(TIM2, LL_TIM_CHANNEL_CH4, LL_TIM_OCMODE_ACTIVE);
}

int stim_init(uint32_t min_us, uint32_t max_us)
{
	const struct device *clk = DEVICE_DT_GET(STM32_CLOCK_CONTROL_NODE);
	const struct stm32_pclken pclken = STM32_CLOCK_INFO(0, DT_NODELABEL(timers2));
	uint32_t cyc_per_us = sys_clock_hw_cycles_per_sec() / 1000000U;
	int ret;

	stim_min = min_us * cyc_per_us;
	stim_span = (max_us - min_us) * cyc_per_us;

	if (!gpio_is_ready_dt(&resp)) {
		return -ENODEV;
	}
	ret = gpio_pin_configure_dt(&resp, GPIO_INPUT);
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

	printk("LAT META stim_us=%u..%u\n", min_us, max_us);
	return 0;
}

bool stim_static_check(void)
{
	int lo;
	int hi;

	LL_TIM_OC_SetMode(TIM2, LL_TIM_CHANNEL_CH4, LL_TIM_OCMODE_FORCED_INACTIVE);
	k_busy_wait(10);
	lo = gpio_pin_get_dt(&resp);
	LL_TIM_OC_SetMode(TIM2, LL_TIM_CHANNEL_CH4, LL_TIM_OCMODE_FORCED_ACTIVE);
	k_busy_wait(10);
	hi = gpio_pin_get_dt(&resp);
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
