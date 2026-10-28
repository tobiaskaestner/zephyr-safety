Pinned trees (``validation/trees/``)
====================================

Each :term:`tree` is one west manifest, ``validation/trees/<tree>.yml``.
The file has only the pins. The paths of a host are in the ``.lab/config`` of its
:term:`lab space` (see :doc:`lab-config`):

- The trees root is ``[trees] root``. ``--trees-root`` or the environment
  variable ``LATBENCH_TREES_ROOT`` overrides it.
- The SDK path is ``[toolchain] zephyr_sdk``. The default is
  ``~/zephyr-sdk-<version>``.
- A folder of local clones to clone from is ``[trees] source``, with the
  layout ``<source>/<tree>/<path>``. Two trees can use the same clone
  (a link ``<source>/<tree2>`` to ``<source>/<tree1>``), if it has the
  commits of both.

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
   The Zephyr of the safety workspace. No experiment uses this tree now.

``ws-up``
   An upstream Zephyr ``main`` (v4.5.0-rc3-40). The study measures this
   Zephyr version.

``ws-up-irqoff``
   The Zephyr of ``ws-up`` plus the interrupt mask hooks of M4 (see
   :doc:`../../explanation/mask-time`), on a local branch
   (``tkaestner/latency-irqoff-hook-up``). The branch is not pushed, so
   ``study.py trees setup`` needs a local clone for this tree
   (``[trees] source``).

``ws-up-driftfix``
   The Zephyr of ``ws-up`` plus a SysTick :term:`experiment`, on a local
   branch (``tkaestner/latency-systick-drift-up``). The branch is not
   pushed, so ``study.py trees setup`` needs a local clone for this tree.

Each tree has the repositories ``zephyr``, ``cmsis_6``, ``hal_stm32``,
``hal_nordic`` and ``hal_nxp``. The boards and the modules that each board
needs are in ``boards.yaml``.

``study.py trees setup``, ``check`` and ``show`` make and examine the
trees of a lab space (see :ref:`benchguide-lab-trees`). The rules for a
change of a tree are in :ref:`benchguide-tree-rule`.

Do not change files in a tree. A tree with changes is not clean, and
``run.py`` refuses it.
