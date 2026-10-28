/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @defgroup kernel_unit_obj_core kernel/obj_core.c
 * @ingroup kernel_unit_tests
 * @brief Design specification of kernel/obj_core.c, written as unit tests.
 *
 * @par The object core framework
 * The object core framework keeps a list of the kernel objects of each
 * object type. Tools and shell commands walk these lists, for example to
 * show the statistics of all objects.
 * - An object type (@c struct @c k_obj_type) has an ID, the offset of the
 *   object core in the object, and the list @c list of its objects. With
 *   @kconfig{CONFIG_OBJ_CORE_STATS}, it also has a statistics descriptor.
 * - The global list @c z_obj_type_list holds all object types.
 * - An object core (@c struct @c k_obj_core) is a member of a kernel object.
 *   It has the node in the list of its type and a pointer to its type. With
 *   @kconfig{CONFIG_OBJ_CORE_STATS}, it also has a pointer to the statistics
 *   buffer of the object.
 *
 * @par Operations
 * - z_obj_type_init() initializes an object type and appends it to
 *   @c z_obj_type_list. k_obj_type_find() finds a type by its ID.
 * - k_obj_core_init() sets the type of an object core and clears its node.
 *   k_obj_core_link() appends the node to the list of the type.
 *   k_obj_core_init_and_link() does both. k_obj_core_unlink() removes the
 *   node.
 * - k_obj_type_walk_locked() and k_obj_type_walk_unlocked() call a function
 *   for each object of a type, until the function returns a value that is
 *   not 0.
 * - The boot init z_obj_core_init_all() initializes each type of the
 *   iterable section @c k_obj_core_desc and links its static objects.
 *   With @kconfig{CONFIG_OBJ_CORE_SYSTEM}, init_kernel_obj_core_list()
 *   links the kernel object @c _kernel.
 * - With @kconfig{CONFIG_OBJ_CORE_STATS}, k_obj_core_stats_register() and
 *   k_obj_core_stats_deregister() set the statistics buffer of an object.
 *   k_obj_core_stats_raw(), _query(), _reset(), _disable() and _enable()
 *   check the request and call the function of the statistics descriptor.
 *
 * @par One lock for all lists
 * obj_core.c has one spinlock, the static @c obj_core_lock. k_obj_core_link(),
 * k_obj_core_unlink(), k_obj_type_find(), k_obj_type_walk_locked() and all
 * statistics functions lock it. k_obj_core_init(), z_obj_type_init() and
 * k_obj_type_walk_unlocked() do not lock it.
 *
 * @par Interfaces below obj_core.c
 * - Lists (@c zephyr/sys/slist.h): real code, not fakes.
 * - Architecture: arch_irq_lock() and arch_irq_unlock() through
 *   k_spin_lock() and k_spin_unlock().
 * - The kernel object @c _kernel (fake group @c init).
 * - With @kconfig{CONFIG_OBJ_CORE_STATS_SYSTEM}: z_kernel_stats_raw() and
 *   z_kernel_stats_query() (@c kernel/usage.c, fake group @c usage).
 *
 * @par Kconfig options that change obj_core.c
 * - @kconfig{CONFIG_OBJ_CORE}: the unit itself. Each scenario enables it.
 * - @kconfig{CONFIG_OBJ_CORE_SYSTEM}: the kernel object type. It has no
 *   prompt and is always enabled with @kconfig{CONFIG_OBJ_CORE}.
 * - @kconfig{CONFIG_OBJ_CORE_STATS}: the statistics functions.
 * - @kconfig{CONFIG_OBJ_CORE_STATS_SYSTEM}: the statistics of the kernel
 *   object.
 *
 * @par The second init of a linked object (finding F-1)
 * k_obj_core_init() sets the node of the object core to NULL, and
 * k_obj_core_link() appends the node. Neither function examines if the node
 * is already in a list. Seven kernel init functions call
 * k_obj_core_init_and_link() on each call, for example k_sem_init(). Thus a
 * second init of a linked object appends its node a second time. The tests
 * of the second init (see "Second init of a linked object" below) state the
 * correct behavior, and ZTEST_EXPECT_FAIL() marks each of them. The suite passes while the
 * defect is in the code. If a change of obj_core.c fixes the defect, the
 * test passes, ztest reports an unexpected pass, and the suite fails. Then
 * remove the ZTEST_EXPECT_FAIL() line.
 *
 * @par Test method
 * The test source includes obj_core.c. The tests use their own object
 * types and objects (@c struct @c unit_obj). The boot tests use descriptors
 * of the test in the section @c k_obj_core_desc. The tests never walk a list
 * that can have a cycle with SYS_SLIST_FOR_EACH_NODE(): they use the bounded
 * walk of @c obj_core_list.h, or a walk function that stops the walk after a
 * limit. The second test source (@c test_obj_core_sem.c) includes
 * @c kernel/sem.c and shows the second init through k_sem_init().
 *
 * @par Structure of the tests
 * Each public function of obj_core.c has one group below this group. The
 * static functions and the data of obj_core.c have the last group. Each
 * test is in the group of the function under test. The rules below (object
 * types, object core link, walks, statistics, second init) apply to more
 * than one function. Their tests are in the group of the function that they
 * call. The tests of the second init are in the group of
 * k_obj_core_init_and_link(), also if their action is a walk or an unlink
 * that shows the effect of the second init.
 *
 * @par Object types
 * z_obj_type_init() registers an object type, and k_obj_type_find() finds
 * it by its ID.
 * The global list @c z_obj_type_list holds the types in the order of
 * their registration. The boot init registers the types of the section
 * @c k_obj_core_desc. Other code can register a type later, for example
 * the socket code (@c subsys/net/lib/sockets/socket_obj_core.c).
 *
 * @par Object core link
 * k_obj_core_init() prepares an object core, k_obj_core_link() and
 * k_obj_core_unlink() change the list of its type.
 * The list of a type holds the objects in the order of their link.
 * k_obj_core_link() and k_obj_core_unlink() lock @c obj_core_lock.
 * k_obj_core_init() does not lock it: it writes only the object core.
 *
 * @par Walks
 * k_obj_type_walk_locked() and k_obj_type_walk_unlocked() call a function
 * for each object of a type.
 * Both walks go from the head to the tail. Each walk stops at the first
 * call that returns a value that is not 0, and returns this value. The
 * locked walk holds @c obj_core_lock (interrupts locked) during all calls.
 * The unlocked walk takes no lock. It reads the next node before the call,
 * so the function can unlink the object of the call.
 *
 * @par Statistics
 * With CONFIG_OBJ_CORE_STATS, obj_core.c checks each statistics request and
 * forwards it to the descriptor of the type.
 * The statistics descriptor of a type gives the size of the raw statistics
 * (@c raw_size), the size of the reported statistics (@c query_size) and
 * up to five functions. A request returns:
 * - -ENOTSUP if the type has no descriptor or the descriptor has no
 *   function for the request.
 * - -EINVAL if the buffer size is not the size of the descriptor, or the
 *   object has no registered statistics buffer.
 * - Else the return value of the function of the descriptor.
 *
 * Each request locks @c obj_core_lock once and calls the function of the
 * descriptor with the lock held. The tests that send each request are in
 * the group of k_obj_core_stats_raw().
 *
 * @par Second init of a linked object (finding F-1)
 * A second init of a linked object keeps each object in the list of its
 * type exactly one time.
 * The tests of the second init state the correct behavior. obj_core.c does
 * not have it today: k_obj_core_init() sets the next pointer of the node to
 * NULL, and k_obj_core_link() appends the node again. ZTEST_EXPECT_FAIL()
 * marks each test. The output of each test prints the list that the unit
 * made.
 *
 * The effect depends on the position of the object in the list:
 * - Tail or only object: the tail points to itself. The list has a cycle,
 *   and a walk does not end. k_obj_type_walk_locked() then holds
 *   @c obj_core_lock with interrupts locked, without end.
 * - Head or middle: the next pointer of the object becomes NULL. The objects
 *   after it are no longer in the list. A walk does not find them.
 */

/**
 * @defgroup kernel_unit_obj_core_z_obj_type_init z_obj_type_init()
 * @ingroup kernel_unit_obj_core
 * @brief z_obj_type_init() initializes an object type and appends it to the global type list.
 *
 * See "Object types" in @ref kernel_unit_obj_core.
 *
 * @par Functions in kernel/obj_core.c
 * - z_obj_type_init()
 */

/**
 * @defgroup kernel_unit_obj_core_k_obj_core_init k_obj_core_init()
 * @ingroup kernel_unit_obj_core
 * @brief k_obj_core_init() sets the type of an object core and clears its node.
 *
 * See "Object core link" in @ref kernel_unit_obj_core.
 *
 * @par Functions in kernel/obj_core.c
 * - k_obj_core_init(). It clears the statistics buffer pointer only with
 *   @kconfig{CONFIG_OBJ_CORE_STATS}.
 */

/**
 * @defgroup kernel_unit_obj_core_k_obj_core_link k_obj_core_link()
 * @ingroup kernel_unit_obj_core
 * @brief k_obj_core_link() appends the object core to the list of its type.
 *
 * See "Object core link" in @ref kernel_unit_obj_core.
 *
 * @par Functions in kernel/obj_core.c
 * - k_obj_core_link()
 */

/**
 * @defgroup kernel_unit_obj_core_k_obj_core_init_and_link k_obj_core_init_and_link()
 * @ingroup kernel_unit_obj_core
 * @brief k_obj_core_init_and_link() does k_obj_core_init() and k_obj_core_link().
 *
 * This group also has the tests of the second init of a linked object
 * (finding F-1, see "Second init of a linked object" in
 * @ref kernel_unit_obj_core), and the tests of the second init through
 * k_sem_init() below.
 *
 * @par Second init through k_sem_init()
 * k_sem_init() of a linked semaphore keeps each semaphore in the list of
 * the semaphore type exactly one time.
 * The test source @c test_obj_core_sem.c includes @c kernel/sem.c. Its calls
 * into the object core go to the real obj_core.c of the other test source,
 * not to fakes. The scheduler and the wait queue are fakes (fake group
 * @c sched), as in the @c sem application.
 *
 * k_sem_init() calls k_obj_core_init_and_link() on each call
 * (sem.c:69). It does not unlink the semaphore first. Thus a second
 * k_sem_init() of a linked semaphore has the effects of finding F-1.
 * A semaphore of K_SEM_DEFINE() is linked at boot, so its first
 * k_sem_init() is already a second link. With @kconfig{CONFIG_USERSPACE},
 * z_vrfy_k_sem_init() checks the object with K_SYSCALL_OBJ_INIT()
 * (@c _OBJ_INIT_ANY), so a user thread can also init a semaphore again.
 *
 * The tests that state the correct behavior have ZTEST_EXPECT_FAIL().
 * The test of the boot link of the static semaphores is in the group
 * @ref kernel_unit_obj_core_static.
 *
 * @par Functions in kernel/obj_core.c
 * - k_obj_core_init_and_link()
 */

/**
 * @defgroup kernel_unit_obj_core_k_obj_core_unlink k_obj_core_unlink()
 * @ingroup kernel_unit_obj_core
 * @brief k_obj_core_unlink() removes the object core from the list of its type.
 *
 * See "Object core link" in @ref kernel_unit_obj_core.
 *
 * @par Functions in kernel/obj_core.c
 * - k_obj_core_unlink()
 */

