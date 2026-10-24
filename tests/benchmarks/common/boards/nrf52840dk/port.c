/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Board port nrf52840dk (see latbench/port.h): TIMER3 CC[0] -> PPI ->
 * GPIOTE SET task on D2 (P1.03). Response on A3 (P0.29), GPIOTE IRQ 6.
 */

#include <latbench/port.h>

const char *const port_name = "nrf52840dk/timer3-ppi-gpiote";

#include "../nordic/nrf_port.c"
