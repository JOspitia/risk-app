"""La guarda de `revocar_sesion`, contra Supabase real.

La pertenencia de una sesion la comprueba la **base de datos**, no el backend:
la funcion de Postgres compara el `session_id` que se pide revocar con el
claim del token de quien llama, y con la sesion viva en `auth.sessions`.

Verificado el 2026-11-27 contra el stack local con la migracion 012 aplicada.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Config

from .conftest import UsuarioDePrueba

pytestmark = pytest.mark.integration

RUTA_PERFIL = "/api/v1/auth/me"
EXPIRA_EN_LEJANO = "2099-01-01T00:00:00+00:00"


def _autorizado(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class TestRevocarLaSesionDeOtro:
    """El acceso cruzado a sesiones de otra persona se rechaza."""

    def test_la_funcion_rechaza_la_sesion_de_otro_usuario(
        self,
        config_local: Config,
        usuario_de_prueba: Callable[..., UsuarioDePrueba],
    ) -> None:
        atacante = usuario_de_prueba(nombres="Atacante")
        victima = usuario_de_prueba(nombres="Victima")

        with httpx.Client(
            base_url=f"{config_local.supabase_url}/rest/v1/",
            headers={"apikey": config_local.supabase_anon_key},
        ) as http:
            respuesta = http.post(
                "rpc/revocar_sesion",
                json={
                    "p_session_id": victima.session_id,
                    "p_expira_en": EXPIRA_EN_LEJANO,
                },
                headers=_autorizado(atacante.token),
            )

        assert respuesta.status_code == 403
        assert respuesta.json()["code"] == "42501"

    def test_la_sesion_de_la_victima_sigue_sirviendo(
        self,
        cliente: TestClient,
        config_local: Config,
        usuario_de_prueba: Callable[..., UsuarioDePrueba],
    ) -> None:
        atacante = usuario_de_prueba(nombres="Atacante")
        victima = usuario_de_prueba(nombres="Victima")

        with httpx.Client(
            base_url=f"{config_local.supabase_url}/rest/v1/",
            headers={"apikey": config_local.supabase_anon_key},
        ) as http:
            http.post(
                "rpc/revocar_sesion",
                json={
                    "p_session_id": victima.session_id,
                    "p_expira_en": EXPIRA_EN_LEJANO,
                },
                headers=_autorizado(atacante.token),
            )

        assert cliente.get(RUTA_PERFIL, headers=_autorizado(victima.token)).status_code == 200

    def test_un_session_id_inventado_se_rechaza(
        self,
        config_local: Config,
        usuario_de_prueba: Callable[..., UsuarioDePrueba],
    ) -> None:
        """No se revoca una sesion que no es de nadie."""
        atacante = usuario_de_prueba(nombres="Atacante")

        with httpx.Client(
            base_url=f"{config_local.supabase_url}/rest/v1/",
            headers={"apikey": config_local.supabase_anon_key},
        ) as http:
            respuesta = http.post(
                "rpc/revocar_sesion",
                json={
                    "p_session_id": "00000000-0000-4000-8000-000000000000",
                    "p_expira_en": EXPIRA_EN_LEJANO,
                },
                headers=_autorizado(atacante.token),
            )

        assert respuesta.status_code == 403
        assert respuesta.json()["code"] == "42501"

    def test_sin_token_no_se_puede_revocar(
        self,
        config_local: Config,
        usuario_de_prueba: Callable[..., UsuarioDePrueba],
    ) -> None:
        """El ACL de la migracion 010 sigue en pie: `anon` no ejecuta la funcion."""
        usuario = usuario_de_prueba()

        with httpx.Client(
            base_url=f"{config_local.supabase_url}/rest/v1/",
            headers={"apikey": config_local.supabase_anon_key},
        ) as http:
            respuesta = http.post(
                "rpc/revocar_sesion",
                json={
                    "p_session_id": usuario.session_id,
                    "p_expira_en": EXPIRA_EN_LEJANO,
                },
            )

        assert respuesta.status_code == 401


class TestInsercionDirecta:
    """La politica de alta tambien comprueba la pertenencia."""

    def test_no_se_puede_insertar_la_revocacion_de_otro(
        self,
        config_local: Config,
        usuario_de_prueba: Callable[..., UsuarioDePrueba],
    ) -> None:
        """Sin esta guarda, un usuario podria invalidar el token de otro."""
        atacante = usuario_de_prueba(nombres="Atacante")
        victima = usuario_de_prueba(nombres="Victima")

        with httpx.Client(
            base_url=f"{config_local.supabase_url}/rest/v1/",
            headers={"apikey": config_local.supabase_anon_key},
        ) as http:
            respuesta = http.post(
                "sesiones_revocadas",
                json={
                    "session_id": victima.session_id,
                    "usuario_id": atacante.id,
                    "expira_en": EXPIRA_EN_LEJANO,
                },
                headers=_autorizado(atacante.token),
            )

        assert respuesta.status_code == 403

    def test_la_sesion_de_la_victima_sigue_sirviendo(
        self,
        cliente: TestClient,
        config_local: Config,
        usuario_de_prueba: Callable[..., UsuarioDePrueba],
    ) -> None:
        atacante = usuario_de_prueba(nombres="Atacante")
        victima = usuario_de_prueba(nombres="Victima")

        with httpx.Client(
            base_url=f"{config_local.supabase_url}/rest/v1/",
            headers={"apikey": config_local.supabase_anon_key},
        ) as http:
            http.post(
                "sesiones_revocadas",
                json={
                    "session_id": victima.session_id,
                    "usuario_id": atacante.id,
                    "expira_en": EXPIRA_EN_LEJANO,
                },
                headers=_autorizado(atacante.token),
            )

        assert cliente.get(RUTA_PERFIL, headers=_autorizado(victima.token)).status_code == 200
