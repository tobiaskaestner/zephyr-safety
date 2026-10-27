--------------------------- MODULE SchedulerTest ---------------------------
(***************************************************************************)
(* Example tests of lib/Scheduler.tla (see WaitQueueTest for the method).  *)
(* The tests fix the selection rule (Choices) for single states: the       *)
(* direction of the priorities, the cooperative threads, the tie rule and  *)
(* the CPUs. The invariant RunRuleHolds of MCScheduler uses the same rule  *)
(* as the actions, so it cannot find an error in the rule itself.          *)
(***************************************************************************)
EXTENDS Integers, TLC

Th == {"t1", "t2", "t3"}

\* The scheduler with the CPUs cs, the thread states ts, the Zephyr
\* priorities zp, the current threads cu and the return values sr.
At(cs, ts, zp, cu, sr) ==
    INSTANCE Scheduler WITH Threads <- Th, Objs <- {"o1"}, None <- "none",
        CPUS <- cs, Isrs <- {"i1"}, IsrCpu <- [i \in {"i1"} |-> "c1"], Idle <- "idle",
        Data <- {"d"}, NoData <- "nod", Backend <- "DLIST", HeapCapacity <- 0,
        tstate <- ts, prio <- [t \in Th |-> -zp[t]], cur <- cu,
        swapRet <- sr, swapData <- [t \in Th |-> "nod"], panic <- "none",
        pendedOn <- [t \in Th |-> "none"], stamp <- [t \in Th |-> 0],
        tq <- <<>>, tqCost <- [op |-> "none", n |-> 0, cost |-> 0]

\* A test: the value got must be the value want.
Check(name, got, want) == Assert(got = want, <<name, "got", got, "want", want>>)

UP  == {"c1"}
SMP == {"c1", "c2"}

AllReady   == [t \in Th |-> "ready"]
T1Pending  == [AllReady EXCEPT !["t1"] = "pending"]
AllPending == [t \in Th |-> "pending"]
NoRets     == [t \in Th |-> 1]

\* Zephyr priorities <<t1, t2, t3>>.
Z(a, b, c) == [t1 |-> a, t2 |-> b, t3 |-> c]

\* The queries in fixed states. An instance with parameters cannot be the
\* value of a definition, so each wrapper applies At with "!".
Cu2 == [c1 |-> "t1", c2 |-> "t2"]
ToZ(p)          == At(UP, AllReady, Z(0, 0, 0), [c1 |-> "t1"], NoRets)!ToZephyr(p)
FromZ(z)        == At(UP, AllReady, Z(0, 0, 0), [c1 |-> "t1"], NoRets)!FromZephyr(z)
Coop(p)         == At(UP, AllReady, Z(0, 0, 0), [c1 |-> "t1"], NoRets)!Cooperative(p)
CpuOf2(a)       == At(SMP, AllReady, Z(0, 0, 0), Cu2, NoRets)!CpuOf(a)
Running2(t)     == At(SMP, AllReady, Z(0, 0, 0), Cu2, NoRets)!Running(t)
CanCall2(sr, a) == At(SMP, AllReady, Z(0, 0, 0), Cu2, sr)!CanCall(a)

\* The choices of CPU c in the state of At.
Ch(cs, ts, zp, cu, c) == At(cs, ts, zp, cu, NoRets)!Choices(c, ts, [t \in Th |-> -zp[t]], cu)

-----------------------------------------------------------------------------
(* The tests *)

\* The conversion of the priorities. Zephyr: a lower number is a higher
\* priority, a negative number is cooperative.
TestPrio ==
    /\ Check("prio: round trip",    ToZ(FromZ(-1)), -1)
    /\ Check("prio: higher",        FromZ(-1) > FromZ(0), TRUE)
    /\ Check("prio: coop -1",       Coop(FromZ(-1)), TRUE)
    /\ Check("prio: preemptible 0", Coop(FromZ(0)), FALSE)

\* The selection rule on one CPU.
TestChoicesUp ==
    /\ Check("up: higher preempts",
             Ch(UP, AllReady, Z(1, 0, 2), [c1 |-> "t1"], "c1"), {"t2"})
    /\ Check("up: lower does not preempt",
             Ch(UP, AllReady, Z(0, 1, 2), [c1 |-> "t1"], "c1"), {"t1"})
    /\ Check("up: current wins a tie",
             Ch(UP, AllReady, Z(0, 0, 1), [c1 |-> "t1"], "c1"), {"t1"})
    /\ Check("up: coop keeps the CPU",
             Ch(UP, AllReady, Z(-1, -2, 0), [c1 |-> "t1"], "c1"), {"t1"})
    /\ Check("up: coop preempts a preemptible",
             Ch(UP, AllReady, Z(0, -1, 1), [c1 |-> "t1"], "c1"), {"t2"})
    /\ Check("up: pending coop leaves",
             Ch(UP, T1Pending, Z(-1, 0, 1), [c1 |-> "t1"], "c1"), {"t2"})
    /\ Check("up: any of a tie after a wait",
             Ch(UP, T1Pending, Z(0, 1, 1), [c1 |-> "t1"], "c1"), {"t2", "t3"})
    /\ Check("up: idle if no thread is ready",
             Ch(UP, AllPending, Z(0, 0, 0), [c1 |-> "t1"], "c1"), {"idle"})
    /\ Check("up: idle leaves",
             Ch(UP, AllReady, Z(2, 1, 0), [c1 |-> "idle"], "c1"), {"t3"})

\* The selection rule on two CPUs: a thread that runs on the other CPU is
\* not a candidate.
TestChoicesSmp ==
    /\ Check("smp: other CPU's thread excluded",
             Ch(SMP, AllReady, Z(1, 0, 2), [c1 |-> "t1", c2 |-> "t2"], "c1"), {"t1"})
    /\ Check("smp: idle takes the ready thread",
             Ch(SMP, AllReady, Z(1, 0, 2), [c1 |-> "t1", c2 |-> "idle"], "c2"), {"t2"})
    /\ Check("smp: nothing left",
             Ch(SMP, T1Pending, Z(0, 0, 0), [c1 |-> "t2", c2 |-> "t3"], "c1"), {"t2"})

\* The queries of the actors.
TestActors ==
    /\ Check("CpuOf isr",           CpuOf2("i1"), "c1")
    /\ Check("CpuOf thread",        CpuOf2("t2"), "c2")
    /\ Check("Running",             Running2("t3"), FALSE)
    /\ Check("CanCall isr",         CanCall2(NoRets, "i1"), TRUE)
    /\ Check("CanCall running",     CanCall2(NoRets, "t1"), TRUE)
    /\ Check("CanCall not running", CanCall2(NoRets, "t3"), FALSE)
    \* t1 runs again after a wake and has not returned from its wait.
    /\ Check("CanCall after wake",  CanCall2([NoRets EXCEPT !["t1"] = 0], "t1"), FALSE)

-----------------------------------------------------------------------------
(* The spec: one state, no deadlock. Its only purpose is the run of the    *)
(* invariants above.                                                       *)

VARIABLE unused
Init == unused = 0
Next == UNCHANGED unused
=============================================================================
