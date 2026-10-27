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
(***************************************************************************)
EXTENDS Integers, FiniteSets

CONSTANTS t1, t2, t3, o1, o2, i1, c1, c2, NoObj, IdleT, d1, NoD,
          MCCPUS, MCZPrios, MCMutant, MCIsrPends

VARIABLES tstate, prio, cur, swapRet, swapData, panic, pendedOn, stamp, tq, tqCost

vars == <<tstate, prio, cur, swapRet, swapData, panic, pendedOn, stamp, tq, tqCost>>

Threads == {t1, t2, t3}
Objs    == {o1, o2}
Isrs    == {i1}
Actors  == Threads \cup Isrs

MCIsrCpu == [i \in Isrs |-> c1]

Sched == INSTANCE Scheduler WITH None <- NoObj, CPUS <- MCCPUS, IsrCpu <- MCIsrCpu,
            Idle <- IdleT, Data <- {d1}, NoData <- NoD,
            Backend <- "DLIST", HeapCapacity <- 0

\* Zephyr priorities. A configuration file cannot give negative numbers, so
\* it selects a set with MCZPrios <- ZPriosMixed.
\* Mixed: one cooperative (-1) and two preemptible priorities.
ZPriosMixed == {-1, 0, 1}
\* Coop: two cooperative priorities and one preemptible. Each cooperative
\* priority is higher than each preemptible one, so only a second
\* cooperative priority can be higher than a cooperative thread.
ZPriosCoop == {-2, -1, 0}

\* The model priorities of the Zephyr priorities of the configuration.
Prios == {Sched!FromZephyr(z) : z \in MCZPrios}

\* The walk wakes each waiter except t1, the data depends on the thread.
InWalk(t)   == t # t1
WalkData(t) == d1
\* The object code gives t1 the data d1, the other threads no data.
WithRet(t)  == <<Sched!OK, IF t = t1 THEN d1 ELSE NoD>>

Init == \E p0 \in [Threads -> Prios] : Sched!InitState(p0)

-----------------------------------------------------------------------------
(* The calls of the objects. Each one is one critical section.            *)

\* A running thread waits on o.
PendStep ==
    \E a \in Threads, o \in Objs, to \in Sched!WaitTimeouts :
        Sched!CanCall(a) /\ Sched!PendCurr(a, o, to)

\* The ISR calls a wait: panic.
IsrPendStep ==
    /\ MCIsrPends
    /\ \E a \in Isrs, o \in Objs, to \in Sched!WaitTimeouts : Sched!PendCurr(a, o, to)

\* A wake and z_reschedule(), by a running thread or by the ISR.
WakeStep ==
    \E a \in Actors, o \in Objs :
        /\ Sched!CanCall(a)
        /\ \/ Sched!WakeFirst(o, Sched!OK, d1)
           \/ Sched!WakeFirstWith(o, WithRet)
           \/ Sched!WakeAll(o, Sched!EAGAIN, NoD)
           \/ Sched!WakeWalk(o, InWalk, WalkData)
        /\ Sched!Release(a, "resched")

\* Mutant: a wake that ends with k_spin_unlock().
MissedReschedStep ==
    /\ MCMutant = "missed_resched"
    /\ \E a \in Threads, o \in Objs :
        /\ Sched!CanCall(a)
        /\ Sched!WakeFirst(o, Sched!OK, d1)
        /\ Sched!Release(a, "unlock")

\* Mutant: z_sched_wake_thread_locked() on the best waiter, without
\* z_abort_timeout() first.
WakeNoCancelStep ==
    /\ MCMutant = "wake_no_cancel"
    /\ \E a \in Actors, o \in Objs :
        /\ Sched!CanCall(a)
        /\ Sched!HasWaiters(o)
        /\ LET t == Sched!WQ!Best(o) IN
           /\ Sched!WQ!Remove(t)
           /\ tstate' = [tstate EXCEPT ![t] = "ready"]
           /\ swapRet' = [swapRet EXCEPT ![t] = Sched!OK]
           /\ UNCHANGED <<prio, swapData, panic, tq, tqCost>>
        /\ Sched!Release(a, "resched")

-----------------------------------------------------------------------------

\* After a panic the system does nothing. This step is not a deadlock.
Halted == panic # "none" /\ UNCHANGED vars

Next ==
    \/ panic = "none" /\ (PendStep \/ IsrPendStep \/ WakeStep
                          \/ MissedReschedStep \/ WakeNoCancelStep)
    \/ \E c \in MCCPUS : Sched!ThreadTimeout(c) \/ Sched!Preempt(c)
    \/ \E a \in Actors, t \in Threads : Sched!Abort(a, t)
    \/ \E a \in Actors, t \in Threads, p \in Prios : p # prio[t] /\ Sched!SetPrio(a, t, p)
    \/ \E t \in Threads : Sched!Resume(t)
    \/ Halted

Spec == Init /\ [][Next]_vars /\ Sched!Fairness

-----------------------------------------------------------------------------
(* Properties of the library module *)

Inv_TypeOK          == Sched!TypeOK
Inv_CurUnique       == Sched!CurUnique
Inv_CurIsReady      == Sched!CurIsReady
Inv_PendingIsQueued == Sched!PendingIsQueued
Inv_ArmedArePending == Sched!ArmedArePending
Inv_DeadIsInert     == Sched!DeadIsInert
\* @expected violation (configuration smp_rule: the IPI comes later)
Inv_RunRuleHolds    == Sched!RunRuleHolds
\* @expected violation (configuration isr_pend)
Inv_NoPanic         == Sched!NoPanic
Inv_WQ_StampsNormal == Sched!WQ!StampsNormal
Inv_WQ_RanksDistinct == Sched!WQ!RanksDistinct
Inv_TO_ArmedOnce    == Sched!TO!ArmedOnce
Inv_TO_CostBounded  == Sched!TO!CostBounded

Live_TimedWaitEnds    == Sched!TimedWaitEnds
Live_SelectionHappens == Sched!SelectionHappens

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
=============================================================================
