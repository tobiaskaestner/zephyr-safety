---------------------------- MODULE TimeoutTest ----------------------------
(***************************************************************************)
(* Example tests of lib/Timeout.tla. Each test evaluates a query or a      *)
(* helper on a chosen queue and compares the value with the expected       *)
(* value (see WaitQueueTest for the method). The cost tests fix the        *)
(* numbers that the invariant CostBounded of MCTimeout compares.           *)
(***************************************************************************)
EXTENDS Naturals, Sequences, FiniteSets, TLC

NoCostRec == [op |-> "none", n |-> 0, cost |-> 0]

\* Timeout with the backend b, the heap capacity cap and the queue q.
At(b, cap, q) == INSTANCE Timeout WITH Entries <- {"e1", "e2", "e3"}, Backend <- b,
                    HeapCapacity <- cap, tq <- q, tqCost <- NoCostRec

\* The helpers and the costs do not depend on the queue.
D == INSTANCE Timeout WITH Entries <- {"e1", "e2", "e3"}, Backend <- "DLIST",
        HeapCapacity <- 0, tq <- <<>>, tqCost <- NoCostRec
H == INSTANCE Timeout WITH Entries <- {"e1", "e2", "e3"}, Backend <- "MINHEAP",
        HeapCapacity <- 2, tq <- <<>>, tqCost <- NoCostRec

\* The condition of the CHOOSE in Timeout!Log2Ceil.
Log2Cond(n, k) == 2^k >= n + 1 /\ (k = 0 \/ 2^(k - 1) < n + 1)

\* A test: the value got must be the value want.
Check(name, got, want) == Assert(got = want, <<name, "got", got, "want", want>>)

-----------------------------------------------------------------------------
(* The tests *)

\* The helpers. Log2Ceil(n) is the smallest k with 2^k >= n + 1.
TestHelpers ==
    /\ Check("Log2Ceil 0..8",  [i \in 1..9 |-> D!Log2Ceil(i - 1)], <<0, 1, 2, 2, 3, 3, 3, 3, 4>>)
    /\ Check("Log2Ceil max",   D!Log2Ceil(2^D!MaxHeight - 1), D!MaxHeight)
    \* The CHOOSE of Log2Ceil has exactly one witness (design note, section
    \* Apalache). Checked for small n and for the largest n.
    /\ Check("Log2Ceil one witness",
             {n \in (0..1023) \cup {2^D!MaxHeight - 2, 2^D!MaxHeight - 1} :
                 Cardinality({k \in 0..D!MaxHeight : Log2Cond(n, k)}) # 1},
             {})
    /\ Check("InsertAt first", D!InsertAt(<<"b", "c">>, 1, "a"), <<"a", "b", "c">>)
    /\ Check("InsertAt mid",   D!InsertAt(<<"a", "c">>, 2, "b"), <<"a", "b", "c">>)
    /\ Check("InsertAt last",  D!InsertAt(<<"a", "b">>, 3, "c"), <<"a", "b", "c">>)
    /\ Check("RemoveElem",     D!RemoveElem(<<"a", "b", "c">>, "b"), <<"a", "c">>)

\* The queries. Only a MINHEAP can be full.
TestQueries ==
    /\ Check("First",            At("DLIST", 0, <<"e2", "e1">>)!First, "e2")
    /\ Check("Armed",            At("DLIST", 0, <<"e2", "e1">>)!Armed, {"e1", "e2"})
    /\ Check("Full minheap",     At("MINHEAP", 2, <<"e1", "e2">>)!Full, TRUE)
    /\ Check("not Full minheap", At("MINHEAP", 2, <<"e1">>)!Full, FALSE)
    /\ Check("not Full dlist",   At("DLIST", 0, <<"e1", "e2">>)!Full, FALSE)

\* The costs. DLIST: the insert loop passes i entries, or all n entries for
\* an append. MINHEAP: the heap height, for each operation.
TestCosts ==
    /\ Check("dlist insert empty", D!InsertCost(1, 0), 0)
    /\ Check("dlist insert first", D!InsertCost(1, 3), 1)
    /\ Check("dlist insert last",  D!InsertCost(3, 3), 3)
    /\ Check("dlist append",       D!InsertCost(4, 3), 3)
    /\ Check("dlist remove",       D!RemoveCost(3), 1)
    /\ Check("dlist bound insert", D!CostBound("insert", 3), 4)
    /\ Check("dlist bound remove", D!CostBound("remove", 3), 1)
    /\ Check("heap insert",        H!InsertCost(1, 3), 2)
    /\ Check("heap remove",        H!RemoveCost(3), 2)
    /\ Check("heap bound",         H!CostBound("insert", 3), 3)
    \* A cancellation of k <= n entries: at most n removals.
    /\ Check("dlist bound cancel_set", D!CostBound("cancel_set", 3), 3)
    /\ Check("heap bound cancel_set",  H!CostBound("cancel_set", 3), 9)

-----------------------------------------------------------------------------
(* The spec: one state, no deadlock. Its only purpose is the run of the    *)
(* invariants above.                                                       *)

VARIABLE unused
Init == unused = 0
Next == UNCHANGED unused
=============================================================================
