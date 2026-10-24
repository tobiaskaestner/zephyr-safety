/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * ISR to thread wake latency benchmark (measurement point M2 of the
 * latency plan).
 *
 * The hardware stimulus makes an edge on the stimulus pin (see
 * latbench/stim.h). The ISR of the response pin takes a time stamp and
 * wakes a thread through a kernel object. The thread takes a time stamp
 * as soon as its wait call returns. All time stamps come from the
 * stimulus timer. Three histograms:
 *
 *   irq      edge -> first instruction of the ISR
 *   isr2thr  ISR time stamp -> woken thread time stamp
 *   irq2thr  edge -> woken thread (end to end)
 *
 * Two phase histograms record irq and isr2thr by the tick phase of the
 * edge.
 *
 * The thread arms the next stimulus after it took its time stamps, so one
 * stimulus is in flight at a time.
 */

#include <zephyr/kernel.h>
#include <zephyr/irq.h>
#include <zephyr/sys/printk.h>

#include <latbench/hist.h>
#include <latbench/load.h>
#include <latbench/meta.h>
#include <latbench/stim.h>

#if defined(CONFIG_LATBENCH_WAKE_ISR_DIRECT)
#define ISR_KIND "direct"
#else
#define ISR_KIND "wrapped"
#endif

#if defined(CONFIG_LATBENCH_WAKE_SEM)
#define PRIMITIVE "sem"
#elif defined(CONFIG_LATBENCH_WAKE_EVENT)
#define PRIMITIVE "event"
#elif defined(CONFIG_LATBENCH_WAKE_MSGQ)
#define PRIMITIVE "msgq"
#elif defined(CONFIG_LATBENCH_WAKE_FIFO)
#define PRIMITIVE "fifo"
#else
#define PRIMITIVE "poll"
#endif

#if defined(CONFIG_LATBENCH_BG_BUSY)
#define BACKGROUND "busy"
#else
#define BACKGROUND "idle"
#endif

#define N_TOTAL (CONFIG_LATBENCH_WARMUP + CONFIG_LATBENCH_SAMPLES)

static LAT_HIST_DEFINE(h_irq, "irq");
static LAT_HIST_DEFINE(h_isr2thr, "isr2thr");
static LAT_HIST_DEFINE(h_irq2thr, "irq2thr");
static LAT_PHASE_DEFINE(p_irq, "irq");
static LAT_PHASE_DEFINE(p_isr2thr, "isr2thr");

static volatile uint32_t t_isr;
static volatile uint32_t n_spurious;
static volatile bool done;

/* The kernel object between the ISR and the thread. */
#if defined(CONFIG_LATBENCH_WAKE_SEM)
static K_SEM_DEFINE(wake_sem, 0, 1);
#elif defined(CONFIG_LATBENCH_WAKE_EVENT)
static K_EVENT_DEFINE(wake_event);
#elif defined(CONFIG_LATBENCH_WAKE_MSGQ)
static K_MSGQ_DEFINE(wake_msgq, sizeof(uint32_t), 1, 4);
#elif defined(CONFIG_LATBENCH_WAKE_FIFO)
static K_FIFO_DEFINE(wake_fifo);
static struct {
	void *fifo_reserved;
} wake_item;
#else
static struct k_poll_signal wake_signal = K_POLL_SIGNAL_INITIALIZER(wake_signal);
static struct k_poll_event wake_poll_event =
	K_POLL_EVENT_STATIC_INITIALIZER(K_POLL_TYPE_SIGNAL, K_POLL_MODE_NOTIFY_ONLY, &wake_signal, 0);
#endif

static inline void wake_from_isr(void)
{
#if defined(CONFIG_LATBENCH_WAKE_SEM)
	k_sem_give(&wake_sem);
#elif defined(CONFIG_LATBENCH_WAKE_EVENT)
	k_event_post(&wake_event, BIT(0));
#elif defined(CONFIG_LATBENCH_WAKE_MSGQ)
	uint32_t msg = 1U;

	(void)k_msgq_put(&wake_msgq, &msg, K_NO_WAIT);
#elif defined(CONFIG_LATBENCH_WAKE_FIFO)
	k_fifo_put(&wake_fifo, &wake_item);
#else
	k_poll_signal_raise(&wake_signal, 0);
#endif
}

/* Block until the ISR wakes the thread. */
static inline void wait_for_isr(void)
{
#if defined(CONFIG_LATBENCH_WAKE_SEM)
	(void)k_sem_take(&wake_sem, K_FOREVER);
#elif defined(CONFIG_LATBENCH_WAKE_EVENT)
	(void)k_event_wait(&wake_event, BIT(0), false, K_FOREVER);
#elif defined(CONFIG_LATBENCH_WAKE_MSGQ)
	uint32_t msg;

	(void)k_msgq_get(&wake_msgq, &msg, K_FOREVER);
#elif defined(CONFIG_LATBENCH_WAKE_FIFO)
	(void)k_fifo_get(&wake_fifo, K_FOREVER);
#else
	(void)k_poll(&wake_poll_event, 1, K_FOREVER);
#endif
}

