..
   Copyright (c) 2026 inovex GmbH
   SPDX-License-Identifier: Apache-2.0

Glossary of the formal specification
####################################

The words of the method, one meaning each. The source is the methodology
(draft 4) and the decisions on the two method reviews (D1 to D37,
2026-10-30 and 2026-10-31). Both are chapters of the Zephyr Kernel Formal Design
Specification (``doc/specification/formal-design``), which includes this
glossary. A word that a decision changed names the decision.

Components and modules
**********************

Component
   The code in scope that shares one state under one lock, and that the
   other code sees as one thing. Example: the scheduler component is
   ``sched.c``, the scheduler part of ``scheduler.c``, ``ksched.h``,
   ``kswap.h``, ``metairq.h`` and ``scheduler.h``.

Unit
   The part of one C file that belongs to one component. A unit test app
   tests one C file.

Uses graph
   One node for each component, and an edge from A to B if code of A calls
   code of B. A is a caller of B. In TLA+, a uses edge is an ``INSTANCE``
   or an ``EXTENDS``.

Cut, higher, lower
   A cut is an edge that the method removes to break the cycles of the uses
   graph (the call stays in the code). After the cuts, A is higher than B
   if a path of edges goes from A to B. This is a partial order, not a
   number.

Hook
   A call on a cut edge: a lower component calls a function that a higher
   component gives, and does not use the result. Example: the scheduler
   calls the slice reset of the time slice at each switch. The lower module
   records the call in ``obs`` of its step; the higher module adds its own
   change in the same step (D12).

Layer
   One of five ordered groups of components: client, kernel API,
   scheduler, foundation, world. An edge of the uses graph never goes to a
   higher layer. "Layer" has no other meaning in the method.

Client
   An application on top of the kernel. It calls the kernel through the
   kernel API.

Contract module
   The module of a component: what the component gives to its callers.
   Example: ``lib/Scheduler.tla`` (it also covers the run queue and the
   scheduler lock today).

Template module
   A module without a component of its own, which the contract modules of
   several components instantiate. Example: ``lib/Waitable.tla`` for the
   kernel objects.

World module
   The contract module of the world layer: ``lib/Platform.tla``, the
   hardware and the arch code. It covers one board family, Cortex-M with
   BASEPRI (D3).

Client module
   The module of a client, in the folder ``clients/``, for example
   ``clients/KSemClient.tla``. Its guards are the assumptions of use of
   the client. A kernel module has no such guard. The model-check module
   instantiates the client module (D9, D27).

Abstract module
   A module above a contract module, at coarse grain, with a reduced
   representation. It is in the folder ``abstract/`` and exists only when
   the state space of a component needs it (D17, D25).

Grain and refinement
********************

Grain
   How much code one step of a module is. **Coarse**: one critical section
   is one step. **Fine**: the module splits some boundaries into separate
   steps (lock acquire and release, interrupt entry and exit). The header
   of each module states its grain with the tag ``@grain``. An action has
   the tag only where its grain differs from the grain of its module
   (D14, D24). A coarse module is for one CPU by construction: on SMP a
   step can span two locks.

Representation
   How a module keeps the state of the code, for example a set with stamps
   in place of the dlist of the code. Grain and representation are the two
   axes of refinement.

Refinement tree
   The modules that describe one component, ordered by *refines*. The root
   is the most abstract module: the contract module, or an abstract module
   above it when the state space of an object needs one (D17, D25). Each other module
   refines one parent and states its reason (what it shows that the parent
   hides). One parent is a choice for each refinement check, not a law: a
   module can also refine a second module that does not refine the first,
   and that check is evidence of its own.

Fine module
   A module at fine grain in a refinement tree. Name ``<Module>_<Reason>``,
   for example ``Scheduler_SmpLocks`` (D14). Its fairness conditions are
   weak fairness on its own exit steps and on ``PendSV``, with its own
   variables as the subscript (D30).

Abstracts
   The relation from an action or an operator to a kernel function. The
   action follows the code, also where the code is surprising. Tag
   ``@c-function``. Tests check it, so its evidence is coverage and
   mutation scores, not a proof.

Inside a module
***************

Behavior part
   The definitions that come from the code (the operators and actions).

Property part
   The definitions that come from the requirements (``@source``). It is in
   the contract module.

Role
   What a definition does: parameter, query, helper, step action,
   sub-action, environment action, behavior invariant, requirement
   property, and others (methodology, section 6). The tag ``@kind`` gives
   the TLA+ form, not the role.

Requirement, reading, expresses
   A requirement is a statement that the kernel must satisfy (ZEP-SRS, the
   API docs, the safety needs). A reading is one interpretation of its
   text. A property expresses one reading of one requirement. Readings stay
   in the specs; the docs show them for each requirement UID (D8).

Assumption
   A fact that TLC does not check. A **world assumption** is a fact of the
   hardware or the arch code (tag ``@assumption``). A **grain assumption**
   is the claim that each step of a coarse module is atomic in the code.

Assumption of use (AoU)
   A rule that the client or the product must obey. It goes into the
   safety manual. Id ``AoU-<n>`` (D26). A rule of the client is a guard in
   a client module, a rule of the product is an ``ASSUME`` or a constant.
   In a kernel module it is never a guard: the module keeps the most
   general ``Next``, and a detector shows the misuse (D9). An assumption
   of use can have a parameter, for example ``H`` in ``AoU-H``, the
   longest time in ticks for which a client holds the interrupt lock
   (D29, D33).

