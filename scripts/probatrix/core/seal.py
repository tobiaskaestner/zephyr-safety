# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The seal of a raw run folder.

The seal is the file <UTC>.sha256 beside the run folder <UTC>/: one line
"<sha256>  <path>" for each file of the folder, sorted by path. The run
folder does not change after the run. The digest of the run is
"sha256:" + the sha256 of the seal file.
"""

import hashlib
from pathlib import Path


class SealError(Exception):
    pass


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def seal_path(run_dir):
    run_dir = Path(run_dir)
    return run_dir.parent / f"{run_dir.name}.sha256"


def seal_text(run_dir):
    run_dir = Path(run_dir)
    files = sorted(p for p in run_dir.rglob("*") if p.is_file())
    if not files:
        raise SealError(f"{run_dir}: no files")
    return "".join(f"{file_sha256(p)}  {p.relative_to(run_dir).as_posix()}\n" for p in files)


def digest(run_dir):
    """The digest of a sealed run: "sha256:" + the sha256 of its seal file."""
    return "sha256:" + file_sha256(seal_path(run_dir))


def write(run_dir):
    """Write the seal of a run folder; refuse to write a different seal over an existing one."""
    path = seal_path(run_dir)
    text = seal_text(run_dir)
    if path.exists():
        if path.read_text() != text:
            raise SealError(f"{path}: the run folder does not agree with its seal")
        return digest(run_dir)
    path.write_text(text)
    return digest(run_dir)


def verify(run_dir):
    """Return the digest if the run folder agrees with its seal, else raise SealError."""
    path = seal_path(run_dir)
    if not path.is_file():
        raise SealError(f"{run_dir}: no seal {path.name}")
    want = {}
    for line in path.read_text().splitlines():
        sha, _, rel = line.partition("  ")
        want[rel] = sha
    have = {p.relative_to(run_dir).as_posix(): p for p in Path(run_dir).rglob("*") if p.is_file()}
    missing = sorted(set(want) - set(have))
    extra = sorted(set(have) - set(want))
    changed = sorted(r for r in set(want) & set(have) if file_sha256(have[r]) != want[r])
    if missing or extra or changed:
        raise SealError(f"{run_dir}: does not agree with its seal: missing {missing[:5]}, "
                        f"extra {extra[:5]}, changed {changed[:5]}")
    return digest(run_dir)


def files(run_dir):
    """The sha256 of each file of a sealed run, from its seal: {path: sha256}."""
    out = {}
    for line in seal_path(run_dir).read_text().splitlines():
        sha, _, rel = line.partition("  ")
        out[rel] = sha
    return out
