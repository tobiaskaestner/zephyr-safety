Host tools and reproducibility
==============================

The folder ``scripts/benchmarks/`` has the host tools. They need Python
3 and the packages in ``scripts/benchmarks/requirements.txt``
(``pyserial``, ``PyYAML``, ``matplotlib``).

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Script
     - Purpose
   * - ``study.py``
     - Study designs (lint, scaffold), lab spaces, pinned trees
       (``study.py trees``), campaigns, and the aggregates of a results
       tree (see :doc:`studies` and :doc:`lab`).
   * - ``trees.py``
     - The library of the pinned trees of ``validation/trees/``. It
       has no commands of its own: use ``study.py trees``. It reads
       ``boards.yaml`` for ``run.py``.
   * - ``run.py``
     - Runs an experiment from pinned, clean trees and records its
       provenance.
   * - ``latbench.py``
     - Captures, parses and summarizes the ``LAT`` output.
   * - ``plot.py``
     - Plots the distributions from the logs.
   * - ``loadmodel.py``
     - Calculates the ticks on which several periodic load timers expire.

Reproducibility rules
---------------------

A data point that you publish or compare must come from ``run.py`` with
an experiment file in the safety repository. These rules apply:

- ``validation/trees/<tree>.yml`` pins each tree (a west manifest): the
  Zephyr revision, the revision of each module, and the Zephyr SDK
  version.
- A pinned revision does not change, because old results refer to it. A
  changed revision means a new tree (see :ref:`benchguide-tree-rule`).
- A Zephyr patch for the study goes on a branch in the Zephyr repository.
  The commit of the patch is the revision of the new tree.
- ``run.py`` stops before it builds anything in these conditions:

  - The safety repository is not clean.
  - The lab space uses a different design repository (see :doc:`lab`).
  - A repository of a tree that the build needs is not at its pinned
    revision, or it is not clean.
  - The SDK version is not the pinned version.

- The safety repository stays clean and at the same commit while the run
  builds. ``run.py`` makes sure of this before each point, and stops if
  the repository changed.
- A manual build or capture is for development only. Its results are
  unpinned.

Pinned trees (``validation/trees/``)
------------------------------------

Each tree is one west manifest, ``validation/trees/<tree>.yml``. The file
has only the pins. The paths of a host are in the ``.lab/config`` of its
lab space (see :doc:`lab`):

- The trees root is ``[trees] root``. ``--trees-root`` or the environment
  variable ``LATBENCH_TREES_ROOT`` overrides it.
- The SDK path is ``[toolchain] zephyr_sdk``. The default is
  ``~/zephyr-sdk-<version>``.
- A folder of local clones to clone from is ``[trees] source``, with the
  layout ``<source>/<tree>/<path>``.

A tree manifest has these keys (the west manifest format):

``manifest.self.userdata``
   ``description`` (one line) and ``zephyr_sdk``, the pinned SDK version.
   The scripts compare it with the ``sdk_version`` file of the SDK. All
   trees must have the same SDK version, because a lab space has one SDK.

``manifest.projects``
   One entry for each repository, with ``name``, ``url``, the pinned
   ``revision`` (a commit), ``path`` in the tree, and ``userdata:
   {branch}``, the branch that has the commit. The project ``zephyr`` has
   ``west-commands: scripts/west-commands.yml``, so that ``west build``
   works in the tree. The manifest does not import the ``west.yml`` of
   Zephyr: the tree has only the projects of the file.

The design lint checks each tree manifest with the parser of west. There
are four trees today:

``ws-safety``
   The Zephyr of the safety workspace.

``ws-up``
   An upstream Zephyr ``main``.

``ws-up-irqoff``
   The Zephyr of ``ws-up`` plus the interrupt mask hooks of M4 (see
   :doc:`m4`), on a local branch (``tkaestner/latency-irqoff-hook``). The
   branch is not pushed, so ``study.py trees setup`` needs a local clone
   for this tree (``[trees] source``).

