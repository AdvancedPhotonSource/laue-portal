"""Short completed-stack notification entry point, suitable for a DM hook over SSH."""

import argparse
import json
import time
from pathlib import Path

from laue_portal.workflows.live import get_live, notify_ready, request_action, session_status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("status", "stop"):
        sub = commands.add_parser(command)
        sub.add_argument("session_id", type=int)
    notify = commands.add_parser("notify")
    notify.add_argument("session_id", type=int)
    notify.add_argument("path")
    notify.add_argument("--complete", action="store_true", help="Assert detector/transfer completion")
    replay = commands.add_parser("replay", help="Rehearse explicit arrivals from already closed files")
    replay.add_argument("session_id", type=int)
    replay.add_argument("--points", required=True)
    replay.add_argument("--interval", type=float, default=51)
    replay.add_argument("--closed-inputs", action="store_true", required=True)
    args = parser.parse_args()
    if args.command == "notify":
        print(json.dumps({"arrival_id": notify_ready(args.session_id, args.path, complete=args.complete)}))
    elif args.command == "replay":
        from laue_portal.workflows.files import normalize_integer_range

        if args.interval < 0:
            parser.error("Replay interval cannot be negative")
        live = get_live(args.session_id)
        _, points = normalize_integer_range(args.points, "replay points")
        template = (live.recipe["reconstruction"] or live.recipe["indexing"])["filename_prefixes"][0]
        started = time.monotonic()
        for index, point in enumerate(points):
            time.sleep(max(0, started + index * args.interval - time.monotonic()))
            path = Path(live.recipe["input_directory"]) / (template % point)
            print(
                json.dumps({"point": point, "arrival_id": notify_ready(args.session_id, path, complete=True)}),
                flush=True,
            )
    elif args.command == "stop":
        request_action(args.session_id, args.command)
    else:
        print(json.dumps(session_status(args.session_id), indent=2))


if __name__ == "__main__":
    main()
