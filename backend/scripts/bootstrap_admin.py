"""Crear el primer administrador del sistema.

El primer `admin` **no se crea con SQL**. Insertar un usuario en `auth.users` con un
`insert` es fragil: Supabase espera filas coordinadas en `auth.users` y
`auth.identities`, con el formato interno de GoTrue, y ese formato cambia entre
versiones. Lo que hace este script es usar la **API de administracion** de Supabase,
que es la via soportada, y despues registrar el perfil y la membresia.

Es **idempotente**: si el correo ya existe, actualiza el perfil y no crea un
duplicado. Se ejecuta una vez, despues de `supabase db push` y antes de que la
aplicacion se use.

Es el unico lugar del proyecto que usa `service_role` para crear usuarios por
consola, y esta justificado porque no hay todavia ningun `admin` que pueda hacerlo
desde la interfaz. Ver `docs/ARQUITECTURA.md` seccion 5.6.

Uso:

    uv run python -m scripts.bootstrap_admin \\
        --correo admin@ejemplo.com \\
        --organizacion "Equipo inicial" \\
        --contrasena "una-clave-fuerte"
"""

from __future__ import annotations

import argparse
import secrets
import sys
from dataclasses import dataclass

import httpx

from app.config import obtener_config

# Longitud de la contrasena autogenerada. Es un valor de arranque, no un parametro
# de seguridad: la contrasena se cambia en el primer inicio de sesion
# (`perfiles.debe_cambiar_contrasena`).
LONGITUD_CONTRASENA = 20

# Alfabeto sin caracteres ambiguos: una contrasena que se dicta por telefono no
# puede tener `0`/`O` ni `1`/`l`.
ALFABETO = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"

# Paginas que se recorren al buscar un usuario por correo. La API de administracion
# de Supabase no filtra por correo: hay que listar y filtrar en el cliente.
PAGINA_USUARIOS = 100
PAGINAS_MAXIMAS = 10


class BootstrapError(Exception):
    """Fallo del arranque del administrador. El mensaje va al usuario, sin traceback."""


@dataclass(frozen=True)
class Resultado:
    """Lo que hizo el script. Se imprime al final, para que quede en la consola."""

    correo: str
    organizacion: str
    usuario_id: str
    creado: bool
    contrasena: str | None


def generar_contrasena() -> str:
    """Contrasena temporal, criptograficamente fuerte.

    Usa `secrets`, no `random`: una contrasena que se puede predecir no es una
    contrasena. El cambio obligatorio en el primer inicio de sesion es la segunda
    barrera, no la unica.
    """
    return "".join(secrets.choice(ALFABETO) for _ in range(LONGITUD_CONTRASENA))


def _pedir_contrasena() -> str:
    """Pide la contrasena por consola sin eco.

    Se usa `getpass`, que no escribe en la terminal. Es preferible a un argumento de
    linea de comandos: un argumento queda en el historial del shell y en la lista de
    procesos del sistema.
    """
    import getpass

    return getpass.getpass("Contrasena del administrador: ")


def _buscar_usuario_por_correo(
    cliente: httpx.Client,
    endpoint: str,
    llave_servicio: str,
    correo: str,
) -> str | None:
    """Busca el id del usuario con ese correo, o `None` si no existe.

    La API de administracion de Supabase **no** filtra por `filter=email.eq.`:
    devuelve `{"users": []}` aunque el usuario exista. Lo verificado el 2026-11-28
    contra el stack local. Lo que si soporta es la paginacion, asi que se listan las
    paginas hasta encontrar el correo.

    Se pagina con un tope deliberado: un proyecto con miles de usuarios no debe
    hacer que el arranque recorra todas las paginas, y para el caso de uso (crear el
    primer administrador) el usuario esta al principio de la lista.
    """
    cabeceras = {
        "apikey": llave_servicio,
        "Authorization": f"Bearer {llave_servicio}",
    }

    pagina = 1
    while pagina <= PAGINAS_MAXIMAS:
        respuesta = cliente.get(
            endpoint,
            params={"page": pagina, "per_page": PAGINA_USUARIOS},
            headers=cabeceras,
        )
        if respuesta.status_code != 200:
            raise BootstrapError(
                f"No se pudo consultar el usuario: {respuesta.status_code} {respuesta.text}"
            )

        cuerpo = respuesta.json()
        usuarios = cuerpo.get("users") or []
        for usuario in usuarios:
            if (usuario.get("email") or "").lower() == correo.lower():
                return usuario["id"]

        if len(usuarios) < PAGINA_USUARIOS:
            # Ultima pagina: no hay mas usuarios.
            return None

        pagina += 1

    raise BootstrapError(
        f"No se encontro el usuario '{correo}' en las primeras {PAGINAS_MAXIMAS} paginas. "
        "El proyecto tiene demasiados usuarios; revisa el correo o usa la consola de "
        "Supabase."
    )


