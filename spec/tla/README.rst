..
   Copyright (c) 2026 inovex GmbH
   SPDX-License-Identifier: Apache-2.0

TLA+ design specification of the kernel objects
###############################################

This directory holds the formal design model of the Zephyr kernel objects
(semaphore, queue, message queue, stack, memory slab, events, condition
variable, mutex, and more later). The model is written in TLA+ and checked
with TLC.

Status: design note of 2026-10-21 (roadmap step 2.0). ``lib/WaitQueue``
and ``lib/Timeout`` exist and are checked alone (``mc/MCWaitQueue``,
``mc/MCTimeout``). ``Platform``, ``Scheduler`` and ``Waitable`` do not
exist yet. The k_sem proof of concept is still in the workspace notes
(``claude/kernel-unit/tla/``). It moves here when it is expressed on the
library.

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
  scheduler with fakes. The scheduler layer of this model (layer A below)
  is the contract that a reference fake implements and that contract tests
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
   * - Layers
     - Two. Layer A is the contract of the scheduler API that the objects
       call. Layer B is the ``Waitable`` template that the objects
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
       (``cur[c]``), the interrupt lock state, and whether an ISR runs.
     - Registers, caches, the memory model.
   * - Interrupt and ISR
     - An ISR is an actor that runs on a CPU while that CPU has interrupts
       unlocked. It is not preempted by a thread. It calls only
       non-blocking operations. A pend from an ISR sets ``panic``, as
       ``z_pend_curr()`` does (``kernel/sched.c``). At first, at most one
       ISR runs on each CPU (no nesting).
     - Interrupt priorities, nesting (later, for the timer findings).
   * - Thread
     - Base priority and current priority (``prio[t]``), the state (ready,
       running, pending, suspended, dead), the object that it waits on
       (``pendedOn[t]``), the result of its last wait (``swapRet[t]``,
       ``swapData[t]``).
     - Stacks, the thread entry function.
   * - Scheduler
     - The ready set, the rule "the highest priority runs", cooperative
       threads, the reschedule points.
     - The ready queue implementations (``CONFIG_SCHED_*``).
   * - Wait queue
     - One set of waiters for each object, with priorities and stamps (see
       `The wait queue`_).
     - The list and tree code (``sys_dlist``, ``rbtree``). The unit tests
       of that code cover it.
   * - Spinlock
     - Level 1: implicit, each action is one critical section. Level 2: an
       owner CPU for each lock (see `Two grains`_).
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
       configuration with the same options.
     -

Module structure
****************

.. code-block:: none

   lib/Platform     CPUs, ISR actors, lock owners (level 2)
     |
   lib/Scheduler    thread state, priorities, current thread, swap result,
     |              panic, ready set; Abort, SetPrio, Resume
   lib/WaitQueue    pendedOn, stamps, Before, Best, Ordered; Add, Remove
     |
   lib/Timeout      timeout entries, the expiry event, the insertion cost
     |
   lib/Waitable     layer B: Take, Give, Flush, ResumeOp, the common
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
     - CPUs, ISR actors, lock owners (level 2 only)
     - ``InIsr(a)``, lock steps
     - objects, priorities
   * - ``Scheduler``
     - ``tstate``, ``prio``, ``cur``, ``swapRet``, ``swapData``, ``panic``
     - layer A operators, ``Abort``, ``SetPrio``, ``Resume``, the ISR guard,
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

``pendedOn`` is one function over all threads and all objects of all types.
The mutex chain walk reads the wait state of other threads, and an abort or
a priority change acts on a waiter in any wait queue.

Layer A: the scheduler contract
===============================

One operator for each C function of the scheduler API that the objects
call. An object action composes these operators inside one critical
section. The trace hook of the unit tests logs one record for each call of
this API. Thus the names in the trace and in the model are the same.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Operator
     - C function and meaning
   * - ``PendCurr(o, t, to)``
     - ``z_pend_curr()``: panic if the caller is an ISR. Else add ``t`` to
       the wait queue of ``o``, preset ``swapRet[t]`` to ``-EAGAIN``, add a
       timeout entry if ``to`` is finite, release the lock, switch.
   * - ``WakeFirst(o, ret, data)``
     - ``z_sched_wake()``: the best waiter leaves the wait queue, its
       timeout is cancelled, it gets ``ret`` and ``data``, it is ready.
       FALSE if the wait queue is empty.
   * - ``WakeFirstWith(o, F)``
     - ``z_unpend_first_thread_locked()`` and ``z_sched_ready_locked()``
       with object code between them (msgq copy, mutex owner). ``F(t)``
       gives the result for the woken thread.
   * - ``WakeAll(o, ret, data)``
     - The loop ``while (z_sched_wake(...))``. One atomic wake of all
       waiters.
   * - ``WakeWalk(o, P, D)``
     - ``z_sched_waitq_walk()``: wake each waiter that satisfies ``P``, in
       the walk order, with the data ``D``.
   * - ``Timeout(t)``, ``Abort(t)``, ``SetPrio(t, p)``, ``Resume(t)``
     - Environment actions: the expiry of a timeout, ``k_thread_abort()``,
       ``z_thread_prio_set()`` (a waiter gets a new stamp), the return
       from the swap.

Layer B: the ``Waitable`` template
==================================

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

Two grains
**********

**Level 1 (object grain).** One action is one critical section under the
object lock. This is correct on one CPU, because the object lock also
locks the interrupts. It is also correct on SMP if the operation holds the
lock from the first read of the resource or the wait queue to the last
scheduler call. Most takes and gives of the eight units satisfy this.
Level 1 is the grain of the trace hook and of the generated tests.

