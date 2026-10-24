Hardware setup
==============

This page describes the setup for the only board that the suite supports
today, the NUCLEO-G474RE. :doc:`boards` lists the board-specific code.

Parts and wiring
----------------

- One NUCLEO-G474RE board.
- One USB cable to the ST-LINK connector of the board. The ST-LINK gives
  the flash interface and the console (``/dev/ttyACM0``, 115200 baud).
- One wire from D2 to A3 on the Arduino header.

.. list-table::
   :header-rows: 1
   :widths: 15 15 70

   * - Header pin
     - MCU pin
     - Function
   * - D2
     - PA10
     - Stimulus output. PA10 is also TIM2 channel 4. TIM2 makes the edge by
       output compare.
   * - A3
     - PB0
     - Response input. PB0 is on EXTI line 0, which has its own interrupt
       vector (``EXTI0_IRQn``).

Make sure that the wire is connected before you start a run. Each app with
the TIM2 stimulus does a static check at start-up (see
:ref:`benchguide-static-check`). If the static check fails, the app prints
``LAT ERROR`` and stops.

To do a test of the wire alone, build and flash ``loopback_check``. Use
these commands in the root folder of the safety repository, in a west
workspace:

.. code-block:: console

   west build -b nucleo_g474re -d build/loopback_check tests/benchmarks/loopback_check
   west flash -d build/loopback_check -r openocd

If the wire is good, the console shows ``RESULT: OK``. The
``loopback_check`` app is also a Twister test with a console harness.

How the app calculates the latency
----------------------------------

TIM2 is a 32-bit timer. The stimulus code (``common/src/stim.c``) sets it
up as follows:

- The prescaler is 0, and the auto-reload value is ``UINT32_MAX``. TIM2
  counts each cycle of its clock and wraps after 2\ :sup:`32` cycles.
- TIM2 runs at the core clock. A ``BUILD_ASSERT`` in ``stim.c`` makes sure
  that the AHB prescaler and the APB1 prescaler are 1.
- Channel 4 is in output compare mode, without preload, with active-high
  polarity.

To program the next edge, ``stim_arm()`` does these steps:

#. It sets channel 4 to "forced inactive". PA10 goes low.
#. It calculates the time of the next edge (see
   :ref:`benchguide-stim-modes`).
#. It calculates the tick phase of that time (see
   :ref:`benchguide-tick-phase`).
#. It writes the time to ``CCR4`` and clears the ``CC4`` flag.
#. It sets channel 4 to "active on match". When ``TIM2->CNT`` reaches
   ``CCR4``, PA10 goes high.

The wire takes the rising edge to PB0. EXTI line 0 then starts the
interrupt. The measurement point reads ``TIM2->CNT`` as its first action.
The latency is:

.. code-block:: text

   latency = TIM2->CNT at the measurement point - CCR4

The subtraction is in unsigned 32-bit arithmetic, so a wrap of TIM2
between the edge and the measurement point gives the correct value. TIM2
counts also while the core sleeps in WFI, so the latency includes the
wake-up from WFI.

The ISR also reads the ``CC4`` flag of TIM2 (``stim_fired()``). If an EXTI0
interrupt comes without this flag, the edge did not come from the
stimulus. The app counts such an edge in ``spurious_edges``.

.. _benchguide-stim-modes:

Random and fixed stimulus
-------------------------

The Kconfig choice ``LATBENCH_STIM_MODE`` selects how the stimulus
calculates the time of the next edge.

``LATBENCH_STIM_RANDOM`` (default)
   The next edge comes a random time after the call of ``stim_arm()``. The
   time is in [``LATBENCH_STIM_MIN_US``, ``LATBENCH_STIM_MAX_US``). The random
   generator is xorshift32 with a fixed seed. Thus each run uses the same
   sequence of delays. The random part prevents a lock of the stimulus to
   the phase of the system timer.

``LATBENCH_STIM_FIXED``
   The next edge comes ``LATBENCH_STIM_PERIOD_US`` microseconds plus
   ``LATBENCH_STIM_PERIOD_ADJ_CYC`` cycles after the previous edge. The
   period does not depend on the latency. If the code arms the next edge
   less than 1000 cycles before its time, the stimulus counts an overrun
   (``stim_overruns``). Then it starts a new period from the time of the
   arm call.

With a fixed period of a whole number of ticks, all edges have the same
tick phase. ``LATBENCH_STIM_PERIOD_ADJ_CYC`` moves the phase by that number
of cycles for each edge. A small value scans the full tick slowly. For
example, 1 cycle at 170 MHz and 10000 ticks/s scans the tick in 17000
edges.

In all apps, only one edge is in flight at a time. The code that handles
an edge arms the next edge.

.. _benchguide-tick-phase:

Tick phase
----------

The tick phase of an edge is its position in the kernel tick, in cycles
after the tick boundary (0 to ``tick_period_cyc - 1``). The system timer
interrupts come at phase 0. The phase histograms (see
:ref:`benchguide-phase-hist`) use this value to show where in the tick a
latency comes from.

The timer driver keeps its tick boundaries at multiples of the tick
period in the count of ``k_cycle_get_64()``. TIM2 does not know this grid.
Thus ``stim_arm()`` reads ``TIM2->CNT`` and ``k_cycle_get_64()`` together,
with interrupts locked, and calculates:

.. code-block:: text

   phase = (k_cycle_get_64() + (t_edge - TIM2->CNT)) mod tick_period_cyc

The code uses a fresh pair of readings for each edge, not a reference from
the start of the run. :doc:`pitfalls` gives the reason.

The stimulus module prints two checks of the phase as ``LAT META``:

``tick_phase_check`` and ``tick_phase_check_end``
   At the start and at the end of the run, the main thread sleeps for one
   tick. Then it calculates its own phase. A thread that wakes from a
   one-tick sleep runs shortly after a tick boundary. Thus the value must
   be small: the system timer ISR and one context switch.

``clock_drift_cyc``
   The number of cycles that ``k_cycle_get_64()`` fell behind TIM2 since
   ``stim_init()``. A negative value means that it ran ahead.
   ``clock_elapsed_cyc`` gives the elapsed cycles of ``k_cycle_get_64()``
   for the same time.

The phase code needs the SysTick driver and a 64-bit cycle counter
(``CONFIG_CORTEX_M_SYSTICK`` and ``CONFIG_TIMER_HAS_64BIT_CYCLE_COUNTER``). A
``BUILD_ASSERT`` in ``stim.c`` makes sure that both are set.

Clock overlays
--------------

The board default is a core clock of 170 MHz. The folder ``common/clocks/``
has two devicetree overlays that change the core clock:

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
