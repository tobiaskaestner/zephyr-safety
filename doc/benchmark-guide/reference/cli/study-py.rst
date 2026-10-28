The tool study.py
=================

``study.py`` (``<repo>/scripts/benchmarks/study.py``) has all commands of
the :term:`studies <study>`, the :term:`lab spaces <lab space>` and the
results, in six namespaces. In a lab space, each ``study.py`` runs the
``study.py`` of the :term:`design repository` with the Python of the lab
space (see :doc:`../files/lab-config`). ``study.py --help`` and
``study.py <namespace> <command> --help`` give the options.

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Namespace
     - Commands
   * - ``design``
     - ``lint``, ``scaffold study``, ``scaffold experiment``: the design
       files.
   * - ``lab``
     - ``init``, ``status``, ``hwcheck``, ``export``, ``import``: the lab
       space.
   * - ``trees``
     - ``setup``, ``check``, ``show``: the pinned :term:`trees <Tree>`.
   * - ``campaign``
     - ``prepare``, ``check``, ``run``, ``status``, ``resume``: runs of
       experiments.
   * - ``instance``
     - ``new``, ``add``, ``exclude``, ``reference``, ``verdict``,
       ``merge``, ``seal``, ``verify``: the run lists.
   * - ``analysis``
     - ``build``, ``check``, ``show``, ``missing``, ``notebooks``,
       ``html``: the aggregates, the verdicts and the pages.

The exit code is 0 for success and 1 for a failure or a refusal. It is 2
for a ``lab hwcheck`` that cannot run, and for a command line that
``argparse`` refuses (a usage error). An error gives one line
``error: ...``.

Design
------

``design lint``
~~~~~~~~~~~~~~~

.. code-block:: console

   scripts/benchmarks/study.py design lint [FOLDER] [--warn-as-error]

