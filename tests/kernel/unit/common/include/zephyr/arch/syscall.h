/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Shadow of include/zephyr/arch/syscall.h.
 *
 * The real header includes the system call header of the architecture.
 * The unit_testing architecture identifies itself as X86, so the real
 * header gives x86 inline assembly. Here, each function forwards to an FFF
 * fake with the prefix unit_, as in the shadow zephyr/arch/cpu.h.
 */

#ifndef ZEPHYR_INCLUDE_ARCH_SYSCALL_H_
#define ZEPHYR_INCLUDE_ARCH_SYSCALL_H_

#ifdef CONFIG_USERSPACE

#include <stdbool.h>
#include <stdint.h>
#include <zephyr/fff.h>

#ifdef __cplusplus
extern "C" {
#endif

#define ARCH_SYSCALL_FFF_FAKES_LIST(FAKE)                                                          \
	FAKE(unit_arch_syscall_invoke0)                                                            \
	FAKE(unit_arch_syscall_invoke1)                                                            \
	FAKE(unit_arch_syscall_invoke2)                                                            \
	FAKE(unit_arch_syscall_invoke3)                                                            \
	FAKE(unit_arch_syscall_invoke4)                                                            \
	FAKE(unit_arch_syscall_invoke5)                                                            \
	FAKE(unit_arch_syscall_invoke6)                                                            \
	FAKE(unit_arch_is_user_context)

DECLARE_FAKE_VALUE_FUNC(uintptr_t, unit_arch_syscall_invoke0, uintptr_t);
DECLARE_FAKE_VALUE_FUNC(uintptr_t, unit_arch_syscall_invoke1, uintptr_t, uintptr_t);
DECLARE_FAKE_VALUE_FUNC(uintptr_t, unit_arch_syscall_invoke2, uintptr_t, uintptr_t, uintptr_t);
DECLARE_FAKE_VALUE_FUNC(uintptr_t, unit_arch_syscall_invoke3, uintptr_t, uintptr_t, uintptr_t,
			uintptr_t);
DECLARE_FAKE_VALUE_FUNC(uintptr_t, unit_arch_syscall_invoke4, uintptr_t, uintptr_t, uintptr_t,
			uintptr_t, uintptr_t);
DECLARE_FAKE_VALUE_FUNC(uintptr_t, unit_arch_syscall_invoke5, uintptr_t, uintptr_t, uintptr_t,
			uintptr_t, uintptr_t, uintptr_t);
DECLARE_FAKE_VALUE_FUNC(uintptr_t, unit_arch_syscall_invoke6, uintptr_t, uintptr_t, uintptr_t,
			uintptr_t, uintptr_t, uintptr_t, uintptr_t);
DECLARE_FAKE_VALUE_FUNC(bool, unit_arch_is_user_context);

static inline uintptr_t arch_syscall_invoke0(uintptr_t call_id)
{
	return unit_arch_syscall_invoke0(call_id);
}

static inline uintptr_t arch_syscall_invoke1(uintptr_t arg1, uintptr_t call_id)
{
	return unit_arch_syscall_invoke1(arg1, call_id);
}

static inline uintptr_t arch_syscall_invoke2(uintptr_t arg1, uintptr_t arg2, uintptr_t call_id)
{
	return unit_arch_syscall_invoke2(arg1, arg2, call_id);
}

static inline uintptr_t arch_syscall_invoke3(uintptr_t arg1, uintptr_t arg2, uintptr_t arg3,
					     uintptr_t call_id)
{
	return unit_arch_syscall_invoke3(arg1, arg2, arg3, call_id);
}

static inline uintptr_t arch_syscall_invoke4(uintptr_t arg1, uintptr_t arg2, uintptr_t arg3,
					     uintptr_t arg4, uintptr_t call_id)
{
	return unit_arch_syscall_invoke4(arg1, arg2, arg3, arg4, call_id);
}

static inline uintptr_t arch_syscall_invoke5(uintptr_t arg1, uintptr_t arg2, uintptr_t arg3,
					     uintptr_t arg4, uintptr_t arg5, uintptr_t call_id)
{
	return unit_arch_syscall_invoke5(arg1, arg2, arg3, arg4, arg5, call_id);
}

static inline uintptr_t arch_syscall_invoke6(uintptr_t arg1, uintptr_t arg2, uintptr_t arg3,
					     uintptr_t arg4, uintptr_t arg5, uintptr_t arg6,
					     uintptr_t call_id)
{
	return unit_arch_syscall_invoke6(arg1, arg2, arg3, arg4, arg5, arg6, call_id);
}

static inline bool arch_is_user_context(void)
{
	return unit_arch_is_user_context();
}

#ifdef __cplusplus
}
#endif

#endif /* CONFIG_USERSPACE */

#endif /* ZEPHYR_INCLUDE_ARCH_SYSCALL_H_ */
