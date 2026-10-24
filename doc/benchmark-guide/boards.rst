Board support
=============

The board-specific code of the stimulus is in a board port. The apps,
``stim.c``, the histograms, the load generators and the host tools are the
same on each board.

Boards
------

.. list-table::
   :header-rows: 1
   :widths: 40 25 35

   * - Board target
     - Port
     - State
   * - ``nucleo_g474re``
     - ``nucleo_g474re``
     - Tested: data points exist.
   * - ``nrf52840dk/nrf52840``
     - ``nrf52840dk``
     - Planned, port in progress.
   * - ``nrf54l15dk/nrf54l15/cpuapp``
     - ``nrf54l15dk``
     - Planned, port in progress.
   * - ``mimxrt1060_evk@C/mimxrt1062/qspi``
     - ``mimxrt1060_evk``
     - Planned, port in progress.

``boards.yaml`` declares all four board targets. It marks the three
planned boards as ``untested``. This page gets their details when their
ports are merged.

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
   * - ``stim.overlay``
     - The ``zephyr,user`` node with ``resp-gpios`` (the response pin) and
       the pin function of the stimulus pin. It also disables drivers that
       use the stimulus timer.
   * - ``resp_irq_own.overlay``
     - Takes the response IRQ away from the GPIO driver. ``port.cmake`` adds
       it only if ``LATBENCH_RESP_IRQ_OWN`` is set.
   * - ``include/latbench/port_impl.h``
     - The fast functions of the contract as ``static inline`` functions,
       and the macros ``PORT_RESP_IRQN`` and ``PORT_RESP_IRQ_OWNED``.
   * - ``port.c``
     - The other functions of the contract.
   * - ``clocks/``
     - Optional. Clock overlays of the board.

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
     - Returns the clock of the stimulus timer in Hz.
   * - ``port_core_hz()``
     - Returns the clock of the CPU core in Hz.
   * - ``port_stim_set(at)``
     - Drives the stimulus pin low. Then it makes the hardware drive the pin
       high when the counter reaches ``at``. It clears the compare flag.
   * - ``port_stim_stop()``
     - Drives the stimulus pin low and keeps it low.
   * - ``port_stim_force(high)``
     - Drives the stimulus pin to a fixed level, for the static check.
   * - ``port_resp_irq_init()``
     - Configures the response pin as an interrupt on the rising edge, for
       an app with its own ISR. The app enables ``PORT_RESP_IRQN`` itself.
   * - ``port_debug_reset(buf, len)``
     - Undoes debugger settings that change the behavior of the core in
       sleep. Writes the old value as text to ``buf``.

The apps do not call the port directly, except ``port_debug_reset()``.
They use the stimulus interface of ``stim.h`` (see :doc:`common`).

Example: the port ``nucleo_g474re``
-----------------------------------

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Part
     - Implementation
   * - Stimulus timer
     - TIM2 (32 bits) at the core clock, prescaler 0. A ``BUILD_ASSERT`` makes
       sure that the AHB and APB1 prescalers are 1. Another
       ``BUILD_ASSERT`` makes sure that SysTick is the system timer.
   * - Stimulus pin
     - D2 (PA10), TIM2 channel 4, pin function ``tim2_ch4_pa10`` through
       pinctrl. ``port_stim_set()`` uses the output compare modes "forced
       inactive" and "active on match".
   * - Response pin
     - A3 (PB0) on EXTI line 0. ``PORT_RESP_IRQN`` is ``EXTI0_IRQn``.
       ``port_resp_irq_init()`` routes PB0 to EXTI line 0 through SYSCFG,
       with the rising edge only.
   * - ``stim.overlay``
     - The ``zephyr,user`` node, and ``pwm2`` disabled (the board uses TIM2
       for the LED).
   * - ``resp_irq_own.overlay``
     - The EXTI node without line 0. ``PORT_RESP_IRQ_OWNED`` is true if the
       EXTI node has no interrupt named ``line0``.
   * - ``port.conf``
     - ``CONFIG_CORTEX_M_SYSTICK_64BIT_CYCLE_COUNTER=y``
   * - ``port_debug_reset()``
     - Saves and clears ``DBGMCU->CR``.
   * - Clocks
     - ``port_stim_hz()`` and ``port_core_hz()`` both return
       ``sys_clock_hw_cycles_per_sec()``. ``clocks/`` has the 85 MHz and
       16 MHz overlays (see :doc:`hardware`).
   * - ``boards.yaml``
     - Modules ``cmsis_6`` and ``hal_stm32``, flash with OpenOCD, console
       ``/dev/ttyACM0``.

Add a board
-----------

#. Make sure that the board has a free-running 32-bit timer with an output
   compare channel that can drive a pin. Find a response pin with an
   interrupt on the rising edge, and connect a wire between the two pins.
#. Find the board target and the board name without qualifiers and
   revision.
#. Make the folder ``common/boards/<board>/``. Use the port
   ``nucleo_g474re`` as the model.
#. Write ``stim.overlay`` with the ``zephyr,user`` node (``resp-gpios`` and
   the pin function of the stimulus pin). Disable drivers that use the
   stimulus timer.
#. Write ``resp_irq_own.overlay``. It must take the response IRQ away from
   the GPIO driver.
#. Write ``port.cmake``. Copy it from ``nucleo_g474re`` and add a
   ``port.conf`` if the port needs Kconfig options.
#. Write ``include/latbench/port_impl.h`` with the fast functions and the
   macros of the contract.
#. Write ``port.c`` with the other functions of the contract.
#. If the stimulus timer does not run at the core clock, make sure that
   ``port_stim_hz()`` and ``port_core_hz()`` return the correct clocks. The
   stimulus converts the counts to system timer cycles for the tick phase.
#. Add the board target to ``boards.yaml``: ``port``, ``modules``,
   ``flash``, ``console`` and ``status: untested``.
#. If a tree does not pin a module of the board, add the module to the
   tree in ``trees.yaml``. Do not change the pinned revisions.
#. Add the board target to ``platform_allow`` in the ``testcase.yaml`` of
   each app.
#. Build all apps for the board:
   ``run.py <experiment> --out <dir> --build-only`` with
   ``board: <board target>`` in the experiment.
#. Connect the board and the wire, and run ``irq_latency``. Make sure that
   ``static_check=ok`` and ``spurious_edges=0``.
#. When data points exist, set ``status: tested`` in ``boards.yaml``.

What the method needs from a board
----------------------------------

A new board must have these properties, or an equivalent:

- A 32-bit hardware timer with an output compare channel that drives a
  pin with no software in the path.
- A pin with an interrupt on the rising edge, and a wire from the timer
  pin to this pin.
- A system timer with a 64-bit cycle counter
  (``CONFIG_TIMER_HAS_64BIT_CYCLE_COUNTER``), for the tick phase.
- A serial console that the host can read without loss at the output rate
  of the apps.
