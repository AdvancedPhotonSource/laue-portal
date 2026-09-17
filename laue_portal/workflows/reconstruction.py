"""Wire reconstruction creation and retrieval services."""

import os
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, joinedload

from laue_portal.database import db_schema, session_utils
from laue_portal.workflows.files import (
    ProgressCallback,
    WorkflowValidationError,
    format_output_path,
    normalize_filename_templates,
    normalize_input_directory,
    normalize_integer_range,
    normalize_output_path_template,
    resolve_inputs,
)
from laue_portal.workflows.run_records import new_job, publish_run_inputs, request_document


@dataclass(frozen=True)
class WireReconstructionRequest:
    """Normalized inputs required to create one wire reconstruction run."""

    scan_number: int | None
    input_path: str
    output_path_template: str
    filename_prefixes: Sequence[str]
    geometry_file: str
    percent_brightest: float
    wire_edges: str
    depth_start: float
    depth_end: float
    depth_resolution: float
    num_threads: int
    memory_limit_mb: int
    scan_points: str
    verbose: int
    author: str | None = None
    notes: str | None = None
    algorithm_version: str | None = None
    computer_name: str = "example_computer"
    priority: int = 0
    submitted_at: datetime = field(default_factory=datetime.now)
    scan_point_values: tuple[int, ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        scan_points, scan_point_values = normalize_integer_range(self.scan_points, "scan points")
        computer_name = str(self.computer_name).strip()
        geometry_file = os.path.normpath(os.fspath(self.geometry_file))
        if not computer_name:
            raise WorkflowValidationError("Computer name is required")
        if not geometry_file or geometry_file == ".":
            raise WorkflowValidationError("Geometry file is required")

        object.__setattr__(self, "scan_number", int(self.scan_number) if self.scan_number is not None else None)
        object.__setattr__(self, "input_path", normalize_input_directory(self.input_path))
        object.__setattr__(self, "output_path_template", normalize_output_path_template(self.output_path_template))
        object.__setattr__(self, "filename_prefixes", normalize_filename_templates(self.filename_prefixes))
        object.__setattr__(self, "geometry_file", geometry_file)
        object.__setattr__(self, "scan_points", scan_points)
        object.__setattr__(self, "scan_point_values", scan_point_values)
        object.__setattr__(self, "computer_name", computer_name)
        object.__setattr__(self, "priority", int(self.priority))


def create_reconstruction(
    request: WireReconstructionRequest,
    *,
    engine: Engine | None = None,
    progress_callback: ProgressCallback | None = None,
) -> db_schema.ReconstructionRun:
    """Resolve files, create the run and its job atomically, then publish the manifest."""

    inputs = resolve_inputs(
        request.input_path,
        request.filename_prefixes,
        request.scan_point_values,
        append_suffix_wildcard=True,
        progress_callback=progress_callback,
    )

    database_engine = engine or session_utils.get_engine()
    with Session(database_engine, expire_on_commit=False) as session:
        with session.begin():
            job = new_job(
                computer_name=request.computer_name,
                priority=request.priority,
                submitted_at=request.submitted_at,
                n_inputs=len(inputs),
            )
            session.add(job)
            session.flush()

            run = db_schema.ReconstructionRun(
                scan_number=request.scan_number,
                job=job,
                method="wire",
                input_path=request.input_path,
                output_path=None,
                author=request.author,
                notes=request.notes,
                algorithm_version=request.algorithm_version,
                created_at=request.submitted_at,
            )
            session.add(run)
            session.flush()
            run.output_path = format_output_path(request.output_path_template, run.id)
            job.run_directory = run.output_path
            run.wire_parameters = db_schema.WireReconstructionParameters(
                filename_prefixes=list(request.filename_prefixes),
                geometry_file=request.geometry_file,
                percent_brightest=request.percent_brightest,
                wire_edges=request.wire_edges,
                depth_start=request.depth_start,
                depth_end=request.depth_end,
                depth_resolution=request.depth_resolution,
                num_threads=request.num_threads,
                memory_limit_mb=request.memory_limit_mb,
                scan_points=request.scan_points,
                scan_points_len=len(request.scan_point_values),
                verbose=request.verbose,
            )
        run_id = run.id
        job_id = job.job_id
        run_directory = run.output_path

    payload = {
        "kind": "wire_reconstruction",
        "run": {
            "reconstruction_id": run_id,
            "job_id": job_id,
            "scan_number": request.scan_number,
            "method": "wire",
        },
        "request": request_document(request),
        "output": {"directory": run_directory},
    }
    publish_run_inputs(
        database_engine,
        job_id=job_id,
        display_id=f"Reconstruction R{run_id}",
        run_directory=run_directory,
        inputs=inputs,
        request_payload=payload,
        now=request.submitted_at,
    )
    return get_reconstruction(run_id, engine=database_engine)


def get_reconstruction(reconstruction_id: int, *, engine: Engine | None = None) -> db_schema.ReconstructionRun | None:
    """Load a reconstruction with its parameters and job."""

    database_engine = engine or session_utils.get_engine()
    statement = (
        select(db_schema.ReconstructionRun)
        .where(db_schema.ReconstructionRun.id == reconstruction_id)
        .options(
            joinedload(db_schema.ReconstructionRun.wire_parameters),
            joinedload(db_schema.ReconstructionRun.job),
        )
    )
    with Session(database_engine) as session:
        return session.scalars(statement).one_or_none()