/**
 * @defgroup kernel_unit_obj_core_k_obj_type_find k_obj_type_find()
 * @ingroup kernel_unit_obj_core
 * @brief k_obj_type_find() finds a registered object type by its ID.
 *
 * See "Object types" in @ref kernel_unit_obj_core.
 *
 * @par Functions in kernel/obj_core.c
 * - k_obj_type_find()
 */

/**
 * @defgroup kernel_unit_obj_core_k_obj_type_walk_locked k_obj_type_walk_locked()
 * @ingroup kernel_unit_obj_core
 * @brief k_obj_type_walk_locked() calls a function for each object of a type, with the lock held.
 *
 * See "Walks" in @ref kernel_unit_obj_core.
 *
 * @par Functions in kernel/obj_core.c
 * - k_obj_type_walk_locked()
 */

/**
 * @defgroup kernel_unit_obj_core_k_obj_type_walk_unlocked k_obj_type_walk_unlocked()
 * @ingroup kernel_unit_obj_core
 * @brief k_obj_type_walk_unlocked() calls a function for each object of a type, without a lock.
 *
 * See "Walks" in @ref kernel_unit_obj_core.
 *
 * @par Functions in kernel/obj_core.c
 * - k_obj_type_walk_unlocked()
 */

/**
 * @defgroup kernel_unit_obj_core_k_obj_core_stats_register k_obj_core_stats_register()
 * @ingroup kernel_unit_obj_core
 * @brief k_obj_core_stats_register() sets the statistics buffer of an object.
 *
 * See "Statistics" in @ref kernel_unit_obj_core.
 *
 * @par Functions in kernel/obj_core.c
 * - k_obj_core_stats_register(), with @kconfig{CONFIG_OBJ_CORE_STATS}
 */

/**
 * @defgroup kernel_unit_obj_core_k_obj_core_stats_deregister k_obj_core_stats_deregister()
 * @ingroup kernel_unit_obj_core
 * @brief k_obj_core_stats_deregister() clears the statistics buffer of an object.
 *
 * See "Statistics" in @ref kernel_unit_obj_core.
 *
 * @par Functions in kernel/obj_core.c
 * - k_obj_core_stats_deregister(), with @kconfig{CONFIG_OBJ_CORE_STATS}
 */

/**
 * @defgroup kernel_unit_obj_core_k_obj_core_stats_raw k_obj_core_stats_raw()
 * @ingroup kernel_unit_obj_core
 * @brief k_obj_core_stats_raw() checks the raw statistics request and calls the function of the
 * descriptor.
 *
 * See "Statistics" in @ref kernel_unit_obj_core. The tests of this group
 * that send each statistics request (raw, query, reset, disable and enable)
 * are also the tests of the other request functions.
 *
 * @par Functions in kernel/obj_core.c
 * - k_obj_core_stats_raw(), with @kconfig{CONFIG_OBJ_CORE_STATS}
 */

/**
 * @defgroup kernel_unit_obj_core_k_obj_core_stats_query k_obj_core_stats_query()
 * @ingroup kernel_unit_obj_core
 * @brief No test of its own: the statistics request tests of
 * k_obj_core_stats_raw() cover k_obj_core_stats_query().
 *
 * No test is in this group. The tests of k_obj_core_stats_raw() also call
 * k_obj_core_stats_query() (the statistics requests), and the boot test of
 * the kernel statistics in @ref kernel_unit_obj_core_static calls it.
 * See "Statistics" in @ref kernel_unit_obj_core.
 *
 * @par Functions in kernel/obj_core.c
 * - k_obj_core_stats_query(), with @kconfig{CONFIG_OBJ_CORE_STATS}
 */

/**
 * @defgroup kernel_unit_obj_core_k_obj_core_stats_reset k_obj_core_stats_reset()
 * @ingroup kernel_unit_obj_core
 * @brief No test of its own: the statistics request tests of
 * k_obj_core_stats_raw() cover k_obj_core_stats_reset().
 *
 * No test is in this group. The tests of k_obj_core_stats_raw() also call
 * k_obj_core_stats_reset() (the statistics requests), and the boot test of
 * the kernel statistics in @ref kernel_unit_obj_core_static calls it.
 * See "Statistics" in @ref kernel_unit_obj_core.
 *
 * @par Functions in kernel/obj_core.c
 * - k_obj_core_stats_reset(), with @kconfig{CONFIG_OBJ_CORE_STATS}
 */

/**
 * @defgroup kernel_unit_obj_core_k_obj_core_stats_disable k_obj_core_stats_disable()
 * @ingroup kernel_unit_obj_core
 * @brief No test of its own: the statistics request tests of
 * k_obj_core_stats_raw() cover k_obj_core_stats_disable().
 *
 * No test is in this group. The tests of k_obj_core_stats_raw() also call
 * k_obj_core_stats_disable() (the statistics requests), and the boot test of
 * the kernel statistics in @ref kernel_unit_obj_core_static calls it.
 * See "Statistics" in @ref kernel_unit_obj_core.
 *
 * @par Functions in kernel/obj_core.c
 * - k_obj_core_stats_disable(), with @kconfig{CONFIG_OBJ_CORE_STATS}
 */

/**
 * @defgroup kernel_unit_obj_core_k_obj_core_stats_enable k_obj_core_stats_enable()
 * @ingroup kernel_unit_obj_core
 * @brief No test of its own: the statistics request tests of
 * k_obj_core_stats_raw() cover k_obj_core_stats_enable().
 *
 * No test is in this group. The tests of k_obj_core_stats_raw() also call
 * k_obj_core_stats_enable() (the statistics requests), and the boot test of
 * the kernel statistics in @ref kernel_unit_obj_core_static calls it.
 * See "Statistics" in @ref kernel_unit_obj_core.
 *
 * @par Functions in kernel/obj_core.c
 * - k_obj_core_stats_enable(), with @kconfig{CONFIG_OBJ_CORE_STATS}
 */

/**
 * @defgroup kernel_unit_obj_core_static Static functions and data
 * @ingroup kernel_unit_obj_core
 * @brief The static functions of obj_core.c, and the data that obj_core.c defines.
 *
 * @par Boot init
 * At boot, obj_core.c initializes the types of the section k_obj_core_desc
 * and links their static objects.
 * K_OBJ_TYPE_DEFINE() puts one descriptor for each type into the section.
 * z_obj_core_init_all() registers each type and links each static object of
 * the type, in address order. With @kconfig{CONFIG_OBJ_CORE_STATS}, it also
 * sets the statistics descriptor of the type and registers the statistics
 * buffer of each static object. K_KERNEL_INIT_PRE() runs both init
 * functions of the unit before the kernel starts.
 *
 * @par Functions in kernel/obj_core.c
 * - z_obj_core_init_all(), static, the boot init (K_KERNEL_INIT_PRE()). The
 *   statistics part is only in the code with
 *   @kconfig{CONFIG_OBJ_CORE_STATS}.
 * - init_kernel_obj_core_list(), static, the boot init of the kernel object
 *   (K_KERNEL_INIT_PRE()), with @kconfig{CONFIG_OBJ_CORE_SYSTEM}. The
 *   statistics part is only in the code with
 *   @kconfig{CONFIG_OBJ_CORE_STATS_SYSTEM}.
 *
 * @par Data in kernel/obj_core.c
 * - @c obj_core_lock, static: the one spinlock of all lists.
 * - @c z_obj_type_list: the global list of the object types (external
 *   linkage).
 * - @c obj_type_kernel, static, with @kconfig{CONFIG_OBJ_CORE_SYSTEM}: the
 *   type of the kernel object.
 * - @c kernel_stats_desc, static, with
 *   @kconfig{CONFIG_OBJ_CORE_STATS_SYSTEM}: the statistics descriptor of the
 *   kernel object.
 */

#include <string.h>
#include <zephyr/ztest.h>
#include <kernel_unit.h>
#include <kernel_unit_models.h>
#include "obj_core_list.h"

#ifdef CONFIG_OBJ_CORE_STATS_SYSTEM
/* Fakes of kernel/usage.c. obj_core.c refers to them in kernel_stats_desc. */
#include <fakes/usage.h>
#endif /* CONFIG_OBJ_CORE_STATS_SYSTEM */

#include <kernel/obj_core.c>

/* Value that fills a structure before a test, to show the fields that the unit writes */
#define FILL 0xA5

/* IDs of the object types of the test */
#define UNIT_TYPE_A_ID K_OBJ_TYPE_ID_GEN("UTA_")
#define UNIT_TYPE_B_ID K_OBJ_TYPE_ID_GEN("UTB_")
#define UNIT_TYPE_C_ID K_OBJ_TYPE_ID_GEN("UTC_")
#define UNIT_TYPE_D_ID K_OBJ_TYPE_ID_GEN("UTD_")
#define UNIT_TYPE_UNKNOWN_ID K_OBJ_TYPE_ID_GEN("NONE")

/* Return value of a walk function that stops the walk because of the limit */
#define WALK_LIMIT_STATUS (-ELOOP)

/* Number of calls after which the walk function stops a walk */
#define WALK_LIMIT 16U

/* A kernel object of the test, with an object core */
struct unit_obj {
	const char *name;
	struct k_obj_core obj_core;
#ifdef CONFIG_OBJ_CORE_STATS
	uint32_t stats[2];
#endif /* CONFIG_OBJ_CORE_STATS */
};

/* Objects for the link, unlink and walk tests */
static struct unit_obj obj_a = {.name = "a"};
static struct unit_obj obj_b = {.name = "b"};
static struct unit_obj obj_c = {.name = "c"};
static struct unit_obj obj_d = {.name = "d"};

/* Object types of the test */
static struct k_obj_type unit_type;
static struct k_obj_type unit_type2;

/* Name of a node of a list of unit_obj objects or of object types */
static const char *node_name(const sys_snode_t *node)
{
	if (node == &unit_type.node) {
		return "type";
	}
	if (node == &unit_type2.node) {
		return "type2";
	}

	const struct k_obj_core *core = CONTAINER_OF(node, struct k_obj_core, node);

	return CONTAINER_OF(core, struct unit_obj, obj_core)->name;
}

/* Node of an object, for the expected lists */
#define NODE(obj) (&(obj).obj_core.node)

/* Initialize the test type and link the objects in this order */
static void link_objects(struct unit_obj *const *objs, size_t n)
{
	for (size_t i = 0; i < n; i++) {
		k_obj_core_init_and_link(&objs[i]->obj_core, &unit_type);
	}
}

/* Record of a walk */
struct walk_log {
	/* Number of calls of the walk function */
	size_t calls;
	/* The object cores of the calls, up to WALK_LIMIT */
	struct k_obj_core *seen[WALK_LIMIT];
	/* Number of the call that returns stop_status (1 is the first call), or 0 */
	size_t stop_at;
	/* Return value of call number stop_at */
	int stop_status;
	/* Number of held locks of obj_core_lock at each call */
	int lock_depth[WALK_LIMIT];
	/* If true, the walk function unlinks the object of the call */
	bool unlink;
};

/*
 * Walk function of the tests. It records each call. It stops the walk at
 * call number stop_at, and after WALK_LIMIT calls. Thus a walk of a list
 * with a cycle ends.
 */
