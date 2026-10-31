Decisions on the questions of the method review
###############################################

.. note::

   The user decided D1 to D18 on 2026-10-30 and 2026-10-31. The chapter
   :doc:`/methodology/index` (draft 3) does not apply them yet.

Source: the method review (workspace notes), section 6 and recommendations 3 to 10, and its
patch notes (workspace notes). This chapter records the decisions of the user and what each one
changes. It does not change the chapter :doc:`/methodology/index` (draft 3). The text changes go
into the next draft.

In this chapter, "the architecture" and "architecture section" refer to the chapter
:doc:`/methodology/index`, not to the Architecture document.

Round 1 (2026-10-30): scope of the safety case
----------------------------------------------

D1. IEC 61508-3 claim (review section 6, question 1)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Decision:** the TLA+ specs are a **formal design notation**, and bounded model checking is the
**verification of the design**. The safety case does **not** claim "formal proof" (Table A.9).

Effects:

- Recommendation 5 is **required evidence**. Each ``pass`` that the case uses needs its small-scope
  argument (workspace notes) and its sensitivity lines. This includes the open points of
  section 11 of the small-scope argument, and the last line ``p7_rules_sens_t4_sym``.
- A vacuous pass is not evidence (small-scope argument, observation 2). The probes for the premises
  (open point 5) are necessary, or the evidence scope lists the vacuous pairs.
- Recommendation 6 (Apalache inductive checks) is an **optional strengthening**. It removes the
  depth bound for the invariants that it covers, but the claim does not depend on it.
- The tool note (``spec/tla/tools/TOOLS.rst``) and the one-worker rule stay necessary: each cited
  ``pass`` comes from an evidence run.

D2. SMP (review section 6, question 3; roadmap open decision 6)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Decision:** safety case 1 is for **one CPU (UP) only**. SMP comes in a later increment.

Effects:

- Recommendation 8 (lock module ``SchedLock``, refinement lattice, fairness rule) **waits** for the
  SMP increment. Exception: the wrong sentence about transitivity in section 5.2 (patch note A3)
  is a logic error and is corrected in the next draft anyway.
- Patch note B21 goes into the next draft: the coarse modules are UP-only by construction.
- The configurations ``smp``, ``smp_rule`` and ``reach_smp`` stay as design exploration. They are not
  evidence, and the evidence scope says so.
- Roadmap step 5 (level 2 at lock grain) moves behind increment 1. The Apalache part of step 5
  follows D1 (optional).

D3. Board families of the world module (review section 6, question 4)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Decision:** ``Platform`` covers **one board family: Cortex-M with BASEPRI** (ARMv7-M and ARMv8-M
Mainline). The evidence board is the **NUCLEO-G474RE** (SysTick).

Effects:

- Patch note B20 goes into the next draft: "a board family module", with the family named in the
  evidence scope of each result.
- The nRF54L15 (GRTC clock), ARMv8-M with PACBTI and the RT1060 (PM timers) are out of increment 1.
- The drift finding of the drift tooling note in the workspace notes (upstream removes the ISBs in
  ``arch_irq_lock()``/``arch_irq_unlock()`` and changes the PendSV store) is in this family. Thus it
  is in scope: review ``Platform!IrqUnlock`` and the P2-w window before the next re-pin.

D4. Increment 1 (recommendation 10)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Decision:** increment 1 = the foundation (``WaitQueue``, ``Timeout``, ``Platform``, ``Scheduler``), the
eight objects with a unit app (sem, mutex, condvar, queue, stack, msgq, mem_slab, event), **plus
time slicing** (``TimeSlice``) **and** ``k_timer``. Align with the scope of the committee when it is
published.

Out of increment 1, each with a reason still to write: ``Poll``, ``Work``, ``Mailbox``, ``Userspace``,
``Boot``, ``Usage``, ``Idle``.

Effects (more than the recommended option):

- **The model of time comes forward.** The two-step timeout (abort, then add) that the first cut
  of the review left out (method review, Q6), and the model of time that the peer research
  waits for (P3 of the Kconfig work), are now in increment 1.
