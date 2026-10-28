/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @defgroup kernel_unit_queue kernel/queue.c
 * @ingroup kernel_unit_tests
 * @brief Design specification of kernel/queue.c, written as unit tests.
 *
 * @par The queue object
 * A queue (@c struct @c k_queue) is a list of data items with these parts:
 * - @c data_q: a singly linked list with flags (@c sys_sflist_t). Each
 *   node of the list is an item, or a wrapper node for an item.
 * - @c lock: the spinlock of the queue. Each queue has its own lock.
 * - @c wait_q: the wait queue of the threads that wait in k_queue_get().
 * - @c poll_events: with @kconfig{CONFIG_POLL}, the k_poll() events on the
 *   queue.
 *
 * The queue does not copy the data. A data item is a block of memory of
 * the caller. Its first word is the list node (@c sys_sfnode_t): the
 * pointer to the next node and, in the low bits, the flags of the node.
 * The caller does not use this word while the item is in the queue.
 *
 * @par Items with an allocated node
 * k_queue_alloc_append() and k_queue_alloc_prepend() do not write to the
 * item. A user thread can give an item in memory that the kernel must not
 * change. These functions allocate a wrapper node (@c struct
 * @c alloc_node: a list node and a data pointer) from the resource pool of
 * the thread with z_thread_malloc(). Flag 1 of the node marks a wrapper.
 * When an operation removes a wrapper from the list (k_queue_get(),
 * k_queue_remove()), it gives the data pointer to the caller and frees the
 * wrapper with k_free(). A node with flag 0 is the item itself.
 *
 * @par Hand-over to a waiting thread
 * A thread waits in k_queue_get() only if the queue is empty. Thus, while
 * a thread waits, the list is empty. An insert operation first tries
 * z_sched_wake() with the item. If a thread waits, the scheduler gives the
 * item to this thread (as @c swap_data, with the return value 0), and the
 * item does not go into the list. k_queue_get() of the woken thread then
 * returns @c _current->base.swap_data.
 *
 * @par Operations
 * - k_queue_init() makes the list empty and initializes the other parts.
 * - k_queue_append(), k_queue_prepend() and k_queue_insert() put an item
 *   at the tail, at the head or after another item.
 *   k_queue_alloc_append() and k_queue_alloc_prepend() do the same with a
 *   wrapper node and can fail with -ENOMEM.
 * - k_queue_unique_append() appends an item only if it is not in the list.
 * - k_queue_append_list() and k_queue_merge_slist() append a
 *   NULL-terminated list of items in one operation.
 * - k_queue_get() removes the head item. If the list is empty, it returns
 *   NULL (timeout K_NO_WAIT) or waits.
 * - k_queue_remove() removes one item from any position.
 * - k_queue_peek_head() and k_queue_peek_tail() return an item and do not
 *   remove it. k_queue_is_empty() is static inline in @c zephyr/kernel.h.
 * - k_queue_cancel_wait() makes one waiting thread return NULL from
 *   k_queue_get().
 *
 * The FIFO (@c struct @c k_fifo) and the LIFO (@c struct @c k_lifo) are
 * macros in @c zephyr/kernel.h around a queue: a FIFO appends, a LIFO
 * prepends, and both get from the head.
 *
 * @par Locks
 * Each operation, except k_queue_init() and k_queue_is_empty(), locks the
 * spinlock of its queue before it reads the list or uses the wait queue.
 * k_spin_lock() locks the interrupts with arch_irq_lock() and returns a
 * key. Each path releases the lock exactly once, with the same key, as its
 * last call to the layers below:
 * - k_spin_unlock(), if no thread became ready.
 * - z_reschedule(), if the operation made a thread ready.
 * - z_pend_curr(), if k_queue_get() must wait. z_pend_curr() adds the
 *   current thread to the wait queue, releases the lock and switches
 *   threads in one step.
 *
 * The allocation and the free of a wrapper node occur while the lock is
 * held. Thus the time with locked interrupts includes the time of the
 * heap.
 *
 * @par Interfaces below queue.c
 * - Scheduler (@c ksched.h): z_sched_wake(), z_reschedule(),
 *   z_pend_curr(), and @c _current (the data of @c kernel/init.c).
 * - Wait queue (@c wait_q.h): z_waitq_init().
 * - Memory (@c kernel/mempool.c): z_thread_malloc(), k_free().
 * - Poll (@c kernel_internal.h): z_handle_obj_poll_events().
 * - Object core: K_OBJ_TYPE_DEFINE() of the FIFO and LIFO types.
 * - Kernel objects: k_object_init().
 * - System call checks: K_SYSCALL_OBJ(), K_SYSCALL_OBJ_NEVER_INIT(),
 *   K_OOPS().
 * - Architecture: arch_irq_lock() and arch_irq_unlock() through
 *   k_spin_lock() and k_spin_unlock().
 * - List functions (@c zephyr/sys/sflist.h, @c zephyr/sys/slist.h): these
 *   are static inline. They are not fakes: the tests examine the real
 *   list.
 *
 * @par Kconfig options that change queue.c
 * - @kconfig{CONFIG_POLL}: the poll events of the queue.
 * - @kconfig{CONFIG_USERSPACE}: the verification functions
 *   z_vrfy_k_queue_*() and the kernel object of the queue.
 * - @kconfig{CONFIG_OBJ_CORE_FIFO}, @kconfig{CONFIG_OBJ_CORE_LIFO}: the
 *   object type descriptors of the FIFO and the LIFO.
 * - The CHECKIF() options for the argument checks of k_queue_append_list()
 *   and k_queue_merge_slist(): @kconfig{CONFIG_RUNTIME_ERROR_CHECKS}
 *   (default) returns -EINVAL, @kconfig{CONFIG_NO_RUNTIME_CHECKS} does no
 *   check, @kconfig{CONFIG_ASSERT_ON_ERRORS} asserts.
 * - @kconfig{CONFIG_ASSERT}: queue.c has no assertion of its own. The
 *   option enables @kconfig{CONFIG_SPIN_VALIDATE} in @c zephyr/spinlock.h.
 *
 * @par Test method
 * The tests call the functions of queue.c directly (z_impl_k_queue_*() for
 * the system calls) and z_vrfy_k_queue_*(). All calls below queue.c go to
 * FFF fakes. The fake unit_arch_irq_lock() returns KERNEL_UNIT_IRQ_KEY.
 * Thus a test can follow the key to the call that releases the lock. The
 * FFF call history gives the order of the calls. A test models waiting
 * threads with the fake z_sched_wake(), and the heap with the fake
 * z_thread_malloc(), which gives nodes from a pool of the test. The
 * scenarios in @c testcase.yaml build the tests once for each Kconfig
 * option above. A test that applies only to some configurations is in an
 * @c \#ifdef block, or it calls ztest_test_skip().
 *
 * @par Structure of the tests
 * Each public function of queue.c has one group below this group. A system
 * call has one group for z_impl_k_queue_*() and z_vrfy_k_queue_*(). The
 * static functions and the data of queue.c have the last group. Each test
 * is in the group of the function under test. The rules below (insert,
 * hand-over, allocated nodes, locking, system call verification, object
 * core, FIFO and LIFO) apply to more than one function. Their tests are in
 * the group of the function that they call.
 *
 * @par Insert
 * The insert functions put an item into the list, if no thread waits.
 * k_queue_append(), k_queue_prepend(), k_queue_insert() and
 * k_queue_unique_append() share the static function queue_insert(). The
 * list node of the item is the first word of the item. queue_insert()
 * writes this word with the pointer to the next node and the flags 0. It
 * does not write the other words of the item. These functions do not
 * allocate memory. If a thread waits, see "Hand-over of an inserted item"
 * below.
 *
 * @par Hand-over of an inserted item
 * If a thread waits, an insert function gives the item to this thread and
 * not to the list.
 * Before queue_insert() changes the list, it calls z_sched_wake() with the
 * wait queue, the return value 0 and the item. If a thread waits, the
 * scheduler makes it ready with the item as its @c swap_data, and
 * queue_insert() releases the lock with z_reschedule(). The item does not
 * go into the list, and queue_insert() does not write to it. The
 * allocating functions then do not allocate a node.
 *
 * @par Allocated nodes
 * The alloc functions put a wrapper node for the item into the list, and the
 * get and remove functions free it.
 * k_queue_alloc_append() and k_queue_alloc_prepend() allocate a
 * @c struct @c alloc_node with z_thread_malloc() from the resource pool of
 * the current thread. The node has flag 1 and points to the item. The
 * item does not change. If no memory is available, the functions return
 * -ENOMEM and change nothing. k_queue_get() and k_queue_remove() free the
 * node with k_free() and give the item to the caller. The peek functions
 * give the item and do not free the node.
 *
 * @par Locking
 * The spinlock of the queue protects the list and the wait queue. Each path
 * releases it exactly once.
 * Each path of the queue operations, except k_queue_init() and
 * k_queue_is_empty(), locks the spinlock of its queue once, as its first
 * call to the layers below. Each path releases the lock once, as its last
 * call, with the key of the lock. The release is k_spin_unlock() (seen as
 * arch_irq_unlock()), z_reschedule() or z_pend_curr(). k_queue_insert(),
 * k_queue_append(), k_queue_prepend(), k_queue_unique_append() and the
 * alloc functions give the lock key to queue_insert(), which releases the
 * lock. The list changes only while the lock is held. z_thread_malloc()
 * and k_free() run while the lock is held.
 *
 * @par System call verification
 * With CONFIG_USERSPACE, each verification function checks the queue object
 * before it calls the implementation.
 * A system call from a user thread goes to z_vrfy_k_queue_*(). This
 * function checks that the pointer is a queue object of the kernel that the
 * thread has access to. z_vrfy_k_queue_init() uses
 * K_SYSCALL_OBJ_NEVER_INIT(): the object must not be initialized yet. Thus
 * a user thread cannot initialize a queue again while other threads use
 * it. The other functions use K_SYSCALL_OBJ(): the object must be
 * initialized. If the check fails, K_OOPS() stops the thread. Otherwise
 * the function calls z_impl_k_queue_*() with the same arguments and
 * returns its result.
 *
 * k_queue_append(), k_queue_prepend(), k_queue_insert(),
 * k_queue_append_list(), k_queue_merge_slist(), k_queue_remove() and
 * k_queue_unique_append() are not system calls. A user thread can only
 * add items with the alloc functions, which do not write to the item.
 *
 * In the test, K_OOPS() calls the fake unit_syscall_oops(), and this fake
 * returns. The real K_OOPS() does not return. Thus the tests check that
 * the oops occurs before the implementation locks or changes the queue.
 *
 * @par Object core
 * With CONFIG_OBJ_CORE_FIFO and CONFIG_OBJ_CORE_LIFO, queue.c defines the
 * object types of the FIFO and the LIFO.
 * A plain queue has no object core. queue.c defines the object types
 * @c _obj_type_fifo and @c _obj_type_lifo. K_OBJ_TYPE_DEFINE() puts one
 * descriptor of each type into the iterable section @c k_obj_core_desc.
 * At boot, the object core code initializes the type from the descriptor
 * and links the FIFOs and LIFOs that K_FIFO_DEFINE() and K_LIFO_DEFINE()
 * define (the sections @c k_fifo and @c k_lifo). The macros k_fifo_init()
 * and k_lifo_init() in @c zephyr/kernel.h link each FIFO or LIFO that they
 * initialize to the type of queue.c. The tests of the descriptors are in
 * the group @ref kernel_unit_queue_static. The tests of the link by
 * k_fifo_init() and k_lifo_init() are in the group of k_queue_init().
 *
 * @par FIFO and LIFO
 * The FIFO and the LIFO are queues: a FIFO appends at the tail, a LIFO
 * prepends at the head, and both get from the head.
 * The FIFO and LIFO functions are macros in @c zephyr/kernel.h. Each one
 * calls a function of queue.c with the queue @c _queue of the FIFO or
 * LIFO. These tests show that the order of the items comes from the choice
 * of the queue function. Each test is in the group of the queue function
 * that its first FIFO or LIFO macro calls.
 */

/**
 * @defgroup kernel_unit_queue_k_queue_init k_queue_init()
 * @ingroup kernel_unit_queue
 * @brief k_queue_init() makes the queue empty and initializes its parts.
 *
 * k_queue_init() makes the list empty, sets the lock to its initial value,
 * and initializes the wait queue, the poll events and the kernel object.
 * It does not lock the queue: until k_queue_init() returns, only the
 * caller uses the queue. It does not link an object core. The FIFO and
 * LIFO macros do this (see "Object core" in @ref kernel_unit_queue).
 *
 * @par Functions in kernel/queue.c
 * - z_impl_k_queue_init()
 * - z_vrfy_k_queue_init(), static inline, with @kconfig{CONFIG_USERSPACE}
 */

/**
 * @defgroup kernel_unit_queue_k_queue_cancel_wait k_queue_cancel_wait()
 * @ingroup kernel_unit_queue
 * @brief k_queue_cancel_wait() makes one waiting thread return NULL from k_queue_get().
 *
 * k_queue_cancel_wait() calls z_sched_wake() with the return value 0 and
 * the data NULL. The scheduler wakes the first waiting thread, and its
 * k_queue_get() returns NULL. The function does not change the list. With
 * CONFIG_POLL it signals K_POLL_STATE_CANCELLED to the poll events (see
 * @ref kernel_unit_queue_static).
 *
 * @par Functions in kernel/queue.c
 * - z_impl_k_queue_cancel_wait()
 * - z_vrfy_k_queue_cancel_wait(), static inline, with
 *   @kconfig{CONFIG_USERSPACE}
 */

/**
 * @defgroup kernel_unit_queue_k_queue_insert k_queue_insert()
 * @ingroup kernel_unit_queue
 * @brief k_queue_insert() puts an item after another item.
 *
 * k_queue_insert() calls the static function queue_insert() (see "Insert"
 * and "Hand-over of an inserted item" in @ref kernel_unit_queue).
 *
 * @par Functions in kernel/queue.c
 * - k_queue_insert()
 */

/**
 * @defgroup kernel_unit_queue_k_queue_append k_queue_append()
 * @ingroup kernel_unit_queue
 * @brief k_queue_append() puts an item at the tail.
 *
 * k_queue_append() calls the static function queue_insert() (see "Insert"
 * and "Hand-over of an inserted item" in @ref kernel_unit_queue).
 *
 * @par Functions in kernel/queue.c
 * - k_queue_append()
 */

/**
 * @defgroup kernel_unit_queue_k_queue_prepend k_queue_prepend()
 * @ingroup kernel_unit_queue
 * @brief k_queue_prepend() puts an item at the head.
 *
 * k_queue_prepend() calls the static function queue_insert() (see "Insert"
 * and "Hand-over of an inserted item" in @ref kernel_unit_queue).
 *
 * @par Functions in kernel/queue.c
 * - k_queue_prepend()
 */

/**
 * @defgroup kernel_unit_queue_k_queue_alloc_append k_queue_alloc_append()
 * @ingroup kernel_unit_queue
 * @brief k_queue_alloc_append() puts a wrapper node for the item at the tail, and can fail with
 * -ENOMEM.
 *
 * See "Allocated nodes" and "Hand-over of an inserted item" in
 * @ref kernel_unit_queue.
 *
 * @par Functions in kernel/queue.c
 * - z_impl_k_queue_alloc_append()
 * - z_vrfy_k_queue_alloc_append(), static inline, with
 *   @kconfig{CONFIG_USERSPACE}
 */

/**
 * @defgroup kernel_unit_queue_k_queue_alloc_prepend k_queue_alloc_prepend()
 * @ingroup kernel_unit_queue
 * @brief k_queue_alloc_prepend() puts a wrapper node for the item at the head, and can fail with
 * -ENOMEM.
 *
 * See "Allocated nodes" and "Hand-over of an inserted item" in
 * @ref kernel_unit_queue.
 *
 * @par Functions in kernel/queue.c
 * - z_impl_k_queue_alloc_prepend()
 * - z_vrfy_k_queue_alloc_prepend(), static inline, with
 *   @kconfig{CONFIG_USERSPACE}
 */

/**
 * @defgroup kernel_unit_queue_k_queue_append_list k_queue_append_list()
 * @ingroup kernel_unit_queue
 * @brief k_queue_append_list() and k_queue_merge_slist() append a list of items in one operation.
 *
 * The caller gives a NULL-terminated, singly linked list of items: the
 * first word of each item points to the next item. k_queue_append_list()
 * first gives one item to each waiting thread, in list order. It follows
 * the next pointers until no thread waits or the list ends. Then it
 * appends the rest of the list (from the current item to @p tail) to the
 * queue in one step. It does not write the list nodes, so the flags of
 * each node must be 0.
 *
 * Both functions check their arguments with CHECKIF(). The Kconfig
 * options of CHECKIF() change what an invalid argument causes.
 *
 * @par Functions in kernel/queue.c
 * - k_queue_append_list()
 */

/**
 * @defgroup kernel_unit_queue_k_queue_merge_slist k_queue_merge_slist()
 * @ingroup kernel_unit_queue
 * @brief k_queue_merge_slist() appends the items of a sys_slist_t and makes the slist empty.
 *
 * k_queue_merge_slist() appends the items of a @c sys_slist_t with
 * k_queue_append_list() and then makes the slist empty.
 *
 * Both functions check their arguments with CHECKIF(). The Kconfig
 * options of CHECKIF() change what an invalid argument causes.
 *
 * @par Functions in kernel/queue.c
 * - k_queue_merge_slist()
 */

/**
 * @defgroup kernel_unit_queue_k_queue_get k_queue_get()
 * @ingroup kernel_unit_queue
 * @brief k_queue_get() removes the head item, or returns NULL, or waits.
 *
 * If the list is not empty, k_queue_get() removes the head node and
 * returns its item (and frees a wrapper node). It then does not wait, for
 * any timeout. If the list is empty and the timeout is K_NO_WAIT, it
 * returns NULL. Otherwise it waits on the wait queue with z_pend_curr().
 * After the wait, it returns the @c swap_data of the current thread if
 * the wait result is 0, else NULL. An insert function or
 * k_queue_cancel_wait() sets @c swap_data and the result 0 with
 * z_sched_wake().
 *
 * The API says that an ISR must use K_NO_WAIT. queue.c has no check of this
 * rule. In an ISR, a wait reaches z_pend_curr(), and the scheduler refuses
 * it with a panic in every build.
 *
 * @par Functions in kernel/queue.c
 * - z_impl_k_queue_get()
 * - z_vrfy_k_queue_get(), static inline, with @kconfig{CONFIG_USERSPACE}
 */

/**
 * @defgroup kernel_unit_queue_k_queue_remove k_queue_remove()
 * @ingroup kernel_unit_queue
 * @brief k_queue_remove() removes one item at any position.
 *
 * k_queue_remove() searches the list from the head for the first node
 * with the item and removes it. It returns true if it found the item.
 *
 * @par Functions in kernel/queue.c
 * - k_queue_remove()
 */

