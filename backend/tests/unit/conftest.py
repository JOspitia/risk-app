"""Piezas compartidas por las pruebas unitarias.

Ninguna prueba unitaria abre un socket. El cliente HTTP se intercepta con
`httpx.MockTransport` y el token se firma con la libreria real: lo que se
prueba es el codigo, no la red.

La base de datos tambien es falsa, pero **no es un mock del repositorio**: es
un mock del transporte HTTP. El repositorio, el mapeo de filas y las consultas
se ejecutan de verdad contra las filas que la base falsa devuelve. Un mock del
repositorio no detectaria un `select` mal escrito, y esa es exactamente la
clase de fallo que la capa 5 de `SKILL.md` 13 busca.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient

from app.config import Config
from app.main import crear_app

SECRETO_DE_PRUEBA = "secreto-de-prueba-para-firmar-los-tokens-de-las-pruebas"
URL_DE_PRUEBA = "https://ejemplo.supabase.co"
EMISOR_DE_PRUEBA = f"{URL_DE_PRUEBA}/auth/v1"
AUDIENCIA = "authenticated"

USUARIO_ID = "3ad2a179-04be-4023-86ff-9bfb0660adf7"
ORGANIZACION_ID = "c41a0000-0000-4000-8000-000000000001"
SESSION_ID = "e5f0cc4f-024f-4b97-aae6-3764ccc4c0cd"

PERFIL_DE_PRUEBA: dict[str, Any] = {
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

MEMBRESIA_DE_PRUEBA: dict[str, Any] = {
    "organizacion_id": ORGANIZACION_ID,
    "rol": "analista",
}


@dataclass
class BaseDeDatosFalsa:
    """Las filas que la base de datos devuelve, y lo que se le pidio."""

    perfil: dict[str, Any] | None = field(default_factory=lambda: dict(PERFIL_DE_PRUEBA))
    membresia: dict[str, Any] | None = field(default_factory=lambda: dict(MEMBRESIA_DE_PRUEBA))
    sesiones_revocadas: list[dict[str, Any]] = field(default_factory=list)
    revocaciones: list[dict[str, Any]] = field(default_factory=list)
    auditoria: list[dict[str, Any]] = field(default_factory=list)
    peticiones: list[httpx.Request] = field(default_factory=list)

    def manejar(self, request: httpx.Request) -> httpx.Response:
        self.peticiones.append(request)
        ruta = request.url.path

        if ruta.endswith("/perfiles"):
            return _json([self.perfil] if self.perfil else [])
        if ruta.endswith("/organizaciones_miembros"):
            return _json([self.membresia] if self.membresia else [])
        if ruta.endswith("/sesiones_revocadas"):
            return _json(self.sesiones_revocadas)
        if ruta.endswith("/rpc/revocar_sesion"):
            self.revocaciones.append(_cuerpo(request))
            return httpx.Response(204)
        if ruta.endswith("/auditoria"):
            self.auditoria.append(_cuerpo(request))
            return httpx.Response(201)
        return httpx.Response(404, json={"code": "PGRST205", "message": "ruta desconocida"})


def _json(cuerpo: Any) -> httpx.Response:
    return httpx.Response(200, json=cuerpo)


def _cuerpo(request: httpx.Request) -> dict[str, Any]:
    return json.loads(request.content.decode("utf-8") or "{}")


@pytest.fixture
def config_de_prueba() -> Config:
    """La configuracion del proceso, construida a mano.

    `tests/conftest.py` borra las variables del entorno: cada prueba construye
    su `Config` a mano, como hace `test_salud.py`.
    """
    return Config(
        supabase_url=URL_DE_PRUEBA,
        supabase_anon_key="pub",
        supabase_service_role_key="srv",
        supabase_jwt_secret=SECRETO_DE_PRUEBA,
    )


@pytest.fixture
def secreto_de_prueba() -> str:
    """El secreto con el que se firman los tokens de prueba.

    PyJWT avisa cuando la clave HMAC es mas corta de 32 bytes, y el
    `pyproject.toml` convierte los avisos en errores: la clave de prueba es
    larga a proposito.
    """
    return SECRETO_DE_PRUEBA


@pytest.fixture
def token_de_prueba() -> Callable[..., str]:
    """Firma un token con el secreto de prueba. Los claims se pueden alterar."""

    def _crear(**desviaciones: Any) -> str:
        ahora = int(time.time())
        claims: dict[str, Any] = {
            "iss": EMISOR_DE_PRUEBA,
            "sub": USUARIO_ID,
            "aud": AUDIENCIA,
            "exp": ahora + 3600,
            "iat": ahora,
            "session_id": SESSION_ID,
            "email": "ana@ejemplo.co",
            "role": "authenticated",
        }
        claims.update(desviaciones)
        return jwt.encode(claims, SECRETO_DE_PRUEBA, algorithm="HS256")

    return _crear


@pytest.fixture
def base_de_datos() -> BaseDeDatosFalsa:
    return BaseDeDatosFalsa()


@pytest.fixture
def cliente(base_de_datos: BaseDeDatosFalsa, config_de_prueba: Config) -> Iterator[TestClient]:
    """La aplicacion real, con el transporte HTTP interceptado."""
    http = httpx.AsyncClient(
        base_url=f"{URL_DE_PRUEBA}/rest/v1/",
        headers={"apikey": config_de_prueba.supabase_anon_key},
        transport=httpx.MockTransport(base_de_datos.manejar),
    )
    with TestClient(crear_app(config=config_de_prueba, cliente_http=http)) as cliente_http:
        yield cliente_http
