.. _benchguide-lab:

Lab spaces and campaigns
========================

A lab space holds everything of one host that a study needs and that the
repository must not hold: the pinned trees, the Zephyr SDK, the results
tree, the hardware map, the build cache and the campaign records. A
campaign runs all experiments below a folder of the design, adds each run
to its instance and builds the results after each run.

In this page, ``study.py`` is ``<repo>/scripts/benchmarks/study.py`` and
``<repo>`` is the safety repository.

Typical session
---------------

.. code-block:: console

   # on the lab host: make the lab space and the trees (once)
   <repo>/scripts/benchmarks/study.py lab init ~/lab --repo <repo> --sdk ~/zephyr-sdk-1.0.1
   cd ~/lab
   study.py trees setup --clone-source
   study.py lab status
   # run all experiments of a study
   study.py campaign check <repo>/validation/empirical/latencies/st-default-latencies
   study.py campaign run <repo>/validation/empirical/latencies/st-default-latencies --detach
   study.py campaign status
   study.py lab export -o lab.tar.gz --campaign <id>

   # on the analysis host (another lab space), with lab.tar.gz and lab.tar.gz.sha256
   study.py lab import lab.tar.gz
   study.py build results/kernel-latency
   study.py html results/kernel-latency

.. _benchguide-lab-space:

The lab space
-------------

A lab space is a folder with the file ``.lab/config``, as a west
workspace is a folder with ``.west/config``. The tools find the lab space
from the current folder upwards. Thus run the tools in the lab folder or
in a folder below it.

``.lab/config`` is an INI file. A relative path is relative to the lab
folder. ``~`` is the home folder. Example:

.. code-block:: ini

   [lab]
   id = lab-smoke-3f9a1c2e
   name = lab-smoke
   [design]
   repo = safety
   [trees]
   root = trees
   source = /path/of/other/trees
   [toolchain]
   zephyr_sdk = ~/zephyr-sdk-1.0.1
   [results]
   root = results
   [hardware]
   map = hw-map.yml

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Key
     - Meaning
   * - ``[lab] id``
     - The name and a random part. ``lab init`` sets it once. The runs,
       the exports and the campaign records name the lab space by its id.
   * - ``[lab] name``
     - The name of the lab space (default: the folder name).
   * - ``[design] repo``
     - The safety repository with the study designs and the tools.
   * - ``[trees] root``
     - The folder of the pinned trees (default ``trees``).
   * - ``[trees] source``
     - Optional. A folder with ``<tree>/<path>`` clones, for example the
       trees root of another lab space. ``trees setup`` clones from it
       first.
   * - ``[toolchain] zephyr_sdk``
     - Optional. The Zephyr SDK. The default is
       ``~/zephyr-sdk-<version>``, with the version of
       ``validation/trees.yaml``.
   * - ``[results] root``
     - The folder of the results trees (default ``results``). The results
       tree of the design is ``<root>/kernel-latency``.
   * - ``[hardware] map``
     - The hardware map of the host (default ``hw-map.yml``, see
       :ref:`benchguide-hw-map`).

The folder ``.lab/`` also holds the build cache (``build-cache/``), the
campaign records (``campaigns/``), the campaign lock (``campaign.lock``)
and the builds of the wire check (``hwcheck/<board>/``).

The tools use the lab space as follows:

- ``study.py`` runs the ``study.py`` of the design repository of the lab
  space. If you start another ``study.py`` (for example of a different
  worktree), it starts the ``study.py`` of ``[design] repo`` with the same
  arguments. ``study.py lab init`` is the exception.
- ``run.py`` stops if the lab space uses a different design repository.
  It takes the hardware map of the lab space by default.
- The trees root comes from ``--trees-root``, the environment variable
  ``LATBENCH_TREES_ROOT`` or ``[trees] root``, in this order. Without a
  lab space and without the two overrides, a tool that needs a tree
  stops.
- The SDK path comes from ``[toolchain] zephyr_sdk``.

``lab init``
~~~~~~~~~~~~

.. code-block:: console

   study.py lab init FOLDER --repo REPO [--name N] [--trees-root DIR] [--trees-source DIR]
                            [--sdk DIR] [--results DIR] [--hw-map FILE]

``lab init`` makes ``FOLDER/.lab/config``, the results folder and the
trees root. ``REPO`` must have ``scripts/benchmarks/study.py``. If
``FOLDER`` is a lab space already, the command stops. A path in
``FOLDER`` goes into the file as a relative path. The command prints the
next step, ``study.py trees setup --clone-source``. If the hardware map
does not exist, it tells you to make it with twister. If the results
folder is outside ``FOLDER``, it gets the file ``.lab-space`` with the
path of the lab folder: the build then finds the lab space of the results
also from another folder (``lab.owner()``, not the current folder).