/**
 * @defgroup kernel_unit_queue_k_queue_unique_append k_queue_unique_append()
 * @ingroup kernel_unit_queue
 * @brief k_queue_unique_append() appends an item only if it is not in the list.
 *
 * k_queue_unique_append() calls the static function queue_insert() (see
 * "Insert" and "Hand-over of an inserted item" in @ref kernel_unit_queue).
 *
 * @par Functions in kernel/queue.c
 * - k_queue_unique_append()
 */

/**
 * @defgroup kernel_unit_queue_k_queue_peek_head k_queue_peek_head()
 * @ingroup kernel_unit_queue
 * @brief The peek functions read the list and do not change it.
 *
 * k_queue_peek_head() and k_queue_peek_tail() return the item of the head
 * or tail node, or NULL for an empty list. They do not change the list.
 *
 * @par Functions in kernel/queue.c
 * - z_impl_k_queue_peek_head()
 * - z_vrfy_k_queue_peek_head(), static inline, with
 *   @kconfig{CONFIG_USERSPACE}
 */

/**
 * @defgroup kernel_unit_queue_k_queue_peek_tail k_queue_peek_tail()
 * @ingroup kernel_unit_queue
 * @brief k_queue_peek_tail() returns the item of the tail node, or NULL for an empty list.
 *
 * See k_queue_peek_head() (@ref kernel_unit_queue_k_queue_peek_head).
 *
 * @par Functions in kernel/queue.c
 * - z_impl_k_queue_peek_tail()
 * - z_vrfy_k_queue_peek_tail(), static inline, with
 *   @kconfig{CONFIG_USERSPACE}
 */

/**
 * @defgroup kernel_unit_queue_k_queue_is_empty k_queue_is_empty()
 * @ingroup kernel_unit_queue
 * @brief k_queue_is_empty() reads the list without the lock.
 *
 * k_queue_is_empty() is static inline in @c zephyr/kernel.h and reads the
 * list without the lock.
 *
 * @par Functions in kernel/queue.c
 * - z_vrfy_k_queue_is_empty(), static inline, with
 *   @kconfig{CONFIG_USERSPACE}. queue.c has no z_impl_k_queue_is_empty().
 */

/**
 * @defgroup kernel_unit_queue_static Static functions and data
 * @ingroup kernel_unit_queue
 * @brief The static functions of queue.c, and the data that queue.c defines.
 *
 * @par Poll events
 * With CONFIG_POLL, a queue signals K_POLL_STATE_DATA_AVAILABLE when items
 * go into the list, and K_POLL_STATE_CANCELLED on k_queue_cancel_wait().
 * The static function queue_handle_poll_events() calls
 * z_handle_obj_poll_events() with the poll events of the queue. The return
 * value tells if a polling thread became ready. Then the operation
 * releases the lock with z_reschedule(). Without CONFIG_POLL,
 * queue_handle_poll_events() returns false and calls nothing.
 *
 * - queue_insert() signals only if the item went into the list: not after
 *   a hand-over to a waiting thread, and not after -ENOMEM.
 * - k_queue_append_list() always signals, also if all items went to
 *   waiting threads.
 * - k_queue_cancel_wait() always signals, also if it woke a thread.
 * - k_queue_get(), k_queue_remove() and the peek functions do not signal.
 *
 * Most tests of these rules are in the groups of the functions that they
 * call.
 *
 * @par Functions in kernel/queue.c
 * - z_queue_node_peek(), static. It gives the item of a node, and frees a
 *   wrapper node if the caller asks for it. The tests of k_queue_get(),
 *   k_queue_remove() and the peek functions call it.
 * - queue_handle_poll_events(), static inline. The poll part is only in the
 *   code with @kconfig{CONFIG_POLL}.
 * - queue_insert(), static. The common code of the insert and alloc
 *   functions (see "Insert" in @ref kernel_unit_queue).
 *
 * @par Data in kernel/queue.c
 * - @c _obj_type_fifo and its descriptor (K_OBJ_TYPE_DEFINE()), with
 *   @kconfig{CONFIG_OBJ_CORE_FIFO}.
 * - @c _obj_type_lifo and its descriptor (K_OBJ_TYPE_DEFINE()), with
 *   @kconfig{CONFIG_OBJ_CORE_LIFO}.
 *
 * These two object types have external linkage: the macros k_fifo_init()
 * and k_lifo_init() in @c zephyr/kernel.h use them. The tests of the
 * descriptors are in this group.
 */

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

#include <kernel/queue.c>

/* Value that fills a queue or an item before a test, to show what the unit writes. */
#define FILL KERNEL_UNIT_FILL

/* Timeout that is not K_NO_WAIT and not K_FOREVER */
#define TEST_TIMEOUT K_TICKS(10)

/* Value of a spy record before the spy fake runs */
#define LEN_UNSET ((size_t)-1)

/* Number of the data items and of the wrapper nodes of a test */
#define N_ITEMS 6
#define N_NODES 6

/* A data item: the first word is for the queue, the rest belongs to the caller. */
struct item {
	void *reserved;
	uint32_t value;
};

static struct item items[N_ITEMS];
static struct item *const a = &items[0];
static struct item *const b = &items[1];
static struct item *const c = &items[2];
static struct item *const d = &items[3];

/* The heap of the test: z_thread_malloc() gives these nodes. */
static struct alloc_node node_pool[N_NODES];
static size_t nodes_used;

/* The current thread of the test, for k_queue_get() after a wait. */
static struct k_thread current_thread;

/*
 * Kernel-mode entry points of the queue system calls. Without
 * CONFIG_USERSPACE, the generated file zephyr/syscalls/kernel.h makes each
 * k_queue_*() system call a call of z_impl_k_queue_*(). The unittest build
 * does not generate this file, so the test defines the entry points that
 * the FIFO and LIFO macros of zephyr/kernel.h use.
 */
void k_queue_init(struct k_queue *queue)
{
	z_impl_k_queue_init(queue);
}

void *k_queue_get(struct k_queue *queue, k_timeout_t timeout)
{
	return z_impl_k_queue_get(queue, timeout);
}

int32_t k_queue_alloc_append(struct k_queue *queue, void *data)
{
	return z_impl_k_queue_alloc_append(queue, data);
}

int32_t k_queue_alloc_prepend(struct k_queue *queue, void *data)
{
	return z_impl_k_queue_alloc_prepend(queue, data);
}

static void *malloc_from_pool(size_t size)
{
	zassert_equal(size, sizeof(struct alloc_node), "z_thread_malloc() size %zu", size);

	if (nodes_used >= N_NODES) {
		return NULL;
	}

	return &node_pool[nodes_used++];
}

/* Put a queue into a known, empty state without k_queue_init(). */
static void queue_prepare(struct k_queue *queue)
{
	memset(queue, 0, sizeof(*queue));
	sys_sflist_init(&queue->data_q);
#ifdef CONFIG_POLL
	sys_dlist_init(&queue->poll_events);
#endif
}

/* Return the data of a list node, without the functions of the unit. */
static void *node_data(sys_sfnode_t *node)
{
	if (sys_sfnode_flags_get(node) != 0U) {
		return CONTAINER_OF(node, struct alloc_node, node)->data;
	}

	return node;
}

/* Return the number of nodes in the list of the queue. */
static size_t queue_len(struct k_queue *queue)
{
	size_t n = 0;
	sys_sfnode_t *node;

	SYS_SFLIST_FOR_EACH_NODE(&queue->data_q, node) {
		n++;
	}

	return n;
}

/*
 * Assert that the list of the queue has exactly these data items in this
 * order, and that the tail pointer of the list is the last node.
 */
static void assert_contents(struct k_queue *queue, void *const *expected, size_t n_expected)
{
	size_t n = 0;
	sys_sfnode_t *node;
	sys_sfnode_t *last = NULL;

	SYS_SFLIST_FOR_EACH_NODE(&queue->data_q, node) {
		zassert_true(n < n_expected, "the queue has more than %zu items", n_expected);
		zassert_equal_ptr(node_data(node), expected[n], "item %zu is not as expected", n);
		last = node;
		n++;
	}
	zassert_equal(n, n_expected, "the queue has %zu items, not %zu", n, n_expected);
	zassert_equal_ptr(sys_sflist_peek_tail(&queue->data_q), last, "wrong tail of the list");
}

#define zassert_queue_contents(queue, ...)                                                         \
	do {                                                                                       \
		void *const expected_[] = {__VA_ARGS__};                                           \
		assert_contents(queue, expected_, ARRAY_SIZE(expected_));                          \
	} while (false)

#define zassert_queue_empty(queue) assert_contents(queue, NULL, 0)

/*
 * The queue that the spy fakes read. A spy fake records the length of the
 * list at the time of its call. Thus a test sees the order of the list
 * changes and the calls to the layers below.
 */
static struct k_queue *spied_queue;
static size_t len_at_lock;
static size_t len_at_release;
static size_t len_at_poll;

/* Observers of the lock spies (kernel_unit_spy_on_lock()). */
static void observe_lock(void)
{
	len_at_lock = queue_len(spied_queue);
}

static void observe_release(void)
{
	len_at_release = queue_len(spied_queue);
}

static __maybe_unused bool poll_spy(sys_dlist_t *events, uint32_t state)
{
	ARG_UNUSED(events);
	ARG_UNUSED(state);

	len_at_poll = queue_len(spied_queue);

	return false;
}

/* Install the spy fakes of the lock and of the release paths. */
static void spy_on_lock(struct k_queue *queue)
{
	spied_queue = queue;
	len_at_lock = LEN_UNSET;
	len_at_release = LEN_UNSET;
	len_at_poll = LEN_UNSET;
	kernel_unit_spy_on_lock(observe_lock, observe_release);
}

/* Assert the lock invariant of one operation on the queue (kernel_unit_models.h). */
static void assert_lock_released_once(struct k_queue *queue, enum kernel_unit_release how)
{
	kernel_unit_assert_lock_released_once(&queue->lock, how);
}

/* Forget the calls of the test setup. */
static void reset_history(void)
{
	FFF_RESET_HISTORY();
	RESET_FAKE(unit_arch_irq_lock);
	RESET_FAKE(unit_arch_irq_unlock);
	RESET_FAKE(z_reschedule);
	RESET_FAKE(z_thread_malloc);
	RESET_FAKE(k_free);
	unit_arch_irq_lock_fake.return_val = KERNEL_UNIT_IRQ_KEY;
	z_thread_malloc_fake.custom_fake = malloc_from_pool;
}

static void queue_unit_before(void *fixture)
{
	ARG_UNUSED(fixture);

	/* The fake rules reset all fakes and _kernel before this function. */
	unit_arch_irq_lock_fake.return_val = KERNEL_UNIT_IRQ_KEY;
	z_thread_malloc_fake.custom_fake = malloc_from_pool;

	for (size_t i = 0; i < N_ITEMS; i++) {
		items[i].reserved = NULL;
		items[i].value = 0x1000U + i;
	}
	memset(node_pool, FILL, sizeof(node_pool));
	nodes_used = 0;
	kernel_unit_waiting_threads = 0;
	spied_queue = NULL;
	memset(&current_thread, 0, sizeof(current_thread));
	_kernel.cpus[0].current = &current_thread;
}

ZTEST_SUITE(queue_unit, NULL, NULL, queue_unit_before, NULL, NULL);

/*
 * Tests: Initialization. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_queue, at the top of this file.
 */

/**
 * @brief k_queue_init() makes the list of the queue empty.
 *
 * @details
 * - Setup: a queue filled with a pattern.
 * - Action: z_impl_k_queue_init().
 * - Expected: the list has no head and no tail. k_queue_is_empty() returns
 *   a value other than 0.
 *
 * @ingroup kernel_unit_queue_k_queue_init
 * @see z_impl_k_queue_init()
 */
ZTEST(queue_unit, test_init_empties_list)
{
	struct k_queue queue;

	memset(&queue, FILL, sizeof(queue));

	z_impl_k_queue_init(&queue);

	zassert_is_null(sys_sflist_peek_head(&queue.data_q));
	zassert_is_null(sys_sflist_peek_tail(&queue.data_q));
	zassert_not_equal(z_impl_k_queue_is_empty(&queue), 0);
}

/**
 * @brief k_queue_init() sets the lock of the queue to its initial value.
 *
 * @details
 * - Setup: a queue filled with a pattern.
 * - Action: z_impl_k_queue_init().
 * - Expected: all bytes of the lock are 0 (the value of an unlocked
 *   spinlock).
 *
 * @ingroup kernel_unit_queue_k_queue_init
 * @see z_impl_k_queue_init()
 */
ZTEST(queue_unit, test_init_resets_lock)
{
	struct k_queue queue;
	const struct k_spinlock unlocked = {};

	memset(&queue, FILL, sizeof(queue));

	z_impl_k_queue_init(&queue);

	zassert_mem_equal(&queue.lock, &unlocked, sizeof(unlocked));
}

/**
 * @brief k_queue_init() initializes the wait queue of the queue.
 *
 * @details
 * - Action: z_impl_k_queue_init().
 * - Expected: one call of z_waitq_init() with the wait queue of the queue.
 *
 * @ingroup kernel_unit_queue_k_queue_init
 * @see z_impl_k_queue_init()
 */
ZTEST(queue_unit, test_init_initializes_wait_queue)
{
	struct k_queue queue;

	z_impl_k_queue_init(&queue);

	zassert_equal(z_waitq_init_fake.call_count, 1);
	zassert_equal_ptr(z_waitq_init_fake.arg0_val, &queue.wait_q);
}

#ifdef CONFIG_POLL
/**
 * @brief With CONFIG_POLL, k_queue_init() makes the list of poll events empty.
 *
 * @details
 * - Setup: a queue filled with a pattern.
 * - Action: z_impl_k_queue_init().
 * - Expected: the list @c poll_events is a valid, empty list.
 *
 * @ingroup kernel_unit_queue_k_queue_init
 * @see z_impl_k_queue_init()
 */
ZTEST(queue_unit, test_init_empties_poll_events)
{
	struct k_queue queue;

	memset(&queue, FILL, sizeof(queue));

	z_impl_k_queue_init(&queue);

	zassert_true(sys_dlist_is_empty(&queue.poll_events));
}
#endif /* CONFIG_POLL */

#ifdef CONFIG_USERSPACE
/**
 * @brief With CONFIG_USERSPACE, k_queue_init() marks the queue as an initialized kernel object.
 *
 * @details
 * - Action: z_impl_k_queue_init().
 * - Expected: one call of k_object_init() with the queue.
 *
 * @ingroup kernel_unit_queue_k_queue_init
 * @see z_impl_k_queue_init()
 */
ZTEST(queue_unit, test_init_initializes_kernel_object)
{
	struct k_queue queue;

	z_impl_k_queue_init(&queue);

	zassert_equal(k_object_init_fake.call_count, 1);
	zassert_equal_ptr(k_object_init_fake.arg0_val, &queue);
}
#endif /* CONFIG_USERSPACE */

/**
 * @brief k_queue_init() initializes the wait queue, then the kernel object, and calls nothing
 * else.
 *
 * @details
 * - Action: z_impl_k_queue_init().
 * - Expected calls, in this order: z_waitq_init(), k_object_init() (with
 *   CONFIG_USERSPACE). No lock, no object core link, no allocation.
 *
 * @ingroup kernel_unit_queue_k_queue_init
 * @see z_impl_k_queue_init()
 */
ZTEST(queue_unit, test_init_call_order)
{
	struct k_queue queue;

	z_impl_k_queue_init(&queue);

	zassert_call_history(z_waitq_init, KERNEL_UNIT_IF_ENABLED(CONFIG_USERSPACE, k_object_init));
}

/*
 * Tests: Insert. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_queue, at the top of this file.
 */

/**
 * @brief k_queue_append() puts the item at the tail of the list.
 *
 * @details
 * - Setup: an empty queue. No thread waits.
 * - Action: k_queue_append() of the items a, b and c.
 * - Expected: the list is a, b, c. The tail of the list is c.
 *
 * @ingroup kernel_unit_queue_k_queue_append
 * @see k_queue_append()
 */
ZTEST(queue_unit, test_append_puts_item_at_tail)
{
	struct k_queue queue;

	queue_prepare(&queue);

	k_queue_append(&queue, a);
	k_queue_append(&queue, b);
	k_queue_append(&queue, c);

	zassert_queue_contents(&queue, a, b, c);
}

/**
 * @brief k_queue_prepend() puts the item at the head of the list.
 *
 * @details
 * - Setup: an empty queue. No thread waits.
 * - Action: k_queue_prepend() of the items a, b and c.
 * - Expected: the list is c, b, a. The tail of the list is a.
 *
 * @ingroup kernel_unit_queue_k_queue_prepend
 * @see k_queue_prepend()
 */
ZTEST(queue_unit, test_prepend_puts_item_at_head)
{
	struct k_queue queue;

	queue_prepare(&queue);

	k_queue_prepend(&queue, a);
	k_queue_prepend(&queue, b);
	k_queue_prepend(&queue, c);

	zassert_queue_contents(&queue, c, b, a);
}

/**
 * @brief k_queue_insert() puts the item after the item prev.
 *
 * @details
 * - Setup: the list is a, c. No thread waits.
 * - Action: k_queue_insert() of b after a, then of d after c.
 * - Expected: the list is a, b, c, d. The tail of the list is d.
 *
 * @ingroup kernel_unit_queue_k_queue_insert
 * @see k_queue_insert()
 */
ZTEST(queue_unit, test_insert_puts_item_after_prev)
{
	struct k_queue queue;

	queue_prepare(&queue);
	k_queue_append(&queue, a);
	k_queue_append(&queue, c);

	k_queue_insert(&queue, a, b);
	k_queue_insert(&queue, c, d);

	zassert_queue_contents(&queue, a, b, c, d);
}

/**
 * @brief k_queue_insert() with prev NULL puts the item at the head of the list.
 *
 * @details
 * - Setup: the list is a. No thread waits.
 * - Action: k_queue_insert() of b with prev NULL.
 * - Expected: the list is b, a.
 *
 * @ingroup kernel_unit_queue_k_queue_insert
 * @see k_queue_insert()
 */
ZTEST(queue_unit, test_insert_null_prev_puts_item_at_head)
{
	struct k_queue queue;

	queue_prepare(&queue);
	k_queue_append(&queue, a);

	k_queue_insert(&queue, NULL, b);

	zassert_queue_contents(&queue, b, a);
}

/**
 * @brief The insert functions write only the first word of the item, with the flags 0.
 *
 * @details
 * - Setup: an empty queue. The first word of item a has a pattern.
 * - Action: k_queue_append() of a.
 * - Expected: the first word of a is the list node with the flags 0 and
 *   no next node. The other words of a do not change.
 *
 * @ingroup kernel_unit_queue_k_queue_append
 * @see k_queue_append(), queue_insert()
 */
