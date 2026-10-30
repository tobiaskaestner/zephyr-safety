/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * The scenarios of irq_latency other than the entry
 * (LATBENCH_IRQ_SCENARIO). They come from the upstream interrupt benchmark
 * (Zephyr PR 117170): unlock to ISR, nested preemption, exit to the
 * interrupted thread, back to back. CMakeLists.txt adds this file only
 * with such a scenario, so the images of the entry do not change.
 *
 * The main thread drives each sample: it arms the edge, does the part of
 * the scenario before the edge, waits for the ISR and records the sample.
 * Between the samples it spins (no WFI). The edge keeps its random time,
 * so the samples keep a random tick phase.
 */

#include <zephyr/kernel.h>
#include <zephyr/irq.h>
#include <zephyr/sys/printk.h>
#include <cmsis_core.h>

#include <latbench/hist.h>
#include <latbench/load.h>
#include <latbench/stim.h>
#include <latbench/tail.h>

#include "scenario.h"

BUILD_ASSERT(IS_ENABLED(CONFIG_LATBENCH_IRQ_PATH_WRAPPED) || IS_ENABLED(CONFIG_LATBENCH_IRQ_PATH_DIRECT),
	     "the scenarios need the wrapped or the direct path");
BUILD_ASSERT(!IS_ENABLED(CONFIG_LATBENCH_SWTRIG), "LATBENCH_SWTRIG is for the entry scenario only");
BUILD_ASSERT(IS_ENABLED(CONFIG_LATBENCH_BG_IDLE),
	     "in the scenarios the main thread spins: a busy thread never runs");

#define N_TOTAL (CONFIG_LATBENCH_WARMUP + CONFIG_LATBENCH_SAMPLES)

/* The main thread starts the part of a sample that needs the edge this many us before the edge. */
#define LEAD_US 20
/* A wait that is longer than this many ms is a timeout (a lost interrupt). */
#define TIMEOUT_MS 20
/* Stop after this many samples that did not fit the scenario. */
#define MAX_MISSED 10000U

#if defined(CONFIG_LATBENCH_IRQ_SCEN_UNLOCK)
#define SCEN_NAME "unlock"
#define MAIN_NAME "irq_unlock"
#elif defined(CONFIG_LATBENCH_IRQ_SCEN_NESTED)
#define SCEN_NAME "nested"
#define MAIN_NAME "irq_nested"
#if !defined(PORT_SPARE_IRQN)
#error "the scenario nested needs PORT_SPARE_IRQN of the board port"
#endif
#elif defined(CONFIG_LATBENCH_IRQ_SCEN_EXIT)
#define SCEN_NAME "exit"
#define MAIN_NAME "irq_exit"
#else
#define SCEN_NAME "burst"
#define MAIN_NAME "irq_b2b"
#endif

#if defined(CONFIG_LATBENCH_IRQ_SCEN_BURST)
/* The phase histogram has the first entry of each burst. */
#define PHASE_NAME "irq"
#else
#define PHASE_NAME MAIN_NAME
#endif

/* The main histogram of the scenario, and its phase histogram (by the tick phase of the edge). */
static LAT_HIST_DEFINE(h_main, MAIN_NAME);
static LAT_PHASE_DEFINE(p_main, PHASE_NAME);
#if defined(CONFIG_LATBENCH_IRQ_SCEN_EXIT) || defined(CONFIG_LATBENCH_IRQ_SCEN_BURST)
/* The entry from the spinning main thread: edge to the first ISR time stamp. */
static LAT_HIST_DEFINE(h_irq, "irq");
#endif
#if defined(CONFIG_LATBENCH_IRQ_SCEN_NESTED)
/* STIR store in the lower-priority ISR to the ISR time stamp (the upstream span). */
static LAT_HIST_DEFINE(h_sw, "irq_nested_sw");
#endif

