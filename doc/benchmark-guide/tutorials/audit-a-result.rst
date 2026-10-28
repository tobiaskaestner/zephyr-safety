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

   $ python3 -m json.tool results/kernel-latency/st-default-latencies@nucleo_g474re/st-irq-entry/instance.json | sed -n "/\"runs\"/,/]/p"
       "runs": [
           {
               "id": "irq-smoke/20261028T015416Z",
               "digest": "sha256:17aa3ddb5f5d66404bff0f7cca8914a1d23dd17c0582916f29b11c9d605590a5",
               "role": "evidence",
               "campaign": "20261028T015411Z"
           }
       ],

The run list of the instance names each run with its digest, its
:term:`role` and its campaign. Only the runs of this list count.

The seal
--------

.. code-block:: console

   $ safety/scripts/benchmarks/study.py instance verify results/kernel-latency/st-default-latencies@nucleo_g474re/st-irq-entry/ex-irq-smoke/20261028T015416Z
   sha256:17aa3ddb5f5d66404bff0f7cca8914a1d23dd17c0582916f29b11c9d605590a5 results/kernel-latency/st-default-latencies@nucleo_g474re/st-irq-entry/ex-irq-smoke/20261028T015416Z
   $ head -3 results/kernel-latency/st-default-latencies@nucleo_g474re/st-irq-entry/ex-irq-smoke/20261028T015416Z.sha256
   060d3d5056e62a3544d6cd5146597c7320513b2c479132f362324fd3087805b2  manifest.json
   aa1dd3a5365e6c5cb08d827d156b55760cc9a77fdc6138a48ba8165e8d1daf0e  summary.txt
   a2844fe0b792dffa4b90d5207d2a70802385a3bdb7781e2ae9e4b352ee84c9f3  ws-safety/direct-busy/.config

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

   $ git -C safety log --oneline -1 refs/latbench/run/irq-smoke/20261028T015416Z
   8ac1023 validation: latencies: the yaml comments name the new guide pages

``run.py --rebuild`` builds each point again from that commit (in a
temporary folder; the run folder does not change) and compares the
images:

.. code-block:: console

   $ safety/scripts/benchmarks/run.py --rebuild results/kernel-latency/st-default-latencies@nucleo_g474re/st-irq-entry/ex-irq-smoke/20261028T015416Z
   rebuild /wrk/z/lab-tutorial/results/kernel-latency/st-default-latencies@nucleo_g474re/st-irq-entry/ex-irq-smoke/20261028T015416Z  5 points
   [ws-safety/stock-idle] same: same ELF image, zephyr.hex, .config, zephyr.dts; different zephyr.elf
   [ws-safety/wrapped-idle] same: same ELF image, zephyr.hex, .config, zephyr.dts; different zephyr.elf
   [ws-safety/direct-idle] same: same ELF image, zephyr.hex, .config, zephyr.dts; different zephyr.elf
   [ws-safety/zli-idle] same: same ELF image, zephyr.hex, .config, zephyr.dts; different zephyr.elf
   [ws-safety/direct-busy] same: same ELF image, zephyr.hex, .config, zephyr.dts; different zephyr.elf
   5 of 5 points give the same image and .config
   record: /wrk/z/lab-tutorial/results/kernel-latency/st-default-latencies@nucleo_g474re/st-irq-entry/ex-irq-smoke/20261028T015416Z.rebuild-20261028T020310Z.json

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

   $ safety/scripts/benchmarks/study.py analysis check results/kernel-latency
   FAIL: 1 files differ from a new build:
      /wrk/z/lab-tutorial/results/kernel-latency/st-default-latencies@nucleo_g474re/st-irq-entry/study.json
   note: 1 inputs are newer than the last build (for example st-default-latencies@nucleo_g474re/st-irq-entry/ex-irq-smoke/20261028T015416Z.rebuild-20261028T020310Z.json); after 'study.py analysis build' the check compares again

The check fails because the last build did not have the rebuild record.
The note names the new input. Build the results, then check again:

.. code-block:: console

   $ safety/scripts/benchmarks/study.py analysis build results/kernel-latency | head -1
   built 6 instances, 2 runs; 12 files written
   $ safety/scripts/benchmarks/study.py analysis check results/kernel-latency
   ok: 2 runs agree with their seals; the build gives the same 6 study.json files

``analysis check`` checks each seal and builds all aggregates again in
memory: the same runs and the same tools give the same bytes. Thus each
verdict comes from the sealed runs and nothing else.

:doc:`../howto/reproduce-a-data-point` gives the steps to reproduce a
data point, also the measurement.

Next: :doc:`combine-two-labs`.
