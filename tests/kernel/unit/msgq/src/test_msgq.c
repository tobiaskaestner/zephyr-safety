/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @defgroup kernel_unit_msgq kernel/msg_q.c
 * @ingroup kernel_unit_tests
 * @brief Design specification of kernel/msg_q.c, written as unit tests.
 *
 * @par The message queue object
 * A message queue (@c struct @c k_msgq) is a ring buffer of messages of one
 * fixed size. It has these parts:
 * - @c buffer_start, @c buffer_end: the ring buffer. It has space for
 *   @c max_msgs messages of @c msg_size bytes. @c buffer_end is the first
 *   byte after the ring buffer.
 * - @c read_ptr: the slot of the oldest message (the head).
 * - @c write_ptr: the slot after the newest message (the tail).
 * - @c used_msgs: the number of messages in the ring buffer.
 * - @c lock: the spinlock of the message queue. Each message queue has its
 *   own lock.
 * - @c wait_q: the wait queue. Readers wait on it if the ring buffer is
 *   empty, and writers wait on it if the ring buffer is full.
 * - @c flags: @c K_MSGQ_FLAG_ALLOC if msg_q.c allocated the ring buffer.
 * - @c poll_events: with @kconfig{CONFIG_POLL}, the k_poll() events.
 *
 * The message queue copies the data. k_msgq_put() copies @c msg_size bytes
 * from the caller into the ring buffer. k_msgq_get() copies them from the
 * ring buffer to the caller. The caller can use its memory again when the
 * function returns. If @c read_ptr or @c write_ptr moves to @c buffer_end,
 * it moves to @c buffer_start (wrap-around). Thus the ring buffer has no
 * gaps, and @c write_ptr is @c used_msgs slots after @c read_ptr.
 *
 * @par Hand-over to a waiting thread
 * A reader waits only if the ring buffer is empty. A writer waits only if
 * the ring buffer is full. A waiting thread keeps the address of its data in
 * @c _current->base.swap_data and calls z_pend_curr().
 * - k_msgq_put() and k_msgq_put_front(): if the ring buffer is not full and
 *   a reader waits, the message goes directly into the buffer of the reader
 *   (@c swap_data). It does not go into the ring buffer.
 * - k_msgq_get(): after it removes the head message, the ring buffer has one
 *   free slot. If a writer waits, the message of the writer (@c swap_data)
 *   goes into this slot at the tail.
 *
 * In both cases, the operation removes the thread from the wait queue with
 * z_unpend_first_thread_locked(), sets its return value to 0 with
 * arch_thread_return_value_set(), and makes it ready with
 * z_sched_ready_locked(). The copy comes before the thread is ready.
 *
 * @par Operations
 * - k_msgq_init() initializes a message queue on a buffer of the caller.
 *   k_msgq_alloc_init() allocates the buffer with z_thread_malloc() from the
 *   resource pool of the thread, and k_msgq_cleanup() frees it.
 * - k_msgq_put() appends a message at the tail. k_msgq_put_front() puts a
 *   message at the head and never waits.
 * - k_msgq_get() removes the head message.
 * - k_msgq_peek() and k_msgq_peek_at() copy a message and do not remove it.
 * - k_msgq_purge() discards all messages and wakes all waiting threads with
 *   -ENOMSG.
 * - k_msgq_get_attrs(), k_msgq_num_free_get() and k_msgq_num_used_get()
 *   read the state. The last two are static inline in @c zephyr/kernel.h.
 *
 * @par Locks
 * Each operation, except the initialization, k_msgq_get_attrs() and the
 * static inline functions, locks the spinlock of its message queue before it
 * reads the state. k_spin_lock() locks the interrupts with arch_irq_lock()
 * and returns a key. Each path releases the lock exactly once, with the same
 * key, as its last call to the layers below:
 * - k_spin_unlock(), if no thread became ready.
 * - z_reschedule(), if the operation made a thread ready.
 * - z_pend_curr(), if the operation must wait. z_pend_curr() adds the
 *   current thread to the wait queue, releases the lock and switches threads
 *   in one step.
 *
 * The hand-over is in a block @c LOCK_SCHED_SPINLOCK. With one CPU
 * (@kconfig{CONFIG_MP_MAX_NUM_CPUS} = 1), this block adds no lock: the lock
 * of the message queue locks the interrupts, and this is sufficient. With
 * more than one CPU, the block also locks the scheduler spinlock. Thus a
 * timeout handler on another CPU cannot wake the waiting thread before the
 * copy is complete.
 *
 * k_msgq_cleanup() frees the buffer while the lock is held.
 *
 * @par Interfaces below msg_q.c
 * - Scheduler (@c ksched.h): z_unpend_first_thread_locked(),
 *   z_sched_ready_locked(), z_sched_wake(), z_reschedule(), z_pend_curr(),
 *   and @c _current (the data of @c kernel/init.c).
 * - Scheduler spinlock (@c kspinlock.h): @c LOCK_SCHED_SPINLOCK and
 *   @c _sched_spinlock.
 * - Wait queue (@c wait_q.h): z_waitq_init(), z_waitq_head(),
 *   z_waitq_head_locked().
 * - Architecture (@c kernel_arch_interface.h): arch_thread_return_value_set(),
 *   arch_is_in_isr(), and arch_irq_lock() and arch_irq_unlock() through
 *   k_spin_lock() and k_spin_unlock().
 * - Memory (@c kernel/mempool.c): z_thread_malloc(), k_free().
 * - Poll (@c kernel_internal.h): z_handle_obj_poll_events().
 * - Object core: k_obj_core_init_and_link() and K_OBJ_TYPE_DEFINE().
 * - Kernel objects: k_object_init().
 * - System call checks: K_SYSCALL_OBJ(), K_SYSCALL_OBJ_NEVER_INIT(),
 *   K_SYSCALL_MEMORY_READ(), K_SYSCALL_MEMORY_WRITE(), K_OOPS().
 *
 * @par Kconfig options that change msg_q.c
 * - @kconfig{CONFIG_POLL}: the poll events of the message queue.
 * - @kconfig{CONFIG_USERSPACE}: the verification functions
 *   z_vrfy_k_msgq_*() and the kernel object of the message queue.
 * - @kconfig{CONFIG_OBJ_CORE_MSGQ}: the object type of the message queues.
 * - @kconfig{CONFIG_MP_MAX_NUM_CPUS}: with more than one CPU, the hand-over
 *   locks the scheduler spinlock.
 * - The CHECKIF() options for the check of the wait queue in
 *   z_msgq_cleanup(): @kconfig{CONFIG_RUNTIME_ERROR_CHECKS} (default) returns
 *   -EBUSY, @kconfig{CONFIG_NO_RUNTIME_CHECKS} does no check,
 *   @kconfig{CONFIG_ASSERT_ON_ERRORS} asserts.
 * - @kconfig{CONFIG_ASSERT}: the assertions on the buffer size, on a wait
 *   in an ISR and on the write pointer. The option also enables
 *   @kconfig{CONFIG_SPIN_VALIDATE} in @c zephyr/spinlock.h.
 *
 * @par Test method
 * The tests call the functions of msg_q.c directly (z_impl_k_msgq_*() for
 * the system calls) and z_vrfy_k_msgq_*(). All calls below msg_q.c go to
 * FFF fakes. The fake unit_arch_irq_lock() returns KERNEL_UNIT_IRQ_KEY for
 * the lock of the message queue. Thus a test can follow the key to the call
 * that releases the lock. The FFF call history gives the order of the calls.
 *
 * The scheduler is a model in the test:
 * - A waiting thread is a @c struct @c k_thread of the test with
 *   @c base.swap_data set. The fake z_unpend_first_thread_locked() returns
 *   it once, and then NULL.
 * - The fake z_pend_curr() records @c _current->base.swap_data and returns
 *   a result that the test selects. It does not switch threads.
 * - The fake z_sched_wake() returns true for the first @a n calls.
 *
 * Thus the tests specify the contract of msg_q.c with the scheduler, not the
 * scheduler. Some tests connect the two sides of a hand-over: the
 * @c swap_data that k_msgq_get() gives to z_pend_curr() is the buffer that
 * k_msgq_put() writes to.
 *
 * The scenarios in @c testcase.yaml build the tests once for each Kconfig
 * option above. A test that applies only to some configurations is in an
 * @c \#ifdef block, or it calls ztest_test_skip().
 *
 * @par Structure of the tests
 * Each public function of msg_q.c has one group below this group. A system
 * call has one group for z_impl_k_msgq_*() and z_vrfy_k_msgq_*(). The static
 * functions and the data of msg_q.c have the last group. Each test is in the
 * group of the function under test. The rules below (hand-over, locking,
 * assertions, system call verification, object core) apply to more than one
 * function. Their tests are in the group of the function that they call.
 *
 * @par Rules of the hand-over
 * A message goes directly to a waiting reader, and a waiting writer gets the
 * free slot.
 * Put: if the ring buffer is not full, put_msg_in_queue() asks the scheduler
 * for the first waiting thread with z_unpend_first_thread_locked(). A thread
 * waits on a message queue that is not full only if it is a reader. If there
 * is a reader, put_msg_in_queue() copies the message to the buffer of the
 * reader (@c swap_data of the thread), sets the return value of the reader
 * to 0 and makes it ready. The ring buffer and @c used_msgs do not change.
 *
 * Get: after k_msgq_get() removes the head message, it asks for the first
 * waiting thread. A thread waits on a message queue with messages only if it
 * is a writer. If there is a writer, k_msgq_get() copies the message of the
 * writer (@c swap_data) to @c write_ptr, moves @c write_ptr one slot forward
 * and increments @c used_msgs. Then it sets the return value of the writer to
 * 0 and makes it ready. Thus the message of the writer is the new tail.
 *
 * In both cases the copy comes before arch_thread_return_value_set(), and
 * this comes before z_sched_ready_locked(). One operation makes at most one
 * thread ready. The other side of the hand-over is the wait in
 * k_msgq_get() or k_msgq_put(), which sets @c swap_data (see
 * @ref kernel_unit_msgq_k_msgq_get and @ref kernel_unit_msgq_k_msgq_put).
 *
 * @par Locking
 * The spinlock of the message queue protects its state. Each path releases
 * it exactly once.
 * Each path of the operations, except the initialization,
 * k_msgq_get_attrs() and the static inline functions, locks the spinlock of
 * its message queue once, as its first call to the layers below. Only the
 * ISR check of an __ASSERT() (@kconfig{CONFIG_ASSERT}) comes before it. Each
 * path releases the lock once, as its last call, with the key of the lock.
 * The release is k_spin_unlock() (seen as arch_irq_unlock()),
 * z_reschedule() or z_pend_curr().
 *
 * The hand-over (z_unpend_first_thread_locked(), the copy,
 * arch_thread_return_value_set() and z_sched_ready_locked()) is in a block
 * @c LOCK_SCHED_SPINLOCK. With more than one CPU, this block locks and
 * unlocks the scheduler spinlock inside the lock of the message queue. The
 * block runs on each put to a message queue that is not full and on each get
 * of a message, also if no thread waits. The ring buffer and @c used_msgs
 * change only while the lock is held. k_free() in z_msgq_cleanup() runs
 * while the lock is held.
 *
 * @par Assertions
 * With CONFIG_ASSERT, msg_q.c asserts that an ISR does not wait and that the
 * write pointer is in the ring buffer.
 * k_msgq_put(), k_msgq_put_front() and k_msgq_get() assert, before the lock,
 * that the caller is not an ISR or that the timeout is K_NO_WAIT. Before a
 * put writes to @c write_ptr, and before a get can give the slot at
 * @c write_ptr to a writer, they assert that @c write_ptr is in the ring
 * buffer with space for one message. The initialization asserts are in
 * @ref kernel_unit_msgq_k_msgq_init. In the test, the assertion hook returns,
 * so the operation continues.
 *
 * @par System call verification
 * With CONFIG_USERSPACE, each verification function checks the message
 * queue object and the user buffer before it calls the implementation.
 * A system call from a user thread goes to z_vrfy_k_msgq_*(). This function
 * first checks that the pointer is a message queue object of the kernel that
 * the thread has access to. z_vrfy_k_msgq_alloc_init() uses
 * K_SYSCALL_OBJ_NEVER_INIT(): the object must not be initialized yet. The
 * other functions use K_SYSCALL_OBJ(): the object must be initialized.
 *
 * Then the functions with a user buffer check that the thread can access
 * it: K_SYSCALL_MEMORY_READ() of @c msg_size bytes for the message of
 * k_msgq_put() and k_msgq_put_front(); K_SYSCALL_MEMORY_WRITE() of
 * @c msg_size bytes for the buffer of k_msgq_get(), k_msgq_peek() and
 * k_msgq_peek_at(); K_SYSCALL_MEMORY_WRITE() of the attribute structure for
 * k_msgq_get_attrs(). The size comes from the message queue, so the object
 * check comes first. If a check fails, K_OOPS() stops the thread. Else the
 * function calls z_impl_k_msgq_*() with the same arguments and returns its
 * result.
 *
 * k_msgq_init() and k_msgq_cleanup() are not system calls.
 *
 * In the test, K_OOPS() calls the fake unit_syscall_oops(), and this fake
 * returns. The real K_OOPS() does not return. Thus the tests check that the
 * oops occurs before the implementation locks or changes the message queue.
 *
 * @par Object core
 * With CONFIG_OBJ_CORE_MSGQ, msg_q.c defines the object type of the message
 * queues and links each initialized message queue to it.
 * msg_q.c defines the object type @c obj_type_msgq. K_OBJ_TYPE_DEFINE() puts
 * one descriptor of this type into the iterable section @c k_obj_core_desc.
 * At boot, the object core code initializes the type from the descriptor and
 * links the message queues that K_MSGQ_DEFINE() defines (the section
 * @c k_msgq). k_msgq_init() links each message queue that it initializes,
 * with k_obj_core_init_and_link().
 */

/**
 * @defgroup kernel_unit_msgq_k_msgq_init k_msgq_init()
 * @ingroup kernel_unit_msgq
 * @brief k_msgq_init() makes an empty message queue on a buffer of the caller.
 *
 * k_msgq_init() sets the size of the messages, the number of slots and the
 * ring buffer. It sets the read and write pointers to the start of the ring
 * buffer, the number of messages to 0 and the flags to 0. It initializes the
 * lock, the wait queue, the poll events, the object core and the kernel
 * object. It does not lock the message queue: until k_msgq_init() returns,
 * only the caller uses it. It does not write to the ring buffer. With
 * @kconfig{CONFIG_ASSERT}, it asserts that the size of the ring buffer and
 * its end address do not overflow.
 *
 * @par Static definition
 * K_MSGQ_DEFINE() gives the state of k_msgq_init().
 * K_MSGQ_DEFINE() in @c zephyr/kernel.h defines the ring buffer and the
 * message queue in the iterable section @c k_msgq. Its initializer
 * Z_MSGQ_INITIALIZER() gives the same state as k_msgq_init(). The test of
 * K_MSGQ_DEFINE() is in this group.
 *
 * @par Functions in kernel/msg_q.c
 * - k_msgq_init(). It is not a system call.
 */

/**
 * @defgroup kernel_unit_msgq_k_msgq_alloc_init k_msgq_alloc_init()
 * @ingroup kernel_unit_msgq
 * @brief k_msgq_alloc_init() allocates the ring buffer, and k_msgq_cleanup() frees it.
 *
 * k_msgq_alloc_init() calculates the size of the ring buffer as
 * msg_size * max_msgs. If the multiplication overflows, it returns -EINVAL.
 * Else it allocates the buffer with z_thread_malloc() from the resource pool
 * of the current thread. If the allocation fails, it returns -ENOMEM and
 * does not change the message queue. Else it calls k_msgq_init() on the
 * buffer and then sets the flag K_MSGQ_FLAG_ALLOC. It does not lock the
 * message queue.
 *
 * k_msgq_cleanup() and z_msgq_cleanup() are in
 * @ref kernel_unit_msgq_k_msgq_cleanup.
 *
 * @par Functions in kernel/msg_q.c
 * - z_impl_k_msgq_alloc_init()
 * - z_vrfy_k_msgq_alloc_init(), with @kconfig{CONFIG_USERSPACE}
 */

/**
 * @defgroup kernel_unit_msgq_z_msgq_cleanup z_msgq_cleanup()
 * @ingroup kernel_unit_msgq
 * @brief z_msgq_cleanup() is the cleanup of k_msgq_cleanup(), with a parameter for the lock state
 * of the caller.
 *
 * k_msgq_cleanup() calls z_msgq_cleanup() with @c locked false. The test in
 * this group calls z_msgq_cleanup() with @c locked true. Some tests of
 * k_msgq_cleanup() also call z_msgq_cleanup() with @c locked true on a
 * second message queue. The design text of both functions is in
 * @ref kernel_unit_msgq_k_msgq_cleanup.
 *
 * @par Functions in kernel/msg_q.c
 * - z_msgq_cleanup(). It is not a system call. The object code of the kernel
 *   (@c kernel/userspace/userspace.c) calls it.
 */

/**
 * @defgroup kernel_unit_msgq_k_msgq_cleanup k_msgq_cleanup()
 * @ingroup kernel_unit_msgq
 * @brief k_msgq_cleanup() frees an allocated ring buffer if no thread waits.
 *
 * k_msgq_cleanup() calls z_msgq_cleanup() with @c locked false. The object
 * code of the kernel (@c kernel/userspace/userspace.c) calls
 * z_msgq_cleanup() when a message queue has no more references. Then
 * @c locked is true: the caller holds the scheduler spinlock. Thus
 * z_msgq_cleanup() reads the wait queue with z_waitq_head_locked(), which
 * does not lock the scheduler spinlock again. With @c locked false, it uses
 * z_waitq_head().
 *
 * z_msgq_cleanup() locks the message queue. If a thread waits, it returns
 * -EBUSY. This check is a CHECKIF(): with @kconfig{CONFIG_NO_RUNTIME_CHECKS}
 * there is no check, and with @kconfig{CONFIG_ASSERT_ON_ERRORS} it is an
 * assertion. If the flag K_MSGQ_FLAG_ALLOC is set, z_msgq_cleanup() frees
 * the buffer with k_free() and clears the flag. Thus a second call does not
 * free the buffer again. z_msgq_cleanup() does not change the other fields.
 *
 * @par Functions in kernel/msg_q.c
 * - k_msgq_cleanup(). It is not a system call.
 */

/**
 * @defgroup kernel_unit_msgq_k_msgq_put k_msgq_put()
 * @ingroup kernel_unit_msgq
 * @brief k_msgq_put() copies a message to the tail, and k_msgq_put_front() to the head.
 *
 * Both functions share the static function put_msg_in_queue(). If the ring
 * buffer is not full and no reader waits, k_msgq_put() copies @c msg_size
 * bytes to @c write_ptr and moves @c write_ptr one slot forward, with
 * wrap-around. k_msgq_put_front() moves @c read_ptr one slot back, with
 * wrap-around, and copies the message to the new @c read_ptr. Both
 * increment @c used_msgs and return 0. If a reader waits, see the rules of
 * the hand-over in @ref kernel_unit_msgq.
 *
 * If the ring buffer is full, k_msgq_put() returns -ENOMSG for the timeout
 * K_NO_WAIT. For another timeout it waits: it sets
 * @c _current->base.swap_data to the message and calls z_pend_curr(). The
 * result of z_pend_curr() is the return value. k_msgq_put_front() always
 * uses K_NO_WAIT, so it never waits.
 *
 * The poll events are in @ref kernel_unit_msgq_static.
 *
 * @par Functions in kernel/msg_q.c
 * - z_impl_k_msgq_put()
 * - z_vrfy_k_msgq_put(), static inline, with @kconfig{CONFIG_USERSPACE}
 */

/**
 * @defgroup kernel_unit_msgq_k_msgq_put_front k_msgq_put_front()
 * @ingroup kernel_unit_msgq
 * @brief k_msgq_put_front() copies a message to the head and never waits.
 *
 * k_msgq_put_front() shares the static function put_msg_in_queue() with
 * k_msgq_put(). The design text of both functions is in
 * @ref kernel_unit_msgq_k_msgq_put. The poll events are in
 * @ref kernel_unit_msgq_static.
 *
 * @par Functions in kernel/msg_q.c
 * - z_impl_k_msgq_put_front()
 * - z_vrfy_k_msgq_put_front(), static inline, with @kconfig{CONFIG_USERSPACE}
 */

/**
 * @defgroup kernel_unit_msgq_k_msgq_get_attrs k_msgq_get_attrs()
 * @ingroup kernel_unit_msgq
 * @brief k_msgq_get_attrs() reads the state of the message queue without the lock.
 *
 * k_msgq_get_attrs() (in msg_q.c), k_msgq_num_free_get() and
 * k_msgq_num_used_get() (static inline in @c zephyr/kernel.h) read the state
 * without the lock. Each reads @c used_msgs once, so the result is a value
 * that the message queue had during the call.
 *
 * @par Functions in kernel/msg_q.c
 * - z_impl_k_msgq_get_attrs()
 * - z_vrfy_k_msgq_get_attrs(), static inline, with @kconfig{CONFIG_USERSPACE}
 */

/**
 * @defgroup kernel_unit_msgq_k_msgq_get k_msgq_get()
 * @ingroup kernel_unit_msgq
 * @brief k_msgq_get() copies the head message to the caller and removes it.
 *
 * If the ring buffer has a message, k_msgq_get() copies @c msg_size bytes
 * from @c read_ptr to the caller, moves @c read_ptr one slot forward with
 * wrap-around, decrements @c used_msgs and returns 0. Then it gives the free
 * slot to a waiting writer, if there is one (see the rules of the hand-over
 * in @ref kernel_unit_msgq). If the ring buffer is empty, k_msgq_get()
 * returns -ENOMSG for the timeout K_NO_WAIT. For another timeout it waits:
 * it sets @c _current->base.swap_data to the buffer of the caller and calls
 * z_pend_curr(). The result of z_pend_curr() is the return value.
 *
 * @par Functions in kernel/msg_q.c
 * - z_impl_k_msgq_get()
 * - z_vrfy_k_msgq_get(), static inline, with @kconfig{CONFIG_USERSPACE}
 */

/**
 * @defgroup kernel_unit_msgq_k_msgq_peek k_msgq_peek()
 * @ingroup kernel_unit_msgq
 * @brief k_msgq_peek() and k_msgq_peek_at() copy a message and do not remove it.
 *
 * k_msgq_peek() copies the head message. k_msgq_peek_at() copies the message
 * at index @a idx from the head: index 0 is the head. If @a idx is not less
 * than @c used_msgs, k_msgq_peek_at() returns -ENOMSG. If the message is
 * after the end of the ring buffer, k_msgq_peek_at() calculates its address
 * from the start (wrap-around). Both functions never wait and do not change
 * the message queue.
 *
 * @par Functions in kernel/msg_q.c
 * - z_impl_k_msgq_peek()
 * - z_vrfy_k_msgq_peek(), static inline, with @kconfig{CONFIG_USERSPACE}
 */

/**
 * @defgroup kernel_unit_msgq_k_msgq_peek_at k_msgq_peek_at()
 * @ingroup kernel_unit_msgq
 * @brief k_msgq_peek_at() copies the message at an index from the head and does not remove it.
 *
 * The design text of k_msgq_peek() and k_msgq_peek_at() is in
 * @ref kernel_unit_msgq_k_msgq_peek.
 *
 * @par Functions in kernel/msg_q.c
 * - z_impl_k_msgq_peek_at()
 * - z_vrfy_k_msgq_peek_at(), static inline, with @kconfig{CONFIG_USERSPACE}
 */

/**
 * @defgroup kernel_unit_msgq_k_msgq_purge k_msgq_purge()
 * @ingroup kernel_unit_msgq
 * @brief k_msgq_purge() discards all messages and wakes all waiting threads with -ENOMSG.
 *
 * k_msgq_purge() wakes each thread of the wait queue with z_sched_wake(),
 * with the return value -ENOMSG and the data NULL, until z_sched_wake()
 * returns false. Then it sets @c used_msgs to 0 and @c read_ptr to
 * @c write_ptr. It does not write to the ring buffer. Readers and writers
 * share one wait queue, so k_msgq_purge() wakes the waiting writers of a
 * full message queue and the waiting readers of an empty message queue.
 *
 * @par Functions in kernel/msg_q.c
 * - z_impl_k_msgq_purge()
 * - z_vrfy_k_msgq_purge(), static inline, with @kconfig{CONFIG_USERSPACE}
 */

/**
 * @defgroup kernel_unit_msgq_k_msgq_num_free_get k_msgq_num_free_get()
 * @ingroup kernel_unit_msgq
 * @brief k_msgq_num_free_get() returns the number of free slots without the lock.
 *
 * z_impl_k_msgq_num_free_get() is static inline in @c zephyr/kernel.h. It
 * reads the state without the lock (see
 * @ref kernel_unit_msgq_k_msgq_get_attrs).
 *
 * @par Functions in kernel/msg_q.c
 * - z_vrfy_k_msgq_num_free_get(), static inline, with
 *   @kconfig{CONFIG_USERSPACE}. msg_q.c has no z_impl_k_msgq_num_free_get().
 */

