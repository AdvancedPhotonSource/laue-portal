"""Publish run support files without overwriting a previous run's files.

A file is written completely to ``partial_path(final)`` in the same directory
and then published by a hard link, which fails atomically when ``final``
already exists. ``overwrite=True`` uses ``os.replace`` instead. The same
convention is used by lauelab for scientific output.
"""

import errno
import os
from pathlib import Path

PARTIAL_SUFFIX = ".partial"
_LINK_UNSUPPORTED = {errno.EPERM, errno.ENOTSUP, errno.EOPNOTSUPP, errno.EXDEV, errno.EMLINK}


def partial_path(final: str | os.PathLike[str]) -> Path:
    final = Path(final)
    return final.with_name(final.name + PARTIAL_SUFFIX)


def publish_file(partial: str | os.PathLike[str], final: str | os.PathLike[str], *, overwrite: bool = False) -> Path:
    """Rename ``partial`` to ``final``; refuse to clobber unless ``overwrite``."""

    partial = Path(partial)
    final = Path(final)
    if partial.parent != final.parent:
        raise ValueError(f"{partial} and {final} must be in the same directory")
    if not partial.exists():
        raise FileNotFoundError(errno.ENOENT, "partial file is missing", str(partial))
    if overwrite:
        os.replace(partial, final)
        return final
    try:
        os.link(partial, final)
    except FileExistsError:
        raise
    except OSError as error:
        if error.errno not in _LINK_UNSUPPORTED:
            raise
        if final.exists():
            raise FileExistsError(errno.EEXIST, "File exists", str(final)) from None
        os.replace(partial, final)
        return final
    os.unlink(partial)
    return final


def discard_partial(final: str | os.PathLike[str]) -> None:
    """Remove a leftover partial file, ignoring its absence."""

    try:
        partial_path(final).unlink()
    except FileNotFoundError:
        pass
