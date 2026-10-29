/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * The reference fake of the scheduler contract (fake group sched_ref). See
 * kernel_unit_sched_ref.h for the use, and safety/spec/tla/lib/Scheduler.tla
 * for the contract. One CPU (CPUS = {c1}).
 *
 * Each fake function of a scheduler call is the custom fake of the FFF fake
 * with the same C name. Its comment names the operator of the contract. Where
 * the C code and the contract differ, the fake follows the C code, and the
 * comment says so.
 *
 * Check points: the fake evaluates the invariants only at the end of a
 * critical section that it sees (z_reschedule(), the selection in
 * z_pend_curr(), an environment step, the resume). Inside a critical section,
 * an invariant can be false for a short time.
 */

#include <string.h>
#include <zephyr/ztest.h>
#include <zephyr/kernel_structs.h>
#include <ksched.h>
#include <scheduler.h>
#include <timeout_q.h>
#include <wait_q.h>
#include <kthread.h>
#include <kernel_arch_interface.h>
#ifdef KERNEL_UNIT_FAKE_GROUP_scheduler
#include <fakes/scheduler.h>
#endif
#include <kernel_unit_sched_ref.h>

struct kernel_unit_sched_ref kernel_unit_sched_ref;

/* Short name of the state in this file. */
#define REF kernel_unit_sched_ref

/* The swap return value of a thread after a wait without a wake (EAGAIN). */
#define REF_EAGAIN (-EAGAIN)

/*
 * Return value of z_pend_curr() if the waiting thread never runs again. The
 * real z_pend_curr() does not return. -EAGAIN is the safe value, as for the
 * ISR refusal (KERNEL_UNIT_PEND_REFUSED).
 */
#define REF_NO_RETURN_VALUE (-EAGAIN)

static const char *check_name(unsigned int check)
{
	switch (check) {
	case KERNEL_UNIT_SCHED_REF_CUR_IS_READY:
		return "CurIsReady";
	case KERNEL_UNIT_SCHED_REF_PENDING_IS_QUEUED:
		return "PendingIsQueued";
	case KERNEL_UNIT_SCHED_REF_ARMED_ARE_PENDING:
		return "ArmedArePending";
	case KERNEL_UNIT_SCHED_REF_DEAD_IS_INERT:
		return "DeadIsInert";
	case KERNEL_UNIT_SCHED_REF_RUN_RULE_HOLDS:
		return "RunRuleHolds";
	case KERNEL_UNIT_SCHED_REF_NO_LOST_THREAD:
		return "NoLostThread";
	case KERNEL_UNIT_SCHED_REF_MISUSE:
		return "Misuse";
	case KERNEL_UNIT_SCHED_REF_NO_RETURN:
		return "NoReturn";
	default:
		return "?";
	}
}

/*
 * A check failed. Record it. If the test does not expect it, print it and
 * fail the test.
 */
static void report(unsigned int check, const char *what)
{
	REF.found |= check;
	if ((REF.expected & check) == 0U) {
		TC_PRINT("sched_ref: check %s failed: %s\n", check_name(check), what);
		ztest_test_fail();
	}
}

static void trace(const char *op, const char *c_function, _wait_q_t *wait_q,
		  struct k_thread *thread, int value)
{
	if (REF.trace != NULL) {
		bool isr = kernel_unit_context_is_isr();
		struct kernel_unit_sched_ref_record rec = {
			.op = op,
			.c_function = c_function,
			.actor = isr ? NULL : _current,
			.isr = isr,
			.wait_q = wait_q,
			.thread = thread,
			.value = value,
		};

		REF.trace(&rec);
	}
}

struct kernel_unit_sched_ref_thread *kernel_unit_sched_ref_of(const struct k_thread *thread)
{
	for (size_t i = 0; i < REF.n_threads; i++) {
		if (REF.threads[i].thread == thread) {
			return &REF.threads[i];
		}
	}

	return NULL;
}

/* Return the fake state of a thread. An unknown thread is a misuse. */
static struct kernel_unit_sched_ref_thread *known(const struct k_thread *thread, const char *where)
{
	struct kernel_unit_sched_ref_thread *t = kernel_unit_sched_ref_of(thread);

	if (t == NULL) {
		report(KERNEL_UNIT_SCHED_REF_MISUSE, where);
	}

	return t;
}

uint32_t kernel_unit_sched_ref_bit(const struct k_thread *thread)
{
	if (thread == NULL) {
		return KERNEL_UNIT_SCHED_REF_IDLE;
	}
	for (size_t i = 0; i < REF.n_threads; i++) {
		if (REF.threads[i].thread == thread) {
			return BIT(i);
		}
	}

	return 0U;
}

/*
 * Keep the timeout state in base.timeout, because the real copy of
 * z_is_inactive_timeout() reads it.
 */
