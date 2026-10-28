The apps and their variants
===========================

This page gives the options, the variants and the output of each app.
:doc:`../explanation/apps` tells what each app measures.

``irq_latency`` (M1)
--------------------

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

``wake_latency`` (M2)
---------------------

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

The app prints ``RESULT: OK`` or ``RESULT: FAIL``. It does not use the
``LAT`` line format. The ``use_switch`` scenario of its ``testcase.yaml``
builds it with ``CONFIG_USE_SWITCH=y``.
