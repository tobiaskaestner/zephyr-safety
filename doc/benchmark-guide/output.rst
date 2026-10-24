Output format
=============

The measurement apps print their results on the console as text lines
that start with ``LAT``. The functions in ``common/src/hist.c`` and
``common/src/meta.c`` print most of the lines. ``scripts/latbench.py``
parses them. Lines without the ``LAT`` prefix (for example the Zephyr boot
banner) are ignored.

Line types
----------

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Line
     - Meaning
   * - ``LAT BEGIN``
     - Start of a run on the target. The parser starts a new record at each
       ``BEGIN`` and keeps only the last record of a log.
   * - ``LAT META <key>=<value>``
     - One metadata value. The value is the text after the first ``=``.
   * - ``LAT CFG <SYM>=<0|1> ...``
     - The state of the Kconfig options that change latency, on one line
       (see :ref:`benchguide-lat-cfg`).
   * - ``LAT ERROR <text>``
     - The app stopped because of an error. ``LAT DONE`` follows.
   * - ``LAT HIST <name> n=<n> min=<min> max=<max> mean=<m>.<mm> overflow=<k>``
     - Start of a histogram. The mean has two decimal places.
   * - ``LAT BIN <cycles> <count>``
     - One 1-cycle bin. Only bins with a count other than 0 are printed.
   * - ``LAT CBIN <lower edge> <count> <width>``
     - One coarse bin, with its lower edge and its width in cycles.
   * - ``LAT OVF <e> <count>``
     - One log2 overflow bin: values from 2\ :sup:`e` to
       2\ :sup:`e+1` - 1.
   * - ``LAT END <name>``
     - End of a histogram or of a phase histogram.
   * - ``LAT PHASE <name> bins=<bins> period=<cycles>``
     - Start of a phase histogram. ``period`` is the tick period in cycles.
   * - ``LAT PB <bin> <count> <min> <max> <sum>``
     - One bin of a phase histogram. Only bins with a count other than 0
       are printed.
   * - ``LAT DONE``
     - End of the output. The host stops the capture at the first
       ``LAT DONE`` after a ``LAT BEGIN``.

The order of the lines in a measurement app is:

#. ``LAT BEGIN``, the build metadata, ``LAT CFG``.
#. The metadata of the app and of the stimulus set-up, and the static
   check.
#. After the last sample: ``spurious_edges``, the stimulus counters, the
   load settings and counters (with the phase histogram ``tmr`` if there
   are load timers), the histograms, the phase histograms.
#. ``LAT DONE``.

Example (shortened):

.. code-block:: text

   LAT BEGIN
   LAT META app=irq_latency
   LAT META variant=direct
   LAT META zephyr=...
   LAT META bench_rev=...
   LAT META board=nucleo_g474re
   LAT META core_hz=170000000
   LAT META ticks_per_sec=10000
   LAT META samples=100000
   LAT CFG USE_SWITCH=0 TIMESLICING=1 ...
   LAT META stim_mode=random
   LAT META stim_us=200..1000
   LAT META tick_period_cyc=17000
   LAT META tick_phase_check=...
   LAT META static_check=ok
   ...
   LAT HIST irq n=100000 min=... max=... mean=... overflow=0
   LAT BIN 41 ...
   LAT END irq
   LAT PHASE irq bins=64 period=17000
   LAT PB 0 ...
   LAT END irq
   LAT DONE

.. _benchguide-lat-cfg:

The CFG line
------------

The ``LAT CFG`` line gives 1 or 0 for each of these Kconfig options:
``USE_SWITCH``, ``TIMESLICING``, ``MPU_STACK_GUARD``,
``HW_STACK_PROTECTION``, ``SCHED_SIMPLE``, ``SCHED_SCALABLE``,
``SCHED_MULTIQ``, ``WAITQ_SCALABLE``, ``TIMEOUT_BACKEND_DLIST``,
``ZERO_LATENCY_IRQS``, ``TICKLESS_KERNEL``, ``FPU``, ``FPU_SHARING``,
``SPEED_OPTIMIZATIONS``, ``SIZE_OPTIMIZATIONS``, ``ASSERT``,
``SPIN_VALIDATE``, ``TRACING``, ``THREAD_RUNTIME_STATS``, ``PM``,
``USERSPACE``.

If ``CONFIG_TIMESLICE_SIZE`` exists, a ``LAT META timeslice_ms`` line
follows.

The ``.config`` in the result folder is the full record of a build. The
``CFG`` line is a short summary in the log itself.

Metadata keys
-------------

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - Key
     - Printed by
     - Meaning
   * - ``app``, ``variant``
     - all
     - App name and variant name
   * - ``zephyr``
     - all
     - Zephyr version (``BUILD_VERSION``, or the kernel version string)
   * - ``bench_rev``
     - all
     - Revision of the benchmark sources (``LATBENCH_SRC_REV``)
   * - ``board``
     - all
     - Board target
   * - ``core_hz``, ``ticks_per_sec``
     - all
     - Core clock and tick rate
   * - ``samples``
     - all
     - ``LATBENCH_SAMPLES``
   * - ``timeslice_ms``
     - all
     - ``CONFIG_TIMESLICE_SIZE``, if it exists
   * - ``dbgmcu_cr_at_boot``
     - all
     - ``DBGMCU->CR`` before the app cleared it
   * - ``poll_ms``
     - all
     - ``LATBENCH_POLL_MS``
   * - ``irq_path``, ``background``
     - ``irq_latency``
     - Interrupt path and background
   * - ``wake_isr``, ``primitive``, ``background``, ``wake_prio``
     - ``wake_latency``
     - ISR kind, kernel object, background, priority of the woken thread
   * - ``primitive``, ``t2t_mode``, ``giver_prio``
     - ``thread_latency``
     - Primitive, preempt mode, priorities of giver and taker
   * - ``taker_missed``
     - ``thread_latency``
     - Wakes for which the taker did not run exactly once
   * - ``stim_mode``
     - stimulus
     - ``random`` or ``fixed``
   * - ``stim_us``
     - stimulus
     - Limits of the random stimulus (``<min>..<max>``)
   * - ``stim_period_cyc``
     - stimulus
     - Period of the fixed stimulus in cycles
   * - ``tick_period_cyc``
     - stimulus
     - Length of a tick in cycles
   * - ``tick_phase_check``, ``tick_phase_check_end``
     - stimulus
     - Phase check at the start and at the end (see :doc:`hardware`)
   * - ``static_check``
     - stimulus
     - ``ok`` or ``fail``
   * - ``spurious_edges``
     - all
     - EXTI0 interrupts without a TIM2 compare match
   * - ``stim_overruns``
     - stimulus
     - Edges that the fixed stimulus armed too late
   * - ``clock_elapsed_cyc``, ``clock_drift_cyc``
     - stimulus
     - Clock drift check (see :doc:`hardware`)
   * - ``load_threads``, ``load_timers``
     - load
     - Number of load threads and load timers
   * - ``load_thread_kind``, ``load_sleep_ms``, ``load_sleeper_wakes``
     - load
     - Kind of the load threads, sleep limits, number of wakes
   * - ``load_timer_kind``, ``load_timer_ms``, ``load_timer_expiries``
     - load
     - Kind of the load timers, period limits, number of expiries

``thread_latency`` prints ``giver_prio`` and ``taker_prio`` on one ``META``
line. The parser takes the text after the first ``=`` as the value. Thus the
parsed value of ``giver_prio`` is ``2 taker_prio=1``, and there is no
separate ``taker_prio`` key.
