Add a study
===========

A :term:`study` asks one verification question. :doc:`../tutorials/your-own-study`
does these steps with real output. The commands run in the lab folder.

#. Make a local branch in the :term:`design repository`. The study goes
   on this branch:

   .. code-block:: console

      git -C safety switch -c <branch>

#. Make the study from the templates (see :ref:`benchguide-scaffold`).
   ``PARENT`` is the folder of the parent study:

   .. code-block:: console

      safety/scripts/probatrix/benchmarks/study.py design scaffold study <PARENT>/st-<name>

#. Make each experiment of the study:

   .. code-block:: console

      safety/scripts/probatrix/benchmarks/study.py design scaffold experiment <PARENT>/st-<name>/ex-<experiment> --app <app>

#. Write each ``experiment.yaml``: the axes, the points and the
   acceptance checks (see :doc:`../reference/files/experiment-yaml` and
   :doc:`add-an-experiment`).
#. Write ``study.yaml``, ``study.md`` and each ``experiment.md`` (see
   :doc:`../reference/files/study-yaml`). Replace each ``TODO`` text.
#. Write the hypotheses and their checks in ``hypotheses.yaml``, before
   the runs. Set ``written`` of each check (see
   :doc:`../reference/check-forms`).
#. Write the central results in ``study.yaml`` (see
   :doc:`write-a-central-result`).
#. Run the design lint, and correct each error and each warning (see
   :doc:`../reference/lint-rules`):

   .. code-block:: console

      safety/scripts/probatrix/benchmarks/study.py design lint safety/validation/empirical/latencies

#. Commit the files on the branch. ``run.py`` refuses a design repository
   that is not clean.
#. Do the :term:`pre-flight check` of the campaign:

   .. code-block:: console

      safety/scripts/probatrix/benchmarks/study.py campaign check <PARENT>/st-<name>

#. Run the campaign:

   .. code-block:: console

      safety/scripts/probatrix/benchmarks/study.py campaign run <PARENT>/st-<name> --detach

#. When the campaign is done, read the verdicts and the central results:

   .. code-block:: console

      safety/scripts/probatrix/benchmarks/study.py analysis show results/kernel-latency/<instance> --details
      safety/scripts/probatrix/benchmarks/study.py analysis show results/kernel-latency/<instance> --explain

:doc:`../reference/cli/study-py` gives the options of each command.
