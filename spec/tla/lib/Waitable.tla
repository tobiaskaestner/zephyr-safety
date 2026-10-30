------------------------------ MODULE Waitable ------------------------------
(***************************************************************************)
(* Layer B: the template of a kernel object with a wait queue. Minimal     *)
(* version (roadmap step 2, the k_sem slice): only the actions that KSem   *)
(* needs. Each action is one critical section of the object lock at the    *)
(* grain of the scheduler contract (level 1, coarse).                      *)
(*                                                                         *)
(* - Take: the resource is available (Consume), or the call returns        *)
(*   NoWaitRet (K_NO_WAIT), or the caller waits (Scheduler!PendCurr).      *)
(* - Give: the best waiter gets the resource (z_sched_wake()), or the      *)
(*   resource changes (Settle) and the poll events get a signal.           *)
(* - Flush: all waiters stop to wait with FlushRet, the resource becomes   *)
(*   FlushR, and the poll events get a signal (k_sem_reset()).             *)
(* - ResumeOp: a thread returns from its wait with the value of the waker  *)
(*   (Scheduler!Resume).                                                   *)
(* - InitOp: the init function of the object, with z_waitq_init().         *)
(*                                                                         *)
(* The object module gives its operators as arguments (design note,        *)
(* "Composition pattern"), not as CONSTANT operators.                      *)
(*                                                                         *)
(* The variables of the template: r, the resource of each object (the      *)
(* object module defines its fields); req, the object of the wait of each  *)
(* thread, from the wait to the return (None if the thread has no wait);   *)
(* obs, the observation of the last step.                                  *)
(*                                                                         *)
(* The observation record obs has a generic part: the actor, the           *)
(* operation, the object, the arguments, the timeout, the return value,    *)
(* the woken threads, and calls: the calls of the step into the lock and   *)
(* into the scheduler contract, in order (the hook-call record of the      *)
(* review, answer Q3). One call is a record [fn, obj, arg, ret, res, thread]: *)
(* the C function, the object, the argument that the contract fixes (the   *)
(* swap return value of a wake, the timeout of a wait, the poll state),    *)
(* the return value (1 or 0 for a bool), the measure of the resource at    *)
(* the call (Res of the object: the count of a semaphore), and the woken   *)
(* thread of a wake (Idle if none). The trace hook of the unit tests       *)
(* writes the same calls from the fakes, so a trace check compares them    *)
(* one by one. The record also shows the lock discipline of the grain      *)
(* assumption: each step that takes the lock has the lock as its first     *)
(* call and one release as its last call.                                  *)
(***************************************************************************)
EXTENDS Integers, Sequences, FiniteSets

CONSTANTS Threads, Objs, None, Isrs, IsrCpu, MaxIrqNest, Idle, Data, NoData, JoinQ,
          CPUS, UseSwitch, Backend, HeapCapacity

VARIABLES
    \* The variables of Scheduler (and of WaitQueue, Timeout, Platform).
    tstate, prio, cur, swapRet, swapData, panic, rqStamp, preemptOk, readySince,
    pendedOn, stamp, tq, tqCost, irqNest, pendsv,
    \* The resource of each object. The object module defines the fields.
    r,
    \* The object of the wait of each thread, until the thread returns from
    \* the wait (None: no wait). The scheduler forgets the object at the
    \* wake (pendedOn); the object needs it for the return.
    req,
    \* The observation of the last step.
    obs

\* The scheduler contract.
S == INSTANCE Scheduler

schedVars == <<tstate, prio, cur, swapRet, swapData, panic, rqStamp, preemptOk, readySince,
               pendedOn, stamp, tq, tqCost, irqNest, pendsv>>

OK     == S!OK
EAGAIN == S!EAGAIN
NoRet  == S!NoRet

-----------------------------------------------------------------------------
(* The observation record *)

