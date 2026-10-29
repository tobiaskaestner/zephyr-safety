/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * The model of the platform below the scheduler (model group platform). See
 * kernel_unit_platform.h for the use, and safety/spec/tla/lib/Platform.tla
 * for the contract. One CPU, Cortex-M (ARMv7-M, ARMv8-M Mainline).
 *
 * Each function names its operator of Platform, or the code location of
 * Zephyr 770fdef1567 that it follows (an @assumption of Platform).
 */

#include <string.h>
#include <zephyr/ztest.h>
#include <zephyr/kernel_structs.h>
#include <zephyr/arch/cpu.h>
#include <kernel_arch_interface.h>
#include <kernel_arch_func.h>
#include <kthread.h>
#ifdef CONFIG_USE_SWITCH
#ifndef KERNEL_UNIT_REAL_HEADER_ksched
#error "the platform model with CONFIG_USE_SWITCH needs the real ksched.h"
#endif
#include <ksched.h>
#endif
#ifdef KERNEL_UNIT_FAKE_GROUP_timeout
#include <fakes/timeout.h>
#endif
#include <kernel_unit_platform.h>

struct kernel_unit_platform kernel_unit_platform;

/* Short name of the state in this file. */
#define PF kernel_unit_platform

static const char *check_name(unsigned int check)
{
	switch (check) {
	case KERNEL_UNIT_PLATFORM_MISUSE:
		return "Misuse";
	case KERNEL_UNIT_PLATFORM_NO_RETURN:
		return "NoReturn";
	case KERNEL_UNIT_PLATFORM_SWITCH_LOCKED:
		return "NoSwitchWhileLocked";
	default:
		return "?";
	}
}

/* A check failed. Record it. If the test does not expect it, print it and fail the test. */
static void report(unsigned int check, const char *what)
{
	PF.found |= check;
	if ((PF.expected & check) == 0U) {
		TC_PRINT("platform: check %s failed: %s\n", check_name(check), what);
		ztest_test_fail();
	}
}

/* Record a change of _current. */
static void record_switch(struct k_thread *from, struct k_thread *to, const char *where)
{
	if ((from != to) && (PF.n_switches < ARRAY_SIZE(PF.switches))) {
		PF.switches[PF.n_switches++] = (struct kernel_unit_platform_switch){
			.from = from, .to = to, .where = where};
	}
}

/* The thread can run: no wait, not dead (the swap is a preemption, not a wait). */
static bool can_run(const struct k_thread *thread)
{
	return z_is_thread_ready(thread);
}

/*
 * IrqLock: arch_irq_lock() returns the old BASEPRI and raises it.
 * @assumption include/zephyr/arch/arm/asm_inline_gcc.h:56 (the key is the old BASEPRI)
 */
static unsigned int model_irq_lock(void)
{
	unsigned int key = PF.basepri;

	PF.basepri = KERNEL_UNIT_PLATFORM_LOCKED;

	return key;
}

/*
 * IrqUnlock: arch_irq_unlock(key) writes BASEPRI and calls no kernel code. It
 * is not a reschedule point.
 * @assumption include/zephyr/arch/arm/asm_inline_gcc.h:80-99
 */
static void model_irq_unlock(unsigned int key)
{
	PF.basepri = key;
}

/*
 * KeyUnlocked: a key is unlocked if it is 0.
 * @assumption include/zephyr/arch/arm/asm_inline_gcc.h:102-106
 */
static bool model_irq_unlocked(unsigned int key)
{
	return key == 0U;
}

/*
 * InIsr: arch_is_in_isr(). At level 1 an ISR is one step of the model.
 * @assumption arch/arm/include/cortex_m/exception.h:93 (each exception is an ISR)
 */
static bool model_is_in_isr(void)
{
	return PF.in_isr;
}

#ifndef CONFIG_USE_SWITCH
/* arch_thread_return_value_set(): arch/arm/include/cortex_m/kernel_arch_func.h:66-69. */
static void model_return_value_set(struct k_thread *thread, unsigned int value)
{
	thread->arch.swap_return_value = (int)value;
}
#endif

#ifndef CONFIG_USE_SWITCH
/*
 * PendSVRuns: the PendSV handler switches to the cache as it is now, and
 * restores the BASEPRI of the new thread.
 * @assumption arch/arm/core/cortex_m/swap_helper.S:147 (PendSV reads the
 * cache when it runs)
 */