#if defined(CONFIG_LATBENCH_TAIL)
/* Witnesses of the main histogram. The window starts at the arm of the edge. */
LAT_TAIL_DEFINE(tail, MAIN_NAME);
static struct lat_tail_mark tail_m;
#define TAIL_MARK() lat_tail_mark(&tail_m)
#define TAIL_ADD(seq, lat, aux)                                                                    \
	lat_tail_add(&tail, &tail_m, (seq), (lat), (aux), stim_edge_phase(), LAT_TAIL_NO_CTX)
#else
#define TAIL_MARK()
#define TAIL_ADD(seq, lat, aux)
#endif

/* Set by the ISR of the edge (of the last ISR of a burst). */
static volatile bool flag;
/* Time stamp of the ISR of the edge. */
static volatile uint32_t t_isr;
static volatile uint32_t n_spurious;
static uint32_t n_missed;
static uint32_t n_timeouts;
static uint32_t lead_cyc;
static uint32_t timeout_cyc;

#if defined(CONFIG_LATBENCH_IRQ_SCEN_EXIT)
/* The last time stamp of the ISR. */
static volatile uint32_t t_exit;
#endif

#if defined(CONFIG_LATBENCH_IRQ_SCEN_NESTED)
/* The lower-priority ISR runs. */
static volatile bool in_low;
/* The edge ISR preempted the lower-priority ISR. */
static volatile bool nested_ok;
static volatile bool low_done;
static volatile bool sw_pending;
static volatile uint32_t t0_sw;
static volatile uint32_t t_isr_sw;
#endif

#if defined(CONFIG_LATBENCH_IRQ_SCEN_BURST)
static volatile uint32_t b_k;
static volatile uint32_t b_stamps[CONFIG_LATBENCH_BURST_LEN];
#endif

/* Spin until cond is true, or count a timeout. */
#define SPIN_UNTIL(cond)                                                                           \
	do {                                                                                       \
		uint32_t start_ = stim_now();                                                      \
		while (!(cond)) {                                                                  \
			if ((uint32_t)(stim_now() - start_) > timeout_cyc) {                       \
				n_timeouts++;                                                      \
				break;                                                             \
			}                                                                          \
		}                                                                                  \
	} while (0)

#if defined(CONFIG_LATBENCH_IRQ_SCEN_UNLOCK) || defined(CONFIG_LATBENCH_IRQ_SCEN_NESTED)
/* Spin until LEAD_US before the edge. */
static void lead_wait(void)
{
	while ((int32_t)(stim_edge() - stim_now()) > (int32_t)lead_cyc) {
	}
}
#endif

/* The ISR of the response IRQ, after its time stamp now. */
static inline void resp_body(uint32_t now)
{
#if defined(CONFIG_LATBENCH_IRQ_SCEN_BURST)
	uint32_t i = b_k;

	/* Pend the next run first, as the upstream scenario (it re-triggers at the top). */
	if (i + 1U < CONFIG_LATBENCH_BURST_LEN) {
		NVIC->STIR = STIM_RESP_IRQN;
	}
	b_stamps[i] = now;
	b_k = i + 1U;
	stim_resp_ack();
	if (i == 0U && !stim_fired()) {
		n_spurious++;
	}
	if (i + 1U >= CONFIG_LATBENCH_BURST_LEN) {
		flag = true;
	}
#else
	stim_resp_ack();
#if defined(CONFIG_LATBENCH_IRQ_SCEN_NESTED)
	if (sw_pending) {
		/* The software part of the sample: no edge. */
		t_isr_sw = now;
		sw_pending = false;
		return;
	}
	nested_ok = in_low;
#endif
	if (!stim_fired()) {
		n_spurious++;
	}
	t_isr = now;
	flag = true;
#if defined(CONFIG_LATBENCH_IRQ_SCEN_EXIT)
	/* The last action of the ISR. */
	t_exit = stim_now();
#endif
#endif
}

#if defined(CONFIG_LATBENCH_IRQ_PATH_WRAPPED)
static void resp_isr(const void *arg)
{
	uint32_t now = stim_now();

	ARG_UNUSED(arg);
	resp_body(now);
}
#else
ISR_DIRECT_DECLARE(resp_isr)
{
	uint32_t now = stim_now();

	resp_body(now);
	/* No reschedule: the ISR wakes no thread. */
	return 0;
}
#endif

