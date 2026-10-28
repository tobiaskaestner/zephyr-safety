Board support
=============

The board-specific code of the stimulus is in a :term:`board port`. The :term:`apps <App>`,
``stim.c``, the histograms, the load generators and the host tools are the
same on each board.

Boards
------

.. list-table::
   :header-rows: 1
   :widths: 38 22 40

   * - Board target
     - Port
     - Status in ``boards.yaml``
   * - ``nucleo_g474re``
     - ``nucleo_g474re``
     - ``tested``: data points exist.
   * - ``nrf52840dk/nrf52840``
     - ``nrf52840dk``
     - ``untested``: builds, not run on hardware.
   * - ``nrf54l15dk/nrf54l15/cpuapp``
     - ``nrf54l15dk``
     - ``untested``: builds, not run on hardware.
   * - ``mimxrt1060_evk@C/mimxrt1062/qspi``
     - ``mimxrt1060_evk``
     - ``untested``: builds, not run on hardware.

For each ``untested`` board, the page of the board lists what to
examine first on the hardware. A smoke :term:`experiment` with ``board:
<board target>`` is the first run for such a board (see
:doc:`../howto/add-a-board`). The study ``kernel-latency`` has no
experiment for these boards.

Structure of a port
-------------------

A port is a folder ``common/boards/<board>/``. ``<board>`` is the board
target without qualifiers and revision (see
:ref:`benchguide-latbench-cmake`). The folder has these files:

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - File
     - Content
   * - ``port.cmake``
     - Adds the devicetree overlays and the Kconfig fragments of the port to
       ``EXTRA_DTC_OVERLAY_FILE`` and ``EXTRA_CONF_FILE``.
       ``latbench_board.cmake`` includes it before ``find_package(Zephyr)``.
   * - ``port.conf``
     - Optional. A Kconfig fragment of the port.
   * - ``Kconfig.port``
     - Optional. Defaults of the port for the options of ``common/Kconfig``.
       ``common/Kconfig`` sources it first, so its defaults have priority.
       Today it gives only ``LATBENCH_CODE_RAM_REGION``. A port without it
       does not support ``LATBENCH_CODE_RAM``.
   * - ``stim.overlay``
     - The ``zephyr,user`` node with ``resp-gpios`` (the response pin), and
       the stimulus pin (a pin function, or ``stim-gpios``). It also
       disables drivers that use the stimulus timer.
   * - ``resp_irq_own.overlay``
     - Takes the response IRQ away from the GPIO driver. ``port.cmake`` adds
       it only if ``LATBENCH_RESP_IRQ_OWN`` is set.
   * - ``include/latbench/port_impl.h``
     - The fast functions of the contract as ``static inline`` functions,
       and the macros of the contract.
   * - ``port.c``
     - The other functions of the contract.
   * - Other files
     - Optional. For example clock overlays (``clocks/``), SysTick overlays
       (``systick/``) or Kconfig fragments for experiments
       (``ticks_1024.conf``).

The two Nordic ports share their code in ``common/boards/nordic/``
(``nrf_port_impl.h`` and ``nrf_port.c``). The ``port_impl.h`` of the board
defines the TIMER, the GPIOTE and the clock node, and then includes the
shared header. The ``port.c`` of the board defines ``port_name`` and then
includes ``nrf_port.c``.

The contract
------------

``common/include/latbench/port.h`` is the contract of a port. The stimulus
timer must be a free-running 32-bit up-counter with an output compare
channel. At the compare value, the hardware drives the stimulus pin high,
with no software in the path.

Fast functions and macros, in ``port_impl.h``:

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Name
     - Purpose
   * - ``port_stim_now()``
     - Returns the counter of the stimulus timer.
   * - ``port_stim_fired()``
     - Returns true if the compare flag is set (the edge came from the
       timer).
   * - ``port_resp_ack()``
     - Clears the pending flag of the response interrupt (own ISR only).
   * - ``PORT_RESP_IRQN``
     - The IRQ line of the response pin (own ISR only).
   * - ``PORT_RESP_IRQ_OWNED``
     - 1 if the devicetree gives the response interrupt to the app, 0 if
       the GPIO driver has it.
   * - ``PORT_RESP_PIN``
     - Optional. The pin number that the own ISR serves. If the port
       defines it, ``irq_latency`` compares the pin of ``resp-gpios`` with
       it and stops with ``LAT ERROR irq setup`` if they are different.

Other functions, in ``port.c``:

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Name
     - Purpose
   * - ``port_name``
     - The name of the port, for the output (``LAT META port``).
   * - ``port_stim_init()``
     - Starts the stimulus timer (free-running, 32 bits) and sets up the
       stimulus pin with the output low.
   * - ``port_stim_hz()``
     - Returns the clock of the stimulus timer in Hz. ``stim_init()`` calls
       it before ``port_stim_init()``.
   * - ``port_core_hz()``
     - Returns the clock of the CPU core in Hz.
   * - ``port_stim_set(at)``
     - Drives the stimulus pin low. Then it makes the hardware drive the pin
       high when the counter reaches ``at``. It clears the compare flag.
       ``stim_arm()`` calls it with interrupts locked.
   * - ``port_stim_stop()``
     - Drives the stimulus pin low and keeps it low.
   * - ``port_stim_force(high)``
     - Drives the stimulus pin to a fixed level, for the static check.
   * - ``port_resp_irq_init()``
     - Configures the response pin as an interrupt on the rising edge, for
       an app with its own ISR. The app enables ``PORT_RESP_IRQN`` itself.
   * - ``port_debug_reset(buf, len)``
     - Undoes debugger settings that change the behavior of the core in
       sleep, if the SoC permits it. Writes the old value as text to
       ``buf``.

The apps do not call the port directly, except ``port_debug_reset()``.
They use the stimulus interface of ``stim.h`` (see :doc:`common-modules`).

Board pages
-----------

Each port has its documentation beside its code, in
``tests/benchmarks/common/boards/<board>/doc/``, as the boards of Zephyr
do: the pins, the stimulus timer, the files of the port and what to
examine first on the hardware. The guide collects these pages.

.. toctree::
   :maxdepth: 1
   :glob:

   /benchmarks/common/boards/*/doc/index
