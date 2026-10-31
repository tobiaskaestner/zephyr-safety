# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The errors that the engine and the kinds share.

NoValue and MissingRun: the data do not give a value (a check or a central result
waits or has no verdict). DesignError: a design file is wrong. SchemaError: a file
breaks its schema. SealError: a raw run does not agree with its seal. RunError and CampaignError:
the runner and the campaign engine stop.
"""


class NoValue(Exception):
    """The data do not give the value (the metric is absent, a form has no tool)."""


class MissingRun(NoValue):
    """No evidence run of an experiment in an instance: the run is to be made (analysis missing)."""

    def __init__(self, experiment, where):
        super().__init__(f"no evidence run of {experiment} in {where}")
        self.experiment, self.where = experiment, where


class DesignError(Exception):
    pass


class SchemaError(ValueError):
    pass


class SealError(Exception):
    pass


class RunError(Exception):
    """A run stops before or while it is made: the repo is dirty, it changed, the run list refuses the run."""


class CampaignError(Exception):
    """A campaign cannot start or go on (a lock, a dirty repo, a wrong folder)."""
