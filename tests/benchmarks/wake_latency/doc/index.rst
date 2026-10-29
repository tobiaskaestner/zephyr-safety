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

Software trigger
----------------

With ``LATBENCH_SWTRIG=y`` each edge sample is followed by a software
sample. After it took the edge sample, the woken thread starts the trigger
thread (priority ``LATBENCH_WAKE_PRIO`` + 1) and waits again. The trigger
thread waits a random gap, reads the stimulus timer (``t0``) and writes the
response IRQ to ``NVIC->STIR``. The ISR wakes the thread, which preempts
the trigger thread. This is the set-up of the scenario ``irq_to_thread``
of Zephyr PR 117170: a lower-priority thread spins, and the interrupt wakes
a higher-priority thread.

The extra histograms are ``irq_sw`` (``t0`` to the ISR), ``isr2thr_sw``
(ISR to thread) and ``irq2thr_sw`` (``t0`` to the thread), and the phase
histogram ``irq_sw``. :ref:`benchguide-irq-latency-swtrig` describes the
time stamps and the ``LAT META`` keys. The edge samples meet the idle
thread in WFI. The software samples meet a running thread, so the wake
path switches away from a preempted thread and not from the idle thread.

Tail witnesses
--------------

With ``LATBENCH_TAIL=y`` the woken thread keeps a witness table of the
largest ``irq2thr`` samples (``LAT TAIL irq2thr``, ``aux`` is the ``irq``
part). The window starts when the thread arms the edge and ends after the
time stamps of the thread. With ``LATBENCH_SWTRIG=y`` a second table
``irq2thr_sw`` has the software samples. Its window starts at the request
to the trigger thread. The tables have no PC: a read in the ISR makes the
wake path longer. See :doc:`/explanation/tail-witnesses`.
