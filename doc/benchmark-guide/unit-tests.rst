Unit tests
==========

The unit tests find errors in the histogram code, in the code placement,
in the host scripts and in the experiment files. They do not use the
board. ``unit/README.md`` gives the full commands.

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
   * - ``scripts/tests/test_latbench.py``
     - A pytest module for ``scripts/latbench.py`` and ``scripts/plot.py``
   * - ``scripts/tests/test_run.py``
     - A pytest module for the rebuild functions of ``scripts/run.py``
   * - ``scripts/tests/test_experiments.py``
     - A pytest module that checks the experiment files
   * - ``scripts/tests/fixtures/hist_*.log``
     - The console output of the ztest app, one log for each scenario

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

Run pytest in the ``scripts`` folder. It needs the packages in
``scripts/requirements.txt`` and ``pytest``:

.. code-block:: console

   cd tests/benchmarks/scripts
   python3 -m pytest tests

``test_latbench.py`` has tests of the parser, the percentiles, the standard
deviation, the mean without invalid samples, and the plot values. Its
round-trip tests read the fixtures. They make the same pseudo-random
samples as the ztest app, and compare the parsed log with values from
these samples.

``test_experiments.py`` reads each file in ``experiments/``. A code pad
must have ``LATBENCH_CODE_FLASH_PAD`` or ``LATBENCH_CODE_RAM``, and must
be a multiple of 4. A point must select at most one code placement.
``LATBENCH_CODE_RAM`` needs a port with ``Kconfig.port``. Kconfig only
warns about such errors, and ``run.py`` finds them only after the build.

If you change the output format or the sample generator
``fixture_sample()`` of the ztest app, make the fixtures again.
``unit/README.md`` gives the procedure.

Known gaps
----------

A test for a known defect asserts the correct behavior. While the defect
is in the code, the test is an expected failure:

- In the ztest app, ``KNOWN_GAP()`` skips the test and prints
  ``KNOWN GAP:`` with the input and the result. If the result becomes
  correct, the test fails. Then remove ``KNOWN_GAP()`` from the test.
- In pytest, the test has ``xfail(strict=True)``. If the test passes,
  pytest reports a failure. Then remove the marker.

``unit/README.md`` lists the open gaps. Two gaps are open today:

- ``lat_phase_add()`` does not make sure that the phase is less than the
  period. A larger phase writes after the last bin.
- In ``lat_hist_print()``, ``sum * 100`` wraps at 2\ :sup:`64`. This occurs
  only if the sum is more than 1.8e17 cycles.
