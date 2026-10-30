"""Creation, persistence, and retrieval services for processing workflows."""

from importlib import import_module

_EXPORTS = {
    "ExecutionStateError": "execution",
    "JobStatus": "execution",
    "RunPhase": "execution",
    "FileResolutionError": "files",
    "ResolvedInput": "files",
    "WorkflowValidationError": "files",
    "LaueGoIndexingRequest": "indexing",
    "create_indexing": "indexing",
    "get_indexing": "indexing",
    "FailureRecord": "manifest",
    "FailureReportWriter": "manifest",
    "ManifestEntry": "manifest",
    "ManifestError": "manifest",
    "read_manifest": "manifest",
    "RunProgress": "progress",
    "load_progress": "progress",
    "WireReconstructionRequest": "reconstruction",
    "create_reconstruction": "reconstruction",
    "get_reconstruction": "reconstruction",
    "RunPublicationError": "run_records",
}


def __getattr__(name):
    """Load database-backed services only when requested by the portal."""
    if name not in _EXPORTS:
        raise AttributeError(name)
    value = getattr(import_module(f"{__name__}.{_EXPORTS[name]}"), name)
    globals()[name] = value
    return value


__all__ = [
    "ExecutionStateError",
    "FailureRecord",
    "FailureReportWriter",
    "FileResolutionError",
    "JobStatus",
    "LaueGoIndexingRequest",
    "ManifestEntry",
    "ManifestError",
    "ResolvedInput",
    "RunPhase",
    "RunProgress",
    "RunPublicationError",
    "WireReconstructionRequest",
    "WorkflowValidationError",
    "create_indexing",
    "create_reconstruction",
    "get_indexing",
    "get_reconstruction",
    "load_progress",
    "read_manifest",
]
