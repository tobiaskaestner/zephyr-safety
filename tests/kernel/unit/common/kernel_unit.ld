/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Iterable sections of the kernel objects, for the unit tests. The
 * unittest linker script (ztest_unittest.ld) has only the ztest sections.
 *
 * k_obj_core_desc: the descriptors that K_OBJ_TYPE_DEFINE() puts there.
 * k_<object>: the statically defined objects of one type (K_SEM_DEFINE(),
 * K_FIFO_DEFINE(), K_LIFO_DEFINE(), K_MSGQ_DEFINE(), K_STACK_DEFINE(),
 * K_MEM_SLAB_DEFINE(), K_EVENT_DEFINE(), K_CONDVAR_DEFINE(),
 * K_MUTEX_DEFINE()).
 * An object core descriptor points to the bounds of this section.
 */

SECTIONS
{
	.data.kernel_unit_k_obj_core_desc_area : ALIGN(8)
	{
		_k_obj_core_desc_list_start = .;
		KEEP(*(SORT_BY_NAME(._k_obj_core_desc.static.*)))
		_k_obj_core_desc_list_end = .;
	}
	.data.kernel_unit_k_sem_area : ALIGN(8)
	{
		_k_sem_list_start = .;
		KEEP(*(SORT_BY_NAME(._k_sem.static.*)))
		_k_sem_list_end = .;
	}
	.data.kernel_unit_k_fifo_area : ALIGN(8)
	{
		_k_fifo_list_start = .;
		KEEP(*(SORT_BY_NAME(._k_fifo.static.*)))
		_k_fifo_list_end = .;
	}
	.data.kernel_unit_k_lifo_area : ALIGN(8)
	{
		_k_lifo_list_start = .;
		KEEP(*(SORT_BY_NAME(._k_lifo.static.*)))
		_k_lifo_list_end = .;
	}
	.data.kernel_unit_k_msgq_area : ALIGN(8)
	{
		_k_msgq_list_start = .;
		KEEP(*(SORT_BY_NAME(._k_msgq.static.*)))
		_k_msgq_list_end = .;
	}
	.data.kernel_unit_k_stack_area : ALIGN(8)
	{
		_k_stack_list_start = .;
		KEEP(*(SORT_BY_NAME(._k_stack.static.*)))
		_k_stack_list_end = .;
	}
	.data.kernel_unit_k_mem_slab_area : ALIGN(8)
	{
		_k_mem_slab_list_start = .;
		KEEP(*(SORT_BY_NAME(._k_mem_slab.static.*)))
		_k_mem_slab_list_end = .;
	}
	.data.kernel_unit_k_event_area : ALIGN(8)
	{
		_k_event_list_start = .;
		KEEP(*(SORT_BY_NAME(._k_event.static.*)))
		_k_event_list_end = .;
	}
	.data.kernel_unit_k_condvar_area : ALIGN(8)
	{
		_k_condvar_list_start = .;
		KEEP(*(SORT_BY_NAME(._k_condvar.static.*)))
		_k_condvar_list_end = .;
	}
	.data.kernel_unit_k_mutex_area : ALIGN(8)
	{
		_k_mutex_list_start = .;
		KEEP(*(SORT_BY_NAME(._k_mutex.static.*)))
		_k_mutex_list_end = .;
	}
}
INSERT AFTER .data;

/*
 * With CONFIG_USERSPACE, ztest defines an app memory partition. Its bounds
 * come from the linker script of a real build. A unit test runs no user
 * thread, so the partition is empty.
 */
PROVIDE(z_data_smem_ztest_mem_partition_part_start = 0);
PROVIDE(z_data_smem_ztest_mem_partition_part_size = 0);
PROVIDE(z_data_smem_ztest_mem_partition_bss_start = 0);
PROVIDE(z_data_smem_ztest_mem_partition_bss_size = 0);
