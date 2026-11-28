"""DTO de salida del cierre de sesion."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CierreSesionDTO:
    """Confirmacion de que la sesion quedo revocada."""

    session_id: str
    revocado: bool
