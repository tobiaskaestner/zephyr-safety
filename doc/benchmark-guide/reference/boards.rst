.. _benchguide-clock-overlays:

Clock overlays
--------------

The board default of the NUCLEO-G474RE is a core clock of 170 MHz. The
folder ``common/boards/nucleo_g474re/clocks/`` has two devicetree overlays
that change the core clock:

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Overlay
     - Core clock
   * - ``nucleo_g474re_85mhz.overlay``
     - 85 MHz from the PLL (HSE 24 MHz / 6 * 85 / 4). The clock driver sets
       the flash wait states.
   * - ``nucleo_g474re_16mhz.overlay``
     - 16 MHz from the HSI. The flash needs 0 wait states.

APB1 stays at /1 in both overlays, so TIM2 still runs at the core clock.
A latency in cycles that changes with the clock shows an effect of the
flash wait states. To use an overlay, add it to ``dtc_overlays`` of a point
(see :ref:`benchguide-experiment-file`).
