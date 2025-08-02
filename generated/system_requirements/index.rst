Zephyr System Requirements
$$$$$$$$$$$$$$$$$$$$$$$$$$

SPDX-License-Identifier: Apache-2.0

.. _ZEP-SYRS-1:

Architecture Layer Interface
============================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SYRS-1
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Hardware Architecture Interface

The Zephyr RTOS shall provide a framework to communicate with a set of hardware architectural services.

**USER_STORY:**

As a Zephyr RTOS user I want to be able to easily switch my application to a different MCU architecture (x86, ARM Cortex-M/A, RISCV etc.).

**Children:**

- ``[ZEP-SRS-19-1]`` :ref:`ZEP-SRS-19-1`
- ``[ZEP-SRS-19-2]`` :ref:`ZEP-SRS-19-2`
- ``[ZEP-SRS-19-3]`` :ref:`ZEP-SRS-19-3`
- ``[ZEP-SRS-19-4]`` :ref:`ZEP-SRS-19-4`
- ``[ZEP-SYRS-2]`` :ref:`ZEP-SYRS-2`

.. _ZEP-SYRS-2:

Support multiprocessor management
=================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SYRS-2
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Hardware Architecture Interface

The Zephyr RTOS shall support symmetric multiprocessing on multiple cores.

**USER_STORY:**

As a Zephyr RTOS user I want to use Zephyr OS on multi core (SMP-)MCUs/MPUs.

**Parents:**

- ``[ZEP-SYRS-1]`` :ref:`ZEP-SYRS-1`

.. _ZEP-SYRS-3:

Support Subset of Standard C Library
====================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SYRS-3
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - C Library

The Zephyr RTOS shall support a subset of the standard C library.

**USER_STORY:**

As a Zephyr RTOS user I want to have a selection of standard C library implementations e.g. a full extend and a minimal with a smaller footprint or a particular fast executing implementation.

**Children:**

- ``[ZEP-SRS-18-1]`` :ref:`ZEP-SRS-18-1`
- ``[ZEP-SRS-18-2]`` :ref:`ZEP-SRS-18-2`
- ``[ZEP-SRS-18-3]`` :ref:`ZEP-SRS-18-3`
- ``[ZEP-SRS-18-4]`` :ref:`ZEP-SRS-18-4`
- ``[ZEP-SRS-18-5]`` :ref:`ZEP-SRS-18-5`
- ``[ZEP-SRS-18-6]`` :ref:`ZEP-SRS-18-6`
- ``[ZEP-SRS-18-7]`` :ref:`ZEP-SRS-18-7`
- ``[ZEP-SRS-18-8]`` :ref:`ZEP-SRS-18-8`
- ``[ZEP-SRS-18-9]`` :ref:`ZEP-SRS-18-9`
- ``[ZEP-SRS-18-10]`` :ref:`ZEP-SRS-18-10`
- ``[ZEP-SRS-18-11]`` :ref:`ZEP-SRS-18-11`

.. _ZEP-SYRS-4:

Device Driver Abstraction
=========================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SYRS-4
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Device Drivers

The Zephyr RTOS shall provide a framework for managing device drivers and peripherals.

**USER_STORY:**

As a Zephyr RTOS user I want my application to be portable between different MCU architectures (ARM Cortex-M/A, Intel x86, RISCV etc.) and MCU vendors (STM, NXP, Intel, etc.) without having to change the MCU peripherals access.

.. _ZEP-SYRS-5:

Fatal error and exception handling
==================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SYRS-5
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Exception and Error Handling

The Zephyr RTOS shall provide a framework for error and exception handling.

**USER_STORY:**

As a Zephyr RTOS user I want errors and exceptions to handled and react according to my applications requirements (e.g. reach/establish the applications safety state).

.. _ZEP-SYRS-6:

Common File system operation support
====================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SYRS-6
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - File Systems

The Zephyr RTOS shall provide a framework for managing file system access.

**USER_STORY:**

As a Zephyr RTOS user I want a posix / c like file system access to store data.

.. _ZEP-SYRS-7:

Interrupt Management
====================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SYRS-7
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Interrupts

The Zephyr RTOS shall provide a framework for interrupt and interrupt service routine management.

**USER_STORY:**

As the Zephyr RTOS user I want the Kernel to provide abstracted interfaces to
the platform enabling me to implement standard interrupts interrupt service routines
without detailed knowledge of the platform architecture and programming model.

**Children:**

