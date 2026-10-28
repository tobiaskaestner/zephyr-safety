Run an experiment (``run.py``)
==============================

.. code-block:: console

   scripts/benchmarks/run.py validation/empirical/latencies/st-<study>/ex-<name>/experiment.yaml --out <dir>

In a lab space, a campaign runs ``run.py`` for each experiment (see
:doc:`../../explanation/campaigns`).

Options:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Option
     - Meaning
   * - ``--out <dir>``
     - The folder for the results (necessary, but not with
       ``--build-only`` or ``--dry-run``).
   * - ``--only ID ...``
     - Run only the points with these IDs.
   * - ``--dry-run``
     - Do the checks and list the points. Do not build.
   * - ``--build-only``
     - Build each point. Do not flash. In a lab space, the images go into
       the build cache. Outside a lab space, the builds go to a temporary
       folder.
   * - ``--no-cache``
     - Do not use the build cache of the lab space: build each point
       again, and do not store the image in the cache.
   * - ``--warn-as-error``
     - Stop before the build if the design lint finds a problem (error or
       warning) in the experiment or in its study (see
       :ref:`benchguide-lint`). Without it, ``run.py`` prints the problems
       and continues.
   * - ``--keep-build``
     - Keep the build folder of each point. With the build cache of a lab
       space, the build is in a work folder of the cache and the cache
       keeps only the files of an entry, so ``--keep-build`` keeps nothing
       there (use ``--no-cache``). With ``--rebuild``, the builds stay in
       the temporary folder of the rebuild.
   * - ``--role``, ``--reason``
     - The role of the run in the run list of an instance (``evidence``,
       ``adjustment``, ``excluded``; the default is ``evidence``, and a
       run of some points with ``--only`` must name it) and the reason of
       a role other than ``evidence``. ``run.py`` checks the role, the
       reason and the instance (the experiment of its study, the board)
       before the first build.
   * - ``--campaign``
     - The id of the campaign that starts the run, for the run-list
       entry. A run without it takes the board lock of the lab space.
   * - ``--rebuild <run>``
     - Build the points of an old run again and compare them with the
       stored files (see :ref:`benchguide-rebuild`). ``<run>`` is a run
       folder or one ``<run>/<tree>/<point>`` folder. Use it without an
       experiment and without ``--out``. ``--only`` selects points.
   * - ``--hardware-map <file>``
     - The hardware map (default: ``[hardware] map`` of the lab space,
       else ``tests/benchmarks/hw-map.yml``, see :ref:`benchguide-hw-map`).
   * - ``--probe <id>``
     - Select the map entry with this probe ID, if the map has more than
       one entry for the board. With ``--port``, ``run.py`` uses no map.
   * - ``--port <dev>``
     - The serial port (default: ``serial`` of the map entry).
   * - ``--trees-root <dir>``
     - Override the trees root of the lab space (also
       ``LATBENCH_TREES_ROOT``).

``run.py`` does these steps:

#. **Checks.** It makes sure that the safety repository is clean and that
   the experiment file is in it. In a lab space, the design repository of
   the lab space must be this repository. It runs the design lint for the
   experiment and its study (see :ref:`benchguide-lint`). It finds the board target (``board:`` of
   the experiment, or ``default`` of ``boards.yaml``). It makes sure that
   the SDK is as pinned. For each tree of the experiment, it makes sure
   that the tree pins ``zephyr`` and the modules of the board. Then it
   makes sure that these repositories are as pinned. Other repositories of the tree are
   not examined. Then it expands the points.
   An axis value name that YAML reads as a Boolean (``on``, ``off``,
   ``yes``, ``no``, ``true``, ``false``) stops the run.
#. **Hardware.** It selects the entry of the board in the hardware map
   (see :ref:`benchguide-hw-map`). Without one connected entry with the
   fixture ``latbench_loopback``, the run stops before it builds.

#. **Sources and build.** :doc:`../../explanation/reproducibility` describes these
   two steps.

#. **Kconfig check.** It compares each Kconfig value of the point with the
   ``.config`` of the build. If the ``.config`` does not have the requested
   value, the run stops. Kconfig can ignore a value without an error
   (see :doc:`../../explanation/measurement-effects`).
#. **Flash and capture.** For each repetition, it opens the serial port
   and runs the ``flash`` commands of the board in order. Then it saves the
   output until ``LAT DONE``. If no ``LAT DONE`` comes before the timeout,
   or the flash fails, the run stops.
#. **Summary.** It writes ``summary.txt`` with the percentiles of each
   histogram, one column per axis, and prints how many images came from
   the build cache.
#. **Seal and run list.** It writes the seal. If ``--out`` is the folder
   of a study instance, it adds the run to the run list of the instance,
   with ``--role`` (default ``evidence``) and ``--reason``. ``--campaign
   ID`` names the campaign in the entry. It prints ``run <id> added to the
   instance <folder>``.

``run.py`` writes ``manifest.json`` at the start and updates it after each
repetition. Thus a run that stops still has a manifest for the completed
repetitions. A run that stops before its seal (an error, Ctrl-C or
SIGTERM) writes ``<UTC time>.failed.json`` beside its folder: the step
(for example ``flash and capture ws-safety/stock-idle rep 1``), the error
and the last 20 lines of the log of that step. Such a run is not in a run
list, so the results build and the export do not see it.
