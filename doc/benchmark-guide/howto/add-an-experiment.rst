Add an experiment
=================

:doc:`../reference/files/experiment-yaml` gives the keys of
``experiment.yaml`` and the sections of ``experiment.md``.

#. Find the study in ``validation/empirical/latencies/`` that asks your
   question. A study is a folder ``st-<name>/``.
#. Select a name for the experiment. The name must be unique in all
   studies. It has only lower case letters, digits and ``-``.
#. Make the files from the templates (see :ref:`benchguide-scaffold`):

   .. code-block:: console

      scripts/probatrix/benchmarks/study.py design scaffold experiment <study folder>/ex-<name> --app <app>

   The command also adds the name to ``experiments`` of ``study.yaml``,
   and a line to the section Experiments of ``study.md``.
#. As an alternative to step 3, copy an experiment folder of the study
   that is near to your question. Give the copy the folder name
   ``ex-<name>``. Set ``name`` in ``experiment.yaml`` to the name without
   ``ex-``. Add the name to ``experiments`` in ``study.yaml``.
#. Write ``experiment.md``: what it measures, the method, and what each
   axis varies.
#. Write the predictions in the ``hypotheses.yaml`` of the study, before
   the runs.
#. Set ``app``, ``trees``, ``repeat`` and ``timeout``. A point with 1
   million samples needs a timeout of approximately 900 s to 1200 s.
#. If the experiment is not for the default board, set ``board`` to a
   board target of ``boards.yaml``.
#. Put the settings that all points share into ``common``.
#. Put the factors into ``axes``. Put single extra points into ``points``.
#. Do not list the overlays of the board port. The port adds them. If a
   point needs another overlay (for example a clock overlay), add it to
   ``dtc_overlays``.
#. Use text for the value names of an axis, not ``on``, ``off``, ``yes``
   or ``no``.
#. Run the design lint, and correct each error:

   .. code-block:: console

      scripts/probatrix/benchmarks/study.py design lint validation/empirical/latencies/st-<study>

#. Commit the files. ``run.py`` refuses a safety repository that is not
   clean.
#. Make sure that the points are correct:

   .. code-block:: console

      scripts/probatrix/benchmarks/run.py validation/empirical/latencies/st-<study>/ex-<name>/experiment.yaml --dry-run

#. Make sure that all points build. This step also does the Kconfig
   comparison of each point:

   .. code-block:: console

      scripts/probatrix/benchmarks/run.py validation/empirical/latencies/st-<study>/ex-<name>/experiment.yaml --build-only

#. In a lab space, run the experiment with a campaign (see
   :doc:`../reference/cli/study-py`). The campaign adds the run to the
   run list of its instance:

   .. code-block:: console

      scripts/probatrix/benchmarks/study.py campaign run <experiment folder>

#. Without a campaign, see :doc:`run-without-a-campaign`.

Each value in ``kconfig`` of a point must be an option of the app or of
the tree. If the tree does not define the option, the build stops. Thus
an experiment can use an option that only one tree has (for example a
timeout backend) only with that tree. If Kconfig ignores a value (unmet
dependencies, or a second member of a choice), the Kconfig comparison
stops the run (see :doc:`../explanation/measurement-effects`).
