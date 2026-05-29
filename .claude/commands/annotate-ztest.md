---
description: Annotate ZTEST functions and static helpers with structured Doxygen comments for the safety test specification
allowed-tools: Read, Edit, Bash
---

# Annotate ZTest Functions for Test Specification

Annotate one or more ZTEST functions (and any related static helpers) in a
Zephyr test source file with structured Doxygen comments suitable for
extraction into the safety test specification.

Apply the rules below to every function named in $ARGUMENTS, or — if no
arguments are given — to every undocumented ZTEST in the current file.

---

## Group hierarchy

Every test source file lives inside a four-level Doxygen group hierarchy.
Understand the full chain before touching any file:

```
all_tests                        doc/_doxygen/safety-test-groups.dox
  └── kernel_queue_tests         doc/_doxygen/safety-test-groups.dox
        └── kernel_queue_module  tests/.../main.c   (Test Module — one per test application)
              ├── queue_api      tests/.../main.c   (ZTEST_SUITE)
              └── queue_api_1cpu tests/.../main.c   (ZTEST_SUITE)
```

Key rules:
- **Test Module** (`*_module`) is always defined in `main.c` alongside the
  `ZTEST_SUITE` macros, and is `@ingroup` the suite-collection group from
  `safety-test-groups.dox`.
- **Test suites** (`@defgroup` for each `ZTEST_SUITE`) are defined in
  `main.c` and are `@ingroup` the module group.
- **Shared Test Procedures** sub-groups (`*_procedures`) are defined at the
  top of the `.c` source file that contains the static helpers, one per
  suite that uses them. Their group IDs follow the pattern
  `{suite_name}_procedures`.

---

## ZTEST docstring template

Place a leading `/** ... */` block immediately before each `ZTEST(...)` macro.
Use standard Zephyr comment style throughout: every continuation line starts
with ` * ` (space-asterisk-space).

```c
/**
 * @brief <One sentence — states the BEHAVIOUR verified, not the test
 *         structure. Subject is the system under test, not the test itself.>
 *
 * @details
 * <2–4 sentences: the scenario, what dispatch/API property is exercised,
 * and why it matters for correctness. Reference which requirements this
 * verifies if not already covered by the verbatim block below.>
 *
 * @verbatim embed:rst
 * - :external+req:ref:`zep-srs-XX-N`
 * @endverbatim
 *
 * @see <references to the API functions used in the test> 
 */
ZTEST(suite_name, test_name)
{
```

- Omit the `@verbatim` block if no requirement UID applies.
- `@see` must list every `k_*` API called directly or via named
  procedures; do not list internal static helpers.

---

## In-body @par blocks

With `HIDE_IN_BODY_DOCS = NO` set in the testspec doxyfile, `/** ... */`
comments inside a function body are appended to that function's detailed
description in the HTML output. Use this to place structured step
documentation immediately before the code it describes.

Add one block per phase. Use `-#` for numbered list items.

```c
ZTEST(suite_name, test_name)
{
    /** @par Arrange
     * -# <Step 1 description.>
     * -# <Step 2 description.>
     */
    /* arrange code */

    /** @par Act
     * -# <Action 1 — what event or stimulus is applied.>
     * -# <Action 2.>
     */
    /* act code */

    /** @par Assert
     * -# <Expected outcome 1 — be explicit about values, pointers, or
     *    thread results. If assertions live inside a helper thread, name
     *    the function and state what it checks.>
     * -# <Expected outcome 2.>
     */
    /* assert / join code */

    /** @par Teardown
     * -# <Resource or state restored, if any.>
     */
    /* teardown code */
}
```

- Omit `@par Teardown` when there is nothing to restore.
- When assertions are inside consumer/helper threads, the Assert block must
  name those functions and spell out the expected values — do not write
  "see helper function".

---

## Static helper classification (Option D)

Classify every static function in the file before annotating:

| Category | Examples | Treatment |
|---|---|---|
| **Data operations** — exercise multiple API calls, may contain `zassert_*` | `tqueue_append`, `tqueue_get` | Document as a **Test Procedure** |
| **Scenario drivers** — set up a full multi-context scenario | `tqueue_thread_thread`, `tqueue_alloc` | Document as a **Test Procedure** |
| **Asserting thread entries** — `zassert_*` inside thread body | `low_prio_wait_for_queue`, `high_prio_t1_wait_for_queue` | Document as a **Test Procedure** |
| **Pure dispatch mechanics** — thin wrappers with no logic or assertions | `tIsr_entry_append`, `tIsr_entry_get`, `tThread_entry` | Suppress with `@cond` / `@endcond` |

---

## Test Procedure docstring template

```c
/**
 * @brief <One sentence — what this procedure does or verifies.>
 *
 * @details
 * <Describe steps and/or assertions. For asserting procedures list the
 * expected values explicitly. Use -# lists when order matters.>
 *
 * @pre <Precondition the caller must satisfy, if any.>
 *
 * @param <name> <description>
 *
 * @see k_*(), ...
 *
 * @ingroup <suite_name>_procedures
 * @ingroup <suite_name_2>_procedures   (repeat for every suite that uses this)
 */
static void helper_name(...)
```

- Do NOT add `@par Arrange/Act/Assert` blocks to procedures — that pattern
  is reserved for `ZTEST` test cases.
- `@pre` is required whenever the procedure assumes a specific queue state
  (e.g., "queue must have been populated by `tqueue_append()`").

---

## Suppressing pure mechanics

Wrap dispatch-only helpers with `@cond` so they are excluded from the
Doxygen output entirely:

```c
/** @cond INTERNAL */
static void tIsr_entry_append(const void *p)
{
    tqueue_append((struct k_queue *)p);
}

static void tIsr_entry_get(const void *p)
{
    tqueue_get((struct k_queue *)p);
}
/** @endcond */
```

---

## Procedure group definitions

The `*_procedures` groups are defined at the top of the source file (after
`@file`, before the first `#include`), NOT in `safety-test-groups.dox`:

Example:
```c
/**
 * @defgroup queue_api_procedures Shared Test Procedures
 * @ingroup queue_api
 * @brief Reusable helper procedures invoked by queue_api test cases.
 */

/**
 * @defgroup queue_api_1cpu_procedures Shared Test Procedures
 * @ingroup queue_api_1cpu
 * @brief Reusable helper procedures invoked by queue_api_1cpu test cases.
 */
```

Add one `@defgroup` block per suite that has procedures in this file.
If a procedure is shared across suites, give it a separate `@ingroup` line
for each suite's procedure group.

---

## Whitespace and style

- All Doxygen comment blocks use standard Zephyr style: `/**` to open,
  ` * ` prefix on every continuation line, ` */` to close.
- Function body uses **tabs** for indentation; in-body `/** ... */` blocks
  are indented with one tab.
- No Unicode characters (em-dashes etc.) in C source comments — use `--`
  instead.
- `@brief` must fit on one line; keep it under ~80 characters.

---

## Checklist before finishing

- [ ] Every `ZTEST` has a leading docstring with `@brief`, `@details`,
      optional `@verbatim` requirement refs, and `@see`.
- [ ] Every `ZTEST` body has `@par Arrange`, `@par Act`, `@par Assert`
      (and `@par Teardown` if needed) immediately before the corresponding
      code.
- [ ] Asserting/scenario helpers have procedure docstrings with `@ingroup`
      for every suite that uses them.
- [ ] Pure dispatch wrappers are wrapped in `/** @cond INTERNAL */`.
- [ ] Build target `doxygen-zephyr-safety-testspec` runs clean after changes:
      `cmake --build /wrk/z/ws-safety/bdoc --target doxygen-zephyr-safety-testspec`
- [ ] No new unresolved `@see` warnings in the build output.
