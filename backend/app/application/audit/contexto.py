"""Contexto de auditoria: quien esta haciendo la peticion.

Lo construye el middleware antes del handler y lo reciben los casos de uso.
Los casos de uso **nunca ven el token**: ven esto, que es la forma segura de
transportar la identidad.

Las credenciales invalidas, vencidas o revocadas producen un contexto
**anonimo**, no un 401 inmediato: el 401 lo levanta el guard de la ruta
protegida (`SKILL.md` 9).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class AuditContext:
    """Identidad de la peticion en curso."""

    usuario_id: UUID | None = None
    nombre: str | None = None
    session_id: str | None = None
    rol: str | None = None
    organizacion_id: UUID | None = None
    accion: str | None = None
    ip: str | None = None
    user_agent: str | None = None

    @property
    def es_anonimo(self) -> bool:
        """True cuando la peticion no esta identificada."""
        return self.usuario_id is None
