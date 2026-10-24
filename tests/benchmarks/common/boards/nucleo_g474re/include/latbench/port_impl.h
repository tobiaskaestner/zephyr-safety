/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Fast functions of the nucleo_g474re port (see latbench/port.h). TIM2 is
 * a 32-bit timer at the core clock. Channel 4 drives PA10. The response
 * pin PB0 is EXTI line 0.
 */

#ifndef LATBENCH_PORT_IMPL_H_
#define LATBENCH_PORT_IMPL_H_

#include <stdbool.h>
#include <stdint.h>
#include <zephyr/devicetree.h>
#include <soc.h>
#include <stm32_ll_exti.h>
#include <stm32_ll_tim.h>

#define PORT_RESP_IRQN EXTI0_IRQn

/* resp_irq_own.overlay removes line 0 from the EXTI interrupts of the GPIO driver. */
#define PORT_RESP_IRQ_OWNED (!DT_IRQ_HAS_NAME(DT_NODELABEL(exti), line0))

static inline uint32_t port_stim_now(void)
{
	return TIM2->CNT;
}

static inline bool port_stim_fired(void)
{
	return LL_TIM_IsActiveFlag_CC4(TIM2) != 0U;
}

static inline void port_resp_ack(void)
{
	LL_EXTI_ClearFlag_0_31(LL_EXTI_LINE_0);
}

#endif /* LATBENCH_PORT_IMPL_H_ */
