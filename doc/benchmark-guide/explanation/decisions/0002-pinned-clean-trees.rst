0002. Pinned trees and clean repositories
=========================================

Status
------

Accepted, 2026-10-24. The format of the pins changed with
:doc:`0006-lab-space` (west manifests).

Problem
-------

A latency value depends on the exact code of Zephyr, of its modules and of
the apps. A value from a tree with changes that nobody committed cannot be
made again, and a value of an unknown revision cannot be compared.

Decision
--------

- Each tree is pinned: one revision for each repository, in
  ``validation/trees/<tree>.yml``. A pin never changes; another revision
  is another tree.
- ``run.py`` refuses a tree that is not at its pins or not clean, a
  design repository that is not clean, and an SDK of another version.
- A Zephyr patch for a study goes on a branch, and its commit is the pin
  of a new tree.

Results
-------

- Each data point names its trees, its SDK and its design commit
  (``manifest.json``).
- A manual build is for development only; its values are not data points.
