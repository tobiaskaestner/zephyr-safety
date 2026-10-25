/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Thread to thread wake latency benchmark (measurement point M3 of the
 * latency plan).
 *
 * The hardware stimulus (see latbench/stim.h) makes the response ISR give a
 * semaphore to the giver thread (priority 2). The giver takes the time
 * stamp t0 and wakes the taker thread through the kernel object under
 * test. The taker takes the time stamp t1 as soon as its wait call
 * returns. The giver takes t2 when its wake call returns. All time stamps
 * come from the stimulus timer. Three histograms:
 *
 *   isr2thr  ISR time stamp -> giver (the M2 path, as a check)
 *   t2t      t0 -> t1: the wake call -> first instruction of the taker
 *   t2t_ret  t0 -> t2: the wake call -> return of the wake call
 *
 * With LATBENCH_T2T_PREEMPT=y the taker has priority 1 and preempts the
 * giver in the wake call, so t2t_ret also holds the taker's next wait
 * call and the switch back. With LATBENCH_T2T_PREEMPT=n the taker has
 * priority 3 and runs when the giver blocks for the next stimulus: t2t
 * then holds the rest of the giver loop and its block (for the mutex:
 * the giver blocks on the mutex in the next giver_prepare()), and
 * t2t_ret is the wake call without a switch. In this mode the giver records a
 * sample one stimulus later, so the run has one sample less.
 *
 * The stimulus makes the giver run at a random time, so the wake call
 * meets the timer ISR and the kernel state at random points.
 */

#include <zephyr/kernel.h>
#include <zephyr/irq.h>
#include <zephyr/sys/printk.h>

#include <latbench/hist.h>
#include <latbench/irqmask.h>
#include <latbench/load.h>
#include <latbench/meta.h>
#include <latbench/stim.h>

#if defined(CONFIG_LATBENCH_T2T_SEM)
#define PRIMITIVE "sem"
#elif defined(CONFIG_LATBENCH_T2T_MUTEX)
#define PRIMITIVE "mutex"
#elif defined(CONFIG_LATBENCH_T2T_CONDVAR)
#define PRIMITIVE "condvar"
#elif defined(CONFIG_LATBENCH_T2T_EVENT)
#define PRIMITIVE "event"
#elif defined(CONFIG_LATBENCH_T2T_MSGQ)
#define PRIMITIVE "msgq"
#elif defined(CONFIG_LATBENCH_T2T_FIFO)
#define PRIMITIVE "fifo"
#elif defined(CONFIG_LATBENCH_T2T_LIFO)
#define PRIMITIVE "lifo"
#elif defined(CONFIG_LATBENCH_T2T_STACK)
#define PRIMITIVE "stack"
#elif defined(CONFIG_LATBENCH_T2T_POLL)
#define PRIMITIVE "poll"
#elif defined(CONFIG_LATBENCH_T2T_WORK)
#define PRIMITIVE "work"
#else
#define PRIMITIVE "wakeup"
#endif

#if defined(CONFIG_LATBENCH_T2T_PREEMPT)
#define MODE       "preempt"
#define TAKER_PRIO 1
#else
#define MODE       "nopreempt"
#define TAKER_PRIO 3
#endif
#define GIVER_PRIO 2

#define N_TOTAL (CONFIG_LATBENCH_WARMUP + CONFIG_LATBENCH_SAMPLES)

static LAT_HIST_DEFINE(h_isr2thr, "isr2thr");
static LAT_HIST_DEFINE(h_t2t, "t2t");
static LAT_HIST_DEFINE(h_t2t_ret, "t2t_ret");

static K_SEM_DEFINE(isr_sem, 0, 1);
static volatile uint32_t t_isr;
static volatile uint32_t t_taker;
static volatile uint32_t n_taken;
static volatile uint32_t n_spurious;
static volatile bool done;

#if !defined(CONFIG_LATBENCH_T2T_WORK)
static K_THREAD_STACK_DEFINE(taker_stack, 1024);
static struct k_thread taker_thread;
#endif

