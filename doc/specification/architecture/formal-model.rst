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

Each property with an ``@expresses`` tag, or with the kind ``invariant``,
``liveness`` or ``probe``, is a need of the type "Model Property". A
requirement that a property expresses lists the property as "Expressed by".

.. needtable::
   :types: prop
   :columns: id, title, kind, expected, tla_module as "Module"
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

.. tla:module:: Scheduler
   :body:
   :property-needs:
