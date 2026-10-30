..
   Copyright (c) 2026 inovex GmbH
   SPDX-License-Identifier: Apache-2.0

TLA+ design specification of the kernel objects
###############################################

This directory holds the formal design model of the Zephyr kernel objects
(semaphore, queue, message queue, stack, memory slab, events, condition
variable, mutex, and more later). The model is written in TLA+ and checked
with TLC. ``GLOSSARY.rst`` defines the words of the method.

Status: design note of 2026-10-21 (roadmap step 2.0). ``lib/WaitQueue``,
``lib/Timeout``, ``lib/Platform`` and ``lib/Scheduler`` exist and are
checked alone (``mc/MCWaitQueue``, ``mc/MCTimeout``, ``mc/MCScheduler``)
and by example tests (``mc/WaitQueueTest``, ``mc/TimeoutTest``,
``mc/PlatformTest``, ``mc/SchedulerTest``). ``Platform`` is at coarse grain
since 2026-10-29: the interrupt lock and the two variants of the context
switch. Fine grain adds the IPIs and the lock owners (roadmap step 5).
Round B (2026-10-29) added the swap data in both directions, the wait
queue head, ``z_unpend_all()``, the ordered walk with a stop, the wake of
one thread with its precondition, the join queue, the fault-model step
``WaitqInit``, the ``@kconfig`` tags and the coverage check (see
`Kconfig`_). The k_sem slice (roadmap step 2, 2026-10-30) added
``lib/Waitable`` (minimal: what ``KSem`` needs), ``objects/KSem`` with its
own ``Init``, ``Next`` and ``Spec`` (the environment is
``Scheduler!EnvNext``), the models ``mc/MCKSem`` and the mutants
``mc/MCKSemMutants``, and the trace check of the sem unit tests
(``trace/``, see ``trace/README.rst``). The k_sem proof of concept of the
workspace notes (``claude/kernel-unit/tla/``) is replaced.

.. contents::
   :local:
   :depth: 2

Purpose
*******

