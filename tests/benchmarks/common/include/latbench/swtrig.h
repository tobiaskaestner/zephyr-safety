/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @file
 * @brief Software trigger: a thread pends the response IRQ with NVIC STIR.
 *
 * Only with CONFIG_LATBENCH_SWTRIG. The app alternates the stimuli: after
 * an edge sample it calls swtrig_request(). The trigger thread then waits
 * a random gap (stim_gap()), sets swtrig_pending, reads the stimulus timer
 * (t0) and writes the response IRQ to NVIC STIR. The ISR of the response
 * IRQ calls swtrig_take() first: for a software sample it stores its own
 * time stamp and returns true.
 *
 * Time stamps: t0 and the time stamp of the ISR are reads of the same
 * counter register through the same bus, so the bus delay of the read
 * cancels. The software sample includes the rest of the read of t0, one
 * store of t0 to RAM and the STIR store. The app prints the cost of one
 * read as LAT META sw_read_cyc.
 */

#ifndef LATBENCH_SWTRIG_H_
#define LATBENCH_SWTRIG_H_

#include <stdbool.h>
#include <stdint.h>

#if defined(CONFIG_LATBENCH_SWTRIG)

/** True from just before t0 until the ISR took the software sample. */
extern volatile bool swtrig_pending;
/** The start time stamp of the current software sample. */
extern volatile uint32_t swtrig_t0;
/** The time stamp of the ISR of the current software sample. */
extern volatile uint32_t swtrig_isr;

/**
 * Call it first in the ISR, with the time stamp of the ISR. Returns true
 * for a software sample: the ISR must then not treat the entry as an edge.
 */
static inline bool swtrig_take(uint32_t now)
{
	if (!swtrig_pending) {
		return false;
	}
	swtrig_isr = now;
	swtrig_pending = false;
	return true;
}

/**
 * Function that the trigger thread calls after each software sample, with
 * the start time stamp and the ISR time stamp. NULL: no call (the woken
 * thread of the app takes the sample).
 */
typedef void (*swtrig_done_fn)(uint32_t t0, uint32_t t_isr);

/** Start the trigger thread at the thread priority prio. */
void swtrig_start(int prio, swtrig_done_fn done);

/** Start the next software sample (from an ISR or a thread). */
void swtrig_request(void);

/** Print LAT META sw_trigger, sw_trigger_irqn, sw_trigger_prio, sw_read_cyc, sw_triggers. */
void swtrig_print_setup(void);
void swtrig_print_stats(void);

#endif /* CONFIG_LATBENCH_SWTRIG */

#endif /* LATBENCH_SWTRIG_H_ */
