# timeout-skiplist-1m

## Question

As `timeout-backends-1m`, for the SKIPLIST timeout queue backend.

## Method

As `timeout-backends-1m`, but only in the tree `ws-up`: the SKIPLIST
backend is only in this tree.

| Point | Settings | Why |
|---|---|---|
| `skiplist` | `TIMEOUT_BACKEND_SKIPLIST` | A backend under test. |

The axis has the name `backend`, as in `timeout-backends-1m`.

## References

- `../ex-timeout-backends-1m/experiment.md`: the other backends and the DLIST reference.