\* The names of the calls, as the trace hook of the unit tests writes them
\* (the C functions that the fakes replace). The lock and its release are
\* arch_irq_lock() and arch_irq_unlock() below k_spin_lock() and
\* k_spin_unlock() (one CPU, no spinlock validation).
LockFn     == "arch_irq_lock"
UnlockFn   == "arch_irq_unlock"
ReschedFn  == "z_reschedule"
PendFn     == "z_pend_curr"
WakeFn     == "z_sched_wake"
PollFn     == "z_handle_obj_poll_events"
WaitqInitFn == "z_waitq_init"

\* One call of a step.
\* @typeAlias: call = { fn: Str, obj: OBJ, arg: Int, ret: Int, res: Int, thread: THREAD };
\* @type: (Str, OBJ, Int, Int, Int, THREAD) => $call;
Call(fn, o, arg, ret, res, t) ==
    [fn |-> fn, obj |-> o, arg |-> arg, ret |-> ret, res |-> res, thread |-> t]

\* The integer of a bool return value.
B2I(b) == IF b THEN 1 ELSE 0

\* The argument of z_pend_curr() in the call record: -1 for K_FOREVER, 1 for
\* a finite timeout. K_NO_WAIT never pends (0).
TimeoutArg(to) == CASE to = "FOREVER" -> -1
                    [] to = "TICKS"   -> 1
                    [] OTHER          -> 0

LockCall(o, res)          == Call(LockFn, o, 0, 0, res, Idle)
ReleaseCall(kind, o, res) == Call(IF kind = "unlock" THEN UnlockFn ELSE ReschedFn, o, 0, 0, res, Idle)
PendCall(o, to, res)      == Call(PendFn, o, TimeoutArg(to), 0, res, Idle)
\* z_sched_wake(): woke is TRUE if a thread t stopped its wait.
WakeCall(o, ret, woke, res, t) == Call(WakeFn, o, ret, B2I(woke), res, t)
PollCall(o, state, ready, res) == Call(PollFn, o, state, B2I(ready), res, Idle)
WaitqInitCall(o, res)     == Call(WaitqInitFn, o, 0, 0, res, Idle)

\* The observation of "nothing happened yet", and of a step that is not a
\* call of the object (op "env").
NoObs == [actor   |-> Idle,
          op      |-> "none",
          obj     |-> None,
          args    |-> <<>>,
          timeout |-> "none",
          calls   |-> <<>>,
          ret     |-> NoRet,
          woken   |-> {}]

Obs(a, op, o, to, calls, ret, woken) ==
    [NoObs EXCEPT !.actor = a, !.op = op, !.obj = o, !.timeout = to, !.calls = calls,
                  !.ret = ret, !.woken = woken]

\* The step changes no thread, no wait queue and no timeout, and ends with
\* the release kind (Scheduler!Release: an ISR, and a thread with
\* "resched", are at a reschedule point).
ReleaseOnly(a, kind) ==
    /\ UNCHANGED <<tstate, prio, swapRet, swapData, panic, rqStamp, preemptOk, readySince,
                   pendedOn, stamp, tq, tqCost>>
    /\ S!Release(a, kind)

\* The values of a free result of a hook: the poll events can make a
\* polling thread ready (the model has no polling threads).
PollResults(notify) == IF notify THEN BOOLEAN ELSE {FALSE}

-----------------------------------------------------------------------------
(* The actions *)