ZTEST(queue_unit, test_insert_writes_only_first_word)
{
	struct k_queue queue;

	queue_prepare(&queue);
	memset(&a->reserved, FILL, sizeof(a->reserved));

	k_queue_append(&queue, a);

	zassert_equal(sys_sfnode_flags_get((sys_sfnode_t *)a), 0U);
	zassert_is_null(sys_sflist_peek_next((sys_sfnode_t *)a));
	zassert_equal(a->value, 0x1000U);
}

/**
 * @brief k_queue_append(), k_queue_prepend(), k_queue_insert() and k_queue_unique_append() do not
 * allocate memory.
 *
 * @details
 * - Setup: an empty queue. No thread waits.
 * - Action: each of the four functions with a new item.
 * - Expected: no call of z_thread_malloc() and of k_free().
 *
 * @ingroup kernel_unit_queue_k_queue_append
 * @see k_queue_append(), k_queue_prepend(), k_queue_insert(), k_queue_unique_append()
 */
ZTEST(queue_unit, test_insert_does_not_allocate)
{
	struct k_queue queue;

	queue_prepare(&queue);

	k_queue_append(&queue, a);
	k_queue_prepend(&queue, b);
	k_queue_insert(&queue, a, c);
	zassert_true(k_queue_unique_append(&queue, d));

	zassert_equal(z_thread_malloc_fake.call_count, 0);
	zassert_equal(k_free_fake.call_count, 0);
	zassert_queue_contents(&queue, b, a, c, d);
}

/**
 * @brief k_queue_unique_append() appends an item that is not in the list and returns true.
 *
 * @details
 * - Setup: the list is a. No thread waits.
 * - Action: k_queue_unique_append() of b.
 * - Expected: return value true. The list is a, b.
 *
 * @ingroup kernel_unit_queue_k_queue_unique_append
 * @see k_queue_unique_append()
 */
ZTEST(queue_unit, test_unique_append_appends_new_item)
{
	struct k_queue queue;

	queue_prepare(&queue);
	k_queue_append(&queue, a);

	zassert_true(k_queue_unique_append(&queue, b));

	zassert_queue_contents(&queue, a, b);
}

/**
 * @brief k_queue_unique_append() returns false and changes nothing if the item is in the list.
 *
 * @details
 * - Setup: the list is a, b, c. A thread waits (this cannot occur with a
 *   list that is not empty; it shows that no wake is tried).
 * - Action: k_queue_unique_append() of b.
 * - Expected: return value false. The list is a, b, c. No call of
 *   z_sched_wake() and of the poll subsystem.
 *
 * @ingroup kernel_unit_queue_k_queue_unique_append
 * @see k_queue_unique_append()
 */
ZTEST(queue_unit, test_unique_append_rejects_item_in_list)
{
	struct k_queue queue;

	queue_prepare(&queue);
	k_queue_append(&queue, a);
	k_queue_append(&queue, b);
	k_queue_append(&queue, c);
	reset_history();
	RESET_FAKE(z_sched_wake);
	RESET_FAKE(z_handle_obj_poll_events);
	kernel_unit_set_waiting_threads(1);

	zassert_false(k_queue_unique_append(&queue, b));

	zassert_queue_contents(&queue, a, b, c);
	zassert_equal(z_sched_wake_fake.call_count, 0);
	zassert_equal(z_handle_obj_poll_events_fake.call_count, 0);
}

/**
 * @brief k_queue_unique_append() compares the list nodes with the item, so it does not find an
 * item with an allocated node.
 *
 * @details
 * The list node of an item from k_queue_alloc_append() is a wrapper, not
 * the item. Thus the comparison does not find the item, and the item goes
 * into the list a second time, now as its own node.
 * - Setup: k_queue_alloc_append() of a.
 * - Action: k_queue_unique_append() of a.
 * - Expected: return value true. The list has a two times: first in a
 *   wrapper node, then as the item itself.
 *
 * @ingroup kernel_unit_queue_k_queue_unique_append
 * @see k_queue_unique_append()
 */
ZTEST(queue_unit, test_unique_append_does_not_find_allocated_item)
{
	struct k_queue queue;

	queue_prepare(&queue);
	zassert_equal(z_impl_k_queue_alloc_append(&queue, a), 0);

	zassert_true(k_queue_unique_append(&queue, a));

	zassert_queue_contents(&queue, a, a);
	zassert_equal(sys_sfnode_flags_get(sys_sflist_peek_head(&queue.data_q)), 1U);
	zassert_equal_ptr(sys_sflist_peek_tail(&queue.data_q), (sys_sfnode_t *)a);
}

/*
 * Tests: Hand-over to a waiting thread. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_queue, at the top of this file.
 */

/**
 * @brief If a thread waits, k_queue_append() gives the item to this thread with the return value
 * 0, and the list stays empty.
 *
 * @details
 * - Setup: an empty queue. One thread waits. The first word of item a has
 *   a pattern.
 * - Action: k_queue_append() of a.
 * - Expected: one call of z_sched_wake() with the wait queue of the queue,
 *   the return value 0 and a. The list is empty. The first word of a has
 *   the pattern.
 *
 * @ingroup kernel_unit_queue_k_queue_append
 * @see k_queue_append(), queue_insert()
 */
ZTEST(queue_unit, test_handover_append_gives_item_to_thread)
{
	struct k_queue queue;
	void *pattern;

	queue_prepare(&queue);
	kernel_unit_set_waiting_threads(1);
	memset(&a->reserved, FILL, sizeof(a->reserved));
	pattern = a->reserved;

	k_queue_append(&queue, a);

	zassert_equal(z_sched_wake_fake.call_count, 1);
	zassert_equal_ptr(z_sched_wake_fake.arg0_val, &queue.wait_q);
	zassert_equal(z_sched_wake_fake.arg1_val, 0);
	zassert_equal_ptr(z_sched_wake_fake.arg2_val, a);
	zassert_queue_empty(&queue);
	zassert_equal_ptr(a->reserved, pattern);
}

/**
 * @brief If a thread waits, k_queue_prepend(), k_queue_insert() and k_queue_unique_append() also
 * give the item to this thread.
 *
 * @details
 * - Setup: an empty queue. Three threads wait.
 * - Action: k_queue_prepend() of a, k_queue_insert() of b with prev NULL,
 *   k_queue_unique_append() of c.
 * - Expected: z_sched_wake() with a, b and c. The list is empty.
 *   k_queue_unique_append() returns true.
 *
 * @ingroup kernel_unit_queue_k_queue_prepend
 * @see k_queue_prepend(), k_queue_insert(), k_queue_unique_append()
 */
ZTEST(queue_unit, test_handover_other_inserts_give_item_to_thread)
{
	struct k_queue queue;

	queue_prepare(&queue);
	kernel_unit_set_waiting_threads(3);

	k_queue_prepend(&queue, a);
	k_queue_insert(&queue, NULL, b);
	zassert_true(k_queue_unique_append(&queue, c));

	zassert_equal(z_sched_wake_fake.call_count, 3);
	zassert_equal_ptr(z_sched_wake_fake.arg2_history[0], a);
	zassert_equal_ptr(z_sched_wake_fake.arg2_history[1], b);
	zassert_equal_ptr(z_sched_wake_fake.arg2_history[2], c);
	zassert_queue_empty(&queue);
}

/**
 * @brief If a thread waits, k_queue_alloc_append() and k_queue_alloc_prepend() give the item to
 * this thread without an allocation and return 0.
 *
 * @details
 * - Setup: an empty queue. Two threads wait.
 * - Action: z_impl_k_queue_alloc_append() of a, then
 *   z_impl_k_queue_alloc_prepend() of b.
 * - Expected: return value 0 each time. z_sched_wake() with a and b. No
 *   call of z_thread_malloc(). The list is empty.
 *
 * @ingroup kernel_unit_queue_k_queue_alloc_append
 * @see z_impl_k_queue_alloc_append(), z_impl_k_queue_alloc_prepend()
 */
ZTEST(queue_unit, test_handover_alloc_does_not_allocate)
{
	struct k_queue queue;

	queue_prepare(&queue);
	kernel_unit_set_waiting_threads(2);

	zassert_equal(z_impl_k_queue_alloc_append(&queue, a), 0);
	zassert_equal(z_impl_k_queue_alloc_prepend(&queue, b), 0);

	zassert_equal(z_sched_wake_fake.call_count, 2);
	zassert_equal_ptr(z_sched_wake_fake.arg2_history[0], a);
	zassert_equal_ptr(z_sched_wake_fake.arg2_history[1], b);
	zassert_equal(z_thread_malloc_fake.call_count, 0);
	zassert_queue_empty(&queue);
}

/**
 * @brief An insert function wakes at most one thread.
 *
 * @details
 * - Setup: an empty queue. Two threads wait.
 * - Action: k_queue_append() of a.
 * - Expected: one call of z_sched_wake(). One thread still waits.
 *
 * @ingroup kernel_unit_queue_k_queue_append
 * @see k_queue_append(), queue_insert()
 */
ZTEST(queue_unit, test_handover_wakes_one_thread_only)
{
	struct k_queue queue;

	queue_prepare(&queue);
	kernel_unit_set_waiting_threads(2);

	k_queue_append(&queue, a);

	zassert_equal(z_sched_wake_fake.call_count, 1);
	zassert_equal(kernel_unit_waiting_threads, 1U);
}

/*
 * Tests: Items with an allocated node. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_queue, at the top of this file.
 */

/**
 * @brief k_queue_alloc_append() puts a wrapper node with flag 1 for the item at the tail and does
 * not change the item.
 *
 * @details
 * - Setup: the list is a. No thread waits. z_thread_malloc() gives nodes
 *   from the pool of the test.
 * - Action: z_impl_k_queue_alloc_append() of b.
 * - Expected: return value 0. One call of z_thread_malloc() with the size
 *   of @c struct @c alloc_node. The tail node is the first node of the
 *   pool, with flag 1 and the data pointer b. The list is a, b. Item b does
 *   not change.
 *
 * @ingroup kernel_unit_queue_k_queue_alloc_append
 * @see z_impl_k_queue_alloc_append()
 */
ZTEST(queue_unit, test_alloc_append_wraps_item_at_tail)
{
	struct k_queue queue;
	struct item before;

	queue_prepare(&queue);
	k_queue_append(&queue, a);
	before = *b;

	zassert_equal(z_impl_k_queue_alloc_append(&queue, b), 0);

	zassert_equal(z_thread_malloc_fake.call_count, 1);
	zassert_equal(z_thread_malloc_fake.arg0_val, sizeof(struct alloc_node));
	zassert_equal_ptr(sys_sflist_peek_tail(&queue.data_q), &node_pool[0].node);
	zassert_equal(sys_sfnode_flags_get(&node_pool[0].node), 1U);
	zassert_equal_ptr(node_pool[0].data, b);
	zassert_queue_contents(&queue, a, b);
	zassert_mem_equal(b, &before, sizeof(before));
}

/**
 * @brief k_queue_alloc_prepend() puts a wrapper node with flag 1 for the item at the head and does
 * not change the item.
 *
 * @details
 * - Setup: the list is a. No thread waits.
 * - Action: z_impl_k_queue_alloc_prepend() of b.
 * - Expected: return value 0. The head node is the first node of the pool,
 *   with flag 1 and the data pointer b. The list is b, a. Item b does not
 *   change.
 *
 * @ingroup kernel_unit_queue_k_queue_alloc_prepend
 * @see z_impl_k_queue_alloc_prepend()
 */
ZTEST(queue_unit, test_alloc_prepend_wraps_item_at_head)
{
	struct k_queue queue;
	struct item before;

	queue_prepare(&queue);
	k_queue_append(&queue, a);
	before = *b;

	zassert_equal(z_impl_k_queue_alloc_prepend(&queue, b), 0);

	zassert_equal(z_thread_malloc_fake.call_count, 1);
	zassert_equal_ptr(sys_sflist_peek_head(&queue.data_q), &node_pool[0].node);
	zassert_equal(sys_sfnode_flags_get(&node_pool[0].node), 1U);
	zassert_equal_ptr(node_pool[0].data, b);
	zassert_queue_contents(&queue, b, a);
	zassert_mem_equal(b, &before, sizeof(before));
}

/**
 * @brief If z_thread_malloc() fails, k_queue_alloc_append() returns -ENOMEM and does not change
 * the queue.
 *
 * @details
 * - Setup: the list is a. No thread waits. z_thread_malloc() returns NULL.
 * - Action: z_impl_k_queue_alloc_append() of b.
 * - Expected: return value -ENOMEM. The list is a. No poll signal.
 *
 * @ingroup kernel_unit_queue_k_queue_alloc_append
 * @see z_impl_k_queue_alloc_append()
 */
ZTEST(queue_unit, test_alloc_append_no_memory_returns_enomem)
{
	struct k_queue queue;

	queue_prepare(&queue);
	k_queue_append(&queue, a);
	reset_history();
	RESET_FAKE(z_handle_obj_poll_events);
	z_thread_malloc_fake.custom_fake = NULL;

	zassert_equal(z_impl_k_queue_alloc_append(&queue, b), -ENOMEM);

	zassert_queue_contents(&queue, a);
	zassert_equal(z_handle_obj_poll_events_fake.call_count, 0);
}

/**
 * @brief If z_thread_malloc() fails, k_queue_alloc_prepend() returns -ENOMEM and does not change
 * the queue.
 *
 * @details
 * - Setup: the list is a. No thread waits. z_thread_malloc() returns NULL.
 * - Action: z_impl_k_queue_alloc_prepend() of b.
 * - Expected: return value -ENOMEM. The list is a.
 *
 * @ingroup kernel_unit_queue_k_queue_alloc_prepend
 * @see z_impl_k_queue_alloc_prepend()
 */
ZTEST(queue_unit, test_alloc_prepend_no_memory_returns_enomem)
{
	struct k_queue queue;

	queue_prepare(&queue);
	k_queue_append(&queue, a);
	z_thread_malloc_fake.custom_fake = NULL;

	zassert_equal(z_impl_k_queue_alloc_prepend(&queue, b), -ENOMEM);

	zassert_queue_contents(&queue, a);
}

/**
 * @brief k_queue_get() of an item with a wrapper node returns the item and frees the node.
 *
 * @details
 * - Setup: z_impl_k_queue_alloc_append() of a.
 * - Action: z_impl_k_queue_get() with K_NO_WAIT.
 * - Expected: return value a. One call of k_free() with the node. The list
 *   is empty.
 *
 * @ingroup kernel_unit_queue_k_queue_get
 * @see z_impl_k_queue_get(), z_queue_node_peek()
 */
ZTEST(queue_unit, test_alloc_get_frees_node)
{
	struct k_queue queue;

	queue_prepare(&queue);
	zassert_equal(z_impl_k_queue_alloc_append(&queue, a), 0);

	zassert_equal_ptr(z_impl_k_queue_get(&queue, K_NO_WAIT), a);

	zassert_equal(k_free_fake.call_count, 1);
	zassert_equal_ptr(k_free_fake.arg0_val, &node_pool[0]);
	zassert_queue_empty(&queue);
}

/**
 * @brief k_queue_get() of an item without a wrapper node does not call k_free().
 *
 * @details
 * - Setup: k_queue_append() of a.
 * - Action: z_impl_k_queue_get() with K_NO_WAIT.
 * - Expected: return value a. No call of k_free().
 *
 * @ingroup kernel_unit_queue_k_queue_get
 * @see z_impl_k_queue_get(), z_queue_node_peek()
 */
ZTEST(queue_unit, test_alloc_get_direct_item_does_not_free)
{
	struct k_queue queue;

	queue_prepare(&queue);
	k_queue_append(&queue, a);

	zassert_equal_ptr(z_impl_k_queue_get(&queue, K_NO_WAIT), a);

	zassert_equal(k_free_fake.call_count, 0);
}

/**
 * @brief k_queue_peek_head() and k_queue_peek_tail() return the item of a wrapper node and do not
 * free the node.
 *
 * @details
 * - Setup: z_impl_k_queue_alloc_append() of a and of b.
 * - Action: z_impl_k_queue_peek_head(), z_impl_k_queue_peek_tail().
 * - Expected: return values a and b. No call of k_free(). The list is a,
 *   b.
 *
 * @ingroup kernel_unit_queue_k_queue_peek_head
 * @see z_impl_k_queue_peek_head(), z_impl_k_queue_peek_tail(), z_queue_node_peek()
 */
ZTEST(queue_unit, test_alloc_peek_does_not_free)
{
	struct k_queue queue;

	queue_prepare(&queue);
	zassert_equal(z_impl_k_queue_alloc_append(&queue, a), 0);
	zassert_equal(z_impl_k_queue_alloc_append(&queue, b), 0);

	zassert_equal_ptr(z_impl_k_queue_peek_head(&queue), a);
	zassert_equal_ptr(z_impl_k_queue_peek_tail(&queue), b);

	zassert_equal(k_free_fake.call_count, 0);
	zassert_queue_contents(&queue, a, b);
}

/**
 * @brief k_queue_remove() of an item with a wrapper node removes the node and frees it.
 *
 * @details
 * - Setup: k_queue_append() of a, z_impl_k_queue_alloc_append() of b,
 *   k_queue_append() of c.
 * - Action: k_queue_remove() of b.
 * - Expected: return value true. One call of k_free() with the node of b.
 *   The list is a, c.
 *
 * @ingroup kernel_unit_queue_k_queue_remove
 * @see k_queue_remove(), z_queue_node_peek()
 */
ZTEST(queue_unit, test_alloc_remove_frees_node)
{
	struct k_queue queue;

	queue_prepare(&queue);
	k_queue_append(&queue, a);
	zassert_equal(z_impl_k_queue_alloc_append(&queue, b), 0);
	k_queue_append(&queue, c);

	zassert_true(k_queue_remove(&queue, b));

	zassert_equal(k_free_fake.call_count, 1);
	zassert_equal_ptr(k_free_fake.arg0_val, &node_pool[0]);
	zassert_queue_contents(&queue, a, c);
}

/**
 * @brief Items with and without a wrapper node share one list and keep their order.
 *
 * @details
 * - Setup: k_queue_append() of a, z_impl_k_queue_alloc_append() of b,
 *   z_impl_k_queue_alloc_prepend() of c, k_queue_append() of d.
 * - Action: z_impl_k_queue_get() with K_NO_WAIT, four times.
 * - Expected: return values c, a, b, d. Two calls of k_free().
 *
 * @ingroup kernel_unit_queue_k_queue_get
 * @see z_impl_k_queue_get()
 */
ZTEST(queue_unit, test_alloc_mixed_items_keep_order)
{
	struct k_queue queue;

	queue_prepare(&queue);
	k_queue_append(&queue, a);
	zassert_equal(z_impl_k_queue_alloc_append(&queue, b), 0);
	zassert_equal(z_impl_k_queue_alloc_prepend(&queue, c), 0);
	k_queue_append(&queue, d);

	zassert_equal_ptr(z_impl_k_queue_get(&queue, K_NO_WAIT), c);
	zassert_equal_ptr(z_impl_k_queue_get(&queue, K_NO_WAIT), a);
	zassert_equal_ptr(z_impl_k_queue_get(&queue, K_NO_WAIT), b);
	zassert_equal_ptr(z_impl_k_queue_get(&queue, K_NO_WAIT), d);

	zassert_equal(k_free_fake.call_count, 2);
	zassert_queue_empty(&queue);
}

