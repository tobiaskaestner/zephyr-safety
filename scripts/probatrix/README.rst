.. Copyright (c) 2026 inovex GmbH
.. SPDX-License-Identifier: Apache-2.0

probatrix
=========

``probatrix`` is the Python package behind the study tools of the safety
repository. It has a generic core and the kinds of study.

Folders
-------

``core/``
   The generic engine: Project and design roots, the Kind interface, design
   files and schemas, builds, checks, seals, runs, campaigns and the
   loading of a built instance. It imports no kind.

``benchmarks/``
   The kind ``latbench``: the latency benchmarks, with the runner, the
   trees, the boards, the histograms, the M4 data and the notebooks.

``tlaplus/``
   The kind ``tlaplus``: TLA+ model checks of ``spec/tla``. It has the list
   parser, the subject trees of a run and the adapter for TLC runs (model
   checking and simulation) and the importer of lab runs (``import-lab``).
   Its design root is ``validation/formal/kernel-spec``.

Start the tools
---------------

Use the launcher ``scripts/probatrix/study.py``. ``python -m probatrix``
does the same. The launcher ``scripts/probatrix/benchmarks/study.py`` is
the compat launcher for old lab spaces and old command lines.

.. code-block:: console

   scripts/probatrix/study.py --help
   scripts/probatrix/study.py <namespace> <command> --help

Run the tests
-------------

Run this command in the root of the repository:

.. code-block:: console

   pytest scripts/probatrix

The folders ``core/tests/`` and ``benchmarks/tests/`` hold the tests.

More information
----------------

The page "The probatrix package" in the Latency Benchmark Guide
(``doc/benchmark-guide/explanation/probatrix.rst``) explains the core, the
kinds, the launchers and the lab re-exec.
