Add a tree or a module
======================

A pinned revision never changes (see :ref:`benchguide-tree-rule`).
:doc:`../reference/files/trees-yaml` gives the keys of a tree manifest.

To use another revision of a repository, add a new tree:

#. Make sure that a local clone has the revision of each repository, or
   that the ``url`` has it.
#. Copy a file of ``validation/trees/`` to ``validation/trees/<tree>.yml``,
   and set the description and the revisions. Do not change the
   revisions of an existing tree.
#. Run ``study.py design lint``: it checks the file with the parser of
   west.
#. Commit the new file.
#. Set up the tree in your lab space (see :ref:`benchguide-lab-trees`):

   .. code-block:: console

      scripts/probatrix/study.py trees setup <tree>

To add a module repository that a new board needs to an existing tree:

#. Add the project to ``projects`` of ``validation/trees/<tree>.yml``,
   with its pinned revision. Do not change the other projects.
#. Commit the file.
#. Run ``study.py trees setup <tree>``. It clones only the missing
   repositories.
