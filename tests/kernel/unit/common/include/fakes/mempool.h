/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Fakes of the memory allocation functions of kernel/mempool.c.
 *
 * - z_thread_malloc(): allocates from the resource pool of the current
 *   thread. The real declaration is in kernel/include/kernel_internal.h,
 *   so the shadow kernel_internal.h declares the fake.
 * - k_free(): frees memory of k_malloc() or z_thread_malloc(). The real
 *   header zephyr/kernel.h declares it extern, so it needs no shadow.
 *
 * After the reset of each test, z_thread_malloc() returns NULL. A test
 * that needs memory sets return_val or custom_fake. Link the fake group
 * mempool only if the unit under test is not kernel/mempool.c.
 */

#ifndef KERNEL_UNIT_FAKES_MEMPOOL_H_
#define KERNEL_UNIT_FAKES_MEMPOOL_H_

#include <zephyr/kernel.h>
#include <zephyr/fff.h>
#include <kernel_internal.h>

#ifdef __cplusplus
extern "C" {
#endif

#define MEMPOOL_FFF_FAKES_LIST(FAKE)                                                               \
	FAKE(z_thread_malloc)                                                                      \
	FAKE(k_free)

DECLARE_FAKE_VOID_FUNC(k_free, void *);

#ifdef __cplusplus
}
#endif

#endif /* KERNEL_UNIT_FAKES_MEMPOOL_H_ */
