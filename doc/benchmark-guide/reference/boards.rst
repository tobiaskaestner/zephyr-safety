Board support
=============

The board-specific code of the stimulus is in a :term:`board port`. The :term:`apps <App>`,
``stim.c``, the histograms, the load generators and the host tools are the
same on each board.

Boards
------

.. list-table::
   :header-rows: 1
   :widths: 38 22 40

   * - Board target
     - Port
     - Status in ``boards.yaml``
   * - ``nucleo_g474re``
     - ``nucleo_g474re``
     - ``tested``: data points exist.
   * - ``nrf52840dk/nrf52840``
     - ``nrf52840dk``
     - ``untested``: builds on both :term:`trees <Tree>`, not run on hardware.
   * - ``nrf54l15dk/nrf54l15/cpuapp``
     - ``nrf54l15dk``
     - ``untested``: builds on both trees, not run on hardware.
   * - ``mimxrt1060_evk@C/mimxrt1062/qspi``
     - ``mimxrt1060_evk``
     - ``untested``: builds on both trees, not run on hardware.

For each ``untested`` board, the section of the board lists what to
examine first on the hardware. The ``port-smoke-<port>`` :term:`experiments <Experiment>` are
the first runs for these boards.

Structure of a port
-------------------

A port is a folder ``common/boards/<board>/``. ``<board>`` is the board
target without qualifiers and revision (see
:ref:`benchguide-latbench-cmake`). The folder has these files:

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - File
     - Content
   * - ``port.cmake``
     - Adds the devicetree overlays and the Kconfig fragments of the port to
       ``EXTRA_DTC_OVERLAY_FILE`` and ``EXTRA_CONF_FILE``.
       ``latbench_board.cmake`` includes it before ``find_package(Zephyr)``.
   * - ``port.conf``
     - Optional. A Kconfig fragment of the port.
   * - ``Kconfig.port``
     - Optional. Defaults of the port for the options of ``common/Kconfig``.
       ``common/Kconfig`` sources it first, so its defaults have priority.
       Today it gives only ``LATBENCH_CODE_RAM_REGION``. A port without it
       does not support ``LATBENCH_CODE_RAM``.
   * - ``stim.overlay``
     - The ``zephyr,user`` node with ``resp-gpios`` (the response pin), and
       the stimulus pin (a pin function, or ``stim-gpios``). It also
       disables drivers that use the stimulus timer.
   * - ``resp_irq_own.overlay``
     - Takes the response IRQ away from the GPIO driver. ``port.cmake`` adds
       it only if ``LATBENCH_RESP_IRQ_OWN`` is set.
   * - ``include/latbench/port_impl.h``
     - The fast functions of the contract as ``static inline`` functions,
       and the macros of the contract.
   * - ``port.c``
     - The other functions of the contract.
   * - Other files
     - Optional. For example clock overlays (``clocks/``), SysTick overlays
       (``systick/``) or Kconfig fragments for experiments
       (``ticks_1024.conf``).

The two Nordic ports share their code in ``common/boards/nordic/``
(``nrf_port_impl.h`` and ``nrf_port.c``). The ``port_impl.h`` of the board
defines the TIMER, the GPIOTE and the clock node, and then includes the
shared header. The ``port.c`` of the board defines ``port_name`` and then
includes ``nrf_port.c``.

The contract
------------

``common/include/latbench/port.h`` is the contract of a port. The stimulus
timer must be a free-running 32-bit up-counter with an output compare
channel. At the compare value, the hardware drives the stimulus pin high,
with no software in the path.

Fast functions and macros, in ``port_impl.h``:

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Name
     - Purpose
   * - ``port_stim_now()``
     - Returns the counter of the stimulus timer.
   * - ``port_stim_fired()``
     - Returns true if the compare flag is set (the edge came from the
       timer).
   * - ``port_resp_ack()``
     - Clears the pending flag of the response interrupt (own ISR only).
   * - ``PORT_RESP_IRQN``
     - The IRQ line of the response pin (own ISR only).
   * - ``PORT_RESP_IRQ_OWNED``
     - 1 if the devicetree gives the response interrupt to the app, 0 if
       the GPIO driver has it.
   * - ``PORT_RESP_PIN``
     - Optional. The pin number that the own ISR serves. If the port
       defines it, ``irq_latency`` compares the pin of ``resp-gpios`` with
       it and stops with ``LAT ERROR irq setup`` if they are different.

