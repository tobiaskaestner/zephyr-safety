.. _benchguide-studies:

Studies and their results
=========================

A study asks one verification question. It names the experiments that
answer it, the hypotheses that were written before the runs, and the
central results that state the answer. The reference describes the files of
a study design (:doc:`../reference/files/study-yaml`), the results tree
(:doc:`../reference/files/results-tree`), the tool ``scripts/benchmarks/study.py``
(:doc:`../reference/cli/study-py`) and the forms that a check can use
(:doc:`../reference/check-forms`).

.. _benchguide-provisional:

Provisional verdicts
--------------------

In a lab space, a campaign runs the experiments one after the other, and
the build of the results tree runs after each run (see :doc:`campaigns`).
Thus a build can come before the last run of an experiment. A verdict of
such a build is provisional.

A check of a hypothesis or a central result is provisional if it reads
an experiment that a running campaign of the lab space has still to run.
This includes an experiment that the study imports with ``mode: reuse``.
``study.json`` then has these entries:

- The key ``provisional`` on the check and on the central result, with
  the reason (``waits for <experiment> of the campaign <id>``).
- ``"provisional": true`` on a hypothesis with a provisional check.
- ``state``: ``{final, waits}``. ``final`` is ``false`` if a result of the
  instance is provisional. ``waits`` lists the reasons.

A campaign of this lab space counts while its record has the status
``planned`` (its pre-flight check) or ``running`` and it holds the locks of
its boards; a campaign whose process stopped does not count. An imported
campaign record of another lab space counts while it has the status
``running`` (not after ``lab import --close``). ``study.py analysis show``, ``study.py analysis html`` and
``scripts/benchmarks/data.py`` mark the provisional verdicts.

Known gaps
----------

A test for a known defect asserts the correct behavior. While the defect
is in the code, the test is an expected failure:

- In the ztest app, ``KNOWN_GAP()`` skips the test and prints
  ``KNOWN GAP:`` with the input and the result. If the result becomes
  correct, the test fails. Then remove ``KNOWN_GAP()`` from the test.
- In pytest, the test has ``xfail(strict=True)``. If the test passes,
  pytest reports a failure. Then remove the marker.

``unit/README.md`` lists the open gaps. Two gaps are open today:

- ``lat_phase_add()`` does not make sure that the phase is less than the
  period. A larger phase writes after the last bin.
- In ``lat_hist_print()``, ``sum * 100`` wraps at 2\ :sup:`64`. This occurs
  only if the sum is more than 1.8e17 cycles.
