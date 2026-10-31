9. Checks, tests and the evidence
=================================

9.1 Model checking
------------------

- **Expected result** of a configuration: a line of ``mc/expected.txt``. This file is the only
  record of the expected results. A script checks the ``@expected`` comments in the model-check
  modules against it, or the comments are deleted. The expected result is the hypothesis of the
  line. The result of a run is in the records of section 9.4, not in the repository.
- **Selector**: a constant of the model-check module in a guard of its ``Next`` that removes one
  environment action, for example ``MCJoin`` or ``MCAbort`` (D10). It defines a smaller but
  complete specification, so a liveness property is allowed. A selector also removes the fairness
  of the removed action. So a liveness result under a selector is evidence only for a client that
  never does that action. The evidence scope names each selector.
- **Bound**: a ``CONSTRAINT`` on a counter. Safety properties only, because TLC does not check a
  liveness property correctly under a state constraint.
- Rule for liveness (D10): a configuration with a liveness property has no ``CONSTRAINT``, no
  ``SYMMETRY`` and no ``VIEW``.
- **VIEW rule** (D22): under a ``VIEW``, TLC examines the successors of the first state of each
  view class only, and it checks a state invariant only on a new state. A configuration with
  ``VIEW`` gives a sound result only if all three conditions are true:

  1. No action reads the unprimed value of a variable that the view hides.
  2. No state invariant reads a variable that the view hides.
  3. The configuration has no liveness property.

  A script checks the conditions on each ``.cfg`` file, and two known-answer models of the
  selftest show the limit (both planned). Today ten configurations of ``KSem`` use a view without
  ``obs``. ``KSem!TypeOK`` reads ``obs``, so condition 2 is false for them (a type check, low risk).
- **Example test module** (``mc/<Module>Test.tla``): fixed values of the operators of a module on
  fixed states, checked by TLC. It is not a model-check module. Its ``Next`` is trivial
  (``UNCHANGED unused``), because it checks values, not behaviors.
- **Refinement check** (``mc/MC<Child>Refinement.tla``): a TLC run that shows that a module refines
  its parent. The name comes from the more concrete module, for example
  ``MCScheduler_SmpLocksRefinement.tla``. A failed refinement check is also a candidate finding: the
  parent hides a behavior of the code.
- **Model mutant**: the ``Next`` of a module with one action replaced. It shows that a property can
  fail. Model mutants are not in the code, so they are not in the module.
- **Mutant module** (``mc/MC<Module>Mutants.tla``): the module that holds the model mutants of a
  module, each as its own next-state relation.
- **Probe**: an invariant ``Reach_*`` in a model-check module that must fail. Its counterexample
  shows that a premise or a state is reachable. A probe does not come from a requirement. It is a
  check of the specification, as a model mutant is.
- **Vacuity probe** (D21): a probe for the premise of one property in one configuration. A ``pass``
  of a property whose premise is false in each reachable state is vacuous, and a vacuous pass is
  not evidence (D1). Each vacuous pair (configuration, premise) gets one vacuity probe, as an
  experiment of the small-scope study. Until the probes exist, the evidence scope of each ``pass``
  line lists the properties whose premise the configuration cannot reach.

9.2 Tests on the real code
--------------------------

- **Test double**: C code that replaces real code in a unit test app.
- **Fake**: a test double with state, which replaces a component that the unit calls. It
  implements a query or a step action of a contract module, and names it. A fake of the world
  module contains the world assumptions that it replaces. So a test with this fake cannot find a
  false world assumption.
- **Shadow header**: a test double that replaces a kernel header in the build.
- **Reference fake**: a C implementation of a contract module, step action by step action. Today
  only ``sched_ref.c`` exists. It implements the module ``Scheduler`` (D11). A contract test that
  passes on the fake and fails on the real code is a candidate finding. The fake records the
  version of the module that it implements, and a drift check compares it (planned, D37).
- **Contract test**: a test that calls a kernel function from a fixed state, and checks the result
  against the step action that abstracts it. Where a reference fake exists, the same test also
  runs against it.
- **Trace module**: a module that accepts a recorded run of the real code. The record format is a
  JSON schema next to it, not a module. A **trace check** shows that a recorded run is a behavior
  of a leaf. Its evidence is the property ``Accepted``. A refinement property that each step of the
  trace module conjoins is true by construction and is not evidence of *refines*. The evidence
  scope of the trace checks of ``KSem`` is the counts below 2^31, the largest integer of TLC. CBMC
  covers the larger values (D23). A trace that TLC does not check (``empty``, ``out-of-range``)
  does not count as checked.
- **Board app**: a client on the board that shows a finding on the real kernel.
- **Code mutant**: a changed copy of a C file. It shows that a test can fail.

These kinds of module define a next-state relation: the modules of the refinement trees, the
client modules, the model-check modules (with their selectors), the example test modules, the
mutant modules and the trace modules.

9.3 The guiding principle, in the defined words
-----------------------------------------------

- Each requirement becomes one or more requirement properties. A property expresses one reading.

