What the apps measure
=====================

The suite has four apps. Three apps measure latencies with the hardware
stimulus. The fourth app does a test of the wire.

.. list-table::
   :header-rows: 1
   :widths: 20 10 70

   * - App
     - Point
     - Content
   * - ``irq_latency``
     - M1
     - Edge to the first time stamp in the interrupt path
   * - ``wake_latency``
     - M2
     - Edge to ISR to woken thread, for each kernel object that an ISR can
       use to wake a thread
   * - ``thread_latency``
     - M3
     - ISR to giver thread to taker thread, for each kernel primitive
   * - ``loopback_check``
     - none
     - Static check and interrupt check of the wire

The three measurement apps have the same frame:

#. ``main()`` calls ``port_debug_reset()`` and prints the metadata (see
   :ref:`benchguide-meta`).
#. ``stim_init()`` sets up the stimulus timer and the pins through the
   board port, and prints the stimulus settings.
#. ``stim_static_check()`` does the static check of the wire.
#. The app connects its ISR to the response IRQ ``STIM_RESP_IRQN`` (or a
   GPIO callback) and starts the load generators (``load_start()``).
#. The app arms the first edge. It discards the first
   ``LATBENCH_WARMUP`` samples, and then records ``LATBENCH_SAMPLES``
   samples.
#. The main thread polls a ``done`` flag every ``LATBENCH_POLL_MS``
   milliseconds.
#. At the end, the app prints the counters, the histograms and the phase
   histograms, and then ``LAT DONE``.

Each ``testcase.yaml`` of a measurement app is a build check only
(``build_only: true``). A data point comes only from
``scripts/benchmarks/run.py`` (see :doc:`../reference/cli/run-py`).

``irq_latency`` (M1)
--------------------

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

.. timeline-viz:: ../diagrams/irq-latency.tdl
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

``wake_latency`` (M2)
---------------------

The ISR of the response pin takes a time stamp and wakes a thread
through a kernel object. The app always connects its own ISR
(``LATBENCH_RESP_IRQ_OWN`` in its ``CMakeLists.txt``). The woken thread takes a time stamp when its wait call returns.
Then it arms the next edge.

.. timeline-viz:: ../diagrams/wake-latency.tdl
   :name: benchguide-fig-wake-latency

   ``wake_latency`` with the variant ``wrapped-sem``. The ISR wakes the
   thread. The ISR exit pends PendSV, and PendSV switches from the idle
   thread to the woken thread. The three brackets are the histograms
   ``irq``, ``isr2thr`` and ``irq2thr``.

``thread_latency`` (M3)
-----------------------

The ISR of the response pin gives a semaphore to the giver thread
(priority 2). As in ``wake_latency``, the app always connects its own
ISR. The
giver takes the time stamp ``t0`` and wakes the taker thread through the
primitive under test. The taker takes the time stamp ``t1`` when its wait
call returns. The giver takes the time stamp ``t2`` when its wake call
returns. The edge comes at a random time, so the wake call meets the
timer ISR and the kernel state at random points.

.. timeline-viz:: ../diagrams/thread-latency-preempt.tdl
   :name: benchguide-fig-thread-latency-preempt

   ``thread_latency`` with the variant ``sem-preempt``. The taker has a
   higher priority than the giver, so the wake call switches to the
   taker. ``t2t`` stops in the taker. ``t2t_ret`` stops when the wake call
   returns, after the taker blocked again.

.. timeline-viz:: ../diagrams/thread-latency-nopreempt.tdl
   :name: benchguide-fig-thread-latency-nopreempt

   ``thread_latency`` with the variant ``sem-nopreempt``, from the time
   when the giver wakes. The wake call does not switch. The taker runs
   when the giver blocks for the next edge. ``t2t`` thus includes the rest
   of the giver loop. The giver records ``t2t`` and ``t2t_ret`` after the
   next edge.

``loopback_check``
------------------

The app does a test of the wire without the stimulus timer and without a
board port. It drives the stimulus pin (``stim-gpios``) as a GPIO output
and reads the response pin (``resp-gpios``). Each board has an overlay in
``loopback_check/boards/`` with the same wire as its port. On the
MIMXRT1060-EVKC, A3 drives and D2 reads. The ``testcase.yaml`` permits
only ``nucleo_g474re``.

#. Static check: it drives the stimulus pin low and high and reads the
   response pin.
#. Interrupt check: 1000 times, it sets the stimulus pin high and measures
   the time to the GPIO callback of the response pin with
   ``timing_counter_get()``.
