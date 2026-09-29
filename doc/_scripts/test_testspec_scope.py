# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for testspec_scope.py: python -m pytest doc/_scripts -q"""

import sys
from pathlib import Path

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
