.. _benchguide-boards-yaml:

Boards (``boards.yaml``)
========================

``boards.yaml`` has these keys:

``default``
   The board target of an experiment without ``board:``
   (``nucleo_g474re``).

``boards.<board target>``
   One entry for each board target, with these keys:

   ``port``
      The folder of the board port in ``common/boards/``.

   ``modules``
      The repositories of the tree that the build needs. The build gets
      exactly these as ``ZEPHYR_MODULES``.

   ``flash``
      A list of commands that program the board and reset it. ``run.py``
      runs them in order. In each argument, ``{zephyr}`` is the Zephyr of
      the tree, ``{elf}`` and ``{hex}`` are the images of the point, and
      ``{probe}`` is the probe ID from the hardware map. Each command must
      select the probe with ``{probe}``: a host can have more than one
      probe.

   ``status``
      ``tested`` if data points exist, ``untested`` if the board only
      builds.

Example (the entry of the NUCLEO-G474RE):

.. code-block:: yaml

   nucleo_g474re:
     port: nucleo_g474re
     modules: [cmsis_6, hal_stm32]
     flash:
       - [openocd, -f, "{zephyr}/boards/st/nucleo_g474re/support/openocd.cfg",
          -c, "adapter serial {probe}", -c, "program {elf} verify reset exit"]
     status: tested

``boards.yaml`` has no serial port and no probe ID. These belong to the
host. They are in the hardware map.