Other functions, in ``port.c``:

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Name
     - Purpose
   * - ``port_name``
     - The name of the port, for the output (``LAT META port``).
   * - ``port_stim_init()``
     - Starts the stimulus timer (free-running, 32 bits) and sets up the
       stimulus pin with the output low.
   * - ``port_stim_hz()``
     - Returns the clock of the stimulus timer in Hz. ``stim_init()`` calls
       it before ``port_stim_init()``.
   * - ``port_core_hz()``
     - Returns the clock of the CPU core in Hz.
   * - ``port_stim_set(at)``
     - Drives the stimulus pin low. Then it makes the hardware drive the pin
       high when the counter reaches ``at``. It clears the compare flag.
       ``stim_arm()`` calls it with interrupts locked.
   * - ``port_stim_stop()``
     - Drives the stimulus pin low and keeps it low.
   * - ``port_stim_force(high)``
     - Drives the stimulus pin to a fixed level, for the static check.
   * - ``port_resp_irq_init()``
     - Configures the response pin as an interrupt on the rising edge, for
       an app with its own ISR. The app enables ``PORT_RESP_IRQN`` itself.
   * - ``port_debug_reset(buf, len)``
     - Undoes debugger settings that change the behavior of the core in
       sleep, if the SoC permits it. Writes the old value as text to
       ``buf``.

The apps do not call the port directly, except ``port_debug_reset()``.
They use the stimulus interface of ``stim.h`` (see :doc:`common-modules`).

.. _benchguide-board-nucleo:

Board ``nucleo_g474re``
-----------------------

:doc:`../howto/wire-the-nucleo-g474re` gives the steps to connect the
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

Board ``nrf52840dk``
--------------------

.. list-table::
   :widths: 30 70

   * - Board target
     - ``nrf52840dk/nrf52840`` (nRF52840 DK, Cortex-M4F at 64 MHz)
   * - Port name
     - ``nrf52840dk/timer3-ppi-gpiote``
   * - Stimulus timer
     - TIMER3 (32 bits), prescaler 0, at 16 MHz. The port keeps the HF
       crystal on for the whole run.
   * - Counts per core cycle
     - 1 count is 4 core cycles.
   * - Interconnect
     - The COMPARE[0] event of TIMER3 goes through a PPI channel to the SET
       task of a GPIOTE channel. ``nrfx_gppi`` allocates the channel
       (``CONFIG_NRFX_GPPI=y`` in ``port.conf``).
   * - Stimulus pin
     - D2 (P1.03), ``stim-gpios``, GPIOTE channel in task mode
   * - Response pin
     - A3 (P0.29), GPIOTE IN event. ``PORT_RESP_IRQN`` is the GPIOTE IRQ.
   * - Wire
     - D2 to A3. D2 drives, A3 reads.
   * - Own response IRQ
     - ``resp_irq_own.overlay`` disables the GPIOTE for the GPIO driver.
       The nRF52840 has one GPIOTE for both ports, so the GPIO driver then
       has no pin interrupts on P0 and P1. In the stock path, the port gets
       its GPIOTE channel from the allocator of the GPIO driver.
   * - System timer and tick phase
     - RTC1 at 32768 Hz, with no 64-bit counter (32-bit fallback). The
       default tick rate is 32768 ticks/s, so a tick is 1 RTC cycle and the
       phase is always 0. ``ticks_1024.conf`` sets 1024 ticks/s: a tick is
       32 RTC cycles (977 us), and the phase has 32 steps of 30.5 us. This
       fragment also changes the kernel: timeouts round to 977 us.
   * - ``debug_reg_at_boot``
     - ``dhcsr=<value>``. The SoC has no DBGMCU. Bit 0 of DHCSR
       (``C_DEBUGEN``) is 1 while a debugger is connected.
   * - ``boards.yaml``
     - Modules ``cmsis_6``, ``hal_nordic``. Flash with ``nrfutil`` (the
       ``.hex``). ``--serial-number`` selects the probe.
       ``status: untested``.

