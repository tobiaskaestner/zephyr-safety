Memory Objects
$$$$$$$$$$$$$$

SPDX-License-Identifier: Apache-2.0

.. _ZEP-SRS-9-1:

Dynamic Memory Allocation
=========================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-9-1
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Memory Objects

The Zephyr RTOS shall allow threads to dynamically allocate variable-sized memory regions from a specified range of memory.

**USER_STORY:**

As a Zephyr RTOS user I want my application to be able to dynamically allocate memory of a application defined size.

.. _ZEP-SRS-9-2:

Memory Slab Object
==================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-9-2
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Memory Objects

The Zephyr RTOS shall allow threads to dynamically allocate fixed-sized memory regions from a specified range of memory.

**USER_STORY:**

As a Zephyr RTOS user I want a most efficient and least fragmentation prone dynamic memory allocation mechanism.
