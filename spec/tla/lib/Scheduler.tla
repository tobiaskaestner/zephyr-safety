----------------------------- MODULE Scheduler -----------------------------
(***************************************************************************)
(* Layer A: the contract of the scheduler API that the kernel objects call *)
(* (kernel/sched.c, kernel/include/ksched.h).                              *)
(*                                                                         *)
(* Level 1: each operator is a part of one critical section. An object     *)
(* action composes them: first the changes of the wait queues and of the   *)
(* thread states (PendCurr, WakeFirst, WakeAll, WakeWalk), then the end of *)
(* the critical section (Release). PendCurr includes its Release.          *)
(*                                                                         *)
(* CPUs are explicit. cur[c] is the thread that runs on CPU c. One CPU is  *)
(* the default. At each reschedule point, the CPU selects a thread with    *)
(* the rule of next_up() and should_preempt(): the highest priority runs,  *)
(* a cooperative thread keeps the CPU, the current thread wins a tie. The  *)
(* run queue is not in the model: among the ready threads with the same    *)
(* priority, the model selects any one (the code selects the thread that   *)
(* became ready first). The model has no time slices, no k_yield(), no     *)
(* scheduler lock (k_sched_lock()), no meta-IRQ threads and no CPU masks.  *)
(*                                                                         *)
(* ISRs: an ISR is an actor that runs on one CPU (IsrCpu). At level 1 an   *)
(* ISR is one step, and the exit of the ISR is a reschedule point. The     *)
(* constants CPUS, Isrs and IsrCpu move to the module Platform at level 2  *)
(* (roadmap step 5), together with the lock owners and the IPIs.           *)
(*                                                                         *)
(* Priorities: prio[t] is the model priority, a greater value is a higher  *)
(* priority (as in WaitQueue). Zephyr uses the reverse, and a negative     *)
(* Zephyr priority is a cooperative thread. ToZephyr is the only           *)
(* conversion.                                                             *)
(*                                                                         *)
(* A panic stops the system. panic gives the cause. Each action of this    *)
(* module and of the modules that use it requires panic = "none".          *)
(***************************************************************************)
EXTENDS Integers, Sequences, FiniteSets

CONSTANTS
    \* @type: Set(THREAD);
    Threads,
    \* @type: Set(OBJ);
    Objs,
    \* The value of pendedOn for a thread that does not wait.
    \* @type: OBJ;
    None,
    \* The CPUs. A set with one CPU is a uniprocessor.
    \* @type: Set(CPU);
    CPUS,
    \* The ISR actors of the objects (not the timer ISR of the expiry).
    \* @type: Set(THREAD);
    Isrs,
    \* The CPU of each ISR.
    \* @type: THREAD -> CPU;
    IsrCpu,
    \* cur[c] = Idle: the idle thread of CPU c runs.
    \* @type: THREAD;
    Idle,
    \* The values that a waker gives to a woken thread (swap data).
    \* @type: Set(DATA);
    Data,
    \* The swap data of a thread that has none.
    \* @type: DATA;
    NoData,
    \* The backend of the timeout queue (see Timeout).
    \* @type: Str;
    Backend,
    \* @type: Int;
    HeapCapacity

VARIABLES
    \* The state of each thread: "ready", "pending" or "dead". A running
    \* thread is ready and is cur[c] of one CPU.
    \* @type: THREAD -> Str;
    tstate,
    \* The model priority of each thread.
    \* @type: THREAD -> Int;
    prio,
    \* The thread that runs on each CPU, or Idle.
    \* @type: CPU -> THREAD;
    cur,
    \* The value that z_swap() returns to a thread after a wait. NoRet if
    \* the thread does not wait and has no wait to return from.
    \* @type: THREAD -> Int;
    swapRet,
    \* The data that the waker gives (thread->base.swap_data).
    \* @type: THREAD -> DATA;
    swapData,
    \* "none", or the cause of the panic.
    \* @type: Str;
    panic,
    \* The variables of WaitQueue and Timeout.
    \* @type: THREAD -> OBJ;
    pendedOn,
    \* @type: THREAD -> Int;
    stamp,
    \* @type: Seq(THREAD);
    tq,
    \* @type: { op: Str, n: Int, cost: Int };
    tqCost

ASSUME None \notin Objs
ASSUME Idle \notin Threads \cup Isrs
ASSUME Isrs \cap Threads = {}
ASSUME CPUS # {}
ASSUME \A i \in Isrs : IsrCpu[i] \in CPUS
ASSUME NoData \notin Data