\* The take of actor a on object o with the timeout to. Avail(x) is TRUE if
\* the resource x can be taken now, Consume(x) is the resource after the
\* take, NoWaitRet is the return value for K_NO_WAIT, Res(x) the measure of
\* the resource in the call records. A wait is Scheduler!PendCurr: it adds
\* the caller to the wait queue and releases the lock in the same step
\* (z_pend_curr()), so no give can come between the check and the wait. An
\* ISR that waits makes the scheduler panic (PendCurr).
\* @kind action
Take(o, a, to, Avail(_), Consume(_), NoWaitRet, Res(_)) ==
    /\ panic = "none"
    /\ S!CanCall(a)
    /\ LET x  == r[o]
           c0 == Res(x)
       IN
       IF Avail(x)
         THEN /\ r' = [r EXCEPT ![o] = Consume(x)]
              /\ ReleaseOnly(a, "unlock")
              /\ obs' = Obs(a, "take", o, to,
                            <<LockCall(o, c0), ReleaseCall("unlock", o, Res(Consume(x)))>>, OK, {})
              /\ UNCHANGED req
       ELSE IF to = "NO_WAIT"
         THEN /\ ReleaseOnly(a, "unlock")
              /\ obs' = Obs(a, "take", o, to,
                            <<LockCall(o, c0), ReleaseCall("unlock", o, c0)>>, NoWaitRet, {})
              /\ UNCHANGED <<r, req>>
         ELSE /\ S!PendCurr(a, o, to)
              /\ req' = IF a \in Threads THEN [req EXCEPT ![a] = o] ELSE req
              /\ obs' = Obs(a, "take", o, to, <<LockCall(o, c0), PendCall(o, to, c0)>>, NoRet, {})
              /\ UNCHANGED r

\* The give of actor a on object o. If a thread waits, the best waiter
\* stops to wait with the return value OK (z_sched_wake()), the resource
\* does not change, and the step ends with z_reschedule(). Else the
\* resource becomes Settle(x), and with Notify the poll events get the
\* signal at the measure after the change (z_handle_obj_poll_events() with
\* the state PollState). The step ends with z_reschedule() if a polling
\* thread became ready, else with the unlock.
\* @kind action
Give(o, a, Settle(_), Res(_), Notify, PollState) ==
    /\ panic = "none"
    /\ S!CanCall(a)
    /\ LET x  == r[o]
           c0 == Res(x)
       IN
       IF S!HasWaiters(o)
         THEN LET t == S!WQ!Best(o) IN
              /\ S!WakeFirst(o, OK, NoData)
              /\ S!Release(a, "resched")
              /\ obs' = Obs(a, "give", o, "none",
                            <<LockCall(o, c0), WakeCall(o, OK, TRUE, c0, t),
                              ReleaseCall("resched", o, c0)>>, NoRet, {t})
              /\ UNCHANGED <<r, req>>
         ELSE LET x1 == Settle(x) IN
              \E ready \in PollResults(Notify) :
              /\ r' = [r EXCEPT ![o] = x1]
              /\ ReleaseOnly(a, IF ready THEN "resched" ELSE "unlock")
              /\ obs' = Obs(a, "give", o, "none",
                            <<LockCall(o, c0), WakeCall(o, OK, FALSE, c0, Idle)>>
                            \o (IF Notify THEN <<PollCall(o, PollState, ready, Res(x1))>> ELSE <<>>)
                            \o <<ReleaseCall(IF ready THEN "resched" ELSE "unlock", o, Res(x1))>>,
                            NoRet, {})
              /\ UNCHANGED req

