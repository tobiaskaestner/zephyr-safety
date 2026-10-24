/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @file
 * @brief Board port: the hardware that the stimulus needs.
 *
 * Each board has a folder common/boards/<board>/ (the board name without
 * qualifiers and revision). common/latbench_board.cmake selects it from
 * BOARD. A port supplies:
 *
 * - port.cmake: the devicetree overlays (and Kconfig fragments) of the
 *   port. If LATBENCH_RESP_IRQ_OWN is set, the app connects the
 *   interrupt of the response pin itself, and the port must take it
 *   away from the GPIO driver.
 * - include/latbench/port_impl.h: the fast functions below as static
 *   inline functions, and the macro PORT_RESP_IRQN.
 * - port.c: the other functions below.
 *
 * The stimulus timer is a free-running 32-bit up-counter with an output
 * compare channel. At the compare value the hardware drives the stimulus
 * pin high, with no software in the path. A wire takes the edge to the
 * response pin. The response pin is the "resp-gpios" of the zephyr,user
 * node.
 *
 * Time stamps are counts of the stimulus timer. If the timer does not run
 * at the core clock, the app output gives both clocks (stim_timer_hz and
 * core_hz).
 */

#ifndef LATBENCH_PORT_H_
#define LATBENCH_PORT_H_

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/*
 * Fast functions, in port_impl.h:
 *
 *   uint32_t port_stim_now(void)     the counter of the stimulus timer
 *   bool port_stim_fired(void)       the compare flag is set (the edge
 *                                    came from the timer)
 *   void port_resp_ack(void)         clear the pending flag of the
 *                                    response interrupt (own ISR only)
 *   PORT_RESP_IRQN                   the IRQ line of the response pin
 *                                    (own ISR only)
 *   PORT_RESP_IRQ_OWNED              1 if the devicetree gives the
 *                                    response interrupt to the app, 0 if
 *                                    the GPIO driver has it
 */
#include <latbench/port_impl.h>

/** Name of the port, for the output. */
extern const char *const port_name;

/**
 * Start the stimulus timer (free-running, 32 bits) and set up the
 * stimulus pin with the output low.
 */
int port_stim_init(void);

/** Clock of the stimulus timer in Hz. */
uint32_t port_stim_hz(void);

/** Clock of the CPU core in Hz. */
uint32_t port_core_hz(void);

/**
 * Drive the stimulus pin low, then make the hardware drive it high when
 * the counter reaches at. Clear the compare flag.
 */
void port_stim_set(uint32_t at);

/** Drive the stimulus pin low and keep it low. */
void port_stim_stop(void);

/** Drive the stimulus pin to a fixed level (for the static check). */
void port_stim_force(bool high);

/**
 * Configure the response pin as an interrupt on the rising edge, for an
 * app with its own ISR. The app enables PORT_RESP_IRQN itself.
 */
void port_resp_irq_init(void);

/**
 * Undo debugger settings that change the behaviour of the core in sleep
 * (for example clocks that stay on). Write the old value as text to buf.
 */
void port_debug_reset(char *buf, size_t len);

#endif /* LATBENCH_PORT_H_ */
