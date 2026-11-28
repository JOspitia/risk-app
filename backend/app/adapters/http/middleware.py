"""Middleware de contexto de auditoria.

Es el "filtro de autenticacion" de `SKILL.md` 1.11. Hace exactamente siete
pasos, en este orden (`SKILL.md` 5.2):

1. Extraer el bearer token del header `Authorization`.
2. Verificar la firma. La clave publica sale del **JWKS del proyecto**; el
   secreto simetrico (`SUPABASE_JWT_SECRET`) solo se usa cuando el proyecto
   tiene claves simetricas (ADR-31, Gate 2 del checklist).
3. Verificar `exp`, `aud` e `iss`. El emisor esperado es
   `{SUPABASE_URL}/auth/v1`, no una cadena inventada por la aplicacion.
4. Verificar que el `session_id` no este revocado.
5. Resolver el perfil (rol, organizacion) desde `perfiles`.
6. Construir el `AuditContext`.
7. Si algo falla -> **contexto anonimo**. Los endpoints protegidos llaman a un
   guard, y el guard levanta el 401.

Dos reglas que no se negocian:

- El token se lee **solo** del header `Authorization`. Nunca del cuerpo ni de
  la query (CE-05).
- Una credencial invalida **no** es un 401 inmediato: es un contexto anonimo.
  El 401 lo levanta el guard de la ruta protegida, y asi una ruta publica
  (como `/health`) sigue respondiendo sin token.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import jwt
from fastapi import Request
from jwt.jwks_client import PyJWKClient
from starlette.datastructures import Headers
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.adapters.supabase.auditoria import AuditoriaRepositorySupabase
from app.adapters.supabase.cliente import ClienteDatos
from app.adapters.supabase.perfiles import PerfilRepositorySupabase
from app.adapters.supabase.sesiones import SesionRevocadaRepositorySupabase
from app.application.audit.contexto import AuditContext
from app.application.dto.perfil import PerfilDTO
from app.application.use_cases.obtener_perfil import ObtenerPerfil
from app.config import Config
from app.domain.entities.auditoria import EventoAuditoria
from app.domain.entities.credencial import CredencialSesion
from app.domain.errors import ErrorInesperado, PerfilInexistenteError

logger = logging.getLogger(__name__)

# La audiencia que emite Supabase Auth para un usuario con sesion.
# `Config` todavia no la expone como variable de entorno; mientras tanto, la
# convencion de Supabase Auth es la que manda (HU-01, seccion 4).
AUDIENCIA_AUTENTICADO = "authenticated"

# Los claims que un token de sesion tiene que traer. Faltar cualquiera de
# ellos invalida el token: un token sin `session_id` no se puede revocar.
CLAIMS_REQUERIDOS = ("exp", "aud", "iss", "sub", "session_id")

PREFIJO_BEARER = "bearer"

# El algoritmo simetrico: solo aplica a los proyectos con claves simetricas.
ALGORITMO_SIMETRICO = "HS256"

# Los algoritmos asimetricos: se verifican con el JWKS del proyecto.
ALGORITMOS_ASIMETRICOS = (
    "RS256",
    "RS384",
    "RS512",
    "PS256",
    "PS384",
    "PS512",
    "ES256",
    "ES384",
    "ES512",
    "EdDSA",
)

# Accion con la que se registra la anomalia del header repetido (CE-07).
ACCION_ANOMALIA_AUTORIZACION = "sesion.anomalia_autorizacion"


class TokenInvalidoError(Exception):
    """El token no pasa la validacion.

    El motivo se registra en el log y **no** viaja al cliente: distinguir
    "firma invalida" de "vencido" en la respuesta es informacion para quien
    intenta adivinar un token.
    """

    def __init__(self, motivo: str) -> None:
        super().__init__(motivo)
        self.motivo = motivo


@dataclass(frozen=True)
class TokenExtraido:
    """El token del header `Authorization` y si el header venia repetido."""

    token: str | None
    header_repetido: bool


def extraer_token(headers: Headers) -> TokenExtraido:
    """Lee el token **solo** del header `Authorization`.

    - `Authorization: Bearer <token>` -> el token.
    - `Authorization: Bearer` (sin token) -> nada (CE-01).
    - `Authorization: <token>` (sin `Bearer`) -> nada (CE-02): el backend no
      adivina el formato.
    - Espacios al principio o al final -> se recortan (CE-03).
    - Header repetido -> se toma el primero y se marca la anomalia (CE-07).

    Un header repetido puede llegar como dos cabeceras o como una sola con
    comas. Las dos formas se tratan igual.
    """
    valores = headers.getlist("authorization")
    if not valores:
        return TokenExtraido(token=None, header_repetido=False)

    repetido = len(valores) > 1
    valor = valores[0].strip()

    if "," in valor:
        # Varias credenciales en una sola cabecera: se toma la primera.
        repetido = True
        valor = valor.split(",", 1)[0].strip()

    if not valor:
        return TokenExtraido(token=None, header_repetido=repetido)

    partes = valor.split(None, 1)
    if len(partes) != 2 or partes[0].lower() != PREFIJO_BEARER:
        return TokenExtraido(token=None, header_repetido=repetido)

    token = partes[1].strip()
    if not token:
        return TokenExtraido(token=None, header_repetido=repetido)
    return TokenExtraido(token=token, header_repetido=repetido)


class ValidadorToken:
    """Verifica el token que emite Supabase Auth.

    La via por defecto son las **claves publicas del proyecto** (JWKS): es lo
    que usan los proyectos con claves asimetricas, y el JWKS dice en su
    cabecera que algoritmo se uso.

    `SUPABASE_JWT_SECRET` es el camino alternativo, y solo aplica a los
    tokens `HS256`: es el de los proyectos con claves simetricas. Que la
    variable este en el entorno **no** decide el algoritmo: lo decide el
    token. Un proyecto con claves asimetricas que todavia tenga el secreto
    viejo en el entorno sigue validando por JWKS, que es lo que pide Gate 2.

    Verificado el 2026-11-28 contra el stack local: el token de acceso viene
    firmado con `ES256` y el JWKS del proyecto publica la clave `ES256`
    correspondiente, aunque el secreto simetrico siga presente en el entorno.
    """

    def __init__(self, config: Config, cliente_jwks: PyJWKClient | None = None) -> None:
        self._config = config
        self._secreto = config.supabase_jwt_secret
        self._cliente_jwks = cliente_jwks or PyJWKClient(config.jwks_url)

    async def validar(self, token: str) -> CredencialSesion:
        """Devuelve la credencial que el token acredita, o falla.

        Falla con `TokenInvalidoError` para **cualquier** token que no pase la
        validacion: malformado, con firma adulterada, vencido, con `aud` o
        `iss` que no son los del proyecto, o al que le falta un claim.
        """
        claims = await self._decodificar(token)
        return _credencial_desde_claims(claims)

    async def _decodificar(self, token: str) -> dict[str, Any]:
        opciones = {
            "require": list(CLAIMS_REQUERIDOS),
            "verify_aud": True,
            "verify_iss": True,
            "verify_exp": True,
        }
        algoritmo = _algoritmo_del_token(token)

        try:
            if algoritmo == ALGORITMO_SIMETRICO:
                if self._secreto is None:
                    raise TokenInvalidoError("sin_secreto_para_hs256")
                return jwt.decode(
                    token,
                    self._secreto,
                    algorithms=[ALGORITMO_SIMETRICO],
                    audience=AUDIENCIA_AUTENTICADO,
                    issuer=self._config.jwt_issuer,
                    options=opciones,
                )
            if algoritmo not in ALGORITMOS_ASIMETRICOS:
                raise TokenInvalidoError("algoritmo_no_permitido")
            clave = await asyncio.to_thread(
                self._cliente_jwks.get_signing_key_from_jwt,
                token,
            )
            return jwt.decode(
                token,
                clave.key,
                algorithms=[clave.algorithm_name],
                audience=AUDIENCIA_AUTENTICADO,
                issuer=self._config.jwt_issuer,
                options=opciones,
            )
        except TokenInvalidoError:
            raise
        except jwt.PyJWTError as exc:
            raise TokenInvalidoError(type(exc).__name__) from exc
        except Exception as exc:  # pragma: no cover - red caida, no el token
            raise TokenInvalidoError(type(exc).__name__) from exc


def _algoritmo_del_token(token: str) -> str:
    """El algoritmo con el que el token dice estar firmado.

    Se lee **sin verificar**: todavia no se sabe si la firma es buena. Solo
    decide de donde sale la clave con la que se verifica.
    """
    try:
        segmento = token.split(".")[0]
        relleno = "=" * ((4 - len(segmento) % 4) % 4)
        cabecera = json.loads(
            base64.urlsafe_b64decode(segmento + relleno).decode("utf-8"),
        )
    except (ValueError, IndexError, UnicodeDecodeError) as exc:
        raise TokenInvalidoError("token_malformado") from exc
    if not isinstance(cabecera, dict):
        raise TokenInvalidoError("token_malformado")
    return str(cabecera.get("alg", ""))


def _credencial_desde_claims(claims: dict[str, Any]) -> CredencialSesion:
    """Los claims verificados a la credencial de dominio."""
    try:
        usuario_id = UUID(str(claims["sub"]))
        session_id = str(claims["session_id"])
        expira_en = datetime.fromtimestamp(int(claims["exp"]), tz=UTC)
    except (KeyError, TypeError, ValueError) as exc:
        raise TokenInvalidoError("claims_invalidos") from exc

    correo = claims.get("email")
    return CredencialSesion(
        usuario_id=usuario_id,
        session_id=session_id,
        expira_en=expira_en,
        correo=str(correo) if correo else None,
    )


class ContextoAuditoriaMiddleware(BaseHTTPMiddleware):
    """Construye el contexto antes del handler.

    Credenciales invalidas -> contexto **anonimo**, no 401 inmediato. Los
    endpoints protegidos llaman a un guard.
    """

    def __init__(self, app: Any, config: Config) -> None:
        super().__init__(app)
        self._config = config
        self._validador = ValidadorToken(config)

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        cliente_http = getattr(request.app.state, "cliente_http", None)
        extraido = extraer_token(request.headers)

        credencial: CredencialSesion | None = None
        perfil: PerfilDTO | None = None
        cliente: ClienteDatos | None = None

        if extraido.token is not None:
            if cliente_http is None:
                raise ErrorInesperado("El cliente de datos no esta inicializado")
            cliente = ClienteDatos(http=cliente_http, token=extraido.token)
            credencial = await self._resolver_credencial(extraido.token, cliente)
            perfil = await self._resolver_perfil(credencial, cliente)

        request.state.cliente_datos = cliente
        request.state.credencial = credencial
        request.state.perfil = perfil
        request.state.auditoria = _construir_contexto(request, credencial, perfil)

        if extraido.header_repetido:
            await self._registrar_anomalia(request, credencial, cliente)

        return await call_next(request)

    async def _resolver_credencial(
        self,
        token: str | None,
        cliente: ClienteDatos,
    ) -> CredencialSesion | None:
        """Pasos 2 a 4: firma, `exp`/`aud`/`iss` y revocacion."""
        if token is None:
            return None

        try:
            credencial = await self._validador.validar(token)
        except TokenInvalidoError as exc:
            logger.warning("Token rechazado: %s", exc.motivo)
            return None

        revocada = await SesionRevocadaRepositorySupabase(cliente).esta_revocada(
            credencial.session_id,
        )
        if revocada:
            logger.info("Sesion revocada: %s", credencial.session_id)
            return None

        return credencial

    async def _resolver_perfil(
        self,
        credencial: CredencialSesion | None,
        cliente: ClienteDatos,
    ) -> PerfilDTO | None:
        """Paso 5: resolver el perfil (rol y organizacion) del usuario.

        Un usuario sin perfil deja el contexto sin rol ni organizacion, pero
        **sigue autenticado**: la respuesta es `403 perfil_inexistente`
        (SP-07), no 401.
        """
        if credencial is None:
            return None
        try:
            return await ObtenerPerfil(PerfilRepositorySupabase(cliente)).ejecutar(
                credencial.usuario_id,
            )
        except PerfilInexistenteError:
            return None

    async def _registrar_anomalia(
        self,
        request: Request,
        credencial: CredencialSesion | None,
        cliente: ClienteDatos | None,
    ) -> None:
        """El header `Authorization` venia repetido (CE-07).

        Se toma el primero y se deja la anomalia en la bitacora. Solo se puede
        escribir en la bitacora si el actor esta identificado: la politica de
        `auditoria` no acepta filas sin `usuario_id` del propio actor.
        """
        logger.warning("Header Authorization repetido en %s", request.url.path)
        if credencial is None or cliente is None:
            return
        try:
            await AuditoriaRepositorySupabase(cliente).registrar(
                EventoAuditoria(
                    actor=credencial.correo or str(credencial.usuario_id),
                    accion=ACCION_ANOMALIA_AUTORIZACION,
                    entidad="sesion",
                    usuario_id=credencial.usuario_id,
                    detalles={"anomalia": "authorization_repetido"},
                    ip=request.client.host if request.client else None,
                    user_agent=request.headers.get("user-agent"),
                ),
            )
        except Exception:
            logger.exception("No se pudo registrar la anomalia de autorizacion")


def _construir_contexto(
    request: Request,
    credencial: CredencialSesion | None,
    perfil: PerfilDTO | None,
) -> AuditContext:
    """Paso 6: el `AuditContext` que reciben los casos de uso."""
    return AuditContext(
        usuario_id=credencial.usuario_id if credencial else None,
        nombre=_nombre_del_actor(credencial, perfil),
        session_id=credencial.session_id if credencial else None,
        rol=perfil.rol if perfil else None,
        organizacion_id=perfil.organizacion_id if perfil else None,
        accion=None,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


def _nombre_del_actor(credencial: CredencialSesion | None, perfil: PerfilDTO | None) -> str | None:
    """El nombre del actor para la bitacora."""
    if perfil is not None:
        if perfil.display_name:
            return perfil.display_name
        partes = [perfil.nombres, perfil.apellido_1]
        if perfil.apellido_2:
            partes.append(perfil.apellido_2)
        return " ".join(partes)
    if credencial is not None:
        return credencial.correo
    return None
