Common modules
==============

The folder ``common/`` has the code that all measurement apps share.

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - File
     - Content
   * - ``latbench_board.cmake``
     - Selects the board port. See :ref:`benchguide-latbench-cmake`.
   * - ``latbench.cmake``
     - Adds the common code to the ``app`` target. See
       :ref:`benchguide-latbench-cmake`.
   * - ``Kconfig``
     - The common Kconfig options (see :doc:`kconfig`).
   * - ``include/latbench/hist.h``, ``src/hist.c``
     - Histogram and phase histogram
   * - ``include/latbench/stim.h``, ``src/stim.c``
     - Stimulus, static check, response IRQ set-up, tick phase
   * - ``include/latbench/port.h``
     - The contract of a board port (see :doc:`boards`)
   * - ``boards/<board>/``
     - One board port for each board (see :doc:`boards`)
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

To use a Kconfig fragment, add it to ``conf_files`` of a point (see
:ref:`benchguide-experiment-file`).

.. _benchguide-hist:

Histogram
---------

``struct lat_hist`` records the samples of one quantity. Define it with
``LAT_HIST_DEFINE(var, name)``. The name is the key of the histogram in
the output and in the host tools. Thus each histogram of an app must have
its own name.

``lat_hist_add()`` adds one sample. If the value is 2\ :sup:`31` or more,
it only increments ``invalid`` (see below). Otherwise, it updates
``count``, ``sum``, ``min`` and ``max``, and then puts the value into one of
three bin ranges:

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

A value of 2\ :sup:`31` or more (``LAT_INVALID_MIN``) is a negative
difference: the measurement point ran before the programmed edge time.
It is not a latency. The histogram counts it only in ``invalid``. Thus
``count``, ``sum``, ``min``, ``max`` and the bins do not include it.
``lat_phase_add()`` ignores such a value.

``lat_hist_add()`` is safe in an ISR. Two contexts must not add to the same
histogram at the same time. ``lat_hist_print()`` prints the histogram (see
:doc:`output`).

.. _benchguide-phase-hist:

Phase histogram
---------------

``struct lat_phase`` records samples by the tick phase of their edge.
Define it with ``LAT_PHASE_DEFINE(var, name)``. Call
``lat_phase_init(p, stim_tick_period())`` before the first
``lat_phase_add()``. While the period is 0, ``lat_phase_add()`` does
nothing.

``lat_phase_init()`` refuses a period that is more than
``LAT_PHASE_PERIOD_MAX`` (``UINT32_MAX / LATBENCH_PHASE_BINS``), because the
bin calculation must fit in 32 bits. Then it prints
``LAT ERROR phase <name> period=<p> is larger than <max>`` and sets the
period to 0, so that the phase histogram stays empty.

The phase must be less than the period. ``lat_phase_add()`` does not
examine this condition (a known gap, see :doc:`unit-tests`).

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
     - Configures the response pin as an input and calls
       ``port_stim_init()``. Finds the tick period and prints the stimulus
       settings as ``LAT META``. Sleeps for one tick (phase check).
   * - ``stim_static_check()``
     - Drives the stimulus pin low and high (``port_stim_force()``) and
       reads the response pin. Prints ``static_check=ok`` or
       ``static_check=fail``.
   * - ``stim_resp_irq_init()``
     - Makes the response pin an interrupt on the rising edge, for an app
       with its own ISR. It does not enable the IRQ.
   * - ``STIM_RESP_IRQN``
     - The IRQ line of the response pin, for ``IRQ_CONNECT()`` and
       ``irq_enable()``.
   * - ``stim_resp_ack()``
     - Clears the pending flag of the response interrupt. An own ISR calls
       it.
   * - ``stim_now()``
     - Reads the counter of the stimulus timer.
   * - ``stim_edge()``, ``stim_edge_phase()``
     - The time stamp and the tick phase of the current edge.
   * - ``stim_fired()``
     - True if the stimulus timer reached the compare value since the last
       arm.
   * - ``stim_arm(now)``
     - Programs the next edge. Read ``stim_edge()`` and ``stim_edge_phase()``
       of the current edge before this call.
   * - ``stim_stop()``
     - Drives the stimulus pin low and programs no new edge.
   * - ``stim_tick_period()``
     - The length of a kernel tick in system timer cycles.
   * - ``stim_print_stats()``
     - Prints ``stim_overruns``, the clock drift and the phase check at the
       end of the run.

:doc:`hardware` describes the edge, the stimulus modes and the tick
phase.

.. _benchguide-static-check:

Static check
~~~~~~~~~~~~

``stim_static_check()`` drives the stimulus pin low and then high
(``port_stim_force()``), with 10 microseconds of wait after each change,
and reads the response pin each time. The check passes if the response pin reads 0 and then 1. If the check
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
the board, the core clock, the tick rate and the number of samples. Then
it prints one ``LAT CFG`` line with the Kconfig options that change latency
(see :ref:`benchguide-lat-cfg`).

The core clock comes from ``port_core_hz()``. ``meta.c`` has a weak default
that returns the system timer clock. A board port gives the real value.

``lat_meta_kv(key, value)`` prints one more metadata line.
``lat_done()`` prints ``LAT DONE``. The host stops the capture at this line.

Each measurement app also prints ``debug_reg_at_boot``: the value that
``port_debug_reset()`` found in the debug register before it cleared it
(``DBGMCU->CR`` on the NUCLEO-G474RE, see :doc:`pitfalls`).

.. _benchguide-latbench-cmake:

Build integration
-----------------

The ``CMakeLists.txt`` of a measurement app includes two files.

``common/latbench_board.cmake`` comes before ``find_package(Zephyr)``,
because the port adds devicetree overlays and Kconfig fragments. It does
these steps:

- It takes the board name from ``BOARD`` without qualifiers and revision.
  For example, ``nrf54l15dk/nrf54l15/cpuapp`` gives ``nrf54l15dk``, and
  ``mimxrt1060_evk@C/mimxrt1062/qspi`` gives ``mimxrt1060_evk``.
- It includes ``common/boards/<board>/port.cmake``. If this file does not
  exist, the build stops with ``no board port for <board>``.
- If the app sets ``LATBENCH_RESP_IRQ_OWN`` before the include, the port
  also takes the response IRQ away from the GPIO driver.

``common/latbench.cmake`` comes after ``find_package(Zephyr)``. It does these
steps:

- It adds ``common/include`` to the include path, and ``hist.c`` and
  ``meta.c`` to the ``app`` target.
- It defines ``LATBENCH_SRC_REV``, the revision of the benchmark sources.
  ``run.py`` gives the value with ``-DLATBENCH_SRC_REV=<rev>``, because it
  builds from a snapshot without ``.git``. A manual build gets the value
  from ``git describe --always --abbrev=12 --dirty``. If git gives no
  value, the value is ``unknown``.
- If the app sets ``LATBENCH_STIM`` before the include, it adds the
  ``include`` folder and ``port.c`` of the port, ``stim.c`` and ``load.c``.
  The load timers need the tick period from the stimulus, so ``load.c``
  comes only with the stimulus. If ``latbench_board.cmake`` was not
  included, the build stops.