/**
 * @defgroup kernel_unit_msgq_k_msgq_num_used_get k_msgq_num_used_get()
 * @ingroup kernel_unit_msgq
 * @brief k_msgq_num_used_get() returns the number of messages without the lock.
 *
 * z_impl_k_msgq_num_used_get() is static inline in @c zephyr/kernel.h. It
 * reads the state without the lock (see
 * @ref kernel_unit_msgq_k_msgq_get_attrs). The test of the two queries
 * k_msgq_num_used_get() and k_msgq_num_free_get() on a static message queue
 * is in this group.
 *
 * @par Functions in kernel/msg_q.c
 * - z_vrfy_k_msgq_num_used_get(), static inline, with
 *   @kconfig{CONFIG_USERSPACE}. msg_q.c has no z_impl_k_msgq_num_used_get().
 */

/**
 * @defgroup kernel_unit_msgq_static Static functions and data
 * @ingroup kernel_unit_msgq
 * @brief The static functions of msg_q.c, and the data that msg_q.c defines.
 *
 * @par Poll events
 * With CONFIG_POLL, a message in the ring buffer signals
 * K_POLL_STATE_MSGQ_DATA_AVAILABLE.
 * After put_msg_in_queue() writes a message into the ring buffer and
 * increments @c used_msgs, it calls z_handle_obj_poll_events() with the poll
 * events of the message queue and K_POLL_STATE_MSGQ_DATA_AVAILABLE. If this
 * makes a polling thread ready (return value true), put_msg_in_queue()
 * releases the lock with z_reschedule(). A message that goes directly to a
 * waiting reader does not signal the poll events. k_msgq_get(),
 * k_msgq_peek(), k_msgq_peek_at() and k_msgq_purge() do not signal the poll
 * events. Without @kconfig{CONFIG_POLL}, msgq_handle_poll_events() returns
 * false and calls nothing.
 *
 * Most tests of the poll events call k_msgq_put() or k_msgq_put_front().
 * They are in the groups of these functions.
 *
 * @par Functions in kernel/msg_q.c
 * - msgq_handle_poll_events(), static inline. With @kconfig{CONFIG_POLL}, it
 *   calls z_handle_obj_poll_events(). Without it, it returns false.
 * - put_msg_in_queue(), static inline. k_msgq_put() and k_msgq_put_front()
 *   call it. Its tests are in the groups of these two functions.
 *
 * @par Data in kernel/msg_q.c
 * - @c obj_type_msgq and its descriptor (K_OBJ_TYPE_DEFINE()), with
 *   @kconfig{CONFIG_OBJ_CORE_MSGQ}. The tests of the descriptor are in this
 *   group.
 */

#include <limits.h>
#include <string.h>
#include <zephyr/ztest.h>
#include <kernel_unit.h>
#include <kernel_unit_models.h>
#include <fakes/mempool.h>
#ifdef CONFIG_OBJ_CORE
#include <fakes/obj_core.h>
#endif
#ifdef CONFIG_USERSPACE
#include <fakes/kobject.h>
#endif
#ifdef CONFIG_ASSERT
#include <fakes/assert.h>
#endif

#include <kernel/msg_q.c>

/* A message of the test: two words, the second is the complement of the first. */
struct msg {
	uint32_t id;
	uint32_t check;
};

#define MSG_SIZE sizeof(struct msg)
#define MAX_MSGS 4U

/* Value that fills a buffer before a test, to show what the unit writes. */
#define FILL KERNEL_UNIT_FILL

/* Timeout that is not K_NO_WAIT and not K_FOREVER */
#define TEST_TIMEOUT K_TICKS(10)

/* Interrupt lock key of a nested lock (the scheduler spinlock) */
#define NESTED_IRQ_KEY 0x0E57EDU

/*
 * With more than one CPU, LOCK_SCHED_SPINLOCK locks the scheduler spinlock.
 * SCHED_LOCK_CALL(fn) is an entry of an expected call history that exists
 * only in this case.
 */
#if CONFIG_MP_MAX_NUM_CPUS > 1
#define SCHED_LOCK         1
#define SCHED_LOCK_ENABLED true
#else
#define SCHED_LOCK_ENABLED false
#endif
#define SCHED_LOCK_CALL(fn) KERNEL_UNIT_IF_ENABLED(SCHED_LOCK, fn)

/* The ISR check of the __ASSERT() in k_msgq_put() and k_msgq_get() */
#define ISR_CHECK_CALL KERNEL_UNIT_IF_ENABLED(CONFIG_ASSERT, arch_is_in_isr)

/* The poll signal (CONFIG_POLL) */
#define POLL_CALL KERNEL_UNIT_IF_ENABLED(CONFIG_POLL, z_handle_obj_poll_events)

/* The ring buffer of the test: MAX_MSGS slots and one guard slot after the end. */
static char ring[(MAX_MSGS + 1U) * MSG_SIZE] __aligned(4);

#define RING_END  (&ring[MAX_MSGS * MSG_SIZE])
#define SLOT(n)   (&ring[(n) * MSG_SIZE])
#define GUARD_MSG ((const struct msg *)RING_END)

/* The current thread of the test, and a second thread that waits on the queue. */
static struct k_thread current_thread;
static struct k_thread other_thread;

/* The buffer of a waiting reader */
static struct msg reader_buf;

/* The message of a waiting writer */
static struct msg writer_msg;

static struct msg make_msg(uint32_t id)
{
	return (struct msg){.id = id, .check = ~id};
}

/* Assert that the message at @p p is message @p id. */
#define zassert_msg(p, id_)                                                                        \
	do {                                                                                       \
		const struct msg *m_ = (const struct msg *)(p);                                    \
		zassert_equal(m_->id, (id_), "message %u, not %u", m_->id, (id_));                 \
		zassert_equal(m_->check, ~(uint32_t)(id_), "message %u is not complete", (id_));   \
	} while (false)

/*
 * Lock model. The fake unit_arch_irq_lock() returns KERNEL_UNIT_IRQ_KEY for
 * the outer lock (the lock of the message queue) and NESTED_IRQ_KEY for a
 * lock inside it (the scheduler spinlock). The spy fakes record the lock
 * depth at their call.
 */
static unsigned int lock_depth;
static unsigned int outer_locks;
static unsigned int outer_unlocks;
static unsigned int nested_unlocks;
static unsigned int depth_at_unpend;
static unsigned int depth_at_ready;
static unsigned int depth_at_poll;
static unsigned int depth_at_free;

/* The message queue that the spy fakes read */
static struct k_msgq *spied_msgq;
static uint32_t used_at_lock;
static uint32_t used_at_release;
static uint32_t used_at_ready;
static uint32_t used_at_poll;
static struct msg data_at_ready;
static bool poll_result;

/* The waiting thread that z_unpend_first_thread_locked() returns once */
static struct k_thread *waiting_thread;

/* Wait model of z_pend_curr() */
static int pend_result;
static void *swap_data_at_pend;

/* Return the number of messages of the spied message queue. */
static uint32_t spied_used(void)
{
	return (spied_msgq != NULL) ? spied_msgq->used_msgs : 0U;
}

static unsigned int lock_model(void)
{
	lock_depth++;
	if (lock_depth == 1U) {
		outer_locks++;
		used_at_lock = spied_used();
		return KERNEL_UNIT_IRQ_KEY;
	}

	return NESTED_IRQ_KEY;
}

static void unlock_model(unsigned int key)
{
	if (key == KERNEL_UNIT_IRQ_KEY) {
		outer_unlocks++;
		used_at_release = spied_used();
	} else {
		nested_unlocks++;
	}
	if (lock_depth > 0U) {
		lock_depth--;
	}
}

static struct k_thread *unpend_model(_wait_q_t *wait_q)
{
	struct k_thread *thread = waiting_thread;

	ARG_UNUSED(wait_q);

	depth_at_unpend = lock_depth;
	waiting_thread = NULL;

	return thread;
}

static void ready_spy(struct k_thread *thread)
{
	depth_at_ready = lock_depth;
	used_at_ready = spied_used();
	memcpy(&data_at_ready, thread->base.swap_data, sizeof(data_at_ready));
}

static __maybe_unused bool poll_spy(sys_dlist_t *events, uint32_t state)
{
	ARG_UNUSED(events);
	ARG_UNUSED(state);

	depth_at_poll = lock_depth;
	used_at_poll = spied_used();

	return poll_result;
}

static void free_spy(void *ptr)
{
	ARG_UNUSED(ptr);

	depth_at_free = lock_depth;
}

static int pend_model(struct k_spinlock *lock, k_spinlock_key_t key, _wait_q_t *wait_q,
		      k_timeout_t timeout)
{
	ARG_UNUSED(lock);
	ARG_UNUSED(key);
	ARG_UNUSED(wait_q);
	ARG_UNUSED(timeout);

	swap_data_at_pend = _current->base.swap_data;
	used_at_release = spied_used();

	return pend_result;
}

static void reschedule_spy(struct k_spinlock *lock, k_spinlock_key_t key)
{
	ARG_UNUSED(lock);
	ARG_UNUSED(key);

	used_at_release = spied_used();
}

/* Install the models in the fakes. */
static void install_models(void)
{
	unit_arch_irq_lock_fake.custom_fake = lock_model;
	unit_arch_irq_unlock_fake.custom_fake = unlock_model;
	z_unpend_first_thread_locked_fake.custom_fake = unpend_model;
	z_sched_ready_locked_fake.custom_fake = ready_spy;
	z_pend_curr_fake.custom_fake = pend_model;
	z_reschedule_fake.custom_fake = reschedule_spy;
	z_sched_wake_fake.custom_fake = kernel_unit_wake_waiting_thread;
	k_free_fake.custom_fake = free_spy;
#ifdef CONFIG_POLL
	z_handle_obj_poll_events_fake.custom_fake = poll_spy;
#endif
	lock_depth = 0;
	outer_locks = 0;
	outer_unlocks = 0;
	nested_unlocks = 0;
	depth_at_unpend = UINT_MAX;
	depth_at_ready = UINT_MAX;
	depth_at_poll = UINT_MAX;
	depth_at_free = UINT_MAX;
	used_at_lock = UINT32_MAX;
	used_at_release = UINT32_MAX;
	used_at_ready = UINT32_MAX;
	used_at_poll = UINT32_MAX;
	swap_data_at_pend = NULL;
}

/* Forget the calls of the test setup. The state of the models stays. */
static void reset_history(void)
{
	FFF_RESET_HISTORY();
	RESET_FAKE(unit_arch_irq_lock);
	RESET_FAKE(unit_arch_irq_unlock);
	RESET_FAKE(arch_is_in_isr);
	RESET_FAKE(arch_thread_return_value_set);
	RESET_FAKE(z_unpend_first_thread_locked);
	RESET_FAKE(z_sched_ready_locked);
	RESET_FAKE(z_reschedule);
	RESET_FAKE(z_pend_curr);
	RESET_FAKE(z_sched_wake);
	RESET_FAKE(z_waitq_init);
	RESET_FAKE(z_waitq_head);
	RESET_FAKE(z_waitq_head_locked);
	RESET_FAKE(z_thread_malloc);
	RESET_FAKE(k_free);
	RESET_FAKE(z_handle_obj_poll_events);
	install_models();
}

/* Let a reader wait: its k_msgq_get() waits with the buffer reader_buf. */
static void set_waiting_reader(void)
{
	memset(&reader_buf, FILL, sizeof(reader_buf));
	other_thread.base.swap_data = &reader_buf;
	waiting_thread = &other_thread;
}

/* Let a writer wait: its k_msgq_put() waits with the message writer_msg (id). */
static void set_waiting_writer(uint32_t id)
{
	writer_msg = make_msg(id);
	other_thread.base.swap_data = &writer_msg;
	waiting_thread = &other_thread;
}

/* Let the operation wait, and give it this result after the wait. */
static void set_wait_result(int result)
{
	pend_result = result;
}

/*
 * Put a message queue into the state of K_MSGQ_DEFINE() on the ring buffer
 * of the test, without k_msgq_init(). Fill the ring buffer with FILL.
 */
static void msgq_prepare(struct k_msgq *msgq)
{
	memset(ring, FILL, sizeof(ring));
	*msgq = (struct k_msgq)Z_MSGQ_INITIALIZER((*msgq), ring, MSG_SIZE, MAX_MSGS);
	spied_msgq = msgq;
}

/* Put the messages first .. first + n - 1 at the tail, then forget the calls. */
static void put_msgs(struct k_msgq *msgq, uint32_t first, uint32_t n)
{
	for (uint32_t i = 0; i < n; i++) {
		struct msg m = make_msg(first + i);

		zassert_equal(z_impl_k_msgq_put(msgq, &m, K_NO_WAIT), 0);
	}
	reset_history();
}

/* Move the read and write pointers to slot n of an empty message queue. */
static void msgq_start_at(struct k_msgq *msgq, uint32_t n)
{
	zassert_equal(msgq->used_msgs, 0U);
	msgq->read_ptr = SLOT(n);
	msgq->write_ptr = SLOT(n);
}

/*
 * Assert that the ring buffer has exactly these messages, from the head to
 * the tail, and that the write pointer is after the last one. The reader
 * does not use the functions of the unit.
 */
static void assert_contents(struct k_msgq *msgq, const uint32_t *ids, size_t n)
{
	char *p = msgq->read_ptr;

	zassert_equal(msgq->used_msgs, n, "the queue has %u messages, not %zu", msgq->used_msgs, n);
	for (size_t i = 0; i < n; i++) {
		zassert_msg(p, ids[i]);
		p += MSG_SIZE;
		if (p == msgq->buffer_end) {
			p = msgq->buffer_start;
		}
	}
	zassert_equal_ptr(msgq->write_ptr, p, "the write pointer is not after the tail");
	/* No operation writes the guard slot after the ring buffer. */
	kernel_unit_assert_filled(RING_END, MSG_SIZE);
}

#define zassert_msgq_contents(msgq, ...)                                                           \
	do {                                                                                       \
		const uint32_t expected_[] = {__VA_ARGS__};                                        \
		assert_contents(msgq, expected_, ARRAY_SIZE(expected_));                           \
	} while (false)

#define zassert_msgq_empty(msgq) assert_contents(msgq, NULL, 0)

/*
 * Assert the lock invariant of one operation on msgq:
 * - The lock of the message queue is the first call. Only the ISR check of
 *   an __ASSERT() (CONFIG_ASSERT) can come before it.
 * - With more than one CPU, the operation locks and unlocks the scheduler
 *   spinlock sched_sections times, inside the lock of the message queue.
 *   With one CPU, it does not lock it.
 * - The operation releases the lock of the message queue once, in the given
 *   way, with the key of the lock, as the last call.
 */
static void assert_lock_released_once(struct k_msgq *msgq, enum kernel_unit_release how,
				      unsigned int sched_sections)
{
	unsigned int nested = SCHED_LOCK_ENABLED ? sched_sections : 0U;
	unsigned int releases =
		outer_unlocks + z_reschedule_fake.call_count + z_pend_curr_fake.call_count;
	fff_function_t release;

	zassert_equal(outer_locks, 1, "the queue locked %u times", outer_locks);
	zassert_equal(unit_arch_irq_lock_fake.call_count, 1U + nested, "%u locks, not %u",
		      unit_arch_irq_lock_fake.call_count, 1U + nested);
	zassert_equal(nested_unlocks, nested, "%u nested unlocks, not %u", nested_unlocks, nested);
	zassert_equal(releases, 1, "the queue released %u times", releases);
	zassert_equal(kernel_unit_history_index(KERNEL_UNIT_FN(unit_arch_irq_lock), 0),
		      (int)arch_is_in_isr_fake.call_count, "the lock is not the first call");

	switch (how) {
	case KERNEL_UNIT_RELEASED_BY_UNLOCK:
		zassert_equal(outer_unlocks, 1);
		release = KERNEL_UNIT_FN(unit_arch_irq_unlock);
		break;
	case KERNEL_UNIT_RELEASED_BY_RESCHEDULE:
		zassert_equal(z_reschedule_fake.call_count, 1);
		zassert_equal_ptr(z_reschedule_fake.arg0_val, &msgq->lock);
		zassert_equal((unsigned int)z_reschedule_fake.arg1_val.key, KERNEL_UNIT_IRQ_KEY);
		release = KERNEL_UNIT_FN(z_reschedule);
		break;
	case KERNEL_UNIT_RELEASED_BY_PEND:
	default:
		zassert_equal(z_pend_curr_fake.call_count, 1);
		zassert_equal_ptr(z_pend_curr_fake.arg0_val, &msgq->lock);
		zassert_equal((unsigned int)z_pend_curr_fake.arg1_val.key, KERNEL_UNIT_IRQ_KEY);
		release = KERNEL_UNIT_FN(z_pend_curr);
		break;
	}

	zassert_equal(kernel_unit_history_index(release,
						how == KERNEL_UNIT_RELEASED_BY_UNLOCK ? nested : 0),
		      (int)kernel_unit_history_len() - 1,
		      "the release of the lock is not the last call");
}

/* Heap model: z_thread_malloc() gives the ring buffer of the test. */
static void *malloc_ring(size_t size)
{
	ARG_UNUSED(size);

	return ring;
}

static void msgq_unit_before(void *fixture)
{
	ARG_UNUSED(fixture);

	/* The fake rules reset all fakes and _kernel before this function. */
	install_models();
	memset(ring, FILL, sizeof(ring));
	memset(&current_thread, 0, sizeof(current_thread));
	memset(&other_thread, 0, sizeof(other_thread));
	memset(&reader_buf, FILL, sizeof(reader_buf));
	writer_msg = make_msg(0);
	_kernel.cpus[0].current = &current_thread;
	spied_msgq = NULL;
	waiting_thread = NULL;
	kernel_unit_waiting_threads = 0;
	pend_result = 0;
	poll_result = false;
}

ZTEST_SUITE(msgq_unit, NULL, NULL, msgq_unit_before, NULL, NULL);

/*
 * Tests: Initialization. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_msgq, at the top of this file.
 */

/**
 * @brief k_msgq_init() sets the message size, the number of slots and the limits of the ring
 * buffer.
 *
 * @details
 * - Setup: a message queue filled with a pattern.
 * - Action: k_msgq_init() with the ring buffer, MSG_SIZE and MAX_MSGS.
 * - Expected: @c msg_size is MSG_SIZE, @c max_msgs is MAX_MSGS,
 *   @c buffer_start is the buffer, and @c buffer_end is MAX_MSGS * MSG_SIZE
 *   bytes after it.
 *
 * @ingroup kernel_unit_msgq_k_msgq_init
 * @see k_msgq_init()
 */
ZTEST(msgq_unit, test_init_sets_geometry)
{
	struct k_msgq msgq;

	memset(&msgq, FILL, sizeof(msgq));

	k_msgq_init(&msgq, ring, MSG_SIZE, MAX_MSGS);

	zassert_equal(msgq.msg_size, MSG_SIZE);
	zassert_equal(msgq.max_msgs, MAX_MSGS);
	zassert_equal_ptr(msgq.buffer_start, ring);
	zassert_equal_ptr(msgq.buffer_end, RING_END);
}

/**
 * @brief k_msgq_init() makes the message queue empty.
 *
 * @details
 * - Setup: a message queue filled with a pattern.
 * - Action: k_msgq_init().
 * - Expected: @c read_ptr and @c write_ptr are the start of the buffer.
 *   @c used_msgs is 0. k_msgq_num_used_get() returns 0 and
 *   k_msgq_num_free_get() returns MAX_MSGS.
 *
 * @ingroup kernel_unit_msgq_k_msgq_init
 * @see k_msgq_init()
 */
ZTEST(msgq_unit, test_init_makes_queue_empty)
{
	struct k_msgq msgq;

	memset(&msgq, FILL, sizeof(msgq));

	k_msgq_init(&msgq, ring, MSG_SIZE, MAX_MSGS);

	zassert_equal_ptr(msgq.read_ptr, ring);
	zassert_equal_ptr(msgq.write_ptr, ring);
	zassert_equal(msgq.used_msgs, 0U);
	zassert_equal(z_impl_k_msgq_num_used_get(&msgq), 0U);
	zassert_equal(z_impl_k_msgq_num_free_get(&msgq), MAX_MSGS);
}

/**
 * @brief k_msgq_init() sets the flags to 0: the caller owns the buffer.
 *
 * @details
 * - Setup: a message queue filled with a pattern, so the flag
 *   K_MSGQ_FLAG_ALLOC is set.
 * - Action: k_msgq_init().
 * - Expected: @c flags is 0.
 *
 * @ingroup kernel_unit_msgq_k_msgq_init
 * @see k_msgq_init()
 */
ZTEST(msgq_unit, test_init_clears_flags)
{
	struct k_msgq msgq;

	memset(&msgq, FILL, sizeof(msgq));
	zassert_not_equal(msgq.flags & K_MSGQ_FLAG_ALLOC, 0U);

	k_msgq_init(&msgq, ring, MSG_SIZE, MAX_MSGS);

	zassert_equal(msgq.flags, 0U);
}

/**
 * @brief k_msgq_init() sets the lock of the message queue to its initial value.
 *
 * @details
 * - Setup: a message queue filled with a pattern.
 * - Action: k_msgq_init().
 * - Expected: all bytes of the lock are 0 (the value of an unlocked
 *   spinlock).
 *
 * @ingroup kernel_unit_msgq_k_msgq_init
 * @see k_msgq_init()
 */
ZTEST(msgq_unit, test_init_resets_lock)
{
	struct k_msgq msgq;
	const struct k_spinlock unlocked = {};

	memset(&msgq, FILL, sizeof(msgq));

	k_msgq_init(&msgq, ring, MSG_SIZE, MAX_MSGS);

	zassert_mem_equal(&msgq.lock, &unlocked, sizeof(unlocked));
}

/**
 * @brief k_msgq_init() initializes the wait queue of the message queue.
 *
 * @details
 * - Action: k_msgq_init().
 * - Expected: one call of z_waitq_init() with the wait queue of the message
 *   queue.
 *
 * @ingroup kernel_unit_msgq_k_msgq_init
 * @see k_msgq_init()
 */
ZTEST(msgq_unit, test_init_initializes_wait_queue)
{
	struct k_msgq msgq;

	k_msgq_init(&msgq, ring, MSG_SIZE, MAX_MSGS);

	zassert_equal(z_waitq_init_fake.call_count, 1);
	zassert_equal_ptr(z_waitq_init_fake.arg0_val, &msgq.wait_q);
}

/**
 * @brief k_msgq_init() does not write to the ring buffer.
 *
 * @details
 * - Setup: the ring buffer is filled with a pattern.
 * - Action: k_msgq_init().
 * - Expected: all bytes of the ring buffer keep the pattern.
 *
 * @ingroup kernel_unit_msgq_k_msgq_init
 * @see k_msgq_init()
 */
ZTEST(msgq_unit, test_init_does_not_write_buffer)
{
	struct k_msgq msgq;

	memset(ring, FILL, sizeof(ring));

	k_msgq_init(&msgq, ring, MSG_SIZE, MAX_MSGS);

	kernel_unit_assert_filled(ring, sizeof(ring));
}

#ifdef CONFIG_POLL
/**
 * @brief With CONFIG_POLL, k_msgq_init() makes the list of poll events empty.
 *
 * @details
 * - Setup: a message queue filled with a pattern.
 * - Action: k_msgq_init().
 * - Expected: the list @c poll_events is a valid, empty list.
 *
 * @ingroup kernel_unit_msgq_k_msgq_init
 * @see k_msgq_init()
 */
ZTEST(msgq_unit, test_init_empties_poll_events)
{
	struct k_msgq msgq;

	memset(&msgq, FILL, sizeof(msgq));

	k_msgq_init(&msgq, ring, MSG_SIZE, MAX_MSGS);

	zassert_true(sys_dlist_is_empty(&msgq.poll_events));
}
#endif /* CONFIG_POLL */

#ifdef CONFIG_USERSPACE
/**
 * @brief With CONFIG_USERSPACE, k_msgq_init() marks the message queue as an initialized kernel
 * object.
 *
 * @details
 * - Action: k_msgq_init().
 * - Expected: one call of k_object_init() with the message queue.
 *
 * @ingroup kernel_unit_msgq_k_msgq_init
 * @see k_msgq_init()
 */
ZTEST(msgq_unit, test_init_initializes_kernel_object)
{
	struct k_msgq msgq;

	k_msgq_init(&msgq, ring, MSG_SIZE, MAX_MSGS);

	zassert_equal(k_object_init_fake.call_count, 1);
	zassert_equal_ptr(k_object_init_fake.arg0_val, &msgq);
}
#endif /* CONFIG_USERSPACE */

/**
 * @brief k_msgq_init() initializes the wait queue, then the object core, then the kernel object,
 * and calls nothing else.
 *
 * @details
 * - Action: k_msgq_init().
 * - Expected calls, in this order: z_waitq_init(), k_obj_core_init_and_link()
 *   (with CONFIG_OBJ_CORE_MSGQ), k_object_init() (with CONFIG_USERSPACE). No
 *   lock, no allocation.
 *
 * @ingroup kernel_unit_msgq_k_msgq_init
 * @see k_msgq_init()
 */
