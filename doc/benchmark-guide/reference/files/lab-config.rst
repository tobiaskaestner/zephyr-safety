.. _benchguide-lab-space:

The lab space
=============

A :term:`lab space` is a folder with the file ``.lab/config``, as a west
workspace is a folder with ``.west/config``. The tools find the lab space
from the current folder upwards. Thus the tools must run in the lab
folder or in a folder below it. :doc:`../../howto/set-up-a-lab-space`
gives the steps to make a lab space.

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
       the exports and the :term:`campaign` records name the lab space by its id.
   * - ``[lab] name``
     - The name of the lab space (default: the folder name).
   * - ``[design] repo``
     - The :term:`design repository`: the clone of the :term:`safety repository`
       with the :term:`study` designs and the tools.
   * - ``[trees] root``
     - The folder of the pinned :term:`trees <Tree>` (default ``trees``).
   * - ``[trees] source``
     - Optional. A folder with ``<tree>/<path>`` clones, for example the
       trees root of another lab space. ``trees setup`` clones from it
       first.
   * - ``[toolchain] zephyr_sdk``
     - Optional. The Zephyr SDK. The default is
       ``~/zephyr-sdk-<version>``, with the version of the tree manifests
       in ``validation/trees/``.
   * - ``[results] root``
     - The folder of the results trees (default ``results``). The results
       tree of the design is ``<root>/kernel-latency``.
   * - ``[hardware] map``
     - The hardware map of the host (default ``hw-map.yml``, see
       :ref:`benchguide-hw-map`).
   * - ``[python] venv``
     - The virtual environment of the lab space. ``lab init`` records the
       environment that it runs in (see the Python restart below).

A lab space for analysis only (an import, ``analysis build``, ``analysis
show``) needs no trees and no hardware map. ``run.py``, ``campaign run``
and ``lab hwcheck`` need them.

The folder ``.lab/`` also holds the :term:`build cache` (``build-cache/``), the
campaign records (``campaigns/``), the locks (``locks/``: one for each
board and one for the results build) and the :term:`wire checks <Wire check>`
(``hwcheck/<board>.json`` and ``hwcheck/<board>/``).

.. _benchguide-python-restart:

The tools use the lab space as follows:

- ``study.py`` runs the ``study.py`` of the design repository of the lab
  space, with the Python of ``[python] venv``. You can start another
  ``study.py`` (for example of a different worktree) or another Python.
  It then starts the ``study.py`` of ``[design] repo`` with the Python of
  the lab space and the same arguments. ``study.py lab init`` is the
  exception. Thus the packages are always those of the lab space.
- ``run.py`` and ``plot.py`` start again with the Python of ``[python]
  venv`` if another Python runs them. They keep the script that you
  started. ``run.py`` stops if the lab space uses a different design
  repository. It takes the hardware map of the lab space by default.
- ``latbench.py``, ``m4.py`` and ``loadmodel.py`` do not start again.
  Except for ``latbench.py capture``, they need only the standard library
  of Python (see :doc:`../cli/scripts`).
- The trees root comes from ``--trees-root``, the environment variable
  ``LATBENCH_TREES_ROOT`` or ``[trees] root``, in this order. Without a
  lab space and without the two overrides, a tool that needs a tree
  stops.
- The SDK path comes from ``[toolchain] zephyr_sdk``.
