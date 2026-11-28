"""Pruebas del cliente de PostgREST.

El adaptador es donde se decide que credencial viaja en cada peticion, y esa
decision es la que sostiene el aislamiento. Ademas, los filtros de PostgREST
son la parte que mas se rompe en silencio: un `eq.` de mas convierte un
`gt.` en `eq.gt.` y la consulta deja de filtrar lo que debe filtrar.

Estas pruebas interceptan el transporte HTTP: no hay red.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import httpx
import pytest

from app.adapters.supabase.cliente import ClienteDatos
from app.adapters.supabase.sesiones import SesionRevocadaRepositorySupabase
from app.domain.errors import (
    ErrorInesperado,
    NoAutenticadoError,
    NoEncontradoError,
    ProhibidoError,
    SesionNoRevocableError,
)

pytestmark = pytest.mark.unit

URL = "https://ejemplo.supabase.co/rest/v1/"
USUARIO_ID = UUID("3ad2a179-04be-4023-86ff-9bfb0660adf7")
SESSION_ID = "e5f0cc4f-024f-4b97-aae6-3764ccc4c0cd"


def _cliente(
    manejador: Any,
    token: str | None = None,
) -> tuple[ClienteDatos, list[httpx.Request]]:
    peticiones: list[httpx.Request] = []

    def _capturar(peticion: httpx.Request) -> httpx.Response:
        peticiones.append(peticion)
        return manejador(peticion)

    http = httpx.AsyncClient(
        base_url=URL,
        headers={"apikey": "pub"},
        transport=httpx.MockTransport(_capturar),
    )
    return ClienteDatos(http=http, token=token), peticiones


class TestCredencialQueViaja:
    """La peticion lleva el JWT del usuario, nunca la llave de servicio."""

    async def test_la_credencial_es_el_token_del_usuario(self) -> None:
        cliente, peticiones = _cliente(lambda _: httpx.Response(200, json=[]), token="el-jwt")
        await cliente.seleccionar("perfiles", "id", {"id": "eq.1"})
        assert peticiones[0].headers["authorization"] == "Bearer el-jwt"

    async def test_la_llave_publica_siempre_viaja(self) -> None:
        cliente, peticiones = _cliente(lambda _: httpx.Response(200, json=[]), token="el-jwt")
        await cliente.seleccionar("perfiles", "id", {"id": "eq.1"})
        assert peticiones[0].headers["apikey"] == "pub"

    async def test_sin_token_no_hay_cabecera_authorization(self) -> None:
        cliente, peticiones = _cliente(lambda _: httpx.Response(200, json=[]))
        await cliente.seleccionar("perfiles", "id", {"id": "eq.1"})
        assert "authorization" not in peticiones[0].headers


class TestFiltros:
    """El operador del filtro se escribe explicito: `eq.` no se antepone."""

    async def test_el_filtro_usa_el_operador_dado(self) -> None:
        cliente, peticiones = _cliente(lambda _: httpx.Response(200, json=[]))
        await cliente.seleccionar(
            "sesiones_revocadas",
            "session_id",
            {"session_id": "eq.abc", "expira_en": "gt.2026-11-27T12:00:00+00:00"},
        )
        url = str(peticiones[0].url)
        assert "session_id=eq.abc" in url
        assert "expira_en=gt.2026-11-27" in url
        assert "eq.gt." not in url

    async def test_los_valores_viajan_codificados(self) -> None:
        """El valor es un parametro, no texto pegado en la URL.

        La comilla viaja codificada, asi que no puede cerrar el valor del
        filtro: es lo que impide una inyeccion por el filtro.
        """
        cliente, peticiones = _cliente(lambda _: httpx.Response(200, json=[]))
        await cliente.seleccionar("perfiles", "id", {"correo": "eq.ana' OR '1'='1"})
        url = str(peticiones[0].url)
        assert "'" not in url
        assert "%27" in url


class TestErroresDePostgRest:
    """El codigo de la base de datos se traduce al error de dominio."""

    async def test_42501_es_una_sesion_que_no_es_del_usuario(self) -> None:
        cliente, _ = _cliente(
            lambda _: httpx.Response(
                403,
                json={"code": "42501", "message": "la sesion no pertenece al usuario"},
            ),
        )
        with pytest.raises(SesionNoRevocableError):
            await cliente.llamar_rpc("revocar_sesion", {"p_session_id": "x"})

    async def test_401_es_no_autenticado(self) -> None:
        cliente, _ = _cliente(lambda _: httpx.Response(401, json={"message": "token invalido"}))
        with pytest.raises(NoAutenticadoError):
            await cliente.seleccionar("perfiles", "id", {"id": "eq.1"})

    async def test_403_es_prohibido(self) -> None:
        cliente, _ = _cliente(lambda _: httpx.Response(403, json={"message": "sin permiso"}))
        with pytest.raises(ProhibidoError):
            await cliente.seleccionar("perfiles", "id", {"id": "eq.1"})

    async def test_404_es_no_encontrado(self) -> None:
        cliente, _ = _cliente(lambda _: httpx.Response(404, json={"message": "no existe"}))
        with pytest.raises(NoEncontradoError):
            await cliente.seleccionar("perfiles", "id", {"id": "eq.1"})

    async def test_un_error_desconocido_no_se_reescribe(self) -> None:
        """El original viaja en `detalle`: no se pierde para la depuracion."""
        cliente, _ = _cliente(
            lambda _: httpx.Response(400, json={"code": "22007", "message": "timestamp invalido"}),
        )
        with pytest.raises(ErrorInesperado) as excepcion:
            await cliente.seleccionar("perfiles", "id", {"id": "eq.1"})
        assert "timestamp invalido" in (excepcion.value.detalle or "")


class TestRevocacion:
    """La consulta de revocacion, con su filtro por `expira_en`."""

    async def test_filtra_por_sesion_y_por_expiracion(self) -> None:
        cliente, peticiones = _cliente(lambda _: httpx.Response(200, json=[]), token="el-jwt")
        repositorio = SesionRevocadaRepositorySupabase(cliente)
        await repositorio.esta_revocada(SESSION_ID)
        url = str(peticiones[0].url)
        assert f"session_id=eq.{SESSION_ID}" in url
        assert "expira_en=gt." in url
        assert "limit=1" in url

    async def test_una_sesion_revocada_devuelve_true(self) -> None:
        cliente, _ = _cliente(
            lambda _: httpx.Response(
                200,
                json=[{"session_id": SESSION_ID, "usuario_id": str(USUARIO_ID)}],
            ),
        )
        repositorio = SesionRevocadaRepositorySupabase(cliente)
        assert await repositorio.esta_revocada(SESSION_ID) is True

    async def test_una_sesion_viva_devuelve_false(self) -> None:
        cliente, _ = _cliente(lambda _: httpx.Response(200, json=[]))
        repositorio = SesionRevocadaRepositorySupabase(cliente)
        assert await repositorio.esta_revocada(SESSION_ID) is False

    async def test_la_revocacion_no_manda_el_usuario(self) -> None:
        """El usuario lo toma la funcion de `auth.uid()`: si lo mandamos,
        abririamos la puerta a revocar la sesion de otro."""
        cliente, peticiones = _cliente(lambda _: httpx.Response(204), token="el-jwt")
        repositorio = SesionRevocadaRepositorySupabase(cliente)
        await repositorio.revocar(
            SESSION_ID,
            USUARIO_ID,
            datetime.now(UTC) + timedelta(hours=1),
        )
        cuerpo = peticiones[0].content.decode("utf-8")
        assert "p_session_id" in cuerpo
        assert "usuario_id" not in cuerpo
