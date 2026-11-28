"""Caso de uso: cerrar la sesion.

El cierre de sesion **invalida el token de inmediato**, no al expirar (ADR-31).
`signOut()` del SDK de Supabase revoca el refresh token, pero el access token
sigue siendo criptograficamente valido hasta su `exp`: sin un registro de
revocacion, el criterio "401 de inmediato" es falso.

El orden de las escrituras es deliberado:

1. **Primero** la revocacion. Es lo que protege al usuario, y tiene que
   quedar registrada aunque la bitacora falle despues.
2. **Despues** la bitacora. Si la escritura de la bitacora falla, la sesion ya
   esta revocada y el error sale hacia el cliente: no se esconde una revocacion
   que si ocurrio.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.audit.contexto import AuditContext
from app.application.dto.sesion import CierreSesionDTO
from app.domain.entities.auditoria import EventoAuditoria
from app.domain.entities.credencial import CredencialSesion
from app.domain.ports.auditoria import AuditoriaRepository
from app.domain.ports.sesiones import SesionRevocadaRepository

ACCION_CIERRE_SESION = "sesion.cerrada"


@dataclass(frozen=True)
class CerrarSesion:
    """Revoca la sesion del actor y deja el hecho en la bitacora."""

    sesiones: SesionRevocadaRepository
    auditoria: AuditoriaRepository

    async def ejecutar(
        self,
        credencial: CredencialSesion,
        ctx: AuditContext,
    ) -> CierreSesionDTO:
        await self.sesiones.revocar(
            session_id=credencial.session_id,
            usuario_id=credencial.usuario_id,
            expira_en=credencial.expira_en,
        )

        await self.auditoria.registrar(
            EventoAuditoria(
                actor=ctx.nombre or credencial.correo or str(credencial.usuario_id),
                accion=ctx.accion or ACCION_CIERRE_SESION,
                entidad="sesion",
                usuario_id=credencial.usuario_id,
                organizacion_id=ctx.organizacion_id,
                detalles={"session_id": credencial.session_id},
                ip=ctx.ip,
                user_agent=ctx.user_agent,
            ),
        )

        return CierreSesionDTO(session_id=credencial.session_id, revocado=True)
