#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Doxygen input filter to rename internal function implementations to their
public API names.

This script finds all occurrences of function names prefixed with `z_impl_`
(e.g., `z_impl_k_foo_bar`) and replaces them with the public name
(e.g., `k_foo_bar`).

This is useful for documenting syscalls or other APIs where the implementation
has a different name than the documented function.
"""

import sys
import re
import os

def process_file(file_path):
    """
    Processes a single source file, renames functions, and prints to stdout.

    Args:
        file_path (str): The path to the file to process.
    """
    sys.stderr.write(f"[LOG] Renaming filter running on: {os.path.basename(file_path)}\n")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except IOError as e:
        sys.stderr.write(f"[ERROR] Could not open file {file_path}: {e}\n")
        return

    # The pattern to find: "z_impl_" followed by a name starting with "k_"
    # The parentheses capture the part of the name we want to keep.
    pattern = r'z_impl_(k_\w+)'
    
    # The replacement: r'\1' refers to the first captured group (the public name)
    replacement = r'\1'

    # Perform the substitution
    modified_content, num_replacements = re.subn(pattern, replacement, content)

    if num_replacements > 0:
        sys.stderr.write(f"[LOG] Performed {num_replacements} replacements in the file.\n")
    else:
        sys.stderr.write(f"[LOG] No matching patterns found to replace.\n")

    # --- Output the modified file content ---
    sys.stdout.write(modified_content)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        process_file(sys.argv[1])
    else:
        sys.stderr.write("[ERROR] Usage: python doxygen_rename_filter.py <file_path>\n")

