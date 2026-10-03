# Zephyr Safety Documentation

This repository builds a set of safety documents for the Zephyr RTOS kernel.
The documents trace each software requirement to its design, its code and its
tests:

- **Requirements:** the Zephyr kernel requirements (StrictDoc), as one need per
  requirement.
- **Architecture:** the design elements of Zephyr's kernel documentation and
  the kernel-internal implementation.
- **API documentation:** the safety-scope public API, from Doxygen, with the
  requirements each function satisfies.
- **Test specification:** one test case per Zephyr test (`ZTEST`), with the
  requirements it verifies.
- **Test report:** the results of a twister run, and the coverage adequacy of
  each requirement.
- **Safety Committee:** governance documents of the Zephyr safety committee.

The build engine is [zdocs](https://github.com/tiacsys/zdocs). It builds Sphinx
(sphinx-needs) and Doxygen documents as one set, with cross-references in both
directions.

## Repository layout

| Path | Content |
|---|---|
| `west.yml` | The west manifest of the workspace: Zephyr, the requirements, zdocs and the other projects |
| `doc/documents.yaml` | The document registry: one entry per document |
| `doc/specification/` | Requirements, architecture, API documentation and test specification |
| `doc/verification/` | Test report |
| `doc/governance/` | Safety Committee |
| `doc/dox/` | The Doxygen projects |
| `doc/test-scope.yaml` | The Zephyr test modules in the test specification |
| `doc/_scripts/`, `doc/_extensions/` | Generators, checks and Sphinx extensions of this document set |

## Prerequisites

- Linux, Git and Python 3.12.
- CMake 3.20 or later.
- Doxygen 1.16 or later. The documents use the native `\verifies` and
  `\satisfies` commands of Doxygen 1.16. Most distributions ship an older
  version: use the release binary from <https://www.doxygen.nl/download.html>.
- Graphviz (`dot`).
- For PDF output only: `latexmk` and XeLaTeX.

No Zephyr SDK and no toolchain are necessary to build the documents.

## Build the documents

1. Make a workspace folder and a Python virtual environment:

   ```sh
   mkdir zephyr-safety-ws && cd zephyr-safety-ws
   python3 -m venv .venv
   source .venv/bin/activate
   pip install west
   ```

2. Get the workspace with west. The Safety Committee sources are in projects
   that need access rights (SSH). West leaves them out by default. If you have
   access, add the group before `west update`:

   ```sh
   west init -m https://github.com/tobiaskaestner/zephyr-safety --mr main
   west config manifest.group-filter -- +safety-committee
   west update
   ```

   Without the `safety-committee` group, the build leaves the Safety Committee
   document out and says so at configure time ("Safety Committee document left
   out"). All other documents build as usual. To choose yourself, configure with
   `-DSAFETY_DOC_COMMITTEE=ON` or `-DSAFETY_DOC_COMMITTEE=OFF`.

3. Install the Python packages. The Zephyr file is a lock file with hashes, so
   it goes in its own `pip install`:

   ```sh
   pip install -r zephyr/doc/requirements.txt
   pip install -r tools/zdocs/sphinx/requirements-doc.txt
   ```

4. Configure and build:

   ```sh
   export ZEPHYR_BASE=$PWD/zephyr
   cmake -S safety/doc -B build/doc
   cmake --build build/doc --target doc-index
   cmake --build build/doc --target all-docs
   ```

   `doc-index` builds the indexes of all documents first. The documents link to
   each other, so the final build of each document needs all indexes.
   `all-docs` builds every document and then runs the checks: the
   cross-document links (`doc-check`), and that each test in
   `doc/test-scope.yaml` is in the test specification (`testspec-check`).

5. Open the result. Each document is at
   `build/doc/deploy/html/<document>/index.html`. To serve the set:

   ```sh
   python -m http.server --directory build/doc/deploy/html 8000
   ```

   Then open <http://localhost:8000/requirements/>.

## Optional inputs

- **Test results.** Without a twister run, the test report shows "twister XML
  not found" instead of results. To include results, run twister over the modules of
  `doc/test-scope.yaml`, and give its output directory at configure time:

  ```sh
  cmake -S safety/doc -B build/doc -DZDOCS_TWISTER_OUT=<twister output directory>
  ```

- **Coverage adequacy.** The adequacy page needs a per-test coverage run
  (`west twister --coverage --coverage-tool lcov --coverage-per-test`). Give its
  output directory with `-DZDOCS_COVERAGE_OUT=<directory>`. The run name on
  `doc/verification/test-report/adequacy.rst` (`:run:`) must match that run.

- **PDF.** A document with a `latex` builder in `doc/documents.yaml` has the
  target `<document>-latex`, for example:

  ```sh
  cmake --build build/doc --target requirements-latex
  ```

  The PDF is in `build/doc/deploy/pdf/<document>/`.

## Licence

The files carry SPDX licence headers (mostly Apache-2.0).
