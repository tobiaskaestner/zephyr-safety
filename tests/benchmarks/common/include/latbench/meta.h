/*
 * Copyright (c) 2026 inovex GmbH
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @file
 * @brief Run metadata in the LAT line format.
 */

#ifndef LATBENCH_META_H_
#define LATBENCH_META_H_

/**
 * Print the app name, the variant, the Zephyr version, the clocks and the
 * Kconfig symbols that change latency.
 */
void lat_meta_print(const char *app, const char *variant);

/** Print one more metadata line: "LAT META <key>=<value>". */
void lat_meta_kv(const char *key, const char *value);

/** Print the end marker. The host stops the capture at this line. */
void lat_done(void);

#endif /* LATBENCH_META_H_ */