ZTEST(msgq_unit, test_init_call_order)
{
	struct k_msgq msgq;

	k_msgq_init(&msgq, ring, MSG_SIZE, MAX_MSGS);

	zassert_call_history(z_waitq_init,
			     KERNEL_UNIT_IF_ENABLED(CONFIG_OBJ_CORE_MSGQ, k_obj_core_init_and_link),
			     KERNEL_UNIT_IF_ENABLED(CONFIG_USERSPACE, k_object_init));
}

#ifdef CONFIG_ASSERT
/**
 * @brief With CONFIG_ASSERT, k_msgq_init() asserts that max_msgs * msg_size does not overflow.
 *
 * @details
 * - Action: k_msgq_init() with msg_size SIZE_MAX / 2 + 1 and max_msgs 2.
 * - Expected: one failed assertion. The fake assertion hook returns, so
 *   k_msgq_init() continues. It does not write to the buffer.
 *
 * @ingroup kernel_unit_msgq_k_msgq_init
 * @see k_msgq_init()
 */
ZTEST(msgq_unit, test_init_asserts_size_overflow)
{
	struct k_msgq msgq;

	k_msgq_init(&msgq, ring, (SIZE_MAX / 2U) + 1U, 2U);

	zassert_equal(assert_post_action_fake.call_count, 1);
	zassert_called_before(assert_post_action, z_waitq_init);
}

/**
 * @brief With CONFIG_ASSERT, k_msgq_init() asserts that the end address of the ring buffer does
 * not overflow.
 *
 * @details
 * - Action: k_msgq_init() with a buffer address MSG_SIZE bytes before the
 *   end of the address space, and MAX_MSGS slots. The buffer is not used.
 * - Expected: one failed assertion. The size check passes.
 *
 * @ingroup kernel_unit_msgq_k_msgq_init
 * @see k_msgq_init()
 */
ZTEST(msgq_unit, test_init_asserts_end_address_overflow)
{
	struct k_msgq msgq;
	char *buffer = (char *)(UINTPTR_MAX - MSG_SIZE + 1U);

	k_msgq_init(&msgq, buffer, MSG_SIZE, MAX_MSGS);

	zassert_equal(assert_post_action_fake.call_count, 1);
}

/**
 * @brief With CONFIG_ASSERT, k_msgq_init() does not assert for a valid buffer.
 *
 * @details
 * - Action: k_msgq_init() with the ring buffer of the test, then with
 *   max_msgs 0.
 * - Expected: no failed assertion. A message queue with no slots is valid
 *   for k_msgq_init().
 *
 * @ingroup kernel_unit_msgq_k_msgq_init
 * @see k_msgq_init()
 */
ZTEST(msgq_unit, test_init_valid_buffer_does_not_assert)
{
	struct k_msgq msgq;

	k_msgq_init(&msgq, ring, MSG_SIZE, MAX_MSGS);
	k_msgq_init(&msgq, ring, MSG_SIZE, 0U);

	zassert_equal(assert_post_action_fake.call_count, 0);
}
#endif /* CONFIG_ASSERT */

/*
 * Tests: Static definition and state queries. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_msgq, at the top of this file.
 */

K_MSGQ_DEFINE(unit_static_msgq, MSG_SIZE, MAX_MSGS, 4);

/**
 * @brief K_MSGQ_DEFINE() gives a message queue with the same state as k_msgq_init().
 *
 * @details
 * - Setup: K_MSGQ_DEFINE() of a message queue with MSG_SIZE and MAX_MSGS.
 * - Action: k_msgq_init() of a second message queue on the same buffer.
 * - Expected: the message size, the number of slots, the buffer limits, the
 *   read and write pointers, the number of messages and the flags are
 *   equal. The buffer has MAX_MSGS * MSG_SIZE bytes. The message queue is in
 *   the iterable section @c k_msgq.
 *
 * @ingroup kernel_unit_msgq_k_msgq_init
 * @see K_MSGQ_DEFINE(), k_msgq_init()
 */
ZTEST(msgq_unit, test_static_define_equals_init)
{
	struct k_msgq msgq;
	bool in_section = false;

	k_msgq_init(&msgq, unit_static_msgq.buffer_start, MSG_SIZE, MAX_MSGS);

	zassert_equal(unit_static_msgq.msg_size, msgq.msg_size);
	zassert_equal(unit_static_msgq.max_msgs, msgq.max_msgs);
	zassert_equal_ptr(unit_static_msgq.buffer_end, msgq.buffer_end);
	zassert_equal_ptr(unit_static_msgq.read_ptr, msgq.read_ptr);
	zassert_equal_ptr(unit_static_msgq.write_ptr, msgq.write_ptr);
	zassert_equal(unit_static_msgq.used_msgs, msgq.used_msgs);
	zassert_equal(unit_static_msgq.flags, msgq.flags);
	zassert_equal(sizeof(_k_fifo_buf_unit_static_msgq), MAX_MSGS * MSG_SIZE);

	STRUCT_SECTION_FOREACH(k_msgq, q) {
		if (q == &unit_static_msgq) {
			in_section = true;
		}
	}
	zassert_true(in_section);
}

/**
 * @brief k_msgq_num_used_get() returns the number of messages, and k_msgq_num_free_get() returns
 * the number of free slots. Neither locks the message queue.
 *
 * @details
 * - Setup: a message queue with 3 messages.
 * - Action: k_msgq_num_used_get(), k_msgq_num_free_get().
 * - Expected: 3 and MAX_MSGS - 3. No calls to the layers below.
 *
 * @ingroup kernel_unit_msgq_k_msgq_num_used_get
 * @see z_impl_k_msgq_num_used_get(), z_impl_k_msgq_num_free_get()
 */
ZTEST(msgq_unit, test_static_num_used_and_free)
{
	struct k_msgq msgq;

	msgq_prepare(&msgq);
	put_msgs(&msgq, 1, 3);

	zassert_equal(z_impl_k_msgq_num_used_get(&msgq), 3U);
	zassert_equal(z_impl_k_msgq_num_free_get(&msgq), MAX_MSGS - 3U);
	zassert_equal(kernel_unit_history_len(), 0);
}

/**
 * @brief k_msgq_get_attrs() copies the message size, the number of slots and the number of
 * messages, and does not lock the message queue.
 *
 * @details
 * - Setup: a message queue with 3 messages. An attribute structure filled
 *   with a pattern.
 * - Action: k_msgq_get_attrs().
 * - Expected: @c msg_size is MSG_SIZE, @c max_msgs is MAX_MSGS, @c used_msgs
 *   is 3. No calls to the layers below. The message queue does not change.
 *
 * @ingroup kernel_unit_msgq_k_msgq_get_attrs
 * @see z_impl_k_msgq_get_attrs()
 */
ZTEST(msgq_unit, test_static_get_attrs)
{
	struct k_msgq msgq;
	struct k_msgq_attrs attrs;

	msgq_prepare(&msgq);
	put_msgs(&msgq, 1, 3);
	memset(&attrs, FILL, sizeof(attrs));

	z_impl_k_msgq_get_attrs(&msgq, &attrs);

	zassert_equal(attrs.msg_size, MSG_SIZE);
	zassert_equal(attrs.max_msgs, MAX_MSGS);
	zassert_equal(attrs.used_msgs, 3U);
	zassert_equal(kernel_unit_history_len(), 0);
	zassert_msgq_contents(&msgq, 1, 2, 3);
}

/*
 * Tests: Allocated ring buffer. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_msgq, at the top of this file.
 */

/**
 * @brief k_msgq_alloc_init() allocates msg_size * max_msgs bytes and initializes the message queue
 * on this buffer.
 *
 * @details
 * - Setup: z_thread_malloc() gives the ring buffer of the test.
 * - Action: k_msgq_alloc_init() with MSG_SIZE and MAX_MSGS.
 * - Expected: return value 0. One call of z_thread_malloc() with
 *   MSG_SIZE * MAX_MSGS. The message queue is empty, with the allocated
 *   buffer, MSG_SIZE and MAX_MSGS.
 *
 * @ingroup kernel_unit_msgq_k_msgq_alloc_init
 * @see z_impl_k_msgq_alloc_init()
 */
ZTEST(msgq_unit, test_alloc_init_allocates_buffer)
{
	struct k_msgq msgq;

	memset(&msgq, FILL, sizeof(msgq));
	z_thread_malloc_fake.custom_fake = malloc_ring;

	zassert_equal(z_impl_k_msgq_alloc_init(&msgq, MSG_SIZE, MAX_MSGS), 0);

	zassert_equal(z_thread_malloc_fake.call_count, 1);
	zassert_equal(z_thread_malloc_fake.arg0_val, MSG_SIZE * MAX_MSGS);
	zassert_equal_ptr(msgq.buffer_start, ring);
	zassert_equal_ptr(msgq.buffer_end, RING_END);
	zassert_equal(msgq.msg_size, MSG_SIZE);
	zassert_equal(msgq.max_msgs, MAX_MSGS);
	zassert_msgq_empty(&msgq);
}

/**
 * @brief k_msgq_alloc_init() sets the flag K_MSGQ_FLAG_ALLOC after the initialization.
 *
 * @details
 * - Setup: z_thread_malloc() gives the ring buffer of the test.
 * - Action: k_msgq_alloc_init().
 * - Expected: @c flags is K_MSGQ_FLAG_ALLOC. The calls are
 *   z_thread_malloc(), then the calls of k_msgq_init() (z_waitq_init() and,
 *   with the options, k_obj_core_init_and_link() and k_object_init()). No
 *   lock.
 *
 * @ingroup kernel_unit_msgq_k_msgq_alloc_init
 * @see z_impl_k_msgq_alloc_init()
 */
ZTEST(msgq_unit, test_alloc_init_sets_alloc_flag)
{
	struct k_msgq msgq;

	z_thread_malloc_fake.custom_fake = malloc_ring;

	zassert_equal(z_impl_k_msgq_alloc_init(&msgq, MSG_SIZE, MAX_MSGS), 0);

	zassert_equal(msgq.flags, K_MSGQ_FLAG_ALLOC);
	zassert_call_history(z_thread_malloc, z_waitq_init,
			     KERNEL_UNIT_IF_ENABLED(CONFIG_OBJ_CORE_MSGQ, k_obj_core_init_and_link),
			     KERNEL_UNIT_IF_ENABLED(CONFIG_USERSPACE, k_object_init));
}

/**
 * @brief If msg_size * max_msgs overflows, k_msgq_alloc_init() returns -EINVAL, does not allocate
 * and does not change the message queue.
 *
 * @details
 * - Setup: a message queue filled with a pattern.
 * - Action: k_msgq_alloc_init() with msg_size SIZE_MAX / 2 + 1 and
 *   max_msgs 2.
 * - Expected: return value -EINVAL. No calls to the layers below. All bytes
 *   of the message queue keep the pattern.
 *
 * @ingroup kernel_unit_msgq_k_msgq_alloc_init
 * @see z_impl_k_msgq_alloc_init()
 */
ZTEST(msgq_unit, test_alloc_init_overflow_returns_einval)
{
	struct k_msgq msgq;

	memset(&msgq, FILL, sizeof(msgq));

	zassert_equal(z_impl_k_msgq_alloc_init(&msgq, (SIZE_MAX / 2U) + 1U, 2U), -EINVAL);

	zassert_equal(kernel_unit_history_len(), 0);
	kernel_unit_assert_filled(&msgq, sizeof(msgq));
}

/**
 * @brief If z_thread_malloc() fails, k_msgq_alloc_init() returns -ENOMEM and does not change the
 * message queue.
 *
 * @details
 * - Setup: a message queue filled with a pattern. z_thread_malloc() returns
 *   NULL.
 * - Action: k_msgq_alloc_init().
 * - Expected: return value -ENOMEM. One call of z_thread_malloc() and no
 *   other call. All bytes of the message queue keep the pattern.
 *
 * @ingroup kernel_unit_msgq_k_msgq_alloc_init
 * @see z_impl_k_msgq_alloc_init()
 */
ZTEST(msgq_unit, test_alloc_init_no_memory_returns_enomem)
{
	struct k_msgq msgq;

	memset(&msgq, FILL, sizeof(msgq));
	z_thread_malloc_fake.return_val = NULL;

	zassert_equal(z_impl_k_msgq_alloc_init(&msgq, MSG_SIZE, MAX_MSGS), -ENOMEM);

	zassert_call_history(z_thread_malloc);
	kernel_unit_assert_filled(&msgq, sizeof(msgq));
}

/**
 * @brief k_msgq_alloc_init() does not reject a size of 0: it requests 0 bytes from the heap.
 *
 * @details
 * - Setup: z_thread_malloc() gives the ring buffer of the test.
 * - Action: k_msgq_alloc_init() with max_msgs 0.
 * - Expected: one call of z_thread_malloc() with 0. Return value 0. The
 *   message queue has no slots: @c buffer_end is @c buffer_start.
 *
 * @ingroup kernel_unit_msgq_k_msgq_alloc_init
 * @see z_impl_k_msgq_alloc_init()
 */
ZTEST(msgq_unit, test_alloc_init_zero_size)
{
	struct k_msgq msgq;

	z_thread_malloc_fake.custom_fake = malloc_ring;

	zassert_equal(z_impl_k_msgq_alloc_init(&msgq, MSG_SIZE, 0U), 0);

	zassert_equal(z_thread_malloc_fake.arg0_val, 0U);
	zassert_equal_ptr(msgq.buffer_end, msgq.buffer_start);
	zassert_equal(z_impl_k_msgq_num_free_get(&msgq), 0U);
}

/*
 * Tests: Cleanup. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_msgq, at the top of this file.
 */

/* Make an allocated message queue on the ring buffer of the test. */
static void msgq_prepare_alloc(struct k_msgq *msgq)
{
	msgq_prepare(msgq);
	msgq->flags = K_MSGQ_FLAG_ALLOC;
}

/**
 * @brief k_msgq_cleanup() of an allocated ring buffer frees the buffer, clears the flag and
 * returns 0.
 *
 * @details
 * - Setup: a message queue with K_MSGQ_FLAG_ALLOC. No thread waits.
 * - Action: k_msgq_cleanup().
 * - Expected: return value 0. One call of k_free() with @c buffer_start.
 *   @c flags is 0.
 *
 * @ingroup kernel_unit_msgq_k_msgq_cleanup
 * @see k_msgq_cleanup(), z_msgq_cleanup()
 */
ZTEST(msgq_unit, test_cleanup_frees_allocated_buffer)
{
	struct k_msgq msgq;

	msgq_prepare_alloc(&msgq);

	zassert_equal(k_msgq_cleanup(&msgq), 0);

	zassert_equal(k_free_fake.call_count, 1);
	zassert_equal_ptr(k_free_fake.arg0_val, ring);
	zassert_equal(msgq.flags, 0U);
}

/**
 * @brief k_msgq_cleanup() of a buffer of the caller does not free the buffer and returns 0.
 *
 * @details
 * - Setup: a message queue without K_MSGQ_FLAG_ALLOC. No thread waits.
 * - Action: k_msgq_cleanup().
 * - Expected: return value 0. No call of k_free().
 *
 * @ingroup kernel_unit_msgq_k_msgq_cleanup
 * @see k_msgq_cleanup(), z_msgq_cleanup()
 */
ZTEST(msgq_unit, test_cleanup_keeps_caller_buffer)
{
	struct k_msgq msgq;

	msgq_prepare(&msgq);

	zassert_equal(k_msgq_cleanup(&msgq), 0);

	zassert_equal(k_free_fake.call_count, 0);
}

/**
 * @brief A second k_msgq_cleanup() does not free the buffer again.
 *
 * @details
 * - Setup: a message queue with K_MSGQ_FLAG_ALLOC.
 * - Action: k_msgq_cleanup() two times.
 * - Expected: both return 0. One call of k_free().
 *
 * @ingroup kernel_unit_msgq_k_msgq_cleanup
 * @see k_msgq_cleanup(), z_msgq_cleanup()
 */
ZTEST(msgq_unit, test_cleanup_frees_once)
{
	struct k_msgq msgq;

	msgq_prepare_alloc(&msgq);

	zassert_equal(k_msgq_cleanup(&msgq), 0);
	zassert_equal(k_msgq_cleanup(&msgq), 0);

	zassert_equal(k_free_fake.call_count, 1);
}

/**
 * @brief k_msgq_cleanup() does not change the ring buffer pointers or the number of messages.
 *
 * @details
 * - Setup: an allocated message queue with 2 messages.
 * - Action: k_msgq_cleanup().
 * - Expected: @c buffer_start, @c buffer_end, @c read_ptr, @c write_ptr and
 *   @c used_msgs are as before. Thus the message queue still points to the
 *   freed buffer.
 *
 * @ingroup kernel_unit_msgq_k_msgq_cleanup
 * @see k_msgq_cleanup(), z_msgq_cleanup()
 */
ZTEST(msgq_unit, test_cleanup_keeps_pointers)
{
	struct k_msgq msgq;
	struct k_msgq before;

	msgq_prepare_alloc(&msgq);
	put_msgs(&msgq, 1, 2);
	before = msgq;

	zassert_equal(k_msgq_cleanup(&msgq), 0);

	zassert_equal_ptr(msgq.buffer_start, before.buffer_start);
	zassert_equal_ptr(msgq.buffer_end, before.buffer_end);
	zassert_equal_ptr(msgq.read_ptr, before.read_ptr);
	zassert_equal_ptr(msgq.write_ptr, before.write_ptr);
	zassert_equal(msgq.used_msgs, 2U);
}

/**
 * @brief k_msgq_cleanup() reads the wait queue with z_waitq_head(), and z_msgq_cleanup() with
 * locked true reads it with z_waitq_head_locked().
 *
 * @details
 * - Setup: an allocated message queue. No thread waits.
 * - Action: k_msgq_cleanup(), then z_msgq_cleanup() with @c locked true.
 * - Expected: k_msgq_cleanup() calls z_waitq_head() with the wait queue and
 *   not z_waitq_head_locked(). z_msgq_cleanup(true) calls
 *   z_waitq_head_locked() with the wait queue and not z_waitq_head().
 *   With CONFIG_NO_RUNTIME_CHECKS, the test does not apply.
 *
 * @ingroup kernel_unit_msgq_k_msgq_cleanup
 * @see k_msgq_cleanup(), z_msgq_cleanup()
 */
ZTEST(msgq_unit, test_cleanup_locked_selects_wait_queue_reader)
{
	struct k_msgq msgq;

	if (IS_ENABLED(CONFIG_NO_RUNTIME_CHECKS)) {
		ztest_test_skip();
	}

	msgq_prepare_alloc(&msgq);

	zassert_equal(k_msgq_cleanup(&msgq), 0);

	zassert_equal(z_waitq_head_fake.call_count, 1);
	zassert_equal_ptr(z_waitq_head_fake.arg0_val, &msgq.wait_q);
	zassert_equal(z_waitq_head_locked_fake.call_count, 0);

	msgq_prepare_alloc(&msgq);
	reset_history();

	zassert_equal(z_msgq_cleanup(&msgq, true), 0);

	zassert_equal(z_waitq_head_locked_fake.call_count, 1);
	zassert_equal_ptr(z_waitq_head_locked_fake.arg0_val, &msgq.wait_q);
	zassert_equal(z_waitq_head_fake.call_count, 0);
	zassert_equal(k_free_fake.call_count, 1);
}

/**
 * @brief If a thread waits, k_msgq_cleanup() returns -EBUSY and does not free the buffer.
 *
 * @details
 * - Setup: an allocated message queue. z_waitq_head() returns a thread.
 * - Action: k_msgq_cleanup().
 * - Expected: return value -EBUSY. No call of k_free(). The flag
 *   K_MSGQ_FLAG_ALLOC stays set.
 *
 * @ingroup kernel_unit_msgq_k_msgq_cleanup
 * @see k_msgq_cleanup(), z_msgq_cleanup()
 */
ZTEST(msgq_unit, test_cleanup_waiting_thread_returns_ebusy)
{
	struct k_msgq msgq;

	if (!IS_ENABLED(CONFIG_RUNTIME_ERROR_CHECKS)) {
		ztest_test_skip();
	}

	msgq_prepare_alloc(&msgq);
	z_waitq_head_fake.return_val = &other_thread;

	zassert_equal(k_msgq_cleanup(&msgq), -EBUSY);

	zassert_equal(k_free_fake.call_count, 0);
	zassert_equal(msgq.flags, K_MSGQ_FLAG_ALLOC);
}

/**
 * @brief If a thread waits, z_msgq_cleanup() with locked true returns -EBUSY and does not free the
 * buffer.
 *
 * @details
 * - Setup: an allocated message queue. z_waitq_head_locked() returns a
 *   thread.
 * - Action: z_msgq_cleanup() with @c locked true.
 * - Expected: return value -EBUSY. No call of k_free() and no call of
 *   z_waitq_head().
 *
 * @ingroup kernel_unit_msgq_z_msgq_cleanup
 * @see z_msgq_cleanup()
 */
ZTEST(msgq_unit, test_cleanup_locked_waiting_thread_returns_ebusy)
{
	struct k_msgq msgq;

	if (!IS_ENABLED(CONFIG_RUNTIME_ERROR_CHECKS)) {
		ztest_test_skip();
	}

	msgq_prepare_alloc(&msgq);
	z_waitq_head_locked_fake.return_val = &other_thread;

	zassert_equal(z_msgq_cleanup(&msgq, true), -EBUSY);

	zassert_equal(k_free_fake.call_count, 0);
	zassert_equal(z_waitq_head_fake.call_count, 0);
	zassert_equal(msgq.flags, K_MSGQ_FLAG_ALLOC);
}

/**
 * @brief With CONFIG_NO_RUNTIME_CHECKS, k_msgq_cleanup() does not read the wait queue and frees the
 * buffer also if a thread waits.
 *
 * @details
 * CHECKIF() is empty, so the caller must make sure that no thread waits.
 * - Setup: an allocated message queue. z_waitq_head() and
 *   z_waitq_head_locked() return a thread.
 * - Action: k_msgq_cleanup(), then z_msgq_cleanup() with @c locked true on a
 *   new allocated message queue.
 * - Expected: both return 0. Each frees the buffer. No call of
 *   z_waitq_head() or z_waitq_head_locked().
 *
 * @ingroup kernel_unit_msgq_k_msgq_cleanup
 * @see k_msgq_cleanup(), z_msgq_cleanup()
 */
ZTEST(msgq_unit, test_cleanup_no_runtime_checks_frees_with_waiting_thread)
{
	struct k_msgq msgq;

	if (!IS_ENABLED(CONFIG_NO_RUNTIME_CHECKS)) {
		ztest_test_skip();
	}

	msgq_prepare_alloc(&msgq);
	z_waitq_head_fake.return_val = &other_thread;
	z_waitq_head_locked_fake.return_val = &other_thread;

	zassert_equal(k_msgq_cleanup(&msgq), 0);
	msgq_prepare_alloc(&msgq);
	zassert_equal(z_msgq_cleanup(&msgq, true), 0);

	zassert_equal(k_free_fake.call_count, 2);
	zassert_equal(z_waitq_head_fake.call_count, 0);
	zassert_equal(z_waitq_head_locked_fake.call_count, 0);
}

#ifdef CONFIG_ASSERT_ON_ERRORS
/**
 * @brief With CONFIG_ASSERT_ON_ERRORS, z_msgq_cleanup() asserts that no thread waits.
 *
 * @details
 * - Setup: an allocated message queue. z_waitq_head() returns a thread.
 * - Action: k_msgq_cleanup(), then z_msgq_cleanup() with @c locked true and
 *   z_waitq_head_locked() that returns a thread, then k_msgq_cleanup() with
 *   no waiting thread.
 * - Expected: one failed assertion for each of the first two calls, before
 *   k_free(). No failed assertion for the third call. The fake assertion
 *   hook returns, so each call continues, frees the buffer and returns 0.
 *
 * @ingroup kernel_unit_msgq_k_msgq_cleanup
 * @see k_msgq_cleanup(), z_msgq_cleanup()
 */
ZTEST(msgq_unit, test_cleanup_assert_on_errors)
{
	struct k_msgq msgq;

	msgq_prepare_alloc(&msgq);
	z_waitq_head_fake.return_val = &other_thread;
	zassert_equal(k_msgq_cleanup(&msgq), 0);
	zassert_equal(assert_post_action_fake.call_count, 1);
	zassert_called_before(assert_post_action, k_free);

	msgq_prepare_alloc(&msgq);
	z_waitq_head_fake.return_val = NULL;
	z_waitq_head_locked_fake.return_val = &other_thread;
	zassert_equal(z_msgq_cleanup(&msgq, true), 0);
	zassert_equal(assert_post_action_fake.call_count, 2);

	msgq_prepare_alloc(&msgq);
	z_waitq_head_locked_fake.return_val = NULL;
	zassert_equal(k_msgq_cleanup(&msgq), 0);
	zassert_equal(assert_post_action_fake.call_count, 2);
	zassert_equal(k_free_fake.call_count, 3);
}
#endif /* CONFIG_ASSERT_ON_ERRORS */

