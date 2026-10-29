----------------------------- MODULE Scheduler -----------------------------
(***************************************************************************)
(* Layer A: the contract of the scheduler API that the kernel objects call *)
(* (kernel/sched.c, kernel/include/ksched.h).                              *)
(*                                                                         *)
(* Level 1: each operator is a part of one critical section. An object     *)
(* action composes them: first the changes of the wait queues and of the   *)
(* thread states (PendCurr, WakeFirst, WakeAll, WakeWalk), then the end of *)
(* the critical section (Release). PendCurr includes its Release.          *)
(*                                                                         *)
(* Two layers. The operators are the descriptive layer: they follow the    *)
(* code (@c-function), also where the code is surprising. The properties   *)
(* with a @source tag are the normative layer: each one states a           *)
(* requirement or a documented rule, written from that source and not from *)
(* the code. A property that fails on the model is a design finding.       *)
(*                                                                         *)
(* CPUs are explicit. cur[c] is the thread that runs on CPU c. One CPU is  *)
(* the default, and level 1 claims one CPU only. On one CPU the model has  *)
(* the run queue order (rqStamp) and the cache of the code: the argument   *)
(* of the last update_cache() (preemptOk). Each reschedule point switches  *)
(* to the cache (CacheOf). On SMP the selection is the old free rule       *)
(* (SmpChoices), a design exploration: the run queue variables keep their  *)
(* initial values. The model has no time slices, no k_yield(), no          *)
(* scheduler lock (k_sched_lock()), no meta-IRQ threads and no CPU masks.  *)
(*                                                                         *)
(* The world below sched.c is the module Platform (PF): the CPUs, the ISRs *)
(* and their CPUs (the constants CPUS, Isrs and IsrCpu are parameters of   *)
(* Platform), the outer interrupt lock (irqNest), the in-ISR state and the *)
(* two variants of the context switch (UseSwitch, pendsv). At level 1 an   *)
(* ISR is one step, and the exit of the ISR is a reschedule point. With    *)
(* arch_swap() (UseSwitch FALSE) a reschedule point only sets PendSV       *)
(* pending, and the step PendSV selects the thread later.                  *)
(*                                                                         *)
(* Priorities: prio[t] is the model priority, a greater value is a higher  *)
(* priority (as in WaitQueue). Zephyr uses the reverse, and a negative     *)
(* Zephyr priority is a cooperative thread. ToZephyr is the only           *)
(* conversion.                                                             *)
(*                                                                         *)
(* A panic stops the system. panic gives the cause. Each action of this    *)
(* module and of the modules that use it requires panic = "none".          *)
(***************************************************************************)
EXTENDS Integers, Sequences, FiniteSets

CONSTANTS
    \* @type: Set(THREAD);
    Threads,
    \* @type: Set(OBJ);
    Objs,
    \* The value of pendedOn for a thread that does not wait.
    \* @type: OBJ;
    None,
    \* The parameters of Platform: the CPUs, the ISR actors of the objects
    \* (not the timer ISR of the expiry) and the CPU of each ISR.
    \* @type: Set(CPU);
    CPUS,
    \* @type: Set(THREAD);
    Isrs,
    \* @type: THREAD -> CPU;
    IsrCpu,
    \* The parameters of Platform: the bound of the nested irq_lock() calls
    \* and the variant of the context switch (CONFIG_USE_SWITCH).
    \* @type: Int;
    MaxIrqNest,
    \* @type: Bool;
    UseSwitch,
    \* cur[c] = Idle: the idle thread of CPU c runs.
    \* @type: THREAD;
    Idle,
    \* The values that a waker gives to a woken thread (swap data).
    \* @type: Set(DATA);
    Data,
    \* The swap data of a thread that has none.
    \* @type: DATA;
    NoData,
    \* The backend of the timeout queue (see Timeout).
    \* @type: Str;
    Backend,
    \* @type: Int;
    HeapCapacity

VARIABLES
    \* The state of each thread: "ready", "pending" or "dead". A running
    \* thread is ready and is cur[c] of one CPU.
    \* @type: THREAD -> Str;
    tstate,
    \* The model priority of each thread.
    \* @type: THREAD -> Int;
    prio,
    \* The thread that runs on each CPU, or Idle.
    \* @type: CPU -> THREAD;
    cur,
    \* The value that z_swap() returns to a thread after a wait. NoRet if
    \* the thread does not wait and has no wait to return from.
    \* @type: THREAD -> Int;
    swapRet,
    \* The data that the waker gives (thread->base.swap_data).
    \* @type: THREAD -> DATA;
    swapData,
    \* "none", or the cause of the panic.
    \* @type: Str;
    panic,
    \* The position of each ready thread in the run queue, among the threads
    \* with the same priority: 1..N over all ready threads, 0 for a thread
    \* that is not ready. On one CPU the current thread stays in the run
    \* queue (next_up()). On SMP the value stays at 0.
    \* @type: THREAD -> Int;
    rqStamp,
    \* The argument preempt_ok of the last update_cache() call (one CPU).
    \* The code stores the result, _kernel.ready_q.cache. The model stores
    \* the argument and computes the cache when it needs it (CacheOf). The
    \* two agree, because each change of the run queue, of a priority of a
    \* ready thread or of a thread state calls update_cache().
    \* @type: Bool;
    preemptOk,
    \* A history variable of the normative layer, not a field of the code:
    \* the order in which the ready threads became ready (1..N, threads
    \* that became ready in the same step have the same value), 0 for a
    \* thread that is not ready. A priority change does not change it. The
    \* property TieGoesToLongestReady reads it. On SMP the value stays at 0.
    \* @type: THREAD -> Int;
    readySince,
    \* The variables of WaitQueue and Timeout.
    \* @type: THREAD -> OBJ;
    pendedOn,
    \* @type: THREAD -> Int;
    stamp,
    \* @type: Seq(THREAD);
    tq,
    \* @type: { op: Str, n: Int, cost: Int };
    tqCost,
    \* The variables of Platform: the outer interrupt lock of each CPU and
    \* the pending PendSV of each CPU.
    \* @type: CPU -> Int;
    irqNest,
    \* @type: CPU -> Bool;
    pendsv

