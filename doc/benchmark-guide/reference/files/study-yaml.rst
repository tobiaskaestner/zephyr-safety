Design files
============

A :term:`study` folder has ``study.yaml``, ``study.md`` and
``hypotheses.yaml``. ``study.py design scaffold study`` makes them from
templates (see :ref:`benchguide-scaffold`). The schema
``scripts/probatrix/benchmarks/schemas/study.schema.yaml`` gives the keys and
their types.

``study.yaml``
--------------

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Key
     - Meaning
   * - ``name``
     - The name of the study. The folder is ``st-<name>`` (not for the top study).
   * - ``kind``
     - The name of the kind of the study. All studies of the latency benchmarks
       have ``kind: latbench``. A sub-study inherits it (see
       :doc:`../../explanation/probatrix`).
   * - ``question``
     - The verification question.
   * - ``board``
     - Optional. A :term:`board target`, or ``null``. The schema accepts it, but
       the tools do not read it. The top study has ``board: null``: the
       :term:`instances <Instance>` fix the board (see :doc:`results-tree`).
   * - ``experiments``
     - The names of the :term:`experiments <experiment>` that the study
       owns.
   * - ``imports``
     - ``{study, experiment, mode}``: an experiment of another study.
       ``mode: reuse`` reads the :term:`runs <Run>` of that study. ``mode: rerun`` makes
       own runs of the experiment.
   * - ``substudies``
     - A list of sub-studies. An item is a plain name, or ``{use:
       <name>}``. ``{use: <name>, instances: per-board}`` gives each board
       its own instance of the sub-study.
   * - ``central_results``
     - ``{id, statement, from, stat, group_by, unit}``: see
       :ref:`benchguide-central`.

.. _benchguide-study-md:

``study.md``
------------

``study.md`` describes the study in Markdown. The template has these
sections:

``Background``
   What the study is about and why, and the mechanisms that the
   experiments test.

``Experiments``
   One line for each experiment: why it is there, and how it connects to
   the others. ``scaffold experiment`` adds the line of a new experiment.
   The findings of the study also go here.

``References``
   The sources of the background and of the predictions.

``hypotheses.yaml``
-------------------

A study aims for 1 to 4 :term:`hypotheses <hypothesis>`. The design lint
gives a warning for more than 4. A hypothesis is one claim about a
mechanism: ``id``, ``type`` (``method`` or ``model``), ``statement``,
``basis`` (the mechanism and its sources), ``wrong_if`` and ``checks``.

A :term:`check` has ``id``, ``formerly``, ``written``, the data
(``experiment``, ``select``, ``metric``, ``stat``), the comparison
(``expect``) or ``manual: true`` with a ``statement``, and ``basis``
(where the number of the check comes from). :doc:`../check-forms` gives
the forms. A hypothesis is wrong if one check is wrong, and confirmed if
all checks are confirmed. A check with a ``TODO`` text, or a check of a
hypothesis whose statement has a ``TODO`` text, gets the :term:`verdict`
``draft``.

Notebooks
---------

A study can have notebooks, committed without outputs. Each study has
``report.ipynb``, its report. The report starts with the same part in
all studies: the instance, the question, the central results, the
hypotheses and the checks. Then it shows the data of the study as
interactive figures, each with a table of its values. A notebook reads a
built instance with ``scripts/probatrix/benchmarks/data.py`` and makes its figures
with ``scripts/probatrix/benchmarks/nbfig.py``. In the figures, you can hover for
values, drag to zoom, click a legend entry to hide a series, and select
the metric in the menu above a figure. ``study.py analysis notebooks``
runs the notebooks (see :doc:`../cli/study-py`). The HTML of a report
loads plotly.js from its CDN (``cdn.plot.ly``), so it shows the figures
only with network access.

``study.py analysis notebooks`` also writes the executed notebook
beside its HTML: ``<instance>/notebooks/report.ipynb``, with its outputs.
The copy reads like the study. After the title, it gets the place of
the study in the tree (a link to the report of the parent study, and to
the report of each sub-study with its question and verdicts) and the
text of ``study.md``. At the end, it gets the ``experiment.md`` of each
experiment of the study, and a link to the report of the study that
owns each imported experiment. These cells have the metadata
``latbench: from the design``. A study without hypotheses, for example
a study that has only sub-studies, also has a report.
To open the reports in a browser, install JupyterLab into the venv of the
lab space (``scripts/probatrix/benchmarks/requirements-jupyter.lock``) and start it
at the results root:

.. code-block:: console

   .venv/bin/jupyter lab results/kernel-latency

The file browser shows the results tree: open the ``notebooks`` folder of
an instance, and open ``report.ipynb``. The HTML viewer of JupyterLab runs
no scripts until you click "Trust HTML", so ``report.html`` shows no
figures there; open it in a web browser instead. The page of each
instance (``index.html``) links its report at the top and shows the
overview plot of each experiment. An executed notebook finds its instance from its folder and
the safety repository from the lab space, so it can run again and you
can change it there. To change a report for all, change the notebook in
the safety repository and commit it without outputs. The next ``analysis
notebooks`` writes a new copy over yours.
