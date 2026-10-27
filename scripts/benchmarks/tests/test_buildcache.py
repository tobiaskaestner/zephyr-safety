# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Unit tests of the build cache (studylib/buildcache.py)."""

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))

from studylib import buildcache  # noqa: E402

POINT = {"kconfig": {"A": "y"}, "conf_files": [], "dtc_overlays": []}


def fake_build(tmp_path, name, elf=b"ELF1"):
    b = tmp_path / name
    (b / "zephyr").mkdir(parents=True)
    (b / "zephyr" / "zephyr.elf").write_bytes(elf)
    (b / "zephyr" / ".config").write_text("CONFIG_A=y\n")
    log = tmp_path / f"{name}.log"
    log.write_text("ok\n")
    return b, log


def test_key_has_the_build_version_and_no_paths():
    a = buildcache.key_inputs("b", "app", {"zephyr": "r"}, "1.0", "t1", "t2", POINT, "v4.4.0-1-gabc")
    b = buildcache.key_inputs("b", "app", {"zephyr": "r"}, "1.0", "t1", "t2", POINT, "v4.4.0-2-gabc")
    assert buildcache.key_of(a) != buildcache.key_of(b)
    assert "'/" not in str(a)          # no absolute path


def test_put_keeps_the_first_entry_and_replaces_a_broken_one(tmp_path):
    c = buildcache.Cache(tmp_path / "cache")
    key = "ab" * 32
    b1, log1 = fake_build(tmp_path, "b1", b"ELF1")
    b2, log2 = fake_build(tmp_path, "b2", b"ELF2")
    e1 = c.put(key, {}, b1, ["cmake"], log1, {"repo": "/r1"})
    e2 = c.put(key, {}, b2, ["cmake"], log2, {"repo": "/r2"})       # another process came second
    assert e2 == e1 and (c.entry_dir(key) / "zephyr.elf").read_bytes() == b"ELF1"
    (c.entry_dir(key) / "zephyr.elf").write_bytes(b"cut")             # a broken entry
    assert c.get(key) is None
    e3 = c.put(key, {}, b2, ["cmake"], log2, {"repo": "/r2"})
    assert c.get(key) == e3 and e3["paths"] == {"repo": "/r2"}
    assert c.work_dir(key).name.endswith(f".{__import__('os').getpid()}")
