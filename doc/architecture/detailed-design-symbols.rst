Implementing Symbols
====================

Every kernel-internal symbol in the safety scope that implements a requirement,
from its Doxygen ``\satisfies``: the scheduler, thread, work queue, SMP and
user-mode internals below the Safety API. Each entry links to the requirements
it satisfies and to the symbol's Detailed Design (Doxygen) page; a
requirement's own page lists the symbols that satisfy it ("satisfied by") next
to the test cases that verify it. Generated from the Detailed Design's Doxygen
XML, one section per group or file.

The public API symbols that implement requirements are listed in the API
Documentation (Satisfied Requirements).

.. symbolneeds::
