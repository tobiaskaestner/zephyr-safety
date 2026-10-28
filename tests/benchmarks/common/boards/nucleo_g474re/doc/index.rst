.. _benchguide-board-nucleo:

Board ``nucleo_g474re``
=======================

The :term:`board port` ``nucleo_g474re`` (NUCLEO-G474RE) is in
``tests/benchmarks/common/boards/nucleo_g474re/``. This page is its documentation,
beside its code. :doc:`/reference/boards` gives the structure of a port
and its contract.

:doc:`/howto/wire-the-nucleo-g474re` gives the steps to connect the
board.

.. list-table::
   :widths: 30 70

   * - Board target
     - ``nucleo_g474re`` (NUCLEO-G474RE, STM32G474RE, Cortex-M4F)
   * - Port name
     - ``nucleo_g474re/tim2_ch4-exti0``
   * - Stimulus timer
     - TIM2 (32 bits), prescaler 0, at the core clock (170 MHz by default).
       A ``BUILD_ASSERT`` makes sure that the AHB and APB1 prescalers are 1.
       The auto-reload value is ``UINT32_MAX``: TIM2 counts each cycle of
       its clock and wraps after 2\ :sup:`32` cycles.
   * - Counts per core cycle
     - 1 (one count is one core cycle)
   * - Interconnect
     - None. The output compare of TIM2 channel 4 drives the pin
       ("forced inactive", then "active on match"). Channel 4 has no
       preload and an active-high polarity (``port.c``).
   * - Stimulus pin
     - D2 (PA10), pin function ``tim2_ch4_pa10``. PA10 is TIM2 channel 4.
   * - Response pin
     - A3 (PB0), EXTI line 0, which has its own interrupt vector.
       ``PORT_RESP_IRQN`` is ``EXTI0_IRQn``.
       ``PORT_RESP_PIN`` is 0.
   * - Wire
     - D2 to A3. D2 drives, A3 reads.
   * - Own response IRQ
     - ``resp_irq_own.overlay`` removes EXTI line 0 from the GPIO driver.
       ``stim.overlay`` disables ``pwm2`` (the board uses TIM2 for the LED).
   * - System timer and tick phase
     - SysTick at the core clock. The phase has a resolution of 1 cycle.
       ``port.conf`` sets ``CONFIG_CORTEX_M_SYSTICK_64BIT_CYCLE_COUNTER=y``,
       because SysTick has the 64-bit counter by default only above 60 MHz.
   * - ``debug_reg_at_boot``
     - ``DBGMCU->CR``. ``port_debug_reset()`` clears it.
   * - Hot code in RAM
     - ``Kconfig.port`` sets ``LATBENCH_CODE_RAM_REGION`` to ``CCM``. If
       ``CONFIG_LATBENCH_CODE_RAM=y`` is on the command line,
       ``port.cmake`` adds ``code_ram_ccm.overlay``. The overlay adds the
       memory region ``CCM`` (32 KB at ``0x10000000``) and makes
       ``zephyr,sram`` 96 KB. The CCM SRAM is also at ``0x20018000``, in
       the last 32 KB of ``zephyr,sram`` (a test with OpenOCD: a word
       written at ``0x10000000`` reads back at ``0x20018000``). Thus no
       data can go to the alias of the code. The core fetches code from
       the CCM SRAM over the I-code bus, not over the system bus as from
       SRAM1. No MPU region covers ``0x10000000``, so the code can execute
       when the MPU is on. See :ref:`benchguide-code-placement`.
   * - Other files
     - ``clocks/`` (85 MHz and 16 MHz, see :ref:`benchguide-clock-overlays`), ``systick/``
       (see :ref:`benchguide-systick-wrap`).
   * - ``boards.yaml``
     - Modules ``cmsis_6``, ``hal_stm32``. Flash with OpenOCD. ``adapter serial``
       selects the ST-LINK. ``status: tested``.

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