static int walk_record(struct k_obj_core *obj_core, void *data)
{
	struct walk_log *log = data;

	if (log->calls < WALK_LIMIT) {
		log->seen[log->calls] = obj_core;
		log->lock_depth[log->calls] = (int)unit_arch_irq_lock_fake.call_count -
					      (int)unit_arch_irq_unlock_fake.call_count;
	}
	log->calls++;

	if (log->unlink) {
		k_obj_core_unlink(obj_core);
	}
	if (log->calls == log->stop_at) {
		return log->stop_status;
	}
	if (log->calls >= WALK_LIMIT) {
		return WALK_LIMIT_STATUS;
	}

	return 0;
}

#ifdef CONFIG_OBJ_CORE_STATS
/* Statistics functions of the test descriptor */
DECLARE_FAKE_VALUE_FUNC(int, unit_stats_raw, struct k_obj_core *, void *);
DECLARE_FAKE_VALUE_FUNC(int, unit_stats_query, struct k_obj_core *, void *);
DECLARE_FAKE_VALUE_FUNC(int, unit_stats_reset, struct k_obj_core *);
DECLARE_FAKE_VALUE_FUNC(int, unit_stats_disable, struct k_obj_core *);
DECLARE_FAKE_VALUE_FUNC(int, unit_stats_enable, struct k_obj_core *);
DEFINE_FAKE_VALUE_FUNC(int, unit_stats_raw, struct k_obj_core *, void *);
DEFINE_FAKE_VALUE_FUNC(int, unit_stats_query, struct k_obj_core *, void *);
DEFINE_FAKE_VALUE_FUNC(int, unit_stats_reset, struct k_obj_core *);
DEFINE_FAKE_VALUE_FUNC(int, unit_stats_disable, struct k_obj_core *);
DEFINE_FAKE_VALUE_FUNC(int, unit_stats_enable, struct k_obj_core *);

/* Size of the raw statistics: the buffer of unit_obj */
#define UNIT_RAW_SIZE sizeof(((struct unit_obj *)0)->stats)

/* Size of the reported statistics: not the raw size, to show which size a function compares */
#define UNIT_QUERY_SIZE (UNIT_RAW_SIZE + 4U)

/* Statistics descriptor with all functions */
static struct k_obj_core_stats_desc unit_stats_desc = {
	.raw_size = UNIT_RAW_SIZE,
	.query_size = UNIT_QUERY_SIZE,
	.raw = unit_stats_raw,
	.query = unit_stats_query,
	.reset = unit_stats_reset,
	.disable = unit_stats_disable,
	.enable = unit_stats_enable,
};

/* Statistics descriptor without functions */
static struct k_obj_core_stats_desc unit_stats_desc_empty = {
	.raw_size = UNIT_RAW_SIZE,
	.query_size = UNIT_QUERY_SIZE,
};
#endif /* CONFIG_OBJ_CORE_STATS */

/*
 * Descriptors of the boot init (section k_obj_core_desc). The static
 * objects of a type are an array of the test, not a linker section.
 * - Type A: three objects, a statistics descriptor and a statistics buffer.
 * - Type B: two objects, no statistics descriptor.
 * - Type C: two objects, a statistics descriptor, no statistics buffer.
 * - Type D: no static objects (as K_OBJ_TYPE_DEFINE_TYPE_ONLY()).
 */
static struct k_obj_type boot_type_a;
static struct k_obj_type boot_type_b;
static struct k_obj_type boot_type_c;
static struct k_obj_type boot_type_d;

static struct unit_obj boot_objs_a[3];
static struct unit_obj boot_objs_b[2];
static struct unit_obj boot_objs_c[2];

static const STRUCT_SECTION_ITERABLE(k_obj_core_desc, unit_desc_a) = {
	.type = &boot_type_a,
	.objs_start = &boot_objs_a[0],
	.objs_end = &boot_objs_a[ARRAY_SIZE(boot_objs_a)],
	.obj_core_offset = offsetof(struct unit_obj, obj_core),
	.obj_size = sizeof(struct unit_obj),
	.type_id = UNIT_TYPE_A_ID,
	Z_OBJ_CORE_STATS_DESC(&unit_stats_desc, offsetof(struct unit_obj, stats), UNIT_RAW_SIZE)};

static const STRUCT_SECTION_ITERABLE(k_obj_core_desc, unit_desc_b) = {
	.type = &boot_type_b,
	.objs_start = &boot_objs_b[0],
	.objs_end = &boot_objs_b[ARRAY_SIZE(boot_objs_b)],
	.obj_core_offset = offsetof(struct unit_obj, obj_core),
	.obj_size = sizeof(struct unit_obj),
	.type_id = UNIT_TYPE_B_ID,
	Z_OBJ_CORE_STATS_DESC(NULL, 0, 0)};

static const STRUCT_SECTION_ITERABLE(k_obj_core_desc, unit_desc_c) = {
	.type = &boot_type_c,
	.objs_start = &boot_objs_c[0],
	.objs_end = &boot_objs_c[ARRAY_SIZE(boot_objs_c)],
	.obj_core_offset = offsetof(struct unit_obj, obj_core),
	.obj_size = sizeof(struct unit_obj),
	.type_id = UNIT_TYPE_C_ID,
	Z_OBJ_CORE_STATS_DESC(&unit_stats_desc, 0, 0)};

static const STRUCT_SECTION_ITERABLE(k_obj_core_desc, unit_desc_d) = {
	.type = &boot_type_d,
	.objs_start = NULL,
	.objs_end = NULL,
	.obj_core_offset = offsetof(struct unit_obj, obj_core),
	.obj_size = sizeof(struct unit_obj),
	.type_id = UNIT_TYPE_D_ID,
	Z_OBJ_CORE_STATS_DESC(NULL, 0, 0)};

/* Run the boot init of obj_core.c. The second test source uses it for the static semaphores. */
void obj_core_unit_boot(void)
{
	z_obj_core_init_all();
}

/* Put an object into a known state: filled, with its name. */
static void obj_reset(struct unit_obj *obj, const char *name)
{
	memset(obj, FILL, sizeof(*obj));
	obj->name = name;
}

static void obj_core_unit_before(void *fixture)
{
	static const char *const boot_names[] = {"a0", "a1", "a2", "b0", "b1", "c0", "c1"};

	ARG_UNUSED(fixture);

	/* The fake rules reset all fakes before this function. */
	unit_arch_irq_lock_fake.return_val = KERNEL_UNIT_IRQ_KEY;

	/* The boot init appends the types again: start each test with no types. */
	sys_slist_init(&z_obj_type_list);

	obj_reset(&obj_a, "a");
	obj_reset(&obj_b, "b");
	obj_reset(&obj_c, "c");
	obj_reset(&obj_d, "d");
	memset(&unit_type, FILL, sizeof(unit_type));
	memset(&unit_type2, FILL, sizeof(unit_type2));
	(void)z_obj_type_init(&unit_type, UNIT_TYPE_A_ID, offsetof(struct unit_obj, obj_core));
	sys_slist_init(&z_obj_type_list);

	/* At boot, the types are static data with zeros. */
	memset(&boot_type_a, 0, sizeof(boot_type_a));
	memset(&boot_type_b, 0, sizeof(boot_type_b));
	memset(&boot_type_c, 0, sizeof(boot_type_c));
	memset(&boot_type_d, 0, sizeof(boot_type_d));
	for (size_t i = 0; i < ARRAY_SIZE(boot_objs_a); i++) {
		obj_reset(&boot_objs_a[i], boot_names[i]);
	}
	for (size_t i = 0; i < ARRAY_SIZE(boot_objs_b); i++) {
		obj_reset(&boot_objs_b[i], boot_names[3 + i]);
	}
	for (size_t i = 0; i < ARRAY_SIZE(boot_objs_c); i++) {
		obj_reset(&boot_objs_c[i], boot_names[5 + i]);
	}

#ifdef CONFIG_OBJ_CORE_STATS
	RESET_FAKE(unit_stats_raw);
	RESET_FAKE(unit_stats_query);
	RESET_FAKE(unit_stats_reset);
	RESET_FAKE(unit_stats_disable);
	RESET_FAKE(unit_stats_enable);
	unit_type.stats_desc = NULL;
#endif /* CONFIG_OBJ_CORE_STATS */

	/* The history of the setup is not part of a test. */
	FFF_RESET_HISTORY();
	RESET_FAKE(unit_arch_irq_lock);
	RESET_FAKE(unit_arch_irq_unlock);
	unit_arch_irq_lock_fake.return_val = KERNEL_UNIT_IRQ_KEY;
}

ZTEST_SUITE(obj_core_unit, NULL, NULL, obj_core_unit_before, NULL, NULL);

/* Assert that one operation locked obj_core_lock once and released it with k_spin_unlock(). */
static void assert_lock_released_once(void)
{
	kernel_unit_assert_lock_released_once(&obj_core_lock, KERNEL_UNIT_RELEASED_BY_UNLOCK);
}

/* Forget the lock calls of the setup of a test. */
static void forget_setup_calls(void)
{
	FFF_RESET_HISTORY();
	RESET_FAKE(unit_arch_irq_lock);
	RESET_FAKE(unit_arch_irq_unlock);
	unit_arch_irq_lock_fake.return_val = KERNEL_UNIT_IRQ_KEY;
}

/*
 * Tests: Object types. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_obj_core, at the top of this file.
 */

/**
 * @brief z_obj_type_init() sets the ID and the offset, empties the object list and returns the type.
 *
 * @details
 * - Setup: an object type filled with a pattern.
 * - Action: z_obj_type_init() with an ID and an offset.
 * - Expected: the return value is the type. The type has the ID and the
 *   offset. Its object list is empty.
 *
 * @ingroup kernel_unit_obj_core_z_obj_type_init
 * @see z_obj_type_init()
 */
ZTEST(obj_core_unit, test_type_init_sets_fields)
{
	zassert_equal_ptr(z_obj_type_init(&unit_type2, UNIT_TYPE_B_ID, 24U), &unit_type2);

	zassert_equal(unit_type2.id, UNIT_TYPE_B_ID);
	zassert_equal(unit_type2.obj_core_offset, 24U);
	zassert_true(sys_slist_is_empty(&unit_type2.list));
	zassert_is_null(sys_slist_peek_tail(&unit_type2.list));
}

#ifdef CONFIG_OBJ_CORE_STATS
/**
 * @brief With CONFIG_OBJ_CORE_STATS, z_obj_type_init() does not write the statistics descriptor.
 *
 * @details
 * - Setup: an object type filled with a pattern.
 * - Action: z_obj_type_init().
 * - Expected: @c stats_desc keeps the pattern. Only
 *   k_obj_type_stats_init() sets it.
 *
 * @note Design rule: the storage of a type must be zero before
 * z_obj_type_init(), or the caller must call k_obj_type_stats_init(). The
 * types of K_OBJ_TYPE_DEFINE() are static data, so they are zero at boot.
 * The boot init calls k_obj_type_stats_init() only if the descriptor of the
 * type has statistics. A type in other storage, for example on the heap,
 * gets a statistics descriptor from old data, and a statistics request then
 * calls a function from this data.
 *
 * @ingroup kernel_unit_obj_core_z_obj_type_init
 * @see z_obj_type_init()
 */
ZTEST(obj_core_unit, test_type_init_keeps_stats_desc)
{
	struct k_obj_core_stats_desc *before;

	memset(&unit_type2, FILL, sizeof(unit_type2));
	before = unit_type2.stats_desc;

	(void)z_obj_type_init(&unit_type2, UNIT_TYPE_B_ID, 0U);

	zassert_equal_ptr(unit_type2.stats_desc, before);
}
#endif /* CONFIG_OBJ_CORE_STATS */

/**
 * @brief z_obj_type_init() appends the type to the end of the global type list.
 *
 * @details
 * - Action: z_obj_type_init() for two types.
 * - Expected: @c z_obj_type_list holds the two types in the order of the
 *   calls.
 *
 * @ingroup kernel_unit_obj_core_z_obj_type_init
 * @see z_obj_type_init()
 */
ZTEST(obj_core_unit, test_type_init_appends_to_type_list)
{
	(void)z_obj_type_init(&unit_type, UNIT_TYPE_A_ID, 0U);
	(void)z_obj_type_init(&unit_type2, UNIT_TYPE_B_ID, 0U);

	zassert_list_order(&z_obj_type_list,
			   (const sys_snode_t *const[]){&unit_type.node, &unit_type2.node}, 2U,
			   node_name);
}

/**
 * @brief z_obj_type_init() does not lock obj_core_lock.
 *
 * @details
 * - Action: z_obj_type_init().
 * - Expected: no call of arch_irq_lock().
 *
 * @note This is a possible defect of low severity. k_obj_type_find()
 * walks @c z_obj_type_list with @c obj_core_lock held, but
 * z_obj_type_init() changes the list without the lock. At boot, only one
 * thread runs, so this is correct. The socket code calls z_obj_type_init()
 * at the first socket init after boot (socket_obj_core.c:64). A concurrent
 * k_obj_type_find() on another CPU then reads a list that changes.
 *
 * @ingroup kernel_unit_obj_core_z_obj_type_init
 * @see z_obj_type_init()
 */
ZTEST(obj_core_unit, test_type_init_does_not_lock)
{
	(void)z_obj_type_init(&unit_type, UNIT_TYPE_A_ID, 0U);

	zassert_equal(unit_arch_irq_lock_fake.call_count, 0);
}

/**
 * @brief k_obj_type_find() returns the registered type with the ID.
 *
 * @details
 * - Setup: two registered types.
 * - Action: k_obj_type_find() with the ID of the first and of the second
 *   type.
 * - Expected: the return value is the type with the ID. Each call locks
 *   @c obj_core_lock once and releases it.
 *
 * @ingroup kernel_unit_obj_core_k_obj_type_find
 * @see k_obj_type_find()
 */
ZTEST(obj_core_unit, test_type_find_returns_type)
{
	(void)z_obj_type_init(&unit_type, UNIT_TYPE_A_ID, 0U);
	(void)z_obj_type_init(&unit_type2, UNIT_TYPE_B_ID, 0U);
	forget_setup_calls();

	zassert_equal_ptr(k_obj_type_find(UNIT_TYPE_B_ID), &unit_type2);
	assert_lock_released_once();

	zassert_equal_ptr(k_obj_type_find(UNIT_TYPE_A_ID), &unit_type);
}

/**
 * @brief k_obj_type_find() returns NULL for an ID that no registered type has.
 *
 * @details
 * - Setup: one registered type. Then no registered type.
 * - Action: k_obj_type_find() with an unknown ID.
 * - Expected: NULL each time. The call locks @c obj_core_lock once and
 *   releases it.
 *
 * @ingroup kernel_unit_obj_core_k_obj_type_find
 * @see k_obj_type_find()
 */
ZTEST(obj_core_unit, test_type_find_returns_null_for_unknown_id)
{
	zassert_is_null(k_obj_type_find(UNIT_TYPE_UNKNOWN_ID));

	(void)z_obj_type_init(&unit_type, UNIT_TYPE_A_ID, 0U);
	forget_setup_calls();

	zassert_is_null(k_obj_type_find(UNIT_TYPE_UNKNOWN_ID));
	assert_lock_released_once();
}

/**
 * @brief k_obj_type_find() returns the first registered type if two types have the same ID.
 *
 * @details
 * - Setup: two registered types with the same ID.
 * - Action: k_obj_type_find() with this ID.
 * - Expected: the first type. z_obj_type_init() does not reject a second
 *   type with the same ID, so the second type is not found.
 *
 * @ingroup kernel_unit_obj_core_k_obj_type_find
 * @see k_obj_type_find(), z_obj_type_init()
 */
ZTEST(obj_core_unit, test_type_find_returns_first_of_same_id)
{
	(void)z_obj_type_init(&unit_type, UNIT_TYPE_A_ID, 0U);
	(void)z_obj_type_init(&unit_type2, UNIT_TYPE_A_ID, 0U);

	zassert_equal_ptr(k_obj_type_find(UNIT_TYPE_A_ID), &unit_type);
}

/*
 * Tests: Object core link. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_obj_core, at the top of this file.
 */

/**
 * @brief k_obj_core_init() sets the type, clears the node and, with statistics, clears the buffer.
 *
 * @details
 * - Setup: an object filled with a pattern.
 * - Action: k_obj_core_init() with a type.
 * - Expected: the object core has the type, and the next pointer of its
 *   node is NULL. With CONFIG_OBJ_CORE_STATS, the statistics pointer is
 *   NULL. The list of the type stays empty, and no lock occurs.
 *
 * @ingroup kernel_unit_obj_core_k_obj_core_init
 * @see k_obj_core_init()
 */
ZTEST(obj_core_unit, test_core_init_sets_type_and_clears_node)
{
	k_obj_core_init(&obj_a.obj_core, &unit_type);

	zassert_equal_ptr(obj_a.obj_core.type, &unit_type);
	zassert_is_null(obj_a.obj_core.node.next);
#ifdef CONFIG_OBJ_CORE_STATS
	zassert_is_null(obj_a.obj_core.stats);
#endif /* CONFIG_OBJ_CORE_STATS */
	zassert_true(sys_slist_is_empty(&unit_type.list));
	zassert_equal(unit_arch_irq_lock_fake.call_count, 0);
}

/**
 * @brief k_obj_core_link() appends the object to the end of the list of its type.
 *
 * @details
 * - Action: k_obj_core_init() and k_obj_core_link() for the objects a, b
 *   and c.
 * - Expected: the list of the type is a, b, c. The tail is c.
 *
 * @ingroup kernel_unit_obj_core_k_obj_core_link
 * @see k_obj_core_link()
 */
ZTEST(obj_core_unit, test_link_appends_in_order)
{
	k_obj_core_init(&obj_a.obj_core, &unit_type);
	k_obj_core_link(&obj_a.obj_core);
	k_obj_core_init(&obj_b.obj_core, &unit_type);
	k_obj_core_link(&obj_b.obj_core);
	k_obj_core_init(&obj_c.obj_core, &unit_type);
	k_obj_core_link(&obj_c.obj_core);

	zassert_list_order(&unit_type.list,
			   (const sys_snode_t *const[]){NODE(obj_a), NODE(obj_b), NODE(obj_c)}, 3U,
			   node_name);
}

/**
 * @brief k_obj_core_link() locks obj_core_lock once and releases it with the key.
 *
 * @details
 * - Setup: an object after k_obj_core_init().
 * - Action: k_obj_core_link().
 * - Expected: one arch_irq_lock() as the first call, one arch_irq_unlock()
 *   with the key as the last call.
 *
 * @ingroup kernel_unit_obj_core_k_obj_core_link
 * @see k_obj_core_link()
 */
ZTEST(obj_core_unit, test_link_locks_once)
{
	k_obj_core_init(&obj_a.obj_core, &unit_type);

	k_obj_core_link(&obj_a.obj_core);

	assert_lock_released_once();
}

/**
 * @brief k_obj_core_init_and_link() initializes the object core and appends it.
 *
 * @details
 * - Setup: two objects filled with a pattern.
 * - Action: k_obj_core_init_and_link() for a, then for b.
 * - Expected: each object core has the type. The list is a, b. The second
 *   call locks @c obj_core_lock once and releases it.
 *
 * @ingroup kernel_unit_obj_core_k_obj_core_init_and_link
 * @see k_obj_core_init_and_link()
 */
ZTEST(obj_core_unit, test_init_and_link_links_object)
{
	k_obj_core_init_and_link(&obj_a.obj_core, &unit_type);
	forget_setup_calls();

	k_obj_core_init_and_link(&obj_b.obj_core, &unit_type);

	assert_lock_released_once();
	zassert_equal_ptr(obj_a.obj_core.type, &unit_type);
	zassert_equal_ptr(obj_b.obj_core.type, &unit_type);
	zassert_list_order(&unit_type.list, (const sys_snode_t *const[]){NODE(obj_a), NODE(obj_b)},
			   2U, node_name);
}

/**
 * @brief k_obj_core_unlink() removes the object and keeps the order of the other objects.
 *
 * @details
 * - Setup: the objects a, b, c, d in the list.
 * - Action: k_obj_core_unlink() for b (middle), then for d (tail), then
 *   for a (head).
 * - Expected: after each call, the list holds the other objects in their
 *   order, and the tail is the last object. The next pointer of each
 *   removed node is NULL. Each call locks @c obj_core_lock once.
 *
 * @ingroup kernel_unit_obj_core_k_obj_core_unlink
 * @see k_obj_core_unlink()
 */
ZTEST(obj_core_unit, test_unlink_removes_object)
{
	link_objects((struct unit_obj *const[]){&obj_a, &obj_b, &obj_c, &obj_d}, 4U);
	forget_setup_calls();

	k_obj_core_unlink(&obj_b.obj_core);
	assert_lock_released_once();
	zassert_is_null(obj_b.obj_core.node.next);
	zassert_list_order(&unit_type.list,
			   (const sys_snode_t *const[]){NODE(obj_a), NODE(obj_c), NODE(obj_d)}, 3U,
			   node_name);

	k_obj_core_unlink(&obj_d.obj_core);
	zassert_list_order(&unit_type.list, (const sys_snode_t *const[]){NODE(obj_a), NODE(obj_c)},
			   2U, node_name);

	k_obj_core_unlink(&obj_a.obj_core);
	zassert_list_order(&unit_type.list, (const sys_snode_t *const[]){NODE(obj_c)}, 1U,
			   node_name);
}

/**
 * @brief k_obj_core_unlink() of the only object makes the list empty.
 *
 * @details
 * - Setup: the object a is the only object in the list.
 * - Action: k_obj_core_unlink() for a.
 * - Expected: the list is empty. Head and tail are NULL.
 *
 * @ingroup kernel_unit_obj_core_k_obj_core_unlink
 * @see k_obj_core_unlink()
 */
ZTEST(obj_core_unit, test_unlink_of_only_object_empties_list)
{
	link_objects((struct unit_obj *const[]){&obj_a}, 1U);

	k_obj_core_unlink(&obj_a.obj_core);

	zassert_list_holds(&unit_type.list, NULL, 0U, node_name);
	zassert_is_null(sys_slist_peek_head(&unit_type.list));
}

/**
 * @brief k_obj_core_unlink() of an object that is not in the list changes nothing.
 *
 * @details
 * - Setup: the objects a and b in the list. The object c is initialized,
 *   not linked.
 * - Action: k_obj_core_unlink() for c.
 * - Expected: the list is a, b. The call locks @c obj_core_lock once and
 *   releases it.
 *
 * @ingroup kernel_unit_obj_core_k_obj_core_unlink
 * @see k_obj_core_unlink()
 */
