/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Tests: Second init through k_sem_init(). These tests are in the groups of
 * the file group kernel_unit_obj_core (test_obj_core.c). The design text is
 * in the group kernel_unit_obj_core_k_obj_core_init_and_link.
 */

#include <string.h>
#include <zephyr/ztest.h>
#include <kernel_unit.h>
#include <kernel_unit_models.h>
#include "obj_core_list.h"

#include <kernel/sem.c>

/* The boot init of obj_core.c (defined in test_obj_core.c) */
void obj_core_unit_boot(void);

/*
 * Static semaphores. The linker sorts the section k_sem by name, so the
 * boot init links them in the order a, b, c.
 */
K_SEM_DEFINE(unit_sem_a, 0, 1);
K_SEM_DEFINE(unit_sem_b, 0, 1);
K_SEM_DEFINE(unit_sem_c, 0, 1);

/* Semaphores that only k_sem_init() initializes */
static struct k_sem dyn_sem_1;
static struct k_sem dyn_sem_2;

/* Node of a semaphore in the list of the semaphore type */
#define SEM_NODE(sem) (&(sem).obj_core.node)

/* Name of a node of the semaphore list */
static const char *sem_node_name(const sys_snode_t *node)
{
	static const struct {
		const struct k_sem *sem;
		const char *name;
	} names[] = {
		{&unit_sem_a, "unit_sem_a"}, {&unit_sem_b, "unit_sem_b"},
		{&unit_sem_c, "unit_sem_c"}, {&dyn_sem_1, "dyn_sem_1"},
		{&dyn_sem_2, "dyn_sem_2"},
	};

	for (size_t i = 0; i < ARRAY_SIZE(names); i++) {
		if (node == &names[i].sem->obj_core.node) {
			return names[i].name;
		}
	}

	return "?";
}

static void obj_core_sem_before(void *fixture)
{
	ARG_UNUSED(fixture);

	/* The fake rules reset all fakes before this function. */
	unit_arch_irq_lock_fake.return_val = KERNEL_UNIT_IRQ_KEY;

	/* Boot: register the types and link the static semaphores. */
	sys_slist_init(&z_obj_type_list);
	obj_core_unit_boot();

	memset(&dyn_sem_1, 0, sizeof(dyn_sem_1));
	memset(&dyn_sem_2, 0, sizeof(dyn_sem_2));
}

ZTEST_SUITE(obj_core_sem, NULL, NULL, obj_core_sem_before, NULL, NULL);

/**
 * @brief The boot init links the static semaphores to the semaphore type, in name order.
 *
 * @details
 * - Action: the boot init of obj_core.c (in the before function).
 * - Expected: k_obj_type_find() with K_OBJ_TYPE_SEM_ID returns
 *   @c obj_type_sem. Its list is unit_sem_a, unit_sem_b, unit_sem_c.
 *
 * @ingroup kernel_unit_obj_core_static
 * @see z_obj_core_init_all()
 */
ZTEST(obj_core_sem, test_boot_links_static_semaphores)
{
	zassert_equal_ptr(k_obj_type_find(K_OBJ_TYPE_SEM_ID), &obj_type_sem);
	zassert_list_order(&obj_type_sem.list,
			   (const sys_snode_t *const[]){SEM_NODE(unit_sem_a), SEM_NODE(unit_sem_b),
							SEM_NODE(unit_sem_c)},
			   3U, sem_node_name);
}

/**
 * @brief k_sem_init() appends a new semaphore to the list of the semaphore type.
 *
 * @details
 * - Action: z_impl_k_sem_init() for dyn_sem_1.
 * - Expected: return value 0. The list is unit_sem_a, unit_sem_b,
 *   unit_sem_c, dyn_sem_1.
 *
 * @ingroup kernel_unit_obj_core_k_obj_core_init_and_link
 * @see k_obj_core_init_and_link()
 * @see z_impl_k_sem_init()
 */
