.. _benchguide-glossary:

Glossary
========

This guide uses these terms with one meaning each:

.. glossary::
   :sorted:

   App
      A Zephyr application in a folder of ``tests/benchmarks/``, for example
      ``irq_latency``.

   Variant
      A value of the axis ``variant`` of an experiment: the label of one
      variation of the app, for example ``baseline``. An experiment that
      changes one factor at a time has this one axis (see
      :doc:`files/experiment-yaml`).

   Sample
      One latency value in core cycles.

   Board target
      A Zephyr board target with qualifiers, for example
      ``nrf54l15dk/nrf54l15/cpuapp``. ``boards.yaml`` declares the board
      targets of the suite.

   Board port
      The board-specific code of the stimulus, in ``common/boards/<board>/``
      (see :doc:`boards`).

   Tree
      A pinned set of source repositories (Zephyr and its modules), declared
      as a west manifest in ``validation/trees/<tree>.yml``.

   Experiment
      A folder ``ex-<name>/`` in the folder of a study, below
      ``validation/empirical/latencies/``. It has ``experiment.yaml``, the
      input of ``run.py``: an app, one or more trees and the points (see
      :doc:`files/experiment-yaml`). It also has ``experiment.md``: what
      it measures, the method and the axes. The study that holds the
      folder owns the experiment. Another study can import it
      (``imports:``).

   Point
      One build configuration of an experiment, with an ID.

   Repetition
      One flash and one capture of the serial output of a point.

   Run
      One execution of ``scripts/benchmarks/run.py`` for one experiment,
      and the raw run folder that it makes: ``ex-<experiment>/<UTC>/`` in
      the folder of its instance. The run id is ``<experiment>/<UTC>``. The
      run folder does not change after its seal.

   Study
      A folder with ``study.yaml``. The top study is
      ``validation/empirical/latencies/`` itself. A study can have
      sub-studies (folders ``st-<name>/``) and experiments (folders
      ``ex-<name>/``). A sub-study is a study.

   Instance
      One study design, applied to one board, in a results tree. Its folder
      has ``instance.json``: the run list, the roles of the runs, the
      references and the manual verdicts. The run list is hand-made data.

   Lab space
      A folder with ``.lab/config`` that holds everything of one host that a
      study needs and that the safety repository must not hold: the design
      repository, the Python environment, the pinned trees, the hardware
      map, the results tree, the build cache and the campaign records (see
      :doc:`files/lab-config`).

   Design repository
      The clone of the safety repository in a lab space (``[design]
      repo`` of ``.lab/config``). It has the study designs, the tree pins,
      the apps and the tools. The tools of the lab space come from it. A
      study of your own goes on a local branch of it.

   Safety repository
      The shared origin repository of the suite. Each design repository is
      a clone of it.

   Pre-flight check
      The examination before a campaign runs: the design repository, the
      lint, the SDK, the trees, the images, the hardware map, the boards,
      the wire check, the disk and the duration (see
      :ref:`benchguide-preflight`). ``campaign check`` does only this
      examination.

   Wire check
      A test of the loopback wire of a board: ``study.py lab hwcheck``
      builds and flashes ``loopback_check`` and reads ``RESULT: OK`` or
      ``RESULT: FAIL``. The pre-flight check includes it.

   Campaign
      One command that runs the experiments below a study folder, adds each
      run to its instance and builds the results after each run. Its record
      is ``.lab/campaigns/<id>.json`` (see :doc:`../explanation/campaigns`).

   Hypothesis
      A claim about a mechanism, in the ``hypotheses.yaml`` of a study,
      written before the runs. It is wrong if one of its checks is wrong,
      and confirmed if all its checks are confirmed. A wrong hypothesis is
      a result, not a failure of the tools.

   Check
      A comparison of measured values with a limit (see
      :doc:`check-forms`). An acceptance check belongs to an experiment.
      It decides if a run can be evidence. The checks of a hypothesis
      decide its verdict.

   Verdict
      The result of a check or a hypothesis: ``confirmed``, ``wrong``,
      ``open``, ``not evaluated``, ``draft`` or ``tool error``. A manual
      check gets its verdict from a person (``instance verdict``).

   Central result
      A sentence of a study with measured values in it, made by the build
      from the runs (see :doc:`central-results`).

   Role
      The place of a run in the run list of an instance: ``evidence`` (the
      checks read it), ``adjustment`` (a run to adjust or test something,
      in the plots but not in the checks) or ``excluded``.

   Seal
      The file ``<UTC>.sha256`` beside a run folder: one line ``<sha256>
      <path>`` for each file of the run. The digest of the run is
      ``sha256:`` and the SHA-256 of the seal file. A run folder never
      changes after its seal.

   Provisional
      A verdict or a central result that waits for an experiment of a
      campaign that still runs. The build after the end of the campaign
      makes it final.

   Build cache
      The images of the points of the lab space, in
      ``.lab/build-cache/``, found by a key over all inputs of an image (see
      :doc:`../explanation/reproducibility`).

The prefixes ``st-`` and ``ex-`` are only in the folder names. Names and
references in the files have no prefix: a study path is a path of names
(``load-scaling/t2t-under-load``), a run id is ``<experiment>/<UTC>``.
