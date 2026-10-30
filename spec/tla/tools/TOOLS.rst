..
   Copyright (c) 2026 inovex GmbH
   SPDX-License-Identifier: Apache-2.0

#####################################
Tool note: the tools of the TLA+ work
#####################################

:Status: draft, 2026-10-30. Not reviewed.

This note is the record of the tools that give or check the evidence of
the formal model in ``spec/tla``. IEC 61508-3, 7.4.4, puts a tool that
supports the verification of the design in class T2: an error in the tool
can fail to show a defect. For each tool, the note gives the version, the
identity of the file, the environment, the use, the known defects with the
reason why each one does not affect the evidence, and the regression tests.

The note is a separate file and not a section of the design note
(``README.rst``) for three reasons. The note changes with a tool version,
not with the model. It also covers tools outside ``spec/tla`` (CBMC, the
doc extension). And an assessor can read the record of each tool version
in one place.

.. contents::
   :local:

TLC
***

Identity
========

.. list-table::
   :widths: 25 75

   * - File
     - ``tla2tools.jar``
   * - Version
     - v1.8.0 pre-release, TLC2 Version 2026.10.20.183001
   * - Git revision
     - ``d2e1472884d292df7b0ed788712b1af262edc16e`` of
       https://github.com/tlaplus/tlaplus (``X-Git-Revision`` of the
       manifest; build ``master__d2e1472``, commit count 9039)
   * - Build date
     - 2026-10-20T18:30:01.836Z (``Build-TimeStamp`` of the manifest)
   * - SHA-256
     - ``5bd7b64db99ae4c6c35f290de5e809c0ee41af43f8699cf696099ffb6452b1e2``
       (``tools/tla2tools.sha256``)
   * - Download
     - https://github.com/tlaplus/tlaplus/releases/download/v1.8.0/tla2tools.jar,
       2026-10-22
   * - Archive
     - ``/wrk/z/lab-tla/archive/tla2tools/sha256-<hash>/`` on the lab host
       and ``/wrk/z/tla-archive/tla2tools/sha256-<hash>/`` in the workspace.
       Read-only, with ``ARCHIVE.txt`` (the data of this table) and
       ``tla2tools.jar.sha256``.

The tag v1.8.0 is a rolling pre-release: each new build replaces the jar
at the download URL. A download of 2026-10-29 gave another build (rev
``56d37a9``, another hash). Thus the name "v1.8.0" does not identify the
tool. The hash and the archived file identify it. ``run_tlc.sh`` stops if
the jar has another hash.

Environment
===========

- Lab host (the evidence runs): Eclipse Temurin 25.0.5+8, x64
  (tarball SHA-256
  ``68982529869257d0ee6b824ec5aa270ff8b118bb438670da0b97ebdab178d7fb``),
  in ``/wrk/z/lab-tla/jdk/``. AMD Ryzen 5 5600X, 6 cores, 12 hardware
  threads, 31 GB.
- Local host (development): OpenJDK 25.0.4.1 of Fedora
  (``Red_Hat-25.0.4.1.1-1``), aarch64.
- The two hosts gave the same counts for all 50 lines on 2026-10-29, and
  the same selftest results on 2026-10-30.
- ``~/.tlaplus/esc.txt`` has ``NO_STATISTICS``: TLC sends no statistics
  and does no DNS lookup for them.

Use
===

``tools/run_tlc.sh`` starts each TLC process with these options:

- ``-workers 1`` (see `The one-worker rule`_).
- ``-fp 0``: a fixed fingerprint function. The counts and the traces are
  the same in each run.
- ``-metadir`` and ``-Djava.io.tmpdir``: a new directory for each process.
- ``-cleanup -noGenerateSpecTE``, ``-XX:+UseParallelGC``, ``-Xmx`` from the
  field ``heap=`` of the line or from ``TLC_HEAP``.

The features of TLC that the models use: invariants, action properties
(``[][A]_v``), temporal properties with weak fairness (``WF``),
``INSTANCE ... WITH`` over more than one level, ``CHOOSE``, ``ASSUME``,
model values, definition overrides (``<-``) in the ``.cfg`` files, and
``CHECK_DEADLOCK FALSE`` (one configuration). The sensitivity list
(``mc/sensitivity.txt``) also uses a value for a definition in the ``.cfg``
file (``Threads = {t1, t2, t3, t4}``, which makes a new model value) and
``SYMMETRY`` (the configurations ``*_sym``, safety properties only). The
selftest model ``SelfSym`` checks both. The models do not use
``CONSTRAINT``, ``ACTION_CONSTRAINT``, ``VIEW``, strong fairness,
simulation or ``-continue``.

