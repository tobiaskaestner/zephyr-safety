Add an experiment
=================

#. Find the study in ``validation/empirical/latencies/`` that asks your
   question. A study is a folder ``st-<name>/``, an experiment is a folder
   ``ex-<name>/``. Copy an experiment folder of that study that is near
   to your question, and give the copy the folder name ``ex-<name>``. The
   name must be unique in all studies. Alternatively, make the files from
   templates with ``study.py design scaffold experiment <study
   folder>/ex-<name> --app <app>`` (see :ref:`benchguide-scaffold`). It
   also does the next step.
#. In ``experiment.yaml``, set ``name`` to the name without ``ex-``. Add
   the name to ``experiments`` in the ``study.yaml`` of the study.
#. Write the description ``experiment.md``: the question, the method
   (each point and why), and the references. Write the predictions in the
   ``hypotheses.yaml`` of the study.
#. Set ``app``, ``trees``, ``repeat`` and ``timeout``. If the experiment is
   not for the default board, set ``board`` to a board target of
   ``boards.yaml``. A point with 1 million
   samples needs a timeout of approximately 900 s to 1200 s.
#. Put the settings that all points share into ``common``.
#. Put the factors into ``axes``. Put single extra points into ``points``.
#. Do not list the overlays of the board port. The port adds them. If a
   point needs another overlay (for example a clock overlay), add it to
   ``dtc_overlays``.
#. Use text for the value names of an axis, not ``on``, ``off``, ``yes`` or
   ``no``.
#. Run the design lint, and correct each error:

   .. code-block:: console

      scripts/benchmarks/study.py design lint validation/empirical/latencies/st-<study>

#. Commit the file. ``run.py`` refuses a safety repository that is not
   clean.
#. Make sure that the points are correct:

   .. code-block:: console

      scripts/benchmarks/run.py validation/empirical/latencies/st-<study>/ex-<name>/experiment.yaml --out <dir> --dry-run

#. Make sure that all points build. This step also does the Kconfig
   check of each point:

   .. code-block:: console

      scripts/benchmarks/run.py validation/empirical/latencies/st-<study>/ex-<name>/experiment.yaml --out <dir> --build-only

#. Connect the board and run the experiment without ``--build-only``. In
   a lab space, run it with a campaign: ``study.py campaign run
   <experiment folder>`` (see :doc:`../reference/cli/study-py`). The campaign adds the run to
   the run list of its instance. Without a campaign, use ``--out
   <instance folder>``: ``run.py`` then adds the run to the run list of
   the instance itself (see :doc:`../reference/cli/study-py`).

Each value in ``kconfig`` of a point must be an option of the app or of
the tree. If the tree does not define the option, the build stops. Thus
an experiment can use an option that only one tree has (for example a
timeout backend) only with that tree. If Kconfig ignores a value (unmet
dependencies, or a second member of a choice), the Kconfig check stops
the run (see :doc:`../explanation/measurement-effects`).
