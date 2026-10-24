/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Fast functions of the Nordic ports (see latbench/port.h). The
 * port_impl.h of the board defines these macros, then includes this file:
 *
 *   PORT_NRF_TIMER        the stimulus TIMER (NRF_TIMER_Type *)
 *   PORT_NRF_TIMER_NODE   the devicetree node of that TIMER
 *   PORT_NRF_GPIOTE_NODE  the GPIOTE instance of the stimulus and the
 *                         response pin
 *   PORT_NRF_HFXO_NODE    the clock node that starts the HF crystal
 *
 * Compare channel 0 of the TIMER makes the stimulus edge. A TIMER has no
 * counter register that the CPU can read: port_stim_now() triggers the
 * capture task of channel 1 and reads CC[1]. An interrupt between the
 * two accesses can capture again. Then the interrupted code gets the
 * later value, as if it read the counter after the interrupt.
 */

#ifndef LATBENCH_NRF_PORT_IMPL_H_
#define LATBENCH_NRF_PORT_IMPL_H_

#include <stdbool.h>
#include <stdint.h>
#include <zephyr/devicetree.h>
#include <hal/nrf_gpiote.h>
#include <hal/nrf_timer.h>

/* GPIOTE channel of the response pin, if the app owns the GPIOTE IRQ. */
#define PORT_NRF_RESP_CH 1U

#define PORT_NRF_GPIOTE ((NRF_GPIOTE_Type *)DT_REG_ADDR(PORT_NRF_GPIOTE_NODE))

#define PORT_RESP_IRQN DT_IRQN(PORT_NRF_GPIOTE_NODE)

/*
 * resp_irq_own.overlay disables the GPIOTE instance, so that the GPIO
 * driver does not connect its IRQ.
 */
#define PORT_RESP_IRQ_OWNED (!DT_NODE_HAS_STATUS_OKAY(PORT_NRF_GPIOTE_NODE))

static inline uint32_t port_stim_now(void)
{
	nrf_timer_task_trigger(PORT_NRF_TIMER, NRF_TIMER_TASK_CAPTURE1);
	return nrf_timer_cc_get(PORT_NRF_TIMER, NRF_TIMER_CC_CHANNEL1);
}

static inline bool port_stim_fired(void)
{
	return nrf_timer_event_check(PORT_NRF_TIMER, NRF_TIMER_EVENT_COMPARE0);
}

static inline void port_resp_ack(void)
{
	/* The HAL reads the event back, so the IRQ does not come again. */
	nrf_gpiote_event_clear(PORT_NRF_GPIOTE, nrf_gpiote_in_event_get(PORT_NRF_RESP_CH));
}

#endif /* LATBENCH_NRF_PORT_IMPL_H_ */
