"""Distribute one frozen request across PBS nodes and publish one portal result.

Only the main thread calls MPI. Rank-private writers and locks live outside
results/, so the return transfer contains one catalog or indexing result.
Rank zero owns the existing runner's aggregate summary, heartbeat and lock.
Failed shard outputs remain on Eagle for inspection; they are never mistaken
for a complete result. The normal shared cancellation file reaches every rank.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import threading
import traceback
from dataclasses import replace
from pathlib import Path
from time import perf_counter

from lauelab.indexing import merge_results_files, merge_xml_files

from laue_portal.processing import runner
from laue_portal.processing.compute import RunOutcome
from laue_portal.processing.merge import merge_reconstruction
from laue_portal.workflows.manifest import FailureRecord


def partition(entries, *, kind, rank, size, ranks_per_node):
    """Keep all raw points local; split each reconstructed point's depths locally."""
    if size < 1 or ranks_per_node < 1 or size % ranks_per_node or not 0 <= rank < size:
        raise ValueError("Invalid MPI rank layout")
    if kind == "wire_reconstruction":
        if ranks_per_node != 1:
            raise ValueError("Reconstruction uses one coordinator per node")
        return entries[rank::size]
    nodes = size // ranks_per_node
    node, group = divmod(rank, ranks_per_node)
    points = {}
    assigned = []
    for entry in entries:
        key = (entry.source, entry.point_id)
        point = points.setdefault(key, len(points))
        depth = entry.depth_index if entry.depth_index is not None else entry.index
        if point % nodes == node and depth % ranks_per_node == group:
            assigned.append(entry)
    return assigned


def _relay_progress(directory, size, hooks, stop):
    while not stop.is_set():
        succeeded = failed = 0
        for rank in range(size):
            path = directory / f"rank-{rank:04d}" / "progress.json"
            if path.exists():
                counts = json.loads(path.read_text())  # Each rank publishes atomically.
                succeeded += counts["n_succeeded"]
                failed += counts["n_failed"]
        hooks.report_progress(succeeded=succeeded, failed=failed)
        stop.wait(2)