/* The kernel object between the giver and the taker. */
#if defined(CONFIG_LATBENCH_T2T_SEM)
static K_SEM_DEFINE(obj_sem, 0, 1);
#elif defined(CONFIG_LATBENCH_T2T_MUTEX)
static K_MUTEX_DEFINE(obj_mutex);
/* Tells the taker to try the mutex while the giver holds it. */
static K_SEM_DEFINE(obj_sync, 0, 1);
#elif defined(CONFIG_LATBENCH_T2T_CONDVAR)
static K_MUTEX_DEFINE(obj_cv_mutex);
static K_CONDVAR_DEFINE(obj_cv);
#elif defined(CONFIG_LATBENCH_T2T_EVENT)
static K_EVENT_DEFINE(obj_event);
#elif defined(CONFIG_LATBENCH_T2T_MSGQ)
K_MSGQ_DEFINE(obj_msgq, sizeof(uint32_t), 1, 4);
#elif defined(CONFIG_LATBENCH_T2T_FIFO)
static K_FIFO_DEFINE(obj_fifo);
static struct {
	void *fifo_reserved;
} obj_item;
#elif defined(CONFIG_LATBENCH_T2T_LIFO)
static K_LIFO_DEFINE(obj_lifo);
static struct {
	void *lifo_reserved;
} obj_item;
#elif defined(CONFIG_LATBENCH_T2T_STACK)
static K_STACK_DEFINE(obj_stack, 1);
#elif defined(CONFIG_LATBENCH_T2T_POLL)
static struct k_poll_signal obj_signal = K_POLL_SIGNAL_INITIALIZER(obj_signal);
static struct k_poll_event obj_poll_event =
	K_POLL_EVENT_STATIC_INITIALIZER(K_POLL_TYPE_SIGNAL, K_POLL_MODE_NOTIFY_ONLY, &obj_signal, 0);
#elif defined(CONFIG_LATBENCH_T2T_WORK)
static K_THREAD_STACK_DEFINE(obj_wq_stack, 1024);
static struct k_work_q obj_wq;
static struct k_work obj_work;
#endif

static inline void taker_stamp(void)
{
	t_taker = stim_now();
	n_taken++;
}

#if defined(CONFIG_LATBENCH_T2T_WORK)

static void work_handler(struct k_work *work)
{
	ARG_UNUSED(work);
	taker_stamp();
}

#else

static void taker_fn(void *a, void *b, void *c)
{
	ARG_UNUSED(a);
	ARG_UNUSED(b);
	ARG_UNUSED(c);
#if defined(CONFIG_LATBENCH_T2T_CONDVAR)
	(void)k_mutex_lock(&obj_cv_mutex, K_FOREVER);
#endif
	for (;;) {
#if defined(CONFIG_LATBENCH_T2T_SEM)
		(void)k_sem_take(&obj_sem, K_FOREVER);
		taker_stamp();
#elif defined(CONFIG_LATBENCH_T2T_MUTEX)
		(void)k_sem_take(&obj_sync, K_FOREVER);
		(void)k_mutex_lock(&obj_mutex, K_FOREVER);
		taker_stamp();
		(void)k_mutex_unlock(&obj_mutex);
#elif defined(CONFIG_LATBENCH_T2T_CONDVAR)
		(void)k_condvar_wait(&obj_cv, &obj_cv_mutex, K_FOREVER);
		taker_stamp();
#elif defined(CONFIG_LATBENCH_T2T_EVENT)
		/* reset = true clears the event before the wait. */
		(void)k_event_wait(&obj_event, BIT(0), true, K_FOREVER);
		taker_stamp();
#elif defined(CONFIG_LATBENCH_T2T_MSGQ)
		uint32_t msg;

		(void)k_msgq_get(&obj_msgq, &msg, K_FOREVER);
		taker_stamp();
#elif defined(CONFIG_LATBENCH_T2T_FIFO)
		(void)k_fifo_get(&obj_fifo, K_FOREVER);
		taker_stamp();
#elif defined(CONFIG_LATBENCH_T2T_LIFO)
		(void)k_lifo_get(&obj_lifo, K_FOREVER);
		taker_stamp();
#elif defined(CONFIG_LATBENCH_T2T_STACK)
		stack_data_t v;

		(void)k_stack_pop(&obj_stack, &v, K_FOREVER);
		taker_stamp();
#elif defined(CONFIG_LATBENCH_T2T_POLL)
		(void)k_poll(&obj_poll_event, 1, K_FOREVER);
		taker_stamp();
		k_poll_signal_reset(&obj_signal);
		obj_poll_event.state = K_POLL_STATE_NOT_READY;
#else
		(void)k_sleep(K_FOREVER);
		taker_stamp();
#endif
	}
}

