/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>
#if defined(CONFIG_CORTEX_M_SYSTICK)
#include <cmsis_core.h>
#endif

#include <latbench/hist.h>
#include <latbench/load.h>
#include <latbench/stim.h>

#define N_THREADS CONFIG_LATBENCH_LOAD_THREADS
#define N_TIMERS  CONFIG_LATBENCH_LOAD_TIMERS

#if defined(CONFIG_LATBENCH_LOAD_THREAD_BLOCKED)
#define THREAD_KIND "blocked"
#elif defined(CONFIG_LATBENCH_LOAD_THREAD_SLEEPER)
#define THREAD_KIND "sleeper"
#else
#define THREAD_KIND "busy"
#endif

#if defined(CONFIG_LATBENCH_LOAD_TIMER_PERIODIC)
#define TIMER_KIND "periodic"
#else
#define TIMER_KIND "far"
#endif

/* xorshift32 with a seed of its own, so that the load does not change the stimulus. */
static inline uint32_t rng_next(uint32_t *state)
{
	uint32_t x = *state;

	x ^= x << 13;
	x ^= x >> 17;
	x ^= x << 5;
	*state = x;
	return x;
}

static inline uint32_t rng_range(uint32_t *state, uint32_t lo, uint32_t hi)
{
	return lo + rng_next(state) % (hi - lo + 1U);
}

#if N_THREADS > 0

static K_THREAD_STACK_ARRAY_DEFINE(load_stacks, N_THREADS, CONFIG_LATBENCH_LOAD_THREAD_STACK);
static struct k_thread load_threads[N_THREADS];
#if defined(CONFIG_LATBENCH_LOAD_THREAD_SLEEPER)
static uint32_t n_sleeper_wakes;
#endif

#if defined(CONFIG_LATBENCH_LOAD_THREAD_BLOCKED)
/* Nobody gives these semaphores. Each thread stays in the wait queue of its own. */
static struct k_sem load_sems[N_THREADS];
#endif

static void load_thread_fn(void *a, void *b, void *c)
{
	uint32_t i = POINTER_TO_UINT(a);

	ARG_UNUSED(b);
	ARG_UNUSED(c);
#if defined(CONFIG_LATBENCH_LOAD_THREAD_BLOCKED)
	(void)k_sem_take(&load_sems[i], K_FOREVER);
#elif defined(CONFIG_LATBENCH_LOAD_THREAD_SLEEPER)
	uint32_t rng = 0x9e3779b9U ^ (i * 0x85ebca6bU);

	for (;;) {
		k_msleep(rng_range(&rng, CONFIG_LATBENCH_LOAD_SLEEP_MIN_MS,
				   CONFIG_LATBENCH_LOAD_SLEEP_MAX_MS));
		/* Not atomic: an approximate count is enough. */
		n_sleeper_wakes++;
	}
#else
	ARG_UNUSED(i);
	for (;;) {
		arch_nop();
	}
#endif
}

static void threads_start(void)
{
#if defined(CONFIG_LATBENCH_LOAD_THREAD_BUSY)
	int prio = K_LOWEST_APPLICATION_THREAD_PRIO;
#else
	int prio = CONFIG_LATBENCH_LOAD_THREAD_PRIO;
#endif

	for (uint32_t i = 0; i < N_THREADS; i++) {
#if defined(CONFIG_LATBENCH_LOAD_THREAD_BLOCKED)
		k_sem_init(&load_sems[i], 0, 1);
#endif
		k_thread_create(&load_threads[i], load_stacks[i], K_THREAD_STACK_SIZEOF(load_stacks[i]),
				load_thread_fn, UINT_TO_POINTER(i), NULL, NULL, prio, 0, K_NO_WAIT);
	}
}

#endif /* N_THREADS > 0 */

#if N_TIMERS > 0

static struct k_timer load_timers[N_TIMERS];
static uint32_t n_timer_expiries;
/*
 * Count, min and max of the expiry phase, in LATBENCH_PHASE_BINS bins over the tick. The
 * phase comes from the cycle counter of the timer driver, because the tick
 * grid is in that count.
 */
static LAT_PHASE_DEFINE(p_tmr, "tmr");

