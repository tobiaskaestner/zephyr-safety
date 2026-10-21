------------------------------ MODULE Timeout ------------------------------
(***************************************************************************)
(* The timeout queue of the kernel (kernel/timeout.c).                     *)
(*                                                                         *)
(* The model has no clock. The queue is the sequence of armed entries in   *)
(* the order of their expiry. A new entry goes to any position, because    *)
(* its deadline relative to the other deadlines is not known. Only the     *)
(* head expires. Thus each expiry order is reachable, and the position of  *)
(* an insertion gives its cost.                                            *)
(*                                                                         *)
(* The cost of each operation is a step counter (tqCost). It is the model  *)
(* side of the bound of draft requirement DRAFT-BND-18 (workspace notes,   *)
(* bounds-inventory.md): with CONFIG_TIMEOUT_BACKEND_DLIST, an insertion  *)
(* takes at most T + 1 steps, T = the number of armed timeouts.           *)
(*                                                                         *)
(* The backends (constant Backend):                                        *)
(*                                                                         *)
(* - "DLIST": kernel/timeout_list.h, the default. A sorted delta list. An  *)
(*   insertion walks from the head: linear in T. A removal takes 1 step.   *)
(* - "MINHEAP": kernel/timeout_minheap.h (EXPERIMENTAL). A binary heap     *)
(*   with CONFIG_TIMEOUT_HEAP_MAX_ENTRIES entries. An insertion and a      *)
(*   removal are logarithmic in T. A full heap panics (k_panic()).         *)
(*                                                                         *)
(* The backends BUCKET and WHEEL are not in the model yet.                 *)
(*                                                                         *)
(* A thread wait uses the atomic form of the expiry (Expire). The two-step *)
(* form for the timer object comes later (roadmap step 4).                 *)
(***************************************************************************)
EXTENDS Naturals, Sequences, FiniteSets

CONSTANTS
    \* The objects that can be armed: threads with a finite timeout, later
    \* timers.
    \* @type: Set(ENTRY);
    Entries,
    \* @type: Str;
    Backend,
    \* CONFIG_TIMEOUT_HEAP_MAX_ENTRIES. Used only with Backend = "MINHEAP".
    \* @type: Int;
    HeapCapacity

VARIABLES
    \* The armed entries, earliest expiry first.
    \* @type: Seq(ENTRY);
    tq,
    \* The last operation on the queue and its cost in steps (loop
    \* iterations of the backend). n is the number of armed entries before
    \* the operation.
    \* @type: [op: Str, n: Int, cost: Int];
    tqCost

ASSUME Backend \in {"DLIST", "MINHEAP"}
ASSUME HeapCapacity \in Nat

-----------------------------------------------------------------------------
(* Helpers *)

Range(s) == {s[i] : i \in DOMAIN s}

\* The smallest k with 2^k >= n + 1: the height of a binary heap with n + 1
\* entries.
RECURSIVE Pow2(_)
Pow2(k) == IF k = 0 THEN 1 ELSE 2 * Pow2(k - 1)
Log2Ceil(n) == CHOOSE k \in 0..n : Pow2(k) >= n + 1 /\ (k = 0 \/ Pow2(k - 1) < n + 1)

\* Sequence s with element e inserted at position i (1..Len(s) + 1).
InsertAt(s, i, e) == SubSeq(s, 1, i - 1) \o <<e>> \o SubSeq(s, i, Len(s))

\* Sequence s without element e.
RemoveElem(s, e) == SelectSeq(s, LAMBDA x : x # e)

NoCost == [op |-> "none", n |-> 0, cost |-> 0]

-----------------------------------------------------------------------------
(* Queries *)

\* The entries that are armed.
Armed == Range(tq)

\* The entry that expires next. Defined only if tq # <<>>.
First == Head(tq)

\* The heap is full. An insertion now panics (MINHEAP only).
Full == Backend = "MINHEAP" /\ Len(tq) >= HeapCapacity

\* The cost of an insertion at position i into a queue with n entries.
\* DLIST: the loop of z_timeout_q_insert() stops at the first entry with a
\* later deadline (i iterations), or runs over all n entries (append).
InsertCost(i, n) ==
    IF Backend = "DLIST" THEN IF i <= n THEN i ELSE n
    ELSE Log2Ceil(n)

\* The cost of a removal from a queue with n entries.
RemoveCost(n) == IF Backend = "DLIST" THEN 1 ELSE Log2Ceil(n)

\* The bound of each operation: the backend must not do more steps.
\* DLIST: T + 1 steps (DRAFT-BND-18). MINHEAP: the heap height.
CostBound(op, n) ==
    IF Backend = "DLIST" THEN (IF op = "insert" THEN n + 1 ELSE 1)
    ELSE Log2Ceil(n) + 1

-----------------------------------------------------------------------------
(* Changes. Each one sets tq' and tqCost'.                                 *)

\* z_add_timeout() with a finite timeout: entry e is armed at position i.
\* The caller must handle Full first (the real code panics).
\* @c-function z_add_timeout
\* @c-function z_timeout_q_insert
Insert(e, i) ==
    /\ e \notin Armed
    /\ ~Full
    /\ i \in 1..(Len(tq) + 1)
    /\ tq' = InsertAt(tq, i, e)
    /\ tqCost' = [op |-> "insert", n |-> Len(tq), cost |-> InsertCost(i, Len(tq))]

\* An insertion at a position that the deadline selects (not known).
InsertAny(e) == \E i \in 1..(Len(tq) + 1) : Insert(e, i)

\* z_abort_timeout(): entry e is no longer armed (a give or a flush won
\* the race against the expiry). Without effect if e is not armed.
\* @c-function z_abort_timeout
\* @c-function z_timeout_q_remove
Cancel(e) ==
    IF e \in Armed
      THEN /\ tq' = RemoveElem(tq, e)
           /\ tqCost' = [op |-> "remove", n |-> Len(tq), cost |-> RemoveCost(Len(tq))]
      ELSE UNCHANGED <<tq, tqCost>>

\* sys_clock_announce(): the first entry expires (atomic form). The caller
\* runs the handler of First in the same step.
\* @c-function sys_clock_announce
Expire ==
    /\ tq # <<>>
    /\ tq' = Tail(tq)
    /\ tqCost' = [op |-> "expire", n |-> Len(tq), cost |-> RemoveCost(Len(tq))]

-----------------------------------------------------------------------------
(* Properties *)

\* @kind invariant
TypeOK ==
    /\ tq \in Seq(Entries)
    /\ tqCost.op \in {"none", "insert", "remove", "expire"}
    /\ tqCost.n \in Nat
    /\ tqCost.cost \in Nat

\* An entry is armed at most once.
\* @kind invariant
ArmedOnce == Cardinality(Armed) = Len(tq)

\* Each operation stays within the bound of its backend.
\* @kind invariant
CostBounded == tqCost.cost <= CostBound(tqCost.op, tqCost.n)

\* The heap never holds more than its capacity.
\* @kind invariant
HeapWithinCapacity == Backend = "MINHEAP" => Len(tq) <= HeapCapacity

=============================================================================
