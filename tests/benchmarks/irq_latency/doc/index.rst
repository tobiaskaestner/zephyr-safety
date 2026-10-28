.. _benchguide-app-irq-latency:

``irq_latency`` (M1)
====================

The :term:`app` ``irq_latency`` is in ``tests/benchmarks/irq_latency/``.
This page is its documentation, beside its code.
:doc:`/explanation/apps` gives the frame that all measurement apps
share.

What it measures
----------------

The app measures the time from the edge to the first time stamp in the
interrupt path. The time stamp then arms the next edge. The Kconfig choice
``LATBENCH_IRQ_PATH`` selects the interrupt path:

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Kconfig option
     - Variant
     - Interrupt path
   * - ``LATBENCH_IRQ_PATH_STOCK`` (default)
     - ``stock``
     - The GPIO driver of Zephyr owns the response IRQ. The time stamp is
       in the user callback of the GPIO driver, after ``_isr_wrapper`` and
       the driver dispatch.
   * - ``LATBENCH_IRQ_PATH_WRAPPED``
     - ``wrapped``
     - An ISR of the app, connected with ``IRQ_CONNECT()``. It runs through
       ``_isr_wrapper``.
   * - ``LATBENCH_IRQ_PATH_DIRECT``
     - ``direct``
     - A direct ISR of the app (``IRQ_DIRECT_CONNECT()``).
   * - ``LATBENCH_IRQ_PATH_ZLI``
     - ``zli``
     - A direct zero-latency ISR. It selects ``CONFIG_ZERO_LATENCY_IRQS``.
       BASEPRI does not mask this IRQ, so kernel critical sections do not
       delay it.

.. timeline-viz:: irq-latency.tdl
   :name: benchguide-fig-irq-latency

   ``irq_latency`` with the ``stock`` path. The ``wrapped`` path starts its
   ISR after the exception entry, with ``_isr_wrapper``. The ``direct``
   and ``zli`` paths start their ISR after the exception entry, without
   ``_isr_wrapper``. Thus the ISR reads the counter earlier.

Known limit of the ``zli`` path: ``stim_arm()`` takes the tick phase of the
next edge from ``k_cycle_get_64()``. BASEPRI does not mask a zero-latency
IRQ, so the read can interrupt the timer driver in its locked section and
see an inconsistent count. Only the phase histogram is at risk, not the
latency.

Options, variants and output
----------------------------

The paths ``wrapped``, ``direct`` and ``zli`` connect an ISR of the app.
For these paths, the port must take the response IRQ away from the GPIO
driver. The steps are:

#. ``irq_latency/CMakeLists.txt`` sets ``LATBENCH_RESP_IRQ_OWN_IF`` to the
   three path symbols. ``common/latbench_board.cmake`` reads them from the
   CMake command line (``-DCONFIG_LATBENCH_IRQ_PATH_WRAPPED=y``, ``_DIRECT``
   or ``_ZLI``), or from the sysbuild cache if the build uses sysbuild
   (Twister does this for ``nrf54l15dk``). If one of them is ``y``, it sets
   ``LATBENCH_RESP_IRQ_OWN``.
#. The port then adds its ``resp_irq_own.overlay``. On the NUCLEO-G474RE,
   this overlay removes EXTI line 0 from the GPIO interrupt driver.
#. A ``BUILD_ASSERT`` in ``main.c`` compares the path with
   ``PORT_RESP_IRQ_OWNED``. If they do not agree, the build stops.
#. If the port defines ``PORT_RESP_PIN``, ``irq_setup()`` compares it with
   the pin of ``resp-gpios``. If they are different, the app prints
   ``LAT ERROR irq setup`` and stops.

Thus the path must be on the CMake command line. A path in a Kconfig
fragment or in ``prj.conf`` does not select the overlay, and the build
stops. ``run.py`` puts each ``kconfig`` value of a point on the command
line, and the Twister scenarios use ``extra_args``.

The Kconfig choice ``LATBENCH_BACKGROUND`` selects what the CPU does between
the edges:

- ``LATBENCH_BG_IDLE`` (default): the idle thread runs, and the CPU sleeps
  in WFI.
- ``LATBENCH_BG_BUSY``: a busy thread runs at the lowest application
  priority.

Output: one histogram ``irq`` and one phase histogram ``irq``.
