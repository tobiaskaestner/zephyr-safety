/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * PREDICATE UNDER REVIEW. The predicates are a hand translation of the
 * actions of spec/tla/objects/KSem.tla. A person must review each conjunct
 * against the action before a result of the CBMC harness is evidence
 * (tests/kernel/unit/sem/cbmc/README.rst).
 *
 * KSem!Give and KSem!Take as C predicates over the abstract state before
 * the call (pre), the abstract state at the release of sem_lock (post) and
 * the observation of the call (obs). The header has no CBMC or ztest code.
 * The includer defines KSEM_CHECK():
 *
 * - CBMC harness (tests/kernel/unit/sem/cbmc/): one property for each
 *   conjunct (__CPROVER_assert).
 * - A unit test: a zassert, or a plain bool.
 *
 * Sources: objects/KSem.tla, Give(o, a) = Waitable!Give with SemSettle,
 * and Take(o, a, to) = Waitable!Take with SemAvail, SemConsume and EBUSY,
 * with TakeReturn(t) for the value of a take that waited. First written for
 * the proof of concept of the workspace notes (tla/KSem.tla, the same
 * semantics of give and take).
 *
 * Mapping of the TLA+ variables:
 *
 * - count, limit: sem->count, sem->limit (r[o].count, r[o].limit).
 * - the wait queue of o (Scheduler!WQ!Ordered(o)): the wait queue of the
 *   scheduler stub (the C code of sem.c does not see it). Bounded to
 *   KSEM_MAXQ threads.
 * - the z_sched_wake() calls of obs.calls: obs.wakes, their results in
 *   order; obs.woken, the threads that z_sched_wake() made ready.
 * - swapRet'[t] = OK: the swap_retval argument of the z_sched_wake() call
 *   that woke t.
 * - the z_handle_obj_poll_events() call of obs.calls: obs.poll, the count
 *   at the call; \E ready \in PollResults(Poll): its return value. Without
 *   CONFIG_POLL, sem.c does not call it, and ready is FALSE.
 * - the release (the last call of obs.calls): z_reschedule() ("resched"),
 *   k_spin_unlock() ("unlock") or z_pend_curr() ("pend").
 * - obs.ret: the return value of z_impl_k_sem_take(). For a take that
 *   waits, TakeReturn gives the swap return value of the wait unchanged:
 *   the return value of z_pend_curr().
 *
 * Not in the predicates (ghost or thread state of the model, not in struct
 * k_sem): r[o].init, CanCall(a), the thread state, the timeouts, tokens,
 * req.
 */

#ifndef KSEM_STEP_PRED_H_
#define KSEM_STEP_PRED_H_

#include <limits.h>
#include <stdbool.h>

#ifndef KSEM_CHECK
#define KSEM_CHECK(cond, msg) (cond)
#endif

/** Bound of the abstract wait queue. */
#define KSEM_MAXQ 3
/** Bound of the recorded calls of one kind. */
#define KSEM_MAXCALLS 4

/** UMax of the model: the largest value of unsigned int. */
#define KSEM_UMAX UINT_MAX

/** OK of the model (swap return value of a woken thread). */
#define KSEM_OK 0

/** Abstract state of one semaphore (the TLA+ variables count, limit, waitq). */
struct ksem_abs {
	unsigned int count;
	unsigned int limit;
	unsigned int waitq_len;
	int waitq[KSEM_MAXQ];
};

/** Value of obs.release. */
enum ksem_release {
	KSEM_REL_NONE,
	KSEM_REL_UNLOCK,
	KSEM_REL_RESCHED,
	KSEM_REL_PEND,
};

/** The timeout of a take (Timeouts of KSem). */
enum ksem_timeout {
	KSEM_TO_NO_WAIT,
	KSEM_TO_FOREVER,
	KSEM_TO_TICKS,
};

/** -EBUSY of the model. */
#define KSEM_EBUSY (-16)

