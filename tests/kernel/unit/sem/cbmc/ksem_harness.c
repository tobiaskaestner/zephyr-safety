/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * CBMC harness: z_impl_k_sem_give() against KSem!Give and z_impl_k_sem_take()
 * against KSem!Take, for all inputs. PREDICATE UNDER REVIEW: see
 * common/include/ksem_step_pred.h and README.rst.
 *
 * Build: run.sh. The harness includes sem.c (or a mutant, SEM_C) with the
 * compile flags and the shadow headers of the unit test
 * (tests/kernel/unit/sem). The callees of sem.c are stubs with
 * nondeterministic results within the scheduler contract
 * (spec/tla/lib/Scheduler.tla). The FFF fakes are not linked.
 *
 * spinlock.h stays real, as in the unit test. k_spin_lock() and
 * k_spin_unlock() call the stubs unit_arch_irq_lock() and
 * unit_arch_irq_unlock().
 *
 * Atomicity check. The model makes one call one step. The harness checks
 * the lock discipline that this needs, for one thread:
 *
 * - The stub of the lock gives the semaphore and the wait queue new
 *   nondeterministic values (other actors ran before the lock). Thus a
 *   read before the lock gives a wrong result, and the predicate fails.
 * - A write before the lock or after the release is a separate property.
 * - The lock is taken once, first. It is released once, last, with its key.
 *
 * Options (-D):
 * - KSEM_RUNTIME_CHECKS=1: the start state satisfies the init checks of
 *   z_impl_k_sem_init(): limit > 0 and count <= limit (model constant
 *   RuntimeChecks = TRUE, invariant CountLeLimit). 0: any count and limit.
 */

#include <zephyr/ztest.h>

#ifndef SEM_C
#define SEM_C <kernel/sem.c>
#endif
#include SEM_C

#define KSEM_CHECK(cond, msg) (__CPROVER_assert((cond), msg), (cond))
#include <ksem_step_pred.h>

#ifndef KSEM_RUNTIME_CHECKS
#define KSEM_RUNTIME_CHECKS 1
#endif

#ifdef CONFIG_POLL
#define POLL_CFG true
#else
#define POLL_CFG false
#endif

unsigned int nondet_uint(void);
int nondet_int(void);
bool nondet_bool(void);

/* Phase of the call, for the order of the calls */
enum phase {
	PH_BEFORE,
	PH_LOCKED,
	PH_RELEASED,
};

static struct k_sem *g_sem;
static struct k_sem g_entry;       /* the semaphore at the entry of the call */
static struct ksem_abs g_q;        /* only waitq_len and waitq are used: the wait queue */
static struct ksem_abs g_pre;      /* abstract state when the lock is taken */
static struct ksem_abs g_rel;      /* abstract state at the release */
static struct ksem_obs g_obs;
static enum phase g_phase;

/* Layer A contract: arguments and order of the calls */
static unsigned int g_locks;
static unsigned int g_releases;
static unsigned int g_key;
static bool g_write_before_lock;
static bool g_call_outside_cs;
static bool g_release_key_ok = true;
static bool g_release_lock_ok = true;
static bool g_wake_args_ok = true;
static bool g_poll_args_ok = true;
static bool g_pend_args_ok = true;

static struct ksem_abs abs_of(const struct k_sem *sem)
{
	struct ksem_abs a = g_q;

	a.count = sem->count;
	a.limit = sem->limit;
	return a;
}

/* Byte compare (no memcmp: its newlib prototype has no CBMC body for ILP32) */
static bool same_bytes(const void *a, const void *b, size_t n)
{
	const unsigned char *pa = a;
	const unsigned char *pb = b;

	for (size_t k = 0; k < n; k++) {
		if (pa[k] != pb[k]) {
			return false;
		}
	}
	return true;
}

static void note_call(void)
{
	if (g_phase != PH_LOCKED) {
		g_call_outside_cs = true;
	}
}

/* --- Stubs of the arch layer (k_spin_lock(), k_spin_unlock()) --- */

/* The assertion of k_sem_take() (only with CONFIG_ASSERT): any context. */
bool arch_is_in_isr(void)
{
	return nondet_bool();
}