\* The waiters and their order.
WQ == INSTANCE WaitQueue

\* The timeouts of the waiting threads.
TO == INSTANCE Timeout WITH Entries <- Threads

schedVars == <<tstate, prio, cur, swapRet, swapData, panic, pendedOn, stamp, tq, tqCost>>

\* Return values, with the values of the C error codes.
OK     == 0
EAGAIN == -11
\* "no return value": the thread has no wait to return from.
NoRet  == 1

\* The timeouts of a wait. "TICKS" is any finite timeout. K_NO_WAIT never
\* pends: the object returns without a call of PendCurr.
WaitTimeouts == {"FOREVER", "TICKS"}

ThreadStates == {"ready", "pending", "dead"}

-----------------------------------------------------------------------------
(* Priorities *)

\* The Zephyr priority of the model priority p, and the reverse.
ToZephyr(p) == -p
FromZephyr(z) == -z

\* A thread with a negative Zephyr priority is cooperative: no thread
\* preempts it, it runs until it waits or ends.
Cooperative(p) == ToZephyr(p) < 0

-----------------------------------------------------------------------------
(* Queries *)

\* Thread t runs on a CPU.
Running(t) == \E c \in CPUS : cur[c] = t

\* Actor a can call the kernel API now: an ISR, or a running thread that
\* does not return from a wait now (see Resume).
CanCall(a) == IF a \in Isrs THEN TRUE ELSE Running(a) /\ swapRet[a] = NoRet

\* The CPU of actor a. Defined only if a is an ISR or a running thread. A
\* thread runs on at most one CPU (invariant CurUnique), so the CHOOSE has
\* exactly one witness.
CpuOf(a) == IF a \in Isrs THEN IsrCpu[a] ELSE CHOOSE c \in CPUS : cur[c] = a

\* The thread waits on an object and has a finite timeout.
TimedWait(t) == t \in TO!Armed

\* The constant function with the value v on S (the return values of a
\* wake).
\* @type: (Set(THREAD), a) => (THREAD -> a);
Const(S, v) == [t \in S |-> v]

-----------------------------------------------------------------------------
(* The selection rule. The arguments are the state after the critical      *)
(* section: ts (tstate), pr (prio) and cu (cur).                           *)