/** Observation of one call (the TLA+ variable obs, plus the arguments). */
struct ksem_obs {
	/* obs.wakes */
	unsigned int n_wakes;
	bool wakes[KSEM_MAXCALLS];
	/* obs.woken, with the swap return value that each woken thread got */
	unsigned int n_woken;
	int woken[KSEM_MAXCALLS];
	int woken_swap_ret[KSEM_MAXCALLS];
	/* obs.poll: number of calls, count at the last call, its result */
	unsigned int n_polls;
	unsigned int poll;
	bool poll_ready;
	/* obs.release */
	enum ksem_release release;
	/* take: the z_pend_curr() calls, the timeout of the last one, its return value */
	unsigned int n_pends;
	enum ksem_timeout pend_timeout;
	int pend_ret;
	/* take: obs.ret, the return value of z_impl_k_sem_take() */
	int ret;
};

/* Inc(c) of the model: unsigned increment with wrap. */
static inline unsigned int ksem_inc(unsigned int c)
{
	return (c == KSEM_UMAX) ? 0U : c + 1U;
}

/* waitq' = Tail(waitq) */
static inline bool ksem_is_tail(const struct ksem_abs *pre, const struct ksem_abs *post)
{
	if (post->waitq_len + 1U != pre->waitq_len) {
		return false;
	}
	for (unsigned int k = 0U; k < post->waitq_len && k + 1U < KSEM_MAXQ; k++) {
		if (post->waitq[k] != pre->waitq[k + 1U]) {
			return false;
		}
	}
	return true;
}

/* UNCHANGED waitq */
static inline bool ksem_same_waitq(const struct ksem_abs *pre, const struct ksem_abs *post)
{
	if (post->waitq_len != pre->waitq_len) {
		return false;
	}
	for (unsigned int k = 0U; k < pre->waitq_len && k < KSEM_MAXQ; k++) {
		if (post->waitq[k] != pre->waitq[k]) {
			return false;
		}
	}
	return true;
}

/**
 * KSem!Give(o, a), without the guards r[o].init and CanCall(a).
 *
 * @param poll_cfg The constant Poll (CONFIG_POLL).
 * @return true if the step (pre, post, obs) is a Give step of the model.
 */
static inline bool ksem_give_step(const struct ksem_abs *pre, const struct ksem_abs *post,
				  const struct ksem_obs *obs, bool poll_cfg)
{
	bool ok = true;

	if (pre->waitq_len > 0U) {
		/* IF waitq # <<>> THEN LET t == Head(waitq) IN */
		ok &= KSEM_CHECK(ksem_is_tail(pre, post), "Give/wake: waitq' = Tail(waitq)");
		ok &= KSEM_CHECK(obs->n_wakes == 1U && obs->wakes[0],
				 "Give/wake: obs.wakes = <<TRUE>>");
		ok &= KSEM_CHECK(obs->n_woken == 1U && obs->woken[0] == pre->waitq[0],
				 "Give/wake: obs.woken = {Head(waitq)}");
		ok &= KSEM_CHECK(obs->n_woken == 1U && obs->woken_swap_ret[0] == KSEM_OK,
				 "Give/wake: swapRet'[t] = OK");
		ok &= KSEM_CHECK(obs->n_polls == 0U, "Give/wake: obs.poll = NoPoll");
		ok &= KSEM_CHECK(obs->release == KSEM_REL_RESCHED,
				 "Give/wake: obs.release = resched");
		ok &= KSEM_CHECK(post->count == pre->count, "Give/wake: UNCHANGED count");
		ok &= KSEM_CHECK(post->limit == pre->limit, "Give/wake: UNCHANGED limit");
	} else {
		/* ELSE LET newCount == IF count # limit THEN Inc(count) ELSE count IN */
		unsigned int new_count =
			(pre->count != pre->limit) ? ksem_inc(pre->count) : pre->count;
		/* \E ready \in PollReady (PollReady = {FALSE} without Poll) */
		bool ready = poll_cfg && obs->poll_ready;

		ok &= KSEM_CHECK(post->count == new_count, "Give/count: count' = newCount");
		ok &= KSEM_CHECK(obs->n_wakes == 1U && !obs->wakes[0],
				 "Give/count: obs.wakes = <<FALSE>>");
		ok &= KSEM_CHECK(obs->n_woken == 0U, "Give/count: obs.woken = {}");
		if (poll_cfg) {
			ok &= KSEM_CHECK(obs->n_polls == 1U && obs->poll == new_count,
					 "Give/count: obs.poll = newCount");
		} else {
			ok &= KSEM_CHECK(obs->n_polls == 0U, "Give/count: obs.poll = NoPoll");
		}
		ok &= KSEM_CHECK(obs->release == (ready ? KSEM_REL_RESCHED : KSEM_REL_UNLOCK),
				 "Give/count: obs.release = IF ready THEN resched ELSE unlock");
		ok &= KSEM_CHECK(post->limit == pre->limit, "Give/count: UNCHANGED limit");
		ok &= KSEM_CHECK(ksem_same_waitq(pre, post), "Give/count: UNCHANGED waitq");
	}

	return ok;
}