unsigned int unit_arch_irq_lock(void)
{
	if (g_phase != PH_BEFORE) {
		g_call_outside_cs = true;
	}
	g_locks++;
	if (g_sem->count != g_entry.count || g_sem->limit != g_entry.limit) {
		g_write_before_lock = true;
	}

	/* Other actors ran before the lock: any state of the model */
	g_sem->count = nondet_uint();
	g_sem->limit = nondet_uint();
#if KSEM_RUNTIME_CHECKS
	__CPROVER_assume(g_sem->limit > 0U && g_sem->count <= g_sem->limit);
#endif
	g_q.waitq_len = nondet_uint();
	__CPROVER_assume(g_q.waitq_len <= KSEM_MAXQ);
	for (int k = 0; k < KSEM_MAXQ; k++) {
		g_q.waitq[k] = nondet_int();
	}
	/* No assumption of NoWaitWhileAvailable: Give does not need it. */

	g_pre = abs_of(g_sem);
	g_phase = PH_LOCKED;
	g_key = nondet_uint();
	return g_key;
}

static void release(enum ksem_release how)
{
	note_call();
	g_releases++;
	g_obs.release = how;
	g_rel = abs_of(g_sem);
	g_phase = PH_RELEASED;
}

void unit_arch_irq_unlock(unsigned int key)
{
	if (key != g_key) {
		g_release_key_ok = false;
	}
	release(KSEM_REL_UNLOCK);
}

/* --- Stubs of the scheduler (layer A) --- */

void z_reschedule(struct k_spinlock *lock, k_spinlock_key_t key)
{
	if (lock != &sem_lock) {
		g_release_lock_ok = false;
	}
	if ((unsigned int)key.key != g_key) {
		g_release_key_ok = false;
	}
	release(KSEM_REL_RESCHED);
}

/* WakeFirst(o, ret, data): the first waiter leaves the queue. FALSE if empty. */
bool z_sched_wake(_wait_q_t *wait_q, int swap_retval, void *swap_data)
{
	bool woke = false;

	note_call();
	if (wait_q != &g_sem->wait_q || swap_data != NULL) {
		g_wake_args_ok = false;
	}
	if (g_q.waitq_len > 0U) {
		if (g_obs.n_woken < KSEM_MAXCALLS) {
			g_obs.woken[g_obs.n_woken] = g_q.waitq[0];
			g_obs.woken_swap_ret[g_obs.n_woken] = swap_retval;
		}
		g_obs.n_woken++;
		for (int k = 0; k + 1 < KSEM_MAXQ; k++) {
			g_q.waitq[k] = g_q.waitq[k + 1];
		}
		g_q.waitq_len--;
		woke = true;
	}
	if (g_obs.n_wakes < KSEM_MAXCALLS) {
		g_obs.wakes[g_obs.n_wakes] = woke;
	}
	g_obs.n_wakes++;
	return woke;
}

/* Poll events: a polling thread can become ready (free result). */
bool z_handle_obj_poll_events(sys_dlist_t *events, uint32_t state)
{
	bool ready = nondet_bool();

	note_call();
#ifdef CONFIG_POLL
	if (events != &g_sem->poll_events || state != K_POLL_STATE_SEM_AVAILABLE) {
		g_poll_args_ok = false;
	}
#endif
	g_obs.n_polls++;
	g_obs.poll = g_sem->count;
	g_obs.poll_ready = ready;
	return ready;
}

/* PendCurr(a, o, to): the release of a take that waits. The return value is free. */
int z_pend_curr(struct k_spinlock *lock, k_spinlock_key_t key, _wait_q_t *wait_q,
		k_timeout_t timeout)
{
	int ret = nondet_int();

	if (lock != &sem_lock || wait_q != &g_sem->wait_q) {
		g_pend_args_ok = false;
	}
	if ((unsigned int)key.key != g_key) {
		g_release_key_ok = false;
	}
	g_obs.n_pends++;
	g_obs.pend_timeout = K_TIMEOUT_EQ(timeout, K_FOREVER) ? KSEM_TO_FOREVER
			   : K_TIMEOUT_EQ(timeout, K_NO_WAIT) ? KSEM_TO_NO_WAIT
							      : KSEM_TO_TICKS;
	g_obs.pend_ret = ret;
	release(KSEM_REL_PEND);
	return ret;
}

/* --- The harnesses --- */

