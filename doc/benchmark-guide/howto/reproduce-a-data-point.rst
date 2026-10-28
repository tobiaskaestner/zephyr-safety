.. _benchguide-rebuild:

Reproduce a point
=================

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

``--rebuild`` does not flash, and it never builds in the run folder: at
the end, the run folder is as it was before. The builds go to a temporary
folder ``latbench-rebuild-*`` (with ``--keep-build``, it stays). The
result goes to ``<UTC time>.rebuild-<UTC time of the check>.json`` beside
the run folder. It prints one line for each point and exits with 1 if a
point is not the same. Then
the logs and the builds of the points that are not the same stay in a
temporary folder, and the last line gives the folder.

To reproduce the measurement, run the experiment again, from the safety
repository at ``safety.rev`` of the manifest:

.. code-block:: console

   scripts/benchmarks/study.py trees setup
   scripts/benchmarks/run.py validation/empirical/latencies/st-<study>/ex-<name>/experiment.yaml --out <dir>

Then compare the summaries of the old and the new logs (see
:doc:`../reference/cli/scripts`).