def distributed(directory, request, entries, plan, comm, hooks=None):
    rank, size = comm.Get_rank(), comm.Get_size()
    ranks_per_node = (
        int(plan["execution"].get("indexing_ranks_per_node", 1)) if request.kind == "lauego_indexing" else 1
    )
    if size != int(plan["pbs"]["nodes"]) * ranks_per_node:
        raise ValueError("MPI size disagrees with frozen PBS resource request")
    shard_root = Path(request.run_directory).parent / "shards"
    assigned = partition(entries, kind=request.kind, rank=rank, size=size, ranks_per_node=ranks_per_node)
    document = json.loads(json.dumps(request.document))
    document["output"]["xml"] = "output.xml"  # Every rank must have a private XML writer.
    shard_request = replace(
        request,
        run_directory=str(shard_root / f"rank-{rank:04d}"),
        n_inputs=len(assigned),
        document=document,
    )
    relay_stop = threading.Event()
    relay = None
    if hooks is not None:
        relay = threading.Thread(target=_relay_progress, args=(shard_root, size, hooks, relay_stop), daemon=True)
        relay.start()
    try:
        try:
            shard = runner.run(
                directory,
                request=shard_request,
                entries=assigned,
                compute=(lambda *_: RunOutcome(0, 0)) if not assigned else None,
            )
        except Exception as error:
            # Even a rejected rank directory must participate in the final gather.
            shard = {
                "status": "Failed",
                "host": platform.node(),
                "message": str(error),
                "counters": {"n_inputs": len(assigned), "n_succeeded": 0, "n_failed": 0, "n_indexed": None},
                "provenance": {},
                "artifacts": {},
            }
        shards = comm.gather(shard, root=0)
    finally:
        if relay is not None:
            relay_stop.set()
            relay.join()
    if rank != 0:
        return None
    succeeded = sum(s["counters"]["n_succeeded"] for s in shards)
    failed = sum(s["counters"]["n_failed"] for s in shards)
    indexed = sum(s["counters"]["n_indexed"] or 0 for s in shards) if request.kind == "lauego_indexing" else None
    outcome = RunOutcome(
        succeeded,
        failed,
        n_indexed=indexed,
        provenance={
            **shards[0]["provenance"],
            "mpi_nodes": int(plan["pbs"]["nodes"]),
            "mpi_ranks": size,
            "mpi_ranks_per_node": ranks_per_node,
            "rank_hosts": [s["host"] for s in shards],
        },
        warnings=[warning for shard in shards for warning in shard.get("warnings", [])],
    )
    # Retain each coordinator's counters/host/errors without retransferring its science files.
    runner.write_json_file(Path(request.run_directory) / "ranks.json", shards)
    for number, shard in enumerate(shards):
        if shard.get("failure_report"):
            report = shard_root / f"rank-{number:04d}" / shard["failure_report"]
            with open(report, encoding="utf-8") as handle:
                for line in handle:
                    hooks.record_failure(FailureRecord.from_dict(json.loads(line)))
    hooks.report_progress(succeeded=succeeded, failed=failed)
    hooks.report_outcome(outcome)
    if any(s["status"] != "Finished" for s in shards):
        outcome.stopped = all(s["status"] in {"Finished", "Cancelled"} for s in shards)
        outcome.validation_error = None if outcome.stopped else "At least one MPI rank failed; inspect ranks.json"
        return outcome
    # Ensure the launcher actually distributed coordinators across the requested hosts.
    if len({s["host"] for s in shards}) != int(plan["pbs"]["nodes"]):
        raise ValueError("MPI coordinators did not run on the requested number of nodes")
    for first in range(0, size, ranks_per_node):
        if len({s["host"] for s in shards[first : first + ranks_per_node]}) != 1:
            raise ValueError("MPI rank ordering does not keep each indexing group on one node")
    active = [s for s in shards if s["counters"]["n_inputs"]]
    output = Path(request.run_directory)
    if request.kind == "wire_reconstruction":
        path = output / "reconstruction" / "scan.h5"
        summary = merge_reconstruction([s["artifacts"]["reconstruction"] for s in active], path, entries)
        outcome.artifacts["reconstruction"] = str(path)
        outcome.provenance["reconstruction_summary"] = {
            "run_status": summary.run_status,
            "n_points": summary.n_points,
            "n_complete": summary.n_complete,
            "n_failed": summary.n_failed,
            "n_unattempted": summary.n_unattempted,
        }
    else:
        path = output / "output.h5"
        # Each writer preserves its partition's input order. File concatenation
        # follows rank order, so validate that exact order against the manifest.
        frame_ids = [
            entry.input_id
            for number in range(size)
            for entry in partition(entries, kind=request.kind, rank=number, size=size, ranks_per_node=ranks_per_node)
        ]
        started = perf_counter()
        summary = merge_results_files([s["artifacts"]["results"] for s in active], path, frame_ids=frame_ids)
        outcome.provenance["indexing_hdf5_merge_seconds"] = perf_counter() - started
        outcome.artifacts["results"] = str(path)
        outcome.provenance["results_summary"] = {
            "n_frames": summary.n_frames,
            "n_peaks": summary.n_peaks,
            "n_patterns": summary.n_patterns,
            "n_assignments": summary.n_assignments,
        }
        xml = request.output.get("xml") or "output.xml"
        xml = Path(xml) if os.path.isabs(xml) else output / xml
        try:
            started = perf_counter()
            merge_xml_files([s["artifacts"]["xml"] for s in active], xml, n_steps=succeeded)
            outcome.provenance["indexing_xml_merge_seconds"] = perf_counter() - started
            outcome.artifacts["xml"] = str(xml)
        except Exception as error:
            outcome.warnings.append(f"Merged XML unavailable: {error}")
    outcome.summary = f"{succeeded} inputs completed across {plan['pbs']['nodes']} nodes ({size} MPI ranks)"
    return outcome


def main():
    from mpi4py import MPI

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory")
    args = parser.parse_args()
    comm = MPI.COMM_WORLD
    try:
        if not os.environ.get("PBS_JOBID"):
            raise RuntimeError("The MPI runner requires a PBS allocation")
        directory = Path(args.directory)
        plan = json.loads((directory / "bdp.json").read_text())
        request, entries = runner.load_request(directory, plan)
        if comm.Get_rank() == 0:
            summary = runner.run(
                directory,
                request=request,
                entries=entries,
                compute=lambda req, inputs, hooks: distributed(directory, req, inputs, plan, comm, hooks),
            )
            result = 0 if summary["status"] == "Finished" else 1
        else:
            distributed(directory, request, entries, plan, comm)
            result = None
        return comm.bcast(result, root=0)
    except BaseException:
        traceback.print_exc()
        comm.Abort(1)  # Never leave peers blocked in a collective after one rank fails.


if __name__ == "__main__":
    raise SystemExit(main())
