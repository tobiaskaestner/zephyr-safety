/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Fast functions of the nrf54l15dk port (see latbench/port.h). TIMER00
 * counts at the core clock (128 MHz). GPIOTE20 drives P1.11 and sees the
 * edge on P1.12.
 */

#ifndef LATBENCH_PORT_IMPL_H_
#define LATBENCH_PORT_IMPL_H_

#define PORT_NRF_TIMER       NRF_TIMER00
#define PORT_NRF_TIMER_NODE  DT_NODELABEL(timer00)
#define PORT_NRF_GPIOTE_NODE DT_NODELABEL(gpiote20)
#define PORT_NRF_HFXO_NODE   DT_NODELABEL(xo)

#include "../../../nordic/nrf_port_impl.h"

#endif /* LATBENCH_PORT_IMPL_H_ */
