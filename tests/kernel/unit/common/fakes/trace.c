/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Fake group trace: the trace hook of the unit tests (kernel_unit_trace.h).
 * It needs the groups sched, arch and kernel_internal. With the group
 * sched_ref, it also reads the state of the reference fake for the first
 * line of a test.
 *
 * The hook writes each line to the standard output with the prefix
 * "KTRACE ". Twister keeps the output in handler.log. The script
 * spec/tla/tools/check_traces.py cuts it into one file for each test.
 */

#include <stdio.h>
#include <string.h>
#include <zephyr/ztest.h>
#include <zephyr/kernel.h>
#include <ksched.h>
#include <wait_q.h>
#include <kernel_internal.h>
#include <kernel_arch_interface.h>
#include <kernel_unit_trace.h>
#ifdef KERNEL_UNIT_FAKE_GROUP_sched_ref
#include <kernel_unit_sched_ref.h>
#endif

#define TRACE_MAX_OBJS 4
#define TRACE_MAX_DEPTH 4
#define TRACE_PREFIX "KTRACE "

/* The objects of the test, in the order of their first API call: s1, s2, ... */
static struct kernel_unit_trace_obj objs[TRACE_MAX_OBJS];
/* True if the object has a value: it was ready before its first call, or an init returned 0. */
static bool objs_init[TRACE_MAX_OBJS];
static size_t n_objs;

/* The API calls that run now (an action of the environment runs inside a wait). */
struct api_call {
	const char *op;
	int obj;
	const void *lock;
	char actor[8];
};
static struct api_call stack[TRACE_MAX_DEPTH];
static size_t depth;

/* The waits that run now: the actor and the object of each z_pend_curr(). */
struct wait {
	char actor[8];
	int obj;
};
static struct wait waits[TRACE_MAX_DEPTH];
static size_t n_waits;

/* The key of the last lock (arch_irq_lock() of k_spin_lock()). */
static unsigned int lock_key;
static bool lock_key_known;

/* The line of the last call, written at the next line (its return value is known then). */
struct pending {
	bool used;
	const char *fn;
	int obj;
	int arg;
	unsigned int res;
	bool has_res;
	/* The fake and its call number, for the return value. */
	fff_function_t fake;
	unsigned int call;
	char thread[8];
	const char *bad;
	int data;
};
static struct pending pending;

static bool started;
static bool stopped;
static bool setup_done;

static void line(const char *json)
{
	printf(TRACE_PREFIX "%s\n", json);
}

static const char *obj_id(int k, char *buf, size_t size)
{
	if (k < 0) {
		return "none";
	}
	snprintf(buf, size, "s%d", k + 1);
	return buf;
}

/* The object with this wait queue (or poll events, or object), or -1. */
static int obj_of_wait_q(const void *wait_q)
{
	for (size_t k = 0; k < n_objs; k++) {
		if (objs[k].wait_q == wait_q) {
			return (int)k;
		}
	}
	return -1;
}

static int obj_of_poll(const void *events)
{
	for (size_t k = 0; k < n_objs; k++) {
		if ((objs[k].poll_events != NULL) && (objs[k].poll_events == events)) {
			return (int)k;
		}
	}
	return -1;
}

static int obj_index(const void *obj)
{
	for (size_t k = 0; k < n_objs; k++) {
		if (objs[k].obj == obj) {
			return (int)k;
		}
	}
	return -1;
}

static unsigned int count_of(int k)
{
	return ((k >= 0) && (objs[k].count != NULL)) ? *objs[k].count : 0U;
}

/* The name of a thread in the trace: t1, t2, ... by the index in the reference fake. */
static void thread_name(const struct k_thread *thread, char *buf, size_t size)
{
#ifdef KERNEL_UNIT_FAKE_GROUP_sched_ref
	if (kernel_unit_sched_ref.installed) {
		if (thread == NULL) {
			snprintf(buf, size, "idle");
			return;
		}
		for (size_t i = 0; i < kernel_unit_sched_ref.n_threads; i++) {
			if (kernel_unit_sched_ref.threads[i].thread == thread) {
				snprintf(buf, size, "t%zu", i + 1);
				return;
			}
		}
		snprintf(buf, size, "unknown");
		return;
	}
#endif
	ARG_UNUSED(thread);
	/* Without the reference fake, the test is the thread t1. */
	snprintf(buf, size, "t1");
}

static void actor_name(char *buf, size_t size)
{
	if (kernel_unit_context_is_isr()) {
		snprintf(buf, size, "i1");
	} else {
		thread_name(_current, buf, size);
	}
}

/* The return value of call number n (1 is the first) of a value fake. */
#define RET_OF(fake, n)                                                                            \
	((((n) >= 1U) && ((n) <= FFF_ARG_HISTORY_LEN)) ? (int)fake##_fake.return_val_history[(n) - 1U] \
							: -1000)

static void flush(void)
{
	char buf[256];
	char ob[8];
	int ret = 0;
	int n;

	if (!pending.used) {
		return;
	}
	pending.used = false;
	if (pending.fake == (fff_function_t)z_sched_wake) {
		ret = RET_OF(z_sched_wake, pending.call);
	} else if (pending.fake == (fff_function_t)z_handle_obj_poll_events) {
		ret = RET_OF(z_handle_obj_poll_events, pending.call);
	} else if (pending.fake == (fff_function_t)unit_arch_irq_lock) {
		lock_key = (unsigned int)RET_OF(unit_arch_irq_lock, pending.call);
		lock_key_known = true;
	} else {
		/* A function without a return value, or z_pend_curr() (see pend_ret). */
	}

	n = snprintf(buf, sizeof(buf),
		     "{\"ev\":\"fake\",\"fn\":\"%s\",\"obj\":\"%s\",\"arg\":%d,\"ret\":%d,\"res\":%u",
		     pending.fn, obj_id(pending.obj, ob, sizeof(ob)), pending.arg, ret,
		     pending.res);
	if (pending.thread[0] != '\0') {
		n += snprintf(buf + n, sizeof(buf) - n, ",\"thread\":\"%s\"", pending.thread);
	}
	if (pending.data != 0) {
		n += snprintf(buf + n, sizeof(buf) - n, ",\"data\":%d", pending.data);
	}
	if (pending.bad != NULL) {
		n += snprintf(buf + n, sizeof(buf) - n, ",\"bad\":\"%s\"", pending.bad);
	}
	snprintf(buf + n, sizeof(buf) - n, "}");
	line(buf);
}

static int timeout_arg(k_timeout_t t)
{
	if (K_TIMEOUT_EQ(t, K_FOREVER)) {
		return -1;
	}
	return K_TIMEOUT_EQ(t, K_NO_WAIT) ? 0 : 1;
}

static void check_key(unsigned int key)
{
	if (!lock_key_known || (key != lock_key)) {
		pending.bad = "release with another key";
	}
}

static void check_lock(const void *lock)
{
	if ((depth == 0U) || (lock != stack[depth - 1U].lock)) {
		pending.bad = "release of another lock";
	}
}

