# Zephyr Safety Workspace — Claude Context

## Purpose

This is a Zephyr RTOS safety workspace (`ws-safety/safety`) for exploratory work toward IEC 61508
compliance. The goal is full traceability from **requirements → design → tests** for kernel
subsystems, starting with the **queue** implementation. The intended output is a set of formal
documents (API spec, detailed design, test specification) that can satisfy a safety auditor.

## Workspace Layout

```
/wrk/z/ws-safety/
├── safety/              ← this repo (you are here)
│   ├── doc/             ← Sphinx + Doxygen documentation sources
│   └── generated/       ← generated intermediate artefacts
├── zephyr/              ← Zephyr kernel source (branch: topic-safety-tskr from tiacsys fork)
├── doc/reqmgmt/         ← StrictDoc requirements (separate git project)
├── tools/zdocs/         ← the documentation engine (west project, Zephyr module)
├── bdoc-zdocs/          ← CMake build output on zdocs
└── bdoc/                ← pre-migration reference build — do not rebuild
```

## Two Distinct Kernel Objects — Do Not Conflate

| Object | Header | Implementation | Purpose |
|---|---|---|---|
| `k_queue` | `include/zephyr/kernel/queue.h_` | `kernel/queue.c` | Internal base object; `k_fifo` and `k_lifo` are thin wrappers around it |
| `k_msgq` | `include/zephyr/kernel/msg_q.h` | `kernel/msg_q.c` | Message queue — a completely separate kernel object; **not in scope here** |

The current focus is `k_queue` / `k_fifo` / `k_lifo`. The detailed-design doxyfile was
historically pointing at `msg_q` files by mistake — that is a known WIP issue.

## Requirements Structure

Requirements live in `../doc/reqmgmt/docs/software_requirements/` as StrictDoc `.sdoc` files.
Relevant chapters for the queue scope:

| File | Prefix | Subject |
|---|---|---|
| `queues.sdoc` | `ZEP-SRS-20-*` | `k_queue` base object |
| `lifos.sdoc` | `ZEP-SRS-23-*` | `k_lifo` wrapper |
| `fifos.sdoc` | `ZEP-SRS-24-*` | `k_fifo` wrapper |

`ZEP-SRS-21-*` is condition variables — unrelated. `ZEP-SRS-22-*` is intentionally absent.
`ZEP-SRS-15-*` (`data_passing.sdoc`) is an older/separate data-passing chapter, not the primary
queue requirements.

Requirement UIDs are referenced in test source files using the Sphinx role:
```rst
:external+req:ref:`zep-srs-20-6`
```
(lowercase, matching the StrictDoc cross-reference format). Example already present in
`tests/kernel/queue/src/test_queue_contexts.c`.

## Documentation Build System

The docset is a consumer of the **zdocs** engine (`../tools/zdocs`, declared in `west.yml`
and discovered as a Zephyr module). `doc/CMakeLists.txt` sets the `ZDOCS_*` consumer
contract and calls `add_docs_from_registry()`; every document is declared once in
`doc/documents.yaml`, which drives build targets, intersphinx, Doxygen `TAGFILES`, nav
groups and needs imports. Shared sphinx-needs vocabulary lives in `doc/needs_config.toml`.
Each `doc/<document>/conf.py` is a thin shim around `zdocs_conf.configure()`.

Build directory: `../bdoc-zdocs`. (`../bdoc` is the pre-migration reference build on the
old in-tree engine — do not rebuild it.)

### Build Targets

A document's registry id is its target stem and deploy path:
`<id>-<builder>` → `deploy/<builder>/<id>/`; Doxygen XML goes to `deploy/xml/<id>/`.

| Document id | Kind | Content |
|---|---|---|
| `requirements` | Sphinx + StrictDoc | Requirements from `.sdoc` files |
| `architecture` | Sphinx | Arc42-style architecture document |
| `test-specification` | Sphinx + sphinx-needs | Test spec (sources in `doc/test-specification-sphinxneeds/`) |
| `test-report` | Sphinx + sphinx-needs | Test report (sources in `doc/test-report-sphinxneeds/`) |
| `api-documentation` | Sphinx + Breathe | API doc consuming Doxygen XML |
| `dox-zephyr` | Doxygen | Full kernel API docs |
| `dox-zephyr-safety-api` | Doxygen | Safety-scope public API |
| `dox-zephyr-safety-detailed-design` | Doxygen | Internal design |
| `dox-zephyr-safety-testspec` | Doxygen | Test suite docs, parsed by `testmodule::` |
| `safety-committee` | Sphinx | Governance |
| `sandbox-*` | Sphinx | Superseded experiments (incl. the hand-crafted test spec/report in `doc/test-specification/`, `doc/test-report/`) |

The build is two-stage. `doc-index` builds every document's stage-1 index (objects.inv,
tag files, needs.json); every `<id>-html` depends on **all** of them, so build
`doc-index` first. `doc-check` validates the deploy tree and the xref smoke page.

```sh
cmake -S doc -B ../bdoc-zdocs
cmake --build ../bdoc-zdocs --target doc-index
cmake --build ../bdoc-zdocs --target test-specification-html test-report-html
cmake --build ../bdoc-zdocs --target doc-check
```

