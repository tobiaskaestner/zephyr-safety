Method and hardware setup
=========================

This page describes the measurement method and the hardware setup. The
method is the same on each board. The board port supplies the hardware
parts (see :doc:`boards`). The examples on this page are for the
NUCLEO-G474RE, the only board with data points today.

The method
----------

The method needs these hardware parts:

- A stimulus timer. This is a free-running 32-bit up-counter with an
  output compare channel.
- A stimulus pin. At the compare value, the timer hardware drives this pin
  high, with no software in the path.
- A response pin with an interrupt on the rising edge. This is the
  ``resp-gpios`` property of the ``zephyr,user`` devicetree node.
- A wire from the stimulus pin to the response pin.

The time stamp of the edge is the compare value. The measurement point
reads the counter of the stimulus timer. Thus the latency is:

.. code-block:: text

   latency = stim_now() at the measurement point - stim_edge()

The unit of the latency is one count of the stimulus timer. If the
stimulus timer runs at the core clock, one count is one core cycle. The
output gives both clocks (``stim_timer_hz`` and ``core_hz``).

The subtraction is in unsigned 32-bit arithmetic. Thus a wrap of the
counter between the edge and the measurement point gives the correct
value. The timer counts also while the core sleeps in WFI, so the latency
includes the wake-up from WFI.

The ISR also reads the compare flag of the timer (``stim_fired()``). If a
response interrupt comes without this flag, the edge did not come from
the stimulus. The app counts such an edge in ``spurious_edges``.

Hardware setup on the NUCLEO-G474RE
-----------------------------------

:doc:`boards` gives the pins and the wire of the other boards.

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
     - Stimulus pin. PA10 is also TIM2 channel 4. TIM2 is the stimulus
       timer.
   * - A3
     - PB0
     - Response pin. PB0 is on EXTI line 0, which has its own interrupt
       vector (``EXTI0_IRQn``).

The port sets up TIM2 as follows (``common/boards/nucleo_g474re/port.c``):

- The prescaler is 0, and the auto-reload value is ``UINT32_MAX``. TIM2
  counts each cycle of its clock and wraps after 2\ :sup:`32` cycles.
- TIM2 runs at the core clock. A ``BUILD_ASSERT`` makes sure that the AHB
  prescaler and the APB1 prescaler are 1.
- Channel 4 is in output compare mode, without preload, with active-high
  polarity.

