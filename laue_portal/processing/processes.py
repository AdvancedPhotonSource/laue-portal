"""Compute process cleanup shared by local and standalone executors."""

import psutil

_HELPER_MARKERS = ("multiprocessing.resource_tracker", "multiprocessing.semaphore_tracker")


def _is_helper_process(process: psutil.Process) -> bool:
    """Python's multiprocessing trackers are not compute work and exit with their parent."""

    try:
        command = " ".join(process.cmdline())
    except psutil.Error:
        return False
    return any(marker in command for marker in _HELPER_MARKERS)


def terminate_descendants(grace_seconds: float = 5.0) -> int:
    """Terminate every descendant of this process; returns how many had to be dealt with."""

    try:
        children = [child for child in psutil.Process().children(recursive=True) if not _is_helper_process(child)]
    except psutil.Error:
        return 0
    if not children:
        return 0
    for child in children:
        try:
            child.terminate()
        except psutil.Error:
            pass
    _, alive = psutil.wait_procs(children, timeout=grace_seconds)
    for child in alive:
        try:
            child.kill()
        except psutil.Error:
            pass
    psutil.wait_procs(alive, timeout=grace_seconds)
    return len(children)
