# HU-02 — Roles y permisos

## Encabezado

- **HU ID:** `HU-02`
- **Fecha:** 2026-11-27
- **Estado:** Pendiente de implementacion
- **Cubre:** RF-15 (sistema de roles y permisos que determina que informacion ve cada usuario)
- **ADR relacionados:** ADR-12 (matriz en datos), ADR-17 (la visibilidad la decide el permiso)
- **Bloquea:** HU-09 (consulta de resultados), y parte de HU-03
- **Bloqueado por:** HU-01 (sesion), porque el permiso se comprueba en el caso de uso

---

## 1. Titulo y descripcion

**Titulo:** HU-02 — Roles y permisos

**Descripcion:** Permitir que el sistema determine **que puede ver y que puede hacer cada
usuario**, de modo que dos personas autenticadas en la misma aplicacion no vean lo mismo.

El usuario objetivo es **personal administrativo** que no va a instalar nada ni configurar
roles a mano. El administrador de una organizacion asigna el rol a cada persona una vez, y a
partir de ahi esa persona ve exactamente lo que su rol le da, sin que nadie tenga que
recordar reglas.

La regla general es una sola: **se ve lo que el permiso autoriza**. No hay una regla fija de
"solo lo propio" ni de "el equipo ve todo": lo que decide es la fila de la matriz de
permisos, que vive en la base de datos y no en el codigo.

Esta historia construye el **mecanismo** (matriz, resolucion, comprobacion). Los permisos
concretos de cada tipo de recurso (documentos, plantillas, usuarios) se van rellenando a
medida que se implemente cada modulo, en la misma tabla y con el mismo procedimiento.

---

## 2. Alcance y fuera de alcance

### En alcance

| # | Capacidad |
|---|---|
| 1 | Catalogo de roles y de permisos, con la matriz en la base de datos |
| 2 | Resolucion de los permisos efectivos de un usuario en una organizacion |
| 3 | Comprobacion del permiso en el caso de uso, no solo en el router |
| 4 | Denegacion por defecto: un permiso ausente se deniega |
| 5 | Respuesta 403 cuando el recurso existe pero el usuario no tiene permiso |
| 6 | Consulta del catalogo de roles y permisos, para mostrarlo en la interfaz |

### Fuera de alcance

| # | Fuera de alcance | Va en |
|---|---|---|
| 1 | Crear, desactivar o cambiar el rol de un usuario | HU-03 |
| 2 | Permisos sobre documentos concretos | HU-06, HU-09 |
| 3 | Permisos sobre plantillas de extraccion | HU-09 (sistema) |
| 4 | Roles personalizados creados por el usuario final | `[PENDIENTE]` Si el cliente lo pide |
| 5 | Permisos individuales por usuario, por encima del rol | `[PENDIENTE]` Si el cliente lo pide |
| 6 | Permisos de campo (ver el precio pero no editarlo) | `[PENDIENTE]` |
| 7 | Aprobaciones o flujos de trabajo | Fuera de alcance |
| 8 | Multi-organizacion para un mismo usuario | `[PENDIENTE]` Ver EC-06 de HU-01 |

---

## 3. Bloqueos y dependencias

### Lo que BLOQUEA esta HU

- **HU-01** (sesion). Sin saber quien es el usuario, no hay permiso que resolver.

### Esta HU BLOQUEA

- **HU-03**: el administrador asigna un rol, y el rol es un permiso de la matriz.
- **HU-09**: el listado de documentos filtra por permiso.
- **HU-06**: comprobar que el documento es de uno antes de archivarlo.

### Requisitos de infraestructura

| Requisito | Detalle |
|---|---|
| Tabla `roles` | Catalogo de roles |
| Tabla `permisos` | Catalogo de permisos |
| Tabla `rol_permisos` | Matriz rol -> permiso |
| Tabla `organizaciones_miembros` | Pertenencia con rol por organizacion |
| Politica RLS de `perfiles` | El backend lee el perfil con el JWT del usuario |

---

## 4. Variables y configuracion

| Parametro | Valor | Nota |
|---|---|---|
| Rol por defecto de un usuario nuevo | `analista` | El que menos ve |
| Rol de un usuario sin `organizacion_id` | Ninguno effective | Sin organizacion no hay permisos de organizacion |
| Comportamiento ante permiso ausente | **Denegar** | Deny by default. No hay excepcion "permitido por defecto" |
| Codigo HTTP ante permiso insuficiente | `403` | Distinto de `404` |
| Cache de permisos | Ninguno en la v1 | Con ~200 usuarios, resolver por consulta es suficiente. Un cache se anade solo si se mide la necesidad |
| Separador de permisos en el catalogo | `punto` | `documentos.ver`, `usuarios.gestionar` |

