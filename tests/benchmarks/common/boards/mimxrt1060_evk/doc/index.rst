.. _benchguide-board-mimxrt1060-evk:

Board ``mimxrt1060_evk``
========================

The :term:`board port` ``mimxrt1060_evk`` (MIMXRT1060-EVKC) is in
``tests/benchmarks/common/boards/mimxrt1060_evk/``. This page is its documentation,
beside its code. :doc:`/reference/boards` gives the structure of a port
and its contract.

.. list-table::
   :widths: 30 70

   * - Board target
     - ``mimxrt1060_evk@C/mimxrt1062/qspi`` (MIMXRT1060-EVKC, Cortex-M7 at
       600 MHz)
   * - Port name
     - ``mimxrt1060_evk/gpt2_cmp1-gpio1_11``
   * - Stimulus timer
     - GPT2 (32 bits), free-run mode, no prescaler, at PERCLK. The port
       sets PERCLK to IPG / 2 (75 MHz), the maximum of the data sheet. GPT2
       also counts in wait and doze mode and while a debugger halts the
       core.
   * - Counts per core cycle
     - 1 count is 8 core cycles. The core clock and PERCLK come from the
       same PLL, so the ratio is exact.
   * - Interconnect
     - None. The output compare channel 1 of GPT2 drives the pin (output
       mode "clear", then "set" at the compare match).
   * - Stimulus pin
     - A3 (pad ``GPIO_AD_B1_05``, function ``GPT2_COMPARE1``)
   * - Response pin
     - D2 (pad ``GPIO_AD_B0_11``, ``GPIO1_IO11``). ``PORT_RESP_IRQN`` is
       ``GPIO1_Combined_0_15_IRQn`` (IRQ 80). ``PORT_RESP_PIN`` is 11. A
       ``BUILD_ASSERT`` makes sure that ``resp-gpios`` is this pin.
   * - Wire
     - D2 to A3, as on the NUCLEO-G474RE, but A3 drives and D2 reads. Only
       A3 has a timer compare output on this board.
   * - Own response IRQ
     - ``resp_irq_own.overlay`` removes IRQ 80 from the GPIO1 node. The GPIO
       driver then has no interrupts for the pins 0 to 15 of GPIO1. It keeps
       IRQ 81 (pins 16 to 31). ``stim.overlay`` disables the ``gpt2``
       counter node.
   * - System timer and tick phase
     - SysTick at the core clock. ``port.conf`` sets
       ``CONFIG_CORTEX_M_SYSTICK_64BIT_CYCLE_COUNTER=y``. The phase has a
       resolution of one GPT2 count (8 core cycles). If the core clock is
       not the SysTick clock, ``port_stim_init()`` prints ``LAT ERROR`` and
       the app stops.
   * - ``debug_reg_at_boot``
     - ``n/a clpcr=<value>``. The SoC has no debug register that keeps
       clocks on in sleep. The port gives the low-power mode register
       ``CCM_CLPCR`` instead.
   * - ``boards.yaml``
     - Modules ``cmsis_6``, ``hal_nxp``. Flash with ``pyocd`` (the
       ``.elf``, because the build makes no ``.hex``). ``-u`` selects the
       probe. ``status: untested``.

Examine these items first on the hardware:

- The flash commands are not tested. If more than one probe is connected,
  pyocd asks which one to use. Then add ``-u <probe id>`` to the commands.
- The board puts the kernel RAM into external SDRAM (``zephyr,sram`` is
  ``sdram0``), and the code runs from the QSPI flash (XIP). The caches and
  the external memories are part of each latency.
- The port changes PERCLK for all peripherals that use it.
- ``clock_drift_cyc`` is ``n/a``, because GPT2 and SysTick have different
  clocks.
- The wire direction is the opposite of the other boards. Connect the
  same D2 - A3 wire, and make sure that the static check passes.
