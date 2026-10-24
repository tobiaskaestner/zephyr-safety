Latency Benchmark Guide
=======================

This guide is for the users and the maintainers of the latency benchmark
suite in ``tests/benchmarks/`` of the safety repository. It tells you what
the suite measures and how to set up the hardware. It also tells you how
to run a reproducible experiment and how to extend the suite.

The guide describes the code. It does not give measurement results,
because results change with each tree and each experiment. The results of
a run are in its result folder (see :ref:`benchguide-result-folder`).

All paths in this guide are relative to ``tests/benchmarks/``, unless a
path starts with ``tests/``.

.. toctree::
   :maxdepth: 2

   purpose
   hardware
   apps
   common
   kconfig
   output
   host-tools
   extending
   boards
   pitfalls
