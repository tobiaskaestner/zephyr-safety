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
     - Creates and examines the pinned trees of ``trees.yaml``. Reads
       ``boards.yaml`` for ``run.py``.
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
- A pinned revision does not change, because old results refer to it. A
  changed revision means a new tree (see :ref:`benchguide-tree-rule`).
- A Zephyr patch for the study goes on a branch in the Zephyr repository.
  The commit of the patch is the revision of the new tree.
- ``run.py`` stops before it builds anything in these conditions:

  - The safety repository is not clean.
  - A repository of a tree that the build needs is not at its pinned
    revision, or it is not clean.
  - The SDK version is not the pinned version.

- A manual build or capture is for development only. Its results are
  unpinned.

Pinned trees (``trees.yaml``)
-----------------------------

``trees.yaml`` has these keys:

``root``
   The folder that holds the trees. ``--trees-root`` or the environment
   variable ``LATBENCH_TREES_ROOT`` overrides it.

``toolchain.zephyr_sdk``
   The pinned SDK ``version`` and its ``path``. The scripts compare the
   version with the ``sdk_version`` file of the SDK.

``trees.<name>``
   One entry for each tree, with a ``description`` and a ``repos`` map.
   Each repository has a ``path`` in the tree, a ``url``, an optional
   ``branch``, the pinned ``rev``, and an optional ``source``. The
   ``source`` is a local clone that has the revision, so that no network
   access is necessary.

The file declares three trees today:

``ws-safety``
   The Zephyr of the safety workspace.

``ws-up``
   An upstream Zephyr ``main``.

``ws-safety-driftfix``
   The Zephyr of ``ws-safety`` plus a SysTick experiment, on a local branch
   (``tkaestner/latency-systick-drift``). The branch is not pushed, so
   ``trees.py setup`` needs the local ``source`` clone for this tree.

Each tree has the repositories ``zephyr``, ``cmsis_6``, ``hal_stm32``,
``hal_nordic`` and ``hal_nxp``. The boards and the modules that each board
needs are in ``boards.yaml``.

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

   With ``--clone-source``, ``setup`` clones the ``source`` clone instead
   of adding a worktree to it. The local clone uses hard links to the
   objects and needs no network access. Nothing is written into the
   ``source``: a worktree writes ``.git/worktrees/<name>`` there, and a
   fetch writes objects there. If the revision is not in the ``source``,
   the new clone fetches the ``branch`` from the ``url``. Use it on a host
   where a ``source`` path is a repository of a different workspace that
   must not change.

``check``
   Makes sure that the SDK has the pinned version. Then it makes sure
   that each repository exists, is at its pinned revision and is clean
   (no changes, no untracked files).

``show``
   Prints the trees, the revisions and the paths.

Do not change files in a tree. A tree with changes is not clean, and
``run.py`` refuses it.

.. _benchguide-tree-rule:

Change the trees
~~~~~~~~~~~~~~~~

- A pinned revision never changes. To use another revision of a
  repository, add a new tree with a new name, and keep the old tree.
- You can add a module repository to an existing tree. This does not
  change old builds, because each build uses only the modules of its
  board (``boards.yaml``).
- If a tree does not pin a module of the board, ``run.py`` stops before it
  builds anything.

.. _benchguide-boards-yaml:

Boards (``boards.yaml``)
------------------------

``boards.yaml`` has these keys:

``default``
   The board target of an experiment without ``board:``
   (``nucleo_g474re``).

``boards.<board target>``
   One entry for each board target, with these keys:

   ``port``
      The folder of the board port in ``common/boards/``.

   ``modules``
      The repositories of the tree that the build needs. The build gets
      exactly these as ``ZEPHYR_MODULES``.

   ``flash``
      A list of commands that program the board and reset it. ``run.py``
      runs them in order. In each argument, ``{zephyr}`` is the Zephyr of
      the tree, ``{elf}`` and ``{hex}`` are the images of the point, and
      ``{probe}`` is the probe ID from the hardware map. Each command must
      select the probe with ``{probe}``: a host can have more than one
      probe.

   ``status``
      ``tested`` if data points exist, ``untested`` if the board only
      builds.

Example (the entry of the NUCLEO-G474RE):

.. code-block:: yaml

   nucleo_g474re:
     port: nucleo_g474re
     modules: [cmsis_6, hal_stm32]
     flash:
       - [openocd, -f, "{zephyr}/boards/st/nucleo_g474re/support/openocd.cfg",
          -c, "adapter serial {probe}", -c, "program {elf} verify reset exit"]
     status: tested

