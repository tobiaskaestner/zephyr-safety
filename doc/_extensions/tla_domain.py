# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Sphinx extension: the ``tla`` domain, to show TLA+ specifications.

The ASCII ``.tla`` files stay the source for TLC and Apalache. This extension
reads them at build time and shows them in the document. The comment before a
definition is the prose of the document, so the spec is the single source.

Directives::

    .. tla:module:: KSem
       :body:

    .. tla:definition:: Give
       :module: KSem

    .. tla:definition:: KSem!Give

    .. tla:module-body::
       :module: KSem
       :property-needs:

    .. tla:property:: NoWaitWhileAvailable
       :module: KSem
       :expresses: ZEP-SRS-5-3
       :kind: invariant

Roles: ``:tla:mod:`KSem``` and ``:tla:def:`KSem!Give``` (or ``:tla:def:`Give```
after a ``tla:module`` directive on the same page).

A module argument is a module name or a path to a ``.tla`` file. The
extension finds a module name as ``<name>.tla`` in the directories of
``tla_spec_paths``, then in the directory of the current module. A path is
relative to the document, or relative to the source directory if it starts
with ``/``.

Operator names in a rendered definition link to their definitions, if the
document set shows them. The extension looks for a name in the module of the
definition, then in the modules that it extends. It does not link record
fields, the parameters of the definition, or the name of the definition.

``tla:property`` makes a sphinx-needs need (type ``tla_property_need_type``,
id ``tla_property_id``) with the links ``tla_property_link`` to the
requirements from ``@expresses``. See README.rst for the tags and the fields.

Configuration (in conf.py):

``tla_spec_paths``
    Directories with the ``.tla`` files, relative to the conf.py directory.
``tla_unicode``
    True (default): show the Unicode syntax. False: show ASCII. The directive
    options ``:ascii:`` and ``:unicode:`` override it.
``tla_unicode_prime``
    True (default): show the prime as ``′``.
``tla_unicode_align``
    ``relative`` (default) or ``pad``. See ``tla_unicode``.
``tla_prose``
    ``rst`` (default): parse the doc comments as reStructuredText. ``text``:
    show them as plain paragraphs.
``tla_property_need_type``, ``tla_property_link``, ``tla_property_id``
    The need type (``prop``), the link name (``expresses``) and the id format
    (``PROP-{module}-{name}``).
``tla_property_need_fields``
    Field role -> field name. The roles are ``kind``, ``expected``,
    ``module``, ``source_file``, ``source_line`` and ``c_function``. A role
    with the value None gives no field.
``tla_source_root``
    The ``source_file`` field is relative to this directory (relative to the
    conf.py directory). Default: the source directory.
``tla_c_function_role``
    A role for the ``@c-function`` names (for example ``c:func``). Default:
    None (the names show as literals).
