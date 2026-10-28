Make a hardware map
===================

:doc:`../reference/files/hw-map` describes the map and how ``run.py`` uses it.

Make the map with twister, from a Zephyr tree, on the host with the
boards:

.. code-block:: console

   west twister --generate-hardware-map tests/benchmarks/hw-map.yml --persistent-hardware-map

``--persistent-hardware-map`` writes the serial ports as
``/dev/serial/by-id/...`` names. These names do not change when the
boards are connected in a different sequence. Use them, not
``/dev/ttyACM<n>``. If the file exists, twister updates it and keeps the
other entries.

Then edit each entry:

- Set ``platform`` to the board target of ``boards.yaml``.
- Add the fixture ``latbench_loopback`` if the board has the wire. A text
  after a colon is a note, for example ``latbench_loopback:D2-A3``.
- If a probe has more than one serial port (the J-Link OB of the Nordic
  DKs), twister writes one entry for each port. Keep the entry of the
  console port, and write the reason in ``notes``.

Example:

.. code-block:: yaml

   - connected: true
     id: 0042003F3433510A37363934
     platform: nucleo_g474re
     product: STLINK-V3
     runner: openocd
     serial: /dev/serial/by-id/usb-STMicroelectronics_STLINK-V3_0042003F3433510A37363934-if02
     fixtures:
       - latbench_loopback:D2-A3