ASSUME None \notin Objs
ASSUME Idle \notin Threads \cup Isrs
ASSUME NoData \notin Data

\* The world below sched.c: CPUs, actors, interrupt lock, switch.
PF == INSTANCE Platform

\* The waiters and their order.
WQ == INSTANCE WaitQueue

\* The timeouts of the waiting threads.
TO == INSTANCE Timeout WITH Entries <- Threads

rqVars == <<rqStamp, preemptOk, readySince>>

schedVars == <<tstate, prio, cur, swapRet, swapData, panic, rqStamp, preemptOk, readySince,
               pendedOn, stamp, tq, tqCost, irqNest, pendsv>>

\* Return values, with the values of the C error codes.
OK     == 0
EAGAIN == -11
\* "no return value": the thread has no wait to return from.
NoRet  == 1

\* The timeouts of a wait. "TICKS" is any finite timeout. K_NO_WAIT never
\* pends: the object returns without a call of PendCurr.
WaitTimeouts == {"FOREVER", "TICKS"}

ThreadStates == {"ready", "pending", "dead"}

\* One CPU: the run queue order and the cache are in the model.
UP == Cardinality(CPUS) = 1

-----------------------------------------------------------------------------
(* Priorities *)

\* The Zephyr priority of the model priority p, and the reverse.
ToZephyr(p) == -p
FromZephyr(z) == -z

\* A thread with a negative Zephyr priority is cooperative: no thread
\* preempts it, it runs until it waits or ends.
Cooperative(p) == ToZephyr(p) < 0

-----------------------------------------------------------------------------
(* Queries *)

\* Thread t runs on a CPU: it is _current of that CPU.
Running(t) == \E c \in CPUS : cur[c] = t

\* Thread t executes its code on a CPU: it is _current, and no switch is
\* pending on that CPU (see Platform!SwitchPending).
Executes(t) == \E c \in CPUS : cur[c] = t /\ ~PF!SwitchPending(c)

\* Actor a can call the kernel API now: an ISR while its CPU has
\* interrupts unlocked, or a thread that executes and does not return from
\* a wait now (see Resume).
CanCall(a) ==
    IF a \in Isrs THEN PF!IrqCanRun(IsrCpu[a]) ELSE Executes(a) /\ swapRet[a] = NoRet

\* The CPU of actor a. Defined only if a is an ISR or a running thread. A
\* thread runs on at most one CPU (invariant CurUnique), so the CHOOSE has
\* exactly one witness.
CpuOf(a) == IF a \in Isrs THEN IsrCpu[a] ELSE CHOOSE c \in CPUS : cur[c] = a

\* The thread waits on an object and has a finite timeout.
TimedWait(t) == t \in TO!Armed

\* The constant function with the value v on S (the return values of a
\* wake).
\* @type: (Set(THREAD), a) => (THREAD -> a);
Const(S, v) == [t \in S |-> v]

\* The ready threads.
Ready == {t \in Threads : tstate[t] = "ready"}

-----------------------------------------------------------------------------
(* The run queue on one CPU (kernel/include/run_q.h, priority_q.h). The    *)
(* arguments are the state after the critical section: ts (tstate), pr     *)
(* (prio), cu (cur), rs (rqStamp) and po (preemptOk).                      *)

\* The run queue order: a comes before b. A higher priority first, then
\* the position. z_priq_simple_add() inserts a thread after each thread with
\* the same priority, z_priq_rb_add() and z_priq_mq_add() do the same.
\* @type: (THREAD -> Int, THREAD -> Int, THREAD, THREAD) => Bool;
RqBefore(pr, rs, a, b) ==
    \/ pr[a] > pr[b]
    \/ /\ pr[a] = pr[b]
       /\ rs[a] < rs[b]

\* The head of the run queue, or Idle if no thread is ready. The ready
\* threads have different positions (invariant RqStampsNormal), so the
\* CHOOSE has exactly one witness.
\* @kind definition
\* @c-function runq_best
\* @type: (THREAD -> Str, THREAD -> Int, THREAD -> Int) => THREAD;
RunqBest(ts, pr, rs) ==
    LET R == {t \in Threads : ts[t] = "ready"}
    IN  IF R = {} THEN Idle
        ELSE CHOOSE t \in R : \A u \in R \ {t} : RqBefore(pr, rs, t, u)

\* The cache of CPU c: update_cache(po) on one CPU. next_up() gives the
\* head of the run queue, which can be the current thread.
\* should_preempt() accepts the head if po is TRUE, if the current thread
\* cannot run (pending, dead) or is the idle thread, or if the current
\* thread is preemptible. Else the cache is the current thread. Thus with
\* po TRUE the cooperative rule does not apply. "The current thread wins a
\* tie" is only a result of its position in the run queue.
\* @kind definition
\* @c-function update_cache
\* @c-function next_up
\* @c-function should_preempt
\* @type: (CPU, THREAD -> Str, THREAD -> Int, CPU -> THREAD, THREAD -> Int, Bool) => THREAD;
CacheOf(c, ts, pr, cu, rs, po) ==
    LET u == cu[c] IN
    IF \/ po
       \/ u = Idle
       \/ ts[u] # "ready"
       \/ ~Cooperative(pr[u])
      THEN RunqBest(ts, pr, rs)
      ELSE u

