Formal Design Model
===================

The design of the kernel objects is also a formal model in TLA+. The model
is in ``spec/tla`` of the safety repository. The TLC model checker examines
it: ``spec/tla/tools/run_tlc.sh`` runs each model and compares the result
with ``spec/tla/mc/expected.txt``. The design note
``spec/tla/README.rst`` gives the decisions, the entities and the
conventions of the model.

The model is work in progress. This page shows the modules of the library
(``spec/tla/lib``). The models of the kernel objects come later.

The model has two parts. The operators are the behavior part: they
follow the C code, also where the code is surprising. The properties with a
``@source`` tag are the property part: each one states a requirement or a
documented rule, written from that source and not from the code. A property
of the property part that fails on the model is a design finding. Its
configuration in ``spec/tla/mc/expected.txt`` expects the failure and names
the finding.

Each property with an ``@expresses`` or ``@source`` tag, or with the kind
``invariant``, ``action-property``, ``liveness`` or ``probe``, is a need of
the type "Model Property". A requirement that a property expresses or comes
from lists the property as "Expressed by". The column "Source" gives the
``@source`` tags.

.. needtable::
   :types: prop
   :columns: id, title, kind, expected, tla_source as "Source", tla_module as "Module"
   :style: table

Wait queue
----------

.. tla:module:: WaitQueue
   :body:
   :property-needs:

Timeout queue
-------------

.. tla:module:: Timeout
   :body:
   :property-needs:

Platform (the world below the scheduler)
----------------------------------------

The module ``Platform`` is an assumption module: it states only what
``kernel/sched.c`` relies on. Each item that rests on the architecture code
or on a document has the tag ``@assumption`` with that location. It has the
CPUs, the ISRs and their CPUs, the outer interrupt lock (``irq_lock()``
outside a kernel call) and the two variants of the context switch on
Cortex-M: ``CONFIG_USE_SWITCH`` (the switch is in the step of the reschedule
point) and ``arch_swap()`` with PendSV (the step PendSV selects later, and
ISRs can run in the gap).

.. tla:module:: Platform
   :body:
   :property-needs:

Scheduler contract
------------------

On one CPU the module follows the run queue and the cache of
``kernel/sched.c``. The normative properties ``PreemptibleRunsHighest``,
``SwitchSelectsHighest``, ``TieGoesToLongestReady`` and ``CoopKeepsCpu``
state :need:`ZEP-SRS-2-9`, :need:`ZEP-SRS-2-12`, :need:`ZEP-SRS-2-13` and
:need:`ZEP-SRS-2-14`. TLC finds counterexamples for ``TieGoesToLongestReady``
and ``CoopKeepsCpu`` (expected violations): a priority change with
``k_thread_priority_set()`` and an abort with ``k_thread_abort()`` call
``update_cache(1)``. These are open design findings. They occur with both
variants of the context switch.

TLC also finds counterexamples for ``UnlockPreempts`` (:need:`ZEP-SRS-2-9`):
``irq_unlock()`` is not a reschedule point, so a thread that woke a thread
with a higher priority under an outer interrupt lock keeps the CPU after
the unlock. With ``arch_swap()``, TLC finds a counterexample for
``BlockedLosesCpu`` (:need:`ZEP-SRS-2-12`, :need:`ZEP-SRS-2-14`): an ISR
that runs before PendSV can give the CPU back to a cooperative thread that
waits. These are open design findings too.

Round B (2026-10-29) added the join queue of a thread. TLC finds a
counterexample for ``PreemptibleRunsHighest`` (:need:`ZEP-SRS-2-9`):
``k_thread_abort()`` of another thread makes the joiners of the target
ready, and ``halt_thread()`` does not reschedule, so a joiner with a higher
priority does not run (finding F14). The fault-model step ``WaitqInit``
models ``z_waitq_init()`` on a wait queue with waiters, which is undefined
behavior in the code; ``NoUndefined`` shows the path (finding P6-u).

.. tla:module:: Scheduler
   :body:
   :property-needs:
