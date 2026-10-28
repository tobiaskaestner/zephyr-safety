0004. The firmware hash is the source revision of an image
===========================================================

Status
------

Accepted, 2026-10-27.

Problem
-------

Each app prints the revision of its source (``LATBENCH_SRC_REV``), and the
image contains the string. With the commit of the safety repository as
this revision, each commit gave other images, also a commit that changed
only a study design or a host script. Thus the build cache was empty after
each commit, and two images of the same firmware looked different.

Decision
--------

``LATBENCH_SRC_REV`` is a content hash of the firmware files of
``tests/benchmarks`` (kind ``firmware/1``): all files without the host
scripts in ``scripts/``, Python, Markdown, ``testcase.yaml`` and
``boards.yaml``. The manifest of a run records it with its kind and the
commit.

Results
-------

- The same firmware at two commits gives the same image.
- The code digest (the image with this string set to zeros) compares runs
  of the older kinds (a commit, a git tree hash) with the new ones.
