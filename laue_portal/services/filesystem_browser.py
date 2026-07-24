"""Server-side filesystem operations for reusable path pickers."""

from datetime import datetime
from pathlib import Path

DEFAULT_LISTING_LIMIT = 1000


def normalize_path(path):
    """Return a normalized absolute path without requiring it to exist."""
    if not path or not str(path).strip():
        raise ValueError("Enter a path to browse.")
    return Path(str(path).strip()).expanduser().resolve()


def list_directory(path, extensions=None, limit=DEFAULT_LISTING_LIMIT):
    """List one directory level, with directories before selectable files."""
    directory = normalize_path(path)
    if not directory.is_dir():
        raise ValueError("The path is not an accessible directory.")

    normalized_extensions = {extension.lower() for extension in extensions or []}
    entries = []
    try:
        children = sorted(directory.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))
        for child in children:
            if len(entries) >= limit:
                break
            try:
                is_directory = child.is_dir()
                is_file = child.is_file()
                if not is_directory and not is_file:
                    continue
                if is_file and normalized_extensions and child.suffix.lower() not in normalized_extensions:
                    continue
                stat = child.stat()
            except OSError:
                continue

            entries.append(
                {
                    "name": child.name,
                    "path": str(child.resolve()),
                    "type": "Directory" if is_directory else "File",
                    "size": None if is_directory else stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
    except OSError as exc:
        raise ValueError("The directory cannot be read.") from exc

    return str(directory), entries, len(entries) == limit


def validate_selection(path, mode="file", extensions=None, max_file_size_mb=None):
    """Validate and normalize a file or directory selected by a client."""
    selected = normalize_path(path)
    if mode == "directory":
        if not selected.is_dir():
            raise ValueError("Select an accessible directory.")
        return str(selected)

    if mode != "file":
        raise ValueError(f"Unsupported selection mode: {mode}")
    if not selected.is_file():
        raise ValueError("Select an accessible regular file.")

    normalized_extensions = {extension.lower() for extension in extensions or []}
    if normalized_extensions and selected.suffix.lower() not in normalized_extensions:
        allowed = ", ".join(sorted(normalized_extensions))
        raise ValueError(f"Select a file with one of these extensions: {allowed}.")

    if max_file_size_mb is not None and selected.stat().st_size > max_file_size_mb * 1024 * 1024:
        raise ValueError(f"The selected file exceeds the {max_file_size_mb} MB limit.")
    return str(selected)


def read_selected_file(path, extensions=None, max_file_size_mb=None):
    """Validate a selected file immediately before reading it."""
    selected = validate_selection(
        path,
        mode="file",
        extensions=extensions,
        max_file_size_mb=max_file_size_mb,
    )
    try:
        return Path(selected).read_bytes()
    except OSError as exc:
        raise ValueError("The selected file could not be read.") from exc
