/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Shadow of the ztest unittest stub
 * subsys/testsuite/ztest/unittest/include/zephyr/arch/cpu.h.
 *
 * The architecture layer is the lowest boundary of a kernel unit. Every
 * arch_* function the stub provides forwards to an FFF fake here, so that
 * a test can observe and control the calls into the architecture layer.
 *
 * arch_interface.h declares these functions static inline, so they cannot
 * be fakes themselves. Each one forwards to a fake with the prefix unit_:
 * arch_irq_lock() calls unit_arch_irq_lock(), and a test uses
 * unit_arch_irq_lock_fake.
 */

#ifndef ZEPHYR_SUBSYS_TESTSUITE_ZTEST_INCLUDE_ARCH_CPU_H
#define ZEPHYR_SUBSYS_TESTSUITE_ZTEST_INCLUDE_ARCH_CPU_H

#include <inttypes.h>
#include <stdbool.h>
#include <zephyr/toolchain.h>
#include <zephyr/fff.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Architecture thread structure */
struct _callee_saved {
#ifdef CONFIG_CPP
	/* C++ does not allow empty structs, add an extra 1 byte */
	uint8_t c;
#endif
};

typedef struct _callee_saved _callee_saved_t;

struct _thread_arch {
#ifdef CONFIG_CPP
	/* C++ does not allow empty structs, add an extra 1 byte */
	uint8_t c;
#endif
};

typedef struct _thread_arch _thread_arch_t;

#ifdef CONFIG_USERSPACE
/* Memory domain types and attributes that a real arch header provides */
typedef uint32_t k_mem_partition_attr_t;

#define K_MEM_PARTITION_P_RW_U_RW ((k_mem_partition_attr_t)0x3U)
#define K_MEM_PARTITION_P_RW_U_NA ((k_mem_partition_attr_t)0x2U)
#define K_MEM_PARTITION_P_RO_U_RO ((k_mem_partition_attr_t)0x1U)
#define K_MEM_PARTITION_P_RO_U_NA ((k_mem_partition_attr_t)0x0U)

#ifdef CONFIG_ARCH_MEM_DOMAIN_DATA
struct arch_mem_domain {
	uint8_t c;
};
#endif /* CONFIG_ARCH_MEM_DOMAIN_DATA */
#endif /* CONFIG_USERSPACE */

#define ARCH_CPU_FFF_FAKES_LIST(FAKE)                                                              \
	FAKE(unit_arch_k_cycle_get_32)                                                             \
	FAKE(unit_arch_k_cycle_get_64)                                                             \
	FAKE(unit_arch_irq_lock)                                                                   \
	FAKE(unit_arch_irq_unlock)                                                                 \
	FAKE(unit_arch_irq_unlocked)                                                               \
	FAKE(unit_arch_cpu_irqs_are_enabled)

DECLARE_FAKE_VALUE_FUNC(uint32_t, unit_arch_k_cycle_get_32);
DECLARE_FAKE_VALUE_FUNC(uint64_t, unit_arch_k_cycle_get_64);
DECLARE_FAKE_VALUE_FUNC(unsigned int, unit_arch_irq_lock);
DECLARE_FAKE_VOID_FUNC(unit_arch_irq_unlock, unsigned int);
DECLARE_FAKE_VALUE_FUNC(bool, unit_arch_irq_unlocked, unsigned int);
DECLARE_FAKE_VALUE_FUNC(bool, unit_arch_cpu_irqs_are_enabled);

static inline uint32_t arch_k_cycle_get_32(void)
{
	return unit_arch_k_cycle_get_32();
}

static inline uint64_t arch_k_cycle_get_64(void)
{
	return unit_arch_k_cycle_get_64();
}

static ALWAYS_INLINE unsigned int arch_irq_lock(void)
{
	return unit_arch_irq_lock();
}

static inline void arch_irq_unlock(unsigned int key)
{
	unit_arch_irq_unlock(key);
}

static inline bool arch_irq_unlocked(unsigned int key)
{
	return unit_arch_irq_unlocked(key);
}

static inline bool arch_cpu_irqs_are_enabled(void)
{
	return unit_arch_cpu_irqs_are_enabled();
}

#ifdef __cplusplus
}
#endif /* __cplusplus */

#include <zephyr/arch/arch_interface.h>

#endif /* ZEPHYR_SUBSYS_TESTSUITE_ZTEST_INCLUDE_ARCH_CPU_H */