``ws-safety-driftfix``
   The Zephyr of ``ws-safety`` plus a SysTick experiment, on a local branch
   (``tkaestner/latency-systick-drift``). The branch is not pushed, so
   ``study.py trees setup`` needs a local clone for this tree.

Each tree has the repositories ``zephyr``, ``cmsis_6``, ``hal_stm32``,
``hal_nordic`` and ``hal_nxp``. The boards and the modules that each board
needs are in ``boards.yaml``.

``study.py trees`` has three commands:

.. code-block:: console

   scripts/benchmarks/study.py trees setup [TREE ...]
   scripts/benchmarks/study.py trees check [TREE ...]
   scripts/benchmarks/study.py trees show [TREE ...]

``setup``
   Makes the west workspace ``<trees root>/<tree>/`` of each tree:

   #. It copies the manifest to ``<trees root>/<tree>/manifest/west.yml``.
      If a copy is there and it is different, ``setup`` stops: the pins of
      a tree never change.
   #. It runs ``west init -l manifest`` (only once).
   #. It makes sure that ``west topdir`` gives the tree folder, and stops
      if not.
   #. It runs ``west update``, with ``--path-cache <[trees] source>/<tree>``
      if that folder exists. west makes a plain ``git clone`` of each
      project from the cache (no worktree, no alternates, nothing written
      into the cache) and then sets the remote to the ``url``. A project
      that is not in the cache comes from its ``url``.
   #. It does the same examination as ``check``.

   west runs without the ``ZEPHYR_*`` variables of the caller and without
   the user and system west configuration
   (``WEST_CONFIG_GLOBAL=/dev/null``, ``WEST_CONFIG_SYSTEM=/dev/null``).
   Thus a ``ZEPHYR_BASE`` of another workspace cannot lead west to that
   workspace, and a ``~/.westconfig`` cannot change a build.

``check``
   Makes sure that the SDK has the pinned version. Then it gives the state
   of each tree:

   - ``ok``: each repository is at its pinned revision and clean (no
     changes, no untracked files), and the manifest copy is the same as
     the file in the repository.
   - ``not set up``: a repository has no checkout. This is information:
     a lab space sets up only the trees of its studies. It is an error
     only for a tree that you name.
   - ``wrong``: a repository is not at its pin or not clean, or the
     manifest copy is different. This is an error (exit code 1).

   ``lab status`` shows the same states.

``show``
   Prints the trees root, the trees, the revisions and the paths.

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
repository: ``tests/benchmarks/.gitignore`` lists ``hw-map.yml``. In a
lab space, the map is ``[hardware] map`` of ``.lab/config`` (default
``<lab folder>/hw-map.yml``). Outside a lab space, the default is
``tests/benchmarks/hw-map.yml``.

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

   scripts/benchmarks/run.py validation/empirical/latencies/st-<study>/ex-<name>/experiment.yaml --out <dir>

In a lab space, a campaign runs ``run.py`` for each experiment (see
:doc:`lab`).

Options:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Option
     - Meaning
   * - ``--out <dir>``
     - The folder for the results (necessary, but not with
       ``--build-only`` or ``--dry-run``).
   * - ``--only ID ...``
     - Run only the points with these IDs.
   * - ``--dry-run``
     - Do the checks and list the points. Do not build.
   * - ``--build-only``
     - Build each point. Do not flash. In a lab space, the images go into
       the build cache. Outside a lab space, the builds go to a temporary
       folder.
   * - ``--no-cache``
     - Do not use the build cache of the lab space: build each point
       again, and do not store the image in the cache.
   * - ``--warn-as-error``
     - Stop before the build if the design lint finds a problem (error or
       warning) in the experiment or in its study (see
       :ref:`benchguide-lint`). Without it, ``run.py`` prints the problems
       and continues.
   * - ``--keep-build``
     - Keep the build folder of each point.
   * - ``--rebuild <run>``
     - Build the points of an old run again and compare them with the
       stored files (see :ref:`benchguide-rebuild`). ``<run>`` is a run
       folder or one ``<run>/<tree>/<point>`` folder. Use it without an
       experiment and without ``--out``. ``--only`` selects points.
   * - ``--hardware-map <file>``
     - The hardware map (default: ``[hardware] map`` of the lab space,
       else ``tests/benchmarks/hw-map.yml``, see :ref:`benchguide-hw-map`).
   * - ``--probe <id>``
     - Select the map entry with this probe ID, if the map has more than
       one entry for the board. With ``--port``, ``run.py`` uses no map.
   * - ``--port <dev>``
     - The serial port (default: ``serial`` of the map entry).
   * - ``--trees-root <dir>``
     - Override the trees root of the lab space (also
       ``LATBENCH_TREES_ROOT``).

