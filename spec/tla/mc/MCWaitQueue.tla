---------------------------- MODULE MCWaitQueue ----------------------------
(***************************************************************************)
(* Model of lib/WaitQueue.tla alone. An environment adds and removes       *)
(* waiters and changes priorities in any order. TLC checks that the order  *)
(* rule holds in each reachable state, and that each change keeps the      *)
(* order of arrival.                                                       *)
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

Inv_TypeOK       == WQ!TypeOK
Inv_StampsNormal == WQ!StampsNormal
Inv_OrderIsTotal == WQ!OrderIsTotal
Inv_BestIsHead   == WQ!BestIsHead

-----------------------------------------------------------------------------
(* Action properties *)

\* A new waiter comes after each waiter of the same object with the same
\* priority (FIFO among equal priorities).
AddIsFifo ==
    [][\A t \in Threads, o \in Objs :
         (pendedOn[t] = NoObj /\ pendedOn'[t] = o) =>
            \A u \in WQ!W(o) : prio[u] = prio[t] => stamp'[u] < stamp'[t]]_vars

\* A change keeps the order of arrival of the threads that wait before and
\* after it, except for the thread whose priority changes.
KeepsArrivalOrder ==
    [][\A a, b \in WQ!Waiting \cap {t \in Threads : pendedOn'[t] # NoObj} :
         (prio'[a] = prio[a] /\ prio'[b] = prio[b]) =>
            ((stamp[a] < stamp[b]) <=> (stamp'[a] < stamp'[b]))]_vars

\* After a priority change of a waiter, it comes after the other waiters of
\* its object with the new priority.
PrioChangeGoesLast ==
    [][\A t \in Threads :
         (t \in WQ!Waiting /\ prio'[t] # prio[t]) =>
            \A u \in WQ!W(pendedOn[t]) \ {t} : prio'[u] = prio'[t] => stamp'[u] < stamp'[t]]_vars

-----------------------------------------------------------------------------
(* Reachability probes. Each one is the negation of a situation that the   *)
(* model must reach. TLC must report each one as violated.                 *)

Reach_ThreeWaitOnOne    == \A o \in Objs : Cardinality(WQ!W(o)) < 3
Reach_TwoObjectsInUse   == ~(WQ!W(o1) # {} /\ WQ!W(o2) # {})
Reach_LateHigherIsFirst == ~(\E o \in Objs : \E a, b \in WQ!W(o) :
                                stamp[a] > stamp[b] /\ WQ!Best(o) = a)

=============================================================================
