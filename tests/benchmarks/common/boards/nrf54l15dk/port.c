/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Board port nrf54l15dk (see latbench/port.h): TIMER00 CC[0] -> DPPIC00
 * -> PPIB -> DPPIC20 -> GPIOTE20 SET task on P1.11. Response on P1.12,
 * GPIOTE20 IRQ.
 */

#include <latbench/port.h>

/* TIMER00 counts the core clock, so a latency is in core cycles. */
BUILD_ASSERT(NRF_TIMER_IS_128MHZ_TIMER(NRF_TIMER00), "TIMER00 does not run at 128 MHz");

const char *const port_name = "nrf54l15dk/timer00-dppi-gpiote20";

#include "../nordic/nrf_port.c"
