Architecture
============

The suite has four parts: the design repository, the lab space of a host,
the board, and the results tree. The tools run in the lab space; the
design repository is a clone in it.

.. graphviz::
   :caption: The parts of the suite and the flow of the data. A box is a
             folder or a device; an arrow is a command or a data flow.

   digraph latbench {
     rankdir=LR;
     node [shape=box, style=rounded, fontname="sans-serif", fontsize=10];
     edge [fontname="sans-serif", fontsize=9];

     subgraph cluster_repo {
       label="design repository (safety, a clone in the lab space)";
       fontname="sans-serif"; fontsize=10; style=dashed;
       design [label="study designs\nvalidation/empirical/latencies/"];
       pins [label="tree pins\nvalidation/trees/<tree>.yml"];
       apps [label="apps, ports, extractors,\nplot scripts\ntests/benchmarks/"];
       tools [label="tools\nscripts/benchmarks/\n(study.py, run.py)"];
     }

     subgraph cluster_lab {
       label="lab space (.lab/config)";
       fontname="sans-serif"; fontsize=10; style=dashed;
       venv [label="Python environment\n.venv"];
       trees [label="west workspaces\ntrees/<tree>/"];
       cache [label="build cache\n.lab/build-cache/"];
       records [label="campaign records,\nlocks, wire checks\n.lab/"];
       results [label="results tree\nresults/kernel-latency/\n(instances, sealed runs,\nstudy.json, plots, pages)"];
     }

     board [label="board\n(probe, console,\nwire D2 to A3)", shape=box3d];
     other [label="another lab space\n(lab export / lab import)", style="rounded,dashed"];

     pins -> trees [label="trees setup"];
     design -> tools [label="campaign"];
     tools -> cache [label="west build"];
     trees -> cache;
     apps -> cache;
     cache -> board [label="flash"];
     board -> results [label="capture,\nseal, run list"];
     tools -> records;
     results -> results [label="analysis build"];
     results -> other [dir=both];
   }

The parts
---------

Design repository
   The safety repository at one commit. It has the study designs (the
   studies, the experiments, the hypotheses), the pins of the trees, the
   apps with their board ports, extractors and plot scripts, and the
   tools. A run builds from a clean clone at one commit, and the commit
   stays reachable with a local ref (see :doc:`reproducibility`).

Lab space
   One folder of one host (see :doc:`../reference/files/lab-config`). It
   has the clone of the design repository, the Python environment, a west
   workspace for each pinned tree, the build cache, the campaign records,
   the locks and the wire checks, and the results tree. Nothing of a host
   goes into the design repository.

Board
   A board of the hardware map of the lab space, with the wire from the
   stimulus pin to the response pin. One campaign at a time uses a board
   (a lock for each board).

Results tree
   The instances (a study for one board), each with its run list and its
   sealed runs, and the derived files: ``run.json``, the app data,
   ``experiment.json``, ``study.json``, the plots and the pages. The run
   folders never change; the derived files come again from them at any
   time (``analysis check``).

The flow of one campaign
------------------------

#. ``campaign check`` makes sure that the design repository is clean,
   that the trees are at their pins, that the board is there and that the
   wire works.
#. For each experiment, ``run.py`` takes each image from the build cache
   or builds it with ``west build`` in the workspace of the tree, flashes
   the board, reads the samples from the console, and seals the run.
#. ``run.py`` adds the run to the run list of its instance.
#. In the background, ``analysis build`` makes the derived files, the
   plots and the pages, while the next experiment runs.
#. ``lab export`` and ``lab import`` give the runs to another lab space;
   the import checks that both lab spaces have the same experiments.

The reasons for these parts are in :doc:`decisions/index`.
