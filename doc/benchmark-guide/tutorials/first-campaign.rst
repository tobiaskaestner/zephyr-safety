Your first campaign
===================

.. admonition:: Prerequisites

   The lab space of :doc:`set-up-a-lab-space`. The images of
   :doc:`first-experiment` in the build cache help, but are not
   necessary.

A :term:`campaign` runs the experiments of a study, adds each run to the
run list of its :term:`instance` (the study for one board, in the results
tree), and builds the verdicts after each run. In this tutorial you run
``irq-smoke`` as an experiment of its study ``irq-entry``.

Check before you run
--------------------

.. code-block:: console

   $ safety/scripts/benchmarks/study.py campaign check safety/validation/empirical/latencies/st-default-latencies --only irq-smoke
     planned  irq-smoke (default-latencies/irq-entry, nucleo_g474re) -> kernel-latency/st-default-latencies@nucleo_g474re/st-irq-entry (will be made)
     ok   design repo: /wrk/z/lab-tutorial/safety at df1a5d8c69ad
     ok   lint
     ok   zephyr sdk: /home/tobias/zephyr-sdk-1.0.1
     ok   tree ws-up
     ok   images: 5 of 5 in the build cache
     ok   board nucleo_g474re: probe 0042003F3433510A37363934, console /dev/serial/by-id/usb-STMicroelectronics_STLINK-V3_0042003F3433510A37363934-if02
     ok   console of nucleo_g474re: free
     ok   loopback wire of nucleo_g474re: RESULT: OK (record .lab/hwcheck/history/nucleo_g474re/20261029T131929Z.json)
     ok   disk: 883 GiB free, the runs need about 0 MiB
     ok   duration: unknown (no earlier run of irq-smoke)
   pre-flight check: ok

The first line is the plan: the experiment, its study and board, and the
instance folder that the campaign will make. The images are in the
:term:`build cache` already: the run of :doc:`first-experiment` put them
there.

Run it in the background
------------------------

.. code-block:: console

   $ safety/scripts/benchmarks/study.py campaign run safety/validation/empirical/latencies/st-default-latencies --only irq-smoke --detach
   campaign 20261029T131933Z: 1 experiments, record /wrk/z/lab-tutorial/.lab/campaigns/20261029T131933Z.json
   runs in the background (pid 1910104); log /wrk/z/lab-tutorial/.lab/campaigns/20261029T131933Z/campaign.log; 'study.py campaign status 20261029T131933Z'
   $ safety/scripts/benchmarks/study.py campaign status
   campaign 20261029T131933Z: running
     lab lab-tutorial-332eb106 on cos-workstation, repo df1a5d8c69ad, folder /wrk/z/lab-tutorial/safety/validation/empirical/latencies/st-default-latencies
     running  irq-smoke                    kernel-latency/st-default-latencies@nucleo_g474re/st-irq-entry

You can close the terminal. After about five minutes:

.. code-block:: console

   $ cat .lab/campaigns/20261029T131933Z/campaign.log
   campaign 20261029T131933Z: pre-flight check
   [...]
   made the instances of default-latencies for nucleo_g474re
   === irq-smoke (kernel-latency/st-default-latencies@nucleo_g474re/st-irq-entry)
       done (rc 0) in 5 min, 5/5 images from the build cache, run irq-smoke/20261029T131938Z
   waiting for the last build of the results (it makes the verdicts final)
   campaign 20261029T131933Z: done, 0 experiments failed; results /wrk/z/lab-tutorial/results/kernel-latency/index.html

The campaign is done. It held the board lock the whole time. A second
campaign on this board stops at once.

Read the verdicts
-----------------

One line for each instance:

.. code-block:: console

   $ safety/scripts/benchmarks/study.py analysis show results/kernel-latency
   kernel-latency: central 0 of 8
   kernel-latency/st-default-latencies@nucleo_g474re: central 0 of 3
   kernel-latency/st-default-latencies@nucleo_g474re/st-irq-entry: H 1 confirmed, 0 wrong, 2 open; central 0 of 1
   kernel-latency/st-default-latencies@nucleo_g474re/st-isr-to-thread: central 0 of 1
   kernel-latency/st-default-latencies@nucleo_g474re/st-thread-to-thread: H 0 confirmed, 0 wrong, 2 open; central 0 of 1

The details of one instance:

.. code-block:: console

   $ safety/scripts/benchmarks/study.py analysis show results/kernel-latency/st-default-latencies@nucleo_g474re/st-irq-entry --details

   == kernel-latency/st-default-latencies@nucleo_g474re/st-irq-entry
      H1 confirmed (1 of 1)
         a confirmed: ws-up irq mode_share(2) direct-busy: 0
      H2 open (0 of 2)
         a not evaluated: no evidence run of irq-checks-1m in st-default-latencies@nucleo_g474re/st-irq-entry
         b not evaluated: no evidence run of irq-checks-1m in st-default-latencies@nucleo_g474re/st-irq-entry
      H3 open (0 of 1)
         a open (manual): The tail of busy-noslice is at the idle level. The tail of busy is larger.
            give the verdict: study.py instance verdict /wrk/z/lab-tutorial/results/kernel-latency/st-default-latencies@nucleo_g474re/st-irq-entry --hypothesis H3 --check a --verdict confirmed|wrong --by NAME --text WHY
      [irq-entry-p99-direct] not evaluated: instance of study zephyr-versions for board nucleo_g474re: 0 found

The :term:`hypothesis` H1 of ``irq-entry`` is confirmed by the run of
``irq-smoke``. H2 and the :term:`central result` wait for runs of other
experiments. H3 has a manual :term:`check`: a person reads the data and
gives the :term:`verdict` with the command that the output names.

What is missing
---------------

.. code-block:: console

   $ safety/scripts/benchmarks/study.py analysis missing results/kernel-latency
   kernel-latency/st-default-latencies@nucleo_g474re/st-irq-entry: irq-checks-1m: no evidence run; waits: 2 checks (H2 a, H2 b)
   kernel-latency/st-default-latencies@nucleo_g474re/st-isr-to-thread: wake-isr-1m: no evidence run; waits: 1 central result ([isr2thr-p99-sem])
   2 experiments to run; 'study.py campaign check <folder> --only EXP ...'

This is the list of the runs to make next.
:doc:`../explanation/campaigns` tells how a campaign works, and
:doc:`../explanation/studies-and-verdicts` how the verdicts come from the
runs.

The pages
---------

.. code-block:: console

   $ safety/scripts/benchmarks/study.py analysis html results/kernel-latency
   6 pages, top: /wrk/z/lab-tutorial/results/kernel-latency/index.html

Open ``results/kernel-latency/index.html`` in a browser. Each study level
has a page with links up and down, and ``ex-irq-smoke/index.html`` has the
plots of the run and the run list. The campaign writes the pages after
each run, so during a long campaign you can reload them.

Next: :doc:`your-own-study`.
