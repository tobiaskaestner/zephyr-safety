.. _benchguide-experiment-file:

Experiment file
===============

An experiment is a folder ``ex-<name>/`` in the folder of the study that
owns it, below ``validation/empirical/latencies/``. A sub-study is a
folder ``st-<name>/``. The prefixes are only in the folder names; the
names in the files have no prefix. The experiment folder holds the
experiment file ``experiment.yaml`` and the description
``experiment.md``. The schema ``scripts/benchmarks/schemas/experiment.schema.yaml``
gives the keys and their types; ``run.py`` stops on a key that it does not
know. The keys of the experiment file are:

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
       list). The runs, refs and imports with an earlier name stay valid:
       the run ids do not change (``<earlier name>/<UTC>``, folder
       ``ex-<earlier name>/<UTC>``), and the tools map the earlier name to
       ``name``. An earlier name must not be the name of another
       experiment.
   * - ``app``
     - The app folder in ``tests/benchmarks/``.
   * - ``trees``
     - List of tree names (the files of ``validation/trees/``).
   * - ``board``
     - Optional. A board target of ``boards.yaml``. The default is
       ``default`` of ``boards.yaml``.
   * - ``repeat``
     - Number of repetitions of each point (default 1).
   * - ``timeout``
     - Maximum time of one repetition in seconds (default 600).
   * - ``common``
     - Settings for all points.
   * - ``axes``
     - A map of axes. Each axis is a map from a value name to settings.
       ``run.py`` makes one point for each combination of the values
       (Cartesian product). An experiment has one axis or more. An
       experiment that changes one factor at a time has one axis,
       ``variant``.
   * - ``extra_axes``
     - Optional. A map from an axis name to a value name: axes that only
       the explicit points change. All points of ``axes`` get this value.
   * - ``points``
     - Optional. A list of explicit points, each with an ``id`` and with
       ``axes``, a map that gives a value on each axis (also on each of
       ``extra_axes``). You can use ``axes`` and ``points`` together.

Each set of settings (in ``common``, in an axis value or in a point) can
have these keys:

``kconfig``
   A map from a Kconfig option (without ``CONFIG_``) to its value. ``y``
   and ``n`` stay as text. A YAML Boolean becomes ``y`` or ``n``.

``conf_files``
   A list of Kconfig fragments, relative to ``tests/benchmarks/``.

``dtc_overlays``
   A list of devicetree overlays, relative to ``tests/benchmarks/``. The
   board port adds its own overlays. Do not list them here.

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
   trees: [ws-safety]
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

The experiment folders in the study folders below
``validation/empirical/latencies/`` are the current experiments. The
description ``experiment.md`` in each folder gives the question of the
experiment.

``experiment.yaml`` can have ``acceptance``: checks of each run, for
example ``{id: A1, metric: [irq, isr2thr], stat: invalid, expect:
{equals: 0}}``. A run that fails one is not evidence: the hypotheses
and the central results do not read it.