#endif

/* Runs before each stimulus is armed. */
static inline void giver_prepare(void)
{
#if defined(CONFIG_LATBENCH_T2T_MUTEX)
	/*
	 * Take the mutex, then let the taker try it: the taker blocks on the
	 * mutex (and raises the priority of the giver, if it is higher).
	 */
	(void)k_mutex_lock(&obj_mutex, K_FOREVER);
	k_sem_give(&obj_sync);
#endif
}

static inline void giver_wake(void)
{
#if defined(CONFIG_LATBENCH_T2T_SEM)
	k_sem_give(&obj_sem);
#elif defined(CONFIG_LATBENCH_T2T_MUTEX)
	(void)k_mutex_unlock(&obj_mutex);
#elif defined(CONFIG_LATBENCH_T2T_CONDVAR)
	(void)k_condvar_signal(&obj_cv);
#elif defined(CONFIG_LATBENCH_T2T_EVENT)
	(void)k_event_post(&obj_event, BIT(0));
#elif defined(CONFIG_LATBENCH_T2T_MSGQ)
	uint32_t msg = 1U;

	(void)k_msgq_put(&obj_msgq, &msg, K_NO_WAIT);
#elif defined(CONFIG_LATBENCH_T2T_FIFO)
	k_fifo_put(&obj_fifo, &obj_item);
#elif defined(CONFIG_LATBENCH_T2T_LIFO)
	k_lifo_put(&obj_lifo, &obj_item);
#elif defined(CONFIG_LATBENCH_T2T_STACK)
	(void)k_stack_push(&obj_stack, 1);
#elif defined(CONFIG_LATBENCH_T2T_POLL)
	(void)k_poll_signal_raise(&obj_signal, 0);
#elif defined(CONFIG_LATBENCH_T2T_WORK)
	(void)k_work_submit_to_queue(&obj_wq, &obj_work);
#else
	k_wakeup(&taker_thread);
#endif
}

static void resp_isr(const void *arg)
{
	uint32_t now = stim_now();

	ARG_UNUSED(arg);
	stim_resp_ack();
	if (!stim_fired()) {
		n_spurious++;
	}
	t_isr = now;
	k_sem_give(&isr_sem);
}

static uint32_t n_missed;

static void record(uint32_t n, uint32_t t0, uint32_t t2, uint32_t taken_before)
{
	if (n_taken != taken_before + 1U) {
		/* The taker did not run exactly once for this wake. */
		n_missed++;
		return;
	}
	if (n >= CONFIG_LATBENCH_WARMUP) {
		lat_hist_add(&h_t2t, t_taker - t0);
		lat_hist_add(&h_t2t_ret, t2 - t0);
	}
}

