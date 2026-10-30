--------------------------- MODULE WaitQueueTest ---------------------------
(***************************************************************************)
(* Example tests of lib/WaitQueue.tla. Each test evaluates a query or a    *)
(* helper on a chosen state and compares the value with the expected      *)
(* value. The models (MCWaitQueue) check the rules in all reachable        *)
(* states. These tests fix single values that a rule alone does not fix,   *)
(* for example the direction of the priority order.                        *)
(*                                                                         *)
(* The tests are invariants of a spec with one state, not ASSUMEs: SANY    *)
(* gives an expression of an instance of a module with variables the level *)
(* 1, also if each variable is replaced by a constant, and an ASSUME must  *)
(* have the level 0. A failed test stops TLC with the message of Assert:   *)
(* the name of the test, the value got and the value wanted.               *)
(***************************************************************************)
EXTENDS Naturals, TLC

Threads == {"t1", "t2", "t3"}
Objs    == {"o1", "o2"}
NoObj   == "none"
NoThr   == "nothread"

\* WaitQueue in the state pe (pendedOn), st (stamp), pr (prio).
At(pe, st, pr) == INSTANCE WaitQueue WITH pendedOn <- pe, stamp <- st, prio <- pr, None <- NoObj,
                                          NoThread <- NoThr

\* A test: the value got must be the value want.
Check(name, got, want) == Assert(got = want, <<name, "got", got, "want", want>>)

\* The threads in S wait on o1, the others on no object.
Wait(S) == [t \in Threads |-> IF t \in S THEN "o1" ELSE NoObj]
NoStamps == [t \in Threads |-> 0]
Equal    == [t \in Threads |-> 1]               \* one priority for all
P1       == [Equal EXCEPT !["t2"] = 2]           \* t2 has the higher priority

\* t1 waits first, then t2, then t3.
S123 == [t1 |-> 1, t2 |-> 2, t3 |-> 3]
\* Only t1 waits.
S1 == [NoStamps EXCEPT !["t1"] = 1]
\* t1 waits on o1, t2 on o2.
Two == [t1 |-> "o1", t2 |-> "o2", t3 |-> NoObj]
S12 == [t1 |-> 1, t2 |-> 2, t3 |-> 0]

-----------------------------------------------------------------------------
(* The tests *)

\* An empty queue.
TestEmpty ==
    /\ Check("empty: W",         At(Wait({}), NoStamps, Equal)!W("o1"), {})
    /\ Check("empty: Waiting",   At(Wait({}), NoStamps, Equal)!Waiting, {})
    /\ Check("empty: Ordered",   At(Wait({}), NoStamps, Equal)!Ordered("o1"), <<>>)
    /\ Check("empty: NextStamp", At(Wait({}), NoStamps, Equal)!NextStamp, 1)

\* One waiter.
TestOne ==
    /\ Check("one: Best",    At(Wait({"t1"}), S1, Equal)!Best("o1"), "t1")
    /\ Check("one: Rank",    At(Wait({"t1"}), S1, Equal)!Rank("o1", "t1"), 1)
    /\ Check("one: Ordered", At(Wait({"t1"}), S1, Equal)!Ordered("o1"), <<"t1">>)

\* The order rule: a greater prio value first, then the order of arrival.
TestOrder ==
    /\ Check("fifo: Ordered", At(Wait(Threads), S123, Equal)!Ordered("o1"), <<"t1", "t2", "t3">>)
    /\ Check("fifo: Best",    At(Wait(Threads), S123, Equal)!Best("o1"), "t1")
    /\ Check("prio: Best",    At(Wait(Threads), S123, P1)!Best("o1"), "t2")
    /\ Check("prio: Ordered", At(Wait(Threads), S123, P1)!Ordered("o1"), <<"t2", "t1", "t3">>)
    /\ Check("prio: Rank t3", At(Wait(Threads), S123, P1)!Rank("o1", "t3"), 3)
    /\ Check("strict",        \E t \in Threads : At(Wait(Threads), S123, Equal)!Before(t, t), FALSE)
    /\ Check("ranks",         [t \in Threads |-> At(Wait(Threads), S123, P1)!Rank("o1", t)],
                              [t1 |-> 2, t2 |-> 1, t3 |-> 3])

