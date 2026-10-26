.. _benchguide-studies:

Studies and their results
=========================

A study asks one verification question. It names the experiments that
answer it, the hypotheses that were written before the runs, and the
central results that state the answer. This page describes the files of
a study design, the results tree, the tool ``scripts/benchmarks/study.py``
and the forms that a check can use.

Terms
-----

Study
   A folder with ``study.yaml``. The top study is
   ``validation/empirical/latencies/`` itself. A study can have
   sub-studies (folders ``st-<name>/``) and experiments (folders
   ``ex-<name>/``). A sub-study is a study.

Experiment
   A folder ``ex-<name>/`` with ``experiment.yaml`` (the input of
   ``run.py``, see :doc:`host-tools`) and ``experiment.md`` (question,
   method, references). The study that holds the folder owns the
   experiment. Another study can import it (``imports:``).

Instance
   One study design, applied to one board, in a results tree. Its folder
   has ``instance.json``: the run list, the roles of the runs, the
   references and the manual verdicts. The run list is hand-made data.

Run
   One raw run folder of ``run.py``: ``ex-<experiment>/<UTC>/`` in the
   folder of its instance. The run folder does not change after the run.
   Its seal ``<UTC>.sha256`` is beside it: one line ``<sha256>  <path>``
   for each file. The digest of the run is ``sha256:`` + the sha256 of
   the seal file.

The prefixes ``st-`` and ``ex-`` are only in the folder names. Names and
references in the files have no prefix: a study path is a path of names
(``load-scaling/t2t-under-load``), a run id is ``<experiment>/<UTC>``.

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
     - ``{id, statement, from, stat, unit}``: see :ref:`benchguide-central`.

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
axes, the digests of ``.config``, ``zephyr.dts``, ``zephyr.elf``,
``zephyr.hex`` and ``build.log``, the image digest (the loadable
segments of the ELF) and the code digest. The image has the safety
revision of the build (``LATBENCH_SRC_REV``), so the same code at two
revisions gives two image digests; the code digest counts these 40
characters as zeros, so the same code gives the same code digest. The app data come from the extractor of the app,
``tests/benchmarks/<app>/scripts/extract.py``: META, the histograms, the
tick phase tables, the M4 sites, and a check of the ``LAT CFG`` values
against ``.config``.

``experiment.json`` has one row for each run, tree, point, repetition and
metric, with the percentiles. ``study.json`` has the acceptance checks,
the rebuild checks, the hypotheses with each check (measured value,
limit, verdict) and the central results as filled sentences.

The tool study.py
-----------------

.. code-block:: console

   # once: the instance folders of a study for a board
   scripts/benchmarks/study.py new <results> load-scaling --board nucleo_g474re
   # a run goes into its instance folder, then into the run list
   scripts/benchmarks/run.py <experiment.yaml> --out <instance folder>
   scripts/benchmarks/study.py add <instance folder> <run folder>
   # an old run from another place: copy it in (the original stays)
   scripts/benchmarks/study.py add <instance folder> <old run folder> --copy
   # the aggregates, and a check that they come again from the same inputs
   scripts/benchmarks/study.py build <results>/kernel-latency
   scripts/benchmarks/study.py check <results>/kernel-latency
   scripts/benchmarks/study.py show <results>/kernel-latency --brief
   scripts/benchmarks/study.py html <results>/kernel-latency   # one HTML page: index.html
   # a manual verdict (a person, or a proposal that says so in --by)
   scripts/benchmarks/study.py verdict <instance folder> --hypothesis H3 --check h \
       --verdict wrong --by "<name>" --text "<why>"

Other commands: ``add --role excluded --reason <text>``, ``reference``
(a run of another instance that a check reads), ``seal``, ``verify``, and
``merge OTHER ROOT``: it adds the runs of another results tree (for
example a copy of the tree of the lab host) that ROOT does not have, with
their roles, after it checks their seals and digests.

``build`` writes only derived files; it does not change a raw run or
``instance.json``. The same inputs and the same revision of the tools
give the same bytes: ``check`` builds again and compares. Each aggregate
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
An error of the tools gives ``tool error``. Neither is confirmed or
wrong; the hypothesis stays open. A study with a ``mode: rerun`` import
reads only its own runs of that experiment, never those of the owner.

.. _benchguide-central:

Central results
---------------

A central result is characterisation: measured values in a sentence.
``statement`` has ``{placeholders}``; the build fills it once for each
row of values. A placeholder is a stat name, an axis name, ``tree``,
``point``, ``metric``, ``run``, ``board``, or a name that the stat gives.
``from`` names the data (``experiment``, ``point``, ``axes``,
``exclude``, ``tree``, ``metric``), the hypotheses of a ``conclusion``, or a
``substudy`` whose central result of the same id the parent shows.

``stat``: a stat (or a list), ``value``, ``top_site``, ``conclusion`` (a
person confirms the sentence with ``study.py verdict --central-result``),
``phase_share_range``, ``hist_identical_count`` (re-runs against the run
of the owner study), ``{spread: [stats]}``, ``{spread_abs: [stats]}``,
``{slope: {stat, axis}}``, ``{fit_linear: {stat, x: [axes]}}`` (over the
``value:`` numbers of the axes), ``{diff_rank: [stats]}`` (the variants
by their change against ``baseline``), ``{tree_diff: stat}``
(``ws-up`` - ``ws-safety``), ``{ram_cost: [stats]}``,
``{exceedance_bound: {thresholds, confidence}}`` (a one-sided Poisson
upper bound of P(value >= threshold) per sample). For an aggregate stat,
the points form one group for each series and each value of the axes
that the statement names. If the sentences come from more than one run or
tree and the statement does not name them, each sentence ends with
``[<run>, <tree>]``.
