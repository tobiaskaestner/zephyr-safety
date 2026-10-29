/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Shadow of kernel/include/wait_q.h.
 *
 * In the real header the wait queue helpers are static inline. Here each
 * one is an FFF fake, so a unit test sees how the unit uses its wait queue.
 *
 * The walk macros stay real (copies of the real header): they only read the
 * list or the tree of a _wait_q_t. kernel/scheduler.c walks a wait queue
 * with them (z_sched_waitq_walk()).
 */

#ifndef ZEPHYR_KERNEL_INCLUDE_WAIT_Q_H_
#define ZEPHYR_KERNEL_INCLUDE_WAIT_Q_H_

#include <zephyr/kernel_structs.h>
#include <zephyr/sys/dlist.h>
#include <zephyr/sys/rb.h>
#include <zephyr/fff.h>

#ifdef __cplusplus
extern "C" {
#endif

#ifdef CONFIG_WAITQ_SCALABLE
/* KERNEL_UNIT_REAL_COPY_BEGIN kernel/include/wait_q.h */
#define _WAIT_Q_FOR_EACH(wq, thread_ptr) \
	RB_FOR_EACH_CONTAINER(&(wq)->waitq.tree, thread_ptr, base.qnode_rb)
/* KERNEL_UNIT_REAL_COPY_END */
#else
/* KERNEL_UNIT_REAL_COPY_BEGIN kernel/include/wait_q.h */
#define _WAIT_Q_FOR_EACH(wq, thread_ptr) \
	SYS_DLIST_FOR_EACH_CONTAINER(&((wq)->waitq), thread_ptr, \
				     base.qnode_dlist)
/* KERNEL_UNIT_REAL_COPY_END */

/* KERNEL_UNIT_REAL_COPY_BEGIN kernel/include/wait_q.h */
#define _WAIT_Q_FOR_EACH_SAFE(wq, thread_ptr, loop_ptr) \
	SYS_DLIST_FOR_EACH_CONTAINER_SAFE(&((wq)->waitq), thread_ptr, \
					  loop_ptr, base.qnode_dlist)
/* KERNEL_UNIT_REAL_COPY_END */
#endif /* CONFIG_WAITQ_SCALABLE */

#define WAIT_Q_FFF_FAKES_LIST(FAKE)                                                                \
	FAKE(z_waitq_init)                                                                         \
	FAKE(z_waitq_head)                                                                         \
	FAKE(z_waitq_head_locked)

DECLARE_FAKE_VOID_FUNC(z_waitq_init, _wait_q_t *);
DECLARE_FAKE_VALUE_FUNC(struct k_thread *, z_waitq_head, _wait_q_t *);
DECLARE_FAKE_VALUE_FUNC(struct k_thread *, z_waitq_head_locked, _wait_q_t *);

#ifdef __cplusplus
}
#endif

#endif /* ZEPHYR_KERNEL_INCLUDE_WAIT_Q_H_ */