static void mirror_timeout(struct kernel_unit_sched_ref_thread *t)
{
#ifdef CONFIG_SYS_CLOCK_EXISTS
#if defined(CONFIG_TIMEOUT_BACKEND_MINHEAP)
	t->thread->base.timeout.heap_handle.idx = t->armed ? 1U : 0U;
#else
	sys_dnode_t *node = &t->thread->base.timeout.node;

	node->next = t->armed ? node : NULL;
	node->prev = t->armed ? node : NULL;
#endif
#else
	ARG_UNUSED(t);
#endif
}

/* Set the state, and keep the bits of base.thread_state that the real copies read. */
static void set_state(struct kernel_unit_sched_ref_thread *t, enum kernel_unit_sched_ref_tstate s)
{
	uint8_t *bits = &t->thread->base.thread_state;

	t->state = s;
	*bits &= ~(_THREAD_PENDING | _THREAD_DEAD);
	if (s == KERNEL_UNIT_SCHED_REF_PENDING) {
		*bits |= _THREAD_PENDING;
	} else if (s == KERNEL_UNIT_SCHED_REF_DEAD) {
		*bits |= _THREAD_DEAD;
	} else if (s == KERNEL_UNIT_SCHED_REF_READY) {
		t->ready_seq = REF.next_ready++;
	} else {
		/* UNPENDED: no bit, as after unpend_thread_no_timeout() */
	}
}

/* The current thread of the fake (cur[c1]), or NULL for the idle thread. */
static struct kernel_unit_sched_ref_thread *cur(void)
{
	return kernel_unit_sched_ref_of(_current);
}

static void set_cur(struct kernel_unit_sched_ref_thread *t)
{
	_kernel.cpus[0].current = (t != NULL) ? t->thread : NULL;
}

/*
 * Cooperative(p): a negative Zephyr priority. The contract converts with
 * ToZephyr(p) == -p, so the Zephyr priority is the base.prio of the code.
 */
static bool cooperative(const struct kernel_unit_sched_ref_thread *t)
{
	return t->thread->base.prio < 0;
}

/*
 * WaitQueue!Before(a, b): a comes before b. Higher priority first (a lower
 * Zephyr number), then the order of arrival.
 */
static bool before(const struct kernel_unit_sched_ref_thread *a,
		   const struct kernel_unit_sched_ref_thread *b)
{
	if (a->thread->base.prio != b->thread->base.prio) {
		return a->thread->base.prio < b->thread->base.prio;
	}

	return a->stamp < b->stamp;
}

/* WaitQueue!Best(o): the head of the wait queue of o, or NULL if W(o) = {}. */
static struct kernel_unit_sched_ref_thread *best(_wait_q_t *wait_q)
{
	struct kernel_unit_sched_ref_thread *b = NULL;

	for (size_t i = 0; i < REF.n_threads; i++) {
		struct kernel_unit_sched_ref_thread *t = &REF.threads[i];

		if ((t->state == KERNEL_UNIT_SCHED_REF_PENDING) &&
		    (t->thread->base.pended_on == wait_q) && ((b == NULL) || before(t, b))) {
			b = t;
		}
	}

	return b;
}

size_t kernel_unit_sched_ref_waiters(_wait_q_t *wait_q, struct k_thread **out, size_t max)
{
	struct kernel_unit_sched_ref_thread *sorted[KERNEL_UNIT_SCHED_REF_MAX_THREADS];
	size_t n = 0;

	/* WaitQueue!Ordered(o): insertion sort by Before. */
	for (size_t i = 0; i < REF.n_threads; i++) {
		struct kernel_unit_sched_ref_thread *t = &REF.threads[i];
		size_t pos = n;

		if ((t->state != KERNEL_UNIT_SCHED_REF_PENDING) ||
		    (t->thread->base.pended_on != wait_q)) {
			continue;
		}
		while ((pos > 0U) && before(t, sorted[pos - 1U])) {
			sorted[pos] = sorted[pos - 1U];
			pos--;
		}
		sorted[pos] = t;
		n++;
	}
	for (size_t i = 0; (i < n) && (i < max); i++) {
		out[i] = sorted[i]->thread;
	}

	return n;
}

/* Thread t leaves its wait queue (WaitQueue!Remove). The state is set by the caller. */
static void leave_wait_queue(struct kernel_unit_sched_ref_thread *t)
{
	t->thread->base.pended_on = NULL;
	t->stamp = 0U;
}

/* Timeout!Cancel(t). */
static void cancel_timeout(struct kernel_unit_sched_ref_thread *t)
{
	t->armed = false;
	mirror_timeout(t);
}

/*
 * Timeout!InsertAny(t), with a deadline on the fake clock. A relative timeout
 * expires ticks after now. An absolute timeout (K_TIMEOUT_ABS_TICKS(), a
 * negative encoding) expires at its tick, but at least one tick after now,
 * as z_add_timeout() does (dticks = max(1, Z_TICK_ABS(ticks) - curr_tick)).
 * The fake clock has no round-up of a relative timeout by one tick.
 */
static void arm_timeout(struct kernel_unit_sched_ref_thread *t, k_timeout_t timeout)
{
	k_ticks_t ticks = timeout.ticks;

	t->armed = true;
	if (Z_IS_TIMEOUT_RELATIVE(timeout)) {
		t->deadline = REF.clock + ticks;
	} else {
		t->deadline = MAX((int64_t)Z_TICK_ABS(ticks), REF.clock + 1);
	}
	t->armed_seq = REF.next_armed++;
	mirror_timeout(t);
}