``boards.yaml`` has no serial port and no probe ID. These belong to the
host. They are in the hardware map.

.. _benchguide-hw-map:

Hardware map (``hw-map.yml``)
-----------------------------

The hardware map tells ``run.py`` which probe and which serial port a
board has on this host. It is a twister hardware map (see the Zephyr
documentation, "Executing tests on multiple devices"). It is not in the
repository: ``tests/benchmarks/.gitignore`` lists ``hw-map.yml``.

Make the map with twister, from a Zephyr tree, on the host with the
boards:

.. code-block:: console

   west twister --generate-hardware-map tests/benchmarks/hw-map.yml --persistent-hardware-map

``--persistent-hardware-map`` writes the serial ports as
``/dev/serial/by-id/...`` names. These names do not change when the
boards are connected in a different sequence. Use them, not
``/dev/ttyACM<n>``. If the file exists, twister updates it and keeps the
other entries.

Then edit each entry:

- Set ``platform`` to the board target of ``boards.yaml``.
- Add the fixture ``latbench_loopback`` if the board has the wire. A text
  after a colon is a note, for example ``latbench_loopback:D2-A3``.
- If a probe has more than one serial port (the J-Link OB of the Nordic
  DKs), twister writes one entry for each port. Keep the entry of the
  console port, and write the reason in ``notes``.

Example:

.. code-block:: yaml

   - connected: true
     id: 0042003F3433510A37363934
     platform: nucleo_g474re
     product: STLINK-V3
     runner: openocd
     serial: /dev/serial/by-id/usb-STMicroelectronics_STLINK-V3_0042003F3433510A37363934-if02
     fixtures:
       - latbench_loopback:D2-A3

``run.py`` reads the map only when it flashes (not with ``--dry-run``,
``--build-only`` or ``--rebuild``). It checks the map against the twister
schema of the first tree of the experiment
(``scripts/schemas/twister/hwmap-schema.yaml``). Then it selects the one
entry with ``connected: true``, the board target in ``platform`` and the
fixture ``latbench_loopback``. ``probe_id`` replaces ``id`` as the probe
ID, as in twister. ``baud`` or ``serial_baud`` sets the baud rate
(default 115200). The manifest records the entry in ``hardware``.

The map has no data that changes a measurement, so it is not part of the
provenance of a data point. The manifest records it for the
investigation of a failed run.

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
   * - ``--rebuild <run>``
     - Build the points of an old run again and compare them with the
       stored files (see :ref:`benchguide-rebuild`). ``<run>`` is a run
       folder or one ``<run>/<tree>/<point>`` folder. Use it without an
       experiment and without ``--out``. ``--only`` selects points.
   * - ``--hardware-map <file>``
     - The hardware map (default: ``tests/benchmarks/hw-map.yml``, see
       :ref:`benchguide-hw-map`).
   * - ``--probe <id>``
     - Select the map entry with this probe ID, if the map has more than
       one entry for the board. With ``--port``, ``run.py`` uses no map.
   * - ``--port <dev>``
     - The serial port (default: ``serial`` of the map entry).
   * - ``--trees-root <dir>``
     - Override ``root`` of ``trees.yaml``.

``run.py`` does these steps:

#. **Checks.** It makes sure that the safety repository is clean and that
   the experiment file is in it. It finds the board target (``board:`` of
   the experiment, or ``default`` of ``boards.yaml``). It makes sure that
   the SDK is as pinned. For each tree of the experiment, it makes sure
   that the tree pins ``zephyr`` and the modules of the board. Then it
   makes sure that these repositories are as pinned. Other repositories of the tree are
   not examined. Then it expands the points.
   An axis value name that YAML reads as a Boolean (``on``, ``off``,
   ``yes``, ``no``, ``true``, ``false``) stops the run.
#. **Hardware.** It selects the entry of the board in the hardware map
   (see :ref:`benchguide-hw-map`). Without one connected entry with the
   fixture ``latbench_loopback``, the run stops before it builds.
#. **Snapshot.** It exports the safety repository at the current revision
   with ``git archive`` into ``<run>/src/``. All builds use this snapshot,
   not the worktree. Thus work in the worktree during a long run does not
   change what the run builds. The snapshot stays in the result folder, so
   the sources of each data point stay available also after a rebase of
   the branch.
