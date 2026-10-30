---------------------------- MODULE APScheduler ----------------------------
(***************************************************************************)
(* Inductive check of Scheduler!PendingIsQueued with Apalache, on the     *)
(* next-state relation of mc/MCScheduler (the library module has no       *)
(* Next). CInitSmall and CInitDefault give the constants of the           *)
(* configurations small and default of MCScheduler: 3 threads, 1 ISR,    *)
(* 1 CPU, the mixed priorities, CONFIG_USE_SWITCH=y, abort, no outer      *)
(* lock, no join queue; small: 1 object, no priority change; default: 2   *)
(* objects, priority changes by each actor.                                *)
(*                                                                         *)
(* The three obligations (tools/run_apalache.sh, apalache/expected.txt):  *)
(*                                                                         *)
(*   1. Init => IndInv          --init=Init   --inv=IndInv --length=0      *)
(*   2. IndInv /\ Next => IndInv'                                          *)
(*                              --init=IndInv --inv=IndInv --length=1      *)
(*   3. IndInv => Inv           --init=IndInv --inv=Inv    --length=0      *)
(*                                                                         *)
(* The module extends MCScheduler and does not instantiate it: Apalache   *)
(* 0.62.4 rejects an instance of MCScheduler ("used before it is          *)
(* defined"), because MCScheduler gives the constant Threads of Scheduler *)
(* as an operator, and Scheduler gives it to WaitQueue (three levels of   *)
(* INSTANCE).                                                              *)
(*                                                                         *)
(* The values of the model values are strings in the form of the          *)
(* uninterpreted types of Apalache ("t1_OF_THREAD").                      *)
(***************************************************************************)
EXTENDS MCScheduler, Sequences

\* The constants that all checked configurations share.
CInitBase ==
    /\ t1 = "t1_OF_THREAD" /\ t2 = "t2_OF_THREAD" /\ t3 = "t3_OF_THREAD"
    /\ o1 = "o1_OF_OBJ" /\ o2 = "o2_OF_OBJ"
    /\ j1 = "j1_OF_OBJ" /\ j2 = "j2_OF_OBJ" /\ j3 = "j3_OF_OBJ"
    /\ i1 = "i1_OF_THREAD" /\ c1 = "c1_OF_CPU" /\ c2 = "c2_OF_CPU"
    /\ NoObj = "none_OF_OBJ" /\ IdleT = "idle_OF_THREAD"
    /\ d1 = "d1_OF_DATA" /\ NoD = "nod_OF_DATA"
    /\ MCCPUS = {"c1_OF_CPU"}
    /\ MCZPrios = ZPriosMixed
    /\ MCMutant = "none"
    /\ MCIsrPends = FALSE
    /\ MCAbort = TRUE
    /\ MCUseSwitch = TRUE
    /\ MCOuterLock = FALSE
    /\ MCMaxNest = 1
    /\ MCExtra = FALSE
    /\ MCJoin = FALSE
    /\ MCInit = FALSE

\* The constants of MCScheduler_small: one object, no priority change.
CInitSmall ==
    /\ CInitBase
    /\ MCSetPrioBy = "none"
    /\ MCObjs = {"o1_OF_OBJ"}

\* The constants of MCScheduler_default: two objects, priority changes by
\* each actor.
CInitDefault ==
    /\ CInitBase
    /\ MCSetPrioBy = "any"
    /\ MCObjs = {"o1_OF_OBJ", "o2_OF_OBJ"}

\* The disjuncts of MCScheduler!Next in groups, for separate runs of
\* obligation 2 (a run of all 487 transitions of Next with the constants
\* of default did not end in its time limit). NextGroups is Next:
\* the same disjuncts, with "panic = none" distributed over the first
\* group.
NextPend    == panic = "none" /\ (PendStep \/ IsrPendStep)
NextWake    == panic = "none" /\ (WakeStep \/ MissedReschedStep \/ WakeNoCancelStep)
NextOther   == panic = "none" /\ (ExtraStep \/ JoinStep \/ InitStep)
NextCpu     == \E c \in MCCPUS : Sched!ThreadTimeout(c) \/ Sched!Preempt(c) \/ Sched!PendSV(c)
NextAbort   == MCAbort /\ \E a \in Actors, t \in Threads : NoOuterLock(a) /\ Sched!Abort(a, t)
NextPrio    == \E a \in Actors, t \in Threads, p \in Prios :
                  PrioTarget(a, t, p) /\ NoOuterLock(a) /\ Sched!SetPrio(a, t, p)
NextResume  == \E t \in Threads : Sched!Resume(t)
NextLock    == MCOuterLock /\ \E a \in Threads : Sched!IrqLockCall(a) \/ Sched!IrqUnlockCall(a)
NextHalted  == Halted

NextGroups ==
    \/ NextPend \/ NextWake \/ NextOther \/ NextCpu \/ NextAbort \/ NextPrio
    \/ NextResume \/ NextLock \/ NextHalted

\* The initial predicate of MCScheduler in a form for Apalache: the
\* conjuncts of Scheduler!InitState(prio) with prio \in [Threads -> Prios]
\* (Init is \E p0 : InitState(p0), and InitState(p0) has prio = p0), and
\* with RqOrders written as a condition on rqStamp. Apalache 0.62.4 accepts
\* neither the \E of Init nor rqStamp \in RqOrders ("Trying to expand a set
\* of functions"). The text is a copy, so TLC checks that InitAP and Init
\* have the same states (APScheduler_init_eq.cfg, APScheduler_init_eq2.cfg,
\* 162 states each on 2026-10-30). run_tlc.sh does not run apalache/. By
\* hand, from apalache/:
\*   java -DTLA-Library=../lib:../objects:../mc -cp $TLA2TOOLS tlc2.TLC
\*        -workers 1 -fp 0 -config APScheduler_init_eq.cfg APScheduler.tla
InitAP ==
    /\ prio \in [Threads -> Prios]
    /\ rqStamp \in [Threads -> 0..Cardinality(Threads)]
    /\ IF Sched!UP
         THEN \A a, b \in Threads : rqStamp[a] >= 1 /\ (a # b => rqStamp[a] # rqStamp[b])
         ELSE \A t \in Threads : rqStamp[t] = 0
    /\ tstate = [t \in Threads |-> "ready"]
    /\ swapRet = [t \in Threads |-> Sched!NoRet]
    /\ swapData = [t \in Threads |-> NoD]
    /\ panic = "none"
    /\ readySince = rqStamp
    /\ preemptOk = FALSE
    /\ pendedOn = [t \in Threads |-> NoObj]
    /\ stamp = [t \in Threads |-> 0]
    /\ tq = <<>>
    /\ tqCost = Sched!TO!NoCost
    /\ cur \in [MCCPUS -> Threads \cup {IdleT}]
    /\ \A c \in MCCPUS : cur[c] \in Sched!Choices(c, tstate, prio, cur, rqStamp, TRUE)
    /\ \A c, d \in MCCPUS : c # d /\ cur[c] # IdleT => cur[c] # cur[d]
    /\ Sched!PF!InitPlatform

\* For the TLC check of InitAP: no step, so the reachable states are the
\* initial states.
NoStep == UNCHANGED vars

N == Cardinality(Threads)

\* The type part of the strengthening, in the form that Apalache needs for
\* --init=IndInv: each variable has a finite set of values. The timeout
\* queue is a sequence of at most N threads.
TypeDom ==
    /\ tstate \in [Threads -> Sched!ThreadStates]
    /\ prio \in [Threads -> Prios]
    /\ cur \in [MCCPUS -> Threads \cup {IdleT}]
    /\ swapRet \in [Threads -> {Sched!OK, Sched!EAGAIN, Sched!NoRet}]
    /\ swapData \in [Threads -> {d1, NoD}]
    /\ panic \in {"none", "undefined"} \cup Sched!PanicCauses
    /\ rqStamp \in [Threads -> 0..N]
    /\ preemptOk \in BOOLEAN
    /\ readySince \in [Threads -> 0..N]
    /\ pendedOn \in [Threads -> Objs \cup {NoObj}]
    /\ stamp \in [Threads -> 0..N]
    /\ \E n \in 0..N, a, b, c \in Threads : tq = SubSeq(<<a, b, c>>, 1, n)
    /\ tqCost \in [op : {"none", "insert", "remove", "cancel_set", "expire"},
                   n : 0..N, cost : 0..(N * (N + 1))]
    /\ irqNest \in [MCCPUS -> 0..MCMaxNest]
    /\ pendsv \in [MCCPUS -> BOOLEAN]

\* The invariant to prove.
Inv == Inv_PendingIsQueued

\* Candidate 0: the invariant and the types only.
IndInv0 ==
    /\ TypeDom
    /\ Inv_PendingIsQueued

\* Candidate 1: a thread that executes is ready (CTI of candidate 0: a
\* pending thread is the current thread and returns from a wait, Resume).
IndInv1 ==
    /\ IndInv0
    /\ Inv_CurIsReady

\* Candidate 2: the run queue positions and the wait queue stamps are
\* normal (CTI of candidate 1: two ready threads with the same position.
\* The CHOOSE of RunqBest then has no witness, and Apalache gives a value
\* outside Threads, where TLC stops with an error). StampsNormal is not
\* from a CTI: it gives the CHOOSE of WaitQueue!Best one witness, for the
\* same reason.
IndInv2 ==
    /\ IndInv1
    /\ Inv_RqStampsNormal
    /\ Inv_WQ_StampsNormal

\* Candidate 3: each thread is armed at most once (CTI of candidate 2: a
\* timeout queue with a thread twice grows to 4 entries, outside TypeDom).
IndInv3 ==
    /\ IndInv2
    /\ Inv_TO_ArmedOnce

\* The inductive invariant for PendingIsQueued.
IndInv == IndInv3

=============================================================================
