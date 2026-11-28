"""Capa 4 — Ciclo de vida de la sesion, contra Supabase real.

Estos son los casos que de verdad rompen las integraciones de frontend
(`SKILL.md` 13.4). No hay mocks: la peticion va al stack local, con RLS, con
Auth y con las funciones de Postgres de verdad.

Lo que se afirma:

- Peticion autenticada con token valido -> 200.
- Peticion sin token, con token malformado o con firma adulterada -> 401.
- Dos sesiones del mismo usuario funcionan las dos.
- Logout: el token deja de servir **de inmediato**.
- Revocar la sesion de otro usuario -> 403.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient

from app.config import Config

from .conftest import (
    CLAVE_DE_PRUEBA,
    AdministracionSupabase,
    UsuarioDePrueba,
    claims_de,
    iniciar_sesion,
    intentar_iniciar_sesion,
)

pytestmark = pytest.mark.integration

RUTA_PERFIL = "/api/v1/auth/me"
RUTA_LOGOUT = "/api/v1/auth/logout"


def _autorizado(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _token_firmado(
    config_local: Config,
    **claims: Any,
) -> str:
    """Un token firmado con el secreto del proyecto local."""
    ahora = int(time.time())
    base: dict[str, Any] = {
        "iss": config_local.jwt_issuer,
        "sub": "3ad2a179-04be-4023-86ff-9bfb0660adf7",
        "aud": "authenticated",
        "exp": ahora + 3600,
        "iat": ahora,
        "session_id": "e5f0cc4f-024f-4b97-aae6-3764ccc4c0cd",
    }
    base.update(claims)
    return jwt.encode(base, config_local.supabase_jwt_secret or "", algorithm="HS256")


class TestPeticionAutenticada:
    """La ruta protegida con una credencial valida."""

    def test_responde_200(
        self,
        cliente: TestClient,
        usuario_de_prueba: Callable[..., UsuarioDePrueba],
    ) -> None:
        usuario = usuario_de_prueba()
        respuesta = cliente.get(RUTA_PERFIL, headers=_autorizado(usuario.token))
        assert respuesta.status_code == 200

    def test_el_perfil_es_el_del_usuario(
        self,
        cliente: TestClient,
        usuario_de_prueba: Callable[..., UsuarioDePrueba],
    ) -> None:
        usuario = usuario_de_prueba(nombres="Camila")
        cuerpo = cliente.get(RUTA_PERFIL, headers=_autorizado(usuario.token)).json()
        assert cuerpo["data"]["id"] == usuario.id
        assert cuerpo["data"]["nombres"] == "Camila"
        assert cuerpo["data"]["rol"] == "analista"
        assert cuerpo["data"]["organizacion_id"] == usuario.organizacion_id


class TestPeticionSinCredencial:
    """Sin token, con token roto: 401, nunca 500."""

    def test_sin_token_responde_401(self, cliente: TestClient) -> None:
        respuesta = cliente.get(RUTA_PERFIL)
        assert respuesta.status_code == 401
        assert respuesta.json()["errors"][0]["codigo"] == "no_autenticado"

    def test_token_malformado_responde_401(self, cliente: TestClient) -> None:
        respuesta = cliente.get(RUTA_PERFIL, headers=_autorizado("no-es-un-jwt"))
        assert respuesta.status_code == 401

    def test_firma_adulterada_responde_401(
        self,
        cliente: TestClient,
        usuario_de_prueba: Callable[..., UsuarioDePrueba],
    ) -> None:
        usuario = usuario_de_prueba()
        token = usuario.token
        adulterado = token[:-4] + ("aaaa" if not token.endswith("aaaa") else "bbbb")
        respuesta = cliente.get(RUTA_PERFIL, headers=_autorizado(adulterado))
        assert respuesta.status_code == 401

    def test_token_de_otro_proyecto_responde_401(
        self,
        cliente: TestClient,
        config_local: Config,
    ) -> None:
        """SP-09: un token de otro proyecto no verifica."""
        token = _token_firmado(config_local, iss="https://otro-proyecto.supabase.co/auth/v1")
        respuesta = cliente.get(RUTA_PERFIL, headers=_autorizado(token))
        assert respuesta.status_code == 401

    def test_audiencia_incorrecta_responde_401(
        self,
        cliente: TestClient,
        config_local: Config,
    ) -> None:
        token = _token_firmado(config_local, aud="otra-audiencia")
        respuesta = cliente.get(RUTA_PERFIL, headers=_autorizado(token))
        assert respuesta.status_code == 401

    def test_emisor_incorrecto_responde_401(
        self,
        cliente: TestClient,
        config_local: Config,
    ) -> None:
        token = _token_firmado(config_local, iss="https://otro-proyecto.supabase.co/auth/v1")
        respuesta = cliente.get(RUTA_PERFIL, headers=_autorizado(token))
        assert respuesta.status_code == 401

    def test_token_vencido_responde_401(
        self,
        cliente: TestClient,
        config_local: Config,
    ) -> None:
        ahora = int(time.time())
        token = _token_firmado(config_local, exp=ahora - 60, iat=ahora - 3600)
        respuesta = cliente.get(RUTA_PERFIL, headers=_autorizado(token))
        assert respuesta.status_code == 401


class TestVariasSesiones:
    """Dos sesiones del mismo usuario funcionan las dos (CA-14, EC-01)."""

    def test_las_dos_sesiones_sirven(
        self,
        cliente: TestClient,
        usuario_de_prueba: Callable[..., UsuarioDePrueba],
        config_local: Config,
    ) -> None:
        usuario = usuario_de_prueba()
        segundo_token = iniciar_sesion(
            config_local.supabase_url,
            config_local.supabase_anon_key,
            usuario.correo,
        )
        assert segundo_token != usuario.token

        assert cliente.get(RUTA_PERFIL, headers=_autorizado(usuario.token)).status_code == 200
        assert cliente.get(RUTA_PERFIL, headers=_autorizado(segundo_token)).status_code == 200

    def test_cerrar_una_sesion_no_afecta_a_la_otra(
        self,
        cliente: TestClient,
        usuario_de_prueba: Callable[..., UsuarioDePrueba],
        config_local: Config,
    ) -> None:
        usuario = usuario_de_prueba()
        segundo_token = iniciar_sesion(
            config_local.supabase_url,
            config_local.supabase_anon_key,
            usuario.correo,
        )

        respuesta = cliente.post(RUTA_LOGOUT, headers=_autorizado(usuario.token))
        assert respuesta.status_code == 200

        assert cliente.get(RUTA_PERFIL, headers=_autorizado(usuario.token)).status_code == 401
        assert cliente.get(RUTA_PERFIL, headers=_autorizado(segundo_token)).status_code == 200


class TestCierreDeSesion:
    """El logout invalida el token de inmediato (CA-11, ADR-31)."""

    def test_el_logout_responde_200(
        self,
        cliente: TestClient,
        usuario_de_prueba: Callable[..., UsuarioDePrueba],
    ) -> None:
        usuario = usuario_de_prueba()
        respuesta = cliente.post(RUTA_LOGOUT, headers=_autorizado(usuario.token))
        assert respuesta.status_code == 200

    def test_el_token_deja_de_servir_de_inmediato(
        self,
        cliente: TestClient,
        usuario_de_prueba: Callable[..., UsuarioDePrueba],
    ) -> None:
        usuario = usuario_de_prueba()
        assert cliente.get(RUTA_PERFIL, headers=_autorizado(usuario.token)).status_code == 200
        assert cliente.post(RUTA_LOGOUT, headers=_autorizado(usuario.token)).status_code == 200
        assert cliente.get(RUTA_PERFIL, headers=_autorizado(usuario.token)).status_code == 401

    def test_la_sesion_queda_registrada_como_revocada(
        self,
        cliente: TestClient,
        admin: AdministracionSupabase,
        usuario_de_prueba: Callable[..., UsuarioDePrueba],
    ) -> None:
        usuario = usuario_de_prueba()
        cliente.post(RUTA_LOGOUT, headers=_autorizado(usuario.token))

        revocadas = admin.filas(
            "sesiones_revocadas",
            {"select": "session_id,usuario_id", "session_id": f"eq.{usuario.session_id}"},
        )
        assert len(revocadas) == 1
        assert revocadas[0]["usuario_id"] == usuario.id

    def test_el_evento_queda_en_la_bitacora(
        self,
        cliente: TestClient,
        admin: AdministracionSupabase,
        usuario_de_prueba: Callable[..., UsuarioDePrueba],
    ) -> None:
        usuario = usuario_de_prueba()
        cliente.post(RUTA_LOGOUT, headers=_autorizado(usuario.token))

        eventos = admin.filas(
            "auditoria",
            {
                "select": "accion,usuario_id",
                "accion": "eq.sesion.cerrada",
                "usuario_id": f"eq.{usuario.id}",
            },
        )
        assert len(eventos) == 1

    def test_el_logout_sin_token_responde_401(self, cliente: TestClient) -> None:
        assert cliente.post(RUTA_LOGOUT).status_code == 401


class TestCuentaNoUtilizable:
    """Una cuenta inactiva, bloqueada o eliminada no puede iniciar sesion."""

    def test_cuenta_sin_confirmar_no_inicia_sesion(
        self,
        config_local: Config,
        admin: AdministracionSupabase,
    ) -> None:
        correo = f"sin-confirmar-{uuid.uuid4().hex[:8]}@ejemplo.co"
        usuario_id = admin.crear_usuario(correo, CLAVE_DE_PRUEBA, confirmar=False)
        try:
            respuesta = intentar_iniciar_sesion(
                config_local.supabase_url,
                config_local.supabase_anon_key,
                correo,
            )
            assert respuesta.status_code >= 400
        finally:
            admin.eliminar_usuario(usuario_id)

    def test_cuenta_bloqueada_no_inicia_sesion(
        self,
        config_local: Config,
        admin: AdministracionSupabase,
    ) -> None:
        correo = f"bloqueada-{uuid.uuid4().hex[:8]}@ejemplo.co"
        usuario_id = admin.crear_usuario(correo, CLAVE_DE_PRUEBA)
        try:
            admin.bloquear_usuario(usuario_id)
            respuesta = intentar_iniciar_sesion(
                config_local.supabase_url,
                config_local.supabase_anon_key,
                correo,
            )
            assert respuesta.status_code >= 400
        finally:
            admin.limpiar_usuario(usuario_id)

    def test_cuenta_eliminada_no_inicia_sesion(
        self,
        config_local: Config,
        admin: AdministracionSupabase,
    ) -> None:
        correo = f"eliminada-{uuid.uuid4().hex[:8]}@ejemplo.co"
        usuario_id = admin.crear_usuario(correo, CLAVE_DE_PRUEBA)
        admin.eliminar_usuario(usuario_id)
        respuesta = intentar_iniciar_sesion(
            config_local.supabase_url,
            config_local.supabase_anon_key,
            correo,
        )
        assert respuesta.status_code >= 400

    def test_el_token_de_una_cuenta_eliminada_deja_de_servir(
        self,
        cliente: TestClient,
        admin: AdministracionSupabase,
        usuario_de_prueba: Callable[..., UsuarioDePrueba],
    ) -> None:
        """El token deja de servir, aunque la fila de `perfiles` ya no este.

        El codigo es `403 perfil_inexistente` y no 401: el backend no consulta
        `auth.users` (HU-01, seccion 6), asi que no puede distinguir "la
        cuenta se borro" de "nunca tuvo perfil". SP-07 manda: 403 con el
        codigo `perfil_inexistente`.
        """
        usuario = usuario_de_prueba()
        assert cliente.get(RUTA_PERFIL, headers=_autorizado(usuario.token)).status_code == 200

        admin.eliminar_usuario(usuario.id)

        respuesta = cliente.get(RUTA_PERFIL, headers=_autorizado(usuario.token))
        assert respuesta.status_code != 200
        assert respuesta.json()["errors"][0]["codigo"] == "perfil_inexistente"


class TestPerfilInexistente:
    """SP-07: usuario autenticado sin fila en `perfiles`."""

    def test_responde_403_con_el_codigo_propio(
        self,
        cliente: TestClient,
        usuario_de_prueba: Callable[..., UsuarioDePrueba],
    ) -> None:
        usuario = usuario_de_prueba(con_perfil=False)
        respuesta = cliente.get(RUTA_PERFIL, headers=_autorizado(usuario.token))
        assert respuesta.status_code == 403
        assert respuesta.json()["errors"][0]["codigo"] == "perfil_inexistente"


class TestAislamiento:
    """Cada usuario ve su perfil, no el de otro (CA-09)."""

    def test_no_se_ve_el_perfil_de_otra_organizacion(
        self,
        cliente: TestClient,
        usuario_de_prueba: Callable[..., UsuarioDePrueba],
    ) -> None:
        usuario = usuario_de_prueba(nombres="Ana")
        otro = usuario_de_prueba(nombres="Beto")
        assert usuario.organizacion_id != otro.organizacion_id

        cuerpo = cliente.get(RUTA_PERFIL, headers=_autorizado(usuario.token)).json()
        assert cuerpo["data"]["id"] == usuario.id
        assert cuerpo["data"]["organizacion_id"] == usuario.organizacion_id


class TestClaimsDelToken:
    """El claim `session_id` es la llave de revocacion (ADR-31)."""

    def test_el_token_lleva_el_session_id(
        self,
        usuario_de_prueba: Callable[..., UsuarioDePrueba],
    ) -> None:
        usuario = usuario_de_prueba()
        claims: dict[str, Any] = claims_de(usuario.token)
        assert claims["session_id"] == usuario.session_id
