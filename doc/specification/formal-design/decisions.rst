Decisions on the questions of the method review
###############################################

.. note::

   The user decided D1 to D37 on 2026-10-30 and 2026-10-31. Draft 4 of the
   chapter :doc:`/methodology/index` applies them to the text. Section 15
   of the methodology lists the changes of the specs, the tools and the
   tests that are still to do.

Source of rounds 1 to 4: the method review (workspace notes), section 6 and recommendations 3 to
10, and its patch notes (workspace notes). Source of round 5: the second method review and the
reading of it by the user (both workspace notes). This chapter records the decisions of the user
and what each one changes. Draft 4 of the chapter :doc:`/methodology/index` applies the text
changes. A decision of round 5 that changes an earlier decision has a note in that earlier
decision.

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

Changed by D30 (2026-10-31): the fairness rule of a fine module (patch note B22) does not wait
for SMP. The first fine module comes with D4 on one CPU, so draft 4 has the rule. The lock module
(patch note A4) still waits for the SMP increment.

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

Changed by D28, D29 and D32 (2026-10-31):

- ``CONFIG_TIMESLICE_PER_THREAD`` is not forbidden in the product. Finding TS-1 becomes an
  assumption of use (D28).
- Increment 1 claims timing in ticks only (D29).
- The atomic announce step is exact for the thread timeouts of ``KSem``. ``k_timer`` and the time
  slice need a fine announce module (D32).

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

Changed by D36 (2026-10-31): before the triage of a finding, this document states no verdict on
a requirement. The chapter :doc:`counterexample-diagrams` names each counterexample a candidate
finding, with its class.

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

Changed by D26 and D27 (2026-10-31):

- "Condition of use" is now **assumption of use** (AoU), with the ids ``AoU-<n>`` (D26).
- The client module of increment 1 is a separate module in ``clients/``, for example
  ``clients/KSemClient.tla``. The model-check module instantiates it (D27).
- ``NoOuterLock`` is an assumption of use of the client, not a selector: it goes into the safety
  manual. It moves into a client module of the scheduler. ``MCSetPrioBy`` stays a selector.

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

Changed by D22 and D27 (2026-10-31):

- The form of a selector is the form of today: a constant of the model-check module in a guard
  of its ``Next`` (``MCJoin``, ``MCAbort``, ``MCExtra``, ``MCInit``). No ``.cfg`` file overrides an
  action.
- A selector removes an action and the fairness of that action. A liveness result under a
  selector is evidence only for a client that never does the removed action. The record of the
  claim lists the selector as a condition of the claim.
- The full rule: a configuration with a liveness property has no ``CONSTRAINT``, no
  ``SYMMETRY`` and no ``VIEW``. A configuration with ``VIEW`` also obeys the VIEW rule (D22).
  A script checks each ``.cfg`` file (planned).
- A guard that is an assumption of use is a third kind of restriction. It is in the client module
  (D27), not in the model-check module.

D11. The reference fake (patch note A6, review 7 Q4)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Decision:** ``sched_ref.c`` **implements the module** ``Scheduler``. A contract test that passes on
the fake and fails on the real ``sched.c`` is a candidate finding.

Effects: RF-2 to RF-6 become corrections of the module or findings. ``NoLostThread`` goes into the
module first. The meaning of the fake changes for all object tests, so their results are read again
once (the 8 sem pilot tests and the 12 sem tests listed for the move to the fake).

Changed by D36 and D37 (2026-10-31): the text of the decision goes into the header of
``sched_ref.c`` now. The fake must also record the version of ``Scheduler.tla`` that it implements,
and a drift check must compare it. This version pin waits for affirmatrix (D37).

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

Added on 2026-10-31 (second method review, accepted by the user): three rules for ``obs``.

1. **One writer of** ``obs'`` **in each step.** The lowest module that takes part in a step writes
   ``obs'``. Each higher module reads ``obs'`` and adds its own fields with ``EXCEPT``. Today
   ``Waitable!EnvStep`` writes a new record for each scheduler step, so it changes when
   ``Scheduler`` gets ``obs``.