/*
 * Tests: List operations. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_queue, at the top of this file.
 */

/* Link the items into a NULL-terminated list in the order of the arguments. */
static void link_items(size_t n, struct item **list)
{
	for (size_t i = 0; i < n; i++) {
		list[i]->reserved = (i + 1 < n) ? list[i + 1] : NULL;
	}
}

#define LINK_ITEMS(...)                                                                            \
	do {                                                                                       \
		struct item *list_[] = {__VA_ARGS__};                                              \
		link_items(ARRAY_SIZE(list_), list_);                                              \
	} while (false)

/**
 * @brief k_queue_append_list() appends all items from head to tail after the last item of the
 * queue and returns 0.
 *
 * @details
 * - Setup: the list of the queue is a. The items b, c, d are a
 *   NULL-terminated list. No thread waits.
 * - Action: k_queue_append_list() with head b and tail d.
 * - Expected: return value 0. The list is a, b, c, d. The tail is d.
 *
 * @ingroup kernel_unit_queue_k_queue_append_list
 * @see k_queue_append_list()
 */
ZTEST(queue_unit, test_list_append_list_appends_all_items)
{
	struct k_queue queue;

	queue_prepare(&queue);
	k_queue_append(&queue, a);
	LINK_ITEMS(b, c, d);

	zassert_equal(k_queue_append_list(&queue, b, d), 0);

	zassert_queue_contents(&queue, a, b, c, d);
}

/**
 * @brief k_queue_append_list() makes an empty queue hold the list.
 *
 * @details
 * - Setup: an empty queue. The items a, b are a NULL-terminated list.
 * - Action: k_queue_append_list() with head a and tail b.
 * - Expected: return value 0. The list is a, b.
 *
 * @ingroup kernel_unit_queue_k_queue_append_list
 * @see k_queue_append_list()
 */
ZTEST(queue_unit, test_list_append_list_to_empty_queue)
{
	struct k_queue queue;

	queue_prepare(&queue);
	LINK_ITEMS(a, b);

	zassert_equal(k_queue_append_list(&queue, a, b), 0);

	zassert_queue_contents(&queue, a, b);
}

/**
 * @brief k_queue_append_list() gives the first items to the waiting threads, one item to each
 * thread, and appends the rest.
 *
 * @details
 * - Setup: an empty queue. Two threads wait. The items a, b, c are a
 *   NULL-terminated list.
 * - Action: k_queue_append_list() with head a and tail c.
 * - Expected: return value 0. z_sched_wake() with a, then with b (the
 *   wait queue of the queue and the return value 0). Then z_sched_wake()
 *   with c, which wakes no thread. The list is c.
 *
 * @ingroup kernel_unit_queue_k_queue_append_list
 * @see k_queue_append_list()
 */
ZTEST(queue_unit, test_list_append_list_hands_items_to_threads)
{
	struct k_queue queue;

	queue_prepare(&queue);
	kernel_unit_set_waiting_threads(2);
	LINK_ITEMS(a, b, c);

	zassert_equal(k_queue_append_list(&queue, a, c), 0);

	zassert_equal(z_sched_wake_fake.call_count, 3);
	zassert_equal_ptr(z_sched_wake_fake.arg0_history[0], &queue.wait_q);
	zassert_equal(z_sched_wake_fake.arg1_history[0], 0);
	zassert_equal_ptr(z_sched_wake_fake.arg2_history[0], a);
	zassert_equal_ptr(z_sched_wake_fake.arg2_history[1], b);
	zassert_equal_ptr(z_sched_wake_fake.arg2_history[2], c);
	zassert_queue_contents(&queue, c);
}

/**
 * @brief If more threads wait than the list has items, k_queue_append_list() stops at the end of
 * the list and appends nothing.
 *
 * @details
 * - Setup: an empty queue. Three threads wait. The items a, b are a
 *   NULL-terminated list.
 * - Action: k_queue_append_list() with head a and tail b.
 * - Expected: return value 0. Two calls of z_sched_wake(), with a and b.
 *   One thread still waits. The list is empty.
 *
 * @ingroup kernel_unit_queue_k_queue_append_list
 * @see k_queue_append_list()
 */
ZTEST(queue_unit, test_list_append_list_stops_at_end_of_list)
{
	struct k_queue queue;

	queue_prepare(&queue);
	kernel_unit_set_waiting_threads(3);
	LINK_ITEMS(a, b);

	zassert_equal(k_queue_append_list(&queue, a, b), 0);

	zassert_equal(z_sched_wake_fake.call_count, 2);
	zassert_equal(kernel_unit_waiting_threads, 1U);
	zassert_queue_empty(&queue);
}

/**
 * @brief k_queue_append_list() returns -EINVAL and does not lock the queue if head is NULL.
 *
 * @details
 * Applies with CONFIG_RUNTIME_ERROR_CHECKS (the default CHECKIF() option).
 * - Setup: the list of the queue is a.
 * - Action: k_queue_append_list() with head NULL and tail b.
 * - Expected: return value -EINVAL. The list is a. No calls to the layers
 *   below.
 *
 * @ingroup kernel_unit_queue_k_queue_append_list
 * @see k_queue_append_list()
 */
ZTEST(queue_unit, test_list_append_list_rejects_null_head)
{
	struct k_queue queue;

	if (!IS_ENABLED(CONFIG_RUNTIME_ERROR_CHECKS)) {
		ztest_test_skip();
	}

	queue_prepare(&queue);
	k_queue_append(&queue, a);
	reset_history();

	zassert_equal(k_queue_append_list(&queue, NULL, b), -EINVAL);

	zassert_queue_contents(&queue, a);
	zassert_equal(kernel_unit_history_len(), 0);
}

/**
 * @brief k_queue_append_list() returns -EINVAL and does not lock the queue if tail is NULL.
 *
 * @details
 * Applies with CONFIG_RUNTIME_ERROR_CHECKS (the default CHECKIF() option).
 * - Setup: the list of the queue is a. Item b is a list of one item.
 * - Action: k_queue_append_list() with head b and tail NULL.
 * - Expected: return value -EINVAL. The list is a. No calls to the layers
 *   below.
 *
 * @ingroup kernel_unit_queue_k_queue_append_list
 * @see k_queue_append_list()
 */
ZTEST(queue_unit, test_list_append_list_rejects_null_tail)
{
	struct k_queue queue;

	if (!IS_ENABLED(CONFIG_RUNTIME_ERROR_CHECKS)) {
		ztest_test_skip();
	}

	queue_prepare(&queue);
	k_queue_append(&queue, a);
	LINK_ITEMS(b);
	reset_history();

	zassert_equal(k_queue_append_list(&queue, b, NULL), -EINVAL);

	zassert_queue_contents(&queue, a);
	zassert_equal(kernel_unit_history_len(), 0);
}

/**
 * @brief With CONFIG_NO_RUNTIME_CHECKS, k_queue_append_list() accepts an empty list (head and tail
 * NULL) and returns 0.
 *
 * @details
 * CHECKIF() is empty, so the caller must give valid arguments.
 * - Setup: the list of the queue is a.
 * - Action: k_queue_append_list() with head NULL and tail NULL.
 * - Expected: return value 0. The list is a. No call of z_sched_wake().
 *   The queue was locked and released once.
 *
 * @ingroup kernel_unit_queue_k_queue_append_list
 * @see k_queue_append_list()
 */
ZTEST(queue_unit, test_list_append_list_no_runtime_checks_accepts_empty_list)
{
	struct k_queue queue;

	if (!IS_ENABLED(CONFIG_NO_RUNTIME_CHECKS)) {
		ztest_test_skip();
	}

	queue_prepare(&queue);
	k_queue_append(&queue, a);
	reset_history();
	RESET_FAKE(z_sched_wake);

	zassert_equal(k_queue_append_list(&queue, NULL, NULL), 0);

	zassert_queue_contents(&queue, a);
	zassert_equal(z_sched_wake_fake.call_count, 0);
	assert_lock_released_once(&queue, KERNEL_UNIT_RELEASED_BY_UNLOCK);
}

#ifdef CONFIG_ASSERT_ON_ERRORS
/**
 * @brief With CONFIG_ASSERT_ON_ERRORS, k_queue_append_list() asserts that head and tail are not
 * NULL.
 *
 * @details
 * - Action: k_queue_append_list() with head NULL and tail NULL, then with
 *   head a and tail NULL (each on a new queue), then with head a and tail
 *   a.
 * - Expected: one failed assertion for each of the first two calls,
 *   before the lock. No failed assertion for the third call. The fake
 *   assertion hook returns, so each call continues and returns 0.
 *
 * @ingroup kernel_unit_queue_k_queue_append_list
 * @see k_queue_append_list()
 */
ZTEST(queue_unit, test_list_append_list_assert_on_errors)
{
	struct k_queue queue;

	queue_prepare(&queue);
	zassert_equal(k_queue_append_list(&queue, NULL, NULL), 0);
	zassert_equal(assert_post_action_fake.call_count, 1);
	zassert_called_before(assert_post_action, unit_arch_irq_lock);

	queue_prepare(&queue);
	LINK_ITEMS(a);
	zassert_equal(k_queue_append_list(&queue, a, NULL), 0);
	zassert_equal(assert_post_action_fake.call_count, 2);

	queue_prepare(&queue);
	LINK_ITEMS(a);
	zassert_equal(k_queue_append_list(&queue, a, a), 0);
	zassert_equal(assert_post_action_fake.call_count, 2);
	zassert_queue_contents(&queue, a);
}
#endif /* CONFIG_ASSERT_ON_ERRORS */

/**
 * @brief k_queue_merge_slist() appends all items of the slist to the queue, makes the slist empty
 * and returns 0.
 *
 * @details
 * - Setup: the list of the queue is a. An slist has b and c. No thread
 *   waits.
 * - Action: k_queue_merge_slist().
 * - Expected: return value 0. The list of the queue is a, b, c. The slist
 *   is empty.
 *
 * @ingroup kernel_unit_queue_k_queue_merge_slist
 * @see k_queue_merge_slist()
 */
ZTEST(queue_unit, test_list_merge_slist_appends_and_empties_slist)
{
	struct k_queue queue;
	sys_slist_t list;

	queue_prepare(&queue);
	k_queue_append(&queue, a);
	sys_slist_init(&list);
	sys_slist_append(&list, (sys_snode_t *)b);
	sys_slist_append(&list, (sys_snode_t *)c);

	zassert_equal(k_queue_merge_slist(&queue, &list), 0);

	zassert_queue_contents(&queue, a, b, c);
	zassert_true(sys_slist_is_empty(&list));
	zassert_is_null(sys_slist_peek_tail(&list));
}

/**
 * @brief k_queue_merge_slist() returns -EINVAL and does not lock the queue if the slist is empty.
 *
 * @details
 * Applies with CONFIG_RUNTIME_ERROR_CHECKS (the default CHECKIF() option).
 * - Setup: the list of the queue is a. An empty slist.
 * - Action: k_queue_merge_slist().
 * - Expected: return value -EINVAL. The list is a. No calls to the layers
 *   below.
 *
 * @ingroup kernel_unit_queue_k_queue_merge_slist
 * @see k_queue_merge_slist()
 */
ZTEST(queue_unit, test_list_merge_slist_rejects_empty_slist)
{
	struct k_queue queue;
	sys_slist_t list;

	if (!IS_ENABLED(CONFIG_RUNTIME_ERROR_CHECKS)) {
		ztest_test_skip();
	}

	queue_prepare(&queue);
	k_queue_append(&queue, a);
	sys_slist_init(&list);
	reset_history();

	zassert_equal(k_queue_merge_slist(&queue, &list), -EINVAL);

	zassert_queue_contents(&queue, a);
	zassert_equal(kernel_unit_history_len(), 0);
}

/**
 * @brief If k_queue_append_list() fails, k_queue_merge_slist() returns its error and does not
 * change the slist.
 *
 * @details
 * Applies with CONFIG_RUNTIME_ERROR_CHECKS (the default CHECKIF() option).
 * A valid slist that is not empty has a tail, so this path needs an
 * invalid slist.
 * - Setup: an slist with the head b and no tail.
 * - Action: k_queue_merge_slist().
 * - Expected: return value -EINVAL. The slist still has the head b. The
 *   queue is empty.
 *
 * @ingroup kernel_unit_queue_k_queue_merge_slist
 * @see k_queue_merge_slist()
 */
ZTEST(queue_unit, test_list_merge_slist_keeps_slist_on_error)
{
	struct k_queue queue;
	sys_slist_t list;

	if (!IS_ENABLED(CONFIG_RUNTIME_ERROR_CHECKS)) {
		ztest_test_skip();
	}

	queue_prepare(&queue);
	LINK_ITEMS(b);
	list.head = (sys_snode_t *)b;
	list.tail = NULL;

	zassert_equal(k_queue_merge_slist(&queue, &list), -EINVAL);

	zassert_equal_ptr(list.head, (sys_snode_t *)b);
	zassert_queue_empty(&queue);
}

/**
 * @brief With CONFIG_NO_RUNTIME_CHECKS, k_queue_merge_slist() accepts an empty slist and returns
 * 0.
 *
 * @details
 * - Setup: the list of the queue is a. An empty slist.
 * - Action: k_queue_merge_slist().
 * - Expected: return value 0. The list is a. The slist is empty. The
 *   queue was locked and released once (in k_queue_append_list()).
 *
 * @ingroup kernel_unit_queue_k_queue_merge_slist
 * @see k_queue_merge_slist()
 */
ZTEST(queue_unit, test_list_merge_slist_no_runtime_checks_accepts_empty_slist)
{
	struct k_queue queue;
	sys_slist_t list;

	if (!IS_ENABLED(CONFIG_NO_RUNTIME_CHECKS)) {
		ztest_test_skip();
	}

	queue_prepare(&queue);
	k_queue_append(&queue, a);
	sys_slist_init(&list);
	reset_history();

	zassert_equal(k_queue_merge_slist(&queue, &list), 0);

	zassert_queue_contents(&queue, a);
	zassert_true(sys_slist_is_empty(&list));
	assert_lock_released_once(&queue, KERNEL_UNIT_RELEASED_BY_UNLOCK);
}

#ifdef CONFIG_ASSERT_ON_ERRORS
/**
 * @brief With CONFIG_ASSERT_ON_ERRORS, k_queue_merge_slist() asserts that the slist is not empty.
 *
 * @details
 * - Action: k_queue_merge_slist() with an empty slist, then with an slist
 *   that has b.
 * - Expected: for the empty slist, two failed assertions (in
 *   k_queue_merge_slist() and in k_queue_append_list()), and return value
 *   0. For the slist with b, no failed assertion, return value 0, and the
 *   queue has b.
 *
 * @ingroup kernel_unit_queue_k_queue_merge_slist
 * @see k_queue_merge_slist()
 */
ZTEST(queue_unit, test_list_merge_slist_assert_on_errors)
{
	struct k_queue queue;
	sys_slist_t list;

	queue_prepare(&queue);
	sys_slist_init(&list);
	zassert_equal(k_queue_merge_slist(&queue, &list), 0);
	zassert_equal(assert_post_action_fake.call_count, 2);

	sys_slist_append(&list, (sys_snode_t *)b);
	zassert_equal(k_queue_merge_slist(&queue, &list), 0);
	zassert_equal(assert_post_action_fake.call_count, 2);
	zassert_queue_contents(&queue, b);
}
#endif /* CONFIG_ASSERT_ON_ERRORS */

/*
 * Tests: Get. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_queue, at the top of this file.
 */

/**
 * @brief k_queue_get() removes the head item of the list and returns it.
 *
 * @details
 * - Setup: the list is a, b.
 * - Action: z_impl_k_queue_get() with K_NO_WAIT.
 * - Expected: return value a. The list is b.
 *
 * @ingroup kernel_unit_queue_k_queue_get
 * @see z_impl_k_queue_get()
 */
ZTEST(queue_unit, test_get_removes_head_item)
{
	struct k_queue queue;

	queue_prepare(&queue);
	k_queue_append(&queue, a);
	k_queue_append(&queue, b);

	zassert_equal_ptr(z_impl_k_queue_get(&queue, K_NO_WAIT), a);

	zassert_queue_contents(&queue, b);
}

/**
 * @brief If the list is not empty, k_queue_get() does not wait, also if the timeout permits a
 * wait.
 *
 * @details
 * - Setup: the list is a.
 * - Action: z_impl_k_queue_get() with K_FOREVER.
 * - Expected: return value a. No call of z_pend_curr(). The list is empty.
 *
 * @ingroup kernel_unit_queue_k_queue_get
 * @see z_impl_k_queue_get()
 */
ZTEST(queue_unit, test_get_with_data_does_not_wait)
{
	struct k_queue queue;

	queue_prepare(&queue);
	k_queue_append(&queue, a);

	zassert_equal_ptr(z_impl_k_queue_get(&queue, K_FOREVER), a);

	zassert_equal(z_pend_curr_fake.call_count, 0);
	zassert_queue_empty(&queue);
}

/**
 * @brief If the list is empty and the timeout is K_NO_WAIT, k_queue_get() returns NULL and does
 * not wait.
 *
 * @details
 * - Setup: an empty queue.
 * - Action: z_impl_k_queue_get() with K_NO_WAIT.
 * - Expected: return value NULL. No call of z_pend_curr().
 *
 * @ingroup kernel_unit_queue_k_queue_get
 * @see z_impl_k_queue_get()
 */
ZTEST(queue_unit, test_get_empty_no_wait_returns_null)
{
	struct k_queue queue;

	queue_prepare(&queue);

	zassert_is_null(z_impl_k_queue_get(&queue, K_NO_WAIT));

	zassert_equal(z_pend_curr_fake.call_count, 0);
}

/**
 * @brief If the list is empty and the timeout is not K_NO_WAIT, k_queue_get() waits on the wait
 * queue with this timeout.
 *
 * @details
 * - Setup: an empty queue.
 * - Action: z_impl_k_queue_get() with a timeout of 10 ticks.
 * - Expected: one call of z_pend_curr() with the lock of the queue, the
 *   key, the wait queue of the queue and the timeout.
 *
 * @ingroup kernel_unit_queue_k_queue_get
 * @see z_impl_k_queue_get()
 */
ZTEST(queue_unit, test_get_empty_waits_with_timeout)
{
	struct k_queue queue;

	queue_prepare(&queue);

	(void)z_impl_k_queue_get(&queue, TEST_TIMEOUT);

	zassert_equal(z_pend_curr_fake.call_count, 1);
	zassert_equal_ptr(z_pend_curr_fake.arg0_val, &queue.lock);
	zassert_equal((unsigned int)z_pend_curr_fake.arg1_val.key, KERNEL_UNIT_IRQ_KEY);
	zassert_equal_ptr(z_pend_curr_fake.arg2_val, &queue.wait_q);
	zassert_true(K_TIMEOUT_EQ(z_pend_curr_fake.arg3_val, TEST_TIMEOUT));
}

