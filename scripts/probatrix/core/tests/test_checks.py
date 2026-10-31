# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The generic check forms with a fake Kind: values that are numbers, texts or booleans."""

import pytest

from probatrix.core import checks, kinds
from probatrix.core.errors import NoValue


class FakeKind(kinds.BaseKind):
    name = "fake"

    def value(self, rep, metric, stat):
        return rep[metric]

    def known(self, metric, stat):
        return True


class Src:
    kind = FakeKind()

    def __init__(self, obs):
        self.obs = obs

    def observations(self, exp, series=None):
        return [o for o in self.obs if series is None or o.series == series]

    def run_obs(self, ref):
        return self.obs


def src(*values, metric="m"):
    return Src([checks.Obs("e/1", "t", f"p{i}", {}, {metric: v}) for i, v in enumerate(values)])


def run(expect, *values, stat="value"):
    return checks.evaluate({"experiment": "e", "metric": "m", "stat": stat, "expect": expect}, src(*values))


FORMS = [{"range": [0, 2]}, {"spread_le": 1}, {"spread_abs_le": 5}, {"order": ["p0", "p1"]},
         {"diff_to": {"point": "p0", "range": [0, 5]}}, {"ratio_to": {"point": "p0"}, "range": [0, 5]},
         {"diff_change": {"point": "p0", "of": ["p1", "p0"], "range": [0, 5]}}]


def test_numbers_work_in_every_numeric_form():
    for e in FORMS:
        assert run(e, 1, 2)["verdict"] in ("confirmed", "wrong"), e


@pytest.mark.parametrize("bad, word", [(True, "boolean"), (False, "boolean"), ("pass", "text")])
def test_numeric_forms_reject_a_bool_or_a_text_with_a_reason(bad, word):
    for e in FORMS:
        with pytest.raises(NoValue, match=word):
            run(e, 1, bad)
        with pytest.raises(NoValue, match=word):
            run(e, bad, 1)


def test_a_bool_would_pass_range_in_python():
    assert True in range(0, 3)          # the reason for the explicit rule
    with pytest.raises(NoValue, match="boolean True"):
        run({"range": [0, 2]}, True)


def test_equals_takes_texts_and_booleans():
    assert run({"equals": "pass"}, "pass", "pass")["verdict"] == "confirmed"
    assert run({"equals": "pass"}, "pass", "fail")["verdict"] == "wrong"
    assert run({"equals": True}, True, True)["verdict"] == "confirmed"
    assert run({"equals": True}, True, False)["verdict"] == "wrong"
    assert run({"equals": 3}, 3, 3)["verdict"] == "confirmed"


def test_number_helper():
    assert checks.number(3, "x") == 3 and checks.number(2.5, "x") == 2.5
    with pytest.raises(NoValue, match="x: the value is the boolean True"):
        checks.number(True, "x")
    with pytest.raises(NoValue, match="the text 'a'"):
        checks.number("a", "x")
