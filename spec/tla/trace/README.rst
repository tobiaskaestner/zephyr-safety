.. Copyright (c) 2026 inovex GmbH
.. SPDX-License-Identifier: Apache-2.0

Trace checks
############

A trace check shows that a recorded run of the real code is a behavior of a
contract module (the relation *abstracts*). Today one object has a trace
check: k_sem (``KSemTrace.tla`` against ``objects/KSem.tla``).

The parts:

- The trace hook of the unit tests
  (``tests/kernel/unit/common/include/kernel_unit_trace.h``, fake group
  ``trace``, ``CONFIG_KERNEL_UNIT_TRACE``). The sem app has three trace
  scenarios: ``kernel.unit.sem.trace``, ``.trace_poll`` and
  ``.trace_no_runtime_checks``.
- The recorded traces, one NDJSON file for each test and configuration:
  ``ksem/<config>/<test>.ndjson``. They are in the repository, so that the
  check runs without a build, and a change of the code or of a test shows as
  a diff of a trace.
- ``KSemTrace.tla``: reads one trace at run time and checks it (see its
  header).
- ``expected.txt``: the expected verdict of each trace.
- ``../tools/check_traces.py``: ``record`` writes the traces from a twister
  run, ``check`` runs TLC on each trace and compares the verdicts,
  ``coverage`` lists the branches of the step actions that the accepted
  traces reach.
- ``../tools/ksem_trace_mutants.py``: the code mutants of ``kernel/sem.c``
  against the unit tests and the trace check.

.. code-block:: console

   west twister -T tests/kernel/unit/sem -p unit_testing -O build/twister-sem
   spec/tla/tools/check_traces.py record build/twister-sem
   export TLA2TOOLS=/path/to/tla2tools.jar
   spec/tla/tools/check_traces.py check

(In a worktree of the safety repository, give twister also
``-x=ZEPHYR_MODULES=<worktree>``.)

The record format
*****************

Each line is one JSON object. The field ``ev`` gives its kind. A thread is
``t1``, ``t2``, ... (the index in the reference fake of the scheduler, or
``t1`` for the test thread without it), the ISR is ``i1``, an object is
``s1``, ``s2``, ... in the order of its first call.

.. list-table::
   :header-rows: 1
   :widths: 12 40 48

   * - ``ev``
     - Fields
     - Meaning
   * - ``test``
     - ``suite``, ``name``, ``config`` (``poll``, ``rtc``, ``assert``)
     - The start of a test (a ztest rule).
   * - ``sem``
     - ``id``, ``init``; ``count``, ``limit`` if ``init``
     - An object at its first call. ``init`` is false if the first call is
       an init: the memory has no value then.
   * - ``setup``
     - ``ref``; with ``ref``: ``current``, ``preempt_ok``, ``threads``
       (``id``, Zephyr ``prio``, ``state``, ``on``, ``stamp``,
       ``ready_seq``, ``armed``, ``deadline``, ``armed_seq``, ``ret``)
     - The state of the scheduler before the first call. Without the
       reference fake, only ``ref`` false.
   * - ``call``
     - ``op`` (``init``, ``give``, ``take``, ``reset``), ``actor``, ``obj``;
       ``timeout`` (``NO_WAIT``, ``FOREVER``, ``TICKS``); ``args``
     - The start of an API call (a wrapper in the test source).
   * - ``fake``
     - ``fn``, ``obj``, ``arg``, ``ret``, ``res``; ``thread``, ``data``,
       ``bad``
     - A call of the unit into the lock or the scheduler: the function,
       the object, the argument that the contract fixes (the swap return
       value, the timeout as -1 or 1, the poll state), the return value
       (1 or 0 for a bool), the count at the call, the woken thread (with
       the reference fake), ``data`` 1 if swap data was given, ``bad`` if
       the hook found a release of another lock or with another key.
   * - ``pend_ret``
     - ``actor``, ``obj``, ``ret``
     - ``z_pend_curr()`` returns to the waiting thread.
   * - ``ret``
     - ``op``, ``actor``, ``obj``, ``ret`` (1: no return value);
       ``count``, ``limit`` if the object has a value
     - The end of an API call.
   * - ``env``
     - ``op`` (``ThreadTimeout``, ``Abort``), ``thread``
     - A step of the environment that the reference fake runs.
   * - ``panic``
     - ``cause``
     - The fake ``z_pend_curr()`` refused a call in an ISR (the real
       scheduler panics). The hook writes no more lines for this test.
   * - ``end``
     -
     - The end of a test.

The ``fake`` lines are the call record ``obs.calls`` of ``lib/Waitable.tla``:
the trace check compares them one by one with the calls of the model step.