``run.py`` does these steps:

#. **Checks.** It makes sure that the safety repository is clean and that
   the experiment file is in it. In a lab space, the design repository of
   the lab space must be this repository. It runs the design lint for the
   experiment and its study (see :ref:`benchguide-lint`). It finds the board target (``board:`` of
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
#. **Sources.** The build reads the app from the safety repository, not
   from a copy. Before each point, ``run.py`` makes sure that the
   repository is clean and at the commit of the start of the run. If not,
   the run stops. Thus a change in the worktree during a run cannot change
   what the run builds. A campaign also keeps the commit with a ref (see
   :doc:`lab`). Runs of an older ``run.py`` have a copy of the repository
   in ``<run>/src/``.
#. **Build.** For each tree and each point, it takes the image from the
   build cache of the lab space if the cache has it (see
   :ref:`benchguide-build-cache`). Else it runs CMake and Ninja with:

   - ``ZEPHYR_BASE`` set to the Zephyr of the tree, and all other
     ``ZEPHYR_*`` environment variables removed.
   - ``-DBOARD`` set to the board target.
   - ``-DZEPHYR_MODULES`` set to the modules of the board from the tree
     only, so that no module of a west workspace goes into the build. The
     safety repository is one more module: it is the Zephyr
     module ``safety`` (``zephyr/module.yml``), so an app finds it as
     ``ZEPHYR_SAFETY_MODULE_DIR``. The module has no code, so the image
     does not change. The ``.config`` gets one more line,
     ``CONFIG_ZEPHYR_SAFETY_MODULE=y``.
   - ``-DWEST_TOPDIR`` set to the folder of the tree. Zephyr writes the
     paths of ``__FILE__`` (the messages of ``__ASSERT``) and the paths in
     the comments of ``zephyr.dts`` relative to ``WEST_TOPDIR``. Without
     this value, Zephyr looks for a west workspace around the tree, and an
     image with ``ASSERT`` then depends on the host. ``common/latbench.cmake``
     also replaces the folder of the common code with ``LATBENCH_COMMON``
     in ``__FILE__``.
   - ``-DEXTRA_CONF_FILE`` and ``-DEXTRA_DTC_OVERLAY_FILE`` from the point.
   - ``-DCONFIG_<SYM>=<value>`` for each Kconfig value of the point.
   - ``-DLATBENCH_SRC_REV`` set to a content hash of the firmware files of ``tests/benchmarks`` (kind
     ``firmware/1``: all files without the host scripts in ``scripts/``,
     Python, Markdown, ``testcase.yaml`` and ``boards.yaml``) at the commit of
     the run. The same firmware gives the same image at any commit.
   - ``-DBUILD_VERSION`` set to ``git describe --abbrev=12 --always`` of
     the Zephyr tree, as Zephyr makes it. The string depends on the tags
     of the tree; in the CMake command, a rebuild gives the same string.

#. **Kconfig check.** It compares each Kconfig value of the point with the
   ``.config`` of the build. If the ``.config`` does not have the requested
   value, the run stops. Kconfig can ignore a value without an error
   (see :doc:`pitfalls`).
#. **Flash and capture.** For each repetition, it opens the serial port
   and runs the ``flash`` commands of the board in order. Then it saves the
   output until ``LAT DONE``. If no ``LAT DONE`` comes before the timeout,
   or the flash fails, the run stops.
#. **Summary.** It writes ``summary.txt`` with the percentiles of each
   histogram, one column per axis, and prints how many images came from
   the build cache.
#. **Seal and run list.** It writes the seal. If ``--out`` is the folder
   of a study instance, it adds the run to the run list of the instance,
   with ``--role`` (default ``evidence``) and ``--reason``. ``--campaign
   ID`` names the campaign in the entry. It prints ``run <id> added to the
   instance <folder>``.

``run.py`` writes ``manifest.json`` at the start and updates it after each
repetition. Thus a run that stops still has a manifest for the completed
repetitions. A run that stops before its seal (an error, Ctrl-C or
SIGTERM) writes ``<UTC time>.failed.json`` beside its folder: the step
(for example ``flash and capture ws-safety/stock-idle rep 1``), the error
and the last 20 lines of the log of that step. Such a run is not in a run
list, so the results build and the export do not see it.

.. _benchguide-experiment-file:

Experiment file
---------------

An experiment is a folder ``ex-<name>/`` in the folder of the study that
owns it, below ``validation/empirical/latencies/``. A sub-study is a
folder ``st-<name>/``. The prefixes are only in the folder names; the
names in the files have no prefix. The experiment folder holds the
experiment file ``experiment.yaml`` and the description
``experiment.md``. The schema ``scripts/benchmarks/schemas/experiment.schema.yaml``
gives the keys and their types; ``run.py`` stops on a key that it does not
know. The keys of the experiment file are:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Key
     - Meaning
   * - ``name``
     - Name of the experiment. It is the name of the folder in the output.
       The experiment folder must be ``ex-<name>``.
   * - ``app``
     - The app folder in ``tests/benchmarks/``.
   * - ``trees``
     - List of tree names (the files of ``validation/trees/``).
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
     - A map of axes. Each axis is a map from a value name to settings.
       ``run.py`` makes one point for each combination of the values
       (Cartesian product). An experiment has one axis or more. An
       experiment that changes one factor at a time has one axis,
       ``variant``.
   * - ``extra_axes``
     - Optional. A map from an axis name to a value name: axes that only
       the explicit points change. All points of ``axes`` get this value.
   * - ``points``
     - Optional. A list of explicit points, each with an ``id`` and with
       ``axes``, a map that gives a value on each axis (also on each of
       ``extra_axes``). You can use ``axes`` and ``points`` together.

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

``value``
   Only in an axis value. The number of the value, for example ``16`` for
   ``t16`` (16 load timers). A plot uses it as the x value.

The value names of an axis must be text. YAML reads ``on``, ``off``,
``yes``, ``no``, ``true`` and ``false`` as Booleans, so ``run.py`` refuses
these names. Put them in quotes, or use other names.

The axes of each point go into the manifest, so the analysis can group
and plot the points by axis.

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

   extra_axes:
     clock: 170mhz

   points:
     - id: direct-16mhz
       axes: {path: direct, anchor: default, clock: 16mhz}
       kconfig: {LATBENCH_IRQ_PATH_DIRECT: y}
       dtc_overlays: [common/boards/nucleo_g474re/clocks/nucleo_g474re_16mhz.overlay]

The paths ``wrapped``, ``direct`` and ``zli`` need no overlay in the
experiment. ``run.py`` puts their Kconfig value on the CMake command line,
and the port then adds its ``resp_irq_own.overlay`` (see :doc:`apps`).

The experiment folders in the study folders below
``validation/empirical/latencies/`` are the current experiments. The
description ``experiment.md`` in each folder gives the question of the
experiment.

.. _benchguide-result-folder:

Result folder
-------------

A run writes its results to ``<out>/<name>/<UTC time>/``, for example
``<out>/irq-example/20261024T153130Z/``:

.. code-block:: text

   <out>/<name>/<UTC time>/
   ├── manifest.json        provenance of the run
   ├── summary.txt          percentiles of each histogram
   └── <tree>/<point>/
       ├── rep1.log         serial output of repetition 1
       ├── rep2.log         ...
       ├── build.log        CMake and Ninja output
       ├── .config          Kconfig of the build
       ├── zephyr.dts       devicetree of the build
       ├── <app>-<tree>-<point>.elf   the binary
       ├── <app>-<tree>-<point>.hex   the binary as Intel HEX, if the build makes it
       └── build/           only with --keep-build

The image names, for example ``irq_latency-ws-safety-stock-idle.elf``,
say what the image is also outside its folder. The runs before
2026-10-28 have ``zephyr.elf`` and ``zephyr.hex``; their seals cover the
names, so they keep them. The tools find the image by either name.

A run of an older ``run.py`` also has ``src/``, a copy of the safety
repository (``git archive``). Its builds used this copy.

``manifest.json`` has these fields:

- ``experiment``, ``experiment_file``, ``experiment_yaml``,
  ``experiment_sha256``: the name, the path in the repository, the full
  text and the SHA-256 of the experiment file.
- ``command``, ``started``, ``finished``, ``host``.
- ``lab``: the lab space (``id``, ``name``, ``folder``), or ``null``
  outside a lab space.
- ``safety``: the path and the revision of the safety repository, the
  local ref of the run (``ref``), the firmware hash (``bench_tree``, the
  ``LATBENCH_SRC_REV`` of the app, kind ``bench_tree_kind``; the first
  runs of 2026-10-27 have the git tree hash of ``tests/benchmarks`` and
  no kind) and the git tree hash of the module folder ``zephyr/``
  (``module_tree``). A run of an older ``run.py`` has instead the
  benchmark folder in its ``src/`` copy (``snapshot``) and the module
  folder (``module``). A still older run has no ``module``. The oldest
  runs have no ``snapshot``, because they built from the worktree.
- ``trees``, ``trees_root``: the entries of the trees (from the tree
  manifests, ``validation/trees.yaml`` before 2026-10-28), with only the
  repositories that the build used, and the trees root of the host.
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
  In a lab space, it also has ``build``: ``key`` (the key of the build
  cache), ``from`` (``build`` or ``cache``) and, for an image from the
  cache, ``built_by`` (the run that built it, or ``<experiment> (build
  only, <UTC>)`` for ``campaign prepare``). The runs before 2026-10-28 have
  ``cached`` (``true`` or ``false``) instead of ``from``. If the point
  failed, it also has an ``error``.

.. _benchguide-rebuild:

Reproduce a point
~~~~~~~~~~~~~~~~~

A point has two parts that you can reproduce: the image, and the
measurement.

To make sure that the image is the same, build the points of the run
again:

.. code-block:: console

   scripts/benchmarks/run.py --rebuild <run>
   scripts/benchmarks/run.py --rebuild <run>/<tree>/<point>

``--rebuild`` does these steps:

#. It reads the manifest. It makes sure that the trees are at the
   revisions of the manifest and clean, and that the SDK has the version
   of the manifest. The revisions of the current tree manifests are not
   used, so the check also works after a change of these files.
   ``--trees-root`` or ``LATBENCH_TREES_ROOT`` overrides ``trees_root`` of
   the manifest. If that folder does not exist (the trees moved, or a run
   of a different host), the trees root of the lab space is used. A run
   from before ``-DWEST_TOPDIR`` took ``WEST_TOPDIR`` from a west
   workspace around its trees root. ``--rebuild`` then gives the build the
   same folder relative to the new root, so that the ``__FILE__`` strings
   stay the same. If the SDK path of the manifest does not exist (a run of
   a different host), the SDK path of this host is used (``[toolchain]
   zephyr_sdk`` of the lab space, or its default). Its version must be
   that of the manifest.
#. It runs the CMake command of the manifest again, with the same sources.
   For a run with ``safety.bench_tree``, it exports the commit
   ``safety.rev`` of the safety repository (``git archive``) into a
   temporary folder. It stops if the commit is not in the repository
   (fetch it, or its ref ``safety.ref`` from the lab repository), or if the
   hash of the kind ``bench_tree_kind`` at that commit is not
   ``bench_tree``. A run of an older ``run.py`` uses its copy in ``src/``.
   A run without ``src/`` built from the worktree, and its build took the
   revision string from ``git describe``. For such a run, ``--rebuild``
   makes a temporary git worktree at ``safety.rev``, so that ``git
   describe`` gives the same string. It stops if the revision is not in
   the safety repository.
#. It builds into a temporary folder, never into the sealed run folder.
   The ELF then has other debug information, so its SHA-256 differs; the
   flashed image decides (next step).
#. It compares ``zephyr.elf`` (SHA-256), ``zephyr.hex``, ``.config`` and
   ``zephyr.dts`` with the stored files. If the SHA-256 of the ELF is not
   the same, it also compares the loadable sections of the two ELFs
   (``objcopy -O ihex``, without the debug information). It compares
   ``.config`` and ``zephyr.dts`` without their comments, because the
   comments have the paths of the host. A point is the same if the
   flashed image and the ``.config`` are the same. The flashed image is
   ``zephyr.hex``. If the run has no HEX file, it is the ELF or its
   loadable sections.

``--rebuild`` does not flash. At the end, the result folder is as it was
before (with ``--keep-build``, the ``build/`` folders stay). It prints
one line for each point and exits with 1 if a point is not the same. Then
the logs and the builds of the points that are not the same stay in a
temporary folder, and the last line gives the folder.

To reproduce the measurement, run the experiment again, from the safety
repository at ``safety.rev`` of the manifest:

.. code-block:: console

   scripts/benchmarks/study.py trees setup
   scripts/benchmarks/run.py validation/empirical/latencies/st-<study>/ex-<name>/experiment.yaml --out <dir>

Then compare the summaries of the old and the new logs (see the next
section).

Summary and parse (``latbench.py``)
-----------------------------------

.. code-block:: console

   scripts/benchmarks/latbench.py summary [--json | --md] [--hist H]... [--meta KEY]... LOG ...
   scripts/benchmarks/latbench.py parse LOG
   scripts/benchmarks/latbench.py capture [--flash BUILD_DIR] [--runner openocd] [--port P] [--timeout S] [--echo] OUT

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

   scripts/benchmarks/plot.py ccdf  --out f.svg [--title T] [--label L]... [--hist H] LOG ...
   scripts/benchmarks/plot.py hist  --out f.svg [--title T] [--label L]... [--hist H] LOG ...
   scripts/benchmarks/plot.py phase --out f.svg [--title T] [--label L]... [--hist H] LOG ...

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

Load timer model (``loadmodel.py``)
-----------------------------------

.. code-block:: console

   scripts/benchmarks/loadmodel.py run  [--seed S] [--timers N] [--min-ms A] [--max-ms B] [--seconds T] [--parts P]
   scripts/benchmarks/loadmodel.py scan [--timers N] ... [SEED ...]
   scripts/benchmarks/loadmodel.py log  LOG

The periodic load timers of ``common/src/load.c`` get their periods and
first expiries from the seed ``LATBENCH_LOAD_TIMER_SEED``. They do not
depend on the stimulus. Thus each run with the same seed has the same
ticks with k expiries. The system timer ISR processes the k expiries one
after the other, so these ticks are the long ISRs of the run. A different
stimulus seed gives only new edges on the same ticks. A longer run or a
different load seed gives new ticks.

``run``
   For one seed: the number of ticks with k expiries, the time of the
   first tick with at least k expiries, and the counts in each of P parts
   of the run.

``scan``
   For each seed (the default is the 64 SHA-256 round constants): the
   number of ticks with at least k expiries. Use it to select load seeds
   by a rule, not by hand.

``log``
   Reads the timer parameters, the seed and the run length from the
   ``LAT META`` lines of a log, and compares the expiries of the model
   with ``load_timer_expiries``. The model starts the timers at tick 0, so
   the two numbers can differ by a few expiries.
