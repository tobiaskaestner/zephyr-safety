------------------------------- MODULE MCKSem -------------------------------
(* Model values and constant definitions for TLC runs of KSem.tla. *)
EXTENDS KSem

CONSTANTS t1, t2, t3, t4

MCThreads3     == {t1, t2, t3}
MCThreads4     == {t1, t2, t3, t4}
MCPrioEqual    == [t \in Threads |-> 0]
\* t1 has the highest priority, t3 the lowest
MCPrioDistinct == (t1 :> 0) @@ (t2 :> 1) @@ (t3 :> 2)
\* Limit 2: valid arguments, and the two invalid cases that CHECKIF() rejects
MCInitArgs     == {<<0, 2>>, <<2, 2>>, <<3, 2>>, <<0, 0>>}
\* Limit 3, for the larger model
MCInitArgs3    == {<<0, 3>>, <<3, 3>>, <<4, 3>>, <<0, 0>>}

\* State view without the ghost variable tokens. The ghost does not change
\* the other variables, so this view is sound for every property that does
\* not use tokens. Without runtime checks, the ghost has no bound (each
\* give above the limit adds a token that the API view does not count).
ViewNoGhost == <<initialized, count, limit, waitq, pc, tmo, swapRet, obs>>

(* Reachability probes. Each one is the negation of a situation that the
   model must reach. TLC must report each one as violated (run with
   -continue). If a probe holds, the model is vacuous for this situation. *)
Reach_AllThreadsWait   == Len(waitq) < 3
Reach_IsrGivesToWaiter == ~(obs.actor = Isr /\ obs.op = "give" /\ obs.woken # {})
Reach_IsrTakeBusy      == ~(obs.actor = Isr /\ obs.op = "take" /\ obs.ret = EBUSY)
Reach_ResetWakesTwo    == ~(obs.op = "reset" /\ Cardinality(obs.woken) >= 2)
Reach_TimeoutFires     == ~(obs.op = "timeout")
Reach_ReturnEagain     == ~(obs.op = "take_return" /\ obs.ret = EAGAIN)
Reach_ReturnOk         == ~(obs.op = "take_return" /\ obs.ret = OK)
Reach_GiveAtLimit      == ~(obs.op = "give" /\ obs.woken = {} /\ count = limit /\ limit = 2)
Reach_InitRejected     == ~(obs.op = "init" /\ obs.ret = EINVAL)
Reach_PollResched      == ~(obs.op = "give" /\ obs.poll > 0 /\ obs.release = "resched")
=============================================================================
