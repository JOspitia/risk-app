"""Composicion de la aplicacion: aqui se conectan las piezas.

Este es el **unico** lugar donde se sabe que existe FastAPI, que existen los
adaptadores y que existen los casos de uso. Todo lo demas trabaja con puertos.

El arranque **falla** si falta una variable de entorno obligatoria: una
configuracion incompleta que arranca es peor que una que se niega a arrancar,
porque el fallo aparece en produccion y no en el desarrollo.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.adapters.http.error_handlers import registrar_manejadores
from app.adapters.http.middleware import ContextoAuditoriaMiddleware
from app.adapters.http.routers.auth import router as router_auth
from app.adapters.http.salud import router as router_salud
from app.adapters.supabase.cliente import crear_cliente_http
from app.config import Config, obtener_config

logger = logging.getLogger(__name__)


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI) -> AsyncIterator[None]:
    """Arranque y apagado.

    El apagado cierra el cliente HTTP de Supabase. Sin eso, el proceso avisa del
    cierre con una conexion abierta y el `docker compose down` tarda.
    """
    config: Config = app.state.config
    logging.basicConfig(
        level=config.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logger.info("Arranque de Risk-app. Emisor de JWT: %s", config.jwt_issuer)

    yield

    cliente_http: httpx.AsyncClient | None = app.state.cliente_http
    if cliente_http is not None:
        await cliente_http.aclose()
    logger.info("Apagando Risk-app")


def crear_app(
    config: Config | None = None,
    cliente_http: httpx.AsyncClient | None = None,
) -> FastAPI:
    """Construye la aplicacion FastAPI.

    Los routers se montan aqui. Cada endpoint nace en su router y el router se
    registra en un solo lugar: el registro disperso hace imposible responder
    "que endpoints existen".

    `config` y `cliente_http` se pueden inyectar: es lo que permite probar la
    aplicacion sin red y sin base de datos. Por defecto salen del entorno.
    """
    config = config or obtener_config()
    cliente_http = cliente_http or crear_cliente_http(
        config.supabase_url,
        config.supabase_anon_key,
    )

    app = FastAPI(
        title="Risk-app",
        description="Analisis privado de documentos.",
        version="0.1.0",
        lifespan=ciclo_de_vida,
    )

    app.state.config = config
    app.state.cliente_http = cliente_http

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # El filtro de autenticacion se registra **exactamente una vez**:
    # registrarlo dos veces produce el doble de trabajo por peticion y dos
    # contextos de auditoria (`SKILL.md` 7).
    app.add_middleware(
        ContextoAuditoriaMiddleware,
        config=config,
    )

    # Un unico manejador de errores: el envelope es el mismo en exito y en
    # error (Gate 5).
    registrar_manejadores(app)

    # Los routers se montan aqui. El registro esta disperso: cada router se anade
    # en un solo lugar, y por eso se puede responder "que endpoints existen".
    app.include_router(router_salud)
    app.include_router(router_auth)

    return app


app = crear_app()
