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

El router tiene **dos sondas**, y la separacion es deliberada:

- `GET /health` es la **sonda de supervivencia**: mira el proceso, no la base.
  Es la que consulta el `HEALTHCHECK` del contenedor, que solo mira el codigo
  de salida. Si dependiera de la base, un tropiezo de Supabase reiniciaria en
  bucle un contenedor de FastAPI que esta sano.
- `GET /ready` es la **sonda de disponibilidad**: mira la base. Si Supabase no
  responde, o el esquema no esta aplicado, responde 503 y el orquestador deja
  de mandar trafico en vez de reiniciar procesos.

La decision esta registrada en `docs/DECISIONES-PENDIENTES.md` (DP-16) y en
`docs/ARQUITECTURA.md` 8.1.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.adapters.http.responses import Respuesta
from app.adapters.http.schemas.salud import DisponibilidadResource
from app.adapters.supabase.cliente import ClienteDatos
from app.adapters.supabase.salud import SaludRepositorySupabase
from app.application.use_cases.verificar_disponibilidad import VerificarDisponibilidad
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


@router.get("/ready")
async def ready(request: Request) -> Respuesta[DisponibilidadResource]:
    """La sonda de disponibilidad: dice si el servicio puede recibir trafico.

    A diferencia de `/health`, esta **mira la base**. Consulta la vista publica
    `public.salud` con la **llave publica**, nunca con la de servicio: con la de
    servicio, RLS no aplicaria y la sonda estaria mintiendo sobre lo que el
    servidor veria de verdad.

    Responde 200 con el envelope cuando la base responde y el esquema esta
    aplicado, y 503 con el envelope cuando no. El 503 sale del error de dominio
    `ServicioNoDisponibleError`, no de una excepcion: el manejador global lo
    traduce.

    No pide autenticacion, igual que `/health`: es una sonda de la plataforma,
    no un endpoint de negocio. Lo que responde es el catalogo del sistema, no
    datos de persona.
    """
    # El cliente del proceso, **sin token**: la peticion sale con la llave
    # publica (la `apikey` del cliente) y sin cabecera `Authorization`, asi que
    # PostgREST la trata como `anon`. La vista es legible por `anon` y por
    # `authenticated`, y la llave de servicio no viaja nunca por aqui: con ella,
    # RLS no aplicaria y la sonda mentiria sobre lo que el servidor ve.
    cliente = ClienteDatos(http=request.app.state.cliente_http)
    caso = VerificarDisponibilidad(salud=SaludRepositorySupabase(cliente))
    resultado = await caso.ejecutar()
    return Respuesta.ok(
        data=DisponibilidadResource.from_model(resultado),
        mensaje="Servicio disponible",
    )
