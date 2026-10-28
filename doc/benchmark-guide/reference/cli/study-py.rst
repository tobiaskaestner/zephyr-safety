The tool study.py
=================

In this page, ``study.py`` is ``<repo>/scripts/benchmarks/study.py`` and
``<repo>`` is the safety repository.

The commands that change a run list are below ``study.py instance``. In a
lab space, a campaign makes the instances and adds each run (see
:doc:`../../explanation/campaigns`). Without a campaign, use these commands:

.. code-block:: console

   # once: the instance folders of a study for a board
   scripts/benchmarks/study.py instance new <results> load-scaling --board nucleo_g474re
   # a run goes into its instance folder and into its run list (run.py adds it)
   scripts/benchmarks/run.py <experiment.yaml> --out <instance folder> [--role R --reason TEXT]
   # an old run from another place: copy it in (the original stays)
   scripts/benchmarks/study.py instance add <instance folder> <old run folder> --copy
   # the aggregates, and a check that they come again from the same inputs
   scripts/benchmarks/study.py analysis build <results>/kernel-latency
   scripts/benchmarks/study.py analysis check <results>/kernel-latency
   scripts/benchmarks/study.py analysis show <folder>             # one line for each instance
   scripts/benchmarks/study.py analysis show <folder> --details   # each check and central result
   scripts/benchmarks/study.py analysis missing [<folder>]        # the runs that checks wait for
   scripts/benchmarks/study.py analysis html <folder>             # index.html at each level
   # how each central result is made: definition, rows, sentences
   scripts/benchmarks/study.py analysis show <results>/kernel-latency --explain [ID ...]
   # a manual verdict (a person, or a proposal that says so in --by)
   scripts/benchmarks/study.py instance verdict <instance folder> --hypothesis H3 --check h \
       --verdict wrong --by "<name>" --text "<why>"

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
notebook runs (nbclient) with the environment variables
``LATBENCH_INSTANCE`` (the instance folder) and ``LATBENCH_REPO`` (the
safety repository; ``scripts/benchmarks/data.py`` loads the instance), in
the safety repository. The output goes to ``<instance>/notebooks/<name>.html``,
and ``notebooks.json`` has the digest of the inputs (the notebook and
``study.json``): with the same digest, the notebook does not run again.
The instance page links to the notebooks. The output is not byte-stable,
so ``analysis check`` does not compare it. The packages are in
``scripts/benchmarks/requirements-notebooks.lock``; the other commands do
not need them.

``analysis show`` and ``analysis missing`` read the instances at and below
the folder that you give (any folder of a results tree). They name each
instance by its folder below the results folder. The one line of an
instance gives the hypotheses in numbers (confirmed, wrong, open, and the
``draft`` checks), the central results with a sentence, the acceptance
checks that are not confirmed, the notes, the failed runs (a
``<UTC>.failed.json`` in the instance) and ``PROVISIONAL``. ``--details``
gives each check with its measured text, each central result with its
sentences or the reason why it has none, the failed runs, and for an open
manual check its statement and the ``instance verdict`` command that
closes it. ``analysis missing`` lists each experiment without an evidence
run in an instance, with the checks and central results that wait for it:
the runs to make next.

Other commands: ``instance add --role excluded --reason <text>``,
``instance exclude ROOT --campaign ID --reason TEXT`` (the role
``excluded`` for all runs of a campaign, for example a test of the tools;
the entry keeps the earlier role in ``role_before``),
``instance reference`` (a run of another instance that a check reads),
``instance seal``, ``instance verify``, and ``instance merge OTHER ROOT``: it adds the runs
of another results tree that ROOT does not have, with their roles, after
it checks their seals and digests. Use ``instance merge`` for a results
tree that is not in a lab space. Between two lab spaces, use ``study.py
lab export`` and ``study.py lab import`` (see :doc:`../../explanation/lab-exchange`). If OTHER is a
local copy, ``--origin HOST:PATH`` records the original tree in
``copied_from``.

``analysis build`` writes only derived files; it does not change a raw run or
``instance.json``. The same inputs and the same revision of the tools
give the same bytes: ``analysis check`` builds again and compares the JSON
files (``run.json``, the app data, ``experiment.json``, ``study.json``; not
the plots, the pages or the notebooks). Each aggregate
records the safety revision of the tools (``made_by``); ``dirty: true``
means that the tools had changes that were not committed.

``lab init``
------------

.. code-block:: console

   study.py lab init [FOLDER] --repo REPO [--name N] [--trees-root DIR] [--trees-source DIR]
                              [--sdk DIR] [--results DIR] [--hw-map FILE]

The setup order of a lab space is: make the lab folder, clone the safety
repository into it, make a virtual environment with
``scripts/benchmarks/requirements.lock`` of that clone (the exact versions;
``requirements.txt`` has the ranges), and run ``lab init`` with the Python
of that environment, in the lab folder. ``FOLDER`` is the current folder
by default.