/* Timeout!First: the armed timeout with the earliest deadline, or NULL. */
static struct kernel_unit_sched_ref_thread *first_armed(void)
{
	struct kernel_unit_sched_ref_thread *f = NULL;

	for (size_t i = 0; i < REF.n_threads; i++) {
		struct kernel_unit_sched_ref_thread *t = &REF.threads[i];

		if (t->armed && ((f == NULL) || (t->deadline < f->deadline) ||
				 ((t->deadline == f->deadline) && (t->armed_seq < f->armed_seq)))) {
			f = t;
		}
	}

	return f;
}

/*
 * Choices(c, ts, pr, cu) for one CPU: Candidates(c) is each ready thread.
 *
 * Difference from the contract (finding R15 of the review): after
 * z_thread_prio_set() of a ready thread, sched.c calls update_cache(1). The
 * next selection is then runq_best(): the first thread of the highest
 * priority in run queue order. A cooperative current thread does not keep
 * the CPU, and the current thread does not win a tie. The fake follows the
 * code until the next selection (REF.preempt_ok).
 */
uint32_t kernel_unit_sched_ref_choices(void)
{
	struct kernel_unit_sched_ref_thread *u = REF.preempt_ok ? NULL : cur();
	uint32_t top = 0U;
	int top_prio = 0;
	bool any = false;

	if ((u != NULL) && (u->state == KERNEL_UNIT_SCHED_REF_READY) && cooperative(u)) {
		return kernel_unit_sched_ref_bit(u->thread);
	}
	for (size_t i = 0; i < REF.n_threads; i++) {
		const struct kernel_unit_sched_ref_thread *t = &REF.threads[i];

		if (t->state != KERNEL_UNIT_SCHED_REF_READY) {
			continue;
		}
		if (!any || (t->thread->base.prio < top_prio)) {
			top = 0U;
			top_prio = t->thread->base.prio;
			any = true;
		}
		if (t->thread->base.prio == top_prio) {
			top |= BIT(i);
		}
	}
	if (!any) {
		return KERNEL_UNIT_SCHED_REF_IDLE;
	}
	if ((u != NULL) && ((top & kernel_unit_sched_ref_bit(u->thread)) != 0U)) {
		return kernel_unit_sched_ref_bit(u->thread);
	}

	return top;
}

/*
 * Select(c1): the CPU selects a thread of Choices. If the rule permits more
 * than one thread, the fake selects the first thread in run queue order
 * (ready_seq), as the code does. The contract permits any of them. The
 * selection ends the effect of z_thread_prio_set() on the rule.
 */
static void select_thread(void)
{
	uint32_t choices = kernel_unit_sched_ref_choices();
	struct kernel_unit_sched_ref_thread *next = NULL;

	REF.preempt_ok = false;
	if (choices == KERNEL_UNIT_SCHED_REF_IDLE) {
		set_cur(NULL);
		return;
	}
	for (size_t i = 0; i < REF.n_threads; i++) {
		struct kernel_unit_sched_ref_thread *t = &REF.threads[i];

		if (((choices & BIT(i)) != 0U) &&
		    ((next == NULL) || (t->ready_seq < next->ready_seq))) {
			next = t;
		}
	}
	set_cur(next);
}

unsigned int kernel_unit_sched_ref_check(void)
{
	unsigned int bad = 0U;
	struct kernel_unit_sched_ref_thread *c = cur();

	if ((_current != NULL) && ((c == NULL) || (c->state != KERNEL_UNIT_SCHED_REF_READY))) {
		bad |= KERNEL_UNIT_SCHED_REF_CUR_IS_READY;
	}
	for (size_t i = 0; i < REF.n_threads; i++) {
		const struct kernel_unit_sched_ref_thread *t = &REF.threads[i];
		bool pending = (t->state == KERNEL_UNIT_SCHED_REF_PENDING);

		if (t->state == KERNEL_UNIT_SCHED_REF_UNPENDED) {
			bad |= KERNEL_UNIT_SCHED_REF_NO_LOST_THREAD;
		}
		if ((pending != (t->thread->base.pended_on != NULL)) ||
		    (pending && (!t->has_ret || (t->ret != REF_EAGAIN)))) {
			bad |= KERNEL_UNIT_SCHED_REF_PENDING_IS_QUEUED;
		}
		if (t->armed && !pending) {
			bad |= KERNEL_UNIT_SCHED_REF_ARMED_ARE_PENDING;
		}
		if ((t->state == KERNEL_UNIT_SCHED_REF_DEAD) &&
		    ((t->thread->base.pended_on != NULL) || t->has_ret || (t == c))) {
			bad |= KERNEL_UNIT_SCHED_REF_DEAD_IS_INERT;
		}
	}
	if ((kernel_unit_sched_ref_choices() & kernel_unit_sched_ref_bit(_current)) == 0U) {
		bad |= KERNEL_UNIT_SCHED_REF_RUN_RULE_HOLDS;
	}

	return bad;
}