static void pendsv_runs(void)
{
	struct k_thread *next = _kernel.ready_q.cache;

	PF.pendsv = false;
	record_switch(_current, next, "pendsv");
	_kernel.cpus[0].current = next;
	PF.basepri = next->arch.basepri;
	next->arch.basepri = 0U;
}

/* RequestPendSV(c, TRUE). */
static void request_pendsv(void)
{
	PF.pendsv = true;
	PF.pendsv_requests++;
}
#endif

/*
 * The exit of an ISR to thread mode: a reschedule point.
 *
 * Without CONFIG_USE_SWITCH: z_arm_int_exit() sets PendSV pending if the
 * cache differs from _current. PendSV has the lowest priority: it runs after
 * the last pending ISR (in the gap of arch_swap(), after the last step of the
 * gap).
 * @assumption arch/arm/core/cortex_m/exc_exit.c:55-61 (CONFIG_PREEMPT_ENABLED=y)
 *
 * With CONFIG_USE_SWITCH: arm_m_must_switch() locks, calls
 * z_sched_next_handle(_current) (real code), and switches if it gives a
 * handle. The thread that runs after the exit is unlocked.
 * @assumption arch/arm/core/cortex_m/arm-m-switch.c:510-536
 */
static void isr_exit(void)
{
#ifdef CONFIG_USE_SWITCH
	struct k_thread *last = _current;
	struct k_thread *next;
	void *handle;

	PF.basepri = KERNEL_UNIT_PLATFORM_LOCKED;
	handle = z_sched_next_handle(last);
	next = _current;
	if (handle != NULL) {
		/* arm_m_do_switch(): the context of the old thread is its handle. */
		last->switch_handle = last;
		record_switch(last, next, "isr exit");
	} else if (next != last) {
		/* z_get_next_switch_handle() changed _current, but no handle: no switch. */
		report(KERNEL_UNIT_PLATFORM_MISUSE, "a ready thread without a switch handle");
	}
	PF.basepri = 0U;
#else
	if (IS_ENABLED(CONFIG_PREEMPT_ENABLED) && (_kernel.ready_q.cache != _current)) {
		request_pendsv();
	}
	if (PF.pendsv && !PF.in_gap) {
		/* The thread that the interrupt stopped was unlocked. */
		_current->arch.basepri = 0U;
		pendsv_runs();
	}
#endif
}

/* An ISR step: IrqCanRun, the action in ISR context, then the exit. */
static void run_isr(kernel_unit_platform_action_t action, void *arg)
{
	if (PF.basepri != 0U) {
		report(KERNEL_UNIT_PLATFORM_MISUSE, "an interrupt while the CPU is locked");
		return;
	}
	if (PF.in_isr) {
		report(KERNEL_UNIT_PLATFORM_MISUSE, "a nested ISR (level 2)");
		return;
	}
	PF.in_isr = true;
	if (action != NULL) {
		action(arg);
	}
	PF.in_isr = false;
	if (PF.basepri != 0U) {
		report(KERNEL_UNIT_PLATFORM_MISUSE, "an ISR that ends with the CPU locked");
		PF.basepri = 0U;
	}
	isr_exit();
}

#ifdef KERNEL_UNIT_FAKE_GROUP_timeout
static void expire_first(void *arg)
{
	bool *expired = arg;

	*expired = kernel_unit_timeout_expire_first();
}
#endif

/*
 * The timer ISR (ClockCanFire, then Scheduler!ThreadTimeout): the first armed
 * timeout expires, then the exit of the ISR.
 * @assumption drivers/timer/cortex_m_systick.c:330-336
 */
bool kernel_unit_platform_timer_isr(void)
{
	bool expired = false;

#ifdef KERNEL_UNIT_FAKE_GROUP_timeout
	if (kernel_unit_timeout.n_armed > 0U) {
		run_isr(expire_first, &expired);
	}
#endif

	return expired;
}

static bool idle_runs(void)
{
	return (_current == NULL) || (_current == _kernel.cpus[0].idle_thread);
}