static void load_timer_fn(struct k_timer *t)
{
	uint32_t phase = (uint32_t)(k_cycle_get_64() % stim_tick_period());

	ARG_UNUSED(t);
	n_timer_expiries++;
	lat_phase_add(&p_tmr, phase, phase);
}

static void timers_start(void)
{
#if defined(CONFIG_LATBENCH_LOAD_TIMER_PERIODIC)
	uint32_t rng = CONFIG_LATBENCH_LOAD_TIMER_SEED;
#else
	uint32_t rng = 0U;
#endif

	lat_phase_init(&p_tmr, stim_tick_period());

	for (uint32_t i = 0; i < N_TIMERS; i++) {
		k_timer_init(&load_timers[i], load_timer_fn, NULL);
#if defined(CONFIG_LATBENCH_LOAD_TIMER_PERIODIC)
		uint32_t period = rng_range(&rng, k_ms_to_ticks_ceil32(CONFIG_LATBENCH_LOAD_TIMER_MIN_MS),
					    k_ms_to_ticks_ceil32(CONFIG_LATBENCH_LOAD_TIMER_MAX_MS));
		uint32_t first = rng_range(&rng, 1U, period);

		k_timer_start(&load_timers[i], K_TICKS(first), K_TICKS(period));
#else
		ARG_UNUSED(rng);
		/* One hour plus i ticks: in the list for the whole run, never due. */
		k_timer_start(&load_timers[i], K_TICKS(k_ms_to_ticks_ceil32(3600U * 1000U) + i),
			      K_NO_WAIT);
#endif
	}
}

#endif /* N_TIMERS > 0 */

void load_start(void)
{
#if defined(CONFIG_CORTEX_M_SYSTICK) && (CONFIG_LATBENCH_SYSTICK_PRIO >= 0)
	/* Same offset as IRQ_CONNECT() gives an IRQ priority. */
	NVIC_SetPriority(SysTick_IRQn, CONFIG_LATBENCH_SYSTICK_PRIO + _IRQ_PRIO_OFFSET);
#endif
#if N_TIMERS > 0
	timers_start();
#endif
#if N_THREADS > 0
	threads_start();
#endif
}

void load_print(void)
{
#if N_TIMERS > 0
	/* Stop the timers, so that the counters do not change while they print. */
	for (uint32_t i = 0; i < N_TIMERS; i++) {
		k_timer_stop(&load_timers[i]);
	}
#endif
#if defined(CONFIG_CORTEX_M_SYSTICK)
	/* In the numbers of IRQ_CONNECT(). The driver default is 0. */
	printk("LAT META systick_prio=%d\n",
	       (int)NVIC_GetPriority(SysTick_IRQn) - (int)_IRQ_PRIO_OFFSET);
#endif
	printk("LAT META load_threads=%u\n", N_THREADS);
	printk("LAT META load_timers=%u\n", N_TIMERS);
#if N_THREADS > 0
	printk("LAT META load_thread_kind=%s\n", THREAD_KIND);
#if defined(CONFIG_LATBENCH_LOAD_THREAD_SLEEPER)
	printk("LAT META load_sleep_ms=%u..%u\n", CONFIG_LATBENCH_LOAD_SLEEP_MIN_MS,
	       CONFIG_LATBENCH_LOAD_SLEEP_MAX_MS);
	printk("LAT META load_sleeper_wakes=%u\n", n_sleeper_wakes);
#endif
#endif
#if N_TIMERS > 0
	printk("LAT META load_timer_kind=%s\n", TIMER_KIND);
#if defined(CONFIG_LATBENCH_LOAD_TIMER_PERIODIC)
	printk("LAT META load_timer_ms=%u..%u\n", CONFIG_LATBENCH_LOAD_TIMER_MIN_MS,
	       CONFIG_LATBENCH_LOAD_TIMER_MAX_MS);
	printk("LAT META load_timer_seed=0x%08x\n", CONFIG_LATBENCH_LOAD_TIMER_SEED);
#endif
	printk("LAT META load_timer_expiries=%u\n", n_timer_expiries);
	lat_phase_print(&p_tmr);
#endif
}
