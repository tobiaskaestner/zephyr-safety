Queue Test Report
#################

.. note::

   Prototype of the output that the ``.. testreport::`` directive will generate from
   ``twister.json``.  All tests are currently **blocked** due to a build failure
   (undeclared ``k_thread_priority_set_adjoin``).  Test case links resolve to
   the corresponding entries in the :doc:`Test Specification <testspec:kernel/queue/test-spec>`.

**Platform:** ``qemu_cortex_m3/ti_lm3s6965``

**Toolchain:** ``zephyr/gnu``

**Zephyr version:** ``v4.4.0-2154-g5c7f7bb384ff``

**Run date:** 2026-05-30

Status key: **pass** | **fail** | **error** | *blocked* | *skipped*

Queue API Suite (``queue_api``)
================================

.. list-table::
   :header-rows: 1
   :widths: 18 40 21 21

   * - Test ID
     - Test Case
     - ``kernel.queue``
     - ``kernel.queue.minimallibc``
   * - ``TSPEC-QUEUE-API-001``
     - :external+testspec:ref:`access_kernel_obj_with_priv_data <testspec-queue_api-access_kernel_obj_with_priv_data>`
     - *blocked*
     - *blocked*
   * - ``TSPEC-QUEUE-API-002``
     - :external+testspec:ref:`auto_free <testspec-queue_api-auto_free>`
     - *blocked*
     - *blocked*
   * - ``TSPEC-QUEUE-API-003``
     - :external+testspec:ref:`multiple_queues <testspec-queue_api-multiple_queues>`
     - *blocked*
     - *blocked*
   * - ``TSPEC-QUEUE-API-004``
     - :external+testspec:ref:`queue_alloc <testspec-queue_api-queue_alloc>`
     - *blocked*
     - *blocked*
   * - ``TSPEC-QUEUE-API-005``
     - :external+testspec:ref:`queue_alloc_append_null <testspec-queue_api-queue_alloc_append_null>`
     - *blocked*
     - *blocked*
   * - ``TSPEC-QUEUE-API-006``
     - :external+testspec:ref:`queue_alloc_append_user <testspec-queue_api-queue_alloc_append_user>`
     - *blocked*
     - *blocked*
   * - ``TSPEC-QUEUE-API-007``
     - :external+testspec:ref:`queue_alloc_prepend_null <testspec-queue_api-queue_alloc_prepend_null>`
     - *blocked*
     - *blocked*
   * - ``TSPEC-QUEUE-API-008``
     - :external+testspec:ref:`queue_alloc_prepend_user <testspec-queue_api-queue_alloc_prepend_user>`
     - *blocked*
     - *blocked*
   * - ``TSPEC-QUEUE-API-009``
     - :external+testspec:ref:`queue_append_list_error <testspec-queue_api-queue_append_list_error>`
     - *blocked*
     - *blocked*
   * - ``TSPEC-QUEUE-API-010``
     - :external+testspec:ref:`queue_cancel_wait_error <testspec-queue_api-queue_cancel_wait_error>`
     - *blocked*
     - *blocked*
   * - ``TSPEC-QUEUE-API-011``
     - :external+testspec:ref:`queue_get_null <testspec-queue_api-queue_get_null>`
     - *blocked*
     - *blocked*
   * - ``TSPEC-QUEUE-API-012``
     - :external+testspec:ref:`queue_init_null <testspec-queue_api-queue_init_null>`
     - *blocked*
     - *blocked*
   * - ``TSPEC-QUEUE-API-013``
     - :external+testspec:ref:`queue_is_empty_null <testspec-queue_api-queue_is_empty_null>`
     - *blocked*
     - *blocked*
   * - ``TSPEC-QUEUE-API-014``
     - :external+testspec:ref:`queue_isr2thread <testspec-queue_api-queue_isr2thread>`
     - *blocked*
     - *blocked*
   * - ``TSPEC-QUEUE-API-015``
     - :external+testspec:ref:`queue_merge_list_error <testspec-queue_api-queue_merge_list_error>`
     - *blocked*
     - *blocked*
   * - ``TSPEC-QUEUE-API-016``
     - :external+testspec:ref:`queue_peek_head_null <testspec-queue_api-queue_peek_head_null>`
     - *blocked*
     - *blocked*
   * - ``TSPEC-QUEUE-API-017``
     - :external+testspec:ref:`queue_peek_tail_null <testspec-queue_api-queue_peek_tail_null>`
     - *blocked*
     - *blocked*
   * - ``TSPEC-QUEUE-API-018``
     - :external+testspec:ref:`queue_thread2isr <testspec-queue_api-queue_thread2isr>`
     - *blocked*
     - *blocked*
   * - ``TSPEC-QUEUE-API-019``
     - :external+testspec:ref:`queue_unique_append <testspec-queue_api-queue_unique_append>`
     - *blocked*
     - *blocked*

Queue API 1CPU Suite (``queue_api_1cpu``)
==========================================

.. list-table::
   :header-rows: 1
   :widths: 18 40 21 21

   * - Test ID
     - Test Case
     - ``kernel.queue``
     - ``kernel.queue.minimallibc``
   * - ``TSPEC-QUEUE-1CPU-001``
     - :external+testspec:ref:`queue_get_2threads <testspec-queue_api_1cpu-queue_get_2threads>`
     - *blocked*
     - *blocked*
   * - ``TSPEC-QUEUE-1CPU-002``
     - :external+testspec:ref:`queue_get_fail <testspec-queue_api_1cpu-queue_get_fail>`
     - *blocked*
     - *blocked*
   * - ``TSPEC-QUEUE-1CPU-003``
     - :external+testspec:ref:`queue_loop <testspec-queue_api_1cpu-queue_loop>`
     - *blocked*
     - *blocked*
   * - ``TSPEC-QUEUE-1CPU-004``
     - :external+testspec:ref:`queue_multithread_competition <testspec-queue_api_1cpu-queue_multithread_competition>`
     - *blocked*
     - *blocked*
   * - ``TSPEC-QUEUE-1CPU-005``
     - :external+testspec:ref:`queue_poll_race <testspec-queue_api_1cpu-queue_poll_race>`
     - *blocked*
     - *blocked*
   * - ``TSPEC-QUEUE-1CPU-006``
     - :external+testspec:ref:`queue_supv_to_user <testspec-queue_api_1cpu-queue_supv_to_user>`
     - *blocked*
     - *blocked*
   * - ``TSPEC-QUEUE-1CPU-007``
     - :external+testspec:ref:`queue_thread2thread <testspec-queue_api_1cpu-queue_thread2thread>`
     - *blocked*
     - *blocked*
