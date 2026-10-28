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

The model has two layers. The operators are the descriptive layer: they
follow the C code, also where the code is surprising. The properties with a
``@source`` tag are the normative layer: each one states a requirement or a
documented rule, written from that source and not from the code. A property
of the normative layer that fails on the model is a design finding. Its
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

Scheduler contract
------------------

On one CPU the module follows the run queue and the cache of
``kernel/sched.c``. The normative properties ``PreemptibleRunsHighest``,
``SwitchSelectsHighest``, ``TieGoesToLongestReady`` and ``CoopKeepsCpu``
state :need:`ZEP-SRS-2-9`, :need:`ZEP-SRS-2-12`, :need:`ZEP-SRS-2-13` and
:need:`ZEP-SRS-2-14`. TLC finds counterexamples for ``TieGoesToLongestReady``
and ``CoopKeepsCpu`` (expected violations): a priority change with
``k_thread_priority_set()`` and an abort with ``k_thread_abort()`` call
``update_cache(1)``. These are open design findings.

.. tla:module:: Scheduler
   :body:
   :property-needs:
