.. _benchguide-app-irq-latency:

``irq_latency`` (M1)
====================

The :term:`app` ``irq_latency`` is in ``tests/benchmarks/irq_latency/``.
This page is its documentation, beside its code.
:doc:`/explanation/apps` gives the frame that all measurement apps
share.

What it measures
----------------

The app measures the time from the edge to the first time stamp in the
interrupt path. The time stamp then arms the next edge. The Kconfig choice
``LATBENCH_IRQ_PATH`` selects the interrupt path:

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Kconfig option
     - Variant
     - Interrupt path
   * - ``LATBENCH_IRQ_PATH_STOCK`` (default)
     - ``stock``
     - The GPIO driver of Zephyr owns the response IRQ. The time stamp is
       in the user callback of the GPIO driver, after ``_isr_wrapper`` and
       the driver dispatch.
   * - ``LATBENCH_IRQ_PATH_WRAPPED``
     - ``wrapped``
     - An ISR of the app, connected with ``IRQ_CONNECT()``. It runs through
       ``_isr_wrapper``.
   * - ``LATBENCH_IRQ_PATH_DIRECT``
     - ``direct``
     - A direct ISR of the app (``IRQ_DIRECT_CONNECT()``).
   * - ``LATBENCH_IRQ_PATH_ZLI``
     - ``zli``
     - A direct zero-latency ISR. It selects ``CONFIG_ZERO_LATENCY_IRQS``.
       BASEPRI does not mask this IRQ, so kernel critical sections do not
       delay it.

.. timeline-viz:: irq-latency.tdl
   :name: benchguide-fig-irq-latency

   ``irq_latency`` with the ``stock`` path. The ``wrapped`` path starts its
   ISR after the exception entry, with ``_isr_wrapper``. The ``direct``
   and ``zli`` paths start their ISR after the exception entry, without
   ``_isr_wrapper``. Thus the ISR reads the counter earlier.

Known limit of the ``zli`` path: ``stim_arm()`` takes the tick phase of the
next edge from ``k_cycle_get_64()``. BASEPRI does not mask a zero-latency
IRQ, so the read can interrupt the timer driver in its locked section and
see an inconsistent count. Only the phase histogram is at risk, not the
latency.

Options, variants and output
----------------------------

The paths ``wrapped``, ``direct`` and ``zli`` connect an ISR of the app.
For these paths, the port must take the response IRQ away from the GPIO
driver. The steps are:

#. ``irq_latency/CMakeLists.txt`` sets ``LATBENCH_RESP_IRQ_OWN_IF`` to the
   three path symbols. ``common/latbench_board.cmake`` reads them from the
   CMake command line (``-DCONFIG_LATBENCH_IRQ_PATH_WRAPPED=y``, ``_DIRECT``
   or ``_ZLI``), or from the sysbuild cache if the build uses sysbuild
   (Twister does this for ``nrf54l15dk``). If one of them is ``y``, it sets
   ``LATBENCH_RESP_IRQ_OWN``.
#. The port then adds its ``resp_irq_own.overlay``. On the NUCLEO-G474RE,
   this overlay removes EXTI line 0 from the GPIO interrupt driver.
#. A ``BUILD_ASSERT`` in ``main.c`` compares the path with
   ``PORT_RESP_IRQ_OWNED``. If they do not agree, the build stops.
#. If the port defines ``PORT_RESP_PIN``, ``irq_setup()`` compares it with
   the pin of ``resp-gpios``. If they are different, the app prints
   ``LAT ERROR irq setup`` and stops.

Thus the path must be on the CMake command line. A path in a Kconfig
fragment or in ``prj.conf`` does not select the overlay, and the build
stops. ``run.py`` puts each ``kconfig`` value of a point on the command
line, and the Twister scenarios use ``extra_args``.

The Kconfig choice ``LATBENCH_BACKGROUND`` selects what the CPU does between
the edges:

- ``LATBENCH_BG_IDLE`` (default): the idle thread runs, and the CPU sleeps
  in WFI.
- ``LATBENCH_BG_BUSY``: a busy thread runs at the lowest application
  priority.

Output: one histogram ``irq`` and one phase histogram ``irq``.

.. _benchguide-irq-latency-swtrig:

Software trigger
----------------

With ``LATBENCH_SWTRIG=y`` the app alternates two stimuli in one image:

#. An edge of the wire, as without the option. The ISR records the
   sample in ``irq``.
#. A software trigger. The ISR wakes a trigger thread (priority 1). The
   trigger thread waits a random gap (the range of the edges, from a
   generator of its own), reads the stimulus timer (``t0``) and writes the
   response IRQ to ``NVIC->STIR``. The same ISR runs. It sees the flag
   ``swtrig_pending`` and stores its time stamp. The trigger thread then
   records ``ISR time stamp - t0`` in ``irq_sw``, and arms the next edge.

Thus both histograms come from the same ISR, the same code layout and the
same build. The difference of the two histograms is free of the code
placement effect (see :ref:`benchguide-code-placement`).

The software trigger needs the paths ``wrapped`` or ``direct``. The GPIO
driver of the ``stock`` path reads the EXTI pending bit, and a software
pend does not set that bit. A ``zli`` ISR must not call
``k_sem_give()``. A ``BUILD_ASSERT`` stops the other builds. In this build
the direct ISR returns 1, so that the trigger thread runs after the ISR.
This changes only the code after the time stamp.

Time stamps: the start ``t0`` and the end are reads of the same timer
register (``TIM2->CNT``) through the same bus. The counter value comes from
the same point of each read, so the bus delay cancels. The software sample
also contains the rest of the read of ``t0``, one store of ``t0`` to RAM
and the store to ``STIR``. ``LAT META sw_read_cyc`` gives the smallest
difference of two back-to-back reads. The app does not use the DWT cycle
counter: it stops in WFI, and the edge time comes from TIM2. See
:ref:`benchguide-method-swtrig` for the cost of the hardware path that
follows from the two histograms.

The CPU state is different for the two stimuli. An edge meets the idle
thread in WFI (``LATBENCH_BG_IDLE``) or the busy thread
(``LATBENCH_BG_BUSY``). The software trigger always meets the trigger
thread in its spin loop. Thus compare ``irq`` of a busy build with
``irq_sw``.

Output with the option: the histograms and phase histograms ``irq`` and
``irq_sw``, and the ``LAT META`` keys ``stim_trigger=gpio+sw``,
``sw_trigger``, ``sw_trigger_irqn``, ``sw_trigger_prio``, ``sw_read_cyc``
and ``sw_triggers`` (see :doc:`/reference/log-format`).

.. _benchguide-irq-latency-scenarios:

Scenarios
---------

The Kconfig choice ``LATBENCH_IRQ_SCENARIO`` selects what the app
measures. The default ``LATBENCH_IRQ_SCEN_ENTRY`` is the entry, as
described above. The other four scenarios come from the upstream
interrupt benchmark (Zephyr PR 117170, head ``8551fe0ce465``). They need
the path ``wrapped`` or ``direct``. ``src/scenario.c`` has their code.
The build adds the file only for these scenarios, so the images of the
entry do not change.

In these scenarios the main thread drives each sample. It arms the edge
with the usual random delay, does the part of the scenario before the
edge, waits for the ISR and records the sample. Between the samples it
spins: the CPU does not enter WFI. The edge keeps its random time, so the
samples keep a random tick phase.

.. list-table::
   :header-rows: 1
   :widths: 13 44 43

   * - Scenario
     - This app
     - Upstream scenario
   * - ``unlock``
     - 20 us before the edge, the main thread calls ``irq_lock()``. It
       waits until the edge is pending in the NVIC, holds the lock until
       ``LATBENCH_UNLOCK_HOLD_US`` (10) after the edge, reads the timer
       (``t0``) and calls ``irq_unlock()``. ``irq_unlock`` = ISR time
       stamp - ``t0``.
     - ``locked_unlock_to_isr``: the thread locks, pends the IRQ with
       ``STIR``, holds 10 us, walks a cache pollution buffer, reads the DWT
       and calls ``irq_unlock()``. The span is the same. The pend comes
       from the wire, not from ``STIR``, and there is no cache walk.
   * - ``nested``
     - 20 us before the edge, the main thread pends the spare IRQ of the
       port (``PORT_SPARE_IRQN``, priority ``LATBENCH_NESTED_PRIO``). Its
       ISR spins until the edge ISR (priority 0) preempted it.
       ``irq_nested`` = edge to the ISR time stamp. Then the spare ISR
       reads the timer (``t0``), pends the response IRQ with ``STIR`` and
       spins until that ISR ran. ``irq_nested_sw`` = ``t0`` to the ISR
       time stamp.
     - ``nested_preempt``: the low ISR starts the span, pends the high
       line with ``STIR`` and waits. The high ISR ends the span.
       ``irq_nested_sw`` is the same span. ``irq_nested`` is new: the
       edge comes at a random time in the low ISR.
   * - ``exit``
     - The main thread spins in a tight loop on a flag. The ISR sets the
       flag and reads the timer as its last action (``t_exit``). The
       thread reads the timer after the loop. ``irq_exit`` = thread time
       stamp - ``t_exit``. ``irq`` = edge to the ISR time stamp (the
       entry from a busy thread). The direct ISR returns 0 (no
       reschedule).
     - ``exit_resume_interrupted``: the same span. The upstream ISR is a
       regular ISR behind a handler pointer of the benchmark, so its exit
       path has more function returns.
   * - ``burst``
     - The edge starts a burst of ``LATBENCH_BURST_LEN`` (16) ISR runs.
       Just after its time stamp, the ISR pends its own IRQ again with
       ``STIR`` (not in the last run). ``irq_b2b`` = time stamp of a run
       to the time stamp of the next run (15 values per burst). ``irq``
       = edge to the first run.
     - ``throughput_round_trip``: the same span, one value per
       iteration (a burst of two runs). The upstream span also includes
       the call to the handler pointer and the framework.

Common differences to the upstream scenarios:

- The upstream span starts and ends with a DWT read after a ``DSB`` and
  an ``ISB``, and the framework subtracts the mean of an empty span. This
  app reads ``TIM2->CNT`` and subtracts nothing.
- The upstream thread is a cooperative ztest thread
  (``CONFIG_ZTEST_THREAD_PRIORITY=-1``). The main thread of this app is
  preemptible (priority 0), so time slicing applies to it.
- The upstream app runs a scheduler churn and a cache walk before each
  sample. This app runs no load unless the experiment adds it.

Output: the histograms of the scenario (see the table), one phase
histogram (``irq`` in ``burst``, else the main histogram), and the
``LAT META`` keys ``irq_scenario``, ``scen_lead_us``, ``scen_missed``,
``scen_timeouts`` and the setting of the scenario (see
:doc:`/reference/log-format`). With ``LATBENCH_TAIL``, the witness table
has the main histogram of the scenario, without a PC.

Tail witnesses
--------------

With ``LATBENCH_TAIL=y`` the app keeps a witness table of the largest
``irq`` samples (``LAT TAIL irq``). The ISR marks the window when it arms
the next edge, and adds the sample after its time stamp, through a
wrapper that is not inline. The add also reads the interrupted PC and
``ICSR``. The software samples of ``LATBENCH_SWTRIG`` get no table: they
have no tail. See :doc:`/explanation/tail-witnesses`.
