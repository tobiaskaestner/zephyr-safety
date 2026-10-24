Extend the suite
================

Add an experiment
-----------------

#. Copy an experiment file in ``experiments/`` that is near to your
   question. Give the copy a new file name.
#. Set ``name`` to the file name without ``.yaml``.
#. At the top of the file, write a comment with the question, the
   expectation (if you have one), and the meaning of each point.
#. Set ``app``, ``trees``, ``repeat`` and ``timeout``. A point with 1 million
   samples needs a timeout of approximately 900 s to 1200 s.
#. Put the settings that all points share into ``common``.
#. Put the factors into ``axes``. Put single extra points into ``points``.
#. If a point needs an overlay of the app (for example
   ``irq_latency/exti_line0_app.overlay``), add it to ``dtc_overlays``.
#. Commit the file. ``run.py`` refuses a safety repository that is not
   clean.
#. Make sure that the points are correct:

   .. code-block:: console

      tests/benchmarks/scripts/run.py tests/benchmarks/experiments/<name>.yaml --out <dir> --dry-run

#. Make sure that all points build. This step also does the Kconfig
   check of each point:

   .. code-block:: console

      tests/benchmarks/scripts/run.py tests/benchmarks/experiments/<name>.yaml --out <dir> --build-only

#. Connect the board and run the experiment without ``--build-only``.

Each value in ``kconfig`` of a point must be an option of the app or of
the tree. If the tree does not define the option, the build stops. Thus
an experiment can use an option that only one tree has (for example a
timeout backend) only with that tree. If Kconfig ignores a value (unmet
dependencies, or a second member of a choice), the Kconfig check stops
the run (see :doc:`pitfalls`).

Add a tree
----------

#. Make sure that a local clone has the revision of each repository, or
   that the ``url`` has it.
#. Add a new entry under ``trees`` in ``trees.yaml``. Do not change an
   existing entry.
#. Commit ``trees.yaml``.
#. Create the tree:

   .. code-block:: console

      tests/benchmarks/scripts/trees.py setup <tree>

Add an app
----------

#. Make a folder ``tests/benchmarks/<app>/``.
#. Write ``CMakeLists.txt``. If the app uses the TIM2 stimulus, set
   ``LATBENCH_STIM`` before the include:

   .. code-block:: cmake

      cmake_minimum_required(VERSION 3.20.0)
      find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
      project(<app>)

      set(LATBENCH_STIM ON)
      include(${CMAKE_CURRENT_SOURCE_DIR}/../common/latbench.cmake)
      target_sources(app PRIVATE src/main.c)

#. Write ``Kconfig``. Define the options of the app, and
   ``LATBENCH_STIM_MIN_US``, ``LATBENCH_STIM_MAX_US`` and ``LATBENCH_POLL_MS``
   (see :doc:`kconfig`). Then source the common options and Zephyr:

   .. code-block:: kconfig

      rsource "../common/Kconfig"

      source "Kconfig.zephyr"

#. Write ``prj.conf`` with ``CONFIG_GPIO=y``, ``CONFIG_PRINTK=y``,
   ``CONFIG_ASSERT=n`` and ``CONFIG_SPIN_VALIDATE=n``. If the main thread
   only waits, also set ``CONFIG_MAIN_THREAD_PRIORITY`` to a low priority.
#. Write ``boards/nucleo_g474re.overlay``. Copy it from ``wake_latency``: it
   gives the ``zephyr,user`` node, disables ``pwm2``, and removes EXTI
   line 0 from the GPIO interrupt driver.
#. Write ``src/main.c`` with the frame of the existing apps (see
   :doc:`apps`):

   - Save and clear ``DBGMCU->CR``. Print the old value as
     ``dbgmcu_cr_at_boot``.
   - Call ``lat_meta_print()`` with the app name and a variant name that
     names all variant options.
   - Call ``stim_init()``, ``lat_phase_init()`` for each phase histogram,
     and ``stim_static_check()``. If one of them fails, print ``LAT ERROR``
     and call ``lat_done()``.
   - Call ``stim_exti0_init()``, connect the ISR to ``EXTI0_IRQn``, and
     enable the IRQ.
   - Call ``load_start()``. Then arm the first edge.
   - In the ISR, read ``stim_now()`` first, then clear the EXTI flag, then
     examine ``stim_fired()``.
   - Discard ``LATBENCH_WARMUP`` samples. Then record ``LATBENCH_SAMPLES``
     samples. Arm the next edge only after the time stamps of the current
     edge.
   - At the end, print ``spurious_edges``, then call
     ``stim_print_stats()``, ``load_print()``, ``lat_hist_print()`` and
     ``lat_phase_print()``, and then ``lat_done()``.

#. Give each histogram of the app its own name.
#. Write ``testcase.yaml`` with ``build_only: true``,
   ``platform_allow: [nucleo_g474re]``, and one scenario for each important
   variant. Use the tags ``benchmark`` and ``latency``.
#. Add the app to the table in ``tests/benchmarks/README.md`` and to
   :doc:`apps` in this guide.
#. Add an experiment for the app (see above).

If the app prints a new ``LAT`` line type, add it to ``parse_log()`` in
``scripts/latbench.py`` and to :doc:`output` in this guide.
