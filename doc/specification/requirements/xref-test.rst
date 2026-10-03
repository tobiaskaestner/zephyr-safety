Cross-Reference Test
====================

Smoke test for the cross-document reference channels. Each bullet exercises one
channel into one peer document and must render as a link. The page named by
``xref_smoketest:`` in ``doc/documents.yaml`` is checked by ``doc-check``; the
others are for inspection. A document never links to itself here: Sphinx gives
a document no inventory or needs import of its own.

Intersphinx — other Sphinx documents
------------------------------------

* Architecture: :external+arch:doc:`index`
* Test Specification: :external+testspec:doc:`index`
* Test Report: :external+testreport:doc:`index`
* API Documentation: :external+api:doc:`index`

.. only:: committee

   * Safety Committee: :external+committee:doc:`index`

Doxylink — Doxygen documents
----------------------------

* Safety API (Doxygen): :dox_api:`kernel_apis`
* Detailed Design (Doxygen): :dox_design:`kernel_apis`
* Test Specification (Doxygen): :dox_testspec:`tests_kernel_queue`

External needs — sphinx-needs imports
-------------------------------------

* Test Specification: :need:`TSPEC-FIFO-1CPU-001`
* Test Report: :need:`TR-qemu-cortex-m0-nrf51822-kernel-fifo-fifo-api-TSPEC-FIFO-1CPU-001`
* API Documentation: :need:`IMPL-k_queue_get`