#if defined(CONFIG_LATBENCH_IRQ_SCEN_NESTED)
/*
 * The lower-priority ISR. It spins until the edge ISR preempted it. Then
 * it reads the timer and pends the response IRQ with STIR, as the upstream
 * scenario nested_preempt does, and spins until that ISR ran too.
 */
static void low_isr(const void *arg)
{
	ARG_UNUSED(arg);
	in_low = true;
	SPIN_UNTIL(flag);
	sw_pending = true;
	t0_sw = stim_now();
	NVIC->STIR = STIM_RESP_IRQN;
	SPIN_UNTIL(!sw_pending);
	in_low = false;
	low_done = true;
}
#endif

static int scen_irq_setup(void)
{
#if defined(PORT_RESP_PIN)
	if (stim_resp.pin != PORT_RESP_PIN) {
		return -EINVAL;
	}
#endif
	stim_resp_irq_init();
#if defined(CONFIG_LATBENCH_IRQ_PATH_WRAPPED)
	IRQ_CONNECT(STIM_RESP_IRQN, 0, resp_isr, NULL, 0);
#else
	IRQ_DIRECT_CONNECT(STIM_RESP_IRQN, 0, resp_isr, 0);
#endif
	irq_enable(STIM_RESP_IRQN);
#if defined(CONFIG_LATBENCH_IRQ_SCEN_NESTED)
	IRQ_CONNECT(PORT_SPARE_IRQN, CONFIG_LATBENCH_NESTED_PRIO, low_isr, NULL, 0);
	irq_enable(PORT_SPARE_IRQN);
#endif
	return 0;
}

/* One sample. Returns false if the sample did not fit the scenario (not recorded). */
static bool sample(bool rec, uint32_t seq)
{
#if defined(CONFIG_LATBENCH_IRQ_SCEN_UNLOCK)
	unsigned int key;
	uint32_t hold = CONFIG_LATBENCH_UNLOCK_HOLD_US * (port_stim_hz() / 1000000U);
	uint32_t t0;

	flag = false;
	TAIL_MARK();
	stim_arm(stim_now());
	lead_wait();
	key = irq_lock();
	if (flag) {
		/* The edge came before the lock (a long ISR in the lead time). */
		irq_unlock(key);
		return false;
	}
	/* The edge is pending in the NVIC, and the lock holds it. */
	SPIN_UNTIL(NVIC_GetPendingIRQ(STIM_RESP_IRQN) != 0U);
	SPIN_UNTIL((uint32_t)(stim_now() - stim_edge()) >= hold);
	t0 = stim_now();
	irq_unlock(key);
	SPIN_UNTIL(flag);
	if (rec) {
		uint32_t lat = t_isr - t0;

		lat_hist_add(&h_main, lat);
		lat_phase_add(&p_main, stim_edge_phase(), lat);
		TAIL_ADD(seq, lat, t0 - stim_edge());
	}
#elif defined(CONFIG_LATBENCH_IRQ_SCEN_NESTED)
	flag = false;
	low_done = false;
	nested_ok = false;
	TAIL_MARK();
	stim_arm(stim_now());
	lead_wait();
	NVIC->STIR = PORT_SPARE_IRQN;
	SPIN_UNTIL(low_done);
	if (!nested_ok) {
		/* The edge did not meet the lower-priority ISR. */
		return false;
	}
	if (rec) {
		uint32_t lat = t_isr - stim_edge();

		lat_hist_add(&h_main, lat);
		lat_phase_add(&p_main, stim_edge_phase(), lat);
		lat_hist_add(&h_sw, t_isr_sw - t0_sw);
		TAIL_ADD(seq, lat, t_isr_sw - t0_sw);
	}
#elif defined(CONFIG_LATBENCH_IRQ_SCEN_EXIT)
	uint32_t t_thr;

	flag = false;
	TAIL_MARK();
	stim_arm(stim_now());
	/* A tight loop, as the upstream scenario: the ISR returns into it. */
	while (!flag) {
	}
	t_thr = stim_now();
	if (rec) {
		uint32_t lat = t_thr - t_exit;

		lat_hist_add(&h_irq, t_isr - stim_edge());
		lat_hist_add(&h_main, lat);
		lat_phase_add(&p_main, stim_edge_phase(), lat);
		TAIL_ADD(seq, lat, t_isr - stim_edge());
	}
#else /* burst */
	flag = false;
	b_k = 0U;
	TAIL_MARK();
	stim_arm(stim_now());
	while (!flag) {
	}
	if (rec) {
		lat_hist_add(&h_irq, b_stamps[0] - stim_edge());
		lat_phase_add(&p_main, stim_edge_phase(), b_stamps[0] - stim_edge());
		for (uint32_t i = 1U; i < CONFIG_LATBENCH_BURST_LEN; i++) {
			uint32_t lat = b_stamps[i] - b_stamps[i - 1U];

			lat_hist_add(&h_main, lat);
			TAIL_ADD(seq * (CONFIG_LATBENCH_BURST_LEN - 1U) + i - 1U, lat, i);
		}
	}
#endif
	return true;
}

