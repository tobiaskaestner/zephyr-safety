Your own study
==============

.. admonition:: Prerequisites

   The lab space of :doc:`set-up-a-lab-space`. The images of
   :doc:`first-experiment` in the build cache help, but are not necessary.

In this tutorial you ask a question of your own: **does the optimization
level of the compiler change the IRQ entry latency of the direct path?**
You make a study with one experiment (one Kconfig factor, two values), you
write a hypothesis before the run, and you let a campaign decide it.

Your study goes on a local branch of the :term:`design repository`. Do
not push this branch.

Make a branch and the files
---------------------------

.. code-block:: console

   $ git -C safety switch -c tutorial/irq-opt
   Switched to a new branch 'tutorial/irq-opt'
   $ safety/scripts/benchmarks/study.py design scaffold study safety/validation/empirical/latencies/st-tutorial
   new /wrk/z/lab-tutorial/safety/validation/empirical/latencies/st-tutorial/hypotheses.yaml
   new /wrk/z/lab-tutorial/safety/validation/empirical/latencies/st-tutorial/study.md
   new /wrk/z/lab-tutorial/safety/validation/empirical/latencies/st-tutorial/study.yaml
   replace the TODO texts; 'study.py design lint' lists them
   $ safety/scripts/benchmarks/study.py design scaffold experiment safety/validation/empirical/latencies/st-tutorial/ex-irq-opt --app irq_latency
   new /wrk/z/lab-tutorial/safety/validation/empirical/latencies/st-tutorial/ex-irq-opt/experiment.md
   new /wrk/z/lab-tutorial/safety/validation/empirical/latencies/st-tutorial/ex-irq-opt/experiment.yaml
   replace the TODO texts; 'study.py design lint' lists them
   $ safety/scripts/benchmarks/study.py design lint safety/validation/empirical/latencies/st-tutorial
   warning: validation/empirical/latencies/st-tutorial/ex-irq-opt/experiment.md: 3 TODO texts of a template
   warning: validation/empirical/latencies/st-tutorial/ex-irq-opt/experiment.yaml: 1 TODO texts of a template
   warning: validation/empirical/latencies/st-tutorial/hypotheses.yaml: 4 TODO texts of a template
   warning: validation/empirical/latencies/st-tutorial/hypotheses.yaml: H1 has no checks: it stays open
   warning: validation/empirical/latencies/st-tutorial/study.md: 3 TODO texts of a template
   warning: validation/empirical/latencies/st-tutorial/study.yaml: 1 TODO texts of a template
   0 errors, 6 warnings

``scaffold study`` also added ``use: tutorial`` to the top
``study.yaml``. The templates pass the lint without errors. Each
``TODO`` text is a warning until you replace it. The hypothesis of the
template has no checks yet, so the lint also warns that it stays open.

Write the design
----------------

Replace the templates with the content of your study. The experiment has
one axis, ``opt``, with two values. All points use the direct IRQ path
(see :doc:`../reference/files/experiment-yaml`):

.. code-block:: yaml
   :caption: st-tutorial/ex-irq-opt/experiment.yaml

   name: irq-opt
   app: irq_latency
   trees: [ws-up]
   repeat: 1
   timeout: 400
   common:
     kconfig:
       LATBENCH_SAMPLES: 100000
       LATBENCH_IRQ_PATH_DIRECT: y
   axes:
     opt:
       speed: {kconfig: {SPEED_OPTIMIZATIONS: y}}
       size: {kconfig: {SIZE_OPTIMIZATIONS: y}}
   acceptance:
     - id: A1
       metric: irq
       stat: invalid
       expect: {equals: 0}
       basis: No negative differences, so the stimulus and the time stamps work.

Write the hypothesis and its limit **before** the run. A hypothesis is
useful only if the data can make it wrong.

.. code-block:: yaml
   :caption: st-tutorial/hypotheses.yaml

   hypotheses:
     - id: H1
       type: model
       statement: >
         With speed optimizations, the median IRQ entry latency of the direct
         path is not more than with size optimizations.
       basis: >
         Speed optimizations inline more and keep the ISR code short. The
         direct path runs no Zephyr code before the ISR body.
       wrong_if: "speed optimizations make the entry slower"
       checks:
         - id: a
           written: 2026-10-28, before the first run of irq-opt
           experiment: irq-opt
           select: {point: speed}
           metric: irq
           stat: p50
           expect: {diff_to: {point: size, range: [null, 0]}}
           basis: "speed - size <= 0 cycles: the claim of H1."