/*
 * Tests: Put. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_msgq, at the top of this file.
 */

/**
 * @brief k_msgq_put() copies the message to the write pointer, moves the write pointer one slot
 * forward and returns 0.
 *
 * @details
 * - Setup: an empty message queue. No reader waits.
 * - Action: k_msgq_put() of message 1 with K_NO_WAIT.
 * - Expected: return value 0. Slot 0 has message 1. @c write_ptr is slot 1,
 *   @c read_ptr is slot 0, @c used_msgs is 1. The other slots keep the
 *   pattern.
 *
 * @ingroup kernel_unit_msgq_k_msgq_put
 * @see z_impl_k_msgq_put(), put_msg_in_queue()
 */
ZTEST(msgq_unit, test_put_copies_message_to_tail)
{
	struct k_msgq msgq;
	struct msg m = make_msg(1);

	msgq_prepare(&msgq);

	zassert_equal(z_impl_k_msgq_put(&msgq, &m, K_NO_WAIT), 0);

	zassert_msg(SLOT(0), 1);
	zassert_equal_ptr(msgq.read_ptr, SLOT(0));
	zassert_equal_ptr(msgq.write_ptr, SLOT(1));
	zassert_msgq_contents(&msgq, 1);
	kernel_unit_assert_filled(SLOT(1), (MAX_MSGS - 1U) * MSG_SIZE);
}

/**
 * @brief k_msgq_put() does not keep the pointer to the data of the caller.
 *
 * @details
 * - Setup: an empty message queue.
 * - Action: k_msgq_put() of a message, then change the message of the
 *   caller.
 * - Expected: the ring buffer has the message as it was at the call.
 *
 * @ingroup kernel_unit_msgq_k_msgq_put
 * @see z_impl_k_msgq_put()
 */
ZTEST(msgq_unit, test_put_copies_data)
{
	struct k_msgq msgq;
	struct msg m = make_msg(7);

	msgq_prepare(&msgq);

	zassert_equal(z_impl_k_msgq_put(&msgq, &m, K_NO_WAIT), 0);
	m = make_msg(8);

	zassert_msgq_contents(&msgq, 7);
}

/**
 * @brief k_msgq_put() appends the message after the messages in the ring buffer.
 *
 * @details
 * - Setup: a message queue with messages 1 and 2.
 * - Action: k_msgq_put() of message 3.
 * - Expected: the messages from the head are 1, 2, 3.
 *
 * @ingroup kernel_unit_msgq_k_msgq_put
 * @see z_impl_k_msgq_put()
 */
ZTEST(msgq_unit, test_put_appends_after_tail)
{
	struct k_msgq msgq;
	struct msg m = make_msg(3);

	msgq_prepare(&msgq);
	put_msgs(&msgq, 1, 2);

	zassert_equal(z_impl_k_msgq_put(&msgq, &m, K_NO_WAIT), 0);

	zassert_msgq_contents(&msgq, 1, 2, 3);
}

/**
 * @brief When the write pointer reaches the end of the ring buffer, k_msgq_put() moves it to the
 * start.
 *
 * @details
 * - Setup: an empty message queue with the read and write pointers at the
 *   last slot.
 * - Action: k_msgq_put() of messages 1 and 2.
 * - Expected: message 1 is in the last slot, message 2 in slot 0.
 *   @c write_ptr is slot 1. The guard slot after the end keeps the pattern.
 *
 * @ingroup kernel_unit_msgq_k_msgq_put
 * @see z_impl_k_msgq_put()
 */
ZTEST(msgq_unit, test_put_wraps_write_pointer)
{
	struct k_msgq msgq;

	msgq_prepare(&msgq);
	msgq_start_at(&msgq, MAX_MSGS - 1U);

	put_msgs(&msgq, 1, 1);
	zassert_equal_ptr(msgq.write_ptr, SLOT(0));
	put_msgs(&msgq, 2, 1);

	zassert_msg(SLOT(MAX_MSGS - 1U), 1);
	zassert_msg(SLOT(0), 2);
	zassert_equal_ptr(msgq.write_ptr, SLOT(1));
	zassert_msgq_contents(&msgq, 1, 2);
}

/**
 * @brief k_msgq_put() accepts max_msgs messages, and the ring buffer is then full.
 *
 * @details
 * - Setup: an empty message queue.
 * - Action: k_msgq_put() of MAX_MSGS messages with K_NO_WAIT.
 * - Expected: each call returns 0. @c used_msgs is MAX_MSGS,
 *   k_msgq_num_free_get() returns 0. @c write_ptr is @c read_ptr again.
 *
 * @ingroup kernel_unit_msgq_k_msgq_put
 * @see z_impl_k_msgq_put()
 */
ZTEST(msgq_unit, test_put_fills_queue)
{
	struct k_msgq msgq;

	msgq_prepare(&msgq);

	put_msgs(&msgq, 1, MAX_MSGS);

	zassert_msgq_contents(&msgq, 1, 2, 3, 4);
	zassert_equal(z_impl_k_msgq_num_free_get(&msgq), 0U);
	zassert_equal_ptr(msgq.write_ptr, msgq.read_ptr);
}

/**
 * @brief If the ring buffer is full and the timeout is K_NO_WAIT, k_msgq_put() returns -ENOMSG
 * and does not change the message queue.
 *
 * @details
 * - Setup: a full message queue.
 * - Action: k_msgq_put() of message 9 with K_NO_WAIT.
 * - Expected: return value -ENOMSG. The messages are 1, 2, 3, 4. No call of
 *   z_unpend_first_thread_locked() and no call of z_pend_curr().
 *
 * @ingroup kernel_unit_msgq_k_msgq_put
 * @see z_impl_k_msgq_put()
 */
ZTEST(msgq_unit, test_put_full_no_wait_returns_enomsg)
{
	struct k_msgq msgq;
	struct msg m = make_msg(9);

	msgq_prepare(&msgq);
	put_msgs(&msgq, 1, MAX_MSGS);

	zassert_equal(z_impl_k_msgq_put(&msgq, &m, K_NO_WAIT), -ENOMSG);

	zassert_msgq_contents(&msgq, 1, 2, 3, 4);
	zassert_equal(z_unpend_first_thread_locked_fake.call_count, 0);
	zassert_equal(z_pend_curr_fake.call_count, 0);
}

/**
 * @brief If the ring buffer is full and the timeout is not K_NO_WAIT, k_msgq_put() waits on the
 * wait queue with the message as swap data and with this timeout.
 *
 * @details
 * - Setup: a full message queue.
 * - Action: k_msgq_put() of message 9 with TEST_TIMEOUT.
 * - Expected: one call of z_pend_curr() with the lock, the wait queue of the
 *   message queue and TEST_TIMEOUT. At this call, @c _current->base.swap_data
 *   is the message of the caller. The ring buffer does not change.
 *
 * @ingroup kernel_unit_msgq_k_msgq_put
 * @see z_impl_k_msgq_put()
 */
ZTEST(msgq_unit, test_put_full_waits_with_message)
{
	struct k_msgq msgq;
	struct msg m = make_msg(9);

	msgq_prepare(&msgq);
	put_msgs(&msgq, 1, MAX_MSGS);

	(void)z_impl_k_msgq_put(&msgq, &m, TEST_TIMEOUT);

	zassert_equal(z_pend_curr_fake.call_count, 1);
	zassert_equal_ptr(z_pend_curr_fake.arg0_val, &msgq.lock);
	zassert_equal_ptr(z_pend_curr_fake.arg2_val, &msgq.wait_q);
	zassert_true(K_TIMEOUT_EQ(z_pend_curr_fake.arg3_val, TEST_TIMEOUT));
	zassert_equal_ptr(swap_data_at_pend, &m);
	zassert_msgq_contents(&msgq, 1, 2, 3, 4);
}

/**
 * @brief After a wait, k_msgq_put() returns the result of the wait and does not change the ring
 * buffer.
 *
 * @details
 * - Setup: a full message queue.
 * - Action: k_msgq_put() with K_FOREVER three times. The wait gives 0 (a
 *   reader took the message), then -EAGAIN (timeout), then -ENOMSG (purge).
 * - Expected: the return values are 0, -EAGAIN and -ENOMSG. The ring buffer
 *   does not change. The reader, not k_msgq_put(), copies the message after
 *   the wait (see the rules of the hand-over in @ref kernel_unit_msgq).
 *
 * @ingroup kernel_unit_msgq_k_msgq_put
 * @see z_impl_k_msgq_put()
 */
ZTEST(msgq_unit, test_put_returns_wait_result)
{
	struct k_msgq msgq;
	struct msg m = make_msg(9);

	msgq_prepare(&msgq);
	put_msgs(&msgq, 1, MAX_MSGS);

	set_wait_result(0);
	zassert_equal(z_impl_k_msgq_put(&msgq, &m, K_FOREVER), 0);
	set_wait_result(-EAGAIN);
	zassert_equal(z_impl_k_msgq_put(&msgq, &m, K_FOREVER), -EAGAIN);
	set_wait_result(-ENOMSG);
	zassert_equal(z_impl_k_msgq_put(&msgq, &m, K_FOREVER), -ENOMSG);

	zassert_msgq_contents(&msgq, 1, 2, 3, 4);
}

/**
 * @brief k_msgq_put_front() puts the message before the head: it is the next message that
 * k_msgq_get() gives.
 *
 * @details
 * - Setup: a message queue with messages 1 and 2, with the read pointer at
 *   slot 1.
 * - Action: k_msgq_put_front() of message 9.
 * - Expected: return value 0. @c read_ptr is slot 0, and slot 0 has message
 *   9. The messages from the head are 9, 1, 2. @c write_ptr does not change.
 *
 * @ingroup kernel_unit_msgq_k_msgq_put_front
 * @see z_impl_k_msgq_put_front()
 */
ZTEST(msgq_unit, test_put_front_puts_message_at_head)
{
	struct k_msgq msgq;
	struct msg m = make_msg(9);
	char *write_ptr;

	msgq_prepare(&msgq);
	msgq_start_at(&msgq, 1);
	put_msgs(&msgq, 1, 2);
	write_ptr = msgq.write_ptr;

	zassert_equal(z_impl_k_msgq_put_front(&msgq, &m), 0);

	zassert_equal_ptr(msgq.read_ptr, SLOT(0));
	zassert_msg(SLOT(0), 9);
	zassert_equal_ptr(msgq.write_ptr, write_ptr);
	zassert_msgq_contents(&msgq, 9, 1, 2);
}

/**
 * @brief When the read pointer is at the start of the ring buffer, k_msgq_put_front() moves it to
 * the last slot.
 *
 * @details
 * - Setup: a message queue with message 1 in slot 0.
 * - Action: k_msgq_put_front() of message 9.
 * - Expected: message 9 is in the last slot, and @c read_ptr is the last
 *   slot. The messages from the head are 9, 1. The guard slot keeps the
 *   pattern.
 *
 * @ingroup kernel_unit_msgq_k_msgq_put_front
 * @see z_impl_k_msgq_put_front()
 */
ZTEST(msgq_unit, test_put_front_wraps_read_pointer)
{
	struct k_msgq msgq;
	struct msg m = make_msg(9);

	msgq_prepare(&msgq);
	put_msgs(&msgq, 1, 1);

	zassert_equal(z_impl_k_msgq_put_front(&msgq, &m), 0);

	zassert_equal_ptr(msgq.read_ptr, SLOT(MAX_MSGS - 1U));
	zassert_msg(SLOT(MAX_MSGS - 1U), 9);
	zassert_msgq_contents(&msgq, 9, 1);
}

/**
 * @brief If the ring buffer is full, k_msgq_put_front() returns -ENOMSG and does not wait.
 *
 * @details
 * The API documentation says that k_msgq_put_front() behaves as k_msgq_put()
 * if there is no space. The implementation uses K_NO_WAIT, so it does not
 * wait.
 * - Setup: a full message queue.
 * - Action: k_msgq_put_front() of message 9.
 * - Expected: return value -ENOMSG. No call of z_pend_curr(). The messages
 *   are 1, 2, 3, 4.
 *
 * @ingroup kernel_unit_msgq_k_msgq_put_front
 * @see z_impl_k_msgq_put_front()
 */
ZTEST(msgq_unit, test_put_front_full_returns_enomsg)
{
	struct k_msgq msgq;
	struct msg m = make_msg(9);

	msgq_prepare(&msgq);
	put_msgs(&msgq, 1, MAX_MSGS);

	zassert_equal(z_impl_k_msgq_put_front(&msgq, &m), -ENOMSG);

	zassert_equal(z_pend_curr_fake.call_count, 0);
	zassert_msgq_contents(&msgq, 1, 2, 3, 4);
}

/**
 * @brief A message queue with max_msgs 0 is always full: k_msgq_put() does not give a message to a
 * waiting reader.
 *
 * @details
 * - Setup: a message queue with no slots. A reader waits.
 * - Action: k_msgq_put() with K_NO_WAIT.
 * - Expected: return value -ENOMSG. No call of
 *   z_unpend_first_thread_locked(). The buffer of the reader does not
 *   change. Thus such a message queue is not a rendezvous point: the readers
 *   and the writers both wait.
 *
 * @ingroup kernel_unit_msgq_k_msgq_put
 * @see z_impl_k_msgq_put()
 */
ZTEST(msgq_unit, test_put_zero_slots_is_full)
{
	struct k_msgq msgq;
	struct msg m = make_msg(1);

	k_msgq_init(&msgq, ring, MSG_SIZE, 0U);
	reset_history();
	set_waiting_reader();

	zassert_equal(z_impl_k_msgq_put(&msgq, &m, K_NO_WAIT), -ENOMSG);

	zassert_equal(z_unpend_first_thread_locked_fake.call_count, 0);
	kernel_unit_assert_filled(&reader_buf, sizeof(reader_buf));
}

/*
 * Tests: Get. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_msgq, at the top of this file.
 */

/**
 * @brief k_msgq_get() copies the head message to the caller, removes it and returns 0.
 *
 * @details
 * - Setup: a message queue with messages 1, 2. No writer waits.
 * - Action: k_msgq_get() with K_NO_WAIT.
 * - Expected: return value 0. The caller has message 1. @c read_ptr is
 *   slot 1. The message queue has message 2.
 *
 * @ingroup kernel_unit_msgq_k_msgq_get
 * @see z_impl_k_msgq_get()
 */
ZTEST(msgq_unit, test_get_removes_head_message)
{
	struct k_msgq msgq;
	struct msg m;

	msgq_prepare(&msgq);
	put_msgs(&msgq, 1, 2);

	zassert_equal(z_impl_k_msgq_get(&msgq, &m, K_NO_WAIT), 0);

	zassert_msg(&m, 1);
	zassert_equal_ptr(msgq.read_ptr, SLOT(1));
	zassert_msgq_contents(&msgq, 2);
}

/**
 * @brief When the read pointer reaches the end of the ring buffer, k_msgq_get() moves it to the
 * start.
 *
 * @details
 * - Setup: an empty message queue with the pointers at the last slot. Then
 *   messages 1 and 2 (message 2 in slot 0).
 * - Action: k_msgq_get() two times.
 * - Expected: the caller gets 1, then 2. After the first call, @c read_ptr
 *   is slot 0. The message queue is then empty.
 *
 * @ingroup kernel_unit_msgq_k_msgq_get
 * @see z_impl_k_msgq_get()
 */
ZTEST(msgq_unit, test_get_wraps_read_pointer)
{
	struct k_msgq msgq;
	struct msg m;

	msgq_prepare(&msgq);
	msgq_start_at(&msgq, MAX_MSGS - 1U);
	put_msgs(&msgq, 1, 2);

	zassert_equal(z_impl_k_msgq_get(&msgq, &m, K_NO_WAIT), 0);
	zassert_msg(&m, 1);
	zassert_equal_ptr(msgq.read_ptr, SLOT(0));
	zassert_equal(z_impl_k_msgq_get(&msgq, &m, K_NO_WAIT), 0);
	zassert_msg(&m, 2);

	zassert_msgq_empty(&msgq);
}

/**
 * @brief The message queue gives the messages in the order of k_msgq_put(): first in, first out,
 * also across the end of the ring buffer.
 *
 * @details
 * - Setup: an empty message queue.
 * - Action: put 1 to 4, get two messages, put 5 and 6, get four messages.
 * - Expected: the caller gets 1, 2, then 3, 4, 5, 6. The message queue is
 *   then empty.
 *
 * @ingroup kernel_unit_msgq_k_msgq_get
 * @see z_impl_k_msgq_get(), z_impl_k_msgq_put()
 */
ZTEST(msgq_unit, test_get_fifo_order)
{
	struct k_msgq msgq;
	struct msg m;

	msgq_prepare(&msgq);
	put_msgs(&msgq, 1, 4);

	for (uint32_t id = 1; id <= 2U; id++) {
		zassert_equal(z_impl_k_msgq_get(&msgq, &m, K_NO_WAIT), 0);
		zassert_msg(&m, id);
	}
	put_msgs(&msgq, 5, 2);
	for (uint32_t id = 3; id <= 6U; id++) {
		zassert_equal(z_impl_k_msgq_get(&msgq, &m, K_NO_WAIT), 0);
		zassert_msg(&m, id);
	}

	zassert_msgq_empty(&msgq);
}

/**
 * @brief If the ring buffer is empty and the timeout is K_NO_WAIT, k_msgq_get() returns -ENOMSG
 * and does not write to the buffer of the caller.
 *
 * @details
 * - Setup: an empty message queue. A buffer filled with a pattern.
 * - Action: k_msgq_get() with K_NO_WAIT.
 * - Expected: return value -ENOMSG. The buffer keeps the pattern. No call of
 *   z_pend_curr() and no call of z_unpend_first_thread_locked().
 *
 * @ingroup kernel_unit_msgq_k_msgq_get
 * @see z_impl_k_msgq_get()
 */
ZTEST(msgq_unit, test_get_empty_no_wait_returns_enomsg)
{
	struct k_msgq msgq;
	struct msg m;

	msgq_prepare(&msgq);
	memset(&m, FILL, sizeof(m));

	zassert_equal(z_impl_k_msgq_get(&msgq, &m, K_NO_WAIT), -ENOMSG);

	kernel_unit_assert_filled(&m, sizeof(m));
	zassert_equal(z_pend_curr_fake.call_count, 0);
	zassert_equal(z_unpend_first_thread_locked_fake.call_count, 0);
}

/**
 * @brief If the ring buffer is empty and the timeout is not K_NO_WAIT, k_msgq_get() waits on the
 * wait queue with the buffer of the caller as swap data and with this timeout.
 *
 * @details
 * - Setup: an empty message queue.
 * - Action: k_msgq_get() with TEST_TIMEOUT.
 * - Expected: one call of z_pend_curr() with the lock, the wait queue and
 *   TEST_TIMEOUT. At this call, @c _current->base.swap_data is the buffer of
 *   the caller.
 *
 * @ingroup kernel_unit_msgq_k_msgq_get
 * @see z_impl_k_msgq_get()
 */
ZTEST(msgq_unit, test_get_empty_waits_with_buffer)
{
	struct k_msgq msgq;
	struct msg m;

	msgq_prepare(&msgq);

	(void)z_impl_k_msgq_get(&msgq, &m, TEST_TIMEOUT);

	zassert_equal(z_pend_curr_fake.call_count, 1);
	zassert_equal_ptr(z_pend_curr_fake.arg0_val, &msgq.lock);
	zassert_equal_ptr(z_pend_curr_fake.arg2_val, &msgq.wait_q);
	zassert_true(K_TIMEOUT_EQ(z_pend_curr_fake.arg3_val, TEST_TIMEOUT));
	zassert_equal_ptr(swap_data_at_pend, &m);
}

/**
 * @brief After a wait, k_msgq_get() returns the result of the wait.
 *
 * @details
 * - Setup: an empty message queue.
 * - Action: k_msgq_get() with K_FOREVER three times. The wait gives 0 (a
 *   writer gave a message), then -EAGAIN (timeout), then -ENOMSG (purge).
 * - Expected: the return values are 0, -EAGAIN and -ENOMSG. k_msgq_get()
 *   does not read the ring buffer after the wait: the writer copies the
 *   message into the buffer of the caller (see the rules of the hand-over
 *   in @ref kernel_unit_msgq).
 *
 * @ingroup kernel_unit_msgq_k_msgq_get
 * @see z_impl_k_msgq_get()
 */
ZTEST(msgq_unit, test_get_returns_wait_result)
{
	struct k_msgq msgq;
	struct msg m;

	msgq_prepare(&msgq);
	memset(&m, FILL, sizeof(m));

	set_wait_result(0);
	zassert_equal(z_impl_k_msgq_get(&msgq, &m, K_FOREVER), 0);
	set_wait_result(-EAGAIN);
	zassert_equal(z_impl_k_msgq_get(&msgq, &m, K_FOREVER), -EAGAIN);
	set_wait_result(-ENOMSG);
	zassert_equal(z_impl_k_msgq_get(&msgq, &m, K_FOREVER), -ENOMSG);

	kernel_unit_assert_filled(&m, sizeof(m));
	zassert_msgq_empty(&msgq);
}

/**
 * @brief If the ring buffer has a message, k_msgq_get() does not wait, also if the timeout permits
 * a wait.
 *
 * @details
 * - Setup: a message queue with message 1.
 * - Action: k_msgq_get() with K_FOREVER.
 * - Expected: return value 0, the caller has message 1. No call of
 *   z_pend_curr().
 *
 * @ingroup kernel_unit_msgq_k_msgq_get
 * @see z_impl_k_msgq_get()
 */
ZTEST(msgq_unit, test_get_does_not_wait_if_message)
{
	struct k_msgq msgq;
	struct msg m;

	msgq_prepare(&msgq);
	put_msgs(&msgq, 1, 1);

	zassert_equal(z_impl_k_msgq_get(&msgq, &m, K_FOREVER), 0);

	zassert_msg(&m, 1);
	zassert_equal(z_pend_curr_fake.call_count, 0);
}

/*
 * Tests: Peek. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_msgq, at the top of this file.
 */

/**
 * @brief k_msgq_peek() copies the head message and does not remove it.
 *
 * @details
 * - Setup: a message queue with messages 1, 2.
 * - Action: k_msgq_peek().
 * - Expected: return value 0. The caller has message 1. The message queue
 *   still has 1, 2 at the same pointers.
 *
 * @ingroup kernel_unit_msgq_k_msgq_peek
 * @see z_impl_k_msgq_peek()
 */
ZTEST(msgq_unit, test_peek_copies_head_message)
{
	struct k_msgq msgq;
	struct msg m;

	msgq_prepare(&msgq);
	put_msgs(&msgq, 1, 2);

	zassert_equal(z_impl_k_msgq_peek(&msgq, &m), 0);

	zassert_msg(&m, 1);
	zassert_equal_ptr(msgq.read_ptr, SLOT(0));
	zassert_msgq_contents(&msgq, 1, 2);
}

/**
 * @brief For an empty message queue, k_msgq_peek() returns -ENOMSG and does not write to the buffer
 * of the caller.
 *
 * @details
 * - Setup: an empty message queue. A buffer filled with a pattern.
 * - Action: k_msgq_peek().
 * - Expected: return value -ENOMSG. The buffer keeps the pattern.
 *
 * @ingroup kernel_unit_msgq_k_msgq_peek
 * @see z_impl_k_msgq_peek()
 */
ZTEST(msgq_unit, test_peek_empty_returns_enomsg)
{
	struct k_msgq msgq;
	struct msg m;

	msgq_prepare(&msgq);
	memset(&m, FILL, sizeof(m));

	zassert_equal(z_impl_k_msgq_peek(&msgq, &m), -ENOMSG);

	kernel_unit_assert_filled(&m, sizeof(m));
}

/**
 * @brief k_msgq_peek_at() copies the message at the index from the head and does not remove it.
 *
 * @details
 * - Setup: a message queue with messages 1, 2, 3.
 * - Action: k_msgq_peek_at() with the index 0, 1 and 2.
 * - Expected: each returns 0. The caller gets 1, 2 and 3. Index 0 gives the
 *   same message as k_msgq_peek(). The message queue does not change.
 *
 * @ingroup kernel_unit_msgq_k_msgq_peek_at
 * @see z_impl_k_msgq_peek_at()
 */
ZTEST(msgq_unit, test_peek_at_copies_indexed_message)
{
	struct k_msgq msgq;
	struct msg m;

	msgq_prepare(&msgq);
	put_msgs(&msgq, 1, 3);

	for (uint32_t idx = 0; idx < 3U; idx++) {
		zassert_equal(z_impl_k_msgq_peek_at(&msgq, &m, idx), 0);
		zassert_msg(&m, idx + 1U);
	}

	zassert_msgq_contents(&msgq, 1, 2, 3);
}

