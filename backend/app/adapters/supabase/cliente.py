"""Cliente HTTP de PostgREST.

El backend **no** abre una conexion TCP a Postgres: habla con Supabase por
HTTP (ADR-04). Por eso el acceso a datos es una peticion HTTP con cabeceras.

Este modulo es el unico lugar donde se decide que credencial viaja en cada
peticion, y esa decision es la que sostiene el aislamiento:

- `apikey`: la llave **publica** del proyecto. La exige PostgREST para saber
  que esquema usar.
- `Authorization`: el **JWT del usuario**, nunca la llave de servicio. Con el
  JWT del usuario, RLS filtra las filas; con la llave de servicio, RLS no
  aplica y el aislamiento queda solo en el codigo de aplicacion, que es
  exactamente donde no se quiere (`SKILL.md` 5.2).

La llave de servicio no aparece en este archivo, y no aparece en ningun otro
del camino de una peticion de usuario: solo va en el adaptador de
administracion de usuarios (`SKILL.md` 9.2).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.domain.errors import (
    ErrorInesperado,
    NoAutenticadoError,
    NoEncontradoError,
    ProhibidoError,
    SesionNoRevocableError,
)

# Codigo SQLState con el que las funciones de Postgres rechazan una operacion
# por falta de pertenencia. PostgREST lo devuelve en el cuerpo del error.
CODIGO_SIN_PERMISO = "42501"


def crear_cliente_http(url_supabase: str, llave_anonima: str) -> httpx.AsyncClient:
    """El cliente HTTP del proceso, con su pool de conexiones.

    Se crea una sola vez (en el arranque) y se comparte: un cliente por
    peticion abriria una conexion por peticion y perderia el *keep-alive*.
    """
    return httpx.AsyncClient(
        base_url=f"{url_supabase.rstrip('/')}/rest/v1/",
        headers={"apikey": llave_anonima},
        timeout=httpx.Timeout(10.0, connect=5.0),
    )


@dataclass(frozen=True)
class ClienteDatos:
    """Acceso a los datos con la credencial del usuario propagada.

    Es inmutable: `con_token` devuelve otra vista del mismo pool con el JWT
    del usuario. Dos peticiones del mismo usuario comparten conexiones y no
    comparten credenciales.
    """

    http: httpx.AsyncClient
    token: str | None = None

    def con_token(self, token: str) -> ClienteDatos:
        """Vista del mismo cliente que viaja con el JWT del usuario."""
        return ClienteDatos(http=self.http, token=token)

    async def seleccionar(
        self,
        tabla: str,
        columnas: str,
        filtros: dict[str, str],
        orden: str | None = None,
        limite: int | None = None,
        timeout: float | None = None,
    ) -> list[dict[str, Any]]:
        """Una consulta parametrizada. Devuelve las filas o una lista vacia.

        Cada filtro es la **expresion completa** de PostgREST (`eq.<valor>`,
        `gt.<valor>`, ...): el operador se escribe explicito, para que un
        filtro con otro operador no se convierta en `eq.gt.<valor>`.

        Los valores viajan como **parametros** de la peticion, no concatenados
        en la URL: `httpx` los codifica, y PostgREST los trata como datos.

        `timeout` acorta el tiempo de espera de **esta** peticion. Lo usa la
        sonda de disponibilidad, que no puede quedarse esperando: una sonda
        que tarda lo que tarda la base ya no es una sonda.
        """
        params: dict[str, str] = {"select": columnas}
        params.update(filtros)
        if orden is not None:
            params["order"] = orden
        if limite is not None:
            params["limit"] = str(limite)

        if timeout is None:
            respuesta = await self.http.get(
                tabla,
                params=params,
                headers=self._cabeceras(),
            )
        else:
            # `timeout=None` en `httpx` significa "sin espera", no "el de por
            # defecto": por eso el caso sin timeout va en su propia rama.
            respuesta = await self.http.get(
                tabla,
                params=params,
                headers=self._cabeceras(),
                timeout=timeout,
            )
        _verificar(respuesta)
        cuerpo = respuesta.json()
        return list(cuerpo) if isinstance(cuerpo, list) else []

    async def actualizar(
        self,
        tabla: str,
        filtros: dict[str, str],
        cambios: dict[str, Any],
    ) -> None:
        """Una actualizacion parametrizada. Devuelve el error si la politica la rechaza.

        Los filtros son la **expresion completa** de PostgREST, como en
        `seleccionar`, y los cambios viajan como parametros del cuerpo.

        La politica de RLS es la que decide a que filas llega la escritura: la
        peticion lleva el JWT del usuario, no la llave de servicio.
        """
        respuesta = await self.http.patch(
            tabla,
            params=filtros,
            json=cambios,
            headers=self._cabeceras(),
        )
        _verificar(respuesta)

    async def insertar(self, tabla: str, fila: dict[str, Any]) -> None:
        """Una escritura. Devuelve el error si la politica la rechaza."""
        respuesta = await self.http.post(
            tabla,
            json=fila,
            headers={**self._cabeceras(), "Prefer": "return=minimal"},
        )
        _verificar(respuesta)

    async def llamar_rpc(self, funcion: str, cuerpo: dict[str, Any]) -> Any:
        """Una operacion atomica pedida a Postgres (ADR-04, `SKILL.md` 6.1)."""
        respuesta = await self.http.post(
            f"rpc/{funcion}",
            json=cuerpo,
            headers=self._cabeceras(),
        )
        _verificar(respuesta)
        if respuesta.status_code == 204 or not respuesta.content:
            return None
        return respuesta.json()

    def _cabeceras(self) -> dict[str, str]:
        """Las cabeceras de la peticion: la credencial viaja aqui y en ningun otro sitio."""
        if self.token is None:
            return {}
        return {"Authorization": f"Bearer {self.token}"}


def _cuerpo_de_error(respuesta: httpx.Response) -> dict[str, Any]:
    """El cuerpo del error de PostgREST, si es un JSON."""
    try:
        cuerpo = respuesta.json()
    except ValueError:
        return {}
    return cuerpo if isinstance(cuerpo, dict) else {}


def _verificar(respuesta: httpx.Response) -> None:
    """Traduce un error de PostgREST al error de dominio que corresponde.

    La base de datos ya decidio (la politica, la funcion de Postgres): aqui
    solo se traduce el codigo. El original viaja en `detalle` para que la
    depuracion no lo pierda.
    """
    if respuesta.status_code < 400:
        return

    cuerpo = _cuerpo_de_error(respuesta)
    codigo = str(cuerpo.get("code", ""))
    detalle = str(cuerpo.get("message", respuesta.text))[:500]

    if codigo == CODIGO_SIN_PERMISO:
        raise SesionNoRevocableError(detalle)
    if respuesta.status_code == 401:
        raise NoAutenticadoError(detalle)
    if respuesta.status_code == 403:
        raise ProhibidoError(detalle)
    if respuesta.status_code == 404:
        raise NoEncontradoError(detalle)
    raise ErrorInesperado(detalle=detalle)
