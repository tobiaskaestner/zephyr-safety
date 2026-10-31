# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Unit tests of the names and folders of studies, instances and runs."""

import pytest

from probatrix.core import config, layout


def test_layout_names_and_folders(tmp_path):
    assert str(layout.study_folder("load-scaling@x/t2t")) == "st-load-scaling@x/st-t2t"
    assert str(layout.run_folder("e/20260101T000000Z")) == "ex-e/20260101T000000Z"
    root = tmp_path / "top"
    (root / "st-a@b" / "st-c").mkdir(parents=True)
    for f in (root, root / "st-a@b", root / "st-a@b" / "st-c"):
        (f / "instance.json").write_text("{}")
    assert layout.instance_path_of(root / "st-a@b" / "st-c", root) == "a@b/c"
    assert layout.find_root(root / "st-a@b" / "st-c") == root.resolve()
    assert layout.run_id_of(root / "ex-e" / "20260101T000000Z") == "e/20260101T000000Z"
    assert layout.instance_folders(root)[0] == root


def test_display_names():
    assert layout.display("top/a@b/c") == "top/st-a@b/st-c"
    assert layout.display("top") == "top"
    assert layout.ipath_display("") == "(top)"


def test_wrong_folders_are_refused(tmp_path):
    with pytest.raises(ValueError):
        layout.instance_path_of(tmp_path / "x" / "y", tmp_path)
    with pytest.raises(ValueError):
        layout.run_id_of(tmp_path / "ex-e" / "not-a-time")
    with pytest.raises(ValueError):
        layout.find_root(tmp_path)


def test_core_has_no_board_rule():
    assert not hasattr(layout, "strip_board") and not hasattr(layout, "board_suffix")
    assert layout.STUDY_PREFIX == config.project().study_prefix
