/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <zephyr/ztest.h>
#include <zephyr/arch/cpu.h>
#include <zephyr/arch/syscall.h>
#include <kernel_arch_interface.h>
#include <kernel_arch_func.h>
#include <kernel_unit_trace.h>

DEFINE_FAKE_VALUE_FUNC(uint32_t, unit_arch_k_cycle_get_32);
DEFINE_FAKE_VALUE_FUNC(uint64_t, unit_arch_k_cycle_get_64);
DEFINE_FAKE_VALUE_FUNC(unsigned int, unit_arch_irq_lock);
DEFINE_FAKE_VOID_FUNC(unit_arch_irq_unlock, unsigned int);
DEFINE_FAKE_VALUE_FUNC(bool, unit_arch_irq_unlocked, unsigned int);
DEFINE_FAKE_VALUE_FUNC(bool, unit_arch_cpu_irqs_are_enabled);

#ifdef CONFIG_USERSPACE
DEFINE_FAKE_VALUE_FUNC(uintptr_t, unit_arch_syscall_invoke0, uintptr_t);
DEFINE_FAKE_VALUE_FUNC(uintptr_t, unit_arch_syscall_invoke1, uintptr_t, uintptr_t);
DEFINE_FAKE_VALUE_FUNC(uintptr_t, unit_arch_syscall_invoke2, uintptr_t, uintptr_t, uintptr_t);
DEFINE_FAKE_VALUE_FUNC(uintptr_t, unit_arch_syscall_invoke3, uintptr_t, uintptr_t, uintptr_t,
		       uintptr_t);
DEFINE_FAKE_VALUE_FUNC(uintptr_t, unit_arch_syscall_invoke4, uintptr_t, uintptr_t, uintptr_t,
		       uintptr_t, uintptr_t);
DEFINE_FAKE_VALUE_FUNC(uintptr_t, unit_arch_syscall_invoke5, uintptr_t, uintptr_t, uintptr_t,
		       uintptr_t, uintptr_t, uintptr_t);
DEFINE_FAKE_VALUE_FUNC(uintptr_t, unit_arch_syscall_invoke6, uintptr_t, uintptr_t, uintptr_t,
		       uintptr_t, uintptr_t, uintptr_t, uintptr_t);
DEFINE_FAKE_VALUE_FUNC(bool, unit_arch_is_user_context);
#endif /* CONFIG_USERSPACE */

DEFINE_FAKE_VALUE_FUNC(bool, arch_is_in_isr);
#ifndef CONFIG_USE_SWITCH
DEFINE_FAKE_VOID_FUNC(arch_thread_return_value_set, struct k_thread *, unsigned int);
#endif
DEFINE_FAKE_VALUE_FUNC(int, arch_coprocessors_disable, struct k_thread *);

/* The context switch of kernel_arch_func.h (see the model group platform). */
DEFINE_FAKE_VALUE_FUNC(int, arch_swap, unsigned int);
DEFINE_FAKE_VOID_FUNC(arch_switch, void *, void **);
DEFINE_FAKE_VOID_FUNC(arch_spin_relax);

static void arch_fakes_reset(const struct ztest_unit_test *test, void *fixture)
{
	ARG_UNUSED(test);
	ARG_UNUSED(fixture);

	ARCH_CPU_FFF_FAKES_LIST(RESET_FAKE);
#ifdef CONFIG_USERSPACE
	ARCH_SYSCALL_FFF_FAKES_LIST(RESET_FAKE);
#endif
	KERNEL_ARCH_INTERFACE_FFF_FAKES_LIST(RESET_FAKE);
	KERNEL_ARCH_FUNC_FFF_FAKES_LIST(RESET_FAKE);
}

ZTEST_RULE(arch_fakes_reset, arch_fakes_reset, NULL);
