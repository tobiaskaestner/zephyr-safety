Host tools and reproducibility
==============================

The folder ``scripts/`` has the host tools. They need Python 3 and the
packages in ``scripts/requirements.txt`` (``pyserial``, ``PyYAML``,
``matplotlib``).

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Script
     - Purpose
   * - ``trees.py``
     - Creates and examines the pinned trees of ``trees.yaml``.
   * - ``run.py``
     - Runs an experiment from pinned, clean trees and records its
       provenance.
   * - ``latbench.py``
     - Captures, parses and summarizes the ``LAT`` output.
   * - ``plot.py``
     - Plots the distributions from the logs.

Reproducibility rules
---------------------

A data point that you publish or compare must come from ``run.py`` with
an experiment file in the safety repository. These rules apply:

- ``trees.yaml`` pins each tree: the Zephyr revision, the revision of each
  module, and the Zephyr SDK version.
- A pinned revision does not change, because old results refer to it. To
  change a tree, add a new tree to ``trees.yaml`` and keep the old tree.
- A Zephyr patch for the study goes on a branch in the Zephyr repository.
  The commit of the patch is the revision of the new tree.
- ``run.py`` stops before it builds anything in these conditions:

  - The safety repository is not clean.
  - A tree is not at its pinned revision, or it is not clean.
  - The SDK version is not the pinned version.

- A manual build or capture is for development only. Its results are
  unpinned.

Pinned trees (``trees.yaml``)
-----------------------------

``trees.yaml`` has these keys:

``root``
   The folder that holds the trees. ``--trees-root`` or the environment
   variable ``LATBENCH_TREES_ROOT`` overrides it.

``board``
   The default board of the experiments (``nucleo_g474re``).

``toolchain.zephyr_sdk``
   The pinned SDK ``version`` and its ``path``. The scripts compare the
   version with the ``sdk_version`` file of the SDK.

``trees.<name>``
   One entry for each tree, with a ``description`` and a ``repos`` map.
   Each repository has a ``path`` in the tree, a ``url``, an optional
   ``branch``, the pinned ``rev``, and an optional ``source``. The
   ``source`` is a local clone that has the revision, so that no network
   access is necessary.

The file declares two trees today. ``ws-safety`` is the Zephyr of the
safety workspace. ``ws-up`` is an upstream Zephyr ``main``. Each tree has
the repositories ``zephyr``, ``cmsis_6`` and ``hal_stm32``.

``trees.py`` has three commands:

.. code-block:: console

   tests/benchmarks/scripts/trees.py setup [TREE ...]
   tests/benchmarks/scripts/trees.py check [TREE ...]
   tests/benchmarks/scripts/trees.py show

``setup``
   Creates each missing repository at ``<root>/<tree>/<path>``. If the
   ``source`` clone exists, it adds a detached git worktree of it at the
   pinned revision. If the revision is not in the clone, it fetches the
   ``branch`` first. If the ``source`` clone does not exist, it clones the
   ``url``. Then it does the same examination as ``check``.

``check``
   Makes sure that the SDK has the pinned version. Then it makes sure
   that each repository exists, is at its pinned revision and is clean
   (no changes, no untracked files).

``show``
   Prints the trees, the revisions and the paths.

Do not change files in a tree. A tree with changes is not clean, and
``run.py`` refuses it.

Run an experiment (``run.py``)
------------------------------

.. code-block:: console

   tests/benchmarks/scripts/run.py tests/benchmarks/experiments/<name>.yaml --out <dir>

Options:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Option
     - Meaning
   * - ``--out <dir>``
     - The folder for the results (necessary).
   * - ``--only ID ...``
     - Run only the points with these IDs.
   * - ``--dry-run``
     - Do the checks and list the points. Do not build.
   * - ``--build-only``
     - Build each point in a temporary folder. Do not flash.
   * - ``--keep-build``
     - Keep the build folder of each point.
   * - ``--port <dev>``
     - The serial port (default ``/dev/ttyACM0``).
   * - ``--trees-root <dir>``
     - Override ``root`` of ``trees.yaml``.

``run.py`` does these steps:

#. **Checks.** It makes sure that the safety repository is clean and that
   the experiment file is in it. It makes sure that the SDK and each tree
   of the experiment are as pinned. It expands the points.
#. **Snapshot.** It exports the committed benchmark sources at the
   current revision with ``git archive`` into ``<run>/src/``. All builds
   use this snapshot, not the worktree. Thus work in the worktree during
   a long run does not change what the run builds.
