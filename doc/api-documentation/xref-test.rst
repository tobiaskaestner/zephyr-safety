Cross-Reference Test
====================

Smoke test for the cross-document reference channels. Each bullet exercises one
channel into one peer document and must render as a link. The page named by
``xref_smoketest:`` in ``doc/documents.yaml`` is checked by ``doc-check``; the
others are for inspection. A document never links to itself here: Sphinx gives
a document no inventory or needs import of its own.

Intersphinx — other Sphinx documents
------------------------------------

* Requirements: :external+req:doc:`index`
* Architecture: :external+arch:doc:`index`
* Test Specification: :external+testspec:doc:`index`
* Test Report: :external+testreport:doc:`index`
* Safety Committee: :external+committee:doc:`index`
* Test Specification (hand-crafted): :external+sb_testspec:doc:`index`
* Test Report (hand-crafted): :external+sb_testreport:doc:`index`
* Sandbox: mlx.traceability: :external+sb_mlx:doc:`index`
* Sandbox: sphinx-needs: :external+sb_needs:doc:`index`

Doxylink — Doxygen documents
----------------------------

* Safety API (Doxygen): :dox_api:`kernel_apis`
* Detailed Design (Doxygen): :dox_design:`kernel_apis`
* Test Specification (Doxygen): :dox_testspec:`tests_kernel_queue`

External needs — sphinx-needs imports
-------------------------------------

* Requirements: :need:`ZEP-SRS-20-6`
* Test Specification: :need:`TSPEC-FIFO-1CPU-001`
* Test Report: :need:`TR-qemu-cortex-m0-nrf51822-kernel-fifo-fifo-api-TSPEC-FIFO-1CPU-001`
