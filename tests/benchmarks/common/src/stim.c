/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <zephyr/kernel.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/sys/printk.h>

#include <latbench/stim.h>

#define USER_NODE DT_PATH(zephyr_user)

/*
 * The tick phase needs a cycle counter with the tick grid of the timer
 * driver. Without k_cycle_get_64() (nrf_rtc_timer), the 32-bit count has
 * the same grid if the tick period is a power of two.
 */
#if defined(CONFIG_TIMER_HAS_64BIT_CYCLE_COUNTER)
#define SYS_CYC_MASK UINT64_MAX
static inline uint64_t sys_cyc(void)
{
	return k_cycle_get_64();
}
#else
BUILD_ASSERT(CONFIG_SYS_CLOCK_HW_CYCLES_PER_SEC % CONFIG_SYS_CLOCK_TICKS_PER_SEC == 0 &&
		     IS_POWER_OF_TWO(CONFIG_SYS_CLOCK_HW_CYCLES_PER_SEC /
				     CONFIG_SYS_CLOCK_TICKS_PER_SEC),
	     "without k_cycle_get_64(), the tick period must be a power of two cycles");
#define SYS_CYC_MASK UINT32_MAX
static inline uint64_t sys_cyc(void)
{
	return k_cycle_get_32();
}
#endif

/* A fixed-rate edge needs at least this many cycles between arm and edge. */
#define STIM_ARM_MARGIN 1000U

const struct gpio_dt_spec stim_resp = GPIO_DT_SPEC_GET(USER_NODE, resp_gpios);

uint32_t stim_next_ccr;
uint32_t stim_next_phase;
static uint32_t tick_period;
static uint32_t stim_hz;
static uint32_t sys_hz;
static uint32_t n_overruns;
static uint32_t n_late;
/* The stimulus timer and k_cycle_get_64() at stim_init(), for the clock drift check. */
static uint32_t ref_cnt;
static uint64_t ref_cyc;

#if defined(CONFIG_LATBENCH_STIM_RANDOM)
static uint32_t stim_min;
static uint32_t stim_span;
static uint32_t rng_state = CONFIG_LATBENCH_STIM_SEED;

static inline uint32_t rng_next(void)
{
	uint32_t x = rng_state;

	x ^= x << 13;
	x ^= x >> 17;
	x ^= x << 5;
	rng_state = x;
	return x;
}
#else
static uint32_t stim_period;
static bool started;
#endif

uint32_t stim_tick_period(void)
{
	return tick_period;
}

/* Stimulus timer counts to system timer cycles. */
static inline uint64_t to_sys(uint32_t d)
{
	return (stim_hz == sys_hz) ? d : (uint64_t)d * sys_hz / stim_hz;
}

void stim_arm(uint32_t now)
{
	uint32_t next;
	unsigned int key;
	uint32_t cnt;
	uint64_t cyc;

#if defined(CONFIG_LATBENCH_STIM_RANDOM)
	next = now + stim_min + (rng_next() % stim_span);
#else
	next = stim_next_ccr + stim_period;
	if (!started) {
		/* The first edge: there is no previous edge yet. */
		started = true;
		next = now + stim_period;
	} else if ((int32_t)(next - now) < (int32_t)STIM_ARM_MARGIN) {
		/* Too late for this edge: start a new period from now. */
		n_overruns++;
		next = now + stim_period;
	}
#endif
	/*
	 * An ISR can run between the read of now and the write of the
	 * compare value. If it runs longer than the delay, the compare value
	 * is in the past, and the timer reaches it only after a full wrap
	 * (25 s for 32 bits at 170 MHz). So write it with interrupts locked,
	 * and check it against a fresh count first. A late edge comes
	 * STIM_ARM_MARGIN counts after the fresh count, and counts in
	 * stim_late.
	 *
	 * The tick phase comes from the same fresh pair of readings: the
	 * tick grid is in the count of k_cycle_get_64(), and that count can
	 * lose cycles against the stimulus timer (each SysTick reprogram
	 * loses a few, see clock_drift_cyc). A reference of the past drifts.
	 */
	key = irq_lock();
	cnt = port_stim_now();
	cyc = sys_cyc();
	if ((int32_t)(next - cnt) < (int32_t)STIM_ARM_MARGIN) {
		n_late++;
		next = cnt + STIM_ARM_MARGIN;
	}
	stim_next_phase = (uint32_t)((cyc + to_sys(next - cnt)) % tick_period);
	stim_next_ccr = next;
	port_stim_set(next);
	irq_unlock(key);
}

/*
 * The timer driver keeps its tick boundaries at multiples of the tick
 * period in the count of k_cycle_get_64(). Set the first reference, for
 * phase_check() before the first stim_arm().
 */
