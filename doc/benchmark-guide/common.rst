Common modules
==============

The folder ``common/`` has the code that all measurement apps share.

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - File
     - Content
   * - ``latbench.cmake``
     - Adds the common code to the ``app`` target. See
       :ref:`benchguide-latbench-cmake`.
   * - ``Kconfig``
     - The common Kconfig options (see :doc:`kconfig`).
   * - ``include/latbench/hist.h``, ``src/hist.c``
     - Histogram and phase histogram
   * - ``include/latbench/stim.h``, ``src/stim.c``
     - TIM2 stimulus, static check, EXTI0 set-up, tick phase
   * - ``include/latbench/load.h``, ``src/load.c``
     - Load generators: threads and timers
   * - ``include/latbench/meta.h``, ``src/meta.c``
     - Metadata lines and the end marker
   * - ``conf/lean.conf``
     - Kconfig fragment: ``TIMESLICING=n``, ``HW_STACK_PROTECTION=n``,
       ``MPU_STACK_GUARD=n``, ``SPEED_OPTIMIZATIONS=y``
   * - ``conf/use_switch.conf``
     - Kconfig fragment: ``USE_SWITCH=y`` (``arch_switch`` at the exception
       exit, not PendSV)
   * - ``clocks/*.overlay``
     - Core clock overlays (see :doc:`hardware`)

To use a Kconfig fragment, add it to ``conf_files`` of a point (see
:ref:`benchguide-experiment-file`).

.. _benchguide-hist:

Histogram
---------

``struct lat_hist`` records the samples of one quantity. Define it with
``LAT_HIST_DEFINE(var, name)``. The name is the key of the histogram in
the output and in the host tools. Thus each histogram of an app must have
its own name.

``lat_hist_add()`` adds one sample. It updates ``count``, ``sum``, ``min``
and ``max``, and then puts the value into one of three bin ranges:

#. Fine bins. Each value from 0 to ``LATBENCH_HIST_BINS - 1`` has a bin of
   its own (1-cycle bins).
#. Coarse bins. These are optional. If ``LATBENCH_HIST_COARSE_BINS`` is
   not 0, the next values go into coarse bins. Each coarse bin is
   2\ :sup:`LATBENCH_HIST_COARSE_SHIFT` cycles wide.
#. Overflow. A larger value goes into the log2 bin of its magnitude
   (``ovf_log2[e]`` for 2\ :sup:`e` <= value < 2\ :sup:`e+1`), and
   ``overflow`` counts it. ``max`` records the largest value exactly.

The coarse bins let a histogram cover long latencies with less RAM. For
example, 2048 fine bins and 2048 coarse bins of 32 cycles cover 0 to 67583
cycles with the RAM of 4096 fine bins.

A value of 2\ :sup:`31` or more is a negative difference: the measurement
point ran before the programmed edge time. Such a value goes into the
overflow bin 31. ``scripts/plot.py`` leaves these values out and gives
their number in the label.

``lat_hist_add()`` is safe in an ISR. Two contexts must not add to the same
histogram at the same time. ``lat_hist_print()`` prints the histogram (see
:doc:`output`).

.. _benchguide-phase-hist:

Phase histogram
---------------

``struct lat_phase`` records samples by the tick phase of their edge.
Define it with ``LAT_PHASE_DEFINE(var, name)``. Call
``lat_phase_init(p, stim_tick_period())`` before the first
``lat_phase_add()``.

The phase histogram divides the tick into ``LATBENCH_PHASE_BINS`` bins of
equal width. Bin ``b`` holds the phases from ``b * period / BINS`` to
``(b + 1) * period / BINS``. For each bin, it records the count, the
minimum, the maximum and the sum of the samples. Thus it shows the share
of the edges in each part of the tick and the latency in each part.

``lat_phase_print()`` prints the phase histogram.

Stimulus
--------

``common/include/latbench/stim.h`` declares the stimulus interface:

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Function
     - Purpose
   * - ``stim_init()``
     - Sets up TIM2, the PA10 pin function and the PB0 input. Finds the
       tick period and prints the stimulus settings as ``LAT META``. Sleeps
       for one tick (phase check).
   * - ``stim_static_check()``
     - Drives PA10 low and high and reads PB0. Prints
       ``static_check=ok`` or ``static_check=fail``.
   * - ``stim_exti0_init()``
     - Routes PB0 to EXTI line 0, rising edge, and enables the line. It
       does not enable the NVIC IRQ.
   * - ``stim_now()``
     - Reads ``TIM2->CNT``.
   * - ``stim_edge()``, ``stim_edge_phase()``
     - The time stamp and the tick phase of the current edge.
   * - ``stim_fired()``
     - True if TIM2 reached the compare value since the last arm.
   * - ``stim_arm(now)``
     - Programs the next edge. Read ``stim_edge()`` and ``stim_edge_phase()``
       of the current edge before this call.
   * - ``stim_stop()``
     - Drives PA10 low and programs no new edge.
   * - ``stim_tick_period()``
     - The length of a kernel tick in cycles.
   * - ``stim_print_stats()``
     - Prints ``stim_overruns``, the clock drift and the phase check at the
       end of the run.

:doc:`hardware` describes the edge, the stimulus modes and the tick
phase.

.. _benchguide-static-check:

Static check
~~~~~~~~~~~~

``stim_static_check()`` sets channel 4 to "forced inactive" and to "forced
active", with 10 microseconds of wait after each change, and reads PB0
each time. The check passes if PB0 reads 0 and then 1. If the check
fails, each measurement app prints
``LAT ERROR static check failed (wire D2 -> A3?)`` and stops.

Load generators
---------------

``common/src/load.c`` starts a load that the Kconfig options
``LATBENCH_LOAD_*`` set. All random values come from fixed seeds, so each
run starts the same load. The load has its own random generator, so the
load does not change the sequence of the stimulus. An app calls
``load_start()`` after ``stim_init()`` and before the first ``stim_arm()``.
``load_print()`` stops the load timers and prints the load settings and
counters.

Load threads
~~~~~~~~~~~~

``LATBENCH_LOAD_THREADS`` sets the number of load threads (0 to 64). The
Kconfig choice ``LATBENCH_LOAD_THREAD_KIND`` sets what each thread does:

``LATBENCH_LOAD_THREAD_BLOCKED`` (default)
   The thread waits forever on a semaphore of its own. Thus it stays in a
   wait queue for the whole run. Priority: ``LATBENCH_LOAD_THREAD_PRIO``.

``LATBENCH_LOAD_THREAD_SLEEPER``
   The thread sleeps for a random time in [``LATBENCH_LOAD_SLEEP_MIN_MS``,
   ``LATBENCH_LOAD_SLEEP_MAX_MS``], in a loop. Each sleep adds a timeout
   to the timeout queue, and each wake is a timer expiry and a switch.
   Priority: ``LATBENCH_LOAD_THREAD_PRIO``. ``load_sleeper_wakes`` counts
   the wakes (approximately, the counter is not atomic).

``LATBENCH_LOAD_THREAD_BUSY``
   The thread runs a busy loop at the lowest application priority. All
   busy threads have the same priority. With ``CONFIG_TIMESLICING=y``, they
   change at each expiry of a time slice.

Load timers
~~~~~~~~~~~

``LATBENCH_LOAD_TIMERS`` sets the number of ``k_timer`` objects (0 to 512).
The Kconfig choice ``LATBENCH_LOAD_TIMER_KIND`` sets their kind:

``LATBENCH_LOAD_TIMER_PERIODIC`` (default)
   Each timer gets a random period in [``LATBENCH_LOAD_TIMER_MIN_MS``,
   ``LATBENCH_LOAD_TIMER_MAX_MS``] and a random first expiry. The expiry
   function runs in the system timer ISR. Each restart inserts a timeout
   into the timeout queue.

``LATBENCH_LOAD_TIMER_FAR``
   Each timer is a one-shot timer that expires one hour (plus ``i`` ticks)
   after the start. The timers stay in the timeout queue for the whole run
   and do not expire. Only the length of the queue changes.

The expiry function records its own tick phase in the phase histogram
``tmr``. The value of each sample is the phase itself. Thus ``tmr`` shows
where in the tick the system timer ISR runs.

.. _benchguide-meta:

Metadata
--------

``lat_meta_print(app, variant)`` prints ``LAT BEGIN`` and then the metadata
of the build. The metadata names the app, the variant, the Zephyr version
and the revision of the benchmark sources (``bench_rev``). It also gives
the board, the core clock, the tick rate and the number of samples. Then it prints one ``LAT CFG`` line with
the Kconfig options that change latency (see :ref:`benchguide-lat-cfg`).

``lat_meta_kv(key, value)`` prints one more metadata line.
``lat_done()`` prints ``LAT DONE``. The host stops the capture at this line.

Each measurement app also prints ``dbgmcu_cr_at_boot``: the value of
``DBGMCU->CR`` before the app cleared it (see :doc:`pitfalls`).

.. _benchguide-latbench-cmake:

Build integration
-----------------

The ``CMakeLists.txt`` of an app includes ``common/latbench.cmake``. This
file does these steps:

- It adds ``common/include`` to the include path, and ``hist.c`` and
  ``meta.c`` to the ``app`` target.
- It defines ``LATBENCH_SRC_REV``, the revision of the benchmark sources.
  ``run.py`` gives the value with ``-DLATBENCH_SRC_REV=<rev>``, because it
  builds from a snapshot without ``.git``. A manual build gets the value
  from ``git describe --always --abbrev=12 --dirty``. If git gives no
  value, the value is ``unknown``.
- If the app sets ``LATBENCH_STIM`` before the include, it adds ``stim.c``
  and ``load.c``. The load timers need the tick period from the stimulus,
  so ``load.c`` comes only with the stimulus.
