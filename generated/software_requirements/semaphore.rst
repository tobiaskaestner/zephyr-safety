Semaphores
$$$$$$$$$$

SPDX-License-Identifier: Apache-2.0

.. _ZEP-SRS-5-1:

Counting Semaphore Definition At Compile Time
=============================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-5-1
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Semaphore

The Zephyr RTOS shall provide a mechanism to define and initialize a semaphore at compile time.

**Parents:**

- ``[ZEP-SYRS-14]`` :ref:`ZEP-SYRS-14`

.. _ZEP-SRS-5-2:

Counting Semaphore Definition At Run Time
=========================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-5-2
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Semaphore

The Zephyr RTOS shall provide a mechanism to define and initialize a semaphore at runtime.

**Parents:**

- ``[ZEP-SYRS-14]`` :ref:`ZEP-SYRS-14`

.. _ZEP-SRS-5-3:

Maximum limit of a semaphore
============================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-5-3
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Semaphore

The Zephyr RTOS shall define the maximum limit of a semaphore when the semaphore is used for counting purposes and does not have an explicit limit.

.. _ZEP-SRS-5-4:

Initialialization with maximum count value
==========================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-5-4
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Semaphore

When initializing a counting semaphore, the maximum permitted count a semaphore
can have shall be set.

**Parents:**

- ``[ZEP-SYRS-14]`` :ref:`ZEP-SYRS-14`

.. _ZEP-SRS-5-5:

Initial semaphore value
=======================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-5-5
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Semaphore

When initializing a counting semaphore, the initial semaphore value shall be set.

**Parents:**

- ``[ZEP-SYRS-14]`` :ref:`ZEP-SYRS-14`

.. _ZEP-SRS-5-6:

Semaphore acquisition mechanism
===============================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-5-6
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Semaphore

The Zephyr RTOS shall provide a mechanism allowing threads to acquire a semaphore.

**Parents:**

- ``[ZEP-SYRS-14]`` :ref:`ZEP-SYRS-14`

.. _ZEP-SRS-5-7:

Semaphore acquisition with count greater than zero
==================================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-5-7
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Semaphore

While the semaphore's count is greater than zero, the requesting thread shall acquire
the semaphore and decrement its count.

**Parents:**

- ``[ZEP-SYRS-14]`` :ref:`ZEP-SYRS-14`

.. _ZEP-SRS-5-8:

Semaphore acquisition with zero count
=====================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-5-8
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Semaphore

While the semaphore's count is zero, the requesting thread shall be blocked until the semaphore is released by another thread.

**Parents:**

- ``[ZEP-SYRS-14]`` :ref:`ZEP-SYRS-14`

.. _ZEP-SRS-5-9:

Semaphore acquisition timeout
=============================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-5-9
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Semaphore

When attempting to acquire a semaphore, the Zephyr RTOS shall accept options that specify timeout periods, allowing threads to set a maximum wait time for semaphore acquisition.

**Parents:**

- ``[ZEP-SYRS-14]`` :ref:`ZEP-SYRS-14`

.. _ZEP-SRS-5-10:

Semaphore acquisition timeout error handling
============================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-5-10
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Semaphore

When attempting to acquire a semaphore, where the semaphore is not acquired within the
specified time, the Zephyr RTOS shall return an error indicating a timeout.

**Parents:**

- ``[ZEP-SYRS-14]`` :ref:`ZEP-SYRS-14`

.. _ZEP-SRS-5-11:

Semaphore acquisition no wait error handling
============================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-5-11
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Semaphore

When attempting to acquire a semaphore, where the current count is zero and no timeout time was provided, the Zephyr RTOS
shall return an error indicating the semaphore is busy.

**Parents:**

- ``[ZEP-SYRS-14]`` :ref:`ZEP-SYRS-14`

.. _ZEP-SRS-5-12:

Semaphore release
=================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-5-12
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Semaphore

The Zephyr RTOS shall provide a mechanism allowing threads to release a semaphore.

**Parents:**

- ``[ZEP-SYRS-14]`` :ref:`ZEP-SYRS-14`

.. _ZEP-SRS-5-13:

Semaphore release
=================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-5-13
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Semaphore

The Zephyr RTOS shall increment the semaphore's count upon release.

**Parents:**

- ``[ZEP-SYRS-14]`` :ref:`ZEP-SYRS-14`

.. _ZEP-SRS-5-14:

Semaphore release with priority inheritance
===========================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-5-14
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Semaphore

When there are threads waiting on the semaphore, the highest-priority waiting thread
shall be unblocked and acquire the semaphore.

**Parents:**

- ``[ZEP-SYRS-14]`` :ref:`ZEP-SYRS-14`

.. _ZEP-SRS-5-15:

Checking semaphore count
========================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-5-15
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Semaphore

The Zephyr RTOS shall provide a mechanism for threads to check the current count of a semaphore without acquiring it.

**Parents:**

- ``[ZEP-SYRS-14]`` :ref:`ZEP-SYRS-14`

.. _ZEP-SRS-5-16:

Semaphore reset
===============

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-5-16
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Semaphore

The Zephyr RTOS shall provide a mechanism that resets the semaphore count to zero.

**Parents:**

- ``[ZEP-SYRS-14]`` :ref:`ZEP-SYRS-14`

.. _ZEP-SRS-5-17:

Semaphore acquisitions abort after reset
========================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-5-17
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Semaphore

When a semaphore is reset, the Zephyr RTOS shall abort all existing acquisitions
of the semaphore returning a resource contention error code.

**Parents:**

- ``[ZEP-SYRS-14]`` :ref:`ZEP-SYRS-14`

.. _ZEP-SRS-5-18:

Semaphore Initialization Option Validation
==========================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-5-18
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Semaphore

When initializing a counting semaphore, where the maximum permitted count of a semaphore is invalid,
then the Zephyr RTOS shall return an error indicating invalid values.

**Parents:**

- ``[ZEP-SYRS-14]`` :ref:`ZEP-SYRS-14`
