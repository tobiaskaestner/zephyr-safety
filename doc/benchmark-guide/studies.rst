.. _benchguide-studies:

Studies and their results
=========================

A study asks one verification question. It names the experiments that
answer it, the hypotheses that were written before the runs, and the
central results that state the answer. This page describes the files of
a study design, the results tree, the tool ``scripts/benchmarks/study.py``
and the forms that a check can use.

Design files
------------

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

``experiment.yaml`` can have ``acceptance``: checks of each run, for
example ``{id: A1, metric: [irq, isr2thr], stat: invalid, expect:
{equals: 0}}``. A run that fails one is not evidence: the hypotheses
and the central results do not read it.

``report.ipynb`` is the report template of a study (no outputs). It
reads a built instance with ``scripts/benchmarks/data.py``.

.. _benchguide-lint:

Design lint (``study.py design lint``)
--------------------------------------

.. code-block:: console

   scripts/benchmarks/study.py design lint [FOLDER] [--warn-as-error]

The lint reads the design files below ``validation/empirical/latencies/``.
It needs no build and no board. It prints one line for each problem,
``<severity>: <file>: <text>``, and then the number of errors and
warnings. With ``FOLDER``, it prints only the problems of the files below
that folder, and the problems of its parent folders (for example "the
design does not load"). The tree manifests and ``boards.yaml`` are checked
only without ``FOLDER``.

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
pre-flight check of a campaign fails on a lint error (see :doc:`lab`).
The tests in ``scripts/benchmarks/tests/`` fail if the design of the
repository has a lint error.

.. _benchguide-scaffold:

New study or experiment (``study.py design scaffold``)
------------------------------------------------------

.. code-block:: console

   scripts/benchmarks/study.py design scaffold study PARENT/st-NAME
   scripts/benchmarks/study.py design scaffold experiment STUDY/ex-NAME --app APP [--board B]

``scaffold study`` makes a new sub-study ``st-NAME/`` of the study
``PARENT``, with these files:

- ``study.yaml``: the name, a ``question``, no ``experiments`` and an
  empty ``central_results``.
- ``study.md``: the sections Background, Experiments and References.
- ``hypotheses.yaml``: one template hypothesis ``H1`` without checks.

The command also adds ``use: NAME`` to ``substudies`` of the parent
``study.yaml``. The new study has no experiment and its hypothesis has no
check: write each check when the experiment that it reads exists. A
template check would give a verdict from a limit that nobody wrote.

``scaffold experiment`` makes the experiment ``ex-NAME/`` and adds it to
``experiments`` of ``STUDY/study.yaml``, and a line for it to the section
Experiments of ``STUDY/study.md``. The edits are text edits, so the
comments of the files stay.

The template ``experiment.yaml`` has the app, the board (only with
``--board``), the first tree of ``validation/trees/`` (by name), one axis
``variant`` with the value ``default``, and the acceptance check ``A1``
(no invalid samples). The metric of ``A1`` is the main metric of the app:
``irq`` for ``irq_latency``, ``isr2thr`` for ``wake_latency``, ``t2t``
for ``thread_latency``. A name has only lower case letters, digits and
``-``. An experiment name must be unique over all studies.

The templates pass the lint without errors. Each ``TODO`` text gives a
lint warning until you replace it. The command prints the new files and
the line ``replace the TODO texts; 'study.py design lint' lists them``.

Results tree
------------

.. code-block:: none

   results/kernel-latency/                         top instance (no board)
     instance.json  study.json
     st-measurement-validity/
       st-stimulus-sampling@nucleo_g474re/         the board is fixed here
         instance.json  study.json
         ex-stim-seed-1m/
           experiment.json
           20261026T155715Z/                       raw run (sealed)
           20261026T155715Z.sha256                 seal
           20261026T155715Z.run.json               framework data
           20261026T155715Z.wake_latency.json      app data
           20261026T155715Z.rebuild-<UTC>.json     a rebuild check (run.py --rebuild)

The board is in the folder name only at the level that fixes it
(``@<port>``); the sub-instances inherit it.

``run.json`` has the run identity and provenance, and for each point its
axes, the digests of ``.config``, ``zephyr.dts``, the images
(``<app>-<tree>-<point>.elf`` and ``.hex``, or ``zephyr.elf`` and
``zephyr.hex`` in an older run) and ``build.log``, the image digest (the loadable
segments of the ELF) and the code digest. The image has the
``LATBENCH_SRC_REV`` of the build: for the runs since 2026-10-27 this is the
content hash of the firmware files (kind ``firmware/1``), so the same
firmware at two commits gives the same image; older runs have the safety
revision or a git tree hash there. The code digest counts these 40
characters as zeros, so the same code gives the same code digest also
over these kinds. The app data come from the extractor of the app,
``tests/benchmarks/<app>/scripts/extract.py``: META, the histograms, the
tick phase tables, the M4 sites, and a check of the ``LAT CFG`` values
against ``.config``.

The standard plots of an experiment come from the plot script of its app,
``tests/benchmarks/<app>/scripts/plot.py`` (the common part is
``tests/benchmarks/common/scripts/latplot.py``, like the extractor). The
build runs it for each experiment of an instance, with the app data of
the runs that are not excluded (evidence and adjustment, so a smoke
campaign shows its graphs too; the legend names the role of an
adjustment run), and it writes ``ex-<experiment>/plots/`` of the
instance:

- ``overview-<metric>.svg``: the exceedance probability (the share of
  samples at or above x) of each point of the newest run, at most 8 points
  in one chart (with more points: ``overview-<metric>-<k>.svg``);
- ``ccdf-<metric>-<tree>-<point>.svg``: the exceedance probability of one
  point, one line for each run (the newest 8);
- ``hist-<metric>-<tree>-<point>.svg``: the histogram of one point of the
  newest run;
- ``plots.json``: the list of the plots and the digest of their inputs (the
  app data and the plot scripts). With the same digest, the build does not
  draw again.

The metric is the main metric of the app (``irq``, ``isr2thr``, ``t2t``).
The plots show repetition 1 of each point. A run that failed an
acceptance check is in the plots, with ``acceptance failed`` in its label
(it is not evidence for the checks).
The SVG files have no date, so the same inputs and the same matplotlib
give the same bytes. A failed plot gives a note in ``study.json``, not a
failed build. In a campaign, the background build draws the plots of an
experiment as soon as its run is done.

``experiment.json`` has one row for each run, tree, point, repetition and
metric, with the percentiles. ``study.json`` has the acceptance checks,
the rebuild checks, the hypotheses with each check (measured value,
limit, verdict) and the central results as filled sentences. The
``measured`` text of a check has all values if there are 4 or fewer; else
it has a short form (``6 values, min 100, max 105; 3 outside the limit:
...``), and ``measured_lines`` has all of them (``values`` has them as
data). A check or a central result that waits for a run has
``missing_run`` (the experiment and the instance). A manual check that is
open has the ``statement`` for the person.

The tool study.py
-----------------

The commands that change a run list are below ``study.py instance``. In a
lab space, a campaign makes the instances and adds each run (see
:doc:`lab`). Without a campaign, use these commands:

.. code-block:: console

   # once: the instance folders of a study for a board
   scripts/benchmarks/study.py instance new <results> load-scaling --board nucleo_g474re
   # a run goes into its instance folder and into its run list (run.py adds it)
   scripts/benchmarks/run.py <experiment.yaml> --out <instance folder> [--role R --reason TEXT]
   # an old run from another place: copy it in (the original stays)
   scripts/benchmarks/study.py instance add <instance folder> <old run folder> --copy
   # the aggregates, and a check that they come again from the same inputs
   scripts/benchmarks/study.py analysis build <results>/kernel-latency
   scripts/benchmarks/study.py analysis check <results>/kernel-latency
   scripts/benchmarks/study.py analysis show <folder>             # one line for each instance
   scripts/benchmarks/study.py analysis show <folder> --details   # each check and central result
   scripts/benchmarks/study.py analysis missing [<folder>]        # the runs that checks wait for
   scripts/benchmarks/study.py analysis html <folder>             # index.html at each level
   # how each central result is made: definition, rows, sentences
   scripts/benchmarks/study.py analysis show <results>/kernel-latency --explain [ID ...]
   # a manual verdict (a person, or a proposal that says so in --by)
   scripts/benchmarks/study.py instance verdict <instance folder> --hypothesis H3 --check h \
       --verdict wrong --by "<name>" --text "<why>"

``analysis html`` writes ``index.html`` in each instance folder at and
below the folder: the links up to each parent instance, the content of
``study.json``, the experiments (with a link to their pages) and the
direct sub-studies with their verdicts in one line. Each experiment
folder gets ``ex-<experiment>/index.html``: the standard plots and the
runs (role, reason, digest, campaign, acceptance), and the failed runs.
The links are relative, so you can copy the results tree or serve it from
any place. The background build of a campaign writes the pages after each
run.

``analysis notebooks FOLDER [--force]`` runs the notebooks of the studies
against their instances at and below the folder. A study has its
notebooks in its design folder (``*.ipynb`` and ``notebooks/*.ipynb``,
committed without outputs). They are for the questions that the standard
plots cannot answer: comparisons over experiments, trees and boards. Each
notebook runs (nbclient) with the environment variables
``LATBENCH_INSTANCE`` (the instance folder) and ``LATBENCH_REPO`` (the
safety repository; ``scripts/benchmarks/data.py`` loads the instance), in
the safety repository. The output goes to ``<instance>/notebooks/<name>.html``,
and ``notebooks.json`` has the digest of the inputs (the notebook and
``study.json``): with the same digest, the notebook does not run again.
The instance page links to the notebooks. The output is not byte-stable,
so ``analysis check`` does not compare it. The packages are in
``scripts/benchmarks/requirements-notebooks.lock``; the other commands do
not need them.

``analysis show`` and ``analysis missing`` read the instances at and below
the folder that you give (any folder of a results tree). They name each
instance by its folder below the results folder. The one line of an
instance gives the hypotheses in numbers (confirmed, wrong, open, and the
``draft`` checks), the central results with a sentence, the acceptance
checks that are not confirmed, the notes, the failed runs (a
``<UTC>.failed.json`` in the instance) and ``PROVISIONAL``. ``--details``
gives each check with its measured text, each central result with its
sentences or the reason why it has none, the failed runs, and for an open
manual check its statement and the ``instance verdict`` command that
closes it. ``analysis missing`` lists each experiment without an evidence
run in an instance, with the checks and central results that wait for it:
the runs to make next.

Other commands: ``instance add --role excluded --reason <text>``,
``instance exclude ROOT --campaign ID --reason TEXT`` (the role
``excluded`` for all runs of a campaign, for example a test of the tools;
the entry keeps the earlier role in ``role_before``),
``instance reference`` (a run of another instance that a check reads),
``instance seal``, ``instance verify``, and ``instance merge OTHER ROOT``: it adds the runs
of another results tree that ROOT does not have, with their roles, after
it checks their seals and digests. Use ``instance merge`` for a results
tree that is not in a lab space. Between two lab spaces, use ``study.py
lab export`` and ``study.py lab import`` (see :doc:`lab`). If OTHER is a
local copy, ``--origin HOST:PATH`` records the original tree in
``copied_from``.

``analysis build`` writes only derived files; it does not change a raw run or
``instance.json``. The same inputs and the same revision of the tools
give the same bytes: ``analysis check`` builds again and compares the JSON
files (``run.json``, the app data, ``experiment.json``, ``study.json``; not
the plots, the pages or the notebooks). Each aggregate
records the safety revision of the tools (``made_by``); ``dirty: true``
means that the tools had changes that were not committed.

.. _benchguide-check-forms:

Check forms
-----------

Metrics:

``irq``, ``isr2thr``, ``irq2thr``, ``t2t``, ...
   A latency histogram of the app.
``meta.<key>``
   A ``LAT META`` value (stat ``value``). ``meta.m4_masked_share`` is
   ``m4_masked_cyc / m4_window_cyc``; ``meta.used`` and ``meta.dropped``
   come from the ``LAT M4 BEGIN`` line.
``m4.<kind>[.<ctx>][<function>]``
   The M4 sites of a kind (``mask``, ``isr``), of a context (``t`` thread,
   ``e<n>`` exception n: ``e14`` PendSV, ``e15`` SysTick, ``e22`` IRQ 6)
   and of a function. A site has the function that starts the mask
   section and its inlined functions; ``<function>`` matches one of them.
no metric
   The point itself: ``drift_per_wake`` (``clock_drift_cyc / samples``),
   ``drift_ppm``.

Stats of a histogram: ``n``, ``min``, ``max``, ``mean``, ``invalid``,
``p<q>`` (``p50``, ``p99.99``; the lower edge of the bin that holds the
quantile, so in a coarse bin of width w the true value can be up to w - 1
higher), ``count_ge(x)`` (x must be a bin edge),
``mode_share(k)``. A mode is a group of fine bins that each hold at least
0.1 % of the samples, with at most 2 cycles between neighbours, numbered
by value (mode 1 is the fastest); ``mode_share(k)`` is its share of the
samples, 0 if there is no mode k. ``max(<stat>)`` and ``min(<stat>)`` are
the largest and smallest value over the selected points.

Stats of M4 sites: ``n`` (sum of the sections), ``max``, ``max_net``,
``min_net`` (net: minus the floor of the calibration), ``max(<x>)`` over
the sites, ``top_place`` (the function of the site with the largest
``max_net``).

``select``: ``{point: id | [ids]}``, ``{axes: {axis: value | [values]}}``
or ``{axis: value | [values]}``. A point that ``select`` names must be in
the data. An M4 metric with ``[function]`` must find that function in
some point of the experiment (else the name has a typo, or the build has
other code).

``expect`` has exactly one form (``ratio_to`` with ``range``, ``within``
with ``tolerance_bins``):

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Form
     - Confirmed if
   * - ``range: [lo, hi]``
     - each value is in lo..hi (``null``: no limit). A quantile in a coarse
       bin is in the range only if the whole bin is; if a limit is inside
       the bin, the check is not evaluated
   * - ``equals: x``
     - each value is x (``top_place``: x is the start function or one of
       its inlined functions)
   * - ``spread_le: x``
     - (max - min) / min over the selected points <= x (two points or
       more, all values above 0)
   * - ``spread_abs_le: x``
     - max - min over the selected points <= x (two points or more)
   * - ``order: [p1, p2, ...]``
     - the values increase in this order of points (each point must be
       there; equal values are wrong)
   * - ``order: {axis: [v1, v2, ...]}``
     - the values increase along these axis values, for each value of the
       other axes
   * - ``diff_to: {REF, range}``
     - value - the value of the reference is in the range
   * - ``diff_to: {REF, spread_abs_le: x}``
     - the differences (value - reference) over the selected points
       differ by x or less (two points or more)
   * - ``ratio_to: {REF, stat}`` + ``range``
     - value / the value of the reference is in the range
   * - ``diff_change: {point: P, of: [Q, R], range}``
     - (value - P) - (Q - R), in the same run and tree
   * - ``within: {experiment: E, stat: range}`` + ``tolerance_bins: k``
     - the value is in min..max of all points of E, +- k coarse bins
   * - ``hist_identical_to: {run, point}``
     - the histograms are the same, bin for bin (on the same tree, or on
       ``tree``)

REF is ``point: P``, ``axes: {axis: v}`` (the point with this axis value
and the same other axes), ``run: <study path>/<experiment>/<UTC>`` with
``point``, ``points: {selected: reference}`` and ``tree``,
``experiment: E, point: same`` (E must have one run with that point), or
``metric: M, stat: S`` (the same point). For ``max(<stat>)`` over the
points, the reference is that of the point that gives the max. A
``run:`` reference must not be excluded. The points of each run and tree
form a series; a check is confirmed only if it holds in each series, for
each metric and each stat.

A check that the data cannot give (no point, a quantile in the overflow
bin, a limit inside a coarse bin) is ``not evaluated``, with the reason.
An error of the tools gives ``tool error``. A check that has a ``TODO``
text, or whose hypothesis statement has one, is ``draft``: the build does
not evaluate it. None of the three is confirmed or wrong; the hypothesis
stays open. A study with a ``mode: rerun`` import
reads only its own runs of that experiment, never those of the owner.

.. _benchguide-central:

Central results
---------------

A central result is characterisation: measured values in a sentence. It
is an entry of ``central_results`` in ``study.yaml``:

``id``
   The name of the result.

``statement``
   The sentence, with blanks (placeholders) for the values.

``from``
   The data: ``experiment`` (or a list), ``point`` (or a list), ``axes``,
   ``exclude`` (point IDs), ``tree`` and ``metric`` (or a list). A
   ``conclusion`` has ``hypotheses`` instead. A result of a sub-study has
   ``substudy``.

``stat``
   What the build calculates from the data (see the table below).

``group_by``
   Only for an aggregate stat: the axes that divide the points into
   groups.

``unit``
   The unit of the values. The build copies it into ``study.json``.

The build calculates one or more rows from the data. A row is a set of
names with a value each. Then the build fills the statement once for
each row. Each filled statement is one sentence. Before it fills the
statement, the build joins its lines into one line.

``study.py analysis show ROOT --explain [ID ...]`` prints, for each central result
(or for the given IDs) of each instance below ``ROOT``: the definition,
each row, and the sentence of each row.

Placeholders
~~~~~~~~~~~~

A placeholder is a Python format field: ``{name}`` or ``{name:spec}``.
``name`` is a name of the row. ``spec`` is a Python format
specification:

- ``{p99:.0f}`` writes 41 for the value 41.0 (no decimals).
- ``{slope:.1f}`` writes 0.7 for the value 0.6791.
- ``{bound:.1e}`` writes 2.3e-06 for the value 0.00000231.
- ``{confidence:.0%}`` writes 95% for the value 0.95.

A name can have a dot or a hyphen, for example ``{p99.99}``. If the spec
does not fit the value (for example ``.0f`` for a text), the build writes
the value without the spec.

Each row has these names:

- ``board`` and ``instance``: the board and the instance path of the
  instance that the build makes.
- ``run``: the run ID, ``<experiment>/<UTC>``.
- ``tree``: the tree of the point.
- ``metric``: the metric of the row, if ``from`` has one.
- For a per-point stat: ``point`` (the point ID) and one name for each
  axis of the point, with the value name (for example ``path``,
  ``background``).
- For an aggregate stat: only the axes of ``group_by``, not ``point``.
- The names that the stat gives (table below).

A few stats give rows without ``run`` and ``tree`` (see the table).

.. list-table:: Names that each stat adds to a row
   :header-rows: 1
   :widths: 30 70

   * - ``stat``
     - Names in the row
   * - a stat or a list of stats (``p99``, ``[p99, p99.99]``, ``max``,
       ``mode_share(1)``, ``drift_per_wake``)
     - One name for each stat, with the value of the point:
       ``{p99}``, ``{p99.99}``.
   * - ``value`` (with ``meta.<key>`` metrics)
     - ``<key>`` for each metric (the name without ``meta.``), and
       ``value``. The row has no ``metric``.
   * - ``top_site``
     - ``max_net``, ``place`` (the function of the mask site with the
       largest ``max_net``, with ``(via ...)`` for inlined functions) and
       ``ctx``.
   * - ``phase_share_range``
     - ``min`` and ``max``: the smallest and the largest share of a phase
       bin (1 is uniform).
   * - ``hist_identical_count``
     - ``hist_identical_count`` (the points of the re-run with the same
       histograms as the point of the owner study) and ``n`` (the points
       with a point of the owner). One row, without ``run`` and ``tree``.
   * - ``{spread: [stats]}``
     - ``points`` (the points in the group), and for each stat its
       spread (max - min) / min over the group.
   * - ``{spread_abs: [stats]}``
     - ``points``, and for each stat max - min over the group.
   * - ``{slope: {stat, axis}}``
     - ``slope``, ``intercept`` and ``points``: the least-squares line of
       the stat over the ``value:`` numbers of the axis. A point whose axis
       value has no ``value:`` is not used. A group with fewer than two
       points gives no row.
   * - ``{fit_linear: {stat, x: [axes]}}``
     - As ``slope``. x is the sum of the ``value:`` numbers of the axes.
   * - ``{diff_rank: [stats]}``
     - ``stat``, ``first`` (the point with the largest change),
       ``first_diff`` (its change as an integer) and ``ranking`` (all
       points, ``<point> (+n)``). The change of a point is its value minus
       the value of the point with ``variant: baseline`` and the same
       other axes. One row for each metric, stat and series.
   * - ``{tree_diff: stat}``
     - ``tree_diff``: the value of ``ws-up`` minus the value of
       ``ws-safety``. One row for each point and metric, with ``point``,
       ``metric`` and the axes, without ``run`` and ``tree``.
   * - ``{ram_cost: [stats]}``
     - For each stat: the median over the points with a ``place`` value
       that starts with ``r``, minus the median over the points with a
       ``place`` value that starts with ``f``.
   * - ``{exceedance_bound: {thresholds: [..], confidence: c}}``
     - ``load_seed``, ``threshold``, ``count`` (the samples at or above the
       threshold), ``n``, ``bound`` (a one-sided Poisson upper bound of
       P(value >= threshold) per sample, rounded up to 3 digits) and
       ``confidence``. One row for each point, metric and threshold.
   * - ``conclusion``
     - No row (see below).

Rows of a per-point stat and of an aggregate stat
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A series is the points of one run on one tree. A per-point stat (a stat
or a list of stats, ``value``, ``top_site``, ``phase_share_range``,
``exceedance_bound``) gives one row for each point, metric and series.

An aggregate stat (``spread``, ``spread_abs``, ``slope``, ``fit_linear``,
``ram_cost``) puts the points into groups and gives one row for each
group and metric. There is one group for each series and each
combination of values of the ``group_by`` axes. Without ``group_by``, a
group is one series.

The statement does not change the groups. In a group, each axis that is
not in ``group_by`` has several values. Thus the statement of an
aggregate can name only the axes of ``group_by``. The lint finds these
errors (see :ref:`benchguide-lint`):

- The statement names an axis that is not in ``group_by``.
- ``group_by`` is on a stat that is not an aggregate.
- ``group_by`` names an axis that the experiment does not have.

Run and tree tag
~~~~~~~~~~~~~~~~

If the rows come from more than one run and the statement does not name
``{run}``, each sentence ends with the UTC time of its run. If the rows
come from more than one tree and the statement does not name
``{tree}``, each sentence ends with its tree. The tag has the form
``[<run UTC>, <tree>]``, with only the parts that apply.

Missing values
~~~~~~~~~~~~~~

If the data cannot give a value (no point for ``from``, a quantile in
the overflow bin, fewer than two points for a spread), the central
result has no sentence. It is ``not evaluated``, and ``not_evaluated``
in ``study.json`` gives the reason. An error of the tools gives ``not
evaluated`` with the reason ``tool error: ...``.

If a placeholder names a value that the row does not have, the build
keeps the placeholder in the sentence as it is. The name goes into the
list ``unfilled`` of the result. ``analysis show --explain`` prints this list.

Conclusion and sub-study
~~~~~~~~~~~~~~~~~~~~~~~~

``stat: conclusion`` is a sentence without data. ``from`` names the
hypotheses that the sentence is based on. The build does not fill
placeholders in a conclusion. The result has the verdict of each
hypothesis (``verdicts_of_hypotheses``) and the verdict ``open (a person
confirms the sentence)``. A person sets the verdict ``confirmed`` or
``wrong``:

.. code-block:: console

   scripts/benchmarks/study.py instance verdict <instance folder> --central-result <id> \
       --verdict confirmed --by "<name>"

``from: {substudy: <name>}`` shows the central result with the same
``id`` of the sub-study ``<name>``. The parent instance shows the
sentences, the rows and the verdict of the result of the child instance.
If the child has no result with this ``id``, the result is ``not
evaluated``.

Examples
~~~~~~~~

Each example gives the entry of ``study.yaml``, the rows of the build,
and the sentences. The rows and the sentences are the output of ``study.py
analysis show --explain`` on the results tree of the study (state of
2026-10-27).

A per-point stat with two runs. The entry is in
``st-default-latencies/st-irq-entry/study.yaml``:

.. code-block:: none

   - id: irq-entry-p99-direct
     statement: >
       With the board defaults and an idle CPU, the IRQ entry latency of
       the direct path has a p99 of {p99:.0f} cycles.
     from: {experiment: irq-baseline-1m, point: direct-idle, tree: ws-up, metric: irq}
     stat: p99
     unit: CPU cycles (170 MHz)

   rows (one for each point, metric and series):
     run=irq-baseline-1m/20261024T155016Z, tree=ws-up, point=direct-idle,
       path=direct, background=idle, metric=irq, p99=41
     run=irq-baseline-1m/20261026T223523Z, tree=ws-up, point=direct-idle,
       path=direct, background=idle, metric=irq, p99=55

   sentences:
     With the board defaults and an idle CPU, the IRQ entry latency of the
     direct path has a p99 of 41 cycles. [20261024T155016Z]
     With the board defaults and an idle CPU, the IRQ entry latency of the
     direct path has a p99 of 55 cycles. [20261026T223523Z]

The instance has two evidence runs of ``irq-baseline-1m``, and the
statement does not name ``{run}``. Thus each sentence ends with the UTC
time of its run. ``from`` selects one tree, so the tag has no tree.

An aggregate stat with ``group_by``. The entry is in
``st-load-scaling/st-timeout-queue-cost/study.yaml``:

.. code-block:: none

   - id: thread-slope
     statement: >
       With {kind} load threads, the isr2thr p99 grows by {slope:.1f}
       cycles per thread ({tree}).
     from: {experiment: wake-threads-1m, metric: isr2thr}
     stat: {slope: {stat: p99, axis: threads}}
     group_by: [kind]
     unit: cycles per thread

   rows (one for each series, value of kind and metric, 2 of 6):
     run=wake-threads-1m/20261025T004141Z, tree=ws-safety, metric=isr2thr,
       kind=blocked, slope=0.6791, intercept=1667, points=4
     run=wake-threads-1m/20261025T004141Z, tree=ws-safety, metric=isr2thr,
       kind=busy, slope=1.663, intercept=2067, points=4

   sentences:
     With blocked load threads, the isr2thr p99 grows by 0.7 cycles per
     thread (ws-safety).
     With busy load threads, the isr2thr p99 grows by 1.7 cycles per
     thread (ws-safety).

The other four rows are for ``kind=sleeper`` and for the tree ``ws-up``.
The statement names ``{tree}``, so the sentences have no tag. A group has
the four values of ``threads``. Thus ``{threads}`` in the statement is a
lint error.

A conclusion. The entry is in
``st-measurement-validity/st-clock-drift/study.yaml``:

.. code-block:: none

   - id: drift-cause
     statement: >
       Each SysTick reprogram loses about 8 cycles, and the gap
       compensation removes the drift. With many load timers, the driver
       also loses whole reloads when the shortest reload is too short.
     from: {hypotheses: [H1, H2]}
     stat: conclusion

   rows: none

   sentence:
     Each SysTick reprogram loses about 8 cycles, and the gap compensation
     removes the drift. With many load timers, the driver also loses whole
     reloads when the shortest reload is too short.

   study.json: verdict "open (a person confirms the sentence)",
     verdicts_of_hypotheses {H1: open, H2: open}

.. _benchguide-provisional:

Provisional verdicts
--------------------

In a lab space, a campaign runs the experiments one after the other, and
the build of the results tree runs after each run (see :doc:`lab`).
Thus a build can come before the last run of an experiment. A verdict of
such a build is provisional.

A check of a hypothesis or a central result is provisional if it reads
an experiment that a running campaign of the lab space has still to run.
This includes an experiment that the study imports with ``mode: reuse``.
``study.json`` then has these entries:

- The key ``provisional`` on the check and on the central result, with
  the reason (``waits for <experiment> of the campaign <id>``).
- ``"provisional": true`` on a hypothesis with a provisional check.
- ``state``: ``{final, waits}``. ``final`` is ``false`` if a result of the
  instance is provisional. ``waits`` lists the reasons.

A campaign of this lab space counts while its record has the status
``planned`` (its pre-flight check) or ``running`` and it holds the locks of
its boards; a campaign whose process stopped does not count. An imported
campaign record of another lab space counts while it has the status
``running`` (not after ``lab import --close``). ``study.py analysis show``, ``study.py analysis html`` and
``scripts/benchmarks/data.py`` mark the provisional verdicts.