- ``Scheduler`` **gets the time slice.** Today the model has no time slice and no ``k_yield()``
  (method review 3.1, ``spec/tla/lib/Scheduler.tla:23-24``). The unit-map decisions already have
  ``TimeSlice`` as a core unit (unit-map decisions, workspace notes, Q2: both values of ``CONFIG_TIMESLICING``,
  ``CONFIG_TIMESLICE_SIZE`` as the initial value of a variable, ``TIMESLICE_PER_THREAD`` later).
  The global time slice applies only to a preemptible thread at or below ``slice_max_prio``
  (``kernel/timeslicing.c:55-57``), so a cooperative thread is never sliced, and ``CoopKeepsCpu`` is
  not affected. The exception is ``CONFIG_TIMESLICE_PER_THREAD``: a per-thread slice applies to
  each thread, also a cooperative one (``kernel/timeslicing.c:49-53``, small-scope argument 3.6, H3).
  That option is "later" (unit-map decisions, Q2), so it is out of increment 1. The slice
  does affect ``TieGoesToLongestReady`` under reading R1 (small-scope argument 3.5, H3): the end of a
  slice moves the current thread behind its peers. That reading needs the slice end as an
  exception.
- ``k_timer`` **moves from roadmap step 4 into increment 1:** a ``Waitable`` instance with an
  extension (findings F1, F2 of the note on the Waitable boundaries, workspace notes) and a unit app for ``timeout.c``.
- **The latency findings come into scope** (roadmap step 7): the slice reset reprograms SysTick
  twice, ``do_swap()`` resets the slice again with ``CONFIG_USE_SWITCH``, and the DLIST insert walks
  the timeouts of the next slice with the timeout lock held. Thus two review questions become
  necessary for increment 1: question 6 (can a hook have a cost effect, and where is the bound)
  and patch note A5 (hooks as an ``obs`` record that carries the cost).
- Open detail: ``KSem`` has ``poll`` configurations today. ``Poll`` as a component is out, but the poll
  signal of ``k_sem`` stays as a part of ``KSem``.

Round 2 (2026-10-30): process
-----------------------------

D5. Independent reviewer (review section 6, question 2)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Decision:** a **colleague** who did not write or review the specs reviews the readings and the
behavior part, once for each object. The user stays the designer. The user names the colleague.

Effects:

- For each object, a review package: the properties with their readings and ``@source``, the
  behavior part, the evidence (counts, traces, tests, CBMC, board), the findings and the limits.
  The first package is k_sem, built from the k_sem consistency record (workspace notes).
- The review result goes into the consistency record of the object (who, when, what was found).
- Roadmap open decision 1 (review procedure) is answered for the specs. Requirement changes are
  still open (they belong to the project that owns the requirements).

D6. Triage of the findings (recommendation 9)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Decision:** for each open finding, the coordinator prepares a proposal (class, evidence, reason).
The user decides in short triage sessions. The register entry records the decision, the date and
the reason.

Backlog at 2026-10-30: P7-a, P7-b, P7-c, P2-w, SW-1, P6-u, F1 to F14, D1 to D3, TS-1, plus the
items that are not in the register yet: the k_sem design observations 1 to 14 (k_sem report,
workspace notes, 4.4), the unit-test findings (workspace notes), and O1, O2 (see D7).

D7. Fields and source kinds of the register (recommendation 9, review question 8)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Decision:** the register gets four more fields:

- **found by**: model (TLC trace), unit test, CBMC, board app, code reading;
- **owner and date**: who decides, and by when;
- **upstream status**: none, issue, pull request, requirement change (roadmap open decision 2);
- **source kind**: requirement, design rule (a rule that the code states for itself, for example
  ``RunRuleHolds``), or traceability claim (for example ``@satisfies ZEP-SRS-2-14`` on
  ``should_preempt()``). Plus the robustness defect without a requirement (patch note B14).

