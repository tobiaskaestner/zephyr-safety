/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Data pad (LATBENCH_DATA_PAD). latbench.cmake adds this file only with
 * the option. The array is in the .bss of the app, before the data of the
 * kernel, so the kernel data moves by its size. lat_meta_print() refers to
 * it, so the linker keeps it.
 */

#include <stdint.h>
#include <zephyr/toolchain.h>

uint8_t lat_data_pad[CONFIG_LATBENCH_DATA_PAD_BYTES] __aligned(8);
