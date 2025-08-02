Threads
$$$$$$$

SPDX-License-Identifier: Apache-2.0

.. _ZEP-SRS-1-1:

Creating threads
================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-1-1
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Threads

The Zephyr RTOS shall provide an interface to create (start) a thread.

**Parents:**

- ``[ZEP-SYRS-15]`` :ref:`ZEP-SYRS-15`
- ``[ZEP-SYRS-16]`` :ref:`ZEP-SYRS-16`

.. _ZEP-SRS-1-2:

Setting thread priority
=======================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-1-2
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Threads

The Zephyr RTOS shall provide an interface to set a thread's priority.

**Parents:**

- ``[ZEP-SYRS-17]`` :ref:`ZEP-SYRS-17`

.. _ZEP-SRS-1-3:

Suspending a thread
===================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-1-3
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Threads

The Zephyr RTOS shall provide an interface to suspend a thread.

**Parents:**

- ``[ZEP-SYRS-15]`` :ref:`ZEP-SYRS-15`
- ``[ZEP-SYRS-16]`` :ref:`ZEP-SYRS-16`

.. _ZEP-SRS-1-4:

Resuming a suspended thread
===========================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-1-4
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Threads

The Zephyr RTOS shall provide an interface to resume a suspended thread.

**Parents:**

- ``[ZEP-SYRS-15]`` :ref:`ZEP-SYRS-15`
- ``[ZEP-SYRS-16]`` :ref:`ZEP-SYRS-16`

.. _ZEP-SRS-1-5:

Resuming a suspended thread after a timeout
===========================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-1-5
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Threads

The Zephyr RTOS shall provide an interface to resume a suspended thread after a timeout.

**Parents:**

- ``[ZEP-SYRS-15]`` :ref:`ZEP-SYRS-15`
- ``[ZEP-SYRS-16]`` :ref:`ZEP-SYRS-16`

.. _ZEP-SRS-1-6:

Deleting a thread
=================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-1-6
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Threads

The Zephyr RTOS shall provide an interface to delete (end) a thread.

**Parents:**

- ``[ZEP-SYRS-15]`` :ref:`ZEP-SYRS-15`
- ``[ZEP-SYRS-16]`` :ref:`ZEP-SYRS-16`

.. _ZEP-SRS-1-7:

Thread states
=============

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-1-7
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Threads

Threads shall have different states to fulfill the Life-cycle of a thread

**USER_STORY:**

As a Zephyr RTOS user, I want to know in what state a specific thread is.

**Parents:**

- ``[ZEP-SYRS-15]`` :ref:`ZEP-SYRS-15`
- ``[ZEP-SYRS-16]`` :ref:`ZEP-SYRS-16`

.. _ZEP-SRS-1-8:

Thread stack objects
====================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-1-8
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Threads

Every Thread shall have it's own stack.

**USER_STORY:**

As a Zephyr RTOS user I want to be able to configure the stack size of a thread. And every thread shall have it's own dedicated stack.

**Parents:**

- ``[ZEP-SYRS-15]`` :ref:`ZEP-SYRS-15`
- ``[ZEP-SYRS-16]`` :ref:`ZEP-SYRS-16`

.. _ZEP-SRS-1-9:

Thread privileges
=================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-1-9
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Threads

The Zephyr RTOS shall provide an interface to create threads with defined privilege.

**Parents:**

- ``[ZEP-SYRS-15]`` :ref:`ZEP-SYRS-15`
- ``[ZEP-SYRS-16]`` :ref:`ZEP-SYRS-16`

.. _ZEP-SRS-1-10:

Scheduling multiple threads
===========================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-1-10
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Threads

The Zephyr RTOS shall provide an interface to schedule multiple threads.

**Parents:**

- ``[ZEP-SYRS-16]`` :ref:`ZEP-SYRS-16`

.. _ZEP-SRS-1-11:

Thread Options
==============

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-1-11
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Threads

The Zephyr RTOS shall support a set of thread options.

**USER_STORY:**

As a Zephyr RTOS user, I want to be able to pass specific option to a thread.

**Parents:**

- ``[ZEP-SYRS-15]`` :ref:`ZEP-SYRS-15`
- ``[ZEP-SYRS-16]`` :ref:`ZEP-SYRS-16`

.. _ZEP-SRS-1-12:

Thread Custom Data
==================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-1-12
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Threads

Every thread shall have a custom data area.

**USER_STORY:**

As a Zephyr RTOS user, I want to be able to set a thread specific custom area for every thread I create and which can be used only by the thread itself or the can be used by the application

**Parents:**

- ``[ZEP-SYRS-15]`` :ref:`ZEP-SYRS-15`
- ``[ZEP-SYRS-16]`` :ref:`ZEP-SYRS-16`