Make sure that the wire is connected before you start a run. Each app with
the stimulus does a static check at start-up (see
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

How the app arms an edge
------------------------

To program the next edge, ``stim_arm()`` does these steps:

#. It calculates the time of the next edge from the count ``now`` that
   the caller read (see :ref:`benchguide-stim-modes`).
#. It locks interrupts.
#. It reads a fresh count of the stimulus timer and a fresh count of the
   system timer.
#. If the edge time is less than 1000 counts after the fresh count, the
   edge is late. Then ``stim_arm()`` moves the edge to 1000 counts after
   the fresh count, and counts it in ``stim_late``.
#. It calculates the tick phase of the edge from the fresh pair of counts
   (see :ref:`benchguide-tick-phase`).
#. It calls ``port_stim_set()``. On the NUCLEO-G474RE, this function sets
   channel 4 to "forced inactive", so PA10 goes low. Then it writes the
   time to ``CCR4``, clears the ``CC4`` flag, and sets channel 4 to "active
   on match". When ``TIM2->CNT`` reaches ``CCR4``, PA10 goes high.
#. It unlocks interrupts.

The check for a late edge is necessary because an ISR can run between the
read of ``now`` and the write of the compare value. If the ISR takes more
time than the delay to the edge, the compare value is in the past. Then
the timer reaches it only after a full wrap of the 32-bit counter (25 s at
170 MHz), and a repetition can time out. ``stim_late`` other than 0 shows
that this occurred (see :doc:`pitfalls`).

The wire takes the rising edge to the response pin, and its interrupt
starts. The measurement point reads ``stim_now()`` as its first action.

The diagram below shows one edge of ``irq_latency``. In this app, the ISR
of the previous edge arms the edge. In ``wake_latency`` and
``thread_latency``, a thread arms it. After the random delay, the hardware
makes the edge, and the ISR reads the counter. :ref:`benchguide-diagrams`
tells you how to read the diagram.

.. timeline-viz:: diagrams/stim-method.tdl
   :name: benchguide-fig-stim-method

   One edge. Left: ``stim_arm()`` in the ISR of the previous edge. Right:
   the edge, the hardware path to the ISR, and the time stamp. The
   bracket is the latency that the app records.

.. _benchguide-diagrams:

How to read the timing diagrams
-------------------------------

The timing diagrams in this guide show the sequence of one edge. They are
schematic: the width of a box does not show a duration. For measured
durations, see the histograms of a run.

- Each lane is one run context. The lanes are in three groups: the core
  (hardware and the interrupt mask), the ISRs, and the threads.
- In each group, the lane with the highest priority is at the top. The
  box next to the name gives the priority: the ``IRQ_CONNECT()`` priority
  for an ISR (``low`` for PendSV), the thread priority for a thread. Two
  lanes with the same priority have one joined box with ``=``.
- A filled box is code that runs. A dotted box is the CPU in WFI. A
  dashed box without a fill is a thread that waits: blocked, or ready
  but preempted.
- A hatched box on the ``BASEPRI`` lane is a section with interrupts
  locked (``irq_lock()``).
- The orange vertical line is the edge. A black vertical line is a time
  stamp. Its name is the name of the variable in the code.
- A bracket below the lanes is a histogram of the app. Its label is the
  name of the histogram in the output (see :doc:`output`).
- In the HTML output, move the pointer onto a box to see what the code
  does at that step.

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
   ``LATBENCH_STIM_PERIOD_ADJ_CYC`` counts after the previous edge. The
   period does not depend on the latency. If the code arms the next edge
   less than 1000 counts before its time, the stimulus counts an overrun
   (``stim_overruns``). Then it starts a new period from the time of the
   arm call.

The stimulus converts the microsecond values to counts of the stimulus
timer (``us * stim_timer_hz / 1000000``, in 64-bit arithmetic). The 1000
counts of the overrun margin are in counts of the stimulus timer too.

On the NUCLEO-G474RE, TIM2 and the system timer count the same clock. With
a fixed period of a whole number of ticks, all edges then have the same
tick phase. ``LATBENCH_STIM_PERIOD_ADJ_CYC`` moves the phase by that number
of cycles for each edge. A small value scans the full tick slowly. For
example, 1 cycle at 170 MHz and 10000 ticks/s scans the tick in 17000
edges.

In all apps, only one edge is in flight at a time. The code that handles
an edge arms the next edge.

.. _benchguide-tick-phase:

Tick phase
----------

The tick phase of an edge is its position in the kernel tick, in system
timer cycles after the tick boundary (0 to ``tick_period_cyc - 1``). The
system timer interrupts come at phase 0. The phase histograms (see
:ref:`benchguide-phase-hist`) use this value to show where in the tick a
latency comes from.

The timer driver keeps its tick boundaries at multiples of the tick
period in the count of ``k_cycle_get_64()``. The stimulus timer does not
know this grid. Thus ``stim_arm()`` reads ``stim_now()`` and the system
timer count (``sys_cyc()``) together, with interrupts locked, and
calculates:

.. code-block:: text

   phase = (sys_cyc() + to_sys(t_edge - stim_now())) mod tick_period_cyc

``sys_cyc()`` is ``k_cycle_get_64()``. If the timer driver has no 64-bit
counter, it is ``k_cycle_get_32()``, and the tick period must be a power of
two cycles (see :doc:`boards`).

``to_sys()`` converts counts of the stimulus timer to system timer cycles.
If the two clocks are the same (``stim_timer_hz`` = ``sys_timer_hz``), it
does not change the value. The code uses a fresh pair of readings for
each edge, not a reference from the start of the run. :doc:`pitfalls` gives
the reason.

The stimulus module prints two checks of the phase as ``LAT META``:

``tick_phase_check`` and ``tick_phase_check_end``
   At the start and at the end of the run, the main thread sleeps for one
   tick. Then it calculates its own phase. A thread that wakes from a
   one-tick sleep runs shortly after a tick boundary. Thus the value must
   be small: the system timer ISR and one context switch.

``clock_drift_cyc``
   The number of cycles that ``k_cycle_get_64()`` fell behind the stimulus
   timer since ``stim_init()``. A negative value means that it ran ahead.
   ``clock_elapsed_cyc`` gives the elapsed cycles of ``k_cycle_get_64()``
   for the same time. If the two clocks are not the same, the value is
   ``n/a``, because the stimulus timer can wrap before a long run ends.

On the NUCLEO-G474RE, the SysTick driver has the 64-bit counter by
default only above 60 MHz. Thus ``port.conf`` of the
port sets ``CONFIG_CORTEX_M_SYSTICK_64BIT_CYCLE_COUNTER=y``, for the 16 MHz
clock overlay.

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