"""

import os
import re
import shutil
from pathlib import Path

from docutils import nodes
from docutils.parsers.rst import directives
from docutils.statemachine import StringList
from pygments.token import STANDARD_TYPES, Keyword, Name, Operator, Punctuation, Whitespace
from sphinx import addnodes
from sphinx.domains import Domain, ObjType
from sphinx.roles import XRefRole
from sphinx.util import logging
from sphinx.util.docutils import SphinxDirective, is_directive_registered, is_role_registered
from sphinx.util.nodes import make_refnode

from tla_extract import TLAParseError, parse_file
from tla_lexer import TLALexer
from tla_unicode import TLAUnicodeLexer, ascii_tokens, to_unicode, unicode_tokens

logger = logging.getLogger(__name__)

__version__ = "0.1.0"

#: The values of the ``@kind`` tag.
KINDS = ("definition", "action", "action-property", "invariant", "liveness", "probe")
#: The kinds that ``:property-needs:`` makes a need of (with or without @expresses).
NEED_KINDS = ("invariant", "action-property", "liveness", "probe")
#: The values of the ``@expected`` tag.
EXPECTED = ("hold", "violation")
#: The values of the ``@level`` tag (the two grains of the design note).
LEVELS = ("1", "2")
#: The tags that the extension knows. ``@type`` and ``@typeAlias`` are the type
#: annotations of Apalache: they are not prose, and the extension does not show them.
TAGS = ("expresses", "kind", "c-function", "expected", "level", "type", "typeAlias")

CSS_NAME = "tla_domain.css"
#: The start of the rawsource of a rendered block (see code_nodes()).
_RAW_MARK = "\\* tla_domain: rendered from\n"
_CSS_SOURCE = Path(__file__).parent / "tla_static" / CSS_NAME

DEFAULT_NEED_FIELDS = {
    "kind": "kind",
    "expected": "expected",
    "module": "tla_module",
    "source_file": "source_file",
    "source_line": "source_line",
    "c_function": "c_function",
}


# -- Module cache --------------------------------------------------------------

_CACHE = {}


def load_module(path):
    """Parse the module file ``path`` (cached by modification time)."""
    path = os.path.abspath(path)
    mtime = os.stat(path).st_mtime_ns
    hit = _CACHE.get(path)
    if hit and hit[0] == mtime:
        return hit[1]
    module = parse_file(path)
    _CACHE[path] = (mtime, module)
    return module


def anchor_id(module, name=None):
    """The HTML id of a module or of a definition."""

    def clean(text):
        return re.sub(r"[^A-Za-z0-9_]", lambda m: f"-x{ord(m.group(0)):x}-", text)

    if name is None:
        return f"tla-module-{clean(module)}"
    return f"tla-{clean(module)}-{clean(name)}"


def infer_kind(unit):
    """The kind of a property without a ``@kind`` tag, from its formula.

    ``~>``, ``<>``, ``WF_`` or ``SF_`` in the body: liveness. ``[][`` (an
    action under a box): action-property. Else: invariant.
    """
    tokens = [(t, v) for t, v in TLALexer().get_tokens(unit.text) if t not in Whitespace]
    body = tokens
    for k, (ttype, value) in enumerate(tokens):
        if ttype in Operator and value in ("==", "≜"):
            body = tokens[k + 1 :]
            break
    values = [v for t, v in body if t in Operator or t in Keyword]
    if {"~>", "<>", "↝", "◇", "WF", "SF"} & set(values):
        return "liveness"
    for k, (_, value) in enumerate(body[:-1]):
        if value in ("[]", "□") and body[k + 1][1] == "[":
            return "action-property"
    return "invariant"


def _css_class(ttype):
    while ttype not in STANDARD_TYPES:
        ttype = ttype.parent
    return STANDARD_TYPES[ttype]


# -- Domain --------------------------------------------------------------------


class TLAXRefRole(XRefRole):
    def process_link(self, env, refnode, has_explicit_title, title, target):
        refnode["tla:module"] = env.ref_context.get("tla:module")
        return title, target


class TLADomain(Domain):
    """The TLA+ domain."""

    name = "tla"
    label = "TLA+"
    object_types = {
        "module": ObjType("module", "mod"),
        "definition": ObjType("definition", "def"),
        "property": ObjType("property", "def"),
    }
    roles = {
        "mod": TLAXRefRole(warn_dangling=True),
        "def": TLAXRefRole(warn_dangling=True),
    }
    initial_data = {
        "modules": {},  # module -> (docname, anchor)
        "objects": {},  # (module, name) -> (docname, anchor, objtype)
        "extends": {},  # module -> {docname: [extended modules]}
    }
    data_version = 1

    @property
    def modules(self):
        return self.data["modules"]

    @property
    def objects(self):
        return self.data["objects"]

    def is_duplicate_module(self, module, location):
        """True (with a warning) if the domain has the module already."""
        if module not in self.modules:
            return False
        logger.warning(
            "duplicate TLA+ module %s, other instance in %s (use :no-index:)",
            module,
            self.env.doc2path(self.modules[module][0]),
            location=location,
            type="tla",
            subtype="duplicate",
        )
        return True

    def note_module(self, module, anchor):
        self.modules[module] = (self.env.docname, anchor)

    def is_duplicate(self, module, name, location):
        """True (with a warning) if the domain has the definition already."""
        key = (module, name)
        if key not in self.objects:
            return False
        logger.warning(
            "duplicate TLA+ definition %s!%s, other instance in %s (use :no-index:)",
            module,
            name,
            self.env.doc2path(self.objects[key][0]),
            location=location,
            type="tla",
            subtype="duplicate",
        )
        return True

    def note_object(self, module, name, objtype, anchor):
        self.objects[(module, name)] = (self.env.docname, anchor, objtype)

    def note_extends(self, module, extends):
        self.data["extends"].setdefault(module, {})[self.env.docname] = list(extends)

    def clear_doc(self, docname):
        for key, entry in list(self.modules.items()):
            if entry[0] == docname:
                del self.modules[key]
        for key, entry in list(self.objects.items()):
            if entry[0] == docname:
                del self.objects[key]
        for module, by_doc in list(self.data["extends"].items()):
            by_doc.pop(docname, None)
            if not by_doc:
                del self.data["extends"][module]

    def merge_domaindata(self, docnames, otherdata):
        for key, entry in otherdata["modules"].items():
            if entry[0] in docnames:
                self.modules[key] = entry
        for key, entry in otherdata["objects"].items():
            if entry[0] in docnames:
                self.objects[key] = entry
        for module, by_doc in otherdata["extends"].items():
            for docname, ext in by_doc.items():
                if docname in docnames:
                    self.data["extends"].setdefault(module, {})[docname] = ext

    def extends_of(self, module):
        """The modules that ``module`` extends, in order, without repeats."""
        out = []
        for ext in self.data["extends"].get(module, {}).values():
            for name in ext:
                if name not in out:
                    out.append(name)
        return out

    def find_definition(self, module, name, fallback=False):
        """(module, name) of the definition that ``name`` means, else None.

        The search order: ``module``, then the modules that it extends (breadth
        first). With ``fallback``, a name that only one module defines.
        """
        if module:
            seen, queue = set(), [module]
            while queue:
                current = queue.pop(0)
                if current in seen:
                    continue
                seen.add(current)
                if (current, name) in self.objects:
                    return (current, name)
                queue += self.extends_of(current)
        if fallback:
            hits = [key for key in self.objects if key[1] == name]
            if len(hits) == 1:
                return hits[0]
        return None

    def _split_target(self, target, node):
        if "!" in target:
            module, name = target.split("!", 1)
            return module, name, False
        return node.get("tla:module"), target, True

    def resolve_xref(self, env, fromdocname, builder, typ, target, node, contnode):
        if typ in ("code", "codemod"):
            # A name in rendered code: a link if the name is known, else the
            # plain name. Never a missing reference (also not with nitpicky).
            if typ == "codemod":
                entry = self.modules.get(target)
                found = (entry[0], entry[1], target) if entry else None
            else:
                key = self.find_definition(node.get("tla:module"), target)
                found = (*self.objects[key][:2], f"{key[0]}!{key[1]}") if key else None
            if found is None:
                return contnode
            ref = make_refnode(builder, fromdocname, found[0], found[1], contnode, found[2])
            ref["classes"].append("tla-ref")
            return ref
        if typ == "mod":
            entry = self.modules.get(target)
            if entry is None:
                return None
            return make_refnode(builder, fromdocname, entry[0], entry[1], contnode, target)
        module, name, fallback = self._split_target(target, node)
        key = self.find_definition(module, name, fallback=fallback)
        if key is None:
            return None
        docname, anchor, _ = self.objects[key]
        return make_refnode(builder, fromdocname, docname, anchor, contnode, f"{key[0]}!{key[1]}")

    def resolve_any_xref(self, env, fromdocname, builder, target, node, contnode):
        results = []
        if target in self.modules:
            ref = self.resolve_xref(env, fromdocname, builder, "mod", target, node, contnode)
            if ref is not None:
                results.append(("tla:mod", ref))
        ref = self.resolve_xref(env, fromdocname, builder, "def", target, node, contnode)
        if ref is not None:
            results.append(("tla:def", ref))
        return results

    def get_objects(self):
        for module, (docname, anchor) in self.modules.items():
            yield module, module, "module", docname, anchor, 0
        for (module, name), (docname, anchor, objtype) in self.objects.items():
            yield f"{module}!{name}", name, objtype, docname, anchor, 1

    def get_full_qualified_name(self, node):
        target = node.get("reftarget")
        if target and "!" not in target and node.get("tla:module"):
            return f"{node['tla:module']}!{target}"
        return target


# -- Directives ----------------------------------------------------------------


def _code_ref(reftype, name, css, module):
    """A name in rendered code. The domain resolves it to a link or to text."""
    ref = addnodes.pending_xref(
        "",
        refdomain="tla",
        reftype=reftype,
        reftarget=name,
        refexplicit=True,
        refwarn=False,
    )
    ref["tla:module"] = module
    ref += nodes.inline(name, name, classes=[css])
    return ref


def _unit_list(argument):
    return [x for x in re.split(r"[\s,]+", argument or "") if x]


class TLADirective(SphinxDirective):
    """Shared code of the TLA+ directives."""

    common_options = {
        "module": directives.unchanged_required,
        "ascii": directives.flag,
        "unicode": directives.flag,
    }

    # -- Module lookup

    def _spec_dirs(self):
        # _resolve_config() made the paths absolute.
        dirs = [Path(p) for p in self.config.tla_spec_paths]
        current = self.env.ref_context.get("tla:module-path")
        if current:
            dirs.append(Path(current).parent)
        return dirs

    def find_module_path(self, spec):
        """The absolute path of the module ``spec`` (a name or a path), or None."""
        loaded = self.env.temp_data.get("tla:loaded", {})
        if spec in loaded:
            return loaded[spec]
        if spec.endswith(".tla") or "/" in spec:
            _, path = self.env.relfn2path(spec)
            return str(path) if os.path.isfile(path) else None
        for directory in self._spec_dirs():
            candidate = directory / f"{spec}.tla"
            if candidate.is_file():
                return str(candidate.resolve())
        return None

    def get_module(self, spec):
        """Load the module ``spec``. Return the Module, or None (with a warning)."""
        if not spec:
            spec = self.env.ref_context.get("tla:module")
            if not spec:
                logger.warning(
                    "no TLA+ module: give :module: or put a tla:module directive before",
                    location=self.get_location(),
                    type="tla",
                    subtype="module",
                )
                return None
        path = self.find_module_path(spec)
        if path is None:
            logger.warning(
                "TLA+ module %r not found (tla_spec_paths: %s)",
                spec,
                ", ".join(str(d) for d in self._spec_dirs()) or "empty",
                location=self.get_location(),
                type="tla",
                subtype="module",
            )
            return None
        self.env.note_dependency(path)
        try:
            module = load_module(path)
        except (OSError, TLAParseError) as exc:
            logger.warning(
                "cannot read TLA+ module %s: %s",
                path,
                exc,
                location=self.get_location(),
                type="tla",
                subtype="module",
            )
            return None
        self.env.temp_data.setdefault("tla:loaded", {})[module.name] = path
        self.env.domains["tla"].note_extends(module.name, module.extends)
        return module

    # -- Options

    def use_unicode(self):
        if "ascii" in self.options:
            return False
        if "unicode" in self.options:
            return True
        return bool(self.config.tla_unicode)

    # -- Rendering

    def prose_nodes(self, text, line_nos, path):
        """The nodes of a doc comment."""
        if not text.strip():
            return []
        container = nodes.container(classes=["tla-prose"])
        if self.config.tla_prose == "text":
            for para in re.split(r"\n\s*\n", text.strip()):
                container += nodes.paragraph(para, " ".join(para.split()))
            return [container]
        lines = StringList()
        for k, line in enumerate(text.split("\n")):
            line_no = line_nos[k] if k < len(line_nos) else (line_nos[-1] if line_nos else 1)
            lines.append(line, path, line_no - 1)
        self.state.nested_parse(lines, 0, container)
        return [container]

    def code_nodes(self, module, text, exclude=()):
        """A highlighted block of TLA+ code, with links for the known names."""
        if self.use_unicode():
            lines = unicode_tokens(
                text,
                prime=self.config.tla_unicode_prime,
                align=self.config.tla_unicode_align,
            )
        else:
            lines = ascii_tokens(text)
        # rawsource != astext(): the writers show the children as they are (a
        # parsed literal), and do not highlight the text again. An empty
        # rawsource does not work: Sphinx replaces it with astext().
        block = nodes.literal_block(_RAW_MARK + text, "", classes=["tla-code"])
        for k, line in enumerate(lines):
            while line and line[-1][0] in Whitespace and not line[-1][1].strip():
                line = line[:-1]
            if k:
                block += nodes.Text("\n")
            after_extends = False
            for idx, (ttype, value) in enumerate(line):
                css = _css_class(ttype)
                if ttype in Keyword and value == "EXTENDS":
                    after_extends = True
                if self._module_name(line, idx, after_extends):
                    block += _code_ref("codemod", value, css, module.name)
                elif self._linkable(line, idx, exclude):
                    block += _code_ref("code", value, css, module.name)
                elif css:
                    block += nodes.inline(value, value, classes=[css])
                else:
                    block += nodes.Text(value)
        while (
            block.children
            and isinstance(block.children[-1], nodes.Text)
            and not block.children[-1].strip()
        ):
            block.pop()
        inner = nodes.container(classes=["highlight"])
        inner += block
        outer = nodes.container(classes=["highlight-tla", "notranslate", "tla-block"])
        outer += inner
        return [outer]

    @staticmethod
    def _module_name(line, idx, after_extends):
        """True for a module name after EXTENDS or INSTANCE."""
        ttype, _ = line[idx]
        if ttype not in Name:
            return False
        if after_extends:
            return True
        prev = next((t for t in reversed(line[:idx]) if t[0] not in Whitespace), None)
        return bool(prev) and prev[0] in Keyword and prev[1] == "INSTANCE"

    @staticmethod
    def _linkable(line, idx, exclude):
        ttype, value = line[idx]
        if ttype not in Name or ttype in Name.Builtin or ttype in Name.Namespace:
            return False
        if value in exclude:
            return False
        prev = next((t for t in reversed(line[:idx]) if t[0] not in Whitespace), None)
        nxt = next((t for t in line[idx + 1 :] if t[0] not in Whitespace), None)
        if prev and prev[0] in Punctuation and prev[1] == ".":
            return False  # a record field: obs.op, !.actor
        if nxt and nxt[0] in Operator and nxt[1] in ("|->", "↦"):
            return False  # a record field: [actor |-> ...]
        return True

    def tag_nodes(self, module, unit):
        """A field list with the tags of ``unit`` (kind, expresses, ...)."""
        items = []
        uids = [u for v in unit.tags.get("expresses", []) for u in _unit_list(v)]
        if uids:
            if is_role_registered("need"):
                items.append(("Expresses", ", ".join(f":need:`{u}`" for u in uids), True))
            else:
                items.append(("Expresses", ", ".join(f"``{u}``" for u in uids), True))
        funcs = [f for v in unit.tags.get("c-function", []) for f in _unit_list(v)]
        if funcs:
            role = self.config.tla_c_function_role
            fmt = (lambda f: f":{role}:`{f}`") if role else (lambda f: f"``{f}``")
            items.append(("Models", ", ".join(fmt(f) for f in funcs), True))
        expected = (unit.tags.get("expected") or [""])[-1]
        if expected == "violation":
            items.append(("Expected", "violation (TLC reports a counterexample)", False))
        level = (unit.tags.get("level") or [""])[-1]
        if level == "2":
            items.append(("Level", "2 (lock grain)", False))
        if not items:
            return []
        field_list = nodes.field_list(classes=["tla-tags"])
        for label, value, rst in items:
            body = nodes.field_body()
            para = nodes.paragraph()
            if rst:
                text_nodes, messages = self.parse_inline(value, lineno=self.lineno)
                para += text_nodes
                para += messages
            else:
                para += nodes.Text(value)
            body += para
            field_list += nodes.field("", nodes.field_name(label, label), body)
        return [field_list]

    def check_tags(self, module, unit):
        for tag, value, line in unit.tag_lines:
            loc = f"{module.path}:{line}"
            if tag not in TAGS:
                logger.warning(
                    "unknown TLA+ tag @%s (known: %s)",
                    tag,
                    ", ".join("@" + t for t in TAGS),
                    location=loc,
                    type="tla",
                    subtype="tag",
                )
            elif tag == "kind" and value not in KINDS:
                logger.warning(
                    "unknown @kind %r (known: %s)",
                    value,
                    ", ".join(KINDS),
                    location=loc,
                    type="tla",
                    subtype="tag",
                )
            elif tag == "expected" and value not in EXPECTED:
                logger.warning(
                    "unknown @expected %r (known: %s)",
                    value,
                    ", ".join(EXPECTED),
                    location=loc,
                    type="tla",
                    subtype="tag",
                )
            elif tag == "level" and value not in LEVELS:
                logger.warning(
                    "unknown @level %r (known: %s)",
                    value,
                    ", ".join(LEVELS),
                    location=loc,
                    type="tla",
                    subtype="tag",
                )
            elif not value:
                logger.warning("empty tag @%s", tag, location=loc, type="tla", subtype="tag")

    def definition_nodes(
        self,
        module,
        unit,
        *,
        objtype="definition",
        noindex=False,
        prose=True,
        tags=True,
        signature=True,
        content=None,
    ):
        """The nodes of one definition: signature, prose, tags and code."""
        self.check_tags(module, unit)
        domain = self.env.domains["tla"]
        anchor = anchor_id(module.name, unit.name)
        if not noindex and domain.is_duplicate(module.name, unit.name, self.get_location()):
            noindex = True
        if not noindex:
            self.env.temp_data.setdefault("tla:shown", set()).add((module.name, unit.name))
        result = []
        body = []
        if prose:
            body += self.prose_nodes(unit.doc, unit.doc_lines, module.path)
        if tags:
            body += self.tag_nodes(module, unit)
        text = unit.text
        if unit.recursive:
            text = unit.recursive + "\n" + text
        exclude = set(unit.params) | {unit.name}
        body += self.code_nodes(module, text, exclude)
        if content is not None:
            body += content

        if not signature:
            target = nodes.target("", "", ids=[] if noindex else [anchor])
            if not noindex:
                self.state.document.note_explicit_target(target)
                domain.note_object(module.name, unit.name, objtype, anchor)
            box = nodes.container(classes=["tla", objtype])
            box += body
            return [target, box]

        desc = addnodes.desc()
        desc["domain"] = "tla"
        desc["objtype"] = desc["desctype"] = objtype
        desc["no-index"] = noindex
        desc["classes"] += ["tla", objtype]
        sig = addnodes.desc_signature("", "")
        sig["module"] = module.name
        sig["fullname"] = unit.name
        sig["_toc_parts"] = (module.name, unit.name)
        sig["_toc_name"] = unit.name
        kind = (unit.tags.get("kind") or [""])[-1]
        notes = []
        if unit.local:
            notes.append("LOCAL")
        if unit.instance:
            notes.append("INSTANCE")
        if objtype == "property" or (kind and kind != "definition"):
            notes.append(kind or "property")
        for note in notes:
            sig += addnodes.desc_annotation(note + " ", note + " ")
        if unit.plain_head:
            sig += addnodes.desc_name(unit.name, unit.name)
            if "(" in unit.head:
                plist = addnodes.desc_parameterlist()
                for param in unit.params:
                    plist += addnodes.desc_parameter(param, param)
                sig += plist
        else:
            head = to_unicode(unit.head) if self.use_unicode() else unit.head
            sig += addnodes.desc_name(head, head)
        if not noindex:
            sig["ids"].append(anchor)
            self.state.document.note_explicit_target(sig)
            domain.note_object(module.name, unit.name, objtype, anchor)
            index = addnodes.index(
                entries=[
                    ("single", f"{unit.name} (TLA+ {objtype} in {module.name})", anchor, "", None)
                ]
            )
            result.append(index)
        desc += sig
        desc_content = addnodes.desc_content()
        desc_content += body
        desc += desc_content
        result.append(desc)
        return result

    def other_unit_nodes(self, module, unit):
        """ASSUME, THEOREM, INSTANCE and other units: prose and code."""
        self.check_tags(module, unit)
        out = self.prose_nodes(unit.doc, unit.doc_lines, module.path)
        out += self.code_nodes(module, unit.text)
        return out

    def comment_nodes(self, module, unit):
        """A section comment: a rubric for one line, else prose."""
        if not unit.doc.strip():
            return []
        if "\n" not in unit.doc.strip():
            return [nodes.rubric(unit.doc.strip(), unit.doc.strip(), classes=["tla-section"])]
        return self.prose_nodes(unit.doc, unit.doc_lines, module.path)

    # -- Property needs

    def property_values(self, module, unit, options):
        """(kind, uids, expected, c_functions) of a property, options first."""
        kind = options.get("kind") or (unit.tags.get("kind") or [""])[-1]
        if not kind or kind == "definition":
            kind = infer_kind(unit)
        if "expresses" in options:
            uids = _unit_list(options["expresses"])
        else:
            uids = [u for v in unit.tags.get("expresses", []) for u in _unit_list(v)]
        expected = options.get("expected") or (unit.tags.get("expected") or ["hold"])[-1]
        funcs = [f for v in unit.tags.get("c-function", []) for f in _unit_list(v)]
        return kind, uids, expected, funcs

    def property_need_nodes(self, module, unit, options):
        """A need for the property ``unit``, with its rendering as content."""
        need_type = self.config.tla_property_need_type
        if not is_directive_registered(need_type):
            logger.warning(
                "need type %r is not configured: %s!%s renders without a need",
                need_type,
                module.name,
                unit.name,
                location=self.get_location(),
                type="tla",
                subtype="needs",
            )
            return self.definition_nodes(module, unit, objtype="property")
        self.check_tags(module, unit)
        kind, uids, expected, funcs = self.property_values(module, unit, options)
        if kind not in KINDS:
            logger.warning(
                "unknown kind %r", kind, location=self.get_location(), type="tla", subtype="tag"
            )
        if expected not in EXPECTED:
            logger.warning(
                "unknown expected %r",
                expected,
                location=self.get_location(),
                type="tla",
                subtype="tag",
            )
        need_id = options.get("id") or self.config.tla_property_id.format(
            module=module.name, name=unit.name
        )
        fields = dict(DEFAULT_NEED_FIELDS)
        fields.update(self.config.tla_property_need_fields or {})
        root = self.config.tla_source_root or self.env.srcdir
        source_file = os.path.relpath(module.path, root).replace(os.sep, "/")
        values = {
            "kind": kind,
            "expected": expected,
            "module": module.name,
            "source_file": source_file,
            "source_line": str(unit.start_line),
            "c_function": "; ".join(funcs),
        }
        rst = [f".. {need_type}:: {unit.name}", f"   :id: {need_id}"]
        if uids:
            rst.append(f"   :{self.config.tla_property_link}: {', '.join(uids)}")
        for role, name in fields.items():
            if name and values.get(role):
                rst.append(f"   :{name}: {values[role]}")
        rst.append("")
        if unit.doc.strip():
            rst += ["   " + line if line.strip() else "" for line in unit.doc.split("\n")]
            rst.append("")
        rst.append(f"   .. tla:definition:: {module.name}!{unit.name}")
        rst.append("      :objtype: property")
        rst.append("      :no-prose:")
        rst.append("      :no-tags:")
        rst.append("      :no-signature:")
        rst.append("      :ascii:" if not self.use_unicode() else "      :unicode:")
        source, line = self.get_source_info()
        lines = StringList()
        for text in rst:
            lines.append(text, source, (line or 1) - 1)
        container = nodes.container(classes=["tla-property"])
        self.state.nested_parse(lines, 0, container)
        return container.children[:]


class TLAModule(TLADirective):
    """``.. tla:module:: <name or path>``: the module header."""

    required_arguments = 1
    has_content = True
    option_spec = {
        "ascii": directives.flag,
        "unicode": directives.flag,
        "no-index": directives.flag,
        "noindex": directives.flag,
        "no-prose": directives.flag,
        "body": directives.flag,
        "property-needs": directives.flag,
    }

    def run(self):
        module = self.get_module(self.arguments[0])
        if module is None:
            return []
        self.env.ref_context["tla:module"] = module.name
        self.env.ref_context["tla:module-path"] = self.env.temp_data["tla:loaded"][module.name]
        noindex = "no-index" in self.options or "noindex" in self.options
        domain = self.env.domains["tla"]
        if not noindex and domain.is_duplicate_module(module.name, self.get_location()):
            noindex = True
        anchor = anchor_id(module.name)
        result = []

        desc = addnodes.desc()
        desc["domain"] = "tla"
        desc["objtype"] = desc["desctype"] = "module"
        desc["no-index"] = noindex
        desc["classes"] += ["tla", "module"]
        sig = addnodes.desc_signature("", "")
        sig["module"] = module.name
        sig["fullname"] = module.name
        sig["_toc_parts"] = (module.name,)
        sig["_toc_name"] = module.name
        sig += addnodes.desc_annotation("MODULE ", "MODULE ")
        sig += addnodes.desc_name(module.name, module.name)
        if not noindex:
            sig["ids"].append(anchor)
            self.state.document.note_explicit_target(sig)
            domain.note_module(module.name, anchor)
            result.append(
                addnodes.index(
                    entries=[("single", f"{module.name} (TLA+ module)", anchor, "", None)]
                )
            )
        desc += sig
        content = addnodes.desc_content()
        if "no-prose" not in self.options:
            content += self.prose_nodes(module.doc, module.doc_lines, module.path)
        decl = [u.text for u in module.declarations()]
        if decl:
            content += self.code_nodes(module, "\n\n".join(decl))
        if self.content:
            extra = nodes.container()
            self.state.nested_parse(self.content, self.content_offset, extra)
            content += extra.children
        desc += content
        result.append(desc)
        if "body" in self.options:
            result += module_body_nodes(
                self, module, "property-needs" in self.options, declarations=False
            )
        return result


def module_body_nodes(directive, module, property_needs, declarations=True, exclude=()):
    """All units of ``module`` in source order.

    The definitions that the page showed before (with an index entry) and the
    names in ``exclude`` are not shown again.
    """
    out = []
    for unit in module.units:
        if unit.kind == "definition":
            shown = directive.env.temp_data.get("tla:shown", set())
            if (module.name, unit.name) in shown or unit.name in exclude:
                continue
            if property_needs and _is_property(unit):
                out += directive.property_need_nodes(module, unit, {})
            else:
                out += directive.definition_nodes(module, unit)
        elif unit.kind == "comment":
            out += directive.comment_nodes(module, unit)
        elif unit.kind == "recursive":
            continue  # shown in its definition
        elif unit.kind in ("extends", "constants", "variables"):
            if declarations:
                out += directive.other_unit_nodes(module, unit)
        else:
            out += directive.other_unit_nodes(module, unit)
    return out


def _is_property(unit):
    kind = (unit.tags.get("kind") or [""])[-1]
    return bool(unit.tags.get("expresses")) or kind in NEED_KINDS


class TLAModuleBody(TLADirective):
    """``.. tla:module-body::``: all units of a module, in source order."""

    required_arguments = 0
    optional_arguments = 1
    option_spec = {
        **TLADirective.common_options,
        "property-needs": directives.flag,
        "exclude": directives.unchanged,
    }

    def run(self):
        spec = self.arguments[0] if self.arguments else self.options.get("module")
        module = self.get_module(spec)
        if module is None:
            return []
        declarations = self.env.ref_context.get("tla:module") != module.name
        return module_body_nodes(
            self,
            module,
            "property-needs" in self.options,
            declarations,
            exclude=set(_unit_list(self.options.get("exclude"))),
        )


def _split_name(directive):
    arg = directive.arguments[0].strip()
    if "!" in arg:
        module, name = arg.split("!", 1)
        return module, name
    return directive.options.get("module"), arg


class TLADefinition(TLADirective):
    """``.. tla:definition:: Name``: one top-level definition."""

    required_arguments = 1
    has_content = True
    option_spec = {
        **TLADirective.common_options,
        "no-index": directives.flag,
        "noindex": directives.flag,
        "no-prose": directives.flag,
        "no-tags": directives.flag,
        # For the generated content of tla:property.
        "no-signature": directives.flag,
        "objtype": lambda arg: directives.choice(arg, ("definition", "property")),
    }

    def run(self):
        module_spec, name = _split_name(self)
        module = self.get_module(module_spec)
        if module is None:
            return []
        unit = module.definition(name)
        if unit is None:
            logger.warning(
                "TLA+ module %s has no top-level definition %r",
                module.name,
                name,
                location=self.get_location(),
                type="tla",
                subtype="definition",
            )
            return []
        content = None
        if self.content:
            box = nodes.container()
            self.state.nested_parse(self.content, self.content_offset, box)
            content = box.children[:]
        return self.definition_nodes(
            module,
            unit,
            objtype=self.options.get("objtype", "definition"),
            noindex="no-index" in self.options or "noindex" in self.options,
            prose="no-prose" not in self.options,
            tags="no-tags" not in self.options,
            signature="no-signature" not in self.options,
            content=content,
        )


class TLAProperty(TLADirective):
    """``.. tla:property:: Name``: a definition and a sphinx-needs need."""

    required_arguments = 1
    option_spec = {
        **TLADirective.common_options,
        "id": directives.unchanged_required,
        "expresses": directives.unchanged,
        "kind": lambda arg: directives.choice(arg, KINDS),
        "expected": lambda arg: directives.choice(arg, EXPECTED),
    }

    def run(self):
        module_spec, name = _split_name(self)
        module = self.get_module(module_spec)
        if module is None:
            return []
        unit = module.definition(name)
        if unit is None:
            logger.warning(
                "TLA+ module %s has no top-level definition %r",
                module.name,
                name,
                location=self.get_location(),
                type="tla",
                subtype="definition",
            )
            return []
        return self.property_need_nodes(module, unit, self.options)


TLADomain.directives = {
    "module": TLAModule,
    "definition": TLADefinition,
    "module-body": TLAModuleBody,
    "property": TLAProperty,
}


# -- Setup ---------------------------------------------------------------------


def _resolve_config(app, config):
    """Make the paths of the configuration absolute (relative to conf.py)."""
    config.tla_spec_paths = [str(Path(app.confdir, p).resolve()) for p in config.tla_spec_paths]
    if config.tla_source_root:
        config.tla_source_root = str(Path(app.confdir, config.tla_source_root).resolve())


def _copy_css(app, exception):
    if exception is None and app.builder.format == "html":
        static = Path(app.outdir) / "_static"
        static.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(_CSS_SOURCE, static / CSS_NAME)


def setup(app):
    app.add_config_value("tla_spec_paths", [], "env", [list, tuple])
    app.add_config_value("tla_unicode", True, "env", [bool])
    app.add_config_value("tla_unicode_prime", True, "env", [bool])
    app.add_config_value("tla_unicode_align", "relative", "env", [str])
    app.add_config_value("tla_prose", "rst", "env", [str])
    app.add_config_value("tla_property_need_type", "prop", "env", [str])
    app.add_config_value("tla_property_link", "expresses", "env", [str])
    app.add_config_value("tla_property_id", "PROP-{module}-{name}", "env", [str])
    app.add_config_value("tla_property_need_fields", {}, "env", [dict])
    app.add_config_value("tla_source_root", None, "env")
    app.add_config_value("tla_c_function_role", None, "env")

    app.add_lexer("tla", TLALexer)
    app.add_lexer("tlaplus", TLALexer)
    app.add_lexer("tla-unicode", TLAUnicodeLexer)
    app.add_domain(TLADomain)
    app.connect("config-inited", _resolve_config)
    app.add_css_file(CSS_NAME)
    app.connect("build-finished", _copy_css)
    return {"version": __version__, "parallel_read_safe": True, "parallel_write_safe": True}