def _crear_o_actualizar_usuario(
    cliente: httpx.Client,
    url_base: str,
    llave_servicio: str,
    correo: str,
    contrasena: str,
) -> tuple[str, bool]:
    """Crea el usuario en Supabase Auth, o lo actualiza si ya existe.

    Devuelve el `id` del usuario y si se acaba de crear.
    """
    endpoint = f"{url_base}/auth/v1/admin/users"

    usuario_id = _buscar_usuario_por_correo(cliente, endpoint, llave_servicio, correo)
    if usuario_id is not None:
        # Se actualiza la contrasena para que el administrador pueda entrar con la
        # clave que se le acaba de indicar.
        respuesta = cliente.put(
            f"{endpoint}/{usuario_id}",
            headers={
                "apikey": llave_servicio,
                "Authorization": f"Bearer {llave_servicio}",
            },
            json={"password": contrasena, "email_confirm": True},
        )
        if respuesta.status_code not in (200, 204):
            raise BootstrapError(
                f"No se pudo actualizar el usuario: {respuesta.status_code} {respuesta.text}"
            )
        return usuario_id, False

    respuesta = cliente.post(
        endpoint,
        headers={
            "apikey": llave_servicio,
            "Authorization": f"Bearer {llave_servicio}",
        },
        json={
            "email": correo,
            "password": contrasena,
            "email_confirm": True,
        },
    )
    if respuesta.status_code not in (200, 201):
        raise BootstrapError(
            f"No se pudo crear el usuario: {respuesta.status_code} {respuesta.text}"
        )

    return respuesta.json()["id"], True


