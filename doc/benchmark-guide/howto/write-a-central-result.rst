Write a central result
======================

:doc:`../reference/central-results` gives the fields of a
:term:`central result`, the stats, the rows and examples.

#. Add an entry to ``central_results`` of the ``study.yaml`` of the study
   (see :doc:`../reference/files/study-yaml`). Give ``id``,
   ``statement``, ``from``, ``stat`` and ``unit``. For an aggregate stat,
   also give ``group_by``.
#. In ``statement``, write a placeholder for each value, for example
   ``{p99:.0f}``. For an aggregate stat, name only the axes of
   ``group_by``.
#. Run the design lint, and correct each error:

   .. code-block:: console

      safety/scripts/benchmarks/study.py design lint safety/validation/empirical/latencies/st-<study>

#. Commit the change on your branch.
#. Build the results tree:

   .. code-block:: console

      safety/scripts/benchmarks/study.py analysis build results/kernel-latency

#. Show the rows and the sentences of the result:

   .. code-block:: console

      safety/scripts/benchmarks/study.py analysis show results/kernel-latency --explain <id>

   :ref:`benchguide-explain-form` gives the form of the output.
#. If the output has the line ``unfilled placeholders``, a placeholder
   names a value that the rows do not have. Compare the names of the
   placeholders with the names in the ``row:`` lines. Correct the
   statement, and do the steps 3 to 6 again.
#. If the output has ``not evaluated``, read the reason. The reason ``no
   evidence run`` means that the instance has no run of the experiment
   yet. ``study.py analysis missing`` lists these experiments.
#. For ``stat: conclusion``, a person gives the verdict:

   .. code-block:: console

      safety/scripts/benchmarks/study.py instance verdict <instance folder> --central-result <id> \
          --verdict confirmed --by "<name>"
