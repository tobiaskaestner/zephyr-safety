# Introduction

This document is the specification of the kernel unit tests. Each test
application in `tests/kernel/unit` of the safety repository tests one kernel
source file, for example `kernel/sem.c`. The application builds for the
`unit_testing` board, and the kernel does not start. Each function that the
kernel source file calls outside of the file is a fake. Thus each test states
one design rule of the file, as a fact about its state and about its calls
into the layers below it.

## Structure

The topics of this document have the structure of the kernel sources:

- Each kernel source file has one group, for example `kernel/sem.c`. The
  introduction of this group describes the design of the file as a whole:
  the object, the locks, the interfaces below the file and the Kconfig
  options.
- Below the file group, each public function of the file has one group, in
  the order of the source file. A system call has one group for its
  implementation (`z_impl_`) and its verification function (`z_vrfy_`). For
  example, the group `k_sem_give()` has the tests of `z_impl_k_sem_give()` and
  of `z_vrfy_k_sem_give()`.
- The last group of the file has the tests of the static functions of the
  file. It also has the tests of the data that the file defines, for example
  the object type descriptor of the object core.

Each test is in exactly one group: the group of the function that the action
of the test calls. A test that calls more than one function is in the group
of the function under test. Its `@see` list names the other functions.

If a function has no test, the text of its group says so. These groups show
the gaps of the unit tests.

## Test cases

Each test has these parts:

- The brief description: one design rule, as a fact.
- The details: the setup, the action and the expected result.
- "See also": the functions of the unit that the test calls.
- "Depends on": the Kconfig condition of the test, if the test applies only
  to some configurations. The test is then in an `#ifdef` block, or it calls
  `ztest_test_skip()` without the option.

The scenarios of each `testcase.yaml` build the tests once for each Kconfig
option that changes the code of the unit. `tests/kernel/unit/README.rst`
describes the harness: the fakes, the shadow headers, the models of the layers
below a unit, and the procedure to run the tests.

## Test doubles

Each function below a unit is a test double. A test is correct only if the
double behaves as the real function in the case of the test. Thus the
document shows the doubles. The text is generated from the test sources and
from the harness at each build of the document.

- The page @ref kunit_doubles "Test doubles" has each kind of double, the
  fake groups with the default of each fake, the real copies of the pure
  helpers, the shared models with their assumptions, the reference fake of
  the scheduler contract and the known limits.
- The group of a kernel source file has the section "Test doubles of this
  file": a table of the fakes of the unit, and the doubles that the suite
  configures before each test.
- Each test has the sections "Test doubles" (the fakes that the test
  configures, and how), "Checked calls" (the fakes whose calls the test
  checks) and "Known limits" (the known limits of these doubles).

Today the units `sem` and `mutex` have these sections. The page @ref
kunit_limits "Known limits of the test doubles" lists each test with a
known limit.

## Scope

The document has the units `condvar`, `event`, `mem_slab`, `msgq`, `mutex`,
`obj_core`, `queue`, `sem` and `stack`. The application `sched_ref` is not in
this document. It tests the reference fake of the scheduler, not a kernel
source file.
