.. _benchguide-m4:

M4: interrupt mask time per call site
=====================================

M4 measures how long the CPU masks the interrupts, for each place in the
code that masks them. It also measures the time of each ISR body. The
values are in DWT cycles (core clock cycles).

M4 needs a Zephyr :term:`tree` with the hooks of the branch
``tkaestner/latency-irqoff-hook``. In ``validation/trees/`` this tree is
``ws-up-irqoff``. The hooks are only for Cortex-M with BASEPRI (ARMv7-M,
ARMv8-M Mainline) and the legacy context switch (``USE_SWITCH=n``).

.. important::

   The hooks make each mask section longer, and they add time to the
   interrupt path and to the wake path. The latency histograms of an M4
   run are not data. Each M4 log has ``LAT META m4=1`` and a
   ``m4_note`` line that says this. Use only the M4 tables of such a
   run.

How it works
------------

The Zephyr branch adds two Kconfig options:

``CONFIG_ARM_IRQ_MASK_HOOKS``
   The CPU calls ``z_arm_irq_mask_hook_begin()`` when it starts to mask the
   interrupts of ``irq_lock()``, and ``z_arm_irq_mask_hook_end()`` before
   it stops:

   - ``arch_irq_lock()`` with an old BASEPRI of 0, and
     ``arch_irq_unlock()`` with a key of 0. ``k_spin_lock()`` and
     ``arch_swap()`` use these functions.
   - ``z_arm_pendsv()``: from ``BASEPRI_MAX`` to the restore of the
     BASEPRI of the incoming thread.
   - ``arch_cpu_idle()``: the section of the idle thread ends before
     ``WFI``. A new section starts after the wake-up and ends at
     ``cpsie i``. The sleep is not in a section.

``CONFIG_ARM_IRQ_MASK_HOOKS_ISR``
   ``_isr_wrapper()`` and ``sys_clock_isr()`` call
   ``z_arm_isr_hook_enter()`` and ``z_arm_isr_hook_exit()`` around the
   ISR body.

``common/src/irqmask.c`` supplies the four functions. A section is a
*site*: the return address of the start hook (it points into the code
that masks), the exception number at the start (0 in a thread) and the
kind (mask section or ISR body). The site table
(``common/include/latbench/irqmask_table.h``) has 64 entries. Each entry
has count, sum, min, max, the end address of the longest section and a
histogram. The bins are 1 cycle wide below 16 cycles. Each octave above
has 8 bins, up to 65535 cycles. A value of 65536 cycles or more counts in
the overflow bin and in max. If the table is full, a new site counts
only in ``dropped``.

Two sections never overlap: while a section is open, no interrupt that
can start a section can occur. Thus one set of start values is
sufficient.

An app with M4 calls ``irqmask_start()`` after the load starts,
``irqmask_stop()`` at the end of the run and ``irqmask_print()`` before
``lat_done()`` (``latbench/irqmask.h``). Without
``CONFIG_ARM_IRQ_MASK_HOOKS`` these functions are empty, and
``common/irqmask.cmake`` adds no source file. ``wake_latency`` and
``thread_latency`` have M4.

Calibration
-----------

``irqmask_start()`` measures the hooks before the run, as the minimum of
256 tries:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Line
     - Value
   * - ``m4_floor_cyc``
     - The value of an empty section, ``irq_unlock(irq_lock())``. Each
       section value contains it. ``m4.py`` subtracts it in ``max_net``.
   * - ``m4_pair_cost_cyc``
     - The extra CPU time of the hooks for one section, against the same
       BASEPRI writes without hooks. The real mask time of each section is
       longer than its value by the part of this cost after the end time
       stamp.
   * - ``m4_isr_floor_cyc``
     - The value of an empty ISR body measurement.

The probe (``LATBENCH_IRQMASK_PROBE_CYC``, ``LATBENCH_IRQMASK_PROBE_MS``)
is a thread that masks the interrupts for a known number of cycles. Its
site must show this length plus the floor. The IRQ tail of the same run
must show it too. Use the probe only to check the method.

Limits
------

- The return address names the function that contains the lock. All
  callers of a function that is not inlined (for example
  ``z_add_timeout()``) share one site. The context column splits them
  only by the exception number.
- The hooks make each lock larger. GCC with ``SIZE_OPTIMIZATIONS`` then
  can stop to inline a small lock wrapper. In the M4 builds
  ``sys_clock_lock()`` is a function, so all its callers share its site.
  In the builds without hooks it is inlined.
- Not covered: ``USE_SWITCH=y``, ARMv6-M, direct ISRs
  (``ISR_DIRECT_DECLARE()``), the hardware exception entry and exit, the
  code of ``_isr_wrapper()`` and ``sys_clock_isr()`` outside the hooks,
  and the direct BASEPRI write in the ISR exit hook itself.
- The DWT counter stops while the CPU sleeps. No section contains a
  sleep, but a measurement over a sleep is not possible with it. The
  window length comes from ``k_cycle_get_64()``.

Experiments
-----------

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - File
     - Content
   * - ``validation/empirical/latencies/st-measurement-validity/st-mask-instrumentation/ex-m4-validate/experiment.yaml``
     - Calibration, the probe, and the points of ``systick-prio-1m`` and
       of the WHEEL backend, for the check against the IRQ tail
   * - ``validation/empirical/latencies/st-mask-time/ex-m4-sweep/experiment.yaml``
     - Load timers 0/16/64/256 x sleeper threads 0/8/64 x time slicing
       on/off
   * - ``validation/empirical/latencies/st-mask-time/ex-m4-thread/experiment.yaml``
     - ``thread_latency`` with sem and mutex, 0 and 64 load timers
   * - ``validation/empirical/latencies/st-measurement-validity/st-mask-instrumentation/ex-m4-image-check/experiment.yaml``
     - Build check only: ``ws-up`` and ``ws-up-irqoff`` with the hooks
       off give the same code

The M4 points use smaller latency histograms (1024 fine bins and 1024
coarse bins of 64 cycles), because the site table takes 31 KB of RAM.