The check takes the median (``p50``) of the point ``speed`` and its
difference to the point ``size``. The limit is 0 cycles or less (see
:doc:`../reference/check-forms`). The study also gets a central result,
with one sentence for each point (see :doc:`../reference/files/study-yaml`
and :doc:`../reference/central-results`).

.. code-block:: yaml
   :caption: st-tutorial/study.yaml

   name: tutorial
   question: >
     Does the optimization level of the compiler change the IRQ entry
     latency of the direct path?

   experiments:
     - irq-opt

   central_results:
     - id: opt-p50
       statement: >
         With {opt} optimizations, the direct path has a p50 of {p50:.0f} cycles.
       from: {experiment: irq-opt, metric: irq}
       stat: p50
       unit: cycles

Also replace the ``TODO`` texts of ``study.md`` and ``experiment.md``:
what the study is about, and what the axis ``opt`` varies.

Lint and commit
---------------

.. code-block:: console

   $ safety/scripts/benchmarks/study.py design lint safety/validation/empirical/latencies/st-tutorial
   0 errors, 0 warnings
   $ git -C safety add -A && git -C safety commit -q -m 'tutorial: a study of the optimization level' && git -C safety log --oneline -1
   637f52f tutorial: a study of the optimization level

The commit is necessary: ``run.py`` refuses a repository with changes
that are not committed, because a run must name the exact source of its
images.

Run it
------

.. code-block:: console

   $ safety/scripts/benchmarks/study.py campaign check safety/validation/empirical/latencies/st-tutorial
     planned  irq-opt (tutorial, nucleo_g474re) -> kernel-latency/st-tutorial@nucleo_g474re (will be made)
     ok   design repo: /wrk/z/lab-tutorial/safety at 637f52f18ee0
     [...]
   pre-flight check: ok
   $ safety/scripts/benchmarks/study.py campaign run safety/validation/empirical/latencies/st-tutorial --detach
   campaign 20261029T132506Z: 1 experiments, record /wrk/z/lab-tutorial/.lab/campaigns/20261029T132506Z.json
   runs in the background (pid 1912267); log /wrk/z/lab-tutorial/.lab/campaigns/20261029T132506Z/campaign.log; 'study.py campaign status 20261029T132506Z'

After about three minutes:

.. code-block:: console

   $ safety/scripts/benchmarks/study.py analysis show results/kernel-latency/st-tutorial@nucleo_g474re --details

   == kernel-latency/st-tutorial@nucleo_g474re
      H1 wrong (0 of 1)
         a wrong: FAIL ws-up irq p50 speed: 56 - 55 (size) = 1
      [opt-p50] With speed optimizations, the direct path has a p50 of 56 cycles.
      [opt-p50] With size optimizations, the direct path has a p50 of 55 cycles.

The hypothesis is **wrong**: with speed optimizations, the median is 1
cycle more than with size optimizations. A wrong hypothesis is a result,
not a failure of the tools: the claim was written before the data, and
the data decided. The next step of such a study is a new hypothesis
about the cause (for example the code alignment, see
:doc:`../explanation/code-placement`), with a new check.

``--explain`` shows how the build made each sentence of the central
result:

.. code-block:: console

   $ safety/scripts/benchmarks/study.py analysis show results/kernel-latency/st-tutorial@nucleo_g474re --explain opt-p50

   == kernel-latency/st-tutorial@nucleo_g474re [opt-p50]
      statement: With {opt} optimizations, the direct path has a p50 of {p50:.0f} cycles.
      from: {'experiment': 'irq-opt', 'metric': 'irq'}
      stat: p50
      row: run=irq-opt/20261029T132512Z, tree=ws-up, point=speed, opt=speed, metric=irq, p50=56
        -> With speed optimizations, the direct path has a p50 of 56 cycles.
      row: run=irq-opt/20261029T132512Z, tree=ws-up, point=size, opt=size, metric=irq, p50=55
        -> With size optimizations, the direct path has a p50 of 55 cycles.

Next: :doc:`audit-a-result`.
