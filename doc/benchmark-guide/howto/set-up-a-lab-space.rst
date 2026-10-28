Set up a lab space
==================

A :term:`lab space` holds everything of one host that a study needs.
:doc:`../reference/files/lab-config` gives the keys of ``.lab/config``.
:doc:`../tutorials/set-up-a-lab-space` does these steps with real output.

#. Make the lab folder and go into it.
#. Clone the :term:`safety repository` into the lab folder, for example
   as ``safety``. This clone is the :term:`design repository` of the lab
   space.
#. Make a virtual environment in the lab folder:

   .. code-block:: console

      python3 -m venv .venv

#. Install the exact versions of the packages:

   .. code-block:: console

      .venv/bin/pip install -r safety/scripts/benchmarks/requirements.lock

#. If the host has boards, write the hardware map ``hw-map.yml`` in the
   lab folder (see :doc:`make-a-hardware-map` and
   :doc:`../reference/files/hw-map`). A lab space for analysis only needs
   no hardware map.
#. If the host has local clones of the tree repositories, find their
   folder. It must have the layout ``<folder>/<tree>/<path>``, for example
   the trees root of another lab space. Without local clones, the trees
   come from the ``url`` of each project.
#. Run ``lab init`` with the Python of the environment. Give
   ``--trees-source <folder>`` only if you have local clones:

   .. code-block:: console

      .venv/bin/python safety/scripts/benchmarks/study.py lab init --repo safety [--trees-source <folder>]

#. Set up the trees that the studies of the lab space need (see
   :doc:`../reference/files/trees-yaml`). A lab space for analysis only
   needs no trees.

   .. code-block:: console

      safety/scripts/benchmarks/study.py trees setup <tree> ...

#. Make sure that the lab space is complete:

   .. code-block:: console

      safety/scripts/benchmarks/study.py lab status

#. For each board, do the :term:`wire check`:

   .. code-block:: console

      safety/scripts/benchmarks/study.py lab hwcheck <board>

   If the result is ``RESULT: FAIL``, see :doc:`troubleshoot-a-run`.

:doc:`../reference/cli/study-py` gives the options of ``lab init``,
``trees setup``, ``lab status`` and ``lab hwcheck``.
