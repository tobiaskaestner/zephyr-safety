/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Board port nucleo_g474re (see latbench/port.h). TIM2 channel 4 output
 * compare drives D2 (PA10). The response pin A3 (PB0) is EXTI line 0.
 */

#include <zephyr/kernel.h>
#include <zephyr/drivers/pinctrl.h>
#include <zephyr/drivers/clock_control.h>
#include <zephyr/drivers/clock_control/stm32_clock_control.h>
#include <zephyr/sys/printk.h>

#include <stm32_ll_bus.h>
#include <stm32_ll_exti.h>
#include <stm32_ll_system.h>

#include <latbench/port.h>

#define USER_NODE DT_PATH(zephyr_user)
#define RCC_NODE  DT_NODELABEL(rcc)

/* TIM2 must run at the core clock (APB1 timer clock = HCLK). */
BUILD_ASSERT(DT_PROP(RCC_NODE, ahb_prescaler) == 1 && DT_PROP(RCC_NODE, apb1_prescaler) == 1,
	     "TIM2 must run at the core clock");

/* The system timer counts the core clock too, so the tick phase needs no scaling. */
BUILD_ASSERT(IS_ENABLED(CONFIG_CORTEX_M_SYSTICK), "the port expects SysTick as system timer");

PINCTRL_DT_DEFINE(USER_NODE);

const char *const port_name = "nucleo_g474re/tim2_ch4-exti0";

int port_stim_init(void)
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

	LL_TIM_DisableCounter(TIM2);
	LL_TIM_SetPrescaler(TIM2, 0);
	LL_TIM_SetAutoReload(TIM2, UINT32_MAX);
	LL_TIM_OC_DisablePreload(TIM2, LL_TIM_CHANNEL_CH4);
	LL_TIM_OC_SetPolarity(TIM2, LL_TIM_CHANNEL_CH4, LL_TIM_OCPOLARITY_HIGH);
	LL_TIM_OC_SetMode(TIM2, LL_TIM_CHANNEL_CH4, LL_TIM_OCMODE_FORCED_INACTIVE);
	LL_TIM_CC_EnableChannel(TIM2, LL_TIM_CHANNEL_CH4);
	LL_TIM_GenerateEvent_UPDATE(TIM2);
	LL_TIM_EnableCounter(TIM2);
	return 0;
}

uint32_t port_stim_hz(void)
{
	return sys_clock_hw_cycles_per_sec();
}

uint32_t port_core_hz(void)
{
	return sys_clock_hw_cycles_per_sec();
}

void port_stim_set(uint32_t at)
{
	LL_TIM_OC_SetMode(TIM2, LL_TIM_CHANNEL_CH4, LL_TIM_OCMODE_FORCED_INACTIVE);
	LL_TIM_OC_SetCompareCH4(TIM2, at);
	LL_TIM_ClearFlag_CC4(TIM2);
	LL_TIM_OC_SetMode(TIM2, LL_TIM_CHANNEL_CH4, LL_TIM_OCMODE_ACTIVE);
}

void port_stim_stop(void)
{
	LL_TIM_OC_SetMode(TIM2, LL_TIM_CHANNEL_CH4, LL_TIM_OCMODE_FORCED_INACTIVE);
}

void port_stim_force(bool high)
{
	LL_TIM_OC_SetMode(TIM2, LL_TIM_CHANNEL_CH4,
			  high ? LL_TIM_OCMODE_FORCED_ACTIVE : LL_TIM_OCMODE_FORCED_INACTIVE);
}

void port_resp_irq_init(void)
{
	LL_APB2_GRP1_EnableClock(LL_APB2_GRP1_PERIPH_SYSCFG);
	LL_SYSCFG_SetEXTISource(LL_SYSCFG_EXTI_PORTB, LL_SYSCFG_EXTI_LINE0);
	LL_EXTI_EnableRisingTrig_0_31(LL_EXTI_LINE_0);
	LL_EXTI_DisableFallingTrig_0_31(LL_EXTI_LINE_0);
	LL_EXTI_ClearFlag_0_31(LL_EXTI_LINE_0);
	LL_EXTI_EnableIT_0_31(LL_EXTI_LINE_0);
}

void port_debug_reset(char *buf, size_t len)
{
	/*
	 * A debugger session can leave DBGMCU bits set that keep the clocks
	 * on in sleep modes. Clear them, so that WFI behaves as without a
	 * debugger.
	 */
	snprintk(buf, len, "0x%08x", DBGMCU->CR);
	DBGMCU->CR = 0;
}