void kernel_unit_trace_call(fff_function_t fn)
{
	int cur_obj;

	if (!started || stopped || (depth == 0U)) {
		/* A call of the test itself, not of the unit. */
		return;
	}
	if (fn == (fff_function_t)arch_is_in_isr) {
		/* A query of the context (the assertion of k_sem_take()). */
		return;
	}
	flush();
	cur_obj = stack[depth - 1U].obj;
	pending = (struct pending){.used = true, .obj = cur_obj, .fake = fn,
				   .res = count_of(cur_obj)};

	if (fn == (fff_function_t)unit_arch_irq_lock) {
		pending.fn = "arch_irq_lock";
		pending.call = unit_arch_irq_lock_fake.call_count;
	} else if (fn == (fff_function_t)unit_arch_irq_unlock) {
		pending.fn = "arch_irq_unlock";
		check_key(unit_arch_irq_unlock_fake.arg0_val);
	} else if (fn == (fff_function_t)z_reschedule) {
		pending.fn = "z_reschedule";
		check_lock(z_reschedule_fake.arg0_val);
		check_key((unsigned int)z_reschedule_fake.arg1_val.key);
	} else if (fn == (fff_function_t)z_pend_curr) {
		pending.fn = "z_pend_curr";
		check_lock(z_pend_curr_fake.arg0_val);
		check_key((unsigned int)z_pend_curr_fake.arg1_val.key);
		pending.obj = obj_of_wait_q(z_pend_curr_fake.arg2_val);
		pending.arg = timeout_arg(z_pend_curr_fake.arg3_val);
		if (n_waits < TRACE_MAX_DEPTH) {
			actor_name(waits[n_waits].actor, sizeof(waits[n_waits].actor));
			waits[n_waits].obj = pending.obj;
			n_waits++;
		}
	} else if (fn == (fff_function_t)z_sched_wake) {
		pending.fn = "z_sched_wake";
		pending.call = z_sched_wake_fake.call_count;
		pending.obj = obj_of_wait_q(z_sched_wake_fake.arg0_val);
		pending.arg = z_sched_wake_fake.arg1_val;
		pending.data = (z_sched_wake_fake.arg2_val != NULL) ? 1 : 0;
	} else if (fn == (fff_function_t)z_handle_obj_poll_events) {
		pending.fn = "z_handle_obj_poll_events";
		pending.call = z_handle_obj_poll_events_fake.call_count;
		pending.obj = obj_of_poll(z_handle_obj_poll_events_fake.arg0_val);
		pending.arg = (int)z_handle_obj_poll_events_fake.arg1_val;
	} else if (fn == (fff_function_t)z_waitq_init) {
		pending.fn = "z_waitq_init";
		pending.obj = obj_of_wait_q(z_waitq_init_fake.arg0_val);
	} else {
		pending.fn = "unknown";
	}
	if ((pending.obj != cur_obj) && (pending.bad == NULL)) {
		pending.bad = "a call on another object";
	}
	if (pending.obj >= 0) {
		pending.res = count_of(pending.obj);
	}
}

void kernel_unit_trace_pend_return(int ret)
{
	char buf[160];
	char ob[8];

	if (!started || stopped || (n_waits == 0U)) {
		return;
	}
	flush();
	n_waits--;
	snprintf(buf, sizeof(buf), "{\"ev\":\"pend_ret\",\"actor\":\"%s\",\"obj\":\"%s\",\"ret\":%d}",
		 waits[n_waits].actor, obj_id(waits[n_waits].obj, ob, sizeof(ob)), ret);
	line(buf);
}

void kernel_unit_trace_pend_refused(void)
{
	if (!started || stopped) {
		return;
	}
	flush();
	line("{\"ev\":\"panic\",\"cause\":\"pend_in_isr\"}");
	/* The real system stops here. The fake returns: the rest is not a behavior. */
	stopped = true;
}

#ifdef KERNEL_UNIT_FAKE_GROUP_sched_ref
static const char *state_name(enum kernel_unit_sched_ref_tstate s)
{
	switch (s) {
	case KERNEL_UNIT_SCHED_REF_READY:
		return "ready";
	case KERNEL_UNIT_SCHED_REF_PENDING:
		return "pending";
	case KERNEL_UNIT_SCHED_REF_DEAD:
		return "dead";
	default:
		return "unpended";
	}
}

