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