- ``[ZEP-SRS-7-1]`` :ref:`ZEP-SRS-7-1`
- ``[ZEP-SRS-7-2]`` :ref:`ZEP-SRS-7-2`
- ``[ZEP-SRS-7-3 ]`` :ref:`ZEP-SRS-7-3 `
- ``[ZEP-SRS-7-4]`` :ref:`ZEP-SRS-7-4`
- ``[ZEP-SRS-7-5]`` :ref:`ZEP-SRS-7-5`
- ``[ZEP-SRS-7-6]`` :ref:`ZEP-SRS-7-6`
- ``[ZEP-SRS-7-7]`` :ref:`ZEP-SRS-7-7`
- ``[ZEP-SRS-7-8]`` :ref:`ZEP-SRS-7-8`
- ``[ZEP-SRS-7-9]`` :ref:`ZEP-SRS-7-9`
- ``[ZEP-SRS-7-10]`` :ref:`ZEP-SRS-7-10`
- ``[ZEP-SRS-7-11 ]`` :ref:`ZEP-SRS-7-11 `
- ``[ZEP-SRS-7-12 ]`` :ref:`ZEP-SRS-7-12 `
- ``[ZEP-SRS-7-13 ]`` :ref:`ZEP-SRS-7-13 `
- ``[ZEP-SRS-7-14 ]`` :ref:`ZEP-SRS-7-14 `
- ``[ZEP-SYRS-20]`` :ref:`ZEP-SYRS-20`

.. _ZEP-SYRS-20:

Direct ISR, Platform Specific helpers.
======================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SYRS-20
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Interrupts

Zephyr RTOS shall support development of direct ISRs by providing platform specific
code fragments and factory functions including, minimal header instructions,
minimal footer instructions, low power termination, and ISR construction.

**USER_STORY:**

As the Zephyr RTOS user I want the Kernel to provide support for implementing standard low latency
and low power interrupt service routines without detailed knowledge of the platform architecture
and programming model.

**Parents:**

- ``[ZEP-SYRS-7]`` :ref:`ZEP-SYRS-7`

**Children:**

- ``[ZEP-SRS-21-1]`` :ref:`ZEP-SRS-21-1`
- ``[ZEP-SRS-21-2]`` :ref:`ZEP-SRS-21-2`
- ``[ZEP-SRS-21-3]`` :ref:`ZEP-SRS-21-3`
- ``[ZEP-SRS-21-4]`` :ref:`ZEP-SRS-21-4`
- ``[ZEP-SRS-21-5]`` :ref:`ZEP-SRS-21-5`
- ``[ZEP-SRS-21-6]`` :ref:`ZEP-SRS-21-6`
- ``[ZEP-SRS-21-7]`` :ref:`ZEP-SRS-21-7`
- ``[ZEP-SRS-21-8]`` :ref:`ZEP-SRS-21-8`
- ``[ZEP-SRS-21-9]`` :ref:`ZEP-SRS-21-9`

.. _ZEP-SYRS-8:

Logging
=======

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SYRS-8
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Logging

The Zephyr RTOS shall provide a framework for logging events.

**USER_STORY:**

As a Zephyr RTOS user I want to be able to log application defined events as well as framework exceptions.

.. _ZEP-SYRS-9:

Memory Management framework
===========================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SYRS-9
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Memory Management

The Zephyr RTOS shall support a memory management framework.

**USER_STORY:**

As a Zephyr RTOS user I want memory to be allocated and protected to my application threads preventing mistakenly access to foreign memory as far as the hardware allows.

.. _ZEP-SYRS-10:

Power Management
================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SYRS-10
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Power Management

The Zephyr RTOS shall provide an interface to control hardware power states.

**USER_STORY:**

As a Zephyr RTOS user I want to be able to control the power mode of the MCU and its peripherals to take advantage of the hardware features and to be able to implement low power or battery driven long life applications.

Multi core and SMP
==================

.. _ZEP-SYRS-11:

Multiple CPU scheduling
-----------------------

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SYRS-11
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - SMP and Multi core

The Zephyr RTOS shall support scheduling of threads on multiple hardware CPUs.

**USER_STORY:**

As a Zephyr RTOS user I want Zephyr OS to run on MCUs/CPUs with one or more CPU cores.

.. _ZEP-SYRS-12:

Scheduling
----------

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SYRS-12
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - SMP and Multi core

The Zephyr RTOS shall provide an interface to assign a thread to a specific CPU.

**USER_STORY:**

As a Zephyr RTOS user, I want to be able to control which thread will run on which CPU.

Thread Synchronization
======================

.. _ZEP-SYRS-13:

Mutex
-----

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SYRS-13
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Mutex

The Zephyr RTOS shall provide an interface for managing communication between threads.

**USER_STORY:**

As a Zephyr RTOS user I want to able to exchange information between threads in a thread-safe manner guaranteeing data consistence.

.. _ZEP-SYRS-14:

Counting Semaphore
------------------

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SYRS-14
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Semaphore

The system shall implement a semaphore synchronization primitive for coordinating access to shared resources among multiple threads.

**Children:**

- ``[ZEP-SRS-5-1]`` :ref:`ZEP-SRS-5-1`
- ``[ZEP-SRS-5-2]`` :ref:`ZEP-SRS-5-2`
- ``[ZEP-SRS-5-4]`` :ref:`ZEP-SRS-5-4`
- ``[ZEP-SRS-5-5]`` :ref:`ZEP-SRS-5-5`
- ``[ZEP-SRS-5-6]`` :ref:`ZEP-SRS-5-6`
- ``[ZEP-SRS-5-7]`` :ref:`ZEP-SRS-5-7`
- ``[ZEP-SRS-5-8]`` :ref:`ZEP-SRS-5-8`
- ``[ZEP-SRS-5-9]`` :ref:`ZEP-SRS-5-9`
- ``[ZEP-SRS-5-10]`` :ref:`ZEP-SRS-5-10`
- ``[ZEP-SRS-5-11]`` :ref:`ZEP-SRS-5-11`
- ``[ZEP-SRS-5-12]`` :ref:`ZEP-SRS-5-12`
- ``[ZEP-SRS-5-13]`` :ref:`ZEP-SRS-5-13`
- ``[ZEP-SRS-5-14]`` :ref:`ZEP-SRS-5-14`
- ``[ZEP-SRS-5-15]`` :ref:`ZEP-SRS-5-15`
- ``[ZEP-SRS-5-16]`` :ref:`ZEP-SRS-5-16`
- ``[ZEP-SRS-5-17]`` :ref:`ZEP-SRS-5-17`
- ``[ZEP-SRS-5-18]`` :ref:`ZEP-SRS-5-18`

Threads
=======

.. _ZEP-SYRS-15:

Thread support
--------------

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SYRS-15
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Threads

The Zephyr RTOS shall support threads.

**USER_STORY:**

As a Zephyr RTOS user, I want to be able to have support for the kernel objects named threads for processing work.

**Children:**

- ``[ZEP-SRS-2-4]`` :ref:`ZEP-SRS-2-4`
- ``[ZEP-SRS-1-1]`` :ref:`ZEP-SRS-1-1`
- ``[ZEP-SRS-1-3]`` :ref:`ZEP-SRS-1-3`
- ``[ZEP-SRS-1-4]`` :ref:`ZEP-SRS-1-4`
- ``[ZEP-SRS-1-5]`` :ref:`ZEP-SRS-1-5`
- ``[ZEP-SRS-1-6]`` :ref:`ZEP-SRS-1-6`
- ``[ZEP-SRS-1-7]`` :ref:`ZEP-SRS-1-7`
- ``[ZEP-SRS-1-8]`` :ref:`ZEP-SRS-1-8`
- ``[ZEP-SRS-1-9]`` :ref:`ZEP-SRS-1-9`
- ``[ZEP-SRS-1-11]`` :ref:`ZEP-SRS-1-11`
- ``[ZEP-SRS-1-12]`` :ref:`ZEP-SRS-1-12`

.. _ZEP-SYRS-16:

Thread management
-----------------

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SYRS-16
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Threads

The Zephyr RTOS shall provide a framework for managing multiple threads of execution.

**USER_STORY:**

As a Zephyr RTOS user, I want to be able to manage the execute of multiple threads with different priorities.

**Children:**

- ``[ZEP-SRS-1-1]`` :ref:`ZEP-SRS-1-1`
- ``[ZEP-SRS-1-3]`` :ref:`ZEP-SRS-1-3`
- ``[ZEP-SRS-1-4]`` :ref:`ZEP-SRS-1-4`
- ``[ZEP-SRS-1-5]`` :ref:`ZEP-SRS-1-5`
- ``[ZEP-SRS-1-6]`` :ref:`ZEP-SRS-1-6`
- ``[ZEP-SRS-1-7]`` :ref:`ZEP-SRS-1-7`
- ``[ZEP-SRS-1-8]`` :ref:`ZEP-SRS-1-8`
- ``[ZEP-SRS-1-9]`` :ref:`ZEP-SRS-1-9`
- ``[ZEP-SRS-1-10]`` :ref:`ZEP-SRS-1-10`
- ``[ZEP-SRS-1-11]`` :ref:`ZEP-SRS-1-11`
- ``[ZEP-SRS-1-12]`` :ref:`ZEP-SRS-1-12`

