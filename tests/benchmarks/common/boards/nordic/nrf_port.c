/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Common code of the Nordic ports (see latbench/port.h). The port.c of
 * a board defines port_name and includes this file. The macros come from
 * the port_impl.h of the board (see nrf_port_impl.h).
 *
 * Stimulus: the TIMER counts at prescaler 0 in 32-bit mode. At CC[0]
 * the COMPARE[0] event goes through a (D)PPI connection to the SET task
 * of a GPIOTE channel in task mode. The GPIOTE channel drives the
 * stimulus pin high, with no CPU in the path. The CPU drives the pin low
 * with the CLR task. nrfx_gppi allocates the connection. On the nRF54L
 * it can go through PPIB bridges between the domains.
 *
 * GPIOTE channels: if the GPIO driver has the GPIOTE instance (stock
 * path), the port gets the stimulus channel from the nrfx_gpiote
 * allocator of the driver. If resp_irq_own.overlay takes the instance
 * away from the driver, the port uses channel 0 for the stimulus and
 * PORT_NRF_RESP_CH for the response pin. Then nothing else uses the
 * GPIOTE.
 */

#include <zephyr/kernel.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/clock_control/nrf_clock_control.h>
#include <zephyr/sys/printk.h>
#include <helpers/nrfx_gppi.h>

#if !PORT_RESP_IRQ_OWNED
#include <zephyr/drivers/gpio/gpio_nrf.h>
#include <nrfx_gpiote.h>
#endif

#include <latbench/port.h>

#define USER_NODE      DT_PATH(zephyr_user)
#define STIM_PORT_NODE DT_GPIO_CTLR(USER_NODE, stim_gpios)
#define RESP_PORT_NODE DT_GPIO_CTLR(USER_NODE, resp_gpios)
#define STIM_PIN       NRF_DT_GPIOS_TO_PSEL(USER_NODE, stim_gpios)
#define RESP_PIN       NRF_DT_GPIOS_TO_PSEL(USER_NODE, resp_gpios)

/* GPIOTE channel of the stimulus pin, if the app owns the GPIOTE. */
#define STIM_CH_OWN 0U

/* The DHCSR register of the Cortex-M debug block (ARMv7-M and ARMv8-M). */
#define DHCSR_ADDR 0xE000EDF0UL

BUILD_ASSERT(!DT_NODE_HAS_STATUS_OKAY(PORT_NRF_TIMER_NODE),
	     "a driver uses the stimulus TIMER; disable its node");
BUILD_ASSERT(DT_NODE_HAS_STATUS_OKAY(PORT_NRF_HFXO_NODE), "the HFXO clock node is disabled");

#if !PORT_RESP_IRQ_OWNED
/* The GPIO driver gives the channels of this GPIOTE instance. */
BUILD_ASSERT(DT_SAME_NODE(DT_PHANDLE(STIM_PORT_NODE, gpiote_instance), PORT_NRF_GPIOTE_NODE),
	     "the stimulus pin is not on a port of PORT_NRF_GPIOTE_NODE");
BUILD_ASSERT(DT_SAME_NODE(DT_PHANDLE(RESP_PORT_NODE, gpiote_instance), PORT_NRF_GPIOTE_NODE),
	     "the response pin is not on a port of PORT_NRF_GPIOTE_NODE");
#endif

static uint8_t stim_ch;
static nrfx_gppi_handle_t stim_conn;
static bool stim_conn_on;

static int stim_ch_get(void)
{
#if PORT_RESP_IRQ_OWNED
	stim_ch = STIM_CH_OWN;
	return 0;
#else
	const struct device *port = DEVICE_DT_GET(STIM_PORT_NODE);
	nrfx_gpiote_t *gpiote;

	if (!device_is_ready(port)) {
		return -ENODEV;
	}
	gpiote = gpio_nrf_gpiote_by_port_get(port);
	if (gpiote == NULL) {
		return -ENODEV;
	}
	return nrfx_gpiote_channel_alloc(gpiote, &stim_ch);
#endif
}

/*
 * The system timer counts the low frequency clock (32.768 kHz crystal).
 * stim.c scales stimulus timer counts to system timer cycles for the tick
 * phase. With the internal RC oscillator (up to 1.5 % off) the scaling
 * of 1 ms is wrong by up to 15 us, which is more than a tick on the
 * nRF54L. So keep the HF crystal on for the whole run.
 */
static int hfxo_on(void)
{
	return nrf_clock_control_request_sync(DEVICE_DT_GET(PORT_NRF_HFXO_NODE), NULL,
					      K_MSEC(100));
}