ZTEST(obj_core_unit, test_unlink_of_unlinked_object_changes_nothing)
{
	link_objects((struct unit_obj *const[]){&obj_a, &obj_b}, 2U);
	k_obj_core_init(&obj_c.obj_core, &unit_type);
	forget_setup_calls();

	k_obj_core_unlink(&obj_c.obj_core);

	assert_lock_released_once();
	zassert_list_order(&unit_type.list, (const sys_snode_t *const[]){NODE(obj_a), NODE(obj_b)},
			   2U, node_name);
}

/**
 * @brief An unlink before the second init keeps the list correct.
 *
 * @details
 * - Setup: the objects a, b, c in the list.
 * - Action: k_obj_core_unlink() for each object, then
 *   k_obj_core_init_and_link() for each object again.
 * - Expected: the list holds a, b, c, each one time, and has no cycle. This
 *   is the sequence that a correct second init must have.
 *
 * @ingroup kernel_unit_obj_core_k_obj_core_unlink
 * @see k_obj_core_unlink(), k_obj_core_init_and_link()
 */
ZTEST(obj_core_unit, test_unlink_then_link_again_keeps_list)
{
	static struct unit_obj *const objs[] = {&obj_a, &obj_b, &obj_c};

	link_objects(objs, ARRAY_SIZE(objs));

	for (size_t i = 0; i < ARRAY_SIZE(objs); i++) {
		k_obj_core_unlink(&objs[i]->obj_core);
		k_obj_core_init_and_link(&objs[i]->obj_core, &unit_type);
	}

	zassert_list_order(&unit_type.list,
			   (const sys_snode_t *const[]){NODE(obj_a), NODE(obj_b), NODE(obj_c)}, 3U,
			   node_name);
}

/*
 * Tests: Walks. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_obj_core, at the top of this file.
 */

/**
 * @brief k_obj_type_walk_locked() calls the function for each object in list order, and returns 0.
 *
 * @details
 * - Setup: the objects a, b, c in the list.
 * - Action: k_obj_type_walk_locked() with a function that returns 0.
 * - Expected: three calls, with a, b and c, and the data pointer. The
 *   return value is 0.
 *
 * @ingroup kernel_unit_obj_core_k_obj_type_walk_locked
 * @see k_obj_type_walk_locked()
 */
ZTEST(obj_core_unit, test_walk_locked_visits_each_object)
{
	struct walk_log log = {0};

	link_objects((struct unit_obj *const[]){&obj_a, &obj_b, &obj_c}, 3U);

	zassert_equal(k_obj_type_walk_locked(&unit_type, walk_record, &log), 0);

	zassert_equal(log.calls, 3U);
	zassert_equal_ptr(log.seen[0], &obj_a.obj_core);
	zassert_equal_ptr(log.seen[1], &obj_b.obj_core);
	zassert_equal_ptr(log.seen[2], &obj_c.obj_core);
}

/**
 * @brief k_obj_type_walk_locked() holds obj_core_lock during each call, and releases it once.
 *
 * @details
 * - Setup: the objects a and b in the list.
 * - Action: k_obj_type_walk_locked().
 * - Expected: at each call of the function, one lock is held. The walk
 *   locks once and releases once, with the key.
 *
 * @note The function runs with interrupts locked. The time of the walk
 * grows with the number of objects of the type: one call per object.
 *
 * @ingroup kernel_unit_obj_core_k_obj_type_walk_locked
 * @see k_obj_type_walk_locked()
 */
ZTEST(obj_core_unit, test_walk_locked_holds_lock)
{
	struct walk_log log = {0};

	link_objects((struct unit_obj *const[]){&obj_a, &obj_b}, 2U);
	forget_setup_calls();

	zassert_equal(k_obj_type_walk_locked(&unit_type, walk_record, &log), 0);

	zassert_equal(log.lock_depth[0], 1);
	zassert_equal(log.lock_depth[1], 1);
	assert_lock_released_once();
}

/**
 * @brief k_obj_type_walk_locked() stops at the first status that is not 0 and returns it.
 *
 * @details
 * - Setup: the objects a, b, c in the list.
 * - Action: k_obj_type_walk_locked() with a function that returns 7 at
 *   the second call.
 * - Expected: two calls. The return value is 7. The walk releases the lock
 *   once.
 *
 * @ingroup kernel_unit_obj_core_k_obj_type_walk_locked
 * @see k_obj_type_walk_locked()
 */
ZTEST(obj_core_unit, test_walk_locked_stops_at_status)
{
	struct walk_log log = {.stop_at = 2U, .stop_status = 7};

	link_objects((struct unit_obj *const[]){&obj_a, &obj_b, &obj_c}, 3U);
	forget_setup_calls();

	zassert_equal(k_obj_type_walk_locked(&unit_type, walk_record, &log), 7);

	zassert_equal(log.calls, 2U);
	assert_lock_released_once();
}

/**
 * @brief k_obj_type_walk_locked() of an empty type calls no function and returns 0.
 *
 * @details
 * - Setup: a type with no objects.
 * - Action: k_obj_type_walk_locked().
 * - Expected: no call, return value 0, one lock and one release.
 *
 * @ingroup kernel_unit_obj_core_k_obj_type_walk_locked
 * @see k_obj_type_walk_locked()
 */
ZTEST(obj_core_unit, test_walk_locked_of_empty_type)
{
	struct walk_log log = {0};

	zassert_equal(k_obj_type_walk_locked(&unit_type, walk_record, &log), 0);

	zassert_equal(log.calls, 0U);
	assert_lock_released_once();
}

/**
 * @brief k_obj_type_walk_unlocked() calls the function for each object in list order, with no lock.
 *
 * @details
 * - Setup: the objects a, b, c in the list.
 * - Action: k_obj_type_walk_unlocked() with a function that returns 0.
 * - Expected: three calls, with a, b and c. The return value is 0. No
 *   lock occurs.
 *
 * @ingroup kernel_unit_obj_core_k_obj_type_walk_unlocked
 * @see k_obj_type_walk_unlocked()
 */
ZTEST(obj_core_unit, test_walk_unlocked_visits_each_object)
{
	struct walk_log log = {0};

	link_objects((struct unit_obj *const[]){&obj_a, &obj_b, &obj_c}, 3U);
	forget_setup_calls();

	zassert_equal(k_obj_type_walk_unlocked(&unit_type, walk_record, &log), 0);

	zassert_equal(log.calls, 3U);
	zassert_equal_ptr(log.seen[0], &obj_a.obj_core);
	zassert_equal_ptr(log.seen[1], &obj_b.obj_core);
	zassert_equal_ptr(log.seen[2], &obj_c.obj_core);
	zassert_equal(unit_arch_irq_lock_fake.call_count, 0);
}

/**
 * @brief k_obj_type_walk_unlocked() stops at the first status that is not 0 and returns it.
 *
 * @details
 * - Setup: the objects a, b, c in the list. Then a type with no objects.
 * - Action: k_obj_type_walk_unlocked() with a function that returns -5 at
 *   the first call. Then a walk of the empty type.
 * - Expected: one call and the return value -5. The walk of the empty
 *   type calls no function and returns 0.
 *
 * @ingroup kernel_unit_obj_core_k_obj_type_walk_unlocked
 * @see k_obj_type_walk_unlocked()
 */
ZTEST(obj_core_unit, test_walk_unlocked_stops_at_status)
{
	struct walk_log log = {.stop_at = 1U, .stop_status = -5};
	struct walk_log empty_log = {0};

	link_objects((struct unit_obj *const[]){&obj_a, &obj_b, &obj_c}, 3U);

	zassert_equal(k_obj_type_walk_unlocked(&unit_type, walk_record, &log), -5);
	zassert_equal(log.calls, 1U);

	(void)z_obj_type_init(&unit_type2, UNIT_TYPE_B_ID, 0U);
	zassert_equal(k_obj_type_walk_unlocked(&unit_type2, walk_record, &empty_log), 0);
	zassert_equal(empty_log.calls, 0U);
}

/**
 * @brief The function of k_obj_type_walk_unlocked() can unlink the object of the call.
 *
 * @details
 * - Setup: the objects a, b, c in the list.
 * - Action: k_obj_type_walk_unlocked() with a function that unlinks the
 *   object of each call.
 * - Expected: three calls, with a, b and c. The list is empty after the
 *   walk.
 *
 * @ingroup kernel_unit_obj_core_k_obj_type_walk_unlocked
 * @see k_obj_type_walk_unlocked()
 */
ZTEST(obj_core_unit, test_walk_unlocked_permits_unlink)
{
	struct walk_log log = {.unlink = true};

	link_objects((struct unit_obj *const[]){&obj_a, &obj_b, &obj_c}, 3U);

	zassert_equal(k_obj_type_walk_unlocked(&unit_type, walk_record, &log), 0);

	zassert_equal(log.calls, 3U);
	zassert_equal_ptr(log.seen[2], &obj_c.obj_core);
	zassert_list_holds(&unit_type.list, NULL, 0U, node_name);
}

/*
 * Tests: Boot init. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_obj_core, at the top of this file.
 */

/**
 * @brief The unit registers z_obj_core_init_all() and init_kernel_obj_core_list() as boot init.
 *
 * @details
 * - Action: read the entries of K_KERNEL_INIT_PRE().
 * - Expected: the entry @c _kernel_init_pre_z_obj_core_init_all calls
 *   z_obj_core_init_all(). With CONFIG_OBJ_CORE_SYSTEM, the entry
 *   @c _kernel_init_pre_init_kernel_obj_core_list calls
 *   init_kernel_obj_core_list().
 *
 * @ingroup kernel_unit_obj_core_static
 * @see z_obj_core_init_all()
 */
ZTEST(obj_core_unit, test_boot_init_entries)
{
	zassert_equal_ptr(_kernel_init_pre_z_obj_core_init_all.init_fn, z_obj_core_init_all);
#ifdef CONFIG_OBJ_CORE_SYSTEM
	zassert_equal_ptr(_kernel_init_pre_init_kernel_obj_core_list.init_fn,
			  init_kernel_obj_core_list);
#endif /* CONFIG_OBJ_CORE_SYSTEM */
}

/**
 * @brief z_obj_core_init_all() registers each type of the section with its ID and offset.
 *
 * @details
 * - Setup: the descriptors of the types A, B, C and D of the test.
 * - Action: z_obj_core_init_all().
 * - Expected: k_obj_type_find() finds each type with its ID. Each type has
 *   the offset of @c obj_core in @c struct @c unit_obj.
 *
 * @ingroup kernel_unit_obj_core_static
 * @see z_obj_core_init_all()
 */
ZTEST(obj_core_unit, test_boot_registers_types)
{
	z_obj_core_init_all();

	zassert_equal_ptr(k_obj_type_find(UNIT_TYPE_A_ID), &boot_type_a);
	zassert_equal_ptr(k_obj_type_find(UNIT_TYPE_B_ID), &boot_type_b);
	zassert_equal_ptr(k_obj_type_find(UNIT_TYPE_C_ID), &boot_type_c);
	zassert_equal_ptr(k_obj_type_find(UNIT_TYPE_D_ID), &boot_type_d);
	zassert_equal(boot_type_a.obj_core_offset, offsetof(struct unit_obj, obj_core));
	zassert_equal(boot_type_d.obj_core_offset, offsetof(struct unit_obj, obj_core));
}

