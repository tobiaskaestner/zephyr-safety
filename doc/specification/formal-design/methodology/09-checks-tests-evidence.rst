9. Checks, tests and the evidence
=================================

9.1 Model checking
------------------

- **Expected result** of a configuration: a line of ``mc/expected.txt``. This file is the only
  record of the expected results. A script checks the ``@expected`` comments in the model-check
  modules against it, or the comments are deleted.
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

9.2 Tests on the real code
--------------------------

- **Test double**: C code that replaces real code in a unit test app.
- **Fake**: a test double with state, which replaces a component that the unit calls. It
  implements a query or a step action of a contract module, and names it. A fake of the world
  module contains the world assumptions that it replaces. So a test with this fake cannot find a
  false world assumption.
- **Shadow header**: a test double that replaces a kernel header in the build.
- **Reference fake**: a C implementation of a contract module, step action by step action. Today
  only ``sched_ref.c`` exists.
- **Contract test**: a test that calls a kernel function from a fixed state, and checks the result
  against the step action that abstracts it. Where a reference fake exists, the same test also
  runs against it.
- **Trace module**: a module that accepts a recorded run of the real code. The record format is a
  JSON schema next to it, not a module. A **trace check** shows that a recorded run is a behavior
  of a leaf.
- **Board app**: a client on the board that shows a finding on the real kernel.
- **Code mutant**: a changed copy of a C file. It shows that a test can fail.

Only four kinds of module define a next-state relation: the modules of the refinement trees, the
example test modules, the mutant modules and the trace modules.

9.3 The guiding principle, in the defined words
-----------------------------------------------

- Each requirement becomes one or more requirement properties. A property expresses one reading.

- Each kernel function in scope becomes queries and step actions that abstract it, or it is listed
  with its reason.

- TLC checks that the ``Spec`` of each contract module satisfies its properties. A counterexample is
  a candidate finding.

- **Evidence scope** of a result: the conditions under which it is evidence. For a TLC run, these
  are the bounds of its configuration: the number of threads and CPUs, the product, the model
  size. For a test, these are the product and the board.

The evidence for the code connects three relations. Each relation has its own evidence:

.. list-table::
   :header-rows: 1

   * - Relation
     - From, to
     - Evidence
   * - abstracts
     - each module of a refinement tree, to the code
     - trace checks against a leaf (direct), contract tests against the contract module (indirect, through the fakes). No tool proves it.
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
       conditions of use (premises or guards, they go into the safety manual), detectors
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
