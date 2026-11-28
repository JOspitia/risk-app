"""Siembra usuarios de prueba para validar a mano.

Que crea, todos en la organizacion que se indique:

- **Un usuario por cada rol de la matriz** (`admin`, `analista`, `auditor`): con
  perfil y con membresia, cada uno con su rol. Sirve para comprobar que cada rol
  ve lo que puede ver y nada mas.
- **Un usuario anonimo**: entra en Supabase Auth pero **no tiene fila en
  `perfiles`**. Es el caso de SP-07: el backend responde `403` con el codigo
  `perfil_inexistente`, no 401 ni 500.
- **Un usuario inactivo**: tiene perfil, pero `activo = false`. El backend lo
  trata como sin permisos (`security.es_usuario_activo`).

Los usuarios se crean con la **API de administracion** de Supabase
(`service_role`), no con SQL: insertar en `auth.users` a mano es fragil, porque
Supabase espera filas coordinadas en `auth.users` y `auth.identities`, con un
formato interno que cambia entre versiones (`ARQUITECTURA.md` 5.6). Por la misma
razon `supabase/seed.sql` no trae usuarios.

Es **idempotente**: se puede volver a ejecutar y deja a los usuarios en el mismo
estado, con la contrasena que se indique.

Uso:

    python -m scripts.seed_usuarios
    python -m scripts.seed_usuarios --organizacion "Equipo de Validacion"
    python -m scripts.seed_usuarios --contrasena "una-clave-fuerte"

Sin `--contrasena` se genera una y se imprime al final.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

import httpx

from app.config import obtener_config
from scripts.bootstrap_admin import (
    BootstrapError,
    _crear_o_actualizar_usuario,
    _upsert_membresia,
    _upsert_organizacion,
    _upsert_perfil,
    generar_contrasena,
)

ORGANIZACION_POR_DEFECTO = "Equipo de Validacion"
DOMINIO = "ejemplo.co"

# El correo del usuario sin perfil. Es el "anonimo" de la aplicacion: la
# autenticacion en Supabase funciona, pero el backend no lo reconoce.
CORREO_ANONIMO = f"anonimo@{DOMINIO}"
# El usuario con la cuenta desactivada.
CORREO_INACTIVO = f"inactivo@{DOMINIO}"


@dataclass(frozen=True)
class UsuarioSembrado:
    """Un usuario creado, y lo que se espera al entrar con el."""

    correo: str
    rol: str | None
    que_pasa: str


def _roles_de_la_matriz(
    cliente: httpx.Client,
    url_base: str,
    llave_servicio: str,
) -> list[str]:
    """Los roles que define la matriz de permisos.

    Se leen de la base y no se fijan en el codigo: si mañana la matriz tiene un
    rol mas, el seeder lo siembra sin tocar nada.
    """
    url = f"{url_base}/rest/v1/roles"
    cabeceras = {
        "apikey": llave_servicio,
        "Authorization": f"Bearer {llave_servicio}",
    }
    respuesta = cliente.get(url, headers=cabeceras, params={"select": "clave", "order": "clave"})
    if respuesta.status_code != 200:
        raise BootstrapError(
            f"No se pudieron leer los roles: {respuesta.status_code} {respuesta.text}"
        )
    return [str(fila["clave"]) for fila in respuesta.json()]


def _borrar_perfil(
    cliente: httpx.Client,
    url_base: str,
    llave_servicio: str,
    usuario_id: str,
) -> None:
    """Deja al usuario sin perfil.

    El usuario anonimo se define por lo que **no** tiene: si una corrida
    anterior le dejo perfil, hay que quitarselo, o dejaria de ser anonimo.
    """
    url = f"{url_base}/rest/v1/perfiles?id=eq.{usuario_id}"
    cabeceras = {
        "apikey": llave_servicio,
        "Authorization": f"Bearer {llave_servicio}",
    }
    respuesta = cliente.delete(url, headers=cabeceras)
    if respuesta.status_code not in (200, 204):
        raise BootstrapError(
            f"No se pudo borrar el perfil: {respuesta.status_code} {respuesta.text}"
        )


def ejecutar(organizacion: str, contrasena: str) -> list[UsuarioSembrado]:
    """Siembra los usuarios y devuelve lo que se creo."""
    config = obtener_config()
    url_base = config.supabase_url.rstrip("/")
    llave_servicio = config.supabase_service_role_key

    sembrados: list[UsuarioSembrado] = []

    with httpx.Client(timeout=30.0) as cliente:
        organizacion_id = _upsert_organizacion(cliente, url_base, llave_servicio, organizacion)

        for rol in _roles_de_la_matriz(cliente, url_base, llave_servicio):
            correo = f"{rol}@{DOMINIO}"
            usuario_id, _ = _crear_o_actualizar_usuario(
                cliente, url_base, llave_servicio, correo, contrasena
            )
            _upsert_perfil(
                cliente,
                url_base,
                llave_servicio,
                usuario_id,
                correo,
                nombres=rol.capitalize(),
                apellido_1="de Prueba",
                apellido_2=None,
                rol=rol,
                activo=True,
                debe_cambiar_contrasena=False,
            )
            _upsert_membresia(
                cliente,
                url_base,
                llave_servicio,
                organizacion_id,
                usuario_id,
                rol=rol,
            )
            sembrados.append(
                UsuarioSembrado(
                    correo=correo,
                    rol=rol,
                    que_pasa=f"Entra y ve lo que el rol `{rol}` puede ver.",
                )
            )

        # El anonimo: entra en Auth, pero no tiene perfil.
        usuario_id, _ = _crear_o_actualizar_usuario(
            cliente, url_base, llave_servicio, CORREO_ANONIMO, contrasena
        )
        _borrar_perfil(cliente, url_base, llave_servicio, usuario_id)
        sembrados.append(
            UsuarioSembrado(
                correo=CORREO_ANONIMO,
                rol=None,
                que_pasa=(
                    "Entra, pero la API responde 403 `perfil_inexistente`: no tiene "
                    "perfil (SP-07)."
                ),
            )
        )

        # El inactivo: tiene perfil, pero la cuenta esta desactivada.
        usuario_id, _ = _crear_o_actualizar_usuario(
            cliente, url_base, llave_servicio, CORREO_INACTIVO, contrasena
        )
        _upsert_perfil(
            cliente,
            url_base,
            llave_servicio,
            usuario_id,
            CORREO_INACTIVO,
            nombres="Inactivo",
            apellido_1="de Prueba",
            apellido_2=None,
            rol="analista",
            activo=False,
            debe_cambiar_contrasena=False,
        )
        _upsert_membresia(
            cliente,
            url_base,
            llave_servicio,
            organizacion_id,
            usuario_id,
            rol="analista",
        )
        sembrados.append(
            UsuarioSembrado(
                correo=CORREO_INACTIVO,
                rol="analista (inactivo)",
                que_pasa=(
                    "Entra en Supabase, pero el backend lo trata como sin permisos: "
                    "la cuenta esta desactivada."
                ),
            )
        )

    return sembrados


def main() -> int:
    parser = argparse.ArgumentParser(description="Siembra usuarios de prueba.")
    parser.add_argument(
        "--organizacion",
        default=ORGANIZACION_POR_DEFECTO,
        help="Nombre de la organizacion donde quedan los usuarios.",
    )
    parser.add_argument(
        "--contrasena",
        default=None,
        help="Contrasena de todos los usuarios. Si no se indica, se genera una.",
    )
    argumentos = parser.parse_args()

    contrasena = argumentos.contrasena or generar_contrasena()
    try:
        sembrados = ejecutar(argumentos.organizacion, contrasena)
    except BootstrapError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print()
    print("Usuarios de prueba")
    print("===================")
    print()
    for usuario in sembrados:
        print(f"  {usuario.correo}")
        print(f"      rol: {usuario.rol or 'sin perfil'}")
        print(f"      {usuario.que_pasa}")
        print()
    print(f"  contrasena (todos): {contrasena}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