ZTEST(obj_core_sem, test_sem_init_links_new_semaphore)
{
	zassert_equal(z_impl_k_sem_init(&dyn_sem_1, 0U, 1U), 0);

	zassert_list_order(&obj_type_sem.list,
			   (const sys_snode_t *const[]){SEM_NODE(unit_sem_a), SEM_NODE(unit_sem_b),
							SEM_NODE(unit_sem_c), SEM_NODE(dyn_sem_1)},
			   4U, sem_node_name);
}

/**
 * @brief A second k_sem_init() of the last semaphore keeps the list without cycle.
 *
 * @details
 * - Setup: z_impl_k_sem_init() for dyn_sem_1. dyn_sem_1 is the tail.
 * - Action: z_impl_k_sem_init() for dyn_sem_1 again.
 * - Expected: return value 0. The list holds the four semaphores, each one
 *   time, without cycle.
 *
 * @note Expected failure, finding F-1 (kernel unit bounds inventory). Today
 * the next pointer of dyn_sem_1 points to dyn_sem_1. A walk of the
 * semaphore type does not end. If this test passes, the defect is fixed:
 * remove ZTEST_EXPECT_FAIL().
 *
 * @ingroup kernel_unit_obj_core_k_obj_core_init_and_link
 * @see k_obj_core_init_and_link()
 * @see z_impl_k_sem_init()
 */
ZTEST(obj_core_sem, test_sem_init_twice_keeps_list_acyclic)
{
	zassert_equal(z_impl_k_sem_init(&dyn_sem_1, 0U, 1U), 0);

	zassert_equal(z_impl_k_sem_init(&dyn_sem_1, 1U, 1U), 0);

	zassert_list_holds(&obj_type_sem.list,
			   (const sys_snode_t *const[]){SEM_NODE(unit_sem_a), SEM_NODE(unit_sem_b),
							SEM_NODE(unit_sem_c), SEM_NODE(dyn_sem_1)},
			   4U, sem_node_name);
}
ZTEST_EXPECT_FAIL(obj_core_sem, test_sem_init_twice_keeps_list_acyclic);

/**
 * @brief k_sem_init() of a static semaphore keeps the other semaphores in the list.
 *
 * @details
 * - Setup: the boot init linked unit_sem_a, unit_sem_b and unit_sem_c.
 *   Then z_impl_k_sem_init() for dyn_sem_1.
 * - Action: z_impl_k_sem_init() for unit_sem_a (the head).
 * - Expected: the list holds the four semaphores, each one time, without
 *   cycle.
 *
 * @note Expected failure, finding F-1 (kernel unit bounds inventory). An
 * application that defines a semaphore with K_SEM_DEFINE() and later calls
 * k_sem_init() on it does a second link. Today the list is only
 * unit_sem_a: the other three semaphores are no longer in the list, also
 * dyn_sem_1, which is not involved. If this test passes, the defect is fixed:
 * remove ZTEST_EXPECT_FAIL().
 *
 * @ingroup kernel_unit_obj_core_k_obj_core_init_and_link
 * @see k_obj_core_init_and_link()
 * @see z_impl_k_sem_init()
 */
ZTEST(obj_core_sem, test_sem_init_of_static_semaphore_keeps_others)
{
	zassert_equal(z_impl_k_sem_init(&dyn_sem_1, 0U, 1U), 0);

	zassert_equal(z_impl_k_sem_init(&unit_sem_a, 0U, 1U), 0);

	zassert_list_holds(&obj_type_sem.list,
			   (const sys_snode_t *const[]){SEM_NODE(unit_sem_a), SEM_NODE(unit_sem_b),
							SEM_NODE(unit_sem_c), SEM_NODE(dyn_sem_1)},
			   4U, sem_node_name);
}
ZTEST_EXPECT_FAIL(obj_core_sem, test_sem_init_of_static_semaphore_keeps_others);

/**
 * @brief A k_sem_init() that fails its argument check does not change the list.
 *
 * @details
 * - Setup: z_impl_k_sem_init() for dyn_sem_1.
 * - Action: z_impl_k_sem_init() for dyn_sem_1 with the limit 0.
 * - Expected: with the runtime checks (default), the return value is
 *   -EINVAL and the list is unchanged. sem.c checks the arguments before
 *   the link.
 *
 * @ingroup kernel_unit_obj_core_k_obj_core_init_and_link
 * @see k_obj_core_init_and_link()
 * @see z_impl_k_sem_init()
 */
