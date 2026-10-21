/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Bounded checks of a singly linked list (sys_slist_t), for the object core
 * tests.
 *
 * A second init of a linked object can make a cycle in the list of its
 * type (finding F-1). A walk of such a list does not end. Thus the tests
 * do not examine a list with SYS_SLIST_FOR_EACH_NODE(). They use
 * list_shape_get(), which stops after LIST_SHAPE_MAX nodes or at the first
 * node that it found before.
 *
 * Both test sources of the application include this header. All functions
 * are static inline.
 */

#ifndef KERNEL_UNIT_OBJ_CORE_LIST_H_
#define KERNEL_UNIT_OBJ_CORE_LIST_H_

#include <stdbool.h>
#include <stddef.h>
#include <string.h>
#include <zephyr/ztest.h>
#include <zephyr/sys/slist.h>

/* Maximum number of nodes that list_shape_get() follows */
#define LIST_SHAPE_MAX 16U

/* Name of a node in the printed list, given by the test source */
typedef const char *(*list_node_name_t)(const sys_snode_t *node);

/* The nodes that a walk from the head of a list reaches */
struct list_shape {
	/* The distinct nodes, in the order of the walk */
	const sys_snode_t *nodes[LIST_SHAPE_MAX];
	/* Number of entries in nodes */
	size_t count;
	/* True if a node points back to a node of nodes: the list has a cycle */
	bool cycle;
	/* The last node before the cycle (its next pointer goes back) */
	const sys_snode_t *cycle_from;
	/* True if the walk got to NULL */
	bool ended;
	/* The tail pointer of the list */
	const sys_snode_t *tail;
};

/* Walk the list from its head. Stop at NULL, at a repeated node or after LIST_SHAPE_MAX nodes. */
static inline void list_shape_get(const sys_slist_t *list, struct list_shape *shape)
{
	const sys_snode_t *node = sys_slist_peek_head(list);

	memset(shape, 0, sizeof(*shape));
	shape->tail = sys_slist_peek_tail(list);

	while ((node != NULL) && (shape->count < LIST_SHAPE_MAX)) {
		for (size_t i = 0; i < shape->count; i++) {
			if (shape->nodes[i] == node) {
				shape->cycle = true;
				shape->cycle_from = shape->nodes[shape->count - 1U];
				return;
			}
		}
		shape->nodes[shape->count] = node;
		shape->count++;
		node = sys_slist_peek_next_no_check(node);
	}

	shape->ended = (node == NULL);
}

/* Return the number of times that the walk reached the node: 0 or 1. */
static inline size_t list_shape_find(const struct list_shape *shape, const sys_snode_t *node)
{
	size_t found = 0U;

	for (size_t i = 0; i < shape->count; i++) {
		if (shape->nodes[i] == node) {
			found++;
		}
	}

	return found;
}

/* Print the nodes of a walk, the cycle and the tail. */
static inline void list_shape_print(const char *what, const struct list_shape *shape,
				    list_node_name_t name_of)
{
	TC_PRINT("%s: head", what);
	for (size_t i = 0; i < shape->count; i++) {
		TC_PRINT(" -> %s", name_of(shape->nodes[i]));
	}
	if (shape->cycle) {
		TC_PRINT(" -> (back to %s)",
			 name_of(sys_slist_peek_next_no_check(shape->cycle_from)));
	} else if (shape->ended) {
		TC_PRINT(" -> NULL");
	} else {
		TC_PRINT(" -> (more than %u nodes)", LIST_SHAPE_MAX);
	}
	TC_PRINT(", tail %s\n", (shape->tail == NULL) ? "NULL" : name_of(shape->tail));
}

/*
 * Assert that the list holds exactly the n nodes of expected, each one
 * time, in any order. The list has no cycle, it ends with NULL, and its
 * tail is the last node.
 */
static inline void zassert_list_holds(const sys_slist_t *list, const sys_snode_t *const *expected,
				      size_t n, list_node_name_t name_of)
{
	struct list_shape shape;

	list_shape_get(list, &shape);
	list_shape_print("list", &shape, name_of);

	zassert_false(shape.cycle, "the list has a cycle: %s points back to %s",
		      shape.cycle ? name_of(shape.cycle_from) : "-",
		      shape.cycle ? name_of(sys_slist_peek_next_no_check(shape.cycle_from)) : "-");
	zassert_true(shape.ended, "the list has more than %u nodes", LIST_SHAPE_MAX);
	for (size_t i = 0; i < n; i++) {
		zassert_equal(list_shape_find(&shape, expected[i]), 1U,
			      "%s is not in the list (lost)", name_of(expected[i]));
	}
	zassert_equal(shape.count, n, "the list has %zu nodes, expected %zu", shape.count, n);
	if (n == 0U) {
		zassert_is_null(shape.tail, "the tail of an empty list is not NULL");
	} else {
		zassert_equal_ptr(shape.tail, shape.nodes[n - 1U], "the tail %s is not the last node",
				  (shape.tail == NULL) ? "NULL" : name_of(shape.tail));
	}
}

/* Assert that the list holds exactly the n nodes of expected, in this order. */
static inline void zassert_list_order(const sys_slist_t *list, const sys_snode_t *const *expected,
				      size_t n, list_node_name_t name_of)
{
	struct list_shape shape;

	zassert_list_holds(list, expected, n, name_of);

	list_shape_get(list, &shape);
	for (size_t i = 0; i < n; i++) {
		zassert_equal_ptr(shape.nodes[i], expected[i], "node %zu is %s, expected %s", i,
				  name_of(shape.nodes[i]), name_of(expected[i]));
	}
}

#endif /* KERNEL_UNIT_OBJ_CORE_LIST_H_ */