\* The flush of actor a on object o: the loop "while (z_sched_wake())"
\* wakes all waiters with FlushRet in wait queue order (the last call
\* returns false), the resource becomes FlushR(x), and with Notify the
\* poll events get the signal. The step ends with z_reschedule() if a
\* thread became ready (a waiter, or a polling thread), else with the
\* unlock.
\* @kind action
Flush(o, a, FlushRet, FlushR(_), Res(_), Notify, PollState) ==
    /\ panic = "none"
    /\ S!CanCall(a)
    /\ LET x  == r[o]
           c0 == Res(x)
           x1 == FlushR(x)
           Q  == S!WQ!Ordered(o)
       IN
       \E ready \in PollResults(Notify) :
       /\ S!WakeAll(o, FlushRet, NoData)
       /\ r' = [r EXCEPT ![o] = x1]
       /\ S!Release(a, IF Q # <<>> \/ ready THEN "resched" ELSE "unlock")
       /\ obs' = Obs(a, "flush", o, "none",
                     <<LockCall(o, c0)>>
                     \o [k \in 1..Len(Q) |-> WakeCall(o, FlushRet, TRUE, c0, Q[k])]
                     \o <<WakeCall(o, FlushRet, FALSE, c0, Idle)>>
                     \o (IF Notify THEN <<PollCall(o, PollState, ready, Res(x1))>> ELSE <<>>)
                     \o <<ReleaseCall(IF Q # <<>> \/ ready THEN "resched" ELSE "unlock", o, Res(x1))>>,
                     NoRet, {Q[k] : k \in 1..Len(Q)})
       /\ UNCHANGED req

\* Thread t returns from its wait on req[t]: z_pend_curr() returns the swap
\* return value (Scheduler!Resume), and the object call returns it. The
\* object forgets the wait.
\* @kind action
ResumeOp(t) ==
    /\ req[t] # None
    /\ S!Resume(t)
    /\ obs' = Obs(t, "resume", req[t], "none", <<>>, swapRet[t], {})
    /\ req' = [req EXCEPT ![t] = None]
    /\ UNCHANGED r

\* The init function of object o by thread a with the arguments args. If
\* Valid(args) is FALSE, the call returns ErrRet and changes nothing. Else
\* the resource becomes New(args), the wait queue becomes empty
\* (Scheduler!WaitqInit: undefined behavior if threads wait), and the call
\* returns OK. The init takes no lock: the step is atomic only if no other
\* actor uses the object at the same time.
\* @kind action
InitOp(o, a, args, Valid(_), New(_), ErrRet, Res(_)) ==
    /\ panic = "none"
    /\ a \in Threads
    /\ S!CanCall(a)
    /\ IF Valid(args)
         THEN /\ r' = [r EXCEPT ![o] = New(args)]
              /\ S!WaitqInit(o)
              /\ obs' = [Obs(a, "init", o, "none", <<WaitqInitCall(o, Res(New(args)))>>, OK, {})
                         EXCEPT !.args = args]
         ELSE /\ UNCHANGED <<r, panic>>
              /\ obs' = [Obs(a, "init", o, "none", <<>>, ErrRet, {}) EXCEPT !.args = args]
    /\ UNCHANGED <<tstate, prio, cur, swapRet, swapData, rqStamp, preemptOk, readySince,
                   pendedOn, stamp, tq, tqCost, irqNest, pendsv, req>>

\* A step of the environment of the scheduler (Scheduler!EnvNext) in an
\* object model. The object takes the return from a wait as its own step
\* (ResumeOp), so this step is not a Resume: no thread that stays alive
\* loses its swap return value. A thread that dies forgets its wait.
\* @kind action
EnvStep(P) ==
    /\ S!EnvNext(P)
    /\ \A t \in Threads : (swapRet[t] # NoRet /\ swapRet'[t] = NoRet) => tstate'[t] = "dead"
    /\ req' = [t \in Threads |-> IF tstate'[t] = "dead" THEN None ELSE req[t]]
    /\ obs' = [NoObs EXCEPT !.op = "env"]
    /\ UNCHANGED r

-----------------------------------------------------------------------------
(* Properties of the template *)

\* Each call of a step that takes the lock starts with the lock and ends
\* with exactly one release (unlock, z_reschedule() or z_pend_curr()). The
\* grain assumption of the coarse module in the terms of the record. The
\* trace check compares the record of the code with this record.
\* @kind definition
\* @type: (Seq($call)) => Bool;
LockDiscipline(calls) ==
    LET n == Len(calls)
        \* @type: ($call) => Bool;
        IsRelease(c) == c.fn \in {UnlockFn, ReschedFn, PendFn}
    IN  /\ n >= 2
        /\ calls[1].fn = LockFn
        /\ IsRelease(calls[n])
        /\ \A k \in 2..(n - 1) : calls[k].fn \notin {LockFn, UnlockFn, ReschedFn, PendFn}

\* A thread has a wait of the object model if and only if it waits in the
\* wait queue of that object, or it was woken and has not returned yet.
\* @kind invariant
ReqIsWait ==
    \A t \in Threads :
        /\ pendedOn[t] # None => req[t] = pendedOn[t]
        /\ (req[t] # None) => (pendedOn[t] = req[t] \/ (tstate[t] = "ready" /\ swapRet[t] # NoRet))

=============================================================================
