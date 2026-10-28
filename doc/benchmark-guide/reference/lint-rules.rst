.. _benchguide-lint:

Lint rules
==========

An error makes the design unusable, or it makes a check wrong. A warning
is a rule of good practice. ``study.py design lint`` exits with 1 if it finds an
error. With ``--warn-as-error``, a warning also gives exit code 1.

Errors:

- A key or a type that the schema of the file does not allow. The
  schemas are in ``scripts/benchmarks/schemas/`` (JSON Schema, written in
  YAML): ``experiment``, ``study``, ``hypotheses`` and ``boards``. For an
  unknown key, the lint names the nearest known key, for example
  ``schema: (top): unknown key 'repat' (did you mean 'repeat'?)``. The
  tools that read a design file (``run.py``, the design of ``study.py``,
  ``boards.yaml``) stop at the first violation. The copies of
  ``experiment.yaml`` in sealed runs are history; the tools do not check
  them against the current schemas.
- A folder with ``experiment.yaml`` that is not ``ex-<name>``, a folder
  with ``study.yaml`` that is not ``st-<name>``, a ``name`` in
  ``study.yaml`` that is not the folder name, or a folder with neither
  file.
- The design does not load.
- An experiment without ``experiment.md``, with an ``app`` that is not a
  folder of ``tests/benchmarks/``, or without an axis.
- An experiment file that ``run.py`` cannot expand into points (for
  example an axis value name that YAML reads as a Boolean).
- A point without a value on each axis, or an axis ``value`` that is not
  a number.
- A ``board`` that is not in ``boards.yaml``.
- A point with more than one code place (``LATBENCH_CODE_FLASH``,
  ``LATBENCH_CODE_FLASH_PAD``, ``LATBENCH_CODE_RAM``).
  ``LATBENCH_CODE_PAD_BYTES`` without ``LATBENCH_CODE_FLASH_PAD`` or
  ``LATBENCH_CODE_RAM``, or with a value that is not a multiple of 4.
  ``LATBENCH_CODE_RAM`` without a RAM region from the point or the port.
- A check (acceptance or hypothesis) in a form that the tools do not
  know: no ``expect``, no ``stat``, a metric with a stat that the tools
  cannot calculate, or a manual check without ``statement``.
- A check or a central result that reads an experiment that its study
  does not own or import. A ``diff_to`` experiment that does not exist.
- A ``select`` (or a ``point`` of a central result) that names a point,
  an axis or an axis value that the experiment does not have.
- A ``group_by`` with a stat that is not an aggregate, a ``group_by``
  axis that the experiment does not have, or the statement of an
  aggregate that names an axis that is not in ``group_by`` (see
  :ref:`benchguide-central`).
- A central result from a ``substudy`` that is not a sub-study.

Warnings:

- A ``TODO`` text in a ``.yaml`` or ``.md`` file (a template of
  ``study.py design scaffold``).
- A study without ``study.md``.
- A study without experiments, imports and sub-studies.
- An axis that ``experiment.md`` does not name.
- More than 4 hypotheses in a study.

``run.py`` runs the lint for its experiment and for the study that owns
it before it builds. It prints each problem and continues. With
``--warn-as-error``, each problem (error or warning) stops the run. The
pre-flight check of a campaign fails on a lint error (see :doc:`cli/study-py`).
The tests in ``scripts/benchmarks/tests/`` fail if the design of the
repository has a lint error.
