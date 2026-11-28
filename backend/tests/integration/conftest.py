"""Piezas compartidas por las pruebas contra Supabase real.

La capa 4 de `SKILL.md` 13 (ciclo de vida de la sesion) solo tiene valor contra
la base de datos de verdad: RLS, Auth y las funciones de Postgres no se
simulan. Un mock de repositorio no detectaria ni un error de politica ni una
consulta mal escrita.

Por eso estas pruebas necesitan el stack local en marcha y las variables del
entorno. **Las llaves no se escriben en ningun archivo del repositorio**: se
leen del entorno y se pasan por el comando.

El entorno se captura **al importar este modulo**, antes de que
`tests/conftest.py` borre las variables para el resto de la suite.

Se habla con Supabase por HTTP y no con el SDK: el SDK construye clientes
internos que no deja cerrar, y el `pyproject.toml` convierte los avisos en
errores. Ademas, el camino que importa es el del backend: HTTP con el JWT del
usuario.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient

from app.config import Config
from app.main import crear_app

VARIABLES_DEL_ENTORNO = (
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_JWT_SECRET",
)

ENTORNO = {variable: os.environ.get(variable) for variable in VARIABLES_DEL_ENTORNO}

CLAVE_DE_PRUEBA = "ClaveSegura123!"


@dataclass
class UsuarioDePrueba:
    """Un usuario real de Supabase Auth, con su perfil y su sesion."""

    id: str
    correo: str
    organizacion_id: str
    token: str
    session_id: str


class AdministracionSupabase:
    """Operaciones de administracion contra la API de Supabase.

    La llave de servicio se usa **solo** aqui: para crear y borrar usuarios
    de prueba. Ninguna peticion de usuario final pasa por este cliente
    (CA-08).
    """

    def __init__(self, url: str, llave: str) -> None:
        self._url = url.rstrip("/")
        self._http = httpx.Client(
            base_url=f"{self._url}/",
            headers={"apikey": llave, "Authorization": f"Bearer {llave}"},
            timeout=30.0,
        )

    def cerrar(self) -> None:
        self._http.close()

    def crear_usuario(self, correo: str, clave: str, confirmar: bool = True) -> str:
        respuesta = self._http.post(
            "auth/v1/admin/users",
            json={"email": correo, "password": clave, "email_confirm": confirmar},
        )
        respuesta.raise_for_status()
        return str(respuesta.json()["id"])

    def bloquear_usuario(self, usuario_id: str, horas: int = 876_000) -> None:
        respuesta = self._http.put(
            f"auth/v1/admin/users/{usuario_id}",
            json={"ban_duration": f"{horas}h"},
        )
        respuesta.raise_for_status()

    def eliminar_usuario(self, usuario_id: str) -> None:
        """Borra el usuario de Auth.

        GoTrue hace un borrado **logico**: la fila de `auth.users` se queda, y
        por eso el borrado en cascada de `perfiles` no ocurre. La fila del
        perfil se borra aparte, en `limpiar_usuario`.
        """
        respuesta = self._http.delete(f"auth/v1/admin/users/{usuario_id}")
        if respuesta.status_code != 404:
            respuesta.raise_for_status()

    def limpiar_usuario(self, usuario_id: str) -> None:
        """Deja la base sin rastros del usuario de prueba.

        El perfil se borra a mano porque el borrado logico de Auth no dispara
        la cascada, y `perfiles.organizacion_id` no admite `on delete cascade`:
        mientras el perfil exista, la organizacion no se puede borrar.

        Lo mismo pasa con la bitacora: `auditoria.organizacion_id` no admite
        `on delete cascade`, asi que las filas del usuario bloquean el borrado
        de su organizacion.
        """
        self.borrar("auditoria", {"usuario_id": f"eq.{usuario_id}"})
        self.borrar("sesiones_revocadas", {"usuario_id": f"eq.{usuario_id}"})
        self.borrar("perfiles", {"id": f"eq.{usuario_id}"})
        self.borrar("organizaciones_miembros", {"usuario_id": f"eq.{usuario_id}"})
        self.eliminar_usuario(usuario_id)

    def insertar(self, tabla: str, fila: dict[str, Any]) -> dict[str, Any]:
        respuesta = self._http.post(
            f"rest/v1/{tabla}",
            json=fila,
            headers={"Prefer": "return=representation"},
        )
        respuesta.raise_for_status()
        return dict(respuesta.json()[0])

    def filas(self, tabla: str, filtros: dict[str, str]) -> list[dict[str, Any]]:
        respuesta = self._http.get(f"rest/v1/{tabla}", params=filtros)
        respuesta.raise_for_status()
        return list(respuesta.json())

    def borrar(self, tabla: str, filtros: dict[str, str]) -> None:
        respuesta = self._http.delete(f"rest/v1/{tabla}", params=filtros)
        respuesta.raise_for_status()


def intentar_iniciar_sesion(
    url: str,
    llave_anonima: str,
    correo: str,
    clave: str = CLAVE_DE_PRUEBA,
) -> httpx.Response:
    """El login del SDK de Supabase, tal como lo hace el navegador."""
    return httpx.post(
        f"{url.rstrip('/')}/auth/v1/token",
        params={"grant_type": "password"},
        json={"email": correo, "password": clave},
        headers={"apikey": llave_anonima},
        timeout=30.0,
    )


def iniciar_sesion(
    url: str,
    llave_anonima: str,
    correo: str,
    clave: str = CLAVE_DE_PRUEBA,
) -> str:
    """El token de acceso de la sesion."""
    respuesta = intentar_iniciar_sesion(url, llave_anonima, correo, clave)
    respuesta.raise_for_status()
    return str(respuesta.json()["access_token"])


@pytest.fixture(scope="session")
def config_local() -> Config:
    """La configuracion del stack local.

    Sin estas variables las pruebas se **saltan**, no fallan: una suite que
    falla porque el stack local no esta en marcha ensucia el resultado.
    """
    faltantes = [variable for variable, valor in ENTORNO.items() if not valor]
    if faltantes:
        pytest.skip(
            "Faltan las variables del Supabase local: " + ", ".join(faltantes),
        )
    return Config(
        supabase_url=ENTORNO["SUPABASE_URL"] or "",
        supabase_anon_key=ENTORNO["SUPABASE_ANON_KEY"] or "",
        supabase_service_role_key=ENTORNO["SUPABASE_SERVICE_ROLE_KEY"] or "",
        supabase_jwt_secret=ENTORNO["SUPABASE_JWT_SECRET"],
    )


@pytest.fixture(scope="session")
def admin(config_local: Config) -> Iterator[AdministracionSupabase]:
    """El cliente de administracion. Solo crea y borra usuarios de prueba."""
    cliente = AdministracionSupabase(
        config_local.supabase_url,
        config_local.supabase_service_role_key,
    )
    yield cliente
    cliente.cerrar()


@pytest.fixture(scope="session")
def usuario_de_prueba(
    admin: AdministracionSupabase,
    config_local: Config,
) -> Iterator[Callable[..., UsuarioDePrueba]]:
    """Crea usuarios reales, con perfil y membresia, y los borra al terminar."""
    usuarios: list[str] = []
    organizaciones: list[str] = []

    def _crear(
        nombres: str = "Ana",
        activo: bool = True,
        con_perfil: bool = True,
        con_membresia: bool = True,
        apellido_2: str | None = "Integracion",
        rol: str = "analista",
    ) -> UsuarioDePrueba:
        correo = f"prueba-{uuid.uuid4().hex[:10]}@ejemplo.co"
        usuario_id = admin.crear_usuario(correo, CLAVE_DE_PRUEBA)
        usuarios.append(usuario_id)

        organizacion = admin.insertar(
            "organizaciones",
            {"nombre": f"Equipo de {nombres}"},
        )
        organizacion_id = str(organizacion["id"])
        organizaciones.append(organizacion_id)

        if con_perfil:
            admin.insertar(
                "perfiles",
                {
                    "id": usuario_id,
                    "nombres": nombres,
                    "apellido_1": "Prueba",
                    "apellido_2": apellido_2,
                    "display_name": f"{nombres} Prueba Integracion",
                    "correo": correo,
                    "rol": rol,
                    "organizacion_id": organizacion_id,
                    "debe_cambiar_contrasena": False,
                    "activo": activo,
                },
            )
        if con_membresia:
            admin.insertar(
                "organizaciones_miembros",
                {
                    "organizacion_id": organizacion_id,
                    "usuario_id": usuario_id,
                    "rol": rol,
                },
            )

        token = iniciar_sesion(config_local.supabase_url, config_local.supabase_anon_key, correo)
        claims = claims_de(token)
        return UsuarioDePrueba(
            id=usuario_id,
            correo=correo,
            organizacion_id=organizacion_id,
            token=token,
            session_id=str(claims["session_id"]),
        )

    yield _crear

    for usuario_id in usuarios:
        admin.limpiar_usuario(usuario_id)
    if organizaciones:
        admin.borrar("organizaciones", {"id": f"in.({','.join(organizaciones)})"})


@pytest.fixture
def cliente(config_local: Config) -> Iterator[TestClient]:
    """La aplicacion real, contra el Supabase local."""
    with TestClient(crear_app(config=config_local)) as cliente_http:
        yield cliente_http


def claims_de(token: str) -> dict[str, Any]:
    """Los claims de un token, sin verificar: solo para armar pruebas."""
    return dict(jwt.decode(token, options={"verify_signature": False}))


def actualizar_perfil(
    url: str,
    llave_anonima: str,
    token: str,
    usuario_id: str,
    cambios: dict[str, Any],
) -> httpx.Response:
    """Un `UPDATE` a `perfiles` hecho con el JWT del propio usuario.

    Es la via que usa el frontend: PostgREST con el token del usuario, no con
    la llave de servicio. Por eso decide la politica de RLS, y no el codigo de
    Python.
    """
    return httpx.patch(
        f"{url.rstrip('/')}/rest/v1/perfiles",
        params={"id": f"eq.{usuario_id}"},
        json=cambios,
        headers={
            "apikey": llave_anonima,
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )
