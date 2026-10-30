Output format
=============

The measurement :term:`apps <App>` print their results on the console as text lines
that start with ``LAT``. The functions in ``common/src/hist.c`` and
``common/src/meta.c`` print most of the lines.
``scripts/benchmarks/latbench.py`` parses them. Lines without the
``LAT`` prefix (for example the Zephyr boot banner) are ignored.

Line types
----------

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Line
     - Meaning
   * - ``LAT BEGIN``
     - Start of a :term:`run` on the target. The parser starts a new record at each
       ``BEGIN`` and keeps only the last record of a log.
   * - ``LAT META <key>=<value>``
     - One metadata value. The value is the text after the first ``=``.
   * - ``LAT CFG <SYM>=<0|1> ...``
     - The state of the Kconfig options that change latency, on one line
       (see :ref:`benchguide-lat-cfg`).
   * - ``LAT ERROR <text>``
     - An error. After a set-up error, the app stops and ``LAT DONE``
       follows. After a phase error (``LAT ERROR phase ...``), the app
       continues with an empty phase histogram.
   * - ``LAT HIST <name> n=<n> min=<min> max=<max> mean=<m>.<mm> overflow=<k> invalid=<i>``
     - Start of a histogram. The mean has two decimal places. ``n``,
       ``min``, ``max`` and ``mean`` do not include the invalid :term:`samples <Sample>`.
       ``invalid`` is the last field, so that an old parser can read the
       line. A log from before this field has the invalid samples in ``n``,
       ``max``, ``mean`` and in the overflow bin 31.
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
   * - ``LAT TAIL <name> n=<rows> seen=<k> min_cyc=<c> exc_min=<e> exc_max=<e> fields=<f1>,<f2>,...``
     - Start of a witness table of the histogram ``<name>``
       (``LATBENCH_TAIL``, see :doc:`../explanation/tail-witnesses`). ``seen``
       counts the samples of ``min_cyc`` or more. ``exc_min`` and ``exc_max``
       are the smallest and the largest exception cycles of all windows.
       ``fields`` names the values of each row, in their order.
   * - ``LAT TW <value> ...``
     - One row of a witness table, one value per field. ``pc`` and ``icsr``
       are hexadecimal (``0x...``), all others decimal. The rows are not in
       order.
   * - ``LAT DONE``
     - End of the output. The host stops the capture at the first
       ``LAT DONE`` after a ``LAT BEGIN``.

The order of the lines in a measurement app is:

#. ``LAT BEGIN``, the build metadata, ``LAT CFG``.
#. The metadata of the app and of the stimulus set-up, and the static
   check.
#. After the last sample: ``spurious_edges``, the stimulus counters, the
   load settings and counters (with the phase histogram ``tmr`` if there
   are load timers), the histograms, the phase histograms. With
   ``LATBENCH_SWTRIG``: then ``sw_triggers`` and the ``_sw`` histograms.
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
   LAT META irq_path=direct
   LAT META background=idle
   LAT META debug_reg_at_boot=0x00000000
   LAT META poll_ms=100
   LAT META port=nucleo_g474re/tim2_ch4-exti0
   LAT META stim_timer_hz=170000000
   LAT META sys_timer_hz=170000000
   LAT META stim_mode=random
   LAT META stim_us=200..1000
   LAT META stim_seed=0x2545f491
   LAT META tick_period_cyc=17000
   LAT META tick_phase_check=...
   LAT META static_check=ok
   ...
   LAT HIST irq n=100000 min=... max=... mean=... overflow=0 invalid=0
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
     - Core clock (``port_core_hz()``) and tick rate
   * - ``samples``
     - all
     - ``LATBENCH_SAMPLES``
   * - ``code_place``
     - all
     - ``flash``, ``flash-pad`` or ``ram`` (choice ``LATBENCH_CODE_PLACE``).
       A log without this line comes from a build before the choice: its
       code is in flash.
   * - ``code_pad``, ``code_pad_at``
     - all
     - ``LATBENCH_CODE_PAD_BYTES`` and the address of the pad function
   * - ``data_pad``, ``data_pad_at``
     - all, with ``LATBENCH_DATA_PAD``
     - ``LATBENCH_DATA_PAD_BYTES`` and the address of the data pad
   * - ``msp``
     - Cortex-M, with ``LATBENCH_DATA_PAD`` or ``LATBENCH_TAIL``
     - The top of the interrupt stack (MSP in thread mode). It shows where
       the build put the stacks (see :ref:`benchguide-data-placement`)
   * - ``code_ram_region``, ``code_ram_text``
     - all, with ``LATBENCH_CODE_RAM``
     - ``LATBENCH_CODE_RAM_REGION``, and the start and the end of the
       relocated code (``0x10000000..0x10002dd8``). ``code_pad_at`` is the
       start, plus 1 (the Thumb bit).
   * - ``timeslice_ms``
     - all
     - ``CONFIG_TIMESLICE_SIZE``, if it exists
   * - ``debug_reg_at_boot``
     - all
     - The debug register that ``port_debug_reset()`` found. The format
       depends on the port: ``0x...`` (``DBGMCU->CR``), ``dhcsr=0x...``
       (Nordic), ``n/a clpcr=0x...`` (RT1060).
   * - ``poll_ms``
     - all
     - ``LATBENCH_POLL_MS``
   * - ``irq_path``, ``background``
     - ``irq_latency``
     - Interrupt path and background
   * - ``wake_isr``, ``primitive``, ``background``, ``wake_prio``
     - ``wake_latency``
     - ISR kind, kernel object, background, priority of the woken thread
   * - ``primitive``, ``t2t_mode``, ``giver_prio``, ``taker_prio``
     - ``thread_latency``
     - Primitive, preempt mode, priorities of giver and taker
   * - ``taker_missed``
     - ``thread_latency``
     - Wakes for which the taker did not run exactly once
   * - ``port``
     - stimulus
     - Name of the :term:`board port`, for example
       ``nucleo_g474re/tim2_ch4-exti0``
   * - ``stim_timer_hz``, ``sys_timer_hz``
     - stimulus
     - Clock of the stimulus timer and of the system timer
   * - ``stim_mode``
     - stimulus
     - ``random`` or ``fixed``
   * - ``stim_us``
     - stimulus
     - Limits of the random stimulus (``<min>..<max>``)
   * - ``stim_seed``
     - stimulus
     - Seed of the random stimulus (``LATBENCH_STIM_SEED``). A log without
       it is from before the option and has the seed ``0x2545f491``
   * - ``stim_period_cyc``
     - stimulus
     - Period of the fixed stimulus in counts of the stimulus timer
   * - ``tick_period_cyc``
     - stimulus
     - Length of a tick in system timer cycles
   * - ``tick_phase_check``, ``tick_phase_check_end``
     - stimulus
     - Phase check at the start and at the end (see :doc:`../explanation/method`)
   * - ``static_check``
     - stimulus
     - ``ok`` or ``fail``
   * - ``spurious_edges``
     - all
     - Response interrupts without a compare match of the stimulus timer.
       With ``LATBENCH_SWTRIG``, the software samples do not count
   * - ``stim_trigger``
     - ``LATBENCH_SWTRIG``
     - ``gpio+sw``: the app alternates edges and software triggers. A log
       without this key has edges only
   * - ``sw_trigger``, ``sw_trigger_irqn``, ``sw_trigger_prio``
     - ``LATBENCH_SWTRIG``
     - The kind of the software trigger (``nvic-stir``), the IRQ that it
       pends (the response IRQ), the priority of the trigger thread
   * - ``sw_read_cyc``
     - ``LATBENCH_SWTRIG``
     - The smallest difference of two back-to-back reads of the stimulus
       timer. It is the bound of the offset in the hardware path (see
       :ref:`benchguide-method-swtrig`)
   * - ``tail_n``, ``tail_min_cyc``
     - ``LATBENCH_TAIL``
     - ``LATBENCH_TAIL_N`` and ``LATBENCH_TAIL_MIN_CYC``
   * - ``tail_cost_empty_cyc``, ``tail_cost_mark_cyc``,
       ``tail_cost_reject_cyc``, ``tail_cost_store_cyc``,
       ``tail_cost_full_cyc``
     - ``LATBENCH_TAIL``
     - The cost of the witness calls in counts of the stimulus timer, with
       the interrupts locked, the smallest of 64 tries: two time stamps
       with nothing between, the mark, an add that the table rejects, an
       add that fills the last free row (with the scan of the full
       table), an add that replaces a row. Each value includes one empty
       pair (``tail_cost_empty_cyc``)
   * - ``sw_triggers``
     - ``LATBENCH_SWTRIG``
     - Number of software triggers, warm-up included. It comes after the
       edge histograms, before the ``_sw`` histograms
   * - ``irq_scenario``, ``scen_lead_us``
     - ``irq_latency``, a scenario other than the entry
     - The scenario (``unlock``, ``nested``, ``exit``, ``burst``) and the
       time before the edge at which the main thread starts the part of
       the sample that needs the edge (see
       :ref:`benchguide-irq-latency-scenarios`)
   * - ``unlock_hold_us``, ``nested_prio``, ``spare_irqn``, ``burst_len``
     - the scenario
     - ``LATBENCH_UNLOCK_HOLD_US``, ``LATBENCH_NESTED_PRIO`` and the spare
       IRQ of the port, ``LATBENCH_BURST_LEN``
   * - ``scen_missed``, ``scen_timeouts``
     - a scenario other than the entry
     - Samples that did not fit the scenario and were not recorded (the
       edge came before the lock, or did not meet the lower-priority ISR),
       and waits that took more than 20 ms. Both must be 0
   * - ``stim_overruns``
     - stimulus
     - Edges that the fixed stimulus armed too late for its period
   * - ``stim_late``
     - stimulus
     - Edges that ``stim_arm()`` moved, because the edge time was less than
       1000 counts after the fresh count (see :doc:`../explanation/method`)
   * - ``clock_elapsed_cyc``, ``clock_drift_cyc``
     - stimulus
     - Clock drift check (see :doc:`../explanation/method`). ``clock_drift_cyc`` is
       ``n/a`` if the two clocks are not the same.
   * - ``load_threads``, ``load_timers``
     - load
     - Number of load threads and load timers
   * - ``load_thread_kind``, ``load_sleep_ms``, ``load_sleeper_wakes``
     - load
     - Kind of the load threads, sleep limits, number of wakes
   * - ``load_timer_kind``, ``load_timer_ms``, ``load_timer_seed``,
       ``load_timer_expiries``
     - load
     - Kind of the load timers, period limits, seed
       (``LATBENCH_LOAD_TIMER_SEED``), number of expiries. A log without
       ``load_timer_seed`` used the seed 0x6a09e667.
   * - ``systick_prio``
     - load
     - SysTick priority in the NVIC, in the numbers of ``IRQ_CONNECT()``
       (only with ``CONFIG_CORTEX_M_SYSTICK``)

