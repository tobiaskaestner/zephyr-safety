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


Adding this directory to ``sys.path``
-------------------------------------

``zdocs_conf`` puts the engine's ``_extensions`` at ``sys.path[0]``. A
``conf.py`` shim that needs a module from here must **append** this directory,
never prepend it — prepending would let a same-named module here shadow the
engine's copy:

.. code-block:: python

    # doc/ is where the registry lives, however deep the document sits.
    sys.path.append(str(Path(os.environ["ZDOCS_REGISTRY"]).parent / "_extensions"))