Known defects and limits
========================

.. list-table::
   :header-rows: 1
   :widths: 30 35 35

   * - Defect or limit
     - Effect
     - Why the evidence runs are not affected
   * - tlaplus issue #1445, "TLC can miss states due to unnormalized
       values". Fixed by PR #1448, after the pinned build.
     - With more than one worker in one TLC process, TLC can drop
       successors and miss violations of invariants, of properties and
       of liveness.
     - Each TLC process of an evidence run has one worker. The defect is
       a race between the workers of one process. Processes that run at
       the same time share only the jar and the modules, which they only
       read. A record with more workers has ``evidence: false``.
   * - tlaplus issue #1475: TLC reports "No error has been found" for a
       model with no initial state.
     - A model that checks nothing looks like a pass.
     - ``run_tlc.sh`` reads the distinct states and reports
       ``no-states``. The selftest model ``SelfNoInit`` checks this. Each
       pass line also has a recorded state count.
   * - Fingerprint collisions (a property of the method, not a defect).
     - TLC keeps a 64-bit fingerprint of each state. Two states with the
       same fingerprint count as one, and the second one is not
       examined.
     - TLC prints an estimate of the probability. The summary and the
       record of each run have the estimate of each pass line (columns
       "calculated" and "actual"). See the reference run below for the
       values.
   * - TLC names only one violated temporal property. For more than one,
       it writes "Temporal properties were violated", without a name.
     - A run that violates two temporal properties does not name them.
     - ``run_tlc.sh`` then gives a result without the expected name, and
       the line fails. The error is in the safe direction.
   * - TLC checks temporal properties on the graph that a ``CONSTRAINT``
       or an ``ACTION_CONSTRAINT`` cuts, and ``SYMMETRY`` or ``VIEW`` are
       not sound for liveness.
     - A false lasso, or a missed lasso.
     - No configuration uses these features. Rule: a configuration with
       ``PROPERTIES`` has no constraint, no symmetry and no view.

Regression tests of the tool
============================

1. **The selftest** (``selftest/``, ``selftest/expected.txt``): small
   models with answers that follow from the model, one for each feature
   that the evidence runs use. An invariant violation with a known trace
   length, an action-property violation, a liveness violation with a
   known lasso under ``WF``, a liveness pass that needs the fairness, an
   ``INSTANCE ... WITH`` chain of three modules with a known state count,
   a ``CHOOSE`` with one witness and an ``ASSUME`` (true and false), a
   model with no initial state, two runs with ``-fp 0`` that must give
   the same counts, and a symmetry set with a value of a definition in the
   ``.cfg`` file (``SelfSym``, known counts with and without the symmetry,
   and a violation under it). The selftest also checks ``run_tlc.sh``: each kind of
   result goes through its parser. The models do not change when the specs
   change. The lab runner runs the selftest before each run, with one
   worker. If the selftest fails, no model runs.
2. **The recorded counts**: each pass line of ``mc/expected.txt`` has
   ``states=`` and ``depth=``. With ``-fp 0`` and one worker, the counts
   are deterministic. A different count fails the line. A change of the
   state space is then visible, also if the verdict stays ``pass``.
3. **The probes and the mutants** of ``mc/``: each probe (``Reach_*``,
   lines ``probes``) must be violated, so the states that a property talks
   about exist. Each mutant (``MCMutant``, lines ``fail:<Name>``) must
   give the expected violation. These lines test the tool on the specs,
   and the specs against vacuity. They change with the specs, so they do
   not replace the selftest.

The one-worker rule
===================

An evidence run of TLC has one worker in each TLC process (``-workers
1``). For speed, several TLC processes run at the same time
(``run_tlc_remote.py --jobs``). The rule stays until a new pin with the
fix of #1445 passes the steps of `A new pin`_. Then a decision can
change it.

``run_tlc_remote.py --workers <n>`` with n > 1 stays for experiments. Its
record has ``evidence: false``.

Conditions of an evidence run
=============================

A run of TLC is evidence if all these conditions are true. The lab runner
checks the first four and writes the result to ``record.json``
(``evidence``, ``not_evidence_reasons``):

1. Pinned mode: the run is of a commit of the repository, not of a
   working tree.
2. The jar has the pinned hash.
3. One worker in each TLC process.
4. The selftest ran before the models and gave the expected results.
5. Each line gives its expected result and its recorded counts
   (``status`` 0). A line with an unexpected result is a finding, or a
   change of the model that needs a review and new recorded counts.

A new pin
=========

A jar with another hash is a new tool version, also if its name is
v1.8.0. Before its first evidence run:

