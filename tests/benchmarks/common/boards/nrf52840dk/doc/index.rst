.. _benchguide-board-nrf52840dk:

Board ``nrf52840dk``
====================

The :term:`board port` ``nrf52840dk`` (nRF52840 DK) is in
``tests/benchmarks/common/boards/nrf52840dk/``. This page is its documentation,
beside its code. :doc:`/reference/boards` gives the structure of a port
and its contract.

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