- Each kernel function in scope becomes queries and step actions that abstract it, or it is listed
  with its reason.

- TLC checks that the ``Spec`` of each contract module satisfies its properties. A counterexample is
  a candidate finding.

- **Evidence scope** of a result: the conditions under which it is evidence. For a TLC run, these
  are the bounds of its configuration (the number of threads and CPUs, the product, the model
  size), its selectors, the assumptions of use of its client module, the board family of the world
  module, and the vacuous properties. For a test, these are the product and the board.

The evidence for the code connects three relations. Each relation has its own evidence:

.. list-table::
   :header-rows: 1

   * - Relation
     - From, to
     - Evidence
   * - abstracts
     - each module of a refinement tree, to the code
     - trace checks against a leaf (direct), contract tests against the contract module (indirect, through the fakes). Tests check it, so its evidence is the coverage of the step actions and the mutation scores of these checks. No tool proves it.
   * - refines
     - a module, to its parent
     - refinement check (TLC)
   * - satisfies
     - the contract module, to its properties
     - TLC runs, within their evidence scope

A refinement tree without a fine module has a gap. The coarse grain is then a grain assumption:
each critical section is atomic. Only a test that the lock is held during each change of state
checks it. A fake of the spinlock can record this.

The evidence for a component depends on the evidence for each component that it uses. For
example, the properties of ``KSem`` hold for the code only if the scheduler code follows the contract
module of the scheduler. Board apps do not test the abstraction.
They show that a finding occurs on the hardware.

Figure 3, one component (the scheduler as example):

::

     requirements (ZEP-SRS, kernel API documentation, safety needs)
           |
           | expresses (one reading)
           v
     PROPERTY PART of the component (in the contract module)
       requirement properties
       assumptions of use (premises, ASSUME, guards of client modules: they go into the safety manual), detectors
           ^
           | satisfies? (TLC, within the evidence scope)
           |    -- counterexample --> candidate finding --triage--> finding --> board app
           |
     BEHAVIOR PART: the refinement tree, more abstract on the left, more concrete on the right
           |
       Scheduler           <--refines--   Scheduler_SmpLocks  --abstracts-->  C code:
       root, contract                     leaf, fine (planned)                sched.c,
       module, coarse      <--refines--   Scheduler_IrqNesting                scheduler.c (part),
       + behavior                         leaf, fine (planned)                ksched.h, kswap.h, ...
         invariants                       + behavior invariants
           |                                                                      ^
           +------------------------------ abstracts -----------------------------+
                                           contract tests (indirect)

                           refinement checks (TLC)             trace checks (direct)

     world assumptions (world module Platform): what all modules of the tree take from outside the
     scope. Grain assumption of each coarse module: checked only by a test that the lock is held.

9.4 The records of the evidence
-------------------------------

The formal runs are **studies** and **experiments**, as the runs of the latency benchmarks are
(D19). The tool is ``probatrix`` (planned). It has two kinds of study: ``tlaplus`` and ``cbmc``.

- **Study**: one question about the spec or the code, for example "do the properties of
  ``Scheduler`` hold in the small scope". It has hypotheses.
- **Experiment**: one tool over one list file, for example TLC over ``mc/expected.txt``, the trace
  check over ``trace/expected.txt``, or a CBMC batch. Each line of the list is a point with its
  expected verdict.
- **Run**: one execution of an experiment, with a run id. A second run of the same experiment is
  a reproduction.
- **Digest**: the SHA-256 of a sealed run. A document cites a run by its instance, its experiment,
  its run id and its digest.

Rules:

- The repository holds the designs and the hypotheses, not the run data. The results tree is on
  the lab host. Later, sealed bundles go to an artifact registry (firmhold).
- A run is evidence for a commit only if its subject files and its tool files are the same as at
  that commit. Else its role is ``historical``.
- The runs of TLC, Apalache, the trace checks, the mutants, the lock-spy tests and CBMC are all
  experiments of this kind (review 2, section 3.3).
- The consistency record of an object becomes a page of this document that cites its runs. The
  first one is k_sem (planned).

9.5 The claim of the safety manual
----------------------------------

The claim is in **open form** (D34): "if the client obeys ``AoU-1`` to ``AoU-n``, the kernel
guarantees ``G``".

- For each safety guarantee ``G``, TLC checks the action property ``[][~bad => G]_vars``. ``bad``
  is a history variable: ``bad' = bad \/ ~AoU``. A script generates the predicate ``AoU`` from the
  ``AoU-`` ids, so a missing assumption of use cannot be silent.
- A liveness guarantee has no open form. Its claim is stated under the selectors and the
  assumptions of use of the client module, and the evidence scope names them.
- The record keeps the detectors apart from the hypotheses. A detector configuration shows what
  occurs without an assumption of use. It is not a hypothesis of the claim.
- Each timing claim is a safety bound (D35). One configuration without a view checks that time
  does not stop (non-Zeno, ``SF(Tick)``). This is a check of the spec, not a timing claim. No
  liveness property is checked under a view that moves time.
