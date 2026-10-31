Audit a result
==============

.. admonition:: Prerequisites

   The campaign of :doc:`first-campaign`.

An auditor asks two questions about a result: is the data the data of the
run, and does the source of the run give the same image? In this
tutorial you answer both for the run of ``irq-smoke`` from
:doc:`first-campaign`.

The run list
------------

.. code-block:: console

   $ python3 -m json.tool results/kernel-latency/st-default-latencies@nucleo_g474re/st-irq-entry/instance.json | sed -n '/"runs"/,/]/p'
       "runs": [
           {
               "id": "irq-smoke/20261029T131938Z",
               "digest": "sha256:a219a528a03a43489deec81a62d511811d49800c2b030a38d2108210729352c7",
               "role": "evidence",
               "campaign": "20261029T131933Z"
           }
       ],

The run list of the instance names each run with its digest, its
:term:`role` and its campaign. Only the runs of this list count.

The seal
--------

.. code-block:: console

   $ safety/scripts/probatrix/study.py instance verify results/kernel-latency/st-default-latencies@nucleo_g474re/st-irq-entry/ex-irq-smoke/20261029T131938Z
   sha256:a219a528a03a43489deec81a62d511811d49800c2b030a38d2108210729352c7 results/kernel-latency/st-default-latencies@nucleo_g474re/st-irq-entry/ex-irq-smoke/20261029T131938Z
   $ head -3 results/kernel-latency/st-default-latencies@nucleo_g474re/st-irq-entry/ex-irq-smoke/20261029T131938Z.sha256
   cd52e47c5e9feb387e2184149d79a6d32a882c5b2f083d70198f7c0621b0501b  manifest.json
   c3ac24a96e54e39f4a50d4ec371bae972e95ad3bdc988d7a95843ea7c1843417  summary.txt
   3e676427c8e0c4661b1577cf54d316b37a3d8e00883b8b0fa454bb3e646e4470  ws-up/direct-busy/.config

``instance verify`` computes the SHA-256 of each file of the run folder
again and compares it with the :term:`seal`. A changed file, a changed
log or a missing image gives an error. The command prints the digest of
the run. It does not read the run list. Compare the digest with
``digest`` of the run entry in ``instance.json``: the two must be the
same.

The source
----------

The manifest names the commit of the run, and a local ref keeps it:

.. code-block:: console

   $ git -C safety log --oneline -1 refs/latbench/run/irq-smoke/20261029T131938Z
   df1a5d8 validation: trees: ws-safety removed; lab init names the how-to

``run.py --rebuild`` builds each point again from that commit (in a
temporary folder; the run folder does not change) and compares the
images:

.. code-block:: console

   $ safety/scripts/probatrix/benchmarks/run.py --rebuild results/kernel-latency/st-default-latencies@nucleo_g474re/st-irq-entry/ex-irq-smoke/20261029T131938Z
   rebuild /wrk/z/lab-tutorial/results/kernel-latency/st-default-latencies@nucleo_g474re/st-irq-entry/ex-irq-smoke/20261029T131938Z  5 points
   [ws-up/stock-idle] same: same ELF image, zephyr.hex, .config, zephyr.dts; different zephyr.elf
   [ws-up/wrapped-idle] same: same ELF image, zephyr.hex, .config, zephyr.dts; different zephyr.elf
   [ws-up/direct-idle] same: same ELF image, zephyr.hex, .config, zephyr.dts; different zephyr.elf
   [ws-up/zli-idle] same: same ELF image, zephyr.hex, .config, zephyr.dts; different zephyr.elf
   [ws-up/direct-busy] same: same ELF image, zephyr.hex, .config, zephyr.dts; different zephyr.elf
   5 of 5 points give the same image and .config
   record: /wrk/z/lab-tutorial/results/kernel-latency/st-default-latencies@nucleo_g474re/st-irq-entry/ex-irq-smoke/20261029T131938Z.rebuild-20261029T132753Z.json

The flashed image (the ``.hex`` file and the loadable parts of the ELF),
the ``.config`` and the devicetree are the same (see
:doc:`../explanation/decisions/0003-build-from-the-repository` and
:doc:`../explanation/decisions/0004-firmware-hash`). The ELF file itself is
different only in its debug information, which has the path of the build
folder. The record of the rebuild goes beside the run folder.

The aggregates
--------------

The rebuild record is an input of the study results. Check the results
now:

.. code-block:: console

   $ safety/scripts/probatrix/study.py analysis check results/kernel-latency
   FAIL: 1 files differ from a new build:
      /wrk/z/lab-tutorial/results/kernel-latency/st-default-latencies@nucleo_g474re/st-irq-entry/study.json
   note: 1 inputs are newer than the last build (for example st-default-latencies@nucleo_g474re/st-irq-entry/ex-irq-smoke/20261029T131938Z.rebuild-20261029T132753Z.json); after 'study.py analysis build' the check compares again

The check fails because the last build did not have the rebuild record.
The note names the new input. Build the results, then check again:

.. code-block:: console

   $ safety/scripts/probatrix/study.py analysis build results/kernel-latency | head -1
   built 6 instances, 2 runs; 12 files written
   $ safety/scripts/probatrix/study.py analysis check results/kernel-latency
   ok: 2 runs agree with their seals; the build gives the same 6 study.json files

``analysis check`` checks each seal and builds all aggregates again in
memory: the same runs and the same tools give the same bytes. Thus each
verdict comes from the sealed runs and nothing else.

:doc:`../howto/reproduce-a-data-point` gives the steps to reproduce a
data point, also the measurement.

Next: :doc:`combine-two-labs`.
