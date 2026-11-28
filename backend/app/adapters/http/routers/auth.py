"""Router de autenticacion.

**No hay endpoint de login.** El backend no emite tokens: el login lo hace el
SDK de Supabase en el navegador, con `signInWithPassword`. `POST
/api/v1/auth/login` no existe, y si aparece en un router es un error
(`SKILL.md` 5.2).

Lo que hay:

- `GET /api/v1/auth/me`: el perfil del usuario autenticado.
- `POST /api/v1/auth/logout`: revoca la sesion del usuario autenticado.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.adapters.http.deps import (
    caso_cambiar_contrasena,
    caso_cerrar_sesion,
    contexto_de_cambio,
    contexto_de_cierre,
    requiere_autenticado,
    requiere_perfil,
)
from app.adapters.http.responses import Respuesta
from app.adapters.http.schemas.auth import (
    CambioContrasenaResource,
    CierreSesionResource,
    PerfilResource,
)
from app.application.audit.contexto import AuditContext
from app.application.dto.perfil import PerfilDTO
from app.application.use_cases.cambiar_contrasena import CambiarContrasena
from app.application.use_cases.cerrar_sesion import CerrarSesion
from app.domain.entities.credencial import CredencialSesion

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.get("/me", response_model=Respuesta[PerfilResource])
async def mi_perfil(
    perfil: PerfilDTO = Depends(requiere_perfil),
) -> Respuesta[PerfilResource]:
    """El perfil del usuario autenticado.

    Responde 200 con el perfil dentro del envelope. Responde 401 si no hay
    credencial valida y 403 con el codigo `perfil_inexistente` si el usuario
    esta autenticado pero no tiene perfil.
    """
    return Respuesta.ok(
        data=PerfilResource.from_model(perfil),
        mensaje="Perfil consultado",
    )


@router.post("/logout", response_model=Respuesta[CierreSesionResource])
async def cerrar_sesion(
    credencial: CredencialSesion = Depends(requiere_autenticado),
    ctx: AuditContext = Depends(contexto_de_cierre),
    caso: CerrarSesion = Depends(caso_cerrar_sesion),
) -> Respuesta[CierreSesionResource]:
    """Cierra la sesion del usuario autenticado.

    Revoca el `session_id` del token, de modo que el token deja de servir de
    inmediato, sin esperar su expiracion natural (ADR-31). No necesita cuerpo:
    la sesion que se revoca es la del token.
    """
    resultado = await caso.ejecutar(credencial, ctx)
    return Respuesta.ok(
        data=CierreSesionResource.from_model(resultado),
        mensaje="Sesion cerrada",
    )


@router.post("/cambiar-contrasena", response_model=Respuesta[CambioContrasenaResource])
async def cambiar_contrasena(
    perfil: PerfilDTO = Depends(requiere_perfil),
    credencial: CredencialSesion = Depends(requiere_autenticado),
    ctx: AuditContext = Depends(contexto_de_cambio),
    caso: CambiarContrasena = Depends(caso_cambiar_contrasena),
) -> Respuesta[CambioContrasenaResource]:
    """Confirma el cambio de credencial del usuario autenticado.

    **No cambia la contrasena.** La credencial vive en Supabase Auth (ADR-05):
    el frontend la cambia con `supabase.auth.updateUser` y despues llama a esta
    ruta para confirmar. El backend no ve la contrasena, no la verifica y no la
    almacena.

    Lo que hace es limpiar `perfiles.debe_cambiar_contrasena` de la fila del
    usuario y dejar el hecho en la bitacora. Sin esa limpieza, la bandera
    seguiria mandando al usuario a cambiar la credencial en cada inicio de
    sesion, aunque ya la haya cambiado.

    No necesita cuerpo: la fila que se modifica es la del token.
    """
    resultado = await caso.ejecutar(credencial, ctx)
    return Respuesta.ok(
        data=CambioContrasenaResource.from_model(resultado),
        mensaje="Credencial confirmada",
    )
