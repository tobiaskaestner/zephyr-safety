-------------------------------- MODULE KSem --------------------------------
(***************************************************************************)
(* Design specification of the Zephyr semaphore, kernel/sem.c.             *)
(*                                                                         *)
(* Abstraction level: the level of the unit tests in                       *)
(* safety/tests/kernel/unit/sem/src/test_sem.c. The spec has one semaphore *)
(* object (count, limit, wait queue, poll signal) and the actors that use  *)
(* it: threads and one ISR.                                                *)
(*                                                                         *)
(* Atomicity: sem.c has one spinlock, sem_lock, for all semaphores.        *)
(* k_sem_give(), k_sem_take() and k_sem_reset() lock it before they read   *)
(* the count or use the wait queue, and release it once as their last      *)
(* call (k_spin_unlock(), z_reschedule() or z_pend_curr()). On one CPU,    *)
(* the lock also locks the interrupts. Thus each call is one atomic step   *)
(* of the spec. A wait is two steps: the take that adds the thread to the  *)
(* wait queue (z_pend_curr() does the add and the release in one step),    *)
(* and a later step in which the thread runs again and returns the value   *)
(* that the waker set (swap return value). A timeout is a separate step of *)
(* the timer ISR. k_sem_init() takes no lock. The spec makes it atomic     *)
(* too, which is correct only if no other actor uses the semaphore at the  *)
(* same time (see the constant ReInit).                                    *)
(*                                                                         *)
(* Each step writes the variable obs: the observation of the step, in the  *)
(* terms of the unit tests (the results of the calls into the fakes, the   *)
(* release of sem_lock, the return value). The trace spec KSemTrace.tla    *)
(* compares obs with the events that a unit test records.                  *)
(***************************************************************************)
EXTENDS Integers, Sequences, FiniteSets, TLC

CONSTANTS
    Threads,        \* the thread IDs (model values)
    Isr,            \* the ISR actor (model value)
    Prio,           \* [Threads -> Int]: smaller value = higher priority, as in Zephyr
    InitArgs,       \* set of <<initial_count, limit>> that k_sem_init() can get
    UMax,           \* the largest value of the unsigned count (UINT_MAX, scaled down)
    RuntimeChecks,  \* TRUE: CONFIG_RUNTIME_ERROR_CHECKS. FALSE: CONFIG_NO_RUNTIME_CHECKS
    Poll,           \* CONFIG_POLL
    ReInit,         \* TRUE: k_sem_init() can occur on a semaphore in use
                    \* (z_vrfy_k_sem_init() accepts _OBJ_INIT_ANY, design observation 9)
    PendAtomic      \* TRUE: as in sem.c. FALSE: a mutant that releases
                    \* sem_lock before the thread is in the wait queue

ASSUME Isr \notin Threads
ASSUME Prio \in [Threads -> Int]
ASSUME InitArgs \subseteq (0..UMax) \X (0..UMax)
ASSUME {RuntimeChecks, Poll, ReInit, PendAtomic} \subseteq BOOLEAN

Actors == Threads \cup {Isr}

\* Return values, with the values of the C error codes
OK     == 0
EAGAIN == -11
EBUSY  == -16
EINVAL == -22
NoRet  == 1         \* "no return value" (the call does not return now)

NoPoll == -1        \* z_handle_obj_poll_events() was not called

Timeouts == {"NO_WAIT", "FOREVER", "TICKS"}   \* TICKS: a finite timeout

\* Observation of the step "nothing happened yet"
NoObs == [actor   |-> "none",
          op      |-> "none",
          timeout |-> "none",
          args    |-> <<>>,
          wakes   |-> <<>>,      \* return values of the z_sched_wake() calls, in order
          woken   |-> {},        \* the threads that the step made ready
          poll    |-> NoPoll,    \* count at the call of z_handle_obj_poll_events()
          release |-> "none",    \* "unlock", "resched", "pend" or "none"
          ret     |-> NoRet]

VARIABLES
    initialized,    \* k_sem_init() returned 0 one time
    count,          \* sem->count
    limit,          \* sem->limit
    waitq,          \* sem->wait_q, as a sequence: Head is the next thread to wake
    pc,             \* [Threads -> {"idle", "pending", "waiting", "woken"}]
    tmo,            \* the timeout of a waiting thread
    swapRet,        \* the value that the k_sem_take() of a woken thread returns
    tokens,         \* ghost: tokens that the API made available and not yet taken
    obs             \* observation of the last step

vars == <<initialized, count, limit, waitq, pc, tmo, swapRet, tokens, obs>>

-----------------------------------------------------------------------------
(* Helpers *)

Range(s) == {s[k] : k \in DOMAIN s}

Min(S) == CHOOSE m \in S : \A n \in S : m <= n