**Level 2 (lock grain).** Lock acquire and lock release are separate steps.
Level 2 is necessary only for the operations that break level 1. The paper
check lists them:

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

Level 2 comes in roadmap step 5. Until then, each level-1 action of these
operations has a comment that names the gap.

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
construction. The walk order of ``z_sched_waitq_walk()`` is a separate
operator, because ``CONFIG_WAITQ_SCALABLE`` changes the walk, not the
order.

**Normalization.** Stamps grow without a limit, and TLC needs a finite
state space. After each step, the stamps are renumbered to their rank
(``1`` to ``|W|`` over all waiters). Two states that differ only in the
absolute stamp values become one state. A separate, bounded model can keep
real stamps with a wrap, to examine the renumbering of ``next_order_key``
in ``z_priq_rb_add()`` (an ``int``, the wrap is a signed overflow).

Higher priority means a lower number in Zephyr. ``Before`` uses the model
value ``prio`` with "greater is higher". The object modules convert at one
place, so that the review compares one rule.

Time and bounds
***************

The model has no clock. A thread that waits with a finite timeout has a
timeout entry. The action ``Timeout(t)`` is enabled while the entry exists.
``K_FOREVER`` makes no entry. ``K_NO_WAIT`` never pends.

For a thread wait, an atomic ``Timeout(t)`` is equal to the two-step
dispatch of ``kernel/timeout.c``: if a give wins, the handler finds nothing
to do. For the timer object this is not true (finding F1 of the paper
check). Thus ``Timeout`` offers the atomic form for level 1 and a two-step
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

In ``mc/MCTimeout``, the invariant ``CostBounded`` holds by construction:
the module computes the cost with the formula of the backend, and the bound
is a little larger. The probe ``Reach_DlistWorstCase`` shows that the worst
case (an insertion that walks over all entries) is reachable. The bound
becomes a real check when an object action adds the costs of several
operations (for example a wake of all waiters that cancels one timeout for
each waiter).

The observation record
**********************

Each action writes the variable ``obs``. It has a generic part from layer A
(``actor``, ``op``, ``wakes``, ``woken``, ``release``, ``ret``, the work
counters) and an object part (``args``). The trace hook of the unit tests
writes the same record from the fakes. The trace spec compares the two.
The generated tests read the same record. One record type also suits
Apalache.

Apalache
********

Apalache is a symbolic model checker for TLA+. It checks inductive
invariants and handles large integers, which TLC cannot list. It comes in
roadmap step 5. The specs keep a style that it can read from the start:

- Type annotations on each variable and constant (``\* @type: ...;``).
- A type annotation on each operator that reads a record field of its
  parameter, and on each generic helper (``Seq(a) => Set(a)``). Apalache
  cannot infer the record type from ``r.count`` alone. A type alias
  (``\* @typeAlias: semRes = { count: Int, limit: Int };``) keeps the
  annotations short.
- No ``CONSTANT`` operators (see `Composition pattern`_).
- No ``LAMBDA`` as an operator argument. A ``LAMBDA`` cannot have an
  annotation, so a ``LAMBDA`` that reads a record field does not
  type-check. Use a named operator.
- A range has constant bounds: ``1..Cardinality(W(o))`` is not
  accepted. ``WaitQueue!Ordered`` has such a range, so it is for TLC
  only (trace views).
- ``CHOOSE`` only over finite sets.
- Records with a fixed set of fields.
- No ``RECURSIVE`` operators (Apalache needs unroll limits for them).

The doc extension takes ``@type`` and ``@typeAlias`` lines as tags, so
they do not show in the rendered prose.

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
      \* @kind invariant
      \* @c-function z_impl_k_sem_give
      \* @expected violation

   ``@expresses`` names a requirement that the definition expresses (one
   UID on each line). ``@kind`` is one of:

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

Model configurations
   ``mc/MC<Object>_<scenario>.tla`` and ``.cfg``, one for each twister
   scenario of the unit test app of the object, with the same Kconfig
   options as constants.

Expected results
   ``mc/expected.txt`` lists each model with its expected result (pass, or
   the name of the property that fails). The run script compares the
   results with this file. A difference fails the run, as the test
   inventory of the unit tests does.

Layout
******

.. code-block:: none

   spec/tla/
     README.rst        this design note
     lib/              Platform, Scheduler, WaitQueue, Timeout, Waitable
     objects/          one module for each kernel object
     mc/               model configurations, expected.txt
     trace/            trace specs and the schema of the trace records
     tools/            run_tlc.sh, tla2tools.sha256, apalache.sha256

Running
*******

TLC needs Java 11 or later and ``tla2tools.jar`` v1.8.0, the pre-release
build of 2026-10-20 (rev ``d2e1472``). The run script stops if the hash of
the jar is not the hash in ``tools/tla2tools.sha256``.

The pre-release is a rolling release: each new build replaces the jar at
the download URL of the tag ``v1.8.0``. Keep a copy of the pinned jar. A
later download has a different hash, and the run script refuses it. The
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

Apalache 0.62.4 (``tools/apalache.sha256``) needs Java 17 or later. There is
no run script yet. The library modules type-check:

.. code-block:: console

   cd spec/tla/lib && apalache-mc typecheck WaitQueue.tla

Open points
***********

1. Done (2026-10-21): Apalache accepts operators as arguments for the
   template (see `Composition pattern`_).
2. Abort: model ``k_thread_abort()`` of a waiter, and state the
   documented limits (``kernel.h``) as expected violations. The mutex has
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