/**
 * @brief z_obj_core_init_all() links the static objects of each type in address order.
 *
 * @details
 * - Setup: the static objects of the types A (3), B (2) and C (2), filled
 *   with a pattern. The type D has no static objects.
 * - Action: z_obj_core_init_all().
 * - Expected: the list of each type holds its static objects in address
 *   order. Each object core has its type. The list of type D is empty.
 *
 * @ingroup kernel_unit_obj_core_static
 * @see z_obj_core_init_all()
 */
ZTEST(obj_core_unit, test_boot_links_static_objects)
{
	z_obj_core_init_all();

	zassert_list_order(&boot_type_a.list,
			   (const sys_snode_t *const[]){NODE(boot_objs_a[0]), NODE(boot_objs_a[1]),
							NODE(boot_objs_a[2])},
			   3U, node_name);
	zassert_list_order(&boot_type_b.list,
			   (const sys_snode_t *const[]){NODE(boot_objs_b[0]), NODE(boot_objs_b[1])},
			   2U, node_name);
	zassert_list_order(&boot_type_c.list,
			   (const sys_snode_t *const[]){NODE(boot_objs_c[0]), NODE(boot_objs_c[1])},
			   2U, node_name);
	zassert_list_holds(&boot_type_d.list, NULL, 0U, node_name);
	zassert_equal_ptr(boot_objs_a[2].obj_core.type, &boot_type_a);
	zassert_equal_ptr(boot_objs_b[0].obj_core.type, &boot_type_b);
}

#ifdef CONFIG_OBJ_CORE_STATS
/**
 * @brief With CONFIG_OBJ_CORE_STATS, z_obj_core_init_all() registers the statistics of a static
 * object only if the type has a descriptor and a buffer size.
 *
 * @details
 * - Setup: type A has a statistics descriptor and a buffer, type B has no
 *   descriptor, type C has a descriptor and the buffer size 0.
 * - Action: z_obj_core_init_all().
 * - Expected: the types A and C have the descriptor, type B has none.
 *   Each object of type A has its own buffer @c stats as statistics. The
 *   objects of the types B and C have no statistics (NULL).
 *
 * @ingroup kernel_unit_obj_core_static
 * @see z_obj_core_init_all()
 */
ZTEST(obj_core_unit, test_boot_registers_static_statistics)
{
	z_obj_core_init_all();

	zassert_equal_ptr(boot_type_a.stats_desc, &unit_stats_desc);
	zassert_is_null(boot_type_b.stats_desc);
	zassert_equal_ptr(boot_type_c.stats_desc, &unit_stats_desc);
	for (size_t i = 0; i < ARRAY_SIZE(boot_objs_a); i++) {
		zassert_equal_ptr(boot_objs_a[i].obj_core.stats, boot_objs_a[i].stats);
	}
	zassert_is_null(boot_objs_b[0].obj_core.stats);
	zassert_is_null(boot_objs_c[0].obj_core.stats);
	zassert_is_null(boot_objs_c[1].obj_core.stats);
}
#endif /* CONFIG_OBJ_CORE_STATS */

#ifdef CONFIG_OBJ_CORE_SYSTEM
/* Name of the node of the kernel object */
static const char *kernel_node_name(const sys_snode_t *node)
{
	return (node == &_kernel.obj_core.node) ? "_kernel" : "?";
}

/**
 * @brief With CONFIG_OBJ_CORE_SYSTEM, init_kernel_obj_core_list() registers the kernel type and
 * links the kernel object.
 *
 * @details
 * - Setup: @c _kernel filled with zeros (rule of the fake group init).
 * - Action: init_kernel_obj_core_list().
 * - Expected: k_obj_type_find() with K_OBJ_TYPE_KERNEL_ID returns the
 *   kernel type. Its offset is the offset of @c obj_core in
 *   @c struct @c z_kernel. Its list holds only @c _kernel.
 *
 * @ingroup kernel_unit_obj_core_static
 * @see init_kernel_obj_core_list()
 */
ZTEST(obj_core_unit, test_boot_links_kernel_object)
{
	init_kernel_obj_core_list();

	zassert_equal_ptr(k_obj_type_find(K_OBJ_TYPE_KERNEL_ID), &obj_type_kernel);
	zassert_equal(obj_type_kernel.obj_core_offset, offsetof(struct z_kernel, obj_core));
	zassert_equal_ptr(_kernel.obj_core.type, &obj_type_kernel);
	zassert_list_order(&obj_type_kernel.list,
			   (const sys_snode_t *const[]){&_kernel.obj_core.node}, 1U,
			   kernel_node_name);
}
#endif /* CONFIG_OBJ_CORE_SYSTEM */

#ifdef CONFIG_OBJ_CORE_STATS_SYSTEM
/**
 * @brief With CONFIG_OBJ_CORE_STATS_SYSTEM, the kernel object has statistics that forward to
 * z_kernel_stats_raw() and z_kernel_stats_query().
 *
 * @details
 * - Setup: init_kernel_obj_core_list().
 * - Action: k_obj_core_stats_raw() with the size of @c _kernel.usage, and
 *   k_obj_core_stats_query() with the size of
 *   @c struct @c k_thread_runtime_stats. Then k_obj_core_stats_reset(),
 *   _disable() and _enable().
 * - Expected: the statistics buffer of the kernel object is
 *   @c _kernel.usage. The raw and the query request return the value of
 *   z_kernel_stats_raw() and z_kernel_stats_query(), which get the object
 *   core and the buffer. The kernel descriptor has no reset, disable and
 *   enable functions: these requests return -ENOTSUP.
 *
 * @ingroup kernel_unit_obj_core_static
 * @see init_kernel_obj_core_list(), k_obj_core_stats_raw(), k_obj_core_stats_query()
 */
ZTEST(obj_core_unit, test_boot_kernel_statistics)
{
	struct k_cycle_stats raw[CONFIG_MP_MAX_NUM_CPUS];
	struct k_thread_runtime_stats query;

	init_kernel_obj_core_list();
	z_kernel_stats_raw_fake.return_val = 3;
	z_kernel_stats_query_fake.return_val = 4;

	zassert_equal_ptr(obj_type_kernel.stats_desc, &kernel_stats_desc);
	zassert_equal_ptr(_kernel.obj_core.stats, _kernel.usage);
	zassert_equal(sizeof(raw), sizeof(_kernel.usage));

	zassert_equal(k_obj_core_stats_raw(&_kernel.obj_core, raw, sizeof(raw)), 3);
	zassert_equal_ptr(z_kernel_stats_raw_fake.arg0_val, &_kernel.obj_core);
	zassert_equal_ptr(z_kernel_stats_raw_fake.arg1_val, raw);

	zassert_equal(k_obj_core_stats_query(&_kernel.obj_core, &query, sizeof(query)), 4);
	zassert_equal_ptr(z_kernel_stats_query_fake.arg0_val, &_kernel.obj_core);
	zassert_equal_ptr(z_kernel_stats_query_fake.arg1_val, &query);

	zassert_equal(k_obj_core_stats_reset(&_kernel.obj_core), -ENOTSUP);
	zassert_equal(k_obj_core_stats_disable(&_kernel.obj_core), -ENOTSUP);
	zassert_equal(k_obj_core_stats_enable(&_kernel.obj_core), -ENOTSUP);
}
#endif /* CONFIG_OBJ_CORE_STATS_SYSTEM */

#ifdef CONFIG_OBJ_CORE_STATS
/*
 * Tests: Statistics. Each test is in the group of the function that it
 * tests. The design text is in that group, or in the introduction of
 * the group kernel_unit_obj_core, at the top of this file.
 */

/* The five requests that forward to a function of the descriptor */
enum stats_request {
	REQ_RAW,
	REQ_QUERY,
	REQ_RESET,
	REQ_DISABLE,
	REQ_ENABLE,
	REQ_COUNT,
};

static const char *const request_names[REQ_COUNT] = {"raw", "query", "reset", "disable",
						     "enable"};

/* Buffer for the raw and the query request: large enough for both sizes */
static uint8_t request_buf[UNIT_QUERY_SIZE + 8U];

/* Do one request. size is the buffer size of the raw and the query request. */
static int stats_request(enum stats_request req, struct k_obj_core *obj_core, size_t size)
{
	switch (req) {
	case REQ_RAW:
		return k_obj_core_stats_raw(obj_core, request_buf, size);
	case REQ_QUERY:
		return k_obj_core_stats_query(obj_core, request_buf, size);
	case REQ_RESET:
		return k_obj_core_stats_reset(obj_core);
	case REQ_DISABLE:
		return k_obj_core_stats_disable(obj_core);
	case REQ_ENABLE:
	default:
		return k_obj_core_stats_enable(obj_core);
	}
}

/* The correct buffer size of a request */
static size_t request_size(enum stats_request req)
{
	return (req == REQ_QUERY) ? UNIT_QUERY_SIZE : UNIT_RAW_SIZE;
}

/* The fake of the descriptor function of a request */
static fff_function_t request_fake(enum stats_request req)
{
	static const fff_function_t fakes[REQ_COUNT] = {
		KERNEL_UNIT_FN(unit_stats_raw),     KERNEL_UNIT_FN(unit_stats_query),
		KERNEL_UNIT_FN(unit_stats_reset),   KERNEL_UNIT_FN(unit_stats_disable),
		KERNEL_UNIT_FN(unit_stats_enable),
	};

	return fakes[req];
}

/* Number of calls of the descriptor functions */
static unsigned int descriptor_calls(void)
{
	return unit_stats_raw_fake.call_count + unit_stats_query_fake.call_count +
	       unit_stats_reset_fake.call_count + unit_stats_disable_fake.call_count +
	       unit_stats_enable_fake.call_count;
}

/* Link object a to the test type with the descriptor, and register its statistics buffer */
static void prepare_registered(struct k_obj_core_stats_desc *desc)
{
	unit_type.stats_desc = desc;
	k_obj_core_init_and_link(&obj_a.obj_core, &unit_type);
	obj_a.obj_core.stats = obj_a.stats;
	forget_setup_calls();
}

/**
 * @brief k_obj_core_stats_register() sets the statistics buffer if the size is the raw size.
 *
 * @details
 * - Setup: an object of a type with a statistics descriptor.
 * - Action: k_obj_core_stats_register() with a buffer of the raw size.
 * - Expected: return value 0. The statistics pointer is the buffer. The call
 *   locks @c obj_core_lock once and releases it.
 *
 * @ingroup kernel_unit_obj_core_k_obj_core_stats_register
 * @see k_obj_core_stats_register()
 */
ZTEST(obj_core_unit, test_stats_register_sets_buffer)
{
	prepare_registered(&unit_stats_desc);
	obj_a.obj_core.stats = NULL;

	zassert_equal(k_obj_core_stats_register(&obj_a.obj_core, obj_a.stats, UNIT_RAW_SIZE), 0);

	zassert_equal_ptr(obj_a.obj_core.stats, obj_a.stats);
	assert_lock_released_once();
}

