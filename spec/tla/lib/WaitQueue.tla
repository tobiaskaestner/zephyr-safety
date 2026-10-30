----------------------------- MODULE WaitQueue -----------------------------
(***************************************************************************)
(* The wait queues of all kernel objects.                                  *)
(*                                                                         *)
(* A thread waits on at most one object. The model keeps the order rule of *)
(* the Zephyr wait queue, not its data structure: a higher priority comes  *)
(* first, and threads with the same priority keep their order of arrival.  *)
(* Both CONFIG_WAITQ_SIMPLE (z_priq_simple_add()) and                      *)
(* CONFIG_WAITQ_SCALABLE (z_priq_rb_add()) give this order. These options  *)
(* are of Kconfig kind 1: the module covers both values, and the unit      *)
(* tests of the wait queue check each backend. One visible difference is   *)
(* not in this module: k_event_post() wakes the matched waiters in the     *)
(* reverse walk order with CONFIG_WAITQ_SCALABLE (Scheduler!WakeWalk; the  *)
(* run queue order of threads that become ready in one step is free).      *)
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
EXTENDS Naturals, FiniteSets, Apalache

CONSTANTS
    \* @type: Set(THREAD);
    Threads,
    \* @type: Set(OBJ);
    Objs,
    \* The value of pendedOn for a thread that does not wait.
    \* @type: OBJ;
    None,
    \* The value "no thread" of Head and WalkStop, and the filler of Ordered
    \* after the last waiter. Not a thread. Scheduler sets it to Idle.
    \* @type: THREAD;
    NoThread

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
ASSUME NoThread \notin Threads

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
\* Exactly one waiter has the rank 1 (invariants BestIsHead, RanksDistinct).
\* @c-function z_priq_simple_best
\* @c-function z_priq_rb_best
Best(o) == CHOOSE t \in W(o) : Rank(o, t) = 1

\* The wait queue of o as a sequence, head first. This is the view of the
\* trace records and of the generated tests. Exactly one waiter has the
\* rank i, for each i (invariant RanksDistinct). Apalache does not accept a
\* range with a bound that depends on the state. Thus the function has the
\* constant domain 1..Cardinality(Threads), with NoThread after the last
\* waiter, and FunAsSeq (module Apalache) cuts it to the waiters. The value
\* is the sequence [i \in 1..Cardinality(W(o)) |-> ...] of the ranks.
Ordered(o) ==
    LET n == Cardinality(W(o))
    IN  FunAsSeq([i \in 1..Cardinality(Threads) |->
                     IF i <= n THEN CHOOSE t \in W(o) : Rank(o, t) = i ELSE NoThread],
                 n, Cardinality(Threads))

\* z_waitq_head() and z_waitq_head_locked() (wait_q.h:50-53, 93-96,
\* 100-117): the first waiter of o, or NoThread if no thread waits. The two
\* functions differ only in the lock: z_waitq_head() takes the scheduler
\* lock, which matters only on SMP. Users at Zephyr 770fdef1567:
\*
\* - the priority inheritance of the mutex: the best waiter of each mutex
\*   that the owner holds (mutex.c:157);
\* - the checks "no waiter" of the cleanup functions of the stack
\*   (stack.c:94, 99), the message queue (msg_q.c:137, 142) and the timer
\*   (timer.c:181, 186), and of sem_destroy() of POSIX
\*   (subsys/portability/posix/options/semaphore.c:94);
\* - the loops "until the queue is empty" of z_unpend_all() and of the
\*   static unpend_all() (sched.c:810-812, 832-834);
\* - the expiry of a timer, which wakes only the first waiter of
\*   k_timer_status_sync() (timer.c:147, a single call and not a loop:
\*   finding F2);
\* - later: the trace hook of the unit tests (roadmap step 2.2), which
\*   needs a name for the call.
\*
\* The module does not extend Sequences, so that the name Head is free.
\* The module Apalache instantiates Sequences as LOCAL, so it does not
\* export Head either.
\* @c-function z_waitq_head
\* @c-function z_waitq_head_locked
Head(o) == IF W(o) = {} THEN NoThread ELSE Best(o)

\* The waiters of o that z_sched_waitq_walk() visits: the waiters in wait
\* queue order up to the first waiter t with Stop(t) (walk_func returns a
\* value other than 0), this waiter included; all waiters if no waiter
\* stops the walk. The walk follows the wait queue order with both
\* backends (_WAIT_Q_FOR_EACH_SAFE and _WAIT_Q_FOR_EACH, scheduler.c:91-97).
\* @kind definition
\* @c-function z_sched_waitq_walk
Walked(o, Stop(_)) == {t \in W(o) : \A u \in W(o) : Before(u, t) => ~Stop(u)}

