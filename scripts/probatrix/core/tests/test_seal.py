# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Unit tests of the seal of a raw run folder."""

import pytest

from probatrix.core import errors, seal


def test_seal_write_verify_and_tamper(tmp_path):
    run = tmp_path / "ex-a" / "20260101T000000Z"
    (run / "t" / "p").mkdir(parents=True)
    (run / "manifest.json").write_text("{}")
    (run / "t" / "p" / "rep1.log").write_text("LAT BEGIN\n")
    d = seal.write(run)
    assert d.startswith("sha256:") and seal.verify(run) == d
    assert seal.write(run) == d  # the same seal again
    (run / "t" / "p" / "rep1.log").write_text("changed\n")
    with pytest.raises(seal.SealError):
        seal.verify(run)
    with pytest.raises(seal.SealError):
        seal.write(run)


def test_the_seal_error_is_the_error_of_core():
    assert seal.SealError is errors.SealError
