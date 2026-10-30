---------------------------- MODULE MCScheduler ----------------------------
(***************************************************************************)
(* Model of lib/Scheduler.tla alone. An environment of threads and one ISR *)
(* calls the layer A operators in each order that the contract allows:     *)
(* a wait, a wake (first, all, walk, first with object code) followed by   *)
(* z_reschedule(), an abort, a priority change, a timeout, the return from *)
(* a wait, an IPI.                                                         *)
(*                                                                         *)
(* MCMutant plants one misuse of the contract, as evidence that the        *)
(* invariants find it:                                                     *)
(*                                                                         *)
(* - "missed_resched": a thread wakes a waiter and ends with               *)
(*   k_spin_unlock() in place of z_reschedule().                           *)
(* - "wake_no_cancel": a wake with z_sched_wake_thread_locked() without    *)
(*   the cancellation of the timeout first.                                *)
(*                                                                         *)
(* MCIsrPends lets the ISR call z_pend_curr(), which panics.               *)
(*                                                                         *)
(* MCSetPrioBy selects the target of k_thread_priority_set(): "any",       *)
(* "self" (the caller sets its own priority), "other" (another thread),    *)
(* "other_same" (another thread that does not run, to its own priority)   *)
(* or "none" (no call).                                                    *)
(* The configurations p7_* use "self" and "other" to give the short        *)
(* counterexamples of the findings P7-a and P7-b one at a time. MCAbort    *)
(* FALSE removes k_thread_abort() from the environment for the same        *)
(* reason. The new priority can be the old one: the code then also         *)
(* requeues the thread.                                                    *)
(*                                                                         *)
(* MCUseSwitch selects the variant of the context switch (Platform,        *)
(* CONFIG_USE_SWITCH). The configurations without the suffix _pendsv use   *)
(* TRUE: the switch is in the step, as in the model before Platform. The   *)
(* configurations *_pendsv use FALSE (arch_swap() and PendSV, the default  *)
(* on Cortex-M).                                                           *)
(*                                                                         *)
(* MCOuterLock lets a thread call irq_lock() and irq_unlock() outside a    *)
(* kernel call, up to MCMaxNest nested calls (finding P2-w). Under an      *)
(* outer lock a thread calls only the functions that an ISR can call (the  *)
(* wakes): it does not wait, set a priority or abort a thread              *)
(* (doc/kernel/services/interrupts.rst, "Preventing Interruptions"). The   *)
(* mutant "pend_locked" breaks this rule: a thread waits under the lock.   *)
(*                                                                         *)
(* MCObjs is the set of objects ({o1, o2}, or {o1} for the small runs).    *)
(*                                                                         *)
(* Round B (2026-10-29):                                                   *)
(*                                                                         *)
(* - MCExtra adds the calls of proposal P1, P4 and P5 of the review of the *)
(*   reference fake: a thread writes its swap data before a wait (d1, the  *)
(*   buffer of msgq and mailbox), z_unpend_all() (k_heap_free()), the walk *)
(*   of a mailbox send (stop at the first receiver that wrote d1) and a    *)
(*   msgq wake that keeps the buffer pointer of the waiter. The wakers of  *)
(*   the other calls give no swap data (NoD, see WD).                      *)
(* - MCJoin gives each thread a join queue (the objects j1, j2, j3) and    *)
(*   adds k_thread_join(). An abort then wakes the joiners (finding F14).  *)
(* - MCInit adds z_waitq_init() of an object by a thread: on a wait queue  *)
(*   with waiters, undefined behavior (finding P6-u).                      *)
(*                                                                         *)
(* Sensitivity set (2026-10-30, recommendation 5 of the review): the       *)
(* configurations *_sens_* change only the bounds of a base                *)
(* configuration. A configuration file overrides the definition Threads    *)
(* (Threads = {t1, t2, t3, t4} makes t4 a new model value) and the         *)
(* constant MCObjs ({o1, o2, o3}). With four threads and MCJoin, it also   *)
(* sets JoinQ4 to a new object j4. The configurations *_sym add the        *)
(* symmetry set SymThreadsObjs. The argument for each bound and for the    *)
(* symmetry is in the workspace notes (tla/small-scope.md).                *)
(***************************************************************************)
EXTENDS Integers, FiniteSets
LOCAL INSTANCE TLC

