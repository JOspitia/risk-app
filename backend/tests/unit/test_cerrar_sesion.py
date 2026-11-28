"""Pruebas del caso de uso `CerrarSesion`.

El cierre de sesion tiene que ser efectivo de inmediato (ADR-31): el token
deja de servir en la peticion siguiente, sin esperar su expiracion natural.

Aqui se comprueba el **contrato** del caso de uso: que revoca, que registra y
que no envuelve los errores.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from app.application.audit.contexto import AuditContext
from app.application.use_cases.cerrar_sesion import ACCION_CIERRE_SESION, CerrarSesion
from app.domain.entities.auditoria import EventoAuditoria
from app.domain.entities.credencial import CredencialSesion
from app.domain.errors import SesionNoRevocableError

pytestmark = pytest.mark.unit

USUARIO_ID = UUID("3ad2a179-04be-4023-86ff-9bfb0660adf7")
ORGANIZACION_ID = UUID("c41a0000-0000-4000-8000-000000000001")
SESSION_ID = "e5f0cc4f-024f-4b97-aae6-3764ccc4c0cd"


class SesionesEnMemoria:
    """Implementacion del puerto de revocaciones, en memoria."""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.revocaciones: list[tuple[str, UUID, datetime]] = []

    async def esta_revocada(self, session_id: str) -> bool:
        return False

    async def revocar(self, session_id: str, usuario_id: UUID, expira_en: datetime) -> None:
        if self.error is not None:
            raise self.error
        self.revocaciones.append((session_id, usuario_id, expira_en))


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


class TestRevocacion:
    """La sesion que se revoca es la del token, con su expiracion."""

    async def test_revoca_la_sesion_del_token(self) -> None:
        sesiones = SesionesEnMemoria()
        caso = CerrarSesion(sesiones=sesiones, auditoria=AuditoriaEnMemoria())
        await caso.ejecutar(_credencial(), _contexto())
        assert len(sesiones.revocaciones) == 1
        session_id, usuario_id, _ = sesiones.revocaciones[0]
        assert session_id == SESSION_ID
        assert usuario_id == USUARIO_ID

    async def test_revoca_con_la_expiracion_del_token(self) -> None:
        """La revocacion caduca con el token: por eso guarda su `exp`."""
        sesiones = SesionesEnMemoria()
        credencial = _credencial()
        caso = CerrarSesion(sesiones=sesiones, auditoria=AuditoriaEnMemoria())
        await caso.ejecutar(credencial, _contexto())
        _, _, expira_en = sesiones.revocaciones[0]
        assert expira_en == credencial.expira_en

    async def test_devuelve_el_dto_de_cierre(self) -> None:
        caso = CerrarSesion(sesiones=SesionesEnMemoria(), auditoria=AuditoriaEnMemoria())
        resultado = await caso.ejecutar(_credencial(), _contexto())
        assert resultado.session_id == SESSION_ID
        assert resultado.revocado is True


class TestAuditoria:
    """El hecho queda en la bitacora, con el actor."""

    async def test_registra_el_evento(self) -> None:
        auditoria = AuditoriaEnMemoria()
        caso = CerrarSesion(sesiones=SesionesEnMemoria(), auditoria=auditoria)
        await caso.ejecutar(_credencial(), _contexto())
        assert len(auditoria.eventos) == 1
        evento = auditoria.eventos[0]
        assert evento.accion == ACCION_CIERRE_SESION
        assert evento.usuario_id == USUARIO_ID
        assert evento.organizacion_id == ORGANIZACION_ID
        assert evento.ip == "127.0.0.1"
        assert evento.detalles == {"session_id": SESSION_ID}

    async def test_el_actor_es_el_nombre_del_contexto(self) -> None:
        auditoria = AuditoriaEnMemoria()
        caso = CerrarSesion(sesiones=SesionesEnMemoria(), auditoria=auditoria)
        await caso.ejecutar(_credencial(), _contexto())
        assert auditoria.eventos[0].actor == "Ana Restrepo Duque"


class TestErrores:
    """Los errores de dominio no se reenvuelven."""

    async def test_el_error_de_la_base_de_datos_sube_sin_envolver(self) -> None:
        """Si el error se reenvuelve, el 403 se degrada en 500."""
        sesiones = SesionesEnMemoria(error=SesionNoRevocableError())
        caso = CerrarSesion(sesiones=sesiones, auditoria=AuditoriaEnMemoria())
        with pytest.raises(SesionNoRevocableError) as excepcion:
            await caso.ejecutar(_credencial(), _contexto())
        assert excepcion.value.status_http == 403

    async def test_si_la_revocacion_falla_no_se_escribe_la_bitacora(self) -> None:
        """La revocacion va primero: si falla, no se dice que se cerro."""
        auditoria = AuditoriaEnMemoria()
        sesiones = SesionesEnMemoria(error=SesionNoRevocableError())
        caso = CerrarSesion(sesiones=sesiones, auditoria=auditoria)
        with pytest.raises(SesionNoRevocableError):
            await caso.ejecutar(_credencial(), _contexto())
        assert auditoria.eventos == []
