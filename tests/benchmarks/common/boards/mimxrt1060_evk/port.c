/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Board port mimxrt1060_evk (see latbench/port.h).
 *
 * Stimulus: GPT2 is a free-running 32-bit up-counter. Compare channel 1
 * drives A3 (pad GPIO_AD_B1_05, GPT2_COMPARE1). The port sets the output
 * mode of channel 1 to "set output pin" when it arms an edge, so the
 * hardware drives the pin high at the compare match.
 *
 * Clock: GPT2 counts PERCLK_CLK_ROOT. The port sets PERCLK to IPG / 2
 * (75 MHz with the core at 600 MHz), the maximum PERCLK that the RT1060
 * data sheet gives. One count is 8 core cycles. SysTick (the system
 * timer) counts the core clock. The core clock and PERCLK come from the
 * same ARM PLL, so the ratio is exactly 8 and the tick phase is exact to
 * one count.
 *
 * Response: D2 (pad GPIO_AD_B0_11, GPIO1_IO11). Its interrupt is the
 * GPIO1 interrupt for pins 0 to 15 (IRQ 80). resp_irq_own.overlay takes
 * this IRQ away from the GPIO driver for the apps with an own ISR.
 */

#include <zephyr/kernel.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/pinctrl.h>
#include <zephyr/sys/printk.h>

#include <fsl_clock.h>

#include <latbench/port.h>

#define USER_NODE DT_PATH(zephyr_user)

/* PERCLK = IPG / PORT_PERCLK_DIV. 1 gives 150 MHz, more than the data sheet permits. */
#define PORT_PERCLK_DIV 2U

/* Output compare modes of GPT_CR.OM1. */
#define GPT_OM_CLEAR 2U
#define GPT_OM_SET   3U

/*
 * A forced compare (FO1) has its effect on the pin after the
 * synchronization into the GPT clock. Wait this many counts before the
 * output mode changes again.
 */
#define GPT_FORCE_WAIT_CNT 3U

/* The response pin must be the pin that port_impl.h and resp_irq_own.overlay use. */
BUILD_ASSERT(DT_SAME_NODE(DT_GPIO_CTLR(USER_NODE, resp_gpios), DT_NODELABEL(gpio1)) &&
		     DT_GPIO_PIN(USER_NODE, resp_gpios) == PORT_RESP_PIN,
	     "the port expects the response pin on GPIO1_IO11 (Arduino D2)");

/* The tick phase needs a system timer that counts the core clock. */
BUILD_ASSERT(IS_ENABLED(CONFIG_CORTEX_M_SYSTICK), "the port expects SysTick as system timer");

PINCTRL_DT_DEFINE(USER_NODE);

const char *const port_name = "mimxrt1060_evk/gpt2_cmp1-gpio1_11";

/* Do the action of output mode om on the pin now. Leave om as output mode. */
static void gpt_force(uint32_t om)
{
	uint32_t cr = (GPT2->CR & ~GPT_CR_OM1_MASK) | GPT_CR_OM1(om);
	uint32_t t0;

	GPT2->CR = cr;
	GPT2->CR = cr | GPT_CR_FO1_MASK;
	/* The read also makes sure that the writes are complete. */
	t0 = GPT2->CNT;
	while ((uint32_t)(GPT2->CNT - t0) < GPT_FORCE_WAIT_CNT) {
	}
}

int port_stim_init(void)
{
	int ret;

	/* The core clock must be the clock of SysTick, see the tick phase. */
	if (CLOCK_GetFreq(kCLOCK_CpuClk) != sys_clock_hw_cycles_per_sec()) {
		printk("LAT ERROR core clock %u Hz, SysTick expects %u Hz\n",
		       CLOCK_GetFreq(kCLOCK_CpuClk), sys_clock_hw_cycles_per_sec());
		return -EINVAL;
	}

	ret = pinctrl_apply_state(PINCTRL_DT_DEV_CONFIG_GET(USER_NODE), PINCTRL_STATE_DEFAULT);
	if (ret < 0) {
		return ret;
	}

	/* PERCLK from IPG, divided by PORT_PERCLK_DIV. */
	CLOCK_SetMux(kCLOCK_PerclkMux, 0U);
	CLOCK_SetDiv(kCLOCK_PerclkDiv, PORT_PERCLK_DIV - 1U);

	CLOCK_EnableClock(kCLOCK_Gpt2);
	CLOCK_EnableClock(kCLOCK_Gpt2S);

	GPT2->CR = 0U;
	GPT2->IR = 0U;
	GPT2->CR = GPT_CR_SWR_MASK;
	while ((GPT2->CR & GPT_CR_SWR_MASK) != 0U) {
	}

	/*
	 * Peripheral clock (PERCLK), no prescaler, free-run mode (a compare
	 * match does not reset the counter), and the counter also runs in
	 * wait and doze mode and when a debugger halts the core.
	 */
	GPT2->PR = 0U;
	GPT2->CR = GPT_CR_CLKSRC(1U) | GPT_CR_FRR_MASK | GPT_CR_ENMOD_MASK | GPT_CR_WAITEN_MASK |
		   GPT_CR_DOZEEN_MASK | GPT_CR_DBGEN_MASK | GPT_CR_OM1(GPT_OM_CLEAR);
	GPT2->SR = GPT_SR_OF1_MASK;
	GPT2->CR |= GPT_CR_EN_MASK;

	/* Pin low (gpt_force() needs the running counter). */
	gpt_force(GPT_OM_CLEAR);
	return 0;
}

uint32_t port_stim_hz(void)
{
	/* stim_init() calls this before port_stim_init(), so give the rate that it sets. */
	return CLOCK_GetFreq(kCLOCK_IpgClk) / PORT_PERCLK_DIV;
}

uint32_t port_core_hz(void)
{
	return CLOCK_GetFreq(kCLOCK_CpuClk);
}

void port_stim_set(uint32_t at)
{
	gpt_force(GPT_OM_CLEAR);
	GPT2->OCR[0] = at;
	GPT2->SR = GPT_SR_OF1_MASK;
	GPT2->CR = (GPT2->CR & ~GPT_CR_OM1_MASK) | GPT_CR_OM1(GPT_OM_SET);
}

void port_stim_stop(void)
{
	gpt_force(GPT_OM_CLEAR);
}

void port_stim_force(bool high)
{
	gpt_force(high ? GPT_OM_SET : GPT_OM_CLEAR);
}

void port_resp_irq_init(void)
{
	GPIO_Type *gpio = PORT_RESP_GPIO;
	const uint32_t shift = 2U * PORT_RESP_PIN;

	/* Rising edge: ICR = 2 for the pin (pins 0 to 15 are in ICR1), no EDGE_SEL. */
	gpio->IMR &= ~BIT(PORT_RESP_PIN);
	gpio->EDGE_SEL &= ~BIT(PORT_RESP_PIN);
	gpio->ICR1 = (gpio->ICR1 & ~(3U << shift)) | (2U << shift);
	gpio->ISR = BIT(PORT_RESP_PIN);
	gpio->IMR |= BIT(PORT_RESP_PIN);
}

void port_debug_reset(char *buf, size_t len)
{
	/*
	 * The RT1062 has no debug register that keeps clocks on in sleep
	 * (no DBGMCU). In RUN mode, WFI stops only the core clock. Record
	 * the low-power mode register CCM_CLPCR instead (LPM = bits 1:0).
	 */
	snprintk(buf, len, "n/a clpcr=0x%08x", CCM->CLPCR);
}