/**
 * KSem!Take(o, a, to), without the guards r[o].init and CanCall(a), and
 * with TakeReturn for the return value after a wait.
 *
 * @param to The timeout of the call.
 * @return true if the step (pre, post, obs) is a Take step of the model.
 */
static inline bool ksem_take_step(const struct ksem_abs *pre, const struct ksem_abs *post,
				  const struct ksem_obs *obs, enum ksem_timeout to)
{
	bool ok = true;

	ok &= KSEM_CHECK(post->limit == pre->limit, "Take: UNCHANGED limit");
	ok &= KSEM_CHECK(obs->n_wakes == 0U && obs->n_polls == 0U,
			 "Take: no z_sched_wake(), no z_handle_obj_poll_events()");
	if (pre->count > 0U) {
		/* IF SemAvail(x): count' = count - 1, release unlock, ret OK */
		ok &= KSEM_CHECK(post->count == pre->count - 1U, "Take/avail: count' = count - 1");
		ok &= KSEM_CHECK(obs->release == KSEM_REL_UNLOCK && obs->n_pends == 0U,
				 "Take/avail: obs.release = unlock");
		ok &= KSEM_CHECK(obs->ret == KSEM_OK, "Take/avail: obs.ret = OK");
	} else if (to == KSEM_TO_NO_WAIT) {
		/* ELSE IF to = NO_WAIT: no change, release unlock, ret EBUSY */
		ok &= KSEM_CHECK(post->count == pre->count, "Take/busy: UNCHANGED count");
		ok &= KSEM_CHECK(obs->release == KSEM_REL_UNLOCK && obs->n_pends == 0U,
				 "Take/busy: obs.release = unlock");
		ok &= KSEM_CHECK(obs->ret == KSEM_EBUSY, "Take/busy: obs.ret = EBUSY");
	} else {
		/* ELSE PendCurr(a, o, to): the release is z_pend_curr() with to */
		ok &= KSEM_CHECK(post->count == pre->count, "Take/wait: UNCHANGED count");
		ok &= KSEM_CHECK(obs->release == KSEM_REL_PEND && obs->n_pends == 1U,
				 "Take/wait: obs.release = pend");
		ok &= KSEM_CHECK(obs->pend_timeout == to, "Take/wait: the timeout of z_pend_curr()");
		/* TakeReturn: obs.ret = swapRet[t], the value of z_pend_curr() */
		ok &= KSEM_CHECK(obs->ret == obs->pend_ret, "Take/return: obs.ret = swapRet");
	}

	return ok;
}

#endif /* KSEM_STEP_PRED_H_ */
