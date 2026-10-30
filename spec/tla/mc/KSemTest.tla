------------------------------ MODULE KSemTest ------------------------------
(***************************************************************************)
(* Example tests of objects/KSem.tla and of the helpers of lib/Waitable.tla *)
(* that KSem uses. Each test evaluates an operator on chosen values and    *)
(* compares the value with the expected value (see WaitQueueTest for the   *)
(* form). The models (MCKSem) check the rules in all reachable states.     *)
(***************************************************************************)
EXTENDS Integers, Sequences, TLC

VARIABLE unused

Init == unused = 0
Next == UNCHANGED unused

Th == {"t1", "t2"}

\* KSem with the runtime checks rc, UMax 3, in a fixed state (the operators
\* under test read no variable; the state only gives each variable a value).
K(rc) == INSTANCE KSem WITH
    Threads <- Th, Objs <- {"s1"}, None <- "none", Isrs <- {"i1"},
    IsrCpu <- [i \in {"i1"} |-> "c1"], MaxIrqNest <- 0, Idle <- "idle", Data <- {},
    NoData <- "nod", JoinQ <- [t \in Th |-> "none"], CPUS <- {"c1"}, UseSwitch <- TRUE,
    Backend <- "DLIST", HeapCapacity <- 0, InitArgs <- {}, UMax <- 3, InitPrios <- {0},
    EnvPrios <- {}, RuntimeChecks <- rc, Poll <- FALSE, ReInit <- FALSE, IsrWaits <- FALSE,
    tstate <- [t \in Th |-> "ready"], prio <- [t \in Th |-> 0], cur <- [c \in {"c1"} |-> "t1"],
    swapRet <- [t \in Th |-> 1], swapData <- [t \in Th |-> "nod"], panic <- "none",
    rqStamp <- [t \in Th |-> 0], preemptOk <- FALSE, readySince <- [t \in Th |-> 0],
    pendedOn <- [t \in Th |-> "none"], stamp <- [t \in Th |-> 0], tq <- <<>>,
    tqCost <- [op |-> "none", n |-> 0, cost |-> 0], irqNest <- [c \in {"c1"} |-> 0],
    pendsv <- [c \in {"c1"} |-> FALSE],
    r <- [o \in {"s1"} |-> [init |-> TRUE, count |-> 0, limit |-> 1]],
    req <- [t \in Th |-> "none"], tokens <- [o \in {"s1"} |-> 0], obs <- <<>>

Check(name, got, want) == Assert(got = want, <<name, "got", got, "want", want>>)

Sem(c, l) == [init |-> TRUE, count |-> c, limit |-> l]

-----------------------------------------------------------------------------
(* The tests *)

\* The unsigned increment wraps at UMax.
TestInc ==
    /\ Check("Inc(1)", K(TRUE)!Inc(1), 2)
    /\ Check("Inc(UMax)", K(TRUE)!Inc(3), 0)

\* A give without a waiter: +1 below the limit, no change at the limit,
\* and +1 (with wrap) above the limit (the comparison is !=).
TestSettle ==
    /\ Check("settle below", K(TRUE)!SemSettle(Sem(1, 2)), Sem(2, 2))
    /\ Check("settle at limit", K(TRUE)!SemSettle(Sem(2, 2)), Sem(2, 2))
    /\ Check("settle above limit", K(FALSE)!SemSettle(Sem(3, 2)), Sem(0, 2))
    /\ Check("settle limit 0", K(FALSE)!SemSettle(Sem(0, 0)), Sem(0, 0))

\* Take and reset.
TestTakeReset ==
    /\ Check("avail 0", K(TRUE)!SemAvail(Sem(0, 1)), FALSE)
    /\ Check("avail 1", K(TRUE)!SemAvail(Sem(1, 1)), TRUE)
    /\ Check("consume", K(TRUE)!SemConsume(Sem(2, 2)), Sem(1, 2))
    /\ Check("flush", K(TRUE)!SemFlushR(Sem(2, 2)), Sem(0, 2))

\* The argument check of k_sem_init() exists only with runtime checks.
TestValid ==
    /\ Check("valid <<0, 1>>", K(TRUE)!SemValid(<<0, 1>>), TRUE)
    /\ Check("valid <<1, 1>>", K(TRUE)!SemValid(<<1, 1>>), TRUE)
    /\ Check("limit 0", K(TRUE)!SemValid(<<0, 0>>), FALSE)
    /\ Check("count above limit", K(TRUE)!SemValid(<<2, 1>>), FALSE)
    /\ Check("no checks: limit 0", K(FALSE)!SemValid(<<0, 0>>), TRUE)
    /\ Check("no checks: count above limit", K(FALSE)!SemValid(<<2, 1>>), TRUE)
    /\ Check("new", K(TRUE)!SemNew(<<1, 2>>), Sem(1, 2))

\* The call records of Waitable.
TestCalls ==
    /\ Check("timeout FOREVER", K(TRUE)!W!TimeoutArg("FOREVER"), -1)
    /\ Check("timeout TICKS", K(TRUE)!W!TimeoutArg("TICKS"), 1)
    /\ Check("release unlock", K(TRUE)!W!ReleaseCall("unlock", "s1", 0).fn, "arch_irq_unlock")
    /\ Check("release resched", K(TRUE)!W!ReleaseCall("resched", "s1", 0).fn, "z_reschedule")
    /\ Check("wake false", K(TRUE)!W!WakeCall("s1", 0, FALSE, 0, "idle").ret, 0)
    /\ Check("discipline: lock, unlock",
             K(TRUE)!W!LockDiscipline(<<K(TRUE)!W!LockCall("s1", 0),
                                        K(TRUE)!W!ReleaseCall("unlock", "s1", 0)>>), TRUE)
    /\ Check("discipline: lock, wake, resched",
             K(TRUE)!W!LockDiscipline(<<K(TRUE)!W!LockCall("s1", 0),
                                        K(TRUE)!W!WakeCall("s1", 0, TRUE, 0, "t2"),
                                        K(TRUE)!W!ReleaseCall("resched", "s1", 0)>>), TRUE)
    /\ Check("discipline: no release",
             K(TRUE)!W!LockDiscipline(<<K(TRUE)!W!LockCall("s1", 0)>>), FALSE)
    /\ Check("discipline: two releases",
             K(TRUE)!W!LockDiscipline(<<K(TRUE)!W!LockCall("s1", 0),
                                        K(TRUE)!W!ReleaseCall("unlock", "s1", 0),
                                        K(TRUE)!W!ReleaseCall("unlock", "s1", 0)>>), FALSE)
    /\ Check("discipline: release first",
             K(TRUE)!W!LockDiscipline(<<K(TRUE)!W!ReleaseCall("unlock", "s1", 0),
                                        K(TRUE)!W!LockCall("s1", 0)>>), FALSE)
=============================================================================
