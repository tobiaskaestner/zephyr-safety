Documentation guidelines
========================

This page gives the rules of this guide. The rules apply to each person
and each tool that writes or reviews a page.

Format
------

- The guide is a Sphinx document in reStructuredText.
- ``sphinx-build -W`` gives no warnings. Thus a broken cross-reference
  or an unknown ``:term:`` stops the build.
- Each page is in a toctree. The guide has no page that a reader cannot
  find from the start page.

Structure
---------

Each page is in one of the four parts of
`Diátaxis <https://diataxis.fr/>`_. The writer chooses the part before
writing the page. A page is in one part only.

Tutorial (``tutorials/``)
   A lesson. The reader does the steps and gets a working result. The
   tutorials tell one story. Each tutorial starts where the tutorial
   before it stops.

How-to guide (``howto/``)
   The steps of one task, for a reader who knows the suite.

Reference (``reference/``)
   The facts to look up: the commands, the files, the options, the
   formats and the terms. A reference page has no story.

Explanation (``explanation/``)
   How the method and the tools work, and why.

Facts
-----

- A page states facts in the present tense.
- An explanation page gives the current facts. It does not tell the
  history of a decision.
- A function that does not work yet is a plan, and the page says so. A
  page links only to pages and functions that exist.
- The guide gives no measurement results, because the results change
  with each tree and each experiment. The results of a run are in its
  result folder (see :ref:`benchguide-result-folder`).

Tutorials
---------

- A tutorial starts with ``.. admonition:: Prerequisites``. The
  admonition lists the hardware, the software and the tutorials that
  must come first.
- If a tutorial does not work yet, its first content is a
  ``.. warning::`` with the text "This tutorial does not work yet."
- The console output in a tutorial is real output. It is a copy of the
  output of a run, without changes.

Terms
-----

- The glossary (:doc:`../reference/glossary`) owns the terms. Each term
  has one definition, in the glossary.
- The other pages use ``:term:`` at the first use of a term on the page.

Language
--------

- All text follows Simple English, the pragmatic mode of ASD-STE100.
  The sentences are short. Each word has one meaning. The text uses the
  active voice. A procedure uses the imperative.
- Code, commands, identifiers and quoted output do not change.
