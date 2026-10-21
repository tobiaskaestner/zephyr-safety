/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Shadow of kernel/include/kernel_internal.h.
 *
 * Only the symbols that a unit under test uses are here. Each function
 * is an FFF fake.
 *
 * The fake group kernel_internal defines z_handle_obj_poll_events(). The
 * fake group mempool defines z_thread_malloc(), together with k_free()
 * (see fakes/mempool.h): kernel/mempool.c implements both functions.
 */

#ifndef ZEPHYR_KERNEL_INCLUDE_KERNEL_INTERNAL_H_
#define ZEPHYR_KERNEL_INCLUDE_KERNEL_INTERNAL_H_

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/dlist.h>
#include <zephyr/fff.h>
#include <kernel_arch_interface.h>

#ifdef __cplusplus
extern "C" {
#endif

#define KERNEL_INTERNAL_FFF_FAKES_LIST(FAKE) FAKE(z_handle_obj_poll_events)

DECLARE_FAKE_VALUE_FUNC(bool, z_handle_obj_poll_events, sys_dlist_t *, uint32_t);

/* Fake of the fake group mempool. */
DECLARE_FAKE_VALUE_FUNC(void *, z_thread_malloc, size_t);

/*
 * Boot-time init hook of a kernel unit, a copy of the real definition. It
 * is not a fake: the entry is data in the unit. A test can read the entry
 * _kernel_init_pre_<fn> of the unit, and call the static init function
 * directly. The kernel does not start, so nothing runs the entries.
 */
struct k_kernel_init_pre_entry {
	void (*init_fn)(void);
};

#define K_KERNEL_INIT_PRE(_fn)                                                                     \
	static const STRUCT_SECTION_ITERABLE(k_kernel_init_pre_entry, _kernel_init_pre_##_fn) = {  \
		.init_fn = (_fn),                                                                  \
	}

#ifdef __cplusplus
}
#endif

#endif /* ZEPHYR_KERNEL_INCLUDE_KERNEL_INTERNAL_H_ */