1. Archive the jar by hash, read-only, on the lab host and in the
   workspace, with ``ARCHIVE.txt``.
2. Update ``tools/tla2tools.sha256`` and the identity table of this note.
   Read the issues fixed and opened since the old build, and update the
   table of known defects.
3. Run the selftest (``run_tlc_remote.py --selftest-only``). Each line
   must give the expected result.
4. Make a new reference run of all lines with one worker. Compare each
   count with the recorded counts of the old version. Explain each
   difference in the notes, and record the new counts in
   ``mc/expected.txt`` in a separate commit.

A new Java version is a change of the environment. Run the selftest. The
recorded counts check each later run.

Reference runs
==============

.. list-table::
   :header-rows: 1
   :widths: 30 15 55

   * - Run id
     - Commit
     - Result
   * - ``20261030-010342-adbf86df2``
     - ``adbf86d``
     - The first run with the rules of this note: 1 worker, 6 processes,
       heap 2g, selftest passed, all 50 lines as expected. Wall time
       29 min. The counts are equal to round B and are the recorded
       counts of ``mc/expected.txt``. Collision estimates of the pass
       lines: at most 8.5E-7 (calculated) and 2.0E-8 (actual), for
       ``MCScheduler default`` and ``p7_rules``. Peak memory at most
       2.1 GB (``MCScheduler default``).
   * - ``20261030-013351-8b2d2f1a5``
     - ``8b2d2f1``
     - The reference run of the pinned jar: ``evidence: true``. Jar from
       the archive, 1 worker, 6 processes, heap 2g. Selftest: 10 of 10
       lines as expected. Models: 50 of 50 lines as expected, each pass
       line with its recorded counts. Wall time 30 min. Collision
       estimates of the pass lines: at most 8.5E-7 (calculated) and
       2.0E-8 (actual). Peak memory at most 2.2 GB (``small_b``).

Apalache
********

Identity
========

.. list-table::
   :widths: 25 75

   * - File
     - ``apalache-0.62.4.tgz`` (the release), with ``lib/apalache.jar``
       and the launcher ``bin/apalache-mc``
   * - Version
     - 0.62.4, build ``7954daf`` (``Implementation-Version`` of the
       manifest, and the first line of each log)
   * - SHA-256
     - ``b781b53bba32fac14ac2e02b0332e1dc2edc64cb7b850c0608d8142cc7aa2ef4``
       of the tarball, ``e5223915507b65cc5f1638bd037ede60f8a4fc1644aff46355779f9b05df9262``
       of ``lib/apalache.jar`` in it (``tools/apalache.sha256``)
   * - Solver
     - Z3 4.14.1.0, the native library in the jar
       (``com/microsoft/z3/linux/<arch>/libz3.so``)
   * - Download
     - https://github.com/apalache-mc/apalache/releases, 2026-10-21, with
       the ``sha256sum.txt`` of the release
   * - Archive
     - ``/wrk/z/tla-archive/apalache/sha256-<hash>/`` in the workspace.
       Read-only, with ``ARCHIVE.txt`` and ``apalache-0.62.4.tgz.sha256``.
       Not on the lab host yet.

Environment
===========

Local host only (2026-10-30): OpenJDK 25.0.4.1 of Fedora, aarch64. Apalache
needs Java 17 or later. The lab host has no Apalache runs yet.

Use
===

Research only. ``tools/run_apalache.sh`` runs the lines of
``apalache/expected.txt``:

- It stops if the jar has another hash, and if the archived tarball
  exists with another hash.
- One run at a time. ``JVM_ARGS=-Xmx2g`` (``APALACHE_HEAP``). Each run
  is in a systemd scope with ``MemoryMax=3G`` and no swap
  (``APALACHE_MEM``): Z3 runs in the same process outside the Java heap,
  and a run that needs more memory stops alone. ``TMPDIR`` and
  ``--out-dir`` are in the build directory.
- ``typecheck`` for the lines with the name ``typecheck*``. Else
  ``check --no-deadlock`` with ``--init``, ``--next``, ``--inv``,
  ``--length``, ``--cinit`` of the line, and the defaults of the release
  for the other options (``--algo=incremental``,
  ``--smt-encoding=oopsla19``, ``--discard-disabled=true``).
- The script copies ``lib/``, ``objects/``, ``mc/`` and ``apalache/`` into
  one directory and removes the definitions of the key ``omit=``. Today
  this is ``WaitQueue!Head`` and ``WaitQueue!WalkStop``, which Apalache
  does not accept and which no checked formula uses.

The features that the lines use: ``typecheck``, invariants with
``--init`` other than ``Init`` (the inductive step), ``--cinit``,
``--next`` with a part of ``Next``, ``EXTENDS`` of a model module, and
``INSTANCE`` of the library.

