# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for satisfies_check.py: python -m pytest doc/_scripts -q"""

import json
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import satisfies_check  # noqa: E402

SOURCE = """\
/**
 * @brief Documented and kept.
 *
 * @satisfies ZEP-SRS-1-1
 * @satisfies ZEP-SRS-1-2
 */
int k_kept(void);

/**
 * @brief Excluded by the Doxyfile.
 *
 * @satisfies ZEP-SRS-1-3
 */
int z_hidden(void);

/**
 * @brief Documents the next one.
 */
int k_next(void);

/* @satisfies ZEP-SRS-1-4 in a plain comment */
int k_plain(void);

/**
 * @brief Declared in two projects.
 *
 * @satisfies ZEP-SRS-1-5
 */
int k_twice(void);
"""


def _member(ident, name, line, uids=()):
    sat = ""
    if uids:
        reqs = "".join(f'<requirement refid="requirement_{u}"/>' for u in uids)
        sat = f"<satisfies>{reqs}</satisfies>"
    return (
        f'<memberdef kind="function" id="{ident}"><name>{name}</name>{sat}'
        f'<location file="zephyr/api.h" line="{line}" declfile="zephyr/api.h"'
        f' declline="{line}"/></memberdef>'
    )


def _project(tmp, name, members):
    xml = tmp / name
    xml.mkdir()
    (xml / "index.xml").write_text(
        '<doxygenindex><compound refid="api_8h" kind="file"><name>api.h</name>'
        "</compound></doxygenindex>"
    )
    (xml / "api_8h.xml").write_text(
        '<doxygen><compounddef id="api_8h" kind="file"><compoundname>api.h</compoundname>'
        f'<sectiondef kind="func">{"".join(members)}</sectiondef></compounddef></doxygen>'
    )
    return xml


def _needs(tmp, doc, ids):
    d = tmp / doc
    d.mkdir()
    needs = {i: {"id": i, "type": "impl", "is_external": False} for i in ids}
    (d / "needs.json").write_text(
        json.dumps({"current_version": "", "versions": {"": {"needs": needs}}})
    )
    return d / "needs.json"


def test_comments_spans_and_kinds():
    text = '/** a\n b */\nint x; /* c */ // d\n/// e\nchar *s = "/* no";\n'
    got = [(c.start, c.end, c.doc) for c in satisfies_check.comments(text)]
    assert got == [(1, 2, True), (3, 3, False), (3, 3, False), (4, 4, True)]


def test_doxyfile_inputs(tmp_path):
    doxyfile = tmp_path / "d.doxyfile"
    doxyfile.write_text(
        textwrap.dedent(
            """\
            # INPUT = not/this
            INPUT                  = /a/one.h \\
                                     /b/two.c \\

            INPUT_ENCODING         = UTF-8
            """
        )
    )
    assert satisfies_check.doxyfile_inputs(doxyfile) == [Path("/a/one.h"), Path("/b/two.c")]


def test_classify_sites(tmp_path, capsys):
    src = tmp_path / "include" / "zephyr" / "api.h"
    src.parent.mkdir(parents=True)
    src.write_text(SOURCE)
    doxyfile = tmp_path / "api.doxyfile"
    doxyfile.write_text(f"INPUT = {src}\n")
    api = _project(tmp_path, "api", [
        _member("a1", "k_kept", 7, ["ZEP-SRS-1-1", "ZEP-SRS-1-2"]),
        _member("a2", "k_next", 19),
        _member("a3", "k_plain", 22),
        _member("a4", "k_twice", 29, ["ZEP-SRS-1-5"]),
    ])
    design = _project(tmp_path, "design", [_member("d1", "k_twice", 29, ["ZEP-SRS-1-5"])])
    needs = _needs(tmp_path, "api-documentation", ["IMPL-k_kept", "IMPL-k_twice"])
    accepted = tmp_path / "accepted.yaml"
    accepted.write_text(
        'accepted:\n'
        '  - site: "include/zephyr/api.h ZEP-SRS-1-4"\n'
        '    reason: "plain comment, upstream to fix"\n'
        '  - site: "include/zephyr/api.h ZEP-SRS-9-9"\n'
        '    reason: "gone"\n'
    )
    rc = satisfies_check.main([
        "--doxygen", str(doxyfile), str(api), "--doxygen", str(doxyfile), str(design),
        "--needs", str(needs), "--zephyr-base", str(tmp_path), "--accepted", str(accepted),
    ])
    out = capsys.readouterr().out
    assert rc == 1
    assert "5 @satisfies sites in 1 files: 2 OK on 1 impl needs, 1 MISSING, 1 DUPLICATE, 1 accepted" in out
    assert "MISSING  include/zephyr/api.h:12  ZEP-SRS-1-3  its comment documents no entity" in out
    assert "MISSING (accepted)  include/zephyr/api.h:21  ZEP-SRS-1-4  in a plain comment" in out
    assert "DUPLICATE  include/zephyr/api.h:27  ZEP-SRS-1-5" in out
    assert "STALE accepted entry  include/zephyr/api.h ZEP-SRS-9-9" in out


def test_unscanned(tmp_path):
    (tmp_path / "a.h").write_text("/** @satisfies ZEP-SRS-1-1 */\nint a;\n")
    (tmp_path / "b.h").write_text("int b;\n")
    (tmp_path / "c.c").write_text("/** @satisfies ZEP-SRS-1-2 */\nint c;\n")
    got = satisfies_check.unscanned([tmp_path], [tmp_path / "c.c"])
    assert got == [tmp_path / "a.h"]