#. **Build.** For each tree and each point, it runs CMake and Ninja with:

   - ``ZEPHYR_BASE`` set to the Zephyr of the tree, and all other
     ``ZEPHYR_*`` environment variables removed.
   - ``-DZEPHYR_MODULES`` set to the modules of the tree only, so that no
     module of a west workspace goes into the build.
   - ``-DEXTRA_CONF_FILE`` and ``-DEXTRA_DTC_OVERLAY_FILE`` from the point.
   - ``-DCONFIG_<SYM>=<value>`` for each Kconfig value of the point.
   - ``-DLATBENCH_SRC_REV`` set to the safety revision.

#. **Kconfig check.** It compares each Kconfig value of the point with the
   ``.config`` of the build. If the ``.config`` does not have the requested
   value, the run stops. Kconfig can ignore a value without an error
   (see :doc:`pitfalls`).
#. **Flash and capture.** For each repetition, it opens the serial port
   and flashes the ELF with OpenOCD. OpenOCD uses the ``openocd.cfg`` of
   the board in the Zephyr of the tree. Then ``run.py`` saves the output
   until ``LAT DONE``. If no ``LAT DONE`` comes before the timeout,
   or the flash fails, the run stops.
#. **Summary.** It writes ``summary.txt`` with the percentiles of each
   histogram.

``run.py`` writes ``manifest.json`` at the start and updates it after each
repetition. Thus a run that stops still has a manifest for the completed
repetitions.

.. _benchguide-experiment-file:

Experiment file
---------------

An experiment file is a YAML file in ``experiments/``. The keys are:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Key
     - Meaning
   * - ``name``
     - Name of the experiment. It is the name of the folder in the output.
       By convention, it is the file name without ``.yaml``.
   * - ``app``
     - The app folder in ``tests/benchmarks/``.
   * - ``trees``
     - List of tree names from ``trees.yaml``.
   * - ``board``
     - Optional. The default is ``board`` of ``trees.yaml``.
   * - ``repeat``
     - Number of repetitions of each point (default 1).
   * - ``timeout``
     - Maximum time of one repetition in seconds (default 600).
   * - ``common``
     - Settings for all points.
   * - ``axes``
     - Optional. A map of axes. Each axis is a map from a value name to
       settings. ``run.py`` makes one point for each combination of the
       values (Cartesian product).
   * - ``points``
     - Optional. A list of explicit points, each with an ``id``. You can use
       ``axes`` and ``points`` together.

Each set of settings (in ``common``, in an axis value or in a point) can
have these keys:

``kconfig``
   A map from a Kconfig option (without ``CONFIG_``) to its value. ``y``
   and ``n`` stay as text. A YAML Boolean becomes ``y`` or ``n``.

``conf_files``
   A list of Kconfig fragments, relative to ``tests/benchmarks/``.

``dtc_overlays``
   A list of devicetree overlays, relative to ``tests/benchmarks/``.

The settings merge in this order: ``common``, then the axis values in the
order of the axes, or the point. For ``kconfig``, a later value replaces
an earlier value of the same option. ``conf_files`` and ``dtc_overlays``
are concatenated. The ID of a point from the axes is the value names,
joined by ``-``, in the order of the axes. Two points with the same ID
stop the run.

Example: four interrupt paths times two anchors give eight points
(``stock-default``, ``stock-lean``, ``wrapped-default`` and more).

.. code-block:: yaml

   # Question: what does lean.conf change on each interrupt path?

   name: irq-example
   app: irq_latency
   trees: [ws-safety]
   repeat: 1
   timeout: 900

   common:
     kconfig:
       LATBENCH_SAMPLES: 1000000
       LATBENCH_STIM_MIN_US: 100
       LATBENCH_STIM_MAX_US: 500

   axes:
     path:
       stock:
         kconfig: {LATBENCH_IRQ_PATH_STOCK: y}
       wrapped:
         kconfig: {LATBENCH_IRQ_PATH_WRAPPED: y}
         dtc_overlays: [irq_latency/exti_line0_app.overlay]
       direct:
         kconfig: {LATBENCH_IRQ_PATH_DIRECT: y}
         dtc_overlays: [irq_latency/exti_line0_app.overlay]
       zli:
         kconfig: {LATBENCH_IRQ_PATH_ZLI: y}
         dtc_overlays: [irq_latency/exti_line0_app.overlay]
     anchor:
       default: {}
       lean:
         conf_files: [common/conf/lean.conf]

   points:
     - id: direct-16mhz
       kconfig: {LATBENCH_IRQ_PATH_DIRECT: y}
       dtc_overlays:
         - irq_latency/exti_line0_app.overlay
         - common/clocks/nucleo_g474re_16mhz.overlay

