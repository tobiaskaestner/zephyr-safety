0008. Results during a campaign and provisional verdicts
========================================================

Status
------

Accepted, 2026-10-27.

Problem
-------

A :term:`campaign` can run for many hours. The host has nothing to do while the
board measures, and the first results are useful long before the end.
But a :term:`verdict` that reads an :term:`experiment` that the campaign has still to run
can change.

Decision
--------

- After each run, a background process (low priority, one at a time)
  builds the results tree, the plots and the pages.
- A check or a :term:`central result` that reads an experiment that a running
  campaign has still to run is :term:`provisional`. ``study.json`` says so
  in the entry and in ``state``.
- After the end of a campaign (also an abort), one more build makes the
  verdicts final.

Results
-------

- The plots of an experiment are there a few seconds after its run.
- ``analysis check`` during a campaign can differ from the last build. It
  says so.
