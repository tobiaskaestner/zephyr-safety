.. _benchguide-tail-witnesses:

Tail witnesses
==============

A histogram gives the size of the tail, but not its cause. The option
``LATBENCH_TAIL`` adds a witness table to the main histograms of
``irq_latency`` (``irq``) and ``wake_latency`` (``irq2thr``, and
``irq2thr_sw`` with ``LATBENCH_SWTRIG``). The table keeps the
``LATBENCH_TAIL_N`` largest :term:`samples <Sample>` of
``LATBENCH_TAIL_MIN_CYC`` cycles or more. For each sample it keeps the
counters of a window around the sample. The host then names the cause of
each sample. The idea comes from the outlier trace of the upstream
interrupt benchmark (Zephyr PR 117170), which reads the same kind of
counters for each outlier.

The window
----------

The window starts when the app arms the stimulus (``lat_tail_mark()``),
before the sample starts. It ends after the end time stamp of the sample
(``lat_tail_add()``). Thus the window contains the random gap before the
stimulus and the sample itself. The host uses ``win`` (the length of the
window) and ``lat`` to tell the two parts apart where it can.

The counters of the window:

.. list-table::
   :header-rows: 1
   :widths: 15 85

   * - Field
     - Content
   * - ``win``
     - Counts of the stimulus timer from the mark to the add.
   * - ``exc``
     - DWT ``EXCCNT`` in the window: the cycles of exception entry and
       exit. Each exception adds to it. The counter has 8 bits, so more
       than 255 cycles of exception overhead in one window wrap it.
       ``exc_min`` of the table is the value of a window with no other
       exception than the sample itself.
   * - ``st0``, ``st1``
     - SysTick ``VAL`` at the mark and at the add. If SysTick did not
       reload, ``st0 - st1`` is ``win``. A difference shows a SysTick
       wrap (its interrupt) or a reprogram by the driver. A read of
       ``VAL`` does not clear ``COUNTFLAG``, so the driver does not see the
       read.
   * - ``ld``
     - SysTick ``LOAD`` at the add. After a reload, ``ld - st1`` is the
       time since the last reload or reprogram (``systick_age``).
   * - ``tmr``, ``wake``
     - Expiries of the load timers and wakes of the sleeper load threads
       in the window.
   * - ``pc``, ``icsr``
     - Only in ``irq_latency``: the PC that the interrupt of the sample
       interrupted (the stacked PC on the process stack) and SCB
       ``ICSR``. ``pc`` is 0 if the ISR preempted another exception
       (``ICSR.RETTOBASE`` is 0).
   * - ``aux``, ``phase``
     - A second value of the app (``wake_latency``: the ``irq`` part of
       the sample) and the tick phase of the stimulus.

The kernel tick count is not a witness: with the tickless kernel it counts
time, not system timer interrupts.

The causes
----------

``scripts/benchmarks/tails.py`` gives each row its labels (the witnesses
that the counters show) and one cause. The module text has the exact
rules. In short:

``systick``
   SysTick reloaded in the window, the last reload was during the sample
   (``systick_age`` is at most ``lat`` plus the time of the add) or the
   stimulus came less than 4000 cycles after a tick boundary, and the
   window has extra exception cycles. The SysTick ISR has the same
   priority as the response IRQ, so it delays the sample.
   ``systick+timers``: the same, and load timers expired in the window
   (their expiry functions run in the SysTick ISR).
``nested``
   The ISR of the sample preempted another exception.
``exception``
   More exception cycles than ``exc_min``, but no SysTick reload during
   the sample. This is a weak witness: the extra exception can be in the
   gap before the stimulus.
``reprogram``
   SysTick reloaded during the sample, but the window has no extra
   exception cycles: the code of the sample reprogrammed SysTick, and no
   SysTick interrupt came. In ``wake_latency`` the slice reset of the
   scheduler does this in the slow mode (label ``systick-reprogram``).
``none``
   No counter shows a cause. The cause is then not an exception, for
   example a section with masked interrupts. In ``irq_latency``, ``pc``
   then names the function that unmasked the interrupts.

``data.Instance.tails()`` gives one row per witness row, with its labels
and cause. ``nbfig.tails()`` draws each tail sample at its tick phase,
coloured by its cause. The checks read the witness table as the metric
``tail.<hist>`` (see :ref:`benchguide-check-forms`).

The cost and the latency path
-----------------------------

The witness code must not change the latency of the sample that it
describes. Three properties make sure of this:

#. ``lat_tail_mark()`` runs before the stimulus, in the gap of at least
   100 us before the edge.
#. ``lat_tail_add()`` runs after the end time stamp, in a function that is
   not inline. In ``irq_latency``, the ISR calls a small wrapper with two
   arguments, so the compiler needs no more registers before the time
   stamp. ``scripts/benchmarks/prestamp.py`` compares the instructions of
   the ISR up to the time stamp in two images (register names and literal
   offsets masked). For ``resp_isr`` of the wrapped and the direct path,
   the instructions are the same with and without the witnesses.
#. The witness code adds code to the image, so the other code moves. In
   flash, a move of the code changes the latency by up to about 30 cycles
   (see :ref:`benchguide-code-placement`). Thus a comparison of the data
   with and without the witnesses uses ``LATBENCH_CODE_RAM``. The
   sub-study ``measurement-validity/tail-witnesses`` makes this check.

At the start, the app measures the cost of the calls with the interrupts
locked and prints it as ``LAT META tail_cost_*_cyc`` (see
:doc:`../reference/log-format`). On the NUCLEO-G474RE: the mark costs about
37 cycles, an add that the table rejects about 76 cycles, and an add that
stores a row about 550 cycles (most of it is the scan of a full table for
its smallest row). Set ``LATBENCH_TAIL_MIN_CYC`` above the body of the
distribution, so that most adds take the short path.

The add runs in the ISR (``irq_latency``) or in the woken thread
(``wake_latency``), after the time stamps. It makes the ISR or the thread
longer, but the next stimulus comes at least 100 us later.
