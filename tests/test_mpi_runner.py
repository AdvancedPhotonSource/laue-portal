"""Check actual lauelab shard outputs, not just launcher text or mocked writers."""

from __future__ import annotations

import copy
import json
from collections import Counter
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4
from xml.etree import ElementTree as ET

import h5py
import numpy as np
import pytest
from lauelab.indexing import InvalidResultsFile, merge_results_files, validate_results_file
from lauelab.reconstruct import validate_scan_file

from laue_portal.processing import runner
from laue_portal.processing.bdp import plan
from laue_portal.processing.bdp.pbs import build_script
from laue_portal.processing.merge import merge_reconstruction
from laue_portal.processing.mpi_runner import distributed, partition
from laue_portal.workflows.manifest import ManifestEntry
from tests.run_support import load_job
from tests.test_bdp import remote_run as remote_fixture
from tests.test_bdp import stage_fixture

remote_run = remote_fixture


def test_full_point_local_index_partition_covers_each_depth_once():
    entries = [
        ManifestEntry(p * 121 + d, f"{p}_{d}", f"/points/{p}.h5", 0, p, d, point_id=str(p), depth_index=d)
        for p in range(825)
        for d in range(121)
    ]
    assignments = [
        partition(entries, kind="lauego_indexing", rank=rank, size=16, ranks_per_node=4) for rank in range(16)
    ]
    assert Counter(entry.index for subset in assignments for entry in subset) == Counter(range(825 * 121))
    for rank, subset in enumerate(assignments):
        assert all(int(entry.point_id) % 4 == rank // 4 and entry.depth_index % 4 == rank % 4 for entry in subset)
    assert max(map(len, assignments)) - min(map(len, assignments)) <= 238


def _run_shards(document, entries, request, size):
    summaries = []
    for rank in range(size):
        subset = entries[rank::size]
        shard_document = copy.deepcopy(request.document)
        shard_document["output"]["xml"] = "output.xml"
        shard = replace(
            request,
            run_directory=str(Path(request.run_directory).parent / "shards" / str(rank)),
            n_inputs=len(subset),
            document=shard_document,
        )
        summary = runner.run(document["control_directory"], request=shard, entries=subset)
        assert summary["status"] == "Finished", summary
        summaries.append(summary)
    return summaries


def test_reconstruction_merge_keeps_global_point_order_links_and_indices(remote_run):
    engine, run, settings = remote_run
    document = plan.save_plan(load_job(engine, run.job_id), settings, str(uuid4()))
    stage_fixture(document, settings)
    request, entries = runner.load_request(document["control_directory"], document)
    # Reverse the shard completion order; the final catalog must use manifest order.
    summaries = list(reversed(_run_shards(document, entries, request, 2)))
    destination = Path(request.run_directory) / "reconstruction/scan.h5"
    merged = merge_reconstruction([s["artifacts"]["reconstruction"] for s in summaries], destination, entries)
    assert (merged.n_points, merged.n_complete) == (2, 2)
    with h5py.File(destination, "r") as catalog:
        assert list(catalog["points/point_ids"].asstr()[:]) == [entry.input_id for entry in entries]
        for entry, name in zip(entries, catalog["points/paths"].asstr()[:], strict=True):
            with h5py.File(destination.parent / name, "r") as point:
                assert point["entry1/reconstruction/manifest_index"][()] == entry.index
                assert np.prod(point["entry1/data/data"].shape) > 0
    # The complete directory is portable, with no links back into rank-private output.
    for path in destination.parent.rglob("*.h5"):
        assert not path.is_symlink()
    assert validate_scan_file(destination).n_complete == 2


def test_indexing_merge_matches_single_writer_values_and_rebases_offsets(remote_run, tmp_path, monkeypatch):
    from laue_portal.processing.compute.contract import RunRequest
    from tests.test_compute_lauego import CRYSTAL, GEOMETRY, _frames_dir, _parameters

    engine, run, settings = remote_run
    document = plan.save_plan(load_job(engine, run.job_id), settings, str(uuid4()))
    stage_fixture(document, settings)
    frames = _frames_dir(tmp_path)
    entries = [ManifestEntry(i, f"frame_{i + 1}", str(frames / f"frame_{i + 1}.h5"), 0, i + 1, None) for i in range(3)]
    request = RunRequest(
        run.job_id,
        "lauego_indexing",
        "Indexing I1",
        str(tmp_path / "merged"),
        "unused",
        {
            "request": _parameters(geometry_file=str(GEOMETRY), crystal_file=str(CRYSTAL)),
            "output": {"xml": "output.xml"},
        },
        3,
        1,
        2,
    )
    summaries = _run_shards(document, entries, request, 2)
    assert [s["counters"]["n_succeeded"] for s in summaries] == [2, 1]
    destination = Path(request.run_directory) / "output.h5"
    destination.parent.mkdir()
    for rank, summary in enumerate(summaries):
        summary["host"] = f"compute-{rank}"
    comm = Mock()
    comm.Get_rank.return_value = 0
    comm.Get_size.return_value = 2
    comm.gather.return_value = summaries
    document["pbs"]["nodes"] = 2
    document["execution"]["indexing_ranks_per_node"] = 1
    with monkeypatch.context() as patch:
        # Replace transport/execution only: the gathered outputs are real
        # lauelab results and the MPI coordinator performs the actual merge.
        patch.setattr(runner, "run", lambda *args, **kwargs: summaries[0])
        outcome = distributed(document["control_directory"], request, entries, document, comm, Mock())
    assert outcome.n_succeeded == 3
    assert outcome.provenance["indexing_hdf5_merge_seconds"] >= 0
    assert outcome.provenance["indexing_xml_merge_seconds"] >= 0
    assert validate_results_file(destination).n_frames == 3
    assert len(ET.parse(destination.with_suffix(".xml")).getroot()) == 3
    serial = runner.run(
        document["control_directory"], request=replace(request, run_directory=str(tmp_path / "serial")), entries=entries
    )
    assert serial["status"] == "Finished"
    with h5py.File(destination, "r") as merged, h5py.File(serial["artifacts"]["results"], "r") as baseline:
        ids = list(merged["frames/frame_ids"].asstr()[:])
        assert ids == [entries[i].input_id for i in [0, 2, 1]]
        assert list(merged.attrs["merged_sources"]) == [s["artifacts"]["results"] for s in summaries]
        for i, frame_id in enumerate(baseline["frames/frame_ids"].asstr()[:]):
            j = ids.index(frame_id)
            for group, offsets in (("peaks", "frames/peak_offsets"), ("patterns", "frames/pattern_offsets")):
                a, b = baseline[offsets][i : i + 2]
                c, d = merged[offsets][j : j + 2]
                for column in baseline[group]:
                    if column.endswith("_offsets"):
                        continue
                    np.testing.assert_equal(baseline[group][column][a:b], merged[group][column][c:d])
            # Assignment rows reference frame-local peaks, so their indices must not be rebased.
            a, b = baseline["frames/pattern_offsets"][i : i + 2]
            c, d = merged["frames/pattern_offsets"][j : j + 2]
            x, y = baseline["patterns/assignment_offsets"][[a, b]] if a != b else (0, 0)
            u, v = merged["patterns/assignment_offsets"][[c, d]] if c != d else (0, 0)
            for column in baseline["assignments"]:
                np.testing.assert_equal(baseline["assignments"][column][x:y], merged["assignments"][column][u:v])
    with pytest.raises(InvalidResultsFile, match="identities"):
        merge_results_files(
            [summaries[0]["artifacts"]["results"]], tmp_path / "bad.h5", frame_ids=[e.input_id for e in entries]
        )
    assert not (tmp_path / "bad.h5").exists()


@pytest.mark.parametrize("kind,ranks", [("wire_reconstruction", 4), ("lauego_indexing", 16)])
def test_four_node_pbs_layout(remote_run, kind, ranks):
    engine, run, settings = remote_run
    document = plan.build_plan(load_job(engine, run.job_id), settings, str(uuid4()))
    document["kind"] = kind
    document["pbs"]["nodes"] = 4
    document["execution"]["indexing_ranks_per_node"] = 4
    script = build_script(document)
    assert "#PBS -l select=4:system=crux" in script
    assert f"mpiexec -n {ranks} --ppn {ranks // 4}" in script
    assert "-m laue_portal.processing.mpi_runner" in script
    assert json.loads(json.dumps(document))["pbs"]["nodes"] == 4
