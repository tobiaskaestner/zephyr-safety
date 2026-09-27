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

Requirement UIDs are uppercase, exactly as authored in StrictDoc (`ZEP-SRS-20-6`), everywhere:
need ids, Doxygen links and cross-references. Sources link to them with Doxygen's native
commands, **one UID per command** — `@verifies ZEP-SRS-20-6` on a test case,
`@satisfies ZEP-SRS-20-6` on an API. A second UID on the same line silently becomes link
text (deferred issue 003). In RST, reference a requirement as a need: `:need:`ZEP-SRS-20-6``.
A UID no requirement defines fails the build (zdocs' stage-2 Doxygen warning gate).

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
| `requirements` | Sphinx + sphinx-needs | One `req` need per StrictDoc requirement, generated (see below) |
| `architecture` | Sphinx | Arc42-style architecture document |
| `test-specification` | Sphinx + sphinx-needs | Test spec |
| `test-report` | Sphinx + sphinx-needs | Test report |
| `api-documentation` | Sphinx + Breathe | API doc consuming Doxygen XML |
| `dox-zephyr` | Doxygen | Full kernel API docs |
| `dox-zephyr-safety-api` | Doxygen | Safety-scope public API |
| `dox-zephyr-safety-detailed-design` | Doxygen | Internal design |
| `dox-zephyr-safety-testspec` | Doxygen | Test suite docs, parsed by `testmodule::` |
| `dox-requirements` | Doxygen | Generated `\requirement` blocks; hidden (`internal` group). Its tag file makes `\verifies`/`\satisfies` resolve |
| `safety-committee` | Sphinx | Governance |
| `sandbox-*` | Sphinx | Superseded experiments (sources under `doc/sandbox/`, incl. the hand-crafted test spec/report) |

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

Templates: `doc/dox/*/Doxyfile.in`. zdocs expands them and then **appends** the keys it
owns (output paths, XML, tag files, `TAGFILES`, theme, header/footer, logo), so those must
not be set in the templates — they would be silently overridden.

| Doxyfile | `INPUT` sources |
|---|---|
| `dox-zephyr-safety-api` | `mainpage.md`, `_doxygen/safety-api-groups.dox`, `kernel.h` |
| `dox-zephyr-safety-detailed-design` | `mainpage.md`, `_doxygen/safety-api-groups.dox`, `queue.h_`, `kernel/queue.c` |
| `dox-zephyr-safety-testspec` | `mainpage.md`, `groups.dox`, the generated groups `.dox`, each in-scope module's `src/` (from `doc/test-scope.yaml`) |
| `dox-zephyr` | the full upstream Zephyr API plus the generated `requirements.dox` — `crossref: false`, a stand-alone reference that no safety document links into |
| `dox-requirements` | the generated `requirements.dox` only |

### Requirements generation

The `requirements-gen` target in `doc/CMakeLists.txt` runs `strictdoc export --formats json`
over `../doc/reqmgmt`, then Zephyr's own `doc/_scripts/gen_requirements.py` — **unchanged,
from the zephyr tree** — which writes `requirements-gen/rst/generated/*.rst` (`.. req::`
needs, copied into the `requirements` document by its `conf.py`) and
`requirements-gen/dox/requirements.dox` (`\requirement` blocks). The need vocabulary is the
generator's: type `req`, link `trace`, fields `rtype`/`component` (`needs_config.toml`).

`doc/_doxygen/safety-api-groups.dox` holds the API group hierarchy stubs (kept here, not
inline in source, so the upstream source tree stays clean and rebasing is easier).

### Breathe Integration (Sphinx ↔ Doxygen)

Sphinx documents pull rendered content from doxygen XML via Breathe directives:
```rst
.. doxygengroup:: queue_apis
   :members:
```
Example: `doc/api-documentation/queue_apis.rst` → `dox-zephyr-safety-api` XML.

## Traceability Chain

```
StrictDoc (.sdoc)  ─ requirements-gen ─►  requirements-html (req needs)
  ZEP-SRS-20-* / 23-* / 24-*              dox-requirements   (\requirement, tag file)

        ↕  @verifies / @satisfies (native Doxygen), one UID per command

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

**Test groups** (root and procedure groups in `doc/dox/zephyr-safety-testspec/groups.dox`; area, module and suite groups generated from `doc/test-scope.yaml`):
```
all_tests
  └── kernel_queue_tests
        └── kernel_queue_module     (the group `testmodule::` is pointed at)
              ├── queue_api          (one per ZTEST_SUITE, generated)
              ├── queue_api_1cpu
              └── queue_procedures
```

The testspec's macro expansion makes each `ZTEST(suite, fn)` land in its suite group
(`ZTEST_SUITE` itself expands to nothing). `doc/_scripts/testspec_scope.py` generates the
area, module and suite groups on every build; a group the sources define by hand wins, but
none of ours do any more — the zephyr branch carries no group blocks. Test ids are added to
the sources by `doc/_scripts/assign_testids.py` (by hand; ledger `doc/testids.yaml`).
Adding a test area means an entry in `doc/test-scope.yaml`, then running that script.

Upstream's own
`tests_kernel_{queue,fifo,lifo}` groups also appear (they say `@ingroup all_tests`); they are
upstream's, carry no test cases, and are left alone to keep the diff against upstream small.

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

### Documentation config (in `doc/`)
- `documents.yaml` — the document registry (read by zdocs)
- `needs_config.toml` — shared sphinx-needs types, links and fields
- `_doxygen/safety-api-groups.dox` — API group stubs
- `dox/*/Doxyfile.in`, `dox/*/mainpage.md` — Doxygen templates and introductions
- `api-documentation/queue_apis.rst` — Breathe pull for API doc
- `test-specification/`, `test-report/` — the sphinx-needs test spec and report
- `sdoc/requirements/` — requirements document (generated `req` needs; see Requirements generation)
- `sdoc/safety-committee/` — governance, rendered by `strictdoc_runner`
- `sandbox/` — superseded experiments, kept for reference
- `_extensions/strictdoc_runner.py` — runs `strictdoc export` on Sphinx build-init (safety-committee only)
- `_scripts/` — Doxygen input filters (`FILTER_PATTERNS`)

### Requirements (in `../doc/reqmgmt/docs/software_requirements/`)
- `queues.sdoc` — `ZEP-SRS-20-*`
- `lifos.sdoc` — `ZEP-SRS-23-*`
- `fifos.sdoc` — `ZEP-SRS-24-*`

## Open Work Items

Tracked in `../claude/traceability-reconciliation/next-session.md` (phase plan, decisions,
work items) and `../claude/traceability-reconciliation/issues/` (deferred issues).
