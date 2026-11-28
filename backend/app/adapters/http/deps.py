"""Guards y dependencias de la capa HTTP.

Un guard es la unica forma de que una peticion llegue a un caso de uso sin
identidad. Levanta el error de dominio que corresponde y el manejador global
lo traduce:

- Sin credencial valida -> `NoAutenticadoError` (401).
- Con credencial valida pero sin perfil -> `PerfilInexistenteError` (403).

Los guards **no deciden permisos**: el permiso se comprueba en el caso de uso
(`SKILL.md` 9.1). Aqui solo se comprueba que hay alguien detras de la
peticion.
"""

from __future__ import annotations

from dataclasses import replace
from typing import cast

from fastapi import Request

from app.adapters.supabase.auditoria import AuditoriaRepositorySupabase
from app.adapters.supabase.cliente import ClienteDatos
from app.adapters.supabase.sesiones import SesionRevocadaRepositorySupabase
from app.application.audit.contexto import AuditContext
from app.application.dto.perfil import PerfilDTO
from app.application.use_cases.cerrar_sesion import ACCION_CIERRE_SESION, CerrarSesion
from app.domain.entities.credencial import CredencialSesion
from app.domain.errors import NoAutenticadoError, PerfilInexistenteError


def contexto_auditoria(request: Request) -> AuditContext:
    """El contexto que construyo el middleware."""
    return cast(AuditContext, request.state.auditoria)


def credencial_sesion(request: Request) -> CredencialSesion:
    """La credencial verificada de la peticion, o 401."""
    credencial = cast(CredencialSesion | None, getattr(request.state, "credencial", None))
    if credencial is None:
        raise NoAutenticadoError()
    return credencial


def requiere_autenticado(request: Request) -> CredencialSesion:
    """Guard: la peticion tiene que estar identificada."""
    return credencial_sesion(request)


def requiere_perfil(request: Request) -> PerfilDTO:
    """Guard: la peticion tiene que tener perfil.

    Un token valido sin fila en `perfiles` es `403 perfil_inexistente`, no 401
    ni 404 (SP-07 de la HU-01).
    """
    credencial_sesion(request)
    perfil = cast(PerfilDTO | None, getattr(request.state, "perfil", None))
    if perfil is None:
        raise PerfilInexistenteError()
    return perfil


def cliente_datos(request: Request) -> ClienteDatos:
    """El cliente de datos de la peticion, con el JWT del usuario propagado."""
    cliente = cast(ClienteDatos | None, getattr(request.state, "cliente_datos", None))
    if cliente is None:
        raise NoAutenticadoError()
    return cliente


def caso_cerrar_sesion(request: Request) -> CerrarSesion:
    """El caso de uso de cierre de sesion, con los puertos de esta peticion."""
    cliente = cliente_datos(request)
    return CerrarSesion(
        sesiones=SesionRevocadaRepositorySupabase(cliente),
        auditoria=AuditoriaRepositorySupabase(cliente),
    )


def contexto_de_cierre(request: Request) -> AuditContext:
    """El contexto de auditoria con la accion del cierre de sesion."""
    return replace(contexto_auditoria(request), accion=ACCION_CIERRE_SESION)
