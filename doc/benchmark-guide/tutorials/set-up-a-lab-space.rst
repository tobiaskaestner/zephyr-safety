.. _benchguide-tut-lab:

Set up a lab space
==================

.. admonition:: Prerequisites

   - A Linux host with Python 3.12 or later, git, CMake, Ninja and
     ``openocd``.
   - The Zephyr SDK of the pinned trees (1.0.1) in ``~/zephyr-sdk-1.0.1``.
   - A NUCLEO-G474RE on a USB port of the host, with a wire from D2 to A3
     (see :doc:`../howto/wire-the-nucleo-g474re`).
   - Network access to PyPI for the Python packages, and to the Zephyr
     repositories if you have no local clones of them.
   - git with a user identity (``git config user.name`` and ``git config
     user.email``). The tutorial :doc:`your-own-study` makes a commit.

A :term:`lab space` is a folder that holds everything of one host that a
study needs and that the safety repository must not hold: the pinned
trees, the Python environment, the hardware map, the results and the
build cache. In this tutorial, you make the lab space
``/wrk/z/lab-tutorial``. Use a folder of your own.

Make the folder and clone the safety repository
-----------------------------------------------

.. code-block:: console

   $ mkdir lab-tutorial && cd lab-tutorial && git clone -q <safety repository> safety && git -C safety log --oneline -1
   df1a5d8 validation: trees: ws-safety removed; lab init names the how-to

The clone is the :term:`design repository` of the lab space. It has the
study designs and the tools. The tools of the lab space always come from
this clone.

Make the Python environment
---------------------------

.. code-block:: console

   $ python3 -m venv .venv && .venv/bin/pip install -q --disable-pip-version-check -r safety/scripts/benchmarks/requirements.lock && echo installed
   installed

``requirements.lock`` has the exact versions of the packages: those of
the scripts, and those that the Zephyr build needs.

Write the hardware map
----------------------

The hardware map tells the tools the probe and the console of each board.
Find the console of the board in the list of the serial devices:

.. code-block:: console

   $ /bin/ls -l /dev/serial/by-id/ | grep STLINK
   lrwxrwxrwx 1 root root 13 Oct 26 11:31 usb-STMicroelectronics_STLINK-V3_0042003F3433510A37363934-if02 -> ../../ttyACM1

The console of the ST-LINK has a name of the form
``usb-STMicroelectronics_STLINK-V3_<serial>-if02``. The long hex
``<serial>`` is the probe ID. Write ``hw-map.yml`` in the lab folder,
with your console name and your probe ID:

.. code-block:: yaml

   - connected: true
     id: 0042003F3433510A37363934
     platform: nucleo_g474re
     product: STLINK-V3
     runner: openocd
     serial: /dev/serial/by-id/usb-STMicroelectronics_STLINK-V3_0042003F3433510A37363934-if02
     baud: 115200
     fixtures:
       - latbench_loopback

The fixture ``latbench_loopback`` says that the wire D2 to A3 is there.
See :doc:`../howto/make-a-hardware-map` for the details.

Make the lab space
------------------

``lab init`` can clone the trees from local clones. ``--trees-source``
names a folder of local clones, with the layout ``<folder>/<tree>/<path>``,
for example the trees root of another lab space. If you have no local
clones, leave out ``--trees-source``. Then the trees come from their
URLs.

Run ``lab init`` in the lab folder with the Python of the environment:

.. code-block:: console

   $ .venv/bin/python safety/scripts/benchmarks/study.py lab init --repo safety --trees-source /wrk/z/latency-trees-src
   lab space lab-tutorial-332eb106 in /wrk/z/lab-tutorial
     design repo  /wrk/z/lab-tutorial/safety
     python       /wrk/z/lab-tutorial/.venv (the Python of lab init)
     trees        /wrk/z/lab-tutorial/trees (clone from /wrk/z/latency-trees-src)
     results      /wrk/z/lab-tutorial/results
     hardware map /wrk/z/lab-tutorial/hw-map.yml
   next: cd /wrk/z/lab-tutorial && /wrk/z/lab-tutorial/safety/scripts/benchmarks/study.py trees setup <tree>

``lab init`` writes ``.lab/config``. It records the Python environment.
From now on, each ``study.py`` in the lab folder runs with that Python.
This is also true if you start it with the Python of the system (see
:doc:`../reference/files/lab-config`).

Set up the pinned tree
----------------------

A :term:`tree` is a pinned set of repositories: Zephyr and its modules.
The experiments of this tutorial use the tree ``ws-up``:

.. code-block:: console

   $ safety/scripts/benchmarks/study.py trees setup ws-up
   ws-up: west workspace /wrk/z/lab-tutorial/trees/ws-up
   ws-up/zephyr: ec98918869ca (from /wrk/z/latency-trees-src/ws-up)
   ws-up/cmsis_6: 1c1840af7a7e (from https://github.com/zephyrproject-rtos/CMSIS_6)
   ws-up/hal_stm32: c95501991862 (from https://github.com/zephyrproject-rtos/hal_stm32)
   ws-up/hal_nordic: c708b9fe1b7a (from https://github.com/zephyrproject-rtos/hal_nordic)
   ws-up/hal_nxp: a8b437ef366f (from https://github.com/zephyrproject-rtos/hal_nxp)

Each tree is a west workspace of its own, with exactly the pinned
revisions of ``validation/trees/ws-up.yml``.

Look at the lab space
---------------------

.. code-block:: console

   $ safety/scripts/benchmarks/study.py lab status
   lab space lab-tutorial-332eb106 in /wrk/z/lab-tutorial
     design repo  /wrk/z/lab-tutorial/safety at df1a5d8c69ad
     python       /wrk/z/lab-tutorial/.venv/bin/python (/wrk/z/lab-tutorial/.venv)
     zephyr sdk   /home/tobias/zephyr-sdk-1.0.1 (1.0.1)
     tree ws-up                ok
     tree ws-up-driftfix       not set up
     tree ws-up-irqoff         not set up
     results      /wrk/z/lab-tutorial/results
     board        nucleo_g474re: connected, fixtures latbench_loopback

The trees that you did not set up are information, not errors.

Check the wire
--------------

The :term:`wire check` builds a small app, flashes the board, and measures
the wire:

.. code-block:: console

   $ safety/scripts/benchmarks/study.py lab hwcheck nucleo_g474re
   nucleo_g474re: build loopback_check (ws-up)
   nucleo_g474re: flash, probe 0042003F3433510A37363934, console /dev/serial/by-id/usb-STMicroelectronics_STLINK-V3_0042003F3433510A37363934-if02
     *** Booting Zephyr OS build v4.5.0-rc3-40-gec98918869ca ***
     loopback_check: 170000000 Hz core, timing 170 MHz
     static: drive 0, read 0 OK
     static: drive 1, read 1 OK
     irq: n=1000 missed=0 min=344 avg=344 max=344 cycles
     RESULT: OK
   nucleo_g474re: loopback wire ok; record /wrk/z/lab-tutorial/.lab/hwcheck/history/nucleo_g474re/20261029T131311Z.json

If you see ``RESULT: FAIL``, look at the wire D2 to A3 (see
:doc:`../howto/troubleshoot-a-run`). The record keeps all lines of the
wire check.

You have a lab space that works. Next: :doc:`first-experiment`.
