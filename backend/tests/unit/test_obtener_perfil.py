"""Pruebas del caso de uso `ObtenerPerfil`.

Es el caso de uso de `GET /api/v1/auth/me`. Sus reglas propias:

1. Sin perfil -> `PerfilInexistenteError` (403), no 404 y no 500.
2. La organizacion y el rol efectivos salen de `organizaciones_miembros`
   (ADR-33), no de `perfiles`.
"""

from __future__ import annotations

from uuid import UUID

import pytest

from app.application.use_cases.obtener_perfil import ObtenerPerfil
from app.domain.entities.perfil import Membresia, Perfil
from app.domain.errors import PerfilInexistenteError

pytestmark = pytest.mark.unit

USUARIO_ID = UUID("3ad2a179-04be-4023-86ff-9bfb0660adf7")
ORGANIZACION_ID = UUID("c41a0000-0000-4000-8000-000000000001")
OTRA_ORGANIZACION_ID = UUID("c41a0000-0000-4000-8000-000000000002")


class PerfilEnMemoria:
    """Implementacion del puerto, en memoria."""

    def __init__(
        self,
        perfil: Perfil | None,
        membresia: Membresia | None = None,
    ) -> None:
        self.perfil = perfil
        self.membresia = membresia
        self.consultas: list[str] = []

    async def obtener(self, usuario_id: UUID) -> Perfil | None:
        self.consultas.append("obtener")
        return self.perfil

    async def membresia_actual(self, usuario_id: UUID) -> Membresia | None:
        self.consultas.append("membresia_actual")
        return self.membresia


def _perfil(**cambios: object) -> Perfil:
    base = {
        "id": USUARIO_ID,
        "nombres": "Ana",
        "apellido_1": "Restrepo",
        "apellido_2": "Duque",
        "display_name": "Ana Restrepo Duque",
        "correo": "ana@ejemplo.co",
        "rol": "analista",
        "organizacion_id": ORGANIZACION_ID,
        "debe_cambiar_contrasena": False,
        "activo": True,
    }
    base.update(cambios)
    return Perfil(**base)  # type: ignore[arg-type]


class TestPerfilExistente:
    """El camino feliz."""

    async def test_devuelve_el_dto_con_los_datos_del_usuario(self) -> None:
        caso = ObtenerPerfil(PerfilEnMemoria(_perfil()))
        resultado = await caso.ejecutar(USUARIO_ID)
        assert resultado.id == USUARIO_ID
        assert resultado.nombres == "Ana"
        assert resultado.apellido_1 == "Restrepo"
        assert resultado.apellido_2 == "Duque"
        assert resultado.display_name == "Ana Restrepo Duque"
        assert resultado.debe_cambiar_contrasena is False

    async def test_no_devuelve_la_entidad_cruda(self) -> None:
        """El caso de uso devuelve un DTO, no la entidad de dominio."""
        caso = ObtenerPerfil(PerfilEnMemoria(_perfil()))
        resultado = await caso.ejecutar(USUARIO_ID)
        assert not isinstance(resultado, Perfil)
        assert not hasattr(resultado, "correo")
        assert not hasattr(resultado, "activo")


class TestPerfilInexistente:
    """SP-07: usuario autenticado sin fila en `perfiles`."""

    async def test_lanza_perfil_inexistente(self) -> None:
        caso = ObtenerPerfil(PerfilEnMemoria(None))
        with pytest.raises(PerfilInexistenteError):
            await caso.ejecutar(USUARIO_ID)

    async def test_el_error_es_403_con_codigo_propio(self) -> None:
        caso = ObtenerPerfil(PerfilEnMemoria(None))
        with pytest.raises(PerfilInexistenteError) as excepcion:
            await caso.ejecutar(USUARIO_ID)
        assert excepcion.value.status_http == 403
        assert excepcion.value.codigo == "perfil_inexistente"


class TestOrganizacionEfectiva:
    """La organizacion y el rol salen de la membresia (ADR-33)."""

    async def test_la_membresia_manda_sobre_el_perfil(self) -> None:
        perfil = _perfil(rol="analista", organizacion_id=ORGANIZACION_ID)
        membresia = Membresia(organizacion_id=OTRA_ORGANIZACION_ID, rol="admin")
        caso = ObtenerPerfil(PerfilEnMemoria(perfil, membresia))
        resultado = await caso.ejecutar(USUARIO_ID)
        assert resultado.organizacion_id == OTRA_ORGANIZACION_ID
        assert resultado.rol == "admin"

    async def test_sin_membresia_se_usa_el_perfil(self) -> None:
        caso = ObtenerPerfil(PerfilEnMemoria(_perfil(), None))
        resultado = await caso.ejecutar(USUARIO_ID)
        assert resultado.organizacion_id == ORGANIZACION_ID
        assert resultado.rol == "analista"

    async def test_sin_membresia_ni_organizacion_la_organizacion_es_nula(self) -> None:
        caso = ObtenerPerfil(PerfilEnMemoria(_perfil(organizacion_id=None), None))
        resultado = await caso.ejecutar(USUARIO_ID)
        assert resultado.organizacion_id is None
