Measurement method
==================

This page describes the measurement method. The method is the same on
each board. The :term:`board port` supplies the hardware
parts (see :doc:`../reference/boards`). The examples on this page are for the
NUCLEO-G474RE, the only board with data points today.

Why the stimulus comes from hardware
------------------------------------

If the measured software makes the stimulus itself, the CPU is never in
a critical section at that moment. Then the measurement shows only the
best case. The ``loopback_check`` :term:`app` is an example: its main thread sets
the pin and then waits in a busy loop, so all its :term:`samples <Sample>` have the same
value.

For this reason, the apps of the suite use a hardware timer as the
stimulus. The timer sets the pin at a programmed time, which is
asynchronous to the software. The edge can come while the kernel holds a
lock, while the system timer ISR runs, or while the CPU sleeps. The time
stamp of the edge is the compare value of the timer, so it does not
depend on software (see :doc:`decisions/0001-stimulus-from-hardware`).

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
170 MHz), and a :term:`repetition` can time out. ``stim_late`` other than 0 shows
that this occurred (see :doc:`measurement-effects`).

The wire takes the rising edge to the response pin, and its interrupt
starts. The measurement point reads ``stim_now()`` as its first action.

The diagram below shows one edge of ``irq_latency``. In this app, the ISR
of the previous edge arms the edge. In ``wake_latency`` and
``thread_latency``, a thread arms it. After the random delay, the hardware
makes the edge, and the ISR reads the counter. :ref:`benchguide-diagrams`
tells you how to read the diagram.

.. timeline-viz:: ../diagrams/stim-method.tdl
   :name: benchguide-fig-stim-method

   One edge. Left: ``stim_arm()`` in the ISR of the previous edge. Right:
   the edge, the hardware path to the ISR, and the time stamp. The
   bracket is the latency that the app records.

.. _benchguide-stim-modes:

Random and fixed stimulus
-------------------------

The Kconfig choice ``LATBENCH_STIM_MODE`` selects how the stimulus
calculates the time of the next edge.

``LATBENCH_STIM_RANDOM`` (default)
   The next edge comes a random time after the call of ``stim_arm()``. The
   time is in [``LATBENCH_STIM_MIN_US``, ``LATBENCH_STIM_MAX_US``). The random
   generator is xorshift32 with the seed ``LATBENCH_STIM_SEED`` (default
   ``0x2545f491``, the seed of all runs before the option). Thus each run
   with the same seed uses the same sequence of delays, and gives the same
   histogram on the same image (shown on two hosts). The random part
   prevents a lock of the stimulus to the phase of the system timer. A
   different seed shows how much a result depends on the sequence. The
   log has the seed in ``stim_seed``.

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
two cycles (see :doc:`../reference/boards`).

``to_sys()`` converts counts of the stimulus timer to system timer cycles.
If the two clocks are the same (``stim_timer_hz`` = ``sys_timer_hz``), it
does not change the value. The code uses a fresh pair of readings for
each edge, not a reference from the start of the run. :doc:`measurement-effects` gives
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

The system timer and the tick phase
-----------------------------------

The tick phase is in cycles of the system timer (see
:ref:`benchguide-tick-phase`). Its meaning depends on the system timer of
the board:

- If the system timer counts the core clock (SysTick), the phase has the
  resolution of one count of the stimulus timer.
- If the system timer has a slow clock (RTC, GRTC), the phase has the
  resolution of one system timer cycle. A tick of a few cycles gives a
  phase histogram with a few steps only.

``stim.c`` reads the system timer count with ``k_cycle_get_64()``. If the
timer driver does not have a 64-bit counter
(``CONFIG_TIMER_HAS_64BIT_CYCLE_COUNTER=n``), ``stim.c`` uses the 32-bit
count of ``k_cycle_get_32()``. A wrap of the 32-bit count keeps the tick
grid only if the tick period is a power of two cycles. A ``BUILD_ASSERT``
in ``stim.c`` makes sure of this.

If the stimulus timer and the system timer have different clocks,
``stim.c`` converts the counts for the phase. ``clock_drift_cyc`` is then
``n/a``.

.. _benchguide-method-swtrig:

The software trigger and the hardware path
------------------------------------------

The latency of an edge sample starts at the compare match of the
stimulus timer. Thus it contains a hardware path that the software of an
application does not see:

#. The compare match sets the output of the timer channel.
#. The output drives the stimulus pin, and the wire takes the edge to the
   response pin.
#. The input synchronizer of the response pin samples the edge.
#. The EXTI line detects the edge and pends the IRQ in the NVIC.

The upstream interrupt benchmark (Zephyr PR 117170) does not have this
path. It pends the IRQ from software with a store to ``NVIC->STIR``. The
option ``LATBENCH_SWTRIG`` adds the same trigger to ``irq_latency`` and
``wake_latency``, beside the edges, in the same image (see
:ref:`benchguide-irq-latency-swtrig`).

Both stimuli end at the same time stamp in the same ISR. Thus:

.. code-block:: text

   hardware path = irq - irq_sw + offset

The offset is the time from the counter value of the ``t0`` read to the
pend of the IRQ by the ``STIR`` store. It contains the rest of the read,
the store of ``t0``, the ``STIR`` store and the time until the NVIC sees
the pend. The first three take about ``sw_read_cyc`` + 2 cycles. The
time of the last one is not known. Thus a difference ``irq - irq_sw`` of
d cycles gives a hardware path of at least d + ``sw_read_cyc`` + 2
cycles only if the NVIC sees the pend at once.

Use ``irq`` of a busy build for the difference. An idle edge also
contains the wake-up from WFI, and the software trigger never meets WFI.

On the NUCLEO-G474RE (sub-study ``measurement-validity/stimulus-path``,
code in RAM) the edge from a busy CPU is 2 cycles faster than the
``STIR`` path, for the wrapped and the direct path. ``sw_read_cyc`` is 3.
Thus the pin, the synchronizer and the EXTI line cost about as much as
the ``STIR`` pend: a few cycles. The method cannot split the two. For a
comparison with a benchmark that uses ``STIR``, the entry numbers of the
study need no correction for the hardware path. The edge from an idle
CPU is 5 cycles slower (the wake-up from WFI).

The software trigger is synchronous to the software: it never meets a
kernel lock, a system timer ISR or WFI, except when such an event comes
in the few cycles between ``t0`` and the store. Thus ``irq_sw`` shows the
floor of the entry path, but not its tail. The tail needs the edges.

What the method needs from a board
----------------------------------

A new board must have these properties, or an equivalent:

- A 32-bit hardware timer with an output compare channel that drives a
  pin with no software in the path. On the Nordic SoCs, a (D)PPI
  connection to a GPIOTE task is the equivalent.
- A pin with an interrupt on the rising edge, and a wire from the timer
  pin to this pin.
- A system timer with a 64-bit cycle counter, or a tick period of a power
  of two cycles, for the tick phase.
- A serial console that the host can read without loss at the output rate
  of the apps.
