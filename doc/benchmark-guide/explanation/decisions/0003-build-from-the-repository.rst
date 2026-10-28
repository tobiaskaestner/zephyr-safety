0003. Build from the repository, not from a copy
================================================

Status
------

Accepted, 2026-10-27. It replaces the copy of the repository in each run
(``<run>/src/``, 2026-10-26).

Problem
-------

A run had a copy of the whole :term:`safety repository` in ``src/``, and its
builds used the copy. The copy made each run large and had many files that
the :term:`experiment` does not use, which was confusing.

Decision
--------

- A run builds from the clone of the :term:`lab space`. Before each point and
  after each build, ``run.py`` makes sure that the clone is clean and at
  the commit of the start of the run.
- The commit stays reachable with a local ref,
  ``refs/latbench/run/<experiment>/<UTC>`` (and
  ``refs/latbench/campaign/<id>``). The refs are never pushed.
- ``run.py --rebuild`` exports that commit into a temporary folder and
  builds there. It never builds in the sealed run folder.

Results
-------

- A run is about 4 MB instead of a copy of the repository.
- A rebuild on another host needs the commit there: an export carries it
  in a git bundle (:doc:`0007-import-checks`).
