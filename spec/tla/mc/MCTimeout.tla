----------------------------- MODULE MCTimeout -----------------------------
(***************************************************************************)
(* Model of lib/Timeout.tla alone. An environment arms, cancels and        *)
(* expires entries in any order. TLC checks the cost bound of each         *)
(* operation for the backend of the configuration.                         *)
(***************************************************************************)
EXTENDS Naturals, Sequences, FiniteSets

CONSTANTS e1, e2, e3, MCBackend, MCHeapCapacity

VARIABLES tq, tqCost

vars == <<tq, tqCost>>

Entries == {e1, e2, e3}

TO == INSTANCE Timeout WITH Backend <- MCBackend, HeapCapacity <- MCHeapCapacity

Init ==
    /\ tq = <<>>
    /\ tqCost = TO!NoCost

\* A full heap panics in the real code. The model stops the insertion.
Next ==
    \/ \E e \in Entries : ~TO!Full /\ TO!InsertAny(e)
    \/ \E e \in TO!Armed : TO!Cancel(e)
    \/ TO!Expire

Spec == Init /\ [][Next]_vars

Inv_TypeOK             == TO!TypeOK
Inv_ArmedOnce          == TO!ArmedOnce
Inv_CostBounded        == TO!CostBounded
Inv_HeapWithinCapacity == TO!HeapWithinCapacity

\* Reachability probes (each one must be violated).
\* The worst case of the list: an insertion that walks over all entries.
Reach_DlistWorstCase == ~(tqCost.op = "insert" /\ tqCost.n = 2 /\ tqCost.cost = 2)
\* Each entry can expire first.
Reach_LastArmedFirst == ~(Len(tq) = 3 /\ tq[1] = e3)
\* The heap becomes full.
Reach_HeapFull       == ~TO!Full
=============================================================================
