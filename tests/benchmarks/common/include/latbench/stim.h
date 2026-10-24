/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @file
 * @brief Hardware stimulus on nucleo_g474re: TIM2 channel 4 on PA10.
 *
 * TIM2 runs at the core clock. stim_arm() programs a rising edge on PA10
 * at a random time in the future and stim_edge() returns its time stamp
 * (the compare value). The wire D2 (PA10) -> A3 (PB0) takes the edge to
 * EXTI line 0. stim_now() reads the counter, so stim_now() - stim_edge()
 * is the time since the edge in core cycles.
 *
 * The app overlay must give the zephyr,user node "pinctrl-0 =
 * <&tim2_ch4_pa10>", "resp-gpios" (PB0), and disable pwm2.
 */

#ifndef LATBENCH_STIM_H_
#define LATBENCH_STIM_H_

#include <stdbool.h>
#include <stdint.h>
#include <soc.h>
#include <stm32_ll_tim.h>

extern uint32_t stim_next_ccr;

/** Set up TIM2, the PA10 pin function and the PB0 input. */
int stim_init(uint32_t min_us, uint32_t max_us);

/** Drive PA10 low and high and read PB0. Print the result as LAT META. */
bool stim_static_check(void);

/** Route PB0 to EXTI line 0, rising edge, and enable the line (not the NVIC IRQ). */
void stim_exti0_init(void);

static inline uint32_t stim_now(void)
{
	return TIM2->CNT;
}

static inline uint32_t stim_edge(void)
{
	return stim_next_ccr;
}

/**
 * True if TIM2 reached the compare value since the last stim_arm(). An
 * EXTI0 interrupt without this flag did not come from the stimulus.
 */
static inline bool stim_fired(void)
{
	return LL_TIM_IsActiveFlag_CC4(TIM2) != 0U;
}

/** Program the next edge at a random time after now. */
void stim_arm(uint32_t now);

/** Drive PA10 low and program no new edge. */
static inline void stim_stop(void)
{
	LL_TIM_OC_SetMode(TIM2, LL_TIM_CHANNEL_CH4, LL_TIM_OCMODE_FORCED_INACTIVE);
}

#endif /* LATBENCH_STIM_H_ */