\* Unsigned increment of the count, with wrap (``count += 1U``).
Inc(c) == IF c = UMax THEN 0 ELSE c + 1

\* The wait queue is ordered by priority. A thread goes after all threads
\* with the same or a higher priority (FIFO for equal priorities).
Enqueue(q, t) ==
    LET later == {k \in DOMAIN q : Prio[q[k]] > Prio[t]}
        pos   == IF later = {} THEN Len(q) + 1 ELSE Min(later)
    IN  SubSeq(q, 1, pos - 1) \o <<t>> \o SubSeq(q, pos, Len(q))

\* An ISR can always run. A thread can call the API only if it does not wait.
CanCall(a) == IF a = Isr THEN TRUE ELSE pc[a] = "idle"

\* z_handle_obj_poll_events() returns TRUE if a polling thread became ready.
\* The spec does not model the polling threads, so the result is free.
PollReady == IF Poll THEN BOOLEAN ELSE {FALSE}

\* Woken threads that will return 0: each one holds one token.
Inflight == Cardinality({t \in Threads : pc[t] = "woken" /\ swapRet[t] = OK})

-----------------------------------------------------------------------------
(* Initial state: the semaphore memory is not initialized. *)

Init ==
    /\ initialized = FALSE
    /\ count = 0
    /\ limit = 0
    /\ waitq = <<>>
    /\ pc = [t \in Threads |-> "idle"]
    /\ tmo = [t \in Threads |-> "none"]
    /\ swapRet = [t \in Threads |-> NoRet]
    /\ tokens = 0
    /\ obs = NoObs

-----------------------------------------------------------------------------
(* Actions. Each action is one call of sem.c, under sem_lock. *)

\* z_impl_k_sem_init(). CHECKIF() rejects limit 0 and count > limit only
\* with runtime checks. z_waitq_init() makes the wait queue empty: if
\* threads wait (only possible with ReInit), they are lost.
SemInit(a, args) ==
    LET c == args[1]
        l == args[2]
    IN
    /\ a \in Threads
    /\ pc[a] = "idle"
    /\ ~initialized \/ ReInit
    /\ IF RuntimeChecks /\ (l = 0 \/ c > l)
         THEN /\ obs' = [NoObs EXCEPT !.actor = a, !.op = "init", !.args = args,
                                      !.ret = EINVAL]
              /\ UNCHANGED <<initialized, count, limit, waitq, pc, tmo, swapRet, tokens>>
         ELSE /\ initialized' = TRUE
              /\ count' = c
              /\ limit' = l
              /\ waitq' = <<>>
              \* API view: after init, c tokens are available. Tokens of
              \* woken threads stay with these threads.
              /\ tokens' = tokens - count + c
              /\ obs' = [NoObs EXCEPT !.actor = a, !.op = "init", !.args = args,
                                      !.ret = OK]
              /\ UNCHANGED <<pc, tmo, swapRet>>

\* z_impl_k_sem_give(). z_sched_wake() wakes the first thread of the wait
\* queue with the return value 0. If no thread waits, the count increments
\* (the C code compares with !=, not <) and the poll events get the signal.
\* @kind action
\* @c-function z_impl_k_sem_give
Give(a) ==
    /\ initialized
    /\ CanCall(a)
    /\ IF waitq # <<>>
         THEN LET t == Head(waitq) IN
              /\ waitq' = Tail(waitq)
              /\ pc' = [pc EXCEPT ![t] = "woken"]
              /\ swapRet' = [swapRet EXCEPT ![t] = OK]
              /\ tmo' = [tmo EXCEPT ![t] = "none"]
              /\ tokens' = tokens + 1
              /\ obs' = [NoObs EXCEPT !.actor = a, !.op = "give", !.wakes = <<TRUE>>,
                                      !.woken = {t}, !.release = "resched"]
              /\ UNCHANGED <<initialized, count, limit>>
         ELSE LET newCount == IF count # limit THEN Inc(count) ELSE count IN
              \E ready \in PollReady :
              /\ count' = newCount
              \* API view: a give at the limit has no effect.
              /\ tokens' = IF count < limit THEN tokens + 1 ELSE tokens
              /\ obs' = [NoObs EXCEPT !.actor = a, !.op = "give", !.wakes = <<FALSE>>,
                                      !.poll = IF Poll THEN newCount ELSE NoPoll,
                                      !.release = IF ready THEN "resched" ELSE "unlock"]
              /\ UNCHANGED <<initialized, limit, waitq, pc, tmo, swapRet>>