#. **Build.** For each tree and each point, it runs CMake and Ninja with:

   - ``ZEPHYR_BASE`` set to the Zephyr of the tree, and all other
     ``ZEPHYR_*`` environment variables removed.
   - ``-DBOARD`` set to the board target.
   - ``-DZEPHYR_MODULES`` set to the modules of the board from the tree
     only, so that no module of a west workspace goes into the build. The
     snapshot is one more module: the safety repository is the Zephyr
     module ``safety`` (``zephyr/module.yml``), so an app finds it as
     ``ZEPHYR_SAFETY_MODULE_DIR``. The module has no code, so the image
     does not change. The ``.config`` gets one more line,
     ``CONFIG_ZEPHYR_SAFETY_MODULE=y``.
   - ``-DEXTRA_CONF_FILE`` and ``-DEXTRA_DTC_OVERLAY_FILE`` from the point.
   - ``-DCONFIG_<SYM>=<value>`` for each Kconfig value of the point.
   - ``-DLATBENCH_SRC_REV`` set to the safety revision.

#. **Kconfig check.** It compares each Kconfig value of the point with the
   ``.config`` of the build. If the ``.config`` does not have the requested
   value, the run stops. Kconfig can ignore a value without an error
   (see :doc:`pitfalls`).
#. **Flash and capture.** For each repetition, it opens the serial port
   and runs the ``flash`` commands of the board in order. Then it saves the
   output until ``LAT DONE``. If no ``LAT DONE`` comes before the timeout,
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
     - Optional. A board target of ``boards.yaml``. The default is
       ``default`` of ``boards.yaml``.
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
   A list of devicetree overlays, relative to ``tests/benchmarks/``. The
   board port adds its own overlays. Do not list them here.

The value names of an axis must be text. YAML reads ``on``, ``off``,
``yes``, ``no``, ``true`` and ``false`` as Booleans, so ``run.py`` refuses
these names. Put them in quotes, or use other names.

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
       direct:
         kconfig: {LATBENCH_IRQ_PATH_DIRECT: y}
       zli:
         kconfig: {LATBENCH_IRQ_PATH_ZLI: y}
     anchor:
       default: {}
       lean:
         conf_files: [common/conf/lean.conf]

   points:
     - id: direct-16mhz
       kconfig: {LATBENCH_IRQ_PATH_DIRECT: y}
       dtc_overlays: [common/boards/nucleo_g474re/clocks/nucleo_g474re_16mhz.overlay]

The paths ``wrapped``, ``direct`` and ``zli`` need no overlay in the
experiment. ``run.py`` puts their Kconfig value on the CMake command line,
and the port then adds its ``resp_irq_own.overlay`` (see :doc:`apps`).

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
   ├── src/                 snapshot of the safety repository
   └── <tree>/<point>/
       ├── rep1.log         serial output of repetition 1
       ├── rep2.log         ...
       ├── build.log        CMake and Ninja output
       ├── .config          Kconfig of the build
       ├── zephyr.dts       devicetree of the build
       ├── zephyr.elf       the binary
       ├── zephyr.hex       the binary as Intel HEX, if the build makes it
       └── build/           only with --keep-build

``manifest.json`` has these fields:

- ``experiment``, ``experiment_file``, ``experiment_yaml``: the name, the
  path in the repository and the full text of the experiment file.
- ``command``, ``started``, ``finished``, ``host``.
- ``safety``: the path and the revision of the safety repository, the
  benchmark folder in the snapshot (``snapshot``), and the module folder
  (``module``). A run of an older ``run.py`` has only
  ``tests/benchmarks`` in the snapshot and no ``module``. The oldest runs
  have no ``snapshot``, because they built from the worktree.
- ``trees``, ``trees_root``: the entries of the trees from ``trees.yaml``,
  with only the repositories that the build used.
- ``toolchain``: the SDK version and path.
- ``tools``: the versions of CMake, Ninja, Python, pyserial, and of each
  tool in the ``flash`` commands of the board (for example ``openocd``,
  ``nrfutil`` or ``pyocd``).
- ``board``, ``board_cfg``, ``console``: the board target, its entry from
  ``boards.yaml``, and the serial port.
- ``probe_serial``: the serial number of the debug probe of the console
  port (from ``udevadm``).
- ``points``: one entry for each tree and point. An entry has the axes,
  the settings, the CMake command, the SHA-256 of the ELF and the logs.
  If the point failed, it also has an ``error``.

