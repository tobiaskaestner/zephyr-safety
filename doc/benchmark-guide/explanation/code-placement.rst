.. _benchguide-code-placement:

Code placement
==============

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
------------

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
---------------

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
(see :doc:`../reference/boards`). If the port gives no region, the build stops with a
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

.. _benchguide-code-place:

The place of the code changes the latency
-----------------------------------------

On the NUCLEO-G474RE the code runs from flash through the ART
accelerator (a small instruction cache and a prefetch buffer). If the
code of the hot paths starts at a different address, the number of
cache misses can change, and so can the latency. A change in an
unrelated part of the build can move all the code after it. For
example, a different number of load threads changes the size of
``load.c``.

In wake-threads-1m, builds that differ only in the number of load
threads gave an IRQ p50 of 82 or 86 cycles, and a clock drift of 8.0 or
9.7 cycles per wake. The difference between the two trees in the ISR to
thread p50 was from 0 to 190 cycles, by build.

The experiment ``code-layout`` moved all code with a code pad of 0 to 28
bytes. The IRQ p50, the drift and the ISR to thread p50 with time slicing
change with a period of 8 bytes, the width of a flash read. The ISR to
thread p50 without time slicing changes by up to 35 cycles. A pad moves
all code by the same amount, but two builds also have a different order
of functions. Thus a pad explains only a part of the difference between
two builds.

Thus do not compare single builds in flash when the difference is small.
Use the choice ``LATBENCH_CODE_PLACE`` (see
:ref:`benchguide-code-placement`) as follows:

- To compare two builds (two trees, two Kconfig values), use
  ``LATBENCH_CODE_RAM``. The hot code then runs from RAM with no wait
  states, and its address has no effect on the latency.
- To give an absolute number for an application in flash, use
  ``LATBENCH_CODE_FLASH_PAD`` with a set of pads, and give the range over
  the pads. The pad set is an axis of the experiment, not a Kconfig value.
- ``LATBENCH_CODE_FLASH`` gives the number of one build. Use it only
  together with a range from a pad set, or for a smoke test.

The experiments ``code-place-q4`` and ``code-place-q4-up`` checked this
rule on ``nucleo_g474re`` (50000 samples for each point). With
``LATBENCH_CODE_RAM`` the 8 pads gave the same IRQ p50 (48), the same
ISR to thread p50 (1145 with time slicing, 523 without) and the same
drift (8.04 cycles per wake). The difference between the trees
(ws-up - ws-safety) was -40 and -42 cycles at the pads 0 and 4. In flash
the same difference was -121 and -10 cycles (time slicing).

Any change of the code size before the hot code also moves it. An
example: ``LATBENCH_SAMPLES`` = 50000 fits in one instruction (``movw``),
200000 needs a literal word. Thus two flash builds that differ only in
the number of samples have a different code layout, and their ISR to
thread p50 without time slicing differs by up to 17 cycles.

The pad set must cover each position of the code in the line of the
cache or of the flash read, in steps of 4 bytes:

- ``nucleo_g474re``: 0, 4, 8, ..., 28 (8 pads). This covers both phases
  of the 8-byte period and the 16-byte part. The pads 0 and 4 are the
  smallest set that covers both phases of the 8-byte period.
- A board with a larger line, for example a Cortex-M7 with 32-byte cache
  lines: 0, 4, ..., L - 4 for a line of L bytes (8 pads for 32 bytes).

With ``LATBENCH_CODE_RAM`` the result is not the latency of an
application in flash. On ``nucleo_g474re`` it is faster, because the
code has no flash wait states. Give the
cost of the code placement with the result: the flash range and the RAM
number of the same build.
