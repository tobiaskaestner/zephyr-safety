/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @file
 * @brief Load generators: filler threads and kernel timers (plan §2.4).
 *
 * Kconfig sets the number and the kind of each load (LATBENCH_LOAD_*).
 * All random values come from a fixed seed, so each run starts the same
 * load.
 *
 * The load timers also record the tick phase of their expiry function in
 * the phase histogram "tmr" (the value is the phase itself). The expiry
 * function runs in the system timer ISR, so this shows where in the tick
 * the timer ISR runs.
 *
 * On a SysTick system, load_start() also sets the SysTick priority if
 * LATBENCH_SYSTICK_PRIO is 0 or more.
 */

#ifndef LATBENCH_LOAD_H_
#define LATBENCH_LOAD_H_

/**
 * Start the load. Call it after stim_init() (for the tick period) and
 * before the first stim_arm().
 */
void load_start(void);

/** Stop the load timers, then print the load settings and counters. */
void load_print(void);

#endif /* LATBENCH_LOAD_H_ */
