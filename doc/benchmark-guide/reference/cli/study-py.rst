The tool study.py
=================

The commands that change a run list are below ``study.py instance``. In a
lab space, a campaign makes the instances and adds each run (see
:doc:`../../lab`). Without a campaign, use these commands:

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
lab export`` and ``study.py lab import`` (see :doc:`../../lab`). If OTHER is a
local copy, ``--origin HOST:PATH`` records the original tree in
``copied_from``.

``analysis build`` writes only derived files; it does not change a raw run or
``instance.json``. The same inputs and the same revision of the tools
give the same bytes: ``analysis check`` builds again and compares the JSON
files (``run.json``, the app data, ``experiment.json``, ``study.json``; not
the plots, the pages or the notebooks). Each aggregate
records the safety revision of the tools (``made_by``); ``dirty: true``
means that the tools had changes that were not committed.

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
