Thread Scheduling
$$$$$$$$$$$$$$$$$

SPDX-License-Identifier: Apache-2.0

Thread Scheduling
=================

.. _ZEP-SRS-2-1:

Support operation on more than one CPU
--------------------------------------

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-2-1
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Multi Core

The Zephyr RTOS shall support operation on more than one physical CPU sharing the same kernel state.

.. _ZEP-SRS-2-2:

Running threads on specific CPUs
--------------------------------

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-2-2
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Multi Core

The Zephyr RTOS shall provide an interface for running threads on specific sets of CPUs ( default is 1 CPU).

**USER_STORY:**

As a Zephyr RTOS user I want Zephyr OS to be able to specify the CPU core or the set of CPU cores on which a thread shall be executed.

.. _ZEP-SRS-2-3:

Exclusion between physical CPUs
-------------------------------

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-2-3
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Multi Core

The Zephyr RTOS shall provide an interface for mutual exclusion between multiple physical CPUs.

**USER_STORY:**

As a Zephyr RTOS user I want Zephyr OS to provide synchronization mechanisms between the CPU cores and the access to common resources.

Thread Scheduling
=================

.. _ZEP-SRS-2-4:

Scheduling a thread based on an event
-------------------------------------

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-2-4
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Thread Scheduling

The Zephyr RTOS shall provide an interface to schedule a thread based on an event.

**USER_STORY:**

As a Zephyr RTOS user, I want to be able to execute work which reacts on events and interrupts the current executed work.

**Parents:**

- ``[ZEP-SYRS-15]`` :ref:`ZEP-SYRS-15`

.. _ZEP-SRS-2-5:

Deadline Scheduling Priorities
------------------------------

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-2-5
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Thread Scheduling

The Zephyr RTOS shall organize running threads by earliest deadline first priority.

**USER_STORY:**

As a Zephyr RTOS user, I want to be able to schedule threads by earliest deadline first.

.. _ZEP-SRS-2-6:

Work Queue utility capable of running preemptible work items
------------------------------------------------------------

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-2-6
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Thread Scheduling

The Zephyr RTOS shall provide a thread-pooled work queue utility capable of running preemptible work items with specific scheduler priorities.

**USER_STORY:**

As a Zephyr RTOS user, I want to be able to add work items in a thread work queue with different priorities and these shall be scheduled according their priorities.

.. _ZEP-SRS-2-7:

Run user supplied functions in-order in a separate thread(s)
------------------------------------------------------------

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-2-7
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Thread Scheduling

The Zephyr RTOS shall provide an interface for running user-supplied functions.

**USER_STORY:**

As a Zephyr RTOS user, I want to be able to run functions in-order in a separated thread/threads.

.. _ZEP-SRS-2-8:

Organize running threads into a fixed list
------------------------------------------

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-2-8
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Thread Scheduling

The Zephyr RTOS shall organize running threads into a fixed list of numeric priorities.

**USER_STORY:**

As a Zephyr RTOS user, I want that the OS organize running threads in a fixed list of numeric priorities.

.. _ZEP-SRS-2-9:

Preemption support
------------------

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-2-9
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Thread Scheduling

The Zephyr RTOS shall support preemption of a running thread by a higher priority thread.

**USER_STORY:**

As a Zephyr RTOS user, I want that the OS preempt running threads by a thread with higher priority.

.. _ZEP-SRS-2-10:

Un-preemptible thread priorities
--------------------------------

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-2-10
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Thread Scheduling

The Zephyr RTOS shall support thread priorities which cannot be preempted by other user threads.

**USER_STORY:**

As a Zephyr RTOS user, I want to be able to configure thread prioritizes which cannot be preempted by other user threads.

.. _ZEP-SRS-2-11:

Time sharing of CPU resources
-----------------------------

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-2-11
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - Thread Scheduling

The Zephyr RTOS shall support time sharing of CPU resources among threads of the same priority.

**USER_STORY:**

As a Zephyr RTOS user, I want to be able to configure my RTOS in the way, that the CPU resources are shared evenly among executed threads of the same priority.