def _upsert_perfil(
    cliente: httpx.Client,
    url_base: str,
    llave_servicio: str,
    usuario_id: str,
    correo: str,
    nombres: str,
    apellido_1: str,
    apellido_2: str | None,
) -> None:
    """Registra el perfil del administrador.

    Va por la API de `service_role`, que es la que puede escribir en `perfiles` sin
    que las politicas lo bloqueen. El `insert` no puede simplemente reintentarse: la
    politica de `perfiles` no tiene `upsert` y el `id` es la clave primaria, asi que
    se borra y se inserta dentro de una peticion.
    """
    url = f"{url_base}/rest/v1/perfiles"
    cabeceras = {
        "apikey": llave_servicio,
        "Authorization": f"Bearer {llave_servicio}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }

    cuerpo = {
        "id": usuario_id,
        "organizacion_id": None,
        "rol": "admin",
        "nombres": nombres,
        "apellido_1": apellido_1,
        "apellido_2": apellido_2,
        "display_name": f"{nombres} {apellido_1}".strip(),
        "correo": correo,
        "debe_cambiar_contrasena": True,
        "activo": True,
    }

    respuesta = cliente.post(url, headers=cabeceras, json=cuerpo)
    if respuesta.status_code in (200, 201, 409):
        if respuesta.status_code == 409:
            respuesta = cliente.patch(
                f"{url}?id=eq.{usuario_id}",
                headers=cabeceras,
                json=cuerpo,
            )
            if respuesta.status_code not in (200, 204):
                raise BootstrapError(
                    f"No se pudo actualizar el perfil: {respuesta.status_code} {respuesta.text}"
                )
        return

    raise BootstrapError(
        f"No se pudo registrar el perfil: {respuesta.status_code} {respuesta.text}"
    )


def _upsert_organizacion(
    cliente: httpx.Client,
    url_base: str,
    llave_servicio: str,
    nombre: str,
) -> str:
    """Crea la organizacion, o la reutiliza si ya existe con ese nombre."""
    url = f"{url_base}/rest/v1/organizaciones"
    cabeceras = {
        "apikey": llave_servicio,
        "Authorization": f"Bearer {llave_servicio}",
        "Content-Type": "application/json",
    }

    respuesta = cliente.get(
        url,
        params={"nombre": f"eq.{nombre}", "select": "id"},
        headers=cabeceras,
    )
    if respuesta.status_code != 200:
        raise BootstrapError(
            f"No se pudo consultar la organizacion: {respuesta.status_code} {respuesta.text}"
        )

    existentes = respuesta.json()
    if existentes:
        return existentes[0]["id"]

    respuesta = cliente.post(
        url,
        headers={**cabeceras, "Prefer": "return=representation"},
        json={"nombre": nombre},
    )
    if respuesta.status_code not in (200, 201):
        raise BootstrapError(
            f"No se pudo crear la organizacion: {respuesta.status_code} {respuesta.text}"
        )

    return respuesta.json()[0]["id"]


def _upsert_membresia(
    cliente: httpx.Client,
    url_base: str,
    llave_servicio: str,
    organizacion_id: str,
    usuario_id: str,
) -> None:
    """Registra al administrador como miembro de la organizacion, con rol `admin`.

    Sin esta fila, el aislamiento no tiene ninguna membresia que resolver y el
    administrador no ve nada: `organizaciones_miembros` es la fuente del aislamiento
    (ADR-33).
    """
    url = f"{url_base}/rest/v1/organizaciones_miembros"
    cabeceras = {
        "apikey": llave_servicio,
        "Authorization": f"Bearer {llave_servicio}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }

    respuesta = cliente.post(
        url,
        headers=cabeceras,
        json={
            "organizacion_id": organizacion_id,
            "usuario_id": usuario_id,
            "rol": "admin",
        },
    )
    if respuesta.status_code not in (200, 201, 204):
        raise BootstrapError(
            f"No se pudo registrar la membresia: {respuesta.status_code} {respuesta.text}"
        )


def ejecutar(
    correo: str,
    organizacion: str,
    contrasena: str,
    nombres: str,
    apellido_1: str,
    apellido_2: str | None,
) -> Resultado:
    """Ejecuta el arranque completo."""
    config = obtener_config()
    url_base = config.supabase_url.rstrip("/")
    llave_servicio = config.supabase_service_role_key

    with httpx.Client(timeout=30.0) as cliente:
        usuario_id, creado = _crear_o_actualizar_usuario(
            cliente, url_base, llave_servicio, correo, contrasena
        )
        _upsert_perfil(
            cliente,
            url_base,
            llave_servicio,
            usuario_id,
            correo,
            nombres,
            apellido_1,
            apellido_2,
        )
        organizacion_id = _upsert_organizacion(cliente, url_base, llave_servicio, organizacion)
        _upsert_membresia(cliente, url_base, llave_servicio, organizacion_id, usuario_id)

    return Resultado(
        correo=correo,
        organizacion=organizacion,
        usuario_id=usuario_id,
        creado=creado,
        contrasena=contrasena,
    )


def main() -> int:
    """Punto de entrada de linea de comandos."""
    analizador = argparse.ArgumentParser(
        description="Crea el primer administrador de Risk-app.",
    )
    analizador.add_argument("--correo", required=True, help="Correo del administrador.")
    analizador.add_argument(
        "--organizacion",
        required=True,
        help="Nombre de la organizacion inicial.",
    )
    analizador.add_argument(
        "--nombres",
        default="Administrador",
        help="Nombres del administrador.",
    )
    analizador.add_argument(
        "--apellido-1",
        default="Principal",
        help="Primer apellido del administrador.",
    )
    analizador.add_argument(
        "--apellido-2",
        default=None,
        help="Segundo apellido del administrador. Opcional.",
    )
    analizador.add_argument(
        "--contrasena",
        default=None,
        help=(
            "Contrasena del administrador. Si no se indica, se genera una y se imprime al final."
        ),
    )
    argumentos = analizador.parse_args()

    contrasena = argumentos.contrasena or generar_contrasena()
    contrasena_generada = argumentos.contrasena is None

    try:
        resultado = ejecutar(
            correo=argumentos.correo,
            organizacion=argumentos.organizacion,
            contrasena=contrasena,
            nombres=argumentos.nombres,
            apellido_1=argumentos.apellido_1,
            apellido_2=argumentos.apellido_2,
        )
    except BootstrapError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except Exception as error:
        print(f"Error inesperado: {error}", file=sys.stderr)
        return 1

    accion = "creado" if resultado.creado else "actualizado"
    print("")
    print(f"Administrador {accion}: {resultado.correo}")
    print(f"Organizacion: {resultado.organizacion}")
    print(f"Usuario id: {resultado.usuario_id}")
    print("")
    if contrasena_generada:
        print(f"Contrasena temporal: {resultado.contrasena}")
        print("El usuario debera cambiarla en su primer inicio de sesion.")
    print("")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
