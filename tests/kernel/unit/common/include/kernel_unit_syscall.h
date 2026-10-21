/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Support for the stubs of the generated system call files
 * (zephyr/syscalls/<name>_mrsh.c).
 *
 * In a real build, the generated marshalling function z_mrsh_<name>()
 * calls z_vrfy_<name>(). A unit test does not generate the marshalling
 * functions. Many z_vrfy_* functions are static inline, so without a
 * reference the compiler does not emit them. Then code coverage does not
 * see them. KERNEL_UNIT_SYSCALL_STUB() takes the address of the function,
 * so the compiler emits it as in a real build.
 */

#ifndef KERNEL_UNIT_SYSCALL_H_
#define KERNEL_UNIT_SYSCALL_H_

#include <zephyr/toolchain.h>

#define KERNEL_UNIT_SYSCALL_STUB(vrfy_fn)                                                          \
	static __typeof__(&vrfy_fn) const __used kernel_unit_keep_##vrfy_fn = &vrfy_fn

#endif /* KERNEL_UNIT_SYSCALL_H_ */