/**
 * @brief k_obj_core_stats_register() rejects a type without statistics and a wrong size.
 *
 * @details
 * - Setup: an object without statistics buffer.
 * - Action: k_obj_core_stats_register() for a type without descriptor.
 *   Then for a type with a descriptor, with the query size (not the raw
 *   size).
 * - Expected: -ENOTSUP, then -EINVAL. The statistics pointer stays NULL.
 *   Each call releases the lock once.
 *
 * @ingroup kernel_unit_obj_core_k_obj_core_stats_register
 * @see k_obj_core_stats_register()
 */
ZTEST(obj_core_unit, test_stats_register_rejects_request)
{
	prepare_registered(NULL);
	obj_a.obj_core.stats = NULL;

	zassert_equal(k_obj_core_stats_register(&obj_a.obj_core, obj_a.stats, UNIT_RAW_SIZE),
		      -ENOTSUP);
	zassert_is_null(obj_a.obj_core.stats);
	assert_lock_released_once();

	unit_type.stats_desc = &unit_stats_desc;
	zassert_equal(k_obj_core_stats_register(&obj_a.obj_core, obj_a.stats, UNIT_QUERY_SIZE),
		      -EINVAL);
	zassert_is_null(obj_a.obj_core.stats);
}

/**
 * @brief k_obj_core_stats_deregister() clears the statistics buffer, if the type has statistics.
 *
 * @details
 * - Setup: an object with a registered buffer.
 * - Action: k_obj_core_stats_deregister(). Then the same for a type
 *   without descriptor.
 * - Expected: return value 0 and the statistics pointer is NULL. For the
 *   type without descriptor: -ENOTSUP, and the pointer does not change.
 *   Each call releases the lock once.
 *
 * @ingroup kernel_unit_obj_core_k_obj_core_stats_deregister
 * @see k_obj_core_stats_deregister()
 */
ZTEST(obj_core_unit, test_stats_deregister_clears_buffer)
{
	prepare_registered(&unit_stats_desc);

	zassert_equal(k_obj_core_stats_deregister(&obj_a.obj_core), 0);
	zassert_is_null(obj_a.obj_core.stats);
	assert_lock_released_once();

	unit_type.stats_desc = NULL;
	obj_a.obj_core.stats = obj_a.stats;
	zassert_equal(k_obj_core_stats_deregister(&obj_a.obj_core), -ENOTSUP);
	zassert_equal_ptr(obj_a.obj_core.stats, obj_a.stats);
}

/**
 * @brief Each statistics request calls the function of the descriptor with the lock held, and
 * returns its value.
 *
 * @details
 * - Setup: an object with a registered buffer. The type has a descriptor
 *   with all functions. Each function returns its own value.
 * - Action: the raw, query, reset, disable and enable request, each with
 *   the correct buffer size.
 * - Expected: each request returns the value of its function. The function
 *   gets the object core, and the raw and the query function also get the
 *   buffer. The call history is: lock, function, release with the key.
 *
 * @ingroup kernel_unit_obj_core_k_obj_core_stats_raw
 * @see k_obj_core_stats_raw(), k_obj_core_stats_query(), k_obj_core_stats_reset(),
 * k_obj_core_stats_disable(), k_obj_core_stats_enable()
 */
ZTEST(obj_core_unit, test_stats_request_forwards_to_descriptor)
{
	prepare_registered(&unit_stats_desc);
	unit_stats_raw_fake.return_val = 11;
	unit_stats_query_fake.return_val = 12;
	unit_stats_reset_fake.return_val = 13;
	unit_stats_disable_fake.return_val = 14;
	unit_stats_enable_fake.return_val = 15;

	for (int req = 0; req < REQ_COUNT; req++) {
		forget_setup_calls();

		zassert_equal(stats_request(req, &obj_a.obj_core, request_size(req)), 11 + req,
			      "request %s", request_names[req]);
		zassert_call_history(unit_arch_irq_lock, request_fake(req), unit_arch_irq_unlock);
		zassert_equal(unit_arch_irq_unlock_fake.arg0_val, KERNEL_UNIT_IRQ_KEY);
	}

	zassert_equal_ptr(unit_stats_raw_fake.arg0_val, &obj_a.obj_core);
	zassert_equal_ptr(unit_stats_raw_fake.arg1_val, request_buf);
	zassert_equal_ptr(unit_stats_query_fake.arg0_val, &obj_a.obj_core);
	zassert_equal_ptr(unit_stats_query_fake.arg1_val, request_buf);
	zassert_equal_ptr(unit_stats_reset_fake.arg0_val, &obj_a.obj_core);
	zassert_equal_ptr(unit_stats_disable_fake.arg0_val, &obj_a.obj_core);
	zassert_equal_ptr(unit_stats_enable_fake.arg0_val, &obj_a.obj_core);
}

/**
 * @brief Each statistics request returns -ENOTSUP if the type has no descriptor.
 *
 * @details
 * - Setup: an object with a registered buffer. The type has no descriptor.
 * - Action: each request with the correct buffer size.
 * - Expected: -ENOTSUP. No descriptor function runs. Each request releases
 *   the lock once.
 *
 * @ingroup kernel_unit_obj_core_k_obj_core_stats_raw
 * @see k_obj_core_stats_raw(), k_obj_core_stats_query(), k_obj_core_stats_reset(),
 * k_obj_core_stats_disable(), k_obj_core_stats_enable()
 */
ZTEST(obj_core_unit, test_stats_request_without_descriptor)
{
	prepare_registered(NULL);

	for (int req = 0; req < REQ_COUNT; req++) {
		forget_setup_calls();

		zassert_equal(stats_request(req, &obj_a.obj_core, request_size(req)), -ENOTSUP,
			      "request %s", request_names[req]);
		assert_lock_released_once();
	}
	zassert_equal(descriptor_calls(), 0U);
}

/**
 * @brief Each statistics request returns -ENOTSUP if the descriptor has no function for it.
 *
 * @details
 * - Setup: an object with a registered buffer. The descriptor of the type
 *   has the sizes, but no functions.
 * - Action: each request with the correct buffer size.
 * - Expected: -ENOTSUP for each request.
 *
 * @ingroup kernel_unit_obj_core_k_obj_core_stats_raw
 * @see k_obj_core_stats_raw(), k_obj_core_stats_query(), k_obj_core_stats_reset(),
 * k_obj_core_stats_disable(), k_obj_core_stats_enable()
 */
ZTEST(obj_core_unit, test_stats_request_without_function)
{
	prepare_registered(&unit_stats_desc_empty);

	for (int req = 0; req < REQ_COUNT; req++) {
		zassert_equal(stats_request(req, &obj_a.obj_core, request_size(req)), -ENOTSUP,
			      "request %s", request_names[req]);
	}
}

/**
 * @brief Each statistics request returns -EINVAL if the object has no registered buffer.
 *
 * @details
 * - Setup: an object of a type with a full descriptor. The object has no
 *   statistics buffer (NULL).
 * - Action: each request with the correct buffer size.
 * - Expected: -EINVAL. No descriptor function runs.
 *
 * @ingroup kernel_unit_obj_core_k_obj_core_stats_raw
 * @see k_obj_core_stats_raw(), k_obj_core_stats_query(), k_obj_core_stats_reset(),
 * k_obj_core_stats_disable(), k_obj_core_stats_enable()
 */
ZTEST(obj_core_unit, test_stats_request_without_buffer)
{
	prepare_registered(&unit_stats_desc);
	obj_a.obj_core.stats = NULL;

	for (int req = 0; req < REQ_COUNT; req++) {
		zassert_equal(stats_request(req, &obj_a.obj_core, request_size(req)), -EINVAL,
			      "request %s", request_names[req]);
	}
	zassert_equal(descriptor_calls(), 0U);
}

/**
 * @brief The raw request compares the size with raw_size, the query request with query_size.
 *
 * @details
 * - Setup: an object with a registered buffer. The raw size and the query
 *   size of the descriptor are different.
 * - Action: the raw request with the query size, and the query request
 *   with the raw size.
 * - Expected: -EINVAL for both. No descriptor function runs.
 *
 * @ingroup kernel_unit_obj_core_k_obj_core_stats_raw
 * @see k_obj_core_stats_raw(), k_obj_core_stats_query()
 */
ZTEST(obj_core_unit, test_stats_request_rejects_wrong_size)
{
	prepare_registered(&unit_stats_desc);

	zassert_equal(stats_request(REQ_RAW, &obj_a.obj_core, UNIT_QUERY_SIZE), -EINVAL);
	zassert_equal(stats_request(REQ_QUERY, &obj_a.obj_core, UNIT_RAW_SIZE), -EINVAL);
	zassert_equal(descriptor_calls(), 0U);
}

/**
 * @brief A second k_obj_core_init() clears the statistics buffer of the object.
 *
 * @details
 * - Setup: an object with a registered buffer.
 * - Action: k_obj_core_init() for the object.
 * - Expected: the statistics pointer is NULL. A raw request returns
 *   -EINVAL. The caller of a second init must register the buffer again,
 *   as k_mem_slab_init() does.
 *
 * @ingroup kernel_unit_obj_core_k_obj_core_init
 * @see k_obj_core_init(), k_obj_core_stats_raw()
 */
ZTEST(obj_core_unit, test_stats_second_init_clears_buffer)
{
	prepare_registered(&unit_stats_desc);

	k_obj_core_init(&obj_a.obj_core, &unit_type);

	zassert_is_null(obj_a.obj_core.stats);
	zassert_equal(stats_request(REQ_RAW, &obj_a.obj_core, UNIT_RAW_SIZE), -EINVAL);
}
#endif /* CONFIG_OBJ_CORE_STATS */

/*
 * Tests: Second init of a linked object (finding F-1). Each test is in the
 * group of the function that it tests. The design text is in that group, or
 * in the introduction of the group kernel_unit_obj_core, at the top of this
 * file.
 */

/**
 * @brief A second init of the tail keeps the list without cycle.
 *
 * @details
 * - Setup: the objects a, b, c in the list. c is the tail.
 * - Action: k_obj_core_init_and_link() for c again.
 * - Expected: the next pointer of c does not point to c. The list holds a,
 *   b and c, each one time, ends with NULL, and its tail is the last node.
 *
 * @note Expected failure, finding F-1 (kernel unit bounds inventory). Today
 * the list is a -> b -> c -> c (a cycle). If this test passes, the defect is
 * fixed: remove ZTEST_EXPECT_FAIL().
 *
 * @ingroup kernel_unit_obj_core_k_obj_core_init_and_link
 * @see k_obj_core_init_and_link()
 */
ZTEST(obj_core_unit, test_reinit_of_tail_keeps_list_acyclic)
{
	link_objects((struct unit_obj *const[]){&obj_a, &obj_b, &obj_c}, 3U);

	k_obj_core_init_and_link(&obj_c.obj_core, &unit_type);

	zassert_list_holds(&unit_type.list,
			   (const sys_snode_t *const[]){NODE(obj_a), NODE(obj_b), NODE(obj_c)}, 3U,
			   node_name);
	zassert_true(obj_c.obj_core.node.next != NODE(obj_c), "c points to itself");
}
ZTEST_EXPECT_FAIL(obj_core_unit, test_reinit_of_tail_keeps_list_acyclic);

