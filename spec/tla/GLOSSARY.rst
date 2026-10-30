..
   Copyright (c) 2026 inovex GmbH
   SPDX-License-Identifier: Apache-2.0

Glossary of the formal specification
####################################

The words of the method, one meaning each. The source is the architecture
of the method (draft 3, workspace notes
``claude/kernel-unit/tla/architecture/spec-architecture.md``) and the
decisions on the method review of 2026-10-30
(``claude/kernel-unit/tla/architecture/review-decisions.md``, D1 to D14).
A word that a decision changed names the decision.

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
   The module of a client. A condition of use of the client is a guard
   only here (D9).

Grain and refinement
********************

Grain
   How much code one step of a module is. **Coarse**: one critical section
   is one step. **Fine**: the module splits some boundaries into separate
   steps (lock acquire and release, interrupt entry and exit). Tag
   ``@grain fine`` on an action that is finer than its module (D14).

Representation
   How a module keeps the state of the code, for example a set with stamps
   in place of the dlist of the code. Grain and representation are the two
   axes of refinement.

Refinement tree
   The modules that describe one component, ordered by *refines*. The root
   is the contract module, at coarse grain. Each other module refines one
   parent and states its reason (what it shows that the parent hides).

Fine module
   A module at fine grain in a refinement tree. Name ``<Module>_<Reason>``,
   for example ``Scheduler_SmpLocks`` (D14).

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
   property, and others (architecture section 6). The tag ``@kind`` gives
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

Condition of use
   A rule that the client or the product must obey; it goes into the safety
   manual. In a kernel module it is never a guard: the module keeps the
   most general ``Next``, and a detector shows the misuse (D9).

Detector
   An invariant that names the bad state that only a client or a product
   that breaks a condition of use can reach, for example ``NoPanic``.

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
   A ``.cfg`` override of one environment action, for example
   ``Join <- MCJoin``. It defines a smaller but complete specification, so
   liveness properties are allowed. The evidence scope names it (D10).

Bound
   A ``CONSTRAINT`` on a counter. Safety properties only (D10).

Probe
   An invariant ``Reach_*`` that must fail: its counterexample shows that a
   state or a premise is reachable.

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
   (``trace/``).

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
