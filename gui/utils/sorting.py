"""Shared sorting helpers for GUI file/path lists."""

from __future__ import annotations

import os
import re
from typing import Iterable, TypeVar


T = TypeVar("T", str, os.PathLike)


def natural_basename_sort_key(value: str | os.PathLike) -> tuple[tuple[int, object], ...]:
    """Return a case-insensitive natural sort key for a path basename.

    Args:
        value: Filename or path-like value to sort.

    Returns:
        Tuple key where numeric chunks from the basename compare as integers.
    """
    basename = os.path.basename(os.fspath(value)).casefold()
    chunks = re.split(r"(\d+)", basename)
    key: list[tuple[int, object]] = []
    for chunk in chunks:
        if not chunk:
            continue
        if chunk.isdigit():
            key.append((0, int(chunk)))
        else:
            key.append((1, chunk))
    return tuple(key)


def natural_sorted_by_basename(values: Iterable[T]) -> list[T]:
    """Sort filenames or paths naturally by basename, case-insensitively.

    Args:
        values: Iterable of filename or path-like values.

    Returns:
        List sorted by basename with numeric chunks compared as integers.
    """
    return sorted(values, key=natural_basename_sort_key)
