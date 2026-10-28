Results tree
============

.. code-block:: none

   results/kernel-latency/                         top instance (no board)
     instance.json  study.json
     st-measurement-validity/
       st-stimulus-sampling@nucleo_g474re/         the board is fixed here
         instance.json  study.json
         ex-stim-seed-1m/
           experiment.json
           20261026T155715Z/                       raw run (sealed)
           20261026T155715Z.sha256                 seal
           20261026T155715Z.run.json               framework data
           20261026T155715Z.wake_latency.json      app data
           20261026T155715Z.rebuild-<UTC>.json     a rebuild check (run.py --rebuild)

The board is in the folder name only at the level that fixes it
(``@<port>``); the sub-instances inherit it.

``run.json`` has the run identity and provenance, and for each point its
axes, the digests of ``.config``, ``zephyr.dts``, the images
(``<app>-<tree>-<point>.elf`` and ``.hex``, or ``zephyr.elf`` and
``zephyr.hex`` in an older run) and ``build.log``, the image digest (the loadable
segments of the ELF) and the code digest. The image has the
``LATBENCH_SRC_REV`` of the build: for the runs since 2026-10-27 this is the
content hash of the firmware files (kind ``firmware/1``), so the same
firmware at two commits gives the same image; older runs have the safety
revision or a git tree hash there. The code digest counts these 40
characters as zeros, so the same code gives the same code digest also
over these kinds. The app data come from the extractor of the app,
``tests/benchmarks/<app>/scripts/extract.py``: META, the histograms, the
tick phase tables, the M4 sites, and a check of the ``LAT CFG`` values
against ``.config``.

The standard plots of an experiment come from the plot script of its app,
``tests/benchmarks/<app>/scripts/plot.py`` (the common part is
``tests/benchmarks/common/scripts/latplot.py``, like the extractor). The
build runs it for each experiment of an instance, with the app data of
the runs that are not excluded (evidence and adjustment, so a smoke
campaign shows its graphs too; the legend names the role of an
adjustment run), and it writes ``ex-<experiment>/plots/`` of the
instance:

- ``overview-<metric>.svg``: the exceedance probability (the share of
  samples at or above x) of each point of the newest run, at most 8 points
  in one chart (with more points: ``overview-<metric>-<k>.svg``);
- ``ccdf-<metric>-<tree>-<point>.svg``: the exceedance probability of one
  point, one line for each run (the newest 8);
- ``hist-<metric>-<tree>-<point>.svg``: the histogram of one point of the
  newest run;
- ``plots.json``: the list of the plots and the digest of their inputs (the
  app data and the plot scripts). With the same digest, the build does not
  draw again.

The metric is the main metric of the app (``irq``, ``isr2thr``, ``t2t``).
The plots show repetition 1 of each point. A run that failed an
acceptance check is in the plots, with ``acceptance failed`` in its label
(it is not evidence for the checks).
The SVG files have no date, so the same inputs and the same matplotlib
give the same bytes. A failed plot gives a note in ``study.json``, not a
failed build. In a campaign, the background build draws the plots of an
experiment as soon as its run is done.

``experiment.json`` has one row for each run, tree, point, repetition and
metric, with the percentiles. ``study.json`` has the acceptance checks,
the rebuild checks, the hypotheses with each check (measured value,
limit, verdict) and the central results as filled sentences. The
``measured`` text of a check has all values if there are 4 or fewer; else
it has a short form (``6 values, min 100, max 105; 3 outside the limit:
...``), and ``measured_lines`` has all of them (``values`` has them as
data). A check or a central result that waits for a run has
``missing_run`` (the experiment and the instance). A manual check that is
open has the ``statement`` for the person.

.. _benchguide-result-folder:

Result folder
-------------

A run writes its results to ``<out>/<name>/<UTC time>/``, for example
``<out>/irq-example/20261024T153130Z/``. If ``<out>`` is the folder of an
instance (it has ``instance.json``), the folder is
``<out>/ex-<name>/<UTC time>/``.

.. code-block:: text

   <out>/<name>/<UTC time>/
   ├── manifest.json        provenance of the run
   ├── summary.txt          percentiles of each histogram
   └── <tree>/<point>/
       ├── rep1.log         serial output of repetition 1
       ├── rep2.log         ...
       ├── build.log        output of the build (west build, or CMake and Ninja)
       ├── .config          Kconfig of the build
       ├── zephyr.dts       devicetree of the build
       ├── <app>-<tree>-<point>.elf   the binary
       ├── <app>-<tree>-<point>.hex   the binary as Intel HEX, if the build makes it
       └── build/           only with --keep-build

The image names, for example ``irq_latency-ws-safety-stock-idle.elf``,
say what the image is also outside its folder. The runs before
2026-10-28 have ``zephyr.elf`` and ``zephyr.hex``; their seals cover the
names, so they keep them. The tools find the image by either name.

A run of an older ``run.py`` also has ``src/``, a copy of the safety
repository (``git archive``). Its builds used this copy.

``manifest.json`` has these fields:

- ``experiment``, ``experiment_file``, ``experiment_yaml``,
  ``experiment_sha256``: the name, the path in the repository, the full
  text and the SHA-256 of the experiment file.
- ``command``, ``started``, ``finished``, ``host``.
- ``lab``: the lab space (``id``, ``name``, ``folder``), or ``null``
  outside a lab space.
- ``safety``: the path and the revision of the safety repository, the
  local ref of the run (``ref``), the firmware hash (``bench_tree``, the
  ``LATBENCH_SRC_REV`` of the app, kind ``bench_tree_kind``; the first
  runs of 2026-10-27 have the git tree hash of ``tests/benchmarks`` and
  no kind) and the git tree hash of the module folder ``zephyr/``
  (``module_tree``). A run of an older ``run.py`` has instead the
  benchmark folder in its ``src/`` copy (``snapshot``) and the module
  folder (``module``). A still older run has no ``module``. The oldest
  runs have no ``snapshot``, because they built from the worktree.
- ``trees``, ``trees_root``: the entries of the trees (from the tree
  manifests, ``validation/trees.yaml`` before 2026-10-28), with only the
  repositories that the build used, and the trees root of the host.
- ``toolchain``: the SDK version and path.
- ``tools``: the versions of CMake, Ninja, Python, pyserial, and of each
  tool in the ``flash`` commands of the board (for example ``openocd``,
  ``nrfutil`` or ``pyocd``); ``builder`` (``west <version>`` or
  ``cmake``); ``python_packages`` (the versions of the packages of
  ``requirements.txt`` and ``requirements.lock``).
- ``board``, ``board_cfg``, ``console``: the board target, its entry from
  ``boards.yaml``, and the serial port.
- ``probe_serial``: the serial number of the debug probe of the console
  port (from ``udevadm``).
- ``points``: one entry for each tree and point. An entry has the axes,
  the settings, the CMake command, the SHA-256 of the ELF and the logs.
  In a lab space, it also has ``build``: ``key`` (the key of the build
  cache), ``from`` (``build`` or ``cache``) and, for an image from the
  cache, ``built_by`` (the run that built it, or ``<experiment> (build
  only, <UTC>)`` for a build without a run: ``campaign prepare``,
  ``run.py --build-only``, ``lab hwcheck``). The runs before 2026-10-28 have
  ``cached`` (``true`` or ``false``) instead of ``from``. If the point
  failed, it also has an ``error``.

Build cache
-----------

In a lab space, ``run.py`` keeps the image of each point in the build
cache ``.lab/build-cache/<key[:2]>/<key>/``. An entry has ``zephyr.elf``,
``zephyr.hex``, ``.config``, ``zephyr.dts``, ``build.log``,
``entry.json`` (the inputs of the key, the CMake command, the SHA-256 of
the ELF and ``built_by``, the run that built it) and ``uses.jsonl``: one
line for each run that took the image, with the run, the experiment, the
point, ``from`` (``build`` or ``cache``), the host and the time. The entry keeps the names
``zephyr.elf`` and ``zephyr.hex``, because two experiments can share it. A
run gives the images their names ``<app>-<tree>-<point>`` when it copies
them into its point folder.

Campaign record
---------------

The record ``.lab/campaigns/<id>.json`` (format ``latbench-campaign/1``)
is written at the start and after each step. Thus a crash leaves a valid
record. Each experiment has its log in ``.lab/campaigns/<id>/<experiment>.log``.

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Field
     - Meaning
   * - ``id``, ``format``
     - The campaign id (UTC time) and the format.
   * - ``lab``, ``host``
     - The lab space (``id``, ``name``, ``folder``) and the host.
   * - ``command``, ``cwd``, ``folder``, ``board``
     - The command, its folder, the ``FOLDER`` of the campaign and the
       board (or ``null``).
   * - ``repo``, ``ref``
     - The design repository (``path``, ``rev``) and the ref of the
       campaign.
   * - ``status``
     - ``planned``, ``running``, ``done``, ``failed`` or ``aborted``.
   * - ``created``, ``started``, ``finished``, ``pid``
     - The times and the process id.
   * - ``stopped``
     - The reason why the campaign stopped early.
   * - ``preflight``
     - The items of the pre-flight check: ``status``, ``what``, ``text``.
   * - ``post``
     - The background builds: ``n``, ``rc``, ``noticed`` (the time when
       the campaign saw the end of the build).
   * - ``python``
     - The Python of the campaign: ``executable``, ``prefix``,
       ``version`` and the ``packages`` with their versions.
   * - ``role``, ``reason``, ``hwcheck_each``
     - The role of the runs (``--role``, ``--reason``) and
       ``--hwcheck-each``.
   * - ``experiments``
     - One entry for each experiment: ``experiment``, ``study``,
       ``design`` (the experiment file), ``board``, ``state``
       (``planned``, ``running``, ``done``, ``failed``, ``skipped``),
       ``instance``, ``started``, ``finished``, ``log``, ``rc``, ``run``
       (the run id), ``note``, ``attempts`` (after a resume) and
       ``hwcheck`` (the record of its wire check, with
       ``--hwcheck-each``).
