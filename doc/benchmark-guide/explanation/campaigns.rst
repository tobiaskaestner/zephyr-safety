.. _benchguide-lab:

Lab spaces and campaigns
========================

A lab space holds everything of one host that a study needs and that the
repository must not hold: the pinned trees, the Zephyr SDK, the results
tree, the hardware map, the build cache and the campaign records. A
campaign runs all experiments below a folder of the design, adds each run
to its instance and builds the results after each run.

Campaigns
---------

The experiments of a campaign come in this order:

#. The experiments of the study, in the order of its ``study.yaml``.
#. The ``mode: rerun`` imports of the study.
#. The experiments of each sub-study, depth first.

A sub-study with ``instances: per-board`` is not in the campaign, unless
``FOLDER`` is in it. ``--only`` keeps only the given experiments.
``--skip`` and a board that is not the board of the campaign mark an
experiment as ``skipped``.

``run``
~~~~~~~

``run`` makes the campaign record and runs the campaign:

#. The design repository must be clean. The campaign id is the UTC time
   (``20261026T223523Z``).
#. It takes the lock and sets the ref ``refs/latbench/campaign/<id>`` of
   the design repository to the commit of the campaign.
#. It does the pre-flight check. If an item is ``fail``, nothing runs,
   and the status of the campaign is ``failed``.
#. For each experiment that is not ``done`` or ``skipped``: it makes sure
   that the design repository is clean and at the commit of the
   campaign. It makes the instance if there is none (``instance new`` at
   the level that fixes the board). Then it runs ``run.py <experiment.yaml>
   --out <instance folder> --campaign <id> --role R``.
#. ``run.py`` adds the run to the run list of the instance, with the role
   of the campaign (``--role``, default ``evidence``; ``adjustment`` or
   ``excluded`` need ``--reason``) and the campaign id. The experiment is
   ``done``. The log has one line for it, for example ``done (rc 0) in
   6 min, 5/5 images from the build cache, run irq-smoke/20261027T175848Z``.
#. After each ``done`` experiment, a background process builds the
   results tree (``study.py analysis build`` and ``study.py analysis html``).

Failure rules:

- A failed experiment does not stop the campaign. The next experiment
  starts. The record gives the reason in ``note``: the step and the error
  of ``<UTC>.failed.json`` (see :doc:`../reference/cli/run-py`), or a part of a run
  folder that ``run.py`` left. Such a run is not in the run list.
- A change of the design repository (a new commit, or changes that are
  not committed) stops the campaign before the next experiment.
- ``SIGTERM`` or Ctrl-C stops the campaign. The running experiment is
  ``failed``, and the campaign is ``aborted``.

The background build runs with ``nice 10``, one build at a time. If a run
ends while a build runs, one more build follows. At the end, the campaign
sets its status and asks for one more build: after the build that runs
at that time, if there is one. That last build starts after the end of
the campaign, so it makes the verdicts final. The builds write
``.lab/campaigns/<id>/post.log``. While the campaign runs, the build
marks the verdicts that wait for an experiment of the campaign as
provisional (see :ref:`benchguide-provisional`).

Lock and ref
~~~~~~~~~~~~

A campaign holds one lock for each board of its plan: an ``flock`` on
``.lab/locks/board-<board>.lock``. Two campaigns on different boards run
at the same time; a second campaign on a board that a campaign uses
stops at once and names the holder. A campaign takes all its locks or
none. The kernel releases a lock when the process ends, so a crash or a
kill leaves no stale lock. The file has the campaign id, the process id,
the host and the board of the holder, for information. A campaign of this
lab space counts as running (for provisional verdicts) only while it
holds its locks.

The results build has a lab-wide lock, ``.lab/locks/results.lock``:
``analysis build`` and ``analysis html`` wait for it, so the background
builds of two campaigns (and a build by hand) run one after the other.

The campaign record names the Python and the versions of the packages of
``requirements.txt`` (``python``); the manifest of each run has them too
(``tools.python_packages``).

The ref ``refs/latbench/campaign/<id>`` keeps the commit of the campaign
in the design repository, also after a rebase of the branch. It is a
local ref. Do not push it. ``run.py --rebuild`` needs this commit. Each
run also gets the ref ``refs/latbench/run/<experiment>/<UTC>`` (manifest
``safety.ref``), also without a campaign.
