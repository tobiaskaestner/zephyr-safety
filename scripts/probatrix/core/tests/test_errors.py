# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The errors of core are the same objects that the modules export."""

from probatrix.core import design, errors, schema, seal


def test_the_modules_export_the_errors_of_core():
    assert design.DesignError is errors.DesignError
    assert schema.SchemaError is errors.SchemaError and issubclass(errors.SchemaError, ValueError)
    assert seal.SealError is errors.SealError


def test_a_missing_run_is_a_no_value():
    e = errors.MissingRun("exp", "inst")
    assert isinstance(e, errors.NoValue) and e.experiment == "exp" and e.where == "inst"
    assert "no evidence run of exp in inst" in str(e)