**Matriz inicial** (propuesta, afinable con el cliente):

| Permiso | admin | analista | auditor |
|---|:---:|:---:|:---:|
| `documentos.ver` | si | si (los propios y los compartidos) | si (lectura) |
| `documentos.analizar` | si | si | no |
| `documentos.borrar` | si | los propios | no |
| `documentos.compartir` | si | si | no |
| `archivos.descargar` | si | el propio | si (lectura) |
| `archivos.eliminar` | si | el propio | no |
| `analisis.ver_todos` | si | **no** | si (lectura) |
| `plantillas.ver` | si | si | si (lectura) |
| `plantillas.editar` | si | no | no |
| `configuracion.ver` | si | si | si (lectura) |
| `configuracion.editar` | si | si (propia) | no |
| `usuarios.gestionar` | si | no | no |
| `organizacion.gestionar` | si | no | no |
| `auditoria.ver` | si | no | si (lectura) |

---

## 5. Suposiciones

1. El rol de un usuario se resuelve **por organizacion**: `organizaciones_miembros` tiene el
   rol, y `perfiles.rol` es el rol por defecto cuando el usuario tiene una sola
   organizacion.
2. Los permisos son **additivos**: tener un permiso por rol y otro por rol distinto acumula.
   No hay permisos que resten.
3. Un rol `is_system = true` **no se puede eliminar** ni modificar sus permisos desde la
   aplicacion. Se cambia con una migracion, no con un click. `[PENDIENTE]` Confirmar si el
   cliente quiere gestion de roles en caliente.
4. Un usuario desactivado **no puede hacer nada**, sin importar sus permisos. La
   desactivacion es unaROW mas fuerte que el permiso.
5. El permiso se comprueba **en el caso de uso**. El router puede comprobarlo tambien, pero
   no es el unico sitio donde se comprueba: una comprobacion unica en el router deja el
   hueco abierto en cuanto alguien llama al caso de uso desde otro camino.
6. Un recurso que **existe** pero sobre el que el usuario no tiene permiso produce `403`, no
   `404`. Producir `404` oculta la diferencia entre "no existe" y "no es tuyo".
7. El **rol `analista` no recibe `analisis.ver_todos` por defecto.** Ve lo propio y lo que
   se le comparte de forma explicita. Una organizacion que quiera lo contrario lo concede
   en la matriz, sin cambiar codigo.
8. El auditor es de **solo lectura**. No puede analizar, ni borrar, ni crear usuarios.
9. El `admin` es de la organizacion. No hay un administrador global por encima de las
   organizaciones. `[PENDIENTE]` Si el cliente necesita alguien con acceso transversal a
   varias organizaciones, es un rol mas y una fila mas en la matriz.

---

## 6. Modelo de datos

### Tablas nuevas

#### `roles`

```
clave       TEXT PRIMARY KEY   -- admin | analista | auditor
nombre      TEXT NOT NULL
descripcion TEXT
is_system   BOOLEAN NOT NULL DEFAULT false   -- true = no se puede eliminar ni editar
created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
```

#### `permisos`

```
clave       TEXT PRIMARY KEY   -- documentos.ver | usuarios.gestionar | ...
nombre      TEXT NOT NULL
descripcion TEXT NOT NULL
created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
```

#### `rol_permisos`

```
rol       TEXT NOT NULL REFERENCES roles(clave) ON DELETE CASCADE
permiso   TEXT NOT NULL REFERENCES permisos(clave) ON DELETE CASCADE
PRIMARY KEY (rol, permiso)
```

#### `organizaciones_miembros`

```
organizacion_id UUID NOT NULL REFERENCES organizaciones(id) ON DELETE CASCADE
usuario_id      UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE
rol             TEXT NOT NULL
created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
PRIMARY KEY (organizacion_id, usuario_id)
INDEX: (usuario_id)
```

**Nota sobre `perfiles.rol`:** existe como rol por defecto para el caso de una sola
organizacion. Cuando el usuario pertenece a varias, la fuente de verdad es
`organizaciones_miembros`.

### Semilla inicial

Los roles y permisos base se crean con una **migracion** (no con un seeder editable): la
matriz es parte del esquema, y el versionarla es lo que hace auditable quien puede ver que.

---

## 7. Camino feliz principal

### 7.1 Resolver los permisos efectivos

1. El usuario hace una peticion autenticada. El middleware valida el token y construye el
   `AuditContext` con `usuario_id` y `organizacion_id`.