/**
 * @brief k_msgq_peek_at() finds a message after the end of the ring buffer at the start of the
 * ring buffer.
 *
 * @details
 * - Setup: a message queue with the head at slot 2 and messages 1, 2, 3, 4
 *   (in slots 2, 3, 0, 1).
 * - Action: k_msgq_peek_at() with the index 0 to 3.
 * - Expected: the caller gets 1, 2, 3, 4. Index 2 is the first message
 *   after the wrap-around: its offset from the read pointer is equal to the
 *   bytes to the end.
 *
 * @ingroup kernel_unit_msgq_k_msgq_peek_at
 * @see z_impl_k_msgq_peek_at()
 */
ZTEST(msgq_unit, test_peek_at_wraps_around)
{
	struct k_msgq msgq;
	struct msg m;

	msgq_prepare(&msgq);
	msgq_start_at(&msgq, 2);
	put_msgs(&msgq, 1, 4);

	for (uint32_t idx = 0; idx < 4U; idx++) {
		zassert_equal(z_impl_k_msgq_peek_at(&msgq, &m, idx), 0);
		zassert_msg(&m, idx + 1U);
	}

	zassert_msgq_contents(&msgq, 1, 2, 3, 4);
}

/**
 * @brief k_msgq_peek_at() returns -ENOMSG if the index is not less than the number of messages.
 *
 * @details
 * - Setup: a message queue with messages 1, 2. A buffer filled with a
 *   pattern.
 * - Action: k_msgq_peek_at() with the index 2, then UINT32_MAX. Then
 *   k_msgq_peek_at() with the index 0 on an empty message queue.
 * - Expected: each returns -ENOMSG. The buffer keeps the pattern.
 *
 * @ingroup kernel_unit_msgq_k_msgq_peek_at
 * @see z_impl_k_msgq_peek_at()
 */
ZTEST(msgq_unit, test_peek_at_index_out_of_range_returns_enomsg)
{
	struct k_msgq msgq;
	struct msg m;

	msgq_prepare(&msgq);
	put_msgs(&msgq, 1, 2);
	memset(&m, FILL, sizeof(m));

	zassert_equal(z_impl_k_msgq_peek_at(&msgq, &m, 2), -ENOMSG);
	zassert_equal(z_impl_k_msgq_peek_at(&msgq, &m, UINT32_MAX), -ENOMSG);
	msgq_prepare(&msgq);
	zassert_equal(z_impl_k_msgq_peek_at(&msgq, &m, 0), -ENOMSG);

	kernel_unit_assert_filled(&m, sizeof(m));
}

/**
 * @brief k_msgq_peek() and k_msgq_peek_at() do not wake a thread and do not signal the poll
 * events.
 *
 * @details
 * - Setup: a message queue with message 1. A writer waits.
 * - Action: k_msgq_peek(), k_msgq_peek_at() with the index 0.
 * - Expected: no call of z_unpend_first_thread_locked(), z_sched_wake(),
 *   z_handle_obj_poll_events() or z_reschedule().
 *
 * @ingroup kernel_unit_msgq_k_msgq_peek
 * @see z_impl_k_msgq_peek(), z_impl_k_msgq_peek_at()
 */
ZTEST(msgq_unit, test_peek_does_not_wake)
{
	struct k_msgq msgq;
	struct msg m;

	msgq_prepare(&msgq);
	put_msgs(&msgq, 1, 1);
	set_waiting_writer(2);

	zassert_equal(z_impl_k_msgq_peek(&msgq, &m), 0);
	zassert_equal(z_impl_k_msgq_peek_at(&msgq, &m, 0), 0);

	zassert_equal(z_unpend_first_thread_locked_fake.call_count, 0);
	zassert_equal(z_sched_wake_fake.call_count, 0);
	zassert_equal(z_handle_obj_poll_events_fake.call_count, 0);
	zassert_equal(z_reschedule_fake.call_count, 0);
}

/*
 * Tests: Purge. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_msgq, at the top of this file.
 */

/**
 * @brief k_msgq_purge() discards all messages: the read pointer moves to the write pointer.
 *
 * @details
 * - Setup: a message queue with the head at slot 1 and messages 1, 2, 3.
 * - Action: k_msgq_purge().
 * - Expected: @c used_msgs is 0, @c read_ptr is @c write_ptr (slot 0).
 *   k_msgq_num_free_get() returns MAX_MSGS. The ring buffer still has the
 *   bytes of the messages.
 *
 * @ingroup kernel_unit_msgq_k_msgq_purge
 * @see z_impl_k_msgq_purge()
 */
ZTEST(msgq_unit, test_purge_discards_messages)
{
	struct k_msgq msgq;

	msgq_prepare(&msgq);
	msgq_start_at(&msgq, 1);
	put_msgs(&msgq, 1, 3);

	z_impl_k_msgq_purge(&msgq);

	zassert_equal(msgq.used_msgs, 0U);
	zassert_equal_ptr(msgq.read_ptr, SLOT(0));
	zassert_equal_ptr(msgq.write_ptr, SLOT(0));
	zassert_equal(z_impl_k_msgq_num_free_get(&msgq), MAX_MSGS);
	zassert_msg(SLOT(1), 1);
	zassert_msgq_empty(&msgq);
}

/**
 * @brief k_msgq_purge() wakes all waiting threads with the return value -ENOMSG and the data NULL.
 *
 * @details
 * - Setup: a full message queue. Three writers wait.
 * - Action: k_msgq_purge().
 * - Expected: four calls of z_sched_wake() with the wait queue, -ENOMSG and
 *   NULL: three wake a thread, and the fourth returns false. The message
 *   queue is empty. The messages of the writers do not go into the ring
 *   buffer.
 *
 * @ingroup kernel_unit_msgq_k_msgq_purge
 * @see z_impl_k_msgq_purge()
 */
ZTEST(msgq_unit, test_purge_wakes_all_waiting_threads)
{
	struct k_msgq msgq;

	msgq_prepare(&msgq);
	put_msgs(&msgq, 1, MAX_MSGS);
	kernel_unit_set_waiting_threads(3);

	z_impl_k_msgq_purge(&msgq);

	zassert_equal(z_sched_wake_fake.call_count, 4);
	for (unsigned int i = 0; i < 4U; i++) {
		zassert_equal_ptr(z_sched_wake_fake.arg0_history[i], &msgq.wait_q);
		zassert_equal(z_sched_wake_fake.arg1_history[i], -ENOMSG);
		zassert_is_null(z_sched_wake_fake.arg2_history[i]);
	}
	zassert_msgq_empty(&msgq);
}

/**
 * @brief k_msgq_purge() of an empty message queue also wakes the waiting readers with -ENOMSG.
 *
 * @details
 * - Setup: an empty message queue. Two readers wait.
 * - Action: k_msgq_purge().
 * - Expected: three calls of z_sched_wake() with -ENOMSG. The message queue
 *   is empty.
 *
 * @ingroup kernel_unit_msgq_k_msgq_purge
 * @see z_impl_k_msgq_purge()
 */
ZTEST(msgq_unit, test_purge_wakes_waiting_readers)
{
	struct k_msgq msgq;

	msgq_prepare(&msgq);
	kernel_unit_set_waiting_threads(2);

	z_impl_k_msgq_purge(&msgq);

	zassert_equal(z_sched_wake_fake.call_count, 3);
	zassert_equal(z_sched_wake_fake.arg1_val, -ENOMSG);
	zassert_msgq_empty(&msgq);
}

/**
 * @brief After k_msgq_purge(), the message queue accepts max_msgs messages again, in order.
 *
 * @details
 * - Setup: a full message queue. k_msgq_purge().
 * - Action: put 5 to 8, then get four messages.
 * - Expected: each put returns 0. The caller gets 5, 6, 7, 8.
 *
 * @ingroup kernel_unit_msgq_k_msgq_purge
 * @see z_impl_k_msgq_purge()
 */
ZTEST(msgq_unit, test_purge_then_reuse)
{
	struct k_msgq msgq;
	struct msg m;

	msgq_prepare(&msgq);
	put_msgs(&msgq, 1, MAX_MSGS);
	z_impl_k_msgq_purge(&msgq);

	put_msgs(&msgq, 5, MAX_MSGS);
	for (uint32_t id = 5; id <= 8U; id++) {
		zassert_equal(z_impl_k_msgq_get(&msgq, &m, K_NO_WAIT), 0);
		zassert_msg(&m, id);
	}
}

/*
 * Tests: Hand-over to a waiting thread. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_msgq, at the top of this file.
 */

/**
 * @brief If a reader waits, k_msgq_put() copies the message to the buffer of the reader and not to
 * the ring buffer.
 *
 * @details
 * - Setup: an empty message queue. A reader waits with an empty buffer.
 * - Action: k_msgq_put() of message 1 with K_NO_WAIT.
 * - Expected: return value 0. One call of z_unpend_first_thread_locked() with
 *   the wait queue. The buffer of the reader has message 1. The message
 *   queue is empty, and the ring buffer keeps the pattern.
 *
 * @ingroup kernel_unit_msgq_k_msgq_put
 * @see z_impl_k_msgq_put(), put_msg_in_queue()
 */
ZTEST(msgq_unit, test_handover_put_copies_to_reader)
{
	struct k_msgq msgq;
	struct msg m = make_msg(1);

	msgq_prepare(&msgq);
	set_waiting_reader();

	zassert_equal(z_impl_k_msgq_put(&msgq, &m, K_NO_WAIT), 0);

	zassert_equal(z_unpend_first_thread_locked_fake.call_count, 1);
	zassert_equal_ptr(z_unpend_first_thread_locked_fake.arg0_val, &msgq.wait_q);
	zassert_msg(&reader_buf, 1);
	zassert_msgq_empty(&msgq);
	kernel_unit_assert_filled(ring, sizeof(ring));
}

/**
 * @brief k_msgq_put() copies the message to the reader, then sets the return value 0 of the
 * reader, then makes the reader ready.
 *
 * @details
 * - Setup: an empty message queue. A reader waits.
 * - Action: k_msgq_put() of message 1.
 * - Expected: arch_thread_return_value_set() with the reader and 0, then
 *   z_sched_ready_locked() with the reader. When z_sched_ready_locked() is
 *   called, the buffer of the reader already has message 1.
 *
 * @ingroup kernel_unit_msgq_k_msgq_put
 * @see z_impl_k_msgq_put(), put_msg_in_queue()
 */
ZTEST(msgq_unit, test_handover_put_readies_reader_after_copy)
{
	struct k_msgq msgq;
	struct msg m = make_msg(1);

	msgq_prepare(&msgq);
	set_waiting_reader();

	zassert_equal(z_impl_k_msgq_put(&msgq, &m, K_NO_WAIT), 0);

	zassert_equal(arch_thread_return_value_set_fake.call_count, 1);
	zassert_equal_ptr(arch_thread_return_value_set_fake.arg0_val, &other_thread);
	zassert_equal(arch_thread_return_value_set_fake.arg1_val, 0U);
	zassert_equal(z_sched_ready_locked_fake.call_count, 1);
	zassert_equal_ptr(z_sched_ready_locked_fake.arg0_val, &other_thread);
	zassert_called_before(arch_thread_return_value_set, z_sched_ready_locked);
	zassert_msg(&data_at_ready, 1);
}

/**
 * @brief If a reader waits, k_msgq_put_front() also gives the message to the reader.
 *
 * @details
 * - Setup: an empty message queue. A reader waits.
 * - Action: k_msgq_put_front() of message 1.
 * - Expected: return value 0. The reader has message 1 and is ready. The
 *   message queue is empty, and @c read_ptr does not change.
 *
 * @ingroup kernel_unit_msgq_k_msgq_put_front
 * @see z_impl_k_msgq_put_front(), put_msg_in_queue()
 */
ZTEST(msgq_unit, test_handover_put_front_copies_to_reader)
{
	struct k_msgq msgq;
	struct msg m = make_msg(1);

	msgq_prepare(&msgq);
	set_waiting_reader();

	zassert_equal(z_impl_k_msgq_put_front(&msgq, &m), 0);

	zassert_msg(&reader_buf, 1);
	zassert_equal(z_sched_ready_locked_fake.call_count, 1);
	zassert_equal_ptr(msgq.read_ptr, SLOT(0));
	zassert_msgq_empty(&msgq);
}

/**
 * @brief A put makes at most one waiting reader ready.
 *
 * @details
 * - Setup: an empty message queue. A reader waits.
 * - Action: k_msgq_put() of message 1, then of message 2.
 * - Expected: the reader has message 1. The message queue has message 2.
 *   Each put calls z_unpend_first_thread_locked() once, and
 *   z_sched_ready_locked() is called once in total.
 *
 * @ingroup kernel_unit_msgq_k_msgq_put
 * @see z_impl_k_msgq_put(), put_msg_in_queue()
 */
ZTEST(msgq_unit, test_handover_put_wakes_one_reader)
{
	struct k_msgq msgq;
	struct msg m1 = make_msg(1);
	struct msg m2 = make_msg(2);

	msgq_prepare(&msgq);
	set_waiting_reader();

	zassert_equal(z_impl_k_msgq_put(&msgq, &m1, K_NO_WAIT), 0);
	zassert_equal(z_impl_k_msgq_put(&msgq, &m2, K_NO_WAIT), 0);

	zassert_msg(&reader_buf, 1);
	zassert_msgq_contents(&msgq, 2);
	zassert_equal(z_unpend_first_thread_locked_fake.call_count, 2);
	zassert_equal(z_sched_ready_locked_fake.call_count, 1);
}

/**
 * @brief The message that k_msgq_put() gives to a waiting reader is in the buffer that the
 * k_msgq_get() of the reader gave as swap data.
 *
 * @details
 * Model of both sides: the reader calls k_msgq_get() on an empty message
 * queue, and the fake z_pend_curr() records its swap data. Then the test
 * makes the current thread the waiting thread, and a writer calls
 * k_msgq_put().
 * - Setup: an empty message queue.
 * - Action: k_msgq_get() with K_FOREVER into a buffer, then k_msgq_put() of
 *   message 5.
 * - Expected: the buffer of k_msgq_get() has message 5. The message queue is
 *   empty.
 *
 * @ingroup kernel_unit_msgq_k_msgq_get
 * @see z_impl_k_msgq_get(), z_impl_k_msgq_put()
 */
ZTEST(msgq_unit, test_handover_get_buffer_receives_put_message)
{
	struct k_msgq msgq;
	struct msg buf;
	struct msg m = make_msg(5);

	msgq_prepare(&msgq);
	memset(&buf, FILL, sizeof(buf));

	(void)z_impl_k_msgq_get(&msgq, &buf, K_FOREVER);
	zassert_equal_ptr(current_thread.base.swap_data, &buf);
	waiting_thread = &current_thread;
	zassert_equal(z_impl_k_msgq_put(&msgq, &m, K_NO_WAIT), 0);

	zassert_msg(&buf, 5);
	zassert_msgq_empty(&msgq);
}

/**
 * @brief If a writer waits, k_msgq_get() copies the message of the writer to the tail after it
 * removes the head message.
 *
 * @details
 * - Setup: a full message queue (1 to 4). A writer waits with message 9.
 * - Action: k_msgq_get().
 * - Expected: return value 0. The caller has message 1. The message queue
 *   has 2, 3, 4, 9: it is full again. The writer has the return value 0
 *   and is ready.
 *
 * @ingroup kernel_unit_msgq_k_msgq_get
 * @see z_impl_k_msgq_get()
 */
ZTEST(msgq_unit, test_handover_get_takes_writer_message)
{
	struct k_msgq msgq;
	struct msg m;

	msgq_prepare(&msgq);
	put_msgs(&msgq, 1, MAX_MSGS);
	set_waiting_writer(9);

	zassert_equal(z_impl_k_msgq_get(&msgq, &m, K_NO_WAIT), 0);

	zassert_msg(&m, 1);
	zassert_msgq_contents(&msgq, 2, 3, 4, 9);
	zassert_equal(arch_thread_return_value_set_fake.call_count, 1);
	zassert_equal_ptr(arch_thread_return_value_set_fake.arg0_val, &other_thread);
	zassert_equal(arch_thread_return_value_set_fake.arg1_val, 0U);
	zassert_equal(z_sched_ready_locked_fake.call_count, 1);
	zassert_equal_ptr(z_sched_ready_locked_fake.arg0_val, &other_thread);
}

/**
 * @brief k_msgq_get() puts the message of the writer into the ring buffer before the writer
 * becomes ready.
 *
 * @details
 * - Setup: a full message queue. A writer waits with message 9.
 * - Action: k_msgq_get().
 * - Expected: when z_sched_ready_locked() is called, @c used_msgs is
 *   MAX_MSGS again. arch_thread_return_value_set() comes before
 *   z_sched_ready_locked().
 *
 * @ingroup kernel_unit_msgq_k_msgq_get
 * @see z_impl_k_msgq_get()
 */
ZTEST(msgq_unit, test_handover_get_readies_writer_after_copy)
{
	struct k_msgq msgq;
	struct msg m;

	msgq_prepare(&msgq);
	put_msgs(&msgq, 1, MAX_MSGS);
	set_waiting_writer(9);

	zassert_equal(z_impl_k_msgq_get(&msgq, &m, K_NO_WAIT), 0);

	zassert_equal(used_at_ready, MAX_MSGS);
	zassert_called_before(arch_thread_return_value_set, z_sched_ready_locked);
}

/**
 * @brief When k_msgq_get() puts the message of a writer into the last slot, it moves the write
 * pointer to the start.
 *
 * @details
 * - Setup: a full message queue with the head at the last slot, so
 *   @c write_ptr is the last slot. A writer waits with message 9.
 * - Action: k_msgq_get().
 * - Expected: message 9 is in the last slot, and @c write_ptr is slot 0. The
 *   message queue has 2, 3, 4, 9. The guard slot keeps the pattern.
 *
 * @ingroup kernel_unit_msgq_k_msgq_get
 * @see z_impl_k_msgq_get()
 */
ZTEST(msgq_unit, test_handover_get_wraps_write_pointer)
{
	struct k_msgq msgq;
	struct msg m;

	msgq_prepare(&msgq);
	msgq_start_at(&msgq, MAX_MSGS - 1U);
	put_msgs(&msgq, 1, MAX_MSGS);
	zassert_equal_ptr(msgq.write_ptr, SLOT(MAX_MSGS - 1U));
	set_waiting_writer(9);

	zassert_equal(z_impl_k_msgq_get(&msgq, &m, K_NO_WAIT), 0);

	zassert_msg(SLOT(MAX_MSGS - 1U), 9);
	zassert_equal_ptr(msgq.write_ptr, SLOT(0));
	zassert_msgq_contents(&msgq, 2, 3, 4, 9);
}

/**
 * @brief The message that k_msgq_get() takes from a waiting writer is the message that the
 * k_msgq_put() of the writer gave as swap data.
 *
 * @details
 * Model of both sides: the writer calls k_msgq_put() on a full message
 * queue, and the fake z_pend_curr() records its swap data. Then the test
 * makes the current thread the waiting thread, and a reader calls
 * k_msgq_get().
 * - Setup: a full message queue (1 to 4).
 * - Action: k_msgq_put() of message 7 with K_FOREVER, then k_msgq_get().
 * - Expected: the reader gets message 1. The message queue has 2, 3, 4, 7.
 *
 * @ingroup kernel_unit_msgq_k_msgq_put
 * @see z_impl_k_msgq_put(), z_impl_k_msgq_get()
 */
ZTEST(msgq_unit, test_handover_put_message_reaches_queue_via_get)
{
	struct k_msgq msgq;
	struct msg w = make_msg(7);
	struct msg m;

	msgq_prepare(&msgq);
	put_msgs(&msgq, 1, MAX_MSGS);

	(void)z_impl_k_msgq_put(&msgq, &w, K_FOREVER);
	zassert_equal_ptr(current_thread.base.swap_data, &w);
	waiting_thread = &current_thread;
	zassert_equal(z_impl_k_msgq_get(&msgq, &m, K_NO_WAIT), 0);

	zassert_msg(&m, 1);
	zassert_msgq_contents(&msgq, 2, 3, 4, 7);
}

/**
 * @brief If no writer waits, k_msgq_get() does not make a thread ready.
 *
 * @details
 * - Setup: a message queue with message 1. No thread waits.
 * - Action: k_msgq_get().
 * - Expected: one call of z_unpend_first_thread_locked() with the wait
 *   queue, which returns NULL. No call of arch_thread_return_value_set() or
 *   z_sched_ready_locked().
 *
 * @ingroup kernel_unit_msgq_k_msgq_get
 * @see z_impl_k_msgq_get()
 */
ZTEST(msgq_unit, test_handover_get_no_writer)
{
	struct k_msgq msgq;
	struct msg m;

	msgq_prepare(&msgq);
	put_msgs(&msgq, 1, 1);

	zassert_equal(z_impl_k_msgq_get(&msgq, &m, K_NO_WAIT), 0);

	zassert_equal(z_unpend_first_thread_locked_fake.call_count, 1);
	zassert_equal_ptr(z_unpend_first_thread_locked_fake.arg0_val, &msgq.wait_q);
	zassert_equal(arch_thread_return_value_set_fake.call_count, 0);
	zassert_equal(z_sched_ready_locked_fake.call_count, 0);
}

/*
 * Tests: Poll events. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_msgq, at the top of this file.
 */

/**
 * @brief With CONFIG_POLL, k_msgq_put() signals K_POLL_STATE_MSGQ_DATA_AVAILABLE after the message
 * is in the ring buffer.
 *
 * @details
 * - Setup: an empty message queue. No reader waits.
 * - Action: k_msgq_put() of message 1.
 * - Expected: one call of z_handle_obj_poll_events() with the poll events of
 *   the message queue and K_POLL_STATE_MSGQ_DATA_AVAILABLE. At this call,
 *   @c used_msgs is 1. The lock is held.
 *
 * @ingroup kernel_unit_msgq_k_msgq_put
 * @see z_impl_k_msgq_put(), msgq_handle_poll_events()
 */
ZTEST(msgq_unit, test_poll_put_signals_data_available)
{
	struct k_msgq msgq;
	struct msg m = make_msg(1);

	if (!IS_ENABLED(CONFIG_POLL)) {
		ztest_test_skip();
	}

	msgq_prepare(&msgq);

	zassert_equal(z_impl_k_msgq_put(&msgq, &m, K_NO_WAIT), 0);

	zassert_equal(z_handle_obj_poll_events_fake.call_count, 1);
#ifdef CONFIG_POLL
	zassert_equal_ptr(z_handle_obj_poll_events_fake.arg0_val, &msgq.poll_events);
	zassert_equal(z_handle_obj_poll_events_fake.arg1_val, K_POLL_STATE_MSGQ_DATA_AVAILABLE);
#endif
	zassert_equal(used_at_poll, 1U);
	zassert_equal(depth_at_poll, 1U);
}

/**
 * @brief With CONFIG_POLL, k_msgq_put_front() also signals K_POLL_STATE_MSGQ_DATA_AVAILABLE after
 * the message is in the ring buffer.
 *
 * @details
 * - Setup: a message queue with message 1. No reader waits.
 * - Action: k_msgq_put_front() of message 2.
 * - Expected: one call of z_handle_obj_poll_events(). At this call,
 *   @c used_msgs is 2.
 *
 * @ingroup kernel_unit_msgq_k_msgq_put_front
 * @see z_impl_k_msgq_put_front(), msgq_handle_poll_events()
 */
ZTEST(msgq_unit, test_poll_put_front_signals_data_available)
{
	struct k_msgq msgq;
	struct msg m = make_msg(2);

	if (!IS_ENABLED(CONFIG_POLL)) {
		ztest_test_skip();
	}

	msgq_prepare(&msgq);
	put_msgs(&msgq, 1, 1);

	zassert_equal(z_impl_k_msgq_put_front(&msgq, &m), 0);

	zassert_equal(z_handle_obj_poll_events_fake.call_count, 1);
	zassert_equal(used_at_poll, 2U);
}

/**
 * @brief If a put gives the message to a waiting reader, it does not signal the poll events.
 *
 * @details
 * - Setup: an empty message queue. A reader waits.
 * - Action: k_msgq_put() of message 1.
 * - Expected: no call of z_handle_obj_poll_events().
 *
 * @ingroup kernel_unit_msgq_k_msgq_put
 * @see z_impl_k_msgq_put(), put_msg_in_queue()
 */
ZTEST(msgq_unit, test_poll_handover_does_not_signal)
{
	struct k_msgq msgq;
	struct msg m = make_msg(1);

	msgq_prepare(&msgq);
	set_waiting_reader();

	zassert_equal(z_impl_k_msgq_put(&msgq, &m, K_NO_WAIT), 0);

	zassert_equal(z_handle_obj_poll_events_fake.call_count, 0);
}

/**
 * @brief A put to a full message queue does not signal the poll events.
 *
 * @details
 * - Setup: a full message queue.
 * - Action: k_msgq_put() with K_NO_WAIT, k_msgq_put() with K_FOREVER,
 *   k_msgq_put_front().
 * - Expected: no call of z_handle_obj_poll_events().
 *
 * @ingroup kernel_unit_msgq_k_msgq_put
 * @see z_impl_k_msgq_put(), z_impl_k_msgq_put_front()
 */
