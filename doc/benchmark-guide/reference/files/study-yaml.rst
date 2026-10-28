Design files
============

``study.yaml``

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Key
     - Meaning
   * - ``name``
     - The name of the study. The folder is ``st-<name>`` (not for the top study).
   * - ``question``
     - The verification question.
   * - ``experiments``
     - The names of the experiments that the study owns.
   * - ``imports``
     - ``{study, experiment, mode}``: an experiment of another study.
       ``mode: reuse`` reads the runs of that study; ``mode: rerun`` makes
       own runs of the experiment.
   * - ``substudies``
     - ``{use: <name>}``. ``instances: per-board`` gives each board its
       own instance of the sub-study.
   * - ``central_results``
     - ``{id, statement, from, stat, group_by, unit}``: see
       :ref:`benchguide-central`.

``hypotheses.yaml`` has 1 to 4 hypotheses. A hypothesis is one claim
about a mechanism: ``id``, ``type`` (``method`` or ``model``),
``statement``, ``basis`` (the mechanism and its sources), ``wrong_if``
and ``checks``. A check: ``id``, ``formerly``, ``written``, the data
(``experiment``, ``select``, ``metric``, ``stat``), the comparison
(``expect``) or ``manual: true`` with a ``statement``, and ``basis``
(where the number of the check comes from). A hypothesis is wrong if one
check is wrong, and confirmed if all checks are confirmed.

``report.ipynb`` is the report template of a study (no outputs). It
reads a built instance with ``scripts/benchmarks/data.py``.
