Memory protection
$$$$$$$$$$$$$$$$$

SPDX-License-Identifier: Apache-2.0

.. _ZEP-SRS-8-1:

Memory Protection
=================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-8-1
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Memory Protection

The Zephyr RTOS shall support memory protection features to isolate a thread's memory region.

**USER_STORY:**

As a Zephyr RTOS user I want memory to be allocated and protected to my application threads preventing mistakenly access to foreign memory as far as the hardware allows.

.. _ZEP-SRS-8-2:

Granting access to kernel objects
=================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-8-2
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Memory Protection

The Zephyr RTOS shall provide a mechanism to grant user threads access to kernel objects.

**USER_STORY:**

As a Zephyr RTOS user I want, from the user space, under certain conditions, access to kernel objects.

.. _ZEP-SRS-8-3:

Separation between user and kernel threads for memory access
============================================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-8-3
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Memory Protection

The Zephyr RTOS shall be able to differentiate between user threads and kernel threads for memory access.

**USER_STORY:**

As a Zephyr RTOS user I want, from the kernel space, unconditioned access to kernel objects.

.. _ZEP-SRS-8-4:

Safely handle unimplemented calls or invalid system calls
=========================================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-8-4
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Memory Protection

The Zephyr RTOS shall have a defined behaviour when an invocation of an unimplemented system call is made.

**USER_STORY:**

As a Zephyr RTOS user I want Zephyr OS to indicate any unimplemented system call by an appropriate error message.

.. _ZEP-SRS-8-5:

Response to invalid system call IDs
===================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-8-5
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Memory Protection

The Zephyr RTOS shall have a defined behaviour when an invalid system call ID is used.

**USER_STORY:**

As a Zephyr RTOS user I want Zephyr OS to indicate invalid system call by an appropriate error message.

.. _ZEP-SRS-8-6:

Prevent user threads creating higher priority threads
=====================================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-8-6
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Memory Protection

The Zephyr RTOS shall prevent user threads from creating new threads that are higher priority than the caller.

.. _ZEP-SRS-8-7:

Revoking threads permissions on a kernel object
===============================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-8-7
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Memory Protection

The Zephyr RTOS shall support revoking permission to a kernel object. User mode threads may only revoke their own access to an object.

**USER_STORY:**

As a Zephyr RTOS user I want to be protected against other user threads changing access to kernel objects of my thread.

.. _ZEP-SRS-8-8:

Prevent user threads creating supervisor threads
================================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-8-8
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Memory Protection

The Zephyr RTOS shall prevent user threads from creating kernel threads.

**USER_STORY:**

As a Zephyr RTOS user I want to be protected against user threads creating higher privileged kernel/supervisor threads.

.. _ZEP-SRS-8-9:

Reduced Privilege Level Threads
===============================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-8-9
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Memory Protection

The Zephyr RTOS shall allow the creation of threads that run in reduced privilege level.

**USER_STORY:**

As a Zephyr RTOS user I want to be able to create lower privileged threads than my own.

.. _ZEP-SRS-8-10:

User Mode Threads Performing Privileged Operations
==================================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-8-10
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Memory Protection

The Zephyr RTOS shall provide system calls to allow user mode threads to perform privileged operations.

**USER_STORY:**

As a Zephyr RTOS user I want to be able to perform privileged operations in the kernel mode through a well defined interface.

.. _ZEP-SRS-8-11:

User mode handling of detected stack overflow
=============================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-8-11
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Memory Protection

The Zephyr RTOS shall support a defined mechanism for user mode handling a of detected stack overflow.

**USER_STORY:**

As a Zephyr RTOS user I want, when a stack overflow is detected, to be able to implement a graceful, application defined handling of the exception.

.. _ZEP-SRS-8-12:

Stack Overflow Detection
========================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-8-12
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Memory Protection

The Zephyr RTOS shall support detection of stack overflows.

**USER_STORY:**

As a Zephyr RTOS user I want to get an indication when a stack overflow occurs at least during debugging / the development phase, and for safety applications also in a release version of my application.

.. _ZEP-SRS-8-13:

Boot Time Memory Access Policy
==============================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-8-13
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Memory Protection

The Zephyr RTOS shall support configurable access to memory during boot time.

.. _ZEP-SRS-8-14:

System Call Handler Functions
=============================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-8-14
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Memory Protection

The Zephyr RTOS shall provide helper functions for system call handler functions to validate the inputs passed in from user mode before invoking the implementation function to protect the kernel.

**USER_STORY:**

As a Zephyr RTOS user I want Zepyhr OS to validate system call parameters passed from the user mode to the kernel mode to avoid crashes and undefined behaviour.

.. _ZEP-SRS-8-15:

System Call C strings in user mode
==================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-8-15
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Memory Protection

The Zephyr RTOS shall support system calls to be able to safely accept C strings passed in from user mode.

**USER_STORY:**

As a Zephyr RTOS user I want Zepyhr OS to validate system call string type parameters passed from the user mode to the kernel mode to avoid crashes and undefined behaviour.

e.g.

- verify the string length is smaller or equal to the syscalls defined max.
- verify that the length type does not overflow when allocating one more byte ???

.. _ZEP-SRS-8-16:

Tracking kernel objects in used by user mode threads
====================================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-8-16
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Memory Protection

The Zephyr RTOS shall track kernel objects that are used by user mode threads.

Note: this means Zephyr shall track the resources used by the user mode thread (associate this with a user story).

.. _ZEP-SRS-8-17:

Granting threads access to specific memory
==========================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-8-17
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Memory Protection

The Zephyr RTOS shall have an interface to request access to specific memory after initial allocation.

**USER_STORY:**

As a Zephyr RTOS user I want to be able to request read-only or read-write access to a dedicated memory area/pool during runtime.

.. _ZEP-SRS-8-18:

Assigning memory pools to act as a thread resource pool
=======================================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-8-18
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Memory Protection

The Zephyr RTOS shall support assigning a memory pool to act as that thread's resource pool.

**USER_STORY:**

As a Zephyr RTOS user I want to be able, during runtime from the kernel, to request a memory area/pool which is exclusively available to the requesting thread protected against access from other threads.
