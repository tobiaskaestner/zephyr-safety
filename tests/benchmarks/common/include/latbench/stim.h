/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @file
 * @brief Hardware stimulus: a timer output compare drives a pin.
 *
 * The board port (latbench/port.h) supplies the timer and the pins.
 * stim_arm() programs a rising edge on the stimulus pin at a time in the
 * future and stim_edge() returns its time stamp (the compare value). A
 * wire takes the edge to the response pin. stim_now() reads the counter,
 * so stim_now() - stim_edge() is the time since the edge in counts of the
 * stimulus timer (core cycles, if the timer runs at the core clock).
 *
 * The time to the next edge is random or fixed (LATBENCH_STIM_MODE).
 * stim_edge_phase() gives the position of the edge in the kernel tick
 * (0 .. stim_tick_period() - 1 system timer cycles). The system timer
 * interrupts come at phase 0.
 */

#ifndef LATBENCH_STIM_H_
#define LATBENCH_STIM_H_

#include <stdbool.h>
#include <stdint.h>
#include <zephyr/drivers/gpio.h>

#include <latbench/port.h>

/** The response pin ("resp-gpios" of the zephyr,user node). */
extern const struct gpio_dt_spec stim_resp;

extern uint32_t stim_next_ccr;
extern uint32_t stim_next_phase;

/**
 * Set up the stimulus timer and pins (port_stim_init()) and the response
 * input, and find the tick phase of the timer. Print the stimulus
 * settings as LAT META. Sleeps for one tick.
 */
int stim_init(void);

/** Drive the stimulus pin low and high and read the response pin. Print the result as LAT META. */
bool stim_static_check(void);

/**
 * Make the response pin an interrupt on the rising edge, for an app with
 * its own ISR on STIM_RESP_IRQN. The app enables the IRQ itself.
 */
static inline void stim_resp_irq_init(void)
{
	port_resp_irq_init();
}

/** The IRQ line of the response pin, for an app with its own ISR. */
#define STIM_RESP_IRQN PORT_RESP_IRQN

/** Clear the pending flag of the response interrupt (own ISR only). */
static inline void stim_resp_ack(void)
{
	port_resp_ack();
}

static inline uint32_t stim_now(void)
{
	return port_stim_now();
}

/** Time stamp of the current edge (stimulus timer counts). */
static inline uint32_t stim_edge(void)
{
	return stim_next_ccr;
}

/** Tick phase of the current edge, in cycles after the tick boundary. */
static inline uint32_t stim_edge_phase(void)
{
	return stim_next_phase;
}

/** Length of a kernel tick in system timer cycles. */
uint32_t stim_tick_period(void);

/**
 * True if the timer reached the compare value since the last stim_arm().
 * A response interrupt without this flag did not come from the stimulus.
 */
static inline bool stim_fired(void)
{
	return port_stim_fired();
}

/**
 * Program the next edge. now is the current count of the stimulus timer. Read stim_edge()
 * and stim_edge_phase() of the current edge before this call.
 */
void stim_arm(uint32_t now);

/** Drive the stimulus pin low and program no new edge. */
static inline void stim_stop(void)
{
	port_stim_stop();
}

/** Print the counters of the stimulus (overruns) as LAT META. */
void stim_print_stats(void);

#endif /* LATBENCH_STIM_H_ */
