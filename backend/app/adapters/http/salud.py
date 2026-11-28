"""Router de salud del servicio.

Sirve para dos cosas, y por eso vive en su propio router en vez de en el cuerpo de
`main.py`:

1. **El `HEALTHCHECK` del contenedor** lo consulta para saber si el proceso esta
   vivo. Sin el, Docker no puede distinguir "arrancando" de "caido".
2. **El despliegue** lo consulta antes de mandar trafico.

Por eso **no pide autenticacion** y **no expone ningun dato del sistema**: es la
unica ruta de la API que responde sin token, asi que no puede filtrar nada. Lo que
devuelve es que el proceso arranco y que la configuracion se leyo.

Los endpoints de negocio van todos con token y con permiso. Este es el unico
exception, y es deliberado.

Las dos rutas devuelven el **mismo envelope** que el resto de la API: una sola
forma de leer una respuesta, tambien en un endpoint sin token.

> **Pendiente de decision.** `docs/ARQUITECTURA.md` 8.1 marca como `[DECIDIDO]`
> que `/health` consulte la vista publica `public.salud` y responda **503** cuando
> la base no responde. Esa vista no existe en ninguna migracion, y el
> comportamiento de este router no la consulta. Corregirlo cambia lo que el
> orquestador hace cuando la base se cae, asi que queda anotado en
> `docs/DECISIONES-PENDIENTES.md` en vez de resolverse aqui.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.adapters.http.responses import Respuesta
from app.config import obtener_config

router = APIRouter(tags=["salud"])


@router.get("/health")
async def health() -> Respuesta[dict[str, str]]:
    """Comprueba que el proceso esta vivo.

    Devuelve `200` con un cuerpo minimo. Deliberadamente **no** comprueba la
    conexion con Supabase: un fallo de la base de datos es un problema de la base de
    datos, y un `/health` que depende de ella reportaria caido el servicio entero y
    el orquestador reiniciaria procesos que funcionan.
    """
    return Respuesta.ok({"estado": "ok"})


@router.get("/health/config")
async def health_config() -> Respuesta[dict[str, str | bool]]:
    """Comprueba que la configuracion se leyo y que los valores obligatorios
    existen.

    No devuelve ningun valor de configuracion: solo si estan presentes. Una ruta
    que devuelve la URL de Supabase o el emisor del JWT es una ruta que filtra
    informacion de la infraestructura a cualquiera que la llame.
    """
    config = obtener_config()
    return Respuesta.ok(
        {
            "estado": "ok",
            "supabase_url_configurada": bool(config.supabase_url),
            "anon_key_configurada": bool(config.supabase_anon_key),
            "service_role_key_configurada": bool(config.supabase_service_role_key),
        }
    )
