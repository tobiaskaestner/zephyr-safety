# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Unit tests of the build cache (studylib/buildcache.py)."""

from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent

from probatrix.benchmarks.studylib import buildcache  # noqa: E402

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


def test_built_by_uses_and_the_names_in_a_point_folder(tmp_path):
    from probatrix.benchmarks.studylib import images
    c = buildcache.Cache(tmp_path / "cache")
    key = "cd" * 32
    b, log = fake_build(tmp_path, "b")
    (b / "zephyr" / "zephyr.hex").write_text(":00\n")
    e = c.put(key, {}, b, ["cmake"], log, {}, built_by="irq-smoke/20261028T000000Z")
    assert e["built_by"] == "irq-smoke/20261028T000000Z" and c.uses(key) == []
    c.note_use(key, {"run": "irq-smoke/20261028T000000Z", "from": "build"})
    c.note_use(key, {"run": "fast-mode/20261028T010000Z", "from": "cache"})
    assert [u["from"] for u in c.uses(key)] == ["build", "cache"]
    pdir = tmp_path / "run" / "ws-safety" / "stock-idle"
    pdir.mkdir(parents=True)
    c.copy_to(key, pdir, images.names("irq_latency", "ws-safety", "stock-idle"))
    assert (pdir / "irq_latency-ws-safety-stock-idle.elf").read_bytes() == b"ELF1"
    assert images.find(pdir, ".hex").name == "irq_latency-ws-safety-stock-idle.hex"
    assert not (pdir / "zephyr.elf").exists() and (pdir / ".config").is_file()
    old = tmp_path / "old"
    old.mkdir()
    (old / "zephyr.elf").write_bytes(b"x")
    assert images.find(old, ".elf").name == "zephyr.elf" and images.find(old, ".hex") is None
