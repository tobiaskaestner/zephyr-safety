Common modules
==============

The folder ``common/`` has the code that all measurement apps share.

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - File
     - Content
   * - ``latbench_board.cmake``
     - Selects the board port. See :ref:`benchguide-latbench-cmake`.
   * - ``latbench.cmake``
     - Adds the common code to the ``app`` target. See
       :ref:`benchguide-latbench-cmake`.
   * - ``Kconfig``
     - The common Kconfig options (see :doc:`kconfig`).
   * - ``include/latbench/hist.h``, ``src/hist.c``
     - Histogram and phase histogram
   * - ``include/latbench/stim.h``, ``src/stim.c``
     - Stimulus, static check, response IRQ set-up, tick phase
   * - ``include/latbench/port.h``
     - The contract of a board port (see :doc:`boards`)
   * - ``boards/<board>/``
     - One board port for each board (see :doc:`boards`)
   * - ``include/latbench/load.h``, ``src/load.c``
     - Load generators: threads and timers
   * - ``include/latbench/meta.h``, ``src/meta.c``
     - Metadata lines and the end marker
   * - ``conf/lean.conf``
     - Kconfig fragment: ``TIMESLICING=n``, ``HW_STACK_PROTECTION=n``,
       ``MPU_STACK_GUARD=n``, ``SPEED_OPTIMIZATIONS=y``
   * - ``conf/use_switch.conf``
     - Kconfig fragment: ``USE_SWITCH=y`` (``arch_switch`` at the exception
       exit, not PendSV)

To use a Kconfig fragment, add it to ``conf_files`` of a point (see
:ref:`benchguide-experiment-file`).

.. _benchguide-hist:

Histogram
---------

``struct lat_hist`` records the samples of one quantity. Define it with
``LAT_HIST_DEFINE(var, name)``. The name is the key of the histogram in
the output and in the host tools. Thus each histogram of an app must have
its own name.

``lat_hist_add()`` adds one sample. If the value is 2\ :sup:`31` or more,
it only increments ``invalid`` (see below). Otherwise, it updates
``count``, ``sum``, ``min`` and ``max``, and then puts the value into one of
three bin ranges:

#. Fine bins. Each value from 0 to ``LATBENCH_HIST_BINS - 1`` has a bin of
   its own (1-cycle bins).
#. Coarse bins. These are optional. If ``LATBENCH_HIST_COARSE_BINS`` is
   not 0, the next values go into coarse bins. Each coarse bin is
   2\ :sup:`LATBENCH_HIST_COARSE_SHIFT` cycles wide.
#. Overflow. A larger value goes into the log2 bin of its magnitude
   (``ovf_log2[e]`` for 2\ :sup:`e` <= value < 2\ :sup:`e+1`), and
   ``overflow`` counts it. ``max`` records the largest value exactly.

The coarse bins let a histogram cover long latencies with less RAM. For
example, 2048 fine bins and 2048 coarse bins of 32 cycles cover 0 to 67583
cycles with the RAM of 4096 fine bins.

A value of 2\ :sup:`31` or more (``LAT_INVALID_MIN``) is a negative
difference: the measurement point ran before the programmed edge time.
It is not a latency. The histogram counts it only in ``invalid``. Thus
``count``, ``sum``, ``min``, ``max`` and the bins do not include it.
``lat_phase_add()`` ignores such a value.

``lat_hist_add()`` is safe in an ISR. Two contexts must not add to the same
histogram at the same time. ``lat_hist_print()`` prints the histogram (see
:doc:`output`).

.. _benchguide-phase-hist:

Phase histogram
---------------

``struct lat_phase`` records samples by the tick phase of their edge.
Define it with ``LAT_PHASE_DEFINE(var, name)``. Call
``lat_phase_init(p, stim_tick_period())`` before the first
``lat_phase_add()``. While the period is 0, ``lat_phase_add()`` does
nothing.

``lat_phase_init()`` refuses a period that is more than
``LAT_PHASE_PERIOD_MAX`` (``UINT32_MAX / LATBENCH_PHASE_BINS``), because the
bin calculation must fit in 32 bits. Then it prints
``LAT ERROR phase <name> period=<p> is larger than <max>`` and sets the
period to 0, so that the phase histogram stays empty.

The phase must be less than the period. ``lat_phase_add()`` does not
examine this condition (a known gap, see :doc:`unit-tests`).

The phase histogram divides the tick into ``LATBENCH_PHASE_BINS`` bins of
equal width. Bin ``b`` holds the phases from ``b * period / BINS`` to
``(b + 1) * period / BINS``. For each bin, it records the count, the
minimum, the maximum and the sum of the samples. Thus it shows the share
of the edges in each part of the tick and the latency in each part.

