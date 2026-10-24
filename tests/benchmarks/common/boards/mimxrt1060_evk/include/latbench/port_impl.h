/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Fast functions of the mimxrt1060_evk port (see latbench/port.h). GPT2 is
 * a 32-bit timer at PERCLK (75 MHz, 8 core cycles per count). Compare
 * channel 1 drives A3. The response pin D2 is GPIO1_IO11, and its
 * interrupt is the GPIO1 interrupt for pins 0 to 15.
 */

#ifndef LATBENCH_PORT_IMPL_H_
#define LATBENCH_PORT_IMPL_H_

#include <stdbool.h>
#include <stdint.h>
#include <zephyr/devicetree.h>
#include <zephyr/sys/util_macro.h>
#include <soc.h>

#define PORT_RESP_GPIO GPIO1
#define PORT_RESP_PIN  11
#define PORT_RESP_IRQN GPIO1_Combined_0_15_IRQn

/* 1 if interrupt idx of the gpio1 node is IRQ 80 (pins 0 to 15). */
#define PORT_GPIO1_IRQ_IS_RESP(idx)                                                                \
	COND_CODE_1(DT_IRQ_HAS_IDX(DT_NODELABEL(gpio1), idx),                                      \
		    ((DT_IRQ_BY_IDX(DT_NODELABEL(gpio1), idx, irq) == GPIO1_Combined_0_15_IRQn)),  \
		    (0))

/* resp_irq_own.overlay removes IRQ 80 from the interrupts of the GPIO driver. */
#define PORT_RESP_IRQ_OWNED (!PORT_GPIO1_IRQ_IS_RESP(0) && !PORT_GPIO1_IRQ_IS_RESP(1))

static inline uint32_t port_stim_now(void)
{
	return GPT2->CNT;
}

static inline bool port_stim_fired(void)
{
	return (GPT2->SR & GPT_SR_OF1_MASK) != 0U;
}

static inline void port_resp_ack(void)
{
	PORT_RESP_GPIO->ISR = BIT(PORT_RESP_PIN);
	/*
	 * Make sure that the write is complete before the ISR returns.
	 * Else the NVIC can see the old request and enter the ISR again.
	 */
	__DSB();
}

#endif /* LATBENCH_PORT_IMPL_H_ */