/* Run one environment step. */
static void run_step(const struct kernel_unit_platform_step *step)
{
	switch (step->kind) {
	case KERNEL_UNIT_PLATFORM_STEP_THREAD:
		if (_current != step->thread) {
			report(KERNEL_UNIT_PLATFORM_MISUSE,
			       "the thread of an environment step does not run");
		} else if (step->action != NULL) {
			step->action(step->arg);
		}
		break;
	case KERNEL_UNIT_PLATFORM_STEP_RUNNING:
		if (idle_runs()) {
			run_isr(step->action, step->arg);
		} else if (step->action != NULL) {
			step->action(step->arg);
		}
		break;
	case KERNEL_UNIT_PLATFORM_STEP_ISR:
	case KERNEL_UNIT_PLATFORM_STEP_GAP_ISR:
		run_isr(step->action, step->arg);
		break;
	case KERNEL_UNIT_PLATFORM_STEP_TIMEOUT:
	default:
		if (!kernel_unit_platform_timer_isr()) {
			report(KERNEL_UNIT_PLATFORM_MISUSE,
			       "a timeout step without an armed timeout");
		}
		break;
	}
	if (PF.check_point != NULL) {
		PF.check_point();
	}
}

/* The waiting thread never runs again. The harness continues on its stack. */
static void no_return(const char *what)
{
	report(KERNEL_UNIT_PLATFORM_NO_RETURN, what);
	PF.halted = true;
}

/*
 * The thread w waits (it cannot run) and is not current. Run the environment
 * until w is current again. If no step is left, the first armed timeout
 * expires, as the reference fake does. If no timeout is armed, no event can
 * give w the CPU: the switch does not return.
 */
static void wait_until_current(struct k_thread *w)
{
	while ((_current != w) && !PF.halted) {
		if ((w->base.thread_state & _THREAD_DEAD) != 0U) {
			no_return("the waiting thread was aborted");
		} else if (PF.next_step < PF.n_steps) {
			run_step(&PF.steps[PF.next_step++]);
		} else if (kernel_unit_platform_timer_isr()) {
			if (PF.check_point != NULL) {
				PF.check_point();
			}
		} else {
			no_return(can_run(w) ? "the woken thread does not get the CPU"
					     : "the thread waits for ever (no waker, no timeout)");
		}
	}
}

/*
 * The part of a switch after _current changed: a thread that waits (it
 * cannot run) runs the environment. A wait inside an environment action is a
 * misuse: one host stack cannot keep two waiting threads.
 */
static void after_switch(struct k_thread *old, bool waits)
{
	if ((_current == old) || !waits) {
		return;
	}
	if (PF.depth > 1U) {
		report(KERNEL_UNIT_PLATFORM_MISUSE, "an environment action waits");
		return;
	}
	wait_until_current(old);
}

#ifndef CONFIG_USE_SWITCH
/*
 * arch_swap(key): arch/arm/include/cortex_m/kernel_arch_func.h:87-103.
 *
 * - RequestPendSV(c, TRUE): the key and -EAGAIN go to the thread, PendSV is
 *   pending, irq_unlock(0) unlocks the CPU.
 * - The gap of CONFIG_SWAP_NONATOMIC: the ISR steps of the kind GAP_ISR run
 *   before PendSV (PendSV has the lowest priority).
 *   @assumption arch/arm/include/cortex_m/exception.h:144-149
 * - PendSVRuns: the switch to the cache.
 * - A thread that waits runs the environment until it is current again.
 *
 * The thread must not hold an outer interrupt lock (NoSwitchWhileLocked,
 * PendingIsUnlocked): a key other than 0 fails the check SWITCH_LOCKED.
 */
static int model_arch_swap(unsigned int key)
{
	struct k_thread *old = _current;
	bool waits = !can_run(old);

	if (key != 0U) {
		report(KERNEL_UNIT_PLATFORM_SWITCH_LOCKED, "arch_swap() with an outer irq_lock()");
	}
	PF.depth++;
	old->arch.basepri = key;
	old->arch.swap_return_value = -EAGAIN;
	request_pendsv();
	arch_irq_unlock(0U);

	PF.in_gap = true;
	while ((PF.next_step < PF.n_steps) &&
	       (PF.steps[PF.next_step].kind == KERNEL_UNIT_PLATFORM_STEP_GAP_ISR)) {
		run_step(&PF.steps[PF.next_step++]);
	}
	PF.in_gap = false;
	if (PF.pendsv) {
		pendsv_runs();
	}
	after_switch(old, waits);
	PF.depth--;

	return old->arch.swap_return_value;
}
#else
/*
 * arch_switch(): SwitchAtOnce. do_swap() of kswap.h has selected the cache
 * with the interrupts locked and has set _current. arm_m_switch() stores the
 * context of the old thread in *switched_from, and the new thread unlocks
 * after the stack switch.
 * @assumption arch/arm/core/cortex_m/arm-m-switch.c (arm_m_switch())
 */
