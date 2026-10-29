The tool run.py
===============

.. code-block:: console

   scripts/benchmarks/run.py validation/empirical/latencies/st-<study>/ex-<name>/experiment.yaml --out <dir>
   scripts/benchmarks/run.py --rebuild <run>[/<tree>/<point>] [--only ID ...]

``run.py`` runs one :term:`experiment`: it builds the :term:`points
<point>` from the pinned :term:`trees <tree>`, flashes the board, and
saves the serial output. One execution of ``run.py`` makes one
:term:`run`. In a :term:`lab space`, a :term:`campaign` runs ``run.py``
for each experiment (see :doc:`../../explanation/campaigns`).

``--out`` names the folder for the results. The run folder is
``<out>/<experiment>/<UTC time>/``. ``<out>`` can be the folder of an
:term:`instance` (it has ``instance.json``). Then the run folder is
``<out>/ex-<experiment>/<UTC time>/``, and ``run.py`` adds the run to the
run list of the instance. A run with ``--out`` outside an instance is a
try-out: no :term:`study` reads it.

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
     - Do the checks of the first step and list the points. Do not build.
   * - ``--build-only``
     - Build each point. Do not flash. In a lab space, the images go into
       the :term:`build cache`. Outside a lab space, the builds go to a
       temporary folder.
   * - ``--no-cache``
     - Do not use the build cache of the lab space: build each point
       again, and do not store the image in the cache.
   * - ``--warn-as-error``
     - Stop before the build if the design lint finds a problem (error or
       warning) in the experiment or in its study (see
       :ref:`benchguide-lint`). Without it, ``run.py`` prints the problems
       and continues.
   * - ``--keep-build``
     - Keep the build folder of each point. With the build cache, the
       build is in a work folder of the cache. The cache keeps only the
       files of an entry. Thus ``--keep-build`` keeps nothing there: use
       it with ``--no-cache``. With ``--rebuild``, the builds stay in the
       temporary folder of the rebuild.
   * - ``--role``, ``--reason``
     - The :term:`role` of the run in the run list of an instance
       (``evidence``, ``adjustment``, ``excluded``). The default is
       ``evidence``. A run of some points with ``--only`` must name the
       role. ``--reason`` gives the reason of a role other than
       ``evidence``. ``run.py`` checks the role, the reason and the
       instance (the experiment of its study, the board) before the first
       build.
   * - ``--campaign``
     - The id of the campaign that starts the run, for the run-list
       entry. A run without it takes the board lock of the lab space.
   * - ``--rebuild <run>``
     - Build the points of an old run again and compare them with the
       stored files (see :ref:`benchguide-rebuild-ref`). ``<run>`` is a run
       folder or one ``<run>/<tree>/<point>`` folder. Use it without an
       experiment and without ``--out``. ``--only`` selects points.
   * - ``--hardware-map <file>``
     - The hardware map (default: ``[hardware] map`` of the lab space,
       else ``tests/benchmarks/hw-map.yml``, see :ref:`benchguide-hw-map`).
   * - ``--probe <id>``
     - Select the entry of the hardware map with this probe ID. This is
       necessary if the map has more than one connected entry for the
       board.
   * - ``--port <dev>``
     - The serial port of the console. Alone, it replaces ``serial`` of
       the selected map entry. Together with ``--probe``, ``run.py`` does
       not read the hardware map (see the step **Hardware**).
   * - ``--trees-root <dir>``
     - Override the trees root of the lab space (also
       ``LATBENCH_TREES_ROOT``).

Steps of a run
--------------

``run.py`` does these steps:

#. **Checks.** It makes sure that the :term:`safety repository` is clean and that
   the experiment file is in it. In a lab space, the :term:`design repository` of
   the lab space must be this repository. It runs the design lint for the
   experiment and its study (see :ref:`benchguide-lint`). It finds the
   :term:`board target` (``board:`` of the experiment, or ``default`` of
   ``boards.yaml``, see :doc:`../files/boards-yaml`). It makes sure that
   the SDK is as pinned. For each tree of the experiment, it makes sure
   that the tree pins ``zephyr`` and the modules of the board. Then it
   makes sure that these repositories are as pinned. Other repositories
   of the tree are not examined. Then it expands the points. An axis
   value name that YAML reads as a Boolean (``on``, ``off``, ``yes``,
   ``no``, ``true``, ``false``) stops the run.
#. **Hardware.** It selects the connected entry of the board in the
   hardware map (see :ref:`benchguide-hw-map`). The entry must have the
   fixture ``latbench_loopback``. If no entry agrees, the run stops
   before it builds. With ``--probe`` and ``--port`` together, ``run.py``
   does not read the map: it uses this probe and this port, and it does
   not examine the fixture.
