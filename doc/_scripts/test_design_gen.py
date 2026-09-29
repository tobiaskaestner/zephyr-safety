# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for design_gen.py: python -m pytest doc/_scripts -q"""

import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import design_gen  # noqa: E402


def _parse(tmp_path, text):
    f = tmp_path / "page.rst"
    f.write_text(textwrap.dedent(text))
    return design_gen.parse_file(f, "doc/kernel/page.rst")


def test_marker_block(tmp_path):
    blocks, raw = _parse(
        tmp_path,
        """
        .. _lifos_v2:

        LIFOs
        #####

        .. design:: DESIGN-LIFOS LIFOs
           :fulfills: ZEP-SRS-23-1 ZEP-SRS-23-2
              ZEP-SRS-23-3

        A :dfn:`LIFO` is a kernel object.
        """,
    )
    assert raw == 1
    (b,) = blocks
    assert (b.id, b.caption, b.line) == ("DESIGN-LIFOS", "LIFOs", 7)
    assert b.fulfills == ["ZEP-SRS-23-1", "ZEP-SRS-23-2", "ZEP-SRS-23-3"]


def test_folded_options_and_status(tmp_path):
    blocks, _ = _parse(
        tmp_path,
        """
        .. design:: DESIGN-X
           :satisfies: ZEP-SRS-1-1
           :realizes: ZEP-SRS-1-2
           :status: draft
        """,
    )
    (b,) = blocks
    assert b.caption == "DESIGN-X"
    assert b.fulfills == ["ZEP-SRS-1-1", "ZEP-SRS-1-2"]
    assert b.fields == {"status": "draft"}


@pytest.mark.parametrize("opt", ["implements", "trace", "bogus"])
def test_unmapped_option_fails(tmp_path, opt):
    with pytest.raises(design_gen.DesignError):
        _parse(tmp_path, f".. design:: DESIGN-X X\n   :{opt}: Y\n")


def test_validate():
    a = design_gen.Block("DESIGN-A", "A", "doc/kernel/a.rst", 1, ["ZEP-SRS-1-1"])
    dup = design_gen.Block("DESIGN-A", "A", "doc/kernel/b.rst", 3, ["ZEP-SRS-1-9"])
    errors = design_gen.validate([a, dup], 2, {"ZEP-SRS-1-1"})
    assert any("duplicate design id DESIGN-A" in e for e in errors)
    assert any("ZEP-SRS-1-9: no such requirement (dangling)" in e for e in errors)
    assert design_gen.validate([a], 1, {"ZEP-SRS-1-1"}) == []
    assert design_gen.validate([a], 2, {"ZEP-SRS-1-1"})  # raw hit not parsed