2. **No definition reads the unprimed** ``obs``, except ``vars``, ``Init``, the type invariant,
   the probes and the trace module. This rule is also condition 1 of the VIEW rule (D22).
3. **The fairness subscript has no** ``obs``. A step that changes only ``obs`` must not satisfy a
   fairness condition. ``Scheduler!Fairness`` uses ``WF_schedVars``, and it stays so.

D13. Identifiers of findings (patch note A7, architecture section 10)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Decision:** **keep each existing id** (F1 to F14, P7-a, P2-w, SW-1, P6-u, D1 to D3, TS-1), because
app names, commits and tests use them. Fix the collision: the ``F-1`` of ``obj_core`` becomes ``OC-1``,
and the unit-test findings get unit prefixes (``SEM-n``, ``MUTEX-n``, ...). A new finding gets a short
topic id (as TS-1). The D7 fields carry the source and the method.

Effect: the ``F-`` row of architecture section 10 changes in the next draft. The other prefixes of
section 10 (``RD-``, ``WA-``, ``CU-``, ``O-``) apply to new records.

Changed by D26 and D36 (2026-10-31): draft 4 has the new ``F-`` row. ``AoU-`` replaces ``CU-``
(D26).

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

Changed by D25 (2026-10-31): a module above the contract module is in the folder ``abstract/``.
The name rule ``<Module>_<Aspect>`` does not apply to it.

D18. ``KeepsArrivalOrder`` in the composition (small-scope argument, open point 1)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Decision:** keep the property as the FIFO rule, check it in the composition with an expected
failure, and register the candidate.

Done 2026-10-31: ``MCScheduler_arrival_same`` with ``Prop_WQ_KeepsArrivalOrder``
(``tkaestner/tla-spec`` ``2a76ff9``), line ``fail:Sched!WQ!KeepsArrivalOrder`` in ``mc/expected.txt``.
Register entry P7-w in the register of findings (workspace notes).

Round 5 (2026-10-31): the second method review
----------------------------------------------

Source: the second method review (workspace notes), sections 2 to 6, and the reading of it by the
user. Where the decision of the user differs from the review, the decision applies.

D19. Records of the evidence: studies and experiments (review 2, question 4, sections 3.1 and 3.3)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Decision:** the formal runs are **studies and experiments**, as the runs of the latency
benchmarks are. The tool is **probatrix** (planned). It has two kinds of study: ``tlaplus`` (TLC
model checks and simulation, Apalache, trace checks, TLA+ mutants) and ``cbmc`` (CBMC
configurations and CBMC mutants). The run data does not go into the repository.

Effects:

- The repository holds the designs and the hypotheses. The list files ``mc/expected.txt``,
  ``mc/sensitivity.txt``, ``apalache/expected.txt`` and ``trace/expected.txt`` keep the expected
  verdict of each line.
- The results tree is on the lab host. Later, sealed bundles of runs go to an artifact registry
  (firmhold).
- A document cites a run by its instance, its experiment, its run id and its digest (the SHA-256
  of the sealed run). The form is ``<instance>/<experiment>/<run id> sha256:<digest>``.
- A run is evidence for a commit only if its subject files (for example ``spec/tla/lib``, ``mc``,
  ``objects``) and its tool files are the same as at that commit. Else its role is
  ``historical``.
- The CBMC runs, the mutant runs and the trace checks become experiments with result files in the
  lab results (review 2, section 3.3). The lock-spy tests are lines of the trace experiment.
- The existing runs are imported, not repeated. The sensitivity runs on ``7ac0a35`` (branch
  ``tkaestner/tla-scope``) are history, because their spec files differ from the tip.
- The consistency record of k_sem becomes a page of this document. The page cites the runs. It is
  planned and not written yet. Its numbers then come from the cited runs, not from a note.
- The tool does not exist yet. Its design is a note in the workspace notes (study framework).

