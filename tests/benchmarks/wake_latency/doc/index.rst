.. _benchguide-app-wake-latency:

``wake_latency`` (M2)
=====================

The :term:`app` ``wake_latency`` is in ``tests/benchmarks/wake_latency/``.
This page is its documentation, beside its code.
:doc:`/explanation/apps` gives the frame that all measurement apps
share.

What it measures
----------------

The ISR of the response pin takes a time stamp and wakes a thread
through a kernel object. The app always connects its own ISR
(``LATBENCH_RESP_IRQ_OWN`` in its ``CMakeLists.txt``). The woken thread takes a time stamp when its wait call returns.
Then it arms the next edge.

.. timeline-viz:: wake-latency.tdl
   :name: benchguide-fig-wake-latency

   ``wake_latency`` with the variant ``wrapped-sem``. The ISR wakes the
   thread. The ISR exit pends PendSV, and PendSV switches from the idle
   thread to the woken thread. The three brackets are the histograms
   ``irq``, ``isr2thr`` and ``irq2thr``.

Options, variants and output
----------------------------

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