### Doxygen Configuration

Templates: `doc/dox-*/Doxyfile.in`. zdocs expands them and then **appends** the keys it
owns (output paths, XML, tag files, `TAGFILES`, theme, header/footer, logo), so those must
not be set in the templates — they would be silently overridden.

| Doxyfile | `INPUT` sources |
|---|---|
| `dox-zephyr-safety-api` | `mainpage.md`, `_doxygen/safety-api-groups.dox`, `kernel.h` |
| `dox-zephyr-safety-detailed-design` | `mainpage.md`, `_doxygen/safety-api-groups.dox`, `queue.h_`, `kernel/queue.c` |
| `dox-zephyr-safety-testspec` | `mainpage.md`, `groups.dox`, queue + fifo test sources |
| `dox-zephyr` | the full upstream Zephyr API — `crossref: false`, a stand-alone reference that no safety document links into |

`doc/_doxygen/safety-api-groups.dox` holds the API group hierarchy stubs (kept here, not
inline in source, so the upstream source tree stays clean and rebasing is easier).

### Breathe Integration (Sphinx ↔ Doxygen)

Sphinx documents pull rendered content from doxygen XML via Breathe directives:
```rst
.. doxygengroup:: queue_apis
   :members:
```
Example: `doc/api-documentation/queue_apis.rst` → `dox-zephyr-safety-api` XML.

## Traceability Chain (Goal)

```
StrictDoc (.sdoc)             requirements-html (Sphinx)
  ZEP-SRS-20-* / 23-* / 24-*

        ↕  :external+req:ref: roles in source file docstrings

Doxygen @defgroup/@ingroup    api-documentation-html        (public API)
  queue.h_                    dox-zephyr-safety-detailed-design (internal design)
  queue.c

Doxygen @defgroup/@ingroup    test-specification-html       (test spec)
  tests/kernel/queue/src/*.c  dox-zephyr-safety-testspec
```

### Doxygen Group Hierarchy

**API groups** (defined in `doc/_doxygen/safety-api-groups.dox` and `queue.h_`):
```
kernel_apis
  └── queue_apis
```

**Test groups** (defined in `doc/_doxygen/safety-test-groups.dox` and `tests/.../main.c`):
```
all_tests
  └── kernel_queue_tests
        ├── queue_api          (@defgroup in main.c → ZTEST_SUITE)
        └── queue_api_1cpu     (@defgroup in main.c → ZTEST_SUITE)
```

Individual `ZTEST` functions need `@ingroup queue_api` or `@ingroup queue_api_1cpu` to appear
in the test specification doxygen output.

## `queue.h_` — Why the Unusual Name

This file is a branch-local workaround: it extracts the queue portion of the upstream
`kernel.h` monolith into a standalone file so that the doxygen `INPUT` can be kept narrow and
rebasing against upstream Zephyr is less painful. It is not an upstream Zephyr convention.

## Key Source Files

### Implementation (in `../zephyr/`)
- `kernel/queue.c` — `k_queue_*` implementation; `sys_sflist_t` + `k_spinlock`
- `include/zephyr/kernel/queue.h_` — public API header; `@defgroup queue_apis`

### Tests (in `../zephyr/tests/kernel/queue/`)
- `src/main.c` — `ZTEST_SUITE` + `@defgroup` anchors
- `src/test_queue_contexts.c` — context/threading tests; has existing `ZEP-SRS-20-*` refs
- `src/test_queue_fail.c` — error/failure tests
- `src/test_queue_loop.c` — stress/loop tests
- `src/test_queue_user.c` — userspace API tests
- `test-spec.rst` — RST stub using `doxygengroup::` directives

### Documentation config (in `doc/`)
- `documents.yaml` — the document registry (read by zdocs)
- `needs_config.toml` — shared sphinx-needs types, links and fields
- `_doxygen/safety-api-groups.dox` — API group stubs
- `dox-*/Doxyfile.in`, `dox-*/mainpage.md` — Doxygen templates and introductions
- `api-documentation/queue_apis.rst` — Breathe pull for API doc
- `test-specification-sphinxneeds/` — test spec Sphinx root (registry id `test-specification`)
- `_extensions/strictdoc_runner.py` — auto-runs `strictdoc export` on Sphinx build-init

### Requirements (in `../doc/reqmgmt/docs/software_requirements/`)
- `queues.sdoc` — `ZEP-SRS-20-*`
- `lifos.sdoc` — `ZEP-SRS-23-*`
- `fifos.sdoc` — `ZEP-SRS-24-*`

## Open Work Items (as of 2026-05-29)

1. **Testspec doxyfile** — replace dummy scaffolding files with real test sources; add `@ingroup`
   annotations to each `ZTEST` function so they appear in the testspec doxygen output.
2. **Detailed-design doxyfile** — redirect `INPUT` from `msg_q.*` to `queue.c` / `queue.h_`.
3. **Test-specification Sphinx doc** — create `doc/test-specification/kernel/test-spec.rst`
   (or wire up the existing `tests/kernel/queue/test-spec.rst` via include/symlink).
4. **Requirement traceability** — propagate `:external+req:ref:` annotations to all relevant
   `ZTEST` functions, following the pattern already in `test_queue_contexts.c`.
