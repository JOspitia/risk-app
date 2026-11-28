"""Pruebas de la validacion del token.

Son los siete pasos de `SKILL.md` 5.2, y cada fallo tiene que ser un token
rechazado, **nunca** un 500. Aqui se prueba el validador directamente, sin
base de datos y sin red.

Las dos vias de firma se prueban:

- **HS256**, con `SUPABASE_JWT_SECRET`: es la de los proyectos con claves
  simetricas.
- **JWKS**, con las claves publicas del proyecto: es la via por defecto (ADR-31,
  Gate 2 del checklist). El JWKS se sirve desde un archivo local, asi que la
  prueba no necesita red.
"""

from __future__ import annotations

import time
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from jwt.jwks_client import PyJWKClient

from app.adapters.http.middleware import TokenInvalidoError, ValidadorToken
from app.config import Config

pytestmark = pytest.mark.unit

KID_DE_PRUEBA = "llave-de-prueba"


class ClienteJwksEnMemoria(PyJWKClient):
    """El cliente real de PyJWT, con la descarga del JWKS resuelta en memoria.

    Se sustituye **solo** la descarga: la eleccion de la clave por `kid` y la
    verificacion de la firma son las de PyJWT. La prueba no abre un socket.
    """

    def __init__(self, jwks: dict[str, Any]) -> None:
        super().__init__(uri="https://ejemplo.supabase.co/auth/v1/.well-known/jwks.json")
        self._jwks = jwks

    def fetch_data(self) -> Any:
        return self._jwks


def _claims(**desviaciones: Any) -> dict[str, Any]:
    ahora = int(time.time())
    base: dict[str, Any] = {
        "iss": "https://ejemplo.supabase.co/auth/v1",
        "sub": "3ad2a179-04be-4023-86ff-9bfb0660adf7",
        "aud": "authenticated",
        "exp": ahora + 3600,
        "iat": ahora,
        "session_id": "e5f0cc4f-024f-4b97-aae6-3764ccc4c0cd",
        "email": "ana@ejemplo.co",
        "role": "authenticated",
    }
    base.update(desviaciones)
    return base


class TestTokenValido:
    """Un token bien formado pasa y produce la credencial."""

    async def test_devuelve_la_credencial(
        self,
        config_de_prueba: Config,
        token_de_prueba: Any,
    ) -> None:
        credencial = await ValidadorToken(config_de_prueba).validar(token_de_prueba())
        assert str(credencial.usuario_id) == "3ad2a179-04be-4023-86ff-9bfb0660adf7"
        assert credencial.session_id == "e5f0cc4f-024f-4b97-aae6-3764ccc4c0cd"
        assert credencial.correo == "ana@ejemplo.co"
        assert credencial.expira_en.timestamp() > time.time()

    def test_el_emisor_esperado_es_el_del_proyecto(self, config_de_prueba: Config) -> None:
        """`iss` es `{SUPABASE_URL}/auth/v1`, no una cadena de la aplicacion."""
        assert config_de_prueba.jwt_issuer == "https://ejemplo.supabase.co/auth/v1"


