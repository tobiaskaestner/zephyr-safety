Pitfalls
========

This page lists the pitfalls that the work on the suite found so far,
and what the code does about each one.

The kernel cycle counter loses cycles
-------------------------------------

The count of ``k_cycle_get_64()`` loses a few cycles against a hardware
timer each time the SysTick driver programs SysTick again. Both count the
same clock, but the difference grows during a run. With time slicing,
each wake can program SysTick again for the slice timeout.

Thus a tick phase that the code calculates from a reference at the start
of the run moves away from the real tick grid. ``stim_arm()`` reads
the stimulus timer and ``k_cycle_get_64()`` again for each edge, and
calculates the phase from this fresh pair. ``clock_drift_cyc`` in the
output shows the drift of a run. The experiment ``clock-drift`` measures
it. The experiment ``clock-drift-fix`` examines a change of the SysTick
driver on the tree ``ws-safety-driftfix``.

.. _benchguide-systick-wrap:

The SysTick driver sees at most one counter wrap
------------------------------------------------

Know this property of the SysTick driver when you read
``clock_drift_cyc``. Between two reads of SysTick, the driver adds at most
one wrap of the counter to the kernel time. It programs a reload of at
least 10 us by default. This is correct only if the SysTick IRQ never
stays masked for longer than the shortest reload.

Long masked sections break this condition, for example timeout inserts
with many load timers. Then the counter wraps more than once, and the
kernel time loses whole reloads. ``clock_drift_cyc`` then includes these
lost reloads, not only the few cycles of each reprogram.

The devicetree property ``zephyr,min-timeout-cycles`` of the ``systick``
node sets a longer shortest reload. The port ``nucleo_g474re`` has two
overlays in ``common/boards/nucleo_g474re/systick/``:
``min_timeout_50us.overlay`` and ``min_timeout_200us.overlay``. The
experiment ``clock-drift-fix`` uses them.

Late edges
----------

An ISR can run between the read of the counter and the write of the
compare value. If it runs for longer than the delay to the edge, the
compare value is in the past. Then the timer reaches it only after a full
wrap of the 32-bit counter (25 s at 170 MHz). A repetition with many
samples can time out.

``stim_arm()`` writes the compare value with interrupts locked, after it
compares the edge time with a fresh count. It moves a late edge to 1000
counts after the fresh count and counts it in ``stim_late``. A late edge
has a correct latency, but its delay is not the delay of the stimulus
sequence.

Kconfig ignores some requested values
-------------------------------------

If a ``-DCONFIG_<SYM>=<value>`` names an option that the tree does not
define, the build stops (``Aborting due to Kconfig warnings``). Two other
cases do not stop the build:

- A value for an option whose dependencies are not met. Kconfig prints a
  warning and ignores the value. For example, ``LATBENCH_STIM_MIN_US`` has
  no effect with ``LATBENCH_STIM_FIXED=y``.
- Two members of the same choice set to ``y``. Kconfig uses one of them and
  ignores the other, with no warning. For example, a build with
  ``LATBENCH_WAKE_SEM=y`` and ``LATBENCH_WAKE_FIFO=y`` gives the ``sem``
  variant.

In both cases the build is successful, but the point does not measure
what its name says. ``run.py`` compares each value in ``kconfig`` of a
point with the ``.config`` of the build. If the ``.config`` does not have
the requested value, the run stops. This check does not examine the
values that come from ``conf_files``.

Debug register bits from a debugger
-----------------------------------

A debugger session can leave bits set in a debug register that keep the
clocks on in the sleep modes (``DBGMCU->CR`` on the NUCLEO-G474RE). Then
WFI does not behave as without a debugger, and the latency from WFI
changes. Each measurement app calls ``port_debug_reset()`` at the start.
On the NUCLEO-G474RE, this function clears the register and gives the old
value, which the app prints as ``debug_reg_at_boot``. ``loopback_check``
does not clear it.

The other SoCs have no such register. On the Nordic SoCs, the SoC stays in
debug interface mode while a debugger is connected, and software cannot
stop this mode. The port only prints DHCSR. Disconnect the debugger or do
a power cycle before a run. The RT1060 port prints ``CCM_CLPCR``.

The trees have different debug defaults
---------------------------------------

The two trees have different defaults for ``CONFIG_ASSERT`` and
``CONFIG_SPIN_VALIDATE``. Both options add code to the kernel paths that
the suite measures. Each measurement app sets both to ``n`` in its
``prj.conf``, so that the trees build the same set of debug code. The
``LAT CFG`` line shows the values of the build.

The board gives the timer and the IRQ to drivers
------------------------------------------------

On the NUCLEO-G474RE, the board devicetree gives TIM2 to ``pwm2`` (the LED
on PA5), and EXTI line 0 to the GPIO interrupt driver. ``stim.overlay`` of
the port disables ``pwm2``. An app with its own ISR on the response pin
also needs ``resp_irq_own.overlay``. The port adds it if the app sets
``LATBENCH_RESP_IRQ_OWN``.

``irq_latency`` sets ``LATBENCH_RESP_IRQ_OWN`` only if the interrupt path is
on the CMake command line. If the path comes from a Kconfig fragment, the
port does not add the overlay, and a ``BUILD_ASSERT`` stops the build.

Negative samples
----------------

If the measurement point runs before the programmed edge time, the
difference is negative and shows as a value of 2\ :sup:`31` or more. The
histogram counts such a value only in ``invalid`` (see
:ref:`benchguide-hist`). The apps count each response interrupt without a
compare match of the stimulus timer in ``spurious_edges``. A value other
than 0 in ``invalid`` or in ``spurious_edges`` means that the data of the
run needs an analysis before you use it.

Tick phase in the zero-latency ISR
----------------------------------

In the ``zli`` path of ``irq_latency``, the ISR calls ``stim_arm()``, which
reads ``k_cycle_get_64()``. BASEPRI does not mask a zero-latency IRQ. Thus
the read can interrupt the timer driver in its locked section and see an
inconsistent count. Only the phase histogram is at risk, not the latency.