ZTEST(msgq_unit, test_poll_full_put_does_not_signal)
{
	struct k_msgq msgq;
	struct msg m = make_msg(9);

	msgq_prepare(&msgq);
	put_msgs(&msgq, 1, MAX_MSGS);

	(void)z_impl_k_msgq_put(&msgq, &m, K_NO_WAIT);
	(void)z_impl_k_msgq_put(&msgq, &m, K_FOREVER);
	(void)z_impl_k_msgq_put_front(&msgq, &m);

	zassert_equal(z_handle_obj_poll_events_fake.call_count, 0);
}

/**
 * @brief k_msgq_get(), k_msgq_peek(), k_msgq_peek_at() and k_msgq_purge() do not signal the poll
 * events.
 *
 * @details
 * - Setup: a full message queue. A writer waits.
 * - Action: k_msgq_peek(), k_msgq_peek_at(), k_msgq_get() (which takes the
 *   message of the writer), k_msgq_purge().
 * - Expected: no call of z_handle_obj_poll_events().
 *
 * @ingroup kernel_unit_msgq_k_msgq_get
 * @see z_impl_k_msgq_get(), z_impl_k_msgq_peek(), z_impl_k_msgq_peek_at(),
 * z_impl_k_msgq_purge()
 */
ZTEST(msgq_unit, test_poll_read_operations_do_not_signal)
{
	struct k_msgq msgq;
	struct msg m;

	msgq_prepare(&msgq);
	put_msgs(&msgq, 1, MAX_MSGS);
	set_waiting_writer(9);

	zassert_equal(z_impl_k_msgq_peek(&msgq, &m), 0);
	zassert_equal(z_impl_k_msgq_peek_at(&msgq, &m, 1), 0);
	zassert_equal(z_impl_k_msgq_get(&msgq, &m, K_NO_WAIT), 0);
	z_impl_k_msgq_purge(&msgq);

	zassert_equal(z_handle_obj_poll_events_fake.call_count, 0);
}

#ifndef CONFIG_POLL
/**
 * @brief Without CONFIG_POLL, a put does not call the poll subsystem.
 *
 * @details
 * - Setup: an empty message queue.
 * - Action: k_msgq_put(), k_msgq_put_front().
 * - Expected: no call of z_handle_obj_poll_events(). Each releases the lock
 *   with k_spin_unlock().
 *
 * @ingroup kernel_unit_msgq_static
 * @see msgq_handle_poll_events()
 */
ZTEST(msgq_unit, test_poll_disabled_no_signal)
{
	struct k_msgq msgq;
	struct msg m = make_msg(1);

	msgq_prepare(&msgq);

	zassert_equal(z_impl_k_msgq_put(&msgq, &m, K_NO_WAIT), 0);
	zassert_equal(z_impl_k_msgq_put_front(&msgq, &m), 0);

	zassert_equal(z_handle_obj_poll_events_fake.call_count, 0);
	zassert_equal(z_reschedule_fake.call_count, 0);
	zassert_equal(unit_arch_irq_unlock_fake.call_count, 2U + (SCHED_LOCK_ENABLED ? 2U : 0U));
}
#endif /* CONFIG_POLL */

/*
 * Tests: Locking. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_msgq, at the top of this file.
 */

/**
 * @brief If a put makes no thread ready, it releases the lock with k_spin_unlock().
 *
 * @details
 * - Setup: an empty message queue. No reader waits. No polling thread
 *   becomes ready.
 * - Action: k_msgq_put() of message 1.
 * - Expected calls: arch_is_in_isr() (with CONFIG_ASSERT), arch_irq_lock(),
 *   the scheduler spinlock section (with more than one CPU) around
 *   z_unpend_first_thread_locked(), z_handle_obj_poll_events() (with
 *   CONFIG_POLL), arch_irq_unlock() with the key.
 *
 * @ingroup kernel_unit_msgq_k_msgq_put
 * @see z_impl_k_msgq_put(), put_msg_in_queue()
 */
ZTEST(msgq_unit, test_lock_put_no_ready_thread_unlocks)
{
	struct k_msgq msgq;
	struct msg m = make_msg(1);

	msgq_prepare(&msgq);

	zassert_equal(z_impl_k_msgq_put(&msgq, &m, K_NO_WAIT), 0);

	zassert_call_history(ISR_CHECK_CALL, unit_arch_irq_lock,
			     SCHED_LOCK_CALL(unit_arch_irq_lock), z_unpend_first_thread_locked,
			     SCHED_LOCK_CALL(unit_arch_irq_unlock), POLL_CALL,
			     unit_arch_irq_unlock);
	assert_lock_released_once(&msgq, KERNEL_UNIT_RELEASED_BY_UNLOCK, 1);
}

/**
 * @brief If a put gives the message to a waiting reader, it releases the lock with z_reschedule().
 *
 * @details
 * - Setup: an empty message queue. A reader waits.
 * - Action: k_msgq_put() of message 1.
 * - Expected calls: arch_is_in_isr() (with CONFIG_ASSERT), arch_irq_lock(),
 *   in the scheduler spinlock section: z_unpend_first_thread_locked(),
 *   arch_thread_return_value_set(), z_sched_ready_locked(); then
 *   z_reschedule() with the lock of the message queue and the key.
 *
 * @ingroup kernel_unit_msgq_k_msgq_put
 * @see z_impl_k_msgq_put(), put_msg_in_queue()
 */
ZTEST(msgq_unit, test_lock_put_handover_reschedules)
{
	struct k_msgq msgq;
	struct msg m = make_msg(1);

	msgq_prepare(&msgq);
	set_waiting_reader();

	zassert_equal(z_impl_k_msgq_put(&msgq, &m, K_NO_WAIT), 0);

	zassert_call_history(ISR_CHECK_CALL, unit_arch_irq_lock,
			     SCHED_LOCK_CALL(unit_arch_irq_lock), z_unpend_first_thread_locked,
			     arch_thread_return_value_set, z_sched_ready_locked,
			     SCHED_LOCK_CALL(unit_arch_irq_unlock), z_reschedule);
	assert_lock_released_once(&msgq, KERNEL_UNIT_RELEASED_BY_RESCHEDULE, 1);
}

/**
 * @brief With CONFIG_POLL, if a put makes a polling thread ready, it releases the lock with
 * z_reschedule().
 *
 * @details
 * - Setup: an empty message queue. No reader waits. z_handle_obj_poll_events()
 *   returns true.
 * - Action: k_msgq_put() of message 1.
 * - Expected calls: as for a put without a ready thread, but the release is
 *   z_reschedule() with the lock and the key.
 *
 * @ingroup kernel_unit_msgq_k_msgq_put
 * @see z_impl_k_msgq_put(), put_msg_in_queue()
 */
ZTEST(msgq_unit, test_lock_put_poll_ready_reschedules)
{
	struct k_msgq msgq;
	struct msg m = make_msg(1);

	if (!IS_ENABLED(CONFIG_POLL)) {
		ztest_test_skip();
	}

	msgq_prepare(&msgq);
	poll_result = true;

	zassert_equal(z_impl_k_msgq_put(&msgq, &m, K_NO_WAIT), 0);

	zassert_call_history(ISR_CHECK_CALL, unit_arch_irq_lock,
			     SCHED_LOCK_CALL(unit_arch_irq_lock), z_unpend_first_thread_locked,
			     SCHED_LOCK_CALL(unit_arch_irq_unlock), z_handle_obj_poll_events,
			     z_reschedule);
	assert_lock_released_once(&msgq, KERNEL_UNIT_RELEASED_BY_RESCHEDULE, 1);
}

/**
 * @brief If the ring buffer is full and the timeout is K_NO_WAIT, a put releases the lock with
 * k_spin_unlock() and does not lock the scheduler spinlock.
 *
 * @details
 * - Setup: a full message queue.
 * - Action: k_msgq_put() with K_NO_WAIT, then k_msgq_put_front().
 * - Expected calls for each: arch_is_in_isr() (with CONFIG_ASSERT),
 *   arch_irq_lock(), arch_irq_unlock() with the key.
 *
 * @ingroup kernel_unit_msgq_k_msgq_put
 * @see z_impl_k_msgq_put(), z_impl_k_msgq_put_front()
 */
ZTEST(msgq_unit, test_lock_put_full_unlocks)
{
	struct k_msgq msgq;
	struct msg m = make_msg(9);

	msgq_prepare(&msgq);
	put_msgs(&msgq, 1, MAX_MSGS);

	zassert_equal(z_impl_k_msgq_put(&msgq, &m, K_NO_WAIT), -ENOMSG);

	zassert_call_history(ISR_CHECK_CALL, unit_arch_irq_lock, unit_arch_irq_unlock);
	assert_lock_released_once(&msgq, KERNEL_UNIT_RELEASED_BY_UNLOCK, 0);

	reset_history();
	zassert_equal(z_impl_k_msgq_put_front(&msgq, &m), -ENOMSG);

	zassert_call_history(ISR_CHECK_CALL, unit_arch_irq_lock, unit_arch_irq_unlock);
	assert_lock_released_once(&msgq, KERNEL_UNIT_RELEASED_BY_UNLOCK, 0);
}

/**
 * @brief If a put waits, z_pend_curr() releases the lock, and the put does not release it again.
 *
 * @details
 * - Setup: a full message queue.
 * - Action: k_msgq_put() with TEST_TIMEOUT.
 * - Expected calls: arch_is_in_isr() (with CONFIG_ASSERT), arch_irq_lock(),
 *   z_pend_curr() with the lock of the message queue and the key.
 *
 * @ingroup kernel_unit_msgq_k_msgq_put
 * @see z_impl_k_msgq_put(), put_msg_in_queue()
 */
ZTEST(msgq_unit, test_lock_put_wait_releases_in_pend)
{
	struct k_msgq msgq;
	struct msg m = make_msg(9);

	msgq_prepare(&msgq);
	put_msgs(&msgq, 1, MAX_MSGS);

	(void)z_impl_k_msgq_put(&msgq, &m, TEST_TIMEOUT);

	zassert_call_history(ISR_CHECK_CALL, unit_arch_irq_lock, z_pend_curr);
	assert_lock_released_once(&msgq, KERNEL_UNIT_RELEASED_BY_PEND, 0);
}

/**
 * @brief k_msgq_put_front() has the same lock paths as k_msgq_put().
 *
 * @details
 * - Setup: an empty message queue.
 * - Action: k_msgq_put_front() without a waiting reader, then with a
 *   waiting reader.
 * - Expected: the first call releases the lock with k_spin_unlock(), the
 *   second with z_reschedule(). Both lock the scheduler spinlock section
 *   once (with more than one CPU).
 *
 * @ingroup kernel_unit_msgq_k_msgq_put_front
 * @see z_impl_k_msgq_put_front(), put_msg_in_queue()
 */
ZTEST(msgq_unit, test_lock_put_front_paths)
{
	struct k_msgq msgq;
	struct msg m = make_msg(1);

	msgq_prepare(&msgq);

	zassert_equal(z_impl_k_msgq_put_front(&msgq, &m), 0);
	assert_lock_released_once(&msgq, KERNEL_UNIT_RELEASED_BY_UNLOCK, 1);

	msgq_prepare(&msgq);
	reset_history();
	set_waiting_reader();
	zassert_equal(z_impl_k_msgq_put_front(&msgq, &m), 0);
	assert_lock_released_once(&msgq, KERNEL_UNIT_RELEASED_BY_RESCHEDULE, 1);
}

/**
 * @brief If a get takes a message and no writer waits, it releases the lock with k_spin_unlock().
 *
 * @details
 * - Setup: a message queue with message 1. No thread waits.
 * - Action: k_msgq_get().
 * - Expected calls: arch_is_in_isr() (with CONFIG_ASSERT), arch_irq_lock(),
 *   the scheduler spinlock section around z_unpend_first_thread_locked(),
 *   arch_irq_unlock() with the key.
 *
 * @ingroup kernel_unit_msgq_k_msgq_get
 * @see z_impl_k_msgq_get()
 */
ZTEST(msgq_unit, test_lock_get_no_writer_unlocks)
{
	struct k_msgq msgq;
	struct msg m;

	msgq_prepare(&msgq);
	put_msgs(&msgq, 1, 1);

	zassert_equal(z_impl_k_msgq_get(&msgq, &m, K_NO_WAIT), 0);

	zassert_call_history(ISR_CHECK_CALL, unit_arch_irq_lock,
			     SCHED_LOCK_CALL(unit_arch_irq_lock), z_unpend_first_thread_locked,
			     SCHED_LOCK_CALL(unit_arch_irq_unlock), unit_arch_irq_unlock);
	assert_lock_released_once(&msgq, KERNEL_UNIT_RELEASED_BY_UNLOCK, 1);
}

/**
 * @brief If a get gives the free slot to a waiting writer, it releases the lock with
 * z_reschedule().
 *
 * @details
 * - Setup: a full message queue. A writer waits.
 * - Action: k_msgq_get().
 * - Expected calls: arch_is_in_isr() (with CONFIG_ASSERT), arch_irq_lock(),
 *   in the scheduler spinlock section: z_unpend_first_thread_locked(),
 *   arch_thread_return_value_set(), z_sched_ready_locked(); then
 *   z_reschedule() with the lock and the key.
 *
 * @ingroup kernel_unit_msgq_k_msgq_get
 * @see z_impl_k_msgq_get()
 */
ZTEST(msgq_unit, test_lock_get_handover_reschedules)
{
	struct k_msgq msgq;
	struct msg m;

	msgq_prepare(&msgq);
	put_msgs(&msgq, 1, MAX_MSGS);
	set_waiting_writer(9);

	zassert_equal(z_impl_k_msgq_get(&msgq, &m, K_NO_WAIT), 0);

	zassert_call_history(ISR_CHECK_CALL, unit_arch_irq_lock,
			     SCHED_LOCK_CALL(unit_arch_irq_lock), z_unpend_first_thread_locked,
			     arch_thread_return_value_set, z_sched_ready_locked,
			     SCHED_LOCK_CALL(unit_arch_irq_unlock), z_reschedule);
	assert_lock_released_once(&msgq, KERNEL_UNIT_RELEASED_BY_RESCHEDULE, 1);
}

/**
 * @brief If a get finds no message and the timeout is K_NO_WAIT, it releases the lock with
 * k_spin_unlock() and does not lock the scheduler spinlock.
 *
 * @details
 * - Setup: an empty message queue.
 * - Action: k_msgq_get() with K_NO_WAIT.
 * - Expected calls: arch_is_in_isr() (with CONFIG_ASSERT), arch_irq_lock(),
 *   arch_irq_unlock() with the key.
 *
 * @ingroup kernel_unit_msgq_k_msgq_get
 * @see z_impl_k_msgq_get()
 */
ZTEST(msgq_unit, test_lock_get_empty_unlocks)
{
	struct k_msgq msgq;
	struct msg m;

	msgq_prepare(&msgq);

	zassert_equal(z_impl_k_msgq_get(&msgq, &m, K_NO_WAIT), -ENOMSG);

	zassert_call_history(ISR_CHECK_CALL, unit_arch_irq_lock, unit_arch_irq_unlock);
	assert_lock_released_once(&msgq, KERNEL_UNIT_RELEASED_BY_UNLOCK, 0);
}

/**
 * @brief If a get waits, z_pend_curr() releases the lock, and the get does not release it again.
 *
 * @details
 * - Setup: an empty message queue.
 * - Action: k_msgq_get() with TEST_TIMEOUT.
 * - Expected calls: arch_is_in_isr() (with CONFIG_ASSERT), arch_irq_lock(),
 *   z_pend_curr() with the lock and the key.
 *
 * @ingroup kernel_unit_msgq_k_msgq_get
 * @see z_impl_k_msgq_get()
 */
ZTEST(msgq_unit, test_lock_get_wait_releases_in_pend)
{
	struct k_msgq msgq;
	struct msg m;

	msgq_prepare(&msgq);

	(void)z_impl_k_msgq_get(&msgq, &m, TEST_TIMEOUT);

	zassert_call_history(ISR_CHECK_CALL, unit_arch_irq_lock, z_pend_curr);
	assert_lock_released_once(&msgq, KERNEL_UNIT_RELEASED_BY_PEND, 0);
}

/**
 * @brief k_msgq_peek() and k_msgq_peek_at() release the lock with k_spin_unlock() on each path.
 *
 * @details
 * - Setup: a message queue with message 1.
 * - Action: k_msgq_peek(), k_msgq_peek_at() with the index 0, then both on
 *   an empty message queue.
 * - Expected calls for each: arch_irq_lock(), arch_irq_unlock() with the
 *   key. No ISR check: the peek functions never wait.
 *
 * @ingroup kernel_unit_msgq_k_msgq_peek
 * @see z_impl_k_msgq_peek(), z_impl_k_msgq_peek_at()
 */
ZTEST(msgq_unit, test_lock_peek_unlocks)
{
	struct k_msgq msgq;
	struct msg m;

	msgq_prepare(&msgq);
	put_msgs(&msgq, 1, 1);

	zassert_equal(z_impl_k_msgq_peek(&msgq, &m), 0);
	zassert_call_history(unit_arch_irq_lock, unit_arch_irq_unlock);
	assert_lock_released_once(&msgq, KERNEL_UNIT_RELEASED_BY_UNLOCK, 0);

	reset_history();
	zassert_equal(z_impl_k_msgq_peek_at(&msgq, &m, 0), 0);
	zassert_call_history(unit_arch_irq_lock, unit_arch_irq_unlock);
	assert_lock_released_once(&msgq, KERNEL_UNIT_RELEASED_BY_UNLOCK, 0);

	msgq_prepare(&msgq);
	reset_history();
	zassert_equal(z_impl_k_msgq_peek(&msgq, &m), -ENOMSG);
	assert_lock_released_once(&msgq, KERNEL_UNIT_RELEASED_BY_UNLOCK, 0);

	reset_history();
	zassert_equal(z_impl_k_msgq_peek_at(&msgq, &m, 0), -ENOMSG);
	assert_lock_released_once(&msgq, KERNEL_UNIT_RELEASED_BY_UNLOCK, 0);
}

/**
 * @brief If k_msgq_purge() wakes no thread, it releases the lock with k_spin_unlock().
 *
 * @details
 * - Setup: a message queue with message 1. No thread waits.
 * - Action: k_msgq_purge().
 * - Expected calls: arch_irq_lock(), z_sched_wake() (returns false),
 *   arch_irq_unlock() with the key.
 *
 * @ingroup kernel_unit_msgq_k_msgq_purge
 * @see z_impl_k_msgq_purge()
 */
ZTEST(msgq_unit, test_lock_purge_no_waiter_unlocks)
{
	struct k_msgq msgq;

	msgq_prepare(&msgq);
	put_msgs(&msgq, 1, 1);

	z_impl_k_msgq_purge(&msgq);

	zassert_call_history(unit_arch_irq_lock, z_sched_wake, unit_arch_irq_unlock);
	assert_lock_released_once(&msgq, KERNEL_UNIT_RELEASED_BY_UNLOCK, 0);
}

/**
 * @brief If k_msgq_purge() wakes threads, it releases the lock once with z_reschedule() after the
 * last wake.
 *
 * @details
 * - Setup: a full message queue. Two writers wait.
 * - Action: k_msgq_purge().
 * - Expected calls: arch_irq_lock(), z_sched_wake() three times,
 *   z_reschedule() with the lock and the key.
 *
 * @ingroup kernel_unit_msgq_k_msgq_purge
 * @see z_impl_k_msgq_purge()
 */
ZTEST(msgq_unit, test_lock_purge_waiters_reschedules)
{
	struct k_msgq msgq;

	msgq_prepare(&msgq);
	put_msgs(&msgq, 1, MAX_MSGS);
	kernel_unit_set_waiting_threads(2);

	z_impl_k_msgq_purge(&msgq);

	zassert_call_history(unit_arch_irq_lock, z_sched_wake, z_sched_wake, z_sched_wake,
			     z_reschedule);
	assert_lock_released_once(&msgq, KERNEL_UNIT_RELEASED_BY_RESCHEDULE, 0);
}

/* The wait queue check of z_msgq_cleanup() (not with CONFIG_NO_RUNTIME_CHECKS) */
#define CLEANUP_CHECK_CALL(fn) COND_CODE_1(CONFIG_NO_RUNTIME_CHECKS, (NULL), (fn))

/**
 * @brief z_msgq_cleanup() checks the wait queue and frees the buffer while the lock is held, and
 * releases the lock with k_spin_unlock().
 *
 * @details
 * - Setup: an allocated message queue. No thread waits.
 * - Action: k_msgq_cleanup(), then z_msgq_cleanup() with @c locked true on
 *   a new allocated message queue.
 * - Expected calls of each: arch_irq_lock(), z_waitq_head() or
 *   z_waitq_head_locked() (not with CONFIG_NO_RUNTIME_CHECKS), k_free(),
 *   arch_irq_unlock() with the key. At the call of k_free(), the lock is
 *   held.
 *
 * @ingroup kernel_unit_msgq_k_msgq_cleanup
 * @see k_msgq_cleanup(), z_msgq_cleanup()
 */
ZTEST(msgq_unit, test_lock_cleanup_frees_under_lock)
{
	struct k_msgq msgq;

	msgq_prepare_alloc(&msgq);

	zassert_equal(k_msgq_cleanup(&msgq), 0);

	zassert_call_history(unit_arch_irq_lock, CLEANUP_CHECK_CALL(z_waitq_head), k_free,
			     unit_arch_irq_unlock);
	assert_lock_released_once(&msgq, KERNEL_UNIT_RELEASED_BY_UNLOCK, 0);
	zassert_equal(depth_at_free, 1U);

	msgq_prepare_alloc(&msgq);
	reset_history();

	zassert_equal(z_msgq_cleanup(&msgq, true), 0);

	zassert_call_history(unit_arch_irq_lock, CLEANUP_CHECK_CALL(z_waitq_head_locked), k_free,
			     unit_arch_irq_unlock);
	assert_lock_released_once(&msgq, KERNEL_UNIT_RELEASED_BY_UNLOCK, 0);
	zassert_equal(depth_at_free, 1U);
}

/**
 * @brief If a thread waits, z_msgq_cleanup() releases the lock with k_spin_unlock() and does not
 * free.
 *
 * @details
 * - Setup: an allocated message queue. z_waitq_head() and
 *   z_waitq_head_locked() return a thread.
 * - Action: k_msgq_cleanup(), then z_msgq_cleanup() with @c locked true.
 * - Expected calls of the first: arch_irq_lock(), z_waitq_head(),
 *   arch_irq_unlock() with the key. Of the second: arch_irq_lock(),
 *   z_waitq_head_locked(), arch_irq_unlock() with the key.
 *
 * @ingroup kernel_unit_msgq_k_msgq_cleanup
 * @see k_msgq_cleanup(), z_msgq_cleanup()
 */
ZTEST(msgq_unit, test_lock_cleanup_busy_unlocks)
{
	struct k_msgq msgq;

	if (!IS_ENABLED(CONFIG_RUNTIME_ERROR_CHECKS)) {
		ztest_test_skip();
	}

	msgq_prepare_alloc(&msgq);
	z_waitq_head_fake.return_val = &other_thread;

	zassert_equal(k_msgq_cleanup(&msgq), -EBUSY);

	zassert_call_history(unit_arch_irq_lock, z_waitq_head, unit_arch_irq_unlock);
	assert_lock_released_once(&msgq, KERNEL_UNIT_RELEASED_BY_UNLOCK, 0);

	reset_history();
	z_waitq_head_locked_fake.return_val = &other_thread;

	zassert_equal(z_msgq_cleanup(&msgq, true), -EBUSY);

	zassert_call_history(unit_arch_irq_lock, z_waitq_head_locked, unit_arch_irq_unlock);
	assert_lock_released_once(&msgq, KERNEL_UNIT_RELEASED_BY_UNLOCK, 0);
}

/**
 * @brief k_msgq_init(), k_msgq_alloc_init(), k_msgq_get_attrs() and the static inline state
 * queries do not lock the message queue.
 *
 * @details
 * - Action: k_msgq_init(), k_msgq_alloc_init(), k_msgq_get_attrs(),
 *   k_msgq_num_free_get(), k_msgq_num_used_get().
 * - Expected: no call of arch_irq_lock().
 *
 * @ingroup kernel_unit_msgq_k_msgq_init
 * @see k_msgq_init(), z_impl_k_msgq_alloc_init(), z_impl_k_msgq_get_attrs()
 */
ZTEST(msgq_unit, test_lock_init_and_queries_do_not_lock)
{
	struct k_msgq msgq;
	struct k_msgq_attrs attrs;

	z_thread_malloc_fake.custom_fake = malloc_ring;

	k_msgq_init(&msgq, ring, MSG_SIZE, MAX_MSGS);
	zassert_equal(z_impl_k_msgq_alloc_init(&msgq, MSG_SIZE, MAX_MSGS), 0);
	z_impl_k_msgq_get_attrs(&msgq, &attrs);
	(void)z_impl_k_msgq_num_free_get(&msgq);
	(void)z_impl_k_msgq_num_used_get(&msgq);

	zassert_equal(unit_arch_irq_lock_fake.call_count, 0);
}

