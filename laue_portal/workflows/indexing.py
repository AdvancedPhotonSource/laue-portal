"""LaueGo indexing creation and retrieval services."""

import os
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import Engine, insert, select
from sqlalchemy.orm import Session, joinedload

from laue_portal.database import db_schema, session_utils
from laue_portal.workflows.files import (
    ProgressCallback,
    WorkflowValidationError,
    format_output_path,
    normalize_filename_templates,
    normalize_input_directory,
    normalize_integer_range,
    normalize_optional_integer_range,
    normalize_output_path_template,
    resolve_input_files,
)

QUEUED_STATUS = 0
SUBJOB_INSERT_BATCH_SIZE = 10_000


@dataclass(frozen=True)
class LaueGoIndexingRequest:
    """Normalized inputs required to create one LaueGo indexing run."""

    scan_number: int | None
    reconstruction_id: int | None
    input_path: str
    output_path_template: str
    filename_prefixes: Sequence[str]
    threshold: int | None
    threshold_ratio: int | None
    max_rfactor: float
    box_size: int
    max_number: int
    min_separation: int
    peak_shape: str
    scan_points: str
    depth_range: str | None
    detector_crop_x1: int
    detector_crop_x2: int
    detector_crop_y1: int
    detector_crop_y2: int
    min_size: float
    max_peaks: int
    smooth: bool
    mask_file: str | None
    index_kev_max_calc: float
    index_kev_max_test: float
    index_angle_tolerance: float
    index_h: int
    index_k: int
    index_l: int
    index_cone: float
    energy_unit: str
    exposure_unit: str
    cosmic_filter: bool
    reciprocal_lattice_unit: str
    lattice_parameters_unit: str
    output_xml: str | None
    geometry_file: str
    crystal_file: str
    depth: str | None
    beamline: str
    author: str | None = None
    notes: str | None = None
    algorithm_version: str | None = None
    computer_name: str = "example_computer"
    priority: int = 0
    submitted_at: datetime = field(default_factory=datetime.now)
    scan_point_values: tuple[int, ...] = field(init=False, repr=False)
    depth_values: tuple[int, ...] | None = field(init=False, repr=False)

    def __post_init__(self) -> None:
        scan_points, scan_point_values = normalize_integer_range(self.scan_points, "scan points")
        depth_range, depth_values = normalize_optional_integer_range(self.depth_range, "depth range")
        computer_name = str(self.computer_name).strip()
        geometry_file = os.path.normpath(os.fspath(self.geometry_file))
        crystal_file = os.path.normpath(os.fspath(self.crystal_file))
        if not computer_name:
            raise WorkflowValidationError("Computer name is required")
        if not geometry_file or geometry_file == ".":
            raise WorkflowValidationError("Geometry file is required")
        if not crystal_file or crystal_file == ".":
            raise WorkflowValidationError("Crystal file is required")

        mask_file = str(self.mask_file).strip() if self.mask_file is not None else None
        object.__setattr__(self, "scan_number", int(self.scan_number) if self.scan_number is not None else None)
        object.__setattr__(
            self,
            "reconstruction_id",
            int(self.reconstruction_id) if self.reconstruction_id is not None else None,
        )
        object.__setattr__(self, "input_path", normalize_input_directory(self.input_path))
        object.__setattr__(self, "output_path_template", normalize_output_path_template(self.output_path_template))
        object.__setattr__(self, "filename_prefixes", normalize_filename_templates(self.filename_prefixes))
        object.__setattr__(self, "geometry_file", geometry_file)
        object.__setattr__(self, "crystal_file", crystal_file)
        object.__setattr__(self, "mask_file", mask_file or None)
        object.__setattr__(self, "scan_points", scan_points)
        object.__setattr__(self, "scan_point_values", scan_point_values)
        object.__setattr__(self, "depth_range", depth_range)
        object.__setattr__(self, "depth_values", depth_values)
        object.__setattr__(self, "computer_name", computer_name)
        object.__setattr__(self, "priority", int(self.priority))


def _persist_subjobs(
    session: Session,
    request: LaueGoIndexingRequest,
    job_id: int,
    input_files: tuple[str, ...],
    output_root: str,
) -> None:
    for start in range(0, len(input_files), SUBJOB_INSERT_BATCH_SIZE):
        batch = input_files[start : start + SUBJOB_INSERT_BATCH_SIZE]
        rows = [
            {
                "job_id": job_id,
                "computer_name": request.computer_name,
                "status": QUEUED_STATUS,
                "priority": request.priority,
                "input_path": input_path,
                "output_path": output_root,
            }
            for input_path in batch
        ]
        session.execute(insert(db_schema.SubJob), rows)


