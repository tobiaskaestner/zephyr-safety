/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @file
 * @brief Tail witnesses: what happened during the largest samples.
 *
 * Only with CONFIG_LATBENCH_TAIL (Cortex-M with DWT and SysTick). A table
 * keeps the CONFIG_LATBENCH_TAIL_N largest samples of one histogram with a
 * value of CONFIG_LATBENCH_TAIL_MIN_CYC or more. For each kept sample it
 * has the counters of a window around the sample:
 *
 * - lat_tail_mark() takes the start of the window. The app calls it when
 *   it arms the stimulus, before the sample starts.
 * - lat_tail_add() takes the end of the window, after the end time stamp
 *   of the sample. It is not inline: the code before the time stamp of the
 *   app does not change.
 *
 * The counters:
 *
 * - win: counts of the stimulus timer from the mark to the add.
 * - exc: DWT EXCCNT (cycles of exception entry and exit, 8 bits) in the
 *   window. Each exception adds to it.
 * - st0, st1: SysTick VAL at the mark and at the add. Without a reload,
 *   st0 - st1 = win (if SysTick counts the clock of the stimulus timer).
 *   A difference shows a SysTick wrap (its interrupt) or a reprogram of
 *   the driver in the window. A read of VAL does not clear COUNTFLAG, so
 *   the driver does not see it.
 * - ld: SysTick LOAD at the add. After a jump, ld - st1 is the time since
 *   the last reload or reprogram of SysTick, so the host can tell if the
 *   system timer was active during the sample or only earlier in the
 *   window.
 * - tmr, wake: expiries of the load timers and wakes of the sleeper
 *   threads in the window (latbench/load.h).
 * - pc, icsr: the PC that the interrupt of the sample interrupted (the
 *   stacked PC on PSP), and SCB ICSR. Only if the app gives them; pc is 0
 *   if the ISR preempted another exception (ICSR RETTOBASE is 0).
 *
 * The kernel tick count is not a witness here: with the tickless kernel
 * it counts time, not system timer interrupts.
 */

#ifndef LATBENCH_TAIL_H_
#define LATBENCH_TAIL_H_

#include <stdint.h>

#if defined(CONFIG_LATBENCH_TAIL)

#include <cmsis_core.h>
#include <latbench/load.h>
#include <latbench/stim.h>

struct lat_tail_mark {
	uint32_t cnt;
	uint32_t exc;
	uint32_t st;
	uint32_t tmr;
	uint32_t wake;
};

struct lat_tail_row {
	uint32_t seq;
	uint32_t lat;
	uint32_t aux;
	uint32_t phase;
	uint32_t win;
	uint32_t exc;
	uint32_t st0;
	uint32_t st1;
	uint32_t ld;
	uint32_t tmr;
	uint32_t wake;
	uint32_t pc;
	uint32_t icsr;
};

struct lat_tail {
	const char *name;
	/** Samples of CONFIG_LATBENCH_TAIL_MIN_CYC or more. */
	uint32_t seen;
	/** Rows in use. */
	uint32_t n;
	/** The smallest lat in the full table, and its row. */
	uint32_t low;
	uint32_t low_i;
	/** Smallest and largest exc of all samples: the exc of a sample without other exceptions. */
	uint32_t exc_min;
	uint32_t exc_max;
	struct lat_tail_row rows[CONFIG_LATBENCH_TAIL_N];
};

#define LAT_TAIL_DEFINE(_var, _name) struct lat_tail _var = {.name = (_name), .exc_min = UINT32_MAX}

/** Enable the DWT exception counter. Call it once before the first mark. */
void lat_tail_init(void);

/** The start of the window of the next sample. */
static inline void lat_tail_mark(struct lat_tail_mark *m)
{
	m->cnt = stim_now();
	m->exc = DWT->EXCCNT;
	m->st = SysTick->VAL;
	m->tmr = load_timer_count();
	m->wake = load_wake_count();
}

/** No interrupted context (lat_tail_add() outside the ISR of the sample). */
#define LAT_TAIL_NO_CTX 0
/** lat_tail_add() runs in the ISR of the sample: it reads the interrupted context itself. */
#define LAT_TAIL_ISR_CTX 1

/**
 * The end of the window: add the sample. seq is the number of the sample,
 * aux a second value of the app (0 if none), phase the tick phase of the
 * stimulus. ctx is LAT_TAIL_ISR_CTX or LAT_TAIL_NO_CTX.
 */
void lat_tail_add(struct lat_tail *t, const struct lat_tail_mark *m, uint32_t seq, uint32_t lat,
		  uint32_t aux, uint32_t phase, int ctx);

/** Print the table in the LAT line format (LAT TAIL, LAT TW, LAT END). */
void lat_tail_print(const struct lat_tail *t);

/** Measure the cost of the witness calls and print it as LAT META tail_*. */
void lat_tail_print_setup(void);

#endif /* CONFIG_LATBENCH_TAIL */

#endif /* LATBENCH_TAIL_H_ */