2. El caso de uso llama a `PermisosResolver.resolver(contexto)`.
3. El resolver consulta `organizaciones_miembros` para el rol del usuario en esa
   organizacion.
4. Consulta `rol_permisos` por ese rol y devuelve el conjunto de permisos.
5. Si el usuario esta desactivado, el conjunto es vacio, sin importar el rol.
6. El caso de uso llama a `contexto.permisos.exige("documentos.ver")`.
7. Si el permiso esta, la operacion sigue. Si no, el caso de uso lanza `ProhibidoError`.
8. El manejador global lo traduce a `403`.

### 7.2 Comprobar un permiso en un caso de uso

```python
# application/use_cases/listar_documentos.py
async def ejecutar(self, cmd, ctx: AuditContext) -> list[Documento]:
    ctx.permisos.exige("documentos.ver")          # <- aqui, no en el router

    organizacion_id = ctx.organizacion_id
    if organizacion_id is None:
        raise ProhibidoError("El usuario no pertenece a ninguna organizacion")

    documentos, total = await self.documentos.listar(
        usuario_id=ctx.usuario_id,
        organizacion_id=organizacion_id,
        solo_mios=not ctx.permisos.permite("analisis.ver_todos"),
        estado=cmd.estado,
        pagina=cmd.pagina,
        tamano=cmd.tamano,
    )
    return [DocumentoDTO.from_model(d) for d in documentos]
```

### 7.3 Consultar el catalogo

1. El usuario abre la pantalla de administracion.
2. El frontend llama a `GET /api/v1/roles`.
3. El backend comprueba el permiso `organizacion.gestionar` **en el caso de uso**.
4. Responde `200` con la lista de roles y, para cada uno, sus permisos.

```json
{
  "success": true,
  "message": "OK",
  "data": [
    {
      "clave": "analista",
      "nombre": "Analista de Riesgos",
      "is_system": true,
      "permisos": ["documentos.ver", "documentos.analizar", "configuracion.editar"]
    }
  ],
  "errors": null,
  "timestamp": "2026-11-27T12:00:00Z"
}
```

---

## 8. Caminos tristes

| # | Escenario | Comportamiento del sistema | Codigo |
|---|---|---|---|
| SP-01 | Usuario sin el permiso requerido | `ProhibidoError` | 403 |
| SP-02 | Usuario sin `organizacion_id` | `ProhibidoError` con mensaje explicito | 403 |
| SP-03 | Usuario desactivado | Se resuelve el conjunto de permisos como vacio. **403 en todo**, aunque sea `admin` | 403 |
| SP-04 | Rol desconocido en `organizacion_miembros` | El resolver no encuentra permisos. Se responde 403, **nunca 500** | 403 |
| SP-05 | Se intenta modificar un rol `is_system` | Rechazado con mensaje explicito | 422 |
| SP-06 | Se intenta eliminar un rol `is_system` | Rechazado con mensaje explicito | 422 |
| SP-07 | Se intenta crear un rol con una clave que ya existe | Conflicto | 409 |
| SP-08 | Se intenta asignar un rol a un usuario de otra organizacion | `ProhibidoError` | 403 |
| SP-09 | Permiso solicitado que no existe en el catalogo | El resolver lo ignora. La operacion se deniega. **Nunca se "permite por ausencia"** | 403 |
| SP-10 | Usuario con `organizacion.gestionar` intenta quitarse a si mismo su propio rol | Se rechaza: un administrador no puede dejar la organizacion sin administrador | 422 |

---

## 9. Casos limite y casos "estupidos"

### Casos limite

| # | Caso | Comportamiento del sistema |
|---|---|---|
| EC-01 | El usuario tiene el rol `analista` y el permiso `analisis.ver_todos` concedido en la matriz de su organizacion | Ve los analisis de los demas. La matriz manda sobre el rol por defecto |
| EC-02 | El usuario pertenece a dos organizaciones con roles distintos | Cada peticion resuelve los permisos **de la organizacion del recurso**, no la del usuario. `[PENDIENTE]` Falta definir como se elige la organizacion activa en la peticion |
| EC-03 | Un permiso se agrega a un rol con usuarios activos | Aplica de inmediato. No hay cache que invalidar en la v1 |
| EC-04 | Un usuario es dueno de un documento que ya no ve por cambio de rol | El documento sigue siendo suyo. El permiso cambia **lo que puede hacer con el**, no la propiedad |
| EC-05 | El rol `analista` no tiene ningun permiso | El usuario se autentica pero no puede hacer nada. La UI muestra un estado vacio, no un error |
| EC-06 | La matriz esta vacia en una organizacion nueva | Sus usuarios no pueden operar. Se reporta como configuracion pendiente, no como bug |

