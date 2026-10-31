Combine lab spaces
==================

Give the runs of lab space A to lab space B. :doc:`../reference/files/export`
gives the content of an export and the checks of an import.
:doc:`../explanation/lab-exchange` tells why.
:doc:`../tutorials/combine-two-labs` does these steps with real output.

#. In the lab folder of A, export the runs:

   .. code-block:: console

      safety/scripts/probatrix/study.py lab export [FOLDER] -o <file>.tar.gz [--campaign ID ...] [--all]

   Without options, the export has the runs that A made. ``--campaign``
   selects the runs of some campaigns. ``--all`` also adds the runs that A
   imported.
#. Copy ``<file>.tar.gz`` and ``<file>.tar.gz.sha256`` to the host of B
   (for example with ``scp``).
#. In the lab folder of B, do the checks of the import only:

   .. code-block:: console

      safety/scripts/probatrix/study.py lab import <file>.tar.gz --dry-run

#. Read each warning and each refused run. A refused run of an experiment
   that is not in the design of B, or that differs there, stays refused.
   To accept it, B needs the same experiment file as A.
#. Import the runs:

   .. code-block:: console

      safety/scripts/probatrix/study.py lab import <file>.tar.gz

#. Build the results tree of B:

   .. code-block:: console

      safety/scripts/probatrix/study.py analysis build results/kernel-latency

#. A campaign of A can be incomplete at the time of the export. If A
   exports no more, close the record of this campaign in B. Then its
   experiments do not make the verdicts of B provisional:

   .. code-block:: console

      safety/scripts/probatrix/study.py lab import --close <id>@<lab id of A>

:doc:`../reference/cli/study-py` gives the options of ``lab export`` and
``lab import``.