void scen_main(void)
{
	uint32_t n = 0U;

	lat_phase_init(&p_main, stim_tick_period());
	if (!stim_static_check()) {
		printk("LAT ERROR static check failed (wire D2 -> A3?)\n");
		return;
	}
	if (scen_irq_setup() < 0) {
		printk("LAT ERROR irq setup\n");
		return;
	}
	lead_cyc = LEAD_US * (port_stim_hz() / 1000000U);
	timeout_cyc = TIMEOUT_MS * (port_stim_hz() / 1000U);
	printk("LAT META irq_scenario=%s\n", SCEN_NAME);
	printk("LAT META scen_lead_us=%u\n", LEAD_US);
#if defined(CONFIG_LATBENCH_IRQ_SCEN_UNLOCK)
	printk("LAT META unlock_hold_us=%u\n", CONFIG_LATBENCH_UNLOCK_HOLD_US);
#elif defined(CONFIG_LATBENCH_IRQ_SCEN_NESTED)
	printk("LAT META nested_prio=%u\n", CONFIG_LATBENCH_NESTED_PRIO);
	printk("LAT META spare_irqn=%d\n", (int)PORT_SPARE_IRQN);
#elif defined(CONFIG_LATBENCH_IRQ_SCEN_BURST)
	printk("LAT META burst_len=%u\n", CONFIG_LATBENCH_BURST_LEN);
#endif
#if defined(CONFIG_LATBENCH_TAIL)
	lat_tail_init();
	lat_tail_print_setup(&tail);
#endif
	load_start();
	while (n < N_TOTAL) {
		if (sample(n >= CONFIG_LATBENCH_WARMUP, n - CONFIG_LATBENCH_WARMUP)) {
			n++;
		} else if (++n_missed >= MAX_MISSED) {
			printk("LAT ERROR too many samples did not fit the scenario\n");
			break;
		}
	}
	stim_stop();

	printk("LAT META spurious_edges=%u\n", n_spurious);
	printk("LAT META scen_missed=%u\n", n_missed);
	printk("LAT META scen_timeouts=%u\n", n_timeouts);
	stim_print_stats();
	load_print();
#if defined(CONFIG_LATBENCH_IRQ_SCEN_EXIT) || defined(CONFIG_LATBENCH_IRQ_SCEN_BURST)
	lat_hist_print(&h_irq);
#endif
	lat_hist_print(&h_main);
	lat_phase_print(&p_main);
#if defined(CONFIG_LATBENCH_IRQ_SCEN_NESTED)
	lat_hist_print(&h_sw);
#endif
#if defined(CONFIG_LATBENCH_TAIL)
	lat_tail_print(&tail);
#endif
}
