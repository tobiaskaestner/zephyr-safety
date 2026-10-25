The apps and their variants
===========================

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
(``build_only: true``). A data point comes only from ``scripts/run.py``
(see :doc:`host-tools`).

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

.. timeline-viz:: diagrams/irq-latency.tdl
   :name: benchguide-fig-irq-latency

   ``irq_latency`` with the ``stock`` path. The ``wrapped`` path starts its
   ISR after the exception entry, with ``_isr_wrapper``. The ``direct``
   and ``zli`` paths start their ISR after the exception entry, without
   ``_isr_wrapper``. Thus the ISR reads the counter earlier.

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

Known limit of the ``zli`` path: ``stim_arm()`` takes the tick phase of the
next edge from ``k_cycle_get_64()``. BASEPRI does not mask a zero-latency
IRQ, so the read can interrupt the timer driver in its locked section and
see an inconsistent count. Only the phase histogram is at risk, not the
latency.

The Kconfig choice ``LATBENCH_BACKGROUND`` selects what the CPU does between
the edges:

- ``LATBENCH_BG_IDLE`` (default): the idle thread runs, and the CPU sleeps
  in WFI.
- ``LATBENCH_BG_BUSY``: a busy thread runs at the lowest application
  priority.

Output: one histogram ``irq`` and one phase histogram ``irq``.

``wake_latency`` (M2)
---------------------

The ISR of the response pin takes a time stamp and wakes a thread
through a kernel object. The app always connects its own ISR
(``LATBENCH_RESP_IRQ_OWN`` in its ``CMakeLists.txt``). The woken thread takes a time stamp when its wait call returns.
Then it arms the next edge.

.. timeline-viz:: diagrams/wake-latency.tdl
   :name: benchguide-fig-wake-latency

   ``wake_latency`` with the variant ``wrapped-sem``. The ISR wakes the
   thread. The ISR exit pends PendSV, and PendSV switches from the idle
   thread to the woken thread. The three brackets are the histograms
   ``irq``, ``isr2thr`` and ``irq2thr``.

The Kconfig choice ``LATBENCH_WAKE_ISR`` selects how the ISR is connected:

- ``LATBENCH_WAKE_ISR_WRAPPED`` (default): ``IRQ_CONNECT()``, through
  ``_isr_wrapper``.
- ``LATBENCH_WAKE_ISR_DIRECT``: ``IRQ_DIRECT_CONNECT()``. The ISR returns 1,
  so the kernel does a reschedule at the ISR exit.

The Kconfig choice ``LATBENCH_WAKE_PRIMITIVE`` selects the kernel object:

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - Kconfig option
     - Variant part
     - ISR call / thread call
   * - ``LATBENCH_WAKE_SEM`` (default)
     - ``sem``
     - ``k_sem_give()`` / ``k_sem_take()``
   * - ``LATBENCH_WAKE_EVENT``
     - ``event``
     - ``k_event_post()`` / ``k_event_wait()``
   * - ``LATBENCH_WAKE_MSGQ``
     - ``msgq``
     - ``k_msgq_put()`` / ``k_msgq_get()``, 4-byte message
   * - ``LATBENCH_WAKE_FIFO``
     - ``fifo``
     - ``k_fifo_put()`` / ``k_fifo_get()``
   * - ``LATBENCH_WAKE_POLL``
     - ``poll``
     - ``k_poll_signal_raise()`` / ``k_poll()``

The variant name is ``<isr>-<primitive>``, for example ``wrapped-sem``.

``LATBENCH_WAKE_PRIO`` sets the priority of the woken thread (default 0).
Priority 0 is the highest preemptible priority. With
``CONFIG_TIMESLICING=y``, a thread at priority 0 can get time slices, so
the default includes the cost of time slicing. A negative value makes the
thread cooperative. The main thread has priority 10 (``prj.conf``), so it
does not compete with the woken thread. ``LATBENCH_BACKGROUND`` is the same
as in ``irq_latency``.

Output:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Histogram
     - Quantity
   * - ``irq``
     - Edge to the first instruction of the ISR (M1 in this app). Also a
       phase histogram.
   * - ``isr2thr``
     - ISR time stamp to the time stamp of the woken thread (M2). Also a
       phase histogram.
   * - ``irq2thr``
     - Edge to the woken thread (end to end).

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