/**
 * @brief After a wait with the result 0, k_queue_get() returns the item that the scheduler gave
 * to the current thread.
 *
 * @details
 * - Setup: an empty queue. z_pend_curr() sets @c swap_data of the current
 *   thread to a and returns 0 (an insert function gave a to the thread).
 * - Action: z_impl_k_queue_get() with K_FOREVER.
 * - Expected: return value a. The list is empty.
 *
 * @ingroup kernel_unit_queue_k_queue_get
 * @see z_impl_k_queue_get()
 */
ZTEST(queue_unit, test_get_after_wait_returns_handed_item)
{
	struct k_queue queue;

	queue_prepare(&queue);
	kernel_unit_set_wait_result(a, 0);

	zassert_equal_ptr(z_impl_k_queue_get(&queue, K_FOREVER), a);

	zassert_queue_empty(&queue);
}

/**
 * @brief After a wait with a result other than 0, k_queue_get() returns NULL, also if swap_data is
 * set.
 *
 * @details
 * - Setup: an empty queue. z_pend_curr() sets @c swap_data of the current
 *   thread to a and returns -EAGAIN (timeout).
 * - Action: z_impl_k_queue_get() with a timeout of 10 ticks.
 * - Expected: return value NULL.
 *
 * @ingroup kernel_unit_queue_k_queue_get
 * @see z_impl_k_queue_get()
 */
ZTEST(queue_unit, test_get_after_timeout_returns_null)
{
	struct k_queue queue;

	queue_prepare(&queue);
	kernel_unit_set_wait_result(a, -EAGAIN);

	zassert_is_null(z_impl_k_queue_get(&queue, TEST_TIMEOUT));
}

/**
 * @brief In an ISR, a k_queue_get() that must wait reaches z_pend_curr(), and the scheduler
 * refuses it with a panic. queue.c has no earlier check.
 *
 * @details
 * The real z_pend_curr() refuses a call from an ISR in every build, before
 * it changes a thread or a wait queue.
 * - Setup: an empty queue. arch_is_in_isr() returns true. The scheduler
 *   model would give a with the result 0. The test expects the refusal of
 *   z_pend_curr().
 * - Action: z_impl_k_queue_get() with K_FOREVER.
 * - Expected: one call of z_pend_curr() with the lock of the queue. No call
 *   of arch_is_in_isr() by queue.c. The scheduler refuses the wait with a
 *   failed assertion (with CONFIG_ASSERT, the only one) and a panic. The
 *   model does not run. The lock stays locked, and the list stays empty.
 *   After the panic, the fake returns KERNEL_UNIT_PEND_REFUSED (a timeout),
 *   and k_queue_get() returns NULL.
 *
 * @ingroup kernel_unit_queue_k_queue_get
 * @see z_impl_k_queue_get()
 */
ZTEST(queue_unit, test_get_in_isr_with_wait_refused_by_scheduler)
{
	struct k_queue queue;

	queue_prepare(&queue);
	arch_is_in_isr_fake.return_val = true;
	kernel_unit_set_wait_result(a, 0);
	kernel_unit_expect_pend_refusal();

	zassert_is_null(z_impl_k_queue_get(&queue, K_FOREVER));

	kernel_unit_assert_pend_refused();
	zassert_equal(z_pend_curr_fake.call_count, 1);
	zassert_equal_ptr(z_pend_curr_fake.arg0_val, &queue.lock);
	zassert_equal(arch_is_in_isr_fake.call_count, 0);
	zassert_equal(unit_arch_irq_unlock_fake.call_count, 0);
	zassert_is_null(current_thread.base.swap_data, "the scheduler model ran");
	zassert_queue_empty(&queue);
#ifdef CONFIG_ASSERT
	zassert_equal(assert_post_action_fake.call_count, 1);
#endif
}

/**
 * @brief An item that an insert function gives to a waiting thread is the return value of the
 * k_queue_get() of this thread.
 *
 * @details
 * The test connects the two sides of the hand-over: the arguments of
 * z_sched_wake() in k_queue_append() become the result of the wait in
 * k_queue_get().
 * - Setup: an empty queue. One thread waits. k_queue_append() of a gives a
 *   to the thread.
 * - Action: z_impl_k_queue_get() with K_FOREVER, where z_pend_curr()
 *   returns the return value and the data of the z_sched_wake() call.
 * - Expected: return value a.
 *
 * @ingroup kernel_unit_queue_k_queue_get
 * @see z_impl_k_queue_get(), k_queue_append()
 */
ZTEST(queue_unit, test_get_receives_item_of_append)
{
	struct k_queue queue;

	queue_prepare(&queue);
	kernel_unit_set_waiting_threads(1);
	k_queue_append(&queue, a);
	zassert_equal(z_sched_wake_fake.call_count, 1);

	kernel_unit_set_wait_result(z_sched_wake_fake.arg2_val, z_sched_wake_fake.arg1_val);

	zassert_equal_ptr(z_impl_k_queue_get(&queue, K_FOREVER), a);
}

/*
 * Tests: Peek, remove and empty check. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_queue, at the top of this file.
 */

/**
 * @brief k_queue_peek_head() returns the head item and does not remove it.
 *
 * @details
 * - Setup: the list is a, b.
 * - Action: z_impl_k_queue_peek_head().
 * - Expected: return value a. The list is a, b.
 *
 * @ingroup kernel_unit_queue_k_queue_peek_head
 * @see z_impl_k_queue_peek_head()
 */
ZTEST(queue_unit, test_peek_head_returns_head_item)
{
	struct k_queue queue;

	queue_prepare(&queue);
	k_queue_append(&queue, a);
	k_queue_append(&queue, b);

	zassert_equal_ptr(z_impl_k_queue_peek_head(&queue), a);

	zassert_queue_contents(&queue, a, b);
}

/**
 * @brief k_queue_peek_tail() returns the tail item and does not remove it.
 *
 * @details
 * - Setup: the list is a, b.
 * - Action: z_impl_k_queue_peek_tail().
 * - Expected: return value b. The list is a, b.
 *
 * @ingroup kernel_unit_queue_k_queue_peek_tail
 * @see z_impl_k_queue_peek_tail()
 */
ZTEST(queue_unit, test_peek_tail_returns_tail_item)
{
	struct k_queue queue;

	queue_prepare(&queue);
	k_queue_append(&queue, a);
	k_queue_append(&queue, b);

	zassert_equal_ptr(z_impl_k_queue_peek_tail(&queue), b);

	zassert_queue_contents(&queue, a, b);
}

/**
 * @brief For an empty queue, k_queue_peek_head() and k_queue_peek_tail() return NULL.
 *
 * @details
 * - Setup: an empty queue.
 * - Action: z_impl_k_queue_peek_head(), z_impl_k_queue_peek_tail().
 * - Expected: return value NULL each time.
 *
 * @ingroup kernel_unit_queue_k_queue_peek_head
 * @see z_impl_k_queue_peek_head(), z_impl_k_queue_peek_tail(), z_queue_node_peek()
 */
ZTEST(queue_unit, test_peek_empty_returns_null)
{
	struct k_queue queue;

	queue_prepare(&queue);

	zassert_is_null(z_impl_k_queue_peek_head(&queue));
	zassert_is_null(z_impl_k_queue_peek_tail(&queue));
}

/**
 * @brief k_queue_is_empty() returns 1 if the list is empty, else 0, and does not lock the queue.
 *
 * @details
 * - Setup: an empty queue, then the list a.
 * - Action: z_impl_k_queue_is_empty() each time.
 * - Expected: return value 1, then 0. No lock.
 *
 * @ingroup kernel_unit_queue_k_queue_is_empty
 * @see z_impl_k_queue_is_empty()
 */
ZTEST(queue_unit, test_is_empty_reads_list_without_lock)
{
	struct k_queue queue;

	queue_prepare(&queue);
	zassert_equal(z_impl_k_queue_is_empty(&queue), 1);

	k_queue_append(&queue, a);
	reset_history();
	zassert_equal(z_impl_k_queue_is_empty(&queue), 0);

	zassert_equal(unit_arch_irq_lock_fake.call_count, 0);
}

/**
 * @brief k_queue_remove() removes the item from any position and returns true.
 *
 * @details
 * - Setup: the list is a, b, c.
 * - Action: k_queue_remove() of b, then of c, then of a.
 * - Expected: return value true each time. The list is a, c, then a (the
 *   tail is a again), then empty.
 *
 * @ingroup kernel_unit_queue_k_queue_remove
 * @see k_queue_remove()
 */
ZTEST(queue_unit, test_remove_removes_item_at_any_position)
{
	struct k_queue queue;

	queue_prepare(&queue);
	k_queue_append(&queue, a);
	k_queue_append(&queue, b);
	k_queue_append(&queue, c);

	zassert_true(k_queue_remove(&queue, b));
	zassert_queue_contents(&queue, a, c);

	zassert_true(k_queue_remove(&queue, c));
	zassert_queue_contents(&queue, a);

	zassert_true(k_queue_remove(&queue, a));
	zassert_queue_empty(&queue);
}

/**
 * @brief k_queue_remove() returns false and changes nothing if the item is not in the list.
 *
 * @details
 * - Setup: the list is a, b. Then an empty queue.
 * - Action: k_queue_remove() of c each time.
 * - Expected: return value false each time. The list does not change. No
 *   call of k_free().
 *
 * @ingroup kernel_unit_queue_k_queue_remove
 * @see k_queue_remove()
 */
ZTEST(queue_unit, test_remove_absent_item_returns_false)
{
	struct k_queue queue;

	queue_prepare(&queue);
	k_queue_append(&queue, a);
	k_queue_append(&queue, b);

	zassert_false(k_queue_remove(&queue, c));
	zassert_queue_contents(&queue, a, b);

	queue_prepare(&queue);
	zassert_false(k_queue_remove(&queue, c));
	zassert_queue_empty(&queue);

	zassert_equal(k_free_fake.call_count, 0);
}

/**
 * @brief k_queue_remove() removes only the first node with the item.
 *
 * @details
 * - Setup: z_impl_k_queue_alloc_append() of a, of b and again of a.
 * - Action: k_queue_remove() of a.
 * - Expected: return value true. The list is b, a. One call of k_free()
 *   with the first node.
 *
 * @ingroup kernel_unit_queue_k_queue_remove
 * @see k_queue_remove()
 */
ZTEST(queue_unit, test_remove_removes_first_match_only)
{
	struct k_queue queue;

	queue_prepare(&queue);
	zassert_equal(z_impl_k_queue_alloc_append(&queue, a), 0);
	zassert_equal(z_impl_k_queue_alloc_append(&queue, b), 0);
	zassert_equal(z_impl_k_queue_alloc_append(&queue, a), 0);

	zassert_true(k_queue_remove(&queue, a));

	zassert_queue_contents(&queue, b, a);
	zassert_equal(k_free_fake.call_count, 1);
	zassert_equal_ptr(k_free_fake.arg0_val, &node_pool[0]);
}

/*
 * Tests: Cancel a wait. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_queue, at the top of this file.
 */

/**
 * @brief k_queue_cancel_wait() wakes one waiting thread with the return value 0 and the data
 * NULL.
 *
 * @details
 * - Setup: an empty queue. Two threads wait.
 * - Action: z_impl_k_queue_cancel_wait().
 * - Expected: one call of z_sched_wake() with the wait queue of the queue,
 *   0 and NULL. One thread still waits.
 *
 * @ingroup kernel_unit_queue_k_queue_cancel_wait
 * @see z_impl_k_queue_cancel_wait()
 */
ZTEST(queue_unit, test_cancel_wait_wakes_one_thread_with_null)
{
	struct k_queue queue;

	queue_prepare(&queue);
	kernel_unit_set_waiting_threads(2);

	z_impl_k_queue_cancel_wait(&queue);

	zassert_equal(z_sched_wake_fake.call_count, 1);
	zassert_equal_ptr(z_sched_wake_fake.arg0_val, &queue.wait_q);
	zassert_equal(z_sched_wake_fake.arg1_val, 0);
	zassert_is_null(z_sched_wake_fake.arg2_val);
	zassert_equal(kernel_unit_waiting_threads, 1U);
}

/**
 * @brief The k_queue_get() of a thread that k_queue_cancel_wait() woke returns NULL.
 *
 * @details
 * - Setup: an empty queue. One thread waits. z_impl_k_queue_cancel_wait()
 *   wakes it.
 * - Action: z_impl_k_queue_get() with K_FOREVER, where z_pend_curr()
 *   returns the return value and the data of the z_sched_wake() call.
 * - Expected: return value NULL.
 *
 * @ingroup kernel_unit_queue_k_queue_cancel_wait
 * @see z_impl_k_queue_cancel_wait(), z_impl_k_queue_get()
 */
ZTEST(queue_unit, test_cancel_wait_makes_get_return_null)
{
	struct k_queue queue;

	queue_prepare(&queue);
	kernel_unit_set_waiting_threads(1);
	z_impl_k_queue_cancel_wait(&queue);
	zassert_equal(z_sched_wake_fake.call_count, 1);

	kernel_unit_set_wait_result(z_sched_wake_fake.arg2_val, z_sched_wake_fake.arg1_val);

	zassert_is_null(z_impl_k_queue_get(&queue, K_FOREVER));
}

/**
 * @brief k_queue_cancel_wait() does not change the list.
 *
 * @details
 * - Setup: the list is a, b. No thread waits.
 * - Action: z_impl_k_queue_cancel_wait().
 * - Expected: the list is a, b.
 *
 * @ingroup kernel_unit_queue_k_queue_cancel_wait
 * @see z_impl_k_queue_cancel_wait()
 */
ZTEST(queue_unit, test_cancel_wait_keeps_list)
{
	struct k_queue queue;

	queue_prepare(&queue);
	k_queue_append(&queue, a);
	k_queue_append(&queue, b);

	z_impl_k_queue_cancel_wait(&queue);

	zassert_queue_contents(&queue, a, b);
}

/*
 * Tests: Poll events. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_queue, at the top of this file.
 */

#ifdef CONFIG_POLL
/**
 * @brief With CONFIG_POLL, an insert function signals K_POLL_STATE_DATA_AVAILABLE after the item
 * is in the list.
 *
 * @details
 * - Setup: an empty queue. No thread waits.
 * - Action: k_queue_append() of a.
 * - Expected: one call of z_handle_obj_poll_events() with the poll events
 *   of the queue and K_POLL_STATE_DATA_AVAILABLE. At this call, the list
 *   has one item.
 *
 * @ingroup kernel_unit_queue_k_queue_append
 * @see k_queue_append()
 * @see queue_insert(), queue_handle_poll_events()
 */
ZTEST(queue_unit, test_poll_insert_signals_after_insert)
{
	struct k_queue queue;

	queue_prepare(&queue);
	spy_on_lock(&queue);
	z_handle_obj_poll_events_fake.custom_fake = poll_spy;

	k_queue_append(&queue, a);

	zassert_equal(z_handle_obj_poll_events_fake.call_count, 1);
	zassert_equal_ptr(z_handle_obj_poll_events_fake.arg0_val, &queue.poll_events);
	zassert_equal(z_handle_obj_poll_events_fake.arg1_val, K_POLL_STATE_DATA_AVAILABLE);
	zassert_equal(len_at_poll, 1U);
}

/**
 * @brief With CONFIG_POLL, k_queue_append_list() signals K_POLL_STATE_DATA_AVAILABLE after the
 * items are in the list.
 *
 * @details
 * - Setup: an empty queue. No thread waits. The items a, b are a
 *   NULL-terminated list.
 * - Action: k_queue_append_list() with head a and tail b.
 * - Expected: one call of z_handle_obj_poll_events() with the poll events
 *   of the queue and K_POLL_STATE_DATA_AVAILABLE. At this call, the list
 *   has two items.
 *
 * @ingroup kernel_unit_queue_k_queue_append_list
 * @see k_queue_append_list()
 */
ZTEST(queue_unit, test_poll_append_list_signals_after_append)
{
	struct k_queue queue;

	queue_prepare(&queue);
	spy_on_lock(&queue);
	z_handle_obj_poll_events_fake.custom_fake = poll_spy;
	LINK_ITEMS(a, b);

	zassert_equal(k_queue_append_list(&queue, a, b), 0);

	zassert_equal(z_handle_obj_poll_events_fake.call_count, 1);
	zassert_equal_ptr(z_handle_obj_poll_events_fake.arg0_val, &queue.poll_events);
	zassert_equal(z_handle_obj_poll_events_fake.arg1_val, K_POLL_STATE_DATA_AVAILABLE);
	zassert_equal(len_at_poll, 2U);
}
#endif /* CONFIG_POLL */

/**
 * @brief If an insert function gives the item to a waiting thread, it does not signal the poll
 * events.
 *
 * @details
 * - Setup: an empty queue. One thread waits.
 * - Action: k_queue_append() of a.
 * - Expected: no call of z_handle_obj_poll_events().
 *
 * @ingroup kernel_unit_queue_k_queue_append
 * @see k_queue_append()
 * @see queue_insert()
 */
ZTEST(queue_unit, test_poll_insert_no_signal_after_handover)
{
	struct k_queue queue;

	if (!IS_ENABLED(CONFIG_POLL)) {
		ztest_test_skip();
	}

	queue_prepare(&queue);
	kernel_unit_set_waiting_threads(1);

	k_queue_append(&queue, a);

	zassert_equal(z_handle_obj_poll_events_fake.call_count, 0);
}

/**
 * @brief If an alloc function returns -ENOMEM, it does not signal the poll events.
 *
 * @details
 * - Setup: an empty queue. No thread waits. z_thread_malloc() returns
 *   NULL.
 * - Action: z_impl_k_queue_alloc_append() of a.
 * - Expected: return value -ENOMEM. No call of z_handle_obj_poll_events().
 *
 * @ingroup kernel_unit_queue_k_queue_alloc_append
 * @see z_impl_k_queue_alloc_append()
 * @see queue_insert()
 */
ZTEST(queue_unit, test_poll_insert_no_signal_on_enomem)
{
	struct k_queue queue;

	if (!IS_ENABLED(CONFIG_POLL)) {
		ztest_test_skip();
	}

	queue_prepare(&queue);
	z_thread_malloc_fake.custom_fake = NULL;

	zassert_equal(z_impl_k_queue_alloc_append(&queue, a), -ENOMEM);

	zassert_equal(z_handle_obj_poll_events_fake.call_count, 0);
}

/**
 * @brief With CONFIG_POLL, k_queue_append_list() signals K_POLL_STATE_DATA_AVAILABLE also if all
 * items went to waiting threads and the list is empty.
 *
 * @details
 * - Setup: an empty queue. Two threads wait. The items a, b are a
 *   NULL-terminated list.
 * - Action: k_queue_append_list() with head a and tail b.
 * - Expected: the list is empty. One call of z_handle_obj_poll_events()
 *   with K_POLL_STATE_DATA_AVAILABLE, after the last call of
 *   z_sched_wake().
 *
 * @ingroup kernel_unit_queue_k_queue_append_list
 * @see k_queue_append_list()
 */