ZTEST(obj_core_sem, test_sem_init_with_bad_limit_does_not_link)
{
	if (!IS_ENABLED(CONFIG_RUNTIME_ERROR_CHECKS)) {
		ztest_test_skip();
	}

	zassert_equal(z_impl_k_sem_init(&dyn_sem_1, 0U, 1U), 0);

	zassert_equal(z_impl_k_sem_init(&dyn_sem_1, 0U, 0U), -EINVAL);

	zassert_list_order(&obj_type_sem.list,
			   (const sys_snode_t *const[]){SEM_NODE(unit_sem_a), SEM_NODE(unit_sem_b),
							SEM_NODE(unit_sem_c), SEM_NODE(dyn_sem_1)},
			   4U, sem_node_name);
}

#ifdef CONFIG_USERSPACE
/**
 * @brief With CONFIG_USERSPACE, z_vrfy_k_sem_init() accepts a semaphore that is already
 * initialized.
 *
 * @details
 * - Setup: the object checks pass.
 * - Action: z_vrfy_k_sem_init() for dyn_sem_1.
 * - Expected: return value 0. The object check has the type K_OBJ_SEM and
 *   the init check @c _OBJ_INIT_ANY. Thus a user thread with access to a
 *   semaphore can init it again, as often as it wants.
 *
 * @ingroup kernel_unit_obj_core_k_obj_core_init_and_link
 * @see k_obj_core_init_and_link()
 * @see z_vrfy_k_sem_init()
 */
ZTEST(obj_core_sem, test_user_sem_init_accepts_initialized_semaphore)
{
	kernel_unit_pass_object_check();

	zassert_equal(z_vrfy_k_sem_init(&dyn_sem_1, 0U, 1U), 0);

	kernel_unit_assert_object_check(&dyn_sem_1, K_OBJ_SEM, _OBJ_INIT_ANY);
}

/**
 * @brief With CONFIG_USERSPACE, a second z_vrfy_k_sem_init() keeps the list without cycle.
 *
 * @details
 * - Setup: the object checks pass. z_vrfy_k_sem_init() for dyn_sem_1, then
 *   for dyn_sem_2.
 * - Action: z_vrfy_k_sem_init() for dyn_sem_2 again, as a user thread does.
 * - Expected: the list holds the five semaphores, each one time, without
 *   cycle.
 *
 * @note Expected failure, finding F-1 (kernel unit bounds inventory). Today
 * the next pointer of dyn_sem_2 points to dyn_sem_2. A user thread can thus
 * make the next walk of the semaphore type run without end, with
 * interrupts locked. If this test passes, the defect is fixed: remove
 * ZTEST_EXPECT_FAIL().
 *
 * @ingroup kernel_unit_obj_core_k_obj_core_init_and_link
 * @see k_obj_core_init_and_link()
 * @see z_vrfy_k_sem_init()
 */
ZTEST(obj_core_sem, test_user_sem_init_twice_keeps_list_acyclic)
{
	kernel_unit_pass_object_check();
	zassert_equal(z_vrfy_k_sem_init(&dyn_sem_1, 0U, 1U), 0);
	zassert_equal(z_vrfy_k_sem_init(&dyn_sem_2, 0U, 1U), 0);

	zassert_equal(z_vrfy_k_sem_init(&dyn_sem_2, 0U, 1U), 0);

	zassert_list_holds(&obj_type_sem.list,
			   (const sys_snode_t *const[]){SEM_NODE(unit_sem_a), SEM_NODE(unit_sem_b),
							SEM_NODE(unit_sem_c), SEM_NODE(dyn_sem_1),
							SEM_NODE(dyn_sem_2)},
			   5U, sem_node_name);
}
ZTEST_EXPECT_FAIL(obj_core_sem, test_user_sem_init_twice_keeps_list_acyclic);
#endif /* CONFIG_USERSPACE */