.. timeline-viz:: diagrams/thread-latency-preempt.tdl
   :name: benchguide-fig-thread-latency-preempt

   ``thread_latency`` with the variant ``sem-preempt``. The taker has a
   higher priority than the giver, so the wake call switches to the
   taker. ``t2t`` stops in the taker. ``t2t_ret`` stops when the wake call
   returns, after the taker blocked again.

The Kconfig choice ``LATBENCH_T2T_PRIMITIVE`` selects the primitive:

.. list-table::
   :header-rows: 1
   :widths: 30 15 55

   * - Kconfig option
     - Variant part
     - Giver call / taker call
   * - ``LATBENCH_T2T_SEM`` (default)
     - ``sem``
     - ``k_sem_give()`` / ``k_sem_take()``
   * - ``LATBENCH_T2T_MUTEX``
     - ``mutex``
     - ``k_mutex_unlock()`` / ``k_mutex_lock()``. Before each edge, the giver
       locks the mutex and lets the taker block on it (contended, with
       priority inheritance).
   * - ``LATBENCH_T2T_CONDVAR``
     - ``condvar``
     - ``k_condvar_signal()`` / ``k_condvar_wait()``
   * - ``LATBENCH_T2T_EVENT``
     - ``event``
     - ``k_event_post()`` / ``k_event_wait()`` with reset
   * - ``LATBENCH_T2T_MSGQ``
     - ``msgq``
     - ``k_msgq_put()`` / ``k_msgq_get()``, 4-byte message
   * - ``LATBENCH_T2T_FIFO``
     - ``fifo``
     - ``k_fifo_put()`` / ``k_fifo_get()``
   * - ``LATBENCH_T2T_LIFO``
     - ``lifo``
     - ``k_lifo_put()`` / ``k_lifo_get()``
   * - ``LATBENCH_T2T_STACK``
     - ``stack``
     - ``k_stack_push()`` / ``k_stack_pop()``
   * - ``LATBENCH_T2T_POLL``
     - ``poll``
     - ``k_poll_signal_raise()`` / ``k_poll()``
   * - ``LATBENCH_T2T_WORK``
     - ``work``
     - ``k_work_submit_to_queue()`` / the work handler in a work queue
       thread. The work queue thread is the taker.
   * - ``LATBENCH_T2T_WAKEUP``
     - ``wakeup``
     - ``k_wakeup()`` / ``k_sleep(K_FOREVER)``

``LATBENCH_T2T_PREEMPT`` selects the preempt mode (default ``y``):

- ``y`` (``preempt``): the taker has priority 1 and preempts the giver in
  the wake call.
- ``n`` (``nopreempt``): the taker has priority 3. It runs when the giver
  blocks again. The giver records the sample one edge later, so the run
  has one sample less.

.. timeline-viz:: diagrams/thread-latency-nopreempt.tdl
   :name: benchguide-fig-thread-latency-nopreempt

   ``thread_latency`` with the variant ``sem-nopreempt``, from the time
   when the giver wakes. The wake call does not switch. The taker runs
   when the giver blocks for the next edge. ``t2t`` thus includes the rest
   of the giver loop. The giver records ``t2t`` and ``t2t_ret`` after the
   next edge.

The variant name is ``<primitive>-<mode>``, for example ``sem-preempt``.

Output:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Histogram
     - Quantity
   * - ``isr2thr``
     - ISR time stamp to the giver (the M2 path, as a cross check).
   * - ``t2t``
     - ``t0`` to ``t1``: the wake call to the first instruction of the taker
       (M3). In ``nopreempt`` mode, this includes the rest of the giver loop
       and its block. For ``mutex``, the giver blocks on the mutex in its
       next ``giver_prepare()``.
   * - ``t2t_ret``
     - ``t0`` to ``t2``: the wake call to its return. In ``preempt`` mode,
       this includes the taker, its next wait call and the switch back. In
       ``nopreempt`` mode, it is the wake call without a switch.

If the taker did not run exactly once for a wake, the giver does not
record ``t2t`` and ``t2t_ret`` for that wake. It counts the wake in
``taker_missed``. This app has no phase histograms and no
``LATBENCH_BACKGROUND`` option.

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

The app prints ``RESULT: OK`` or ``RESULT: FAIL``. It does not use the
``LAT`` line format. The ``use_switch`` scenario of its ``testcase.yaml``
builds it with ``CONFIG_USE_SWITCH=y``.
