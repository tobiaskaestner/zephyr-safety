Add a board
===========

:doc:`../reference/boards` gives the structure of a board port and its
contract.

#. Make sure that the board has a free-running 32-bit timer with an output
   compare channel that can drive a pin. Find a response pin with an
   interrupt on the rising edge, and connect a wire between the two pins.
#. Find the board target and the board name without qualifiers and
   revision.
#. Make the folder ``common/boards/<board>/``. Use the port of a similar
   board as the model.
#. Write ``stim.overlay`` with the ``zephyr,user`` node (``resp-gpios`` and
   the stimulus pin). Disable drivers that use the stimulus timer.
#. Write ``resp_irq_own.overlay``. It must take the response IRQ away from
   the GPIO driver.
#. Write ``port.cmake``. Copy it from an existing port, and add a
   ``port.conf`` if the port needs Kconfig options.
#. Write ``include/latbench/port_impl.h`` with the fast functions and the
   macros of the contract. If the own ISR serves only one pin, define
   ``PORT_RESP_PIN``.
#. Write ``port.c`` with the other functions of the contract.
#. If the stimulus timer does not run at the core clock, examine
   ``port_stim_hz()`` and ``port_core_hz()``. Each must return its correct
   clock.
#. If the system timer has no 64-bit counter, make sure that the tick
   period is a power of two cycles.
#. Optional: to support ``LATBENCH_CODE_RAM``, write ``Kconfig.port`` with
   the default of ``LATBENCH_CODE_RAM_REGION``. Use a region with no wait
   states that the MPU lets the core execute (for example an ITCM). If
   the region needs a devicetree node, add it with an overlay in
   ``port.cmake``, as ``nucleo_g474re`` does. Run the unit tests of the
   code placement and a smoke run with ``LATBENCH_CODE_RAM``.
#. Add the board target to ``boards.yaml`` (see
   :doc:`../reference/files/boards-yaml`): ``port``, ``modules``,
   ``flash`` (with ``{probe}``, so that the command selects the probe)
   and ``status: untested``. Write the wire and the untested parts in a
   comment. Add the board to the hardware map of your host (see
   :ref:`benchguide-hw-map`).
#. If a tree does not pin a module of the board, add the module to the
   tree in ``validation/trees/<tree>.yml`` (see :doc:`add-a-tree`).
#. Add an overlay for ``loopback_check`` in ``loopback_check/boards/``.
#. Add a ``wake-port-smoke-<port>`` experiment with ``board: <board target>``
   (see :doc:`add-an-experiment`). Build all points with ``run.py
   <experiment> --build-only``.
#. Connect the board and the wire, and run the smoke experiment. Make sure
   that ``static_check=ok``, ``spurious_edges=0`` and ``stim_late=0``.
#. When data points exist, set ``status: tested`` in ``boards.yaml``.