ZTEST(queue_unit, test_poll_append_list_signals_after_handover)
{
	struct k_queue queue;

	if (!IS_ENABLED(CONFIG_POLL)) {
		ztest_test_skip();
	}

	queue_prepare(&queue);
	kernel_unit_set_waiting_threads(2);
	LINK_ITEMS(a, b);

	zassert_equal(k_queue_append_list(&queue, a, b), 0);

	zassert_queue_empty(&queue);
	zassert_equal(z_handle_obj_poll_events_fake.call_count, 1);
	zassert_equal(z_handle_obj_poll_events_fake.arg1_val, K_POLL_STATE_DATA_AVAILABLE);
	zassert_true(kernel_unit_history_index(KERNEL_UNIT_FN(z_sched_wake), 1) <
		     kernel_unit_history_index(KERNEL_UNIT_FN(z_handle_obj_poll_events), 0));
}

/**
 * @brief With CONFIG_POLL, k_queue_cancel_wait() signals K_POLL_STATE_CANCELLED after the wake,
 * also if it woke a thread.
 *
 * @details
 * - Setup: an empty queue. One thread waits. Then no thread waits.
 * - Action: z_impl_k_queue_cancel_wait() each time.
 * - Expected: each time one call of z_handle_obj_poll_events() with the
 *   poll events of the queue and K_POLL_STATE_CANCELLED, after
 *   z_sched_wake().
 *
 * @ingroup kernel_unit_queue_k_queue_cancel_wait
 * @see z_impl_k_queue_cancel_wait()
 */
ZTEST(queue_unit, test_poll_cancel_wait_signals_cancelled)
{
	struct k_queue queue;

	if (!IS_ENABLED(CONFIG_POLL)) {
		ztest_test_skip();
	}

	queue_prepare(&queue);
	kernel_unit_set_waiting_threads(1);

	z_impl_k_queue_cancel_wait(&queue);
	z_impl_k_queue_cancel_wait(&queue);

	zassert_equal(z_handle_obj_poll_events_fake.call_count, 2);
	zassert_equal(z_handle_obj_poll_events_fake.arg1_history[0], K_POLL_STATE_CANCELLED);
	zassert_equal(z_handle_obj_poll_events_fake.arg1_history[1], K_POLL_STATE_CANCELLED);
	zassert_called_before(z_sched_wake, z_handle_obj_poll_events);
	zassert_equal(kernel_unit_waiting_threads, 0U);
}

/**
 * @brief k_queue_get(), k_queue_remove(), the peek functions and k_queue_unique_append() of an
 * item in the list do not signal the poll events.
 *
 * @details
 * - Setup: the list is a, b, c.
 * - Action: z_impl_k_queue_peek_head(), z_impl_k_queue_peek_tail(),
 *   k_queue_unique_append() of b, k_queue_remove() of b,
 *   z_impl_k_queue_get() with K_NO_WAIT.
 * - Expected: no call of z_handle_obj_poll_events().
 *
 * @ingroup kernel_unit_queue_k_queue_get
 * @see z_impl_k_queue_get(), k_queue_remove(), k_queue_unique_append()
 */
ZTEST(queue_unit, test_poll_read_and_remove_do_not_signal)
{
	struct k_queue queue;

	queue_prepare(&queue);
	k_queue_append(&queue, a);
	k_queue_append(&queue, b);
	k_queue_append(&queue, c);
	RESET_FAKE(z_handle_obj_poll_events);

	(void)z_impl_k_queue_peek_head(&queue);
	(void)z_impl_k_queue_peek_tail(&queue);
	zassert_false(k_queue_unique_append(&queue, b));
	zassert_true(k_queue_remove(&queue, b));
	zassert_equal_ptr(z_impl_k_queue_get(&queue, K_NO_WAIT), a);

	zassert_equal(z_handle_obj_poll_events_fake.call_count, 0);
}

#ifndef CONFIG_POLL
/**
 * @brief Without CONFIG_POLL, the insert, list and cancel functions do not call the poll
 * subsystem.
 *
 * @details
 * - Setup: an empty queue. No thread waits.
 * - Action: k_queue_append() of a, k_queue_append_list() of b, c,
 *   z_impl_k_queue_cancel_wait().
 * - Expected: no call of z_handle_obj_poll_events(). Each operation
 *   releases the lock with k_spin_unlock() (no reschedule).
 *
 * @ingroup kernel_unit_queue_static
 * @see queue_handle_poll_events()
 */
ZTEST(queue_unit, test_poll_not_called_without_config)
{
	struct k_queue queue;

	queue_prepare(&queue);
	LINK_ITEMS(b, c);

	k_queue_append(&queue, a);
	zassert_equal(k_queue_append_list(&queue, b, c), 0);
	z_impl_k_queue_cancel_wait(&queue);

	zassert_equal(z_handle_obj_poll_events_fake.call_count, 0);
	zassert_equal(z_reschedule_fake.call_count, 0);
	zassert_equal(unit_arch_irq_unlock_fake.call_count, 3);
}
#endif /* !CONFIG_POLL */

/*
 * Tests: Locking. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_queue, at the top of this file.
 */

/**
 * @brief If an insert function makes no thread ready, it releases the lock with k_spin_unlock().
 *
 * @details
 * - Setup: an empty queue. No thread waits. No polling thread becomes
 *   ready.
 * - Action: k_queue_append() of a.
 * - Expected calls: arch_irq_lock(), z_sched_wake(),
 *   z_handle_obj_poll_events() (with CONFIG_POLL), arch_irq_unlock() with
 *   the key.
 *
 * @ingroup kernel_unit_queue_k_queue_append
 * @see k_queue_append(), queue_insert()
 */
ZTEST(queue_unit, test_lock_insert_no_ready_thread_unlocks)
{
	struct k_queue queue;

	queue_prepare(&queue);

	k_queue_append(&queue, a);

	zassert_call_history(unit_arch_irq_lock, z_sched_wake,
			     KERNEL_UNIT_IF_ENABLED(CONFIG_POLL, z_handle_obj_poll_events),
			     unit_arch_irq_unlock);
	assert_lock_released_once(&queue, KERNEL_UNIT_RELEASED_BY_UNLOCK);
}

/**
 * @brief If an insert function gives the item to a waiting thread, it releases the lock with
 * z_reschedule().
 *
 * @details
 * - Setup: an empty queue. One thread waits.
 * - Action: k_queue_prepend() of a.
 * - Expected calls: arch_irq_lock(), z_sched_wake(), z_reschedule() with
 *   the lock of the queue and the key.
 *
 * @ingroup kernel_unit_queue_k_queue_prepend
 * @see k_queue_prepend(), queue_insert()
 */
ZTEST(queue_unit, test_lock_insert_handover_reschedules)
{
	struct k_queue queue;

	queue_prepare(&queue);
	kernel_unit_set_waiting_threads(1);

	k_queue_prepend(&queue, a);

	zassert_call_history(unit_arch_irq_lock, z_sched_wake, z_reschedule);
	assert_lock_released_once(&queue, KERNEL_UNIT_RELEASED_BY_RESCHEDULE);
}

/**
 * @brief With CONFIG_POLL, if an insert function makes a polling thread ready, it releases the
 * lock with z_reschedule().
 *
 * @details
 * - Setup: an empty queue. No thread waits. z_handle_obj_poll_events()
 *   returns true.
 * - Action: k_queue_insert() of a with prev NULL.
 * - Expected calls: arch_irq_lock(), z_sched_wake(),
 *   z_handle_obj_poll_events(), z_reschedule() with the lock of the queue
 *   and the key.
 *
 * @ingroup kernel_unit_queue_k_queue_insert
 * @see k_queue_insert(), queue_insert()
 */
ZTEST(queue_unit, test_lock_insert_poll_ready_reschedules)
{
	struct k_queue queue;

	if (!IS_ENABLED(CONFIG_POLL)) {
		ztest_test_skip();
	}

	queue_prepare(&queue);
	z_handle_obj_poll_events_fake.return_val = true;

	k_queue_insert(&queue, NULL, a);

	zassert_call_history(unit_arch_irq_lock, z_sched_wake, z_handle_obj_poll_events,
			     z_reschedule);
	assert_lock_released_once(&queue, KERNEL_UNIT_RELEASED_BY_RESCHEDULE);
}

/**
 * @brief The alloc functions allocate the wrapper node after the wake attempt and while the lock
 * is held.
 *
 * @details
 * - Setup: an empty queue. No thread waits.
 * - Action: z_impl_k_queue_alloc_append() of a.
 * - Expected calls: arch_irq_lock(), z_sched_wake(), z_thread_malloc(),
 *   z_handle_obj_poll_events() (with CONFIG_POLL), arch_irq_unlock() with
 *   the key.
 *
 * @ingroup kernel_unit_queue_k_queue_alloc_append
 * @see z_impl_k_queue_alloc_append(), queue_insert()
 */
ZTEST(queue_unit, test_lock_alloc_allocates_under_lock)
{
	struct k_queue queue;

	queue_prepare(&queue);

	zassert_equal(z_impl_k_queue_alloc_append(&queue, a), 0);

	zassert_call_history(unit_arch_irq_lock, z_sched_wake, z_thread_malloc,
			     KERNEL_UNIT_IF_ENABLED(CONFIG_POLL, z_handle_obj_poll_events),
			     unit_arch_irq_unlock);
	assert_lock_released_once(&queue, KERNEL_UNIT_RELEASED_BY_UNLOCK);
}

/**
 * @brief If the allocation fails, the alloc functions release the lock with k_spin_unlock().
 *
 * @details
 * - Setup: an empty queue. No thread waits. z_thread_malloc() returns
 *   NULL.
 * - Action: z_impl_k_queue_alloc_prepend() of a.
 * - Expected calls: arch_irq_lock(), z_sched_wake(), z_thread_malloc(),
 *   arch_irq_unlock() with the key.
 *
 * @ingroup kernel_unit_queue_k_queue_alloc_prepend
 * @see z_impl_k_queue_alloc_prepend(), queue_insert()
 */
ZTEST(queue_unit, test_lock_alloc_no_memory_unlocks)
{
	struct k_queue queue;

	queue_prepare(&queue);
	z_thread_malloc_fake.custom_fake = NULL;

	zassert_equal(z_impl_k_queue_alloc_prepend(&queue, a), -ENOMEM);

	zassert_call_history(unit_arch_irq_lock, z_sched_wake, z_thread_malloc,
			     unit_arch_irq_unlock);
	assert_lock_released_once(&queue, KERNEL_UNIT_RELEASED_BY_UNLOCK);
}

/**
 * @brief k_queue_unique_append() of a new item locks the queue once and gives the key to
 * queue_insert().
 *
 * @details
 * - Setup: the list is a. No thread waits.
 * - Action: k_queue_unique_append() of b.
 * - Expected calls: arch_irq_lock(), z_sched_wake(),
 *   z_handle_obj_poll_events() (with CONFIG_POLL), arch_irq_unlock() with
 *   the key.
 *
 * @ingroup kernel_unit_queue_k_queue_unique_append
 * @see k_queue_unique_append()
 */
ZTEST(queue_unit, test_lock_unique_append_new_item_locks_once)
{
	struct k_queue queue;

	queue_prepare(&queue);
	k_queue_append(&queue, a);
	reset_history();
	RESET_FAKE(z_sched_wake);

	zassert_true(k_queue_unique_append(&queue, b));

	zassert_call_history(unit_arch_irq_lock, z_sched_wake,
			     KERNEL_UNIT_IF_ENABLED(CONFIG_POLL, z_handle_obj_poll_events),
			     unit_arch_irq_unlock);
	assert_lock_released_once(&queue, KERNEL_UNIT_RELEASED_BY_UNLOCK);
}

/**
 * @brief If k_queue_unique_append() finds the item, it releases the lock with k_spin_unlock().
 *
 * @details
 * - Setup: the list is a.
 * - Action: k_queue_unique_append() of a.
 * - Expected calls: arch_irq_lock(), arch_irq_unlock() with the key.
 *
 * @ingroup kernel_unit_queue_k_queue_unique_append
 * @see k_queue_unique_append()
 */
ZTEST(queue_unit, test_lock_unique_append_duplicate_unlocks)
{
	struct k_queue queue;

	queue_prepare(&queue);
	k_queue_append(&queue, a);
	reset_history();

	zassert_false(k_queue_unique_append(&queue, a));

	zassert_call_history(unit_arch_irq_lock, unit_arch_irq_unlock);
	assert_lock_released_once(&queue, KERNEL_UNIT_RELEASED_BY_UNLOCK);
}

/**
 * @brief If k_queue_append_list() makes no thread ready, it releases the lock with
 * k_spin_unlock().
 *
 * @details
 * - Setup: an empty queue. No thread waits. The items a, b are a list.
 * - Action: k_queue_append_list() with head a and tail b.
 * - Expected calls: arch_irq_lock(), z_sched_wake(),
 *   z_handle_obj_poll_events() (with CONFIG_POLL), arch_irq_unlock() with
 *   the key.
 *
 * @ingroup kernel_unit_queue_k_queue_append_list
 * @see k_queue_append_list()
 */
ZTEST(queue_unit, test_lock_append_list_no_ready_thread_unlocks)
{
	struct k_queue queue;

	queue_prepare(&queue);
	LINK_ITEMS(a, b);

	zassert_equal(k_queue_append_list(&queue, a, b), 0);

	zassert_call_history(unit_arch_irq_lock, z_sched_wake,
			     KERNEL_UNIT_IF_ENABLED(CONFIG_POLL, z_handle_obj_poll_events),
			     unit_arch_irq_unlock);
	assert_lock_released_once(&queue, KERNEL_UNIT_RELEASED_BY_UNLOCK);
}

/**
 * @brief If k_queue_append_list() gives items to waiting threads, it releases the lock once with
 * z_reschedule() after the last wake.
 *
 * @details
 * - Setup: an empty queue. Two threads wait. The items a, b, c are a list.
 * - Action: k_queue_append_list() with head a and tail c.
 * - Expected calls: arch_irq_lock(), z_sched_wake() three times,
 *   z_handle_obj_poll_events() (with CONFIG_POLL), z_reschedule() with the
 *   lock of the queue and the key.
 *
 * @ingroup kernel_unit_queue_k_queue_append_list
 * @see k_queue_append_list()
 */
ZTEST(queue_unit, test_lock_append_list_handover_reschedules)
{
	struct k_queue queue;

	queue_prepare(&queue);
	kernel_unit_set_waiting_threads(2);
	LINK_ITEMS(a, b, c);

	zassert_equal(k_queue_append_list(&queue, a, c), 0);

	zassert_call_history(unit_arch_irq_lock, z_sched_wake, z_sched_wake, z_sched_wake,
			     KERNEL_UNIT_IF_ENABLED(CONFIG_POLL, z_handle_obj_poll_events),
			     z_reschedule);
	assert_lock_released_once(&queue, KERNEL_UNIT_RELEASED_BY_RESCHEDULE);
}

/**
 * @brief With CONFIG_POLL, if k_queue_append_list() makes a polling thread ready, it releases the
 * lock with z_reschedule().
 *
 * @details
 * - Setup: an empty queue. No thread waits. z_handle_obj_poll_events()
 *   returns true. The items a, b are a list.
 * - Action: k_queue_append_list() with head a and tail b.
 * - Expected calls: arch_irq_lock(), z_sched_wake(),
 *   z_handle_obj_poll_events(), z_reschedule() with the lock of the queue
 *   and the key.
 *
 * @ingroup kernel_unit_queue_k_queue_append_list
 * @see k_queue_append_list()
 */
ZTEST(queue_unit, test_lock_append_list_poll_ready_reschedules)
{
	struct k_queue queue;

	if (!IS_ENABLED(CONFIG_POLL)) {
		ztest_test_skip();
	}

	queue_prepare(&queue);
	z_handle_obj_poll_events_fake.return_val = true;
	LINK_ITEMS(a, b);

	zassert_equal(k_queue_append_list(&queue, a, b), 0);

	zassert_call_history(unit_arch_irq_lock, z_sched_wake, z_handle_obj_poll_events,
			     z_reschedule);
	assert_lock_released_once(&queue, KERNEL_UNIT_RELEASED_BY_RESCHEDULE);
}

/**
 * @brief If k_queue_cancel_wait() makes no thread ready, it releases the lock with
 * k_spin_unlock().
 *
 * @details
 * - Setup: an empty queue. No thread waits. No polling thread becomes
 *   ready.
 * - Action: z_impl_k_queue_cancel_wait().
 * - Expected calls: arch_irq_lock(), z_sched_wake(),
 *   z_handle_obj_poll_events() (with CONFIG_POLL), arch_irq_unlock() with
 *   the key.
 *
 * @ingroup kernel_unit_queue_k_queue_cancel_wait
 * @see z_impl_k_queue_cancel_wait()
 */
ZTEST(queue_unit, test_lock_cancel_wait_no_ready_thread_unlocks)
{
	struct k_queue queue;

	queue_prepare(&queue);

	z_impl_k_queue_cancel_wait(&queue);

	zassert_call_history(unit_arch_irq_lock, z_sched_wake,
			     KERNEL_UNIT_IF_ENABLED(CONFIG_POLL, z_handle_obj_poll_events),
			     unit_arch_irq_unlock);
	assert_lock_released_once(&queue, KERNEL_UNIT_RELEASED_BY_UNLOCK);
}

/**
 * @brief If k_queue_cancel_wait() wakes a thread, it releases the lock with z_reschedule().
 *
 * @details
 * - Setup: an empty queue. One thread waits.
 * - Action: z_impl_k_queue_cancel_wait().
 * - Expected calls: arch_irq_lock(), z_sched_wake(),
 *   z_handle_obj_poll_events() (with CONFIG_POLL), z_reschedule() with the
 *   lock of the queue and the key.
 *
 * @ingroup kernel_unit_queue_k_queue_cancel_wait
 * @see z_impl_k_queue_cancel_wait()
 */
ZTEST(queue_unit, test_lock_cancel_wait_wake_reschedules)
{
	struct k_queue queue;

	queue_prepare(&queue);
	kernel_unit_set_waiting_threads(1);

	z_impl_k_queue_cancel_wait(&queue);

	zassert_call_history(unit_arch_irq_lock, z_sched_wake,
			     KERNEL_UNIT_IF_ENABLED(CONFIG_POLL, z_handle_obj_poll_events),
			     z_reschedule);
	assert_lock_released_once(&queue, KERNEL_UNIT_RELEASED_BY_RESCHEDULE);
}

/**
 * @brief With CONFIG_POLL, if k_queue_cancel_wait() makes a polling thread ready, it releases the
 * lock with z_reschedule().
 *
 * @details
 * - Setup: an empty queue. No thread waits. z_handle_obj_poll_events()
 *   returns true.
 * - Action: z_impl_k_queue_cancel_wait().
 * - Expected calls: arch_irq_lock(), z_sched_wake(),
 *   z_handle_obj_poll_events(), z_reschedule() with the lock of the queue
 *   and the key.
 *
 * @ingroup kernel_unit_queue_k_queue_cancel_wait
 * @see z_impl_k_queue_cancel_wait()
 */
