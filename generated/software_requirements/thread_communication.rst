Thread Communication
$$$$$$$$$$$$$$$$$$$$

SPDX-License-Identifier: Apache-2.0

.. _ZEP-SRS-3-1:

Exchanging data between threads
===============================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-3-1
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Thread Communication

The Zephyr RTOS shall provide a mechanism for exchanging data between threads.

**USER_STORY:**

(Note: copying data may be needed here - what is Zephyr doing? is it configurable?)

.. _ZEP-SRS-3-2:

Waiting for results during communication
========================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-3-2
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Thread Communication

The Zephyr RTOS shall provide mechanisms to enable waiting for results during communication between threads. (NOTE:  waiting for results is really bad and dangerous, want to avoid if at all possible).

**USER_STORY:**

=N73

.. _ZEP-SRS-3-3:

Poll Operation Support
======================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-3-3
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Thread Communication

The Zephyr RTOS shall support a poll operation which enables waiting concurrently for any one of multiple conditions to be fulfilled.

**USER_STORY:**

As a Zephyr RTOS user I want my thread to wait for one of several defined events to occur and only continue when one of them has occurred.

.. _ZEP-SRS-3-4:

Pipe Communication Primitive
============================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-3-4
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Thread Communication

The Zephyr RTOS shall provide a communication primitive that allows a thread to transfer a block of
data to another thread.

**USER_STORY:**

As a Zephyr RTOS user I want to send a byte stream from one thread to another in a thread-safe manner.

.. _ZEP-SRS-3-5:

Message Queue
=============

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-3-5
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Thread Communication

The Zephyr RTOS shall provide a a communication primitive that allow threads and ISRs to asynchronously exchange fixed-size data items.

.. _ZEP-SRS-3-6:

Mailbox Kernel Primitive
========================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-3-6
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Thread Communication

The Zephyr RTOS shall provide a communication primitive that allows threads to exchange messages of varying sizes asynchronously or synchronously.

**USER_STORY:**

As a Zephyr RTOS user I want a sending thread to deposit a message into the mailbox,
and a receiving thread to be able to retrieve the message at its convenience. This
allows for asynchronous communication, where threads do not need to synchronize their
execution explicitly.
