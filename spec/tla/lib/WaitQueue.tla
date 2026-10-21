----------------------------- MODULE WaitQueue -----------------------------
(***************************************************************************)
(* The wait queues of all kernel objects.                                  *)
(*                                                                         *)
(* A thread waits on at most one object. The model keeps the order rule of *)
(* the Zephyr wait queue, not its data structure: a higher priority comes  *)
(* first, and threads with the same priority keep their order of arrival.  *)
(* Both CONFIG_WAITQ_SIMPLE (z_priq_simple_add()) and                      *)
(* CONFIG_WAITQ_SCALABLE (z_priq_rb_add()) give this order.                *)
(*                                                                         *)
(* The stamp of a waiter is its position in the order of arrival over all  *)
(* waiters. Each action that changes the waiters renumbers the stamps to   *)
(* 1..N (N = the number of waiters). Thus the state space stays finite,    *)
(* and two states that differ only in absolute stamp values are one state. *)
(*                                                                         *)
(* The module that uses this one declares the variables and instantiates  *)
(* it (INSTANCE WaitQueue). prio belongs to the Scheduler. This module     *)
(* reads it and does not change it.                                        *)
(***************************************************************************)
EXTENDS Naturals, FiniteSets, Sequences

CONSTANTS
    \* @type: Set(THREAD);
    Threads,
    \* @type: Set(OBJ);
    Objs,
    \* The value of pendedOn for a thread that does not wait.
    \* @type: OBJ;
    None

VARIABLES
    \* The object that each thread waits on, or None.
    \* @type: THREAD -> OBJ;
    pendedOn,
    \* The position of each waiter in the order of arrival, 0 if it does
    \* not wait.
    \* @type: THREAD -> Int;
    stamp,
    \* The priority of each thread. A greater value is a higher priority.
    \* (Zephyr uses the reverse: a lower number is a higher priority. The
    \* Scheduler converts at one place.)
    \* @type: THREAD -> Int;
    prio

ASSUME None \notin Objs

-----------------------------------------------------------------------------
(* Queries *)

\* The waiters of object o.
W(o) == {t \in Threads : pendedOn[t] = o}

\* All threads that wait on an object.
Waiting == {t \in Threads : pendedOn[t] # None}

\* The order rule of a wait queue: a comes before b. Higher priority first,
\* then the order of arrival. No requirement states this rule for all
\* objects yet (see README.rst, open points).
\* @kind definition
Before(a, b) ==
    \/ prio[a] > prio[b]
    \/ /\ prio[a] = prio[b]
       /\ stamp[a] < stamp[b]

\* The position of waiter t in the wait queue of o (1 is the head).
Rank(o, t) == Cardinality({u \in W(o) : Before(u, t)}) + 1

\* The waiter that a wake of o selects first. Defined only if W(o) # {}.
\* @c-function z_priq_simple_best
\* @c-function z_priq_rb_best
Best(o) == CHOOSE t \in W(o) : Rank(o, t) = 1

\* The wait queue of o as a sequence, head first. This is the view of the
\* trace records and of the generated tests.
Ordered(o) == [i \in 1..Cardinality(W(o)) |-> CHOOSE t \in W(o) : Rank(o, t) = i]

-----------------------------------------------------------------------------
(* Stamps *)

\* The stamps after the waiters become ws, with the arrival order given by
\* s. Each waiter gets its rank in the arrival order, the other threads get
\* 0.
Renumber(s, ws) ==
    [t \in Threads |-> IF t \in ws
                         THEN Cardinality({u \in ws : s[u] < s[t]}) + 1
                         ELSE 0]

\* A stamp that is greater than the stamp of each waiter.
NextStamp == Cardinality(Waiting) + 1

-----------------------------------------------------------------------------
(* Changes. Each one sets pendedOn' and stamp'. An action of the user      *)
(* module uses at most one of them, so that the primed variables have one  *)
(* value.                                                                  *)

\* Thread t starts to wait on o. It comes after all waiters of o with the
\* same or a higher priority.
\* @c-function z_priq_simple_add
\* @c-function z_priq_rb_add
Add(t, o) ==
    /\ pendedOn[t] = None
    /\ pendedOn' = [pendedOn EXCEPT ![t] = o]
    /\ stamp' = Renumber([stamp EXCEPT ![t] = NextStamp], Waiting \cup {t})

\* The threads in S stop to wait (wake, timeout, abort, flush).
\* @c-function z_priq_simple_remove
\* @c-function z_priq_rb_remove
RemoveSet(S) ==
    /\ S \subseteq Waiting
    /\ pendedOn' = [t \in Threads |-> IF t \in S THEN None ELSE pendedOn[t]]
    /\ stamp' = Renumber(stamp, Waiting \ S)

Remove(t) == RemoveSet({t})

\* The priority of waiter t changes. z_thread_prio_set() removes the thread
\* and adds it again, so it comes after the other waiters with its new
\* priority. The caller sets prio'.
\* @c-function z_thread_prio_set
Restamp(t) ==
    /\ t \in Waiting
    /\ UNCHANGED pendedOn
    /\ stamp' = Renumber([stamp EXCEPT ![t] = NextStamp], Waiting)

-----------------------------------------------------------------------------
(* Properties *)

\* @kind invariant
TypeOK ==
    /\ pendedOn \in [Threads -> Objs \cup {None}]
    /\ stamp \in [Threads -> 0..Cardinality(Threads)]

\* The stamps of the waiters are 1..N, and each stamp is unique. A thread
\* that does not wait has the stamp 0.
\* @kind invariant
StampsNormal ==
    /\ {stamp[t] : t \in Waiting} = 1..Cardinality(Waiting)
    /\ \A t \in Threads \ Waiting : stamp[t] = 0

\* Before is a strict total order on the waiters of each object. Thus Best
\* and Ordered are defined, and the wake order is fixed.
\* @kind invariant
OrderIsTotal ==
    \A o \in Objs : \A a, b \in W(o) :
        /\ ~Before(a, a)
        /\ a # b => (Before(a, b) \/ Before(b, a))
        /\ Before(a, b) => ~Before(b, a)

\* The head of the ordered view is the waiter that a wake selects.
\* @kind invariant
BestIsHead ==
    \A o \in Objs : W(o) # {} => Ordered(o)[1] = Best(o)

=============================================================================