static void giver_fn(void *a, void *b, void *c)
{
	uint32_t prev_t0 = 0;
	uint32_t prev_t2 = 0;
	uint32_t prev_taken = 0;

	ARG_UNUSED(a);
	ARG_UNUSED(b);
	ARG_UNUSED(c);

	for (uint32_t n = 0; n < N_TOTAL; n++) {
		giver_prepare();
		stim_arm(stim_now());
		(void)k_sem_take(&isr_sem, K_FOREVER);

		uint32_t t_thr = stim_now();
		uint32_t taken = n_taken;

#if !defined(CONFIG_LATBENCH_T2T_PREEMPT)
		/* The taker ran while the giver waited for this stimulus. */
		if (n > 0U) {
			record(n - 1U, prev_t0, prev_t2, prev_taken);
			taken = n_taken;
		}
#endif
		uint32_t t0 = stim_now();

		giver_wake();

		uint32_t t2 = stim_now();

		if (n >= CONFIG_LATBENCH_WARMUP) {
			lat_hist_add(&h_isr2thr, t_thr - t_isr);
		}
#if defined(CONFIG_LATBENCH_T2T_PREEMPT)
		record(n, t0, t2, taken);
#else
		prev_t0 = t0;
		prev_t2 = t2;
		prev_taken = taken;
#endif
	}
	ARG_UNUSED(prev_t0);
	ARG_UNUSED(prev_t2);
	ARG_UNUSED(prev_taken);
	stim_stop();
	done = true;
}

static K_THREAD_STACK_DEFINE(giver_stack, 1024);
static struct k_thread giver_thread;

int main(void)
{
	char buf[24];

	/* Undo debugger settings that keep clocks on in sleep (see the port). */
	port_debug_reset(buf, sizeof(buf));

	lat_meta_print("thread_latency", PRIMITIVE "-" MODE);
	lat_meta_kv("primitive", PRIMITIVE);
	lat_meta_kv("t2t_mode", MODE);
	lat_meta_kv("debug_reg_at_boot", buf);
	printk("LAT META giver_prio=%d\n", GIVER_PRIO);
	printk("LAT META taker_prio=%d\n", TAKER_PRIO);
	printk("LAT META poll_ms=%u\n", CONFIG_LATBENCH_POLL_MS);

	if (stim_init() < 0) {
		printk("LAT ERROR setup\n");
		lat_done();
		return 0;
	}
	if (!stim_static_check()) {
		printk("LAT ERROR static check failed (wire D2 -> A3?)\n");
		lat_done();
		return 0;
	}

	stim_resp_irq_init();
	IRQ_CONNECT(STIM_RESP_IRQN, 0, resp_isr, NULL, 0);
	irq_enable(STIM_RESP_IRQN);
	load_start();
	/* M4: empty unless CONFIG_ARM_IRQ_MASK_HOOKS=y. */
	irqmask_start();

	/* The taker starts first, so that it waits before the first wake. */
#if defined(CONFIG_LATBENCH_T2T_WORK)
	k_work_init(&obj_work, work_handler);
	k_work_queue_start(&obj_wq, obj_wq_stack, K_THREAD_STACK_SIZEOF(obj_wq_stack), TAKER_PRIO,
			   NULL);
#else
	k_thread_create(&taker_thread, taker_stack, K_THREAD_STACK_SIZEOF(taker_stack), taker_fn,
			NULL, NULL, NULL, TAKER_PRIO, 0, K_NO_WAIT);
#endif
	/* A taker with a lower priority than main must also reach its wait. */
	k_msleep(10);
	k_thread_create(&giver_thread, giver_stack, K_THREAD_STACK_SIZEOF(giver_stack), giver_fn,
			NULL, NULL, NULL, GIVER_PRIO, 0, K_NO_WAIT);

	while (!done) {
		k_msleep(CONFIG_LATBENCH_POLL_MS);
	}
	irqmask_stop();

	printk("LAT META spurious_edges=%u\n", n_spurious);
	printk("LAT META taker_missed=%u\n", n_missed);
	stim_print_stats();
	load_print();
	lat_hist_print(&h_isr2thr);
	lat_hist_print(&h_t2t);
	lat_hist_print(&h_t2t_ret);
	irqmask_print();
	lat_done();
	return 0;
}