/* The setup of the reference fake: the threads, the current thread, the armed timeouts. */
static void setup_ref(void)
{
	const struct kernel_unit_sched_ref *ref = &kernel_unit_sched_ref;
	char buf[1024];
	char name[8];
	char ob[8];
	int n;

	thread_name(_current, name, sizeof(name));
	n = snprintf(buf, sizeof(buf), "{\"ev\":\"setup\",\"ref\":true,\"current\":\"%s\","
				       "\"preempt_ok\":%s,\"threads\":[",
		     name, ref->preempt_ok ? "true" : "false");
	for (size_t i = 0; i < ref->n_threads; i++) {
		const struct kernel_unit_sched_ref_thread *t = &ref->threads[i];

		n += snprintf(buf + n, sizeof(buf) - n,
			      "%s{\"id\":\"t%zu\",\"prio\":%d,\"state\":\"%s\",\"on\":\"%s\","
			      "\"stamp\":%u,\"ready_seq\":%u,\"armed\":%s,\"deadline\":%lld,"
			      "\"armed_seq\":%u,\"ret\":%d}",
			      (i == 0U) ? "" : ",", i + 1U, t->thread->base.prio,
			      state_name(t->state),
			      obj_id(obj_of_wait_q(t->thread->base.pended_on), ob, sizeof(ob)),
			      t->stamp, t->ready_seq, t->armed ? "true" : "false",
			      (long long)t->deadline, t->armed_seq,
			      t->has_ret ? t->ret : 1);
	}
	snprintf(buf + n, sizeof(buf) - n, "]}");
	line(buf);
}

void kernel_unit_trace_sched_ref(const struct kernel_unit_sched_ref_record *rec)
{
	char buf[128];
	char name[8];

	if (!started || stopped) {
		return;
	}
	if ((strcmp(rec->op, "WakeFirst") == 0) && pending.used &&
	    (pending.fake == (fff_function_t)z_sched_wake) && (rec->thread != NULL)) {
		thread_name(rec->thread, pending.thread, sizeof(pending.thread));
	} else if ((strcmp(rec->op, "ThreadTimeout") == 0) || (strcmp(rec->op, "Abort") == 0)) {
		flush();
		thread_name(rec->thread, name, sizeof(name));
		snprintf(buf, sizeof(buf), "{\"ev\":\"env\",\"op\":\"%s\",\"thread\":\"%s\"}", rec->op,
			 name);
		line(buf);
	} else {
		/* The other records are steps of the calls that the trace has. */
	}
}
#else
void kernel_unit_trace_sched_ref(const struct kernel_unit_sched_ref_record *rec)
{
	ARG_UNUSED(rec);
}
#endif /* KERNEL_UNIT_FAKE_GROUP_sched_ref */

static bool ref_installed(void)
{
#ifdef KERNEL_UNIT_FAKE_GROUP_sched_ref
	return kernel_unit_sched_ref.installed;
#else
	return false;
#endif
}

void kernel_unit_trace_api_enter(const char *op, const struct kernel_unit_trace_obj *o,
				 const void *lock, const char *timeout, const unsigned int *args,
				 size_t n_args)
{
	char buf[256];
	char name[8];
	char ob[8];
	int k;
	int n;

	if (!started || stopped) {
		return;
	}
	flush();
	k = obj_index(o->obj);
	if ((k < 0) && (n_objs < TRACE_MAX_OBJS)) {
		k = (int)n_objs;
		objs_init[n_objs] = (strcmp(op, "init") != 0);
		objs[n_objs++] = *o;
		/* The state of the object at its first call. Before an init, the memory has no value. */
		if (strcmp(op, "init") == 0) {
			snprintf(buf, sizeof(buf), "{\"ev\":\"sem\",\"id\":\"%s\",\"init\":false}",
				 obj_id(k, ob, sizeof(ob)));
		} else {
			snprintf(buf, sizeof(buf),
				 "{\"ev\":\"sem\",\"id\":\"%s\",\"init\":true,\"count\":%u,"
				 "\"limit\":%u}",
				 obj_id(k, ob, sizeof(ob)), (o->count != NULL) ? *o->count : 0U,
				 (o->limit != NULL) ? *o->limit : 0U);
		}
		line(buf);
	}
	if (!setup_done) {
		/* The state of the scheduler before the first call of the test. */
		setup_done = true;
#ifdef KERNEL_UNIT_FAKE_GROUP_sched_ref
		if (ref_installed()) {
			setup_ref();
		} else {
			line("{\"ev\":\"setup\",\"ref\":false}");
		}
#else
		line("{\"ev\":\"setup\",\"ref\":false}");
#endif
	}
	actor_name(name, sizeof(name));
	n = snprintf(buf, sizeof(buf), "{\"ev\":\"call\",\"op\":\"%s\",\"actor\":\"%s\",\"obj\":\"%s\"",
		     op, name, obj_id(k, ob, sizeof(ob)));
	if (timeout != NULL) {
		n += snprintf(buf + n, sizeof(buf) - n, ",\"timeout\":\"%s\"", timeout);
	}
	if (args != NULL) {
		n += snprintf(buf + n, sizeof(buf) - n, ",\"args\":[");
		for (size_t i = 0; i < n_args; i++) {
			n += snprintf(buf + n, sizeof(buf) - n, "%s%u", (i == 0U) ? "" : ",", args[i]);
		}
		n += snprintf(buf + n, sizeof(buf) - n, "]");
	}
	snprintf(buf + n, sizeof(buf) - n, "}");
	line(buf);
	if (depth < TRACE_MAX_DEPTH) {
		stack[depth] = (struct api_call){.op = op, .obj = k, .lock = lock};
		memcpy(stack[depth].actor, name, sizeof(stack[depth].actor));
		depth++;
	}
}

