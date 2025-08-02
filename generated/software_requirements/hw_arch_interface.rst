Hardware Architecture Interface
$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$

SPDX-License-Identifier: Apache-2.0

.. _ZEP-SRS-19-1:

Atomic Operations
=================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-19-1
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Hardware Architecture Interface

The Zephyr RTOS shall provide an interface functionality to access memory while ensuring mutual exclusion. Note: Implementation by atomic variables and accessing them by APIs.

**USER_STORY:**

As a Zephyr RTOS user I want to read from or write into a memory areas without being disturbed by other threads or ISRs.

**Parents:**

- ``[ZEP-SYRS-1]`` :ref:`ZEP-SYRS-1`

.. _ZEP-SRS-19-2:

Thread Context Switching
========================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-19-2
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Hardware Architecture Interface

The Zephyr RTOS shall provide a mechanism for context switching between threads.

**USER_STORY:**

As a Zephyr RTOS user I want to execute code concurrently in one or more threads and when interrupted at a code location in a thread, to continue at the very same location.

**Parents:**

- ``[ZEP-SYRS-1]`` :ref:`ZEP-SYRS-1`

.. _ZEP-SRS-19-3:

Software Exceptions
===================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-19-3
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Hardware Architecture Interface

The Zephyr RTOS shall provide an interface to implement software exceptions.

**USER_STORY:**

As a Zephyr RTOS user I want to catch any software exception and handle it according to my application needs.

**Parents:**

- ``[ZEP-SYRS-1]`` :ref:`ZEP-SYRS-1`

.. _ZEP-SRS-19-4:

Processor Mode Support
======================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-19-4
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Hardware Architecture Interface

The Zephyr RTOS shall provide an interface for managing processor modes.

**USER_STORY:**

If MCU power state was meant here:
As a Zephyr RTOS user I want to control the MCU's power saving mode such e.g. operation, sleep, deep sleep or similar as supported by the selected MCU.

**Parents:**

- ``[ZEP-SYRS-1]`` :ref:`ZEP-SYRS-1`
