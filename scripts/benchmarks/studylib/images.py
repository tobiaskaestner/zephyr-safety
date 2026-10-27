# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The names of the images in a point folder <run>/<tree>/<point>/.

A run gives each image the name <app>-<tree>-<point>.elf and .hex, so a
copy of the file outside its folder still says what it is. The runs before
2026-10-28 have zephyr.elf and zephyr.hex: their seals cover the names, so
they keep them. find() knows both. The build cache keeps zephyr.elf and
zephyr.hex in its entries: an entry has no app, tree or point of its own
(two experiments can share it).
"""

from pathlib import Path

EXTS = (".elf", ".hex")


def name(app, tree, point, ext):
    return f"{app}-{tree}-{point}{ext}"


def names(app, tree, point):
    """{cache file name: point folder file name} of the images."""
    return {f"zephyr{ext}": name(app, tree, point, ext) for ext in EXTS}


def find(pdir, ext):
    """The image with the extension ext in a point folder (old or new name), or None."""
    pdir = Path(pdir)
    old = pdir / f"zephyr{ext}"
    if old.is_file():
        return old
    found = sorted(pdir.glob(f"*{ext}"))
    return found[0] if len(found) == 1 else None
