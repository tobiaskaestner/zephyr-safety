# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Unit tests of the deterministic JSON output."""

import json

from probatrix.core import jsonout


def test_jsonout_is_deterministic(tmp_path):
    obj = {"b": [1, 2], "a": {"rows": [[1, "x"], [2, "y"]]}, "c": [{"d": 1}]}
    s1 = jsonout.write(tmp_path / "x.json", obj)
    s2 = jsonout.write(tmp_path / "y.json", json.loads((tmp_path / "x.json").read_text()))
    assert s1 == s2
    assert json.loads((tmp_path / "x.json").read_text()) == obj
    assert jsonout.read(tmp_path / "x.json") == obj