/**
 * @brief A second init of the only object keeps the list without cycle.
 *
 * @details
 * - Setup: the object a is the only object in the list.
 * - Action: k_obj_core_init_and_link() for a again.
 * - Expected: the list holds only a, one time. The next pointer of a is
 *   NULL.
 *
 * @note Expected failure, finding F-1 (kernel unit bounds inventory). Today
 * the next pointer of a points to a (a cycle). If this test passes, the
 * defect is fixed: remove ZTEST_EXPECT_FAIL().
 *
 * @ingroup kernel_unit_obj_core_k_obj_core_init_and_link
 * @see k_obj_core_init_and_link()
 */
ZTEST(obj_core_unit, test_reinit_of_only_object_keeps_list_acyclic)
{
	link_objects((struct unit_obj *const[]){&obj_a}, 1U);

	k_obj_core_init_and_link(&obj_a.obj_core, &unit_type);

	zassert_list_holds(&unit_type.list, (const sys_snode_t *const[]){NODE(obj_a)}, 1U,
			   node_name);
	zassert_is_null(obj_a.obj_core.node.next);
}
ZTEST_EXPECT_FAIL(obj_core_unit, test_reinit_of_only_object_keeps_list_acyclic);

/**
 * @brief A second init of the head keeps the other objects in the list.
 *
 * @details
 * - Setup: the objects a, b, c in the list. a is the head.
 * - Action: k_obj_core_init_and_link() for a again.
 * - Expected: the list holds a, b and c, each one time, without cycle.
 *
 * @note Expected failure, finding F-1 (kernel unit bounds inventory). Today
 * the list is only a. The tail is a. b and c are no longer in the list
 * (b -> c -> a). If this test passes, the defect is fixed: remove
 * ZTEST_EXPECT_FAIL().
 *
 * @ingroup kernel_unit_obj_core_k_obj_core_init_and_link
 * @see k_obj_core_init_and_link()
 */
ZTEST(obj_core_unit, test_reinit_of_head_keeps_other_objects)
{
	link_objects((struct unit_obj *const[]){&obj_a, &obj_b, &obj_c}, 3U);

	k_obj_core_init_and_link(&obj_a.obj_core, &unit_type);

	zassert_list_holds(&unit_type.list,
			   (const sys_snode_t *const[]){NODE(obj_a), NODE(obj_b), NODE(obj_c)}, 3U,
			   node_name);
}
ZTEST_EXPECT_FAIL(obj_core_unit, test_reinit_of_head_keeps_other_objects);

/**
 * @brief A second init of an object in the middle keeps the later objects in the list.
 *
 * @details
 * - Setup: the objects a, b, c, d in the list.
 * - Action: k_obj_core_init_and_link() for b again.
 * - Expected: the list holds a, b, c and d, each one time, without cycle.
 *
 * @note Expected failure, finding F-1 (kernel unit bounds inventory). Today
 * the list is a -> b. c and d are no longer in the list (c -> d -> b). If
 * this test passes, the defect is fixed: remove ZTEST_EXPECT_FAIL().
 *
 * @ingroup kernel_unit_obj_core_k_obj_core_init_and_link
 * @see k_obj_core_init_and_link()
 */
ZTEST(obj_core_unit, test_reinit_of_middle_keeps_later_objects)
{
	link_objects((struct unit_obj *const[]){&obj_a, &obj_b, &obj_c, &obj_d}, 4U);

	k_obj_core_init_and_link(&obj_b.obj_core, &unit_type);

	zassert_list_holds(
		&unit_type.list,
		(const sys_snode_t *const[]){NODE(obj_a), NODE(obj_b), NODE(obj_c), NODE(obj_d)},
		4U, node_name);
}
ZTEST_EXPECT_FAIL(obj_core_unit, test_reinit_of_middle_keeps_later_objects);

/**
 * @brief After a second init of the tail, k_obj_type_walk_locked() ends after each object.
 *
 * @details
 * - Setup: the objects a, b, c in the list. Then k_obj_core_init_and_link()
 *   for c again.
 * - Action: k_obj_type_walk_locked() with the walk function of the test. The
 *   function stops the walk after WALK_LIMIT calls.
 * - Expected: three calls and the return value 0.
 *
 * @note Expected failure, finding F-1 (kernel unit bounds inventory). Today
 * the walk calls the function for c again and again, with
 * @c obj_core_lock held. Only the limit of the test function ends the walk
 * (return value -ELOOP). Without this limit, the walk does not end, and
 * the interrupts of the CPU stay locked. If this test passes, the defect is
 * fixed: remove ZTEST_EXPECT_FAIL().
 *
 * @ingroup kernel_unit_obj_core_k_obj_core_init_and_link
 * @see k_obj_core_init_and_link(), k_obj_type_walk_locked()
 */
ZTEST(obj_core_unit, test_reinit_of_tail_locked_walk_ends)
{
	struct walk_log log = {0};
	int status;

	link_objects((struct unit_obj *const[]){&obj_a, &obj_b, &obj_c}, 3U);
	k_obj_core_init_and_link(&obj_c.obj_core, &unit_type);

	status = k_obj_type_walk_locked(&unit_type, walk_record, &log);

	TC_PRINT("locked walk: %zu calls, status %d\n", log.calls, status);
	zassert_equal(status, 0);
	zassert_equal(log.calls, 3U);
}
ZTEST_EXPECT_FAIL(obj_core_unit, test_reinit_of_tail_locked_walk_ends);

/**
 * @brief After a second init of the tail, k_obj_type_walk_unlocked() ends after each object.
 *
 * @details
 * - Setup: the objects a, b, c in the list. Then k_obj_core_init_and_link()
 *   for c again.
 * - Action: k_obj_type_walk_unlocked() with the walk function of the test.
 * - Expected: three calls and the return value 0.
 *
 * @note Expected failure, finding F-1 (kernel unit bounds inventory). Today
 * the walk calls the function for c until the limit of the test function
 * (return value -ELOOP). If this test passes, the defect is fixed: remove
 * ZTEST_EXPECT_FAIL().
 *
 * @ingroup kernel_unit_obj_core_k_obj_core_init_and_link
 * @see k_obj_core_init_and_link(), k_obj_type_walk_unlocked()
 */
ZTEST(obj_core_unit, test_reinit_of_tail_unlocked_walk_ends)
{
	struct walk_log log = {0};
	int status;

	link_objects((struct unit_obj *const[]){&obj_a, &obj_b, &obj_c}, 3U);
	k_obj_core_init_and_link(&obj_c.obj_core, &unit_type);

	status = k_obj_type_walk_unlocked(&unit_type, walk_record, &log);

	TC_PRINT("unlocked walk: %zu calls, status %d\n", log.calls, status);
	zassert_equal(status, 0);
	zassert_equal(log.calls, 3U);
}
ZTEST_EXPECT_FAIL(obj_core_unit, test_reinit_of_tail_unlocked_walk_ends);

/**
 * @brief After a second init of the tail, k_obj_core_unlink() removes the object.
 *
 * @details
 * - Setup: the objects a, b, c in the list. Then k_obj_core_init_and_link()
 *   for c again.
 * - Action: k_obj_core_unlink() for c.
 * - Expected: the list holds a and b, without cycle, and the tail is b.
 *   c is not in the list.
 *
 * @note Expected failure, finding F-1 (kernel unit bounds inventory). Today
 * the unlink finds c after b and sets the next pointer of b to the next
 * pointer of c, which is c. Then it sets the next pointer of c to NULL. The
 * list is a -> b -> c with the tail b: c stays in the list, and the tail is
 * not the last node. The next link appends after b and removes c from the
 * list. If this test passes, the defect is fixed: remove
 * ZTEST_EXPECT_FAIL().
 *
 * @ingroup kernel_unit_obj_core_k_obj_core_init_and_link
 * @see k_obj_core_init_and_link(), k_obj_core_unlink()
 */
ZTEST(obj_core_unit, test_unlink_after_reinit_of_tail_removes_object)
{
	link_objects((struct unit_obj *const[]){&obj_a, &obj_b, &obj_c}, 3U);
	k_obj_core_init_and_link(&obj_c.obj_core, &unit_type);

	k_obj_core_unlink(&obj_c.obj_core);

	zassert_list_holds(&unit_type.list, (const sys_snode_t *const[]){NODE(obj_a), NODE(obj_b)},
			   2U, node_name);
}
ZTEST_EXPECT_FAIL(obj_core_unit, test_unlink_after_reinit_of_tail_removes_object);

/**
 * @brief A second k_obj_core_link() of the tail, without init, keeps the list without cycle.
 *
 * @details
 * - Setup: the objects a and b in the list. b is the tail.
 * - Action: k_obj_core_link() for b again.
 * - Expected: the list holds a and b, each one time, without cycle.
 *
 * @note Expected failure, finding F-1 (kernel unit bounds inventory).
 * sys_slist_append() sets the next pointer of the node to NULL itself, so
 * also a link without init makes the cycle b -> b. k_fifo_init() and
 * k_lifo_init() (zephyr/kernel.h) use K_OBJ_CORE_INIT() and
 * K_OBJ_CORE_LINK() on each call. If this test passes, the defect is fixed:
 * remove ZTEST_EXPECT_FAIL().
 *
 * @ingroup kernel_unit_obj_core_k_obj_core_link
 * @see k_obj_core_link()
 */
ZTEST(obj_core_unit, test_second_link_of_tail_keeps_list_acyclic)
{
	link_objects((struct unit_obj *const[]){&obj_a, &obj_b}, 2U);

	k_obj_core_link(&obj_b.obj_core);

	zassert_list_holds(&unit_type.list, (const sys_snode_t *const[]){NODE(obj_a), NODE(obj_b)},
			   2U, node_name);
}
ZTEST_EXPECT_FAIL(obj_core_unit, test_second_link_of_tail_keeps_list_acyclic);

/**
 * @brief A second z_obj_type_init() of the last type keeps the type list without cycle.
 *
 * @details
 * - Setup: the types type and type2 in @c z_obj_type_list. type2 is the
 *   tail.
 * - Action: z_obj_type_init() for type2 again.
 * - Expected: the type list holds type and type2, each one time, without
 *   cycle.
 *
 * @note Expected failure, finding F-1 (kernel unit bounds inventory), the
 * same pattern on the type list. Today the type list is
 * type -> type2 -> type2. k_obj_type_find() with an unknown ID then does not
 * end, with @c obj_core_lock held. Only a second run of the boot init, or a
 * second registration by other code, does this. The socket code guards its
 * registration with a flag (socket_obj_core.c:60-68). If this test passes,
 * the defect is fixed: remove ZTEST_EXPECT_FAIL().
 *
 * @ingroup kernel_unit_obj_core_z_obj_type_init
 * @see z_obj_type_init(), k_obj_type_find()
 */
ZTEST(obj_core_unit, test_second_type_init_keeps_type_list_acyclic)
{
	(void)z_obj_type_init(&unit_type, UNIT_TYPE_A_ID, 0U);
	(void)z_obj_type_init(&unit_type2, UNIT_TYPE_B_ID, 0U);

	(void)z_obj_type_init(&unit_type2, UNIT_TYPE_B_ID, 0U);

	zassert_list_holds(&z_obj_type_list,
			   (const sys_snode_t *const[]){&unit_type.node, &unit_type2.node}, 2U,
			   node_name);
}
ZTEST_EXPECT_FAIL(obj_core_unit, test_second_type_init_keeps_type_list_acyclic);