/* Make the object ready for the next wait. Runs after the time stamps. */
static inline void rearm_object(void)
{
#if defined(CONFIG_LATBENCH_WAKE_EVENT)
	k_event_clear(&wake_event, BIT(0));
#elif defined(CONFIG_LATBENCH_WAKE_POLL)
	k_poll_signal_reset(&wake_signal);
	wake_poll_event.state = K_POLL_STATE_NOT_READY;
#endif
}

#if defined(CONFIG_LATBENCH_WAKE_ISR_DIRECT)

ISR_DIRECT_DECLARE(resp_isr)
{
	uint32_t now = stim_now();

	stim_resp_ack();
	if (!stim_fired()) {
		n_spurious++;
	}
	t_isr = now;
	wake_from_isr();
	/* Ask for a reschedule at the exit, so that the woken thread runs. */
	return 1;
}

#else

static void resp_isr(const void *arg)
{
	uint32_t now = stim_now();

	ARG_UNUSED(arg);
	stim_resp_ack();
	if (!stim_fired()) {
		n_spurious++;
	}
	t_isr = now;
	wake_from_isr();
}

#endif

static void waker_fn(void *a, void *b, void *c)
{
	stim_arm(stim_now());
	for (uint32_t n = 0; n < N_TOTAL; n++) {
		wait_for_isr();

		uint32_t t_thr = stim_now();
		uint32_t edge = stim_edge();
		uint32_t phase = stim_edge_phase();
		uint32_t ti = t_isr;

		if (n >= CONFIG_LATBENCH_WARMUP) {
			lat_hist_add(&h_irq, ti - edge);
			lat_hist_add(&h_isr2thr, t_thr - ti);
			lat_hist_add(&h_irq2thr, t_thr - edge);
			lat_phase_add(&p_irq, phase, ti - edge);
			lat_phase_add(&p_isr2thr, phase, t_thr - ti);
		}
		rearm_object();
		if (n + 1 < N_TOTAL) {
			stim_arm(stim_now());
		}
	}
	stim_stop();
	done = true;
}

static K_THREAD_STACK_DEFINE(waker_stack, 1024);
static struct k_thread waker_thread;

#if defined(CONFIG_LATBENCH_BG_BUSY)
static void busy_fn(void *a, void *b, void *c)
{
	for (;;) {
		arch_nop();
	}
}

K_THREAD_DEFINE(busy_tid, 512, busy_fn, NULL, NULL, NULL, K_LOWEST_APPLICATION_THREAD_PRIO, 0,
		0);
#endif

int main(void)
{
	char buf[24];

	/* Undo debugger settings that keep clocks on in sleep (see the port). */
	port_debug_reset(buf, sizeof(buf));

	lat_meta_print("wake_latency", ISR_KIND "-" PRIMITIVE);
	lat_meta_kv("wake_isr", ISR_KIND);
	lat_meta_kv("primitive", PRIMITIVE);
	lat_meta_kv("background", BACKGROUND);
	lat_meta_kv("debug_reg_at_boot", buf);
	printk("LAT META wake_prio=%d\n", CONFIG_LATBENCH_WAKE_PRIO);
	printk("LAT META poll_ms=%u\n", CONFIG_LATBENCH_POLL_MS);

	if (stim_init() < 0) {
		printk("LAT ERROR setup\n");
		lat_done();
		return 0;
	}
	lat_phase_init(&p_irq, stim_tick_period());
	lat_phase_init(&p_isr2thr, stim_tick_period());
	if (!stim_static_check()) {
		printk("LAT ERROR static check failed (wire D2 -> A3?)\n");
		lat_done();
		return 0;
	}

	stim_resp_irq_init();
#if defined(CONFIG_LATBENCH_WAKE_ISR_DIRECT)
	IRQ_DIRECT_CONNECT(STIM_RESP_IRQN, 0, resp_isr, 0);
#else
	IRQ_CONNECT(STIM_RESP_IRQN, 0, resp_isr, NULL, 0);
#endif
	irq_enable(STIM_RESP_IRQN);
	load_start();

	k_thread_create(&waker_thread, waker_stack, K_THREAD_STACK_SIZEOF(waker_stack), waker_fn,
			NULL, NULL, NULL, CONFIG_LATBENCH_WAKE_PRIO, 0, K_NO_WAIT);

	while (!done) {
		k_msleep(CONFIG_LATBENCH_POLL_MS);
	}

	printk("LAT META spurious_edges=%u\n", n_spurious);
	stim_print_stats();
	load_print();
	lat_hist_print(&h_irq);
	lat_hist_print(&h_isr2thr);
	lat_hist_print(&h_irq2thr);
	lat_phase_print(&p_irq);
	lat_phase_print(&p_isr2thr);
	lat_done();
	return 0;
}
