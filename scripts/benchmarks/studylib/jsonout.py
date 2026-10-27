# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Deterministic JSON output: the same object gives the same bytes.

Indent 2, keys in the order of the object, and a list of scalars (or a
list of short lists of scalars, such as histogram bins) on one line, so
that the files stay readable and small.
"""

import hashlib
import json
import os
from pathlib import Path


def _scalar(x):
    return not isinstance(x, (dict, list))


def dumps(obj, ind=0):
    pad = "  " * ind
    if isinstance(obj, dict):
        if not obj:
            return "{}"
        items = [f"{pad}  {json.dumps(k)}: {dumps(v, ind + 1)}" for k, v in obj.items()]
        return "{\n" + ",\n".join(items) + f"\n{pad}}}"
    if isinstance(obj, list):
        if all(_scalar(x) for x in obj):
            return json.dumps(obj)
        if all(isinstance(x, list) and all(_scalar(y) for y in x) for x in obj):
            return "[\n" + ",\n".join(f"{pad}  {json.dumps(x)}" for x in obj) + f"\n{pad}]"
        return "[\n" + ",\n".join(f"{pad}  {dumps(x, ind + 1)}" for x in obj) + f"\n{pad}]"
    return json.dumps(obj)


def write(path, obj):
    """Write obj to path (a reader sees the old or the new file, never a part); return the sha256 of the bytes."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (dumps(obj) + "\n").encode()
    if not path.exists() or path.read_bytes() != data:
        tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        tmp.write_bytes(data)
        tmp.replace(path)
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())
