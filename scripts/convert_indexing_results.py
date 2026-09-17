#!/usr/bin/env python3
"""Convert historical indexing XML results to lauelab results files.

Examples::

    python scripts/convert_indexing_results.py --dry-run --all
    python scripts/convert_indexing_results.py I12 I13 40-46 --report report.json
    python scripts/convert_indexing_results.py --all --destination-root /writable/results

The database named in config.yaml is used unless ``--db`` is given. Sources are
never modified; ``--destination-root`` places ``index_<id>/output.h5`` under a
writable root when the historical output directories are read-only.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("ids", nargs="*", help="Indexing identities: I12, 12, or 3-7 ranges")
    parser.add_argument("--all", action="store_true", help="Every indexing run in the database")
    parser.add_argument("--dry-run", action="store_true", help="Report what would happen; write nothing")
    parser.add_argument(
        "--destination-root", type=Path, default=None, help="Write index_<id>/output.h5 under this directory"
    )
    parser.add_argument(
        "--geometry", type=Path, default=None, help="Geometry XML recorded instead of the one named in the XML"
    )
    parser.add_argument(
        "--replace-invalid",
        action="store_true",
        help="Replace an existing destination that is not a valid results file",
    )
    parser.add_argument("--report", type=Path, default=None, help="Write a machine-readable JSON report here")
    parser.add_argument("--db", type=Path, default=None, help="SQLite database (default: db_file from config.yaml)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if bool(args.ids) == args.all:
        raise SystemExit("Give indexing identities or --all, not both and not neither")

    from sqlalchemy import create_engine, event

    from laue_portal.database import session_utils
    from laue_portal.services import indexing_results

    if args.db is not None:
        if not args.db.is_file():
            raise SystemExit(f"Database does not exist: {args.db}")
        engine = create_engine(f"sqlite:///{args.db}")
        event.listen(engine, "connect", session_utils.enable_sqlite_pragmas)
    else:
        engine = session_utils.get_engine()

    ids = None if args.all else indexing_results.iter_ids(args.ids)
    report = indexing_results.convert_indexing_results(
        ids,
        engine=engine,
        dry_run=args.dry_run,
        destination_root=str(args.destination_root) if args.destination_root else None,
        geometry=str(args.geometry) if args.geometry else None,
        replace_invalid=args.replace_invalid,
        progress=lambda outcome: print(f"I{outcome.indexing_id}: {outcome.outcome}", file=sys.stderr, flush=True),
    )
    print(report.format_text())
    if args.report is not None:
        indexing_results.write_report(report, args.report)
        print(f"Report written to {args.report}")
    counts = report.counts()
    return 1 if counts.get("failed") else 0


if __name__ == "__main__":
    sys.exit(main())