/*
 * A check point: the end of a critical section. RunRuleHolds is checked only
 * if run_rule is true: at the end of an ISR or of an environment step. Inside
 * an ISR, the selection comes only at the exit.
 */
static void check_point(bool run_rule)
{
	unsigned int bad;

	if (REF.halted) {
		return;
	}
	bad = kernel_unit_sched_ref_check();
	if (!run_rule) {
		bad &= ~KERNEL_UNIT_SCHED_REF_RUN_RULE_HOLDS;
	}
	for (unsigned int bit = 0U; bit < 8U; bit++) {
		if ((bad & BIT(bit)) != 0U) {
			report(BIT(bit), "invariant false at the end of a critical section");
		}
	}
}

void kernel_unit_sched_ref_assert_ok(void)
{
	unsigned int unexpected;

	check_point(true);
	unexpected = REF.found & ~REF.expected;
	if (unexpected != 0U) {
		TC_PRINT("sched_ref: unexpected failed checks 0x%x\n", unexpected);
		ztest_test_fail();
	}
}

void kernel_unit_sched_ref_expect(unsigned int checks)
{
	REF.expected |= checks;
}

/*
 * The preconditions of each call of an object: no panic, no stop, and
 * CanCall(a). The actor is an ISR or the thread that runs, and it does not
 * return from a wait now.
 */
static bool can_call(const char *where)
{
	struct kernel_unit_sched_ref_thread *c;

	if (kernel_unit_pend_refusal.count > 0U) {
		report(KERNEL_UNIT_SCHED_REF_MISUSE, "a scheduler call after a panic");
		return false;
	}
	if (REF.halted) {
		report(KERNEL_UNIT_SCHED_REF_MISUSE, "a scheduler call after a stop");
		return false;
	}
	if (kernel_unit_context_is_isr()) {
		return true;
	}
	c = cur();
	if ((c == NULL) || (c->state != KERNEL_UNIT_SCHED_REF_READY) || c->has_ret) {
		report(KERNEL_UNIT_SCHED_REF_MISUSE, where);
		return false;
	}

	return true;
}

/*
 * WakeSet({t}, ret, data): t stops to wait, gets ret and data, and is ready.
 * With cancel, the timeout is cancelled first, as z_unpend_first_thread_locked()
 * does.
 */
static void wake(struct kernel_unit_sched_ref_thread *t, int ret, void *data, bool cancel)
{
	leave_wait_queue(t);
	if (cancel) {
		cancel_timeout(t);
	}
	t->has_ret = true;
	t->ret = ret;
	t->thread->base.swap_data = data;
	set_state(t, KERNEL_UNIT_SCHED_REF_READY);
}

/* ThreadTimeout(c1): the first armed timeout expires. Its thread keeps -EAGAIN. */
static bool expire_first(void)
{
	struct kernel_unit_sched_ref_thread *t = first_armed();

	if (t == NULL) {
		return false;
	}
	REF.clock = t->deadline;
	cancel_timeout(t);
	if (t->state == KERNEL_UNIT_SCHED_REF_PENDING) {
		leave_wait_queue(t);
		set_state(t, KERNEL_UNIT_SCHED_REF_READY);
	}
	trace("ThreadTimeout", "z_thread_timeout", NULL, t->thread, t->ret);
	/* The exit of the timer ISR selects a thread. */
	select_thread();

	return true;
}

/*
 * Abort(a, t). The actor is the thread that runs, or an ISR if the CPU runs
 * the idle thread. A thread that aborts itself, and an ISR, select a thread.
 * A thread that aborts another thread does not reschedule.
 *
 * As halt_thread() of the code (sched.c:914), the abort calls update_cache(1)
 * for each target: the next selection has no tie rule and no cooperative
 * rule (REF.preempt_ok). After an abort of another thread by a thread, the
 * check RUN_RULE_HOLDS can fail until the next selection (finding P7-c).
 * The swap data of the target does not change (the code does not write it).
 * The fake has no join queue and no k_thread_suspend() (the same path).
 */
static void abort_thread(struct k_thread *thread)
{
	struct kernel_unit_sched_ref_thread *t = known(thread, "abort of an unknown thread");
	struct kernel_unit_sched_ref_thread *a = cur();

	if ((t == NULL) || (t->state == KERNEL_UNIT_SCHED_REF_DEAD)) {
		report(KERNEL_UNIT_SCHED_REF_MISUSE, "abort of a dead thread");
		return;
	}
	if (t->state == KERNEL_UNIT_SCHED_REF_PENDING) {
		leave_wait_queue(t);
	}
	cancel_timeout(t);
	set_state(t, KERNEL_UNIT_SCHED_REF_DEAD);
	t->has_ret = false;
	REF.preempt_ok = true;
	trace("Abort", "z_thread_abort", NULL, thread, 0);
	if ((a == NULL) || (a == t)) {
		select_thread();
	}
}

