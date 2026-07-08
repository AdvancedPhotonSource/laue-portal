"""JZT-backed missing-reflection simulation adapter.

The legacy JZT package is shipped under ``laue_portal.analysis.JZTLaueSim`` but
keeps absolute ``JZTLaueSim.*`` imports internally.  Import it only when the user
requests missing-spot simulation so Dash startup stays lightweight.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from importlib import import_module
from pathlib import Path
from typing import Any

import numpy as np

from laue_portal.analysis.back_projection import full_to_roi, q_to_pixel_batch, xyz_to_pixel
from laue_portal.analysis.geometry import DetectorGeometry


@dataclass
class JZTSimulationResult:
    """Neutral result from the optional JZT simulation backend."""

    hkl: np.ndarray = field(default_factory=lambda: np.zeros((0, 3), dtype=int))
    predicted_xy: np.ndarray = field(default_factory=lambda: np.zeros((0, 2)))
    energy_kev: np.ndarray = field(default_factory=lambda: np.zeros((0,)))
    warnings: list[str] = field(default_factory=list)
    used_backend: bool = False


class _PortalDetectorAdapter:
    """Detector facade with the methods/attributes JZT's LauePattern uses."""

    def __init__(self, detector: DetectorGeometry, depth: float = 0.0):
        self._detector = detector
        self._depth = depth
        self.name = detector.detector_id
        self.Nx = detector.Nx
        self.Ny = detector.Ny
        self.dx = detector.sizeX / detector.Nx / 1000.0
        self.dy = detector.sizeY / detector.Ny / 1000.0
        self.XYZcenter = self.pixel2XYZ((detector.Nx - 1) / 2.0, detector.Ny - 1.0)

    def pixel2XYZ(self, px, py):
        from laue_portal.analysis.back_projection import pixel_to_xyz

        xyz_mm = pixel_to_xyz(self._detector, float(px), float(py))
        return np.matrix(xyz_mm / 1000.0)

    def XYZ2pixel(self, xyz):
        try:
            arr = np.asarray(xyz, dtype=float).reshape(3)
        except (TypeError, ValueError):
            return None
        # JZT passes the outgoing scattering direction kf, not a q-vector.
        px, py = xyz_to_pixel(self._detector, arr, depth=self._depth, on_detector=True)
        if not (np.isfinite(px) and np.isfinite(py)):
            return None
        return float(px), float(py)


def simulate_missing_spots(
    *,
    crystal: dict[str, Any],
    detector: DetectorGeometry,
    recip: np.ndarray,
    indexed_hkl: np.ndarray,
    depth: float,
    energy_range_kev: tuple[float, float],
    roi=None,
) -> JZTSimulationResult:
    """Run the vendored JZT simulation and return spots absent from XML HKLs."""
    warnings = _validate_crystal_metadata(crystal)
    if warnings:
        return JZTSimulationResult(warnings=warnings)

    try:
        modules = _import_jzt_modules()
    except ModuleNotFoundError as exc:
        return JZTSimulationResult(
            warnings=[f"JZT missing-spot simulation unavailable ({exc}); using lightweight candidate simulation."]
        )
    except Exception as exc:
        return JZTSimulationResult(warnings=[f"JZT missing-spot simulation import failed: {exc}."])

    try:
        lattice = _build_lattice(crystal, modules["LatticeBase"], modules["Lattice"])
        jzt_detector = _PortalDetectorAdapter(detector, depth=depth)
        # Portal stores reciprocal basis vectors as rows; JZT expects columns.
        jzt_recip = np.matrix(np.asarray(recip, dtype=float).T)
        pattern = modules["LauePattern"].LauePattern(lattice, detector=jzt_detector, recip=jzt_recip)
        elo, ehi = sorted((float(energy_range_kev[0]), float(energy_range_kev[1])))
        spots = pattern.calc(ELO=elo, EHI=ehi, Nmax=100000)
        result = _spots_to_result(spots, detector, depth, roi, indexed_hkl)
        result.used_backend = True
        return result
    except Exception as exc:
        return JZTSimulationResult(warnings=[f"JZT missing-spot simulation failed: {exc}."])