\* z_impl_k_sem_take(). An ISR gives only K_NO_WAIT (the __ASSERT() in sem.c).
Take(a, to) ==
    /\ initialized
    /\ CanCall(a)
    /\ a = Isr => to = "NO_WAIT"
    /\ \/ /\ count > 0
          /\ count' = count - 1
          /\ tokens' = tokens - 1
          /\ obs' = [NoObs EXCEPT !.actor = a, !.op = "take", !.timeout = to,
                                  !.release = "unlock", !.ret = OK]
          /\ UNCHANGED <<initialized, limit, waitq, pc, tmo, swapRet>>
       \/ /\ count = 0
          /\ to = "NO_WAIT"
          /\ obs' = [NoObs EXCEPT !.actor = a, !.op = "take", !.timeout = to,
                                  !.release = "unlock", !.ret = EBUSY]
          /\ UNCHANGED <<initialized, count, limit, waitq, pc, tmo, swapRet, tokens>>
       \/ /\ count = 0
          /\ to # "NO_WAIT"
          /\ IF PendAtomic
               THEN /\ waitq' = Enqueue(waitq, a)
                    /\ pc' = [pc EXCEPT ![a] = "waiting"]
               ELSE /\ waitq' = waitq
                    /\ pc' = [pc EXCEPT ![a] = "pending"]
          /\ tmo' = [tmo EXCEPT ![a] = to]
          /\ obs' = [NoObs EXCEPT !.actor = a, !.op = "take", !.timeout = to,
                                  !.release = "pend"]
          /\ UNCHANGED <<initialized, count, limit, swapRet, tokens>>

\* Only for PendAtomic = FALSE: the thread released sem_lock and now adds
\* itself to the wait queue, without a new look at the count.
Pend(t) ==
    /\ pc[t] = "pending"
    /\ waitq' = Enqueue(waitq, t)
    /\ pc' = [pc EXCEPT ![t] = "waiting"]
    /\ obs' = [NoObs EXCEPT !.actor = t, !.op = "pend"]
    /\ UNCHANGED <<initialized, count, limit, tmo, swapRet, tokens>>

\* z_impl_k_sem_reset(). The while loop wakes all threads with -EAGAIN
\* (the last z_sched_wake() returns false), then the count becomes 0, then
\* the poll events get the signal (always, with CONFIG_POLL).
Reset(a) ==
    /\ initialized
    /\ CanCall(a)
    /\ LET W == Range(waitq) IN
       \E ready \in PollReady :
       /\ waitq' = <<>>
       /\ pc' = [t \in Threads |-> IF t \in W THEN "woken" ELSE pc[t]]
       /\ swapRet' = [t \in Threads |-> IF t \in W THEN EAGAIN ELSE swapRet[t]]
       /\ tmo' = [t \in Threads |-> IF t \in W THEN "none" ELSE tmo[t]]
       /\ count' = 0
       \* API view: reset discards the available tokens.
       /\ tokens' = tokens - count
       /\ obs' = [NoObs EXCEPT !.actor = a, !.op = "reset",
                     !.wakes = [k \in 1..(Len(waitq) + 1) |-> k <= Len(waitq)],
                     !.woken = W,
                     !.poll = IF Poll THEN 0 ELSE NoPoll,
                     !.release = IF W # {} \/ ready THEN "resched" ELSE "unlock"]
       /\ UNCHANGED <<initialized, limit>>

\* The timeout of a waiting thread expires (timer ISR, z_thread_timeout()).
\* The thread leaves the wait queue and its k_sem_take() returns -EAGAIN.
Timeout(t) ==
    /\ pc[t] = "waiting"
    /\ tmo[t] = "TICKS"
    /\ t \in Range(waitq)
    /\ waitq' = SelectSeq(waitq, LAMBDA x : x # t)
    /\ pc' = [pc EXCEPT ![t] = "woken"]
    /\ swapRet' = [swapRet EXCEPT ![t] = EAGAIN]
    /\ tmo' = [tmo EXCEPT ![t] = "none"]
    /\ obs' = [NoObs EXCEPT !.actor = Isr, !.op = "timeout", !.woken = {t}]
    /\ UNCHANGED <<initialized, count, limit, tokens>>

\* The scheduler runs a woken thread again. z_pend_curr() returns the swap
\* return value, and k_sem_take() returns it without a change.
ReturnFromWait(t) ==
    /\ pc[t] = "woken"
    /\ pc' = [pc EXCEPT ![t] = "idle"]
    /\ swapRet' = [swapRet EXCEPT ![t] = NoRet]
    /\ tokens' = IF swapRet[t] = OK THEN tokens - 1 ELSE tokens
    /\ obs' = [NoObs EXCEPT !.actor = t, !.op = "take_return", !.ret = swapRet[t]]
    /\ UNCHANGED <<initialized, count, limit, waitq, tmo>>

-----------------------------------------------------------------------------

GiveStep == \E a \in Actors : Give(a)

Next ==
    \/ \E a \in Threads, args \in InitArgs : SemInit(a, args)
    \/ \E a \in Actors : \/ Give(a)
                         \/ Reset(a)
                         \/ \E to \in Timeouts : Take(a, to)
    \/ \E t \in Threads : \/ Pend(t)
                          \/ Timeout(t)
                          \/ ReturnFromWait(t)

