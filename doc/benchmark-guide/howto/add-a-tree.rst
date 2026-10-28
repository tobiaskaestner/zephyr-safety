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