Detector
   An invariant that names the bad state that only a client or a product
   that breaks an assumption of use can reach, for example ``NoPanic``, or
   ``lockedFor[c] <= H`` for ``AoU-H``. A detector is not a hypothesis of
   the claim of the safety manual (D34).

Open form
   The claim of the safety manual: "if the client obeys ``AoU-1`` to
   ``AoU-n``, the kernel guarantees ``G``". TLC checks a safety guarantee
   as ``[][~bad => G]_vars``, with the history variable
   ``bad' = bad \/ ~AoU``. A script generates the predicate ``AoU`` from
   the ``AoU-`` ids (D34).

``obs``
   The record of the last step: the actor, the operation, the object, the
   return value, the woken threads, and the calls of the step into the lock
   and the scheduler contract, in order. Trace checks compare it with the
   calls that the unit-test fakes record. Hook calls go into it (D12).

Model checking
**************

Model-check module and configuration
   ``mc/MC<Module>.tla`` with a ``.cfg`` file for each scenario. A
   configuration is a product (the Kconfig constants), its selectors and
   bounds, and its properties.

Selector
   A constant of the model-check module in a guard of its ``Next`` that
   removes one environment action, for example ``MCJoin``. It defines a
   smaller but complete specification, so liveness properties are
   allowed. A liveness result under a selector is evidence only for a
   client that never does the removed action. The evidence scope names it
   (D10).

Bound
   A ``CONSTRAINT`` on a counter. Safety properties only (D10).

VIEW rule
   A configuration with ``VIEW`` gives a sound result only if no action
   reads the unprimed value of a hidden variable, no state invariant reads
   a hidden variable, and the configuration has no liveness property. A
   configuration with a liveness property has no ``CONSTRAINT``, no
   ``SYMMETRY`` and no ``VIEW`` (D10, D22).

Probe
   An invariant ``Reach_*`` that must fail: its counterexample shows that a
   state or a premise is reachable.

Vacuity probe
   A probe for the premise of one property in one configuration. A pass
   of a property whose premise no reachable state makes true is vacuous,
   and it is not evidence (D1, D21).

Model mutant
   The ``Next`` of a module with one action replaced. It shows that a
   property can fail.

Sensitivity line
   A configuration ``<base>_sens_<axis>`` that changes one bound of a base
   configuration and must give its result (``mc/sensitivity.txt``).

Evidence run
   A TLC run whose results the safety case can cite: a pinned commit, one
   worker for each TLC process, the selftest first, the pinned jar
   (``tools/TOOLS.rst``). The claim is design verification by bounded model
   checking, not a formal proof (D1).

Study, experiment, run, digest
   The records of the formal runs (D19), as for the latency benchmarks. A
   study is one question with hypotheses. An experiment is one tool over
   one list file. A run is one execution of an experiment, with a run id.
   The digest is the SHA-256 of the sealed run. A document cites a run by
   its instance, experiment, run id and digest. The run data is not in the
   repository. The tool ``probatrix`` is planned.

Time
****

Overdue allowance ``L``
   The number of ticks for which a timeout entry can be overdue. The guard
   of the step ``Tick`` is "no entry is overdue by more than ``L`` ticks",
   so the bound can fail. ``L`` is a fact of the client and the world
   (D32).

``MaxAnnounce``
   The number of ticks that one call of ``sys_clock_announce()`` can carry.
   A fact of the product and the driver, separate from ``L`` (D32).

Timing claim
   A bound in ticks, checked as a safety property. One configuration
   without a view checks that time does not stop (D29, D35).

Tests
*****

Fake, shadow header
   Test doubles of the unit test apps: a fake replaces a component that the
   unit calls; a shadow header replaces a kernel header in the build.

Reference fake
   A C implementation of a contract module, step action by step action:
   ``sched_ref.c`` implements ``Scheduler``. A contract test that passes on
   it and fails on the real code is a candidate finding (D11).

Contract test
   A test that calls a kernel function from a fixed state and checks the
   result against the step action that abstracts it.

Trace check
   A check that a recorded run of the real code is a behavior of a module
   (``trace/``). For ``KSem``, its evidence scope is the counts below 2^31.
   CBMC covers the larger values (D23).

Board app
   A client on the board that shows a finding on the real kernel
   (``tests/kernel/findings/`` of the branch ``tkaestner/finding-apps``).

Findings
********

Finding
   A divergence between the code and a requirement, between two
   requirements, or between the code and a design rule that it states for
   itself. All findings are in one register. Each has a class (defect,
   intended but undocumented, accepted deviation, open), found by, owner
   and date, upstream status and source kind (D6, D7).

Identifiers
   Existing ids stay (F1 to F14, P7-a, P2-w, SW-1, P6-u, D1 to D3, TS-1).
   A new finding gets a short topic id. Unit-test findings have a unit
   prefix (``OC-1`` for the old ``F-1`` of ``obj_core``) (D13).

Retired words
*************

"Level 1/2", ``@level``, ``_L2``
   Now coarse and fine grain, ``@grain``, ``<Module>_<Reason>``. "Level"
   stays only in Zephyr's own meanings (init level, interrupt priority
   level, log level) and in the SANY meaning "expression level", written in
   full.

"Layer A/B"
   Now the contract module of the scheduler and the template module.

"Descriptive/normative layer"
   Now the behavior part and the property part.

"Condition of use", ``CU-``
   Now assumption of use, ``AoU-`` (D26). Comments in the specs keep the
   old words until their next change.
