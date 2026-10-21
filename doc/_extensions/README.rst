Sphinx Extensions
=================

This directory holds the **downstream** Sphinx extensions of the safety docset —
the ones specific to this project rather than to the documentation engine.

The generic machinery (``doxygen_parser``, ``twister_reader``, ``rst_builders``,
``test_module`` with its ``testmodule`` / ``testreport`` / ``twisterinfo``
directives, and ``xref_builder``) lives in the zdocs engine at
``tools/zdocs/sphinx/_extensions/``, together with its test suite.


Modules
-------

``strictdoc_runner.py``
    Runs ``strictdoc export`` on Sphinx build-init to generate the requirements
    RST from the StrictDoc sources. Used by ``requirements`` and
    ``safety-committee``.

``skip_classes.py``
    The ``skipclasscounts`` directive: the test report's skipped results by
    zdocs ``skip_class`` and board (one ``:need_count:`` per cell, the boards
    from the run's ``twister.json``). Used by ``test-report`` (``skips.rst``).

``tla_domain.py`` (with ``tla_lexer.py``, ``tla_unicode.py``, ``tla_extract.py``, ``tla_static/``)
    The ``tla`` domain: it shows the TLA+ specs (``spec/tla/*.tla``) in a
    document. The ASCII ``.tla`` files stay the source for TLC and Apalache.
    Used by ``architecture`` (``formal-model.rst``). The tests are in
    ``_tests/``.

    - ``tla_lexer.py``: a Pygments lexer for TLA+ (ASCII and Unicode), names
      ``tla`` and ``tlaplus``. ``tla-unicode`` shows ASCII as Unicode.
    - ``tla_unicode.py``: the ASCII-to-Unicode rendering (the tlauc table),
      token-aware. It does not change comments or strings.
    - ``tla_extract.py``: it splits a module into its units (definitions,
      declarations, comments) and reads the doc comment of each unit.
    - ``tla_domain.py``: the directives ``tla:module``, ``tla:definition``,
      ``tla:module-body`` and ``tla:property``, the roles ``:tla:mod:`` and
      ``:tla:def:``.


The TLA+ domain
---------------

Directives:

.. code-block:: rst

    .. tla:module:: KSem
       :body:              (all definitions after the header)
       :property-needs:    (with :body:, see below)

    .. tla:definition:: Give          (the module of the tla:module above)
    .. tla:definition:: KSem!Give
       :ascii:

    .. tla:module-body:: KSem
       :exclude: Init, Spec

    .. tla:property:: NoWaitWhileAvailable
       :expresses: ZEP-SRS-5-3, ZEP-SRS-5-4
       :kind: invariant
       :expected: hold

``:tla:def:`KSem!Give``` links to a definition, ``:tla:mod:`KSem``` to a
module. A module argument is a name or a path. The extension finds a name as
``<name>.tla`` in the directories of ``tla_spec_paths`` (relative to
conf.py). ``tla:module-body`` does not show a definition that the page
showed before it.

**Extent of a definition.** Only the text between the module header and
the footer is read. A unit starts at a line with code at column 0. It ends
before the next line at column 0: the next unit, a comment at column 0, a
``----`` line, a nested module or the footer. Lines with indentation belong
to the unit above them. The head is the text before the first ``==``
outside brackets: ``Name``, ``Name(p)``, ``Name[x \in S]``, infix ``a OP b``,
prefix ``OP a``, postfix ``a OP``, with ``LOCAL`` or ``INSTANCE``. A
``RECURSIVE`` line belongs to the next definition of its name. Thus a
comment at column 0 inside a definition body cuts the definition. Indent
the comments in a body.

**Doc comment.** The comment lines at column 0 directly above a unit (no
blank line between) are its doc comment: ``\*`` lines or a ``(* *)``
block (also a box). The extension removes the comment markers, dedents the
text and parses it as reStructuredText (``tla_prose = "text"`` shows plain
paragraphs). A comment with a blank line below it is a section comment. One
line gives a rubric. In reStructuredText, ``\`` is an escape character.
Thus write TLA+ operators in the prose as literals, for example ``/\``. A line
that starts with ``@`` is a tag, not prose:

=========================  =============================================  =====================
Tag                        Meaning                                        Need field
=========================  =============================================  =====================
``@expresses <UID>``       the requirement that the property expresses    link ``expresses``
                           (one UID for each line, repeatable)
``@kind <kind>``           ``invariant``, ``action``, ``liveness``,        ``kind``
                           ``probe`` or ``definition`` (default)
``@c-function <name>``     the C function that an action models           ``c_function``
                           (repeatable)                                   (joined, ``;``)
``@expected violation``    TLC must report a counterexample               ``expected``
                                                                          (``hold`` / ``violation``)
=========================  =============================================  =====================

The extension also sets ``tla_module``, ``source_file`` (relative to
``tla_source_root``) and ``source_line`` (the line of the head). An option
of ``tla:property`` replaces the tag value. Without a ``@kind`` and without
``:kind:``, the extension uses the formula: ``~>``, ``<>``, ``WF_`` or
``SF_`` give ``liveness``, ``[][`` gives ``action``, else ``invariant``. An
unknown tag or value gives a warning.

**Property needs.** ``tla:property`` makes one need of the type ``prop``
with the id ``PROP-<Module>-<Name>`` (``tla_property_id``). Its title is
the name, its content is the doc comment and the formula. With
``:property-needs:``, the body makes a need of each definition that has an
``@expresses`` tag or the kind ``invariant``, ``liveness`` or ``probe``.
The kind ``action`` alone does not make a need: an action and an action
property both use it.

**Unicode alignment.** Each Unicode symbol takes one column. The
indentation of each line is calculated again: a line with the same
indentation as the nearest line above it gets the new indentation of that
line, so the bullets of a list stay in one column. A line with more
indentation starts below the same character of that line as in ASCII (below
``IF``, below ``LET``). If the line starts to the right of the end of that
line, it keeps its distance to the indentation. Trailing comments that were
in one column stay in one column. ``tla_unicode_align = "pad"`` keeps each
ASCII column instead (spaces after each symbol). ``tla_unicode = False``
shows ASCII. The browser font must have the symbols (see
``tla_static/tla_domain.css``).

**Vocabulary.** ``doc/needs_config.toml`` declares the need type ``prop``,
the link ``expresses`` and the fields ``kind``, ``expected``,
``tla_module`` and ``c_function``. A model property also uses the fields
``source_file`` and ``source_line`` of the design elements. The test
project (``_tests/roots/test-tla``) declares the same vocabulary in its
``conf.py``.

**Wiring.** ``doc/CMakeLists.txt`` gives the Sphinx builds the directory of
the spec library as ``SAFETY_TLA_SPEC_DIR``. The ``conf.py`` of the
architecture sets ``tla_spec_paths`` (``spec/tla/lib``) and
``tla_source_root`` (the safety repository) from it.

**Tests.** Run them with the Python environment of the workspace::

    ../.venv/bin/python -m pytest doc/_extensions/_tests --basetemp=<scratch dir>

The Sphinx test project must build with ``-W``::

    ../.venv/bin/sphinx-build -W -b html doc/_extensions/_tests/roots/test-tla <out dir>

Adding this directory to ``sys.path``
-------------------------------------

``zdocs_conf`` puts the engine's ``_extensions`` at ``sys.path[0]``. A
``conf.py`` shim that needs a module from here must **append** this directory,
never prepend it — prepending would let a same-named module here shadow the
engine's copy:

.. code-block:: python

    # doc/ is where the registry lives, however deep the document sits.
    sys.path.append(str(Path(os.environ["ZDOCS_REGISTRY"]).parent / "_extensions"))
