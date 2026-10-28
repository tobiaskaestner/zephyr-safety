.. _benchguide-rebuild:

Reproduce a data point
======================

A data point has two parts that you can reproduce: the image, and the
measurement. :ref:`benchguide-rebuild-ref` tells what ``--rebuild`` does.
:doc:`../explanation/reproducibility` and
:doc:`../explanation/decisions/0003-build-from-the-repository` tell why
the same sources give the same image.

The image
---------

#. Make sure that the design repository has the commit of the run. The
   manifest gives it as ``safety.rev``. The ref ``safety.ref``
   (``refs/latbench/run/<experiment>/<UTC>``) keeps it in the design
   repository of the lab space that made the run. An import adds the
   commits of the runs as ``refs/latbench/import/<lab id>/<commit>``.
#. Set up the trees of the run. The manifest names them in ``trees``:

   .. code-block:: console

      safety/scripts/benchmarks/study.py trees setup <tree> ...

#. Build all points of the run again, or one point:

   .. code-block:: console

      safety/scripts/benchmarks/run.py --rebuild <run>
      safety/scripts/benchmarks/run.py --rebuild <run>/<tree>/<point>

#. Read the last lines. ``run.py`` prints one line for each point and
   exits with 1 if a point is not the same. The record
   ``<UTC>.rebuild-<UTC>.json`` goes beside the run folder.

The measurement
---------------

#. Check out the commit ``safety.rev`` of the manifest in the design
   repository, or the ref ``safety.ref``:

   .. code-block:: console

      git -C safety switch --detach <safety.rev>

#. Set up the trees of the run:

   .. code-block:: console

      safety/scripts/benchmarks/study.py trees setup <tree> ...

#. Run the experiment again:

   .. code-block:: console

      safety/scripts/benchmarks/run.py safety/validation/empirical/latencies/st-<study>/ex-<name>/experiment.yaml --out <dir>

#. Compare the summaries of the old and the new logs with
   ``latbench.py summary`` (see :doc:`../reference/cli/scripts`).
