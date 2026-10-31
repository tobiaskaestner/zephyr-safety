# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Unit tests of the schema registry (several folders, the $id prefix as a parameter)."""

from pathlib import Path

import pytest

from probatrix.core import schema

BENCH = Path(__file__).resolve().parents[2] / "benchmarks" / "schemas"


def make_folder(tmp_path, prefix):
    (tmp_path / f"{prefix}.schema.yaml").write_text(
        f"$schema: https://json-schema.org/draft/2020-12/schema\n$id: {prefix}/thing.schema.yaml\n"
        "type: object\nadditionalProperties: false\nrequired: [name]\nproperties:\n  name: {type: string}\n")
    return tmp_path


@pytest.fixture
def clean(monkeypatch):
    monkeypatch.setattr(schema, "_FOLDERS", {})
    monkeypatch.setattr(schema, "_NOT_DEFAULT", set())
    schema.validator.cache_clear()
    yield
    schema.validator.cache_clear()


def test_a_second_folder_with_its_own_prefix(tmp_path, clean):
    schema.register("latbench", BENCH)
    schema.register("tst", make_folder(tmp_path, "tst"))
    assert schema.prefixes() == ["latbench", "tst"]
    assert schema.problems("thing", {"name": "x"}, prefix="tst") == []
    assert "missing key 'name'" in schema.problems("thing", {}, prefix="tst")[0]
    assert "unknown key 'nme'" in schema.problems("thing", {"name": "x", "nme": 1}, prefix="tst")[0]
    assert schema.problems("study", {"name": "top"}) == []          # the first prefix is the default
    with pytest.raises(schema.SchemaError, match="unknown key"):
        schema.check("study", {"name": "top", "kindd": 1}, "study.yaml")


def test_no_folder_is_an_error(clean):
    with pytest.raises(schema.SchemaError, match="no schema folder"):
        schema.problems("study", {})


def test_a_prefix_cannot_change_its_folder(tmp_path, clean):
    schema.register("tst", make_folder(tmp_path, "tst"))
    schema.register("tst", tmp_path)                                  # the same folder again: fine
    with pytest.raises(ValueError):
        schema.register("tst", tmp_path / "other")


def test_the_default_prefix_is_the_first_one_that_is_not_marked_otherwise(tmp_path, clean):
    """A kind that registers with default=False never becomes the default, whatever the import order."""
    folder = tmp_path / "t"
    folder.mkdir()
    schema.register("tst", make_folder(folder, "tst"), default=False)
    assert schema.prefixes() == ["tst"]
    assert schema.problems("thing", {"name": "x"}) == []              # the only prefix is the default
    schema.register("latbench", BENCH)
    assert schema.prefixes() == ["tst", "latbench"]
    assert schema.problems("study", {"name": "top"}) == []            # latbench is the default
