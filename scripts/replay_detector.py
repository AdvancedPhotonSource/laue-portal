#!/usr/bin/env python3
"""Simulate closed detector files by copying immutable inputs at a selected rate.

DM should watch the destination directory. A private temporary file is flushed,
closed, and published exclusively under its final filename. Existing inputs and
destination files are never overwritten. This tool does not notify the portal.
"""

import argparse
import json
import math
import os
import re
import shutil
import tempfile
import time
import uuid
from pathlib import Path


def publish(source, destination, temporary_directory):
    temporary = Path(temporary_directory) / f".{destination.name}.{uuid.uuid4().hex}.part"
    try:
        with source.open("rb") as incoming, temporary.open("xb") as output:
            shutil.copyfileobj(incoming, output, length=1024 * 1024)
            output.flush()
        os.link(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--filename", required=True, help="One filename template containing one %%d index")
    parser.add_argument("--fps", type=float, default=10)
    parser.add_argument("--first", type=int)
    parser.add_argument("--count", type=int)
    parser.add_argument(
        "--temporary-directory",
        type=Path,
        help="Writable directory on the destination filesystem, outside the entire DAQ watch tree (default: source parent)",
    )
    args = parser.parse_args()
    if not math.isfinite(args.fps) or args.fps <= 0 or args.count is not None and args.count <= 0:
        parser.error("FPS and count must be positive")
    if args.filename.count("%d") != 1 or Path(args.filename).name != args.filename:
        parser.error("Filename must contain one %d index and no directories")
    source = args.source.resolve(strict=True)
    destination = args.destination.resolve()
    if source == destination or destination.is_relative_to(source) or source.is_relative_to(destination):
        parser.error("Source and destination must be separate directories")
    pattern = re.compile(re.escape(args.filename).replace("%d", r"(\d+)"))
    files = []
    for path in source.iterdir():
        match = pattern.fullmatch(path.name)
        if match and path.is_file() and (args.first is None or int(match[1]) >= args.first):
            files.append((int(match[1]), path))
    files.sort()
    if args.count is not None:
        if len(files) < args.count:
            parser.error("Not enough matching source files")
        files = files[: args.count]
    if not files:
        parser.error("No matching source files")
    destination.mkdir(parents=True, exist_ok=True)
    if any((destination / path.name).exists() for _, path in files):
        parser.error("Replay destination already contains selected files; choose a fresh folder")
    temporary_parent = (args.temporary_directory or source.parent).resolve(strict=True)
    if temporary_parent.is_relative_to(destination):
        parser.error("Temporary directory must be outside the DAQ watch tree")
    if temporary_parent.stat().st_dev != destination.stat().st_dev:
        parser.error("Temporary and destination directories must be on the same filesystem")
    with tempfile.TemporaryDirectory(prefix=".laue-replay-", dir=temporary_parent) as temporary:
        started = time.monotonic()
        for index, (_, path) in enumerate(files):
            time.sleep(max(0, started + index / args.fps - time.monotonic()))
            publish(path, destination / path.name, temporary)
            if (index + 1) % max(1, round(args.fps)) == 0 or index + 1 == len(files):
                print(
                    json.dumps(
                        {
                            "copied": index + 1,
                            "total": len(files),
                            "elapsed_seconds": round(time.monotonic() - started, 3),
                        }
                    ),
                    flush=True,
                )


if __name__ == "__main__":
    main()
