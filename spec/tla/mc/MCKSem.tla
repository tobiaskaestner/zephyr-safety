------------------------------- MODULE MCKSem -------------------------------
(***************************************************************************)
(* Model of objects/KSem.tla: the semaphore on the scheduler contract,     *)
(* with the most general environment (KSem!Next). One CPU,                 *)
(* CONFIG_USE_SWITCH=y, the timeout backend DLIST, no outer interrupt lock *)
(* (MaxIrqNest 0), one ISR. The configuration gives the threads, the       *)
(* semaphores, the arguments of k_sem_init(), the priorities and the       *)
(* Kconfig options.                                                        *)
(*                                                                         *)
(* The views: ViewNoObs is the state without obs. Each property of KSem    *)
(* reads obs only as obs' in an action property, which TLC checks on each  *)
(* step it generates, so the view is sound for them. The probes and the    *)
(* liveness configurations use no view.                                    *)
(***************************************************************************)
EXTENDS Integers, FiniteSets, Sequences

CONSTANTS t1, t2, t3, s1, s2, i1, c1, NoObj, IdleT, NoD,
          MCThreads, MCSems, MCInitArgs, MCUMax, MCInitPrios, MCEnvPrios,
          MCRuntimeChecks, MCPoll, MCReInit, MCIsrWaits

VARIABLES tstate, prio, cur, swapRet, swapData, panic, rqStamp, preemptOk, readySince,
          pendedOn, stamp, tq, tqCost, irqNest, pendsv, r, req, tokens, obs

MCIsrs == {i1}

K == INSTANCE KSem WITH Threads <- MCThreads, Objs <- MCSems, None <- NoObj,
        Isrs <- MCIsrs, IsrCpu <- [i \in MCIsrs |-> c1], MaxIrqNest <- 0, Idle <- IdleT,
        Data <- {}, NoData <- NoD, JoinQ <- [t \in MCThreads |-> NoObj],
        CPUS <- {c1}, UseSwitch <- TRUE, Backend <- "DLIST", HeapCapacity <- 0,
        InitArgs <- MCInitArgs, UMax <- MCUMax, InitPrios <- MCInitPrios,
        EnvPrios <- MCEnvPrios, RuntimeChecks <- MCRuntimeChecks, Poll <- MCPoll,
        ReInit <- MCReInit, IsrWaits <- MCIsrWaits

vars == K!vars

Spec == K!Spec
\* The safety part only: no fairness (the safety configurations).
SafetySpec == K!Init /\ [][K!Next]_vars

ViewNoObs == K!stateVars

\* Sets for the configurations (a .cfg file has no negative numbers).
Threads2 == {t1, t2}
Threads3 == {t1, t2, t3}
Sems1 == {s1}
Sems2 == {s1, s2}
\* Model priorities: a greater value is a higher priority; 0 and -1 are the
\* preemptible Zephyr priorities 0 and 1.
PriosEqual == {0}
PriosTwo   == {0, -1}
\* k_sem_init(): limit 2 with the counts 0 and 2, and the two arguments that
\* CHECKIF() rejects (count above the limit, limit 0).
ArgsDefault == {<<0, 2>>, <<2, 2>>, <<3, 2>>, <<0, 0>>}
ArgsSmall   == {<<0, 1>>, <<1, 1>>}
ArgsChecks  == {<<0, 1>>, <<2, 1>>, <<0, 0>>}

-----------------------------------------------------------------------------
(* Properties of the library modules *)

Inv_TypeOK               == K!TypeOK
Inv_ReqIsWait            == K!ReqIsWait
Inv_PendingIsQueued      == K!S!PendingIsQueued
Inv_ArmedArePending      == K!S!ArmedArePending
Inv_DeadIsInert          == K!S!DeadIsInert
Inv_CurIsReady           == K!S!CurIsReady
Inv_RunRuleHolds         == K!S!RunRuleHolds
Inv_CountLeLimit         == K!CountLeLimit
Inv_NoWaitWhileAvailable == K!NoWaitWhileAvailable
Inv_TokenConservation    == K!TokenConservation
\* @expected violation (configuration isr_waits)
Inv_NoPanic              == K!NoPanic
\* @expected violation (configuration reinit, finding P6-u)
Inv_NoUndefined          == K!NoUndefined

Prop_CallsHoldLock         == K!CallsHoldLock
Prop_GiveHandsOverOrCounts == K!GiveHandsOverOrCounts
Prop_GiveWakesHighest      == K!GiveWakesHighest
Prop_TakeResult            == K!TakeResult
Prop_ResetWakesAll         == K!ResetWakesAll
Prop_WaitResult            == K!WaitResult
\* @expected violation (configuration poll, design observation 4)
Prop_PollSignalMeansAvailable == K!PollSignalMeansAvailable

\* @expected violation (configuration live_prio: starvation)
Live_WaiterServedIfGives == K!WaiterServedIfGives
Live_TimedWaitEnds       == K!S!TimedWaitEnds

-----------------------------------------------------------------------------
(* Reachability probes. Each one is the negation of a situation that the   *)
(* model must reach. TLC must report each one as violated.                 *)

Reach_AllThreadsWait   == ~(\A t \in MCThreads : pendedOn[t] = s1)
Reach_IsrGivesToWaiter == ~(obs.actor = i1 /\ obs.op = "give" /\ obs.woken # {})
Reach_IsrTakeBusy      == ~(obs.actor = i1 /\ obs.op = "take" /\ obs.ret = K!EBUSY)
Reach_ResetWakesTwo    == ~(obs.op = "flush" /\ Cardinality(obs.woken) >= 2)
Reach_TimeoutReturns   == ~(obs.op = "resume" /\ obs.ret = K!EAGAIN /\ tqCost.op = "expire")
Reach_ReturnEagain     == ~(obs.op = "resume" /\ obs.ret = K!EAGAIN)
Reach_ReturnOk         == ~(obs.op = "resume" /\ obs.ret = K!OK)
Reach_GiveAtLimit      == ~(obs.op = "give" /\ obs.woken = {} /\ r[s1].count = r[s1].limit
                            /\ r[s1].limit = 2)
Reach_InitRejected     == ~(obs.op = "init" /\ obs.ret = K!EINVAL)
Reach_WokenPreempts    == ~(obs.op = "give" /\ obs.woken # {} /\ cur[c1] \in obs.woken)
\* With CONFIG_POLL: a give signals the poll events, and a polling thread
\* becomes ready (the release is z_reschedule()).
Reach_PollResched      == ~(obs.op = "give" /\ obs.woken = {} /\ Len(obs.calls) = 4
                            /\ obs.calls[4].fn = "z_reschedule")
=============================================================================