def _import_jzt_modules() -> dict[str, Any]:
    """Import the local legacy JZT package only when simulation is requested."""
    analysis_dir = Path(__file__).resolve().parent
    if str(analysis_dir) not in sys.path:
        sys.path.insert(0, str(analysis_dir))

    modules = {
        "LauePattern": import_module("JZTLaueSim.LauePattern"),
        "LatticeBase": import_module("JZTLaueSim.LatticeBase"),
        "Lattice": import_module("JZTLaueSim.Lattice"),
    }
    import_module("JZTLaueSim.LauePattern_allspots")
    return modules


def _build_lattice(crystal: dict[str, Any], lattice_base_module, lattice_module):
    atom_objects = []
    for atom in crystal.get("atoms") or []:
        label = atom.get("label") or atom.get("symbol") or "X"
        z_atom = atom.get("Zatom") or atom.get("symbol") or label
        atom_objects.append(
            lattice_base_module.atomXtal(
                label=label,
                Zatom=z_atom,
                xyz=atom.get("xyz"),
            )
        )

    lattice_params = [float(v) for v in np.asarray(crystal.get("lattice_params"), dtype=float)]
    return lattice_module.Lattice3D(
        int(crystal.get("space_group")),
        lattice_params,
        desc=crystal.get("structure_desc") or "",
        atoms=tuple(atom_objects),
    )


def _spots_to_result(
    spots, detector: DetectorGeometry, depth: float, roi, indexed_hkl: np.ndarray
) -> JZTSimulationResult:
    indexed = {tuple(map(int, hkl)) for hkl in np.asarray(indexed_hkl, dtype=int).reshape(-1, 3)}
    hkl_values = []
    energy_values = []
    qhat_values = []

    for spot in spots or []:
        hkl = tuple(int(spot.hkl.item(0, i)) for i in range(3))
        if hkl in indexed:
            continue
        hkl_values.append(hkl)
        energy_values.append(float(spot.keV))
        qhat_values.append(np.asarray(spot.qhat, dtype=float).reshape(3))

    if not hkl_values:
        return JZTSimulationResult(used_backend=True)

    qhat = np.asarray(qhat_values, dtype=float)
    full_xy = q_to_pixel_batch(detector, qhat, depth=depth, on_detector=True)
    if roi is not None:
        px, py = full_to_roi(full_xy[:, 0], full_xy[:, 1], roi)
        pred_xy = np.column_stack([px, py])
    else:
        pred_xy = full_xy

    finite = np.isfinite(pred_xy[:, 0]) & np.isfinite(pred_xy[:, 1])
    return JZTSimulationResult(
        hkl=np.asarray(hkl_values, dtype=int)[finite],
        predicted_xy=pred_xy[finite],
        energy_kev=np.asarray(energy_values, dtype=float)[finite],
        used_backend=True,
    )


def _validate_crystal_metadata(crystal: dict[str, Any]) -> list[str]:
    """Return user-facing warnings for metadata gaps that block JZT simulation."""
    missing = []
    try:
        space_group = int(crystal.get("space_group") or 0)
    except (TypeError, ValueError):
        space_group = 0
    if space_group <= 0:
        missing.append("SpaceGroup")

    lattice_params = np.asarray(crystal.get("lattice_params"), dtype=float)
    if lattice_params.shape != (6,) or not np.all(np.isfinite(lattice_params)) or np.allclose(lattice_params, 0):
        missing.append("latticeParameters")

    atoms = crystal.get("atoms") or []
    if not atoms:
        missing.append("atom")

    if missing:
        return ["JZT missing-spot simulation skipped; XML crystal metadata is incomplete: " + ", ".join(missing) + "."]
    return []
