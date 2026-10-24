/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Fast functions of the nrf52840dk port (see latbench/port.h). TIMER3
 * counts at 16 MHz (4 core cycles at 64 MHz). The GPIOTE drives D2
 * (P1.03) and sees the edge on A3 (P0.29).
 */

#ifndef LATBENCH_PORT_IMPL_H_
#define LATBENCH_PORT_IMPL_H_

#define PORT_NRF_TIMER       NRF_TIMER3
#define PORT_NRF_TIMER_NODE  DT_NODELABEL(timer3)
#define PORT_NRF_GPIOTE_NODE DT_NODELABEL(gpiote)
#define PORT_NRF_HFXO_NODE   DT_NODELABEL(hfclk)

#include "../../../nordic/nrf_port_impl.h"

#endif /* LATBENCH_PORT_IMPL_H_ */