int port_stim_init(void)
{
	NRF_TIMER_Type *t = PORT_NRF_TIMER;
	NRF_GPIOTE_Type *g = PORT_NRF_GPIOTE;
	uint32_t eep;
	uint32_t tep;
	int ret;

	ret = hfxo_on();
	if (ret < 0) {
		return ret;
	}
	ret = stim_ch_get();
	if (ret < 0) {
		return ret;
	}

	nrf_timer_task_trigger(t, NRF_TIMER_TASK_STOP);
	nrf_timer_task_trigger(t, NRF_TIMER_TASK_CLEAR);
	nrf_timer_mode_set(t, NRF_TIMER_MODE_TIMER);
	nrf_timer_bit_width_set(t, NRF_TIMER_BIT_WIDTH_32);
	nrf_timer_prescaler_set(t, 0);
	nrf_timer_cc_set(t, NRF_TIMER_CC_CHANNEL0, 0);
	nrf_timer_event_clear(t, NRF_TIMER_EVENT_COMPARE0);

	/* Task mode with polarity "none": only the SET and CLR tasks change the pin. */
	nrf_gpiote_task_configure(g, stim_ch, STIM_PIN, NRF_GPIOTE_POLARITY_NONE,
				  NRF_GPIOTE_INITIAL_VALUE_LOW);
	nrf_gpiote_task_enable(g, stim_ch);

	/* The connection stays disabled until the first port_stim_set(). */
	eep = nrf_timer_event_address_get(t, NRF_TIMER_EVENT_COMPARE0);
	tep = nrf_gpiote_task_address_get(g, nrf_gpiote_set_task_get(stim_ch));
	ret = nrfx_gppi_conn_alloc(eep, tep, &stim_conn);
	if (ret < 0) {
		return ret;
	}
	stim_conn_on = false;

	nrf_timer_task_trigger(t, NRF_TIMER_TASK_START);
	return 0;
}

uint32_t port_stim_hz(void)
{
	/* Prescaler 0: the base clock of the TIMER. */
	return NRF_TIMER_BASE_FREQUENCY_GET(PORT_NRF_TIMER);
}

uint32_t port_core_hz(void)
{
	return SystemCoreClock;
}

void port_stim_set(uint32_t at)
{
	NRF_GPIOTE_Type *g = PORT_NRF_GPIOTE;

	/*
	 * The compare event comes only when the counter is equal to CC[0].
	 * The old CC[0] is in the past, so it does not match again before the
	 * 32-bit counter wraps.
	 */
	nrf_gpiote_task_trigger(g, nrf_gpiote_clr_task_get(stim_ch));
	nrf_timer_cc_set(PORT_NRF_TIMER, NRF_TIMER_CC_CHANNEL0, at);
	nrf_timer_event_clear(PORT_NRF_TIMER, NRF_TIMER_EVENT_COMPARE0);
	if (!stim_conn_on) {
		nrfx_gppi_conn_enable(stim_conn);
		stim_conn_on = true;
	}
}

void port_stim_stop(void)
{
	/* Disable the connection: else the old CC[0] sets the pin after a counter wrap. */
	nrfx_gppi_conn_disable(stim_conn);
	stim_conn_on = false;
	nrf_gpiote_task_trigger(PORT_NRF_GPIOTE, nrf_gpiote_clr_task_get(stim_ch));
}

void port_stim_force(bool high)
{
	NRF_GPIOTE_Type *g = PORT_NRF_GPIOTE;

	nrf_gpiote_task_trigger(g, high ? nrf_gpiote_set_task_get(stim_ch)
					: nrf_gpiote_clr_task_get(stim_ch));
}

void port_resp_irq_init(void)
{
#if PORT_RESP_IRQ_OWNED
	NRF_GPIOTE_Type *g = PORT_NRF_GPIOTE;

	nrf_gpiote_event_configure(g, PORT_NRF_RESP_CH, RESP_PIN, NRF_GPIOTE_POLARITY_LOTOHI);
	nrf_gpiote_event_enable(g, PORT_NRF_RESP_CH);
	nrf_gpiote_event_clear(g, nrf_gpiote_in_event_get(PORT_NRF_RESP_CH));
	nrf_gpiote_int_enable(g, (uint32_t)NRF_GPIOTE_INT_IN0_MASK << PORT_NRF_RESP_CH);
#else
	/* The GPIO driver has the GPIOTE. Only the stock path runs here. */
#endif
}

void port_debug_reset(char *buf, size_t len)
{
	/*
	 * The nRF SoCs have no DBGMCU. While a debugger is connected, the
	 * SoC stays in debug interface mode: clocks and regulators stay on in
	 * sleep. Software cannot stop this mode. Only the debugger (or a
	 * power cycle) stops it. So write DHCSR only for the output: bit 0
	 * (C_DEBUGEN) is 1 while a debugger is connected.
	 */
	snprintk(buf, len, "dhcsr=0x%08x", *(volatile uint32_t *)DHCSR_ADDR);
}
