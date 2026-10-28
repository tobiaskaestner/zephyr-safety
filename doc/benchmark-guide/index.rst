Latency Benchmark Guide
=======================

This guide is for the users and the maintainers of the latency benchmark
suite in ``tests/benchmarks/`` of the safety repository. It tells you what
the suite measures and how to set up the hardware. It also tells you how
to run a reproducible experiment and how to extend the suite.

The guide describes the code. It does not give measurement results,
because results change with each tree and each experiment. The results of
a run are in its result folder (see :ref:`benchguide-result-folder`).

All paths in this guide are relative to ``tests/benchmarks/``. A path
that starts with ``tests/``, ``scripts/`` or ``validation/`` is relative
to the root of the safety repository.

The guide has four parts, as in `Diátaxis <https://diataxis.fr/>`_. Each
part answers a different question:

- **Tutorials**: lessons. You do the steps, and you get a working result.
- **How-to guides**: the steps of one task, for a reader who knows the
  suite.
- **Reference**: the facts of the tools, the files, the options and the
  terms.
- **Explanation**: how the method and the tools work, and why.

.. toctree::
   :maxdepth: 2
   :caption: Tutorials

   tutorials/index

.. toctree::
   :maxdepth: 2
   :caption: How-to guides

   howto/index

.. toctree::
   :maxdepth: 2
   :caption: Reference

   reference/index

.. toctree::
   :maxdepth: 2
   :caption: Explanation

   explanation/index

.. toctree::
   :maxdepth: 2

   purpose
   hardware
   apps
   common
   kconfig
   output
   host-tools
   unit-tests
   m4
   studies
   lab
   extending
   boards
   pitfalls
