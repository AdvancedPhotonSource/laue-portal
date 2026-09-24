"""Requests, results, and executor hooks for compute functions."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from laue_portal.workflows.manifest import FailureRecord, ManifestEntry


@dataclass(frozen=True)
class RunRequest:
    """Compute settings loaded from ``request.json`` and the execution policy."""

    job_id: int
    kind: str
    display_id: str
    run_directory: str
    manifest_path: str
    document: Mapping[str, Any]  # the full request.json document
    n_inputs: int
    workers: int
    max_in_flight: int | None
    reconstruction_workers: int = 1  # points a wire reconstruction computes at once

    @property
    def parameters(self) -> Mapping[str, Any]:
        """Saved form parameters."""

        return self.document.get("request", {})

    @property
    def output(self) -> Mapping[str, Any]:
        return self.document.get("output", {})


class RunHooks(Protocol):
    """Executor callbacks for progress, cancellation, and output reporting."""

    def should_stop(self) -> bool:
        """True once cancellation or shutdown was requested; stop admitting new inputs."""

    def report_progress(self, *, succeeded: int, failed: int) -> None:
        """Absolute processed counts so far; the executor rate-limits persistence."""

    def record_failure(self, record: FailureRecord) -> None:
        """Append one failed or unattempted input to the run's failure report."""

    def report_outcome(self, outcome: RunOutcome) -> None:
        """Keep output details for the run summary if computation raises."""

    def log(self, message: str) -> None:
        """Operational message for the run log."""


@dataclass
class RunOutcome:
    """Compute results used by the executor to determine the final run status."""

    n_succeeded: int
    n_failed: int
    stopped: bool = False  # admission ended because should_stop() returned True
    artifacts: dict[str, str] = field(default_factory=dict)  # name -> path of published outputs
    warnings: list[str] = field(default_factory=list)  # auxiliary problems (for example XML export)
    validation_error: str | None = None  # authoritative output failed structural validation
    provenance: dict[str, Any] = field(default_factory=dict)  # versions and effective configuration
    summary: str | None = None
    n_indexed: int | None = None  # frames with at least one pattern, when known

    @property
    def n_processed(self) -> int:
        return self.n_succeeded + self.n_failed


ComputeFunction = Callable[[RunRequest, Iterable[ManifestEntry], RunHooks], RunOutcome]


class UnknownRunKind(LookupError):
    """No compute function is registered for a request kind."""


_REGISTRY: dict[str, ComputeFunction] = {}


def register_compute_function(kind: str, function: ComputeFunction) -> None:
    _REGISTRY[kind] = function


def get_compute_function(kind: str) -> ComputeFunction:
    try:
        return _REGISTRY[kind]
    except KeyError:
        from laue_portal.processing.compute import lauego, wire  # noqa: F401  registers the native adapters

        try:
            return _REGISTRY[kind]
        except KeyError:
            raise UnknownRunKind(f"no compute function is registered for run kind {kind!r}") from None
