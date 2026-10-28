.. Copyright (c) 2026 inovex GmbH
.. SPDX-License-Identifier: Apache-2.0

Kernel unit tests
#################

Each test application in this directory tests one kernel source file, for
example ``kernel/sem.c``. The application builds for the ``unit_testing``
board. The kernel does not start.

The test source includes the kernel source file (``#include
<kernel/sem.c>``). Thus a test can call the static functions of the unit
and read its static data.

Every function that the unit calls outside of its file is an FFF fake. A
test sets the return values of the fakes and examines their calls. Thus the
tests show the calls of the unit into the scheduler and into the
architecture layer.

The tests are a design specification of the unit. Each test states one
design rule (see `Write a test`_).

The application ``sched_ref`` is an exception: it includes no kernel source
file. It is the self-test of the reference fake of the scheduler (see
`Reference fake of the scheduler`_).

Test applications
*****************

.. list-table::
   :header-rows: 1

   * - Directory
     - Unit
     - Scenarios
   * - ``sem``
     - ``kernel/sem.c``
     - 7
   * - ``queue``
     - ``kernel/queue.c``
     - 7
   * - ``msgq``
     - ``kernel/msg_q.c``
     - 9
   * - ``stack``
     - ``kernel/stack.c``
     - 7
   * - ``mem_slab``
     - ``kernel/mem_slab.c``
     - 9
   * - ``event``
     - ``kernel/events.c``
     - 6
   * - ``condvar``
     - ``kernel/condvar.c``
     - 4
   * - ``mutex``
     - ``kernel/mutex.c``
     - 13
   * - ``obj_core``
     - ``kernel/obj_core.c``
     - 5
   * - ``sched_ref``
     - the fake group ``sched_ref`` (no kernel source file)
     - 2

`Configurations`_ gives the configuration options of each unit.

Run the tests
*************

Run the tests from the workspace root:

.. code-block:: console

   west twister -T safety/tests/kernel/unit -p unit_testing

To build and run one configuration:

.. code-block:: console

   west build -b unit_testing -d build-unit safety/tests/kernel/unit/sem
   build-unit/testbinary

This build has no scenario name, so the test inventory check is off (see
`Test inventory`_). To give the scenario name, add
``-- -DKERNEL_UNIT_SCENARIO=kernel.unit.sem`` to the ``west build``
command. For a scenario with ``extra_configs``, also give its Kconfig
options.

Guards against lost tests
*************************

A change outside of a test can remove the test without an error. Then the
run passes with fewer tests, and the tests lose part of the specification
without a signal. Finding F1 of the drift experiment is an example. An
upstream revert removed the macro ``Z_MUTEX_PI_ENABLED``. The 14 ``#if
Z_MUTEX_PI_ENABLED`` blocks of ``mutex/src/test_mutex.c`` then had the
value 0, and 45 tests of each configuration were not in the binary.

The harness has two guards. Both are active in each twister run.

Undefined macros in ``#if``
===========================

``cmake/kernel_unit.cmake`` compiles the test binary with ``-Wundef
-Werror=undef``. If a ``#if`` uses an undefined macro, the build stops.
The guard applies to the test sources, the fakes, the shadow headers, the
included kernel source file and the public headers.

The guard does not find these changes:

- ``#ifdef CONFIG_X``, ``#if defined(CONFIG_X)`` and ``IS_ENABLED(CONFIG_X)``
  with a renamed or removed symbol. For these, the preprocessor gives no
  diagnostic by design.
- A deleted test, or a changed suite predicate.

Two upstream sources need a special case:

- ``subsys/testsuite/ztest/src/ztest.c`` has ``#if CONFIG_ZTEST_SHUFFLE``,
  and the option is a bool. Only ``ztest.c`` compiles with
  ``-Wno-undef``.
- ``zephyr/kernel.h`` has ``#if (K_HEAP_MEM_POOL_SIZE > 0)``. In a real
  build, ``kernel/CMakeLists.txt`` defines this macro on the command line.
  The unittest build does not read this file. Thus ``kernel_unit.cmake``
  defines the macro. With ``CONFIG_KERNEL_MEM_POOL``, the value is
  ``CONFIG_HEAP_MEM_POOL_SIZE``, else 0. The value does not include the
  requests of the ``CONFIG_HEAP_MEM_POOL_ADD_SIZE_*`` options.

Test inventory
==============

Each application has one expected set of tests for each twister
scenario, in ``<application>/inventory/<scenario>.txt``. Each line is one
test and its state:

.. code-block:: text

   run mutex_unit.test_init_makes_mutex_free
   skip mutex_unit.test_pi_boost_limited_by_ceiling

The state ``skip`` means that each run of the test was a skip, or that
the test did not run (for example, the predicate of its suite was false).
All other tests have the state ``run``. A test that failed also has the
state ``run``, because ztest reports the failure itself. A test with
``ZTEST_EXPECT_FAIL()`` or ``ZTEST_EXPECT_SKIP()`` passes, so its state is
``run``. The lines are sorted.

``common/src/test_inventory.c`` replaces the weak ``test_main()`` of
ztest. After all suites ran, it compares the tests of the binary with the
expected set of the scenario. These differences make the run fail:

- ``MISSING``: a test of the expected set is not in the binary.
- ``EXTRA``: a test of the binary is not in the expected set.
- ``CHANGED``: the state is different, for example ``run`` in the expected
  set and ``skip`` in the binary. A renamed symbol in
  ``IS_ENABLED(CONFIG_X)`` gives this difference.

For each difference, the binary prints one line with the test. Then it
prints ``PROJECT EXECUTION FAILED`` and exits with status 1. Twister
reports the configuration as failed (``rc=1``), and the lines are in its
``handler.log``. The binary always writes the tests of the run to
``test_inventory.actual.txt`` in its build directory.

Twister gives the scenario name to CMake in ``TC_NAME``.
``kernel_unit.cmake`` runs ``common/test_inventory.py gen`` when the
application is configured. The script writes the expected set as C data
into the build directory. If the file has an incorrect line, the
configuration stops. A change of the file configures the application
again.

These cases are not differences:

- If the application has no ``inventory`` directory, the check is off.
  The configuration and the binary print a warning, and the run passes.
  This is the state of a new application until it has its expected sets.
- If the build has no scenario name, the check is off.

The check does not find a removed scenario: no build of the scenario
occurs. The ``update`` command (see below) prints a warning for its file.

If the application has an ``inventory`` directory, but no file for the
scenario, the run fails. Each test is then ``EXTRA``.

Regenerate the expected sets
----------------------------

Regenerate the expected sets only from a run in which all tests pass.

#. Run twister:

   .. code-block:: console

      west twister -T safety/tests/kernel/unit -p unit_testing

#. Copy the actual sets of the run to the expected sets:

   .. code-block:: console

      python3 safety/tests/kernel/unit/common/test_inventory.py update twister-out

#. Review the diff with ``git diff -- safety/tests/kernel/unit``.

The script prints each new and each changed file. It also prints a warning
for an expected set that had no run in the twister output. If the scenario
of this file is removed, delete the file.

To make the expected sets of a new application, do the same steps. The
script makes the ``inventory`` directory.

Triage of a failure
===================

A ``-Wundef`` error or an inventory difference is not a test failure of
the unit. It shows that the set of tests changed.

- If the change is deliberate (a new test, a removed test, a new
  scenario), regenerate the expected sets. Then review the diff and
  commit it together with the change.
