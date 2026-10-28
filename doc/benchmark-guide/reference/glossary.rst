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
      One build of an app with a set of Kconfig options, for example the
      ``direct`` IRQ path of ``irq_latency``.

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
      A folder ``ex-<name>/`` in the folder of the study that owns it,
      below ``validation/empirical/latencies/``, with the file
      ``experiment.yaml``. It
      names an app, one or more trees, and a list of points.

      A folder ``ex-<name>/`` with ``experiment.yaml`` (the input of
      ``run.py``, see :doc:`files/experiment-yaml`) and ``experiment.md`` (question,
      method, references). The study that holds the folder owns the
      experiment. Another study can import it (``imports:``).

   Point
      One build configuration of an experiment, with an ID.

   Repetition
      One flash and one capture of the serial output of a point.

   Run
      One execution of ``scripts/benchmarks/run.py`` for one experiment. A
      run makes one result folder.

      One raw run folder of ``run.py``: ``ex-<experiment>/<UTC>/`` in the
      folder of its instance. The run folder does not change after the run.
      Its seal ``<UTC>.sha256`` is beside it: one line ``<sha256>  <path>``
      for each file. The digest of the run is ``sha256:`` + the sha256 of
      the seal file.

   Study
      A folder with ``study.yaml``. The top study is
      ``validation/empirical/latencies/`` itself. A study can have
      sub-studies (folders ``st-<name>/``) and experiments (folders
      ``ex-<name>/``). A sub-study is a study.

   Instance
      One study design, applied to one board, in a results tree. Its folder
      has ``instance.json``: the run list, the roles of the runs, the
      references and the manual verdicts. The run list is hand-made data.

The prefixes ``st-`` and ``ex-`` are only in the folder names. Names and
references in the files have no prefix: a study path is a path of names
(``load-scaling/t2t-under-load``), a run id is ``<experiment>/<UTC>``.