The lint reads the design files below ``validation/empirical/latencies/``.
It needs no build and no board. It prints one line for each problem,
``<severity>: <file>: <text>``, and then the number of errors and
warnings. With ``FOLDER``, it prints only the problems of the files below
that folder, and the problems of its parent folders (for example "the
design does not load"). The tree manifests and ``boards.yaml`` are checked
only without ``FOLDER``.

The rules are in :doc:`../lint-rules`.

.. _benchguide-scaffold:

``design scaffold``
~~~~~~~~~~~~~~~~~~~

.. code-block:: console

   scripts/benchmarks/study.py design scaffold study PARENT/st-NAME
   scripts/benchmarks/study.py design scaffold experiment STUDY/ex-NAME --app APP [--board B]

``scaffold study`` makes a new sub-study ``st-NAME/`` of the study
``PARENT``, with these files:

- ``study.yaml``: the name, a ``question``, no ``experiments`` and an
  empty ``central_results``.
- ``study.md``: the sections Background, Experiments and References (see
  :ref:`benchguide-study-md`).
- ``hypotheses.yaml``: one template :term:`hypothesis` ``H1`` without
  checks.

The command also adds ``use: NAME`` to ``substudies`` of the parent
``study.yaml``. The new study has no experiment, and its hypothesis has
no :term:`check`. A template check gives a :term:`verdict` from a limit
that nobody wrote. Thus the template has no check. Write each check when
the experiment that it reads exists.

``scaffold experiment`` makes the :term:`experiment` ``ex-NAME/`` and adds it to
``experiments`` of ``STUDY/study.yaml``, and a line for it to the section
Experiments of ``STUDY/study.md``. The edits are text edits, so the
comments of the files stay.

The template ``experiment.yaml`` has the :term:`app`, the board (only with
``--board``), the first tree of ``validation/trees/`` (by name), one axis
``variant`` with the value ``default``, and the acceptance check ``A1``
(no invalid :term:`samples <Sample>`). The metric of ``A1`` is the main metric of the app:
``irq`` for ``irq_latency``, ``isr2thr`` for ``wake_latency``, ``t2t``
for ``thread_latency``. The template ``experiment.md`` has the sections
of :ref:`benchguide-experiment-md`.

A name has only lower case letters, digits and ``-``. An experiment name
must be unique over all studies. The templates pass the lint without
errors. Each ``TODO`` text gives a lint warning until you replace it. The
command prints the new files and the line ``replace the TODO texts;
'study.py design lint' lists them``.

.. _benchguide-lab-commands:

Lab space
---------

.. code-block:: console

   study.py lab init [FOLDER] --repo REPO [--name N] [--trees-root DIR] [--trees-source DIR]
                     [--sdk DIR] [--results DIR] [--hw-map FILE]
   study.py lab status
   study.py lab hwcheck BOARD [--tree TREE]
   study.py lab export [FOLDER] -o FILE [--campaign ID ...] [--all]
   study.py lab import FILE [--dry-run]
   study.py lab import --close ID@LAB

``lab init``
~~~~~~~~~~~~

.. code-block:: console

   study.py lab init [FOLDER] --repo REPO [--name N] [--trees-root DIR] [--trees-source DIR]
                              [--sdk DIR] [--results DIR] [--hw-map FILE]

``lab init`` makes ``FOLDER/.lab/config``, the results folder and the
trees root. ``FOLDER`` is the current folder by default. ``REPO`` is the
design repository, a clone of the :term:`safety repository`. It must
have ``scripts/benchmarks/study.py``. The options set these keys of
``.lab/config`` (see :doc:`../files/lab-config`): ``--name`` sets
``[lab] name``, ``--trees-root`` and ``--trees-source`` set ``[trees]
root`` and ``[trees] source``, ``--sdk`` sets ``[toolchain] zephyr_sdk``,
``--results`` sets ``[results] root`` and ``--hw-map`` sets ``[hardware]
map``. :doc:`../../howto/set-up-a-lab-space` gives the steps before and
after ``lab init``. If
``FOLDER`` is a lab space already, the command stops. The virtual
environment of the Python that runs ``lab init`` goes into ``[python]
venv``. ``lab init`` gives a warning in two cases (``lab status`` gives
the same warnings):

- It runs without a virtual environment.
- A package of ``requirements.txt`` is missing or does not have a
  version in its range.

A path in ``FOLDER`` goes into the file as a relative path. The command prints the
next step, ``study.py trees setup <tree>``. If the hardware map
does not exist, it says that the map is missing. The results
folder can be outside ``FOLDER``. Then it gets the file ``.lab-space``
with the path of the lab folder. Thus the build finds the lab space of
the results also from another folder (``lab.owner()``, not the current
folder).

``lab status``
~~~~~~~~~~~~~~

``study.py lab status`` prints:

- The id and the folder of the lab space.
- The design repository, its commit, and ``(dirty)`` if it has changes.
- The Python that runs (the venv of the lab space), and a warning for
  each package that is missing or not at the version of
  ``requirements.txt`` or ``requirements.lock``.
- The SDK and its version, or the problem.
- Each tree: ``ok``, ``not set up``, or ``wrong`` with the first line of
  the problem.
- The results folder.
- Each board of the hardware map: connected or not, and its fixtures.
- The last three :term:`campaigns <Campaign>`, and each imported campaign that is not
  complete.

``lab hwcheck``
~~~~~~~~~~~~~~~

.. code-block:: console

   study.py lab hwcheck BOARD [--tree TREE]

The command does the :term:`wire check` of a board: it makes sure that
the loopback wire works. It builds
the app ``tests/benchmarks/loopback_check`` for the board from a pinned
tree, through the :term:`build cache` like a :term:`point` of a :term:`run`, and copies the
image to ``.lab/hwcheck/<board>/``. The default tree is the first tree (by
name) that pins ``zephyr`` and the modules of the board and that the lab
space set up (``ok``). Then it flashes
the board with the ``flash`` commands of ``boards.yaml`` and reads the
console until ``RESULT: OK`` or ``RESULT: FAIL``, for 60 s or less. The
exit code is 0 for ``OK``, 1 for ``FAIL``, and 2 if the check cannot run
(build, flash, board, hardware map, tree, SDK, console). The check takes
the board lock, as a campaign does (a check that a campaign runs uses the
lock of the campaign), and opens the console exclusively.

Each check writes its own record,
``.lab/hwcheck/history/<board>/<UTC>.json``, also a check that cannot run
(``result: error`` and the ``error``), and a copy of the newest record as
``.lab/hwcheck/<board>.json``. A record has:

- The time, the host and the tree.
- The commit of the design repository (``repo``: ``rev``, ``dirty``).
- The probe and the console.
- The image (SHA-256, cache key, from build or cache).
- The result and all console lines (with the loopback measurement).

The :term:`pre-flight check` of a campaign names the record of its wire
check. If the design repository has changes that are not committed, the
image cannot go into the cache. Then the wire check builds in
``.lab/hwcheck/<board>/build/``, and the record has ``repo.dirty:
true``.

``campaign run --hwcheck-each`` also does the wire check before each
experiment. The experiment gets the record of its wire check
(``hwcheck``). If the wire check fails, the experiment is ``failed`` (the
note says why), and the campaign continues with the next experiment.
With the image from the build cache, a wire check takes 10 s to 20 s.

``lab export`` and ``lab import``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``lab export`` writes the runs of this lab space to ``FILE`` and its
digest to ``FILE.sha256``. The default is the runs that this lab space
made. ``--campaign`` selects the runs of these campaigns. ``--all``
selects all runs, also the runs from another lab space. ``FOLDER``
selects only the instances below this folder of the results tree.

``lab import FILE`` adds the runs of an export to the results tree.
``--dry-run`` does only the checks. The command prints each warning, each
refused run and the numbers. It exits with 1 if it refused a run.
``lab import --close ID@LAB`` ends an imported campaign record that is
not complete.

:doc:`../files/export` gives the content of an export and the checks of
an import. :doc:`../../explanation/lab-exchange` tells why, and
:doc:`../../howto/combine-lab-spaces` gives the steps.

.. _benchguide-lab-trees:

Pinned trees (``study.py trees``)
---------------------------------

.. code-block:: console

   study.py trees setup [TREE ...]
   study.py trees check [TREE ...]
   study.py trees show [TREE ...]
   # all three: [--trees-root DIR]

The pins are the west manifests ``validation/trees/<tree>.yml`` (see
:doc:`../files/trees-yaml`). The paths come from the lab space: the trees
root is ``[trees] root``, and ``--trees-root`` or
``LATBENCH_TREES_ROOT`` overrides it. Without ``TREE``, a command works on
all trees.

``setup``
   Makes the west workspace ``<trees root>/<tree>/`` of each tree:

   #. It copies the manifest to ``<trees root>/<tree>/manifest/west.yml``.
      If a copy is there and it is different, ``setup`` stops: the pins of
      a tree never change. A new project is accepted.
   #. It runs ``west init -l manifest`` (only once).
   #. It makes sure that ``west topdir`` gives the tree folder, and stops
      if not.
   #. It runs ``west update``, with ``--path-cache <[trees] source>/<tree>``
      if that folder exists. west makes a plain ``git clone`` of each
      project from the cache (no worktree, no alternates, nothing written
      into the cache) and then sets the remote to the ``url``. A project
      that is not in the cache comes from its ``url``.
   #. It does the same examination as ``check``.

   west runs without the ``ZEPHYR_*`` variables of the caller and without
   the user and system west configuration
   (``WEST_CONFIG_GLOBAL=/dev/null``, ``WEST_CONFIG_SYSTEM=/dev/null``).
   Thus a ``ZEPHYR_BASE`` of another workspace cannot lead west to that
   workspace, and a ``~/.westconfig`` cannot change a build.

   A lab space made before 2026-10-28 has its trees as plain clones in
   the same paths. ``trees setup <tree>`` makes them a west workspace: it
   adds the manifest copy and ``.west/`` and keeps the clones.

``check``
   Makes sure that the SDK has the pinned version. Then it gives the state
   of each tree:

   - ``ok``: each repository is at its pinned revision and clean (no
     changes, no untracked files), and the manifest copy is the same as
     the file in the repository.
   - ``not set up``: a repository has no checkout. This is information,
     because a lab space sets up only the trees of its studies. It is an
     error only for a tree that you name.
   - ``wrong``: a repository is not at its pin or not clean, or the
     manifest copy is different. This is an error (exit code 1).

   A tree that is not a west workspace yet, or whose ``.west/config`` has
   a key that ``west init`` does not write (for example
   ``build.cmake-args``), is not ``ok``. ``lab status`` shows the same
   states.

``show``
   Prints the trees root, the trees, the revisions and the paths.

.. _benchguide-campaign:

Campaigns
---------

.. code-block:: console

   study.py campaign prepare FOLDER [--board B] [--only EXP ...] [--skip EXP ...]
   study.py campaign check   FOLDER [--board B] [--only ...] [--skip ...] [--no-hwcheck] [--warn-as-error]
   study.py campaign run     FOLDER [--board B] [--only ...] [--skip ...] [--no-hwcheck] [--warn-as-error] [--detach]
                             [--role R --reason TEXT] [--hwcheck-each]
   study.py campaign status  [ID] [--verdicts]
   study.py campaign resume  ID [--no-hwcheck] [--warn-as-error] [--detach]

``FOLDER`` is a study folder (``st-*``) or an experiment folder
(``ex-*``) of the design, or an instance folder of the results tree of
the lab space. For an instance folder, the board of the instance is the
board of the campaign.

``prepare``
~~~~~~~~~~~

``prepare`` runs ``run.py --build-only`` for each experiment. It fills
the build cache, so that the run builds nothing. The output goes to
``.lab/prepare.log``.

.. _benchguide-preflight:

``check`` (the pre-flight check)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``check`` prints the plan and then the :term:`pre-flight check`. The plan has one
line for each experiment: its state, its study and board, and its
instance folder, with ``exists`` or ``will be made``, for example::

     planned  irq-smoke (default-latencies/irq-entry, nucleo_g474re) -> kernel-latency/st-default-latencies@nucleo_g474re/st-irq-entry (exists)

A new instance gets the board one level below the top study, or at the
level of a sub-study with ``instances: per-board`` (and the sub-studies
below it inherit the board).

Each item of the pre-flight check is ``ok``, ``warn`` or ``fail``:

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
- The wire check of each board (``lab hwcheck``). ``--no-hwcheck``
  removes this item.
- Disk: the free space is more than two times the size of the earlier
  runs of the experiments.
- Duration: the sum of the durations of the last earlier run of each
  experiment. This item is always ``ok``. It names the experiments
  without an earlier run.

A ``fail`` gives exit code 1.

``run``
~~~~~~~

:doc:`../../explanation/campaigns` describes what ``run`` does.

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

``resume ID`` runs the experiments of the campaign ``ID`` that are not
``done`` or ``skipped`` (see :ref:`benchguide-resume-rules`). The design
repository must be at the commit of the campaign. ``--detach`` starts it
in the background, as for ``run``. :doc:`../../howto/resume-a-campaign`
gives the steps.

Instances
---------

.. code-block:: console

   study.py instance new RESULTS STUDY --board B
   study.py instance add INSTANCE RUN [--role R --reason TEXT] [--copy]
   study.py instance exclude ROOT --campaign ID --reason TEXT
   study.py instance reference INSTANCE OTHER RUN_ID --reason TEXT
   study.py instance verdict INSTANCE --verdict V --by NAME [--text T]
                    (--hypothesis H --check C | --central-result ID)
   study.py instance merge OTHER ROOT [--origin HOST:PATH]
   study.py instance seal RUN ...
   study.py instance verify RUN ...

The run list of an :term:`instance` is hand-made data. In a lab space,
a campaign makes the instances and ``run.py`` adds each run.

``instance new``
   Makes the instance folders of the study ``STUDY`` for the board ``B``
   in the results tree ``RESULTS``.

``instance add``
   Adds the run folder ``RUN`` to the run list of ``INSTANCE``, with
   ``--role`` and ``--reason``. With ``--copy``, it copies the run into the
   instance folder, and the original stays.

``instance exclude``
   Gives the :term:`role` ``excluded`` to all runs of the campaign ``ID`` below
   ``ROOT``, for example a test of the tools. The entry keeps the earlier
   role in ``role_before``.

``instance reference``
   Adds a run of another instance that a check reads.

``instance verdict``
   Records a manual verdict of a check (``--hypothesis H --check C``) or
   of a central result (``--central-result ID``). ``--by`` names the
   person, or a proposal that says so.

``instance merge``
   Adds the runs of the results tree ``OTHER`` that ``ROOT`` does not
   have, with their roles, after it examines their seals and digests. Use
   it for a results tree that is not in a lab space. Between two lab
   spaces, use ``lab export`` and ``lab import``. If ``OTHER`` is a local
   copy, ``--origin HOST:PATH`` records the original tree in
   ``copied_from``.

``instance seal``
   Writes the :term:`seal` of old run folders. ``run.py`` writes the seal
   of a new run.

``instance verify``
   Computes the SHA-256 of each file of a run folder again and compares
   it with the seal. It prints the digest of each run. A missing, changed
   or extra file gives an error. The command does not read the run list:
   compare the digest with ``digest`` of the run-list entry.

:doc:`../../howto/run-without-a-campaign` gives the steps to use these
commands without a campaign.

Analysis
--------

.. code-block:: console

   study.py analysis build ROOT
   study.py analysis check ROOT
   study.py analysis show FOLDER [--details] [--explain [ID ...]]
   study.py analysis missing [FOLDER]
   study.py analysis notebooks FOLDER [--force]
   study.py analysis html FOLDER

``ROOT`` and ``FOLDER`` are folders of a results tree. ``build`` and
``check`` always work on the whole tree of ``ROOT``.

``analysis build`` writes only derived files. It does not change a raw
run or ``instance.json``. The same inputs and the same revision of the
tools give the same bytes. ``analysis check`` examines each seal, builds
again in memory and compares the JSON files: ``run.json``, the app data,
``experiment.json`` and ``study.json``. It does not compare the plots,
the pages or the notebooks. Each aggregate records the safety revision
of the tools (``made_by``). ``dirty: true`` means that the tools had
changes that were not committed.

``analysis show`` and ``analysis missing`` read the instances at and below
the folder that you give (any folder of a results tree). They name each
instance by its folder below the results folder. The one line of an
instance gives:

- The hypotheses in numbers (confirmed, wrong, open, and the ``draft``
  checks).
- The central results with a sentence.
- The acceptance checks that are not confirmed.
- The notes and the failed runs (a ``<UTC>.failed.json`` in the
  instance).
- ``PROVISIONAL``, if a result is provisional.

``--details`` gives each check with its measured text, and each central
result with its sentences or the reason why it has none. It also gives
the failed runs. For an open manual check, it gives its statement and the
``instance verdict`` command that closes it.

``analysis missing`` lists each experiment without an evidence run in an
instance, with the checks and central results that wait for it. These
are the runs to make next.

.. _benchguide-explain-form:

The output of ``--explain``
~~~~~~~~~~~~~~~~~~~~~~~~~~~

``analysis show FOLDER --explain [ID ...]`` prints, for each
:term:`central result` (or for the given IDs) of each instance: the
definition, each row, and the sentence of each row (see
:doc:`../central-results`). The output has this form:

.. code-block:: none

   == <instance> [<id>]
      statement: <the statement, on one line>
      from: <from>
      stat: <stat>
      group_by: <group_by, if the result has it>
      row: <name>=<value>, <name>=<value>, ...
        -> <the sentence of this row>
      unfilled placeholders: [<name>, ...] (no such value in the rows)

A result without a value prints ``not evaluated: <reason>`` instead of
the rows. The last line is there only if a placeholder stays unfilled.

``analysis html`` and ``analysis notebooks``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``analysis html`` writes ``index.html`` in each instance folder at and
below the folder: the links up to each parent instance, the content of
``study.json``, the experiments (with a link to their pages) and the
direct sub-studies with their verdicts in one line. Each experiment
folder gets ``ex-<experiment>/index.html``: the standard plots and the
runs (role, reason, digest, campaign, acceptance), and the failed runs.
The links are relative, so you can copy the results tree or serve it from
any place. The background build of a campaign writes the pages after each
run.

``analysis notebooks FOLDER [--force]`` runs the notebooks of the studies
against their instances at and below the folder. A study has its
notebooks in its design folder (``*.ipynb`` and ``notebooks/*.ipynb``,
committed without outputs). They are for the questions that the standard
plots cannot answer: comparisons over experiments, trees and boards. Each
notebook runs (nbclient) in the safety repository, with the environment
variables ``LATBENCH_INSTANCE`` (the instance folder) and
``LATBENCH_REPO`` (the safety repository). ``scripts/benchmarks/data.py``
loads the instance. The output goes to
``<instance>/notebooks/<name>.html``. ``notebooks.json`` has the digest
of the inputs (the notebook and ``study.json``). With the same digest,
the notebook does not run again. The instance page links to the
notebooks. The output is not byte-stable, so ``analysis check`` does not
compare it. The packages are in
``scripts/benchmarks/requirements-notebooks.lock``. The other commands do
not need them.
