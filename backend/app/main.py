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

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.adapters.http.salud import router as router_salud
from app.config import obtener_config

logger = logging.getLogger(__name__)


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI) -> AsyncIterator[None]:
    """Arranque y apagado.

    El apagado cierra el cliente HTTP de Supabase. Sin eso, el proceso avisa del
    cierre con una conexion abierta y el `docker compose down` tarda.
    """
    config = obtener_config()
    logging.basicConfig(
        level=config.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logger.info("Arranque de Risk-app. Emisor de JWT: %s", config.jwt_issuer)

    yield

    logger.info("Apagando Risk-app")


def crear_app() -> FastAPI:
    """Construye la aplicacion FastAPI.

    Los routers se montan aqui. Cada endpoint nace en su router y el router se
    registra en un solo lugar: el registro disperso hace imposible responder
    "que endpoints existen".
    """
    config = obtener_config()

    app = FastAPI(
        title="Risk-app",
        description="Analisis privado de documentos.",
        version="0.1.0",
        lifespan=ciclo_de_vida,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Los routers se montan aqui. El registro esta disperso: cada router se anade
    # en un solo lugar, y por eso se puede responder "que endpoints existen".
    app.include_router(router_salud)

    return app


app = crear_app()
