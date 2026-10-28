.. _benchguide-export-file:

Export file
===========

``study.py lab export`` writes the export file ``FILE`` (a ``tar.gz``
file) and its digest ``FILE.sha256`` (see :doc:`../cli/study-py`).
:doc:`../../explanation/lab-exchange` tells why an import does these
checks.

Content
-------

The archive has:

``export.json``
   The index of the export. It has:

   - the format ``latbench-export/2``, the :term:`lab space`, the host and the
     commit of the :term:`design repository`.
   - for each :term:`experiment` of the runs: the file, its SHA-256, its parsed
     content and its earlier names.
   - for each :term:`instance` of the runs: ``study.yaml`` and
     ``hypotheses.yaml`` with their SHA-256, the references and the
     manual :term:`verdicts <Verdict>`.
   - for each run: the instance path, the run-list entry (``id``,
     ``digest``, ``role``, ``reason``, ``campaign``), the experiment, the
     board, the :term:`campaign` and the :term:`tree` pins.
``runs/<instance folder>/ex-<experiment>/<UTC>/`` and ``<UTC>.sha256``
   The raw :term:`runs <Run>` and their :term:`seals <Seal>`.
``campaigns/<id>.json``
   The records of the campaigns of the runs.
``repo.bundle``
   A git bundle of the commits of the design repository that the runs and
   the campaigns used, with their history (about 3 MB). ``export.json``
   lists the commits that the exporting repository does not have
   (``bundle.missing``).

Import checks
-------------

``lab import`` first makes sure that ``FILE`` has the digest of
``FILE.sha256``. It refuses an export of this lab space. Then it does
these checks for each run:

.. list-table::
   :header-rows: 1
   :widths: 60 40

   * - Condition
     - Result
   * - The run id is in the results tree with another digest (collision).
     - The run is refused.
   * - The run id is in the results tree with the same digest.
     - The run is skipped.
   * - The content of ``experiment.yaml`` differs between the two lab
       spaces, or the experiment is not in the design here (see the
       content rules below).
     - The run is refused.
   * - ``study.yaml`` or ``hypotheses.yaml`` of the instance differs.
     - A warning. The build here uses the design files here.
   * - The tree pins of the run differ from ``validation/trees/``
       here.
     - A warning.
   * - The seal does not give the digest of the run-list entry.
     - The run is refused.
   * - The run folder exists here, but it is not in the run list.
     - The run is refused.

The content of an experiment is the parsed YAML without comments,
``name`` and ``renamed_from``. Thus these changes are no difference:

- a comment.
- a rename with ``renamed_from``: the run keeps its id, and the earlier
  name maps to the new one.

An export of format 1 has only the SHA-256 of the file. For such an
export, the bytes count.

After the checks
----------------

The import copies each run that it accepts, with its seal, into its
instance. It adds the run-list entry with its :term:`role` and reason. If the instance does not exist, the
import makes it, with the board of the run at the level that fixes the
board in the other lab space. ``copied_from`` of the entry is
``lab <lab id>, campaign <id>``. The campaign records go to
``.lab/campaigns/<id>@<lab id>.json``. A record of a campaign that ran
at the time of the export gets
``running_at_export`` (the time of the export), and ``lab status`` and
``campaign status`` show it as ``imported, not complete``. A later import
with the end of the campaign replaces the record. ``lab import --close
<id>@<lab id>`` ends the record here (status ``closed``). An older export
does not open it again. The
default of ``campaign status`` (the latest campaign) is never an imported
record.

The import fetches the commits of ``repo.bundle`` (after ``git bundle
verify``) into the design repository of this lab space, as the local refs
``refs/latbench/import/<lab id>/<commit>``. Thus ``run.py --rebuild`` of an
imported run works here. These refs are local. If the bundle is missing
or the fetch fails, the import gives a warning.

The import also adds the references and the manual verdicts of each
instance that exists here.
