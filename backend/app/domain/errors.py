"""Errores de dominio.

Cada error lleva **su propia semantica HTTP**: el codigo de estado y el codigo
legible por maquina son parte del error, no una decision que se toma en el
adaptador de entrada. Por eso el manejador global de `adapters/http` solo tiene
que leer `exc.status_http` y `exc.codigo`.

**Los errores de dominio no se reenvuelven.** Capturarlos y relanzarlos como
`RuntimeError` destruye su tipo, el manejador deja de reconocerlos y cada error
de negocio se degrada en 500. La regla es de `SKILL.md` 12.6 y no tiene
excepcion: si hace falta contexto, se anade al error, no se envuelve.

Este modulo no importa nada: es la capa mas interna del nucleo y no conoce
FastAPI, ni Pydantic, ni Supabase.
"""

from __future__ import annotations


class ErrorDominio(Exception):  # noqa: N818 - el nombre lo fija `SKILL.md` 1.10
    """Base de los errores de dominio.

    Los errores de dominio son *unchecked*: no hace falta capturarlos, y el
    manejador global los traduce a la respuesta de la API.
    """

    codigo: str = "error_dominio"
    status_http: int = 500
    mensaje: str = "Error inesperado"

    def __init__(self, mensaje: str | None = None) -> None:
        self.mensaje = mensaje or self.mensaje
        super().__init__(self.mensaje)


class ValidacionError(ErrorDominio):
    """La peticion no cumple una regla de negocio o de formato."""

    codigo = "validacion"
    status_http = 400
    mensaje = "La peticion no es valida"


class NoAutenticadoError(ErrorDominio):
    """No hay credencial valida: falta, esta vencida o es invalida."""

    codigo = "no_autenticado"
    status_http = 401
    mensaje = "No autenticado"


class ProhibidoError(ErrorDominio):
    """El actor esta autenticado pero la accion no le corresponde."""

    codigo = "prohibido"
    status_http = 403
    mensaje = "Operacion no permitida"


class PerfilInexistenteError(ErrorDominio):
    """El usuario esta autenticado pero no tiene fila en `perfiles`.

    No es 404: el recurso que falta es el perfil **del propio actor**, y el
    error dice exactamente eso. Ver `SP-07` de la HU-01.
    """

    codigo = "perfil_inexistente"
    status_http = 403
    mensaje = "El usuario autenticado no tiene perfil"


class NoEncontradoError(ErrorDominio):
    """El recurso no existe, o RLS filtro la fila."""

    codigo = "no_encontrado"
    status_http = 404
    mensaje = "Recurso no encontrado"


class ConflictoError(ErrorDominio):
    """La operacion contradice el estado actual del recurso."""

    codigo = "conflicto"
    status_http = 409
    mensaje = "La operacion entra en conflicto con el estado actual"


class ServicioNoDisponibleError(ErrorDominio):
    """El servicio no puede atender peticiones en este momento.

    Lo levanta la sonda de disponibilidad: la base de datos no responde, o el
    esquema todavia no esta aplicado. Es 503 y no 500 porque **no es un fallo
    del proceso**: el proceso esta vivo y por eso `/health` sigue respondiendo
    200.
    """

    codigo = "no_disponible"
    status_http = 503
    mensaje = "El servicio no esta disponible"


class ErrorInesperado(ErrorDominio):
    """Fallo que no tiene semantica de negocio propia.

    Se usa cuando no hay un error de dominio mas preciso: el mensaje del
    original viaja en `detalle` para que la depuracion no lo pierda.
    """

    codigo = "error_inesperado"
    status_http = 500
    mensaje = "Error inesperado"

    def __init__(self, mensaje: str | None = None, detalle: str | None = None) -> None:
        super().__init__(mensaje)
        self.detalle = detalle


class SesionNoRevocableError(ErrorDominio):
    """La sesion que se pide revocar no pertenece al usuario autenticado."""

    codigo = "sesion_no_revocable"
    status_http = 403
    mensaje = "La sesion no pertenece al usuario autenticado"
