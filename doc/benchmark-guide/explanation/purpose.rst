Purpose and scope
=================

What the suite measures
-----------------------

The suite measures the distributions of interrupt latencies and
scheduling latencies of Zephyr. A distribution shows the floor, the modes
and the tail of a latency. An average hides the tail, and a safety
argument needs the tail. For this reason, each app records every sample
in a histogram on the target, not only a mean.

All times are in counts of the stimulus timer. On the NUCLEO-G474RE, the
stimulus timer runs at the core clock, so one count is one core cycle (see
:doc:`../hardware`). This guide uses "cycles" for these counts.

The suite has four measurement points:

.. list-table::
   :header-rows: 1
   :widths: 8 20 30 30 12

   * - ID
     - Quantity
     - Start
     - Stop
     - App
   * - M1
     - IRQ to ISR
     - The stimulus edge on the pin (hardware time stamp)
     - The first time stamp in the ISR (or in the GPIO callback)
     - ``irq_latency``
   * - M2
     - ISR to thread
     - The time stamp in the ISR, before the ISR wakes a thread
     - The time stamp of the woken thread, after its wait call returns
     - ``wake_latency``
   * - M3
     - Thread to thread
     - The time stamp before the wake call of the giver thread
     - The time stamp of the taker thread, after its wait call returns
     - ``thread_latency``
   * - M4
     - Time with interrupts locked
     - The lock (nesting 0 to 1)
     - The unlock (nesting 1 to 0)
     - Not implemented

M4 is a plan. It needs a hook in the interrupt lock path of Zephyr. No app
of the suite measures M4 today. The tail of M1 gives an indirect lower
limit of the longest locked section that the stimulus hit.
