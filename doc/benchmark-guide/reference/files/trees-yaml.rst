Pinned trees (``validation/trees/``)
====================================

Each tree is one west manifest, ``validation/trees/<tree>.yml``. The file
has only the pins. The paths of a host are in the ``.lab/config`` of its
lab space (see :doc:`lab-config`):

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
   :doc:`../../explanation/mask-time`), on a local branch (``tkaestner/latency-irqoff-hook``). The
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
