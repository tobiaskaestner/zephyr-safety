What the apps measure
=====================

The suite has four :term:`apps <App>`. Three apps measure latencies with the hardware
stimulus. The fourth app does a test of the wire.

.. list-table::
   :header-rows: 1
   :widths: 20 10 70

   * - App
     - Point
     - Content
   * - ``irq_latency``
     - M1
     - Edge to the first time stamp in the interrupt path
   * - ``wake_latency``
     - M2
     - Edge to ISR to woken thread, for each kernel object that an ISR can
       use to wake a thread
   * - ``thread_latency``
     - M3
     - ISR to giver thread to taker thread, for each kernel primitive
   * - ``loopback_check``
     - none
     - Static check and interrupt check of the wire

The three measurement apps have the same frame:

#. ``main()`` calls ``port_debug_reset()`` and prints the metadata (see
   :ref:`benchguide-meta`).
#. ``stim_init()`` sets up the stimulus timer and the pins through the
   :term:`board port`, and prints the stimulus settings.
#. ``stim_static_check()`` does the static check of the wire.
#. The app connects its ISR to the response IRQ ``STIM_RESP_IRQN`` (or a
   GPIO callback) and starts the load generators (``load_start()``).
#. The app arms the first edge. It discards the first
   ``LATBENCH_WARMUP`` :term:`samples <Sample>`, and then records ``LATBENCH_SAMPLES``
   samples.
#. The main thread polls a ``done`` flag every ``LATBENCH_POLL_MS``
   milliseconds.
#. At the end, the app prints the counters, the histograms and the phase
   histograms, and then ``LAT DONE``.

Each ``testcase.yaml`` of a measurement app is a build check only
(``build_only: true``). A data point comes only from
``scripts/benchmarks/run.py`` (see :doc:`../reference/cli/run-py`).

Each app has its own page beside its code, in
``tests/benchmarks/<app>/doc/``: what it measures, with a timing diagram,
and its options, variants and output. :doc:`../reference/apps` collects
these pages.