CONSTANTS
    \* @type: THREAD;
    t1,
    \* @type: THREAD;
    t2,
    \* @type: THREAD;
    t3,
    \* @type: OBJ;
    o1,
    \* @type: OBJ;
    o2,
    \* @type: OBJ;
    j1,
    \* @type: OBJ;
    j2,
    \* @type: OBJ;
    j3,
    \* @type: THREAD;
    i1,
    \* @type: CPU;
    c1,
    \* @type: CPU;
    c2,
    \* @type: OBJ;
    NoObj,
    \* @type: THREAD;
    IdleT,
    \* @type: DATA;
    d1,
    \* @type: DATA;
    NoD,
    \* @type: Set(CPU);
    MCCPUS,
    \* @type: Set(Int);
    MCZPrios,
    \* @type: Str;
    MCMutant,
    \* @type: Bool;
    MCIsrPends,
    \* @type: Str;
    MCSetPrioBy,
    \* @type: Bool;
    MCAbort,
    \* @type: Bool;
    MCUseSwitch,
    \* @type: Bool;
    MCOuterLock,
    \* @type: Int;
    MCMaxNest,
    \* @type: Set(OBJ);
    MCObjs,
    \* @type: Bool;
    MCExtra,
    \* @type: Bool;
    MCJoin,
    \* @type: Bool;
    MCInit

\* The variables of Scheduler (see there).
VARIABLES
    \* @type: THREAD -> Str;
    tstate,
    \* @type: THREAD -> Int;
    prio,
    \* @type: CPU -> THREAD;
    cur,
    \* @type: THREAD -> Int;
    swapRet,
    \* @type: THREAD -> DATA;
    swapData,
    \* @type: Str;
    panic,
    \* @type: THREAD -> Int;
    rqStamp,
    \* @type: Bool;
    preemptOk,
    \* @type: THREAD -> Int;
    readySince,
    \* @type: THREAD -> OBJ;
    pendedOn,
    \* @type: THREAD -> Int;
    stamp,
    \* @type: Seq(THREAD);
    tq,
    \* @type: { op: Str, n: Int, cost: Int };
    tqCost,
    \* @type: CPU -> Int;
    irqNest,
    \* @type: CPU -> Bool;
    pendsv

vars == <<tstate, prio, cur, swapRet, swapData, panic, rqStamp, preemptOk, readySince,
          pendedOn, stamp, tq, tqCost, irqNest, pendsv>>

\* The threads. A sensitivity configuration overrides this definition with
\* a value (Threads = {t1, t2} or {t1, t2, t3, t4}). t1 must stay in the
\* set: InWalk and WithRet name it.
Threads == {t1, t2, t3}
\* The objects of the kernel calls (not the join queues).
ObjQs   == MCObjs
\* The join queue of a fourth thread. A configuration with four threads and
\* MCJoin sets it to a new object (JoinQ4 = j4). Without that line, t3 and
\* t4 share j3, and the ASSUME on JoinQ in Scheduler fails.
JoinQ4  == j3
\* The join queue of each thread, if MCJoin.
MCJoinQ == IF MCJoin THEN [t \in Threads |-> CASE t = t1 -> j1 [] t = t2 -> j2 [] t = t3 -> j3
                                                 [] OTHER -> JoinQ4]
           ELSE [t \in Threads |-> NoObj]
Objs    == MCObjs \cup (IF MCJoin THEN {MCJoinQ[t] : t \in Threads} ELSE {})
Isrs    == {i1}
Actors  == Threads \cup Isrs

MCIsrCpu == [i \in Isrs |-> c1]