/* Run an action in ISR context. The exit of the ISR selects a thread (Release of an ISR). */
static void run_isr(kernel_unit_sched_ref_action_t action)
{
	arch_is_in_isr_Fake saved = arch_is_in_isr_fake;

	arch_is_in_isr_fake.custom_fake = NULL;
	arch_is_in_isr_fake.custom_fake_seq_len = 0;
	arch_is_in_isr_fake.return_val_seq_len = 0;
	arch_is_in_isr_fake.return_val = true;
	if (action != NULL) {
		action();
	}
	/* Keep the record of the calls, restore the behavior. */
	arch_is_in_isr_fake.custom_fake = saved.custom_fake;
	arch_is_in_isr_fake.custom_fake_seq_len = saved.custom_fake_seq_len;
	arch_is_in_isr_fake.return_val_seq_len = saved.return_val_seq_len;
	arch_is_in_isr_fake.return_val = saved.return_val;
	select_thread();
}

/* Run one environment step. */
static void run_step(const struct kernel_unit_sched_ref_step *step)
{
	REF.in_env = true;
	switch (step->kind) {
	case KERNEL_UNIT_SCHED_REF_STEP_THREAD:
		if (_current != step->thread) {
			report(KERNEL_UNIT_SCHED_REF_MISUSE,
			       "the thread of an environment step does not run");
		} else if (step->action != NULL) {
			step->action();
		}
		break;
	case KERNEL_UNIT_SCHED_REF_STEP_ISR:
		run_isr(step->action);
		break;
	case KERNEL_UNIT_SCHED_REF_STEP_TIMEOUT:
		if (!expire_first()) {
			report(KERNEL_UNIT_SCHED_REF_MISUSE,
			       "a timeout step without an armed timeout");
		}
		break;
	case KERNEL_UNIT_SCHED_REF_STEP_ABORT:
	default:
		abort_thread(step->thread);
		break;
	}
	REF.in_env = false;
	check_point(true);
}

/* The waiting thread w never runs again. The harness continues on its stack. */
static int no_return(struct kernel_unit_sched_ref_thread *w, const char *what)
{
	report(KERNEL_UNIT_SCHED_REF_NO_RETURN, what);
	REF.halted = true;
	_kernel.cpus[0].current = w->thread;

	return REF_NO_RETURN_VALUE;
}

/*
 * z_pend_curr(): PendCurr(a, o, to), then Release(a, "swap"), then the
 * environment, then Resume(a). The ISR refusal of the fake group sched comes
 * before this function: in an ISR, the fake does not call it.
 *
 * As the contract (proposal P1 of the review) and the C code, the wait does
 * not change base.swap_data: msgq and mailbox write it before the wait
 * (Scheduler!SetSwapData), and Resume does not reset it.
 */
static int ref_pend_curr(struct k_spinlock *lock, k_spinlock_key_t key, _wait_q_t *wait_q,
			 k_timeout_t timeout)
{
	struct kernel_unit_sched_ref_thread *a;
	int ret;

	ARG_UNUSED(lock);
	ARG_UNUSED(key);

	if (REF.in_env) {
		report(KERNEL_UNIT_SCHED_REF_MISUSE, "an environment action waits");
		return REF_NO_RETURN_VALUE;
	}
	if (K_TIMEOUT_EQ(timeout, K_NO_WAIT)) {
		report(KERNEL_UNIT_SCHED_REF_MISUSE, "a wait with K_NO_WAIT");
		return REF_NO_RETURN_VALUE;
	}
	if (!can_call("z_pend_curr() of a thread that does not run")) {
		return REF_NO_RETURN_VALUE;
	}
	a = cur();

	/* PendCurr(a, o, to) */
	a->thread->base.pended_on = wait_q;
	a->stamp = REF.next_stamp++;
	if (!K_TIMEOUT_EQ(timeout, K_FOREVER)) {
		arm_timeout(a, timeout);
	}
	a->has_ret = true;
	a->ret = REF_EAGAIN;
	set_state(a, KERNEL_UNIT_SCHED_REF_PENDING);
	trace("PendCurr", "z_pend_curr", wait_q, a->thread, REF_EAGAIN);
	/* Release(a, "swap") */
	select_thread();
	check_point(true);

	/* The environment runs until Resume(a) is enabled: Running(a) and swapRet # NoRet. */
	while ((_current != a->thread) || !a->has_ret) {
		if (a->state == KERNEL_UNIT_SCHED_REF_DEAD) {
			return no_return(a, "the waiting thread was aborted");
		}
		if (REF.next_step < REF.n_steps) {
			run_step(&REF.steps[REF.next_step++]);
		} else if (!expire_first()) {
			/* No step left and no armed timeout: no event can end the wait. */
			return no_return(
				a, (a->state == KERNEL_UNIT_SCHED_REF_PENDING)
					   ? "the thread waits for ever (no waker, no timeout)"
					   : "the woken thread does not get the CPU");
		} else {
			check_point(true);
		}
	}

	/* Resume(a) */
	ret = a->ret;
	a->has_ret = false;
	trace("Resume", "z_pend_curr", wait_q, a->thread, ret);
	check_point(true);

	return ret;
}

