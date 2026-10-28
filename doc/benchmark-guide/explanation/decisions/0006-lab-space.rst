0006. A lab space; trees as west workspaces
===========================================

Status
------

Accepted, 2026-10-27 (lab space); 2026-10-28 (west workspaces, Python
environment).

Problem
-------

The tools need things of a host that the repository must not hold: the
paths of the trees and of the SDK, the hardware map, the Python packages,
the results, the build cache. The first version took the paths from
environment variables and from host paths in the pins file, and it cloned
the trees with its own code.

Decision
--------

- A lab space is a folder with ``.lab/config``, as a west workspace has
  ``.west/config``. It names the design repository (a clone in the
  folder), the trees root, the SDK, the results and the hardware map, and
  the Python environment of the lab space. Each ``study.py`` in the folder
  runs the tools of that clone with that Python.
- Each tree is a west manifest, and ``trees setup`` makes a west
  workspace for each tree, side by side. The build is ``west build`` in
  that workspace. The tools run west without the ``ZEPHYR_*`` variables of
  the caller and without the user and system west configuration, and only
  after ``west topdir`` gives the expected folder.

Results
-------

- The suite uses west for what west does, and keeps its own checks for
  the reproducibility rules (:doc:`0002-pinned-clean-trees`).
- A host can have several lab spaces; each one is complete in itself.