### Casos "estupidos"

| # | Caso | Comportamiento del sistema |
|---|---|---|
| CE-01 | El cliente envia `{"rol": "superadmin"}` en un cuerpo de peticion | Se ignora. El rol **nunca** se toma del cuerpo de la peticion: sale de la base |
| CE-02 | El cliente intenta escalar privilegios cambiando un campo del JWT | La firma no verifica. 401 |
| CE-03 | Peticion con `X-Role: admin` | El header se ignora por completo |
| CE-04 | Rol con espacios o caracteres raros (`"admin "` con espacio final) | No coincide con ninguna clave de la matriz. Se trata como rol desconocido: 403, no 500 |
| CE-05 | Nombre de permiso con mayusculas (`"Documentos.Ver"`) | Las claves son en minusculas. No coincide: se deniega |
| CE-06 | Permiso pedido en el cuerpo de la peticion para "activar" algo | Se ignora. Los permisos se comprueban, no se conceden por peticion |

---

## 10. Criterios de aceptacion

### CA-01: La matriz vive en datos
**Dado** el esquema de la base
**Cuando** se inspecciona
**Entonces** los roles y permisos estan en tablas, y la matriz en `rol_permisos`
**Y** agregar un permiso no requiere cambiar codigo
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-02: Deny by default
**Dado** un permiso que no esta en la matriz del rol del usuario
**Cuando** el usuario intenta la operacion
**Entonces** se deniega
**Y** **no** hay ninguna rama de codigo que conceda por ausencia
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-03: El permiso se comprueba en el caso de uso
**Dado** el codigo de los casos de uso
**Cuando** se busca una comprobacion de permiso
**Entonces** esta **dentro del caso de uso**, no solo en el router
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-04: 403 cuando falta el permiso, 404 cuando la fila no existe
**Dado** un documento de la organizacion del usuario sobre el que no tiene el permiso de la accion
**Cuando** pide el detalle
**Entonces** responde 403 con el codigo `prohibido`
**Y** la respuesta **no** revela el contenido ni el nombre del recurso
**Y** el permiso se comprueba **antes** de consultar la fila
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-04b: 404 para un recurso de otra organizacion
**Dado** un documento que pertenece a otra organizacion
**Cuando** se pide su detalle con un JWT valido
**Entonces** responde 404 con el codigo `no_encontrado`
**Y** la respuesta no confirma que ese identificador exista
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-05: Un usuario desactivado no hace nada
**Dado** un usuario `admin` desactivado
**Cuando** intenta cualquier operacion
**Entonces** responde 403 en todas, sin excepcion
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-06: El rol no viene de la peticion
**Dado** una peticion que incluye `rol` en el cuerpo o en un header
**Cuando** se procesa
**Entonces** ese valor se ignora. El rol sale de `organizaciones_miembros`
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-07: El JWT no se puede escalar
**Dado** un token con el payload modificado
**Cuando** se envia
**Entonces** la firma no verifica y responde 401
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-08: Rol desconocido
**Dado** un rol que no existe en el catalogo
**Cuando** se resuelve el contexto
**Entonces** responde 403 con un mensaje util
**Y** **nunca** 500
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-09: Los roles de sistema no se tocan desde la aplicacion
**Dado** un rol con `is_system = true`
**Cuando** se intenta modificar sus permisos o eliminarlo
**Entonces** la operacion se rechaza con 422
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-10: El permiso no decide la propiedad
**Dado** un documento propio de un usuario que pierde el permiso `documentos.borrar`
**Cuando** el usuario lista sus documentos
**Entonces** el documento sigue apareciendo en su listado
**Y** el permiso gobierna lo que puede **hacer** con el, no si es suyo
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-11: Aislamiento entre organizaciones
**Dado** un usuario de la organizacion A
**Cuando** intenta ver un recurso de la organizacion B
**Entonces** no lo obtiene: 403 o 404 segun la politica
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-12: La matriz inicial esta sembrada
**Dado** una base recien migrada
**Cuando** se consulta `rol_permisos`
**Entonces** los tres roles base (`admin`, `analista`, `auditor`) tienen sus permisos
**Y** la migracion es la que los creo, de forma versionada
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-13: Un rol nuevo no rompe nada
**Dado** un rol anadido en la matriz
**Cuando** un usuario con ese rol inicia sesion
**Entonces** sus permisos se resuelven sin necesidad de desplegar codigo
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL
