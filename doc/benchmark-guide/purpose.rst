Purpose and scope
=================

What the suite measures
-----------------------

The suite measures the distributions of interrupt latencies and
scheduling latencies of Zephyr. A distribution shows the floor, the modes
and the tail of a latency. An average hides the tail, and a safety
argument needs the tail. For this reason, each app records every sample
in a histogram on the target, not only a mean.

All times are in core cycles. The stimulus timer runs at the core clock,
so one timer count is one core cycle (see :doc:`hardware`).

The suite has four measurement points:

.. list-table::
   :header-rows: 1
   :widths: 8 20 30 30 12

   * - ID
     - Quantity
     - Start
     - Stop
     - App
   * - M1
     - IRQ to ISR
     - The stimulus edge on the pin (hardware time stamp)
     - The first time stamp in the ISR (or in the GPIO callback)
     - ``irq_latency``
   * - M2
     - ISR to thread
     - The time stamp in the ISR, before the ISR wakes a thread
     - The time stamp of the woken thread, after its wait call returns
     - ``wake_latency``
   * - M3
     - Thread to thread
     - The time stamp before the wake call of the giver thread
     - The time stamp of the taker thread, after its wait call returns
     - ``thread_latency``
   * - M4
     - Time with interrupts locked
     - The lock (nesting 0 to 1)
     - The unlock (nesting 1 to 0)
     - Not implemented

M4 is a plan. It needs a hook in the interrupt lock path of Zephyr. No app
of the suite measures M4 today. The tail of M1 gives an indirect lower
limit of the longest locked section that the stimulus hit.

Why the stimulus comes from hardware
------------------------------------

If the measured software makes the stimulus itself, the CPU is never in
a critical section at that moment. Then the measurement shows only the
best case. The ``loopback_check`` app is an example: its main thread sets
the pin and then waits in a busy loop, so all its samples have the same
value.

For this reason, the apps of the suite use a hardware timer as the
stimulus. The timer sets the pin at a programmed time, which is
asynchronous to the software. The edge can come while the kernel holds a
lock, while the system timer ISR runs, or while the CPU sleeps. The time
stamp of the edge is the compare value of the timer, so it does not
depend on software.

Terms
-----

This guide uses these terms with one meaning each:

App
   A Zephyr application in a folder of ``tests/benchmarks/``, for example
   ``irq_latency``.

Variant
   One build of an app with a set of Kconfig options, for example the
   ``direct`` IRQ path of ``irq_latency``.

Sample
   One latency value in core cycles.

Tree
   A pinned set of source repositories (Zephyr and its modules), declared
   in ``trees.yaml``.

Experiment
   A YAML file in ``experiments/``. It names an app, one or more trees,
   and a list of points.

Point
   One build configuration of an experiment, with an ID.

Repetition
   One flash and one capture of the serial output of a point.

Run
   One execution of ``scripts/run.py`` for one experiment. A run makes one
   result folder.
