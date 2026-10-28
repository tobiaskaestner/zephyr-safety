.. _benchguide-app-thread-latency:

``thread_latency`` (M3)
=======================

The :term:`app` ``thread_latency`` is in ``tests/benchmarks/thread_latency/``.
This page is its documentation, beside its code.
:doc:`/explanation/apps` gives the frame that all measurement apps
share.

What it measures
----------------

The ISR of the response pin gives a semaphore to the giver thread
(priority 2). As in ``wake_latency``, the app always connects its own
ISR. The
giver takes the time stamp ``t0`` and wakes the taker thread through the
primitive under test. The taker takes the time stamp ``t1`` when its wait
call returns. The giver takes the time stamp ``t2`` when its wake call
returns. The edge comes at a random time, so the wake call meets the
timer ISR and the kernel state at random points.

.. timeline-viz:: thread-latency-preempt.tdl
   :name: benchguide-fig-thread-latency-preempt

   ``thread_latency`` with the variant ``sem-preempt``. The taker has a
   higher priority than the giver, so the wake call switches to the
   taker. ``t2t`` stops in the taker. ``t2t_ret`` stops when the wake call
   returns, after the taker blocked again.

.. timeline-viz:: thread-latency-nopreempt.tdl
   :name: benchguide-fig-thread-latency-nopreempt

   ``thread_latency`` with the variant ``sem-nopreempt``, from the time
   when the giver wakes. The wake call does not switch. The taker runs
   when the giver blocks for the next edge. ``t2t`` thus includes the rest
   of the giver loop. The giver records ``t2t`` and ``t2t_ret`` after the
   next edge.

Options, variants and output
----------------------------

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
  blocks again. The giver records the :term:`sample` one edge later, so the run
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
