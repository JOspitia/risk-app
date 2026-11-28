"""Pruebas de la capa HTTP de autenticacion.

La ruta protegida tiene que rechazar con 401 **todo** token que no vale, y
nunca con 500. Y el envelope tiene que ser el mismo en exito y en error.

La base de datos es falsa (ver `conftest.py`), pero el repositorio, el mapeo
de filas y las consultas se ejecutan de verdad: lo que se prueba es el
comportamiento del endpoint, no un mock del caso de uso.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.adapters.http.middleware import ACCION_ANOMALIA_AUTORIZACION

from .conftest import BaseDeDatosFalsa

pytestmark = pytest.mark.unit

CAMPOS_DEL_ENVELOPE = {"success", "message", "data", "errors", "timestamp"}


class TestRutaProtegida:
    """`GET /api/v1/auth/me` sin credencial valida."""

    def test_sin_token_responde_401(self, cliente: TestClient) -> None:
        respuesta = cliente.get("/api/v1/auth/me")
        assert respuesta.status_code == 401

    def test_sin_token_el_codigo_es_no_autenticado(self, cliente: TestClient) -> None:
        cuerpo = cliente.get("/api/v1/auth/me").json()
        assert cuerpo["errors"][0]["codigo"] == "no_autenticado"

    def test_token_malformado_responde_401(self, cliente: TestClient) -> None:
        respuesta = cliente.get("/api/v1/auth/me", headers={"Authorization": "Bearer no-es-un-jwt"})
        assert respuesta.status_code == 401

    def test_token_con_firma_adulterada_responde_401(self, cliente: TestClient) -> None:
        token = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ4In0.aaaa"
        respuesta = cliente.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert respuesta.status_code == 401

    def test_sin_la_palabra_bearer_responde_401(self, cliente: TestClient) -> None:
        """CE-02: el backend no adivina el formato del header."""
        respuesta = cliente.get("/api/v1/auth/me", headers={"Authorization": "un-token-cualquiera"})
        assert respuesta.status_code == 401

    def test_bearer_sin_token_responde_401(self, cliente: TestClient) -> None:
        """CE-01: `Authorization: Bearer` y nada mas."""
        respuesta = cliente.get("/api/v1/auth/me", headers={"Authorization": "Bearer"})
        assert respuesta.status_code == 401

    def test_bearer_con_espacios_responde_401(self, cliente: TestClient) -> None:
        """CE-03: se recorta, y si sigue siendo invalido, 401."""
        respuesta = cliente.get("/api/v1/auth/me", headers={"Authorization": "Bearer   "})
        assert respuesta.status_code == 401

    def test_el_token_en_el_cuerpo_se_ignora(self, cliente: TestClient) -> None:
        """CE-05: el token se lee solo del header."""
        respuesta = cliente.post("/api/v1/auth/me", json={"token": "algo"})
        assert respuesta.status_code == 405

    def test_el_token_en_la_query_se_ignora(self, cliente: TestClient) -> None:
        respuesta = cliente.get("/api/v1/auth/me?access_token=algo")
        assert respuesta.status_code == 401

    def test_el_error_no_es_500(self, cliente: TestClient) -> None:
        respuesta = cliente.get("/api/v1/auth/me", headers={"Authorization": "Bearer no-es-un-jwt"})
        assert respuesta.status_code != 500


class TestTokenValido:
    """`GET /api/v1/auth/me` con credencial valida."""

    def test_responde_200(self, cliente: TestClient, token_de_prueba: Any) -> None:
        respuesta = cliente.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token_de_prueba()}"},
        )
        assert respuesta.status_code == 200

    def test_el_perfil_va_dentro_del_envelope(
        self,
        cliente: TestClient,
        token_de_prueba: Any,
    ) -> None:
        cuerpo = cliente.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token_de_prueba()}"},
        ).json()
        assert cuerpo["success"] is True
        assert cuerpo["errors"] is None
        assert cuerpo["data"]["nombres"] == "Ana"
        assert cuerpo["data"]["apellido_1"] == "Restrepo"
        assert cuerpo["data"]["rol"] == "analista"
        assert cuerpo["data"]["organizacion_id"] == "c41a0000-0000-4000-8000-000000000001"
        assert cuerpo["data"]["debe_cambiar_contrasena"] is False

    def test_el_envelope_tiene_los_cinco_campos(
        self,
        cliente: TestClient,
        token_de_prueba: Any,
    ) -> None:
        cuerpo = cliente.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token_de_prueba()}"},
        ).json()
        assert set(cuerpo) == CAMPOS_DEL_ENVELOPE

    def test_la_respuesta_no_filtra_datos_sensibles(
        self,
        cliente: TestClient,
        token_de_prueba: Any,
    ) -> None:
        """CA-07: ni `auth.users`, ni hash, ni refresh token, ni llave de servicio."""
        respuesta = cliente.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token_de_prueba()}"},
        )
        texto = respuesta.text
        for prohibido in ("password_hash", "refresh_token", "service_role", "auth.users"):
            assert prohibido not in texto
        assert set(respuesta.json()["data"]) == {
            "id",
            "nombres",
            "apellido_1",
            "apellido_2",
            "display_name",
            "rol",
            "organizacion_id",
            "debe_cambiar_contrasena",
        }

    def test_el_token_del_usuario_viaja_a_la_base_de_datos(
        self,
        cliente: TestClient,
        token_de_prueba: Any,
        base_de_datos: BaseDeDatosFalsa,
    ) -> None:
        """La peticion propaga el JWT del usuario: por eso RLS filtra."""
        token = token_de_prueba()
        cliente.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        peticiones_con_token = [
            p for p in base_de_datos.peticiones if p.headers.get("authorization")
        ]
        assert peticiones_con_token
        for peticion in peticiones_con_token:
            assert peticion.headers["authorization"] == f"Bearer {token}"

    def test_la_llave_de_servicio_no_viaja(
        self,
        cliente: TestClient,
        token_de_prueba: Any,
        base_de_datos: BaseDeDatosFalsa,
    ) -> None:
        """CA-08: la llave de servicio no atiende peticiones de usuario."""
        cliente.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_de_prueba()}"})
        for peticion in base_de_datos.peticiones:
            assert "srv" not in peticion.headers.get("authorization", "")


class TestPerfilInexistente:
    """SP-07: token valido, pero sin fila en `perfiles`."""

    def test_responde_403(
        self,
        cliente: TestClient,
        token_de_prueba: Any,
        base_de_datos: BaseDeDatosFalsa,
    ) -> None:
        base_de_datos.perfil = None
        respuesta = cliente.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token_de_prueba()}"},
        )
        assert respuesta.status_code == 403

    def test_el_codigo_es_perfil_inexistente(
        self,
        cliente: TestClient,
        token_de_prueba: Any,
        base_de_datos: BaseDeDatosFalsa,
    ) -> None:
        base_de_datos.perfil = None
        cuerpo = cliente.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token_de_prueba()}"},
        ).json()
        assert cuerpo["errors"][0]["codigo"] == "perfil_inexistente"


class TestSesionRevocada:
    """Un token de una sesion revocada deja de servir."""

    def test_responde_401(
        self,
        cliente: TestClient,
        token_de_prueba: Any,
        base_de_datos: BaseDeDatosFalsa,
    ) -> None:
        base_de_datos.sesiones_revocadas = [
            {
                "session_id": "e5f0cc4f-024f-4b97-aae6-3764ccc4c0cd",
                "usuario_id": "3ad2a179-04be-4023-86ff-9bfb0660adf7",
                "revocado_en": "2026-11-27T12:00:00+00:00",
                "expira_en": "2099-01-01T00:00:00+00:00",
            }
        ]
        respuesta = cliente.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token_de_prueba()}"},
        )
        assert respuesta.status_code == 401


class TestCierreDeSesion:
    """`POST /api/v1/auth/logout`."""

    def test_responde_200(
        self,
        cliente: TestClient,
        token_de_prueba: Any,
    ) -> None:
        respuesta = cliente.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {token_de_prueba()}"},
        )
        assert respuesta.status_code == 200

    def test_revuoca_la_sesion_del_token(
        self,
        cliente: TestClient,
        token_de_prueba: Any,
        base_de_datos: BaseDeDatosFalsa,
    ) -> None:
        cliente.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {token_de_prueba()}"},
        )
        assert len(base_de_datos.revocaciones) == 1
        assert (
            base_de_datos.revocaciones[0]["p_session_id"]
            == "e5f0cc4f-024f-4b97-aae6-3764ccc4c0cd"
        )

    def test_registra_el_evento_en_la_bitacora(
        self,
        cliente: TestClient,
        token_de_prueba: Any,
        base_de_datos: BaseDeDatosFalsa,
    ) -> None:
        cliente.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {token_de_prueba()}"},
        )
        assert len(base_de_datos.auditoria) == 1
        assert base_de_datos.auditoria[0]["accion"] == "sesion.cerrada"
        assert base_de_datos.auditoria[0]["usuario_id"] == (
            "3ad2a179-04be-4023-86ff-9bfb0660adf7"
        )

    def test_el_cuerpo_vacio_no_es_problema(
        self,
        cliente: TestClient,
        token_de_prueba: Any,
    ) -> None:
        """CE-06: cerrar sesion no necesita cuerpo."""
        respuesta = cliente.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {token_de_prueba()}"},
        )
        assert respuesta.status_code == 200

    def test_sin_token_responde_401(self, cliente: TestClient) -> None:
        assert cliente.post("/api/v1/auth/logout").status_code == 401


class TestNoHayLogin:
    """CA-03: el backend no emite tokens."""

    def test_el_endpoint_de_login_no_existe(self, cliente: TestClient) -> None:
        respuesta = cliente.post("/api/v1/auth/login", json={})
        assert respuesta.status_code == 404

    def test_no_hay_ningun_endpoint_que_emita_un_token(self, cliente: TestClient) -> None:
        rutas = cliente.get("/openapi.json").json()["paths"]
        assert "/api/v1/auth/login" not in rutas
        for metodo in rutas:
            assert "login" not in metodo, f"Ruta sospechosa: {metodo}"
            assert "token" not in metodo, f"Ruta sospechosa: {metodo}"


class TestHeaderRepetido:
    """CE-07: se toma el primero y se deja la anomalia en la bitacora."""

    def test_toma_el_primer_token(
        self,
        cliente: TestClient,
        token_de_prueba: Any,
    ) -> None:
        primero = token_de_prueba()
        segundo = token_de_prueba(session_id="otro-sesion")
        respuesta = cliente.get(
            "/api/v1/auth/me",
            headers=[
                ("Authorization", f"Bearer {primero}"),
                ("Authorization", f"Bearer {segundo}"),
            ],
        )
        assert respuesta.status_code == 200

    def test_registra_la_anomalia(
        self,
        cliente: TestClient,
        token_de_prueba: Any,
        base_de_datos: BaseDeDatosFalsa,
    ) -> None:
        primero = token_de_prueba()
        cliente.get(
            "/api/v1/auth/me",
            headers=[("Authorization", f"Bearer {primero}"), ("Authorization", "Bearer otro")],
        )
        acciones = [evento["accion"] for evento in base_de_datos.auditoria]
        assert ACCION_ANOMALIA_AUTORIZACION in acciones
