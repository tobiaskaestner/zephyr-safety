Timers
$$$$$$

SPDX-License-Identifier: Apache-2.0

.. _ZEP-SRS-4-1:

Timer definition at compile time
================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-4-1
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Timers

The Zephyr RTOS shall provide a mechanism to define and statically (i.e. compile time) initialize timers.

**Parents:**

- ``[ZEP-SYRS-18]`` :ref:`ZEP-SYRS-18`

.. _ZEP-SRS-4-2:

Timer expiry function
=====================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-4-2
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Timers

When initializing a timer, the Zephyr RTOS shall support setting a function that gets called when the timer expires.

**Parents:**

- ``[ZEP-SYRS-18]`` :ref:`ZEP-SYRS-18`

.. _ZEP-SRS-4-3:

Timer stop function
===================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-4-3
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Timers

When initializing a timer, the Zephyr RTOS shall support setting a function that gets called when a running timer is stopped.

**Parents:**

- ``[ZEP-SYRS-18]`` :ref:`ZEP-SYRS-18`

.. _ZEP-SRS-4-4:

Timer definition at run time
============================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-4-4
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Timers

The Zephyr RTOS shall provide a mechanism to define and initialize timers at run time.

**Parents:**

- ``[ZEP-SYRS-18]`` :ref:`ZEP-SYRS-18`

.. _ZEP-SRS-4-5:

Timer start
===========

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-4-5
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Timers

The Zephyr RTOS shall provide a mechanism to start a timer for a specific duration and periodicity.

**Parents:**

- ``[ZEP-SYRS-18]`` :ref:`ZEP-SYRS-18`

.. _ZEP-SRS-4-6:

Timer stop
==========

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-4-6
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Timers

The Zephyr RTOS shall provide a mechanism to stop a running timer.

**Parents:**

- ``[ZEP-SYRS-18]`` :ref:`ZEP-SYRS-18`

.. _ZEP-SRS-4-7:

Timer status
============

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-4-7
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Non-Functional
    * - **COMPONENT:**
      - Timers

The Zephyr RTOS shall provide a mechanism to read the number of times a timer has expired and then reset this number to 0.

**Parents:**

- ``[ZEP-SYRS-18]`` :ref:`ZEP-SYRS-18`

.. _ZEP-SRS-4-8:

Timer status reinitialization
=============================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-4-8
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Non-Functional
    * - **COMPONENT:**
      - Timers

When a timer is initialized, started or synchronized to a thread, the Zephyr RTOS shall reset the timer number of times it has expired to 0.

**Parents:**

- ``[ZEP-SYRS-18]`` :ref:`ZEP-SYRS-18`

.. _ZEP-SRS-4-9:

Timer thread synchronization
============================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-4-9
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Timers

The Zephyr RTOS shall provide a mechanism to synchronize a thread to a timer and then block the thread execution until any of the following conditions is satisfied:
- The timer is stopped
- The timer number of times it has expired is superior to 0

**Parents:**

- ``[ZEP-SYRS-18]`` :ref:`ZEP-SYRS-18`

.. _ZEP-SRS-4-10:

Timer next expiration time in system ticks
==========================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-4-10
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Timers

The Zephyr RTOS shall provide a mechanism to get a timer's next expiration time in system ticks.

**Parents:**

- ``[ZEP-SYRS-18]`` :ref:`ZEP-SYRS-18`

.. _ZEP-SRS-4-11:

Timer remaining time until expiration in system ticks
=====================================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-4-11
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Timers

The Zephyr RTOS shall provide a mechanism to get a timer's remaining time until its next expiry in system ticks.

**Parents:**

- ``[ZEP-SYRS-18]`` :ref:`ZEP-SYRS-18`

.. _ZEP-SRS-4-12:

Timer remaining time until expiration in milliseconds
=====================================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-4-12
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Timers

The Zephyr RTOS shall provide a mechanism to get the timer's remaining time until its next expiry in milliseconds.

**Parents:**

- ``[ZEP-SYRS-18]`` :ref:`ZEP-SYRS-18`

.. _ZEP-SRS-4-13:

Timer set user data
===================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-4-13
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Timers

The Zephyr RTOS shall support adding user defined data to a timer.

**Parents:**

- ``[ZEP-SYRS-18]`` :ref:`ZEP-SYRS-18`

.. _ZEP-SRS-4-14:

Timer get user data
===================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-4-14
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Timers

The Zephyr RTOS shall support retrieving user defined data from a timer.

**Parents:**

- ``[ZEP-SYRS-18]`` :ref:`ZEP-SYRS-18`

.. _ZEP-SRS-4-15:

Timer expire functions in interrupt context
===========================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-4-15
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Timers

When a timer expiry function is called, the Zephyr RTOS shall do so in the interrupt context.

**Parents:**

- ``[ZEP-SYRS-18]`` :ref:`ZEP-SYRS-18`
