/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Shadow of include/zephyr/internal/syscall_handler.h.
 *
 * Without CONFIG_USERSPACE the real header is empty, and so is this one.
 * With CONFIG_USERSPACE it has the verification macros that the z_vrfy_*
 * functions of a unit use. The macros keep their structure, but each
 * function they call is an FFF fake:
 *
 * - K_SYSCALL_IS_OBJ() calls k_object_find() and
 *   k_object_validation_check() (static inline in the real header).
 * - K_OOPS() calls unit_syscall_oops() in place of
 *   arch_syscall_oops(_current->syscall_frame).
 *
 * K_SYSCALL_VERIFY_MSG() does not log.
 */

#ifndef ZEPHYR_INCLUDE_SYSCALL_HANDLER_H_
#define ZEPHYR_INCLUDE_SYSCALL_HANDLER_H_

#ifdef CONFIG_USERSPACE

#include <stdbool.h>
#include <zephyr/kernel.h>
#include <zephyr/fff.h>

#ifdef __cplusplus
extern "C" {
#endif

enum _obj_init_check {
	_OBJ_INIT_TRUE = 0,
	_OBJ_INIT_FALSE = -1,
	_OBJ_INIT_ANY = 1
};

#define SYSCALL_HANDLER_FFF_FAKES_LIST(FAKE)                                                       \
	FAKE(k_object_find)                                                                        \
	FAKE(k_object_validation_check)                                                            \
	FAKE(unit_syscall_oops)

DECLARE_FAKE_VALUE_FUNC(struct k_object *, k_object_find, const void *);
DECLARE_FAKE_VALUE_FUNC(int, k_object_validation_check, struct k_object *, const void *,
			enum k_objects, enum _obj_init_check);
DECLARE_FAKE_VOID_FUNC(unit_syscall_oops);

#define K_OOPS(expr)                                                                               \
	do {                                                                                       \
		if (expr) {                                                                        \
			unit_syscall_oops();                                                       \
		}                                                                                  \
	} while (false)

#define K_SYSCALL_VERIFY_MSG(expr, fmt, ...)                                                       \
	({                                                                                         \
		bool expr_copy = !(expr);                                                          \
		expr_copy;                                                                         \
	})

#define K_SYSCALL_VERIFY(expr) K_SYSCALL_VERIFY_MSG(expr, #expr)

#define K_SYSCALL_IS_OBJ(ptr, type, init)                                                          \
	K_SYSCALL_VERIFY_MSG(k_object_validation_check(k_object_find((const void *)(ptr)),         \
						       (const void *)(ptr), (type), (init)) == 0,  \
			     "access denied")

#define K_SYSCALL_OBJ(ptr, type) K_SYSCALL_IS_OBJ(ptr, type, _OBJ_INIT_TRUE)

#define K_SYSCALL_OBJ_INIT(ptr, type) K_SYSCALL_IS_OBJ(ptr, type, _OBJ_INIT_ANY)

#define K_SYSCALL_OBJ_NEVER_INIT(ptr, type) K_SYSCALL_IS_OBJ(ptr, type, _OBJ_INIT_FALSE)

/*
 * Memory checks. K_SYSCALL_MEMORY() keeps the structure of the real macro:
 * the size check, the pointer overflow check and arch_buffer_validate().
 * arch_buffer_validate() is extern in zephyr/arch/arch_interface.h and is a
 * fake here. After the reset it returns 0: the thread has access.
 */
#define SYSCALL_HANDLER_MEMORY_FFF_FAKES_LIST(FAKE) FAKE(arch_buffer_validate)

DECLARE_FAKE_VALUE_FUNC(int, arch_buffer_validate, const void *, size_t, int);

#define K_SYSCALL_MEMORY_SIZE_CHECK(ptr, size) (((uintptr_t)(ptr) + (size)) >= (uintptr_t)(ptr))

#define K_SYSCALL_MEMORY(ptr, size, write)                                                         \
	K_SYSCALL_VERIFY_MSG(K_SYSCALL_MEMORY_SIZE_CHECK(ptr, size) &&                             \
				     !Z_DETECT_POINTER_OVERFLOW(ptr, size) &&                      \
				     (arch_buffer_validate((void *)(ptr), (size), (write)) == 0),  \
			     "memory access denied")

#define K_SYSCALL_MEMORY_READ(ptr, size) K_SYSCALL_MEMORY(ptr, size, 0)

#define K_SYSCALL_MEMORY_WRITE(ptr, size) K_SYSCALL_MEMORY(ptr, size, 1)

#ifdef __cplusplus
}
#endif

#endif /* CONFIG_USERSPACE */

#endif /* ZEPHYR_INCLUDE_SYSCALL_HANDLER_H_ */