class TestTokensRechazados:
    """Todo token invalido se rechaza. Ninguno produce una excepcion distinta."""

    async def test_token_malformado(self, config_de_prueba: Config) -> None:
        with pytest.raises(TokenInvalidoError):
            await ValidadorToken(config_de_prueba).validar("esto-no-es-un-jwt")

    async def test_token_opaco(self, config_de_prueba: Config) -> None:
        with pytest.raises(TokenInvalidoError):
            await ValidadorToken(config_de_prueba).validar("a" * 40)

    async def test_firma_adulterada(
        self,
        config_de_prueba: Config,
        token_de_prueba: Any,
    ) -> None:
        token = token_de_prueba()
        adulterado = token[:-4] + ("aaaa" if not token.endswith("aaaa") else "bbbb")
        with pytest.raises(TokenInvalidoError):
            await ValidadorToken(config_de_prueba).validar(adulterado)

    async def test_firmado_con_otro_secreto(self, config_de_prueba: Config) -> None:
        token = jwt.encode(_claims(), "otro-secreto-que-no-es-el-del-proyecto", algorithm="HS256")
        with pytest.raises(TokenInvalidoError):
            await ValidadorToken(config_de_prueba).validar(token)

    async def test_vencido(self, config_de_prueba: Config, token_de_prueba: Any) -> None:
        token = token_de_prueba(exp=int(time.time()) - 60)
        with pytest.raises(TokenInvalidoError):
            await ValidadorToken(config_de_prueba).validar(token)

    async def test_audiencia_incorrecta(
        self,
        config_de_prueba: Config,
        token_de_prueba: Any,
    ) -> None:
        token = token_de_prueba(aud="otra-audiencia")
        with pytest.raises(TokenInvalidoError):
            await ValidadorToken(config_de_prueba).validar(token)

    async def test_emisor_incorrecta(self, config_de_prueba: Config, token_de_prueba: Any) -> None:
        token = token_de_prueba(iss="https://otro-proyecto.supabase.co/auth/v1")
        with pytest.raises(TokenInvalidoError):
            await ValidadorToken(config_de_prueba).validar(token)

    async def test_emitido_en_el_futuro(
        self,
        config_de_prueba: Config,
        token_de_prueba: Any,
    ) -> None:
        """CE-08: `exp` en el pasado y `iat` en el futuro."""
        token = token_de_prueba(exp=int(time.time()) - 60, iat=int(time.time()) + 3600)
        with pytest.raises(TokenInvalidoError):
            await ValidadorToken(config_de_prueba).validar(token)

    async def test_sin_session_id(self, config_de_prueba: Config, secreto_de_prueba: str) -> None:
        """Sin `session_id` el token no se puede revocar: no sirve."""
        claims = _claims()
        del claims["session_id"]
        token = jwt.encode(claims, secreto_de_prueba, algorithm="HS256")
        with pytest.raises(TokenInvalidoError):
            await ValidadorToken(config_de_prueba).validar(token)

    async def test_sin_sub(self, config_de_prueba: Config, secreto_de_prueba: str) -> None:
        claims = _claims()
        del claims["sub"]
        token = jwt.encode(claims, secreto_de_prueba, algorithm="HS256")
        with pytest.raises(TokenInvalidoError):
            await ValidadorToken(config_de_prueba).validar(token)


class TestViaDelJwks:
    """La via por defecto: las claves publicas del proyecto (ADR-31)."""

    @staticmethod
    def _jwks() -> tuple[dict[str, Any], ec.EllipticCurvePrivateKey]:
        privada = ec.generate_private_key(ec.SECP256R1())
        jwk = jwt.algorithms.ECAlgorithm.to_jwk(privada.public_key(), as_dict=True)
        jwk.update({"kid": KID_DE_PRUEBA, "alg": "ES256", "use": "sig"})
        return {"keys": [jwk]}, privada

    def _validador_jwks(
        self,
        config_de_prueba: Config,
        jwks: dict[str, Any],
    ) -> ValidadorToken:
        config = config_de_prueba.model_copy(update={"supabase_jwt_secret": None})
        return ValidadorToken(config, cliente_jwks=ClienteJwksEnMemoria(jwks))

    async def test_acepta_un_token_firmado_con_la_clave_del_jwks(
        self,
        config_de_prueba: Config,
    ) -> None:
        jwks, privada = self._jwks()
        token = jwt.encode(
            _claims(),
            privada,
            algorithm="ES256",
            headers={"kid": KID_DE_PRUEBA},
        )

        credencial = await self._validador_jwks(config_de_prueba, jwks).validar(token)
        assert str(credencial.usuario_id) == "3ad2a179-04be-4023-86ff-9bfb0660adf7"
        assert credencial.session_id == "e5f0cc4f-024f-4b97-aae6-3764ccc4c0cd"

    async def test_rechaza_un_token_firmado_con_otra_clave(
        self,
        config_de_prueba: Config,
    ) -> None:
        jwks, _ = self._jwks()
        otra = ec.generate_private_key(ec.SECP256R1())
        token = jwt.encode(
            _claims(),
            otra,
            algorithm="ES256",
            headers={"kid": KID_DE_PRUEBA},
        )

        with pytest.raises(TokenInvalidoError):
            await self._validador_jwks(config_de_prueba, jwks).validar(token)

    async def test_rechaza_un_token_hs256_cuando_el_proyecto_usa_jwks(
        self,
        config_de_prueba: Config,
        token_de_prueba: Any,
    ) -> None:
        """Con JWKS, un token firmado con el secreto simetrico no vale."""
        jwks, _ = self._jwks()
        token = token_de_prueba()

        with pytest.raises(TokenInvalidoError):
            await self._validador_jwks(config_de_prueba, jwks).validar(token)
