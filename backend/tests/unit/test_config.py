"""Pruebas de la configuracion.

La configuracion es la primera linea de codigo del proyecto y la que mas
fallos silenciosos produce: un valor por defecto utilizable hace que el
arranque funcione en la maquina del desarrollador y falle en produccion.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import Config

pytestmark = pytest.mark.unit


class TestVariablesObligatorias:
    """Sin una variable obligatoria, la app no arranca."""

    @pytest.mark.parametrize(
        "variable",
        ["supabase_url", "supabase_anon_key", "supabase_service_role_key"],
    )
    def test_falla_si_falta_una_obligatoria(self, variable: str) -> None:
        datos = {
            "supabase_url": "https://ejemplo.supabase.co",
            "supabase_anon_key": "pub",
            "supabase_service_role_key": "srv",
        }
        datos.pop(variable)

        with pytest.raises(ValidationError):
            Config(**datos)

    def test_no_hay_valor_por_defecto_utilizable(self) -> None:
        """La URL de Supabase no puede tener un default: sin ella no hay proyecto."""
        with pytest.raises(ValidationError):
            Config(
                supabase_anon_key="pub",
                supabase_service_role_key="srv",
            )


class TestOrigenesCors:
    """CORS con credenciales y `*` es una combinacion que no se permite."""

    def test_parte_la_lista_por_comas(self) -> None:
        config = Config(
            supabase_url="https://ejemplo.supabase.co",
            supabase_anon_key="pub",
            supabase_service_role_key="srv",
            cors_origins="http://localhost:5173, http://localhost:4173",
        )
        assert config.cors_origins == ["http://localhost:5173", "http://localhost:4173"]

    def test_rechaza_el_comodin(self) -> None:
        with pytest.raises(ValidationError, match="CORS_ORIGINS"):
            Config(
                supabase_url="https://ejemplo.supabase.co",
                supabase_anon_key="pub",
                supabase_service_role_key="srv",
                cors_origins="*",
            )


class TestUrlsDerivadas:
    """El emisor del JWT y el JWKS se derivan de la URL del proyecto."""

    def test_el_emisor_es_auth_v1(self) -> None:
        config = Config(
            supabase_url="https://ejemplo.supabase.co",
            supabase_anon_key="pub",
            supabase_service_role_key="srv",
        )
        assert config.jwt_issuer == "https://ejemplo.supabase.co/auth/v1"

    def test_el_jwks_se_deriva_cuando_no_se_da(self) -> None:
        config = Config(
            supabase_url="https://ejemplo.supabase.co",
            supabase_anon_key="pub",
            supabase_service_role_key="srv",
        )
        assert config.jwks_url == ("https://ejemplo.supabase.co/auth/v1/.well-known/jwks.json")

    def test_el_jwks_explicito_manda(self) -> None:
        config = Config(
            supabase_url="https://ejemplo.supabase.co",
            supabase_anon_key="pub",
            supabase_service_role_key="srv",
            supabase_jwks_url="https://otro.supabase.co/jwks.json",
        )
        assert config.jwks_url == "https://otro.supabase.co/jwks.json"

    def test_la_barra_final_no_se_duplica(self) -> None:
        config = Config(
            supabase_url="https://ejemplo.supabase.co/",
            supabase_anon_key="pub",
            supabase_service_role_key="srv",
        )
        assert config.jwt_issuer == "https://ejemplo.supabase.co/auth/v1"
