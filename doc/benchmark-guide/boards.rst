Board support
=============

.. note::

   This page describes the state of the code today. Work to put the
   board-specific code into a separate compilation unit for each board is
   in progress on another branch. That work adds the boards nRF52840-DK,
   nRF54L15-DK and MIMXRT1060-EVKC. When it is merged, this page gets a
   new version.

Supported boards
----------------

The suite supports one board today: ``nucleo_g474re`` (NUCLEO-G474RE,
STM32G474RE, Cortex-M4F, 170 MHz by default).

Board-specific code
-------------------

The board-specific code is in these places:

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Location
     - Board-specific content
   * - ``common/src/stim.c``
     - TIM2 set-up and output compare with the STM32 LL API, the TIM2
       clock (``STM32_CLOCK_INFO``), the pin function ``tim2_ch4_pa10``
       through pinctrl, the EXTI0 routing through SYSCFG, and the
       ``BUILD_ASSERT`` on the RCC prescalers.
   * - ``common/include/latbench/stim.h``
     - Inline access to ``TIM2->CNT`` and to the ``CC4`` flag,
       ``stm32_ll_tim.h``.
   * - ``*/boards/nucleo_g474re.overlay``
     - The ``zephyr,user`` node (``resp-gpios`` on A3, ``pinctrl-0 =
       <&tim2_ch4_pa10>``), ``pwm2`` disabled (the board uses TIM2 for the
       LED), and in ``wake_latency`` and ``thread_latency`` the EXTI node
       without line 0. ``loopback_check`` uses ``stim-gpios`` on D2 instead.
   * - ``irq_latency/exti_line0_app.overlay``
     - The EXTI node without line 0, for the own ISR paths.
   * - ``*/src/main.c``
     - ``DBGMCU->CR``, ``EXTI0_IRQn``, ``LL_EXTI_ClearFlag_0_31()``
       (``stm32_ll_exti.h``).
   * - ``common/clocks/``
     - Clock overlays for this board.
   * - ``*/testcase.yaml``
     - ``platform_allow: nucleo_g474re``.
   * - ``trees.yaml``
     - ``board: nucleo_g474re``, and the module ``hal_stm32`` in each tree.
   * - ``scripts/run.py``
     - Flash with OpenOCD through the ``openocd.cfg`` of the board.

The portable parts are the histograms (``hist.c``), the metadata
(``meta.c``), the measurement logic in the apps, and the host tools. The
load generators (``load.c``) are also portable, but they take the tick
period from the stimulus.

What the method needs from a board
----------------------------------

A new board must have these properties, or an equivalent:

- A 32-bit hardware timer that runs at the core clock and can set a pin at
  a programmed compare value.
- A pin with an external interrupt that has its own interrupt vector, and
  a wire from the timer pin to this pin.
- A system timer and a 64-bit cycle counter that count the same clock as
  the stimulus timer, for the tick phase.
- A serial console that the host can read without loss at the output rate
  of the apps.