.. _ZEP-SYRS-17:

Thread priority
---------------

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SYRS-17
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Threads

Threads shall have a priority.

**USER_STORY:**

As a Zephyr RTOS user, I want to be able to give my threads different priorities for execution.

**Children:**

- ``[ZEP-SRS-1-2]`` :ref:`ZEP-SRS-1-2`

.. _ZEP-SYRS-18:

Timers
======

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SYRS-18
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Timers

The Zephyr RTOS shall provide a framework for managing time-based events.

**USER_STORY:**

As a Zephyr RTOS user, I want to start, suspend, resume and stop timers which shall trigger an event on a set expiration time.

**Children:**

- ``[ZEP-SRS-4-1]`` :ref:`ZEP-SRS-4-1`
- ``[ZEP-SRS-4-2]`` :ref:`ZEP-SRS-4-2`
- ``[ZEP-SRS-4-3]`` :ref:`ZEP-SRS-4-3`
- ``[ZEP-SRS-4-4]`` :ref:`ZEP-SRS-4-4`
- ``[ZEP-SRS-4-5]`` :ref:`ZEP-SRS-4-5`
- ``[ZEP-SRS-4-6]`` :ref:`ZEP-SRS-4-6`
- ``[ZEP-SRS-4-7]`` :ref:`ZEP-SRS-4-7`
- ``[ZEP-SRS-4-8]`` :ref:`ZEP-SRS-4-8`
- ``[ZEP-SRS-4-9]`` :ref:`ZEP-SRS-4-9`
- ``[ZEP-SRS-4-10]`` :ref:`ZEP-SRS-4-10`
- ``[ZEP-SRS-4-11]`` :ref:`ZEP-SRS-4-11`
- ``[ZEP-SRS-4-12]`` :ref:`ZEP-SRS-4-12`
- ``[ZEP-SRS-4-13]`` :ref:`ZEP-SRS-4-13`
- ``[ZEP-SRS-4-14]`` :ref:`ZEP-SRS-4-14`
- ``[ZEP-SRS-4-15]`` :ref:`ZEP-SRS-4-15`

.. _ZEP-SYRS-19:

Tracing
=======

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SYRS-19
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Tracing

Zepyhr shall provide a framework mechanism for tracing low level system operations  (NOTE: system calls, interrupts, kernel calls, thread, synchronization, etc.).

**USER_STORY:**

As a Zephyr RTOS user, I want to be able to trace different OS operations.

Condition Variables
===================

.. _ZEP-SYRS-21:

Condition Variables
-------------------

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SYRS-21
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Non-Functional
    * - **COMPONENT:**
      - Condition Variables

The Zephyr RTOS shall provide a framework to synchronize threads based on a condition variable.

**Children:**

- ``[ZEP-SRS-20-1]`` :ref:`ZEP-SRS-20-1`
- ``[ZEP-SRS-20-2]`` :ref:`ZEP-SRS-20-2`
- ``[ZEP-SRS-20-3]`` :ref:`ZEP-SRS-20-3`
- ``[ZEP-SRS-20-4]`` :ref:`ZEP-SRS-20-4`
- ``[ZEP-SRS-20-5]`` :ref:`ZEP-SRS-20-5`
- ``[ZEP-SRS-20-6]`` :ref:`ZEP-SRS-20-6`
- ``[ZEP-SRS-20-7]`` :ref:`ZEP-SRS-20-7`
- ``[ZEP-SRS-20-8]`` :ref:`ZEP-SRS-20-8`
- ``[ZEP-SRS-20-9]`` :ref:`ZEP-SRS-20-9`
- ``[ZEP-SRS-20-10]`` :ref:`ZEP-SRS-20-10`
- ``[ZEP-SRS-20-11]`` :ref:`ZEP-SRS-20-11`
- ``[ZEP-SRS-20-12]`` :ref:`ZEP-SRS-20-12`
- ``[ZEP-SRS-20-13]`` :ref:`ZEP-SRS-20-13`
- ``[ZEP-SRS-20-14]`` :ref:`ZEP-SRS-20-14`

Queues
======

.. _ZEP-SYRS-22:

Queues data passing
-------------------

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SYRS-22
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Queues

The Zephyr RTOS shall implement a queue which can be used to pass data between threads and interrupt service routines.