``lab status``
~~~~~~~~~~~~~~

``study.py lab status`` prints:

- The id and the folder of the lab space.
- The design repository, its commit, and ``(dirty)`` if it has changes.
- The SDK and its version, or the problem.
- Each tree: ``ok``, or the first line of the problem.
- The results folder.
- Each board of the hardware map: connected or not, and its fixtures.
- The last three campaigns.

``lab hwcheck``
~~~~~~~~~~~~~~~

.. code-block:: console

   study.py lab hwcheck BOARD [--tree TREE]

The command makes sure that the loopback wire of a board works. It builds
the app ``tests/benchmarks/loopback_check`` for the board from a pinned
tree, in ``.lab/hwcheck/<board>/``. The default tree is the first tree
that pins ``zephyr`` and the modules of the board. Then it flashes the
board with the ``flash`` commands of ``boards.yaml`` and reads the console
until ``RESULT: OK`` or ``RESULT: FAIL``, for 60 s or less. The exit code
is 0 for ``OK``, 1 for ``FAIL``, and 2 if the check cannot run (build,
flash, no board). The check writes no result data.

.. _benchguide-lab-trees:

Pinned trees (``study.py trees``)
---------------------------------

.. code-block:: console

   study.py trees setup [--clone-source] [TREE ...]
   study.py trees check [TREE ...]
   study.py trees show
   # all three: [--trees-root DIR]

The pins are in ``validation/trees.yaml`` (see :doc:`host-tools`). The
paths come from the lab space.

``setup`` makes each missing repository at
``<trees root>/<tree>/<path>``, at its pinned revision. The clone source
is the first of these that exists:

#. ``<[trees] source>/<tree>/<path>`` of the lab space (a git
   repository).
#. The ``source`` of the repository in ``validation/trees.yaml``.
#. The ``url``. Then ``setup`` clones from the network.

With a local source, ``setup`` adds a detached git worktree to the
source. If the revision is not in the source, it fetches the ``branch``
into the source first. With ``--clone-source``, ``setup`` makes a local
clone of the source instead. The clone uses hard links to the objects,
and nothing is written into the source. If the revision is not in the
clone, the clone fetches it from the ``url``. Use ``--clone-source`` if
the source is a repository of a different workspace that must not
change. After ``setup``, the command does the same as ``check``.

``check`` makes sure that the SDK has the pinned version and that each
repository is at its pinned revision and clean. ``show`` prints the trees
root, the trees, the revisions and the paths.

.. _benchguide-build-cache:

Build cache
-----------

In a lab space, ``run.py`` keeps the image of each point in the build
cache ``.lab/build-cache/<key[:2]>/<key>/``. An entry has ``zephyr.elf``,
``zephyr.hex``, ``.config``, ``zephyr.dts``, ``build.log`` and
``entry.json`` (the inputs of the key, the CMake command and the SHA-256
of the ELF).

The key is the SHA-256 of all inputs of the image:

- the board and the app,
- the pinned revisions of the tree repositories that the board needs,
- the ``BUILD_VERSION`` of the Zephyr tree (``git describe``, which
  depends on the tags of the tree; ``run.py`` gives it to CMake),
- the SDK version,
- a content hash of the firmware files of ``tests/benchmarks`` (kind
  ``firmware/1``: all files without the host scripts in ``scripts/``,
  Python, Markdown, ``testcase.yaml`` and ``boards.yaml``), and the git
  tree hash of the module folder ``zephyr/`` of the safety repository,
- the point: its Kconfig values, conf files and overlays.

The key has no host path, no experiment name and no safety commit. The
app gets the firmware hash as ``LATBENCH_SRC_REV``, not the commit. Thus
these runs get the image from the cache:

- A repeat of an experiment.
- A run after a commit that changes only the design files (for example
  ``study.yaml``), the tools or an extractor, because the hashes stay the
  same.
- A point of another experiment with the same settings.

An entry counts only if its ELF has the SHA-256 of ``entry.json``. The
manifest of the run records ``build: {key, cached}`` for each point. Each
build has a folder of its own process, and an entry that another process
stored first stays. Before an image goes into the run or the cache,
``run.py`` checks again that the repository did not change during the
build.
``run.py --build-only`` and ``study.py campaign prepare`` fill the cache.
``run.py --no-cache`` builds again and does not use the cache.

.. _benchguide-campaign:

Campaigns
---------

.. code-block:: console

   study.py campaign prepare FOLDER [--board B] [--only EXP ...] [--skip EXP ...]
   study.py campaign check   FOLDER [--board B] [--only ...] [--skip ...] [--no-hwcheck] [--warn-as-error]
   study.py campaign run     FOLDER [--board B] [--only ...] [--skip ...] [--no-hwcheck] [--warn-as-error] [--detach]
   study.py campaign status  [ID] [--verdicts]
   study.py campaign resume  ID [--no-hwcheck] [--warn-as-error] [--detach]

``FOLDER`` is a study folder (``st-*``) or an experiment folder
(``ex-*``) of the design, or an instance folder of the results tree of
the lab space. For an instance folder, the board of the instance is the
board of the campaign.

The experiments of a campaign come in this order:

#. The experiments of the study, in the order of its ``study.yaml``.
#. The ``mode: rerun`` imports of the study.
#. The experiments of each sub-study, depth first.

A sub-study with ``instances: per-board`` is not in the campaign, unless
``FOLDER`` is in it. ``--only`` keeps only the given experiments.
``--skip`` and a board that is not the board of the campaign mark an
experiment as ``skipped``.

``prepare``
~~~~~~~~~~~

``prepare`` runs ``run.py --build-only`` for each experiment. It fills
the build cache, so that the run builds nothing. The output goes to
``.lab/prepare.log``.

.. _benchguide-preflight:

``check`` (the pre-flight check)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``check`` prints the plan and then the pre-flight check. Each item is
``ok``, ``warn`` or ``fail``:

- Design repository: clean (``fail`` if it has changes).
- Lint: the problems of each experiment of the plan and of its study.
  An error is ``fail``. A warning is ``warn``, or ``fail`` with
  ``--warn-as-error``.
- Zephyr SDK: the pinned version.
- Each tree of the experiments: at its pinned revision and clean.
- Images: the points with an image in the build cache. ``warn`` if
  some are missing (the run then builds them).
- Hardware map: the file loads.
- Each board: an entry in the hardware map, and its console exists.
- The console of each board is free (no other program has it open).
- The loopback wire of each board (``lab hwcheck``). ``--no-hwcheck``
  removes this item.
- Disk: the free space is more than two times the size of the earlier
  runs of the experiments.
- Duration: the sum of the durations of the last earlier run of each
  experiment. This item is always ``ok``. It names the experiments
  without an earlier run.

A ``fail`` gives exit code 1.

``run``
~~~~~~~

``run`` makes the campaign record and runs the campaign:

#. The design repository must be clean. The campaign id is the UTC time
   (``20261026T223523Z``).
#. It takes the lock and sets the ref ``refs/latbench/campaign/<id>`` of
   the design repository to the commit of the campaign.
#. It does the pre-flight check. If an item is ``fail``, nothing runs,
   and the status of the campaign is ``failed``.
#. For each experiment that is not ``done`` or ``skipped``: it makes sure
   that the design repository is clean and at the commit of the
   campaign. It makes the instance if there is none (``instance new`` at
   the level that fixes the board). Then it runs ``run.py <experiment.yaml>
   --out <instance folder>``.
#. If ``run.py`` succeeds, it adds the run to the run list of the
   instance (role ``evidence``). The experiment is ``done``.
#. After each ``done`` experiment, a background process builds the
   results tree (``study.py build`` and ``study.py html``).

Failure rules:

- A failed experiment does not stop the campaign. The next experiment
  starts. If ``run.py`` left a part of a run folder, the record names it
  in ``note``. This part is not in the run list.
- A change of the design repository (a new commit, or changes that are
  not committed) stops the campaign before the next experiment.
- ``SIGTERM`` or Ctrl-C stops the campaign. The running experiment is
  ``failed``, and the campaign is ``aborted``.

The background build runs with ``nice 10``, one build at a time. If a run
ends while a build runs, one more build follows. At the end, the campaign
waits for the last build and then builds one more time. The builds write
``.lab/campaigns/<id>/post.log``. While the campaign runs, the build
marks the verdicts that wait for an experiment of the campaign as
provisional (see :ref:`benchguide-provisional`).

With ``--detach``, ``run`` makes the record and starts ``study.py
campaign resume <id>`` in a new session. The command then returns. The
output goes to ``.lab/campaigns/<id>/campaign.log``. The pre-flight check
also runs in the background, so read the log or the status.

``status`` and ``resume``
~~~~~~~~~~~~~~~~~~~~~~~~~

