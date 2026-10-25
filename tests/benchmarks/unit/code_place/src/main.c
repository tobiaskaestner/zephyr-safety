/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Unit tests for the code placement (choice LATBENCH_CODE_PLACE in
 * common/Kconfig, common/latbench.cmake, common/src/pad.c and meta.c).
 *
 * - The metadata names the place and the pad.
 * - With LATBENCH_CODE_RAM, the pad is the first relocated function, the
 *   functions of the hot paths are in the relocated code, and the code that
 *   must stay in flash is not.
 * - With LATBENCH_CODE_RAM, a thread switch, a timeout and an interrupt
 *   run in the relocated code with the MPU on. A fault stops the test.
 */

#include <string.h>
#include <zephyr/ztest.h>
#include <zephyr/irq_offload.h>
#include <zephyr/sys/printk-hooks.h>
#include <latbench/hist.h>
#include <latbench/meta.h>

void lat_code_pad(void);

#ifndef CONFIG_LATBENCH_CODE_PAD_BYTES
#define CONFIG_LATBENCH_CODE_PAD_BYTES 0
#endif

/* The address of a function, without the Thumb bit. */
#define FN_ADDR(fn) ((uintptr_t)(fn) & ~(uintptr_t)1)

/* ----------------------------------------------------- printk capture */

static char cap[4096];
static size_t cap_len;
static printk_hook_fn_t cap_prev;

static int cap_hook(int c)
{
	if (cap_len < sizeof(cap) - 1U) {
		cap[cap_len++] = (char)c;
	}
	return c;
}

static const char *meta_text(void)
{
	cap_len = 0;
	cap_prev = __printk_get_hook();
	__printk_hook_install(cap_hook);
	lat_meta_print("unit", "code_place");
	__printk_hook_install(cap_prev);
	cap[cap_len] = '\0';
	return cap;
}

ZTEST(lat_code_place, test_meta_names_place_and_pad)
{
	const char *t = meta_text();
	char want[64];

	if (IS_ENABLED(CONFIG_LATBENCH_CODE_RAM)) {
		zassert_not_null(strstr(t, "LAT META code_place=ram\n"), "%s", t);
#ifdef CONFIG_LATBENCH_CODE_RAM_REGION
		zassert_not_null(strstr(t, "LAT META code_ram_region=" CONFIG_LATBENCH_CODE_RAM_REGION
					   "\n"), "%s", t);
#endif
		zassert_not_null(strstr(t, "LAT META code_ram_text=0x"), "%s", t);
	} else if (IS_ENABLED(CONFIG_LATBENCH_CODE_FLASH_PAD)) {
		zassert_not_null(strstr(t, "LAT META code_place=flash-pad\n"), "%s", t);
	} else {
		zassert_not_null(strstr(t, "LAT META code_place=flash\n"), "%s", t);
	}
	snprintk(want, sizeof(want), "LAT META code_pad=%u\n", CONFIG_LATBENCH_CODE_PAD_BYTES);
	zassert_not_null(strstr(t, want), "%s", t);
	/* The place comes before the pad, in this order. */
	zassert_true(strstr(t, "code_place=") < strstr(t, "code_pad="));
}

/* ----------------------------------------------------- the layout */

#ifdef CONFIG_LATBENCH_CODE_RAM
extern char __ram_text_reloc_start[];
extern char __ram_text_reloc_end[];

static bool in_ram_text(uintptr_t a)
{
	return a >= (uintptr_t)__ram_text_reloc_start && a < (uintptr_t)__ram_text_reloc_end;
}
#endif

/*
 * Functions of the hot paths, one of each relocated group, and functions
 * that must stay in flash with the region "RAM" (latbench.cmake). The
 * names are linker symbols, so that their prototypes do not matter.
 */
extern char f_sem_give[] __asm__("z_impl_k_sem_give");
extern char f_isr_wrapper[] __asm__("_isr_wrapper");
extern char f_pendsv[] __asm__("z_arm_pendsv");
extern char f_systick_isr[] __asm__("sys_clock_isr");
extern char f_cstart[] __asm__("z_cstart");
extern char f_mpu_init[] __asm__("z_arm_mpu_init");

ZTEST(lat_code_place, test_layout)
{
#ifdef CONFIG_LATBENCH_CODE_RAM
	zassert_equal(FN_ADDR(lat_code_pad), (uintptr_t)__ram_text_reloc_start,
		      "the pad is not the first relocated function");
	zassert_true(in_ram_text(FN_ADDR(f_sem_give)), "kernel");
	zassert_true(in_ram_text(FN_ADDR(f_isr_wrapper)), "arch");
	zassert_true(in_ram_text(FN_ADDR(f_pendsv)), "arch (asm)");
	zassert_true(in_ram_text(FN_ADDR(f_systick_isr)), "timer driver");
	zassert_true(in_ram_text(FN_ADDR(lat_hist_reset)), "app and common code");
	zassert_false(in_ram_text(FN_ADDR(f_cstart)), "kernel/init.c must stay in flash");
	zassert_false(in_ram_text(FN_ADDR(f_mpu_init)), "the MPU driver must stay in flash");
#else
	/* The pad is in flash, before the other app code. */
	zassert_true(FN_ADDR(lat_code_pad) < FN_ADDR(lat_hist_reset));
	zassert_true(FN_ADDR(lat_code_pad) + CONFIG_LATBENCH_CODE_PAD_BYTES <= FN_ADDR(lat_hist_reset));
#endif
}

/* ----------------------------------------------------- execution */

static K_SEM_DEFINE(ping, 0, 1);
static K_SEM_DEFINE(pong, 0, 1);
static K_THREAD_STACK_DEFINE(peer_stack, 1024);
static struct k_thread peer;
static volatile int offload_runs;

static void peer_main(void *a, void *b, void *c)
{
	for (int i = 0; i < 100; i++) {
		k_sem_take(&ping, K_FOREVER);
		k_sem_give(&pong);
	}
}

static void offload_fn(const void *arg)
{
	offload_runs++;
}

ZTEST(lat_code_place, test_switch_timeout_irq)
{
	k_thread_create(&peer, peer_stack, K_THREAD_STACK_SIZEOF(peer_stack), peer_main, NULL,
			NULL, NULL, K_PRIO_PREEMPT(1), 0, K_NO_WAIT);
	for (int i = 0; i < 100; i++) {
		k_sem_give(&ping);
		zassert_ok(k_sem_take(&pong, K_MSEC(100)));
	}
	k_thread_join(&peer, K_FOREVER);

	int64_t t0 = k_uptime_get();

	k_msleep(20);
	zassert_true(k_uptime_get() - t0 >= 20);

	irq_offload(offload_fn, NULL);
	zassert_equal(offload_runs, 1);
}

ZTEST_SUITE(lat_code_place, NULL, NULL, NULL, NULL, NULL);