.. _benchguide-rebuild:

Reproduce a point
~~~~~~~~~~~~~~~~~

A point has two parts that you can reproduce: the image, and the
measurement.

To make sure that the image is the same, build the points of the run
again:

.. code-block:: console

   tests/benchmarks/scripts/run.py --rebuild <run>
   tests/benchmarks/scripts/run.py --rebuild <run>/<tree>/<point>

``--rebuild`` does these steps:

#. It reads the manifest. It makes sure that the trees are at the
   revisions of the manifest and clean, and that the SDK has the version
   of the manifest. The current ``trees.yaml`` is not used, so the check
   also works after a change of ``trees.yaml``. ``--trees-root`` overrides
   ``trees_root`` of the manifest.
#. It runs the CMake command of the manifest again, with the same sources:
   the snapshot in ``src/``. A run without a snapshot built from the
   worktree, and its build took the revision string from ``git
   describe``. For such a run, ``--rebuild`` makes a temporary git
   worktree at ``safety.rev``, so that ``git describe`` gives the same
   string. It stops if the revision is not in the safety repository.
#. It builds into the original build folder, if that folder is free and
   the run folder did not move. Then the ELF has the same debug
   information, and its SHA-256 can be the same as in the manifest. Else
   it builds into a temporary folder.
#. It compares ``zephyr.elf`` (SHA-256), ``zephyr.hex``, ``.config`` and
   ``zephyr.dts`` with the stored files. If the SHA-256 of the ELF is not
   the same, it also compares the loadable sections of the two ELFs
   (``objcopy -O ihex``, without the debug information). A point is the
   same if the flashed image and the ``.config`` are the same. The
   flashed image is ``zephyr.hex``. If the run has no HEX file, it is the
   ELF or its loadable sections.

``--rebuild`` does not flash. At the end, the result folder is as it was
before (with ``--keep-build``, the ``build/`` folders stay). It prints
one line for each point and exits with 1 if a point is not the same. Then
the logs and the builds of the points that are not the same stay in a
temporary folder, and the last line gives the folder.

To reproduce the measurement, run the experiment again, from the safety
repository at ``safety.rev`` of the manifest:

.. code-block:: console

   tests/benchmarks/scripts/trees.py setup
   tests/benchmarks/scripts/run.py tests/benchmarks/experiments/<name>.yaml --out <dir>

Then compare the summaries of the old and the new logs (see the next
section).

Summary and parse (``latbench.py``)
-----------------------------------

.. code-block:: console

   tests/benchmarks/scripts/latbench.py summary [--json | --md] [--hist H]... [--meta KEY]... LOG ...
   tests/benchmarks/scripts/latbench.py parse LOG
   tests/benchmarks/scripts/latbench.py capture [--flash BUILD_DIR] [--runner openocd] [--port P] [--timeout S] [--echo] OUT

``summary``
   Prints one row for each histogram of each log. The columns are
   ``log``, ``variant``, ``hist``, ``n``, ``min``, ``p50``, ``p90``, ``p99``,
   ``p99.9``, ``p99.99``, ``max``, ``mean``, ``sd``, ``ovf`` and ``inv``.
   ``inv`` is the number of invalid samples (see :ref:`benchguide-hist`).
   ``mean`` does not include them. A percentile
   in an overflow bin shows as ``>=2^e`` (for example ``>=8192``). A
   percentile in a coarse bin shows the lower edge of the bin. ``sd`` is
   ``nan`` if samples are in overflow bins. ``--json`` prints the rows as
   JSON. ``--md`` prints a Markdown table. ``summary`` does not include the
   phase histograms.

   ``--hist H`` shows only the histogram ``H``. Give it more than once for
   more histograms. ``--meta KEY`` adds the ``LAT META`` value ``KEY`` as a
   column. The key ``drift_ppm`` is calculated: ``clock_drift_cyc`` divided
   by ``clock_elapsed_cyc``, in parts per million. It is empty if
   ``clock_drift_cyc`` is ``n/a``.

   A log from before the ``invalid=`` field has the invalid samples in the
   overflow bin 31. ``summary`` then counts them in ``inv``. If all other
   samples are in bins, it calculates ``mean`` again from the bins without
   them.

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
A chart can have a maximum of 8 logs. ``plot.py`` gives the number of
invalid samples in the label. In a log from before the ``invalid=`` field,
it leaves out the overflow bin 31.