``status`` prints the record of a campaign: the default is the latest
campaign of this lab space. It prints the status, the lab space, the
host, the commit, the folder, and one line for each experiment (state,
instance, and the run or the note). It also gives the result of the last
background build. With ``--verdicts``, it also prints the verdicts of the
instances of the campaign.

``resume`` runs the experiments of a campaign that are not ``done`` or
``skipped``, also the ``failed`` ones: at the start it sets them to
``planned`` again (``attempts`` + 1), so they make the verdicts
provisional until they run. The design repository must be at
the commit of the campaign. To get it, check out the ref
``refs/latbench/campaign/<id>``.

Lock and ref
~~~~~~~~~~~~

The lock is an ``flock`` on ``.lab/campaign.lock``. It lets one campaign
run in a lab space. The kernel releases it when the process ends, so a
crash or a kill leaves no stale lock. The file has the campaign id, the
process id and the host of the holder, for information. A campaign of
this lab space counts as running (for provisional verdicts) only while
it holds the lock.

The ref ``refs/latbench/campaign/<id>`` keeps the commit of the campaign
in the design repository, also after a rebase of the branch. It is a
local ref. Do not push it. ``run.py --rebuild`` needs this commit. Each
run also gets the ref ``refs/latbench/run/<experiment>/<UTC>`` (manifest
``safety.ref``), also without a campaign.

Campaign record
~~~~~~~~~~~~~~~

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
     - The background builds: ``n``, ``rc``, ``finished``.
   * - ``experiments``
     - One entry for each experiment: ``experiment``, ``study``,
       ``design`` (the experiment file), ``board``, ``state``
       (``planned``, ``running``, ``done``, ``failed``, ``skipped``),
       ``instance``, ``started``, ``finished``, ``log``, ``rc``, ``run``
       (the run id) and ``note``.

.. _benchguide-lab-exchange:

Export and import
-----------------

.. code-block:: console

   study.py lab export [FOLDER] -o FILE [--campaign ID ...] [--all]
   study.py lab import FILE [--dry-run]

``lab export`` writes the runs of this lab space to ``FILE`` (a
``tar.gz`` file) and its digest to ``FILE.sha256``. The default is the
runs that this lab space made (the ``lab`` of the manifest).
``--campaign`` selects the runs of these campaigns. ``--all`` selects all
runs, also the runs from another lab. ``FOLDER`` selects only the
instances below this folder of the results tree. The export stops if the
seal of a run does not give the digest of the run list.

The archive has:

``export.json``
   The format ``latbench-export/1``, the lab space, the host, the commit
   of the design repository, the design files of the exporting lab
   (``experiment.yaml`` of each experiment, ``study.yaml`` and
   ``hypotheses.yaml`` of each instance, with their SHA-256), and for
   each run: the instance path, the run-list entry (``id``, ``digest``,
   ``role``, ``reason``), the board, the campaign and the tree pins.
``runs/<instance folder>/ex-<experiment>/<UTC>/`` and ``<UTC>.sha256``
   The raw runs and their seals.
``campaigns/<id>.json``
   The records of the campaigns of the runs.

``lab import`` first makes sure that ``FILE`` has the digest of
``FILE.sha256``. It refuses an export of this lab space. Then it does
these checks for each run:

.. list-table::
   :header-rows: 1
   :widths: 60 40

   * - Condition
     - Result
   * - The run id is in the results tree with another digest (collision).
     - The run is refused.
   * - The run id is in the results tree with the same digest.
     - The run is skipped.
   * - ``experiment.yaml`` differs between the two labs, or the experiment
       is not in the design here. The two labs work from different design
       files.
     - The run is refused.
   * - ``study.yaml`` or ``hypotheses.yaml`` of the instance differs.
     - A warning. The build here uses the design files here.
   * - The tree pins of the run differ from ``validation/trees.yaml``
       here.
     - A warning.
   * - The seal does not give the digest of the run-list entry.
     - The run is refused.
   * - The run folder exists here, but it is not in the run list.
     - The run is refused.

Then the import copies the run and its seal into its instance and adds
the entry with its role and reason. If the instance does not exist, the
import makes it, with the board of the run at the level that fixes the
board in the other lab. ``copied_from`` of the entry is
``lab <lab id>, campaign <id>``. The campaign records go to
``.lab/campaigns/<id>@<lab id>.json``. Thus a running campaign of the
other lab also makes the verdicts here provisional. The default of
``campaign status`` (the latest campaign) is never an imported record.

``--dry-run`` does only the checks. The command prints each warning, each
refused run and the numbers. It exits with 1 if it refused a run. After
an import, build the results tree (``study.py build``).