static void model_arch_switch(void *switch_to, void **switched_from)
{
	struct k_thread *old = CONTAINER_OF(switched_from, struct k_thread, switch_handle);
	bool waits = !can_run(old);

	ARG_UNUSED(switch_to);

	PF.depth++;
	*switched_from = old;
	record_switch(old, _current, "arch_switch");
	PF.basepri = 0U;
	after_switch(old, waits);
	/* Back in do_swap() of the old thread, which unlocks with its key. */
	PF.basepri = KERNEL_UNIT_PLATFORM_LOCKED;
	PF.depth--;
}
#endif

static void add_step(enum kernel_unit_platform_step_kind kind, struct k_thread *thread,
		     kernel_unit_platform_action_t action, void *arg)
{
	if (PF.n_steps >= ARRAY_SIZE(PF.steps)) {
		report(KERNEL_UNIT_PLATFORM_MISUSE, "too many environment steps");
		return;
	}
	PF.steps[PF.n_steps++] = (struct kernel_unit_platform_step){
		.kind = kind, .thread = thread, .action = action, .arg = arg};
}

void kernel_unit_platform_env_thread(struct k_thread *thread, kernel_unit_platform_action_t action,
				     void *arg)
{
	add_step(KERNEL_UNIT_PLATFORM_STEP_THREAD, thread, action, arg);
}

void kernel_unit_platform_env_running(kernel_unit_platform_action_t action, void *arg)
{
	add_step(KERNEL_UNIT_PLATFORM_STEP_RUNNING, NULL, action, arg);
}

void kernel_unit_platform_env_isr(kernel_unit_platform_action_t action, void *arg)
{
	add_step(KERNEL_UNIT_PLATFORM_STEP_ISR, NULL, action, arg);
}

void kernel_unit_platform_env_gap_isr(kernel_unit_platform_action_t action, void *arg)
{
	add_step(KERNEL_UNIT_PLATFORM_STEP_GAP_ISR, NULL, action, arg);
}

void kernel_unit_platform_env_timeout(void)
{
	add_step(KERNEL_UNIT_PLATFORM_STEP_TIMEOUT, NULL, NULL, NULL);
}

void kernel_unit_platform_run_isr(kernel_unit_platform_action_t action, void *arg)
{
	run_isr(action, arg);
}

bool kernel_unit_platform_locked(void)
{
	return PF.basepri != 0U;
}

void kernel_unit_platform_expect(unsigned int checks)
{
	PF.expected |= checks;
}

void kernel_unit_platform_assert_ok(void)
{
	unsigned int unexpected = PF.found & ~PF.expected;

	if (unexpected != 0U) {
		TC_PRINT("platform: unexpected failed checks 0x%x\n", unexpected);
		ztest_test_fail();
	}
}

void kernel_unit_platform_install(void)
{
	PF.installed = true;
	PF.basepri = 0U;
	unit_arch_irq_lock_fake.custom_fake = model_irq_lock;
	unit_arch_irq_unlock_fake.custom_fake = model_irq_unlock;
	unit_arch_irq_unlocked_fake.custom_fake = model_irq_unlocked;
	arch_is_in_isr_fake.custom_fake = model_is_in_isr;
#ifndef CONFIG_USE_SWITCH
	arch_thread_return_value_set_fake.custom_fake = model_return_value_set;
	arch_swap_fake.custom_fake = model_arch_swap;
#else
	arch_switch_fake.custom_fake = model_arch_switch;
#endif
#ifdef KERNEL_UNIT_FAKE_GROUP_timeout
	kernel_unit_timeout_model_install();
#endif
}

static void platform_reset(const struct ztest_unit_test *test, void *fixture)
{
	ARG_UNUSED(test);
	ARG_UNUSED(fixture);

	memset(&kernel_unit_platform, 0, sizeof(kernel_unit_platform));
}

ZTEST_RULE(platform_reset, platform_reset, NULL);
