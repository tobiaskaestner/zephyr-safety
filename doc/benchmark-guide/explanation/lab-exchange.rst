.. _benchguide-lab-exchange:

Export and import
=================

``lab export`` writes the runs of this lab space to ``FILE`` (a
``tar.gz`` file) and its digest to ``FILE.sha256``. The default is the
runs that this lab space made (the ``lab`` of the manifest).
``--campaign`` selects the runs of these campaigns. ``--all`` selects all
runs, also the runs from another lab. ``FOLDER`` selects only the
instances below this folder of the results tree. The export stops if the
seal of a run does not give the digest of the run list.

The archive has:

``export.json``
   The format ``latbench-export/2``, the lab space, the host, the commit
   of the design repository, the design files of the exporting lab (for
   each experiment: the file, its SHA-256, its parsed content and its
   earlier names; ``study.yaml`` and ``hypotheses.yaml`` of each
   instance, with their SHA-256), and for each run: the instance path,
   the run-list entry (``id``, ``digest``, ``role``, ``reason``,
   ``campaign``), the experiment, the board, the campaign and the tree
   pins.
``runs/<instance folder>/ex-<experiment>/<UTC>/`` and ``<UTC>.sha256``
   The raw runs and their seals.
``campaigns/<id>.json``
   The records of the campaigns of the runs.
``repo.bundle``
   A git bundle of the commits of the design repository that the runs and
   the campaigns used, with their history (about 3 MB). ``export.json``
   lists the commits that the exporting repository does not have
   (``bundle.missing``).

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
   * - The content of ``experiment.yaml`` differs between the two labs, or
       the experiment is not in the design here. The two labs work from
       different design files. The content is the parsed YAML without
       comments, ``name`` and ``renamed_from``, so a comment or a rename
       (``renamed_from``: the run keeps its id, and the earlier name maps
       to the new one) is no difference. An export of format 1 has only
       the SHA-256 of the file: then the bytes count.
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

Then the import copies the run and its seal into its instance and adds
the entry with its role and reason. If the instance does not exist, the
import makes it, with the board of the run at the level that fixes the
board in the other lab. ``copied_from`` of the entry is
``lab <lab id>, campaign <id>``. The campaign records go to
``.lab/campaigns/<id>@<lab id>.json``. Thus a running campaign of the
other lab also makes the verdicts here provisional. Such a record gets
``running_at_export`` (the time of the export), and ``lab status`` and
``campaign status`` show it as ``imported, not complete``. A later import
with the end of the campaign replaces the record. If the other lab
exports no more, ``lab import --close <id>@<lab id>`` ends the record
here (status ``closed``); an older export does not open it again. The
default of ``campaign status`` (the latest campaign) is never an imported
record.

The import fetches the commits of ``repo.bundle`` (after ``git bundle
verify``) into the design repository of this lab space, as the local refs
``refs/latbench/import/<lab id>/<commit>``. Thus ``run.py --rebuild`` of an
imported run works here. Do not push these refs. If the bundle is missing
or the fetch fails, the import gives a warning.
