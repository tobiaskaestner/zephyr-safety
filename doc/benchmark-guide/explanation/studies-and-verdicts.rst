.. _benchguide-studies:

Studies and their results
=========================

A :term:`study` asks one verification question. It names the
:term:`experiments <experiment>` that answer it, the :term:`hypotheses
<hypothesis>` that were written before the runs, and the :term:`central
results <central result>` that state the answer. The reference describes the files of
a study design (:doc:`../reference/files/study-yaml`), the results tree
(:doc:`../reference/files/results-tree`), the tool ``scripts/probatrix/study.py``
(:doc:`../reference/cli/study-py`) and the forms that a :term:`check` can use
(:doc:`../reference/check-forms`).

Hypotheses before the runs
--------------------------

A hypothesis is a claim about a mechanism, with a limit for each check.
The person who writes it writes it before the :term:`run` of its experiment
(``written`` of each check). Thus the data can make the hypothesis
wrong. A hypothesis that the data cannot make wrong gives no
information.

A wrong hypothesis is a result, not a failure of the tools. The claim
was written before the data, and the data decided. The next step of such
a study is a new hypothesis about the cause, with a new check.

.. _benchguide-provisional:

Provisional verdicts
--------------------

In a :term:`lab space`, a :term:`campaign` runs the experiments one after the other, and
the build of the results tree runs after each run (see :doc:`campaigns`).
Thus a build can come before the last run of an experiment. A :term:`verdict` of
such a build is :term:`provisional` (see
:doc:`decisions/0008-results-during-campaigns`).

A check of a hypothesis or a central result is provisional if it reads
an experiment that a running campaign of the lab space has still to run.
This includes an experiment that the study imports with ``mode: reuse``.
``study.json`` then has these entries:

- The key ``provisional`` on the check and on the central result, with
  the reason (``waits for <experiment> of the campaign <id>``).
- ``"provisional": true`` on a hypothesis with a provisional check.
- ``state``: ``{final, waits}``. ``final`` is ``false`` if a result of the
  :term:`instance` is provisional. ``waits`` lists the reasons.

A campaign of this lab space counts while two conditions are true:

- Its record has the status ``planned`` (its :term:`pre-flight check`) or
  ``running``.
- It holds the locks of its boards.

Thus a campaign whose process stopped does not count. An imported
campaign record of another lab space counts while it has the status
``running``. After ``lab import --close``, it does not count.

``study.py analysis show``, ``study.py analysis html`` and
``scripts/probatrix/benchmarks/data.py`` mark the provisional verdicts.
