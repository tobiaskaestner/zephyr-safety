Reproducibility
===============

A data point is reproducible if a second person can make the same image
from the same sources and measure it again. The host tools (see
:doc:`../reference/cli/scripts`) enforce the rules on this page.

Rules
-----

A data point that you publish or compare must come from ``run.py`` with
an :term:`experiment` file in the :term:`safety repository`. These rules apply:

- ``validation/trees/<tree>.yml`` pins each :term:`tree` (a west manifest): the
  Zephyr revision, the revision of each module, and the Zephyr SDK
  version.
- A pinned revision does not change, because old results refer to it. A
  changed revision means a new tree (see :ref:`benchguide-tree-rule`
  and :doc:`decisions/0002-pinned-clean-trees`).
- A Zephyr patch for the :term:`study` goes on a branch in the Zephyr repository.
  The commit of the patch is the revision of the new tree.
- ``run.py`` stops before it builds anything in these conditions:

  - The safety repository is not clean.
  - The :term:`lab space` uses a different :term:`design repository` (see :doc:`../reference/files/lab-config`).
  - A repository of a tree that the build needs is not at its pinned
    revision, or it is not clean.
  - The SDK version is not the pinned version.

- The safety repository stays clean and at the same commit while the run
  builds. ``run.py`` makes sure of this before each point, and stops if
  the repository changed.
- A manual build or capture is for development only. Its results are
  unpinned.

.. _benchguide-tree-rule:

Rules for the trees
-------------------

- A pinned revision never changes. To use another revision of a
  repository, add a new tree with a new name, and keep the old tree.
- You can add a module repository to an existing tree. This does not
  change old builds, because each build uses only the modules of its
  board (``boards.yaml``).
- ``study.py trees setup`` and ``study.py trees check`` accept a new
  project in a tree manifest, but no changed or removed pin.
- If a tree does not pin a module of the board, ``run.py`` stops before it
  builds anything.

:doc:`../howto/add-a-tree` gives the steps.

How ``run.py`` builds a point
-----------------------------

For the sources and the build, ``run.py`` (see :doc:`../reference/cli/run-py`)
does these steps:

#. **Sources.** The build reads the app from the safety repository, not
   from a copy (see :doc:`decisions/0003-build-from-the-repository`). Before each point, ``run.py`` makes sure that the
   repository is clean and at the commit of the start of the run. If not,
   the run stops. Thus a change in the worktree during a run cannot change
   what the run builds. A :term:`campaign` also keeps the commit with a ref (see
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
   ``WEST_CONFIG_SYSTEM`` are ``/dev/null``). If the environment
   variable ``LATBENCH_BUILDER`` is ``cmake``, it runs CMake and Ninja
   instead. This is the builder of the runs before 2026-10-28. It takes
   the Python of ``PATH`` for the Zephyr scripts. The manifest names this
   Python as ``tools.cmake_python``. Both builders give the same image.
   The options are:

   - ``ZEPHYR_BASE`` set to the Zephyr of the tree, and all other
     ``ZEPHYR_*`` environment variables removed.
   - The :term:`board target` (``-b`` of ``west build``, ``-DBOARD`` of CMake).
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
   - ``-DLATBENCH_SRC_REV`` set to the firmware hash (see
     :ref:`benchguide-firmware-hash`) at the commit of the run.
   - ``-DBUILD_VERSION`` set to ``git describe --abbrev=12 --always`` of
     the Zephyr tree, as Zephyr makes it. The string depends on the tags
     of the tree. It is in the CMake command, so a rebuild gives the same
     string.

.. _benchguide-firmware-hash:

The firmware hash
-----------------

The firmware hash is a content hash of the firmware files of
``tests/benchmarks``. The kind ``firmware/1`` counts all files except the
host scripts in ``scripts/``, Python, Markdown, ``testcase.yaml`` and
``boards.yaml``. The manifest records it as ``safety.bench_tree``, with
the kind in ``safety.bench_tree_kind``. The app gets it as
``LATBENCH_SRC_REV``, not the commit. Thus the same firmware gives the
same image at any commit (see :doc:`decisions/0004-firmware-hash`).

.. _benchguide-build-cache:

Build cache
-----------

The :term:`build cache` keeps the images of the points of a lab space
(see :doc:`decisions/0005-build-cache-key`).

The key is the SHA-256 of all inputs of the image:

- the board and the app,
- the pinned revisions of the tree repositories that the board needs,
- the ``BUILD_VERSION`` of the Zephyr tree (``git describe``, which
  depends on the tags of the tree, and ``run.py`` gives it to CMake),
- the builder (``west <version>``, or ``cmake`` with
  ``LATBENCH_BUILDER=cmake``): a new west version gives new keys,
- the SDK version,
- the firmware hash, and the git tree hash of the module folder
  ``zephyr/`` of the safety repository,
- the point: its Kconfig values, conf files and overlays.

The key has no host path, no experiment name and no safety commit. Thus
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
