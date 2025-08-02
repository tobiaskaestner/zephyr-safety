Exception and Error Handling
$$$$$$$$$$$$$$$$$$$$$$$$$$$$

SPDX-License-Identifier: Apache-2.0

.. _ZEP-SRS-16-1:

Fatal Exception Error Handler
=============================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-16-1
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Exception and Error Handling

The Zephyr RTOS shall provide default handlers for exceptions.

**USER_STORY:**

As a Zephyr RTOS user I want exceptions which I did not handle explicitly (by mistake or on purpose) to be caught by a default handler, defined either by Zephyr OS or by myself.

.. _ZEP-SRS-16-2:

Default handler for fatal errors
================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-16-2
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Exception and Error Handling

The Zephyr RTOS shall provide default handlers for fatal errors that do not have a dedicated handler.

.. _ZEP-SRS-16-3:

Assigning a specific handler
============================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-16-3
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Exception and Error Handling

The Zephyr RTOS shall provide an interface to assign a specific handler with an exception.

.. _ZEP-SRS-16-4:

Assigning a specific handler (2)
================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-16-4
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Exception and Error Handling

The Zephyr RTOS shall provide an interface to assign a specific handler for a fatal error.
