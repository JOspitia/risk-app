"""Manejador global de errores.

Un unico lugar traduce un error a la respuesta de la API. Y hay una sola
regla: **el envelope es el mismo en exito y en error** (Gate 5). Por eso los
errores que FastAPI produce por su cuenta (validacion, 404, 405) tambien salen
con la forma del envelope, y no con la de `{"detail": ...}`.

Los errores de dominio **no se reenvuelven**: cada uno lleva su propio codigo
de estado y su propio codigo legible por maquina, y aqui solo se leen
(`SKILL.md` 12.6). Si aqui se reescribiera todo a 500, cada error de negocio
se degradaria en 500 sin que nadie lo notara.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.adapters.http.responses import Respuesta
from app.domain.errors import ErrorDominio

logger = logging.getLogger(__name__)

# Codigo legible por maquina para los errores que no son de dominio.
CODIGO_VALIDACION = "validacion_request"
CODIGO_NO_ENCONTRADO = "no_encontrado"
CODIGO_METODO_NO_PERMITIDO = "metodo_no_permitido"
CODIGO_HTTP = "error_http"
CODIGO_INESPERADO = "error_inesperado"


def registrar_manejadores(app: FastAPI) -> None:
    """Registra los manejadores. Se llama una sola vez, desde `main.py`."""
    app.add_exception_handler(ErrorDominio, _manejar_error_dominio)
    app.add_exception_handler(RequestValidationError, _manejar_validacion)
    app.add_exception_handler(StarletteHTTPException, _manejar_http)
    app.add_exception_handler(Exception, _manejar_inesperado)


def _envolver_error(mensaje: str, codigo: str, detalle: str | None = None) -> dict[str, Any]:
    """El envelope de error, en la misma forma que el de exito."""
    return Respuesta.error(mensaje=mensaje, codigo=codigo, detalle=detalle).model_dump(mode="json")


async def _manejar_error_dominio(request: Request, exc: Exception) -> JSONResponse:
    """Traduce un error de dominio a su codigo de estado y su envelope."""
    if not isinstance(exc, ErrorDominio):  # pragma: no cover - registro por tipo
        raise exc
    return JSONResponse(
        status_code=exc.status_http,
        content=_envolver_error(exc.mensaje, exc.codigo),
    )


async def _manejar_validacion(request: Request, exc: Exception) -> JSONResponse:
    """La validacion declarativa de FastAPI tambien sale con el envelope."""
    if not isinstance(exc, RequestValidationError):  # pragma: no cover - registro por tipo
        raise exc
    campos = sorted({str(error.get("loc", [""])[-1]) for error in exc.errors()})
    detalle = f"Campos invalidos: {', '.join(campos)}" if campos else None
    return JSONResponse(
        status_code=422,
        content=_envolver_error("La peticion no es valida", CODIGO_VALIDACION, detalle),
    )


async def _manejar_http(request: Request, exc: Exception) -> JSONResponse:
    """Los errores HTTP de Starlette (404, 405, ...) tambien salen con el envelope."""
    if not isinstance(exc, StarletteHTTPException):  # pragma: no cover - registro por tipo
        raise exc
    codigo = {
        404: CODIGO_NO_ENCONTRADO,
        405: CODIGO_METODO_NO_PERMITIDO,
    }.get(exc.status_code, CODIGO_HTTP)
    return JSONResponse(
        status_code=exc.status_code,
        content=_envolver_error(str(exc.detail), codigo),
    )


async def _manejar_inesperado(request: Request, exc: Exception) -> JSONResponse:
    """El fallo que no es de dominio.

    El original se registra entero para la depuracion, pero **no** viaja en la
    respuesta: un detalle interno puede contener nombres de tabla, rutas o
    valores de negocio.
    """
    logger.exception("Fallo no controlado en %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content=_envolver_error("Error inesperado", CODIGO_INESPERADO),
    )