ZTEST(queue_unit, test_lock_cancel_wait_poll_ready_reschedules)
{
	struct k_queue queue;

	if (!IS_ENABLED(CONFIG_POLL)) {
		ztest_test_skip();
	}

	queue_prepare(&queue);
	z_handle_obj_poll_events_fake.return_val = true;

	z_impl_k_queue_cancel_wait(&queue);

	zassert_call_history(unit_arch_irq_lock, z_sched_wake, z_handle_obj_poll_events,
			     z_reschedule);
	assert_lock_released_once(&queue, KERNEL_UNIT_RELEASED_BY_RESCHEDULE);
}

/**
 * @brief If the list is not empty, k_queue_get() frees a wrapper node while the lock is held and
 * then releases the lock with k_spin_unlock().
 *
 * @details
 * - Setup: z_impl_k_queue_alloc_append() of a.
 * - Action: z_impl_k_queue_get() with K_FOREVER.
 * - Expected calls: arch_irq_lock(), k_free(), arch_irq_unlock() with the
 *   key.
 *
 * @ingroup kernel_unit_queue_k_queue_get
 * @see z_impl_k_queue_get()
 */
ZTEST(queue_unit, test_lock_get_data_frees_under_lock)
{
	struct k_queue queue;

	queue_prepare(&queue);
	zassert_equal(z_impl_k_queue_alloc_append(&queue, a), 0);
	reset_history();

	zassert_equal_ptr(z_impl_k_queue_get(&queue, K_FOREVER), a);

	zassert_call_history(unit_arch_irq_lock, k_free, unit_arch_irq_unlock);
	assert_lock_released_once(&queue, KERNEL_UNIT_RELEASED_BY_UNLOCK);
}

/**
 * @brief If k_queue_get() returns NULL without a wait, it releases the lock with k_spin_unlock().
 *
 * @details
 * - Setup: an empty queue.
 * - Action: z_impl_k_queue_get() with K_NO_WAIT.
 * - Expected calls: arch_irq_lock(), arch_irq_unlock() with the key.
 *
 * @ingroup kernel_unit_queue_k_queue_get
 * @see z_impl_k_queue_get()
 */
ZTEST(queue_unit, test_lock_get_no_wait_unlocks)
{
	struct k_queue queue;

	queue_prepare(&queue);

	zassert_is_null(z_impl_k_queue_get(&queue, K_NO_WAIT));

	zassert_call_history(unit_arch_irq_lock, unit_arch_irq_unlock);
	assert_lock_released_once(&queue, KERNEL_UNIT_RELEASED_BY_UNLOCK);
}

/**
 * @brief If k_queue_get() waits, z_pend_curr() releases the lock, and k_queue_get() does not
 * release it again.
 *
 * @details
 * - Setup: an empty queue. The wait gives a.
 * - Action: z_impl_k_queue_get() with K_FOREVER.
 * - Expected calls: arch_irq_lock(), z_pend_curr() with the lock of the
 *   queue and the key. No call after z_pend_curr().
 *
 * @ingroup kernel_unit_queue_k_queue_get
 * @see z_impl_k_queue_get()
 */
ZTEST(queue_unit, test_lock_get_wait_hands_lock_to_pend)
{
	struct k_queue queue;

	queue_prepare(&queue);
	kernel_unit_set_wait_result(a, 0);

	zassert_equal_ptr(z_impl_k_queue_get(&queue, K_FOREVER), a);

	zassert_call_history(unit_arch_irq_lock, z_pend_curr);
	assert_lock_released_once(&queue, KERNEL_UNIT_RELEASED_BY_PEND);
}

/**
 * @brief k_queue_remove() frees a wrapper node while the lock is held and releases the lock with
 * k_spin_unlock().
 *
 * @details
 * - Setup: z_impl_k_queue_alloc_append() of a.
 * - Action: k_queue_remove() of a, then (new history) k_queue_remove() of
 *   b, which is not in the list.
 * - Expected calls: arch_irq_lock(), k_free(), arch_irq_unlock() with the
 *   key. Then arch_irq_lock(), arch_irq_unlock() with the key.
 *
 * @ingroup kernel_unit_queue_k_queue_remove
 * @see k_queue_remove()
 */
ZTEST(queue_unit, test_lock_remove_unlocks)
{
	struct k_queue queue;

	queue_prepare(&queue);
	zassert_equal(z_impl_k_queue_alloc_append(&queue, a), 0);
	reset_history();

	zassert_true(k_queue_remove(&queue, a));
	zassert_call_history(unit_arch_irq_lock, k_free, unit_arch_irq_unlock);
	assert_lock_released_once(&queue, KERNEL_UNIT_RELEASED_BY_UNLOCK);

	reset_history();
	zassert_false(k_queue_remove(&queue, b));
	zassert_call_history(unit_arch_irq_lock, unit_arch_irq_unlock);
	assert_lock_released_once(&queue, KERNEL_UNIT_RELEASED_BY_UNLOCK);
}

/**
 * @brief k_queue_peek_head() and k_queue_peek_tail() release the lock with k_spin_unlock().
 *
 * @details
 * - Setup: the list is a.
 * - Action: z_impl_k_queue_peek_head(), then (new history)
 *   z_impl_k_queue_peek_tail().
 * - Expected calls each time: arch_irq_lock(), arch_irq_unlock() with the
 *   key.
 *
 * @ingroup kernel_unit_queue_k_queue_peek_head
 * @see z_impl_k_queue_peek_head(), z_impl_k_queue_peek_tail()
 */
ZTEST(queue_unit, test_lock_peek_unlocks)
{
	struct k_queue queue;

	queue_prepare(&queue);
	k_queue_append(&queue, a);
	reset_history();

	zassert_equal_ptr(z_impl_k_queue_peek_head(&queue), a);
	zassert_call_history(unit_arch_irq_lock, unit_arch_irq_unlock);
	assert_lock_released_once(&queue, KERNEL_UNIT_RELEASED_BY_UNLOCK);

	reset_history();
	zassert_equal_ptr(z_impl_k_queue_peek_tail(&queue), a);
	zassert_call_history(unit_arch_irq_lock, unit_arch_irq_unlock);
	assert_lock_released_once(&queue, KERNEL_UNIT_RELEASED_BY_UNLOCK);
}

/**
 * @brief The insert, get and remove functions change the list only while they hold the lock.
 *
 * @details
 * - Setup: an empty queue. Spy fakes record the length of the list at the
 *   lock and at the release.
 * - Action: k_queue_append() of a, z_impl_k_queue_alloc_append() of b,
 *   k_queue_remove() of a, z_impl_k_queue_get() with K_NO_WAIT. The spies
 *   are reset before each call.
 * - Expected: for each call, the length at the lock is the old length, and
 *   the length at the release is the new length.
 *
 * @ingroup kernel_unit_queue_static
 * @see queue_insert(), k_queue_remove(), z_impl_k_queue_get()
 */
ZTEST(queue_unit, test_lock_protects_list)
{
	struct k_queue queue;

	queue_prepare(&queue);

	spy_on_lock(&queue);
	k_queue_append(&queue, a);
	zassert_equal(len_at_lock, 0U);
	zassert_equal(len_at_release, 1U);

	spy_on_lock(&queue);
	zassert_equal(z_impl_k_queue_alloc_append(&queue, b), 0);
	zassert_equal(len_at_lock, 1U);
	zassert_equal(len_at_release, 2U);

	spy_on_lock(&queue);
	zassert_true(k_queue_remove(&queue, a));
	zassert_equal(len_at_lock, 2U);
	zassert_equal(len_at_release, 1U);

	spy_on_lock(&queue);
	zassert_equal_ptr(z_impl_k_queue_get(&queue, K_NO_WAIT), b);
	zassert_equal(len_at_lock, 1U);
	zassert_equal(len_at_release, 0U);
}

/**
 * @brief Each queue has its own lock.
 *
 * @details
 * - Setup: two empty queues. One thread waits on each.
 * - Action: k_queue_append() of a to the first queue, of b to the second
 *   queue.
 * - Expected: two calls of z_reschedule(), the first with the lock of the
 *   first queue, the second with the lock of the second queue.
 *
 * @ingroup kernel_unit_queue_k_queue_append
 * @see k_queue_append()
 * @see queue_insert()
 */
ZTEST(queue_unit, test_lock_one_lock_per_queue)
{
	struct k_queue queue1;
	struct k_queue queue2;

	queue_prepare(&queue1);
	queue_prepare(&queue2);
	kernel_unit_set_waiting_threads(2);

	k_queue_append(&queue1, a);
	k_queue_append(&queue2, b);

	zassert_equal(z_reschedule_fake.call_count, 2);
	zassert_equal_ptr(z_reschedule_fake.arg0_history[0], &queue1.lock);
	zassert_equal_ptr(z_reschedule_fake.arg0_history[1], &queue2.lock);
}

/**
 * @brief k_queue_init() does not lock the queue.
 *
 * @details
 * - Action: z_impl_k_queue_init().
 * - Expected: no call of arch_irq_lock().
 *
 * @ingroup kernel_unit_queue_k_queue_init
 * @see z_impl_k_queue_init()
 */
ZTEST(queue_unit, test_lock_not_used_by_init)
{
	struct k_queue queue;

	z_impl_k_queue_init(&queue);

	zassert_equal(unit_arch_irq_lock_fake.call_count, 0);
}

#ifdef CONFIG_SPIN_VALIDATE
/**
 * @brief With CONFIG_SPIN_VALIDATE, the spinlock validation sees the lock of the queue on lock and
 * on unlock.
 *
 * @details
 * - Setup: an empty queue.
 * - Action: z_impl_k_queue_peek_head().
 * - Expected: one call of z_spin_lock_valid() and one call of
 *   z_spin_unlock_valid(), each with the lock of the queue.
 *
 * @ingroup kernel_unit_queue_k_queue_peek_head
 * @see z_impl_k_queue_peek_head()
 */
ZTEST(queue_unit, test_lock_validation_sees_queue_lock)
{
	struct k_queue queue;

	queue_prepare(&queue);

	(void)z_impl_k_queue_peek_head(&queue);

	zassert_equal(z_spin_lock_valid_fake.call_count, 1);
	zassert_equal_ptr(z_spin_lock_valid_fake.arg0_val, &queue.lock);
	zassert_equal(z_spin_unlock_valid_fake.call_count, 1);
	zassert_equal_ptr(z_spin_unlock_valid_fake.arg0_val, &queue.lock);
}
#endif /* CONFIG_SPIN_VALIDATE */

#ifdef CONFIG_USERSPACE
/*
 * Tests: System call verification. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_queue, at the top of this file.
 */

/* Assert one object check of queue with the type K_OBJ_QUEUE and init state, and no oops. */
static void assert_object_check(struct k_queue *queue, enum _obj_init_check init)
{
	kernel_unit_assert_object_check(queue, K_OBJ_QUEUE, init);
}

/* Assert one oops, before the first call of fn (the first change of the queue). */
#define zassert_oops_before(fn)                                                                    \
	do {                                                                                       \
		zassert_equal(unit_syscall_oops_fake.call_count, 1);                               \
		zassert_called_before(unit_syscall_oops, fn);                                      \
	} while (false)

/**
 * @brief z_vrfy_k_queue_init() checks that the pointer is a queue object that is not initialized,
 * and then calls z_impl_k_queue_init().
 *
 * @details
 * - Setup: a queue filled with a pattern. The object check passes.
 * - Action: z_vrfy_k_queue_init().
 * - Expected: k_object_find() and k_object_validation_check() with the
 *   queue, K_OBJ_QUEUE and _OBJ_INIT_FALSE, before z_waitq_init(). No oops.
 *   The list is empty.
 *
 * @ingroup kernel_unit_queue_k_queue_init
 * @see z_vrfy_k_queue_init()
 */
ZTEST(queue_unit, test_syscall_init_checks_new_object)
{
	struct k_queue queue;

	memset(&queue, FILL, sizeof(queue));
	kernel_unit_pass_object_check();

	z_vrfy_k_queue_init(&queue);

	assert_object_check(&queue, _OBJ_INIT_FALSE);
	zassert_called_before(k_object_validation_check, z_waitq_init);
	zassert_queue_empty(&queue);
}

/**
 * @brief If the object check fails, z_vrfy_k_queue_init() raises an oops before it changes the
 * queue.
 *
 * @details
 * - Setup: the object check fails (for example, the queue is already
 *   initialized).
 * - Action: z_vrfy_k_queue_init().
 * - Expected: one oops, before z_waitq_init().
 *
 * @ingroup kernel_unit_queue_k_queue_init
 * @see z_vrfy_k_queue_init()
 */
ZTEST(queue_unit, test_syscall_init_oops_on_bad_object)
{
	struct k_queue queue;

	kernel_unit_fail_object_check();

	z_vrfy_k_queue_init(&queue);

	zassert_oops_before(z_waitq_init);
}

/**
 * @brief z_vrfy_k_queue_cancel_wait() checks that the pointer is an initialized queue object, and
 * then calls z_impl_k_queue_cancel_wait().
 *
 * @details
 * - Setup: an empty queue. The object check passes. One thread waits.
 * - Action: z_vrfy_k_queue_cancel_wait().
 * - Expected: the object check with K_OBJ_QUEUE and _OBJ_INIT_TRUE, before
 *   the lock. No oops. One call of z_sched_wake() with NULL.
 *
 * @ingroup kernel_unit_queue_k_queue_cancel_wait
 * @see z_vrfy_k_queue_cancel_wait()
 */
ZTEST(queue_unit, test_syscall_cancel_wait_checks_initialized_object)
{
	struct k_queue queue;

	queue_prepare(&queue);
	kernel_unit_pass_object_check();
	kernel_unit_set_waiting_threads(1);

	z_vrfy_k_queue_cancel_wait(&queue);

	assert_object_check(&queue, _OBJ_INIT_TRUE);
	zassert_called_before(k_object_validation_check, unit_arch_irq_lock);
	zassert_equal(z_sched_wake_fake.call_count, 1);
	zassert_is_null(z_sched_wake_fake.arg2_val);
}

/**
 * @brief If the object check fails, z_vrfy_k_queue_cancel_wait() raises an oops before it locks
 * the queue.
 *
 * @details
 * - Setup: an empty queue. The object check fails.
 * - Action: z_vrfy_k_queue_cancel_wait().
 * - Expected: one oops, before arch_irq_lock().
 *
 * @ingroup kernel_unit_queue_k_queue_cancel_wait
 * @see z_vrfy_k_queue_cancel_wait()
 */
ZTEST(queue_unit, test_syscall_cancel_wait_oops_on_bad_object)
{
	struct k_queue queue;

	queue_prepare(&queue);
	kernel_unit_fail_object_check();

	z_vrfy_k_queue_cancel_wait(&queue);

	zassert_oops_before(unit_arch_irq_lock);
}

/**
 * @brief z_vrfy_k_queue_alloc_append() checks that the pointer is an initialized queue object, and
 * then returns the result of z_impl_k_queue_alloc_append().
 *
 * @details
 * - Setup: an empty queue. The object check passes. z_thread_malloc()
 *   returns NULL.
 * - Action: z_vrfy_k_queue_alloc_append() of a.
 * - Expected: the object check with K_OBJ_QUEUE and _OBJ_INIT_TRUE, before
 *   the lock. No oops. Return value -ENOMEM. Then, with memory, return
 *   value 0 and the list is a.
 *
 * @ingroup kernel_unit_queue_k_queue_alloc_append
 * @see z_vrfy_k_queue_alloc_append()
 */
ZTEST(queue_unit, test_syscall_alloc_append_checks_initialized_object)
{
	struct k_queue queue;

	queue_prepare(&queue);
	kernel_unit_pass_object_check();
	z_thread_malloc_fake.custom_fake = NULL;

	zassert_equal(z_vrfy_k_queue_alloc_append(&queue, a), -ENOMEM);

	assert_object_check(&queue, _OBJ_INIT_TRUE);
	zassert_called_before(k_object_validation_check, unit_arch_irq_lock);

	z_thread_malloc_fake.custom_fake = malloc_from_pool;
	zassert_equal(z_vrfy_k_queue_alloc_append(&queue, a), 0);
	zassert_queue_contents(&queue, a);
}

/**
 * @brief If the object check fails, z_vrfy_k_queue_alloc_append() raises an oops before it locks
 * the queue.
 *
 * @details
 * - Setup: an empty queue. The object check fails.
 * - Action: z_vrfy_k_queue_alloc_append() of a.
 * - Expected: one oops, before arch_irq_lock().
 *
 * @ingroup kernel_unit_queue_k_queue_alloc_append
 * @see z_vrfy_k_queue_alloc_append()
 */
ZTEST(queue_unit, test_syscall_alloc_append_oops_on_bad_object)
{
	struct k_queue queue;

	queue_prepare(&queue);
	kernel_unit_fail_object_check();

	(void)z_vrfy_k_queue_alloc_append(&queue, a);

	zassert_oops_before(unit_arch_irq_lock);
}

/**
 * @brief z_vrfy_k_queue_alloc_prepend() checks that the pointer is an initialized queue object,
 * and then returns the result of z_impl_k_queue_alloc_prepend().
 *
 * @details
 * - Setup: the list is a. The object check passes.
 * - Action: z_vrfy_k_queue_alloc_prepend() of b.
 * - Expected: the object check with K_OBJ_QUEUE and _OBJ_INIT_TRUE, before
 *   the lock. No oops. Return value 0. The list is b, a.
 *
 * @ingroup kernel_unit_queue_k_queue_alloc_prepend
 * @see z_vrfy_k_queue_alloc_prepend()
 */
ZTEST(queue_unit, test_syscall_alloc_prepend_checks_initialized_object)
{
	struct k_queue queue;

	queue_prepare(&queue);
	k_queue_append(&queue, a);
	reset_history();
	kernel_unit_pass_object_check();

	zassert_equal(z_vrfy_k_queue_alloc_prepend(&queue, b), 0);

	assert_object_check(&queue, _OBJ_INIT_TRUE);
	zassert_called_before(k_object_validation_check, unit_arch_irq_lock);
	zassert_queue_contents(&queue, b, a);
}

/**
 * @brief If the object check fails, z_vrfy_k_queue_alloc_prepend() raises an oops before it locks
 * the queue.
 *
 * @details
 * - Setup: an empty queue. The object check fails.
 * - Action: z_vrfy_k_queue_alloc_prepend() of a.
 * - Expected: one oops, before arch_irq_lock().
 *
 * @ingroup kernel_unit_queue_k_queue_alloc_prepend
 * @see z_vrfy_k_queue_alloc_prepend()
 */
ZTEST(queue_unit, test_syscall_alloc_prepend_oops_on_bad_object)
{
	struct k_queue queue;

	queue_prepare(&queue);
	kernel_unit_fail_object_check();

	(void)z_vrfy_k_queue_alloc_prepend(&queue, a);

	zassert_oops_before(unit_arch_irq_lock);
}

