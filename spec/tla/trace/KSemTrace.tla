------------------------------ MODULE KSemTrace ------------------------------
(***************************************************************************)
(* The trace module of the semaphore: it checks that a recorded run of a   *)
(* unit test of kernel/sem.c is a behavior of objects/KSem.tla (a trace     *)
(* check, the relation "abstracts" of the method).                         *)
(*                                                                         *)
(* The trace is one NDJSON file of the trace hook of the unit tests        *)
(* (tests/kernel/unit/common/include/kernel_unit_trace.h; the schema is in  *)
(* README.rst of this directory). The module reads it at run time          *)
(* (ndJsonDeserialize of the module Json of tla2tools.jar) and groups the  *)
(* lines into steps (Steps): one step for each API call that ends at its    *)
(* release (the return, or z_pend_curr()), one for each return from a wait,*)
(* one for each step of the environment that the reference fake of the     *)
(* scheduler reports (a timeout, an abort), and one for a panic.           *)
(*                                                                         *)
(* The initial state comes from the trace:                                 *)
(*                                                                         *)
(* - A test with the reference fake ("setup" with ref = true) gives the    *)
(*   threads, their priorities, waits, timeouts and the current thread.     *)
(*   The initial state is this state.                                      *)
(* - A test with scripted fakes gives only the semaphores. The test thread *)
(*   is t1 and runs. TLC selects the hidden part: which of the threads     *)
(*   h1..hN wait on which semaphore, in which order, with which timeouts   *)
(*   (the fake z_sched_wake() stands for them).                            *)
(*                                                                         *)
(* In both cases the initial state must satisfy the invariants of KSem     *)
(* (TraceInit). It is not checked that KSem!Init reaches it.               *)
(*                                                                         *)
(* A step of the trace is a step of KSem!Next whose observation obs' is    *)
(* the step: the actor, the operation, the object, the timeout, the        *)
(* arguments, the return value, each call into the lock and the scheduler  *)
(* with its argument, return value and count, and the count and limit      *)
(* after the call. Between two steps, KSem can take hidden steps (Hidden), *)
(* at most HiddenMax in a row:                                             *)
(*                                                                         *)
(* - scripted fakes: only while the test thread t1 waits (its return value *)
(*   comes from the fake z_pend_curr(), which stands for these steps), and *)
(*   only steps of other actors;                                           *)
(* - reference fake: only the selection steps of the scheduler (Preempt,   *)
(*   PendSV), which the reference fake does inside its own calls.          *)
(*                                                                         *)
(* Acceptance is positive: the postcondition Accepted holds only if some   *)
(* behavior matched all steps (the register 1 holds the longest matched    *)
(* prefix, CONSTRAINT Progress). Run TLC with one worker. The refinement   *)
(* property RefinesKSem states that each step of the trace behavior is a   *)
(* step of KSem; the invariants and action properties of KSem are checked  *)
(* on the trace behavior too.                                              *)
(***************************************************************************)
EXTENDS Integers, Sequences, FiniteSets, TLC, Json

CONSTANTS
    \* The absolute path of the NDJSON trace of one test.
    TraceFile,
    \* The number of hidden threads of a test with scripted fakes.
    NHidden,
    \* The bound of the hidden steps in a row.
    HiddenMax

VARIABLES
    tstate, prio, cur, swapRet, swapData, panic, rqStamp, preemptOk, readySince,
    pendedOn, stamp, tq, tqCost, irqNest, pendsv, r, req, tokens, obs,
    \* The number of matched steps of the trace.
    i,
    \* The number of hidden steps since the last matched step.
    h

kvars == <<tstate, prio, cur, swapRet, swapData, panic, rqStamp, preemptOk, readySince,
           pendedOn, stamp, tq, tqCost, irqNest, pendsv, r, req, tokens, obs>>
tvars == <<kvars, i, h>>

-----------------------------------------------------------------------------
(* The trace *)

Log == ndJsonDeserialize(TraceFile)

Has(e, f) == f \in DOMAIN e

Lines(kind) == SelectSeq(Log, LAMBDA e : e.ev = kind)

TestLine  == Lines("test")[1]
SetupLine == Lines("setup")[1]
SemLines  == Lines("sem")
CallLines == Lines("call")

IsRef == SetupLine.ref

SemIds == {SemLines[k].id : k \in DOMAIN SemLines}
SemLine(o) == SemLines[CHOOSE k \in DOMAIN SemLines : SemLines[k].id = o]

RefThreadLines == IF IsRef THEN SetupLine.threads ELSE <<>>
RefThreadIds == {RefThreadLines[k].id : k \in DOMAIN RefThreadLines}
TH(t) == RefThreadLines[CHOOSE k \in DOMAIN RefThreadLines : RefThreadLines[k].id = t]

Hidden == {"h" \o ToString(k) : k \in 1..NHidden}
Caller == "t1"

TThreads == IF IsRef THEN RefThreadIds ELSE {Caller} \cup Hidden

\* The bound of the count: the largest integer of TLC. The model of the
\* trace wraps the count there, not at UINT_MAX; a trace with a larger value
\* is out of the range of the check (tools/check_traces.py does not run it).
TUMax == 2147483647

InitCalls == SelectSeq(CallLines, LAMBDA e : e.op = "init")
TInitArgs == {InitCalls[k].args : k \in DOMAIN InitCalls}

\* An init of a semaphore that is in use: initialized before (a second
\* init, or an init after the setup of the test).
TReInit ==
    \E k \in DOMAIN InitCalls :
        \/ SemLine(InitCalls[k].obj).init
        \/ \E j \in DOMAIN InitCalls : j < k /\ InitCalls[j].obj = InitCalls[k].obj

\* An ISR that waits (the test of the panic of z_pend_curr()).
TIsrWaits ==
    \E k \in DOMAIN CallLines :
        CallLines[k].actor = "i1" /\ Has(CallLines[k], "timeout")
        /\ CallLines[k].timeout # "NO_WAIT"

-----------------------------------------------------------------------------
(* The model *)

K == INSTANCE KSem WITH
    Threads <- TThreads, Objs <- SemIds, None <- "none", Isrs <- {"i1"},
    IsrCpu <- [x \in {"i1"} |-> "c1"], MaxIrqNest <- 0, Idle <- "idle", Data <- {},
    NoData <- "nod", JoinQ <- [t \in TThreads |-> "none"], CPUS <- {"c1"},
    UseSwitch <- TRUE, Backend <- "DLIST", HeapCapacity <- 0, InitArgs <- TInitArgs,
    UMax <- TUMax, InitPrios <- {0}, EnvPrios <- {}, RuntimeChecks <- TestLine.config.rtc,
    Poll <- TestLine.config.poll, ReInit <- TReInit, IsrWaits <- TIsrWaits

NoRet == K!NoRet

-----------------------------------------------------------------------------
(* The steps of the trace *)

\* The operation in the model: k_sem_reset() is the flush of the template.
OpName(op) == IF op = "reset" THEN "flush" ELSE op

NoStep == [kind |-> "none"]

ApiStep(e) ==
    [kind    |-> "api",
     actor   |-> e.actor,
     op      |-> OpName(e.op),
     obj     |-> e.obj,
     timeout |-> IF Has(e, "timeout") THEN e.timeout ELSE "none",
     args    |-> IF Has(e, "args") THEN e.args ELSE <<>>,
     calls   |-> <<>>,
     ret     |-> NoRet,
     count   |-> -1,
     limit   |-> -1]

\* Group the lines from line k on. open is the step that has started and not
\* ended, acc the steps so far.
RECURSIVE Group(_, _, _)
Group(k, open, acc) ==
    IF k > Len(Log) THEN acc
    ELSE LET e == Log[k] IN
    CASE e.ev = "call" ->
           Group(k + 1, ApiStep(e), acc)
      [] e.ev = "fake" /\ open.kind = "api" ->
           LET o2 == [open EXCEPT !.calls = Append(@, e)] IN
           IF e.fn = "z_pend_curr"
             \* The release of the take that waits: the step ends here.
             THEN Group(k + 1, NoStep, Append(acc, [o2 EXCEPT !.count = e.res]))
             ELSE Group(k + 1, o2, acc)
      [] e.ev = "pend_ret" ->
           Group(k + 1, [ApiStep([actor |-> e.actor, op |-> "resume", obj |-> e.obj])
                         EXCEPT !.ret = e.ret], acc)
      [] e.ev = "ret" /\ open.kind = "api" ->
           Group(k + 1, NoStep,
                 Append(acc, [open EXCEPT !.ret = IF open.op = "resume" THEN @ ELSE e.ret,
                                          !.count = IF Has(e, "count") THEN e.count ELSE -1,
                                          !.limit = IF Has(e, "limit") THEN e.limit ELSE -1]))
      [] e.ev = "env" ->
           Group(k + 1, open, Append(acc, [kind |-> "env", op |-> e.op, thread |-> e.thread]))
      [] e.ev = "panic" ->
           Group(k + 1, open, Append(acc, [kind |-> "panic"]))
      [] OTHER ->
           Group(k + 1, open, acc)

Steps == Group(1, NoStep, <<>>)

-----------------------------------------------------------------------------
(* The initial state *)

R0 == [o \in SemIds |->
         IF SemLine(o).init
           THEN [init |-> TRUE, count |-> SemLine(o).count, limit |-> SemLine(o).limit]
           ELSE K!NoSem]

\* The armed timeouts in the order of their expiry (reference fake).
Earlier(a, b) ==
    \/ TH(a).deadline < TH(b).deadline
    \/ TH(a).deadline = TH(b).deadline /\ TH(a).armed_seq < TH(b).armed_seq
RefArmed == {t \in TThreads : TH(t).armed}
RefTq == [k \in 1..Cardinality(RefArmed) |->
            CHOOSE t \in RefArmed : Cardinality({u \in RefArmed : Earlier(u, t)}) = k - 1]

RefInit ==
    LET Pend  == {t \in TThreads : TH(t).state = "pending"}
        Ready == {t \in TThreads : TH(t).state = "ready"}
    IN
    /\ tstate = [t \in TThreads |-> TH(t).state]
    /\ prio = [t \in TThreads |-> K!S!FromZephyr(TH(t).prio)]
    /\ cur = [c \in {"c1"} |-> SetupLine.current]
    /\ swapRet = [t \in TThreads |-> TH(t).ret]
    /\ swapData = [t \in TThreads |-> "nod"]
    /\ panic = "none"
    /\ rqStamp = K!S!RqNormal([t \in TThreads |-> TH(t).ready_seq], Ready)
    /\ readySince = rqStamp
    /\ preemptOk = SetupLine.preempt_ok
    /\ pendedOn = [t \in TThreads |-> TH(t).on]
    /\ stamp = K!S!WQ!Renumber([t \in TThreads |-> TH(t).stamp], Pend)
    /\ tq = RefTq
    /\ tqCost = K!S!TO!NoCost
    /\ irqNest = [c \in {"c1"} |-> 0]
    /\ pendsv = [c \in {"c1"} |-> FALSE]
    /\ req = [t \in TThreads |-> IF t \in Pend THEN TH(t).on ELSE "none"]

\* The sequences of the elements of S (each one once).
Perms(S) == {f \in [1..Cardinality(S) -> S] : \A x, y \in DOMAIN f : x # y => f[x] # f[y]}

ScriptInit ==
    \E W \in SUBSET Hidden :
    \E on \in [W -> SemIds] :
    \E st \in Perms(W) :
    \E A \in SUBSET W :
    \E q \in Perms(A) :
    \E rs \in K!S!RqOrders :
    LET Ready == TThreads \ W
        Pos(t) == CHOOSE k \in DOMAIN st : st[k] = t
    IN
    /\ tstate = [t \in TThreads |-> IF t \in W THEN "pending" ELSE "ready"]
    /\ prio = [t \in TThreads |-> 0]
    /\ cur = [c \in {"c1"} |-> Caller]
    /\ swapRet = [t \in TThreads |-> IF t \in W THEN K!EAGAIN ELSE NoRet]
    /\ swapData = [t \in TThreads |-> "nod"]
    /\ panic = "none"
    /\ rqStamp = K!S!RqNormal(rs, Ready)
    /\ rqStamp[Caller] = 1
    /\ readySince = rqStamp
    /\ preemptOk = FALSE
    /\ pendedOn = [t \in TThreads |-> IF t \in W THEN on[t] ELSE "none"]
    /\ stamp = [t \in TThreads |-> IF t \in W THEN Pos(t) ELSE 0]
    /\ tq = q
    /\ tqCost = K!S!TO!NoCost
    /\ irqNest = [c \in {"c1"} |-> 0]
    /\ pendsv = [c \in {"c1"} |-> FALSE]
    /\ req = [t \in TThreads |-> IF t \in W THEN on[t] ELSE "none"]

\* The state of the test must be a correct state of KSem. A thread waits only
\* on an initialized semaphore (k_sem_take() of an uninitialized one is
\* undefined).
InitIsCorrect ==
    /\ \A t \in TThreads : pendedOn[t] # "none" => r[pendedOn[t]].init
    /\ K!TypeOK
    /\ K!ReqIsWait
    /\ K!S!PendingIsQueued
    /\ K!S!ArmedArePending
    /\ K!S!CurIsReady
    /\ K!S!RunRuleHolds
    /\ K!S!RqStampsNormal
    /\ K!S!WQ!StampsNormal
    /\ K!NoWaitWhileAvailable
    /\ K!CountLeLimit

TraceInit ==
    /\ r = R0
    /\ IF IsRef THEN RefInit ELSE ScriptInit
    /\ tokens = [o \in SemIds |-> R0[o].count + K!Inflight(o)]
    /\ obs = K!W!NoObs
    /\ i = 0
    /\ h = 0
    /\ InitIsCorrect

-----------------------------------------------------------------------------
(* The match of a step *)

\* A call of the model and a call line of the trace. The trace hook marks a
\* call with "bad" if it releases another lock or uses another key. k_sem
\* never gives swap data to a woken thread ("data").
CallMatch(m, t) ==
    /\ m.fn = t.fn
    /\ m.obj = t.obj
    /\ m.arg = t.arg
    /\ m.ret = t.ret
    /\ m.res = t.res
    /\ Has(t, "thread") => m.thread = t.thread
    /\ ~Has(t, "bad")
    /\ Has(t, "data") => t.data = 0

CallsMatch(mc, tc) ==
    /\ Len(mc) = Len(tc)
    /\ \A k \in 1..Len(tc) : CallMatch(mc[k], tc[k])

MatchApi(s) ==
    /\ obs'.op = s.op
    /\ obs'.actor = s.actor
    /\ obs'.obj = s.obj
    /\ s.op = "take" => obs'.timeout = s.timeout
    /\ s.op = "init" => obs'.args = s.args
    /\ obs'.ret = s.ret
    /\ CallsMatch(obs'.calls, s.calls)
    \* The count and the limit after the call. The memory of a semaphore
    \* that k_sem_init() did not initialize has no value in the model.
    /\ (s.count >= 0 /\ r'[s.obj].init) => r'[s.obj].count = s.count
    /\ (s.limit >= 0 /\ r'[s.obj].init) => r'[s.obj].limit = s.limit

MatchEnv(s) ==
    /\ obs'.op = "env"
    /\ IF s.op = "ThreadTimeout"
         THEN /\ tq # <<>>
              /\ Head(tq) = s.thread
              /\ K!S!ThreadTimeout("c1")
         ELSE \E a \in K!Actors : K!S!Abort(a, s.thread)

\* The next step of the trace.
EventStep ==
    /\ i < Len(Steps)
    /\ LET s == Steps[i + 1] IN
       IF s.kind = "panic"
         THEN /\ panic # "none"
              /\ UNCHANGED kvars
         ELSE /\ K!Next
              /\ IF s.kind = "env" THEN MatchEnv(s) ELSE MatchApi(s)
    /\ i' = i + 1
    /\ h' = 0

\* A hidden step: a step of KSem that the trace does not show.
HiddenStep ==
    /\ i < Len(Steps)
    /\ h < HiddenMax
    /\ K!Next
    /\ IF IsRef
         THEN /\ obs'.op = "env"
              /\ \E c \in {"c1"} : K!S!Preempt(c) \/ K!S!PendSV(c)
         ELSE /\ req[Caller] # "none"
              /\ obs'.actor # Caller
    /\ i' = i
    /\ h' = h + 1

TraceNext == EventStep \/ HiddenStep

TraceSpec == TraceInit /\ [][TraceNext]_tvars

-----------------------------------------------------------------------------
(* The checks *)

\* The register 1 holds the longest matched prefix. Run TLC with one
\* worker: the register belongs to the worker.
ASSUME TLCSet(1, 0)
Progress == IF i > TLCGet(1) THEN TLCSet(1, i) ELSE TRUE

\* Positive acceptance: a behavior matched all steps of the trace. On a
\* rejection, the output names the first step that no behavior matched.
Accepted ==
    \/ TLCGet(1) = Len(Steps)
    \/ PrintT(<<"rejected: steps matched", TLCGet(1), "of", Len(Steps),
                "first step not matched", Steps[TLCGet(1) + 1]>>) /\ FALSE

\* The refinement property: each step of the trace behavior is a step of
\* KSem (or a stutter at a panic).
RefinesKSem == [][K!Next \/ UNCHANGED kvars]_kvars

\* The current step, for the error traces.
Alias == [i |-> i, h |-> h, step |-> IF i > 0 THEN Steps[i] ELSE "none",
          r |-> r, pendedOn |-> pendedOn, tstate |-> tstate, cur |-> cur,
          swapRet |-> swapRet, req |-> req, tq |-> tq, obs |-> obs]

\* The aliases of the properties of KSem for the configuration.
Inv_TypeOK               == K!TypeOK
Inv_ReqIsWait            == K!ReqIsWait
Inv_PendingIsQueued      == K!S!PendingIsQueued
Inv_NoWaitWhileAvailable == K!NoWaitWhileAvailable
Inv_CountLeLimit         == K!CountLeLimit
Inv_TokenConservation    == K!TokenConservation
Prop_CallsHoldLock         == K!CallsHoldLock
Prop_GiveHandsOverOrCounts == K!GiveHandsOverOrCounts
Prop_GiveWakesHighest      == K!GiveWakesHighest
Prop_TakeResult            == K!TakeResult
Prop_ResetWakesAll         == K!ResetWakesAll
Prop_WaitResult            == K!WaitResult
=============================================================================
