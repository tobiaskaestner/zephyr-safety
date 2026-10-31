The probatrix package
=====================

``probatrix`` is the Python package behind ``study.py``. It lives in
``scripts/probatrix/``. It has a generic core and the kinds of study.
This page explains how the parts fit together.
The latency benchmarks are the first kind. Other kinds come later.

The core and the kinds
----------------------

The core is in ``scripts/probatrix/core/``. It does the work that every
kind of study needs. It reads and checks the design files, builds the
results, seals the runs, runs the campaigns and evaluates the checks.
The core imports no kind.

A kind knows one sort of evidence. It knows how to make the points of an
experiment, how to read the data of a run, and how to read one value from
the data. The core calls these functions through the *Kind interface*. It
calls nothing else of a kind.

The kind ``latbench`` is in ``scripts/probatrix/benchmarks/``. It has all
the code for the latency benchmarks: the builds, the boards, the
histograms, the M4 data and the notebooks. The kinds ``tlaplus`` and
``cbmc`` are planned. They will check a formal model against the code.
They will use the same core.

The Kind interface
------------------

``core/kinds.py`` defines the interface. The class ``Kind`` is the
contract. The class ``BaseKind`` is the class to inherit from. It gives a
default to each optional hook. A new kind writes only the required hooks.

A kind must have these hooks:

- ``name``, ``schema_prefix``, ``schema_folder``, ``format_prefix`` and
  ``ref_prefix``: the identity of the kind, and the places of its schemas
  and git refs.
- ``tool``: the name of the program that makes the data.
- ``points``: the points of an experiment.
- ``run_json`` and ``app_json``: the data of a run and of its app.
- ``value`` and ``known``: one value of the data, and the values that
  exist.

A kind can change these optional hooks:

- ``dirt_paths``: the paths that make a tree dirty.
- ``format_id`` and ``ref``: the format names and the ref names. They come
  from the prefixes by default.
- ``width``, ``seen`` and ``is_point_agg``: details of the check forms.
- ``extra_forms``: check forms of the kind.
- ``generated_checks``: checks that the kind writes itself.
- ``instance_axis``: a rule that splits an instance, for example by
  board. The default is no axis.
- ``experiment_json``, ``plot``, ``central_result`` and ``pending``: the
  aggregates and the plots.
- ``commands``: commands of the kind for ``study.py``.

``core/kinds.py`` keeps a registry. A kind module registers its kind when
it is imported. The list ``PLUGINS`` names the modules that ``get()``
imports on demand. ``kind_of()`` finds the kind of a study or experiment.

Project and design roots
------------------------

A ``Project`` (``core/config.py``) tells the core where things are. It
holds the repository, the *design roots*, the default kind and the name
prefixes of studies and experiments. A design root (``Root``) is the
folder of the top studies. It has a path and the name of a kind. Today the
Project has one root, ``validation/empirical/latencies/``. Formal studies
will have their own root.

The core reads the Project with ``config.project()``. A test replaces it
with ``config.use(project)``.

The kind key
------------

The kind of a study will come from the key ``kind:`` in its
``study.yaml``. A sub-study and an experiment inherit it from the study
above. A study without the key uses the default kind of the Project, which
is ``latbench``. The key is not in the design files yet. A later commit
adds it. Until then, every study is a ``latbench`` study.

The launchers
-------------

Three launchers start the same command line:

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Launcher
     - Use
   * - ``scripts/probatrix/study.py``
     - The launcher to use. ``python -m probatrix`` does the same.
   * - ``scripts/probatrix/benchmarks/study.py``
     - The compat launcher. Old lab spaces and old command lines start it.
   * - ``scripts/benchmarks/study.py``
     - The launcher of the layout before ``probatrix``. A lab space with
       an old clone of the design repository still uses it.

The list ``LAUNCHERS`` in ``benchmarks/studylib/lab.py`` holds the three
paths, newest first. A lab space can hold a clone of any age. So the
tools look for the launchers in this order and take the first that the
clone has.

The lab re-exec
---------------

In a lab space, each launcher runs the launcher of the design repository
of the lab space. It runs it with the Python of the lab space. This
re-exec makes sure that the code and the Python packages of the lab space
are the ones in use.

The re-exec comes first. A launcher puts ``scripts/`` on ``sys.path`` and
loads ``studylib/lab.py`` from its file. It does not import the package at
this point. The package needs PyYAML, and the Python that starts the
launcher can lack it. The launcher imports the package only after the
re-exec. ``run.py`` follows the same order. Tests start the launchers with
a ``yaml`` module that raises ImportError, and they check that the
re-exec happens.

The variable ``LATBENCH_STUDY_REEXEC`` stops a second re-exec. The
command ``lab init`` never re-execs.

Evidence stays out of the repository
------------------------------------

The repository holds code, designs and schemas. It does not hold evidence
data. Runs, instances, results and notebook outputs stay in the results
tree of a lab space. The design records the commit of the code that made a
run (see :doc:`reproducibility`). The results tree is not in the
repository. This rule holds for every kind.

Related pages
-------------

- :doc:`architecture`: the parts of the suite and the flow of the data.
- :doc:`studies-and-verdicts`: studies, hypotheses and verdicts.
- :doc:`../reference/cli/study-py`: the commands of ``study.py``.
