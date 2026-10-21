/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * Native gcov backend for the per-test coverage rule of ztest
 * (CONFIG_ZTEST_COVERAGE_PER_TEST, subsys/testsuite/ztest/src/ztest_rules.c).
 *
 * The rule resets the counters before each test and calls
 * gcov_coverage_dump_tagged("<suite>.<test>") after it. In a target build,
 * subsys/testsuite/coverage does this. A unit test is a host program with
 * libgcov, so this file does it with __gcov_reset() and __gcov_dump().
 *
 * libgcov writes each .gcda file to its canonical path below the
 * directory in GCOV_PREFIX. A tagged dump first writes to a temporary
 * directory. Then it copies each file to "<canonical path>@@<tag>". This is
 * the name that twister finds for per-test coverage
 * (twisterlib/coverage.py, discover_per_test_semihost()).
 */

#define _GNU_SOURCE /* nftw() with FTW_DEPTH and FTW_PHYS */

#include <errno.h>
#include <ftw.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include <coverage.h>
#include <zephyr/debug/gcov.h>

/* libgcov */
extern void __gcov_dump(void);
extern void __gcov_reset(void);

static const char *dump_tag;
static size_t dump_prefix_len;
static int dump_errors;

void gcov_reset_all_counts(void)
{
	__gcov_reset();
}

static int copy_file(const char *src, const char *dst)
{
	char buf[4096];
	size_t n;
	int ret = 0;
	FILE *in = fopen(src, "rb");
	FILE *out;

	if (in == NULL) {
		return -errno;
	}

	out = fopen(dst, "wb");
	if (out == NULL) {
		ret = -errno;
		fclose(in);
		return ret;
	}

	while ((n = fread(buf, 1, sizeof(buf), in)) > 0) {
		if (fwrite(buf, 1, n, out) != n) {
			ret = -EIO;
			break;
		}
	}

	if (ferror(in)) {
		ret = -EIO;
	}
	fclose(in);
	if (fclose(out) != 0 && ret == 0) {
		ret = -EIO;
	}

	return ret;
}

/* Moves <prefix>/<canonical path> to <canonical path>@@<tag>. */
static int move_tagged(const char *path, const struct stat *sb, int type, struct FTW *ftw)
{
	char dst[PATH_MAX];

	(void)sb;
	(void)ftw;

	if (type == FTW_F) {
		if (snprintf(dst, sizeof(dst), "%s@@%s", path + dump_prefix_len, dump_tag) >=
		    (int)sizeof(dst)) {
			fprintf(stderr, "gcov_native: path too long: %s\n", path);
			dump_errors++;
		} else if (copy_file(path, dst) != 0) {
			fprintf(stderr, "gcov_native: cannot write %s\n", dst);
			dump_errors++;
		}
		(void)unlink(path);
	} else if (type == FTW_DP) {
		(void)rmdir(path);
	}

	return 0;
}

static char *save_env(const char *name)
{
	const char *value = getenv(name);

	return (value != NULL) ? strdup(value) : NULL;
}

static void restore_env(const char *name, char *value)
{
	if (value != NULL) {
		setenv(name, value, 1);
		free(value);
	} else {
		unsetenv(name);
	}
}

void gcov_coverage_dump_tagged(const char *tag)
{
	const char *tmpdir = getenv("TMPDIR");
	char prefix[PATH_MAX];
	char *old_prefix;
	char *old_strip;

	if (tag == NULL) {
		__gcov_dump();
		__gcov_reset();
		return;
	}

	snprintf(prefix, sizeof(prefix), "%s/kernel_unit_gcov_XXXXXX",
		 (tmpdir != NULL) ? tmpdir : "/tmp");
	if (mkdtemp(prefix) == NULL) {
		fprintf(stderr, "gcov_native: mkdtemp: %s\n", strerror(errno));
		return;
	}

	old_prefix = save_env("GCOV_PREFIX");
	old_strip = save_env("GCOV_PREFIX_STRIP");
	setenv("GCOV_PREFIX", prefix, 1);
	setenv("GCOV_PREFIX_STRIP", "0", 1);

	__gcov_dump();

	restore_env("GCOV_PREFIX", old_prefix);
	restore_env("GCOV_PREFIX_STRIP", old_strip);

	/*
	 * __gcov_dump() marks the data as dumped and does not dump again
	 * until the next reset.
	 */
	__gcov_reset();

	dump_tag = tag;
	dump_prefix_len = strlen(prefix);
	(void)nftw(prefix, move_tagged, 16, FTW_DEPTH | FTW_PHYS);

	if (dump_errors > 0) {
		fprintf(stderr, "gcov_native: %d files of test %s not written\n", dump_errors, tag);
		dump_errors = 0;
	}
}

void gcov_coverage_dump(void)
{
	gcov_coverage_dump_tagged(NULL);
}
