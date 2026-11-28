"""Pruebas del caso de uso `CambiarContrasena`.

Este caso de uso **no cambia la contrasena**: la credencial vive en Supabase
Auth (ADR-05) y el frontend la cambia con `supabase.auth.updateUser`. Lo que
hace el backend es limpiar `perfiles.debe_cambiar_contrasena` y dejar el hecho
en la bitacora.

Aqui se comprueba el **contrato** del caso de uso: que limpia la bandera del
usuario autenticado, que registra el hecho, y que no envuelve los errores.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from app.application.audit.contexto import AuditContext
from app.application.use_cases.cambiar_contrasena import (
    ACCION_CAMBIO_CONTRASENA,
    CambiarContrasena,
)
from app.domain.entities.auditoria import EventoAuditoria
from app.domain.entities.credencial import CredencialSesion
from app.domain.errors import ProhibidoError

pytestmark = pytest.mark.unit

USUARIO_ID = UUID("3ad2a179-04be-4023-86ff-9bfb0660adf7")
ORGANIZACION_ID = UUID("c41a0000-0000-4000-8000-000000000001")
SESSION_ID = "e5f0cc4f-024f-4b97-aae6-3764ccc4c0cd"


class PerfilesEnMemoria:
    """Implementacion del puerto de perfiles, en memoria."""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.confirmaciones: list[UUID] = []

    async def obtener(self, usuario_id: UUID) -> None:
        return None

    async def membresia_actual(self, usuario_id: UUID) -> None:
        return None

    async def confirmar_cambio_de_contrasena(self, usuario_id: UUID) -> None:
        if self.error is not None:
            raise self.error
        self.confirmaciones.append(usuario_id)


class AuditoriaEnMemoria:
    """Implementacion del puerto de auditoria, en memoria."""

    def __init__(self) -> None:
        self.eventos: list[EventoAuditoria] = []

    async def registrar(self, evento: EventoAuditoria) -> None:
        self.eventos.append(evento)


def _credencial() -> CredencialSesion:
    return CredencialSesion(
        usuario_id=USUARIO_ID,
        session_id=SESSION_ID,
        expira_en=datetime.now(UTC) + timedelta(hours=1),
        correo="ana@ejemplo.co",
    )


def _contexto() -> AuditContext:
    return AuditContext(
        usuario_id=USUARIO_ID,
        nombre="Ana Restrepo Duque",
        session_id=SESSION_ID,
        rol="analista",
        organizacion_id=ORGANIZACION_ID,
        ip="127.0.0.1",
    )


class TestConfirmacion:
    """La bandera se limpia en la fila del usuario autenticado."""

    async def test_limpia_la_bandera_del_usuario_autenticado(self) -> None:
        perfiles = PerfilesEnMemoria()
        caso = CambiarContrasena(perfiles=perfiles, auditoria=AuditoriaEnMemoria())
        await caso.ejecutar(_credencial(), _contexto())
        assert perfiles.confirmaciones == [USUARIO_ID]

    async def test_devuelve_el_dto_de_confirmacion(self) -> None:
        caso = CambiarContrasena(
            perfiles=PerfilesEnMemoria(),
            auditoria=AuditoriaEnMemoria(),
        )
        resultado = await caso.ejecutar(_credencial(), _contexto())
        assert resultado.usuario_id == USUARIO_ID
        assert resultado.confirmado is True


class TestAuditoria:
    """El hecho queda en la bitacora, con el actor."""

    async def test_registra_el_evento(self) -> None:
        auditoria = AuditoriaEnMemoria()
        caso = CambiarContrasena(perfiles=PerfilesEnMemoria(), auditoria=auditoria)
        await caso.ejecutar(_credencial(), _contexto())
        assert len(auditoria.eventos) == 1
        evento = auditoria.eventos[0]
        assert evento.accion == ACCION_CAMBIO_CONTRASENA
        assert evento.usuario_id == USUARIO_ID
        assert evento.organizacion_id == ORGANIZACION_ID
        assert evento.ip == "127.0.0.1"

    async def test_el_actor_es_el_nombre_del_contexto(self) -> None:
        auditoria = AuditoriaEnMemoria()
        caso = CambiarContrasena(perfiles=PerfilesEnMemoria(), auditoria=auditoria)
        await caso.ejecutar(_credencial(), _contexto())
        assert auditoria.eventos[0].actor == "Ana Restrepo Duque"


class TestErrores:
    """Los errores de dominio no se reenvuelven."""

    async def test_el_error_de_la_base_de_datos_sube_sin_envolver(self) -> None:
        """Si el error se reenvuelve, el 403 se degrada en 500."""
        perfiles = PerfilesEnMemoria(error=ProhibidoError())
        caso = CambiarContrasena(perfiles=perfiles, auditoria=AuditoriaEnMemoria())
        with pytest.raises(ProhibidoError) as excepcion:
            await caso.ejecutar(_credencial(), _contexto())
        assert excepcion.value.status_http == 403

    async def test_si_la_confirmacion_falla_no_se_escribe_la_bitacora(self) -> None:
        """La confirmacion va primero: si falla, no se dice que se confirmo."""
        auditoria = AuditoriaEnMemoria()
        perfiles = PerfilesEnMemoria(error=ProhibidoError())
        caso = CambiarContrasena(perfiles=perfiles, auditoria=auditoria)
        with pytest.raises(ProhibidoError):
            await caso.ejecutar(_credencial(), _contexto())
        assert auditoria.eventos == []