/* z_sched_wake(): WakeFirst(o, ret, data). The return value is HasWaiters(o). */
static bool ref_sched_wake(_wait_q_t *wait_q, int swap_retval, void *swap_data)
{
	struct kernel_unit_sched_ref_thread *t;

	if (!can_call("z_sched_wake() of a thread that does not run")) {
		return false;
	}
	t = best(wait_q);
	trace("WakeFirst", "z_sched_wake", wait_q, (t != NULL) ? t->thread : NULL, swap_retval);
	if (t == NULL) {
		return false;
	}
	wake(t, swap_retval, swap_data, true);

	return true;
}

/*
 * z_reschedule(): Release(a, "resched"). A thread selects now. In an ISR,
 * the C code does not swap (resched() is false), and the exit of the ISR
 * selects. The fake does not read the key (finding R8 of the review). The
 * contract does (Scheduler!ReschedOk: no outer irq_lock(), finding P2-w):
 * here the fake would select only if arch_irq_unlocked(key.key) (RF-2, open).
 */
static void ref_reschedule(struct k_spinlock *lock, k_spinlock_key_t key)
{
	bool isr = kernel_unit_context_is_isr();

	ARG_UNUSED(lock);
	ARG_UNUSED(key);

	if (!can_call("z_reschedule() of a thread that does not run")) {
		return;
	}
	trace("Release", "z_reschedule", NULL, NULL, 0);
	if (!isr) {
		select_thread();
	}
	check_point(!isr);
}

/* z_unpend_first_thread_locked(): the first half of WakeFirstWith(o, F). */
static struct k_thread *ref_unpend_first_thread_locked(_wait_q_t *wait_q)
{
	struct kernel_unit_sched_ref_thread *t;

	if (!can_call("z_unpend_first_thread_locked() of a thread that does not run")) {
		return NULL;
	}
	t = best(wait_q);
	trace("WakeFirstWith", "z_unpend_first_thread_locked", wait_q,
	      (t != NULL) ? t->thread : NULL, 0);
	if (t == NULL) {
		return NULL;
	}
	leave_wait_queue(t);
	cancel_timeout(t);
	set_state(t, KERNEL_UNIT_SCHED_REF_UNPENDED);

	return t->thread;
}

/*
 * arch_thread_return_value_set(): the value F(t)[1] of WakeFirstWith, or the
 * value of a woken thread of WakeWalk.
 */
static void ref_thread_return_value_set(struct k_thread *thread, unsigned int value)
{
	struct kernel_unit_sched_ref_thread *t;

	if (!can_call("arch_thread_return_value_set() of a thread that does not run")) {
		return;
	}
	t = known(thread, "arch_thread_return_value_set() of an unknown thread");
	if (t == NULL) {
		return;
	}
	t->has_ret = true;
	t->ret = (int)value;
	trace("WakeSet", "arch_thread_return_value_set", NULL, thread, (int)value);
}

/*
 * z_sched_ready_locked(): the second half of WakeFirstWith(o, F). As
 * ready_thread() of the code: no change for a thread that is not ready to run
 * (pending or dead) or that is ready already.
 */
static void ref_sched_ready_locked(struct k_thread *thread)
{
	struct kernel_unit_sched_ref_thread *t;

	if (!can_call("z_sched_ready_locked() of a thread that does not run")) {
		return;
	}
	t = known(thread, "z_sched_ready_locked() of an unknown thread");
	if (t == NULL) {
		return;
	}
	trace("WakeFirstWith", "z_sched_ready_locked", NULL, thread, 0);
	if (t->state == KERNEL_UNIT_SCHED_REF_UNPENDED) {
		set_state(t, KERNEL_UNIT_SCHED_REF_READY);
	}
}

/*
 * z_sched_wake_thread_locked(): WakeSet({t}, ...) without the cancellation of
 * the timeout. The caller cancels it first. Otherwise the check
 * ArmedArePending fails at the next check point (mutant wake_no_cancel). As
 * the code, the fake ignores a dead thread.
 */
static void ref_sched_wake_thread_locked(struct k_thread *thread)
{
	struct kernel_unit_sched_ref_thread *t;

	if (!can_call("z_sched_wake_thread_locked() of a thread that does not run")) {
		return;
	}
	t = known(thread, "z_sched_wake_thread_locked() of an unknown thread");
	if (t == NULL) {
		return;
	}
	trace("WakeSet", "z_sched_wake_thread_locked", t->thread->base.pended_on, thread, t->ret);
	if ((t->state == KERNEL_UNIT_SCHED_REF_PENDING) ||
	    (t->state == KERNEL_UNIT_SCHED_REF_UNPENDED)) {
		leave_wait_queue(t);
		set_state(t, KERNEL_UNIT_SCHED_REF_READY);
	}
}

