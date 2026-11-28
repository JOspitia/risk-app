"""Puerto de salida de la bitacora de auditoria.

La bitacora es de **solo agregado**: se escribe, no se corrige y no se borra.
"""

from __future__ import annotations

from typing import Protocol

from app.domain.entities.auditoria import EventoAuditoria


class AuditoriaRepository(Protocol):
    """Escritura en la bitacora de auditoria."""

    async def registrar(self, evento: EventoAuditoria) -> None:
        """Deja el evento en la bitacora.

        El `usuario_id` del evento tiene que ser el del actor: la politica de
        la base de datos no acepta otra cosa.
        """
        ...
