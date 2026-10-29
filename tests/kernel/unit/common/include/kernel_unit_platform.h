/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @defgroup kernel_unit_platform Model of the platform below the scheduler
 * @ingroup kernel_unit_models
 * @brief The arch fakes with the behavior of the module Platform, for one Cortex-M CPU.
 *
 * The model group @c platform is the C form of
 * @c safety/spec/tla/lib/Platform.tla (level 1, one CPU) for ARMv7-M and
 * ARMv8-M Mainline (BASEPRI). It is the contract below @c kernel/sched.c. The
 * model sets the @c custom_fake of the fakes of the group @c arch. Each model
 * function names its operator or its @c \@assumption of Platform.
 *
 * - The interrupt lock (IrqLock, IrqUnlock, Key, KeyUnlocked): the state is
 *   BASEPRI. arch_irq_lock() returns the old value and locks.
 *   arch_irq_unlock(key) writes the key. arch_irq_unlocked(key) is true only
 *   for the key 0 (asm_inline_gcc.h:56-106).
 * - arch_is_in_isr() (InIsr): true while an ISR step of the model runs.
 * - arch_thread_return_value_set() (without @c CONFIG_USE_SWITCH): writes
 *   @c thread->arch.swap_return_value.
 * - arch_swap() (RequestPendSV, the gap of @c CONFIG_SWAP_NONATOMIC,
 *   PendSVRuns): it stores the key and -EAGAIN, sets PendSV pending and
 *   unlocks with irq_unlock(0). The ISR steps of the gap run. Then PendSV
 *   switches to @c _kernel.ready_q.cache and restores the BASEPRI of the new
 *   thread.
 * - arch_switch() (@c CONFIG_USE_SWITCH, SwitchAtOnce): do_swap() has set
 *   @c _current. The model stores the handle of the old thread. No gap.
 * - The exit of an ISR: without @c CONFIG_USE_SWITCH, z_arm_int_exit()
 *   (exc_exit.c:55-61) sets PendSV pending if the cache differs from
 *   @c _current, and PendSV runs. With @c CONFIG_USE_SWITCH, the model of
 *   arm_m_must_switch() calls the real z_sched_next_handle().
 *
 * One host thread runs all threads of a test. The test code always runs as
 * @c _current. A switch of a thread that cannot run (it waits or is dead)
 * runs the environment steps of the test until the thread runs again. Then
 * the switch returns the swap return value. A switch of a thread that can run
 * (a preemption) returns at once, and the test continues as the new current
 * thread. An environment action must not wait (check MISUSE), and it ends
 * after its last reschedule point.
 *
 * The model is opt-in: kernel_unit_platform_install(). It needs the groups
 * @c arch and @c init. With the group @c timeout, the timer ISR of the model
 * lets the timeouts expire. A failed check prints a message and fails the
 * test, unless the test expects it (kernel_unit_platform_expect()).
 *
 * @{
 */

#ifndef KERNEL_UNIT_PLATFORM_H_
#define KERNEL_UNIT_PLATFORM_H_

#include <stdbool.h>
#include <stddef.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/util.h>

#ifdef __cplusplus
extern "C" {
#endif

/** The BASEPRI value of arch_irq_lock() (_EXC_IRQ_DEFAULT_PRIO, not 0). */
#define KERNEL_UNIT_PLATFORM_LOCKED 0x20U

/** Maximum number of environment steps of one test. */
#define KERNEL_UNIT_PLATFORM_MAX_STEPS 8

/** Maximum number of recorded switches of one test. */
#define KERNEL_UNIT_PLATFORM_MAX_SWITCHES 16

/** The checks of the model. Each check is one bit. */
enum kernel_unit_platform_check {
	/** A use that the model does not permit, for example a wait in an environment action. */
	KERNEL_UNIT_PLATFORM_MISUSE = BIT(0),
	/** A waiting thread never runs again: the switch does not return. */
	KERNEL_UNIT_PLATFORM_NO_RETURN = BIT(1),
	/** A switch with an outer interrupt lock (NoSwitchWhileLocked, PendingIsUnlocked). */
	KERNEL_UNIT_PLATFORM_SWITCH_LOCKED = BIT(2),
};

/** Action of an environment step. */
typedef void (*kernel_unit_platform_action_t)(void *arg);

/** The kinds of environment steps. */
enum kernel_unit_platform_step_kind {
	/** A given thread runs an action. It must be the current thread. */
	KERNEL_UNIT_PLATFORM_STEP_THREAD,
	/** The thread that runs does an action. If the idle thread runs, an ISR does it. */
	KERNEL_UNIT_PLATFORM_STEP_RUNNING,
	/** An ISR runs an action. Its exit is a reschedule point. */
	KERNEL_UNIT_PLATFORM_STEP_ISR,
	/**
	 * An ISR that is pending when arch_swap() unlocks: it runs in the gap
	 * before PendSV. Outside a gap, it is an ISR step.
	 */
	KERNEL_UNIT_PLATFORM_STEP_GAP_ISR,
	/** The timer ISR: the first armed timeout expires (group timeout). */
	KERNEL_UNIT_PLATFORM_STEP_TIMEOUT,
};

/** One environment step. */
struct kernel_unit_platform_step {
	/** The kind of the step. */
	enum kernel_unit_platform_step_kind kind;
	/** The thread of a step of the kind THREAD. */
	struct k_thread *thread;
	/** The action, or NULL. */
	kernel_unit_platform_action_t action;
	/** The argument of the action. */
	void *arg;
};

/** One change of @c _current. */
struct kernel_unit_platform_switch {
	/** The old current thread. */
	struct k_thread *from;
	/** The new current thread. */
	struct k_thread *to;
	/** The place of the switch: "pendsv", "arch_switch" or "isr exit". */
	const char *where;
};

/** The state of the model. The reset rule of the group sets it to zeros. */
struct kernel_unit_platform {
	/** True after kernel_unit_platform_install(). */
	bool installed;
	/** BASEPRI: 0 if the CPU is unlocked (Platform!Locked is basepri != 0). */
	unsigned int basepri;
	/** True while an ISR step runs (Platform!InIsr). */
	bool in_isr;
	/** True if PendSV is pending (Platform variable pendsv). */
	bool pendsv;
	/** True while the ISR steps of the gap of arch_swap() run. */
	bool in_gap;
	/** The environment steps. */
	struct kernel_unit_platform_step steps[KERNEL_UNIT_PLATFORM_MAX_STEPS];
	/** The number of environment steps. */
	size_t n_steps;
	/** The next environment step. */
	size_t next_step;
	/** The number of switch fakes on the host stack now. */
	unsigned int depth;
	/** True after NO_RETURN: the waiting thread stopped for ever. */
	bool halted;
	/** The checks that the test expects to fail. */
	unsigned int expected;
	/** The checks that failed since the install. */
	unsigned int found;
	/** A check of the test at the end of each environment step, or NULL. */
	void (*check_point)(void);
	/** The changes of @c _current. */
	struct kernel_unit_platform_switch switches[KERNEL_UNIT_PLATFORM_MAX_SWITCHES];
	/** The number of changes of @c _current. */
	size_t n_switches;
	/** The number of times that PendSV became pending. */
	unsigned int pendsv_requests;
};

/** The state of the platform model. */
extern struct kernel_unit_platform kernel_unit_platform;

/** @brief Install the model: set the custom fakes of the group arch. The CPU is unlocked. */
void kernel_unit_platform_install(void);

/** @brief Add a step: @p thread runs @p action while the waiting thread waits. */
void kernel_unit_platform_env_thread(struct k_thread *thread, kernel_unit_platform_action_t action,
				     void *arg);

/** @brief Add a step: the thread that runs (or an ISR, if the idle thread runs) does @p action. */
void kernel_unit_platform_env_running(kernel_unit_platform_action_t action, void *arg);

/** @brief Add a step: an ISR runs @p action (NULL: an interrupt without a kernel call). */
void kernel_unit_platform_env_isr(kernel_unit_platform_action_t action, void *arg);

/** @brief Add a step: an ISR that runs in the gap of the next arch_swap(), before PendSV. */
void kernel_unit_platform_env_gap_isr(kernel_unit_platform_action_t action, void *arg);

/** @brief Add a step: the timer ISR lets the first armed timeout expire. */
void kernel_unit_platform_env_timeout(void);

/**
 * @brief Run @p action in an ISR now. The exit of the ISR is a reschedule point.
 *
 * The CPU must be unlocked (Platform!IrqCanRun), else the check MISUSE fails.
 */
void kernel_unit_platform_run_isr(kernel_unit_platform_action_t action, void *arg);

/**
 * @brief Run the timer ISR now: the first armed timeout expires (ThreadTimeout).
 *
 * @return false if no timeout is armed (the ISR has no expiry).
 */
bool kernel_unit_platform_timer_isr(void);

/** @brief Return true if the CPU is locked (Platform!Locked). */
bool kernel_unit_platform_locked(void);

/** @brief Let the checks in @p checks fail without a failed test. */
void kernel_unit_platform_expect(unsigned int checks);

/** @brief Assert that no check failed that the test does not expect. */
void kernel_unit_platform_assert_ok(void);

#ifdef __cplusplus
}
#endif

/** @} */

#endif /* KERNEL_UNIT_PLATFORM_H_ */