/**
 * @brief The operations change the number of messages only while they hold the lock.
 *
 * @details
 * - Setup: an empty message queue.
 * - Action: k_msgq_put() of message 1; k_msgq_get(); a full message queue
 *   and k_msgq_get() with a waiting writer; k_msgq_purge() of 2 messages.
 * - Expected: at the lock, the number of messages is the value before the
 *   operation. At the release, it is the value after the operation.
 *
 * @ingroup kernel_unit_msgq_k_msgq_put
 * @see z_impl_k_msgq_put(), z_impl_k_msgq_get(), z_impl_k_msgq_purge()
 */
ZTEST(msgq_unit, test_lock_state_changes_under_lock)
{
	struct k_msgq msgq;
	struct msg m = make_msg(1);

	msgq_prepare(&msgq);
	reset_history();
	zassert_equal(z_impl_k_msgq_put(&msgq, &m, K_NO_WAIT), 0);
	zassert_equal(used_at_lock, 0U);
	zassert_equal(used_at_release, 1U);

	reset_history();
	zassert_equal(z_impl_k_msgq_get(&msgq, &m, K_NO_WAIT), 0);
	zassert_equal(used_at_lock, 1U);
	zassert_equal(used_at_release, 0U);

	put_msgs(&msgq, 1, 2);
	z_impl_k_msgq_purge(&msgq);
	zassert_equal(used_at_lock, 2U);
	zassert_equal(used_at_release, 0U);
}

/**
 * @brief The hand-over runs while the lock of the message queue is held, and with more than one CPU
 * also the scheduler spinlock.
 *
 * @details
 * - Setup: an empty message queue with a waiting reader; a full message
 *   queue with a waiting writer.
 * - Action: k_msgq_put(), then k_msgq_get().
 * - Expected: at the calls of z_unpend_first_thread_locked() and
 *   z_sched_ready_locked(), the lock depth is 1 (one CPU) or 2 (more than
 *   one CPU). With CONFIG_SPIN_VALIDATE and more than one CPU, the second
 *   lock is @c _sched_spinlock.
 *
 * @ingroup kernel_unit_msgq_k_msgq_put
 * @see z_impl_k_msgq_put()
 * @see put_msg_in_queue(), z_impl_k_msgq_get()
 */
ZTEST(msgq_unit, test_lock_handover_under_locks)
{
	struct k_msgq msgq;
	struct msg m = make_msg(1);
	unsigned int depth = SCHED_LOCK_ENABLED ? 2U : 1U;

	msgq_prepare(&msgq);
	set_waiting_reader();
	zassert_equal(z_impl_k_msgq_put(&msgq, &m, K_NO_WAIT), 0);
	zassert_equal(depth_at_unpend, depth);
	zassert_equal(depth_at_ready, depth);
#ifdef CONFIG_SPIN_VALIDATE
	zassert_equal_ptr(z_spin_lock_valid_fake.arg0_history[0], &msgq.lock);
	if (SCHED_LOCK_ENABLED) {
		zassert_equal_ptr(z_spin_lock_valid_fake.arg0_history[1], &_sched_spinlock);
		zassert_equal_ptr(z_spin_unlock_valid_fake.arg0_history[0], &_sched_spinlock);
	}
#endif

	msgq_prepare(&msgq);
	put_msgs(&msgq, 1, MAX_MSGS);
	set_waiting_writer(9);
	zassert_equal(z_impl_k_msgq_get(&msgq, &m, K_NO_WAIT), 0);
	zassert_equal(depth_at_unpend, depth);
	zassert_equal(depth_at_ready, depth);
}

/**
 * @brief Each message queue has its own lock.
 *
 * @details
 * - Setup: two empty message queues.
 * - Action: k_msgq_get() with K_FOREVER on each.
 * - Expected: z_pend_curr() gets the lock of the first message queue, then
 *   the lock of the second. With CONFIG_SPIN_VALIDATE, the validation sees
 *   the two locks.
 *
 * @ingroup kernel_unit_msgq_k_msgq_get
 * @see z_impl_k_msgq_get()
 */
ZTEST(msgq_unit, test_lock_each_msgq_has_own_lock)
{
	struct k_msgq q1;
	struct k_msgq q2;
	struct msg m;

	msgq_prepare(&q1);
	msgq_prepare(&q2);

	(void)z_impl_k_msgq_get(&q1, &m, K_FOREVER);
	(void)z_impl_k_msgq_get(&q2, &m, K_FOREVER);

	zassert_equal(z_pend_curr_fake.call_count, 2);
	zassert_equal_ptr(z_pend_curr_fake.arg0_history[0], &q1.lock);
	zassert_equal_ptr(z_pend_curr_fake.arg0_history[1], &q2.lock);
	zassert_equal_ptr(z_pend_curr_fake.arg2_history[0], &q1.wait_q);
	zassert_equal_ptr(z_pend_curr_fake.arg2_history[1], &q2.wait_q);
#ifdef CONFIG_SPIN_VALIDATE
	zassert_equal_ptr(z_spin_lock_valid_fake.arg0_history[0], &q1.lock);
	zassert_equal_ptr(z_spin_lock_valid_fake.arg0_history[1], &q2.lock);
#endif
}

#ifdef CONFIG_SPIN_VALIDATE
/**
 * @brief With CONFIG_SPIN_VALIDATE, the spinlock validation sees the lock of the message queue on
 * lock and on unlock.
 *
 * @details
 * - Setup: a message queue with message 1.
 * - Action: k_msgq_peek().
 * - Expected: z_spin_lock_valid() with the lock of the message queue, and
 *   z_spin_unlock_valid() with the same lock.
 *
 * @ingroup kernel_unit_msgq_k_msgq_peek
 * @see z_impl_k_msgq_peek()
 */
ZTEST(msgq_unit, test_lock_spin_validate_sees_msgq_lock)
{
	struct k_msgq msgq;
	struct msg m;

	msgq_prepare(&msgq);
	put_msgs(&msgq, 1, 1);
	RESET_FAKE(z_spin_lock_valid);
	RESET_FAKE(z_spin_unlock_valid);
	z_spin_lock_valid_fake.return_val = true;
	z_spin_unlock_valid_fake.return_val = true;

	zassert_equal(z_impl_k_msgq_peek(&msgq, &m), 0);

	zassert_equal(z_spin_lock_valid_fake.call_count, 1);
	zassert_equal_ptr(z_spin_lock_valid_fake.arg0_val, &msgq.lock);
	zassert_equal(z_spin_unlock_valid_fake.call_count, 1);
	zassert_equal_ptr(z_spin_unlock_valid_fake.arg0_val, &msgq.lock);
}
#endif /* CONFIG_SPIN_VALIDATE */

#ifdef CONFIG_ASSERT
/*
 * Tests: Assertions. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_msgq, at the top of this file.
 */

/**
 * @brief With CONFIG_ASSERT, k_msgq_put() asserts that an ISR does not wait.
 *
 * @details
 * - Setup: an empty message queue. arch_is_in_isr() returns true.
 * - Action: k_msgq_put() with K_FOREVER, then with K_NO_WAIT.
 * - Expected: one failed assertion for the first call, before the lock. No
 *   failed assertion for the second call.
 *
 * @ingroup kernel_unit_msgq_k_msgq_put
 * @see z_impl_k_msgq_put(), put_msg_in_queue()
 */
ZTEST(msgq_unit, test_assert_put_isr_must_not_wait)
{
	struct k_msgq msgq;
	struct msg m = make_msg(1);

	msgq_prepare(&msgq);
	arch_is_in_isr_fake.return_val = true;

	zassert_equal(z_impl_k_msgq_put(&msgq, &m, K_FOREVER), 0);
	zassert_equal(assert_post_action_fake.call_count, 1);
	zassert_called_before(assert_post_action, unit_arch_irq_lock);

	zassert_equal(z_impl_k_msgq_put(&msgq, &m, K_NO_WAIT), 0);
	zassert_equal(assert_post_action_fake.call_count, 1);
}

/**
 * @brief With CONFIG_ASSERT, a thread can call k_msgq_put() and k_msgq_get() with a timeout.
 *
 * @details
 * - Setup: an empty message queue. arch_is_in_isr() returns false.
 * - Action: k_msgq_put() with K_FOREVER, k_msgq_get() with K_FOREVER.
 * - Expected: no failed assertion. Each call checks arch_is_in_isr() once.
 *
 * @ingroup kernel_unit_msgq_k_msgq_put
 * @see z_impl_k_msgq_put(), z_impl_k_msgq_get()
 */
ZTEST(msgq_unit, test_assert_thread_may_wait)
{
	struct k_msgq msgq;
	struct msg m = make_msg(1);

	msgq_prepare(&msgq);

	zassert_equal(z_impl_k_msgq_put(&msgq, &m, K_FOREVER), 0);
	zassert_equal(z_impl_k_msgq_get(&msgq, &m, K_FOREVER), 0);

	zassert_equal(assert_post_action_fake.call_count, 0);
	zassert_equal(arch_is_in_isr_fake.call_count, 2);
}

/**
 * @brief With CONFIG_ASSERT, k_msgq_get() asserts that an ISR does not wait.
 *
 * @details
 * - Setup: a message queue with message 1. arch_is_in_isr() returns true.
 * - Action: k_msgq_get() with TEST_TIMEOUT, then k_msgq_get() with
 *   K_NO_WAIT on the empty message queue.
 * - Expected: one failed assertion for the first call, before the lock. No
 *   failed assertion for the second call.
 *
 * @ingroup kernel_unit_msgq_k_msgq_get
 * @see z_impl_k_msgq_get()
 */
ZTEST(msgq_unit, test_assert_get_isr_must_not_wait)
{
	struct k_msgq msgq;
	struct msg m;

	msgq_prepare(&msgq);
	put_msgs(&msgq, 1, 1);
	arch_is_in_isr_fake.return_val = true;

	zassert_equal(z_impl_k_msgq_get(&msgq, &m, TEST_TIMEOUT), 0);
	zassert_equal(assert_post_action_fake.call_count, 1);
	zassert_called_before(assert_post_action, unit_arch_irq_lock);

	zassert_equal(z_impl_k_msgq_get(&msgq, &m, K_NO_WAIT), -ENOMSG);
	zassert_equal(assert_post_action_fake.call_count, 1);
}

/*
 * Make the write pointer of an empty message queue invalid for case n:
 * 0: before buffer_start (buffer_start moves to slot 1),
 * 1: at buffer_end (the guard slot of the test),
 * 2: less than one message before buffer_end.
 * A write at this pointer stays in the array of the test.
 */
static void set_bad_write_ptr(struct k_msgq *msgq, int n)
{
	switch (n) {
	case 0:
		msgq->buffer_start = SLOT(1);
		msgq->read_ptr = SLOT(1);
		msgq->write_ptr = SLOT(0);
		break;
	case 1:
		msgq->write_ptr = RING_END;
		break;
	default:
		msgq->write_ptr = RING_END - 1;
		break;
	}
}

/**
 * @brief With CONFIG_ASSERT, k_msgq_put() asserts that the write pointer is in the ring buffer,
 * with space for one message, before it writes.
 *
 * @details
 * - Setup: an empty message queue. @c write_ptr is before @c buffer_start,
 *   or at @c buffer_end, or less than one message before @c buffer_end (one
 *   case for each put).
 * - Action: k_msgq_put() of message 1.
 * - Expected: one failed assertion for each case. The fake hook returns, so
 *   the put writes at the bad pointer (in the memory of the test).
 *
 * @ingroup kernel_unit_msgq_k_msgq_put
 * @see z_impl_k_msgq_put()
 * @see put_msg_in_queue()
 */
ZTEST(msgq_unit, test_assert_put_write_pointer_in_buffer)
{
	struct k_msgq msgq;
	struct msg m = make_msg(1);

	for (int n = 0; n < 3; n++) {
		msgq_prepare(&msgq);
		set_bad_write_ptr(&msgq, n);

		zassert_equal(z_impl_k_msgq_put(&msgq, &m, K_NO_WAIT), 0);

		zassert_equal(assert_post_action_fake.call_count, n + 1, "case %d", n);
	}
}

/**
 * @brief With CONFIG_ASSERT, k_msgq_get() of a message asserts that the write pointer is in the
 * ring buffer, with space for one message.
 *
 * @details
 * - Setup: a message queue with message 1. Then @c write_ptr is made bad as
 *   in the put test (three cases). No writer waits.
 * - Action: k_msgq_get().
 * - Expected: for each case, return value 0, the caller has message 1, and
 *   one failed assertion.
 *
 * @ingroup kernel_unit_msgq_k_msgq_get
 * @see z_impl_k_msgq_get()
 */
ZTEST(msgq_unit, test_assert_get_write_pointer_in_buffer)
{
	struct k_msgq msgq;
	struct msg m;

	for (int n = 0; n < 3; n++) {
		msgq_prepare(&msgq);
		msgq_start_at(&msgq, 1);
		put_msgs(&msgq, 1, 1);
		set_bad_write_ptr(&msgq, n);
		msgq.read_ptr = SLOT(1);

		zassert_equal(z_impl_k_msgq_get(&msgq, &m, K_NO_WAIT), 0);

		zassert_msg(&m, 1);
		zassert_equal(assert_post_action_fake.call_count, n + 1, "case %d", n);
	}
}

/**
 * @brief With CONFIG_ASSERT, k_msgq_put() to a message queue with msg_size 0 asserts.
 *
 * @details
 * k_msgq_init() accepts msg_size 0. Then @c buffer_end is @c buffer_start,
 * and the write pointer check of the put fails.
 * - Setup: k_msgq_init() with msg_size 0 and MAX_MSGS.
 * - Action: k_msgq_put().
 * - Expected: no failed assertion in k_msgq_init(). One failed assertion in
 *   k_msgq_put(). The put continues, returns 0 and counts one message.
 *
 * @ingroup kernel_unit_msgq_k_msgq_put
 * @see z_impl_k_msgq_put()
 * @see k_msgq_init(), put_msg_in_queue()
 */
ZTEST(msgq_unit, test_assert_put_zero_message_size)
{
	struct k_msgq msgq;
	struct msg m = make_msg(1);

	k_msgq_init(&msgq, ring, 0U, MAX_MSGS);
	zassert_equal(assert_post_action_fake.call_count, 0);

	zassert_equal(z_impl_k_msgq_put(&msgq, &m, K_NO_WAIT), 0);

	zassert_equal(assert_post_action_fake.call_count, 1);
	zassert_equal(msgq.used_msgs, 1U);
}
#endif /* CONFIG_ASSERT */

#ifdef CONFIG_USERSPACE
/*
 * Tests: System call verification. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_msgq, at the top of this file.
 */

/* Make the object check pass and the memory check fail. */
static void fail_memory_check(void)
{
	kernel_unit_pass_object_check();
	arch_buffer_validate_fake.return_val = -EPERM;
}

/* Assert one object check of msgq with the type K_OBJ_MSGQ and init state, and no oops. */
static void assert_object_check(struct k_msgq *msgq, enum _obj_init_check init)
{
	kernel_unit_assert_object_check(msgq, K_OBJ_MSGQ, init);
}

/* Assert one memory check of ptr and size for a read (write 0) or a write (write 1). */
static void assert_memory_check(const void *ptr, size_t size, int write)
{
	zassert_equal(arch_buffer_validate_fake.call_count, 1);
	zassert_equal_ptr(arch_buffer_validate_fake.arg0_val, ptr);
	zassert_equal(arch_buffer_validate_fake.arg1_val, size);
	zassert_equal(arch_buffer_validate_fake.arg2_val, write);
	zassert_called_before(k_object_validation_check, arch_buffer_validate);
}

/* Assert one oops, before the first call of fn (the first change of the message queue). */
#define zassert_oops_before(fn)                                                                    \
	do {                                                                                       \
		zassert_equal(unit_syscall_oops_fake.call_count, 1);                               \
		zassert_called_before(unit_syscall_oops, fn);                                      \
	} while (false)

/**
 * @brief z_vrfy_k_msgq_alloc_init() checks that the pointer is a message queue object that is not
 * initialized, and then returns the result of z_impl_k_msgq_alloc_init().
 *
 * @details
 * - Setup: the object check passes. z_thread_malloc() gives the ring buffer.
 * - Action: z_vrfy_k_msgq_alloc_init() with MSG_SIZE and MAX_MSGS.
 * - Expected: return value 0. The object check with K_OBJ_MSGQ and
 *   _OBJ_INIT_FALSE, before z_thread_malloc() with MSG_SIZE * MAX_MSGS. No
 *   oops.
 *
 * @ingroup kernel_unit_msgq_k_msgq_alloc_init
 * @see z_vrfy_k_msgq_alloc_init()
 */
ZTEST(msgq_unit, test_syscall_alloc_init_checks_new_object)
{
	struct k_msgq msgq;

	kernel_unit_pass_object_check();
	z_thread_malloc_fake.custom_fake = malloc_ring;

	zassert_equal(z_vrfy_k_msgq_alloc_init(&msgq, MSG_SIZE, MAX_MSGS), 0);

	assert_object_check(&msgq, _OBJ_INIT_FALSE);
	zassert_called_before(k_object_validation_check, z_thread_malloc);
	zassert_equal(z_thread_malloc_fake.arg0_val, MSG_SIZE * MAX_MSGS);
	zassert_equal(msgq.flags, K_MSGQ_FLAG_ALLOC);
}

/**
 * @brief If the object check fails, z_vrfy_k_msgq_alloc_init() raises an oops before it allocates.
 *
 * @details
 * - Setup: the object check fails (for example, the message queue is
 *   already initialized).
 * - Action: z_vrfy_k_msgq_alloc_init().
 * - Expected: one oops, before z_thread_malloc().
 *
 * @ingroup kernel_unit_msgq_k_msgq_alloc_init
 * @see z_vrfy_k_msgq_alloc_init()
 */
ZTEST(msgq_unit, test_syscall_alloc_init_oops_on_bad_object)
{
	struct k_msgq msgq;

	kernel_unit_fail_object_check();

	(void)z_vrfy_k_msgq_alloc_init(&msgq, MSG_SIZE, MAX_MSGS);

	zassert_oops_before(z_thread_malloc);
}

/**
 * @brief z_vrfy_k_msgq_put() checks the object and that the thread can read msg_size bytes of the
 * message, and then returns the result of z_impl_k_msgq_put() with the same timeout.
 *
 * @details
 * - Setup: a full message queue. The checks pass.
 * - Action: z_vrfy_k_msgq_put() with TEST_TIMEOUT. The wait gives -EAGAIN.
 * - Expected: return value -EAGAIN. The object check with K_OBJ_MSGQ and
 *   _OBJ_INIT_TRUE, then the memory check of the message for MSG_SIZE bytes
 *   and read access, then the lock. z_pend_curr() gets TEST_TIMEOUT.
 *
 * @ingroup kernel_unit_msgq_k_msgq_put
 * @see z_vrfy_k_msgq_put()
 */
ZTEST(msgq_unit, test_syscall_put_checks_object_and_message)
{
	struct k_msgq msgq;
	struct msg m = make_msg(9);

	msgq_prepare(&msgq);
	put_msgs(&msgq, 1, MAX_MSGS);
	kernel_unit_pass_object_check();
	set_wait_result(-EAGAIN);

	zassert_equal(z_vrfy_k_msgq_put(&msgq, &m, TEST_TIMEOUT), -EAGAIN);

	assert_object_check(&msgq, _OBJ_INIT_TRUE);
	assert_memory_check(&m, MSG_SIZE, 0);
	zassert_called_before(arch_buffer_validate, unit_arch_irq_lock);
	zassert_true(K_TIMEOUT_EQ(z_pend_curr_fake.arg3_val, TEST_TIMEOUT));
}

/**
 * @brief If the object check fails, z_vrfy_k_msgq_put() raises an oops before it locks the message
 * queue.
 *
 * @details
 * - Setup: an empty message queue. The object check fails.
 * - Action: z_vrfy_k_msgq_put().
 * - Expected: an oops before arch_irq_lock().
 *
 * @ingroup kernel_unit_msgq_k_msgq_put
 * @see z_vrfy_k_msgq_put()
 */
ZTEST(msgq_unit, test_syscall_put_oops_on_bad_object)
{
	struct k_msgq msgq;
	struct msg m = make_msg(1);

	msgq_prepare(&msgq);
	kernel_unit_fail_object_check();

	(void)z_vrfy_k_msgq_put(&msgq, &m, K_NO_WAIT);

	zassert_called_before(unit_syscall_oops, unit_arch_irq_lock);
}

/**
 * @brief If the thread cannot read the message, z_vrfy_k_msgq_put() raises an oops before it locks
 * the message queue.
 *
 * @details
 * - Setup: an empty message queue. The object check passes, the memory check
 *   fails.
 * - Action: z_vrfy_k_msgq_put().
 * - Expected: one oops, before arch_irq_lock().
 *
 * @ingroup kernel_unit_msgq_k_msgq_put
 * @see z_vrfy_k_msgq_put()
 */
ZTEST(msgq_unit, test_syscall_put_oops_on_bad_message)
{
	struct k_msgq msgq;
	struct msg m = make_msg(1);

	msgq_prepare(&msgq);
	fail_memory_check();

	(void)z_vrfy_k_msgq_put(&msgq, &m, K_NO_WAIT);

	zassert_oops_before(unit_arch_irq_lock);
}

/**
 * @brief z_vrfy_k_msgq_put_front() checks the object and that the thread can read msg_size bytes
 * of the message, and then returns the result of z_impl_k_msgq_put_front().
 *
 * @details
 * - Setup: a message queue with message 1. The checks pass.
 * - Action: z_vrfy_k_msgq_put_front() of message 2.
 * - Expected: return value 0. The object check with K_OBJ_MSGQ and
 *   _OBJ_INIT_TRUE, then the memory check for MSG_SIZE bytes and read
 *   access, then the lock. The messages are 2, 1.
 *
 * @ingroup kernel_unit_msgq_k_msgq_put_front
 * @see z_vrfy_k_msgq_put_front()
 */
ZTEST(msgq_unit, test_syscall_put_front_checks_object_and_message)
{
	struct k_msgq msgq;
	struct msg m = make_msg(2);

	msgq_prepare(&msgq);
	put_msgs(&msgq, 1, 1);
	kernel_unit_pass_object_check();

	zassert_equal(z_vrfy_k_msgq_put_front(&msgq, &m), 0);

	assert_object_check(&msgq, _OBJ_INIT_TRUE);
	assert_memory_check(&m, MSG_SIZE, 0);
	zassert_called_before(arch_buffer_validate, unit_arch_irq_lock);
	zassert_msgq_contents(&msgq, 2, 1);
}

/**
 * @brief If the object check fails, z_vrfy_k_msgq_put_front() raises an oops before it locks the
 * message queue.
 *
 * @details
 * - Setup: an empty message queue. The object check fails.
 * - Action: z_vrfy_k_msgq_put_front().
 * - Expected: an oops before arch_irq_lock().
 *
 * @ingroup kernel_unit_msgq_k_msgq_put_front
 * @see z_vrfy_k_msgq_put_front()
 */
ZTEST(msgq_unit, test_syscall_put_front_oops_on_bad_object)
{
	struct k_msgq msgq;
	struct msg m = make_msg(1);

	msgq_prepare(&msgq);
	kernel_unit_fail_object_check();

	(void)z_vrfy_k_msgq_put_front(&msgq, &m);

	zassert_called_before(unit_syscall_oops, unit_arch_irq_lock);
}

/**
 * @brief If the thread cannot read the message, z_vrfy_k_msgq_put_front() raises an oops before it
 * locks the message queue.
 *
 * @details
 * - Setup: an empty message queue. The memory check fails.
 * - Action: z_vrfy_k_msgq_put_front().
 * - Expected: one oops, before arch_irq_lock().
 *
 * @ingroup kernel_unit_msgq_k_msgq_put_front
 * @see z_vrfy_k_msgq_put_front()
 */
ZTEST(msgq_unit, test_syscall_put_front_oops_on_bad_message)
{
	struct k_msgq msgq;
	struct msg m = make_msg(1);

	msgq_prepare(&msgq);
	fail_memory_check();

	(void)z_vrfy_k_msgq_put_front(&msgq, &m);

	zassert_oops_before(unit_arch_irq_lock);
}

/**
 * @brief z_vrfy_k_msgq_get_attrs() checks the object and that the thread can write the attribute
 * structure, and then calls z_impl_k_msgq_get_attrs().
 *
 * @details
 * - Setup: a message queue with 3 messages. The checks pass.
 * - Action: z_vrfy_k_msgq_get_attrs().
 * - Expected: the object check with K_OBJ_MSGQ and _OBJ_INIT_TRUE, then the
 *   memory check of the attributes for sizeof(struct k_msgq_attrs) bytes and
 *   write access. @c used_msgs of the attributes is 3.
 *
 * @ingroup kernel_unit_msgq_k_msgq_get_attrs
 * @see z_vrfy_k_msgq_get_attrs()
 */
