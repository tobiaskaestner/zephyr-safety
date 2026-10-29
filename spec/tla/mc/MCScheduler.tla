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
(***************************************************************************)
EXTENDS Integers, FiniteSets

CONSTANTS t1, t2, t3, o1, o2, i1, c1, c2, NoObj, IdleT, d1, NoD,
          MCCPUS, MCZPrios, MCMutant, MCIsrPends, MCSetPrioBy, MCAbort,
          MCUseSwitch, MCOuterLock, MCMaxNest, MCObjs

VARIABLES tstate, prio, cur, swapRet, swapData, panic, rqStamp, preemptOk, readySince,
          pendedOn, stamp, tq, tqCost, irqNest, pendsv

vars == <<tstate, prio, cur, swapRet, swapData, panic, rqStamp, preemptOk, readySince,
          pendedOn, stamp, tq, tqCost, irqNest, pendsv>>

Threads == {t1, t2, t3}
Objs    == MCObjs
Isrs    == {i1}
Actors  == Threads \cup Isrs

MCIsrCpu == [i \in Isrs |-> c1]

Sched == INSTANCE Scheduler WITH None <- NoObj, CPUS <- MCCPUS, IsrCpu <- MCIsrCpu,
            Idle <- IdleT, Data <- {d1}, NoData <- NoD,
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

\* Actor a holds no outer interrupt lock (an ISR never does). Under an
\* outer lock a thread calls only the functions that an ISR can call.
NoOuterLock(a) == a \in Isrs \/ \A c \in MCCPUS : cur[c] = a => irqNest[c] = 0

\* A running thread waits on o.
PendStep ==
    \E a \in Threads, o \in Objs, to \in Sched!WaitTimeouts :
        /\ Sched!CanCall(a)
        /\ NoOuterLock(a) \/ MCMutant = "pend_locked"
        /\ Sched!PendCurr(a, o, to)

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
           /\ Sched!QueueReady({t})
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
                          \/ MissedReschedStep \/ WakeNoCancelStep)
    \/ \E c \in MCCPUS : Sched!ThreadTimeout(c) \/ Sched!Preempt(c) \/ Sched!PendSV(c)
    \/ MCAbort /\ \E a \in Actors, t \in Threads : NoOuterLock(a) /\ Sched!Abort(a, t)
    \/ \E a \in Actors, t \in Threads, p \in Prios :
          PrioTarget(a, t, p) /\ NoOuterLock(a) /\ Sched!SetPrio(a, t, p)
    \/ \E t \in Threads : Sched!Resume(t)
    \/ MCOuterLock /\ \E a \in Threads : Sched!IrqLockCall(a) \/ Sched!IrqUnlockCall(a)
    \/ Halted

Spec == Init /\ [][Next]_vars /\ Sched!Fairness

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
Inv_WQ_StampsNormal == Sched!WQ!StampsNormal
Inv_WQ_RanksDistinct == Sched!WQ!RanksDistinct
Inv_TO_ArmedOnce    == Sched!TO!ArmedOnce
Inv_TO_CostBounded  == Sched!TO!CostBounded
Inv_RqStampsNormal  == Sched!RqStampsNormal

Live_TimedWaitEnds    == Sched!TimedWaitEnds
Live_SelectionHappens == Sched!SelectionHappens

-----------------------------------------------------------------------------
(* The normative properties of the library module (one CPU).              *)

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
=============================================================================