D20. The sensitivity set (review 2, section 3.1, recommendation 1)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Decision:** no new run of the sensitivity set now. The useful result of the review is that each
result needs a formal record, and D19 gives it. A pinned run on the tip comes later, as an
experiment of the small-scope study.

Effects:

- ``join_sens_t4`` leaves the set. Reason: the lab run stopped it after 19.5 hours without a
  verdict, at 4,170,347 distinct states. With ``MCJoin``, a fourth thread also adds a fourth join
  queue, so the line grows on two axes. ``join_sens_t2``, ``join_sens_pc`` and
  ``f14_join_sens_t4`` stay. The line leaves ``mc/sensitivity.txt`` with the next change of the
  list.
- ``p7_rules_sens_t4_sym`` runs once later, with ``heap=6g``. The estimate is 9M to 18M states.
- Two corrections of the record: the symmetry group of ``p2_lock_sens_t4_sym`` has the order 6,
  not 12 (``MCObjs = {o1}``). Commit ``c8938bd`` changed 7 sensitivity configurations, not 10
  (the ``MCWaitQueue`` lines).

D21. Vacuous passes (review 2, section 3.6; D1)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Decision:** one **vacuity probe** for each vacuous pair (configuration, premise). The probes are
an experiment of the small-scope study.

Effects:

- A vacuity probe is a probe ``Reach_*`` for the premise of one property in one configuration. It
  must fail.
- Until the probes exist, the evidence scope of each ``pass`` line lists the properties whose
  premise the configuration cannot reach.
- The known pairs (small-scope argument, observation 2):

  - ``BlockedLosesCpu`` in ``gap_coop``
  - ``NoSwitchWhileLocked`` and ``PendingIsUnlocked`` with ``MCOuterLock = FALSE``
  - ``NoUndefined`` with ``MCInit = FALSE``
  - ``NoPanic`` with ``MCIsrPends = FALSE``
  - ``NoPendSVWithSwitch`` in each ``_pendsv`` configuration

D22. The VIEW rule (review 2, section 3.2; D10)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Decision:** the rule for ``VIEW`` goes into D10, into the tool note and into a check script.
Under a ``VIEW``, TLC examines the successors of the first state of each view class only, and it
checks a state invariant only on a new state. So a configuration with ``VIEW`` gives a sound
result only if all three conditions are true:

1. No action reads the unprimed value of a variable that the view hides.
2. No state invariant reads a variable that the view hides.
3. The configuration has no liveness property.

Effects:

- Ten configurations of ``KSem`` use ``VIEW ViewNoObs`` or ``VIEW MViewNoObs``. Eight of them
  check action properties. Conditions 1 and 3 are true. Condition 2 is false: ``KSem!TypeOK``
  reads ``obs``. The clause is a type check, so the risk is low. The spec change is still to do.
- The tool note (``spec/tla/tools/TOOLS.rst``) states the rule. The old text said that no
  configuration uses ``VIEW``.
- Planned: a script that checks the three conditions on each ``.cfg`` file with ``VIEW``, and the
  rule of D10 on each ``.cfg`` file with ``VIEW``, ``SYMMETRY`` or ``CONSTRAINT``. Two known-answer
  models in ``selftest/``: one in which an action property fails on a step that only the view
  hides, and one in which TLC does not see the violation of a state invariant that reads the
  hidden variable.

D23. The evidence scope of the trace checks (review 2, section 3.4)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Decision:** the trace checks are evidence for counts below 2^31 only. CBMC covers the larger
values.

Effects:

- ``trace/expected.txt`` has 152 lines: 119 ``accept``, 1 ``fail:Inv_TokenConservation``, 12
  ``reject``, 17 ``empty`` and 3 ``out-of-range``. TLC does not run for ``empty`` and
  ``out-of-range``. A summary counts these 20 lines as "not checked", not as "as expected".
- The ``out-of-range`` traces have counts above 2^31 - 1, the largest integer of TLC
  (``KSemTrace!TUMax``).
- ``RefinesKSem`` is true by construction, because each step of the trace module conjoins
  ``K!Next``. It is not evidence of *refines*. The evidence of a trace check is ``Accepted``, with
  ``HiddenMax = 3``.