ZTEST(msgq_unit, test_syscall_get_attrs_checks_object_and_attrs)
{
	struct k_msgq msgq;
	struct k_msgq_attrs attrs;

	msgq_prepare(&msgq);
	put_msgs(&msgq, 1, 3);
	kernel_unit_pass_object_check();

	z_vrfy_k_msgq_get_attrs(&msgq, &attrs);

	assert_object_check(&msgq, _OBJ_INIT_TRUE);
	assert_memory_check(&attrs, sizeof(struct k_msgq_attrs), 1);
	zassert_equal(attrs.used_msgs, 3U);
}

/**
 * @brief If the object check fails, z_vrfy_k_msgq_get_attrs() raises an oops.
 *
 * @details
 * - Setup: the object check fails.
 * - Action: z_vrfy_k_msgq_get_attrs().
 * - Expected: an oops, before the memory check.
 *
 * @ingroup kernel_unit_msgq_k_msgq_get_attrs
 * @see z_vrfy_k_msgq_get_attrs()
 */
ZTEST(msgq_unit, test_syscall_get_attrs_oops_on_bad_object)
{
	struct k_msgq msgq;
	struct k_msgq_attrs attrs;

	msgq_prepare(&msgq);
	kernel_unit_fail_object_check();

	z_vrfy_k_msgq_get_attrs(&msgq, &attrs);

	zassert_called_before(unit_syscall_oops, arch_buffer_validate);
}

/**
 * @brief If the thread cannot write the attribute structure, z_vrfy_k_msgq_get_attrs() raises an
 * oops.
 *
 * @details
 * - Setup: the memory check fails.
 * - Action: z_vrfy_k_msgq_get_attrs().
 * - Expected: one oops.
 *
 * @ingroup kernel_unit_msgq_k_msgq_get_attrs
 * @see z_vrfy_k_msgq_get_attrs()
 */
ZTEST(msgq_unit, test_syscall_get_attrs_oops_on_bad_attrs)
{
	struct k_msgq msgq;
	struct k_msgq_attrs attrs;

	msgq_prepare(&msgq);
	fail_memory_check();

	z_vrfy_k_msgq_get_attrs(&msgq, &attrs);

	zassert_equal(unit_syscall_oops_fake.call_count, 1);
	zassert_called_before(arch_buffer_validate, unit_syscall_oops);
}

/**
 * @brief z_vrfy_k_msgq_get() checks the object and that the thread can write msg_size bytes to the
 * buffer, and then returns the result of z_impl_k_msgq_get() with the same timeout.
 *
 * @details
 * - Setup: an empty message queue. The checks pass.
 * - Action: z_vrfy_k_msgq_get() with TEST_TIMEOUT. The wait gives -EAGAIN.
 * - Expected: return value -EAGAIN. The object check with K_OBJ_MSGQ and
 *   _OBJ_INIT_TRUE, then the memory check of the buffer for MSG_SIZE bytes
 *   and write access, then the lock. z_pend_curr() gets TEST_TIMEOUT.
 *
 * @ingroup kernel_unit_msgq_k_msgq_get
 * @see z_vrfy_k_msgq_get()
 */
ZTEST(msgq_unit, test_syscall_get_checks_object_and_buffer)
{
	struct k_msgq msgq;
	struct msg m;

	msgq_prepare(&msgq);
	kernel_unit_pass_object_check();
	set_wait_result(-EAGAIN);

	zassert_equal(z_vrfy_k_msgq_get(&msgq, &m, TEST_TIMEOUT), -EAGAIN);

	assert_object_check(&msgq, _OBJ_INIT_TRUE);
	assert_memory_check(&m, MSG_SIZE, 1);
	zassert_called_before(arch_buffer_validate, unit_arch_irq_lock);
	zassert_true(K_TIMEOUT_EQ(z_pend_curr_fake.arg3_val, TEST_TIMEOUT));
}

/**
 * @brief If the object check fails, z_vrfy_k_msgq_get() raises an oops before it locks the message
 * queue.
 *
 * @details
 * - Setup: an empty message queue. The object check fails.
 * - Action: z_vrfy_k_msgq_get().
 * - Expected: an oops before arch_irq_lock().
 *
 * @ingroup kernel_unit_msgq_k_msgq_get
 * @see z_vrfy_k_msgq_get()
 */
ZTEST(msgq_unit, test_syscall_get_oops_on_bad_object)
{
	struct k_msgq msgq;
	struct msg m;

	msgq_prepare(&msgq);
	kernel_unit_fail_object_check();

	(void)z_vrfy_k_msgq_get(&msgq, &m, K_NO_WAIT);

	zassert_called_before(unit_syscall_oops, unit_arch_irq_lock);
}

/**
 * @brief If the thread cannot write the buffer, z_vrfy_k_msgq_get() raises an oops before it locks
 * the message queue.
 *
 * @details
 * - Setup: an empty message queue. The memory check fails.
 * - Action: z_vrfy_k_msgq_get().
 * - Expected: one oops, before arch_irq_lock().
 *
 * @ingroup kernel_unit_msgq_k_msgq_get
 * @see z_vrfy_k_msgq_get()
 */
ZTEST(msgq_unit, test_syscall_get_oops_on_bad_buffer)
{
	struct k_msgq msgq;
	struct msg m;

	msgq_prepare(&msgq);
	fail_memory_check();

	(void)z_vrfy_k_msgq_get(&msgq, &m, K_NO_WAIT);

	zassert_oops_before(unit_arch_irq_lock);
}

/**
 * @brief z_vrfy_k_msgq_peek() checks the object and that the thread can write msg_size bytes to
 * the buffer, and then returns the result of z_impl_k_msgq_peek().
 *
 * @details
 * - Setup: a message queue with message 1. The checks pass.
 * - Action: z_vrfy_k_msgq_peek().
 * - Expected: return value 0, the caller has message 1. The object check
 *   with K_OBJ_MSGQ and _OBJ_INIT_TRUE, then the memory check for MSG_SIZE
 *   bytes and write access, then the lock.
 *
 * @ingroup kernel_unit_msgq_k_msgq_peek
 * @see z_vrfy_k_msgq_peek()
 */
ZTEST(msgq_unit, test_syscall_peek_checks_object_and_buffer)
{
	struct k_msgq msgq;
	struct msg m;

	msgq_prepare(&msgq);
	put_msgs(&msgq, 1, 1);
	kernel_unit_pass_object_check();

	zassert_equal(z_vrfy_k_msgq_peek(&msgq, &m), 0);

	zassert_msg(&m, 1);
	assert_object_check(&msgq, _OBJ_INIT_TRUE);
	assert_memory_check(&m, MSG_SIZE, 1);
	zassert_called_before(arch_buffer_validate, unit_arch_irq_lock);
}

/**
 * @brief If the object check fails, z_vrfy_k_msgq_peek() raises an oops before it locks the message
 * queue.
 *
 * @details
 * - Setup: the object check fails.
 * - Action: z_vrfy_k_msgq_peek().
 * - Expected: an oops before arch_irq_lock().
 *
 * @ingroup kernel_unit_msgq_k_msgq_peek
 * @see z_vrfy_k_msgq_peek()
 */
ZTEST(msgq_unit, test_syscall_peek_oops_on_bad_object)
{
	struct k_msgq msgq;
	struct msg m;

	msgq_prepare(&msgq);
	kernel_unit_fail_object_check();

	(void)z_vrfy_k_msgq_peek(&msgq, &m);

	zassert_called_before(unit_syscall_oops, unit_arch_irq_lock);
}

/**
 * @brief If the thread cannot write the buffer, z_vrfy_k_msgq_peek() raises an oops before it locks
 * the message queue.
 *
 * @details
 * - Setup: the memory check fails.
 * - Action: z_vrfy_k_msgq_peek().
 * - Expected: one oops, before arch_irq_lock().
 *
 * @ingroup kernel_unit_msgq_k_msgq_peek
 * @see z_vrfy_k_msgq_peek()
 */
ZTEST(msgq_unit, test_syscall_peek_oops_on_bad_buffer)
{
	struct k_msgq msgq;
	struct msg m;

	msgq_prepare(&msgq);
	fail_memory_check();

	(void)z_vrfy_k_msgq_peek(&msgq, &m);

	zassert_oops_before(unit_arch_irq_lock);
}

/**
 * @brief z_vrfy_k_msgq_peek_at() checks the object and that the thread can write msg_size bytes to
 * the buffer, and then returns the result of z_impl_k_msgq_peek_at() with the same index.
 *
 * @details
 * - Setup: a message queue with messages 1, 2. The checks pass.
 * - Action: z_vrfy_k_msgq_peek_at() with the index 1.
 * - Expected: return value 0, the caller has message 2. The object check
 *   with K_OBJ_MSGQ and _OBJ_INIT_TRUE, then the memory check for MSG_SIZE
 *   bytes and write access, then the lock.
 *
 * @ingroup kernel_unit_msgq_k_msgq_peek_at
 * @see z_vrfy_k_msgq_peek_at()
 */
ZTEST(msgq_unit, test_syscall_peek_at_checks_object_and_buffer)
{
	struct k_msgq msgq;
	struct msg m;

	msgq_prepare(&msgq);
	put_msgs(&msgq, 1, 2);
	kernel_unit_pass_object_check();

	zassert_equal(z_vrfy_k_msgq_peek_at(&msgq, &m, 1), 0);

	zassert_msg(&m, 2);
	assert_object_check(&msgq, _OBJ_INIT_TRUE);
	assert_memory_check(&m, MSG_SIZE, 1);
	zassert_called_before(arch_buffer_validate, unit_arch_irq_lock);
}

/**
 * @brief If the object check fails, z_vrfy_k_msgq_peek_at() raises an oops before it locks the
 * message queue.
 *
 * @details
 * - Setup: the object check fails.
 * - Action: z_vrfy_k_msgq_peek_at().
 * - Expected: an oops before arch_irq_lock().
 *
 * @ingroup kernel_unit_msgq_k_msgq_peek_at
 * @see z_vrfy_k_msgq_peek_at()
 */
ZTEST(msgq_unit, test_syscall_peek_at_oops_on_bad_object)
{
	struct k_msgq msgq;
	struct msg m;

	msgq_prepare(&msgq);
	kernel_unit_fail_object_check();

	(void)z_vrfy_k_msgq_peek_at(&msgq, &m, 0);

	zassert_called_before(unit_syscall_oops, unit_arch_irq_lock);
}

/**
 * @brief If the thread cannot write the buffer, z_vrfy_k_msgq_peek_at() raises an oops before it
 * locks the message queue.
 *
 * @details
 * - Setup: the memory check fails.
 * - Action: z_vrfy_k_msgq_peek_at().
 * - Expected: one oops, before arch_irq_lock().
 *
 * @ingroup kernel_unit_msgq_k_msgq_peek_at
 * @see z_vrfy_k_msgq_peek_at()
 */
ZTEST(msgq_unit, test_syscall_peek_at_oops_on_bad_buffer)
{
	struct k_msgq msgq;
	struct msg m;

	msgq_prepare(&msgq);
	fail_memory_check();

	(void)z_vrfy_k_msgq_peek_at(&msgq, &m, 0);

	zassert_oops_before(unit_arch_irq_lock);
}

/**
 * @brief z_vrfy_k_msgq_purge() checks that the pointer is an initialized message queue object, and
 * then calls z_impl_k_msgq_purge().
 *
 * @details
 * - Setup: a message queue with 2 messages. The object check passes.
 * - Action: z_vrfy_k_msgq_purge().
 * - Expected: the object check with K_OBJ_MSGQ and _OBJ_INIT_TRUE, before
 *   the lock. No memory check. The message queue is empty.
 *
 * @ingroup kernel_unit_msgq_k_msgq_purge
 * @see z_vrfy_k_msgq_purge()
 */
ZTEST(msgq_unit, test_syscall_purge_checks_object)
{
	struct k_msgq msgq;

	msgq_prepare(&msgq);
	put_msgs(&msgq, 1, 2);
	kernel_unit_pass_object_check();

	z_vrfy_k_msgq_purge(&msgq);

	assert_object_check(&msgq, _OBJ_INIT_TRUE);
	zassert_called_before(k_object_validation_check, unit_arch_irq_lock);
	zassert_equal(arch_buffer_validate_fake.call_count, 0);
	zassert_msgq_empty(&msgq);
}

/**
 * @brief If the object check fails, z_vrfy_k_msgq_purge() raises an oops before it locks the
 * message queue.
 *
 * @details
 * - Setup: the object check fails.
 * - Action: z_vrfy_k_msgq_purge().
 * - Expected: one oops, before arch_irq_lock().
 *
 * @ingroup kernel_unit_msgq_k_msgq_purge
 * @see z_vrfy_k_msgq_purge()
 */
ZTEST(msgq_unit, test_syscall_purge_oops_on_bad_object)
{
	struct k_msgq msgq;

	msgq_prepare(&msgq);
	kernel_unit_fail_object_check();

	z_vrfy_k_msgq_purge(&msgq);

	zassert_oops_before(unit_arch_irq_lock);
}

/**
 * @brief z_vrfy_k_msgq_num_free_get() and z_vrfy_k_msgq_num_used_get() check that the pointer is an
 * initialized message queue object, and then return the result of the implementation.
 *
 * @details
 * - Setup: a message queue with 3 messages. The object check passes.
 * - Action: z_vrfy_k_msgq_num_free_get(), then z_vrfy_k_msgq_num_used_get().
 * - Expected: MAX_MSGS - 3 and 3. Each call checks the object with
 *   K_OBJ_MSGQ and _OBJ_INIT_TRUE. No oops, no memory check, no lock.
 *
 * @ingroup kernel_unit_msgq_k_msgq_num_free_get
 * @see z_vrfy_k_msgq_num_free_get(), z_vrfy_k_msgq_num_used_get()
 */
ZTEST(msgq_unit, test_syscall_num_free_and_used_check_object)
{
	struct k_msgq msgq;

	msgq_prepare(&msgq);
	put_msgs(&msgq, 1, 3);
	kernel_unit_pass_object_check();

	zassert_equal(z_vrfy_k_msgq_num_free_get(&msgq), MAX_MSGS - 3U);
	assert_object_check(&msgq, _OBJ_INIT_TRUE);

	RESET_FAKE(k_object_find);
	RESET_FAKE(k_object_validation_check);
	kernel_unit_pass_object_check();
	zassert_equal(z_vrfy_k_msgq_num_used_get(&msgq), 3U);
	assert_object_check(&msgq, _OBJ_INIT_TRUE);

	zassert_equal(arch_buffer_validate_fake.call_count, 0);
	zassert_equal(unit_arch_irq_lock_fake.call_count, 0);
}

/**
 * @brief If the object check fails, z_vrfy_k_msgq_num_free_get() and z_vrfy_k_msgq_num_used_get()
 * raise an oops.
 *
 * @details
 * - Setup: the object check fails.
 * - Action: z_vrfy_k_msgq_num_free_get(), then z_vrfy_k_msgq_num_used_get().
 * - Expected: one oops for each call.
 *
 * @ingroup kernel_unit_msgq_k_msgq_num_free_get
 * @see z_vrfy_k_msgq_num_free_get(), z_vrfy_k_msgq_num_used_get()
 */
ZTEST(msgq_unit, test_syscall_num_free_and_used_oops_on_bad_object)
{
	struct k_msgq msgq;

	msgq_prepare(&msgq);
	kernel_unit_fail_object_check();

	(void)z_vrfy_k_msgq_num_free_get(&msgq);
	zassert_equal(unit_syscall_oops_fake.call_count, 1);
	(void)z_vrfy_k_msgq_num_used_get(&msgq);
	zassert_equal(unit_syscall_oops_fake.call_count, 2);
}
/**
 * @brief If the user buffer wraps around the end of the address space, each verification function
 * with a user buffer raises an oops before arch_buffer_validate().
 *
 * @details
 * K_OOPS() is modeled here as a jump back to the test, so the
 * implementation does not run.
 * - Setup: a message queue. The object check passes. The user buffer starts
 *   2 bytes before the end of the address space.
 * - Action: z_vrfy_k_msgq_put(), z_vrfy_k_msgq_put_front(),
 *   z_vrfy_k_msgq_get(), z_vrfy_k_msgq_peek(), z_vrfy_k_msgq_peek_at() and
 *   z_vrfy_k_msgq_get_attrs() with this buffer.
 * - Expected: one oops for each call. No call of arch_buffer_validate() and
 *   no lock.
 *
 * @ingroup kernel_unit_msgq_k_msgq_put
 * @see z_vrfy_k_msgq_put(), z_vrfy_k_msgq_put_front(), z_vrfy_k_msgq_get(),
 * z_vrfy_k_msgq_peek(), z_vrfy_k_msgq_peek_at(), z_vrfy_k_msgq_get_attrs()
 */
ZTEST(msgq_unit, test_syscall_wrapping_buffer_oops)
{
	struct k_msgq msgq;
	void *bad = (void *)(UINTPTR_MAX - 1U);

	msgq_prepare(&msgq);
	kernel_unit_pass_object_check();

	zassert_stopped_by_oops(z_vrfy_k_msgq_put(&msgq, bad, K_NO_WAIT));
	zassert_stopped_by_oops(z_vrfy_k_msgq_put_front(&msgq, bad));
	zassert_stopped_by_oops(z_vrfy_k_msgq_get(&msgq, bad, K_NO_WAIT));
	zassert_stopped_by_oops(z_vrfy_k_msgq_peek(&msgq, bad));
	zassert_stopped_by_oops(z_vrfy_k_msgq_peek_at(&msgq, bad, 0));
	zassert_stopped_by_oops(z_vrfy_k_msgq_get_attrs(&msgq, bad));

	zassert_equal(unit_syscall_oops_fake.call_count, 6);
	zassert_equal(arch_buffer_validate_fake.call_count, 0);
	zassert_equal(unit_arch_irq_lock_fake.call_count, 0);
}

/**
 * @brief The verification functions check the user buffer with the message size of the message
 * queue, also if this size is 0.
 *
 * @details
 * - Setup: a message queue with msg_size 0 and no slots. The checks pass.
 * - Action: z_vrfy_k_msgq_put(), z_vrfy_k_msgq_put_front(),
 *   z_vrfy_k_msgq_get(), z_vrfy_k_msgq_peek(), z_vrfy_k_msgq_peek_at() with
 *   K_NO_WAIT.
 * - Expected: each returns -ENOMSG. Five calls of arch_buffer_validate(), each
 *   with the size 0. No oops.
 *
 * @ingroup kernel_unit_msgq_k_msgq_put
 * @see z_vrfy_k_msgq_put(), z_vrfy_k_msgq_put_front(), z_vrfy_k_msgq_get(),
 * z_vrfy_k_msgq_peek(), z_vrfy_k_msgq_peek_at()
 */
ZTEST(msgq_unit, test_syscall_zero_message_size_check)
{
	struct k_msgq msgq;
	struct msg m = make_msg(1);

	k_msgq_init(&msgq, ring, 0U, 0U);
	reset_history();
	kernel_unit_pass_object_check();

	zassert_equal(z_vrfy_k_msgq_put(&msgq, &m, K_NO_WAIT), -ENOMSG);
	zassert_equal(z_vrfy_k_msgq_put_front(&msgq, &m), -ENOMSG);
	zassert_equal(z_vrfy_k_msgq_get(&msgq, &m, K_NO_WAIT), -ENOMSG);
	zassert_equal(z_vrfy_k_msgq_peek(&msgq, &m), -ENOMSG);
	zassert_equal(z_vrfy_k_msgq_peek_at(&msgq, &m, 0), -ENOMSG);

	zassert_equal(arch_buffer_validate_fake.call_count, 5);
	for (unsigned int i = 0; i < 5U; i++) {
		zassert_equal(arch_buffer_validate_fake.arg1_history[i], 0U);
	}
	zassert_equal(unit_syscall_oops_fake.call_count, 0);
}
#endif /* CONFIG_USERSPACE */

#ifdef CONFIG_OBJ_CORE_MSGQ
/*
 * Tests: Object core. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_msgq, at the top of this file.
 */

/* Return the descriptor of a type, and count the descriptors of this type. */
static const struct k_obj_core_desc *obj_core_desc(struct k_obj_type *type, int *count)
{
	const struct k_obj_core_desc *found = NULL;

	*count = 0;
	STRUCT_SECTION_FOREACH(k_obj_core_desc, desc) {
		if (desc->type == type) {
			found = desc;
			(*count)++;
		}
	}

	return found;
}

/**
 * @brief With CONFIG_OBJ_CORE_MSGQ, msg_q.c defines one object type descriptor with the ID
 * K_OBJ_TYPE_MSGQ_ID.
 *
 * @details
 * - Action: search the section @c k_obj_core_desc for the descriptor of
 *   @c obj_type_msgq.
 * - Expected: one descriptor. Its type ID is K_OBJ_TYPE_MSGQ_ID. Its object
 *   size is the size of @c struct @c k_msgq, and its object core offset is
 *   the offset of @c obj_core. Its object range is the section @c k_msgq.
 *
 * @ingroup kernel_unit_msgq_static
 */
ZTEST(msgq_unit, test_obj_core_type_descriptor)
{
	int count;
	const struct k_obj_core_desc *desc = obj_core_desc(&obj_type_msgq, &count);

	zassert_equal(count, 1);
	zassert_not_null(desc);
	zassert_equal(desc->type_id, K_OBJ_TYPE_MSGQ_ID);
	zassert_equal(desc->obj_size, sizeof(struct k_msgq));
	zassert_equal(desc->obj_core_offset, offsetof(struct k_msgq, obj_core));
	zassert_equal_ptr(desc->objs_start, STRUCT_SECTION_START(k_msgq));
	zassert_equal_ptr(desc->objs_end, STRUCT_SECTION_END(k_msgq));
}

/**
 * @brief The object range of the descriptor contains the message queues that K_MSGQ_DEFINE()
 * defines.
 *
 * @details
 * - Setup: K_MSGQ_DEFINE() of one message queue in the test.
 * - Action: compare its address with the object range of the descriptor.
 * - Expected: the message queue is in the range, at a multiple of the object
 *   size from the start.
 *
 * @ingroup kernel_unit_msgq_static
 */
ZTEST(msgq_unit, test_obj_core_descriptor_covers_static_msgqs)
{
	int count;
	const struct k_obj_core_desc *desc = obj_core_desc(&obj_type_msgq, &count);
	uintptr_t obj = (uintptr_t)&unit_static_msgq;

	zassert_not_null(desc);
	zassert_true((obj >= (uintptr_t)desc->objs_start) && (obj < (uintptr_t)desc->objs_end));
	zassert_equal((obj - (uintptr_t)desc->objs_start) % desc->obj_size, 0U);
}

/**
 * @brief With CONFIG_OBJ_CORE_MSGQ, k_msgq_init() links the message queue to the object type of
 * msg_q.c after it initializes the wait queue.
 *
 * @details
 * - Action: k_msgq_init().
 * - Expected: one call of k_obj_core_init_and_link() with the object core of
 *   the message queue and @c obj_type_msgq, after z_waitq_init().
 *
 * @ingroup kernel_unit_msgq_k_msgq_init
 * @see k_msgq_init()
 */
ZTEST(msgq_unit, test_obj_core_init_links_msgq)
{
	struct k_msgq msgq;

	k_msgq_init(&msgq, ring, MSG_SIZE, MAX_MSGS);

	zassert_equal(k_obj_core_init_and_link_fake.call_count, 1);
	zassert_equal_ptr(k_obj_core_init_and_link_fake.arg0_val, K_OBJ_CORE(&msgq));
	zassert_equal_ptr(k_obj_core_init_and_link_fake.arg1_val, &obj_type_msgq);
	zassert_called_before(z_waitq_init, k_obj_core_init_and_link);
}

/**
 * @brief k_msgq_alloc_init() links the message queue only if the allocation succeeds.
 *
 * @details
 * - Action: k_msgq_alloc_init() with a failed allocation, then with a
 *   successful allocation.
 * - Expected: no call of k_obj_core_init_and_link() after the first call. One
 *   call with the object core of the message queue after the second call.
 *
 * @ingroup kernel_unit_msgq_k_msgq_alloc_init
 * @see z_impl_k_msgq_alloc_init()
 */
ZTEST(msgq_unit, test_obj_core_alloc_init_links_on_success)
{
	struct k_msgq msgq;

	zassert_equal(z_impl_k_msgq_alloc_init(&msgq, MSG_SIZE, MAX_MSGS), -ENOMEM);
	zassert_equal(k_obj_core_init_and_link_fake.call_count, 0);

	z_thread_malloc_fake.custom_fake = malloc_ring;
	zassert_equal(z_impl_k_msgq_alloc_init(&msgq, MSG_SIZE, MAX_MSGS), 0);
	zassert_equal(k_obj_core_init_and_link_fake.call_count, 1);
	zassert_equal_ptr(k_obj_core_init_and_link_fake.arg0_val, K_OBJ_CORE(&msgq));
}
#endif /* CONFIG_OBJ_CORE_MSGQ */
