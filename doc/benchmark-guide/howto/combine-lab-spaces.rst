Combine lab spaces
==================

:doc:`../explanation/lab-exchange` describes the export, the import and their
checks.

.. code-block:: console

   study.py lab export [FOLDER] -o FILE [--campaign ID ...] [--all]
   study.py lab import FILE [--dry-run]
   study.py lab import --close ID@LAB

``--dry-run`` does only the checks. The command prints each warning, each
refused run and the numbers. It exits with 1 if it refused a run. After
an import, build the results tree (``study.py analysis build``).
