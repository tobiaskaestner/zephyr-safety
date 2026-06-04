Sphinx Extensions
=================

This directory contains the custom Sphinx extensions used by the safety
documentation build, along with their supporting parsing modules and test suite.

.. contents:: Contents
   :local:
   :depth: 1


Modules
-------

``doxygen_parser.py``
    Extracts structured data from Doxygen XML output. No Sphinx dependency —
    usable standalone or in an interactive Python session.

``twister_reader.py``
    Reads Twister test output (JUnit XML, ``twister.json``, ``handler.log``).
    No Sphinx dependency.

``rst_builders.py``
    Turns the dicts produced by the above into RST string fragments.
    No Sphinx dependency.

``test_module.py``
    Sphinx extension entry point. Provides the ``testmodule``, ``testreport``,
    and ``twisterinfo`` directives. Imports from the three modules above.

``strictdoc_runner.py``
    Runs ``strictdoc export`` on Sphinx build-init to keep the requirements
    needs.json up to date.


Interactive use
---------------

The parsing modules work in a plain Python session without a Sphinx build.
Add ``_extensions/`` to the path, then call the functions directly against
``xml.etree.ElementTree``:

.. code-block:: python

    import sys
    sys.path.insert(0, "/wrk/z/ws-safety/safety/doc/_extensions")

    from pathlib import Path
    import xml.etree.ElementTree as ET
    from doxygen_parser import load_group_index, parse_memberdef

    xml_dir = Path("/wrk/z/ws-safety/bdoc/deploy/doxygen-zephyr-safety-testspec/xml")

    # Map group names to refids
    index = load_group_index(xml_dir)

    # Load a group and inspect its members
    root = ET.parse(xml_dir / f"{index['queue_api']}.xml").getroot()
    cdef = root.find("compounddef")

    for md in cdef.findall("sectiondef/memberdef[@kind='function']"):
        info = parse_memberdef(md, cdef.get("id"), "", "")
        print(info["name"], info["test_id"], info["status"])

Or launch Python directly from the extensions directory to avoid the
``sys.path`` manipulation:

.. code-block:: bash

    cd /wrk/z/ws-safety/safety/doc/_extensions
    python


Test suite
----------

Tests live in ``_tests/`` (leading underscore keeps Sphinx from copying the
directory into the HTML output). Run from the workspace root:

.. code-block:: bash

    python -m pytest safety/doc/_extensions/_tests/ -v
