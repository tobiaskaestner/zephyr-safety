Purpose and scope
=================

What the suite measures
-----------------------

The suite measures the distributions of interrupt latencies and
scheduling latencies of Zephyr. A distribution shows the floor, the modes
and the tail of a latency. An average hides the tail, and a safety
argument needs the tail. For this reason, each :term:`app` records every :term:`sample`
in a histogram on the target, not only a mean.

All times are in counts of the stimulus timer. On the NUCLEO-G474RE, the
stimulus timer runs at the core clock, so one count is one core cycle (see
:doc:`method`). This guide uses "cycles" for these counts.

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
     - Time with interrupts masked, for each call site, and the time of
       each ISR body
     - The start of a mask section (a hook in the mask path of Zephyr)
     - The end of the mask section (a second hook)
     - ``wake_latency`` and ``thread_latency`` with
       ``CONFIG_ARM_IRQ_MASK_HOOKS``

M4 needs the :term:`tree` ``ws-up-irqoff``, which has the hooks. The hooks make
each mask section longer, so the latency histograms of an M4 run are not
data. The :term:`experiments <Experiment>` ``m4-sweep`` and ``m4-thread`` of the :term:`study`
``mask-time`` measure M4. :doc:`mask-time` describes the method and its
limits.
