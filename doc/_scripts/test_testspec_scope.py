# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for testspec_scope.py: python -m pytest doc/_scripts -q"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import testspec_scope  # noqa: E402


def _module(zephyr, rel, source):
    mod = zephyr / rel
    (mod / "src").mkdir(parents=True)
    (mod / "tests.yaml").write_text(f"tests:\n  {rel.replace('/', '.')}:\n    tags: t\n")
    (mod / "src/main.c").write_text(source)


def test_suite_without_tests_gets_no_group(tmp_path):
    """Two modules declare one suite, only one holds its tests: the suite group
    sits under that module alone, so its tests render on one page only."""
    zephyr = tmp_path / "zephyr"
    _module(
        zephyr, "tests/arch/common/gen_isr_table",
        "ZTEST(multilevel, test_masks)\n{\n}\n\nZTEST_SUITE(multilevel, NULL, NULL, NULL, NULL, NULL);\n",
    )
    _module(
        zephyr, "tests/arch/common/interrupt",
        "ZTEST_USER(interrupt_feature, test_api)\n{\n}\n\n"
        "ZTEST_SUITE(interrupt_feature, NULL, NULL, NULL, NULL, NULL);\n"
        "ZTEST_SUITE(multilevel, NULL, NULL, NULL, NULL, NULL);\n",
    )
    scope = tmp_path / "test-scope.yaml"
    scope.write_text("areas:\n  - path: tests/arch/common\n    code: ARCH\n    title: Arch\n")

    (area,) = testspec_scope.load_scope(scope, zephyr)
    suites = {m.path: m.suites for m in area.modules}
    assert suites == {
        "tests/arch/common/gen_isr_table": ["multilevel"],
        "tests/arch/common/interrupt": ["interrupt_feature"],
    }
    dox = testspec_scope.render_dox([area])
    assert dox.count("@defgroup multilevel ") == 1
    assert "@defgroup multilevel multilevel ZTest suite\n * @ingroup arch_common_gen_isr_table_module" in dox


def _workq(tmp_path, user_work_extra=""):
    zephyr = tmp_path / "zephyr"
    _module(
        zephyr, "tests/kernel/workq/user_work",
        user_work_extra + "ZTEST_USER(workqueue_api, test_user_mode)\n{\n}\n\n"
        "ZTEST_SUITE(workqueue_api, NULL, NULL, NULL, NULL, NULL);\n",
    )
    _module(
        zephyr, "tests/kernel/workq/work_queue",
        "ZTEST(workqueue_api, test_start_stop)\n{\n}\n\nZTEST(work, test_other)\n{\n}\n\n"
        "ZTEST_SUITE(workqueue_api, NULL, NULL, NULL, NULL, NULL);\n"
        "ZTEST_SUITE(work, NULL, NULL, NULL, NULL, NULL);\n",
    )
    scope = tmp_path / "test-scope.yaml"
    scope.write_text("areas:\n  - path: tests/kernel/workq\n    code: WORKQ\n    title: Workq\n")
    return scope, zephyr


def test_shared_suite_gets_a_group_per_module(tmp_path):
    """workqueue_api has tests in two modules: one qualified group in each,
    `<module group>__<suite>`, titled after the real suite; a suite of one
    module keeps its plain name."""
    scope, zephyr = _workq(tmp_path)
    areas = testspec_scope.load_scope(scope, zephyr)
    dox = testspec_scope.render_dox(areas)
    assert "@defgroup workqueue_api " not in dox
    for m in ("kernel_workq_user_work_module", "kernel_workq_work_queue_module"):
        assert (
            f"@defgroup {m}__workqueue_api workqueue_api ZTest suite\n * @ingroup {m}\n" in dox
        )
    assert "@defgroup work work ZTest suite\n * @ingroup kernel_workq_work_queue_module\n" in dox
    assert testspec_scope.qualified_suites(areas, zephyr) == {
        str((zephyr / "tests/kernel/workq/user_work").resolve()):
            {"workqueue_api": "kernel_workq_user_work_module__workqueue_api"},
        str((zephyr / "tests/kernel/workq/work_queue").resolve()):
            {"workqueue_api": "kernel_workq_work_queue_module__workqueue_api"},
    }


def test_declared_only_suite_is_not_shared(tmp_path):
    """A suite a second module only declares (interrupt's
    gen_isr_table_multilevel) is that module's no suite: not qualified."""
    zephyr = tmp_path / "zephyr"
    _module(zephyr, "tests/arch/common/gen_isr_table",
            "ZTEST(multilevel, test_masks)\n{\n}\n\nZTEST_SUITE(multilevel, NULL, NULL, NULL, NULL, NULL);\n")
    _module(zephyr, "tests/arch/common/interrupt",
            "ZTEST(irq, test_api)\n{\n}\n\nZTEST_SUITE(irq, NULL, NULL, NULL, NULL, NULL);\n"
            "ZTEST_SUITE(multilevel, NULL, NULL, NULL, NULL, NULL);\n")
    scope = tmp_path / "test-scope.yaml"
    scope.write_text("areas:\n  - path: tests/arch/common\n    code: ARCH\n    title: Arch\n")
    areas = testspec_scope.load_scope(scope, zephyr)
    assert testspec_scope.qualified_suites(areas, zephyr) == {}


def test_shared_suite_defined_by_hand_fails(tmp_path):
    scope, zephyr = _workq(
        tmp_path,
        "/**\n * @defgroup workqueue_api Work queue API\n * @ingroup kernel_workq_user_work_module\n */\n",
    )
    with pytest.raises(SystemExit, match="workqueue_api"):
        testspec_scope.load_scope(scope, zephyr)


def test_generate_writes_suites_json(tmp_path, monkeypatch):
    scope, zephyr = _workq(tmp_path)
    out = tmp_path / "gen"
    monkeypatch.setattr(sys, "argv", [
        "testspec_scope.py", "--scope", str(scope), "--zephyr-base", str(zephyr), "generate",
        "--dox-out", str(out / "dox/groups.dox"), "--spec-out", str(out / "spec"),
        "--report-out", str(out / "report"), "--suites-out", str(out / "suites.json"),
    ])
    assert testspec_scope.main() == 0
    table = json.loads((out / "suites.json").read_text())
    assert sorted(v["workqueue_api"] for v in table.values()) == [
        "kernel_workq_user_work_module__workqueue_api",
        "kernel_workq_work_queue_module__workqueue_api",
    ]
