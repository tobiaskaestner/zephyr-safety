----------------------------- MODULE MCTimeout -----------------------------
(***************************************************************************)
(* Model of lib/Timeout.tla alone. An environment arms, cancels and        *)
(* expires entries in any order. TLC checks the cost bound of each         *)
(* operation for the backend of the configuration.                         *)
(*                                                                         *)
(* An insertion into a full heap (MINHEAP) panics in the real code         *)
(* (z_add_timeout() calls k_panic()). The model has this step: PanicFull   *)
(* sets panicked, and then the system stops. The invariant NoPanic states  *)
(* the environment assumption "never more armed entries than               *)
(* HeapCapacity". A configuration with HeapCapacity < 3 shows that the     *)
(* assumption is necessary (expected violation). Later the Scheduler       *)
(* module owns panic.                                                      *)
(***************************************************************************)
EXTENDS Naturals, Sequences, FiniteSets

CONSTANTS e1, e2, e3, MCBackend, MCHeapCapacity

VARIABLES tq, tqCost, panicked

vars == <<tq, tqCost, panicked>>

Entries == {e1, e2, e3}

TO == INSTANCE Timeout WITH Backend <- MCBackend, HeapCapacity <- MCHeapCapacity

Init ==
    /\ tq = <<>>
    /\ tqCost = TO!NoCost
    /\ panicked = FALSE

\* z_add_timeout() on a full heap: k_panic(). The queue does not change.
PanicFull ==
    /\ \E e \in Entries \ TO!Armed : TO!Full
    /\ panicked' = TRUE
    /\ UNCHANGED <<tq, tqCost>>

\* After a panic, the system does nothing. This step is not a deadlock.
Halted ==
    /\ panicked
    /\ UNCHANGED vars

Next ==
    \/ /\ ~panicked
       /\ \/ \E e \in Entries : TO!InsertAny(e)
          \/ \E e \in TO!Armed : TO!Cancel(e)
          \/ TO!Expire
       /\ UNCHANGED panicked
    \/ ~panicked /\ PanicFull
    \/ Halted

Spec == Init /\ [][Next]_vars

Inv_TypeOK             == TO!TypeOK
Inv_ArmedOnce          == TO!ArmedOnce
Inv_CostBounded        == TO!CostBounded
Inv_HeapWithinCapacity == TO!HeapWithinCapacity

\* The environment assumption: no insertion into a full heap.
\* @expected violation (configuration minheap_full)
Inv_NoPanic            == ~panicked

\* Reachability probes (each one must be violated).
\* The worst case of the list: an insertion that walks over all entries.
Reach_DlistWorstCase == ~(tqCost.op = "insert" /\ tqCost.n = 2 /\ tqCost.cost = 2)
\* Each entry can expire first.
Reach_LastArmedFirst == ~(Len(tq) = 3 /\ tq[1] = e3)
\* The heap becomes full.
Reach_HeapFull       == ~TO!Full
=============================================================================