- If the change is not deliberate, the difference is a finding. Find the
  cause, for example a renamed Kconfig symbol, a removed macro or a
  changed suite predicate. Do not regenerate before the cause is known.

Code coverage
*************

The coverage report includes only the kernel sources
(``zephyr/kernel``). It does not include ztest, the fakes or the test
sources.

To get one report over all configurations, run twister with coverage:

.. code-block:: console

   west twister -T safety/tests/kernel/unit -p unit_testing \
     --coverage --coverage-basedir zephyr/kernel

The report is in ``twister-out/coverage/index.html``. Without
``--coverage-basedir``, the report also includes ztest and the public
headers.

To get a report for one configuration, build the target ``coverage``
with ``CONFIG_COVERAGE``:

.. code-block:: console

   west build -b unit_testing -d build-unit safety/tests/kernel/unit/sem \
     -t coverage -- -DCONFIG_COVERAGE=y

The target runs the test binary and writes the report to
``build-unit/coverage/index.html``. It needs ``gcovr``.

GCC does not emit an unused static inline function, so coverage does not
see it. The ``*_mrsh.c`` stubs prevent this for the ``z_vrfy_*`` functions
(see `Shadow headers`_). Make sure that each other static inline function
of a unit has a caller in the unit or in a test.

Condition coverage
==================

To get the GCC condition coverage (MC/DC with masking), add
``-x=EXTRA_CFLAGS=-fcondition-coverage`` to the twister command with
``--coverage``. The numbers are ``condition_total`` and
``condition_covered`` in ``twister-out/coverage_summary.json``. The text
report of gcovr has no condition metric: ``--txt-metric`` knows only
``line``, ``branch`` and ``decision``.

Per-test coverage
=================

To get the coverage of each test case, run twister with
``--coverage-per-test``. This option needs the ``lcov`` tool:

.. code-block:: console

   west twister -T safety/tests/kernel/unit -p unit_testing \
     --coverage-per-test --coverage-tool lcov

Twister writes the matrix of test cases and source lines to
``twister-out/coverage/test_matrix.json``. Do not give
``--coverage-basedir zephyr/kernel`` with ``lcov``. Twister then gives the
directory to ``genhtml --prefix``, and ``genhtml`` 2.0 stops with
``file error for sem.c``.

Twister enables ``CONFIG_ZTEST_COVERAGE_PER_TEST``. A ztest rule then
resets the gcov counters before each test and calls
``gcov_coverage_dump_tagged("<suite>.<test>")`` after each test. In
Zephyr, this option needs ``CONFIG_COVERAGE_GCOV`` (target builds).
``common/Kconfig`` defines the option a second time for
``CONFIG_COVERAGE_NATIVE_GCOV``. ``common/src/gcov_native.c`` implements
the reset and the dump with libgcov. It writes each ``.gcda`` file as
``<path>.gcda@@<suite>.<test>``, which is the name that twister finds.

With per-test coverage, the normal ``.gcda`` files have only the counts
after the last reset. Thus the target ``coverage`` gives no useful report
in this configuration.

Shadow headers
**************

The directory ``common/include`` comes before all Zephyr include
directories. Its headers replace real headers of the same name. These are
the *shadow headers*.

- ``ksched.h``, ``scheduler.h``, ``wait_q.h``, ``timeout_q.h``,
  ``kthread.h``, ``kernel_internal.h`` and ``kernel_arch_interface.h``
  replace the kernel-internal headers. They declare only the functions that
  a unit uses, and each one is a fake. Also functions that are static
  inline in the real header are fakes here, for example ``z_sched_wake()``
  and ``z_try_abort_thread_timeout()``. The exceptions are the pure helpers
  (see `Pure helpers stay real`_). A shadow header can declare fakes of
  more than one fake group. For example, ``kernel_internal.h`` declares
  ``z_handle_obj_poll_events()`` (group ``kernel_internal``) and
  ``z_thread_malloc()`` (group ``mempool``).
- ``ksched.h`` includes the shadows ``kspinlock.h``,
  ``kernel_internal.h``, ``timeout_q.h`` and ``wait_q.h``. The real
  ``ksched.h`` includes more headers, for example ``priority_q.h`` (see
  `Known limits`_).
- ``kspinlock.h`` declares no fakes. It declares the data
  ``_sched_spinlock`` (group ``sched``) and defines the macros
  ``LOCK_SCHED_SPINLOCK`` and ``Z_SCHED_SPINLOCK`` as the real header does.
  With one CPU (``CONFIG_MP_MAX_NUM_CPUS`` = 1), ``LOCK_SCHED_SPINLOCK`` is
  empty. With more CPUs, it locks ``_sched_spinlock`` with
  ``K_SPINLOCK()``.
- ``kernel_internal.h`` also defines ``K_KERNEL_INIT_PRE()`` as the real
  header does. The macro defines data, not a fake: the entry
  ``_kernel_init_pre_<fn>``. The kernel does not start, so no code runs the
  entries. A test reads the entry of the unit and calls the static init
  function directly.
- ``zephyr/arch/cpu.h`` replaces the ztest stub of the architecture layer.
  ``arch_interface.h`` requires static inline functions, so each function
  calls a fake with the prefix ``unit_``. For example, ``arch_irq_lock()``
  calls ``unit_arch_irq_lock()``.
- ``zephyr/arch/syscall.h`` replaces the system call functions of the
  architecture (``arch_syscall_invoke*()``, ``arch_is_user_context()``) in
  the same way. The ``unit_testing`` architecture identifies itself as
  X86, so the real header gives x86 inline assembly. The shadow is empty
  without ``CONFIG_USERSPACE``.
- ``zephyr/internal/syscall_handler.h`` replaces the system call
  verification macros. It is empty without ``CONFIG_USERSPACE``. The object
  checks call the fakes ``k_object_find()`` and
  ``k_object_validation_check()``. ``K_OOPS()`` calls
  ``unit_syscall_oops()``. The memory checks ``K_SYSCALL_MEMORY_READ()``
  and ``K_SYSCALL_MEMORY_WRITE()`` keep the size check and the pointer
  overflow check of the real macro. Then they call the fake
  ``arch_buffer_validate()``.
- ``coverage.h`` and ``zephyr/debug/gcov.h`` replace the gcov interface of
  a target build for the per-test coverage rule (see `Per-test coverage`_).
  ``coverage.h`` declares ``gcov_reset_all_counts()``. ``gcov.h`` declares
  the dump functions with ``CONFIG_ZTEST_COVERAGE_PER_TEST``. Without this
  option, it gives empty inline functions.
- ``zephyr/syscalls`` has stubs in place of the generated system call
  files. The unittest build does not generate them. A test calls the
  ``z_impl_*`` and ``z_vrfy_*`` functions directly. Each ``*_mrsh.c`` stub
  of a unit takes the address of its ``z_vrfy_*`` function with
  ``KERNEL_UNIT_SYSCALL_STUB()`` (``kernel_unit_syscall.h``). Thus the
  compiler emits the function also if it is static inline, and code
  coverage sees it. The stubs ``__ztest_set_test_phase_mrsh.c``,
  ``__ztest_set_test_result_mrsh.c`` and ``libc-hooks.h`` are empty. ztest
  and ``zephyr/sys/libc-hooks.h`` include them.

``kernel/include`` is not on the include path. If a unit includes a new
kernel-internal header, the build fails until the header has a shadow.

Pure helpers stay real
======================

A pure helper only computes a result from its arguments, or only reads a
structure. A fake of such a helper only repeats the test data, and the test
then does not show the real semantics. Thus these helpers stay real (user
decision of 2026-10-20). A shadow header has a copy of the static inline
function of the real header, without a change, between two marker lines:

.. code-block:: c

   /* KERNEL_UNIT_REAL_COPY_BEGIN kernel/include/ksched.h */
   static inline bool z_is_prio1_higher_than_prio2(int prio1, int prio2)
   {
           return prio1 < prio2;
   }
   /* KERNEL_UNIT_REAL_COPY_END */

The real helpers are:

- ``ksched.h``: the priority comparisons and the priority ceiling, from
  ``z_is_under_prio_ceiling()`` to ``z_is_prio_lower_or_equal()``, as one
  block. ``z_is_prio_higher()`` and ``z_get_new_prio_with_ceiling()`` are in
  it.
- ``kthread.h``: ``z_is_thread_pending()``,
  ``z_is_thread_prevented_from_running()`` and ``z_is_thread_ready()``. They
  only read ``thread->base.thread_state``.
- ``timeout_q.h``: ``z_is_inactive_timeout()``, one copy for each timeout
  backend and the macro without ``CONFIG_SYS_CLOCK_EXISTS``. It only reads
  the timeout structure.

A function with a side effect stays a fake, for example
``z_thread_prio_set()``, the scheduler functions and the wait queue
functions.

The drift guard ``common/check_real_copies.py`` examines that the text
between the markers occurs in the real header, character for character.
``cmake/kernel_unit.cmake`` runs it when an application is configured. If a
copy is not up to date, the configuration stops and prints the copy. A
change of a shadow header or of a header in ``kernel/include`` runs the
check again. The guard does not check the conditions (``#if``) around a
copy. To run it by hand:

.. code-block:: console

   python3 safety/tests/kernel/unit/common/check_real_copies.py \
     zephyr safety/tests/kernel/unit/common/include/*.h

The public headers stay real, for example ``zephyr/kernel.h`` and
``zephyr/spinlock.h``. Their inline functions run in the test. For
example, ``k_spin_lock()`` calls ``arch_irq_lock()``, and a test sees the
call in ``unit_arch_irq_lock_fake``.

Fakes
*****

A real header can declare a function extern. Such a function needs no
shadow. A file in ``common/include/fakes`` declares its fake, for example
``fakes/obj_core.h``. Some public functions are system calls, for example
``k_mutex_lock()``. The unittest build does not generate their wrappers, so
the unit calls an extern function, and a fake replaces it (see
`System call entry points`_).

The fake definitions are in ``common/fakes``, one file for each group. An
application includes ``cmake/kernel_unit.cmake`` of the safety module and
links the groups that it needs:

.. code-block:: cmake

   include(${ZEPHYR_SAFETY_MODULE_DIR}/cmake/kernel_unit.cmake)

   kernel_unit_fakes(arch sched fatal kernel_internal)
   kernel_unit_fakes_ifdef(CONFIG_OBJ_CORE obj_core)

The safety repository is a Zephyr module (``zephyr/module.yml``). Thus the
build knows its path as ``ZEPHYR_SAFETY_MODULE_DIR``.

Do not link a group that fakes a function of the unit under test. Then the
linker finds two definitions.

A group has the name of the kernel source file that defines the real
functions or data. Thus a later unit test of this file knows which group
it must not link. The groups are:

- ``arch``: the architecture layer. These are the ``unit_arch_*()`` fakes
  of ``zephyr/arch/cpu.h`` and, with ``CONFIG_USERSPACE``, of
  ``zephyr/arch/syscall.h``. The group also has ``arch_is_in_isr()`` and
  ``arch_thread_return_value_set()`` of ``kernel_arch_interface.h``.
- ``sched``: the kernel-internal scheduler interface. These are the fakes
  of the shadows ``ksched.h``, ``scheduler.h``, ``wait_q.h`` and
  ``timeout_q.h``, for example ``z_thread_prio_set()``. The real functions
  are in ``kernel/sched.c``, or they are static inline in
  ``kernel/include``. One exception is
  ``z_sched_waitq_walk()``, which ``kernel/scheduler.c`` defines. The group
  also defines the data ``_sched_spinlock``. The fake ``z_pend_curr()``
  refuses a call from an ISR with a panic, as the real function does (see
  `Scheduler refusal in an ISR`_). Thus the group needs the groups ``arch``
  and ``fatal``, and the group ``assert`` with ``CONFIG_ASSERT``.
- ``scheduler``: only ``k_sched_current_thread_query()``
  (``kernel/scheduler.c``, header ``fakes/scheduler.h``). This is a public
  system call of ``zephyr/kernel.h``, not a kernel-internal function. After
  the reset, it returns NULL. A test that needs a current thread sets
  ``return_val``. A unit test of ``kernel/scheduler.c`` must link neither
  ``scheduler`` nor ``sched``, because ``sched`` fakes
  ``z_sched_waitq_walk()``.
- ``kernel_internal``: ``z_handle_obj_poll_events()`` (``kernel/poll.c``).
- ``mempool``: ``z_thread_malloc()`` and ``k_free()``
  (``kernel/mempool.c``). After the reset, ``z_thread_malloc()`` returns
  NULL. A test that needs memory sets ``return_val`` or ``custom_fake``.
- ``init``: the data ``_kernel`` of ``kernel/init.c``. Without SMP,
  ``_current`` is ``_kernel.cpus[0].current``. The rule sets ``_kernel`` to
  zeros before each test. A test that needs a current thread sets this
  pointer. This group has no fakes and no header: ``zephyr/kernel_structs.h``
  declares ``_kernel``. The group also defines the log module ``os``
  (``LOG_MODULE_REGISTER(os)``), for a unit with
  ``LOG_MODULE_DECLARE(os, ...)``, for example ``mutex.c``.
- ``fatal``: ``z_fatal_error()`` (``kernel/fatal.c``). The
  ``unit_testing`` architecture does not define ``ARCH_EXCEPT()``. Thus
  ``k_panic()`` and ``k_oops()`` of ``zephyr/kernel.h`` call
  ``z_fatal_error(reason, NULL)``. The fake returns. A test examines
  ``z_fatal_error_fake.arg0_val``, for example ``K_ERR_KERNEL_PANIC``. Each
  application links this group, because the group ``sched`` needs it.
- ``mutex``: ``k_mutex_lock()`` and ``k_mutex_unlock()``
  (``kernel/mutex.c``). ``zephyr/kernel.h`` declares them as system calls.
  After the reset, both fakes return 0. Do not link this group in a unit
  test of ``kernel/mutex.c``.
- ``obj_core``: ``k_obj_core_init()``, ``k_obj_core_link()``,
  ``k_obj_core_init_and_link()`` and ``k_obj_core_unlink()``
  (``kernel/obj_core.c``). Link it with
  ``kernel_unit_fakes_ifdef(CONFIG_OBJ_CORE obj_core)``.
- ``obj_core_stats``: ``k_obj_core_stats_register()`` and
  ``k_obj_core_stats_deregister()`` (``kernel/obj_core.c`` with
  ``CONFIG_OBJ_CORE_STATS``). Link it with
  ``kernel_unit_fakes_ifdef(CONFIG_OBJ_CORE_STATS obj_core_stats)``.
- ``kobject``: ``k_object_init()`` (``kernel/userspace/userspace.c``). Link
  it only with ``CONFIG_USERSPACE``.
- ``syscall_handler``: the fakes of the shadow
  ``zephyr/internal/syscall_handler.h``. These are ``k_object_find()``,
  ``k_object_validation_check()``, ``unit_syscall_oops()`` and
  ``arch_buffer_validate()``. After the reset, ``arch_buffer_validate()``
  returns 0: the thread has access. Link the group only with
  ``CONFIG_USERSPACE``.
- ``assert``: ``assert_print()`` and ``assert_post_action()``
  (``lib/os/assert.c``). Link it only with ``CONFIG_ASSERT``.
- ``spinlock``: the spinlock validation functions
  (``kernel/spinlock_validate.c``). Link it only with
  ``CONFIG_SPIN_VALIDATE``.
- ``sched_ref``: the reference fake of the scheduler contract (see
  `Reference fake of the scheduler`_). This group is a model group: no
  kernel source file defines its functions. It sets the ``custom_fake`` of
  the fakes of the groups ``sched`` and ``arch``, so it needs the groups
  ``sched``, ``arch``, ``fatal`` and ``init``.
- ``log_minimal``: ``z_log_minimal_printk()``
  (``subsys/logging/log_minimal.c``). The ``unit_testing`` board uses
  ``CONFIG_LOG_MODE_MINIMAL``. A ``LOG_DBG()`` of the unit calls this
  function only if the log level of the unit is DBG, for example with
  ``CONFIG_KERNEL_LOG_LEVEL_DBG``. Link the group in such a scenario. The
  history helpers ignore its calls.

For each linked group, ``kernel_unit_fakes()`` adds the definition
``KERNEL_UNIT_FAKE_GROUP_<group>`` to the sources. Thus a shared header can
refer to the fakes of a group only if the application links it.

Each group resets its fakes with a ztest rule before each test. After the
reset, a fake returns zero, with one exception: ``z_spin_lock_valid()``
and ``z_spin_unlock_valid()`` return true. ``kernel_unit.cmake`` always
links ``common/fakes/fff_globals.c``. This file defines the FFF globals,
and its rule resets the call history before each test.

Configurations
**************

The ``testcase.yaml`` of an application has a default scenario and one
scenario for each configuration option that changes the code of the unit.
The scenario ``all`` enables most of these options together. The options
of each unit are:

- ``sem.c``: ``CONFIG_POLL``, ``CONFIG_OBJ_CORE_SEM``,
  ``CONFIG_USERSPACE`` and the ``CHECKIF()`` options
  (``CONFIG_NO_RUNTIME_CHECKS``, ``CONFIG_ASSERT_ON_ERRORS``).
- ``queue.c``: the same options, with ``CONFIG_OBJ_CORE_FIFO`` and
  ``CONFIG_OBJ_CORE_LIFO`` in place of ``CONFIG_OBJ_CORE_SEM``.
- ``msg_q.c``: ``CONFIG_POLL``, ``CONFIG_OBJ_CORE_MSGQ``,
  ``CONFIG_USERSPACE``, ``CONFIG_MP_MAX_NUM_CPUS``, ``CONFIG_ASSERT`` and
  the ``CHECKIF()`` options.
- ``stack.c``: ``CONFIG_OBJ_CORE_STACK``, ``CONFIG_USERSPACE``,
  ``CONFIG_ASSERT`` and the ``CHECKIF()`` options. ``stack.c`` has no
  ``CONFIG_POLL`` code.
- ``mem_slab.c``: ``CONFIG_MEM_SLAB_POINTER_VALIDATE``,
  ``CONFIG_MEM_SLAB_TRACE_MAX_UTILIZATION``, ``CONFIG_OBJ_CORE_MEM_SLAB``,
  ``CONFIG_OBJ_CORE_STATS_MEM_SLAB``, ``CONFIG_MULTITHREADING`` and the
  ``CHECKIF()`` options.
- ``events.c``: ``CONFIG_WAITQ_SCALABLE``, ``CONFIG_OBJ_CORE_EVENT``,
  ``CONFIG_USERSPACE`` and ``CONFIG_ASSERT``. ``events.c`` has no
  ``CHECKIF()``, so the ``CHECKIF()`` options have no scenario.
- ``condvar.c``: ``CONFIG_USERSPACE`` and ``CONFIG_OBJ_CORE_CONDVAR``.
  ``condvar.c`` has no ``CHECKIF()`` and no ``__ASSERT()``.
- ``mutex.c``: ``CONFIG_PRIORITY_CEILING`` (scenarios ``ceiling`` with 0
  and ``pi_disabled`` with 15), ``CONFIG_MUTEX_DEADLOCK_DETECT``,
  ``CONFIG_OBJ_CORE_MUTEX``, ``CONFIG_USERSPACE``,
  ``CONFIG_MP_MAX_NUM_CPUS``, ``CONFIG_ASSERT``, the ``CHECKIF()`` options
  and ``CONFIG_KERNEL_LOG_LEVEL_DBG`` (scenario ``logging``). Priority
  inheritance is in the code only if ``CONFIG_PRIORITY_CEILING`` is less
  than ``CONFIG_NUM_PREEMPT_PRIORITIES`` (``Z_MUTEX_PI_ENABLED`` in
  ``zephyr/kernel/thread.h``). ``CONFIG_ASSERT`` enables
  ``CONFIG_MUTEX_DEADLOCK_DETECT`` by default, so the scenario ``assert``
  disables it, and the scenario ``deadlock_detect`` enables it. The tests
  of priority inheritance are in ``#if Z_MUTEX_PI_ENABLED`` blocks. The
  documentation tools do not read this condition (it is not a
  ``CONFIG_X``).
- ``sched_ref`` (the self-test of the reference fake): ``CONFIG_ASSERT``
  (scenario ``assert``), for the assertion hook of the ISR refusal.
- ``obj_core.c``: ``CONFIG_OBJ_CORE`` (all scenarios,
  ``CONFIG_OBJ_CORE_SYSTEM`` has no prompt), ``CONFIG_OBJ_CORE_STATS``,
  ``CONFIG_OBJ_CORE_STATS_SYSTEM`` (scenario ``stats_no_system`` disables
  it), ``CONFIG_MP_MAX_NUM_CPUS`` and ``CONFIG_USERSPACE`` (for
  ``z_vrfy_k_sem_init()``).

Kconfig options for the harness
===============================

The ``unit_testing`` architecture has no user mode support. The option
``CONFIG_KERNEL_UNIT_USERSPACE`` (``common/Kconfig``) selects the
architecture features that ``CONFIG_USERSPACE`` needs. An application
sources ``common/Kconfig`` from its own ``Kconfig`` file.

``CONFIG_MULTITHREADING`` can be disabled only if the architecture
declares ``ARCH_HAS_SINGLE_THREAD_SUPPORT``. The ``mem_slab`` application
has its own option ``CONFIG_KERNEL_UNIT_MEM_SLAB_SINGLE_THREAD``, which
selects it.

The ``unit_testing`` board has no SMP. ``CONFIG_MP_MAX_NUM_CPUS=2``
without ``CONFIG_SMP`` selects the code for more than one CPU. Then
``LOCK_SCHED_SPINLOCK`` locks the scheduler spinlock (scenario
``multi_cpu`` of ``msgq``). A unit that uses the scheduler spinlock directly
needs this scenario.

``CONFIG_WAITQ_SCALABLE`` is a choice against ``CONFIG_WAITQ_SIMPLE``. With
it, ``Z_WAIT_Q_INIT()`` in a static object definition (for example
``K_EVENT_DEFINE()``) refers to ``z_priq_rb_lessthan()`` of
``kernel/priority_queues.c``. The ``event`` application defines a stub of
this function that fails the test if a call occurs.

Assertions
==========

A scenario with ``CONFIG_ASSERT`` also sets ``CONFIG_ASSERT_TEST``. A failed
``__ASSERT()`` calls the hook ``assert_post_action()``. In a unit test, the
hook is a fake that returns. Without ``CONFIG_ASSERT_TEST``, the hook is
followed by ``CODE_UNREACHABLE``, and the unit continues into undefined
behavior. With ``CONFIG_ASSERT_TEST``, the unit continues after the hook,
and a test can examine the calls after the assertion.

If the unit has its own ``__ASSERT()`` checks, add a scenario ``assert``.
This scenario sets ``CONFIG_ASSERT`` and ``CONFIG_ASSERT_TEST``, but not
``CONFIG_ASSERT_ON_ERRORS``. Then the ``CHECKIF()`` checks keep their error
return, and the assertions are active.

``CONFIG_ASSERT`` also enables ``CONFIG_SPIN_VALIDATE`` by default. Thus
the tests run with the calls of the spinlock validation. For this reason,
the scenario ``all`` of ``condvar`` sets ``CONFIG_ASSERT``, although
``condvar.c`` has no ``__ASSERT()``.

Linker sections
===============

The linker script ``common/kernel_unit.ld`` adds the iterable sections of
the kernel objects. ``K_OBJ_TYPE_DEFINE()`` puts its descriptor into
``k_obj_core_desc``. The static objects of each type go into the sections
``k_sem``, ``k_fifo``, ``k_lifo``, ``k_msgq``, ``k_stack``, ``k_mem_slab``,
``k_event``, ``k_condvar`` and ``k_mutex``. A unit with a new object type needs a new
section here.

The linker sorts each section by the object name. A boot-time init function
can walk a section (``STRUCT_SECTION_FOREACH()``). To test it, give the
static objects of the test names in the order that the test needs. The
objects are global, so reset their state in the ``before`` function.

The script also gives the bounds of the ztest memory partition as zero.
ztest defines this partition with ``CONFIG_USERSPACE``, but a unit test
runs no user thread.

Write a test
************

The test source of an application is ``src/test_<unit>.c``, for example
``sem/src/test_sem.c``. It includes the kernel source file exactly once.

Test helpers
============

``common/include/kernel_unit.h`` has the helpers that all applications
share:

- ``KERNEL_UNIT_IRQ_KEY``: a distinctive interrupt lock key. The suite makes
  ``unit_arch_irq_lock()`` return it, with ``return_val`` or with a
  ``custom_fake``. Then a test can follow the key to the call that releases
  the lock, for example ``unit_arch_irq_unlock()`` or ``z_reschedule()``.
- ``zassert_call_history(fn, ...)``: asserts that the FFF call history is
  exactly this list of fakes. ``KERNEL_UNIT_IF_ENABLED(CONFIG_X, fn)`` is an
  entry that counts only if ``CONFIG_X`` is enabled.
- ``zassert_called_before(first, second)``: asserts the order of the first
  calls of two fakes.
- ``kernel_unit_history_index(fn, nth)``: gives the position of call
  number ``nth`` of ``fn`` in the call history, or -1.
- ``kernel_unit_history_len()``: gives the number of calls in the call
  history.
- ``kernel_unit_history()``, ``kernel_unit_history_equal()`` and
  ``kernel_unit_history_print()``: copy, compare and print the call
  history. The macros above use them.
- ``KERNEL_UNIT_FN(fn)``: casts a fake to the type of an entry of the call
  history.

The history helpers ignore the calls of the spinlock validation
(``CONFIG_SPIN_VALIDATE``). These calls come from ``k_spin_lock()`` and
``k_spin_unlock()``, not from the unit. They also ignore the calls of the
minimal log backend (fake group ``log_minimal``): a log call is not a call
into a layer below. If a history is not as expected, the
helper prints it.

FFF records at most ``FFF_CALL_HISTORY_LEN`` (50) calls. A test with more
calls cannot use the history helpers.

Shared models
=============

``common/include/kernel_unit_models.h`` has the models and the checks that
more than one application uses. The Doxygen group ``kernel_unit_models``
documents them. Each model states an assumption about the layer below the
unit. The tests of a unit are correct only if the layer below meets this
assumption. All functions are static inline, and the state is static data
of the test source. Thus the header adds no link dependency: a model of a
fake group that the application does not link is not emitted. Include the
header after ``kernel_unit.h``.

- Fill pattern: ``KERNEL_UNIT_FILL`` and ``kernel_unit_assert_filled()``
  (see `Guard entries`_).
- Lock spies: ``kernel_unit_spy_on_lock(at_lock, at_release)`` replaces
  the fakes of the lock, of ``k_spin_unlock()`` and of ``z_reschedule()``.
  Each spy calls an observer function of the test. The observer records the
  state of the object at the call. Each lock gives ``KERNEL_UNIT_IRQ_KEY``.
- Lock model: ``kernel_unit_lock_model_install()`` counts the holds of the
  lock (``kernel_unit_lock.depth``), the outer and the nested locks, and
  runs an action of another thread when the lock becomes free
  (``kernel_unit_run_when_free()``, ``kernel_unit_run_at_next_release()``).
  A nested lock gives ``KERNEL_UNIT_NESTED_IRQ_KEY``. A ``z_pend_curr()``
  model of the test calls ``kernel_unit_lock_released()``.
- Lock invariant: ``kernel_unit_assert_lock_released_once(lock, how)``
  asserts one lock as the first call and one release, with the key, as the
  last call. ``how`` is ``KERNEL_UNIT_RELEASED_BY_UNLOCK``, ``_RESCHEDULE``
  or ``_PEND``. ``kernel_unit_assert_lock_rule()`` permits calls before the
  lock (a filter, for example the ISR check of an ``__ASSERT()``) and one
  call after ``z_pend_curr()``. The check does not work with nested locks.
- Waiting threads: ``kernel_unit_set_waiting_threads(n)``. ``z_sched_wake()``
  wakes one of ``n`` threads for each call.
- Wait result: ``kernel_unit_set_wait_result(swap_data, result)``.
  ``z_pend_curr()`` gives the swap data to the current thread and returns
  the result.
- Other threads: ``kernel_unit_set_other_thread(action, release_lock)``.
  ``z_pend_curr()`` runs the action of another thread while the current
  thread waits. A wake fake of the test calls ``kernel_unit_wake_current()``.
  If no thread wakes the current thread, the wait is a timeout (-EAGAIN).
  ``kernel_unit_run_as(thread, action)`` runs an action with another
  ``_current``.
- Object checks (``CONFIG_USERSPACE``): ``kernel_unit_pass_object_check()``,
  ``kernel_unit_fail_object_check()``, ``kernel_unit_assert_object_check()``
  and ``kernel_unit_assert_object_check_n()``.
- Scheduler refusal in an ISR: ``kernel_unit_expect_pend_refusal()`` and
  ``kernel_unit_assert_pend_refused()`` (see `Scheduler refusal in an
  ISR`_).
- Checks that do not return: ``zassert_stopped_by_assertion()``,
  ``zassert_stopped_by_oops()`` and ``zassert_stopped_by_panic()`` (see
  `Checks that do not return`_).

The reference fake of the scheduler is not in this header. It has its own
header and fake group (see `Reference fake of the scheduler`_).

Each application keeps its local helpers in its test source. Examples are
the observers of the lock spies, a thin ``assert_lock_released_once()``
that names the lock of the unit, and the models that only one unit needs.
Some units read the context before they take the lock. With
``CONFIG_ASSERT``, ``sem.c``, ``msg_q.c``, ``events.c`` and ``mutex.c`` call
``arch_is_in_isr()`` before the lock. A wait of ``events.c`` also calls
``k_sched_current_thread_query()`` before the lock. The lock invariant of
such a unit gives a filter for these calls.

System call entry points
========================

A test calls ``z_impl_<name>()`` and ``z_vrfy_<name>()`` directly. Some
macros of the public headers call the system call ``<name>()`` itself, for
example ``k_fifo_get()`` calls ``k_queue_get()``. The unittest build does
not generate ``zephyr/syscalls/kernel.h``, and ``__syscall`` is empty for
``ZTEST_UNITTEST``. Thus ``<name>()`` is an undefined extern function. If a
test uses such a macro, the test source defines ``<name>()`` as a call of
``z_impl_<name>()``. This is the code that the generated file has without
``CONFIG_USERSPACE``. See ``queue/src/test_queue.c``.

If the unit itself calls a system call of another kernel source file, a
fake group defines the extern function. Examples are the groups ``mutex``
and ``scheduler`` (see `Fakes`_).

Models of the layers below
==========================

A fake can model the state of a layer below the unit with a
``custom_fake``. Keep a model small. It must only give the unit the inputs
of one design rule. The real behavior of the layer below is the subject of
its own unit test. Use a shared model (see `Shared models`_) if one fits.

A model replaces ``return_val``. If a test needs a plain return value, it
sets ``custom_fake`` to NULL. As an alternative, the model returns the
``return_val`` of its own fake, as the mutex models of ``condvar`` and the
priority model of ``mutex`` do.

The applications use these shared models:

- ``sem``, ``queue``, ``stack``, ``mem_slab`` and ``event``: the lock
  spies.
- ``condvar`` and ``mutex``: the lock model. ``condvar`` shows a lost
  wake-up with it: if the unit releases the lock too early, the signal of
  the other thread finds no waiting thread.
- ``queue``, ``stack``, ``mem_slab`` and ``msgq``: the waiting threads.
- ``queue``, ``stack`` and ``mem_slab``: the wait result.
- ``stack``, ``event`` and ``mutex``: the other threads. In ``stack``, the
  other thread pushes a value, and the value reaches the waiting pop. In
  ``event``, the other thread posts events, and the wait returns the value
  that the post gave to ``arch_thread_return_value_set()``. In ``mutex``,
  the owner unlocks the mutex and gives it to the waiting thread.

Scheduler refusal in an ISR
---------------------------

The real ``z_pend_curr()`` (``kernel/sched.c``) refuses a call from an ISR
in every build, before it does a side effect:

.. code-block:: c

   if (arch_is_in_isr()) {
           __ASSERT(false, "blocking pend from ISR context");
           k_panic();
   }

The fake ``z_pend_curr()`` in ``common/fakes/sched.c`` does the same. The
refusal is in the fake itself, before its ``custom_fake``. Thus each model
of ``z_pend_curr()`` gets it, the shared models and the local models of
the test sources. Do not copy the refusal into a model.

#. The fake records the call as each FFF fake does.
#. It reads the context from the fake ``arch_is_in_isr()`` without a call.
   Thus ``arch_is_in_isr_fake.call_count`` and the call history show only
   the calls of the unit.
#. In an ISR, it increments ``kernel_unit_pend_refusal.count``. Then it
   does the assertion hook (with ``CONFIG_ASSERT``) and the panic,
   ``z_fatal_error(K_ERR_KERNEL_PANIC, NULL)``. It does not call the
   ``custom_fake``, does not release the lock and does not change a wait
   queue or a thread.
#. The fake ``z_fatal_error()`` returns. Then the fake ``z_pend_curr()``
   returns ``KERNEL_UNIT_PEND_REFUSED`` (``-EAGAIN``, a timeout).

The return value is the result of a timeout, because each unit treats it
as a wait that ended without a wake. Then the unit changes nothing that a
timeout does not change. A value that no real wait gives is not safe: for
example, ``k_stack_pop()`` treats each result other than ``-EAGAIN`` as a
wake and reads the swap data.

The real ``z_pend_curr()`` does not return. Thus a test that lets an ISR
reach ``z_pend_curr()`` must show it:

- The test calls ``kernel_unit_expect_pend_refusal()`` before the action.
  If a refusal occurs without this call, the fake prints a message and
  fails the test. Thus no unit continues after the panic without a test
  that shows it.
- ``kernel_unit_assert_pend_refused()`` asserts one refusal and one panic.
  In the call history, the panic comes after ``z_pend_curr()``, with a
  failed assertion between them if ``CONFIG_ASSERT`` is enabled.
- If the unit makes more calls after ``z_pend_curr()`` (for example
  ``k_condvar_wait()`` locks the mutex again), use
  ``zassert_stopped_by_panic()``. Then the unit stops at the panic, and the
  test shows the state at the panic.

The lock invariant (``kernel_unit_assert_lock_rule()``) does not apply to a
refused call: this call does not release the lock.

These models stay local, because only one unit needs them:

- ``queue``: the heap. ``z_thread_malloc()`` gives nodes from a static pool
  of the test and asserts the size.
- ``msgq``: the hand-over (``z_unpend_first_thread_locked()`` returns a
  thread of the test once) and its own lock model with nested keys. Its
  ``z_reschedule()`` and ``z_pend_curr()`` spies do not release the lock
  model, and the msgq tests rely on this. Thus it does not use the shared
  lock model.
- ``stack``: the wait queue head (``z_waitq_head()`` and
  ``z_waitq_head_locked()`` return a thread of the test).
- ``event``: the wait queue walk. ``z_sched_waitq_walk()`` calls the walk
  callback for each thread of an array of the test, then the post-walk
  callback, as the real function in ``kernel/scheduler.c`` does.
- ``condvar``: the mutex (``k_mutex_lock()`` and ``k_mutex_unlock()``
  record if the current thread holds the mutex) and the wait queue with the
  position of the current thread.
- ``mutex``: the wait queues of the mutexes, sorted by priority
  (``z_waitq_head_locked()``, ``z_unpend_first_thread_locked()`` and
  ``z_pend_curr()``), the wake by ``arch_thread_return_value_set()``, and
  the priority (``z_thread_prio_set()`` sets ``base.prio`` and returns its
  ``return_val`` as the reschedule hint).

Reference fake of the scheduler
-------------------------------

The models above state assumptions about the scheduler in prose. The
reference fake is the C form of the scheduler contract
(``safety/spec/tla/lib/Scheduler.tla``, layer A) for one CPU. The header is
``common/include/kernel_unit_sched_ref.h``, the code is
``common/fakes/sched_ref.c`` (fake group ``sched_ref``). The review of the
models against the contract is in the workspace notes
(``claude/kernel-unit/reffake/review.md``).

- The fake has the threads of the test with their priorities, a wait queue
  for each ``_wait_q_t`` (a higher priority first, then the order of
  arrival), the current thread, the swap return value and the swap data of
  each thread, and the armed timeouts.
- Each scheduler function that the objects call has one fake function. Its
  comment names the operator of the contract. ``z_reschedule()`` selects the
  next thread with the rule ``Choices`` of the contract. Where the contract
  and ``kernel/sched.c`` differ, the fake follows the code. For example,
  after ``z_thread_prio_set()`` of a ready thread, the next selection has no
  tie rule and no rule for cooperative threads, as ``update_cache(1)`` of the
  code.
- ``z_pend_curr()`` records the wait, selects the next thread and runs the
  environment steps of the test: an action of another thread, an action of
  an ISR, a timeout or an abort. When the CPU selects the waiting thread
  again, the fake returns its swap return value. A ``K_FOREVER`` wait that
  no step ends does not return: the check ``NO_RETURN`` fails.
- The checks come from the invariants of the contract (for example
  ``ArmedArePending`` and ``RunRuleHolds``) and from the preconditions of
  the operators (``MISUSE``). A failed check fails the test, unless the test
  expects it with ``kernel_unit_sched_ref_expect()``.
- ``z_handle_obj_poll_events()`` stays a plain fake.

The fake is opt-in. A test calls ``kernel_unit_sched_ref_install()``, adds
its threads (``kernel_unit_sched_ref_thread()``), sets the current thread
and the waiting threads, and adds the environment steps. FFF records each
call before the fake runs, so the history helpers work. At the end, the test
calls ``kernel_unit_sched_ref_assert_ok()``. The fake does not work together
with the lock spies or the lock model, because all three replace the
``custom_fake`` of ``z_reschedule()``.

An application that uses the fake links the groups ``init`` and
``sched_ref``. Today ``sem`` uses it (the tests ``test_ref_*``). The
application ``sched_ref`` tests the fake against the example values of
``mc/SchedulerTest.tla`` and against the misuses of ``mc/MCScheduler.tla``.

Real object core code
=====================

The ``obj_core`` application does not link the fake groups ``obj_core``
and ``obj_core_stats``. Its second source includes ``kernel/sem.c`` and
calls the real object core code. The tests never walk a list that can
have a cycle without a bound (``src/obj_core_list.h``).

The tests of the re-init defect (see
``claude/kernel-unit/unit-tests/findings/obj_core-findings.md`` in the
workspace) assert the correct behavior and have
``ZTEST_EXPECT_FAIL()``. If a fix makes such a test pass, ztest reports a
failure. Then remove the ``ZTEST_EXPECT_FAIL()`` line, and regenerate the
expected sets of the application (see `Test inventory`_).

Guard entries
=============

The ``msgq`` and ``stack`` applications put one guard entry after each
buffer of a test, filled with ``KERNEL_UNIT_FILL``. Thus a test can show
that no operation writes after the end of the buffer. This also applies
after a failed assertion or with ``CONFIG_NO_RUNTIME_CHECKS``, and no memory
fault occurs. ``kernel_unit_assert_filled()`` checks the guard entry. The
type of the entry is local to each application.

Checks that do not return
=========================

The fakes ``assert_post_action()``, ``unit_syscall_oops()`` and
``z_fatal_error()`` return, so the unit continues after a failed check or
a panic (see `Known limits`_). Sometimes the unit then uses an invalid
pointer, for example a NULL pointer after an assertion. Then the test
crashes. If the unit continues in this way, use
``zassert_stopped_by_assertion(call)``, ``zassert_stopped_by_oops(call)``
or ``zassert_stopped_by_panic(call)`` of ``kernel_unit_models.h``. The macro
gives the fake a ``custom_fake`` that calls ``longjmp()`` back into the
test, and removes it after the call. Examples are in ``mem_slab``,
``msgq``, ``mutex`` and ``condvar``. ``zassert_stopped_by_panic()`` also
stops the unit at the ISR refusal of ``z_pend_curr()`` (see `Scheduler
refusal in an ISR`_).

Doxygen comments
================

The Doxygen group ``kernel_unit_tests`` (in ``kernel_unit.h``) is the root
of the kernel unit tests. The groups have the structure of the kernel
sources. There is only one grouping: each test is in exactly one group.

- File group: each application defines one group for its kernel source
  file, ``kernel_unit_<unit>``, with ``@ingroup kernel_unit_tests``. Its
  title is the file, for example ``kernel/sem.c``. The introduction of this
  group describes the design of the file as a whole. It covers the object,
  the locks, the interfaces below the file and the Kconfig options. A design
  rule that applies to more than one function (for example the locking, or
  the system call verification) is a ``@par`` section of this introduction.
- Function group: each public function of the file has one group below
  the file group, ``kernel_unit_<unit>_<function>``. Its title is the
  function, for example ``k_sem_give()``. A public function is a function
  with external linkage in the source file. A system call has one group for
  its ``z_impl_`` and its ``z_vrfy_`` function, also if the ``z_vrfy_``
  function is static inline. The group has the name of the system call, for
  example ``kernel_unit_sem_k_sem_give`` for ``z_impl_k_sem_give()`` and
  ``z_vrfy_k_sem_give()``. The group describes the design of the function.
  Its section "Functions in kernel/<file>.c" names the functions and their
  Kconfig conditions. A function also has a group if no test is in that
  group. Its brief description then starts with "No unit test covers" or,
  if tests of other groups call the function, with "No test of its own".
  The text names these tests.
- Static group: the group ``kernel_unit_<unit>_static`` ("Static functions
  and data") has the tests of the static functions of the file, for
  example ``sem_handle_poll_events()``. It also has the tests of the data
  that the file defines, for example the object type descriptor of
  ``K_OBJ_TYPE_DEFINE()``. It is the last group of the file group.

Define the function groups and the static group at the top of the test
source, after the file group, in the order of the kernel source file. With
``SORT_GROUP_NAMES = NO``, Doxygen keeps this order.

Each test has a Doxygen comment:

- ``@brief``: one design rule, as a fact. For example: "k_sem_give() does
  not increment the count above the limit."
- ``@details``: a short list with the setup, the action and the expected
  result.
- ``@ingroup``: the group of the function under test. This is the function
  that the action of the test calls. If the action calls more than one
  function, use the group of the function whose rule the test states. If
  the action reaches a static function through one public function, use
  the group of the public function. If the test calls a static function
  directly, or reaches it through more than one public function, use the
  static group.
- ``@see``: the function under test first, then the other functions of the
  unit that the test calls.

The tests have no ``@testid`` and no ``@verifies`` yet.

The application ``sched_ref`` is not a unit of a kernel source file. Its
group ``kernel_unit_sched_ref_tests`` keeps its subgroups by design topic.

The Doxygen document ``dox-kernel-unit-testspec`` ("Kernel Unit Test
Specification", ``safety/doc/dox/kernel-unit-testspec``) shows these groups.
Its input is the test sources of the units and ``kernel_unit.h``. If you add
a test application, add its test sources to the ``INPUT`` of its
``Doxyfile.in``. To build the document, configure the documentation of the
safety repository and build the target ``dox-kernel-unit-testspec``:

.. code-block:: console

   cmake -S safety/doc -B build-doc
   cmake --build build-doc --target dox-kernel-unit-testspec

Test doubles in the specification
---------------------------------

The document shows the test doubles of each test: the fakes that the test
configures, how it configures them, the calls that it checks and the known
limits of these doubles. Nobody writes this text by hand. The input filter
of the document runs ``safety/doc/_scripts/kernel_unit_doubles.py``. The
script reads the test source, the ``CMakeLists.txt`` of the application and
the sources in ``common``. Thus the text changes together with the tests.

- A test source with the marker ``@kunit_interfaces`` in its file group gets
  the generated sections. Today ``sem`` and ``mutex`` have the marker. Put
  the marker after the paragraph "Interfaces below <file>". The filter adds
  a table there: each fake of the unit, its fake group, and the number of
  tests that configure or check it.
- Each test of such a source gets a section "Test doubles" and a section
  "Checked calls". The doubles are a fixed value (``return_val``), a
  sequence (``SET_RETURN_SEQ()``), a local custom fake, a shared model or
  the reference fake. The statements of the ``before`` function of the
  suite are in the file group, not at each test.
- The page "Test doubles" (``safety/doc/dox/kernel-unit-testspec/doubles.dox``)
  has the fake groups, the defaults after the reset, the real copies, the
  models with their assumptions, the reference fake with the operators of
  the contract, the local custom fakes and the known limits.
- The known limits are in ``common/fake_limits.yaml``. This is the only
  part that is written by hand. Each limit has selectors: the doubles that
  it applies to. A test that uses such a double in its own statements shows
  the limit.

Give each local custom fake a comment directly before the function. The
page "Test doubles" shows the comment as the description of the fake.

The script reads the C text. It does not evaluate ``#if`` or ``if``, so the
result is the set of doubles that a test can use. Run the check after a
change of the tests or of ``fake_limits.yaml``:

.. code-block:: console

   python3 safety/doc/_scripts/kernel_unit_doubles.py check

The check fails if a selector of a limit matches no test or names no fake.
It warns if a local custom fake has no comment. With ``--prose``, it also
warns if the doc comment of a test does not name a fake that the test body
configures. The target ``kernel-unit-doubles-check`` of the documentation
build runs the same check. To see the doubles of the tests of a unit as
text, run ``kernel_unit_doubles.py unit <unit>``.

Tests for some configurations
=============================

If a test needs a symbol that exists only with ``CONFIG_X``, put the test in
an ``#ifdef CONFIG_X`` block. Otherwise start the test with this skip:

.. code-block:: c

   if (!IS_ENABLED(CONFIG_X)) {
           ztest_test_skip();
   }

The documentation tools of the workspace read the Kconfig condition of a
test from these two patterns. For a test that applies only if ``CONFIG_X``
is not enabled, use ``#ifndef CONFIG_X``.

Without ``CONFIG_MULTITHREADING``, a failed ``zassert_*()`` expands to
``return;``. Thus a helper that returns a value cannot use ``zassert_*()``.
Use ``ztest_test_fail()`` there.

Add a test application
**********************

#. Copy the ``sem`` directory and change the included kernel source file.
   Delete the copied ``inventory`` directory.
#. Build the application. For each missing kernel-internal header, add a
   shadow header to ``common/include``. Copy a pure helper of the real
   header between the markers of `Pure helpers stay real`_. Make every
   other function a fake.
#. For each undefined function, add a fake to a fake group. For undefined
   data (for example ``_kernel``), add a definition to the group of the
   source file that defines it.
#. For each ``#include <zephyr/syscalls/<name>_mrsh.c>`` of the unit, add a
   stub to ``common/include/zephyr/syscalls`` with
   ``KERNEL_UNIT_SYSCALL_STUB(z_vrfy_<name>)``.
#. If the unit defines a new object type, add its iterable section to
   ``common/kernel_unit.ld`` (see `Linker sections`_).
#. Add one scenario to ``testcase.yaml`` for each configuration option
   that the unit examines with ``#ifdef``.
#. Add the Doxygen groups of the unit (see `Doxygen comments`_): the file
   group with ``@ingroup kernel_unit_tests``, one group for each public
   function of the kernel source file, in the order of the file, and the
   static group. Put each test in the group of its function under test.
   Put the marker ``@kunit_interfaces`` into the file group (see `Test
   doubles in the specification`_).
#. Add the test sources to the ``INPUT`` of
   ``safety/doc/dox/kernel-unit-testspec/Doxyfile.in``. Build the target
   ``dox-kernel-unit-testspec`` and make sure that it gives no warning.
#. Add the application to the table in `Test applications`_ and its
   options to `Configurations`_.
#. Make the expected sets of the test inventory (see `Regenerate the
   expected sets`_). Review each file.

Known limits
************

- On an aarch64 host, GCC knows neither ``-m32`` nor ``-m64``.
  ``cmake/kernel_unit.cmake`` removes these options. Thus the tests build
  for 64 bits, but the Kconfig configuration is for 32 bits
  (``CONFIG_64BIT`` is not set). On an x86 host, the tests build with
  ``-m32``.
- On a 64-bit build, some overflow checks cannot fail. For example,
  ``z_impl_k_stack_alloc_init()`` multiplies a ``uint32_t`` count by
  ``sizeof(stack_data_t)`` (8) in a 64-bit ``size_t``. The tests of these
  checks call ``ztest_test_skip()`` on a 64-bit build, and the branches
  stay uncovered. On an x86 host (``-m32``), the tests run.
- Tracing is real and empty (``CONFIG_TRACING`` is not set). The tracing
  hooks are not fakes yet.
- ``k_object_init()`` is a fake only with ``CONFIG_USERSPACE``. Without
  it, the function is static inline and empty in ``zephyr/sys/kobject.h``.
- The unittest build compiles at ``-O0``. A ``LOG_DBG()`` below the log
  level of its module still has code and refers to the log backend and to
  the constant data of the log module. A unit with ``LOG_DBG()`` links the
  fake group ``log_minimal``, and the group ``init`` defines the log module
  ``os``. The dead code of the log macro after the minimal-mode ``break``
  (``if (!string_ok)``) gives 2 branches and 2 condition outcomes on each
  ``LOG_DBG()`` line that no test can cover. Twister does not count
  branches on ``LOG_*()`` lines, but plain gcovr and the condition
  coverage do.
- The fakes ``unit_syscall_oops()`` (for ``K_OOPS()``),
  ``assert_post_action()`` and ``z_fatal_error()`` (for ``k_panic()``,
  also in the ISR refusal of ``z_pend_curr()``) return. The real functions
  do not return. After
  an oops or a failed assertion, the unit continues in the test. Thus a
  test cannot show that the unit stops. It shows the order: the oops or
  the assertion comes before the first change of the object. For a stop,
  see `Checks that do not return`_.
- ``K_SYSCALL_MEMORY()`` checks the size (``ptr + size >= ptr``) before
  ``Z_DETECT_POINTER_OVERFLOW()``. If the size check passes, the overflow
  check is always false. Thus each ``z_vrfy_*`` function with a user
  buffer has one branch that no test can cover. The real header has the
  same composition.
- The scenario with ``CONFIG_MP_MAX_NUM_CPUS`` > 1 is not SMP.
  ``_current`` is ``_kernel.cpus[0].current``, and spinlocks do not use
  atomics. The scenario shows the lock nesting, not a race.
- Twister counts no branches on the lines of ``__ASSERT()`` (option
  ``--exclude-branches-by-pattern`` of gcovr). The branches of
  ``CHECKIF()`` count also with ``CONFIG_ASSERT_ON_ERRORS``.
- A unit can depend on a header that a real kernel-internal header
  includes, but a shadow header does not. For example, ``mem_slab.c``
  calls ``size_mul_overflow()`` without an include of
  ``zephyr/sys/math_extras.h``. The real ``ksched.h`` includes it through
  ``priority_q.h``. The test source includes the missing header before the
  unit.
- With ``CONFIG_OBJ_CORE`` and without ``CONFIG_OBJ_CORE_FIFO`` (or
  ``CONFIG_OBJ_CORE_LIFO``), ``k_fifo_init()`` (or ``k_lifo_init()``) does not
  compile. The macro uses the member ``obj_core``, which the structure has
  only with the second option. The ``queue`` scenarios therefore enable
  both options or neither. This is a defect of ``zephyr/kernel.h``, not of
  the harness.