static void phase_init(void)
{
	unsigned int key = irq_lock();
	uint32_t cnt = port_stim_now();
	uint64_t cyc = sys_cyc();

	irq_unlock(key);
	ref_cnt = cnt;
	ref_cyc = cyc;
	stim_next_ccr = cnt;
	stim_next_phase = (uint32_t)(cyc % tick_period);
}

/*
 * The stimulus timer and the system timer count clocks from the same
 * source. Print how many cycles k_cycle_get_64() fell behind the stimulus
 * timer since stim_init() (negative: it ran ahead), in system timer
 * cycles. The 32-bit difference is exact only while the drift is less
 * than 2^31 counts.
 */
static void drift_check(void)
{
	unsigned int key = irq_lock();
	uint32_t cnt = port_stim_now();
	uint64_t cyc = sys_cyc();

	irq_unlock(key);
	printk("LAT META clock_elapsed_cyc=%llu\n", (cyc - ref_cyc) & SYS_CYC_MASK);
	if (stim_hz == sys_hz) {
		printk("LAT META clock_drift_cyc=%d\n",
		       (int32_t)((cnt - ref_cnt) - (uint32_t)(cyc - ref_cyc)));
	} else {
		/* The stimulus timer wraps before a long run ends: no exact count. */
		printk("LAT META clock_drift_cyc=n/a\n");
	}
}

/*
 * Check the phase: a thread that sleeps for one tick wakes shortly after
 * a tick boundary, so its phase must be small (the timer ISR and one
 * switch, about 1000 to 3000 cycles at 170 MHz).
 */
static void phase_check(const char *key)
{
	uint32_t now;

	k_sleep(K_TICKS(1));
	now = port_stim_now();
	printk("LAT META %s=%u\n", key,
	       (uint32_t)((stim_next_phase + to_sys(now - stim_next_ccr)) % tick_period));
}

/* Microseconds to stimulus timer counts, exact for any timer clock. */
static uint32_t us_to_counts(uint32_t us)
{
	return (uint32_t)((uint64_t)us * stim_hz / 1000000U);
}

int stim_init(void)
{
	int ret;

	stim_hz = port_stim_hz();
	sys_hz = sys_clock_hw_cycles_per_sec();
	tick_period = sys_hz / CONFIG_SYS_CLOCK_TICKS_PER_SEC;
	printk("LAT META port=%s\n", port_name);
	printk("LAT META stim_timer_hz=%u\n", stim_hz);
	printk("LAT META sys_timer_hz=%u\n", sys_hz);
#if defined(CONFIG_LATBENCH_STIM_RANDOM)
	stim_min = us_to_counts(CONFIG_LATBENCH_STIM_MIN_US);
	stim_span = us_to_counts(CONFIG_LATBENCH_STIM_MAX_US) - stim_min;
	printk("LAT META stim_mode=random\n");
	printk("LAT META stim_seed=0x%08x\n", CONFIG_LATBENCH_STIM_SEED);
	printk("LAT META stim_us=%u..%u\n", CONFIG_LATBENCH_STIM_MIN_US,
	       CONFIG_LATBENCH_STIM_MAX_US);
#else
	stim_period = us_to_counts(CONFIG_LATBENCH_STIM_PERIOD_US) + CONFIG_LATBENCH_STIM_PERIOD_ADJ_CYC;
	printk("LAT META stim_mode=fixed\n");
	printk("LAT META stim_period_cyc=%u\n", stim_period);
#endif
	printk("LAT META tick_period_cyc=%u\n", tick_period);

	if (!gpio_is_ready_dt(&stim_resp)) {
		return -ENODEV;
	}
	ret = gpio_pin_configure_dt(&stim_resp, GPIO_INPUT);
	if (ret < 0) {
		return ret;
	}
	ret = port_stim_init();
	if (ret < 0) {
		return ret;
	}

	phase_init();
	phase_check("tick_phase_check");
	return 0;
}

void stim_print_stats(void)
{
	printk("LAT META stim_overruns=%u\n", n_overruns);
	printk("LAT META stim_late=%u\n", n_late);
	drift_check();
	/* The same check after the run: a clock drift shows here. */
	phase_check("tick_phase_check_end");
}

bool stim_static_check(void)
{
	int lo;
	int hi;

	port_stim_force(false);
	k_busy_wait(10);
	lo = gpio_pin_get_dt(&stim_resp);
	port_stim_force(true);
	k_busy_wait(10);
	hi = gpio_pin_get_dt(&stim_resp);
	port_stim_force(false);
	k_busy_wait(10);

	printk("LAT META static_check=%s\n", (lo == 0 && hi == 1) ? "ok" : "fail");
	return lo == 0 && hi == 1;
}