Sched == INSTANCE Scheduler WITH None <- NoObj, CPUS <- MCCPUS, IsrCpu <- MCIsrCpu,
            Idle <- IdleT, Data <- {d1}, NoData <- NoD, JoinQ <- MCJoinQ,
            Backend <- "DLIST", HeapCapacity <- 0,
            MaxIrqNest <- MCMaxNest, UseSwitch <- MCUseSwitch

\* Zephyr priorities. A configuration file cannot give negative numbers, so
\* it selects a set with MCZPrios <- ZPriosMixed.
\* Mixed: one cooperative (-1) and two preemptible priorities.
ZPriosMixed == {-1, 0, 1}
\* Coop: two cooperative priorities and one preemptible. Each cooperative
\* priority is higher than each preemptible one, so only a second
\* cooperative priority can be higher than a cooperative thread.
ZPriosCoop == {-2, -1, 0}
\* Wide: two cooperative and two preemptible priorities (only the
\* sensitivity configurations *_sens_pw use it).
ZPriosWide == {-2, -1, 0, 1}

\* The model priorities of the Zephyr priorities of the configuration.
Prios == {Sched!FromZephyr(z) : z \in MCZPrios}

\* The swap data that the wakers of WakeStep give: none (NoD). No guard of
\* the scheduler reads the swap data, so it cannot change the result of a
\* property of the scheduler. Since no step resets it (P1), each thread
\* keeps a value, and data from the wakers multiplies the states: the run
\* small grew from 104141 to more than 358000 states with d1 from the
\* wakers. A waker still overwrites the swap data of the woken thread
\* (with NoD). The data d1 comes only from the waiter (SetSwapData, with
\* MCExtra: small_b, reach_b).
WD == NoD

\* The walk wakes each waiter except t1, the data depends on the thread.
\* The walk of k_event_post() does not stop.
InWalk(t)   == t # t1
NoStop(t)   == FALSE
WalkData(t) == WD
\* A mailbox send: the receiver matches if it wrote d1 (its message) to its
\* swap data. The walk stops at the first match and wakes it. The data of
\* the waiter does not change.
MbxMatch(t) == swapData[t] = d1
KeepData(t) == swapData[t]
\* A msgq put that hands over to a waiting get: the waiter keeps its
\* buffer pointer, the waker copies into the buffer.
CopyTo(t)   == <<Sched!OK, swapData[t]>>
\* The object code gives t1 the data WD, the other threads no data.
WithRet(t)  == <<Sched!OK, IF t = t1 THEN WD ELSE NoD>>

Init == \E p0 \in [Threads -> Prios] : Sched!InitState(p0)

-----------------------------------------------------------------------------
(* The calls of the objects. Each one is one critical section.            *)

\* Actor a holds no outer interrupt lock (an ISR never does). Under an
\* outer lock a thread calls only the functions that an ISR can call.
NoOuterLock(a) == a \in Isrs \/ \A c \in MCCPUS : cur[c] = a => irqNest[c] = 0

\* A running thread waits on o.
PendStep ==
    \E a \in Threads, o \in ObjQs, to \in Sched!WaitTimeouts :
        /\ Sched!CanCall(a)
        /\ NoOuterLock(a) \/ MCMutant = "pend_locked"
        /\ Sched!PendCurr(a, o, to)

\* The ISR calls a wait: panic.
IsrPendStep ==
    /\ MCIsrPends
    /\ \E a \in Isrs, o \in ObjQs, to \in Sched!WaitTimeouts : Sched!PendCurr(a, o, to)

\* A wake and z_reschedule(), by a running thread or by the ISR.
WakeStep ==
    \E a \in Actors, o \in ObjQs :
        /\ Sched!CanCall(a)
        /\ \/ Sched!WakeFirst(o, Sched!OK, WD)
           \/ Sched!WakeFirstWith(o, WithRet)
           \/ Sched!WakeAll(o, Sched!EAGAIN, NoD)
           \/ Sched!WakeWalk(o, InWalk, NoStop, WalkData)
        /\ Sched!Release(a, "resched")