Known defects and limits
========================

.. list-table::
   :header-rows: 1
   :widths: 30 35 35

   * - Defect or limit
     - Effect
     - What the lines do
   * - A ``CHOOSE`` without a witness gives an arbitrary value of the type
       (TLC stops with an error).
     - In an inductive step from a state outside the reachable states, an
       operator such as ``RunqBest`` can give a thread that does not exist.
       A counterexample can be spurious, and a pass can depend on it.
     - Each ``IndInv`` has the invariants that give each ``CHOOSE`` one
       witness (``RqStampsNormal``, ``StampsNormal``, ``ArmedOnce``).
   * - ``INSTANCE`` over three levels, with an operator of the first
       module for a constant: "used before it is defined" at the type
       check (0.62.4).
     - ``INSTANCE MCScheduler`` fails.
     - ``APScheduler`` extends ``MCScheduler`` and gives the constants with
       ``--cinit``.
   * - A function constructor ``[x \in S |-> e]`` has a function type, not
       a sequence type. A range must have constant bounds. An operator has
       one result type.
     - ``Waitable!Flush``, ``WaitQueue!Ordered``, ``WaitQueue!Head`` and
       ``WalkStop`` do not type-check or do not run.
     - The expected file records the failures (``fail:120``).
   * - "Trying to expand a set of functions" for ``\E f \in [S -> T]`` in
       an initial predicate.
     - A type domain of a sequence cannot use a function set.
     - ``TypeDom`` of ``APScheduler`` gives ``tq`` with ``SubSeq`` of a
       tuple of three threads.
   * - The cost grows fast with the constants. One run of the inductive
       step of ``MCScheduler`` with all 487 transitions of ``default`` did
       not end in its time limit.
     - Large steps need long runs and much memory: the wake group takes
       about 25 minutes (``small``) and 28 minutes (``default``), with a
       peak of about 2.3 GB.
     - ``APScheduler`` splits ``Next`` into groups, one line for each
       group.
   * - Apalache checks one fixed set of constants for each line
       (``--cinit`` can give a finite family).
     - The result says nothing for 4 threads or 2 CPUs.
     - The evidence scope of a line is its constants. The small-scope
       arguments cover the other sizes.

No survey of the issue tracker is done yet.

Regression tests of the tool
============================

The expected file has known answers: lines that must give ``violated``
(the candidates 0 to 2 of ``APScheduler``, ``range_inv`` and
``order_step`` of ``APWaitQueue``) and lines that must give ``fail:120``
or ``fail:255`` (the type check). A pass of a check line is not evidence
alone: the same file must also show that the check finds a violation.
There is no selftest of Apalache yet (models that do not change with the
specs, like ``selftest/`` for TLC).

Status
======

No Apalache result is evidence today. Before the first evidence run: the
archive on the lab host, a selftest, a survey of the known defects, and a
decision on ``WaitQueue!Head``, ``WalkStop`` and ``Waitable!Flush``
(the workspace notes have the proposals).

CBMC
****

:Version: 6.8.0 of Fedora (``cbmc-6.8.0-1.fc44``, ``cbmc --version``:
   ``6.8.0 (ad933aa-dirty)``). Not the upstream release (6.11.0).
:Use: research only. The harness of ``k_sem_give()`` against a predicate
   from ``KSem.tla`` (workspace notes, ``kernel-unit/cbmc/results.md``).
   The planted defects of the predicate (step 6 of the notes) showed that
   the check finds them.
:Known defects: not surveyed. The Fedora package has local patches
   ("dirty").
:Status: no CBMC result is evidence today. Before the first evidence
   run: the harness in the repository, an upstream release or a recorded
   reason for the distribution package, an archive of the binary by hash,
   known-answer harnesses, and a survey of the known defects.

The doc extension
*****************

:Files: ``doc/_extensions/tla_domain.py``, ``tla_extract.py``,
   ``tla_lexer.py``, ``tla_unicode.py``. The version is the commit of this
   repository.
:Use: the architecture document shows the library. The extension makes a
   ``prop`` need for each property and the links ``expresses`` to the
   requirements. ``tools/kconfig_coverage.py`` checks that each tagged
   Kconfig value and each tagged property has a run.
:Class: T2. The extension and the coverage script build and check the
   traceability. An error in them can hide a missing link or a missing
   run.
:Regression: the tests in ``doc/_extensions/_tests`` (322 passed at
   round B, 2026-10-29).
:Known defects: none recorded.
:Open: a known-answer test that a property without a link, and a tagged
   property without a run, make the build or the script fail.
