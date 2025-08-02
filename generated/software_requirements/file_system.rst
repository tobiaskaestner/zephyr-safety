File system
$$$$$$$$$$$

SPDX-License-Identifier: Apache-2.0

.. _ZEP-SRS-17-1:

Create file
===========

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-17-1
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - File System

Zephyr shall provide file create capabilities for files on the file system.

**USER_STORY:**

As a Zephyr OS user I want to be able to create a new file or overwrite an existing file at the same filesystem location / identifier (e.g. path + name).

.. _ZEP-SRS-17-2:

Open files
==========

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-17-2
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - File System

Zephyr shall provide file open capabilities for files on the file system.

**USER_STORY:**

As a Zephyr OS user I want to be able to open a file for writing or reading.
When opened for writing, I want to have exclusive access to the file.

.. _ZEP-SRS-17-3:

Read files
==========

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-17-3
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - File System

Zephyr shall provide read access to files in the file system.

**USER_STORY:**

As a Zephyr OS user I want to be able to read from an existing file, also while the file is read from multiple and write accessed from one other instances.

.. _ZEP-SRS-17-4:

Write to files
==============

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-17-4
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - File System

Zephyr shall provide write access to the files in the file system.

**USER_STORY:**

As a Zephyr OS user I want to be able to write to a file either from the beginning of the file or appending at the end.

.. _ZEP-SRS-17-5:

Close file
==========

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-17-5
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - File System

Zephyr shall provide file close capabilities for files on the file system.

**USER_STORY:**

As a Zephyr OS user I want to be able to close a file after being finished with my file operations, unlocking any access restrictions.

.. _ZEP-SRS-17-6:

Move file
=========

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-17-6
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - File System

Zephyr shall provide the capability to move files on the file system.

.. _ZEP-SRS-17-7:

Delete file
===========

.. list-table::
    :align: left
    :header-rows: 0

    * - **UID:**
      - ZEP-SRS-17-7
    * - **STATUS:**
      - Draft
    * - **TYPE:**
      - Functional
    * - **COMPONENT:**
      - File System

Zephyr shall provide file delete capabilities for files on the file system.

**USER_STORY:**

As a Zephyr OS user I want to be able to delete an existing file.