D24. The place of the tag ``@grain`` (review 2, section 1 item 3, section 3.5)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Decision:** the header of each module states its grain (``@grain coarse`` or ``@grain fine``).
An action has the tag only where its grain differs from the grain of its module.

Effect: today no module has the tag. The tag goes into the module headers with the next change of
the specs. The methodology (5.2), the glossary and the design note ``spec/tla/README.rst`` state the
rule.

D25. The folder of an abstract module (review 2, D17)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Decision:** a module above a contract module is in the new folder ``abstract/`` of
``spec/tla``. The folder shows the direction. No name pattern such as ``KSemAbs_`` is necessary.

Effect: the pattern ``<Module>_<Reason>`` is for the fine modules only. A reader of a name
``KSem_X`` then knows that ``X`` is finer than ``KSem``.

D26. Assumption of use (review 2, D9 and D10)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Decision:** the term "condition of use" becomes **assumption of use** (AoU, as in ISO 26262).
The ids are ``AoU-<n>``. They replace the ``CU-`` ids of section 10 of the methodology, and the
role "client restriction" with ``CU-`` ids that the review proposed.

Effect: the methodology, the glossary and the design note use the new term. The comments of the
specs, the configurations and the tests keep the old term until their next change.

D27. The client modules of increment 1 (review 2, question 2, recommendation 5; D9)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Decision:** option (b). A client module is a separate module in the folder ``clients/`` with the
assumptions of use as guards, for example ``clients/KSemClient.tla``. The model-check module
instantiates it.

Effects:

- For ``KSem``: the guards ``IsrWaits`` and ``ReInit`` leave ``objects/KSem.tla`` and go into
  ``clients/KSemClient.tla``. ``KSem`` keeps the most general ``Next``. Its detectors show the
  misuse.
- For ``MCScheduler``: ``NoOuterLock`` goes into a client module of the scheduler.
- The model-check module sets constants, selectors and bounds, adds probes, and instantiates the
  client module. It does not hold an assumption of use.
- The evidence scope names the assumptions of use of the client module apart from the selectors.
- The specs do not have the client modules yet.

D28. ``CONFIG_TIMESLICE_PER_THREAD`` and finding TS-1 (review 2, question 3; D4)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Decision:** the option is not forbidden in the product. TS-1 becomes an assumption of use.

**Proposed wording** (option b, waits for the confirmation of the user): "The application does not
give a per-thread time slice to a thread that runs at a cooperative priority or calls
``k_sched_lock()``."

The other option (a) was: the application does not use a cooperative priority or
``k_sched_lock()`` as a protection against the end of a time slice.

Reason: with ``CONFIG_TIMESLICE_PER_THREAD=y``, a per-thread slice applies to each thread, also to
a cooperative thread (``kernel/timeslicing.c:49-53`` before ``55-57``). The finding is confirmed by
a unit app on the real ``timeslicing.c`` and on the NUCLEO-G474RE.

D29. The unit of time and the bound ``H`` (review 2, questions 1 and 5)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Decision:** increment 1 states each timing claim in ticks only. ``Platform`` gets no clock in
seconds. ``H``, the longest time for which a client holds the interrupt lock, is a parameter of an
assumption of use (D33). The model gives it in ticks. The product states its value. The latency
study can give a value later.

D30. Fairness of a fine module (review 2, section 6.1, recommendation 4; patch note B22; D2)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Decision:** the fairness rule goes into draft 4, not into the SMP increment.

The rule:

- The fairness conditions of a fine module are weak fairness on its own exit steps and on
  ``PendSV``. The fine module writes them with its own variables as the subscript, never through
  ``INSTANCE ... WITH``.
- TLC checks the safety part ``Refines`` through the refinement mapping.
- The liveness part ``RefinesFair`` rests on a written argument: weak fairness on the last fine
  step of each split gives the weak fairness of the coarse step, if the fine steps of one split run
  to the end. The liveness configuration of the fine module checks this premise.

