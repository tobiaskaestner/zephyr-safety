Host scripts
============

Summary and parse (``latbench.py``)
-----------------------------------

.. code-block:: console

   scripts/benchmarks/latbench.py summary [--json | --md] [--hist H]... [--meta KEY]... LOG ...
   scripts/benchmarks/latbench.py parse LOG
   scripts/benchmarks/latbench.py capture [--flash BUILD_DIR] [--runner openocd] [--port P] [--timeout S] [--echo] OUT

``summary``
   Prints one row for each histogram of each log. The columns are
   ``log``, ``variant``, ``hist``, ``n``, ``min``, ``p50``, ``p90``, ``p99``,
   ``p99.9``, ``p99.99``, ``max``, ``mean``, ``sd``, ``ovf`` and ``inv``.
   ``inv`` is the number of invalid samples (see :ref:`benchguide-hist`).
   ``mean`` does not include them. A percentile
   in an overflow bin shows as ``>=2^e`` (for example ``>=8192``). A
   percentile in a coarse bin shows the lower edge of the bin. ``sd`` is
   ``nan`` if samples are in overflow bins. ``--json`` prints the rows as
   JSON. ``--md`` prints a Markdown table. ``summary`` does not include the
   phase histograms.

   ``--hist H`` shows only the histogram ``H``. Give it more than once for
   more histograms. ``--meta KEY`` adds the ``LAT META`` value ``KEY`` as a
   column. The key ``drift_ppm`` is calculated: ``clock_drift_cyc`` divided
   by ``clock_elapsed_cyc``, in parts per million. It is empty if
   ``clock_drift_cyc`` is ``n/a``.

   A log from before the ``invalid=`` field has the invalid samples in the
   overflow bin 31. ``summary`` then counts them in ``inv``. If all other
   samples are in bins, it calculates ``mean`` again from the bins without
   them.

``parse``
   Prints the last record of a log as JSON: ``meta``, ``cfg``, ``hists``,
   ``phases`` and ``errors``.

``capture``
   Flashes a build with ``west flash`` (optional) and saves the serial
   output until ``LAT DONE``. The script reads the port all the time, so
   that the buffer of the host does not overflow. This command is for
   development only. Its results are unpinned.

Plots (``plot.py``)
-------------------

.. code-block:: console

   scripts/benchmarks/plot.py ccdf  --out f.svg [--title T] [--label L]... [--hist H] LOG ...
   scripts/benchmarks/plot.py hist  --out f.svg [--title T] [--label L]... [--hist H] LOG ...
   scripts/benchmarks/plot.py phase --out f.svg [--title T] [--label L]... [--hist H] LOG ...

``ccdf``
   The exceedance probability P(latency > x), on log scales, with one line
   for each log. It shows the floor, the modes and the tail in one chart.

``hist``
   One panel for each log, with the sample count of each bin on a log
   scale. A coarse bin shows its count per cycle.

``phase``
   Two panels for each log, by the tick phase of the edge: the share of
   the samples (1 is uniform), and the minimum, mean and maximum latency.

``--hist`` selects the histogram (or the phase histogram) by name. The
default is the first one in each log. ``--label`` gives the label of the
next log. The default label is ``<tree>/<point>`` from the path of the log.
A chart can have a maximum of 8 logs. ``plot.py`` gives the number of
invalid samples in the label. In a log from before the ``invalid=`` field,
it leaves out the overflow bin 31.

Load timer model (``loadmodel.py``)
-----------------------------------

.. code-block:: console

   scripts/benchmarks/loadmodel.py run  [--seed S] [--timers N] [--min-ms A] [--max-ms B] [--seconds T] [--parts P]
   scripts/benchmarks/loadmodel.py scan [--timers N] ... [SEED ...]
   scripts/benchmarks/loadmodel.py log  LOG

The periodic load timers of ``common/src/load.c`` get their periods and
first expiries from the seed ``LATBENCH_LOAD_TIMER_SEED``. They do not
depend on the stimulus. Thus each run with the same seed has the same
ticks with k expiries. The system timer ISR processes the k expiries one
after the other, so these ticks are the long ISRs of the run. A different
stimulus seed gives only new edges on the same ticks. A longer run or a
different load seed gives new ticks.

``run``
   For one seed: the number of ticks with k expiries, the time of the
   first tick with at least k expiries, and the counts in each of P parts
   of the run.

``scan``
   For each seed (the default is the 64 SHA-256 round constants): the
   number of ticks with at least k expiries. Use it to select load seeds
   by a rule, not by hand.

``log``
   Reads the timer parameters, the seed and the run length from the
   ``LAT META`` lines of a log, and compares the expiries of the model
   with ``load_timer_expiries``. The model starts the timers at tick 0, so
   the two numbers can differ by a few expiries.