#. **Sources and build.** :doc:`../../explanation/reproducibility`
   describes these two steps.
#. **Kconfig comparison.** It compares each Kconfig value of the point
   with the ``.config`` of the build. If the ``.config`` does not have the
   requested value, the run stops. Kconfig can ignore a value without an
   error (see :doc:`../../explanation/measurement-effects`).
#. **Flash and capture.** For each :term:`repetition`, it opens the
   serial port and runs the ``flash`` commands of the board in order.
   Then it saves the output until ``LAT DONE``. If no ``LAT DONE`` comes
   before the timeout, or the flash fails, the run stops.
#. **Summary.** It writes ``summary.txt`` with the percentiles of each
   histogram, one column per axis. It prints how many images came from
   the build cache.
#. **Seal and run list.** It writes the :term:`seal`. If ``--out`` is
   the folder of an instance, it adds the run to the run list of the
   instance, with ``--role`` (default ``evidence``) and ``--reason``.
   ``--campaign ID`` names the campaign in the entry. It prints ``run <id>
   added to the instance <folder>``.

``run.py`` writes ``manifest.json`` at the start and updates it after each
repetition. Thus a run that stops still has a manifest for the completed
repetitions. A run that stops before its seal (an error, Ctrl-C or
SIGTERM) writes ``<UTC time>.failed.json`` beside its folder. This file
has the step (for example ``flash and capture ws-up/stock-idle rep
1``), the error and the last 20 lines of the log of that step. Such a run is not in a run
list, so the results build and the export do not see it.

.. _benchguide-rebuild-ref:

``--rebuild``
-------------

``--rebuild`` does these steps:

#. It reads the manifest. It makes sure that the trees are at the
   revisions of the manifest and clean, and that the SDK has the version
   of the manifest. The revisions of the current tree manifests are not
   used, so the comparison also works after a change of these files.
   ``--trees-root`` or ``LATBENCH_TREES_ROOT`` overrides ``trees_root`` of
   the manifest. If that folder does not exist (the trees moved, or a run
   of a different host), ``run.py`` uses the trees root of the lab space.
#. A run from before ``-DWEST_TOPDIR`` took ``WEST_TOPDIR`` from a west
   workspace around its trees root. ``--rebuild`` then gives the build the
   same folder relative to the new root. Thus the ``__FILE__`` strings
   stay the same.
#. If the SDK path of the manifest does not exist (a run of a different
   host), ``run.py`` uses the SDK path of this host (``[toolchain]
   zephyr_sdk`` of the lab space, or its default). Its version must be
   that of the manifest.
#. It runs the CMake command of the manifest again, with the same
   sources. For a run with ``safety.bench_tree``, it exports the commit
   ``safety.rev`` of the safety repository (``git archive``) into a
   temporary folder. It stops if the commit is not in the repository, or
   if the hash of the kind ``bench_tree_kind`` at that commit is not
   ``bench_tree``. To get a missing commit, fetch it, or fetch its ref
   ``safety.ref`` from the lab repository.
#. A run of an older ``run.py`` uses its copy in ``src/``. A run without
   ``src/`` built from the worktree, and its build took the revision
   string from ``git describe``. For such a run, ``--rebuild`` makes a
   temporary git worktree at ``safety.rev``. Thus ``git describe`` gives
   the same string. It stops if the revision is not in the safety
   repository.
#. It builds into a temporary folder ``latbench-rebuild-*``, never into
   the sealed run folder. The ELF then has other debug information, so
   its SHA-256 differs. The flashed image decides (next step).
#. It compares ``zephyr.elf`` (SHA-256), ``zephyr.hex``, ``.config`` and
   ``zephyr.dts`` with the stored files. If the SHA-256 of the ELF is not
   the same, it also compares the loadable sections of the two ELFs
   (``objcopy -O ihex``, without the debug information). It compares
   ``.config`` and ``zephyr.dts`` without their comments, because the
   comments have the paths of the host.

A point is the same if the flashed image and the ``.config`` are the
same. The flashed image is ``zephyr.hex``. If the run has no HEX file, it
is the ELF or its loadable sections.

``--rebuild`` does not flash. At the end, the run folder is as it was
before. With ``--keep-build``, the temporary folder stays. The result
goes to ``<UTC time>.rebuild-<UTC time of the check>.json`` beside the run
folder. ``run.py`` prints one line for each point. It exits with 1 if a
point is not the same. Then the logs and the builds of these points
stay in a temporary folder. The last line gives the folder.
