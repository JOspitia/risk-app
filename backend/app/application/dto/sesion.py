"""DTO de salida de la sesion y del cambio de credencial."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class CierreSesionDTO:
    """Confirmacion de que la sesion quedo revocada."""

    session_id: str
    revocado: bool


@dataclass(frozen=True)
class CambioContrasenaDTO:
    """Confirmacion de que el cambio de credencial quedo registrado.

    `usuario_id` es el del actor: la credencial que cambio es la suya, y la
    bandera que se limpio es la de su fila.
    """

    usuario_id: UUID
    confirmado: bool
