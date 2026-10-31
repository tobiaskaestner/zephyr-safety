.. _benchguide-experiment-file:

Experiment file
===============

An :term:`experiment` folder ``ex-<name>/`` holds the experiment file
``experiment.yaml`` and the description ``experiment.md`` (see
:ref:`benchguide-experiment-md`). The schema
``scripts/probatrix/benchmarks/schemas/experiment.schema.yaml`` gives the keys and
their types. ``run.py`` stops on a key that it does not know. The keys of
the experiment file are:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Key
     - Meaning
   * - ``name``
     - Name of the experiment. It is the name of the folder in the output.
       The experiment folder must be ``ex-<name>``.
   * - ``renamed_from``
     - Optional. The earlier names of a renamed experiment (a name or a
       list). The :term:`runs <Run>`, refs and imports with an earlier name stay valid:
       the run ids do not change (``<earlier name>/<UTC>``, folder
       ``ex-<earlier name>/<UTC>``), and the tools map the earlier name to
       ``name``. An earlier name must not be the name of another
       experiment.
   * - ``app``
     - The :term:`app` folder in ``tests/benchmarks/``.
   * - ``trees``
     - List of :term:`tree` names (the files of ``validation/trees/``).
   * - ``board``
     - Optional. A :term:`board target` of ``boards.yaml``. The default is
       ``default`` of ``boards.yaml``.
   * - ``repeat``
     - Number of :term:`repetitions <Repetition>` of each point (default 1).
   * - ``timeout``
     - Maximum time of one repetition in seconds (default 600).
   * - ``common``
     - Settings for all points.
   * - ``axes``
     - Optional. A map of axes. Each axis is a map from a value name to
       settings. ``run.py`` makes one :term:`point` for each combination of
       the values (Cartesian product). An experiment that changes one
       factor at a time has one axis, ``variant`` (see :term:`variant`).
   * - ``extra_axes``
     - Optional. A map from an axis name to a value name: axes that only
       the explicit points change. All points of ``axes`` get this value.
   * - ``points``
     - Optional. A list of explicit points, each with an ``id`` and with
       ``axes``, a map that gives a value on each axis (also on each of
       ``extra_axes``).
   * - ``acceptance``
     - Optional. The acceptance checks of each run (see below).

An experiment has ``axes``, ``points``, or both. The design lint gives
these errors:

- The experiment has no axis name: ``axes`` and ``extra_axes`` are both
  empty or missing.
- A point does not have a value on each axis of ``axes`` and
  ``extra_axes``, or it has a value on another axis.

An experiment with only ``points`` names its axes in ``extra_axes``, for
example ``ex-irq-smoke``. An experiment without points stops ``run.py``
(``no points to run``).

Each set of settings (in ``common``, in an axis value or in a point) can
have these keys:

``kconfig``
   A map from a Kconfig option (without ``CONFIG_``) to its value. ``y``
   and ``n`` stay as text. A YAML Boolean becomes ``y`` or ``n``.

``conf_files``
   A list of Kconfig fragments, relative to ``tests/benchmarks/``.

``dtc_overlays``
   A list of devicetree overlays, relative to ``tests/benchmarks/``. The
   :term:`board port` adds its own overlays. Do not list them here.

``value``
   Only in an axis value. The number of the value, for example ``16`` for
   ``t16`` (16 load timers). A plot uses it as the x value.

The value names of an axis must be text. YAML reads ``on``, ``off``,
``yes``, ``no``, ``true`` and ``false`` as Booleans, so ``run.py`` refuses
these names. Put them in quotes, or use other names.

The axes of each point go into the manifest, so the analysis can group
and plot the points by axis.

The settings merge in this order: ``common``, then the axis values in the
order of the axes, or the point. For ``kconfig``, a later value replaces
an earlier value of the same option. ``conf_files`` and ``dtc_overlays``
are concatenated. The ID of a point from the axes is the value names,
joined by ``-``, in the order of the axes. Two points with the same ID
stop the run.

Example: four interrupt paths times two anchors give eight points
(``stock-default``, ``stock-lean``, ``wrapped-default`` and more).

.. code-block:: yaml

   # Question: what does lean.conf change on each interrupt path?

   name: irq-example
   app: irq_latency
   trees: [ws-up]
   repeat: 1
   timeout: 900

   common:
     kconfig:
       LATBENCH_SAMPLES: 1000000
       LATBENCH_STIM_MIN_US: 100
       LATBENCH_STIM_MAX_US: 500

   axes:
     path:
       stock:
         kconfig: {LATBENCH_IRQ_PATH_STOCK: y}
       wrapped:
         kconfig: {LATBENCH_IRQ_PATH_WRAPPED: y}
       direct:
         kconfig: {LATBENCH_IRQ_PATH_DIRECT: y}
       zli:
         kconfig: {LATBENCH_IRQ_PATH_ZLI: y}
     anchor:
       default: {}
       lean:
         conf_files: [common/conf/lean.conf]

   extra_axes:
     clock: 170mhz

   points:
     - id: direct-16mhz
       axes: {path: direct, anchor: default, clock: 16mhz}
       kconfig: {LATBENCH_IRQ_PATH_DIRECT: y}
       dtc_overlays: [common/boards/nucleo_g474re/clocks/nucleo_g474re_16mhz.overlay]

The paths ``wrapped``, ``direct`` and ``zli`` need no overlay in the
experiment. ``run.py`` puts their Kconfig value on the CMake command line,
and the port then adds its ``resp_irq_own.overlay`` (see :doc:`../apps`).

Acceptance
----------

``acceptance`` is a list of checks of each run, for example ``{id: A1,
metric: [irq, isr2thr], stat: invalid, expect: {equals: 0}}`` (see
:doc:`../check-forms`). A run that fails one is not evidence: the
:term:`hypotheses <Hypothesis>` and the :term:`central results <Central result>` do not read it.

.. _benchguide-experiment-md:

The description ``experiment.md``
---------------------------------

``experiment.md`` describes the experiment in Markdown. The template of
``study.py design scaffold experiment`` has these sections:

``What it measures``
   The app, the metric, and what the experiment measures.

``Method``
   How it measures: the stimulus, the :term:`samples <Sample>`, the load and the clock.

``Axes``
   One line for each axis: what the axis varies, and why.

The design lint gives an error if ``experiment.md`` is missing. It gives
a warning if the file does not name an axis of the experiment, or if it
has ``TODO`` texts of a template. The experiment folders below
``validation/empirical/latencies/`` are the current experiments.