The assumptions on one CPU (Cortex-M with BASEPRI, D3), each with a tag ``@assumption`` in
``Platform``:

1. The NVIC takes a pending and enabled exception with a priority above BASEPRI in bounded time.
   Tail chaining changes no order. This gives weak fairness on each step "interrupt entry".
2. Each ISR returns. This is an assumption of use for the ISRs of the client. It gives weak
   fairness on each step "interrupt exit".
3. The interrupt load is not continuous: between two steps of a thread, only a finite number of
   interrupt entries occur. This is an assumption of use of the product.
4. The nesting depth is bounded by the number of priority levels in use. ``MaxIrqNest`` is then a
   constant of the product, not a bound of the model.
5. PendSV runs when no other exception is active. ``Platform`` has this assumption already (PendSV
   has the lowest exception priority).
6. SysTick has the highest priority of the ISRs that call the kernel (D32). So no ISR that calls
   the kernel runs inside the announce loop, and the loop runs to its end.

With 1 to 3 and 5, ``WF(PendSV)`` follows.

D31. No prophecy variable (review 2, section 6.2)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Decision:** the rule of draft 4: a coarse module makes no choice before the step in which the
code makes it. Then a refinement mapping needs no prophecy variable.

Effects:

- Today no refinement mapping of the library needs an auxiliary variable (review 2, section 6.2:
  ``readySince``, ``pendsv``, the slice reset, the announce window, ``Timeout!InsertAny``,
  ``QueueReady``).
- History variables are allowed, because they keep the liveness of the spec. The planned history
  variables are ``bad`` of the open form (D34) and ``lockedFor`` of the detector of ``H`` (D33).

D32. The model of time and the announce loop (review 2, sections 3.9 and 6.3; D4)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Decision:** the model of time has the form of the time note (workspace notes): integer time in
ticks, countdown timers in the state, a step ``Tick`` in ``Next``, no variable ``now`` in the checked
state, and time bounds as safety properties. Two changes:

1. **Overdue allowance** ``L``: the guard of ``Tick`` is "no entry is overdue by more than ``L``
   ticks". Each entry has a counter of its overdue ticks, because the countdown stops at 0. So the
   bound "no entry is overdue by more than ``L``" is a property that can fail.
2. ``MaxAnnounce`` and ``L`` are two constants. ``MaxAnnounce`` is the number of ticks that one
   announce can carry, a fact of the product and the driver. ``L`` is the latency allowance, a fact
   of the client and the world.

The atomic announce step for the thread timeouts of ``KSem`` on one CPU is exact. This is a world
assumption with a code location (Zephyr ``770fdef1567``):

- The SysTick driver sets the priority of SysTick to ``_IRQ_PRIO_OFFSET``
  (``drivers/timer/cortex_m_systick.c:542, 566``).
- ``IRQ_CONNECT()`` adds the same offset to the priority of each ISR
  (``arch/arm/core/cortex_m/irq_manage.c:122``). An equal priority does not preempt.
- Only a zero-latency interrupt has a higher priority, and it must not call the kernel.
- So no ISR that calls the kernel runs in the window where ``sys_clock_announce_locked()`` releases
  ``timeout_lock`` around ``handler(t)`` (``kernel/timeout.c:394-396``).
- The check ``z_timeout_inflight_superseded()`` (``kernel/sched.c:507``) then never finds a
  superseded timeout on one CPU.

A small assumption of use remains: the application does not change the NVIC priorities other
than through ``IRQ_CONNECT()`` and ``irq_priority_set()``.

This corrects the review (sections 3.9 and 6.3). The review supposed that an ISR with a higher
priority than SysTick can call the kernel in the window. On this board family it cannot.

Effects:

- ``k_timer`` and the time slice still need a fine announce module, for another reason. The expiry
  handler runs inside the announce loop with the lock released. It reads and changes the timeout
  state between two pops (``kernel/timeout.c:389-398``). For example, a ``k_timer`` expiry function
  that calls ``k_timer_start()`` or ``k_sem_give()`` acts inside the loop.
