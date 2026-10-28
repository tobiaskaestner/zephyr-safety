Combine two lab spaces
======================

.. admonition:: Prerequisites

   The lab space of the tutorials before, with its runs. Disk space for a
   second lab space; no board is necessary for it.

One host has only some boards of a study, and a second host makes a
study faster. Two lab spaces give each other their runs with an export
file (see :doc:`../explanation/lab-exchange`). In this tutorial you make a second lab space on the same host,
``/wrk/z/lab-tutorial-b``, and you import the runs of the first one.

Export
------

In the first lab folder:

.. code-block:: console

   $ safety/scripts/benchmarks/study.py lab export -o ../lab-tutorial-runs.tar.gz
   2 runs of 2 instances to /wrk/z/lab-tutorial-runs.tar.gz (sha256 1cba77683628)

The export has the runs of this lab space with their seals, the campaign
records, the design files, and a git bundle of the commits of the runs.
The ``.sha256`` file beside it protects the transfer.

A second lab space
------------------

The second lab space has its own clone of the safety repository, on its
main branch: it does not have the study of :doc:`your-own-study`.

Go to the parent folder of the first lab space:

.. code-block:: console

   $ cd ..

Make the second lab space there:

.. code-block:: console

   $ mkdir lab-tutorial-b && cd lab-tutorial-b && git clone -q <safety repository> safety && python3 -m venv .venv && .venv/bin/pip install -q --disable-pip-version-check -r safety/scripts/benchmarks/requirements.lock && .venv/bin/python safety/scripts/benchmarks/study.py lab init --repo safety
   lab space lab-tutorial-b-b84e23dd in /wrk/z/lab-tutorial-b
     design repo  /wrk/z/lab-tutorial-b/safety
     python       /wrk/z/lab-tutorial-b/.venv (the Python of lab init)
     trees        /wrk/z/lab-tutorial-b/trees
     results      /wrk/z/lab-tutorial-b/results
     hardware map /wrk/z/lab-tutorial-b/hw-map.yml (missing: make it with twister)
   next: cd /wrk/z/lab-tutorial-b && /wrk/z/lab-tutorial-b/safety/scripts/benchmarks/study.py trees setup <tree>

A lab space for analysis only needs no trees and no hardware map.

Import
------

``--dry-run`` does only the checks:

.. code-block:: console

   $ safety/scripts/benchmarks/study.py lab import ../lab-tutorial-runs.tar.gz --dry-run
   warning: kernel-latency/tutorial@nucleo_g474re: the study is not in the design here
   refused: irq-opt/20261028T012302Z: the experiment is not in the design here
   1 runs to add, 0 already here, 1 refused (from lab lab-tutorial-703113d7 on cos-workstation)

The import refuses the run of ``irq-opt``: the experiment is not in the
design of this lab space. Two lab spaces can share only the runs of
experiments that they both have with the same content (comments and a
rename do not count). The run of ``irq-smoke`` is good:

.. code-block:: console

   $ safety/scripts/benchmarks/study.py lab import ../lab-tutorial-runs.tar.gz
   2 commits of the runs in refs/latbench/import/lab-tutorial-703113d7/ of /wrk/z/lab-tutorial-b/safety
   warning: kernel-latency/tutorial@nucleo_g474re: the study is not in the design here
   refused: irq-opt/20261028T012302Z: the experiment is not in the design here
   1 runs added, 0 already here, 1 refused (from lab lab-tutorial-703113d7 on cos-workstation)
   next: study.py analysis build /wrk/z/lab-tutorial-b/results/kernel-latency

The commits of the runs are in the clone of this lab space now, so a
rebuild works here too.

The same verdicts
-----------------

.. code-block:: console

   $ safety/scripts/benchmarks/study.py analysis build results/kernel-latency
   built 5 instances, 1 runs; 8 files written
   [...]
   kernel-latency/st-default-latencies@nucleo_g474re/st-irq-entry: H 1 confirmed, 0 wrong, 2 open; central 0 of 1
   [...]
   $ safety/scripts/benchmarks/study.py analysis show results/kernel-latency/st-default-latencies@nucleo_g474re/st-irq-entry --details

   == kernel-latency/st-default-latencies@nucleo_g474re/st-irq-entry
      H1 confirmed (1 of 1)
         a confirmed: ws-safety irq mode_share(2) direct-busy: 0
      [...]

The second lab space gives the same verdicts as the first one from the
same run. In real work, the export file goes to another host (``scp``),
and each host adds the runs of its boards. :doc:`../howto/combine-lab-spaces`
gives the steps.

You have done the full cycle: a lab space, an experiment, a campaign, a
study of your own, an audit, and a second lab space. The
:doc:`../howto/index` give the steps of each task, and the
:doc:`../reference/index` has the details of each command and file.
