Data Passing
$$$$$$$$$$$$

SPDX-License-Identifier: Apache-2.0

.. _ZEP-SRS-15-1:

Traditional FIFO Queue
======================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-15-1
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Data Passing

The Zephyr RTOS shall provide a kernel object that implements a traditional first in, first out (FIFO) queue, allowing threads and ISRs to add and remove a limited number of 32-bit data values.

**USER_STORY:**

As a Zephyr RTOS user I want to be able to exchange 1 to N data objects between different threads and ISR in a thread-safe manner with a first-in-first-out (queue) behaviour.

.. _ZEP-SRS-15-2:

Traditional LIFO queue
======================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-15-2
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Data Passing

The Zephyr RTOS shall provide a kernel object that implements a traditional last in, first out (LIFO) queue, allowing threads and ISRs to add and remove a limited number of 32-bit data values.

**USER_STORY:**

As a Zephyr RTOS user I want to be able to exchange 1 to N data objects between different threads and ISR in a thread-safe manner with a last-in-first-out (stack) behaviour.