\* The calls of round B (MCExtra): a thread writes its swap data before a
\* wait; z_unpend_all() and a reschedule only if it had waiters
\* (k_heap_free()); a mailbox send; a msgq hand-over.
ExtraStep ==
    /\ MCExtra
    /\ \/ \E a \in Threads : Sched!CanCall(a) /\ NoOuterLock(a) /\ Sched!SetSwapData(a, d1)
       \/ \E a \in Actors, o \in ObjQs :
            /\ Sched!CanCall(a)
            /\ \/ /\ Sched!UnpendAll(o)
                  /\ Sched!Release(a, IF Sched!HasWaiters(o) THEN "resched" ELSE "unlock")
               \/ /\ Sched!WakeWalk(o, MbxMatch, MbxMatch, KeepData)
                  /\ Sched!Release(a, "resched")
               \/ /\ Sched!WakeFirstWith(o, CopyTo)
                  /\ Sched!Release(a, "resched")

\* k_thread_join() by a running thread (MCJoin).
JoinStep ==
    /\ MCJoin
    /\ \E a, t \in Threads, to \in Sched!WaitTimeouts :
        /\ Sched!CanCall(a)
        /\ NoOuterLock(a)
        /\ Sched!Join(a, t, to)

\* The init function of an object (k_sem_init() and more) by a running
\* thread, with z_waitq_init() (MCInit). No lock, no reschedule.
InitStep ==
    /\ MCInit
    /\ \E a \in Threads, o \in ObjQs :
        /\ Sched!CanCall(a)
        /\ NoOuterLock(a)
        /\ Sched!WaitqInit(o)

\* Mutant: a wake that ends with k_spin_unlock().
MissedReschedStep ==
    /\ MCMutant = "missed_resched"
    /\ \E a \in Threads, o \in ObjQs :
        /\ Sched!CanCall(a)
        /\ Sched!WakeFirst(o, Sched!OK, WD)
        /\ Sched!Release(a, "unlock")

\* Mutant: z_sched_wake_thread_locked() on the best waiter, without
\* z_try_abort_timeout() first.
WakeNoCancelStep ==
    /\ MCMutant = "wake_no_cancel"
    /\ \E a \in Actors, o \in ObjQs :
        /\ Sched!CanCall(a)
        /\ Sched!HasWaiters(o)
        /\ LET t == Sched!WQ!Best(o) IN
           /\ Sched!WakeThreadLocked(t, Sched!OK, swapData[t])
           /\ UNCHANGED <<tq, tqCost>>
        /\ Sched!Release(a, "resched")

\* The calls of k_thread_priority_set(t, p) by a that the configuration
\* allows.
PrioTarget(a, t, p) ==
    \/ MCSetPrioBy = "any"
    \/ MCSetPrioBy = "self" /\ a = t
    \/ MCSetPrioBy = "other" /\ a # t
    \/ MCSetPrioBy = "other_same" /\ a # t /\ ~Sched!Running(t) /\ p = prio[t]

-----------------------------------------------------------------------------

\* After a panic the system does nothing. This step is not a deadlock.
Halted == panic # "none" /\ UNCHANGED vars

Next ==
    \/ panic = "none" /\ (PendStep \/ IsrPendStep \/ WakeStep
                          \/ MissedReschedStep \/ WakeNoCancelStep
                          \/ ExtraStep \/ JoinStep \/ InitStep)
    \/ \E c \in MCCPUS : Sched!ThreadTimeout(c) \/ Sched!Preempt(c) \/ Sched!PendSV(c)
    \/ MCAbort /\ \E a \in Actors, t \in Threads : NoOuterLock(a) /\ Sched!Abort(a, t)
    \/ \E a \in Actors, t \in Threads, p \in Prios :
          PrioTarget(a, t, p) /\ NoOuterLock(a) /\ Sched!SetPrio(a, t, p)
    \/ \E t \in Threads : Sched!Resume(t)
    \/ MCOuterLock /\ \E a \in Threads : Sched!IrqLockCall(a) \/ Sched!IrqUnlockCall(a)
    \/ Halted

