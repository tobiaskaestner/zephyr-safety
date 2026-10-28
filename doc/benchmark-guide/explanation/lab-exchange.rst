.. _benchguide-lab-exchange:

Export and import
=================

One host has only some boards of a :term:`study`, and a second host makes a
study faster. Thus two :term:`lab spaces <lab space>` give each other
their :term:`runs <Run>` with an export file. :doc:`../reference/files/export` gives
the content of the file and the checks of an import.
:doc:`../howto/combine-lab-spaces` gives the steps, and
:doc:`decisions/0007-import-checks` gives the decision.

The same experiment
-------------------

A run can join a study in another lab space only if both lab spaces mean
the same :term:`experiment`. Thus the import compares the content of
``experiment.yaml`` in the two lab spaces, and refuses the run if the
content differs. A comment or a rename does not change the measurement,
so the comparison ignores them.

``study.yaml`` and ``hypotheses.yaml`` do not change a run. They change
only the :term:`verdicts <Verdict>`. A difference in these files gives a warning only: the
importing lab space builds the verdicts from its own design files. Thus
two lab spaces can give different verdicts from the same runs, and the
warning tells you so.

The :term:`seal` of each run must give the digest of its run-list entry. Thus a
run that changed on the way is refused.

Provisional verdicts over two lab spaces
----------------------------------------

The import copies the :term:`campaign` records of the runs. A campaign of
the other lab space can still run at the time of the export. Such a
campaign makes the verdicts here :term:`provisional`, as a campaign of
this lab space does (see :ref:`benchguide-provisional`). A later import with the end of the
campaign replaces the record. If the other lab space exports no more,
``lab import --close`` ends the record here.

A rebuild in the importing lab space
------------------------------------

The export has a git bundle of the commits of the runs. The import puts
these commits into the :term:`design repository` as local refs. Thus ``run.py
--rebuild`` of an imported run works in the importing lab space.
