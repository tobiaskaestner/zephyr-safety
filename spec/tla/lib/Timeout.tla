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
    Entries

\* The backend of the timeout queue: "DLIST" or "MINHEAP" (see the module
\* header). This is a Kconfig option of kind 2: each model configuration
\* fixes the value. CONFIG_TIMEOUT_BACKEND_WHEEL is in scope (decision Q3
\* of the unit map: kind 2, it does not keep the firing order of the
\* timeouts of one tick) and is not in the model yet. BUCKET is out of
\* scope.
\* @kconfig CONFIG_TIMEOUT_BACKEND_DLIST CONFIG_TIMEOUT_BACKEND_MINHEAP CONFIG_TIMEOUT_BACKEND_WHEEL
\* @type: Str;
CONSTANT Backend

\* CONFIG_TIMEOUT_HEAP_MAX_ENTRIES. Used only with Backend = "MINHEAP". A
\* Kconfig option of kind 3: a heap that is too small panics, so a safe
\* system must have enough entries (the condition of use NoPanic of
\* mc/MCTimeout; configuration minheap_full).
\* @kconfig CONFIG_TIMEOUT_HEAP_MAX_ENTRIES
\* @type: Int;
CONSTANT HeapCapacity

VARIABLES
    \* The armed entries, earliest expiry first.
    \* @type: Seq(ENTRY);
    tq,
    \* The last operation on the queue and its cost in steps (loop
    \* iterations of the backend). n is the number of armed entries before
    \* the operation.
    \* @type: { op: Str, n: Int, cost: Int };
    tqCost

ASSUME Backend \in {"DLIST", "MINHEAP"}
ASSUME HeapCapacity \in Nat

-----------------------------------------------------------------------------
(* Helpers *)

\* @type: Seq(a) => Set(a);
Range(s) == {s[i] : i \in DOMAIN s}

\* The largest heap height that Log2Ceil computes. A heap with this height
\* holds 2^MaxHeight - 1 entries. The bound is a constant, because Apalache
\* accepts only ranges with constant bounds.
\* @type: Int;
MaxHeight == 16

\* Log2Ceil is defined for each size of the heap.
ASSUME Backend = "MINHEAP" => HeapCapacity < 2^MaxHeight

\* The smallest k with 2^k >= n + 1: the height of a binary heap with n + 1
\* entries. Exactly one k satisfies the condition for each n in
\* 0..(2^MaxHeight - 1) (mc/TimeoutTest checks this).
\* @type: Int => Int;
Log2Ceil(n) == CHOOSE k \in 0..MaxHeight : 2^k >= n + 1 /\ (k = 0 \/ 2^(k - 1) < n + 1)

\* Sequence s with element e inserted at position i (1..Len(s) + 1).
\* @type: (Seq(a), Int, a) => Seq(a);
InsertAt(s, i, e) == SubSeq(s, 1, i - 1) \o <<e>> \o SubSeq(s, i, Len(s))

\* Sequence s without element e.
\* @type: (Seq(a), a) => Seq(a);
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
\* DLIST: T + 1 steps (DRAFT-BND-18). MINHEAP: the heap height. A
\* cancellation of k entries does at most n removals (k <= n).
CostBound(op, n) ==
    LET one == IF Backend = "DLIST" THEN (IF op = "insert" THEN n + 1 ELSE 1)
               ELSE Log2Ceil(n) + 1
    IN  IF op = "cancel_set" THEN n * one ELSE one

-----------------------------------------------------------------------------
(* Changes. Each one sets tq' and tqCost'.                                 *)

\* z_add_timeout() with a finite timeout: entry e is armed at position i.
\* The caller must handle Full first (the real code panics).
\* @kind action
\* @c-function z_add_timeout
\* @c-function z_timeout_q_insert
Insert(e, i) ==
    /\ e \notin Armed
    /\ ~Full
    /\ i \in 1..(Len(tq) + 1)
    /\ tq' = InsertAt(tq, i, e)
    /\ tqCost' = [op |-> "insert", n |-> Len(tq), cost |-> InsertCost(i, Len(tq))]

\* An insertion at a position that the deadline selects (not known). The
\* range has a constant bound (Apalache). Insert selects the valid
\* positions 1..(Len(tq) + 1).
\* @kind action
InsertAny(e) == \E i \in 1..(Cardinality(Entries) + 1) : Insert(e, i)

\* z_abort_timeout(): entry e is no longer armed (a give or a flush won
\* the race against the expiry). Without effect if e is not armed.
\* @kind action
\* @c-function z_abort_timeout
\* @c-function z_timeout_q_remove
Cancel(e) ==
    IF e \in Armed
      THEN /\ tq' = RemoveElem(tq, e)
           /\ tqCost' = [op |-> "remove", n |-> Len(tq), cost |-> RemoveCost(Len(tq))]
      ELSE UNCHANGED <<tq, tqCost>>

\* The entries in S are no longer armed, in one critical section (a wake of
\* all waiters). The code calls z_abort_timeout() for each entry. The cost
\* is k removals from a queue with n entries: exact for DLIST, an upper
\* bound for MINHEAP (the heap becomes smaller after each removal). Without
\* effect if no entry of S is armed.
\* @kind action
\* @c-function z_abort_timeout
CancelSet(S) ==
    LET k == Cardinality(S \cap Armed) IN
    IF k > 0
      THEN /\ tq' = SelectSeq(tq, LAMBDA x : x \notin S)
           /\ tqCost' = [op |-> "cancel_set", n |-> Len(tq), cost |-> k * RemoveCost(Len(tq))]
      ELSE UNCHANGED <<tq, tqCost>>

\* sys_clock_announce(): the first entry expires (atomic form). The caller
\* runs the handler of First in the same step.
\* @kind action
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
    /\ tqCost.op \in {"none", "insert", "remove", "cancel_set", "expire"}
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
\* @kconfig CONFIG_TIMEOUT_BACKEND_MINHEAP
HeapWithinCapacity == Backend = "MINHEAP" => Len(tq) <= HeapCapacity

=============================================================================