def create_indexing(
    request: LaueGoIndexingRequest,
    *,
    engine: Engine | None = None,
    progress_callback: ProgressCallback | None = None,
) -> db_schema.IndexingRun:
    """Resolve files, then atomically create a LaueGo run, job, and subjobs."""

    input_files = resolve_input_files(
        request.input_path,
        request.filename_prefixes,
        request.scan_point_values,
        depth_points=request.depth_values,
        progress_callback=progress_callback,
    )

    database_engine = engine or session_utils.get_engine()
    with Session(database_engine, expire_on_commit=False) as session:
        with session.begin():
            parent = None
            if request.reconstruction_id is not None:
                parent = session.get(db_schema.ReconstructionRun, request.reconstruction_id)
                if parent is None:
                    raise WorkflowValidationError(f"Reconstruction R{request.reconstruction_id} does not exist")
                if (
                    request.scan_number is not None
                    and parent.scan_number is not None
                    and request.scan_number != parent.scan_number
                ):
                    raise WorkflowValidationError(
                        f"Indexing scan {request.scan_number} does not match reconstruction scan {parent.scan_number}"
                    )

            scan_number = request.scan_number
            if scan_number is None and parent is not None:
                scan_number = parent.scan_number

            job = db_schema.Job(
                computer_name=request.computer_name,
                status=QUEUED_STATUS,
                priority=request.priority,
                submit_time=request.submitted_at,
                start_time=None,
                finish_time=None,
            )
            session.add(job)
            session.flush()

            run = db_schema.IndexingRun(
                scan_number=scan_number,
                reconstruction=parent,
                job=job,
                method="lauego",
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
            run.lauego_parameters = db_schema.LaueGoIndexingParameters(
                filename_prefixes=list(request.filename_prefixes),
                threshold=request.threshold,
                threshold_ratio=request.threshold_ratio,
                max_rfactor=request.max_rfactor,
                box_size=request.box_size,
                max_number=request.max_number,
                min_separation=request.min_separation,
                peak_shape=request.peak_shape,
                scan_points=request.scan_points,
                scan_points_len=len(request.scan_point_values),
                depth_range=request.depth_range,
                depth_range_len=len(request.depth_values) if request.depth_values is not None else None,
                detector_crop_x1=request.detector_crop_x1,
                detector_crop_x2=request.detector_crop_x2,
                detector_crop_y1=request.detector_crop_y1,
                detector_crop_y2=request.detector_crop_y2,
                min_size=request.min_size,
                max_peaks=request.max_peaks,
                smooth=request.smooth,
                mask_file=request.mask_file,
                index_kev_max_calc=request.index_kev_max_calc,
                index_kev_max_test=request.index_kev_max_test,
                index_angle_tolerance=request.index_angle_tolerance,
                index_h=request.index_h,
                index_k=request.index_k,
                index_l=request.index_l,
                index_cone=request.index_cone,
                energy_unit=request.energy_unit,
                exposure_unit=request.exposure_unit,
                cosmic_filter=request.cosmic_filter,
                reciprocal_lattice_unit=request.reciprocal_lattice_unit,
                lattice_parameters_unit=request.lattice_parameters_unit,
                output_xml=request.output_xml,
                geometry_file=request.geometry_file,
                crystal_file=request.crystal_file,
                depth=request.depth,
                beamline=request.beamline,
            )
            _persist_subjobs(session, request, job.job_id, input_files, run.output_path)
    return run


def get_indexing(indexing_id: int, *, engine: Engine | None = None) -> db_schema.IndexingRun | None:
    """Load an indexing run with its parameters, parent, job, and subjobs."""

    database_engine = engine or session_utils.get_engine()
    statement = (
        select(db_schema.IndexingRun)
        .where(db_schema.IndexingRun.id == indexing_id)
        .options(
            joinedload(db_schema.IndexingRun.lauego_parameters),
            joinedload(db_schema.IndexingRun.reconstruction),
            joinedload(db_schema.IndexingRun.job),
        )
    )
    with Session(database_engine) as session:
        return session.scalars(statement).one_or_none()
