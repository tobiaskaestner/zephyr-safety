Interrupts
$$$$$$$$$$

SPDX-License-Identifier: Apache-2.0

.. _ZEP-SRS-7-1:

Installing static IRQ service routines (ISR).
=============================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-7-1
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Interrupts

Zephyr RTOS shall provide a mechanism to initialize a static IRQ service routine (ISR),
providing all parameters needed to configure the hardware and software.

**Parents:**

- ``[ZEP-SYRS-7]`` :ref:`ZEP-SYRS-7`

.. _ZEP-SRS-7-2:

Static IRQ initial status.
==========================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-7-2
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Interrupts

The static IRQ shall be initially disabled.

**Parents:**

- ``[ZEP-SYRS-7]`` :ref:`ZEP-SYRS-7`

.. _ZEP-SRS-7-3 :

Installing direct IRQ service routines (ISR).
=============================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-7-3 
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Interrupts

Zephyr RTOS shall provide a mechanism to initialize a direct IRQ handler,
providing all parameters needed to configure the hardware and software.

**USER_STORY:**

As the developer of low-power and low-latency applications, I need to implement ISRs 
that avoid the normal interrupt and power management overhead.

**Parents:**

- ``[ZEP-SYRS-7]`` :ref:`ZEP-SYRS-7`

.. _ZEP-SRS-7-4:

Direct IRQ initial status.
==========================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-7-4
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Interrupts

The direct IRQ shall be initially disabled.

**Parents:**

- ``[ZEP-SYRS-7]`` :ref:`ZEP-SYRS-7`

.. _ZEP-SRS-7-5:

Installing dynamic IRQ service routines (ISR).
==============================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-7-5
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Interrupts

Zephyr RTOS shall provide a mechanism to initialize a dynamic IRQ service routine, 
providing all parameters needed to configure the hardware and software.

**Parents:**

- ``[ZEP-SYRS-7]`` :ref:`ZEP-SYRS-7`

.. _ZEP-SRS-7-6:

Dynamic IRQ initial status.
===========================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-7-6
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Interrupts

The dynamic IRQ shall be initially disabled.

**Parents:**

- ``[ZEP-SYRS-7]`` :ref:`ZEP-SYRS-7`

.. _ZEP-SRS-7-7:

Uninstalling dynamic IRQ service routines (ISR).
================================================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-7-7
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Interrupts

Zephyr RTOS shall provide a mechanism to uninstall a dynamic ISR.

**Parents:**

- ``[ZEP-SYRS-7]`` :ref:`ZEP-SYRS-7`

.. _ZEP-SRS-7-8:

Global IRQ disable
==================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-7-8
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Interrupts

Zephyr RTOS shall provide a mechanism to Disable all IRQs on a CPU, and 
return the state the IRQ hardware prior to being disabled.

**Parents:**

- ``[ZEP-SYRS-7]`` :ref:`ZEP-SYRS-7`

.. _ZEP-SRS-7-9:

Global IRQ enable
=================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-7-9
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Interrupts

Zephyr RTOS shall provide a mechanism to Enable all IRQs on a CPU 
and return them to thier previous state.

**Parents:**

- ``[ZEP-SYRS-7]`` :ref:`ZEP-SYRS-7`

.. _ZEP-SRS-7-10:

Specific IRQ disable
====================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-7-10
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Interrupts

Zephyr RTOS shall provide a mechanism to Disable a specified IRQ.

**Parents:**

- ``[ZEP-SYRS-7]`` :ref:`ZEP-SYRS-7`

.. _ZEP-SRS-7-11 :

Specific IRQ enable
===================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-7-11 
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Interrupts

Zephyr RTOS shall provide a mechanism to Enable a specified IRQ.

**Parents:**

- ``[ZEP-SYRS-7]`` :ref:`ZEP-SYRS-7`

.. _ZEP-SRS-7-12 :

IRQ Enabled status
==================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-7-12 
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Interrupts

Zephyr RTOS shall provide mechanisms that returns the Enabled status 
of a specified IRQ, where the status is Enabled or Disabled.

**Parents:**

- ``[ZEP-SYRS-7]`` :ref:`ZEP-SYRS-7`

.. _ZEP-SRS-7-13 :

ISR Context status
==================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-7-13 
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Interrupts

Zephyr RTOS shall provide mechanisms that returns the execution context, 
where the context is In-ISR or Not In-ISR.

**USER_STORY:**

As the developer of functions that may run in either ISR or THREAD context, 
I need to know the current context to enable condition behavior.

**Parents:**

- ``[ZEP-SYRS-7]`` :ref:`ZEP-SYRS-7`

.. _ZEP-SRS-7-14 :

Multi-level interrupts
======================

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-7-14 
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Interrupts

The Zephyr RTOS shall support multi-level preemptive interrupt priorities, when supported by hardware.

**Parents:**

- ``[ZEP-SYRS-7]`` :ref:`ZEP-SYRS-7`
