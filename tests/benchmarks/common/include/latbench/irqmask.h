/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @file
 * @brief M4: interrupt mask time per call site (common/src/irqmask.c).
 *
 * The functions do something only in a build with
 * CONFIG_ARM_IRQ_MASK_HOOKS (a Zephyr tree with the branch
 * tkaestner/latency-irqoff-hook). In all other builds they are empty, so
 * an app can call them always.
 *
 * Call irqmask_start() after the setup and before the stimulus starts,
 * irqmask_stop() at the end of the run, and irqmask_print() before
 * lat_done().
 */

#ifndef LATBENCH_IRQMASK_H_
#define LATBENCH_IRQMASK_H_

#if defined(CONFIG_ARM_IRQ_MASK_HOOKS)

/** Enable the DWT counter, calibrate, clear the table and start to record. */
void irqmask_start(void);
/** Stop to record. */
void irqmask_stop(void);
/** Print the calibration, the totals and the site table in the LAT format. */
void irqmask_print(void);

#else

static inline void irqmask_start(void)
{
}

static inline void irqmask_stop(void)
{
}

static inline void irqmask_print(void)
{
}

#endif

#endif /* LATBENCH_IRQMASK_H_ */