M4 output
---------

``irqmask_print()`` prints the calibration and the totals as ``LAT META``
lines (``m4_window_cyc``, ``m4_sections``, ``m4_masked_cyc``,
``m4_isr_cyc``, ``m4_unmatched_end``, ``m4_begin_open``), then the table:

.. code-block:: text

   LAT M4 BEGIN sites=64 used=37 dropped=0 bins=112 sub_bits=3
   LAT M4SITE m4.mask.e15.08002f19 kind=mask ipsr=15 pc=0x08002f19 end_pc=0x08003001 n=.. sum=.. min=.. max=..
   LAT HIST m4.mask.e15.08002f19 n=.. min=.. max=.. mean=.. overflow=0 invalid=0
   LAT BIN 14 3
   LAT CBIN 2048 17 256
   LAT END m4.mask.e15.08002f19
   ...
   LAT M4 END

The name of a site is ``m4.<kind>.<ctx>.<pc>``: ``ctx`` is ``t`` for a
thread or ``e<n>`` for exception number n (14 PendSV, 15 SysTick, 16 + n
IRQ n). The ``LAT HIST`` blocks have the normal format, so
``latbench.py summary`` also reads them. ``m4_unmatched_end`` counts an
end without an open section, ``m4_begin_open`` a start while a section is
open. Both must be 0 after the start.
