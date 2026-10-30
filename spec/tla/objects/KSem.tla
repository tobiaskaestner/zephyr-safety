-------------------------------- MODULE KSem --------------------------------
(***************************************************************************)
(* The contract module of the semaphore, kernel/sem.c (Zephyr              *)
(* 770fdef1567), on the library: an instance of the template Waitable on   *)
(* the scheduler contract. It replaces the proof of concept of the         *)
(* workspace notes (tla/KSem.tla), which had its own wait queue, its own   *)
(* timeout and free interleaving.                                          *)
(*                                                                         *)
(* Grain: coarse. Each call of k_sem_give(), k_sem_take() and              *)
(* k_sem_reset() is one step: sem.c locks sem_lock before it reads the     *)
(* count or uses the wait queue, and releases it once as its last call     *)
(* (k_spin_unlock(), z_reschedule() or z_pend_curr()). On one CPU the lock *)
(* also locks the interrupts. This is the grain assumption of the module:  *)
(* the lock spy of the unit tests and the CBMC harness check it (see the   *)
(* consistency record of k_sem). k_sem_init() takes no lock: the step is   *)
(* atomic only if no other actor uses the semaphore (ReInit).              *)
(*                                                                         *)
(* All semaphores share sem_lock. At the coarse grain this is not visible: *)
(* the steps on two semaphores are atomic each.                            *)
(*                                                                         *)
(* The resource of a semaphore o is r[o] = [init, count, limit]: init is   *)
(* TRUE after a k_sem_init() that returned 0, count and limit are the      *)
(* fields of struct k_sem. tokens is a ghost variable of the property      *)
(* part (TokenConservation).                                               *)
(*                                                                         *)
(* Next has the most general environment: the API calls of each actor on   *)
(* each semaphore, and Scheduler!EnvNext (timeouts, preemption, aborts,    *)
(* priority changes, the outer interrupt lock). The bounds are constants:  *)
(* the threads, the ISRs, the semaphores, the arguments of k_sem_init()    *)
(* (InitArgs), the priorities (InitPrios, EnvPrios) and the nesting of the *)
(* outer lock (MaxIrqNest).                                                *)
(*                                                                         *)
(* Not in the module: k_sem_count_get() (a read without the lock, a query  *)
(* of the count), the z_vrfy_k_sem_*() functions of CONFIG_USERSPACE (a    *)
(* check of the object, then the same call), CONFIG_OBJ_CORE_SEM (a link   *)
(* into a list that no property reads), the tracing hooks.                 *)
(***************************************************************************)
EXTENDS Integers, Sequences, FiniteSets

CONSTANTS
    \* The parameters of Scheduler (see there). Objs are the semaphores.
    Threads, Objs, None, Isrs, IsrCpu, MaxIrqNest, Idle, Data, NoData, JoinQ,
    CPUS, UseSwitch, Backend, HeapCapacity,
    \* The pairs <<initial_count, limit>> that k_sem_init() can get.
    InitArgs,
    \* The largest value of the unsigned count (UINT_MAX, scaled down).
    UMax,
    \* The model priorities of the threads in the initial state.
    InitPrios,
    \* The model priorities that k_thread_priority_set() can give ({}: no
    \* priority change).
    EnvPrios

\* The argument check of k_sem_init() with CHECKIF() (Kconfig kind 5, the
\* fault model): TRUE with CONFIG_RUNTIME_ERROR_CHECKS (-EINVAL), FALSE
\* with CONFIG_NO_RUNTIME_CHECKS (no check). CONFIG_ASSERT_ON_ERRORS (an
\* assertion) is not in the model.
\* @kconfig CONFIG_RUNTIME_ERROR_CHECKS CONFIG_NO_RUNTIME_CHECKS
CONSTANT RuntimeChecks

\* The poll events of the semaphore (Kconfig kind 2): with CONFIG_POLL,
\* give and reset call z_handle_obj_poll_events().
\* @kconfig CONFIG_POLL
CONSTANT Poll

