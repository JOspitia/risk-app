"""Entidad de dominio de la credencial de sesion.

Es lo que el token **ya verificado** deja: quien es el usuario, que sesion
representa y cuando vence. No es el token: el token es un secreto y nunca
viaja hacia adentro de la aplicacion.

El backend no emite tokens (ADR-05). Esta entidad existe porque el cierre de
sesion necesita el `session_id` (la llave de revocacion, ADR-31) y porque el
contexto de auditoria necesita saber quien hace la peticion.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class CredencialSesion:
    """Identidad que un token verificado acredita."""

    usuario_id: UUID
    session_id: str
    expira_en: datetime
    correo: str | None = None
