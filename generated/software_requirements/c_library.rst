C library
$$$$$$$$$

SPDX-License-Identifier: Apache-2.0

.. _ZEP-SRS-18-1:

Formatted output
================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-18-1
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - C Library

The Zephyr RTOS shall support formatted output.

**USER_STORY:**

As a Zephyr RTOS user, I want to be able to printf with various output formats.

**Parents:**

- ``[ZEP-SYRS-3]`` :ref:`ZEP-SYRS-3`

.. _ZEP-SRS-18-2:

Floating Point Math Support
===========================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-18-2
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - C Library

The Zephyr RTOS shall support floating point math libraries for processors where floating point is available.

**USER_STORY:**

As a Zephyr RTOS user, I want to be able to calculate with floating point numbers.

**Parents:**

- ``[ZEP-SYRS-3]`` :ref:`ZEP-SYRS-3`

.. _ZEP-SRS-18-3:

Boolean Primitives Support
==========================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-18-3
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - C Library

The Zephyr RTOS shall support boolean primitives.

**USER_STORY:**

As a Zephyr RTOS user, I want to be able to work with boolean values and logic.

**Parents:**

- ``[ZEP-SYRS-3]`` :ref:`ZEP-SYRS-3`

.. _ZEP-SRS-18-4:

Standard Unix time interface
============================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-18-4
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - C Library

The Zephyr RTOS shall support the standard UNIX time interface.

**USER_STORY:**

As a Zephyr User, I want to be able to use system time.

**Parents:**

- ``[ZEP-SYRS-3]`` :ref:`ZEP-SYRS-3`

.. _ZEP-SRS-18-5:

Strings support
===============

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-18-5
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - C Library

The Zephyr RTOS shall support an interface to manage strings.

**USER_STORY:**

As a Zephyr RTOS user, I want to be able to manipulate text strings.

**Parents:**

- ``[ZEP-SYRS-3]`` :ref:`ZEP-SYRS-3`

.. _ZEP-SRS-18-6:

Moving/copying regions of memory
================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-18-6
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - C Library

The Zephyr RTOS shall support an interface to move contents between regions of memory.

**USER_STORY:**

As a Zephyr RTOS user, I want to copy the memory contents to different addresses.

**Parents:**

- ``[ZEP-SYRS-3]`` :ref:`ZEP-SYRS-3`

.. _ZEP-SRS-18-7:

I/O based interface
===================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-18-7
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - C Library

The Zephyr RTOS shall support a file i/O based interface for driver communication.

**USER_STORY:**

As a Zephyr RTOS user, I want to be able to use File I/O functions.

**Parents:**

- ``[ZEP-SYRS-3]`` :ref:`ZEP-SYRS-3`

.. _ZEP-SRS-18-8:

C99 integer types
=================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-18-8
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - C Library

The Zephyr RTOS shall support standard C99 integer types.

**USER_STORY:**

As a Zephyr RTOS user, I want to be able to calculate with C99 Integers.

**Parents:**

- ``[ZEP-SYRS-3]`` :ref:`ZEP-SYRS-3`

.. _ZEP-SRS-18-9:

Standard System Error Numbers (IEEE Std 1003.1-2017)
====================================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-18-9
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - C Library

The Zephyr RTOS shall support standard system error numbers as defined by IEEE Std 1003.1-2017.

**USER_STORY:**

As a Zephyr RTOS user, I want to be able to use IEE Std 1003.1-2017 Error Numbers for Interoperability.

**Parents:**

- ``[ZEP-SYRS-3]`` :ref:`ZEP-SYRS-3`

.. _ZEP-SRS-18-10:

Document set of Zephyr OS required C library functions in Safety Manual
=======================================================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-18-10
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - C Library

The set of C Library functions required by Zephyr needs to be documented in the Zephyr Safety Manual.

**USER_STORY:**

As a Zephyr user, I want to know which C library functions are being called by the Zephyr OS safety scope code.

**Parents:**

- ``[ZEP-SYRS-3]`` :ref:`ZEP-SYRS-3`

.. _ZEP-SRS-18-11:

Support external C libraries documentation in Zephyr Safety Manual
==================================================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-18-11
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - C Library

The Zephyr Safety Manual needs to specify how to configure the support of external C Libraries.

**USER_STORY:**

As a Zephyr User, I need to understand how to configure the external C libraries to align with the validation that has been performed.

**Parents:**

- ``[ZEP-SYRS-3]`` :ref:`ZEP-SYRS-3`
