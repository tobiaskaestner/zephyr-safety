Wire the NUCLEO-G474RE
======================

You need:

- One NUCLEO-G474RE board.
- One USB cable to the ST-LINK connector of the board. The ST-LINK gives
  the flash interface and the console (115200 baud).
- One wire.

:ref:`benchguide-board-nucleo` gives the pins, the stimulus timer and the
other facts of the board port.

#. Connect the wire from D2 to A3 on the Arduino header. D2 (PA10) is the
   stimulus pin. A3 (PB0) is the response pin.
#. Connect the USB cable to the host.
#. Find the console of the board. Its name has the form
   ``usb-STMicroelectronics_STLINK-V3_<serial>-if02``:

   .. code-block:: console

      /bin/ls -l /dev/serial/by-id/

#. Add the board to the hardware map, with the fixture
   ``latbench_loopback`` (see :doc:`make-a-hardware-map`).
#. In a lab space, do the :term:`wire check`:

   .. code-block:: console

      safety/scripts/probatrix/study.py lab hwcheck nucleo_g474re

   If the wire is good, the console shows ``RESULT: OK``.

Each app with the stimulus also does a static check of the wire at
start-up (see :ref:`benchguide-static-check`). If the static check fails,
the app prints ``LAT ERROR`` and stops.

Outside a lab space, you can do a test of the wire alone with
``loopback_check``. Use these commands in the root folder of the safety
repository, in a west workspace:

.. code-block:: console

   west build -b nucleo_g474re -d build/loopback_check tests/benchmarks/loopback_check
   west flash -d build/loopback_check -r openocd

The ``loopback_check`` app is also a Twister test with a console harness.