Examine these items first on the hardware:

- The flash commands are not tested.
- ``port_stim_now()`` is not a register read. A TIMER has no counter
  register: the function triggers the capture task of channel 1 and then
  reads ``CC[1]``. An interrupt between the two accesses can capture again.
  Then the interrupted code gets the later value.
- The delay from the compare event through PPI and GPIOTE to the pin is
  part of each latency.
- The system timer driver ``nrf_rtc_timer`` also masks zero-latency IRQs in
  its locked sections. Thus the ``zli`` path can see delays from the timer
  driver.
- Without ``ticks_1024.conf``, the phase histograms have one bin only.
- ``clock_drift_cyc`` is ``n/a``, because the TIMER and the RTC have
  different clocks.
- While a debugger is connected, the SoC stays in debug interface mode, and
  clocks stay on in sleep. Software cannot stop this mode. Disconnect the
  debugger or do a power cycle before a run, and examine
  ``debug_reg_at_boot``.

Board ``nrf54l15dk``
--------------------

.. list-table::
   :widths: 30 70

   * - Board target
     - ``nrf54l15dk/nrf54l15/cpuapp`` (nRF54L15 DK, Cortex-M33 at 128 MHz)
   * - Port name
     - ``nrf54l15dk/timer00-dppi-gpiote20``
   * - Stimulus timer
     - TIMER00 (32 bits), prescaler 0, at 128 MHz. A ``BUILD_ASSERT`` makes
       sure that TIMER00 runs at 128 MHz. The port keeps the HF crystal on
       for the whole run.
   * - Counts per core cycle
     - 1 (TIMER00 counts the core clock)
   * - Interconnect
     - TIMER00 COMPARE[0] goes through DPPIC00, a PPIB bridge and DPPIC20 to
       the SET task of a GPIOTE20 channel. ``nrfx_gppi`` allocates the
       channels (``CONFIG_NRFX_GPPI=y`` in ``port.conf``).
   * - Stimulus pin
     - P1.11, ``stim-gpios``, GPIOTE20 channel in task mode
   * - Response pin
     - P1.12, GPIOTE20 IN event. ``PORT_RESP_IRQN`` is the GPIOTE20 IRQ.
   * - Wire
     - P1.11 to P1.12 on the "PORT P1" header. The DK has no Arduino
       header.
   * - Own response IRQ
     - ``resp_irq_own.overlay`` disables GPIOTE20 for the GPIO driver. The
       GPIO driver then has no pin interrupts on P1. GPIOTE30 (port P0)
       stays with the driver.
   * - System timer and tick phase
     - GRTC at 1 MHz, with a 64-bit counter. The default tick rate is
       31250 ticks/s, so a tick is 32 GRTC cycles (32 us). The phase has 32
       steps of 1 us (128 core cycles).
   * - ``debug_reg_at_boot``
     - ``dhcsr=<value>``, as on the nRF52840 DK.
   * - ``boards.yaml``
     - Modules ``cmsis_6``, ``hal_nordic``. Flash with ``nrfutil`` (the
       ``.hex``). ``--serial-number`` selects the probe. The console
       (``uart20``) is on the second VCOM of the DK (interface ``if02``
       of the J-Link OB). ``status: untested``.

Examine these items first on the hardware:

- The flash commands are not tested.
- ``port_stim_now()`` is a capture task and a read, as on the nRF52840 DK.
- The delay from the compare event through DPPI, the PPIB bridge and
  GPIOTE20 to the pin is part of each latency.
- ``clock_drift_cyc`` is ``n/a``, because TIMER00 and the GRTC have
  different clocks.
- The debug interface mode, as on the nRF52840 DK.

Board ``mimxrt1060_evk``
------------------------

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
