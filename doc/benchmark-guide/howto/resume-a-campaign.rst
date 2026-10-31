Resume a campaign
=================

Resume a :term:`campaign` after it stopped: a crash, Ctrl-C, a failed
pre-flight check, or failed experiments. :ref:`benchguide-resume-rules`
tells what ``resume`` does with each experiment.

#. Find the id of the campaign. ``lab status`` lists the last three
   campaigns. ``campaign status`` without an id gives the latest one:

   .. code-block:: console

      safety/scripts/probatrix/study.py lab status
      safety/scripts/probatrix/study.py campaign status

#. Read the states and the notes of the experiments:

   .. code-block:: console

      safety/scripts/probatrix/study.py campaign status <id>

#. If a note names a problem of the host or the board (the wire, the
   console, the disk), correct it first (see :doc:`troubleshoot-a-run`).
#. Make sure that the design repository is clean and at the commit of
   the campaign. If it moved, check out the ref of the campaign:

   .. code-block:: console

      git -C safety switch --detach refs/latbench/campaign/<id>

#. Resume the campaign. ``--detach`` runs it in the background:

   .. code-block:: console

      safety/scripts/probatrix/study.py campaign resume <id> [--detach]

#. When the campaign is done, read the verdicts:

   .. code-block:: console

      safety/scripts/probatrix/study.py campaign status <id> --verdicts

#. If you checked out the ref in step 4, go back to your branch:

   .. code-block:: console

      git -C safety switch <branch>

:doc:`../reference/cli/study-py` gives the options of ``campaign
resume``.