\* The threads that CPU c can select: ready, and not current on another
\* CPU.
\* @type: (CPU, THREAD -> Str, CPU -> THREAD) => Set(THREAD);
Candidates(c, ts, cu) ==
    {t \in Threads : ts[t] = "ready" /\ \A d \in CPUS \ {c} : cu[d] # t}

\* The threads of S with the highest priority.
\* @type: (Set(THREAD), THREAD -> Int) => Set(THREAD);
Top(S, pr) == {t \in S : \A u \in S : pr[u] <= pr[t]}

\* The threads that CPU c can select at a reschedule point: next_up() and
\* should_preempt() with preempt_ok = 0, in the order of the code.
\* @kind definition
\* @c-function next_up
\* @c-function should_preempt
\* @type: (CPU, THREAD -> Str, THREAD -> Int, CPU -> THREAD) => Set(THREAD);
Choices(c, ts, pr, cu) ==
    LET u == cu[c]
        S == Candidates(c, ts, cu)
    IN  IF u # Idle /\ ts[u] = "ready" /\ Cooperative(pr[u]) THEN {u}
        ELSE IF S = {} THEN {Idle}
        ELSE IF u \in Top(S, pr) THEN {u}
        ELSE Top(S, pr)

\* CPU c selects a thread. The caller sets tstate' and prio' first.
\* @kind action
Select(c) ==
    \E t \in Choices(c, tstate', prio', cur) : cur' = [cur EXCEPT ![c] = t]

\* The end of the critical section of actor a. kind:
\* "unlock"  k_spin_unlock(): a thread keeps its CPU.
\* "resched" z_reschedule(): the CPU of a selects a thread.
\* "swap"    z_swap(): the CPU of a selects a thread (a has stopped).
\* For an ISR each kind is the same: the exit of the ISR selects a thread.
\* @kind action
\* @c-function z_reschedule
\* @c-function k_spin_unlock
Release(a, kind) ==
    IF kind = "unlock" /\ a \notin Isrs
      THEN UNCHANGED cur
      ELSE Select(CpuOf(a))

-----------------------------------------------------------------------------
(* Layer A: one operator for each function that the objects call.         *)

\* z_pend_curr(): the current thread a waits on o with the timeout to. It
\* leaves the CPU, its return value is -EAGAIN until a waker sets another
\* one. From an ISR: panic, and no other change (the check is the first
\* statement of z_pend_curr()). A finite timeout on a full heap: panic in
\* z_add_timeout(). The model then stops; the state of the wait queue at
\* the panic is not modeled.
\* @kind action
\* @c-function z_pend_curr
PendCurr(a, o, to) ==
    IF a \in Isrs
      THEN /\ panic' = "pend_in_isr"
           /\ UNCHANGED <<tstate, prio, cur, swapRet, swapData, pendedOn, stamp, tq, tqCost>>
    ELSE IF to = "TICKS" /\ TO!Full
      THEN /\ panic' = "timeout_heap_full"
           /\ UNCHANGED <<tstate, prio, cur, swapRet, swapData, pendedOn, stamp, tq, tqCost>>
    ELSE /\ WQ!Add(a, o)
         /\ IF to = "TICKS" THEN TO!InsertAny(a) ELSE UNCHANGED <<tq, tqCost>>
         /\ tstate' = [tstate EXCEPT ![a] = "pending"]
         /\ swapRet' = [swapRet EXCEPT ![a] = EAGAIN]
         /\ swapData' = [swapData EXCEPT ![a] = NoData]
         /\ UNCHANGED <<prio, panic>>
         /\ Release(a, "swap")

\* The threads in S stop to wait: they leave the wait queue, their
\* timeouts are cancelled, each one gets its return value ret[t] and its
\* data dat[t], and each one is ready. This is z_sched_wake_thread_locked()
\* with the cancellation of the timeout that its callers do first
\* (z_unpend_first_thread_locked(), event_walk_op()).
\* @kind action
\* @c-function z_sched_wake_thread_locked
\* @type: (Set(THREAD), THREAD -> Int, THREAD -> DATA) => Bool;
WakeSet(S, ret, dat) ==
    /\ WQ!RemoveSet(S)
    /\ TO!CancelSet(S)
    /\ tstate' = [t \in Threads |-> IF t \in S THEN "ready" ELSE tstate[t]]
    /\ swapRet' = [t \in Threads |-> IF t \in S THEN ret[t] ELSE swapRet[t]]
    /\ swapData' = [t \in Threads |-> IF t \in S THEN dat[t] ELSE swapData[t]]
    /\ UNCHANGED <<prio, panic>>

\* The wait queue of o is not empty: z_sched_wake() returns true.
HasWaiters(o) == WQ!W(o) # {}

\* z_sched_wake(): the best waiter of o stops to wait with ret and data.
\* Enabled only if HasWaiters(o) (else z_sched_wake() returns false and
\* changes nothing).
\* @kind action
\* @c-function z_sched_wake
WakeFirst(o, ret, data) ==
    /\ HasWaiters(o)
    /\ LET S == {WQ!Best(o)} IN WakeSet(S, Const(S, ret), Const(S, data))

\* z_unpend_first_thread_locked() and z_sched_ready_locked(), with object
\* code between them (msgq copy, mutex owner). F(t) gives the pair
\* <<return value, data>> for the woken thread t.
\* @kind action
\* @c-function z_unpend_first_thread_locked
\* @c-function z_sched_ready_locked
\* @type: (OBJ, THREAD => <<Int, DATA>>) => Bool;
WakeFirstWith(o, F(_)) ==
    /\ HasWaiters(o)
    /\ LET S == {WQ!Best(o)}
       IN  WakeSet(S, [t \in S |-> F(t)[1]], [t \in S |-> F(t)[2]])

\* The loop "while (z_sched_wake(...))": all waiters of o stop to wait with
\* ret and data, in one critical section. Also enabled on an empty wait
\* queue (no change), because the loop always runs.
\* @kind action
\* @c-function z_sched_wake_all
WakeAll(o, ret, data) ==
    LET S == WQ!W(o) IN WakeSet(S, Const(S, ret), Const(S, data))

\* z_sched_waitq_walk(): each waiter t of o with P(t) stops to wait, with
\* the return value 0 and the data D(t). The walk order changes only the
\* order of the wakes, not the result of the critical section.
\* @kind action
\* @c-function z_sched_waitq_walk
\* @type: (OBJ, THREAD => Bool, THREAD => DATA) => Bool;
WakeWalk(o, P(_), D(_)) ==
    LET S == {t \in WQ!W(o) : P(t)}
    IN  WakeSet(S, Const(S, OK), [t \in S |-> D(t)])

\* z_thread_prio_set(): the priority of t becomes p. A waiter goes to the
\* end of the waiters of its object with the priority p. No reschedule:
\* the caller decides (k_thread_priority_set(), the mutex).
\* @kind action
\* @c-function z_thread_prio_set
PrioSet(t, p) ==
    /\ tstate[t] # "dead"
    /\ prio' = [prio EXCEPT ![t] = p]
    /\ IF t \in WQ!Waiting THEN WQ!Restamp(t) ELSE UNCHANGED <<pendedOn, stamp>>
    /\ UNCHANGED <<tstate, swapRet, swapData, panic, tq, tqCost>>

-----------------------------------------------------------------------------
(* Environment actions. The objects do not call them. A model of an       *)
(* object adds them to its next-state relation.                           *)

\* z_thread_timeout() from sys_clock_announce() on CPU c: the first entry of
\* the timeout queue expires. Its thread stops to wait and keeps the return
\* value -EAGAIN. The exit of the timer ISR selects a thread for c. Only
\* thread waits use this atomic form (see Timeout).
\* @kind action
\* @c-function z_thread_timeout
ThreadTimeout(c) ==
    /\ panic = "none"
    /\ tq # <<>>
    /\ LET t == TO!First IN
       /\ TO!Expire
       /\ WQ!Remove(t)
       /\ tstate' = [tstate EXCEPT ![t] = "ready"]
       /\ UNCHANGED <<prio, swapRet, swapData, panic>>
       /\ Select(c)

\* k_thread_abort(t) by actor a. t is dead: it leaves the CPU, its wait
\* queue and the timeout queue. If a aborts itself, its CPU selects a
\* thread (z_swap()). An ISR selects a thread at its exit. A thread that
\* aborts another thread does not reschedule.
\* Not in the model: the join queue (an object, later), essential threads
\* (panic), and the abort of a thread that runs on another CPU (level 2:
\* the target halts itself in an IPI, roadmap step 5).
\* @kind action
\* @c-function z_thread_abort
\* @c-function halt_thread
Abort(a, t) ==
    /\ panic = "none"
    /\ CanCall(a)
    /\ tstate[t] # "dead"
    /\ \A c \in CPUS : cur[c] = t => (a = t \/ (a \in Isrs /\ IsrCpu[a] = c))
    /\ IF t \in WQ!Waiting THEN WQ!Remove(t) ELSE UNCHANGED <<pendedOn, stamp>>
    /\ TO!Cancel(t)
    /\ tstate' = [tstate EXCEPT ![t] = "dead"]
    /\ swapRet' = [swapRet EXCEPT ![t] = NoRet]
    /\ swapData' = [swapData EXCEPT ![t] = NoData]
    /\ UNCHANGED <<prio, panic>>
    /\ Release(a, IF a = t THEN "swap" ELSE "unlock")

\* k_thread_priority_set(t, p) by actor a. It reschedules only if t is
\* ready (the return value of z_thread_prio_set()).
\* @kind action
\* @c-function k_thread_priority_set
SetPrio(a, t, p) ==
    /\ panic = "none"
    /\ CanCall(a)
    /\ PrioSet(t, p)
    /\ Release(a, IF tstate[t] = "ready" THEN "resched" ELSE "unlock")

\* Thread t runs again after a wait: z_swap() returns swapRet[t] with
\* swapData[t]. The object reads both in the same step (Waitable).
\* @kind action
Resume(t) ==
    /\ panic = "none"
    /\ Running(t)
    /\ swapRet[t] # NoRet
    /\ swapRet' = [swapRet EXCEPT ![t] = NoRet]
    /\ swapData' = [swapData EXCEPT ![t] = NoData]
    /\ UNCHANGED <<tstate, prio, cur, panic, pendedOn, stamp, tq, tqCost>>

\* An interrupt on CPU c without a kernel call (a tick, an IPI). Its exit
\* selects a thread. Enabled only if the selection changes cur[c]. On SMP
\* this is the IPI that a wake on another CPU sends (flag_ipi()).
\* @kind action
Preempt(c) ==
    /\ panic = "none"
    /\ cur[c] \notin Choices(c, tstate, prio, cur)
    /\ \E t \in Choices(c, tstate, prio, cur) : cur' = [cur EXCEPT ![c] = t]
    /\ UNCHANGED <<tstate, prio, swapRet, swapData, panic, pendedOn, stamp, tq, tqCost>>

\* The initial state: all threads ready with the priorities p0, no waiter,
\* and on each CPU a thread that the rule can select.
\* @kind definition
InitState(p0) ==
    /\ tstate = [t \in Threads |-> "ready"]
    /\ prio = p0
    /\ swapRet = [t \in Threads |-> NoRet]
    /\ swapData = [t \in Threads |-> NoData]
    /\ panic = "none"
    /\ pendedOn = [t \in Threads |-> None]
    /\ stamp = [t \in Threads |-> 0]
    /\ tq = <<>>
    /\ tqCost = TO!NoCost
    /\ cur \in [CPUS -> Threads \cup {Idle}]
    /\ \A c \in CPUS : cur[c] \in Choices(c, tstate, prio, cur)
    /\ \A c, d \in CPUS : c # d /\ cur[c] # Idle => cur[c] # cur[d]

\* Fairness of the environment: an armed timeout expires, an IPI arrives.
Fairness ==
    /\ WF_schedVars(\E c \in CPUS : ThreadTimeout(c))
    /\ \A c \in CPUS : WF_schedVars(Preempt(c))

-----------------------------------------------------------------------------
(* Properties *)

\* @kind invariant
TypeOK ==
    /\ tstate \in [Threads -> ThreadStates]
    /\ DOMAIN prio = Threads
    /\ cur \in [CPUS -> Threads \cup {Idle}]
    /\ DOMAIN swapRet = Threads
    /\ swapData \in [Threads -> Data \cup {NoData}]
    /\ panic \in {"none", "pend_in_isr", "timeout_heap_full"}

\* A thread runs on at most one CPU.
\* @kind invariant
CurUnique == \A c, d \in CPUS : c # d /\ cur[c] # Idle => cur[c] # cur[d]

\* A running thread is ready: a pending or dead thread never runs.
\* @kind invariant
CurIsReady == \A c \in CPUS : cur[c] # Idle => tstate[cur[c]] = "ready"

\* A thread is pending if and only if it is in a wait queue, and its
\* return value is -EAGAIN until a waker sets another one.
\* @kind invariant
PendingIsQueued ==
    \A t \in Threads :
        /\ (tstate[t] = "pending") <=> (pendedOn[t] # None)
        /\ tstate[t] = "pending" => swapRet[t] = EAGAIN

\* Only a pending thread has an armed timeout. A woken thread has no
\* timeout left that can wake it from a later wait (the precondition of
\* z_sched_wake_thread_locked()).
\* @kind invariant
ArmedArePending == \A t \in TO!Armed : tstate[t] = "pending"

\* A dead thread has no wait and no return value.
\* @kind invariant
DeadIsInert ==
    \A t \in Threads : tstate[t] = "dead" =>
        /\ pendedOn[t] = None
        /\ swapRet[t] = NoRet
        /\ ~Running(t)

\* Each CPU runs a thread that the rule can select. On one CPU this holds
\* after each step, if each critical section that makes a thread ready
\* ends with a reschedule point. On SMP it can fail until the IPI arrives
\* (see SelectionHappens).
\* @kind invariant
RunRuleHolds == \A c \in CPUS : cur[c] \in Choices(c, tstate, prio, cur)

\* No panic. This is an environment assumption: no ISR calls a wait, and
\* the heap of the timeouts is large enough.
\* @kind invariant
NoPanic == panic = "none"

\* The position of the timeout of t in the timeout queue. Defined only if
\* TimedWait(t). An entry is armed at most once (Timeout!ArmedOnce), so
\* the CHOOSE has exactly one witness.
TimeoutPos(t) == CHOOSE i \in DOMAIN tq : tq[i] = t

\* A step that inserts a timeout in front of the timeout of t.
Overtaken(t) == TimedWait(t) /\ TimedWait(t)' /\ TimeoutPos(t)' > TimeoutPos(t)

\* An armed timeout ends its wait (with the fairness of ThreadTimeout), if
\* eventually no new timeout goes in front of it. The model has no clock:
\* without this condition a new timeout can go in front again and again.
\* Real time permits only a finite number of earlier deadlines (non-Zeno).
\* @kind liveness
TimedWaitEnds ==
    \A t \in Threads :
        (<>[][~Overtaken(t)]_schedVars) => (TimedWait(t) ~> (tstate[t] # "pending"))

\* A CPU that runs a thread that the rule does not select selects again
\* (with the fairness of Preempt).
\* @kind liveness
SelectionHappens ==
    \A c \in CPUS : (cur[c] \notin Choices(c, tstate, prio, cur)) ~>
                    (cur[c] \in Choices(c, tstate, prio, cur))

=============================================================================
