Run the unit tests
==================

The unit tests find errors in these parts: the histogram code, the code
placement, the M4 site table, the host scripts and the design files. They
do not use the board. ``unit/README.md`` gives the full commands.

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Path
     - Content
   * - ``unit/hist/``
     - A ztest app for ``common/include/latbench/hist.h`` and
       ``common/src/hist.c``
   * - ``unit/code_place/``
     - A ztest app for the code placement (``LATBENCH_CODE_PLACE``)
   * - ``unit/irqmask/``
     - A ztest app for the M4 site table
   * - ``scripts/probatrix/benchmarks/tests/test_*.py``
     - The pytest modules of the host tools (list below)
   * - ``scripts/probatrix/benchmarks/tests/fixtures/``
     - The console output of the ztest apps, one log for each scenario

The ztest app
-------------

The app builds only the histogram code (``hist.c``), not ``meta.c`` and not
the stimulus. It sources ``common/Kconfig``. It runs on
``native_sim/native/64`` and on ``mps2/an385`` (Cortex-M3 in QEMU). Its
``testcase.yaml`` has three scenarios:

.. list-table::
   :header-rows: 1
   :widths: 40 15 25 20

   * - Scenario
     - Fine bins
     - Coarse bins
     - Phase bins
   * - ``latbench.unit.hist.fine``
     - 4096
     - 0
     - 64
   * - ``latbench.unit.hist.coarse``
     - 16
     - 4 of 4 cycles
     - 8
   * - ``latbench.unit.hist.experiment``
     - 2048
     - 2048 of 32 cycles
     - 64

The ``experiment`` scenario has the sizes of the experiments with 1 million
samples.

To run the app, set ``ZEPHYR_BASE`` to the Zephyr of a pinned tree, set the
SDK, and run Twister. Put the output folder outside the pinned trees:

.. code-block:: console

   $ZEPHYR_BASE/scripts/twister -T tests/benchmarks/unit/hist \
     -p native_sim/native/64 -p mps2/an385 \
     -x ZEPHYR_MODULES=$ZEPHYR_BASE/../modules/hal/cmsis_6 \
     -O <output folder>

The code placement app
----------------------

``unit/code_place`` uses ``common/latbench.cmake`` and runs on
``mps2/an385``, a Cortex-M3 in QEMU with an ARMv7-M MPU, as on the G474.
Its ``testcase.yaml`` has three scenarios:

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Scenario
     - Kconfig
   * - ``latbench.unit.code_place.flash``
     - The default (``LATBENCH_CODE_FLASH``)
   * - ``latbench.unit.code_place.flash_pad``
     - ``LATBENCH_CODE_FLASH_PAD``, pad 8
   * - ``latbench.unit.code_place.ram``
     - ``LATBENCH_CODE_RAM``, region ``RAM``, pad 8

The tests check the ``code_place`` and ``code_pad`` lines, the place of
the pad and of one function of each relocated group, and that
``z_cstart()`` and ``z_arm_mpu_init()`` stay in flash with the region
``RAM``. A third test makes a thread switch, a timeout and an interrupt
with the MPU stack guard on. If the build relocates ``kernel/init.c``
with the region ``RAM``, the ``ram`` scenario does not boot (a timeout in
Twister).

.. code-block:: console

   $ZEPHYR_BASE/scripts/twister -T tests/benchmarks/unit/code_place \
     -p mps2/an385 \
     -x ZEPHYR_MODULES=$ZEPHYR_BASE/../modules/hal/cmsis_6 \
     -O <output folder>

The pytest modules
------------------

#. Install ``pytest`` into the Python environment that has the packages
   of ``scripts/probatrix/benchmarks/requirements.txt``. In a lab space, this is the
   environment of the lab space.
#. In the root folder of the safety repository, run pytest:

   .. code-block:: console

      python3 -m pytest scripts/probatrix/benchmarks/tests -q

The folder ``scripts/probatrix/benchmarks/tests/`` has these modules:

- ``test_buildcache.py``: the build cache (``studylib/buildcache.py``).
- ``test_campaign.py``: the plan of a campaign, the instances that it
  makes and the experiments that wait.
- ``test_cli.py``: the command line of ``study.py``. Each command of
  ``study.py`` must have a synopsis line in
  :doc:`../reference/cli/study-py`.
- ``test_exchange.py``: the export and the import of runs.
- ``test_experiments.py``: the design of the repository has no lint
  errors, and the code pad of ``wake-code-layout`` is correct.
- ``test_hwmap.py``: the hardware map and its use in ``run.py``.
- ``test_latbench.py``: the parser, the percentiles, the standard
  deviation, the mean without invalid samples, and the plot values of
  ``latbench.py`` and ``plot.py``. Its round-trip tests read the fixtures
  ``hist_*.log``. They make the same pseudo-random samples as the ztest
  app, and compare the parsed log with values from these samples.
- ``test_lint.py``: the design lint on small designs.
- ``test_loadmodel.py``: ``loadmodel.py``.
- ``test_m4.py``: ``m4.py``, with the fixtures ``m4_*.log`` (the output
  of ``unit/irqmask`` on ``native_sim/native/64``).
- ``test_run.py``: the rebuild functions of ``run.py``.
- ``test_studylib.py``: seals, values, check forms, central results and a
  build.
- ``test_trees.py``: ``trees setup`` with local git repositories.

If you change the output format or the sample generator
``fixture_sample()`` of the ztest app, make the fixtures again.
``unit/README.md`` gives the procedure.

The M4 ztest app
----------------

``unit/irqmask/`` tests the site table: the bins, the entries, a full
table and the print format. Run it as the other ztest apps, with
``-T tests/benchmarks/unit/irqmask``.

Known gaps
----------

A test for a known defect asserts the correct behavior. While the defect
is in the code, the test is an expected failure:

- In the ztest app, ``KNOWN_GAP()`` skips the test and prints
  ``KNOWN GAP:`` with the input and the result. If the result becomes
  correct, the test fails. Then remove ``KNOWN_GAP()`` from the test.
- In pytest, the test has ``xfail(strict=True)``. If the test passes,
  pytest reports a failure. Then remove the marker.

``unit/README.md`` lists the open gaps.
