Host tools and reproducibility
==============================

The folder ``scripts/benchmarks/`` has the host tools. They need Python
3 and the packages in ``scripts/benchmarks/requirements.txt`` (the
ranges: ``pyserial``, ``PyYAML``, ``matplotlib``, ``jsonschema``,
``packaging`` and ``west``). A lab space installs the exact versions of
``scripts/benchmarks/requirements.lock``, which also has the Python
packages of the Zephyr build (``pyelftools`` and others) and ``pyocd``.

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Script
     - Purpose
   * - ``study.py``
     - Study designs (lint, scaffold), lab spaces, pinned trees
       (``study.py trees``), campaigns, and the aggregates of a results
       tree (see :doc:`../reference/cli/study-py` and :doc:`campaigns`).
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
  - The lab space uses a different design repository (see :doc:`../reference/files/lab-config`).
  - A repository of a tree that the build needs is not at its pinned
    revision, or it is not clean.
  - The SDK version is not the pinned version.

- The safety repository stays clean and at the same commit while the run
  builds. ``run.py`` makes sure of this before each point, and stops if
  the repository changed.
- A manual build or capture is for development only. Its results are
  unpinned.

How ``run.py`` builds a point
-----------------------------

For the sources and the build, ``run.py`` (see :doc:`../reference/cli/run-py`)
does these steps:

#. **Sources.** The build reads the app from the safety repository, not
   from a copy. Before each point, ``run.py`` makes sure that the
   repository is clean and at the commit of the start of the run. If not,
   the run stops. Thus a change in the worktree during a run cannot change
   what the run builds. A campaign also keeps the commit with a ref (see
   :doc:`campaigns`). Runs of an older ``run.py`` have a copy of the repository
   in ``<run>/src/``.
#. **Build.** For each tree and each point, it takes the image from the
   build cache of the lab space if the cache has it (see
   :ref:`benchguide-build-cache`). Else it runs ``west build
   --no-sysbuild -d <build folder> -b <board> <app> -- <CMake options>``
   in the west workspace of the tree, after it makes sure that ``west
   topdir`` gives that folder and that the ``.west/config`` of the tree
   has only the keys of ``west init``. The user and system west
   configuration do not count (``WEST_CONFIG_GLOBAL`` and
   ``WEST_CONFIG_SYSTEM`` are ``/dev/null``). With the environment
   variable ``LATBENCH_BUILDER=cmake``, it runs CMake and Ninja instead
   (the builder of the runs before 2026-10-28; it takes the Python of
   ``PATH`` for the Zephyr scripts, and the manifest names it as
   ``tools.cmake_python``). Both give the same image. The options are:

   - ``ZEPHYR_BASE`` set to the Zephyr of the tree, and all other
     ``ZEPHYR_*`` environment variables removed.
   - The board target (``-b`` of ``west build``, ``-DBOARD`` of CMake).
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

.. _benchguide-build-cache:

Build cache
-----------

The key is the SHA-256 of all inputs of the image:

- the board and the app,
- the pinned revisions of the tree repositories that the board needs,
- the ``BUILD_VERSION`` of the Zephyr tree (``git describe``, which
  depends on the tags of the tree; ``run.py`` gives it to CMake),
- the builder (``west <version>``, or ``cmake`` with
  ``LATBENCH_BUILDER=cmake``): a new west version gives new keys,
- the SDK version,
- a content hash of the firmware files of ``tests/benchmarks`` (kind
  ``firmware/1``: all files without the host scripts in ``scripts/``,
  Python, Markdown, ``testcase.yaml`` and ``boards.yaml``), and the git
  tree hash of the module folder ``zephyr/`` of the safety repository,
- the point: its Kconfig values, conf files and overlays.

The key has no host path, no experiment name and no safety commit. The
app gets the firmware hash as ``LATBENCH_SRC_REV``, not the commit. Thus
these runs get the image from the cache:

- A repeat of an experiment.
- A run after a commit that changes only the design files (for example
  ``study.yaml``), the tools or an extractor, because the hashes stay the
  same.
- A point of another experiment with the same settings.

An entry counts only if its ELF has the SHA-256 of ``entry.json``. The
manifest of the run records ``build: {key, from, built_by}`` for each
point, and the log of the run has one line for each image from the cache,
for example ``[ws-safety/stock-idle] image from the build cache
(c5c5146c5eef, built by irq-smoke/20261027T172644Z)``. Each
build has a folder of its own process, and an entry that another process
stored first stays. Before an image goes into the run or the cache,
``run.py`` checks again that the repository did not change during the
build.
``run.py --build-only`` and ``study.py campaign prepare`` fill the cache.
``run.py --no-cache`` builds again and does not use the cache.