The files in ``experiments/`` are the current experiments. Each file starts
with a comment that gives the question of the experiment.

.. _benchguide-result-folder:

Result folder
-------------

A run writes its results to ``<out>/<name>/<UTC time>/``, for example
``<out>/irq-example/20261024T153130Z/``:

.. code-block:: text

   <out>/<name>/<UTC time>/
   ├── manifest.json        provenance of the run
   ├── summary.txt          percentiles of each histogram
   ├── src/tests/benchmarks/ snapshot of the committed sources
   └── <tree>/<point>/
       ├── rep1.log         serial output of repetition 1
       ├── rep2.log         ...
       ├── build.log        CMake and Ninja output
       ├── .config          Kconfig of the build
       ├── zephyr.dts       devicetree of the build
       ├── zephyr.elf       the flashed binary
       └── build/           only with --keep-build

``manifest.json`` has these fields:

- ``experiment``, ``experiment_file``, ``experiment_yaml``: the name, the
  path in the repository and the full text of the experiment file.
- ``command``, ``started``, ``finished``, ``host``.
- ``safety``: the path, the revision and the snapshot folder of the safety
  repository.
- ``trees``, ``trees_root``: the full entries of the trees from
  ``trees.yaml``.
- ``toolchain``: the SDK version and path.
- ``tools``: the versions of CMake, Ninja, OpenOCD, Python and pyserial.
- ``board``, ``probe_serial``: the board and the serial number of the
  ST-LINK (from ``udevadm``).
- ``points``: one entry for each tree and point. An entry has the axes,
  the settings, the CMake command, the SHA-256 of the ELF and the logs.
  If the point failed, it also has an ``error``.

To reproduce a point, do these steps:

#. Check out the safety repository at ``safety.rev`` of the manifest.
#. Create the pinned trees, if they do not exist:

   .. code-block:: console

      tests/benchmarks/scripts/trees.py setup

#. Run the experiment again:

   .. code-block:: console

      tests/benchmarks/scripts/run.py tests/benchmarks/experiments/<name>.yaml --out <dir>

#. Compare the summaries of the old and the new logs (see the next
   section).

Summary and parse (``latbench.py``)
-----------------------------------

.. code-block:: console

   tests/benchmarks/scripts/latbench.py summary [--json] LOG ...
   tests/benchmarks/scripts/latbench.py parse LOG
   tests/benchmarks/scripts/latbench.py capture [--flash BUILD_DIR] [--runner openocd] [--port P] [--timeout S] [--echo] OUT

``summary``
   Prints one row for each histogram of each log. The columns are
   ``log``, ``variant``, ``hist``, ``n``, ``min``, ``p50``, ``p90``, ``p99``,
   ``p99.9``, ``p99.99``, ``max``, ``mean``, ``sd`` and ``ovf``. A percentile
   in an overflow bin shows as ``>=2^e`` (for example ``>=8192``). A
   percentile in a coarse bin shows the lower edge of the bin. ``sd`` is
   ``nan`` if samples are in overflow bins. ``--json`` prints the rows as
   JSON. ``summary`` does not include the phase histograms.

``parse``
   Prints the last record of a log as JSON: ``meta``, ``cfg``, ``hists``,
   ``phases`` and ``errors``.

``capture``
   Flashes a build with ``west flash`` (optional) and saves the serial
   output until ``LAT DONE``. The script reads the port all the time, so
   that the buffer of the host does not overflow. This command is for
   development only. Its results are unpinned.

Plots (``plot.py``)
-------------------

.. code-block:: console

   tests/benchmarks/scripts/plot.py ccdf  --out f.svg [--title T] [--label L]... [--hist H] LOG ...
   tests/benchmarks/scripts/plot.py hist  --out f.svg [--title T] [--label L]... [--hist H] LOG ...
   tests/benchmarks/scripts/plot.py phase --out f.svg [--title T] [--label L]... [--hist H] LOG ...

``ccdf``
   The exceedance probability P(latency > x), on log scales, with one line
   for each log. It shows the floor, the modes and the tail in one chart.

``hist``
   One panel for each log, with the sample count of each bin on a log
   scale. A coarse bin shows its count per cycle.

``phase``
   Two panels for each log, by the tick phase of the edge: the share of
   the samples (1 is uniform), and the minimum, mean and maximum latency.

``--hist`` selects the histogram (or the phase histogram) by name. The
default is the first one in each log. ``--label`` gives the label of the
next log. The default label is ``<tree>/<point>`` from the path of the log.
A chart can have a maximum of 8 logs. ``plot.py`` leaves out values of
2\ :sup:`31` or more (negative differences) and gives their number in the
label.
