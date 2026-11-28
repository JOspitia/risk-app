"""Adaptador de salida de la bitacora de auditoria.

La escritura viaja con el **JWT del usuario**: la politica de `auditoria` no
acepta que `usuario_id` sea el de otra persona, y esa comprobacion la hace la
base de datos.

La bitacora es de **solo agregado**: se inserta, no se actualiza y no se
borra.
"""

from __future__ import annotations

import ipaddress
from typing import Any
from uuid import UUID

from app.adapters.supabase.cliente import ClienteDatos
from app.domain.entities.auditoria import EventoAuditoria

TABLA_AUDITORIA = "auditoria"


class AuditoriaRepositorySupabase:
    """Implementa el puerto de auditoria sobre PostgREST."""

    def __init__(self, cliente: ClienteDatos) -> None:
        self._cliente = cliente

    async def registrar(self, evento: EventoAuditoria) -> None:
        await self._cliente.insertar(TABLA_AUDITORIA, _mapear_evento(evento))


def _mapear_evento(evento: EventoAuditoria) -> dict[str, Any]:
    """Evento de dominio a fila de `auditoria`."""
    return {
        "usuario_id": _uuid_texto(evento.usuario_id),
        "organizacion_id": _uuid_texto(evento.organizacion_id),
        "actor": evento.actor,
        "accion": evento.accion,
        "entidad": evento.entidad,
        "entidad_id": _uuid_texto(evento.entidad_id),
        "detalles": evento.detalles,
        "ip": _ip_texto(evento.ip),
        "user_agent": evento.user_agent,
    }


def _uuid_texto(valor: UUID | None) -> str | None:
    return str(valor) if valor is not None else None


def _ip_texto(valor: str | None) -> str | None:
    """La columna `ip` es de tipo `inet`: solo admite una direccion valida.

    Sin esta comprobacion, un `Host` que no es una IP (un nombre de proxy, o
    el cliente de pruebas) hace fallar **toda** la escritura de la bitacora.
    """
    if not valor:
        return None
    try:
        ipaddress.ip_address(valor)
    except ValueError:
        return None
    return valor
