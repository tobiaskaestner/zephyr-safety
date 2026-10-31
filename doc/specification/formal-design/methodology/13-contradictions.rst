13. Contradictions of the current plan, and the answer of this architecture
===========================================================================

.. list-table::
   :header-rows: 1

   * - Contradiction (module map agent, inventory)
     - Answer
   * - Platform at level 2 is a separate ``_L2`` module, or ``Platform`` grows
     - Fine modules of ``Platform`` in its refinement tree, one for each reason. The interrupt lock is already coarse. They add lock owners, IPI flags and interrupt nesting.
   * - "level" means the position in the unit map
     - the uses graph and the layer (section 2)
   * - The grain of 11 planned modules is not decided
     - Each contract module is coarse. A fine module needs a stated reason (5.2).
   * - ClockPort is a module or a hook
     - a hook (section 2)
   * - "provides", "requires" and "uses" all name ``INSTANCE`` / ``EXTENDS``
     - only "uses" stays, at two levels (call, ``INSTANCE``), with the matching rule of 5.1
   * - "each component has one contract module", but ``ThreadState``, ``RunQueue``, ``SchedLock`` are inside ``Scheduler.tla``
     - at most one contract module per component, and one contract module can cover several components (5.1)
   * - Names of the object modules
     - ``K<Object>`` for the contract module of an object (as ``KSem``), ``K<Object>_<Reason>``, ``MCK<Object>Refinement``
   * - The trace record schema is a module or not
     - not a module, a JSON schema next to the trace module
   * - 2-9 and 2-14 belong to ThreadState or to Scheduler
     - A requirement belongs to the component whose property expresses it. ``should_preempt()`` is code of ``kthread.h``, but its rule is a property of ``Scheduler``. The unit map assigns code, not requirements.
   * - Properties in the "descriptive layer" (SC:904)
     - They are behavior invariants (section 6), in the behavior part, with ``@source code``
   * - The contract modules have no ``Next``. The model-check module builds ``Next`` from their actions, client wrappers, mutants and restrictions (``MCSetPrioBy``, ``NoOuterLock``).
     - Each module defines ``Init``, ``Next`` and ``Spec`` with the most general environment. The restrictions become conditions of use in the module (section 6).
   * - ``@kind assumption`` is planned, ``@assumption`` exists
     - ``@assumption`` stays as the tag. The role table lists it.
   * - ``@kind action`` on definitions that are not steps
     - The role (step action or sub-action) is separate from the TLA+ form. The doc extension derives the role from ``Next``.
