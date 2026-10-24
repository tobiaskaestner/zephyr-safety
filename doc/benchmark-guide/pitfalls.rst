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
``TIM2->CNT`` and ``k_cycle_get_64()`` again for each edge, and calculates
the phase from this fresh pair. ``clock_drift_cyc`` in the output shows
the drift of a run. The experiment ``clock-drift`` measures it.

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

DBGMCU bits from a debugger
---------------------------

A debugger session can leave bits set in ``DBGMCU->CR`` that keep the
clocks on in the sleep modes. Then WFI does not behave as without a
debugger, and the latency from WFI changes. Each measurement app clears
``DBGMCU->CR`` at the start and prints the old value as
``dbgmcu_cr_at_boot``. ``loopback_check`` does not clear it.

The trees have different debug defaults
---------------------------------------

The two trees have different defaults for ``CONFIG_ASSERT`` and
``CONFIG_SPIN_VALIDATE``. Both options add code to the kernel paths that
the suite measures. Each measurement app sets both to ``n`` in its
``prj.conf``, so that the trees build the same set of debug code. The
``LAT CFG`` line shows the values of the build.

EXTI line 0 and TIM2 belong to the board
----------------------------------------

The board devicetree gives TIM2 to ``pwm2`` (the LED on PA5), and EXTI
line 0 to the GPIO interrupt driver. The overlays of the apps disable
``pwm2``. An app with its own EXTI0 ISR also needs the EXTI node without
line 0. In ``irq_latency``, a ``BUILD_ASSERT`` stops the build if the
interrupt path and the overlay do not agree.

Negative samples
----------------

If the measurement point runs before the programmed edge time, the
difference is negative and shows as a value of 2\ :sup:`31` or more. The
apps count each EXTI0 interrupt without a TIM2 compare match in
``spurious_edges``. A value other than 0 means that the data of the run
needs an analysis before you use it.
