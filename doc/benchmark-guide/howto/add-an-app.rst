Add an app
==========

#. Make a folder ``tests/benchmarks/<app>/``.
#. Write ``CMakeLists.txt``. Include ``latbench_board.cmake`` before
   ``find_package(Zephyr)``. If the app connects its own ISR to the response
   pin, set ``LATBENCH_RESP_IRQ_OWN`` before this include. If the app uses
   the stimulus, set ``LATBENCH_STIM`` before the include of
   ``latbench.cmake``:

   .. code-block:: cmake

      cmake_minimum_required(VERSION 3.20.0)

      set(LATBENCH_RESP_IRQ_OWN ON)
      include(${CMAKE_CURRENT_SOURCE_DIR}/../common/latbench_board.cmake)

      find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
      project(<app>)

      set(LATBENCH_STIM ON)
      include(${CMAKE_CURRENT_SOURCE_DIR}/../common/latbench.cmake)
      target_sources(app PRIVATE src/main.c)

#. Write ``Kconfig``. Define the options of the app, and
   ``LATBENCH_STIM_MIN_US``, ``LATBENCH_STIM_MAX_US`` and ``LATBENCH_POLL_MS``
   (see :doc:`../reference/kconfig`). Then source the common options and Zephyr:

   .. code-block:: kconfig

      rsource "../common/Kconfig"

      source "Kconfig.zephyr"

#. Write ``prj.conf`` with ``CONFIG_GPIO=y``, ``CONFIG_PRINTK=y``,
   ``CONFIG_ASSERT=n`` and ``CONFIG_SPIN_VALIDATE=n``. If the main thread
   only waits, also set ``CONFIG_MAIN_THREAD_PRIORITY`` to a low priority.
#. Do not write a board overlay. The board port gives the ``zephyr,user``
   node and the other devicetree changes.
#. Write ``src/main.c`` with the frame of the existing apps (see
   :doc:`../explanation/apps`):

   - Call ``port_debug_reset()``. Print the old value as
     ``debug_reg_at_boot``.
   - Call ``lat_meta_print()`` with the app name and a variant name that
     names all variant options.
   - Call ``stim_init()``, ``lat_phase_init()`` for each phase histogram,
     and ``stim_static_check()``. If one of them fails, print ``LAT ERROR``
     and call ``lat_done()``.
   - Call ``stim_resp_irq_init()``, connect the ISR to ``STIM_RESP_IRQN``,
     and enable the IRQ.
   - Call ``load_start()``. Then arm the first edge.
   - In the ISR, read ``stim_now()`` first, then call ``stim_resp_ack()``,
     then examine ``stim_fired()``.
   - Do not use board-specific code in the app. Put it into the board
     port.
   - Discard ``LATBENCH_WARMUP`` samples. Then record ``LATBENCH_SAMPLES``
     samples. Arm the next edge only after the time stamps of the current
     edge.
   - At the end, print ``spurious_edges``, then call
     ``stim_print_stats()``, ``load_print()``, ``lat_hist_print()`` and
     ``lat_phase_print()``, and then ``lat_done()``.

#. Give each histogram of the app its own name.
#. Write ``testcase.yaml`` with ``build_only: true``,
   ``platform_allow`` with the four board targets of ``boards.yaml``, and one scenario for each important
   variant. Use the tags ``benchmark`` and ``latency``.
#. Write ``scripts/extract.py`` and ``scripts/plot.py`` in the app folder,
   from those of an existing app. The extractor calls
   ``latextract.main("<app>")``. The plot script calls
   ``latplot.main("<app>", ["<main metric>"])`` (both in
   ``common/scripts/``). The results build needs both: the extractor for the
   app data, the plot script for the standard plots (see :doc:`../reference/files/results-tree`).
   A value or a plot that only this app gives goes into these files.
#. Write the page of the app, ``doc/index.rst`` in the app folder, from the
   page of an existing app: the label ``benchguide-app-<app>``, what the app
   measures (with a timing diagram ``doc/<app>.tdl`` if it helps), and its
   options, variants and output. The guide collects the page by itself
   (:doc:`../reference/apps`).
#. Add the app to the table in ``tests/benchmarks/README.md`` and to the
   table of :doc:`../explanation/apps`.
#. Add an experiment for the app (see :doc:`add-an-experiment`).

If the app prints a new ``LAT`` line type, add it to ``parse_log()`` in
``scripts/benchmarks/latbench.py``. Also add it to
:doc:`../reference/log-format` in this guide.
