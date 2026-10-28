Add runs to a study without a campaign
======================================

In a :term:`lab space`, a :term:`campaign` makes the instances and adds
each run. Without a campaign, use these steps.
:doc:`../reference/cli/study-py` gives the options of the ``instance``
commands, and :doc:`../reference/cli/run-py` the options of ``run.py``.

#. Make the instance folders of the study for the board. Do this once:

   .. code-block:: console

      scripts/benchmarks/study.py instance new <results> <study> --board <board>

#. Run the experiment with ``--out <instance folder>``. ``run.py`` puts
   the run into the instance folder and adds it to the run list:

   .. code-block:: console

      scripts/benchmarks/run.py <experiment.yaml> --out <instance folder> [--role R --reason TEXT]

#. If you have an old run from another place, copy it into the instance.
   The original stays:

   .. code-block:: console

      scripts/benchmarks/study.py instance add <instance folder> <old run folder> --copy

#. Build the results:

   .. code-block:: console

      scripts/benchmarks/study.py analysis build <results>/kernel-latency

#. If a check is manual, give its verdict. ``--by`` names the person, or
   a proposal that says so:

   .. code-block:: console

      scripts/benchmarks/study.py instance verdict <instance folder> --hypothesis H3 --check a \
          --verdict wrong --by "<name>" --text "<why>"