/* The lock discipline of one call (layer A, atomicity of the step). */
static void check_lock_discipline(const struct k_sem *sem)
{
	struct ksem_abs post = abs_of(sem);

	__CPROVER_assert(g_locks == 1U, "CS: sem_lock is locked exactly once");
	__CPROVER_assert(g_releases == 1U, "CS: sem_lock is released exactly once");
	__CPROVER_assert(!g_call_outside_cs, "CS: each callee is called under sem_lock");
	__CPROVER_assert(g_release_key_ok, "CS: the release uses the key of the lock");
	__CPROVER_assert(g_release_lock_ok, "CS: z_reschedule() gets sem_lock");
	__CPROVER_assert(!g_write_before_lock, "CS: no write to count/limit before the lock");
	__CPROVER_assert(post.count == g_rel.count && post.limit == g_rel.limit,
			 "CS: no write to count/limit after the release");
	__CPROVER_assert(same_bytes(&sem->wait_q, &g_entry.wait_q, sizeof(sem->wait_q)),
			 "Frame: sem->wait_q unchanged (the scheduler owns it)");
#ifdef CONFIG_POLL
	__CPROVER_assert(same_bytes(&sem->poll_events, &g_entry.poll_events,
				    sizeof(sem->poll_events)),
			 "Frame: sem->poll_events unchanged");
#endif
}

void harness_give(void)
{
	struct k_sem sem; /* nondeterministic contents */

	g_sem = &sem;
	g_entry = sem;
	g_phase = PH_BEFORE;

	z_impl_k_sem_give(&sem);

	check_lock_discipline(&sem);
	/* Arguments of the callees (layer A) */
	__CPROVER_assert(g_wake_args_ok, "Args: z_sched_wake(&sem->wait_q, _, NULL)");
	__CPROVER_assert(g_poll_args_ok,
			 "Args: z_handle_obj_poll_events(&sem->poll_events, SEM_AVAILABLE)");
	__CPROVER_assert(g_obs.n_pends == 0U, "Give: no z_pend_curr()");

	/* The step of the model: pre at the lock, post at the release */
	(void)ksem_give_step(&g_pre, &g_rel, &g_obs, POLL_CFG);

#ifdef KSEM_REACH
	/*
	 * Vacuity probes: each one must FAIL. A failure shows that CBMC found
	 * an execution of this case, so the properties above are not true only
	 * because the case is unreachable.
	 */
	__CPROVER_assert(!(g_pre.waitq_len == KSEM_MAXQ), "Reach: wake with a full queue");
	__CPROVER_assert(!(g_pre.waitq_len == 0U && g_pre.count < g_pre.limit &&
			   g_obs.release == KSEM_REL_UNLOCK),
			 "Reach: increment, unlock");
	__CPROVER_assert(!(g_pre.waitq_len == 0U && g_pre.count < g_pre.limit &&
			   g_obs.release == KSEM_REL_RESCHED),
			 "Reach: increment, resched (poll ready)");
	__CPROVER_assert(!(g_pre.waitq_len == 0U && g_pre.count == g_pre.limit &&
			   g_pre.count == KSEM_UMAX),
			 "Reach: no waiter, count = limit = UMax");
	__CPROVER_assert(!(g_pre.waitq_len == 0U && g_pre.count > g_pre.limit),
			 "Reach: no waiter, count > limit");
	__CPROVER_assert(!(g_pre.waitq_len == 0U && g_pre.limit == 0U), "Reach: limit 0");
	__CPROVER_assert(!(g_pre.waitq_len > 0U && g_pre.count > 0U),
			 "Reach: waiter and count > 0");
#endif
}

void harness_take(void)
{
	struct k_sem sem; /* nondeterministic contents */
	k_timeout_t timeout;
	enum ksem_timeout to;
	int ret;

	timeout.ticks = nondet_int();
	to = K_TIMEOUT_EQ(timeout, K_FOREVER) ? KSEM_TO_FOREVER
	     : K_TIMEOUT_EQ(timeout, K_NO_WAIT) ? KSEM_TO_NO_WAIT
						: KSEM_TO_TICKS;
	g_sem = &sem;
	g_entry = sem;
	g_phase = PH_BEFORE;

	ret = z_impl_k_sem_take(&sem, timeout);
	g_obs.ret = ret;

	check_lock_discipline(&sem);
	__CPROVER_assert(g_pend_args_ok, "Args: z_pend_curr(&sem_lock, key, &sem->wait_q, _)");

	(void)ksem_take_step(&g_pre, &g_rel, &g_obs, to);

#ifdef KSEM_REACH
	__CPROVER_assert(!(g_pre.count > 0U), "Reach: take available");
	__CPROVER_assert(!(g_pre.count == 0U && to == KSEM_TO_NO_WAIT), "Reach: take busy");
	__CPROVER_assert(!(g_pre.count == 0U && to == KSEM_TO_FOREVER), "Reach: wait forever");
	__CPROVER_assert(!(g_pre.count == 0U && to == KSEM_TO_TICKS), "Reach: wait with ticks");
	__CPROVER_assert(!(g_pre.count == KSEM_UMAX), "Reach: take at UMax");
#endif
}
