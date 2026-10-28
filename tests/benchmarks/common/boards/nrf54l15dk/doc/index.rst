.. _benchguide-board-nrf54l15dk:

Board ``nrf54l15dk``
====================

The :term:`board port` ``nrf54l15dk`` (nRF54L15 DK) is in
``tests/benchmarks/common/boards/nrf54l15dk/``. This page is its documentation,
beside its code. :doc:`/reference/boards` gives the structure of a port
and its contract.

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
