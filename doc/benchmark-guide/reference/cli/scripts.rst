Host scripts
============

The folder ``scripts/benchmarks/`` has the host tools.

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Script
     - Purpose
   * - ``study.py``
     - :term:`Study` designs (lint, scaffold), lab spaces, pinned :term:`trees <Tree>`, :term:`campaigns <Campaign>`,
       run lists and the aggregates of a results tree (see
       :doc:`study-py`).
   * - ``run.py``
     - Runs an :term:`experiment` from pinned, clean trees and records its
       provenance (see :doc:`run-py`).
   * - ``latbench.py``
     - Captures, parses and summarizes the ``LAT`` output.
   * - ``plot.py``
     - Plots the distributions from the logs.
   * - ``m4.py``
     - Prints the tables of the M4 sites of a log.
   * - ``loadmodel.py``
     - Calculates the ticks on which several periodic load timers expire.
   * - ``trees.py``
     - The library of the pinned trees of ``validation/trees/``. It has
       no commands of its own: use ``study.py trees``. It reads
       ``boards.yaml`` for ``run.py``.
   * - ``hwmap.py``
     - The library that reads the hardware map (no commands).
   * - ``data.py``
     - The library that loads a built :term:`instance` for a notebook (no
       commands).

Python packages
---------------

The tools need Python 3 and the packages of
``scripts/benchmarks/requirements.txt``. This file gives the ranges of
``pyserial``, ``PyYAML``, ``matplotlib``, ``jsonschema``, ``packaging``
and ``west``. ``scripts/benchmarks/requirements.lock`` gives the exact
versions. It also has the Python packages of the Zephyr build
(``pyelftools`` and others) and ``pyocd``. A :term:`lab space` installs
the versions of ``requirements.lock`` (see :doc:`../files/lab-config`).

``latbench.py summary``, ``latbench.py parse``, ``m4.py`` and
``loadmodel.py`` use only the standard library of Python.
``latbench.py capture`` needs ``pyserial``.

Summary and parse (``latbench.py``)
-----------------------------------

.. code-block:: console

   scripts/benchmarks/latbench.py summary [--json | --md] [--hist H]... [--meta KEY]... LOG ...
   scripts/benchmarks/latbench.py parse LOG
   scripts/benchmarks/latbench.py capture [--port P] [--baud B] [--timeout S] [--flash BUILD_DIR] [--runner R] [--echo] OUT

``summary``
   Prints one row for each histogram of each log. The columns are
   ``log``, ``variant``, ``hist``, ``n``, ``min``, ``p50``, ``p90``, ``p99``,
   ``p99.9``, ``p99.99``, ``max``, ``mean``, ``sd``, ``ovf`` and ``inv``.
   ``inv`` is the number of invalid :term:`samples <Sample>` (see :ref:`benchguide-hist`).
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
   that the buffer of the host does not overflow. ``--port`` gives the
   serial port (default ``/dev/ttyACM0``), ``--baud`` the baud rate
   (default 115200), ``--timeout`` the maximum time in seconds (default
   600). ``--flash`` gives the build folder to flash, ``--runner`` the
   runner of ``west flash`` (default ``openocd``). ``--echo`` prints the lines without the
   ``BIN`` and ``OVF`` lines. This command is for development only. Its
   results are unpinned.

Plots (``plot.py``)
-------------------

.. code-block:: console

   scripts/benchmarks/plot.py ccdf  --out f.svg [--title T] [--label L]... [--hist H] LOG ...
   scripts/benchmarks/plot.py hist  --out f.svg [--title T] [--label L]... [--hist H] LOG ...
   scripts/benchmarks/plot.py phase --out f.svg [--title T] [--label L]... [--hist H] LOG ...
   scripts/benchmarks/plot.py sweep --out f.svg --x KEY [--series KEY]... [--title T] [--hist H] LOG ...

``ccdf``
   The exceedance probability P(latency > x), on log scales, with one line
   for each log. It shows the floor, the modes and the tail in one chart.

``hist``
   One panel for each log, with the sample count of each bin on a log
   scale. A coarse bin shows its count per cycle.

``phase``
   Two panels for each log, by the tick phase of the edge: the share of
   the samples (1 is uniform), and the minimum, mean and maximum latency.

``sweep``
   One panel for each statistic (``p50``, ``p99``, ``p99.99``, ``max``).
   Each panel shows the statistic against the numeric key ``--x``, with
   one line for each value of ``--series``. A key is ``meta:<META key>``,
   ``cfg:<CFG symbol>`` or ``tree`` (from the path of the run folder).
   Give ``--series`` more than once to combine keys. A quantile in an
   overflow bin shows at its lower bound, a quantile in a coarse bin at
   the lower edge of the bin.

``--hist`` selects the histogram (or the phase histogram) by name. The
default is the first one in each log. ``--label`` gives the label of the
next log. The default label is ``<tree>/<point>`` from the path of the log.
A chart can have a maximum of 8 logs. ``plot.py`` gives the number of
invalid samples in the label. In a log from before the ``invalid=`` field,
it leaves out the overflow bin 31.

Load timer model (``loadmodel.py``)
-----------------------------------

.. code-block:: console

   scripts/benchmarks/loadmodel.py run  [--seed S] [--timers N] [--min-ms A] [--max-ms B] [--ticks-per-sec F]
                                        [--seconds T] [--parts P] [--json]
   scripts/benchmarks/loadmodel.py scan [--timers N] [--min-ms A] [--max-ms B] [--ticks-per-sec F] [--seconds T] [SEED ...]
   scripts/benchmarks/loadmodel.py log  [--parts P] LOG

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

M4 tables (``m4.py``)
---------------------

.. code-block:: console

   scripts/benchmarks/m4.py table [--elf ELF] [--binutils PREFIX] [--no-names] [--top N] [--md | --json] LOG
   scripts/benchmarks/m4.py sweep [--md | --json] LOG ...

``table``
   Prints one table for the mask sections and one for the ISR bodies,
   sorted by max. It finds the function and the source line of each site
   with ``addr2line`` and ``nm`` of the SDK in the run manifest. The ELF
   is the ``.elf`` file next to the log (``<app>-<tree>-<point>.elf``, or
   ``zephyr.elf`` in an older run). For an inlined lock, ``place`` is the
   line in the real function, and ``via`` lists the inlined functions
   between.

   ``--elf`` gives another ELF. ``--binutils`` gives the prefix of ``nm``
   and ``addr2line`` (default: from the run manifest). ``--no-names``
   prints the addresses without function names. ``--top N`` prints only
   the first N sites of each kind. ``--md`` prints Markdown tables,
   ``--json`` prints JSON.

``sweep``
   Prints one row for each log: the calibration, the masked share of the
   window, the longest mask section and ISR body, and the IRQ tail of the
   same run.

Example:

.. code-block:: console

   python3 scripts/benchmarks/m4.py table <run>/ws-up-irqoff/<point>/rep1.log --top 20
   python3 scripts/benchmarks/m4.py sweep <run>/ws-up-irqoff/*/rep1.log --md

:doc:`../../explanation/mask-time` describes the M4 method.
