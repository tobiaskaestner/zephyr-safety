Logging
$$$$$$$

SPDX-License-Identifier: Apache-2.0

.. _ZEP-SRS-11-1:

Dedicated Logging Thread Support
================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-11-1
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Logging

The Zephyr RTOS shall support isolation of logging from other functionality.

**USER_STORY:**

As a Zephyr RTOS user I want to be able to configure logging of events so the execution of logging activities does have no or only a minimal impact to the timing behaviour of my application.

.. _ZEP-SRS-11-2:

Logs available for post processing
==================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-11-2
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Logging

The Zephyr RTOS logging shall produce logs that are capable of being post processed.

**USER_STORY:**

As a Zephyr RTOS user I want the logging information to be stored in a format which allows to be read possibly converted or displayed by COTS tools.

.. _ZEP-SRS-11-3:

Formatting log messages
=======================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-11-3
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Logging

The Zephyr RTOS logging shall support formatting of log messages to enable filtering.

**USER_STORY:**

As a Zephyr RTOS user I want to be able my application to format texts (printf alike) into the log message.

.. _ZEP-SRS-11-4:

Logging Filtering Support
=========================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-11-4
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Logging

The Zephyr RTOS logging system shall support filtering based on severity level.

**USER_STORY:**

As a Zephyr RTOS user I want to be able to distinguish between different severity level for my log messages (e.g. DEBUG, INFO, WARN, ERROR, PANIC).

.. _ZEP-SRS-11-5:

Multiple Backend Logging Support
================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-11-5
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Logging

The Zephyr RTOS shall support logging messages to multiple system resources.

**USER_STORY:**

As a Zephyr RTOS user I want to be able to simultaneously log to different channels which may store / redirect the information on / to different hardware (EEPROM, Flash, FRAM, UART, Ethernet, USB etc.).

.. _ZEP-SRS-11-6:

Deferred Logging Support
========================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-11-6
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Logging

The Zephyr RTOS shall support deferred logging (TODO: need more detail about the constraints and limits on what can be deferred).

**USER_STORY:**

As a Zephyr RTOS user I want a minimal influence of logging activities to the timing behaviour of my application. Time consuming logging threads shall be done in the background.