\* Two objects: the queues stay apart, the stamps count all waiters.
TestTwoObjects ==
    /\ Check("two: W o1",      At(Two, S12, Equal)!W("o1"), {"t1"})
    /\ Check("two: Best o2",   At(Two, S12, Equal)!Best("o2"), "t2")
    /\ Check("two: Waiting",   At(Two, S12, Equal)!Waiting, {"t1", "t2"})
    /\ Check("two: NextStamp", At(Two, S12, Equal)!NextStamp, 3)

\* Head: z_waitq_head() and z_waitq_head_locked(). NoThread on an empty
\* queue, else the best waiter.
TestHead ==
    /\ Check("head: empty",      At(Wait({}), NoStamps, Equal)!Head("o1"), NoThr)
    /\ Check("head: fifo",       At(Wait(Threads), S123, Equal)!Head("o1"), "t1")
    /\ Check("head: prio",       At(Wait(Threads), S123, P1)!Head("o1"), "t2")
    /\ Check("head: other obj",  At(Two, S12, Equal)!Head("o2"), "t2")

\* The walk of z_sched_waitq_walk(): wait queue order, stop after the
\* first waiter for which walk_func returns non-zero. The order with P1 is
\* t2, t1, t3.
StopT1(t)   == t = "t1"
StopT3(t)   == t = "t3"
StopNone(t) == FALSE
StopAll(t)  == TRUE
NotT2(t)    == t # "t2"
Walked(st, pr, Stop(_)) == At(Wait(Threads), st, pr)!Walked("o1", Stop)
WalkStop(st, pr, Stop(_)) == At(Wait(Threads), st, pr)!WalkStop("o1", Stop)
TestWalk ==
    /\ Check("walk: no stop visits all",  Walked(S123, P1, StopNone), Threads)
    /\ Check("walk: no stop, no thread",  WalkStop(S123, P1, StopNone), NoThr)
    /\ Check("walk: stop at the head",    Walked(S123, P1, StopAll), {"t2"})
    /\ Check("walk: stop at the second",  Walked(S123, P1, StopT1), {"t2", "t1"})
    /\ Check("walk: stopper",             WalkStop(S123, P1, StopT1), "t1")
    \* Without the priority, t1 is the head: the walk stops at once.
    /\ Check("walk: fifo stop at t1",     Walked(S123, Equal, StopT1), {"t1"})
    \* The first match in wait queue order, not the first in the set.
    /\ Check("walk: first of two",        WalkStop(S123, P1, NotT2), "t1")
    /\ Check("walk: stop at the tail",    Walked(S123, P1, StopT3), Threads)
    /\ Check("walk: empty queue",
             At(Wait({}), NoStamps, Equal)!Walked("o1", StopAll), {})

\* Renumber: the stamps that Add, Remove and Restamp compute.
TestRenumber ==
    \* Add t3 to t1 and t2: t3 gets NextStamp = 3.
    /\ Check("add: stamps",
             At(Wait({"t1", "t2"}), S12, Equal)!Renumber([S12 EXCEPT !["t3"] = 3], Threads),
             S123)
    \* Remove t1 (the head): the others keep their order and close the gap.
    /\ Check("remove: stamps",
             At(Wait(Threads), S123, Equal)!Renumber(S123, {"t2", "t3"}),
             [t1 |-> 0, t2 |-> 1, t3 |-> 2])
    \* Restamp t1: it gets NextStamp = 4 and goes to the end.
    /\ Check("restamp: stamps",
             At(Wait(Threads), S123, Equal)!Renumber([S123 EXCEPT !["t1"] = 4], Threads),
             [t1 |-> 3, t2 |-> 1, t3 |-> 2])

-----------------------------------------------------------------------------
(* The spec: one state, no deadlock. Its only purpose is the run of the    *)
(* invariants above.                                                       *)

VARIABLE unused
Init == unused = 0
Next == UNCHANGED unused
=============================================================================