/* z_try_abort_thread_timeout(): Timeout!Cancel(t). One CPU: no handler is in flight. */
static int ref_try_abort_thread_timeout(struct k_thread *thread)
{
	struct kernel_unit_sched_ref_thread *t;

	if (!can_call("z_try_abort_thread_timeout() of a thread that does not run")) {
		return 0;
	}
	t = known(thread, "z_try_abort_thread_timeout() of an unknown thread");
	if (t != NULL) {
		trace("Cancel", "z_try_abort_thread_timeout", NULL, thread, 0);
		cancel_timeout(t);
	}

	return 0;
}

/*
 * z_sched_waitq_walk(): WakeWalk(o, P, Stop, D) and WaitQueue!Walked. As
 * kernel/scheduler.c: walk_func for each waiter in wait queue order until it
 * returns a value other than 0 (Stop), then post_func. The walk uses a copy
 * of the order, so that a callback can wake the thread. The wakes are the
 * calls of the callbacks.
 */
static int ref_sched_waitq_walk(_wait_q_t *wait_q, _waitq_walk_cb_t walk_func,
				_waitq_post_walk_cb_t post_func, void *data)
{
	struct k_thread *order[KERNEL_UNIT_SCHED_REF_MAX_THREADS];
	size_t n;
	int status = 0;

	if (!can_call("z_sched_waitq_walk() of a thread that does not run")) {
		return 0;
	}
	n = kernel_unit_sched_ref_waiters(wait_q, order, ARRAY_SIZE(order));
	trace("WakeWalk", "z_sched_waitq_walk", wait_q, NULL, (int)n);
	for (size_t i = 0; i < n; i++) {
		status = walk_func(order[i], data);
		if (status != 0) {
			break;
		}
	}
	if (post_func != NULL) {
		post_func(status, data);
	}

	return status;
}

/*
 * z_thread_prio_set(): PrioSet(t, p). A waiter goes to the end of the waiters
 * with the new priority (WaitQueue!Restamp). No reschedule. The return value
 * is the one of sched.c: z_is_thread_ready() of the thread.
 *
 * Difference from the contract: for a ready thread, also the current thread
 * on one CPU, sched.c does dequeue_thread() and queue_thread(). The thread
 * goes to the end of its new priority in the run queue, and update_cache(1)
 * permits a switch at the next selection (see kernel_unit_sched_ref_choices()).
 */
static bool ref_thread_prio_set(struct k_thread *thread, int prio)
{
	struct kernel_unit_sched_ref_thread *t;

	if (!can_call("z_thread_prio_set() of a thread that does not run")) {
		return false;
	}
	t = known(thread, "z_thread_prio_set() of an unknown thread");
	if (t == NULL) {
		return false;
	}
	if (t->state == KERNEL_UNIT_SCHED_REF_DEAD) {
		report(KERNEL_UNIT_SCHED_REF_MISUSE, "z_thread_prio_set() of a dead thread");
		return false;
	}
	thread->base.prio = (int8_t)prio;
	if (t->state == KERNEL_UNIT_SCHED_REF_PENDING) {
		t->stamp = REF.next_stamp++;
	} else if (t->state == KERNEL_UNIT_SCHED_REF_READY) {
		t->ready_seq = REF.next_ready++;
		REF.preempt_ok = true;
	} else {
		/* UNPENDED: not in the run queue */
	}
	trace("PrioSet", "z_thread_prio_set", NULL, thread, prio);

	return z_is_thread_ready(thread);
}

/* z_waitq_head() and z_waitq_head_locked(): the query WaitQueue!Head(o). */
static struct k_thread *ref_waitq_head(_wait_q_t *wait_q)
{
	struct kernel_unit_sched_ref_thread *t = best(wait_q);

	trace("Head", "z_waitq_head", wait_q, (t != NULL) ? t->thread : NULL, 0);

	return (t != NULL) ? t->thread : NULL;
}

/*
 * z_waitq_init(): Scheduler!WaitqInit(o). An init of a wait queue with waiters
 * is undefined behavior in the code (finding P6-u): the fake reports MISUSE.
 */
static void ref_waitq_init(_wait_q_t *wait_q)
{
	if (best(wait_q) != NULL) {
		report(KERNEL_UNIT_SCHED_REF_MISUSE, "z_waitq_init() of a wait queue with waiters");
	}
}

#ifdef KERNEL_UNIT_FAKE_GROUP_scheduler
/* k_sched_current_thread_query(): cur[CpuOf(a)]. */
static k_tid_t ref_current_thread_query(void)
{
	return _current;
}
#endif

void kernel_unit_sched_ref_install(void)
{
	REF.installed = true;
	set_cur(NULL);
	z_pend_curr_fake.custom_fake = ref_pend_curr;
	z_reschedule_fake.custom_fake = ref_reschedule;
	z_sched_wake_fake.custom_fake = ref_sched_wake;
	z_sched_ready_locked_fake.custom_fake = ref_sched_ready_locked;
	z_unpend_first_thread_locked_fake.custom_fake = ref_unpend_first_thread_locked;
	z_thread_prio_set_fake.custom_fake = ref_thread_prio_set;
	z_sched_waitq_walk_fake.custom_fake = ref_sched_waitq_walk;
	z_sched_wake_thread_locked_fake.custom_fake = ref_sched_wake_thread_locked;
	z_try_abort_thread_timeout_fake.custom_fake = ref_try_abort_thread_timeout;
	z_waitq_init_fake.custom_fake = ref_waitq_init;
	z_waitq_head_fake.custom_fake = ref_waitq_head;
	z_waitq_head_locked_fake.custom_fake = ref_waitq_head;
	arch_thread_return_value_set_fake.custom_fake = ref_thread_return_value_set;
#ifdef KERNEL_UNIT_FAKE_GROUP_scheduler
	k_sched_current_thread_query_fake.custom_fake = ref_current_thread_query;
#endif
}