\* A condition of use: FALSE if the client calls k_sem_init() only on a
\* semaphore that no other actor uses. TRUE lets a thread initialize a
\* semaphore again at any time (z_vrfy_k_sem_init() accepts an initialized
\* object, finding 9 of the sem findings): with waiters, the code has
\* undefined behavior (Scheduler!WaitqInit, finding P6-u).
CONSTANT ReInit

\* A condition of use: FALSE if an ISR calls k_sem_take() only with
\* K_NO_WAIT (ZEP-SRS-5-20, the __ASSERT() of sem.c). TRUE lets an ISR
\* wait: the scheduler panics (Scheduler!PendCurr, detector NoPanic).
CONSTANT IsrWaits

ASSUME InitArgs \subseteq (0..UMax) \X (0..UMax)
ASSUME {RuntimeChecks, Poll, ReInit, IsrWaits} \subseteq BOOLEAN
ASSUME \A t \in Threads : JoinQ[t] = None

VARIABLES
    tstate, prio, cur, swapRet, swapData, panic, rqStamp, preemptOk, readySince,
    pendedOn, stamp, tq, tqCost, irqNest, pendsv,
    \* The fields of each semaphore: [init, count, limit].
    r,
    \* The semaphore of the wait of each thread (Waitable).
    req,
    \* Ghost: the tokens that the API made available and that no take has
    \* consumed, for each semaphore (TokenConservation).
    tokens,
    \* The observation of the last step (Waitable).
    obs

\* The template, on the same variables.
W == INSTANCE Waitable

\* The scheduler contract.
S == INSTANCE Scheduler

schedVars == W!schedVars

vars == <<schedVars, r, req, tokens, obs>>

\* All variables but the observation: the state of the model. The
\* observation is a function of the last step only.
stateVars == <<schedVars, r, req, tokens>>

Actors == Threads \cup Isrs

\* Return values, with the values of the C error codes.
OK     == S!OK
EAGAIN == S!EAGAIN
EBUSY  == -16
EINVAL == -22
NoRet  == S!NoRet

\* K_POLL_STATE_SEM_AVAILABLE (kernel.h: bit 1 of the poll states).
PollSemAvailable == 2

\* The timeouts of a take. "TICKS" is any finite timeout.
Timeouts == {"NO_WAIT", "FOREVER", "TICKS"}

-----------------------------------------------------------------------------
(* The operators of the semaphore for the template *)

\* The fields of a semaphore memory that k_sem_init() did not initialize.
NoSem == [init |-> FALSE, count |-> 0, limit |-> 0]

\* The count: the measure of the resource in the call records.
SemCount(x) == x.count

\* A take succeeds now: count > 0 (sem.c:138).
SemAvail(x) == x.count > 0

\* The take decrements the count (sem.c:139).
SemConsume(x) == [x EXCEPT !.count = @ - 1]

\* Unsigned increment of the count, with wrap (count += 1U).
Inc(c) == IF c = UMax THEN 0 ELSE c + 1