/**
 * @brief z_vrfy_k_queue_get() checks that the pointer is an initialized queue object, and then
 * calls z_impl_k_queue_get() with the same timeout.
 *
 * @details
 * - Setup: an empty queue. The object check passes. The wait gives a.
 * - Action: z_vrfy_k_queue_get() with a timeout of 10 ticks.
 * - Expected: the object check with K_OBJ_QUEUE and _OBJ_INIT_TRUE, before
 *   the lock. No oops. z_pend_curr() with the timeout. Return value a.
 *
 * @ingroup kernel_unit_queue_k_queue_get
 * @see z_vrfy_k_queue_get()
 */
ZTEST(queue_unit, test_syscall_get_checks_initialized_object)
{
	struct k_queue queue;

	queue_prepare(&queue);
	kernel_unit_pass_object_check();
	kernel_unit_set_wait_result(a, 0);

	zassert_equal_ptr(z_vrfy_k_queue_get(&queue, TEST_TIMEOUT), a);

	assert_object_check(&queue, _OBJ_INIT_TRUE);
	zassert_called_before(k_object_validation_check, unit_arch_irq_lock);
	zassert_true(K_TIMEOUT_EQ(z_pend_curr_fake.arg3_val, TEST_TIMEOUT));
}

/**
 * @brief If the object check fails, z_vrfy_k_queue_get() raises an oops before it locks the
 * queue.
 *
 * @details
 * - Setup: an empty queue. The object check fails.
 * - Action: z_vrfy_k_queue_get() with K_NO_WAIT.
 * - Expected: one oops, before arch_irq_lock().
 *
 * @ingroup kernel_unit_queue_k_queue_get
 * @see z_vrfy_k_queue_get()
 */
ZTEST(queue_unit, test_syscall_get_oops_on_bad_object)
{
	struct k_queue queue;

	queue_prepare(&queue);
	kernel_unit_fail_object_check();

	(void)z_vrfy_k_queue_get(&queue, K_NO_WAIT);

	zassert_oops_before(unit_arch_irq_lock);
}

/**
 * @brief z_vrfy_k_queue_is_empty() checks that the pointer is an initialized queue object, and
 * then returns the result of z_impl_k_queue_is_empty().
 *
 * @details
 * - Setup: the list is a. The object check passes.
 * - Action: z_vrfy_k_queue_is_empty().
 * - Expected: the object check with K_OBJ_QUEUE and _OBJ_INIT_TRUE. No
 *   oops. Return value 0.
 *
 * @ingroup kernel_unit_queue_k_queue_is_empty
 * @see z_vrfy_k_queue_is_empty()
 */
ZTEST(queue_unit, test_syscall_is_empty_checks_initialized_object)
{
	struct k_queue queue;

	queue_prepare(&queue);
	k_queue_append(&queue, a);
	kernel_unit_pass_object_check();

	zassert_equal(z_vrfy_k_queue_is_empty(&queue), 0);

	assert_object_check(&queue, _OBJ_INIT_TRUE);
}

/**
 * @brief If the object check fails, z_vrfy_k_queue_is_empty() raises an oops.
 *
 * @details
 * - Setup: an empty queue. The object check fails.
 * - Action: z_vrfy_k_queue_is_empty().
 * - Expected: one oops.
 *
 * @ingroup kernel_unit_queue_k_queue_is_empty
 * @see z_vrfy_k_queue_is_empty()
 */
ZTEST(queue_unit, test_syscall_is_empty_oops_on_bad_object)
{
	struct k_queue queue;

	queue_prepare(&queue);
	kernel_unit_fail_object_check();

	(void)z_vrfy_k_queue_is_empty(&queue);

	zassert_equal(unit_syscall_oops_fake.call_count, 1);
}

/**
 * @brief z_vrfy_k_queue_peek_head() checks that the pointer is an initialized queue object, and
 * then returns the result of z_impl_k_queue_peek_head().
 *
 * @details
 * - Setup: the list is a, b. The object check passes.
 * - Action: z_vrfy_k_queue_peek_head().
 * - Expected: the object check with K_OBJ_QUEUE and _OBJ_INIT_TRUE, before
 *   the lock. No oops. Return value a.
 *
 * @ingroup kernel_unit_queue_k_queue_peek_head
 * @see z_vrfy_k_queue_peek_head()
 */
ZTEST(queue_unit, test_syscall_peek_head_checks_initialized_object)
{
	struct k_queue queue;

	queue_prepare(&queue);
	k_queue_append(&queue, a);
	k_queue_append(&queue, b);
	reset_history();
	kernel_unit_pass_object_check();

	zassert_equal_ptr(z_vrfy_k_queue_peek_head(&queue), a);

	assert_object_check(&queue, _OBJ_INIT_TRUE);
	zassert_called_before(k_object_validation_check, unit_arch_irq_lock);
}

/**
 * @brief If the object check fails, z_vrfy_k_queue_peek_head() raises an oops before it locks the
 * queue.
 *
 * @details
 * - Setup: an empty queue. The object check fails.
 * - Action: z_vrfy_k_queue_peek_head().
 * - Expected: one oops, before arch_irq_lock().
 *
 * @ingroup kernel_unit_queue_k_queue_peek_head
 * @see z_vrfy_k_queue_peek_head()
 */
ZTEST(queue_unit, test_syscall_peek_head_oops_on_bad_object)
{
	struct k_queue queue;

	queue_prepare(&queue);
	kernel_unit_fail_object_check();

	(void)z_vrfy_k_queue_peek_head(&queue);

	zassert_oops_before(unit_arch_irq_lock);
}

/**
 * @brief z_vrfy_k_queue_peek_tail() checks that the pointer is an initialized queue object, and
 * then returns the result of z_impl_k_queue_peek_tail().
 *
 * @details
 * - Setup: the list is a, b. The object check passes.
 * - Action: z_vrfy_k_queue_peek_tail().
 * - Expected: the object check with K_OBJ_QUEUE and _OBJ_INIT_TRUE, before
 *   the lock. No oops. Return value b.
 *
 * @ingroup kernel_unit_queue_k_queue_peek_tail
 * @see z_vrfy_k_queue_peek_tail()
 */
ZTEST(queue_unit, test_syscall_peek_tail_checks_initialized_object)
{
	struct k_queue queue;

	queue_prepare(&queue);
	k_queue_append(&queue, a);
	k_queue_append(&queue, b);
	reset_history();
	kernel_unit_pass_object_check();

	zassert_equal_ptr(z_vrfy_k_queue_peek_tail(&queue), b);

	assert_object_check(&queue, _OBJ_INIT_TRUE);
	zassert_called_before(k_object_validation_check, unit_arch_irq_lock);
}

/**
 * @brief If the object check fails, z_vrfy_k_queue_peek_tail() raises an oops before it locks the
 * queue.
 *
 * @details
 * - Setup: an empty queue. The object check fails.
 * - Action: z_vrfy_k_queue_peek_tail().
 * - Expected: one oops, before arch_irq_lock().
 *
 * @ingroup kernel_unit_queue_k_queue_peek_tail
 * @see z_vrfy_k_queue_peek_tail()
 */
ZTEST(queue_unit, test_syscall_peek_tail_oops_on_bad_object)
{
	struct k_queue queue;

	queue_prepare(&queue);
	kernel_unit_fail_object_check();

	(void)z_vrfy_k_queue_peek_tail(&queue);

	zassert_oops_before(unit_arch_irq_lock);
}
#endif /* CONFIG_USERSPACE */

/*
 * Tests: Object core. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_queue, at the top of this file.
 */

/* Return the descriptor of a type, and count the descriptors of this type. */
static __maybe_unused const struct k_obj_core_desc *obj_core_desc(struct k_obj_type *type,
								  int *count)
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

#ifdef CONFIG_OBJ_CORE_FIFO
K_FIFO_DEFINE(unit_static_fifo);

/**
 * @brief With CONFIG_OBJ_CORE_FIFO, queue.c defines one object type descriptor with the ID
 * K_OBJ_TYPE_FIFO_ID for the FIFOs.
 *
 * @details
 * - Action: search the section @c k_obj_core_desc for the descriptor of
 *   @c _obj_type_fifo.
 * - Expected: one descriptor. Its type ID is K_OBJ_TYPE_FIFO_ID. Its object
 *   size is the size of @c struct @c k_fifo, and its object core offset is
 *   the offset of @c obj_core. Its object range is the section @c k_fifo.
 *
 * @ingroup kernel_unit_queue_static
 */
ZTEST(queue_unit, test_obj_core_fifo_type_descriptor)
{
	int count;
	const struct k_obj_core_desc *desc = obj_core_desc(&_obj_type_fifo, &count);

	zassert_equal(count, 1);
	zassert_not_null(desc);
	zassert_equal(desc->type_id, K_OBJ_TYPE_FIFO_ID);
	zassert_equal(desc->obj_size, sizeof(struct k_fifo));
	zassert_equal(desc->obj_core_offset, offsetof(struct k_fifo, obj_core));
	zassert_equal_ptr(desc->objs_start, STRUCT_SECTION_START(k_fifo));
	zassert_equal_ptr(desc->objs_end, STRUCT_SECTION_END(k_fifo));
}

/**
 * @brief The object range of the FIFO descriptor contains the FIFOs that K_FIFO_DEFINE() defines.
 *
 * @details
 * - Setup: K_FIFO_DEFINE() of one FIFO in the test.
 * - Action: compare the address of the FIFO with the object range of the
 *   descriptor.
 * - Expected: the FIFO is in the range, at a multiple of the object size
 *   from the start.
 *
 * @ingroup kernel_unit_queue_static
 */
ZTEST(queue_unit, test_obj_core_fifo_descriptor_covers_static_fifos)
{
	int count;
	const struct k_obj_core_desc *desc = obj_core_desc(&_obj_type_fifo, &count);
	uintptr_t obj = (uintptr_t)&unit_static_fifo;

	zassert_not_null(desc);
	zassert_true((obj >= (uintptr_t)desc->objs_start) && (obj < (uintptr_t)desc->objs_end));
	zassert_equal((obj - (uintptr_t)desc->objs_start) % desc->obj_size, 0U);
}

/**
 * @brief With CONFIG_OBJ_CORE_FIFO, k_fifo_init() initializes the queue and then links the FIFO to
 * the FIFO object type of queue.c.
 *
 * @details
 * - Action: k_fifo_init().
 * - Expected calls, in this order: z_waitq_init(), k_object_init() (with
 *   CONFIG_USERSPACE), k_obj_core_init() with the object core of the FIFO
 *   and @c _obj_type_fifo, k_obj_core_link() with the object core of the
 *   FIFO.
 *
 * @ingroup kernel_unit_queue_k_queue_init
 * @see z_impl_k_queue_init()
 */
ZTEST(queue_unit, test_obj_core_fifo_init_links_fifo)
{
	struct k_fifo fifo;

	k_fifo_init(&fifo);

	zassert_call_history(z_waitq_init, KERNEL_UNIT_IF_ENABLED(CONFIG_USERSPACE, k_object_init),
			     k_obj_core_init, k_obj_core_link);
	zassert_equal_ptr(k_obj_core_init_fake.arg0_val, K_OBJ_CORE(&fifo));
	zassert_equal_ptr(k_obj_core_init_fake.arg1_val, &_obj_type_fifo);
	zassert_equal_ptr(k_obj_core_link_fake.arg0_val, K_OBJ_CORE(&fifo));
}
#endif /* CONFIG_OBJ_CORE_FIFO */

#ifdef CONFIG_OBJ_CORE_LIFO
K_LIFO_DEFINE(unit_static_lifo);

/**
 * @brief With CONFIG_OBJ_CORE_LIFO, queue.c defines one object type descriptor with the ID
 * K_OBJ_TYPE_LIFO_ID for the LIFOs.
 *
 * @details
 * - Action: search the section @c k_obj_core_desc for the descriptor of
 *   @c _obj_type_lifo.
 * - Expected: one descriptor. Its type ID is K_OBJ_TYPE_LIFO_ID. Its object
 *   size is the size of @c struct @c k_lifo, and its object core offset is
 *   the offset of @c obj_core. Its object range is the section @c k_lifo.
 *
 * @ingroup kernel_unit_queue_static
 */
ZTEST(queue_unit, test_obj_core_lifo_type_descriptor)
{
	int count;
	const struct k_obj_core_desc *desc = obj_core_desc(&_obj_type_lifo, &count);

	zassert_equal(count, 1);
	zassert_not_null(desc);
	zassert_equal(desc->type_id, K_OBJ_TYPE_LIFO_ID);
	zassert_equal(desc->obj_size, sizeof(struct k_lifo));
	zassert_equal(desc->obj_core_offset, offsetof(struct k_lifo, obj_core));
	zassert_equal_ptr(desc->objs_start, STRUCT_SECTION_START(k_lifo));
	zassert_equal_ptr(desc->objs_end, STRUCT_SECTION_END(k_lifo));
}

/**
 * @brief The object range of the LIFO descriptor contains the LIFOs that K_LIFO_DEFINE() defines.
 *
 * @details
 * - Setup: K_LIFO_DEFINE() of one LIFO in the test.
 * - Action: compare the address of the LIFO with the object range of the
 *   descriptor.
 * - Expected: the LIFO is in the range, at a multiple of the object size
 *   from the start.
 *
 * @ingroup kernel_unit_queue_static
 */
ZTEST(queue_unit, test_obj_core_lifo_descriptor_covers_static_lifos)
{
	int count;
	const struct k_obj_core_desc *desc = obj_core_desc(&_obj_type_lifo, &count);
	uintptr_t obj = (uintptr_t)&unit_static_lifo;

	zassert_not_null(desc);
	zassert_true((obj >= (uintptr_t)desc->objs_start) && (obj < (uintptr_t)desc->objs_end));
	zassert_equal((obj - (uintptr_t)desc->objs_start) % desc->obj_size, 0U);
}

/**
 * @brief With CONFIG_OBJ_CORE_LIFO, k_lifo_init() initializes the queue and then links the LIFO to
 * the LIFO object type of queue.c.
 *
 * @details
 * - Action: k_lifo_init().
 * - Expected calls, in this order: z_waitq_init(), k_object_init() (with
 *   CONFIG_USERSPACE), k_obj_core_init() with the object core of the LIFO
 *   and @c _obj_type_lifo, k_obj_core_link() with the object core of the
 *   LIFO.
 *
 * @ingroup kernel_unit_queue_k_queue_init
 * @see z_impl_k_queue_init()
 */
ZTEST(queue_unit, test_obj_core_lifo_init_links_lifo)
{
	struct k_lifo lifo;

	k_lifo_init(&lifo);

	zassert_call_history(z_waitq_init, KERNEL_UNIT_IF_ENABLED(CONFIG_USERSPACE, k_object_init),
			     k_obj_core_init, k_obj_core_link);
	zassert_equal_ptr(k_obj_core_init_fake.arg0_val, K_OBJ_CORE(&lifo));
	zassert_equal_ptr(k_obj_core_init_fake.arg1_val, &_obj_type_lifo);
	zassert_equal_ptr(k_obj_core_link_fake.arg0_val, K_OBJ_CORE(&lifo));
}
#endif /* CONFIG_OBJ_CORE_LIFO */

/*
 * Tests: FIFO and LIFO. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_queue, at the top of this file.
 */

/**
 * @brief A FIFO gives the items in the order of k_fifo_put(): first in, first out.
 *
 * @details
 * - Setup: k_fifo_init(). No thread waits.
 * - Action: k_fifo_put() of a, b, c, then k_fifo_get() with K_NO_WAIT four
 *   times.
 * - Expected: return values a, b, c, NULL.
 *
 * @ingroup kernel_unit_queue_k_queue_append
 * @see k_queue_append(), z_impl_k_queue_get()
 */
ZTEST(queue_unit, test_wrapper_fifo_is_first_in_first_out)
{
	struct k_fifo fifo;

	k_fifo_init(&fifo);

	k_fifo_put(&fifo, a);
	k_fifo_put(&fifo, b);
	k_fifo_put(&fifo, c);

	zassert_equal_ptr(k_fifo_get(&fifo, K_NO_WAIT), a);
	zassert_equal_ptr(k_fifo_get(&fifo, K_NO_WAIT), b);
	zassert_equal_ptr(k_fifo_get(&fifo, K_NO_WAIT), c);
	zassert_is_null(k_fifo_get(&fifo, K_NO_WAIT));
}

/**
 * @brief A LIFO gives the items in the reverse order of k_lifo_put(): last in, first out.
 *
 * @details
 * - Setup: k_lifo_init(). No thread waits.
 * - Action: k_lifo_put() of a, b, c, then k_lifo_get() with K_NO_WAIT four
 *   times.
 * - Expected: return values c, b, a, NULL.
 *
 * @ingroup kernel_unit_queue_k_queue_prepend
 * @see k_queue_prepend(), z_impl_k_queue_get()
 */
ZTEST(queue_unit, test_wrapper_lifo_is_last_in_first_out)
{
	struct k_lifo lifo;

	k_lifo_init(&lifo);

	k_lifo_put(&lifo, a);
	k_lifo_put(&lifo, b);
	k_lifo_put(&lifo, c);

	zassert_equal_ptr(k_lifo_get(&lifo, K_NO_WAIT), c);
	zassert_equal_ptr(k_lifo_get(&lifo, K_NO_WAIT), b);
	zassert_equal_ptr(k_lifo_get(&lifo, K_NO_WAIT), a);
	zassert_is_null(k_lifo_get(&lifo, K_NO_WAIT));
}

/**
 * @brief k_fifo_alloc_put() appends and k_lifo_alloc_put() prepends an item with an allocated
 * node.
 *
 * @details
 * - Setup: k_fifo_init() and k_lifo_init(). No thread waits.
 * - Action: k_fifo_alloc_put() of a, then of b. k_lifo_alloc_put() of c,
 *   then of d.
 * - Expected: return value 0 each time. The FIFO list is a, b. The LIFO
 *   list is d, c. Four calls of z_thread_malloc().
 *
 * @ingroup kernel_unit_queue_k_queue_alloc_append
 * @see z_impl_k_queue_alloc_append(), z_impl_k_queue_alloc_prepend()
 */
ZTEST(queue_unit, test_wrapper_alloc_put_order)
{
	struct k_fifo fifo;
	struct k_lifo lifo;

	k_fifo_init(&fifo);
	k_lifo_init(&lifo);

	zassert_equal(k_fifo_alloc_put(&fifo, a), 0);
	zassert_equal(k_fifo_alloc_put(&fifo, b), 0);
	zassert_equal(k_lifo_alloc_put(&lifo, c), 0);
	zassert_equal(k_lifo_alloc_put(&lifo, d), 0);

	zassert_queue_contents(&fifo._queue, a, b);
	zassert_queue_contents(&lifo._queue, d, c);
	zassert_equal(z_thread_malloc_fake.call_count, 4);
}
