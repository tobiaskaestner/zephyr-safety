0005. A build cache key without host paths
==========================================

Status
------

Accepted, 2026-10-27. The builder joined the key on 2026-10-28.

Problem
-------

A :term:`campaign` builds many points, and many points are the same in several
:term:`experiments <Experiment>` and in each :term:`repetition` of an experiment. A build takes about
20 s. A key must find the same image again, and must never find a wrong
one.

Decision
--------

The key is the SHA-256 of all inputs of the image:

- The board and the app.
- The pins of the repositories of the board.
- The ``BUILD_VERSION`` of the Zephyr :term:`tree`.
- The builder and its version.
- The SDK version.
- The firmware hash (:doc:`0004-firmware-hash`).
- The git tree hash of the module folder.
- The settings of the point.

The key has no host path, no experiment name and no commit.

Results
-------

- The basis: the rebuilds on other hosts and in other folders gave the
  same images, and ``west build`` and CMake gave the same images.
- A change of a design file or of a host script does not empty the cache.
- The cache keeps who built an entry and which runs took it
  (``uses.jsonl``).
