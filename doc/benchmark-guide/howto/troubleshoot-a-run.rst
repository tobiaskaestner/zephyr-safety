Troubleshoot a run
==================

Find the symptom in the left column. The right column gives the cause and
what to do. The pages that the table names give the details.

The run does not start
----------------------

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Symptom
     - Cause and action
   * - ``safety repo ... is dirty, commit first``
     - The design repository has changes that are not committed. Commit
       them (on a branch), or remove them. A run must name the exact
       source of its images (see :doc:`../explanation/decisions/0002-pinned-clean-trees`).
   * - ``... is at <rev>, pinned rev is <rev>``, ``... is dirty`` (a tree)
     - A repository of a tree is not at its pin or has changes. Do not
       change files in a tree. ``study.py trees check`` names the
       repository.
   * - ``... is not a west workspace yet`` or ``not set up``
     - Run ``study.py trees setup <tree>``.
   * - ``.west/config has build.cmake-args`` (or another key)
     - Somebody ran ``west config`` in the tree. Remove the key with
       ``west config -d <key>`` in the tree folder.
   * - ``Zephyr SDK at ... is <version>, pinned version is ...``
     - Install the pinned SDK, and set ``[toolchain] zephyr_sdk`` in
       ``.lab/config`` (see :doc:`../reference/files/lab-config`).
   * - ``unknown key 'repat' (did you mean 'repeat'?)``
     - A key of a design file is misspelled. ``study.py design lint``
       lists all of them (see :doc:`../reference/lint-rules`).
   * - ``the campaign <id> runs on <board>``
     - Another campaign (or its ``run.py``) holds the board. Wait, or look
       at ``study.py campaign status``. A campaign whose process is gone
       says so. Its ``run.py`` can still hold the board until it ends.
   * - ``No module named 'yaml'`` (or another package)
     - The command does not run with the Python of the lab space. Run it
       in the lab folder. Check ``[python] venv`` with ``study.py lab
       status``, and install ``requirements.lock`` into that venv.
   * - ``no hardware map ...``
     - The lab space has no hardware map. Write it (see
       :doc:`make-a-hardware-map`).
   * - ``no connected entry for board ...``, ``has no fixture
       'latbench_loopback'``
     - The hardware map has no usable entry for the board. Set
       ``connected: true``, the board target in ``platform`` and the
       fixture ``latbench_loopback`` (see :doc:`../reference/files/hw-map`).
   * - ``RESULT: FAIL`` (wire check)
     - The loopback wire does not connect the stimulus pin and the
       response pin. Look at the wire and at the pins of the board (see
       :doc:`../reference/boards`). The record of the wire check in
       ``.lab/hwcheck/`` has all console lines.
   * - ``a run of some points (--only) into an instance needs --role``
     - Name the role of the partial run: ``--role adjustment --reason
       TEXT`` (or ``evidence``).

The run stops
-------------

A run that stops before its seal writes ``<UTC>.failed.json`` beside its
folder. This file has the step, the error and the end of the log of that
step (see :doc:`../reference/cli/run-py`). ``study.py analysis show --details``
lists such runs as ``FAILED RUN``.

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Symptom
     - Cause and action
   * - ``build failed for <tree>/<point>``
     - Read the build log that ``failed.json`` names. In a lab space, it
       is ``.lab/build-cache/work/<key>.log``.
   * - ``Kconfig values not applied``
     - The tree ignores a Kconfig value of the point (a dependency is not
       met, or the option does not exist in the tree). See
       :doc:`../explanation/measurement-effects`, "Kconfig ignores some
       requested values".
   * - No ``LAT DONE`` before the timeout
     - The board does not answer or the run needs more time. Check the
       console in ``rep<N>.log``, the wire (``study.py lab hwcheck``) and
       ``timeout`` of the experiment.
   * - ``RESULT: FAIL`` of the wire check
     - The wire from D2 to A3 is loose or on other pins (see
       :doc:`wire-the-nucleo-g474re`). The record in
       ``.lab/hwcheck/history/<board>/`` has all console lines.

The data looks wrong
--------------------

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Symptom
     - Cause and action
   * - Negative samples (``inv`` is not 0), an acceptance check ``A1``
       wrong
     - The time stamps are wrong. See :doc:`../explanation/measurement-effects`,
       "Negative samples" and "Late edges".
   * - A long tail on all points, a drift of the tick
     - See :doc:`../explanation/measurement-effects`: the cycle counter, the
       SysTick wrap, the debug register bits of a debugger.
   * - The same settings give other values in another experiment
     - The place of the code changes the latency (see
       :doc:`../explanation/code-placement`). Compare the code digests of
       the runs (``run.json``).

The results look wrong
----------------------

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Symptom
     - Cause and action
   * - ``not evaluated: no evidence run of <experiment>``
     - The instance has no run of the experiment yet. ``study.py analysis
       missing`` lists the runs to make.
   * - ``draft``
     - The check or its hypothesis still has a ``TODO`` text of a
       template.
   * - ``PROVISIONAL``
     - A campaign that runs still has to run an experiment that the check
       reads. The build after the end makes it final.
   * - ``analysis check``: ``FAIL: ... files differ``
     - The tree has a new input since the last build, for example a
       rebuild record, a run or a verdict. ``analysis check`` names the
       newer files. Run ``study.py analysis build``, then run ``study.py
       analysis check`` again.
   * - ``instance of study ... for board ...: 2 found``
     - The results tree has two instances of one study for one board (made
       with ``instance new`` at two levels). Keep one.