``lab init`` makes ``FOLDER/.lab/config``, the results folder and the
trees root. ``REPO`` must have ``scripts/benchmarks/study.py``. If
``FOLDER`` is a lab space already, the command stops. The virtual
environment of the Python that runs ``lab init`` goes into ``[python]
venv``. ``lab init`` warns if it runs without a virtual environment, or if
a package of ``requirements.txt`` is missing or does not have a version
in its range (``lab status`` gives the same warnings). A path in
``FOLDER`` goes into the file as a relative path. The command prints the
next step, ``study.py trees setup <tree>``. If the hardware map
does not exist, it tells you to make it with twister. If the results
folder is outside ``FOLDER``, it gets the file ``.lab-space`` with the
path of the lab folder: the build then finds the lab space of the results
also from another folder (``lab.owner()``, not the current folder).

``lab status``
--------------

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
- The last three campaigns, and each imported campaign that is not
  complete.

``lab hwcheck``
---------------

.. code-block:: console

   study.py lab hwcheck BOARD [--tree TREE]

The command makes sure that the loopback wire of a board works. It builds
the app ``tests/benchmarks/loopback_check`` for the board from a pinned
tree, through the build cache like a point of a run, and copies the
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
``.lab/hwcheck/<board>.json``. A record has the time, the host, the tree,
the design repo commit (``repo``: ``rev``, ``dirty``), the probe and the
console, the image (SHA-256, cache key, from build or cache), the result
and all console lines (with the loopback measurement). The pre-flight
check of a campaign names the record of its check. If the design
repository has changes that are not committed, the image cannot go into
the cache: the check builds in ``.lab/hwcheck/<board>/build/`` and the
record has ``repo.dirty: true``.

``campaign run --hwcheck-each`` also does the check before each
experiment; the experiment gets the record of its check (``hwcheck``). If
the check fails, the experiment is ``failed`` (the note says why) and the
campaign goes on with the next one. From the cache, a check takes 10 s to
20 s.

.. _benchguide-lab-trees:

Pinned trees (``study.py trees``)
---------------------------------

.. code-block:: console

   study.py trees setup [TREE ...]
   study.py trees check [TREE ...]
   study.py trees show [TREE ...]
   # all three: [--trees-root DIR]

The pins are the west manifests ``validation/trees/<tree>.yml`` (see
:doc:`../files/trees-yaml`). The paths come from the lab space. ``setup`` makes the
west workspace ``<trees root>/<tree>/`` of each tree, with a copy of its
manifest, and runs ``west update`` with the cache ``<[trees]
source>/<tree>`` of the lab space if it exists. A project that is not in
the cache comes from its ``url``. Nothing is written into the cache. Set
up only the trees that the studies of the lab space need, for example
``study.py trees setup ws-safety ws-up``.

``check`` gives the state of each tree: ``ok``, ``not set up``
(information; an error for a tree that you name) or ``wrong`` (an
error). A tree that is not a west workspace yet, or whose ``.west/config``
has a key that ``west init`` does not write (for example
``build.cmake-args``), is not ``ok``. ``show`` prints the trees root, the
trees, the revisions and the paths.

A lab space made before 2026-10-28 has its trees as plain clones in the
same paths. ``trees setup <tree>`` makes them a west workspace: it adds the
manifest copy and ``.west/`` and keeps the clones.

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

``check`` prints the plan and then the pre-flight check. The plan has one
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

:doc:`../../howto/resume-a-campaign` describes ``resume``.

Design lint (``study.py design lint``)
--------------------------------------

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

New study or experiment (``study.py design scaffold``)
------------------------------------------------------

.. code-block:: console

   scripts/benchmarks/study.py design scaffold study PARENT/st-NAME
   scripts/benchmarks/study.py design scaffold experiment STUDY/ex-NAME --app APP [--board B]

``scaffold study`` makes a new sub-study ``st-NAME/`` of the study
``PARENT``, with these files:

- ``study.yaml``: the name, a ``question``, no ``experiments`` and an
  empty ``central_results``.
- ``study.md``: the sections Background, Experiments and References.
- ``hypotheses.yaml``: one template hypothesis ``H1`` without checks.

The command also adds ``use: NAME`` to ``substudies`` of the parent
``study.yaml``. The new study has no experiment and its hypothesis has no
check: write each check when the experiment that it reads exists. A
template check would give a verdict from a limit that nobody wrote.

``scaffold experiment`` makes the experiment ``ex-NAME/`` and adds it to
``experiments`` of ``STUDY/study.yaml``, and a line for it to the section
Experiments of ``STUDY/study.md``. The edits are text edits, so the
comments of the files stay.

The template ``experiment.yaml`` has the app, the board (only with
``--board``), the first tree of ``validation/trees/`` (by name), one axis
``variant`` with the value ``default``, and the acceptance check ``A1``
(no invalid samples). The metric of ``A1`` is the main metric of the app:
``irq`` for ``irq_latency``, ``isr2thr`` for ``wake_latency``, ``t2t``
for ``thread_latency``. A name has only lower case letters, digits and
``-``. An experiment name must be unique over all studies.
