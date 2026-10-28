0007. The checks of an import
=============================

Status
------

Accepted, 2026-10-27; the parsed compare and the bundle on 2026-10-28.

Problem
-------

One host seldom has all boards of a study, so lab spaces give each other
their runs. A run can join a study only if both lab spaces mean the same
experiment, and the importing host must be able to build the run again.

Decision
--------

- An export is one tar file with a digest file: the sealed runs, the
  campaign records, the design files, the references and the manual
  verdicts of the instances, and a git bundle of the commits of the runs.
- The import refuses a run of an experiment whose content differs between
  the two lab spaces. The content is the parsed YAML without comments,
  ``name`` and ``renamed_from``, so a comment or a rename is no
  difference.
- A different ``study.yaml`` or ``hypotheses.yaml`` gives a warning only:
  the importing lab space builds the verdicts with its own design.
- A run id that is there with another digest is refused.

Results
-------

- Two lab spaces at different commits can share runs, as long as the
  experiments are the same.
- The importing host has the commits of the runs
  (``refs/latbench/import/<lab>/``), so ``run.py --rebuild`` works there.
