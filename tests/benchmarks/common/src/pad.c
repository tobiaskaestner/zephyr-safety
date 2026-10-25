/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Code padding (LATBENCH_CODE_PAD_BYTES). latbench.cmake adds this file
 * first, so its code comes before the other app code and before the
 * kernel code in flash. A pad of N bytes moves all that code by N bytes,
 * and nothing else changes. The function exists also with a pad of 0, so
 * that the other code is the same for all pad sizes. An experiment uses
 * it to measure how much the place of the code changes the latency (flash
 * cache, prefetch).
 *
 * With LATBENCH_CODE_RAM, latbench.cmake compiles this file in a library
 * of its own, and the pad is the first function of the relocated code.
 * Without LATBENCH_CODE_FLASH_PAD and LATBENCH_CODE_RAM the pad is 0.
 */

#include <zephyr/kernel.h>

#ifndef CONFIG_LATBENCH_CODE_PAD_BYTES
#define CONFIG_LATBENCH_CODE_PAD_BYTES 0
#endif

BUILD_ASSERT((CONFIG_LATBENCH_CODE_PAD_BYTES % 4) == 0, "the pad must be a multiple of 4 bytes");

/*
 * Never called. The linker script sorts the .text.* sections by
 * alignment (SORT_BY_ALIGNMENT). With an alignment of 4 the pad comes
 * first in its group, and a multiple of 4 moves the code after it by
 * exactly that number of bytes.
 */
__attribute__((used, naked, aligned(4))) void lat_code_pad(void)
{
	__asm__ volatile(".space " STRINGIFY(CONFIG_LATBENCH_CODE_PAD_BYTES));
}