\* A give without a waiter: the count increments if it is not the limit
\* (sem.c:105, the comparison is !=, not <).
SemSettle(x) == [x EXCEPT !.count = IF x.count # x.limit THEN Inc(x.count) ELSE x.count]

\* The reset sets the count to 0 (sem.c:169).
SemFlushR(x) == [x EXCEPT !.count = 0]

\* The argument check of k_sem_init() (sem.c:51): only with runtime
\* checks.
SemValid(args) == ~(RuntimeChecks /\ (args[2] = 0 \/ args[1] > args[2]))

\* The fields after k_sem_init(args).
SemNew(args) == [init |-> TRUE, count |-> args[1], limit |-> args[2]]

\* The woken threads of a give that hold a token: they will return 0.
Inflight(o) == Cardinality({t \in Threads : req[t] = o /\ swapRet[t] = OK})

-----------------------------------------------------------------------------
(* Initial state: the threads are ready with priorities from InitPrios, no *)
(* thread waits, the memory of each semaphore is not initialized.          *)

Init ==
    /\ \E p0 \in [Threads -> InitPrios] : S!InitState(p0)
    /\ r = [o \in Objs |-> NoSem]
    /\ req = [t \in Threads |-> None]
    /\ tokens = [o \in Objs |-> 0]
    /\ obs = W!NoObs

-----------------------------------------------------------------------------
(* Step actions *)

\* z_impl_k_sem_init() by thread a. A condition of use: the semaphore is
\* not in use (ReInit).
\* @kind action
\* @c-function z_impl_k_sem_init
SemInit(o, a, args) ==
    /\ ~r[o].init \/ ReInit
    /\ W!InitOp(o, a, args, SemValid, SemNew, EINVAL, SemCount)
    \* API view: after the init, args[1] tokens are available. The tokens of
    \* woken threads stay with these threads.
    /\ tokens' = IF SemValid(args) THEN [tokens EXCEPT ![o] = @ - r[o].count + args[1]]
                 ELSE tokens

\* z_impl_k_sem_give() by actor a: a hand-over to the best waiter, or an
\* increment up to the limit and the poll signal.
\* @kind action
\* @c-function z_impl_k_sem_give
Give(o, a) ==
    /\ r[o].init
    /\ W!Give(o, a, SemSettle, SemCount, Poll, PollSemAvailable)
    \* API view: a give at the limit without a waiter has no effect.
    /\ tokens' = IF S!HasWaiters(o) \/ r[o].count < r[o].limit
                   THEN [tokens EXCEPT ![o] = @ + 1] ELSE tokens

\* z_impl_k_sem_take() by actor a with the timeout to. A condition of use:
\* an ISR does not wait (IsrWaits).
\* @kind action
\* @c-function z_impl_k_sem_take
Take(o, a, to) ==
    /\ r[o].init
    /\ (a \in Isrs /\ to # "NO_WAIT") => IsrWaits
    /\ W!Take(o, a, to, SemAvail, SemConsume, EBUSY, SemCount)
    /\ tokens' = IF SemAvail(r[o]) THEN [tokens EXCEPT ![o] = @ - 1] ELSE tokens

\* z_impl_k_sem_reset() by actor a: the flush of the template with
\* -EAGAIN and the count 0. The poll events always get the signal (with
\* CONFIG_POLL), also with the count 0.
\* @kind action
\* @c-function z_impl_k_sem_reset
Reset(o, a) ==
    /\ r[o].init
    /\ W!Flush(o, a, EAGAIN, SemFlushR, SemCount, Poll, PollSemAvailable)
    \* API view: the reset discards the available tokens.
    /\ tokens' = [tokens EXCEPT ![o] = @ - r[o].count]

\* The return of k_sem_take() after a wait: the value of z_pend_curr()
\* (sem.c:153), without a change.
\* @kind action
\* @c-function z_impl_k_sem_take
TakeReturn(t) ==
    /\ W!ResumeOp(t)
    /\ tokens' = IF swapRet[t] = OK THEN [tokens EXCEPT ![req[t]] = @ - 1] ELSE tokens

\* A step of the environment of the scheduler. A thread that dies before it
\* returns from a hand-over takes its token with it.
\* @kind action
Env ==
    /\ W!EnvStep(EnvPrios)
    /\ tokens' = [o \in Objs |->
                    tokens[o] - Cardinality({t \in Threads : req[t] = o /\ swapRet[t] = OK
                                                             /\ tstate'[t] = "dead"})]

\* The steps of the API calls, for the mutant module (one disjunct each).
InitNext   == \E o \in Objs, a \in Threads, args \in InitArgs : SemInit(o, a, args)
GiveNext   == \E o \in Objs, a \in Actors : Give(o, a)
TakeNext   == \E o \in Objs, a \in Actors, to \in Timeouts : Take(o, a, to)
ResetNext  == \E o \in Objs, a \in Actors : Reset(o, a)
ReturnNext == \E t \in Threads : TakeReturn(t)

\* After a panic or undefined behavior the system does nothing. This step
\* is not a deadlock.
Halted == panic # "none" /\ UNCHANGED vars

Next ==
    \/ InitNext
    \/ GiveNext
    \/ TakeNext
    \/ ResetNext
    \/ ReturnNext
    \/ Env
    \/ Halted

\* Fairness: the environment of the scheduler (an armed timeout expires, the
\* CPU selects again, a pending PendSV runs) and the return of a woken
\* thread that runs. The API calls have no fairness.
Fairness ==
    /\ S!Fairness
    /\ \A t \in Threads : WF_vars(TakeReturn(t))

Spec == Init /\ [][Next]_vars /\ Fairness

-----------------------------------------------------------------------------
(* Behavior invariants *)

\* @kind invariant
TypeOK ==
    /\ S!TypeOK
    /\ r \in [Objs -> [init : BOOLEAN, count : 0..UMax, limit : 0..UMax]]
    /\ req \in [Threads -> Objs \cup {None}]
    /\ obs.op \in {"none", "init", "give", "take", "flush", "resume", "env"}

\* @kind invariant
ReqIsWait == W!ReqIsWait

\* Each step of an API call that takes sem_lock has the lock as its first
\* call and one release as its last call (the grain assumption, in the
\* terms of the call record). An action property: it reads obs'.
\* @kind action-property
CallsHoldLock ==
    [][obs'.op \in {"give", "take", "flush"} => W!LockDiscipline(obs'.calls)]_vars

-----------------------------------------------------------------------------
(* Requirement properties. Each one states one reading of a requirement of *)
(* doc/reqmgmt/docs/software_requirements/semaphore.sdoc. The readings     *)
(* are in the comment of each property. Where an action property reads    *)
(* the step, it reads obs' and the state, never obs: the models can then   *)
(* use a view without obs.                                                 *)

\* Reading: the count of an initialized semaphore is never above its
\* limit. The init sets the limit (5-4) and rejects an initial count above
\* it (5-18), and a give at the limit leaves the count unchanged (5-19).
\* Only with runtime checks: without them, the init accepts any count, and
\* a give above the limit increments the count (comparison !=, finding 1
\* of the sem findings).
\* @kind invariant
\* @kconfig CONFIG_RUNTIME_ERROR_CHECKS
\* @source ZEP-SRS-5-4
\* @source ZEP-SRS-5-19
CountLeLimit == RuntimeChecks => \A o \in Objs : r[o].init => r[o].count <= r[o].limit

\* Reading: a thread waits on a semaphore only while its count is 0 ("while
\* the count is zero, the thread shall be blocked"; with the count above
\* 0, the thread acquires it at once, 5-7).
\* @kind invariant
\* @source ZEP-SRS-5-8
NoWaitWhileAvailable == \A o \in Objs : r[o].count > 0 => S!WQ!W(o) = {}

\* Reading: no token is lost or made twice. The ghost tokens counts with
\* the API rules: +1 for a give that wakes a waiter or increments the count
\* (5-13, 5-14), -1 for a take that returns 0 (5-7), and a reset discards
\* the count (5-16). Each token is in the count or held by exactly one
\* woken thread that has not returned yet.
\* @kind invariant
\* @source ZEP-SRS-5-13
\* @source ZEP-SRS-5-14
TokenConservation == \A o \in Objs : tokens[o] = r[o].count + Inflight(o)

\* Reading: a give wakes a waiting thread if one waits, and then the count
\* does not change (the woken thread acquires the semaphore, 5-14). Else
\* the give increments the count (5-13), but not above the limit (5-19).
\* @kind action-property
\* @source ZEP-SRS-5-13
\* @source ZEP-SRS-5-14
\* @source ZEP-SRS-5-19
GiveHandsOverOrCounts ==
    [][obs'.op = "give" =>
         LET o == obs'.obj IN
         IF S!HasWaiters(o)
           THEN /\ Cardinality(obs'.woken) = 1
                /\ r'[o].count = r[o].count
           ELSE /\ obs'.woken = {}
                /\ r'[o].count = IF r[o].count < r[o].limit THEN r[o].count + 1
                                 ELSE r[o].count]_vars

\* Reading: the thread that a give wakes has the highest priority of the
\* waiting threads. The requirement says nothing on equal priorities.
\* @kind action-property
\* @source ZEP-SRS-5-14
GiveWakesHighest ==
    [][(obs'.op = "give" /\ obs'.woken # {}) =>
         \A t \in obs'.woken, u \in S!WQ!W(obs'.obj) : prio[u] <= prio[t]]_vars

\* Reading: a take with the count above 0 returns 0 and decrements the
\* count (5-7). A take with the count 0 and K_NO_WAIT returns -EBUSY and
\* does not wait (5-11). A take of a thread with the count 0 and a timeout
\* waits (5-8).
\* @kind action-property
\* @source ZEP-SRS-5-7
\* @source ZEP-SRS-5-8
\* @source ZEP-SRS-5-11
TakeResult ==
    [][obs'.op = "take" =>
         LET o == obs'.obj
             a == obs'.actor
         IN  /\ r[o].count > 0 => (obs'.ret = OK /\ r'[o].count = r[o].count - 1)
             /\ (r[o].count = 0 /\ obs'.timeout = "NO_WAIT") =>
                    (obs'.ret = EBUSY /\ r'[o].count = 0 /\ pendedOn' = pendedOn)
             /\ (r[o].count = 0 /\ obs'.timeout # "NO_WAIT" /\ a \in Threads) =>
                    pendedOn'[a] = o]_vars

\* Reading: a reset sets the count to 0 (5-16), and each thread that waited
\* returns the error of a wait timeout, -EAGAIN (5-17, 5-10). No thread
\* waits after the reset.
\* @kind action-property
\* @source ZEP-SRS-5-16
\* @source ZEP-SRS-5-17
ResetWakesAll ==
    [][obs'.op = "flush" =>
         LET o == obs'.obj IN
         /\ r'[o].count = 0
         /\ S!WQ!W(o) = obs'.woken
         /\ \A t \in obs'.woken : tstate'[t] = "ready" /\ swapRet'[t] = EAGAIN
         /\ ~\E t \in Threads : pendedOn'[t] = o]_vars

\* Reading: a take that waited returns 0 (a give handed the semaphore
\* over) or -EAGAIN (the timeout expired, 5-10, or a reset aborted the
\* wait, 5-17). No other value.
\* @kind action-property
\* @source ZEP-SRS-5-10
WaitResult == [][obs'.op = "resume" => obs'.ret \in {OK, EAGAIN}]_vars

\* Reading: the poll state K_POLL_STATE_SEM_AVAILABLE means that the count
\* is above 0. TLC finds a violation with CONFIG_POLL: k_sem_reset() gives
\* the signal with the count 0 (design observation 4 of the sem findings).
\* @kind action-property
\* @kconfig CONFIG_POLL
\* @source doc:kernel/services/polling
\* @expected violation
PollSignalMeansAvailable ==
    [][\A k \in DOMAIN obs'.calls :
         obs'.calls[k].fn = W!PollFn => obs'.calls[k].res > 0]_vars

\* Detector of the condition of use IsrWaits: no panic. An ISR may take a
\* semaphore only without a wait (5-20).
\* @kind invariant
\* @source ZEP-SRS-5-20
NoPanic == S!NoPanic

\* Detector of the condition of use ReInit: no undefined behavior (an init
\* of a semaphore with waiters, finding P6-u).
\* @kind invariant
NoUndefined == S!NoUndefined

-----------------------------------------------------------------------------
(* Liveness *)

\* A give on o in the step.
GiveOn(o) == \E a \in Actors : Give(o, a)

\* Reading of 5-8 ("blocked until the semaphore is released"): if gives on
\* o occur again and again, each waiting thread stops its wait. Holds for
\* equal priorities. TLC finds a violation for different priorities: a
\* waiter with a low priority starves (the gives go to the waiter with the
\* highest priority, 5-14).
\* @kind liveness
\* @source ZEP-SRS-5-8
WaiterServedIfGives ==
    \A o \in Objs :
        ([]<><<GiveOn(o)>>_vars) =>
            \A t \in Threads : (pendedOn[t] = o) ~> (pendedOn[t] # o)

=============================================================================