\* Fairness only for the system parts: an expired timeout fires, a woken
\* thread runs again, a pending thread enters the queue. The application
\* calls (give, take, reset) have no fairness.
Fairness ==
    \A t \in Threads : /\ WF_vars(Timeout(t))
                       /\ WF_vars(ReturnFromWait(t))
                       /\ WF_vars(Pend(t))

Spec == Init /\ [][Next]_vars /\ Fairness

-----------------------------------------------------------------------------
(* Safety properties (state invariants) *)

TypeOK ==
    /\ initialized \in BOOLEAN
    /\ count \in 0..UMax
    /\ limit \in 0..UMax
    /\ waitq \in Seq(Threads)
    /\ Len(waitq) = Cardinality(Range(waitq))          \* no thread is in it two times
    /\ pc \in [Threads -> {"idle", "pending", "waiting", "woken"}]
    /\ tmo \in [Threads -> {"none", "FOREVER", "TICKS"}]
    /\ swapRet \in [Threads -> {NoRet, OK, EAGAIN}]
    /\ tokens \in Int
    /\ obs.op \in {"none", "init", "give", "take", "pend", "reset", "timeout", "take_return"}

\* The count is never more than the limit.
\* @kind invariant
\* @expresses TEST-REQ-1
CountLeLimit == initialized => count <= limit

\* No thread waits while the semaphore is available.
\* @expresses TEST-REQ-2
\* @expresses TEST-REQ-3
NoWaitWhileAvailable == count > 0 => waitq = <<>>

\* A thread waits if and only if it is in the wait queue (no lost waiter).
WaitingIsQueued == \A t \in Threads : (pc[t] = "waiting") <=> (t \in Range(waitq))

\* Token conservation. The ghost tokens counts with the API rules: +1 for
\* each give that is not at the limit, -1 for each take that returns 0, and
\* reset discards the count. Each token is in the count or held by exactly
\* one woken thread. A lost or a duplicated token breaks this equation.
TokenConservation == tokens = count + Inflight

\* A give wakes at most one thread. If it wakes one, there is no poll signal.
GiveWakesAtMostOne ==
    obs.op = "give" => /\ Cardinality(obs.woken) <= 1
                       /\ obs.woken # {} => obs.poll = NoPoll

\* After a reset: the queue is empty, the count is 0, and each woken thread
\* returns -EAGAIN.
ResetResult ==
    obs.op = "reset" => /\ waitq = <<>>
                        /\ count = 0
                        /\ \A t \in obs.woken : pc[t] = "woken" /\ swapRet[t] = EAGAIN

\* An ISR never waits.
IsrNeverPends == obs.actor = Isr => obs.release # "pend"

\* The poll signal K_POLL_STATE_SEM_AVAILABLE comes only with count > 0.
\* Expected to FAIL with Poll = TRUE: k_sem_reset() signals with count 0
\* (design observation 4).
\* @kind invariant
\* @expected violation
PollSignalMeansAvailable == obs.poll # NoPoll => obs.poll > 0

(* Safety properties (action properties) *)

\* Reset wakes all threads that waited before the reset, with -EAGAIN.
\* @kind action
\* @expresses TEST-REQ-4
ResetWakesAll ==
    [][obs'.op = "reset" =>
         /\ obs'.woken = Range(waitq)
         /\ \A t \in Range(waitq) : pc'[t] = "woken" /\ swapRet'[t] = EAGAIN]_vars

\* Give hands the semaphore to the first waiter without a change of the
\* count, or (no waiter) increments the count up to the limit.
GiveHandsOverOrCounts ==
    [][obs'.op = "give" =>
         IF waitq # <<>>
           THEN /\ obs'.woken = {Head(waitq)}
                /\ count' = count
           ELSE /\ obs'.woken = {}
                /\ count' = IF count < limit THEN count + 1 ELSE count]_vars

-----------------------------------------------------------------------------
(* Liveness properties *)

\* If gives occur again and again, each waiting thread stops its wait.
\* Holds for equal priorities (FIFO). FAILS for different priorities:
\* starvation of a low-priority thread.
\* @kind liveness
\* @expected violation
WaiterServedIfGives ==
    ([]<><<GiveStep>>_vars) =>
        \A t \in Threads : (pc[t] = "waiting") ~> (pc[t] # "waiting")

\* A wait with a finite timeout always ends.
\* @expresses TEST-REQ-5
TimedWaitEnds ==
    \A t \in Threads : (pc[t] = "waiting" /\ tmo[t] = "TICKS") ~> (pc[t] # "waiting")

\* A woken thread returns from k_sem_take().
WokenReturns == \A t \in Threads : (pc[t] = "woken") ~> (pc[t] = "idle")

=============================================================================
