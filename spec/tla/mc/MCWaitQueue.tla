---------------------------- MODULE MCWaitQueue ----------------------------
(***************************************************************************)
(* Model of lib/WaitQueue.tla alone. An environment adds and removes       *)
(* waiters and changes priorities in any order. TLC checks the invariants  *)
(* and the action properties of the library module.                        *)
(***************************************************************************)
EXTENDS Naturals, FiniteSets

CONSTANTS t1, t2, t3, o1, o2, NoObj

\* The three priorities of the model.
Prios == {1, 2, 3}

VARIABLES pendedOn, stamp, prio

vars == <<pendedOn, stamp, prio>>

Threads == {t1, t2, t3}
Objs    == {o1, o2}

WQ == INSTANCE WaitQueue WITH None <- NoObj

Init ==
    /\ pendedOn = [t \in Threads |-> NoObj]
    /\ stamp = [t \in Threads |-> 0]
    /\ prio \in [Threads -> Prios]

AddStep ==
    \E t \in Threads, o \in Objs : WQ!Add(t, o) /\ UNCHANGED prio

RemoveStep ==
    \E S \in SUBSET WQ!Waiting : S # {} /\ WQ!RemoveSet(S) /\ UNCHANGED prio

PrioStep ==
    \E t \in Threads, p \in Prios :
        /\ p # prio[t]
        /\ prio' = [prio EXCEPT ![t] = p]
        /\ IF t \in WQ!Waiting THEN WQ!Restamp(t) ELSE UNCHANGED <<pendedOn, stamp>>

Next == AddStep \/ RemoveStep \/ PrioStep

Spec == Init /\ [][Next]_vars

-----------------------------------------------------------------------------
(* Invariants of the library module *)

Inv_TypeOK        == WQ!TypeOK
Inv_StampsNormal  == WQ!StampsNormal
Inv_OrderIsTotal  == WQ!OrderIsTotal
Inv_BestIsHead    == WQ!BestIsHead
Inv_RanksDistinct == WQ!RanksDistinct

-----------------------------------------------------------------------------
(* Action properties of the library module *)

Prop_AddIsFifo          == WQ!AddIsFifo
Prop_KeepsArrivalOrder  == WQ!KeepsArrivalOrder
Prop_PrioChangeGoesLast == WQ!PrioChangeGoesLast

-----------------------------------------------------------------------------
(* Reachability probes. Each one is the negation of a situation that the   *)
(* model must reach. TLC must report each one as violated.                 *)

Reach_ThreeWaitOnOne    == \A o \in Objs : Cardinality(WQ!W(o)) < 3
Reach_TwoObjectsInUse   == ~(WQ!W(o1) # {} /\ WQ!W(o2) # {})
Reach_LateHigherIsFirst == ~(\E o \in Objs : \E a, b \in WQ!W(o) :
                                stamp[a] > stamp[b] /\ WQ!Best(o) = a)

=============================================================================
