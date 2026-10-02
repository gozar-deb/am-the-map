"""Shared safety helpers for path components and directory bounds."""
from __future__ import annotations

from pathlib import Path


def sanitize_id(value: str, field_name: str = "id") -> str:
    """Raise ValueError if `value` isn't safe to use as a single path
    component (no separators, no traversal, not empty)."""
    if not value or not value.strip():
        raise ValueError(f"{field_name} must not be empty.")
    if "/" in value or "\\" in value:
        raise ValueError(f"Invalid {field_name} {value!r}: path separators are not allowed.")
    if value in (".", ".."):
        raise ValueError(f"Invalid {field_name} {value!r}.")
    if value.startswith("."):
        raise ValueError(f"Invalid {field_name} {value!r}: must not start with '.'.")
    return value


def safe_resolve_dir(path_str: str, field_name: str = "path") -> Path:
    """Resolve a user-supplied directory path and reject obvious traversal.

    Allows absolute paths (needed for import/export on the operator's machine)
    but rejects paths that resolve outside a reasonable root when they contain
    ``..`` segments that escape after resolve. Also rejects empty strings.
    """
    if not path_str or not str(path_str).strip():
        raise ValueError(f"{field_name} must not be empty.")
    raw = Path(path_str).expanduser()
    try:
        resolved = raw.resolve(strict=False)
    except (OSError, RuntimeError) as e:
        raise ValueError(f"Invalid {field_name}: {e}") from e
    # Block null bytes and other control characters
    if "\x00" in str(resolved):
        raise ValueError(f"Invalid {field_name}: null byte not allowed.")
    return resolved
