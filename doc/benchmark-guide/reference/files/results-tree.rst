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
