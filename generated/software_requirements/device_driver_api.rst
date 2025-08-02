Device Driver API
$$$$$$$$$$$$$$$$$

SPDX-License-Identifier: Apache-2.0

.. _ZEP-SRS-14-1:

Device Driver Abstraction
=========================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-14-1
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Device Driver API

The Zephyr RTOS shall provide abstraction of device drivers with common functionalities as an intermediate interface between applications and device drivers, where such interface is implemented by individual device drivers.

Proposal for replacement: Zephyr shall provide an interface between application and individual device drivers to provide an abstraction of device drivers with common functionalities.

.. _ZEP-SRS-14-2:

Expose kernel to hardware interrupts
====================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-14-2
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Device Driver API

The Zephyr RTOS shall provide an interface for managing a defined set of hardware exceptions (including interrupts) across all systems.

**USER_STORY:**

As a Zephyr RTOS user I want hardware exceptions (hardware failures, programming mistakes) to be handled gracefully (no program crashes as far as possible).