\* The waiter at which z_sched_waitq_walk() stops: the first waiter t of o
\* with Stop(t), or NoThread if the walk visits all waiters (the C function
\* then returns 0). Before is a total order on W(o) (invariant
\* OrderIsTotal), so the CHOOSE has exactly one witness.
\* @kind definition
WalkStop(o, Stop(_)) ==
    LET X == {t \in W(o) : Stop(t)}
    IN  IF X = {} THEN NoThread ELSE CHOOSE t \in X : \A u \in X \ {t} : Before(t, u)

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
\* @kind action
\* @c-function z_priq_simple_add
\* @c-function z_priq_rb_add
Add(t, o) ==
    /\ pendedOn[t] = None
    /\ pendedOn' = [pendedOn EXCEPT ![t] = o]
    /\ stamp' = Renumber([stamp EXCEPT ![t] = NextStamp], Waiting \cup {t})

\* The threads in S stop to wait (wake, timeout, abort, flush).
\* @kind action
\* @c-function z_priq_simple_remove
\* @c-function z_priq_rb_remove
RemoveSet(S) ==
    /\ S \subseteq Waiting
    /\ pendedOn' = [t \in Threads |-> IF t \in S THEN None ELSE pendedOn[t]]
    /\ stamp' = Renumber(stamp, Waiting \ S)

\* Thread t stops to wait.
\* @kind action
Remove(t) == RemoveSet({t})

\* The priority of waiter t changes. z_thread_prio_set() removes the thread
\* and adds it again, so it comes after the other waiters with its new
\* priority. The caller sets prio'.
\* @kind action
\* @c-function z_thread_prio_set
Restamp(t) ==
    /\ t \in Waiting
    /\ UNCHANGED pendedOn
    /\ stamp' = Renumber([stamp EXCEPT ![t] = NextStamp], Waiting)

-----------------------------------------------------------------------------
(* Properties *)

\* @kind invariant
TypeOK ==
    /\ DOMAIN pendedOn = Threads
    /\ DOMAIN stamp = Threads
    /\ \A t \in Threads :
          /\ pendedOn[t] \in Objs \cup {None}
          /\ 0 <= stamp[t] /\ stamp[t] <= Cardinality(Threads)

\* The stamps of the waiters are 1..N, and each stamp is unique. A thread
\* that does not wait has the stamp 0. (N unique values in 1..N are all
\* of 1..N.)
\* @kind invariant
StampsNormal ==
    /\ \A t \in Waiting : 1 <= stamp[t] /\ stamp[t] <= Cardinality(Waiting)
    /\ \A a, b \in Waiting : a # b => stamp[a] # stamp[b]
    /\ \A t \in Threads \ Waiting : stamp[t] = 0

\* Before is a strict total order on the waiters of each object. Thus Best
\* and Ordered are defined, and the wake order is fixed.
\* @kind invariant
OrderIsTotal ==
    \A o \in Objs : \A a, b \in W(o) :
        /\ ~Before(a, a)
        /\ a # b => (Before(a, b) \/ Before(b, a))
        /\ Before(a, b) => ~Before(b, a)

\* No two waiters of an object have the same rank. Rank(o, t) is in
\* 1..Cardinality(W(o)), so each rank has exactly one waiter: the CHOOSE in
\* Best and in Ordered has exactly one witness.
\* @kind invariant
RanksDistinct ==
    \A o \in Objs : \A a, b \in W(o) : a # b => Rank(o, a) # Rank(o, b)

\* The waiter that a wake selects is the head of the queue: the only
\* waiter with the rank 1.
\* @kind invariant
BestIsHead ==
    \A o \in Objs : W(o) # {} =>
        \A t \in W(o) : (Rank(o, t) = 1) <=> (t = Best(o))

\* The variables of the module, for the action properties.
wqVars == <<pendedOn, stamp, prio>>

\* A new waiter comes after each waiter of the same object with the same
\* priority (FIFO among equal priorities). No requirement states this rule
\* for all objects yet (see README.rst, open points).
\* @kind action-property
AddIsFifo ==
    [][\A t \in Threads, o \in Objs :
         (pendedOn[t] = None /\ pendedOn'[t] = o) =>
            \A u \in W(o) : prio[u] = prio[t] => stamp'[u] < stamp'[t]]_wqVars

\* A change keeps the order of arrival of the threads that wait before and
\* after it, except for a thread whose priority changes.
\* @kind action-property
KeepsArrivalOrder ==
    [][\A a, b \in Waiting \cap {t \in Threads : pendedOn'[t] # None} :
         (prio'[a] = prio[a] /\ prio'[b] = prio[b]) =>
            ((stamp[a] < stamp[b]) <=> (stamp'[a] < stamp'[b]))]_wqVars

\* After a priority change of a waiter, it comes after the other waiters of
\* its object with the new priority (z_thread_prio_set()).
\* @kind action-property
PrioChangeGoesLast ==
    [][\A t \in Threads :
         (t \in Waiting /\ prio'[t] # prio[t]) =>
            \A u \in W(pendedOn[t]) \ {t} : prio'[u] = prio'[t] => stamp'[u] < stamp'[t]]_wqVars

=============================================================================