void kernel_unit_sched_ref_thread(struct k_thread *thread, int prio)
{
	struct kernel_unit_sched_ref_thread *t;

	if ((REF.n_threads >= ARRAY_SIZE(REF.threads)) ||
	    (kernel_unit_sched_ref_of(thread) != NULL)) {
		report(KERNEL_UNIT_SCHED_REF_MISUSE, "too many threads, or a thread two times");
		return;
	}
	t = &REF.threads[REF.n_threads++];
	*t = (struct kernel_unit_sched_ref_thread){.thread = thread};
	thread->base.prio = (int8_t)prio;
	thread->base.thread_state = 0U;
	thread->base.pended_on = NULL;
	thread->base.swap_data = NULL;
	mirror_timeout(t);
	set_state(t, KERNEL_UNIT_SCHED_REF_READY);
}

void kernel_unit_sched_ref_set_current(struct k_thread *thread)
{
	struct kernel_unit_sched_ref_thread *t = NULL;

	if (thread != NULL) {
		t = known(thread, "set_current() of an unknown thread");
		if ((t == NULL) || (t->state != KERNEL_UNIT_SCHED_REF_READY)) {
			report(KERNEL_UNIT_SCHED_REF_MISUSE,
			       "set_current() of a thread that is not ready");
			return;
		}
	}
	set_cur(t);
}

void kernel_unit_sched_ref_wait(struct k_thread *thread, _wait_q_t *wait_q, k_timeout_t timeout)
{
	struct kernel_unit_sched_ref_thread *t = known(thread, "wait() of an unknown thread");

	if ((t == NULL) || (t->state != KERNEL_UNIT_SCHED_REF_READY) ||
	    K_TIMEOUT_EQ(timeout, K_NO_WAIT)) {
		report(KERNEL_UNIT_SCHED_REF_MISUSE, "wait() of a thread that is not ready");
		return;
	}
	thread->base.pended_on = wait_q;
	t->stamp = REF.next_stamp++;
	if (!K_TIMEOUT_EQ(timeout, K_FOREVER)) {
		arm_timeout(t, timeout);
	}
	t->has_ret = true;
	t->ret = REF_EAGAIN;
	set_state(t, KERNEL_UNIT_SCHED_REF_PENDING);
}

static void add_step(enum kernel_unit_sched_ref_step_kind kind, struct k_thread *thread,
		     kernel_unit_sched_ref_action_t action)
{
	if (REF.n_steps >= ARRAY_SIZE(REF.steps)) {
		report(KERNEL_UNIT_SCHED_REF_MISUSE, "too many environment steps");
		return;
	}
	REF.steps[REF.n_steps++] = (struct kernel_unit_sched_ref_step){
		.kind = kind, .thread = thread, .action = action};
}

void kernel_unit_sched_ref_env_thread(struct k_thread *thread,
				      kernel_unit_sched_ref_action_t action)
{
	add_step(KERNEL_UNIT_SCHED_REF_STEP_THREAD, thread, action);
}

void kernel_unit_sched_ref_env_isr(kernel_unit_sched_ref_action_t action)
{
	add_step(KERNEL_UNIT_SCHED_REF_STEP_ISR, NULL, action);
}

void kernel_unit_sched_ref_env_timeout(void)
{
	add_step(KERNEL_UNIT_SCHED_REF_STEP_TIMEOUT, NULL, NULL);
}

void kernel_unit_sched_ref_env_abort(struct k_thread *thread)
{
	add_step(KERNEL_UNIT_SCHED_REF_STEP_ABORT, thread, NULL);
}

void kernel_unit_sched_ref_run_isr(kernel_unit_sched_ref_action_t action)
{
	run_isr(action);
	check_point(true);
}

void kernel_unit_sched_ref_timeout(void)
{
	if (!expire_first()) {
		report(KERNEL_UNIT_SCHED_REF_MISUSE, "a timeout without an armed timeout");
	}
	check_point(true);
}

void kernel_unit_sched_ref_abort(struct k_thread *thread)
{
	abort_thread(thread);
	check_point(true);
}

static void sched_ref_reset(const struct ztest_unit_test *test, void *fixture)
{
	ARG_UNUSED(test);
	ARG_UNUSED(fixture);

	memset(&kernel_unit_sched_ref, 0, sizeof(kernel_unit_sched_ref));
	kernel_unit_sched_ref.next_stamp = 1U;
}

ZTEST_RULE(sched_ref_reset, sched_ref_reset, NULL);
