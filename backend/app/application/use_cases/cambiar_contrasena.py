"""Caso de uso: confirmar el cambio de credencial.

**Este caso de uso no cambia la contrasena.** La credencial vive en Supabase
Auth (ADR-05): el frontend la cambia con `supabase.auth.updateUser` y despues
**confirma** aqui. El backend no ve la contrasena, no la verifica y no la
almacena: el hashing y la tabla de sesiones estan fuera del proyecto
(HU-01, seccion 2).

Lo que hace es lo que nadie mas puede hacer por el usuario:

1. **Limpiar `perfiles.debe_cambiar_contrasena`** de la fila del usuario
   autenticado. Sin esto, la bandera seguiria diciendole al usuario que
   cambie la credencial cuando ya la cambio.
2. **Registrar el hecho en la bitacora**, con el actor.

El orden de las escrituras es el de `cerrar_sesion`: primero el hecho que
protege al usuario (la bandera limpia), despues la bitacora. Si la escritura
de la bitacora falla, la bandera ya esta limpia y el error sale hacia el
cliente: no se esconde una confirmacion que si ocurrio.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.audit.contexto import AuditContext
from app.application.dto.sesion import CambioContrasenaDTO
from app.domain.entities.auditoria import EventoAuditoria
from app.domain.entities.credencial import CredencialSesion
from app.domain.ports.auditoria import AuditoriaRepository
from app.domain.ports.perfiles import PerfilRepository

ACCION_CAMBIO_CONTRASENA = "perfil.contrasena_confirmada"


@dataclass(frozen=True)
class CambiarContrasena:
    """Confirma el cambio de credencial del actor y deja el hecho en la bitacora."""

    perfiles: PerfilRepository
    auditoria: AuditoriaRepository

    async def ejecutar(
        self,
        credencial: CredencialSesion,
        ctx: AuditContext,
    ) -> CambioContrasenaDTO:
        await self.perfiles.confirmar_cambio_de_contrasena(credencial.usuario_id)

        await self.auditoria.registrar(
            EventoAuditoria(
                actor=ctx.nombre or credencial.correo or str(credencial.usuario_id),
                accion=ctx.accion or ACCION_CAMBIO_CONTRASENA,
                entidad="perfil",
                usuario_id=credencial.usuario_id,
                organizacion_id=ctx.organizacion_id,
                detalles={"debe_cambiar_contrasena": False},
                ip=ctx.ip,
                user_agent=ctx.user_agent,
            ),
        )

        return CambioContrasenaDTO(usuario_id=credencial.usuario_id, confirmado=True)