- ``z_time_slice()`` runs after the release of ``timeout_lock`` (``kernel/timeout.c:406-410``) and
  takes the scheduler lock itself (``kernel/timeslicing.c:149``). It is a separate coarse step, not
  the last part of the announce step.
- The measurement of the state-space factor of one timed entry on ``MCKSem default`` is the first
  experiment of a design study of the model of time. It runs when the work on time starts.

D33. The assumption of use ``AoU-H`` and its detector (review 2, section 6.4)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Decision:** "the client releases the interrupt lock within ``H`` ticks" is a named assumption of
use, ``AoU-H``, with a detector.

Effects:

- A history variable ``lockedFor[c]`` for each CPU counts the ticks while ``irqNest[c] > 0``.
  ``IrqUnlock`` sets it to 0.
- The detector is ``lockedFor[c] <= H``. A configuration with a client that holds the lock for
  ``H + 1`` ticks must fail it.
- With the overdue allowance ``L`` of D32, ``Tick`` stays enabled under the lock, so the behavior
  of a client that holds the lock too long is visible.
- The latency allowance ``L`` of a kernel claim is at most ``H`` plus the masked sections of the
  kernel. The second part is a measured value of the benchmarks, a world assumption.

D34. The open form of the claim of the safety manual (review 2, section 6.5)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Decision:** the claim of the safety manual is "if the client obeys ``AoU-1`` to ``AoU-n``, the
kernel guarantees ``G``".

- For each safety guarantee ``G``, TLC checks the action property ``[][~bad => G]_vars``. ``bad``
  is a history variable: ``bad' = bad \/ ~AoU``.
- A script generates the predicate ``AoU`` from the ``AoU-`` tags. Thus a missing assumption of
  use cannot be silent.
- A liveness guarantee has no open form. Its claim is stated under the selectors and the
  assumptions of use of the client module, and the evidence scope names them.
- The record keeps the detectors apart from the hypotheses. A detector configuration shows what
  occurs without an assumption of use. It is not a hypothesis of the composition theorem.

D35. Timing claims (review 2, section 6.6)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Decision:** each timing claim of increment 1 is a safety bound. One configuration without a view
checks that time does not stop (non-Zeno, ``SF(Tick)``), as a check of the spec, not as a timing
claim.

Effects:

- No liveness property is checked under a view that moves time. TLC does not check the symmetry
  conditions that such a check needs.
- ``TimedWaitEnds`` and ``SelectionHappens`` stay design exploration.

D36. The text of this document (review 2, sections 3.5 and 3.8)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Decision:** draft 4 of the methodology applies the decisions to the text directly, without the
marker "(changed by Dn)". Also:

- D6: the chapter :doc:`counterexample-diagrams` writes "candidate finding" and the class. It does
  not write that a requirement "is violated".
- The chapter :doc:`formal-model` shows the object modules (``spec/tla/objects``, today ``KSem``).
- D11: the header of ``sched_ref.c`` states the decision now. The version pin waits (D37).
- D13: section 10 of draft 4 has the new ``F-`` row. The rename ``OC-1`` and the unit prefixes in
  the tests are still to do.
- D15: a comment next to the ``WITH`` clause of the ``Scheduler`` instance gives the reason why
  ``Idle`` can be ``NoThread``: ``Idle`` never waits (``ASSUME Idle \notin Threads \cup Isrs``).
  The spec change is still to do.

D37. Drift detection (review 2, recommendation 11 and section 3.7)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Decision:** drift detection is the work of affirmatrix, a separate tool of the user (hashes
anchored to the content, drift detection, affirmations). Each further change of the drift tooling
is first coordinated with it.

Effect: these items wait: the defects of the drift tooling that the review names (the record
``c-functions.json`` without the ``KSem`` tags, the tag scan of ``build/``, the body of
``sys_clock_announce_locked()``, the locations of ``@assumption``), and the version pin of
``sched_ref.c`` (D11).

Still open
----------

- The name of the colleague (D5).
- The wording of the assumption of use for TS-1 (D28). Option (b) is proposed.
