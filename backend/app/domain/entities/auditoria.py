"""Entidad de dominio de un evento de auditoria.

La bitacora responde "quien hizo que, cuando y desde donde". Es un
**registro de solo agregado**: se escribe, no se corrige y no se borra.

Vive en `domain/` porque es un concepto del negocio, no un detalle de la
tabla: el adaptador decide como se persiste, no que se persiste.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class EventoAuditoria:
    """Un hecho registrado en la bitacora."""

    actor: str
    accion: str
    entidad: str
    usuario_id: UUID | None = None
    entidad_id: UUID | None = None
    organizacion_id: UUID | None = None
    detalles: dict[str, Any] | None = None
    ip: str | None = None
    user_agent: str | None = None
