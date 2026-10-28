Design files
============

A :term:`study` folder has ``study.yaml``, ``study.md`` and
``hypotheses.yaml``. ``study.py design scaffold study`` makes them from
templates (see :ref:`benchguide-scaffold`). The schema
``scripts/benchmarks/schemas/study.schema.yaml`` gives the keys and
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

A study can have notebooks, for example ``report.ipynb``, committed
without outputs. A notebook reads a built instance with
``scripts/benchmarks/data.py``. ``study.py analysis notebooks`` runs them
(see :doc:`../cli/study-py`).
