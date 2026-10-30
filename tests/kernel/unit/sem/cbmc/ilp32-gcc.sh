#!/usr/bin/env bash
# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0
# Native compiler of goto-cc for the ILP32 runs (run.sh): drops -m32, which
# the 32-bit ARM gcc of the Zephyr SDK does not know, and preprocesses with
# this gcc, so the predefined macros are the ones of an ILP32 target.
args=()
for a in "$@"; do [[ $a == -m32 ]] || args+=("$a"); done
exec "${SDK_ARM_GCC:-$HOME/zephyr-sdk-1.0.1/gnu/arm-zephyr-eabi/bin/arm-zephyr-eabi-gcc}" "${args[@]}"
