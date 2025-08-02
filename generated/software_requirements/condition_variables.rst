Condition Variables
$$$$$$$$$$$$$$$$$$$

.. _ZEP-SRS-21-1:

Dynamic initialization of condition variables
=============================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-21-1
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Condition Variables

The Zephyr RTOS shall provide a mechanism to define and initialize a condition variable dynamically (at runtime).

**Parents:**

- ``[ZEP-SYRS-20]`` :ref:`ZEP-SYRS-20`

.. _ZEP-SRS-21-2:

Static initialization of condition variables
============================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-21-2
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Condition Variables

The Zephyr RTOS shall provide a mechanism to define and initialize a condition variable statically (at compile time).

**Parents:**

- ``[ZEP-SYRS-20]`` :ref:`ZEP-SYRS-20`

.. _ZEP-SRS-21-3:

Signal one waiting thread
=========================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-21-3
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Condition Variables

The Zephyr RTOS shall provide a mechanism to signal the highest priorite waiting thread when a condition is met.

**Parents:**

- ``[ZEP-SYRS-20]`` :ref:`ZEP-SYRS-20`

.. _ZEP-SRS-21-4:

Signal multiple waiting threads
===============================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-21-4
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Condition Variables

The Zephyr RTOS shall provide a mechanism to signal all waiting threads when a condition is met.

**Parents:**

- ``[ZEP-SYRS-20]`` :ref:`ZEP-SYRS-20`

.. _ZEP-SRS-21-5:

Wait on a condition variable
============================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-21-5
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Condition Variables

The Zephyr RTOS shall provide a mechanism for a thread to wait on a condition variable.

**Parents:**

- ``[ZEP-SYRS-20]`` :ref:`ZEP-SYRS-20`

.. _ZEP-SRS-21-6:

Wait timeout on a condition variable
====================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-21-6
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Condition Variables

When waiting on a condition variable, the thread shall specify a timeout value.

**Parents:**

- ``[ZEP-SYRS-20]`` :ref:`ZEP-SYRS-20`

.. _ZEP-SRS-21-7:

Wait timeout occurence
======================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-21-7
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Condition Variables

When a timeout occurs while waiting on a condition variable, the thread shall be unblocked and a timeout error shall be returned.

**Parents:**

- ``[ZEP-SYRS-20]`` :ref:`ZEP-SYRS-20`

.. _ZEP-SRS-21-8:

Release mutex on wait
=====================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-21-8
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Condition Variables

If a thread is waiting on a condition variable, the thread shall release the current owned mutex independently.

**Parents:**

- ``[ZEP-SYRS-20]`` :ref:`ZEP-SYRS-20`

.. _ZEP-SRS-21-9:

Unblock a waiting thread
========================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-21-9
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Condition Variables

henever some thread signals a condition variable the Zephyr RTOS shall unblock the highest priority thread currently waiting for this condition variable.

**Parents:**

- ``[ZEP-SYRS-20]`` :ref:`ZEP-SYRS-20`
