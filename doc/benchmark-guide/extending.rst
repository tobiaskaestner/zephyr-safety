Extend the suite
================

Add an experiment
-----------------

#. Find the study in ``validation/empirical/latencies/`` that asks your
   question. A study is a folder ``st-<name>/``, an experiment is a folder
   ``ex-<name>/``. Copy an experiment folder of that study that is near
   to your question, and give the copy the folder name ``ex-<name>``. The
   name must be unique in all studies. Alternatively, make the files from
   templates with ``study.py design scaffold experiment <study
   folder>/ex-<name> --app <app>`` (see :ref:`benchguide-scaffold`). It
   also does the next step.
#. In ``experiment.yaml``, set ``name`` to the name without ``ex-``. Add
   the name to ``experiments`` in the ``study.yaml`` of the study.
#. Write the description ``experiment.md``: the question, the method
   (each point and why), and the references. Write the predictions in the
   ``hypotheses.yaml`` of the study.
#. Set ``app``, ``trees``, ``repeat`` and ``timeout``. If the experiment is
   not for the default board, set ``board`` to a board target of
   ``boards.yaml``. A point with 1 million
   samples needs a timeout of approximately 900 s to 1200 s.
#. Put the settings that all points share into ``common``.
#. Put the factors into ``axes``. Put single extra points into ``points``.
#. Do not list the overlays of the board port. The port adds them. If a
   point needs another overlay (for example a clock overlay), add it to
   ``dtc_overlays``.
#. Use text for the value names of an axis, not ``on``, ``off``, ``yes`` or
   ``no``.
#. Run the design lint, and correct each error:

   .. code-block:: console

      scripts/benchmarks/study.py design lint validation/empirical/latencies/st-<study>

#. Commit the file. ``run.py`` refuses a safety repository that is not
   clean.
#. Make sure that the points are correct:

   .. code-block:: console

      scripts/benchmarks/run.py validation/empirical/latencies/st-<study>/ex-<name>/experiment.yaml --out <dir> --dry-run

#. Make sure that all points build. This step also does the Kconfig
   check of each point:

   .. code-block:: console

      scripts/benchmarks/run.py validation/empirical/latencies/st-<study>/ex-<name>/experiment.yaml --out <dir> --build-only

#. Connect the board and run the experiment without ``--build-only``. In
   a lab space, run it with a campaign: ``study.py campaign run
   <experiment folder>`` (see :doc:`lab`). The campaign adds the run to
   the run list of its instance. Without a campaign, use ``--out
   <instance folder>``: ``run.py`` then adds the run to the run list of
   the instance itself (see :doc:`studies`).

Each value in ``kconfig`` of a point must be an option of the app or of
the tree. If the tree does not define the option, the build stops. Thus
an experiment can use an option that only one tree has (for example a
timeout backend) only with that tree. If Kconfig ignores a value (unmet
dependencies, or a second member of a choice), the Kconfig check stops
the run (see :doc:`pitfalls`).

Add a tree or a module
----------------------

A pinned revision never changes (see :ref:`benchguide-tree-rule`).

To use another revision of a repository, add a new tree:

#. Make sure that a local clone has the revision of each repository, or
   that the ``url`` has it.
#. Copy a file of ``validation/trees/`` to ``validation/trees/<tree>.yml``,
   and set the description and the revisions. Do not change the
   revisions of an existing tree.
#. Run ``study.py design lint``: it checks the file with the parser of
   west.
#. Commit the new file.
#. Create the tree in your lab space (see :doc:`lab`):

   .. code-block:: console

      scripts/benchmarks/study.py trees setup <tree>

To add a module repository that a new board needs to an existing tree:

#. Add the project to ``projects`` of ``validation/trees/<tree>.yml``,
   with its pinned revision. Do not change the other projects: ``trees
   setup`` and ``trees check`` accept a new project, but no changed or
   removed pin.
#. Commit the file.
#. Run ``study.py trees setup <tree>``. It creates only the missing
   repositories.

Add an app
----------

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
   (see :doc:`reference/kconfig`). Then source the common options and Zephyr:

   .. code-block:: kconfig

      rsource "../common/Kconfig"

      source "Kconfig.zephyr"

#. Write ``prj.conf`` with ``CONFIG_GPIO=y``, ``CONFIG_PRINTK=y``,
   ``CONFIG_ASSERT=n`` and ``CONFIG_SPIN_VALIDATE=n``. If the main thread
   only waits, also set ``CONFIG_MAIN_THREAD_PRIORITY`` to a low priority.
#. Do not write a board overlay. The board port gives the ``zephyr,user``
   node and the other devicetree changes.
#. Write ``src/main.c`` with the frame of the existing apps (see
   :doc:`explanation/apps`):

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
   ``latextract.main("<app>")``; the plot script calls
   ``latplot.main("<app>", ["<main metric>"])`` (both in
   ``common/scripts/``). The results build needs both: the extractor for the
   app data, the plot script for the standard plots (see :doc:`studies`).
   A value or a plot that only this app gives goes into these files.
#. Add the app to the table in ``tests/benchmarks/README.md`` and to
   :doc:`explanation/apps` and :doc:`reference/apps` in this guide.
#. Add an experiment for the app (see above).

If the app prints a new ``LAT`` line type, add it to ``parse_log()`` in
``scripts/benchmarks/latbench.py`` and to :doc:`reference/log-format` in this guide.
