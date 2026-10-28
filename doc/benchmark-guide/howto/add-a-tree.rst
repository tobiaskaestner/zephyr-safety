Add a tree or a module
======================

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
#. Create the tree in your lab space (see :doc:`../reference/cli/study-py`):

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

.. _benchguide-tree-rule:

Change the trees
----------------

- A pinned revision never changes. To use another revision of a
  repository, add a new tree with a new name, and keep the old tree.
- You can add a module repository to an existing tree. This does not
  change old builds, because each build uses only the modules of its
  board (``boards.yaml``).
- If a tree does not pin a module of the board, ``run.py`` stops before it
  builds anything.