void kernel_unit_trace_api_exit(const char *op, const void *obj, bool has_ret, int ret)
{
	char buf[200];
	char name[8];
	char ob[8];
	int k = obj_index(obj);

	if (!started || stopped) {
		return;
	}
	flush();
	if (depth > 0U) {
		/* The actor of the call: the thread or the ISR that started it. */
		depth--;
		memcpy(name, stack[depth].actor, sizeof(name));
	} else {
		actor_name(name, sizeof(name));
	}
	if ((k >= 0) && (strcmp(op, "init") == 0) && has_ret && (ret == 0)) {
		objs_init[k] = true;
	}
	if ((k >= 0) && objs_init[k]) {
		snprintf(buf, sizeof(buf),
			 "{\"ev\":\"ret\",\"op\":\"%s\",\"actor\":\"%s\",\"obj\":\"%s\","
			 "\"ret\":%d,\"count\":%u,\"limit\":%u}",
			 op, name, obj_id(k, ob, sizeof(ob)), has_ret ? ret : 1, count_of(k),
			 (objs[k].limit != NULL) ? *objs[k].limit : 0U);
	} else {
		/* The memory of an object that no init initialized has no value. */
		snprintf(buf, sizeof(buf),
			 "{\"ev\":\"ret\",\"op\":\"%s\",\"actor\":\"%s\",\"obj\":\"%s\","
			 "\"ret\":%d}",
			 op, name, obj_id(k, ob, sizeof(ob)), has_ret ? ret : 1);
	}
	line(buf);
}

static void trace_before(const struct ztest_unit_test *test, void *fixture)
{
	char buf[256];

	ARG_UNUSED(fixture);

	n_objs = 0U;
	depth = 0U;
	n_waits = 0U;
	lock_key_known = false;
	pending.used = false;
	stopped = false;
	setup_done = false;
	started = true;
	snprintf(buf, sizeof(buf),
		 "{\"ev\":\"test\",\"suite\":\"%s\",\"name\":\"%s\",\"config\":{\"poll\":%s,"
		 "\"rtc\":%s,\"assert\":%s}}",
		 test->test_suite_name, test->name, IS_ENABLED(CONFIG_POLL) ? "true" : "false",
		 IS_ENABLED(CONFIG_NO_RUNTIME_CHECKS) ? "false" : "true",
		 IS_ENABLED(CONFIG_ASSERT) ? "true" : "false");
	line(buf);
}

static void trace_after(const struct ztest_unit_test *test, void *fixture)
{
	ARG_UNUSED(test);
	ARG_UNUSED(fixture);

	if (!stopped) {
		flush();
	}
	line("{\"ev\":\"end\"}");
	started = false;
	fflush(stdout);
}

ZTEST_RULE(kernel_unit_trace, trace_before, trace_after);
