--------------------------- MODULE SchedulerTest ---------------------------
(***************************************************************************)
(* Example tests of lib/Scheduler.tla (see WaitQueueTest for the method).  *)
(* The tests fix the selection rule (Choices, CacheOf) for single states:  *)
(* the direction of the priorities, the cooperative threads, the run queue *)
(* order, the effect of preempt_ok and the CPUs. The invariant             *)
(* RunRuleHolds of MCScheduler uses the same rule as the actions, so it    *)
(* cannot find an error in the rule itself.                                *)
(***************************************************************************)
EXTENDS Integers, TLC

Th == {"t1", "t2", "t3"}

\* The scheduler with the CPUs cs, the thread states ts, the Zephyr
\* priorities zp, the current threads cu, the return values sr, the run
\* queue positions rs and the flag po (preempt_ok of the last
\* update_cache()).
At(cs, ts, zp, cu, sr, rs, po) ==
    INSTANCE Scheduler WITH Threads <- Th, Objs <- {"o1"}, None <- "none",
        CPUS <- cs, Isrs <- {"i1"}, IsrCpu <- [i \in {"i1"} |-> "c1"], Idle <- "idle",
        Data <- {"d"}, NoData <- "nod", Backend <- "DLIST", HeapCapacity <- 0,
        tstate <- ts, prio <- [t \in Th |-> -zp[t]], cur <- cu,
        swapRet <- sr, swapData <- [t \in Th |-> "nod"], panic <- "none",
        rqStamp <- rs, preemptOk <- po, readySince <- rs,
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
\* Run queue positions <<t1, t2, t3>> (0: not ready).
Q(a, b, c) == [t1 |-> a, t2 |-> b, t3 |-> c]
Q123 == Q(1, 2, 3)

\* The queries in fixed states. An instance with parameters cannot be the
\* value of a definition, so each wrapper applies At with "!".
Cu2 == [c1 |-> "t1", c2 |-> "t2"]
ToZ(p)          == At(UP, AllReady, Z(0, 0, 0), [c1 |-> "t1"], NoRets, Q123, FALSE)!ToZephyr(p)
FromZ(z)        == At(UP, AllReady, Z(0, 0, 0), [c1 |-> "t1"], NoRets, Q123, FALSE)!FromZephyr(z)
Coop(p)         == At(UP, AllReady, Z(0, 0, 0), [c1 |-> "t1"], NoRets, Q123, FALSE)!Cooperative(p)
CpuOf2(a)       == At(SMP, AllReady, Z(0, 0, 0), Cu2, NoRets, Q123, FALSE)!CpuOf(a)
Running2(t)     == At(SMP, AllReady, Z(0, 0, 0), Cu2, NoRets, Q123, FALSE)!Running(t)
CanCall2(sr, a) == At(SMP, AllReady, Z(0, 0, 0), Cu2, sr, Q123, FALSE)!CanCall(a)

\* The choices of CPU c in the state of At (run queue rs, flag po).
Ch(cs, ts, zp, cu, rs, po, c) ==
    At(cs, ts, zp, cu, NoRets, rs, po)!Choices(c, ts, [t \in Th |-> -zp[t]], cu, rs, po)

\* The run queue positions after a requeue of t (z_thread_prio_set() of a
\* ready thread) in the state with the Zephyr priorities zp (the new
\* priorities) and the positions rs.
Rq(ts, zp, rs, t) == At(UP, ts, zp, [c1 |-> "t1"], NoRets, rs, FALSE)!Requeue(t)

\* The head of the run queue.
Best(ts, zp, rs) ==
    At(UP, ts, zp, [c1 |-> "t1"], NoRets, rs, FALSE)!RunqBest(ts, [t \in Th |-> -zp[t]], rs)

-----------------------------------------------------------------------------
(* The tests *)

\* The conversion of the priorities. Zephyr: a lower number is a higher
\* priority, a negative number is cooperative.
TestPrio ==
    /\ Check("prio: round trip",    ToZ(FromZ(-1)), -1)
    /\ Check("prio: higher",        FromZ(-1) > FromZ(0), TRUE)
    /\ Check("prio: coop -1",       Coop(FromZ(-1)), TRUE)
    /\ Check("prio: preemptible 0", Coop(FromZ(0)), FALSE)

\* The run queue: a higher priority first, then the position.
TestRunQueue ==
    /\ Check("rq: higher first",      Best(AllReady, Z(1, 0, 0), Q(1, 3, 2)), "t3")
    /\ Check("rq: position in a tie", Best(AllReady, Z(0, 0, 0), Q(2, 3, 1)), "t3")
    /\ Check("rq: pending excluded",  Best(T1Pending, Z(-1, 0, 0), Q(0, 2, 1)), "t3")
    /\ Check("rq: empty is idle",     Best(AllPending, Z(0, 0, 0), Q(0, 0, 0)), "idle")
    \* A requeue puts the thread after each thread of its priority, also
    \* if the priority does not change.
    /\ Check("rq: requeue same prio", Rq(AllReady, Z(0, 0, 1), Q(1, 2, 3), "t1"), Q(3, 1, 2))
    /\ Check("rq: requeue to a higher prio",
             Rq(AllReady, Z(1, 0, 0), Q(1, 2, 3), "t3"), Q(1, 2, 3))
    /\ Check("rq: requeue goes behind the peer",
             Rq(AllReady, Z(0, 1, 1), Q(1, 2, 3), "t2"), Q(1, 3, 2))