The model is one of four artifacts that must be consistent for each kernel
object: the requirements (``ZEP-SRS-*``), the design (this model), the
implementation (``zephyr/kernel/*.c``) and the tests. The model has these
jobs:

- **A review item.** Each requirement is a property of the model, and each
  property traces to a requirement. A review compares the two. A gap is a
  finding, and the finding changes one artifact.
- **An oracle for the unit tests.** The unit tests in
  ``tests/kernel/unit/`` write a trace of each run. TLC checks that each
  trace is a behavior of the model (trace validation).
- **A source of tests.** TLC behaviors give call sequences for tests on
  the unit test board and on the real kernel.
- **The contract of the scheduler fakes.** The unit tests replace the
  scheduler with fakes. The scheduler contract of this model (the module
  ``Scheduler`` below) is the contract that a reference fake implements and that contract tests
  check against the real ``kernel/sched.c``.

The model does not prove the C code. It proves properties of the model.
The connection to the code comes from trace validation, from the tests that
the model gives, and from reviews.

Decisions
*********

All decisions are of 2026-10-21. The background is in the workspace notes
``claude/kernel-unit/roadmap.md`` and
``claude/kernel-unit/tla/waitable-boundaries.md`` (the paper check of the
module boundaries against eight kernel objects).

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Topic
     - Decision
   * - Language
     - Plain TLA+ for all library and object modules. PlusCal only as an
       option for scenario models (one process for each test thread).
   * - Location
     - This directory. The specs are a deliverable under review, like the
       code.
   * - CPUs
     - Explicit. The constant ``CPUS`` is a set. One CPU is the default
       (uniprocessor). The same modules serve SMP.
   * - Contract and template
     - ``Scheduler`` is the contract module of the scheduler API that the
       objects call. ``Waitable`` is the template module that the objects
       instantiate. Both are review items.
   * - Wait queue
     - A set with stamps, not a sequence. The order is a definition
       (``Before``). Stamps are normalized after each step. A derived
       ordered view serves traces and tests.
   * - Time
     - No clock. A finite timeout is an environment event. The cost of a
       timeout insertion is a step counter.
   * - Tools
     - TLC from ``tla2tools.jar`` v1.8.0 (pre-release, rev ``d2e1472``),
       pinned by hash (see `Running`_).
       The style stays readable for Apalache (see `Apalache`_).
   * - Method
     - Two parts in each spec (2026-10-28, see `Behavior part and property
       part`_): the operators follow the code, the properties come from
       the requirements and the documentation (``@source``).

Entities
********

The entities follow the view of the kernel "world": CPUs with an interrupt
controller, memory with kernel objects and threads, kernel code and
application code.

.. list-table::
   :header-rows: 1
   :widths: 18 47 35

   * - Entity
     - In the model
     - Not in the model
   * - CPU
     - An element of ``CPUS``. For each CPU: the current thread
       (``cur[c]``), the outer interrupt lock (``irqNest[c]``, the nested
       ``irq_lock()`` calls of the thread that runs) and a pending PendSV
       (``pendsv[c]``, ``arch_swap()`` only). At coarse grain an ISR is one
       step, so "in an ISR" is the kind of the actor, not a variable
       (``Platform``).
     - Registers, caches, the memory model, the in-ISR state as a
       variable and the ISR nesting (fine grain).
   * - Interrupt and ISR
     - An ISR is an actor that runs on a CPU while that CPU has interrupts
       unlocked (``Platform!IrqCanRun``). It is not preempted by a thread.
       It calls only non-blocking operations. A pend from an ISR sets
       ``panic``, as ``z_pend_curr()`` does (``kernel/sched.c``). At first,
       at most one ISR runs on each CPU (no nesting). The exit of an ISR is
       a reschedule point.
     - Interrupt priorities, nesting (later, for the timer findings),
       zero-latency interrupts (they must not call the kernel).
   * - Context switch
     - Two variants (``Platform!UseSwitch``, ``CONFIG_USE_SWITCH``). With
       ``CONFIG_USE_SWITCH`` the selection is in the step of the
       reschedule point. With ``arch_swap()`` the step sets PendSV pending,
       and the step ``PendSV`` selects later. ISRs can run in the gap. On
       one CPU both variants switch to the cache ``_kernel.ready_q.cache``.
     - The register save and restore, the FPU, the stack switch.
   * - Thread
     - The priority (``prio[t]``, the ``base.prio`` of the code; the mutex
       keeps the original priority), the state (ready, pending, dead; a
       running thread is a ready thread that is ``cur[c]`` of a CPU;
       suspended comes with ``k_thread_suspend()``), the object that it waits on
       (``pendedOn[t]``), the result of its last wait (``swapRet[t]``,
       ``swapData[t]``).
     - Stacks, the thread entry function.
   * - Scheduler
     - The ready set, the run queue order (``rqStamp``) and the cache of
       ``update_cache()`` on one CPU (``preemptOk``), cooperative threads,
       the reschedule points.
     - The data structures of the ready queue (``CONFIG_SCHED_*``: all
       three give the same order), the run queue and the cache on SMP (the
       model selects any thread of the highest priority), time slices,
       ``k_yield()``, ``k_sched_lock()``, meta-IRQ threads, CPU masks.
   * - Wait queue
     - One set of waiters for each object, with priorities and stamps (see
       `The wait queue`_).
     - The list and tree code (``sys_dlist``, ``rbtree``). The unit tests
       of that code cover it.
   * - Spinlock
     - Coarse grain: implicit, each action is one critical section. Fine grain: an
       owner CPU for each lock (see `Coarse and fine grain`_).
     - Ticket order, spinning.
   * - Timeout
     - An entry for each thread that waits with a finite timeout. The
       expiry is an environment event. The insertion has a step counter.
     - Ticks, the clock driver.
   * - Object state
     - The resource of the object (count, items, owner, free blocks, event
       bits), with data as IDs.
     - Bytes, buffers, alignment.
   * - Memory pools
     - A resource, like a semaphore count (allocation can fail).
     - The allocator algorithms.
   * - Kconfig
     - Constants. Each twister scenario of a unit test app has a model
       configuration with the same options (see `Kconfig`_).
     -

Module structure
****************

.. code-block:: none

   lib/Platform     CPUs, ISR actors, interrupt lock, context switch
     |              (two variants), clock events; IPIs, lock owners
     |              (fine grain)
     |
   lib/Scheduler    thread state, priorities, current thread, swap result,
     |              panic, ready set, run queue order, cache; Abort,
     |              SetPrio, Resume
   lib/WaitQueue    pendedOn, stamps, Before, Best, Ordered; Add, Remove
     |
   lib/Timeout      timeout entries, the expiry event, the insertion cost
     |
   lib/Waitable     template: Take, Give, Flush, ResumeOp, the common
     |              properties
   objects/KSem, objects/KQueue, ...   the resource of each object, its
                                       parameters, its own properties

.. list-table::
   :header-rows: 1
   :widths: 18 32 30 20

   * - Module
     - Owns (variables)
     - Provides
     - Does not know
   * - ``Platform``
     - ``irqNest``, ``pendsv``; the constants ``CPUS``, ``Isrs``,
       ``IsrCpu``, ``UseSwitch``. Fine grain: lock owners, IPI flags
     - ``InIsr(a)``, ``Locked``, ``Key``, ``KeyUnlocked``, ``IrqCanRun``,
       ``IrqLock``, ``IrqUnlock``, ``SwitchAtOnce``, ``RequestPendSV``,
       ``SwitchPending``, ``PendSVRuns``, ``ClockCanFire``
     - threads states, objects, priorities, the cache
   * - ``Scheduler``
     - ``tstate``, ``prio``, ``cur``, ``swapRet``, ``swapData``, ``panic``,
       ``rqStamp``, ``preemptOk``, ``readySince`` (a history variable of the
       property part)
     - the contract operators, the selection rule ``Choices``, ``ThreadTimeout``,
       ``Abort``, ``SetPrio``, ``Resume``, ``Preempt``, the ISR guard,
       fairness
     - resources, requests
   * - ``WaitQueue``
     - ``pendedOn``, ``stamp``
     - ``Before``, ``Best``, ``Ordered``, ``Add``, ``Remove``
     - resources, requests
   * - ``Timeout``
     - timeout entries, the step counter of the insertion
     - the expiry event, ``Insert``, ``Cancel``
     - objects
   * - ``Waitable``
     - ``req`` (the request of each waiter)
     - ``Take``, ``Give``, ``Flush``, ``ResumeOp``, the common properties
     - other object types
   * - Object module
     - the resource ``r``
     - the parameter operators, the object properties
     - scheduler internals

``Platform`` is the contract below ``kernel/sched.c`` (roadmap, "Method
decision 2026-10-28"). It is an assumption module: it states only what
``sched.c`` relies on, and each item that rests on the architecture code or
on a document has the tag ``@assumption`` with that location. The fakes of
the ``arch_*`` functions and later the trace validation check these items, not
a proof. ``Scheduler`` instantiates ``Platform`` (``PF``), ``WaitQueue``
and ``Timeout`` (entries: the threads), so a module that uses ``Scheduler``
declares the variables of all four. The constants ``CPUS``, ``Isrs``,
``IsrCpu``, ``MaxIrqNest`` and ``UseSwitch`` belong to ``Platform``.
``Scheduler`` declares them only to pass them on (an ``INSTANCE`` needs
them).

The outer interrupt lock is a state of the CPU, not of the thread. This is
correct only if no thread switches while it holds the lock, which the API
documentation of ``irq_lock()`` forbids. The action property
``Scheduler!NoSwitchWhileLocked`` states this condition of use, and the
mutants ``pend_locked`` and ``pend_locked_pendsv`` violate it.

``pendedOn`` is one function over all threads and all objects of all types.
The mutex chain walk reads the wait state of other threads, and an abort or
a priority change acts on a waiter in any wait queue.

The scheduler contract
======================

One operator for each C function of the scheduler API that the objects
call. An object action composes these operators inside one critical
section: first the changes of the wait queues and of the thread states,
then the end of the critical section (``Release``). The trace hook of the
unit tests logs one record for each call of this API. Thus the names in
the trace and in the model are the same. ``a`` is the actor (a thread or
an ISR), ``o`` an object.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Operator
     - C function and meaning
   * - ``PendCurr(a, o, to)``
     - ``z_pend_curr()``: panic if ``a`` is an ISR. Else add ``a`` to the
       wait queue of ``o``, preset ``swapRet[a]`` to ``-EAGAIN``, add a
       timeout entry if ``to`` is finite (panic on a full heap), and
       switch (``Release(a, "swap")``). The swap data does not change.
   * - ``SetSwapData(a, d)``
     - The thread ``a`` writes ``d`` to its swap data before a wait (msgq
       and mailbox). No step resets the swap data: the code never does.
       The swap data belongs to a later contract ``ThreadState``.
   * - ``WakeFirst(o, ret, data)``
     - ``z_sched_wake()``: the best waiter leaves the wait queue, its
       timeout is cancelled, it gets ``ret`` and ``data``, it is ready.
       Not enabled if the wait queue is empty (``HasWaiters(o)`` is the
       return value).
   * - ``WakeFirstWith(o, F)``
     - ``z_unpend_first_thread_locked()`` and ``z_sched_ready_locked()``
       with object code between them (msgq copy, mutex owner). ``F(t)``
       gives the pair ``<<ret, data>>`` for the woken thread.
   * - ``WakeAll(o, ret, data)``
     - The loop ``while (z_sched_wake(...))``. One wake of all waiters,
       also enabled on an empty wait queue (no change).
   * - ``UnpendAll(o)``
     - ``z_unpend_all()`` (``k_heap_free()``): each waiter leaves the wait
       queue with its timeout cancelled, and keeps the ``-EAGAIN`` preset
       and its old swap data. ``HasWaiters(o)`` before the step is the
       return value.
   * - ``WakeWalk(o, P, Stop, D)``
     - ``z_sched_waitq_walk()`` with ``walk_func`` and ``post_func`` in
       one critical section: the walk visits the waiters in wait queue
       order and stops after the first waiter with ``Stop(t)``
       (``WaitQueue!Walked``, ``WaitQueue!WalkStop``). Each visited waiter
       with ``P(t)`` is woken with the return value 0 and the data
       ``D(t)``. Events: ``Stop`` is false. Mailbox send: ``P`` and
       ``Stop`` are the match.
   * - ``WakeLocked(S, ret, dat)``, ``WakeThreadLocked(t, ret, d)``
     - ``z_sched_wake_thread_locked()``: a dead (or aborting) thread is
       ignored, each other thread leaves its wait queue and is ready. The
       precondition ``WakePre(S)``: the caller has cancelled the timeouts.
       The operator does not change the timeout queue.
   * - ``WakeSet(S, ret, dat)``
     - The common part of the wakes: the cancellation of the timeouts,
       then ``WakeLocked``.
   * - ``WaitqInit(o)``
     - ``z_waitq_init()`` from the init function of an object. On a wait
       queue with waiters the code has undefined behavior: ``panic``
       becomes ``"undefined"`` and the model stops (fault model, Kconfig
       kind 5, invariant ``NoUndefined``, finding P6-u).
   * - ``WaitQueue!Head(o)``
     - The query ``z_waitq_head()`` and ``z_waitq_head_locked()``: the
       best waiter, or ``Idle`` (``WaitQueue!NoThread``).
   * - ``PrioSet(t, p)``
     - ``z_thread_prio_set()``: a waiter goes to the end of the waiters
       with its new priority. A ready thread (on one CPU also the current
       thread) goes to the end of the run queue for its new priority, also
       if the priority does not change, and ``update_cache(1)`` follows.
       No reschedule.
   * - ``Release(a, kind)``
     - The end of the critical section. ``"unlock"``:
       ``k_spin_unlock()``, a thread keeps its CPU. ``"resched"``:
       ``z_reschedule()``, a reschedule point only if ``ReschedOk`` (the
       rule ``resched()``: the key of the critical section is unlocked and
       the actor is not an ISR). ``"swap"``: ``z_swap()``. For an ISR each
       kind is the exit of the ISR, which is a reschedule point.
   * - ``ThreadTimeout(c)``, ``Abort(a, t)``, ``Join(a, t, to)``,
       ``SetPrio(a, t, p)``, ``Resume(t)``, ``Preempt(c)``, ``PendSV(c)``,
       ``IrqLockCall(a)``, ``IrqUnlockCall(a)``
     - Environment actions: the expiry of the first timeout on CPU ``c``,
       ``k_thread_abort()`` (with the static ``unpend_all()`` of the join
       queue), ``k_thread_join()``, ``k_thread_priority_set()``, the return
       from the swap, an interrupt or IPI that selects a thread on ``c``,
       the PendSV handler (``arch_swap()`` only), ``irq_lock()`` and
       ``irq_unlock()`` of a thread outside a kernel call.

**The selection rule.** At each reschedule point, CPU ``c`` selects a
thread from ``Choices(c, ...)``. On one CPU this is the cache of the code
(``CacheOf``). With ``arch_swap()`` the reschedule point only sets PendSV
pending, and the step ``PendSV`` selects the cache as it is then
(``Platform``). ``next_up()`` gives the head of the run queue: the highest
priority, then the position (``rqStamp``). The current thread stays in the
run queue, so "the current thread wins a tie" is only a result of its
position. ``should_preempt()`` accepts the head if the flag ``preemptOk``
(the argument of the last ``update_cache()``) is true, if the current
thread cannot run, or if it is preemptible. Else the current thread keeps
the CPU (the cooperative rule). A wake and a timeout call
``update_cache(0)``. A wait, ``z_thread_prio_set()`` of a ready thread and
an abort call ``update_cache(1)``: then the next reschedule point has no
cooperative rule. Threads that become ready in one critical section get any
order among them (no document orders them). On SMP the rule is
``SmpChoices`` (design exploration): a ready cooperative thread keeps the
CPU, the current thread wins a tie, else any thread with the highest
priority. ``mc/SchedulerTest`` fixes the rules for single states.

**The composition rule.** A critical section that changes the cache ends
with ``"resched"`` (or is an ISR). Then on one CPU the invariant
``RunRuleHolds`` holds after each step: each CPU without an outer
interrupt lock and without a pending PendSV runs the thread that the rule
selects. An outer ``irq_lock()`` defers the switch of ``z_reschedule()``,
and ``irq_unlock()`` is not a reschedule point: after the unlock the
invariant fails until the next reschedule point (configuration
``p2_rule``, finding P2-w). The mutant ``missed_resched`` of ``mc/MCScheduler`` (a wake
that ends with ``k_spin_unlock()``) violates it. The code itself breaks the
rule in one place: ``k_thread_abort()`` of another thread calls
``update_cache(1)`` and ends with ``k_spin_unlock()`` (configuration
``coop_rule``, finding P7-c). A mutex model that de-boosts the owner and
then ends with ``k_spin_unlock()`` must show the same. On SMP the invariant
fails until the IPI arrives (configuration ``smp_rule``, expected). The
liveness property ``SelectionHappens`` holds with the fairness of
``Preempt``.

**Abort.** The constant ``JoinQ`` gives each thread its join queue (an
object of ``Objs``, or ``None``). ``Abort`` wakes the joiners with the
return value 0 and calls ``update_cache(1)``. An abort of another thread
does not reschedule, so a joiner with a higher priority does not run until
the next reschedule point: ``PreemptibleRunsHighest`` fails
(configurations ``f14_join*``, finding F14). At coarse grain ``Abort`` has no
essential threads, no ``k_thread_suspend()`` and no abort of a thread that
runs on another CPU (fine grain: the target halts itself in an IPI).

**Swap data in the models.** No step resets the swap data, so in a model
each thread keeps a value. The wakers of ``mc/MCScheduler`` give no data
(``NoD``): no guard of the scheduler reads the swap data, and with data
from the wakers the run ``small`` has more than three times the states.
The data ``d1`` comes only from ``SetSwapData`` (``MCExtra``: ``small_b``,
``reach_b``), and the msgq and mailbox wakes of these runs keep it.

The ``Waitable`` template
=========================

The template has the actions ``Take``, ``Give``, ``Flush`` and
``ResumeOp``. Each object gives the template its operators. The parameters
that differ between objects are ``Avail``, ``Consume``, ``Select``,
``Deliver``, ``Settle``, ``NoWaitRet`` and ``FlushRet``. The hooks
``OnPend``, ``OnResume``, ``OnHandOver``, ``OnLeave``, ``GiveErr`` and
``Notify`` are the identity or empty for most objects.

The paper check gives this fit:

- **Instances:** sem, stack, mem_slab, queue (FIFO, LIFO).
- **Instances with an extension:** condvar (``OnPend``, ``OnResume``),
  msgq (two roles on one wait queue), events (the selection is a filter),
  mutex (priority inheritance hooks), thread join (its lock is the
  scheduler lock), timer status sync.
- **No fit:** ``k_poll``. A poller waits on several objects. It becomes a
  separate module that uses the ``Notify`` hook of the other objects.

The minimal template of the k_sem slice (``lib/Waitable.tla``) has the
actions ``Take``, ``Give``, ``Flush``, ``ResumeOp``, ``InitOp`` and
``EnvStep`` (the step ``Scheduler!EnvNext`` in an object model, without the
return from a wait, which is the object's ``ResumeOp``). Its variables are
``r`` (the resource of each object), ``req`` (the object of the wait of
each thread, until the thread returns) and ``obs``. The other parameters of
the table below come with the objects that need them.

Composition pattern
-------------------

The template does not declare its parameters as ``CONSTANT`` operators.
The template actions take the object operators as arguments, and the
object module calls them:

.. code-block:: none

   \* objects/KSem.tla
   SemAvail(r, t, q)   == r.count > 0
   SemConsume(r, t, q) == <<[r EXCEPT !.count = @ - 1], OK>>
   Give(o, a) == W!Give(o, a, None, SemProduce, First, SemDeliver, SemSettle)

This is standard TLA+. TLC accepts it. Apalache also accepts operators as
arguments (it expands them), but it does not accept ``CONSTANT``
operators.

A probe confirmed this on 2026-10-21 with Apalache 0.62.4. The probe has
a template with operator arguments, a semaphore that calls it, and
``lib/WaitQueue.tla`` below it. Apalache type-checks it and finds no error
up to 8 steps. With a planted defect in an object operator, Apalache and
TLC both report the violation. The probe gave three rules (see
`Apalache`_): an object operator that the template calls has a type
annotation, an argument is a named operator and not a ``LAMBDA``, and a
range has constant bounds.

Coarse and fine grain
*********************

The grain of a module is how much code one step of the module is (decided
on 2026-10-30; it replaces "level 1" and "level 2" of 2026-10-26).

**Coarse grain.** One action is one critical section under the object
lock. This is correct on one CPU, because each spinlock also locks the
interrupts: no other code runs between the first read and the last write
of the step. It is not correct on SMP. For example, ``k_sem_give()`` holds
the object lock and takes ``_sched_spinlock`` inside it, and another CPU
can see the state between the two locks. Thus a coarse module is for one
CPU by construction, not only by its configurations (safety case 1 is for
one CPU only, decision D2 of the method review). SMP needs fine modules.
Coarse grain is the grain of the trace hook and of the generated tests.

**Fine grain.** Lock acquire and lock release are separate steps. Fine
grain is necessary only for the operations that break the coarse grain.
The paper check lists them:

- ``k_condvar_wait()``: the mutex release, the pend and the relock are
  three sections.
- ``k_mutex_lock()``: the de-boost after a timeout is a second section, and
  the chain walk reads other threads without the scheduler lock.
- ``k_mutex_unlock()``: the owner checks run without the lock, and the last
  unlock has three scheduler sections.
- The timer status sync, the expiry and ``k_timer_stop()``.
- ``k_poll()`` and ``signal_poller()``.
- The msgq and stack cleanup with ``locked = true`` (lock order is the
  reverse of the other operations).
- The init of each object (no lock).

The fine grain comes with the SMP increment (roadmap step 5). Until then,
each coarse-grain action of these operations has a comment that names the
gap.

**Grain and representation are two different axes.** The grain is what one
step of the model is in the code. The representation is the data: a model
can also leave out data or keep a free choice that the code does not have
(for example, a give that wakes any waiter, in place of the head of the
wait queue). Such a model is more abstract in its representation, at the
same grain. Both kinds of model relate by refinement (``Fine => Coarse``
with a refinement mapping). In a refinement from the fine grain to the
coarse grain, the extra steps are stuttering steps of the coarse grain.
Only one step of each critical section, usually the lock release, is the
coarse-grain step.

Marking the grain:

- Coarse grain is the default. A fine module has the name
  ``<Module>_<Reason>``, where the reason says why the grain is finer (for
  example ``objects/KCondVar.tla`` and ``objects/KCondVar_MutexRelease.tla``,
  or ``lib/Scheduler_SmpLocks.tla``). Its header comment states the grain
  and the reason. A fine module is a separate module, because a refinement
  check needs two specs.
- The tag ``@grain fine`` marks an action whose step is finer than the
  grain of its module, for example the two-step form of the expiry in
  ``Timeout``. An action with the grain of its module has no tag.
- Each fine module has a refinement model ``mc/MC<Object>Refinement.tla``.
  It defines the refinement mapping and the properties ``Refines`` (the
  coarse-grain spec) and ``RefinesFair`` (the coarse-grain spec with its
  fairness). Its line in ``mc/expected.txt`` is ``pass``. The fine module
  has its own probes, because a model without steps also refines the
  coarse-grain spec. The suffix is ``Refinement`` and not ``Ref``, because
  ``Ref`` can be read as "reference".
- Each object has one contract module at coarse grain. The requirements
  connect to it. Models that are more abstract in their representation, for
  example a model of the count only, are not part of the library.

The wait queue
**************

Zephyr orders a wait queue by priority, then by arrival:

- ``CONFIG_WAITQ_SIMPLE`` inserts a thread before the first thread with a
  lower priority (``z_priq_simple_add()``).
- ``CONFIG_WAITQ_SCALABLE`` sorts a red-black tree by priority, then by an
  ``order_key`` from a counter (``z_priq_rb_add()``).
- ``z_thread_prio_set()`` removes a waiting thread and adds it again. The
  thread then comes after the other threads with its new priority.

The model keeps the rule, not the data structure:

.. code-block:: none

   pendedOn ∈ [Threads → Objs ∪ {None}]
   stamp    ∈ [Threads → Nat]
   W(o)     ≜ {t ∈ Threads : pendedOn[t] = o}
   Before(a, b) ≜ ∨ prio[a] > prio[b]
                  ∨ prio[a] = prio[b] ∧ stamp[a] < stamp[b]
   Best(o)      ≜ CHOOSE t ∈ W(o) : ∀ u ∈ W(o) \ {t} : Before(t, u)
   Ordered(o)   ≜ the sequence of W(o), sorted by Before

``Before`` reads like the requirement text: higher priority first, then
FIFO. ``pendedOn`` is a function, so a thread waits on at most one object by
construction. The walk of ``z_sched_waitq_walk()`` is a separate
operator (``Walked``, ``WalkStop``): it follows the wait queue order with
both backends and stops at the first waiter for which ``walk_func``
returns non-zero. ``CONFIG_WAITQ_SCALABLE`` changes only what a callback
can do in the walk (no removal before the last step), not the order.
``Head(o)`` is the query ``z_waitq_head()``, with the value ``NoThread``
if no thread waits. ``WaitQueue`` does not extend ``Sequences``, so that
the name ``Head`` is free.

**Normalization.** Stamps grow without a limit, and TLC needs a finite
state space. After each step, the stamps are renumbered to their rank
(``1`` to ``|W|`` over all waiters). Two states that differ only in the
absolute stamp values become one state. A separate, bounded model can keep
real stamps with a wrap, to examine the renumbering of ``next_order_key``
in ``z_priq_rb_add()`` (an ``int``, the wrap is a signed overflow).

Higher priority means a lower number in Zephyr. ``Before`` uses the model
value ``prio`` with "greater is higher". ``Scheduler!ToZephyr`` and
``Scheduler!FromZephyr`` are the only conversion, so that the review
compares one rule.

Time and bounds
***************

The model has no clock. A thread that waits with a finite timeout has a
timeout entry. The action ``Scheduler!ThreadTimeout(c)`` expires the first
entry of the timeout queue.
``K_FOREVER`` makes no entry. ``K_NO_WAIT`` never pends.

For a thread wait, an atomic ``ThreadTimeout`` is equal to the two-step
dispatch of ``kernel/timeout.c``: if a give wins, the handler finds nothing
to do. For the timer object this is not true (finding F1 of the paper
check). Thus ``Timeout`` offers the atomic form for coarse grain and a two-step
form for the timer model (roadmap step 4).

Bounds of time are step counters, not times:

- ``Timeout`` counts the entries that an insertion passes. The timeout list
  of ``kernel/timeout.c`` is sorted, so the cost is linear in the number of
  active timeouts. An invariant bounds the counter.
- The observation record of each action counts the work under the lock
  (wakes, walk steps). Invariants bound these counters by the number of
  waiters and the size of the resource.

These counters are the model side of the draft bound requirements
(``DRAFT-BND-*`` in the workspace notes).

A wake of more than one waiter cancels one timeout for each woken
waiter in one critical section. ``Timeout!CancelSet`` gives this cost:
``k`` removals from a queue with ``n`` entries (exact for ``DLIST``, an
upper bound for ``MINHEAP``), with the bound ``n`` times the bound of one
removal.

The liveness of a timeout needs a condition. The model has no clock, so a
new timeout can go in front of an armed timeout again and again: TLC
found such a behavior for ``TimedWaitEnds`` in the first run of
``mc/MCScheduler``. Real time permits only a finite number of earlier
deadlines (non-Zeno). Thus ``Scheduler!TimedWaitEnds`` states: if
eventually no new timeout goes in front of the timeout of ``t``, the wait
of ``t`` ends.

In ``mc/MCTimeout``, the invariant ``CostBounded`` holds by construction:
the module computes the cost with the formula of the backend, and the bound
is a little larger. The probe ``Reach_DlistWorstCase`` shows that the worst
case (an insertion that walks over all entries) is reachable. The bound
becomes a real check when an object action adds the costs of several
operations (for example a wake of all waiters that cancels one timeout for
each waiter).

An insertion into a full heap (``MINHEAP``) panics in ``kernel/timeout.c``.
``mc/MCTimeout`` has this step (``PanicFull``) and the invariant
``Inv_NoPanic``. This is the environment assumption "never more armed
timeouts than ``CONFIG_TIMEOUT_HEAP_MAX_ENTRIES``". The configuration
``minheap`` (capacity 3 for 3 entries) satisfies it. The configuration
``minheap_full`` (capacity 2) violates it, as expected. A model of the
callers must show that the assumption holds for a product.

The observation record
**********************

Each action writes the variable ``obs``. It has a generic part from the contract
(``actor``, ``op``, ``obj``, ``timeout``, ``woken``, ``ret``) and an object
part (``args``). Since the k_sem slice, the generic part has ``calls``: the
calls of the step into the lock and the scheduler contract, in order, each
as ``[fn, obj, arg, ret, res, thread]`` (``lib/Waitable.tla``). This is the
hook-call record of the review of 2026-10-30 (answer Q3). The trace hook of
the unit tests writes the same calls from the fakes, and ``trace/KSemTrace``
compares them one by one. The generated tests can read the same record.
One record type also suits Apalache.

Apalache
********

Apalache is a symbolic model checker for TLA+. It checks inductive
invariants and handles large integers, which TLC cannot list. It comes in
roadmap step 5. The specs keep a style that it can read from the start:

- Type annotations on each variable and constant (``\* @type: ...;``).
  Apalache reads the annotation only between the keyword and the name.
  A single ``CONSTANT`` statement with a doc comment (the Kconfig tags) has
  the form ``CONSTANT`` / ``\* @type: Bool;`` / ``UseSwitch``, on three
  lines. An annotation in the doc comment before the keyword is not read.
- An operator gives values of one type. For "no thread",
  ``WaitQueue!Head`` and ``WaitQueue!WalkStop`` give the constant
  ``NoThread`` (a thread value that is not in ``Threads``), not the object
  ``None``. ``Scheduler`` sets ``NoThread`` to ``Idle`` (decision D15 of
  2026-10-31).
- A type annotation on each operator that reads a record field of its
  parameter, and on each generic helper (``Seq(a) => Set(a)``). Apalache
  cannot infer the record type from ``r.count`` alone. A type alias
  (``\* @typeAlias: semRes = { count: Int, limit: Int };``) keeps the
  annotations short.
- No ``CONSTANT`` operators (see `Composition pattern`_).
- No ``LAMBDA`` as an operator argument. A ``LAMBDA`` cannot have an
  annotation, so a ``LAMBDA`` that reads a record field does not
  type-check. Use a named operator.
- A range has constant bounds: ``1..Cardinality(W(o))`` and
  ``0..n`` with a parameter ``n`` are not accepted. A bound can be a
  constant definition (``0..MaxHeight`` in ``Timeout!Log2Ceil``) or
  computed from constants (``1..(Cardinality(Entries) + 1)`` in
  ``Timeout!InsertAny``, where ``Insert`` selects the valid positions).
  A sequence with a length that depends on the state is a function on a
  constant domain, cut with ``FunAsSeq(f, len, capacity)`` of the
  standard module ``Apalache`` (decision D16 of 2026-10-31):
  ``WaitQueue!Ordered`` and the wake calls of ``Waitable!Flush`` use
  ``1..Cardinality(Threads)`` and a filler after the last element. TLC
  evaluates ``f`` on all of ``1..capacity``, so ``f`` must be defined
  there. ``lib/Apalache.tla`` is an unchanged copy of the module of
  Apalache 0.62.4 for TLC (``tla2tools.jar`` has no such module). Apalache
  uses its own copy (``tools/run_apalache.sh`` removes the file).
- ``CHOOSE`` only over finite sets.
- Each ``CHOOSE`` has exactly one witness, and an invariant or an example
  test checks this: ``RanksDistinct`` and ``BestIsHead`` for
  ``WaitQueue!Best`` and ``Ordered``, the test "Log2Ceil one witness" in
  ``mc/TimeoutTest`` for ``Timeout!Log2Ceil``. Each ``CASE`` has guards
  that do not overlap, or an ``OTHER``. The reason: TLC, TLAPM and
  Apalache give these constructs different meanings when more than one
  witness exists or when guards overlap (TLA+ RFC 26, open). With this
  rule, a difference between TLC and Apalache has a real cause.
- Records with a fixed set of fields.
- No ``RECURSIVE`` operators (Apalache needs unroll limits for them).

The doc extension takes ``@type`` and ``@typeAlias`` lines as tags, so
they do not show in the rendered prose.

Behavior part and property part
*******************************

Decided on 2026-10-28 (roadmap, "Method decision 2026-10-28"). Each spec
has two parts (named "descriptive layer" and "normative layer" until
2026-10-30):

- **Behavior part: the operators.** They follow the C code
  (``@c-function``), also where the code is surprising. An operator is
  never adjusted to the intent. The unit tests check the code against the
  operators, later trace validation too. An incidental choice of the code,
  which no document promises, is a free choice in the model.
- **Property part: the properties.** Each property is written from its
  own source, before a look at the code if possible: a requirement
  (``@source ZEP-SRS-2-13``) or a document (``@source doc:<page>``). Where
  the source text has more than one reading, the comment of the property
  or the register of findings states the reading. A property can read a
  history variable that records what the source names (``readySince`` for
  "ready the longest"). Such a variable is not a field of the code.

A property of the property part that fails on the model is a design
finding. Its model configuration expects the failure (``mc/expected.txt``,
with a comment that names the finding). A property that cannot be written,
because the sources say nothing, is a finding too. One register holds all
findings (the workspace notes ``claude/kernel-unit/tla/findings.md`` for
now). Each finding gets a class: defect, intended but undocumented,
accepted deviation, or open.

The pilot is ``lib/Scheduler`` (finding P7, 2026-10-28). Its normative
properties are ``PreemptibleRunsHighest`` (ZEP-SRS-2-9, 2-12),
``SwitchSelectsHighest`` (2-12), ``TieGoesToLongestReady`` (2-13) and
``CoopKeepsCpu`` (2-14). The configurations ``p7_*`` and ``coop_rule`` of
``mc/MCScheduler`` check them. The last two properties fail as expected.
Round A of ``Platform`` (2026-10-29) added ``UnlockPreempts`` (2-9, finding
P2-w, configurations ``p2_window*``), ``BlockedLosesCpu`` (2-12, 2-14,
candidate finding SW-1, configuration ``gap_coop_pendsv``) and the
condition of use ``NoSwitchWhileLocked``. The configurations with the
suffix ``_pendsv`` check the variant ``arch_swap()``.

Conventions
***********

Names
   An action that models a C function has the name of the function
   without the prefix (``Give`` for ``z_impl_k_sem_give()``) and the tag
   ``@c-function``. Properties have a name that states the rule
   (``NoWaitWhileAvailable``).

Comments
   The comment block directly before a top-level definition is its
   documentation, in RST. The Sphinx extension in ``doc/_extensions/``
   renders it. Tags at the end of the block, one on each line:

   .. code-block:: none

      \* @expresses ZEP-SRS-5-3
      \* @source ZEP-SRS-2-13
      \* @kind invariant
      \* @c-function z_impl_k_sem_give
      \* @expected violation
      \* @grain fine
      \* @kconfig CONFIG_USE_SWITCH
      \* @assumption arch/arm/core/cortex_m/exc_exit.c:57 (the reason)

   ``@expresses`` names a requirement that the definition expresses (one
   UID on each line). ``@source`` names the source of a property of the
   property part, one on each line: a requirement UID (the doc extension
   also makes it an ``expresses`` link) or ``doc:<page>`` for a document.
   ``@kind`` is one of:

   - ``action``: a step of the system, usually the model of a C function
     (with ``@c-function``). It is part of ``Next``.
   - ``action-property``: a rule for each step (``[][A]_v``). TLC checks
     it as a ``PROPERTY`` and reports "Action property ... is violated".
   - ``invariant``, ``liveness``, ``probe``: the other properties.
   - ``definition``: a helper (the default).

   A property that expresses a design rule is in ``lib/`` or
   ``objects/``, so that the documents show it. ``mc/`` has only what
   belongs to one model run: the constants, the environment and the
   probes. A model checks a library property through an alias
   (``Prop_AddIsFifo == WQ!AddIsFifo``).

   ``@expected violation`` marks a property that TLC must find false (a
   documented limit, or a probe that shows a state is reachable).

   ``@grain fine`` marks an action whose step is finer than the grain of its
   module (see `Coarse and fine grain`_). The values are ``coarse`` and
   ``fine``. A module without the tag has coarse grain.

   ``@kconfig`` names a Kconfig option: on a constant, the option that the
   constant models; on a property, the option under which it applies (see
   `Kconfig`_). The doc extension shows it and sets the need field
   ``tla_kconfig``. A tag line can name more than one option.

   ``@assumption`` marks an item of an assumption module (``Platform``):
   the code location or the document that the item rests on, and a short
   reason in parentheses. One location on each line.

TLC and nested instances
   ``UNCHANGED PF!platVars``, where ``platVars`` is a tuple of the
   variables of an instance of an instance, fails in TLC with "the
   identifier ... is either undefined or not an operator". Name the
   variables (``UNCHANGED <<irqNest, pendsv>>``). An operator of the
   instance with a prime (``PF!SwitchPending(c)'``) works.

Model configurations
   ``mc/MC<Object>_<scenario>.tla`` and ``.cfg``, one for each twister
   scenario of the unit test app of the object, with the same Kconfig
   options as constants. ``mc/MC<Object>Refinement.tla`` and
   ``mc/MC<Object>Refinement_<scenario>.cfg`` check that the fine-grain
   module of the object refines its coarse-grain module (see `Coarse and fine grain`_).

Example tests (decided on 2026-10-26)
   Each module ``lib/<Module>.tla`` and ``objects/<Module>.tla`` has a test
   module ``mc/<Module>Test.tla`` with the configuration
   ``mc/<Module>Test_default.cfg`` and the line ``<Module>Test default
   pass`` in ``mc/expected.txt``. The test module evaluates the queries and
   the helpers of the module on chosen states and compares each value with
   the expected value: ``Check(name, got, want) == Assert(got = want,
   <<name, "got", got, "want", want>>)``. It covers at least the empty
   case, one element, the order or priority rule in both directions, and
   each helper that computes a cost.

   The models and the tests check different things. An invariant checks a
   rule in each reachable state. A test fixes single values that a rule
   alone does not fix. Example: ``Before`` with the wrong direction of the
   priority is still a total order. ``MCWaitQueue`` passes with this
   defect, and ``WaitQueueTest`` fails ("prio: Best", got ``t1``, want
   ``t2``). ``Scheduler!Choices`` with a reversed tie rule passes
   ``MCScheduler`` and fails ``SchedulerTest`` ("up: current wins a tie").

   The tests are invariants of a spec with one state (``Init == unused =
   0``, ``Next == UNCHANGED unused``), not ``ASSUME`` statements. SANY gives an
   expression of an instance of a module with variables the expression level 1, also
   if each variable is replaced by a constant, and it rejects such an
   ``ASSUME``. TLC sees the same invariants as constant formulas and warns
   that an ``ASSUME`` is better. The warning has no effect on the result.
   An action (with primes) cannot be evaluated on fixed states. The models
   check the actions.

Expected results
   ``mc/expected.txt`` lists each model with its expected result (pass, or
   the name of the property that fails). The run script compares the
   results with this file. A difference fails the run, as the test
   inventory of the unit tests does.

Kconfig
*******

Decided on 2026-10-28 (roadmap, "Kconfig in the TLA+ library", from the
research ``research/kconfig-family/`` of the workspace notes). A Kconfig
option has one of five kinds, and each kind has its place in the specs:

.. list-table::
   :header-rows: 1
   :widths: 30 40 30

   * - Kind
     - Place in the spec
     - Examples
   * - 1. No effect at the level of the model: an implementation choice
       with the same visible behavior.
     - Not in the spec. A comment says that the module covers all values.
       The unit tests check each scenario.
     - ``CONFIG_WAITQ_SIMPLE`` / ``_SCALABLE``
   * - 2. Changes the behavior.
     - A ``CONSTANT`` and a predicate that guards a branch of an action.
       Each ``.cfg`` fixes the value and matches one twister scenario.
     - ``CONFIG_USE_SWITCH`` (``Platform!UseSwitch``), the timeout
       backend, ``CPUS``
   * - 3. A condition that a safe system must meet.
     - ``ASSUME`` for a structural limit. The premise of a property for a
       condition of use, with a configuration that shows the failure. It
       goes into the safety manual.
     - the heap size of the timeouts (``minheap_full``)
   * - 4. An initial value that the API can change at run time.
     - The initial value of a variable.
     - ``CONFIG_TIMESLICE_SIZE``
   * - 5. Adds only checks.
     - The fault model: a constant that selects a panic, an error code or
       undefined behavior for a misuse. It comes with the specs of the
       objects.
     - ``CONFIG_ASSERT``, ``CONFIG_RUNTIME_ERROR_CHECKS``

The rules:

- A property that applies only under an option has a guard
  (``Prop == Kconfig => P``), so that the document shows the condition,
  and the tag ``@kconfig`` with the option.
- Each constant of kind 2, 3 or 4 has the tag ``@kconfig CONFIG_X``. A tagged
  constant has its own ``CONSTANT`` statement with a doc comment at column
  0, so that the doc extension and the coverage check read the tag. Round A
  (2026-10-29) tagged ``Platform!UseSwitch``, round B the other constants
  (``CPUS``, ``Backend``, ``HeapCapacity``) and the guarded properties
  (``RqStampsNormal``, ``HeapWithinCapacity``, ``NoPendSVWithSwitch``).
  An option of kind 1 has no tag, only a comment (``WaitQueue``: the wait
  queue backends; ``Scheduler!RqBefore``: the run queue backends).
- TLC checks product by product: one run for each twister scenario. SANY
  accepts only a constant expression for a ``CONSTANT`` of a module with
  variables, so a ``.cfg`` cannot give a family. Apalache can check a
  family with ``--cinit`` (mostly integer ranges).
- The coverage check: each option that a spec names in a ``@kconfig`` tag
  has a ``.cfg`` for each relevant value, or a stated reason.
  ``mc/kconfig.txt`` gives the relevant values of each symbol: the value of
  the library constant for each one (``CONFIG_USE_SWITCH y UseSwitch
  TRUE``), or a reason (``CONFIG_TIMEOUT_BACKEND_WHEEL y - not in the
  model yet ...``). ``tools/kconfig_coverage.py`` reads the tags, this file,
  ``mc/expected.txt`` and the ``.cfg`` files, and reports each value with
  the model runs that check it, and each tagged property with its runs. A
  gap (a value without a run and without a reason, a symbol without lines,
  a property that no run checks) gives the exit status 1. The script finds
  a library constant by its name in the ``INSTANCE ... WITH`` substitutions
  of the model. It needs the Python of the doc build (``pygments``).
  ``CONFIG_USE_SWITCH``: the configurations of ``mc/MCScheduler`` without a
  suffix have ``y``, those with the suffix ``_pendsv`` have ``n``. The
  large runs (``default``, ``coop``, ``p7_rules*``, ``smp*``) have only
  ``y``. ``n`` has the small run ``small_pendsv`` and the P7 runs.
- An option that the architecture always selects is not a constant: the
  spec states it as an ``@assumption`` (``CONFIG_SWAP_NONATOMIC`` is ``y``
  on each Cortex-M).

Layout
******

.. code-block:: none

   spec/tla/
     README.rst        this design note
     lib/              Platform, Scheduler, WaitQueue, Timeout, Waitable,
                       Apalache (a copy of the standard module, for TLC)
     objects/          one module for each kernel object
     mc/               model configurations, example tests, expected.txt
     trace/            trace specs and the schema of the trace records
     c-functions.json  the hashes of the tagged C functions at the pin
     selftest/         known-answer models for TLC, expected.txt
     apalache/         modules for Apalache, expected.txt (research)
     tools/            run_tlc.sh, run_tlc_remote.py, kconfig_coverage.py,
                       run_apalache.sh, tla2tools.sha256, apalache.sha256,
                       TOOLS.rst, c_function_hashes.py, uses_graph_diff.py
       unitmap/        copies of the generator scripts of the unit map

Running
*******

TLC needs Java 11 or later and ``tla2tools.jar`` v1.8.0, the pre-release
build of 2026-10-20 (rev ``d2e1472``). The run script stops if the hash of
the jar is not the hash in ``tools/tla2tools.sha256``.

The pre-release is a rolling release: each new build replaces the jar at
the download URL of the tag ``v1.8.0``. Keep a copy of the pinned jar
(the archive: ``tools/TOOLS.rst``). A later download has a different
hash, and the run script refuses it. The
version 1.8.0 has the REPL (``java -cp tla2tools.jar tlc2.REPL``), the
parameters of an action in the steps of a trace (``Take(t1)``), and the
name of a violated temporal property. These features are the reasons
for the pin (2026-10-22). The results of the models in
``mc/expected.txt`` are the same as with v1.7.4.

TLC 1.8.0 can send usage statistics. Without the file
``~/.tlaplus/esc.txt``, each run looks up a host name in DNS, and sends
statistics if the name resolves. The line ``NO_STATISTICS`` in this file
stops the lookup.

.. code-block:: console

   export TLA2TOOLS=/path/to/tla2tools.jar
   spec/tla/tools/run_tlc.sh              # all models in mc/expected.txt
   spec/tla/tools/run_tlc.sh MCWaitQueue  # one model
   TLC_SUITE=selftest spec/tla/tools/run_tlc.sh  # the selftest of TLC
   TLC_LIST=sensitivity spec/tla/tools/run_tlc.sh MCScheduler:small_sens_t2
   python3 spec/tla/tools/kconfig_coverage.py  # Kconfig coverage (doc Python)

Locally, ``run_tlc.sh`` runs one TLC process at a time, with one worker.
Do not run the large lines (``MCScheduler default``, ``coop``, ``smp``,
``p7_rules*``, ``small*``) on a small host: use the lab host.

A line of ``mc/expected.txt`` can have fields after the expected result:
``states=`` and ``depth=`` (the recorded counts: a different count fails
the line), ``trace=`` and ``lasso=`` (the error trace), ``heap=`` (the
Java heap of the line) and ``repeat=`` (run the line more than once, each
run must give the same counts). Each pass line has recorded counts. After
a change of a model that changes a count, record the new count in the
same commit and give the reason in the commit message.

The sensitivity set is a second list file, ``mc/sensitivity.txt``, in the
format of ``mc/expected.txt``. Each configuration ``<base>_sens_<axis>``
changes only bounds of a base line (threads, objects, priorities,
entries) and checks the same properties. The configurations ``*_sym`` add
a symmetry set. ``TLC_LIST=sensitivity`` (``run_tlc.sh``) or ``--list
sensitivity`` (``run_tlc_remote.py``) selects it. A run of
``mc/expected.txt`` never runs these lines. The whole list takes about 47
hours with one worker. The argument for each bound is in the workspace
notes (``tla/small-scope.md``).

``tools/TOOLS.rst`` is the tool note: the identity of the pinned jar, its
known defects and why they do not affect the evidence, the selftest, and
the steps for a new pin.

Apalache 0.62.4 (``tools/apalache.sha256``) needs Java 17 or later.
``tools/run_apalache.sh`` runs the lines of ``apalache/expected.txt`` and
compares each result with the expected result. See `Apalache checks`_.

.. code-block:: console

   spec/tla/tools/run_apalache.sh              # all lines (about one hour)
   spec/tla/tools/run_apalache.sh APWaitQueue  # the lines of one module

Run one Apalache or TLC process at a time on a small host. The script
limits each run to 3 GB (``APALACHE_MEM``).

Apalache checks
===============

Research only, not evidence (``tools/TOOLS.rst``). The state of
2026-10-30:

- **Type check** (2026-10-31). ``Platform``, ``Timeout``, ``WaitQueue``,
  ``Scheduler`` and ``KSem`` pass, since the decisions D15 (``NoThread``
  for ``WaitQueue!Head`` and ``WalkStop``) and D16 (``FunAsSeq`` in
  ``WaitQueue!Ordered`` and ``Waitable!Flush``). ``Waitable`` is a
  template and type-checks only through an object module.
- **Inductive invariants.** Each module in ``apalache/`` writes an
  inductive invariant ``IndInv`` and checks three obligations:
  ``Init => IndInv`` (length 0), ``IndInv /\ Next => IndInv'`` (initial
  predicate ``IndInv``, length 1) and ``IndInv => Inv`` (length 0). The
  library modules have no ``Next``. The checks use the ``Next`` of the
  model module of ``mc/``, with the constants of one configuration.
- ``apalache/APWaitQueue``: ``StampsNormal`` with the types is inductive
  for the ``Next`` of ``mc/MCWaitQueue`` (3 threads, 2 objects,
  3 priorities). It implies ``OrderIsTotal``, ``RanksDistinct`` and
  ``BestIsHead``. ``OrderIsTotal`` alone is not inductive.
- ``apalache/APScheduler``: ``PendingIsQueued`` with ``CurIsReady``,
  ``RqStampsNormal``, ``StampsNormal``, ``ArmedOnce`` and the types is
  inductive for the ``Next`` of ``mc/MCScheduler`` with the constants of
  ``small`` and of ``default``. The module extends ``MCScheduler`` (Apalache rejects an
  instance chain of three levels with an operator for a constant) and
  splits ``Next`` into groups, one run for each group. The lines remove
  the symmetry set ``SymThreadsObjs`` of ``MCScheduler`` (key ``omit=``):
  it is a set of functions on threads and objects together, and Apalache
  has no type for it.

- The workspace notes have one more check (2026-10-21, no line here): the
  cost bound of ``Timeout`` for both backends and the capacities 1 to 3
  in one run (``--cinit``, length 6,
  ``research/kconfig-family/apalache/MCTimeoutApa.tla``).

These results hold for all lengths of a behavior, but only for the
constants of the line. They do not replace the small-scope arguments for
other sizes.

Running on the lab host
=======================

``tools/run_tlc_remote.py`` runs ``tools/run_tlc.sh`` on the lab host
(default ``tobias@cos-workstation``, directory ``/wrk/z/lab-tla``) and
copies the results back. The lab host has a JDK and the read-only archive
of the pinned jar (``archive/tla2tools/sha256-<hash>/``). The script takes
the same arguments as ``run_tlc.sh``:

.. code-block:: console

   spec/tla/tools/run_tlc_remote.py                        # all lines, pinned
   spec/tla/tools/run_tlc_remote.py MCScheduler:default    # one line
   spec/tla/tools/run_tlc_remote.py --selftest-only        # the selftest only
   spec/tla/tools/run_tlc_remote.py --list sensitivity     # the sensitivity set
   spec/tla/tools/run_tlc_remote.py --unpinned MCTimeout   # working tree
   spec/tla/tools/run_tlc_remote.py --detach MCScheduler   # start only
   spec/tla/tools/run_tlc_remote.py --collect <run-id>     # get results

The two modes:

- **pinned** (default): the worktree must be clean. The script sends the
  current commit in a git bundle. The clone on the lab host takes it with
  ``git merge --ff-only``, so the commit has the same hash on both hosts.
- **unpinned** (``--unpinned``): the script copies the working tree of
  ``spec/tla/`` to the lab host. The record has the mark ``unpinned``, the
  base commit and the SHA-256 of the diff. The output has the diff.

Each job first runs the selftest of TLC (``selftest/expected.txt``) with
one worker. If the selftest fails, no model runs. Then the job runs the
selected lines of ``mc/expected.txt``.

The worker rule: each TLC process has one worker. The pinned jar does not
have the fix of tlaplus issue #1445: with more than one worker in one TLC
process, TLC can miss states and violations. For speed, the job runs
several TLC processes at the same time (``--jobs``, default 6, at most 8).
Each process has its own ``-metadir`` and its own ``java.io.tmpdir``. The
rule and its reason are in ``tools/TOOLS.rst``. ``--workers <n>`` with
n > 1 stays for experiments. Its record has ``evidence: false``. On
2026-10-29, 4 and 8 workers in one process gave the reference counts for
each pass line, but this does not show that no state was missed.

Memory: each line has its own Java heap, the field ``heap=`` of the line
or ``--mem`` (default ``2g``). A line starts only if its heap fits in
``--mem-budget`` (default ``20g``) together with the heaps of the lines
that run. The lines with the most recorded states start first. Each TLC
process also has 2 threads for the garbage collection. On 2026-10-30, all
lines ran with 2g: the peak memory of a process was at most 2.1 GB
(``MCScheduler default``, ``smp`` and ``small_b``, the lines with
liveness properties), so 6 large lines at the same time need about
13 GB of the 31 GB of the lab host. No line needs ``heap=`` today. The
run of all 50 lines took 29 min, in place of 1 h 48 min with one
process. The longest line (``MCScheduler default``, 1738 s) sets the
lower limit.

The output goes to ``build/lab/<run-id>/`` (option ``--out``): the logs,
``selftest/``, ``summary.md``, ``results.txt``, ``rss.txt`` and
``record.json``. For each line, the summary and the record have the
result, the distinct states, the depth, the trace length, the collision
estimate of TLC, the time, the heap and the peak memory (VmHWM). The
record also has the revision, the mode, the jar and its hash, the Java
version, the host, the times, and ``evidence`` (true or false) with the
reasons. A run is evidence only if it is pinned, uses the pinned jar, has
one worker in each process, and the selftest passed.

The rules of the lab host apply to each job. A job holds the lock
``/wrk/z/lab-tla/.lock``, so only one job runs at a time, and the next job
waits. TLC runs with ``nice -n 10``. The job deletes the TLC state
directories at the end. The job continues if the connection stops. Then
``--collect <run-id>`` gets the results.

Drift checks
************

The library follows the code of one Zephyr commit, the pin
(``770fdef1567``, also in the prose of ``lib/Platform.tla``). Two scripts
compare the pin with another commit. They read the Zephyr tree only with
``git grep``, ``git show`` and ``git archive`` of a commit. Nothing runs
them automatically yet.

Body hashes
===========

``tools/c_function_hashes.py`` finds the definition of each name of an
``@c-function`` tag. It removes the comments and the whitespace, and it
hashes the C tokens of the signature and the body. The record
``c-functions.json`` holds, for each name, each definition with its file,
line and hash, and the full hash of the pin.

The script finds functions, static inline functions of headers, aliases
(``FUNC_ALIAS``, ``ALIAS_OF``), macros (``#define``) and assembly routines
(``SECTION_FUNC`` in a ``.S`` file). A name can have more than one
definition: one for each timeout backend (``z_timeout_q_insert``), one for
each ``#if`` branch (``irq_lock``), or an inline function and an alias
(``z_arm_int_exit``). The record holds all of them. The search scope is
the code of the safety case on Cortex-M: ``kernel/``, ``include/zephyr/``
without other architectures, ``arch/arm/`` without Cortex-A/R, and the
SysTick driver files. If a name has no definition, the script looks for
``z_impl_<name>`` (a system call).

The modes:

.. code-block:: console

   spec/tla/tools/c_function_hashes.py tags                  # each tag at the pin
   spec/tla/tools/c_function_hashes.py check --against <rev> # record vs. commit
   spec/tla/tools/c_function_hashes.py check --against <rev> --diff
   spec/tla/tools/c_function_hashes.py log --range <pin>..<rev>
   spec/tla/tools/c_function_hashes.py record --commit <rev> # new pin

- ``tags`` finds a tag without a definition at the pin (the stale tag
  ``z_abort_timeout`` of 2026-10-29 is this case). It also finds a tag that
  is not in the record, a record entry without a tag, and a pin in
  ``lib/Platform.tla`` that is not the pin of the record. It lists each
  wrapper (a body of one statement) whose callee has no tag.
- ``check`` gives one result for each definition: ``unchanged``,
  ``shifted`` (other line), ``moved`` (other file, same hash), ``changed``,
  ``changed-trace`` (only ``SYS_PORT_TRACING_*`` or ``LOG_*`` statements
  changed), ``moved-changed``, ``missing`` or ``added`` (a new definition,
  for example a new backend). ``--diff`` shows the source diff without
  comments.
- ``log`` compares each commit with its first parent and names the
  commit that changed a recorded body. ``--range A..B`` takes the commits
  that change a file of the record.

The exit status is 0 without a difference, 1 with a difference, and 2 on
a setup error.

Uses graph
==========

``tools/uses_graph_diff.py --other <rev>`` runs the generator scripts of
the unit map (copies in ``tools/unitmap/``) on the pin and on ``<rev>``.
It extracts the necessary directories with ``git archive`` into
``build/drift/unitmap/``. It reports:

- the new and the removed edges between the components after the cuts
  (``meta.layers.edges`` of ``units.yaml``);
- the new and the removed cut edges (hooks);
- each edge from a component to a component of a higher layer (world,
  foundation, scheduler, kernel API, client);
- the new, the removed and the unknown unit files. A file that is not in
  the table of ``gen.py`` gets the group ``New``.

``--reference <units.yaml>`` compares the output for the pin with the unit
map of the original scripts. At the pin, the copies give the same edges,
cuts and components. The script needs universal-ctags 6.x and PyYAML.

What the checks do not detect
=============================

A changed hash means that the text changed, not that the behavior
changed. A refactor gives a changed hash: ``772e73c8aac`` changes eight
recorded bodies: it replaces the calls of the scheduler lock with
helpers, and the behavior stays the same. Thus each change needs a
review.

The checks do not detect:

- A change of a callee without a tag. The hash covers the text of the
  tagged function only. ``sys_clock_announce()`` is a wrapper of
  ``sys_clock_announce_locked()``, so its hash does not see a change of
  the announce algorithm. The mode ``tags`` lists such wrappers.
- A change of a macro that a body uses (``K_SPINLOCK``,
  ``Z_SCHED_SPINLOCK``), and of an inline function of a library header.
  Only a tagged macro has a hash.
- A call through a function pointer: timeout handlers, walk callbacks,
  work handlers. The callee is not in the text, and the uses graph has no
  edge for it.
- The Kconfig selection. The scripts read all ``#if`` branches. A change in
  a branch that a product does not build is a change. A new default in a
  Kconfig file is not a change. The record does not say which definition
  (which backend) a product builds.
- A change of data: a new field of ``struct k_thread``, or a new initial
  value in a static initializer.
- The file and line locations of the ``@assumption`` tags.
- The uses graph is lexical: it has no preprocessor, and it does not see
  calls through function pointers or inside most macros (see the limits in
  ``units.yaml``).

A drift job
===========

The tags and hashes are the pointer from the specs to the code. The
detectors of a behavior change are the tests of the real code: the unit
tests, the contract tests and the trace checks. A drift job uses the
scripts to find the specs that a new commit touches. A periodic job does
these steps for a new upstream commit ``<rev>``:

1. Run ``c_function_hashes.py tags``. If a tag is stale, stop: correct
   the tag first.
2. Run ``c_function_hashes.py check --against <rev> --diff``. For each
   result that is not ``unchanged`` or ``shifted``, run ``log --range
   <pin>..<rev>`` to find the commit.
3. Run ``uses_graph_diff.py --other <rev>``. A new edge, a new cut or an
   edge against the layer order is a design change. Compare it with the
   ``INSTANCE`` and ``EXTENDS`` relations of the modules.
4. Build the unit apps against ``<rev>``. Run the unit tests, the contract
   tests and the trace checks.
5. Review each change against the operator that has the tag. Change the
   spec, or record a finding.
6. Move the pin: run ``record --commit <rev>``, change the pin in
   ``lib/Platform.tla``, and commit both together.

Run ``record`` again after each change of a tag. Else ``tags`` reports the
difference.

Open points
***********

1. Done (2026-10-21): Apalache accepts operators as arguments for the
   template (see `Composition pattern`_).
2. Abort: ``Scheduler!Abort`` models ``k_thread_abort()`` of a waiter
   (2026-10-27). Open: state the documented limits (``kernel.h``) as
   expected violations in the object models. The mutex has
   no reaction to the abort of a waiter (the owner stays boosted), and
   ``k_poll()`` leaves registrations (finding F3 of the paper check).
3. The common properties C1 to C14 of the paper check: decide which ones
   become common requirements (roadmap step 2.1).
4. No requirement states the order rule of the wait queues for all
   objects. ``ZEP-SRS-5-14`` states "the highest-priority waiting thread"
   for the semaphore only. The order of arrival among waiters with the
   same priority is a requirement only for mailboxes (``mailboxes.sdoc``)
   and for ready threads (``ZEP-SRS-2-13``). Candidate for a common
   requirement (property C4 of the paper check).
5. The possible defects F1 to F5 of the paper check: confirm them with
   tests before an upstream report.