Effect: O1, O2 (the 8-bit ``sched_lock`` count, note on the sched app, workspace notes, section 16) and the
``@satisfies`` tags go through the same triage as the model findings. Patch note B14 goes into the
next draft.

D8. Where the readings live (review section 6, question 5)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Decision:** the readings stay in the specs, and the docs build generates a page that lists, for
each requirement UID, its readings and the properties that use them. The requirement documents
do not change. A change of a requirement is proposed upstream only for a finding that has a class
from D6.

Effects:

- The ``@reading`` tag, held back in the reading of the architecture (section 14), is now necessary.
  It goes into the next draft and into the doc extension, with the generated page.
- The page is the place where an assessor sees what a UID means for the model (review 3.1).

Round 3 (2026-10-31): architecture text (patch note section A)
--------------------------------------------------------------

A3 (the wrong transitivity sentence) is corrected in the next draft (D2). A4 (``SchedLock``, "fine
uses fine") waits for the SMP increment (D2).

D9. Conditions of use (patch note A1, review 3.7 item 1)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Decision:** a condition of use of the client is a **guard only in a client module**, never in a
kernel module. A condition of use of the product is an ``ASSUME`` or a constant. A kernel module
keeps the most general ``Next``, and a detector property shows what happens when the condition is
broken.

Effects: the guard of ``KSem`` on an ISR ``K_FOREVER`` take (peer finding F3 of the contracts
research) moves out of ``KSem``, and ``NoPanic`` or a detector shows the misuse. The restrictions
``MCSetPrioBy`` and ``NoOuterLock`` of ``MCScheduler`` are selectors (D10), named in the evidence scope.

D10. Restrictions of a model configuration (patch note A2, review 7 Q2, small-scope argument, open point 6)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Decision:** two roles in the model-check module:

- **selector**: a ``.cfg`` override of one environment action (``Join <- MCJoin``). It defines a
  smaller but complete specification, so a **liveness property is allowed**. The evidence scope of
  the result names each selector.
- **bound**: a ``CONSTRAINT`` on a counter. **Safety properties only**, because a TLC liveness check
  under a state constraint is not sound.

Effects: ``small*``, ``small_b`` and ``join`` keep their liveness properties (the conflict of
the small-scope argument, open point 6, is solved this way). Each liveness line must have no ``CONSTRAINT``; a
check script can test this.

D11. The reference fake (patch note A6, review 7 Q4)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Decision:** ``sched_ref.c`` **implements the module** ``Scheduler``. A contract test that passes on
the fake and fails on the real ``sched.c`` is a candidate finding.

Effects: RF-2 to RF-6 become corrections of the module or findings. ``NoLostThread`` goes into the
module first. The meaning of the fake changes for all object tests, so their results are read again
once (the 8 sem pilot tests and the 12 sem tests listed for the move to the fake).

D12. Hooks (patch note A5, review 3.6 and 7 Q3)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Decision:** a lower module makes a hook call by **recording it in** ``obs`` of its step (name,
arguments, count, cost). The higher module defines its step as the step of the lower module and,
if ``obs'`` contains the call, its own change in the same step. A call whose result the caller tests
is not a hook but a uses edge.

Effects: the accepted text "a module sees a hook as a constant operator" (sections 2, 5.1, 5.3)
changes in the next draft. ``Scheduler`` gets ``obs`` (today only ``Waitable`` has it), with a view
without ``obs`` for the state count, as ``MCKSem`` does. The first hook is the slice reset for
``TimeSlice`` (D4); the record carries the SysTick reprograms of the latency findings. Review
question 6 (cost effect of a hook) is answered by this form: the cost is in the record, and the
bound is a property of the higher module.

D13. Identifiers of findings (patch note A7, architecture section 10)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Decision:** **keep each existing id** (F1 to F14, P7-a, P2-w, SW-1, P6-u, D1 to D3, TS-1), because
app names, commits and tests use them. Fix the collision: the ``F-1`` of ``obj_core`` becomes ``OC-1``,
and the unit-test findings get unit prefixes (``SEM-n``, ``MUTEX-n``, ...). A new finding gets a short
topic id (as TS-1). The D7 fields carry the source and the method.

Effect: the ``F-`` row of architecture section 10 changes in the next draft. The other prefixes of
section 10 (``RD-``, ``WA-``, ``CU-``, ``O-``) apply to new records.

D14. Vocabulary (recommendation 3)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Decision:** **rename now**: ``@level`` becomes ``@grain`` (values ``coarse``, ``fine``), "level 1/2"
becomes "coarse/fine grain", and the suffix ``_L2`` becomes ``_<Reason>`` (as ``Scheduler_SmpLocks``),
in the specs, the doc extension and its tests, plus a glossary. Old notes keep "level" and "layer
A/B" as history and are not rewritten.

Done 2026-10-31 on ``tkaestner/tla-spec`` (not pushed): ``9f36bec`` (``@level`` to ``@grain``, the README
section "Coarse and fine grain", the doc extension), ``f6a8c67`` (with the user's OK also "layer A/B"
to contract and template module, "descriptive/normative layer" to behavior and property part, the
reading map markers D/N to B/P), ``9b39994`` (``spec/tla/GLOSSARY.rst``). Only comments and text; SANY
parses each changed module; doc extension tests 322 pass. Not done yet: the ``OC-1`` rename of D13
(``tests/kernel/unit/obj_core``, the ``obj_core`` findings in the workspace notes) and the unit prefixes.

Round 4 (2026-10-31): spec forms (block D) and review question 7
----------------------------------------------------------------

D15. "No thread" in ``WaitQueue!Head`` and ``WalkStop`` (patch note apalache item 3)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Decision:** a constant ``NoThread`` of type ``THREAD``. The ``Scheduler`` instance sets it to ``Idle``,
as ``Waitable`` already uses ``Idle`` for "no thread" in the call record.

Effects: two expected values of ``mc/WaitQueueTest`` and one of ``mc/SchedulerTest`` change. The TLC
results do not change otherwise. With D16, ``WaitQueue``, ``Scheduler``, ``Waitable`` and ``KSem`` can
pass the type check of Apalache (Snowcat).

D16. The call record of ``Waitable!Flush`` (patch note apalache item 4)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Decision:** option (a), ``FunAsSeq`` of Apalache's standard module ``Apalache.tla`` (a copy under
Apache-2.0 in ``spec/tla/lib/``). ``WaitQueue!Ordered`` gets a constant range bound. ``Q # <<>>``
becomes ``S!HasWaiters(o)``, and ``{Q[k] : k \in 1..Len(Q)}`` becomes ``S!WQ!W(o)``.

Effect: the same values in TLC; ``KSem`` can be type-checked and checked inductively. Apalache stays
optional (D1).

D17. A module above the contract module (review section 6, question 7; architecture open decision 1)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Decision:** **allowed, created only when needed.** The name follows the rule of the fine modules,
``<Module>_<Aspect>`` (for example ``KSem_Tokens``), at coarse grain with a reduced representation. The
contract module refines it. The property part stays in the contract module.

Effect: architecture section 5.2 changes in the next draft: the root of a refinement tree is the
most abstract module, which is the contract module unless an object's state space needs a module
above it. Today ``MCKSem default`` has 261,836 states, so no such module is needed yet.

D18. ``KeepsArrivalOrder`` in the composition (small-scope argument, open point 1)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Decision:** keep the property as the FIFO rule, check it in the composition with an expected
failure, and register the candidate.

Done 2026-10-31: ``MCScheduler_arrival_same`` with ``Prop_WQ_KeepsArrivalOrder``
(``tkaestner/tla-spec`` ``2a76ff9``), line ``fail:Sched!WQ!KeepsArrivalOrder`` in ``mc/expected.txt``.
Register entry P7-w in the register of findings (workspace notes).

Still open
----------

The name of the colleague (D5).
