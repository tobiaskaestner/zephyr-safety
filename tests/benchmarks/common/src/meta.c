/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>
#include <zephyr/version.h>
#include <zephyr/toolchain.h>
#include <latbench/meta.h>

#ifdef BUILD_VERSION
#define LAT_ZEPHYR_VERSION STRINGIFY(BUILD_VERSION)
#else
#define LAT_ZEPHYR_VERSION KERNEL_VERSION_STRING
#endif

/* Kconfig symbols that WP3 ranks as relevant for latency. */
#define LAT_CFG(sym) printk(" " #sym "=%d", IS_ENABLED(CONFIG_##sym))

/*
 * The core clock. A board port gives the real value (latbench/port.h).
 * Without a port (loopback_check), the system timer clock is the best
 * guess: on SysTick boards it is the core clock.
 */
__weak uint32_t port_core_hz(void)
{
	return sys_clock_hw_cycles_per_sec();
}

void lat_meta_kv(const char *key, const char *value)
{
	printk("LAT META %s=%s\n", key, value);
}

void lat_meta_print(const char *app, const char *variant)
{
	printk("LAT BEGIN\n");
	lat_meta_kv("app", app);
	lat_meta_kv("variant", variant);
	lat_meta_kv("zephyr", LAT_ZEPHYR_VERSION);
	lat_meta_kv("bench_rev", LATBENCH_SRC_REV);
	lat_meta_kv("board", CONFIG_BOARD_TARGET);
	printk("LAT META core_hz=%u\n", port_core_hz());
	printk("LAT META ticks_per_sec=%u\n", CONFIG_SYS_CLOCK_TICKS_PER_SEC);
	printk("LAT META samples=%u\n", CONFIG_LATBENCH_SAMPLES);

	printk("LAT CFG");
	LAT_CFG(USE_SWITCH);
	LAT_CFG(TIMESLICING);
	LAT_CFG(MPU_STACK_GUARD);
	LAT_CFG(HW_STACK_PROTECTION);
	LAT_CFG(SCHED_SIMPLE);
	LAT_CFG(SCHED_SCALABLE);
	LAT_CFG(SCHED_MULTIQ);
	LAT_CFG(WAITQ_SCALABLE);
	LAT_CFG(TIMEOUT_BACKEND_DLIST);
	LAT_CFG(ZERO_LATENCY_IRQS);
	LAT_CFG(TICKLESS_KERNEL);
	LAT_CFG(FPU);
	LAT_CFG(FPU_SHARING);
	LAT_CFG(SPEED_OPTIMIZATIONS);
	LAT_CFG(SIZE_OPTIMIZATIONS);
	LAT_CFG(ASSERT);
	LAT_CFG(SPIN_VALIDATE);
	LAT_CFG(TRACING);
	LAT_CFG(THREAD_RUNTIME_STATS);
	LAT_CFG(PM);
	LAT_CFG(USERSPACE);
	printk("\n");
#ifdef CONFIG_TIMESLICE_SIZE
	printk("LAT META timeslice_ms=%d\n", CONFIG_TIMESLICE_SIZE);
#endif
}

void lat_done(void)
{
	printk("LAT DONE\n");
}