``lat_phase_print()`` prints the phase histogram.

Stimulus
--------

``common/include/latbench/stim.h`` declares the stimulus interface:

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Function
     - Purpose
   * - ``stim_init()``
     - Configures the response pin as an input and calls
       ``port_stim_init()``. Finds the tick period and prints the stimulus
       settings as ``LAT META``. Sleeps for one tick (phase check).
   * - ``stim_static_check()``
     - Drives the stimulus pin low and high (``port_stim_force()``) and
       reads the response pin. Prints ``static_check=ok`` or
       ``static_check=fail``.
   * - ``stim_resp_irq_init()``
     - Makes the response pin an interrupt on the rising edge, for an app
       with its own ISR. It does not enable the IRQ.
   * - ``STIM_RESP_IRQN``
     - The IRQ line of the response pin, for ``IRQ_CONNECT()`` and
       ``irq_enable()``.
   * - ``stim_resp_ack()``
     - Clears the pending flag of the response interrupt. An own ISR calls
       it.
   * - ``stim_now()``
     - Reads the counter of the stimulus timer.
   * - ``stim_edge()``, ``stim_edge_phase()``
     - The time stamp and the tick phase of the current edge.
   * - ``stim_fired()``
     - True if the stimulus timer reached the compare value since the last
       arm.
   * - ``stim_arm(now)``
     - Programs the next edge, with interrupts locked. It moves a late edge
       and counts it in ``stim_late`` (see :doc:`hardware`). Read
       ``stim_edge()`` and ``stim_edge_phase()`` of the current edge before
       this call.
   * - ``stim_stop()``
     - Drives the stimulus pin low and programs no new edge.
   * - ``stim_tick_period()``
     - The length of a kernel tick in system timer cycles.
   * - ``stim_print_stats()``
     - Prints ``stim_overruns``, ``stim_late``, the clock drift and the phase
       check at the end of the run.

:doc:`hardware` describes the edge, the stimulus modes and the tick
phase.

.. _benchguide-static-check:

Static check
~~~~~~~~~~~~

``stim_static_check()`` drives the stimulus pin low and then high
(``port_stim_force()``), with 10 microseconds of wait after each change,
and reads the response pin each time. The check passes if the response pin reads 0 and then 1. If the check
fails, each measurement app prints
``LAT ERROR static check failed (wire D2 -> A3?)`` and stops.

Load generators
---------------

``common/src/load.c`` starts a load that the Kconfig options
``LATBENCH_LOAD_*`` set. All random values come from fixed seeds, so each
run starts the same load. The load has its own random generator, so the
load does not change the sequence of the stimulus. An app calls
``load_start()`` after ``stim_init()`` and before the first ``stim_arm()``.
``load_print()`` stops the load timers and prints the load settings and
counters.

Load threads
~~~~~~~~~~~~

``LATBENCH_LOAD_THREADS`` sets the number of load threads (0 to 64). The
Kconfig choice ``LATBENCH_LOAD_THREAD_KIND`` sets what each thread does:

``LATBENCH_LOAD_THREAD_BLOCKED`` (default)
   The thread waits forever on a semaphore of its own. Thus it stays in a
   wait queue for the whole run. Priority: ``LATBENCH_LOAD_THREAD_PRIO``.

``LATBENCH_LOAD_THREAD_SLEEPER``
   The thread sleeps for a random time in [``LATBENCH_LOAD_SLEEP_MIN_MS``,
   ``LATBENCH_LOAD_SLEEP_MAX_MS``], in a loop. Each sleep adds a timeout
   to the timeout queue, and each wake is a timer expiry and a switch.
   Priority: ``LATBENCH_LOAD_THREAD_PRIO``. ``load_sleeper_wakes`` counts
   the wakes (approximately, the counter is not atomic).

``LATBENCH_LOAD_THREAD_BUSY``
   The thread runs a busy loop at the lowest application priority. All
   busy threads have the same priority. With ``CONFIG_TIMESLICING=y``, they
   change at each expiry of a time slice.

Load timers
~~~~~~~~~~~

``LATBENCH_LOAD_TIMERS`` sets the number of ``k_timer`` objects (0 to 512).
The Kconfig choice ``LATBENCH_LOAD_TIMER_KIND`` sets their kind:

``LATBENCH_LOAD_TIMER_PERIODIC`` (default)
   Each timer gets a random period in [``LATBENCH_LOAD_TIMER_MIN_MS``,
   ``LATBENCH_LOAD_TIMER_MAX_MS``] and a random first expiry. The expiry
   function runs in the system timer ISR. Each restart inserts a timeout
   into the timeout queue.

