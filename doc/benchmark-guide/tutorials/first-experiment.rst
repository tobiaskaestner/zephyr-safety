Your first experiment
=====================

.. admonition:: Prerequisites

   The lab space of :doc:`set-up-a-lab-space`, with the tree ``ws-up``
   and a wire check that gives ``RESULT: OK``.

An :term:`experiment` is a file ``experiment.yaml``: an app, the trees and
the points to measure. In this tutorial you run the experiment
``irq-smoke`` once with ``run.py`` alone, outside a study, and you look at
what it makes. The commands run in the lab folder.

See the points
--------------

``--dry-run`` checks the repository and the trees and lists the points.
It builds nothing:

.. code-block:: console

   $ safety/scripts/benchmarks/run.py safety/validation/empirical/latencies/st-default-latencies/st-irq-entry/ex-irq-smoke/experiment.yaml --dry-run
   safety df1a5d8c69ad  trees ws-up  5 points x 1
     stock-idle: {'LATBENCH_IRQ_PATH_STOCK': 'y'} [] []
     wrapped-idle: {'LATBENCH_IRQ_PATH_WRAPPED': 'y'} [] []
     direct-idle: {'LATBENCH_IRQ_PATH_DIRECT': 'y'} [] []
     zli-idle: {'LATBENCH_IRQ_PATH_ZLI': 'y'} [] []
     direct-busy: {'LATBENCH_IRQ_PATH_DIRECT': 'y', 'LATBENCH_BG_BUSY': 'y'} [] []

Each :term:`point` is one build of the app with these Kconfig values. The
four IRQ paths run on an idle CPU, and the direct path also on a busy CPU.

Run it
------

``--out`` names the parent folder of the run: the run folder is
``<out>/<experiment>/<UTC time>/``. The run takes about five minutes. It
builds each point, flashes the board and reads 100000 samples:

.. code-block:: console

   $ safety/scripts/benchmarks/run.py safety/validation/empirical/latencies/st-default-latencies/st-irq-entry/ex-irq-smoke/experiment.yaml --out tryout
   safety df1a5d8c69ad  trees ws-up  5 points x 1
   [...]
   board nucleo_g474re: probe 0042003F3433510A37363934 (STLINK-V3), console /dev/serial/by-id/usb-STMicroelectronics_STLINK-V3_0042003F3433510A37363934-if02
   run folder /wrk/z/lab-tutorial/tryout/irq-smoke/20261029T131326Z
   [ws-up/stock-idle] build
   [ws-up/stock-idle] rep 1
   [...]
   [ws-up/direct-busy] build
   [ws-up/direct-busy] rep 1
                           log     path  background  hist       n  min  p50  p90  p99  p99.9  p99.99   max    mean     sd  ovf  inv
     ws-up/stock-idle/rep1.log    stock        idle   irq  100000  228  228  228  255    255    1072  1790  228.51  13.55    0    0
   ws-up/wrapped-idle/rep1.log  wrapped        idle   irq  100000   74   86   86   91     91    1091  1566   86.29   15.3    0    0
    ws-up/direct-idle/rep1.log   direct        idle   irq  100000   54   55   55   59     59     863  1433   55.23  13.79    0    0
       ws-up/zli-idle/rep1.log      zli        idle   irq  100000   50   55   55   59     59      59    62   55.04   0.44    0    0
    ws-up/direct-busy/rep1.log   direct        busy   irq  100000   38   50   54   56     58    1525  2019   51.79  25.98    0    0

   images: 0 of 5 from the build cache
   results in /wrk/z/lab-tutorial/tryout/irq-smoke/20261029T131326Z  (sha256:ac1005a2c121df660c734f81699526ff8b5596db8ffad710a9143a9fb4d5b95f)

The table has one row for each point: the axes (``path``,
``background``) and the percentiles of the IRQ entry latency in core
cycles. The last line gives the :term:`seal` digest of the run.

Look at the run folder
----------------------

.. code-block:: console

   $ find tryout/irq-smoke/20261029T131326Z -maxdepth 3 | sort
   tryout/irq-smoke/20261029T131326Z
   tryout/irq-smoke/20261029T131326Z/manifest.json
   tryout/irq-smoke/20261029T131326Z/summary.txt
   tryout/irq-smoke/20261029T131326Z/ws-up
   tryout/irq-smoke/20261029T131326Z/ws-up/direct-busy
   tryout/irq-smoke/20261029T131326Z/ws-up/direct-busy/.config
   tryout/irq-smoke/20261029T131326Z/ws-up/direct-busy/build.log
   tryout/irq-smoke/20261029T131326Z/ws-up/direct-busy/irq_latency-ws-up-direct-busy.elf
   tryout/irq-smoke/20261029T131326Z/ws-up/direct-busy/irq_latency-ws-up-direct-busy.hex
   tryout/irq-smoke/20261029T131326Z/ws-up/direct-busy/rep1.log
   tryout/irq-smoke/20261029T131326Z/ws-up/direct-busy/zephyr.dts
   [...]

Each point folder has the image (named after the app, the tree and the
point), the ``.config``, the devicetree, the build log and the serial log
of each repetition. ``manifest.json`` records where everything came from:

.. code-block:: console

   $ python3 -m json.tool tryout/irq-smoke/20261029T131326Z/manifest.json | head -20
   {
       "experiment": "irq-smoke",
       "experiment_file": "validation/empirical/latencies/st-default-latencies/st-irq-entry/ex-irq-smoke/experiment.yaml",
       [...]
       "safety": {
           "path": "/wrk/z/lab-tutorial/safety",
           "rev": "df1a5d8c69adb010ba73111fbab3382d4a6fbf4d",
           "ref": "refs/latbench/run/irq-smoke/20261029T131326Z",
           "bench_tree": "5370dca36e46ecabd4626ecdbebddb7a8fe707d4",
           "bench_tree_kind": "firmware/1",
           "module_tree": "0f8dd9da43bb60aba06c67e2183156b4ffcd7e17"

The commit of the safety repository, the pins of the trees, the SDK, the
tools and the CMake command of each point are in the manifest (see
:doc:`../reference/files/results-tree`). The ref
``refs/latbench/run/irq-smoke/<UTC>`` keeps the commit in the clone, so
you can build the run again later (:doc:`audit-a-result`).

Plot the distributions
----------------------

.. code-block:: console

   $ safety/scripts/benchmarks/plot.py ccdf --out irq-smoke-ccdf.svg --title 'irq-smoke: IRQ entry latency' tryout/irq-smoke/20261029T131326Z/ws-up/*/rep1.log
   saved irq-smoke-ccdf.svg

.. figure:: irq-smoke-ccdf.svg
   :width: 100%

   The share of the samples at or above each latency (an example; your
   values are different). The floor, the modes and the tail of each point
   are in one chart.

A run with ``--out`` outside a study is a try-out: no study reads it. The
next tutorial runs the same experiment as part of its study.
:doc:`../reference/cli/run-py` gives all options of ``run.py``, and
:doc:`../reference/cli/scripts` those of ``plot.py`` and ``latbench.py``.

Next: :doc:`first-campaign`.