Spec == Init /\ [][Next]_vars /\ Sched!Fairness

\* The symmetry set of the configurations *_sym. Only for a configuration
\* without liveness properties and without MCJoin. The reasons:
\*
\* - Init, Next and the properties do not name a thread other than t1
\*   (InWalk, WithRet) and do not name an object. MCJoinQ names each
\*   thread, so a configuration with MCJoin is not symmetric.
\* - Each CHOOSE over threads in the library has exactly one witness while
\*   CurUnique, RqStampsNormal, ArmedOnce and RanksDistinct hold, so its
\*   value does not depend on the names. A *_sym configuration checks
\*   these invariants.
\* - TLC can miss a liveness violation under symmetry.
\*
\* SymThreadsObjs is the product of the two groups: each permutation of the
\* threads other than t1 together with each permutation of the objects.
SymThreadsObjs ==
    {[x \in (Threads \ {t1}) \cup MCObjs |-> IF x \in MCObjs THEN q[x] ELSE p[x]] :
        p \in Permutations(Threads \ {t1}), q \in Permutations(MCObjs)}

-----------------------------------------------------------------------------
(* Properties of the library module *)

Inv_TypeOK          == Sched!TypeOK
Inv_P_NoPendSVWithSwitch == Sched!PF!NoPendSVWithSwitch
\* @expected violation (configuration pend_locked_pendsv)
Inv_P_PendingIsUnlocked  == Sched!PF!PendingIsUnlocked
\* @expected violation (configuration pend_locked)
Prop_NoSwitchWhileLocked == Sched!NoSwitchWhileLocked
Inv_CurUnique       == Sched!CurUnique
Inv_CurIsReady      == Sched!CurIsReady
Inv_PendingIsQueued == Sched!PendingIsQueued
Inv_ArmedArePending == Sched!ArmedArePending
Inv_DeadIsInert     == Sched!DeadIsInert
\* @expected violation (configurations smp_rule: the IPI comes later;
\* coop_rule: finding P7-c; p2_rule: finding P2-w)
Inv_RunRuleHolds    == Sched!RunRuleHolds
\* @expected violation (configuration isr_pend)
Inv_NoPanic         == Sched!NoPanic
\* @expected violation (configuration p6_init, finding P6-u)
Inv_NoUndefined     == Sched!NoUndefined
Inv_WQ_StampsNormal == Sched!WQ!StampsNormal
Inv_WQ_RanksDistinct == Sched!WQ!RanksDistinct
Inv_TO_ArmedOnce    == Sched!TO!ArmedOnce
Inv_TO_CostBounded  == Sched!TO!CostBounded
Inv_RqStampsNormal  == Sched!RqStampsNormal

Live_TimedWaitEnds    == Sched!TimedWaitEnds
Live_SelectionHappens == Sched!SelectionHappens

-----------------------------------------------------------------------------
(* The normative properties of the library module (one CPU).              *)

\* @expected violation (configurations f14_join*, finding F14)
Inv_PreemptibleRunsHighest == Sched!PreemptibleRunsHighest
Prop_SwitchSelectsHighest  == Sched!SwitchSelectsHighest
\* @expected violation (configuration p7_tie, finding P7-a)
Prop_TieGoesToLongestReady == Sched!TieGoesToLongestReady
\* @expected violation (configurations p7_coop and p7_abort, findings P7-b
\* and P7-c)
Prop_CoopKeepsCpu          == Sched!CoopKeepsCpu
\* @expected violation (configurations p2_window, finding P2-w)
Prop_UnlockPreempts        == Sched!UnlockPreempts
\* @expected violation (configuration gap_coop_pendsv, candidate finding
\* SW-1)
Prop_BlockedLosesCpu       == Sched!BlockedLosesCpu