``LATBENCH_LOAD_TIMER_FAR``
   Each timer is a one-shot timer that expires one hour (plus ``i`` ticks)
   after the start. The timers stay in the timeout queue for the whole run
   and do not expire. Only the length of the queue changes.

The expiry function records its own tick phase in the phase histogram
``tmr``. The value of each sample is the phase itself. Thus ``tmr`` shows
where in the tick the system timer ISR runs.

SysTick priority
~~~~~~~~~~~~~~~~

The SysTick driver gives SysTick the same priority as an IRQ with
priority 0. If both are pending, SysTick goes first. If
``LATBENCH_SYSTICK_PRIO`` is 0 or more, ``load_start()`` sets this priority
for SysTick. With a value of 1, the stimulus IRQ (priority 0) can preempt
the SysTick ISR, but not its locked sections. ``load_print()`` prints the
priority that the NVIC has as ``systick_prio``. The option is available
only on a board with ``CONFIG_CORTEX_M_SYSTICK``.

.. _benchguide-meta:

Metadata
--------

``lat_meta_print(app, variant)`` prints ``LAT BEGIN`` and then the metadata
of the build. The metadata names the app, the variant, the Zephyr version
and the revision of the benchmark sources (``bench_rev``). It also gives
the board, the core clock, the tick rate and the number of samples. Then
it prints one ``LAT CFG`` line with the Kconfig options that change latency
(see :ref:`benchguide-lat-cfg`).

The core clock comes from ``port_core_hz()``. ``meta.c`` has a weak default
that returns the system timer clock. A board port gives the real value.

``lat_meta_kv(key, value)`` prints one more metadata line.
``lat_done()`` prints ``LAT DONE``. The host stops the capture at this line.

Each measurement app also prints ``debug_reg_at_boot``: the value that
``port_debug_reset()`` found in the debug register. The text depends on
the port (see :doc:`boards` and :doc:`pitfalls`).

.. _benchguide-code-placement:

Code placement
~~~~~~~~~~~~~~

The choice ``LATBENCH_CODE_PLACE`` in ``common/Kconfig`` selects how the
build places the code (see :ref:`benchguide-code-place` for when to use
each option):

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Option
     - Code placement
   * - ``LATBENCH_CODE_FLASH`` (default)
     - All code runs from flash, at the address that the linker gives it.
       ``code_pad`` is 0.
   * - ``LATBENCH_CODE_FLASH_PAD``
     - All code runs from flash. A code pad of ``LATBENCH_CODE_PAD_BYTES``
       moves all app and kernel code.
   * - ``LATBENCH_CODE_RAM``
     - The code of the hot paths runs from RAM. The pad moves only the
       relocated code.

``lat_meta_print()`` prints ``code_place`` (``flash``, ``flash-pad`` or
``ram``), ``code_pad`` and ``code_pad_at``. With ``LATBENCH_CODE_RAM`` it
also prints ``code_ram_region`` and ``code_ram_text`` (the start and the
end of the relocated code). ``code_place`` and ``code_pad`` come from one
``printk()`` call. Thus the default build has the same code size as a
build before the choice existed, and its functions have the same
addresses.

The code pad
^^^^^^^^^^^^

``src/pad.c`` has one function, ``lat_code_pad()``, which is never called.
Its size is ``LATBENCH_CODE_PAD_BYTES``. The pad must be a multiple of 4.
The reference in ``lat_meta_print()`` keeps the function from the garbage
collection of the linker.

In flash, ``latbench.cmake`` adds ``src/pad.c`` as the first source file,
so the pad comes before all other code of the app and the kernel. A pad of
N bytes moves all that code by N bytes, and nothing else changes. The
linker script sorts the ``.text.*`` sections by alignment, so the function
has an alignment of 4.

Hot code in RAM
^^^^^^^^^^^^^^^

With ``LATBENCH_CODE_RAM``, ``latbench.cmake`` calls
``zephyr_code_relocate()`` for these groups. An option selects each group,
and all are on by default:

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Option
     - Relocated files
   * - ``LATBENCH_CODE_RAM_KERNEL``
     - The library ``kernel``
   * - ``LATBENCH_CODE_RAM_ARCH``
     - The libraries ``arch__arm__core__cortex_m`` (without ``reset.S``,
       ``prep_c.c`` and ``vector_table.S``) and ``arch__arm__core__mpu``
   * - ``LATBENCH_CODE_RAM_DRIVERS``
     - The libraries ``drivers__timer``, ``drivers__gpio`` and
       ``drivers__interrupt_controller``, if the build has them
   * - ``LATBENCH_CODE_RAM_APP``
     - The library ``app``: the app, ``common/src`` and the board port