\* The selection rule on one CPU, without preempt_ok (update_cache(0)).
TestChoicesUp ==
    /\ Check("up: higher preempts",
             Ch(UP, AllReady, Z(1, 0, 2), [c1 |-> "t1"], Q123, FALSE, "c1"), {"t2"})
    /\ Check("up: lower does not preempt",
             Ch(UP, AllReady, Z(0, 1, 2), [c1 |-> "t1"], Q123, FALSE, "c1"), {"t1"})
    /\ Check("up: current at the head wins a tie",
             Ch(UP, AllReady, Z(0, 0, 1), [c1 |-> "t1"], Q123, FALSE, "c1"), {"t1"})
    \* After a requeue the current thread is behind its peer. Without
    \* preempt_ok the cache is still the head: a preemptible current thread
    \* loses the tie at the next reschedule point.
    /\ Check("up: current behind a peer loses a tie",
             Ch(UP, AllReady, Z(0, 0, 1), [c1 |-> "t1"], Q(2, 1, 3), FALSE, "c1"), {"t2"})
    /\ Check("up: coop keeps the CPU",
             Ch(UP, AllReady, Z(-1, -2, 0), [c1 |-> "t1"], Q123, FALSE, "c1"), {"t1"})
    /\ Check("up: coop behind a peer keeps the CPU",
             Ch(UP, AllReady, Z(-1, -1, 0), [c1 |-> "t1"], Q(2, 1, 3), FALSE, "c1"), {"t1"})
    /\ Check("up: coop preempts a preemptible",
             Ch(UP, AllReady, Z(0, -1, 1), [c1 |-> "t1"], Q123, FALSE, "c1"), {"t2"})
    /\ Check("up: pending coop leaves",
             Ch(UP, T1Pending, Z(-1, 0, 1), [c1 |-> "t1"], Q(0, 1, 2), FALSE, "c1"), {"t2"})
    /\ Check("up: head of a tie after a wait",
             Ch(UP, T1Pending, Z(0, 1, 1), [c1 |-> "t1"], Q(0, 2, 1), FALSE, "c1"), {"t3"})
    /\ Check("up: idle if no thread is ready",
             Ch(UP, AllPending, Z(0, 0, 0), [c1 |-> "t1"], Q(0, 0, 0), FALSE, "c1"), {"idle"})
    /\ Check("up: idle leaves",
             Ch(UP, AllReady, Z(2, 1, 0), [c1 |-> "idle"], Q123, FALSE, "c1"), {"t3"})

\* The selection after update_cache(1) (z_thread_prio_set() of a ready
\* thread, an abort): the head of the run queue, without the cooperative
\* rule (findings P7-a, P7-b, P7-c).
TestChoicesPreemptOk ==
    \* P7-a: t1 runs with Zephyr priority 5, t3 is ready with 5. t1 calls
    \* k_thread_priority_set(t1, 5): t1 goes behind t3, the cache is t3.
    /\ Check("preempt_ok: same prio on itself switches",
             Ch(UP, AllReady, Z(5, 9, 5), [c1 |-> "t1"],
                Rq(AllReady, Z(5, 9, 5), Q(1, 3, 2), "t1"), TRUE, "c1"),
             {"t3"})
    \* P7-b: t1 runs cooperative (-1), t2 is ready with -2 (higher). A
    \* priority change of t3 sets preempt_ok: the cache is t2.
    /\ Check("preempt_ok: coop loses the CPU to a higher thread",
             Ch(UP, AllReady, Z(-1, -2, 3), [c1 |-> "t1"],
                Rq(AllReady, Z(-1, -2, 3), Q(1, 2, 3), "t3"), TRUE, "c1"),
             {"t2"})
    \* The control: the same state with update_cache(0) keeps t1.
    /\ Check("preempt_ok: control without the flag",
             Ch(UP, AllReady, Z(-1, -2, 3), [c1 |-> "t1"], Q123, FALSE, "c1"), {"t1"})
    \* A requeue of another ready thread keeps the current thread at the
    \* head: no switch.
    /\ Check("preempt_ok: requeue of a peer keeps the current thread",
             Ch(UP, AllReady, Z(5, 5, 9), [c1 |-> "t1"],
                Rq(AllReady, Z(5, 5, 9), Q123, "t2"), TRUE, "c1"),
             {"t1"})

\* The selection rule on two CPUs (SmpChoices, design exploration): a
\* thread that runs on the other CPU is not a candidate. The run queue and
\* the flag have no effect.
TestChoicesSmp ==
    /\ Check("smp: other CPU's thread excluded",
             Ch(SMP, AllReady, Z(1, 0, 2), [c1 |-> "t1", c2 |-> "t2"], Q123, FALSE, "c1"), {"t1"})
    /\ Check("smp: idle takes the ready thread",
             Ch(SMP, AllReady, Z(1, 0, 2), [c1 |-> "t1", c2 |-> "idle"], Q123, FALSE, "c2"), {"t2"})
    /\ Check("smp: nothing left",
             Ch(SMP, T1Pending, Z(0, 0, 0), [c1 |-> "t2", c2 |-> "t3"], Q(0, 1, 2), FALSE, "c1"),
             {"t2"})
    /\ Check("smp: any of a tie after a wait",
             Ch(SMP, T1Pending, Z(0, 1, 1), [c1 |-> "t1", c2 |-> "idle"], Q(0, 2, 1), TRUE, "c1"),
             {"t2", "t3"})

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
