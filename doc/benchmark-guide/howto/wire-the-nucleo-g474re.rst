Hardware setup on the NUCLEO-G474RE
===================================

:doc:`../reference/boards` gives the pins and the wire of the other boards.

- One NUCLEO-G474RE board.
- One USB cable to the ST-LINK connector of the board. The ST-LINK gives
  the flash interface and the console (``/dev/ttyACM0``, 115200 baud).
- One wire from D2 to A3 on the Arduino header.

.. list-table::
   :header-rows: 1
   :widths: 15 15 70

   * - Header pin
     - MCU pin
     - Function
   * - D2
     - PA10
     - Stimulus pin. PA10 is also TIM2 channel 4. TIM2 is the stimulus
       timer.
   * - A3
     - PB0
     - Response pin. PB0 is on EXTI line 0, which has its own interrupt
       vector (``EXTI0_IRQn``).

The port sets up TIM2 as follows (``common/boards/nucleo_g474re/port.c``):

- The prescaler is 0, and the auto-reload value is ``UINT32_MAX``. TIM2
  counts each cycle of its clock and wraps after 2\ :sup:`32` cycles.
- TIM2 runs at the core clock. A ``BUILD_ASSERT`` makes sure that the AHB
  prescaler and the APB1 prescaler are 1.
- Channel 4 is in output compare mode, without preload, with active-high
  polarity.

Make sure that the wire is connected before you start a run. Each app with
the stimulus does a static check at start-up (see
:ref:`benchguide-static-check`). If the static check fails, the app prints
``LAT ERROR`` and stops.

To do a test of the wire alone, build and flash ``loopback_check``. Use
these commands in the root folder of the safety repository, in a west
workspace:

.. code-block:: console

   west build -b nucleo_g474re -d build/loopback_check tests/benchmarks/loopback_check
   west flash -d build/loopback_check -r openocd

If the wire is good, the console shows ``RESULT: OK``. The
``loopback_check`` app is also a Twister test with a console harness.