-----------------------------------------------------------------------------
(* Reachability probes. Each one is the negation of a situation that the   *)
(* model must reach. TLC must report each one as violated.                 *)

\* A woken thread preempts its waker and returns the value of the waker.
Reach_WokenRunsWithOk ==
    ~(\E c \in MCCPUS : cur[c] \in Threads /\ swapRet[cur[c]] = Sched!OK)
\* A thread returns -EAGAIN after its timeout.
Reach_TimeoutRuns ==
    ~(\E c \in MCCPUS : cur[c] \in Threads /\ swapRet[cur[c]] = Sched!EAGAIN
                        /\ tqCost.op = "expire")
\* A cooperative thread keeps the CPU while a thread with a higher priority
\* is ready.
Reach_CoopKeepsCpu ==
    ~(\E c \in MCCPUS, t \in Threads :
        /\ cur[c] \in Threads
        /\ Sched!Cooperative(prio[cur[c]])
        /\ tstate[t] = "ready" /\ ~Sched!Running(t)
        /\ prio[t] > prio[cur[c]])
\* All threads wait: the idle thread runs.
Reach_AllWait == ~(\A t \in Threads : tstate[t] = "pending")
\* All waiters of o2 are woken in one step.
Reach_WakeAllTwo == ~(tqCost.op = "cancel_set" /\ tqCost.cost = 2)
\* Two CPUs run a thread (configuration smp).
Reach_TwoRun == ~(\A c \in MCCPUS : cur[c] \in Threads)
\* arch_swap(): an ISR runs in the gap before PendSV and makes a thread
\* ready (configuration reach_pendsv).
Reach_IsrInGap ==
    ~(\E c \in MCCPUS :
        pendsv[c] /\ cur[c] \in Threads /\ tstate[cur[c]] = "ready" /\ swapRet[cur[c]] = Sched!OK)
\* An outer interrupt lock with two nested calls (configuration
\* reach_lock).
Reach_NestedLock == ~(\E c \in MCCPUS : irqNest[c] = 2)
\* A thread wakes a waiter with a higher priority under an outer lock, and
\* keeps the CPU (configuration reach_lock).
Reach_WakeUnderLock ==
    ~(\E c \in MCCPUS :
        /\ irqNest[c] > 0
        /\ cur[c] \in Threads
        /\ \E t \in Threads : tstate[t] = "ready" /\ prio[t] > prio[cur[c]])
\* Round B (configuration reach_b): a thread that a msgq or mailbox wake
\* ended keeps the data that it wrote before its wait (P1). The other
\* wakes give NoD.
Reach_WaiterDataKept ==
    ~(\E t \in Threads : tstate[t] = "ready" /\ swapRet[t] = Sched!OK /\ swapData[t] = d1)
\* A thread returns -EAGAIN after its timeout and still has the data that
\* it wrote before the wait (P1: no step resets the swap data).
Reach_TimeoutKeepsData ==
    ~(\E c \in MCCPUS : cur[c] \in Threads /\ swapRet[cur[c]] = Sched!EAGAIN
                        /\ swapData[cur[c]] = d1 /\ tqCost.op = "expire")
\* z_unpend_all() wakes two timed waiters in one step: they keep -EAGAIN
\* and their swap data (WakeAll in this model gives NoD, the mailbox walk
\* wakes one waiter).
Reach_UnpendAllTwo ==
    ~(/\ tqCost.op = "cancel_set" /\ tqCost.cost = 2
      /\ \E a, b \in Threads : a # b
           /\ tstate[a] = "ready" /\ tstate[b] = "ready"
           /\ swapRet[a] = Sched!EAGAIN /\ swapRet[b] = Sched!EAGAIN
           /\ swapData[a] = d1)
\* A joiner is ready with the return value 0 after the abort (configuration
\* join).
Reach_JoinerWoken ==
    ~(\E t \in Threads : tstate[t] = "dead" /\ \E u \in Threads : u # t /\ tstate[u] = "ready"
                                                  /\ swapRet[u] = Sched!OK)
=============================================================================
