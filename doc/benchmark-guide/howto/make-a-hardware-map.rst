Make a hardware map
===================

The hardware map tells the tools the probe and the console of each board
on the host. :doc:`../reference/files/hw-map` gives its format and how
``run.py`` uses it. In a :term:`lab space`, the map is ``[hardware] map``
of ``.lab/config``, by default ``<lab folder>/hw-map.yml``.

#. Connect the boards to the host.
#. List the serial devices by their ``by-id`` names:

   .. code-block:: console

      /bin/ls -l /dev/serial/by-id/

   Each name is stable. It does not change when you connect the boards in
   a different sequence. Do not use ``/dev/ttyACM<n>``.
#. Find the console of each board in the list. For an ST-LINK, the name
   has the form
   ``usb-STMicroelectronics_STLINK-V3_<serial>-if02``. The long hex
   ``<serial>`` is the probe ID.
#. Write one entry for each board in the map:

   .. code-block:: yaml

      - connected: true
        id: 0042003F3433510A37363934
        platform: nucleo_g474re
        product: STLINK-V3
        runner: openocd
        serial: /dev/serial/by-id/usb-STMicroelectronics_STLINK-V3_0042003F3433510A37363934-if02
        baud: 115200
        fixtures:
          - latbench_loopback:D2-A3

#. Set ``platform`` to the board target of ``boards.yaml`` (see
   :doc:`../reference/files/boards-yaml`).
#. If the board has the loopback wire, add the fixture
   ``latbench_loopback``. A text after a colon is a note, for example
   ``latbench_loopback:D2-A3``.
#. If a probe has more than one serial port (the J-Link OB of the Nordic
   DKs), write the entry of the console port only. Write the reason in
   ``notes``.
#. In a lab space, look at the board line of ``study.py lab status``. It
   must show the board as connected, with its fixtures.

In a west workspace, twister can write the first version of the map:

.. code-block:: console

   west twister --generate-hardware-map hw-map.yml --persistent-hardware-map

``--persistent-hardware-map`` writes the serial ports as
``/dev/serial/by-id/...`` names. If the file exists, twister updates it
and keeps the other entries. Then do the steps 5 to 7.
