/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * The scenarios of irq_latency other than the entry
 * (LATBENCH_IRQ_SCENARIO, see scenario.c). main() calls scen_main() after
 * stim_init().
 */

#ifndef IRQ_LATENCY_SCENARIO_H_
#define IRQ_LATENCY_SCENARIO_H_

/** Set up the ISRs, run all samples in the calling thread, print the results. */
void scen_main(void);

#endif /* IRQ_LATENCY_SCENARIO_H_ */