The build relocates the code and the read-only data of these files
(``LOCATION <region>_TEXT_RODATA``). Data and bss stay in their normal
sections. The startup code (``arch_data_copy()``) copies the relocated
sections from flash before ``z_cstart()``. Code that is not in the
groups stays in flash, for example the C library, ``libgcc`` and the
console. A call from RAM to flash goes through a linker veneer.

The board port gives the memory region in ``LATBENCH_CODE_RAM_REGION``
(see :doc:`boards`). If the port gives no region, the build stops with a
message. ``nucleo_g474re`` uses the CCM SRAM.

The pad is the first relocated function. Zephyr's
``gen_relocate_app.py`` sorts the sections by the base name of the object
file. Thus ``latbench.cmake`` compiles ``pad.c`` through a wrapper file
``0_latbench_pad.c``, in a library of its own. The script also skips a
file without an error if it does not find its object. A linker check
(``latbench_code_ram.ld`` in the build folder) stops the build in these
cases:

- the pad is not the first relocated function;
- one function of a group is not in the relocated code
  (``lat_meta_print``, ``z_setup_new_thread``, ``_isr_wrapper``,
  ``z_arm_mpu_init``, ``sys_clock_isr``).

Two facts of Zephyr's relocation limit what the build can relocate:

- For the default RAM region (``RAM``, the ``zephyr,sram`` node), the
  script puts the ``.bss`` and ``.noinit`` sections of a relocated file
  into the ``.data`` output section. For ``kernel/init.c`` this includes
  ``z_interrupt_stacks``, the stack that ``arch_data_copy()`` runs on. The
  copy overwrites its own return address, and the board locks up at boot.
  For this reason the build relocates only code and read-only data.
- With the region ``RAM`` and the MPU on, ``z_arm_mpu_init()`` makes the
  SRAM execute-never. The executable region of the relocated code
  (``CODE_DATA_RELOCATION_SRAM``) comes only later, in
  ``z_arm_configure_static_mpu_regions()``. Relocated code that runs
  between the two calls causes a fault (``K_ERR_ARM_MEM_INSTRUCTION_ACCESS``).
  For this reason ``kernel/init.c`` and the MPU driver stay in flash with
  this region. The CCM SRAM of ``nucleo_g474re`` has no MPU region, so
  this limit does not apply there.

.. _benchguide-latbench-cmake:

Build integration
-----------------

The ``CMakeLists.txt`` of a measurement app includes two files.

``common/latbench_board.cmake`` comes before ``find_package(Zephyr)``,
because the port adds devicetree overlays and Kconfig fragments. It does
these steps:

- It takes the board name from ``BOARD`` without qualifiers and revision.
  For example, ``nrf54l15dk/nrf54l15/cpuapp`` gives ``nrf54l15dk``, and
  ``mimxrt1060_evk@C/mimxrt1062/qspi`` gives ``mimxrt1060_evk``.
- It includes ``common/boards/<board>/port.cmake``. If this file does not
  exist, the build stops with ``no board port for <board>``.
- If the app sets ``LATBENCH_RESP_IRQ_OWN`` before the include, the port
  also takes the response IRQ away from the GPIO driver. An app can
  instead set ``LATBENCH_RESP_IRQ_OWN_IF`` to a list of ``CONFIG_``
  symbols: if one of them is ``y`` on the command line, the app owns the
  IRQ.
- Under sysbuild an image gets ``BOARD`` and the ``-D`` values only
  through the sysbuild cache. ``latbench_cache_get()`` reads them from
  there.

``common/latbench.cmake`` comes after ``find_package(Zephyr)``. It does these
steps:

- It adds ``common/include`` to the include path, and ``pad.c``,
  ``hist.c`` and ``meta.c`` to the ``app`` target. With
  ``LATBENCH_CODE_RAM``, ``pad.c`` goes to a library of its own, and the
  build relocates the hot code (see :ref:`benchguide-code-placement`).
- It defines ``LATBENCH_SRC_REV``, the revision of the benchmark sources.
  ``run.py`` gives the value with ``-DLATBENCH_SRC_REV=<rev>``, because it
  builds from a snapshot without ``.git``. A manual build gets the value
  from ``git describe --always --abbrev=12 --dirty``. If git gives no
  value, the value is ``unknown``.
- If the app sets ``LATBENCH_STIM`` before the include, it adds the
  ``include`` folder and ``port.c`` of the port, ``stim.c`` and ``load.c``.
  The load timers need the tick period from the stimulus, so ``load.c``
  comes only with the stimulus. If ``latbench_board.cmake`` was not
  included, the build stops.