\* The positions of N ready threads: each order of 1..N.
RqOrders == {f \in [Threads -> 1..Cardinality(Threads)] :
                \A a, b \in Threads : a # b => f[a] # f[b]}

\* The stamps rs, renumbered to 1..N over the ready threads R.
\* @type: (THREAD -> Int, Set(THREAD)) => (THREAD -> Int);
RqNormal(rs, R) == WQ!Renumber(rs, R)

\* A position after each position of a ready thread.
NextRq == Cardinality(Ready) + 1

\* The run queue part of a step on one CPU: the new positions rs, the
\* argument po of the last update_cache() of the step, and the new
\* history rsince. On SMP the three variables do not change.
\* @type: (THREAD -> Int, Bool, THREAD -> Int) => Bool;
RqStep(rs, po, rsince) ==
    IF UP
      THEN /\ rqStamp' = rs
           /\ preemptOk' = po
           /\ readySince' = rsince
      ELSE UNCHANGED rqVars

\* The threads in S become ready (they were not ready): ready_thread() for
\* each one. queue_thread() adds each one at the end of its priority, and
\* update_cache(0) follows. The code adds them in the order of its wake
\* loop: the wait queue order for z_sched_wake() in a loop, the walk order
\* for z_sched_waitq_walk() (the reverse with CONFIG_WAITQ_SCALABLE, see
\* k_event_post_internal()). No document gives an order among threads
\* that become ready in one critical section, so the model accepts each
\* order (k, an order of all threads, of which only the order on S
\* counts). In the history, the threads of S have the same value. If S is
\* empty, the code calls no ready_thread(): no change.
\* @kind action
\* @c-function ready_thread
\* @c-function queue_thread
\* @type: (Set(THREAD)) => Bool;
QueueReady(S) ==
    IF S = {}
      THEN UNCHANGED rqVars
      ELSE \E k \in RqOrders :
             RqStep(RqNormal([t \in Threads |-> IF t \in S THEN NextRq + k[t] ELSE rqStamp[t]],
                             Ready \cup S),
                    FALSE,
                    RqNormal([t \in Threads |-> IF t \in S THEN NextRq ELSE readySince[t]],
                             Ready \cup S))

\* The positions after thread t (ready) leaves the run queue and comes
\* back: dequeue_thread() and queue_thread(). t comes after each ready
\* thread with the same priority (prio' gives the priority).
\* @type: (THREAD) => (THREAD -> Int);
Requeue(t) == RqNormal([rqStamp EXCEPT ![t] = NextRq], Ready)

\* Thread t stops to be ready: dequeue_thread() and update_cache(1). The
\* argument is 1 for the current thread in unready_thread() and always in
\* halt_thread().
\* @type: (THREAD) => Bool;
Unqueue(t) ==
    RqStep(RqNormal(rqStamp, Ready \ {t}), TRUE, RqNormal(readySince, Ready \ {t}))

-----------------------------------------------------------------------------
(* The selection rule. The arguments are the state after the critical      *)
(* section.                                                                *)

\* The threads that CPU c can select: ready, and not current on another
\* CPU.
\* @type: (CPU, THREAD -> Str, CPU -> THREAD) => Set(THREAD);
Candidates(c, ts, cu) ==
    {t \in Threads : ts[t] = "ready" /\ \A d \in CPUS \ {c} : cu[d] # t}

\* The threads of S with the highest priority.
\* @type: (Set(THREAD), THREAD -> Int) => Set(THREAD);
Top(S, pr) == {t \in S : \A u \in S : pr[u] <= pr[t]}

\* The selection on SMP (design exploration, not a claim of level 1): a
\* ready cooperative thread keeps the CPU, else the current thread wins a
\* tie, else any thread with the highest priority. This is the rule of
\* next_up() with swap_ok = 0, without the run queue order.
\* @kind definition
\* @type: (CPU, THREAD -> Str, THREAD -> Int, CPU -> THREAD) => Set(THREAD);
SmpChoices(c, ts, pr, cu) ==
    LET u == cu[c]
        S == Candidates(c, ts, cu)
    IN  IF u # Idle /\ ts[u] = "ready" /\ Cooperative(pr[u]) THEN {u}
        ELSE IF S = {} THEN {Idle}
        ELSE IF u \in Top(S, pr) THEN {u}
        ELSE Top(S, pr)

\* The threads that CPU c can select at a reschedule point. On one CPU this
\* is the cache (one thread), on SMP the free rule SmpChoices.
\* @kind definition
\* @c-function z_reschedule
\* @c-function need_swap
\* @type: (CPU, THREAD -> Str, THREAD -> Int, CPU -> THREAD, THREAD -> Int, Bool) => Set(THREAD);
Choices(c, ts, pr, cu, rs, po) ==
    IF UP THEN {CacheOf(c, ts, pr, cu, rs, po)} ELSE SmpChoices(c, ts, pr, cu)

\* CPU c is at a reschedule point: z_swap(), or the exit of an interrupt.
\* The caller sets tstate', prio', rqStamp' and preemptOk' first. With
\* CONFIG_USE_SWITCH (and on SMP) the CPU selects a thread in this step.
\* With arch_swap() the step sets PendSV pending if the cache differs from
\* the current thread, and the step PendSV selects later
\* (Platform!RequestPendSV).
\* @kind action
Select(c) ==
    IF PF!SwitchAtOnce
      THEN /\ \E t \in Choices(c, tstate', prio', cur, rqStamp', preemptOk') :
                cur' = [cur EXCEPT ![c] = t]
           /\ UNCHANGED <<irqNest, pendsv>>
      ELSE /\ PF!RequestPendSV(c, CacheOf(c, tstate', prio', cur, rqStamp', preemptOk') # cur[c])
           /\ UNCHANGED cur

\* resched(key) of z_reschedule(): a thread can switch only if the key of
\* the critical section is unlocked (no outer irq_lock()) and the actor is
\* not an ISR. Else z_reschedule() ends with k_spin_unlock() and the CPU
\* keeps its thread.
\* @kind definition
\* @c-function resched
ReschedOk(a, c) == PF!KeyUnlocked(c) /\ ~PF!InIsr(a)

\* The end of the critical section of actor a. kind:
\*
\* - "unlock": k_spin_unlock(), a thread keeps its CPU.
\* - "resched": z_reschedule(). If ReschedOk, the CPU of a is at a
\*   reschedule point (need_swap() and z_swap()). Else as "unlock": the
\*   selection waits for the next reschedule point (finding P2-w).
\* - "swap": z_swap(), the CPU of a is at a reschedule point (a stopped).
\*
\* For an ISR each kind is the same: z_reschedule() does not switch in an
\* ISR, and the exit of the ISR is a reschedule point.
\* @kind action
\* @c-function z_reschedule
\* @c-function k_spin_unlock
Release(a, kind) ==
    IF a \in Isrs THEN Select(IsrCpu[a])
    ELSE IF \/ kind = "unlock"
            \/ kind = "resched" /\ ~ReschedOk(a, CpuOf(a))
      THEN UNCHANGED <<cur, irqNest, pendsv>>
      ELSE Select(CpuOf(a))

-----------------------------------------------------------------------------
(* Layer A: one operator for each function that the objects call.         *)

\* z_pend_curr(): the current thread a waits on o with the timeout to. It
\* leaves the CPU, its return value is -EAGAIN until a waker sets another
\* one. From an ISR (Platform!InIsr): panic, and no other change (the
\* check is the first statement of z_pend_curr()). A finite timeout on a full heap: panic in
\* z_add_timeout(). The model then stops; the state of the wait queue at
\* the panic is not modeled. unready_thread() of the current thread calls
\* update_cache(1).
\* @kind action
\* @c-function z_pend_curr
PendCurr(a, o, to) ==
    IF a \in Isrs
      THEN /\ panic' = "pend_in_isr"
           /\ UNCHANGED <<tstate, prio, cur, swapRet, swapData, pendedOn, stamp, tq, tqCost>>
           /\ UNCHANGED <<rqVars, irqNest, pendsv>>
    ELSE IF to = "TICKS" /\ TO!Full
      THEN /\ panic' = "timeout_heap_full"
           /\ UNCHANGED <<tstate, prio, cur, swapRet, swapData, pendedOn, stamp, tq, tqCost>>
           /\ UNCHANGED <<rqVars, irqNest, pendsv>>
    ELSE /\ WQ!Add(a, o)
         /\ IF to = "TICKS" THEN TO!InsertAny(a) ELSE UNCHANGED <<tq, tqCost>>
         /\ tstate' = [tstate EXCEPT ![a] = "pending"]
         /\ swapRet' = [swapRet EXCEPT ![a] = EAGAIN]
         /\ swapData' = [swapData EXCEPT ![a] = NoData]
         /\ UNCHANGED <<prio, panic>>
         /\ Unqueue(a)
         /\ Release(a, "swap")

\* The threads in S stop to wait: they leave the wait queue, their
\* timeouts are cancelled, each one gets its return value ret[t] and its
\* data dat[t], and each one is ready (QueueReady). This is
\* z_sched_wake_thread_locked() with the cancellation of the timeout that
\* its callers do first (z_unpend_first_thread_locked(), event_walk_op()).
\* @kind action
\* @c-function z_sched_wake_thread_locked
\* @type: (Set(THREAD), THREAD -> Int, THREAD -> DATA) => Bool;
WakeSet(S, ret, dat) ==
    /\ WQ!RemoveSet(S)
    /\ TO!CancelSet(S)
    /\ tstate' = [t \in Threads |-> IF t \in S THEN "ready" ELSE tstate[t]]
    /\ swapRet' = [t \in Threads |-> IF t \in S THEN ret[t] ELSE swapRet[t]]
    /\ swapData' = [t \in Threads |-> IF t \in S THEN dat[t] ELSE swapData[t]]
    /\ UNCHANGED <<prio, panic>>
    /\ QueueReady(S)

\* The wait queue of o is not empty: z_sched_wake() returns true.
HasWaiters(o) == WQ!W(o) # {}

\* z_sched_wake(): the best waiter of o stops to wait with ret and data.
\* Enabled only if HasWaiters(o) (else z_sched_wake() returns false and
\* changes nothing).
\* @kind action
\* @c-function z_sched_wake
WakeFirst(o, ret, data) ==
    /\ HasWaiters(o)
    /\ LET S == {WQ!Best(o)} IN WakeSet(S, Const(S, ret), Const(S, data))

\* z_unpend_first_thread_locked() and z_sched_ready_locked(), with object
\* code between them (msgq copy, mutex owner). F(t) gives the pair
\* <<return value, data>> for the woken thread t.
\* @kind action
\* @c-function z_unpend_first_thread_locked
\* @c-function z_sched_ready_locked
\* @type: (OBJ, THREAD => <<Int, DATA>>) => Bool;
WakeFirstWith(o, F(_)) ==
    /\ HasWaiters(o)
    /\ LET S == {WQ!Best(o)}
       IN  WakeSet(S, [t \in S |-> F(t)[1]], [t \in S |-> F(t)[2]])

\* The loop "while (z_sched_wake(...))": all waiters of o stop to wait with
\* ret and data, in one critical section. Also enabled on an empty wait
\* queue (no change), because the loop always runs.
\* @kind action
\* @c-function z_sched_wake_all
WakeAll(o, ret, data) ==
    LET S == WQ!W(o) IN WakeSet(S, Const(S, ret), Const(S, data))

\* z_sched_waitq_walk(): each waiter t of o with P(t) stops to wait, with
\* the return value 0 and the data D(t). The walk order changes only the
\* order of the wakes, not the result of the critical section.
\* @kind action
\* @c-function z_sched_waitq_walk
\* @type: (OBJ, THREAD => Bool, THREAD => DATA) => Bool;
WakeWalk(o, P(_), D(_)) ==
    LET S == {t \in WQ!W(o) : P(t)}
    IN  WakeSet(S, Const(S, OK), [t \in S |-> D(t)])

\* z_thread_prio_set(): the priority of t becomes p, also if p is the old
\* priority. A ready thread leaves the run queue and comes back at the end
\* of the threads with the priority p (dequeue_thread(), queue_thread()).
\* On one CPU this is also true for the current thread. Then
\* update_cache(1): the next reschedule point selects the head of the run
\* queue, without the cooperative rule (see CacheOf). A waiter goes to the
\* end of the waiters of its object with the priority p, without
\* update_cache(). No reschedule: the caller decides
\* (k_thread_priority_set(), the mutex). The history readySince does not
\* change: the thread stays ready.
\* @kind action
\* @c-function z_thread_prio_set
PrioSet(t, p) ==
    /\ tstate[t] # "dead"
    /\ prio' = [prio EXCEPT ![t] = p]
    /\ IF t \in WQ!Waiting THEN WQ!Restamp(t) ELSE UNCHANGED <<pendedOn, stamp>>
    /\ IF tstate[t] = "ready"
         THEN RqStep(Requeue(t), TRUE, readySince)
         ELSE UNCHANGED rqVars
    /\ UNCHANGED <<tstate, swapRet, swapData, panic, tq, tqCost>>

-----------------------------------------------------------------------------
(* Environment actions. The objects do not call them. A model of an       *)
(* object adds them to its next-state relation.                           *)

\* z_thread_timeout() from sys_clock_announce() on CPU c: the first entry of
\* the timeout queue expires. Its thread stops to wait and keeps the return
\* value -EAGAIN. It becomes ready (ready_thread(), update_cache(0)). The
\* exit of the timer ISR is a reschedule point of c. The timer interrupt
\* runs only while c has interrupts unlocked (Platform!ClockCanFire). Only
\* thread waits use this atomic form (see Timeout).
\* @kind action
\* @c-function z_thread_timeout
ThreadTimeout(c) ==
    /\ panic = "none"
    /\ PF!ClockCanFire(c)
    /\ tq # <<>>
    /\ LET t == TO!First IN
       /\ TO!Expire
       /\ WQ!Remove(t)
       /\ tstate' = [tstate EXCEPT ![t] = "ready"]
       /\ UNCHANGED <<prio, swapRet, swapData, panic>>
       /\ QueueReady({t})
       /\ Select(c)

\* k_thread_abort(t) by actor a. t is dead: it leaves the CPU, its wait
\* queue and the timeout queue. halt_thread() calls update_cache(1) for
\* each target, also for a target that is not ready. If a aborts itself,
\* its CPU selects a thread (z_swap()). An ISR selects a thread at its
\* exit. A thread that aborts another thread does not reschedule: the
\* cache can then differ from the current thread until the next
\* reschedule point (finding P7-c).
\* Not in the model: the join queue (an object, later), essential threads
\* (panic), and the abort of a thread that runs on another CPU (level 2:
\* the target halts itself in an IPI, roadmap step 5).
\* @kind action
\* @c-function z_thread_abort
\* @c-function halt_thread
Abort(a, t) ==
    /\ panic = "none"
    /\ CanCall(a)
    /\ tstate[t] # "dead"
    /\ \A c \in CPUS : cur[c] = t => (a = t \/ (a \in Isrs /\ IsrCpu[a] = c))
    /\ IF t \in WQ!Waiting THEN WQ!Remove(t) ELSE UNCHANGED <<pendedOn, stamp>>
    /\ TO!Cancel(t)
    /\ tstate' = [tstate EXCEPT ![t] = "dead"]
    /\ swapRet' = [swapRet EXCEPT ![t] = NoRet]
    /\ swapData' = [swapData EXCEPT ![t] = NoData]
    /\ UNCHANGED <<prio, panic>>
    /\ Unqueue(t)
    /\ Release(a, IF a = t THEN "swap" ELSE "unlock")

\* k_thread_priority_set(t, p) by actor a. It reschedules only if t is
\* ready (the return value of z_thread_prio_set()):
\* z_reschedule_unlocked() takes a new lock, so ReschedOk applies.
\* @kind action
\* @c-function k_thread_priority_set
SetPrio(a, t, p) ==
    /\ panic = "none"
    /\ CanCall(a)
    /\ PrioSet(t, p)
    /\ Release(a, IF tstate[t] = "ready" THEN "resched" ELSE "unlock")

\* Thread t runs again after a wait: z_swap() returns swapRet[t] with
\* swapData[t]. The object reads both in the same step (Waitable).
\* @kind action
Resume(t) ==
    /\ panic = "none"
    /\ Executes(t)
    /\ swapRet[t] # NoRet
    /\ swapRet' = [swapRet EXCEPT ![t] = NoRet]
    /\ swapData' = [swapData EXCEPT ![t] = NoData]
    /\ UNCHANGED <<tstate, prio, cur, panic, pendedOn, stamp, tq, tqCost>>
    /\ UNCHANGED <<rqVars, irqNest, pendsv>>

\* An interrupt on CPU c without a kernel call (a tick, an IPI). Its exit
\* is a reschedule point (Select): on one CPU the cache, without a new
\* update_cache(). Enabled only if the selection changes cur[c], c has
\* interrupts unlocked and no switch is pending on c. On SMP this is the
\* IPI that a wake on another CPU sends (flag_ipi()).
\* @kind action
Preempt(c) ==
    /\ panic = "none"
    /\ PF!IrqCanRun(c)
    /\ ~PF!SwitchPending(c)
    /\ cur[c] \notin Choices(c, tstate, prio, cur, rqStamp, preemptOk)
    /\ UNCHANGED <<tstate, prio, swapRet, swapData, panic, pendedOn, stamp, tq, tqCost>>
    /\ UNCHANGED rqVars
    /\ Select(c)

\* The PendSV handler runs on CPU c (arch_swap() only, one CPU). It switches
\* to the cache as it is when the handler runs. The cache can differ from
\* the cache at the reschedule point that set PendSV pending: an ISR can
\* run in the gap and change it.
\* @kind action
\* @c-function z_arm_pendsv
PendSV(c) ==
    /\ panic = "none"
    /\ PF!PendSVRuns(c)
    /\ cur' = [cur EXCEPT ![c] = CacheOf(c, tstate, prio, cur, rqStamp, preemptOk)]
    /\ UNCHANGED <<tstate, prio, swapRet, swapData, panic, pendedOn, stamp, tq, tqCost>>
    /\ UNCHANGED rqVars

\* irq_lock() by thread a, outside a kernel call (an outer lock). No other
\* change.
\* @kind action
\* @c-function irq_lock
IrqLockCall(a) ==
    /\ panic = "none"
    /\ a \in Threads
    /\ CanCall(a)
    /\ PF!IrqLock(CpuOf(a))
    /\ UNCHANGED <<tstate, prio, cur, swapRet, swapData, panic, pendedOn, stamp, tq, tqCost>>
    /\ UNCHANGED rqVars

\* irq_unlock(key) by thread a with the key of its last irq_lock(). This is
\* not a reschedule point: the cache can differ from the current thread
\* after the step (finding P2-w).
\* @kind action
\* @c-function irq_unlock
IrqUnlockCall(a) ==
    /\ panic = "none"
    /\ a \in Threads
    /\ CanCall(a)
    /\ PF!IrqUnlock(CpuOf(a))
    /\ UNCHANGED <<tstate, prio, cur, swapRet, swapData, panic, pendedOn, stamp, tq, tqCost>>
    /\ UNCHANGED rqVars

\* The initial state: all threads ready with the priorities p0, no waiter,
\* no outer interrupt lock, no pending PendSV.
\* On one CPU: any run queue order, the history is the run queue order,
\* and the CPU runs the head of the run queue (the state after a switch).
\* On SMP: the run queue variables are 0, and on each CPU a thread that the
\* rule can select.
\* @kind definition
InitState(p0) ==
    /\ tstate = [t \in Threads |-> "ready"]
    /\ prio = p0
    /\ swapRet = [t \in Threads |-> NoRet]
    /\ swapData = [t \in Threads |-> NoData]
    /\ panic = "none"
    /\ rqStamp \in IF UP THEN RqOrders ELSE {[t \in Threads |-> 0]}
    /\ readySince = rqStamp
    /\ preemptOk = FALSE
    /\ pendedOn = [t \in Threads |-> None]
    /\ stamp = [t \in Threads |-> 0]
    /\ tq = <<>>
    /\ tqCost = TO!NoCost
    /\ cur \in [CPUS -> Threads \cup {Idle}]
    /\ \A c \in CPUS : cur[c] \in Choices(c, tstate, prio, cur, rqStamp, TRUE)
    /\ \A c, d \in CPUS : c # d /\ cur[c] # Idle => cur[c] # cur[d]
    /\ PF!InitPlatform

\* Fairness of the environment: an armed timeout expires, an IPI arrives,
\* a pending PendSV runs.
Fairness ==
    /\ WF_schedVars(\E c \in CPUS : ThreadTimeout(c))
    /\ \A c \in CPUS : WF_schedVars(Preempt(c))
    /\ \A c \in CPUS : WF_schedVars(PendSV(c))

-----------------------------------------------------------------------------
(* Properties of the descriptive layer: the consistency of the model.     *)

\* @kind invariant
TypeOK ==
    /\ tstate \in [Threads -> ThreadStates]
    /\ DOMAIN prio = Threads
    /\ cur \in [CPUS -> Threads \cup {Idle}]
    /\ DOMAIN swapRet = Threads
    /\ swapData \in [Threads -> Data \cup {NoData}]
    /\ panic \in {"none", "pend_in_isr", "timeout_heap_full"}
    /\ rqStamp \in [Threads -> 0..Cardinality(Threads)]
    /\ preemptOk \in BOOLEAN
    /\ readySince \in [Threads -> 0..Cardinality(Threads)]
    /\ PF!TypeOK

\* A thread runs on at most one CPU.
\* @kind invariant
CurUnique == \A c, d \in CPUS : c # d /\ cur[c] # Idle => cur[c] # cur[d]

\* A thread that executes is ready: a pending or dead thread never runs its
\* code. With arch_swap() a thread that waits or ends stays _current until
\* PendSV runs, but it executes no code in this gap.
\* @kind invariant
CurIsReady ==
    \A c \in CPUS : cur[c] # Idle /\ ~PF!SwitchPending(c) => tstate[cur[c]] = "ready"

\* A thread is pending if and only if it is in a wait queue, and its
\* return value is -EAGAIN until a waker sets another one.
\* @kind invariant
PendingIsQueued ==
    \A t \in Threads :
        /\ (tstate[t] = "pending") <=> (pendedOn[t] # None)
        /\ tstate[t] = "pending" => swapRet[t] = EAGAIN

\* Only a pending thread has an armed timeout. A woken thread has no
\* timeout left that can wake it from a later wait (the precondition of
\* z_sched_wake_thread_locked()).
\* @kind invariant
ArmedArePending == \A t \in TO!Armed : tstate[t] = "pending"

\* A dead thread has no wait and no return value.
\* @kind invariant
DeadIsInert ==
    \A t \in Threads : tstate[t] = "dead" =>
        /\ pendedOn[t] = None
        /\ swapRet[t] = NoRet
        /\ ~Executes(t)

\* On one CPU the positions of the ready threads are 1..N and different,
\* a thread that is not ready has 0. Thus RunqBest has one witness. The
\* history has the values 1..N (with equal values), 0 if not ready.
\* @kind invariant
RqStampsNormal ==
    UP =>
        /\ \A t \in Ready : 1 <= rqStamp[t] /\ rqStamp[t] <= Cardinality(Ready)
        /\ \A a, b \in Ready : a # b => rqStamp[a] # rqStamp[b]
        /\ \A t \in Threads \ Ready : rqStamp[t] = 0 /\ readySince[t] = 0
        /\ \A t \in Ready : 1 <= readySince[t] /\ readySince[t] <= Cardinality(Ready)

\* Each CPU runs a thread that the rule can select: on one CPU the cache.
\* The premise: the CPU has no outer interrupt lock (the selection waits
\* for the end of the lock) and no switch is pending (arch_swap(): the
\* selection waits for PendSV). This holds after each step if each
\* critical section that changes the cache ends with a reschedule point.
\* k_thread_abort() of another thread does not (finding P7-c): the
\* configuration coop_rule shows it. irq_unlock() is not a reschedule
\* point (finding P2-w): the configuration p2_rule shows it. On SMP it can
\* fail until the IPI arrives (see SelectionHappens).
\* @kind invariant
RunRuleHolds ==
    \A c \in CPUS :
        (~PF!Locked(c) /\ ~PF!SwitchPending(c)) =>
            cur[c] \in Choices(c, tstate, prio, cur, rqStamp, preemptOk)

\* A thread does not switch while it holds an outer interrupt lock: a step
\* that changes the current thread of a CPU, or sets PendSV pending on it,
\* starts without an outer lock. This is a condition of use of the
\* kernel: the model keeps the lock state for each CPU and is not correct
\* without it (the code keeps it for each thread). The mutant pend_locked
\* of mc/MCScheduler violates it.
\* @kind action-property
\* @source doc:api#irq_lock
NoSwitchWhileLocked ==
    [][\A c \in CPUS :
         (\/ cur'[c] # cur[c]
          \/ PF!SwitchPending(c)' /\ ~PF!SwitchPending(c)) => ~PF!Locked(c)]_schedVars

\* No panic. This is an environment assumption: no ISR calls a wait, and
\* the heap of the timeouts is large enough.
\* @kind invariant
NoPanic == panic = "none"

\* The position of the timeout of t in the timeout queue. Defined only if
\* TimedWait(t). An entry is armed at most once (Timeout!ArmedOnce), so
\* the CHOOSE has exactly one witness.
TimeoutPos(t) == CHOOSE i \in DOMAIN tq : tq[i] = t

\* A step that inserts a timeout in front of the timeout of t.
Overtaken(t) == TimedWait(t) /\ TimedWait(t)' /\ TimeoutPos(t)' > TimeoutPos(t)

\* An armed timeout ends its wait (with the fairness of ThreadTimeout), if
\* eventually no new timeout goes in front of it. The model has no clock:
\* without this condition a new timeout can go in front again and again.
\* Real time permits only a finite number of earlier deadlines (non-Zeno).
\* @kind liveness
TimedWaitEnds ==
    \A t \in Threads :
        (<>[][~Overtaken(t)]_schedVars) => (TimedWait(t) ~> (tstate[t] # "pending"))

\* A CPU that runs a thread that the rule does not select selects again
\* (with the fairness of Preempt).
\* @kind liveness
SelectionHappens ==
    \A c \in CPUS : (cur[c] \notin Choices(c, tstate, prio, cur, rqStamp, preemptOk)) ~>
                    (cur[c] \in Choices(c, tstate, prio, cur, rqStamp, preemptOk))

-----------------------------------------------------------------------------
(* Properties of the normative layer. Each one states a requirement, with  *)
(* the reading that the workspace note p7-pilot.md gives. They are for one *)
(* CPU (level 1). "Candidates" and the priorities are the values after the *)
(* step.                                                                   *)

\* While the current thread is preemptible, no ready thread has a higher
\* priority: a thread with a higher priority that becomes ready (also by a
\* priority change) is the current thread at the end of the step. The idle
\* thread runs only if no thread is ready. Two readings (p7-pilot.md and
\* finding P2-w): L1, while the thread holds an outer interrupt lock the
\* selection waits for the end of the lock (irq_lock() prevents the
\* interrupts, and with them the preemption). G1, while a switch is pending
\* (arch_swap(), before PendSV) no thread executes, so the CPU has no
\* current thread in the sense of the requirement.
\* @kind invariant
\* @source ZEP-SRS-2-9
\* @source ZEP-SRS-2-12
PreemptibleRunsHighest ==
    \A c \in CPUS :
        (~PF!Locked(c) /\ ~PF!SwitchPending(c)) =>
        LET S == Candidates(c, tstate, cur)
        IN  /\ cur[c] = Idle => S = {}
            /\ (cur[c] # Idle /\ ~Cooperative(prio[cur[c]])) =>
                   \A t \in S : prio[t] <= prio[cur[c]]

\* The end of an outer interrupt lock is the end of the wait of reading L1:
\* a step that unlocks CPU c (irq_unlock() with the last key) ends with a
\* preemptible current thread only if no ready thread has a higher
\* priority, or a switch is pending on c. TLC finds a violation (finding
\* P2-w): z_reschedule() in the lock does not switch (resched() sees the
\* locked key), and irq_unlock() is not a reschedule point. The thread
\* keeps the CPU until the next reschedule point, for example the exit of
\* the next interrupt.
\* @kind action-property
\* @source ZEP-SRS-2-9
\* @source doc:kernel/services/interrupts
\* @expected violation
UnlockPreempts ==
    [][\A c \in CPUS :
         (/\ PF!Locked(c)
          /\ ~PF!Locked(c)'
          /\ ~PF!SwitchPending(c)'
          /\ cur'[c] # Idle
          /\ ~Cooperative(prio'[cur'[c]])) =>
             \A t \in Candidates(c, tstate', cur') : prio'[t] <= prio'[cur'[c]]]_schedVars

\* A step that selects a new current thread selects a ready thread with
\* the highest priority among the threads that the CPU can run, or the
\* idle thread if no thread is ready. (A "scheduling decision" is a step
\* that changes the current thread.)
\* @kind action-property
\* @source ZEP-SRS-2-12
SwitchSelectsHighest ==
    [][\A c \in CPUS :
         cur'[c] # cur[c] =>
             LET S == Candidates(c, tstate', cur')
             IN  IF S = {} THEN cur'[c] = Idle
                 ELSE /\ cur'[c] \in S
                      /\ \A u \in S : prio'[u] <= prio'[cur'[c]]]_schedVars

\* A thread that waits loses the protection of the cooperative rule: the
\* selection after the wait selects a ready thread with the highest
\* priority (ZEP-SRS-2-14: "until they yield or block", with ZEP-SRS-2-12).
\* With CONFIG_USE_SWITCH the selection is in the step of the wait, and
\* SwitchSelectsHighest checks it. With arch_swap() the selection is the
\* step PendSV. If an ISR in the gap before PendSV makes the waiter ready
\* again, the waiter is still _current at PendSV, and it has not returned
\* from its wait (swapRet # NoRet). TLC finds a violation (candidate
\* finding SW-1): the wake calls update_cache(0), and should_preempt() keeps
\* the cache at _current, because _current is ready and cooperative again.
\* @kind action-property
\* @source ZEP-SRS-2-12
\* @source ZEP-SRS-2-14
\* @expected violation
BlockedLosesCpu ==
    [][\A c \in CPUS :
         LET a == cur[c]
         IN  (/\ PF!SwitchPending(c)
              /\ ~PF!SwitchPending(c)'
              /\ a # Idle
              /\ tstate[a] = "ready"
              /\ swapRet[a] # NoRet
              /\ cur'[c] # Idle) =>
                 \A u \in Candidates(c, tstate', cur') : prio'[u] <= prio'[cur'[c]]]_schedVars

\* A step that selects a new current thread t selects, among the ready
\* threads with the priority of t, a thread that has been ready the
\* longest. The old current thread is one of these ready threads if it is
\* still ready. A priority change does not make a thread "ready again".
\* TLC finds a violation (finding P7-a): z_thread_prio_set() puts the
\* current thread after its peers, also for the same priority.
\* @kind action-property
\* @source ZEP-SRS-2-13
\* @expected violation
TieGoesToLongestReady ==
    [][\A c \in CPUS :
         (cur'[c] # cur[c] /\ cur'[c] # Idle) =>
             \A u \in Candidates(c, tstate', cur') :
                 prio'[u] = prio'[cur'[c]] => readySince'[cur'[c]] <= readySince'[u]]_schedVars

\* A running cooperative thread stays the current thread until it yields
\* or blocks: if it is ready and cooperative before and after the step, it
\* still runs on its CPU. The model has no yield call (k_yield()). A thread
\* that becomes preemptible in the step is not protected. TLC finds
\* violations (findings P7-b, P7-c): z_thread_prio_set() and halt_thread()
\* call update_cache(1), which skips the cooperative rule.
\* @kind action-property
\* @source ZEP-SRS-2-14
\* @expected violation
CoopKeepsCpu ==
    [][\A c \in CPUS :
         LET a == cur[c]
         IN  (/\ a # Idle
              /\ tstate[a] = "ready"
              /\ tstate'[a] = "ready"
              /\ Cooperative(prio[a])
              /\ Cooperative(prio'[a])) => cur'[c] = a]_schedVars

=============================================================================
