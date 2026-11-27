# HU-03 — Administracion de usuarios

## Encabezado

- **HU ID:** `HU-03`
- **Fecha:** 2026-11-27
- **Estado:** Pendiente de implementacion
- **Cubre:** RF-16 (crear cuentas con nombres, apellidos, correo y contrasena autogenerada enviada por correo; asignar rol y organizacion; desactivar)
- **ADR relacionados:** ADR-13 (adaptador de administracion), ADR-18 (alta con credencial temporal), ADR-05 (Supabase Auth emite el token)
- **Bloquea:** ninguna directamente. Es necesaria para que la demo tenga mas de un usuario
- **Bloqueado por:** HU-01 (sesion), HU-02 (roles y permisos)

---

## 1. Titulo y descripcion

**Titulo:** HU-03 — Administracion de usuarios

**Descripcion:** Permitir que un administrador de la organizacion **cree las cuentas de las
personas** y les asigne su rol, sin que ningun usuario tenga que registrarse por su cuenta y
sin que el administrador tenga que inventar contrasenas.

El flujo es: el administrador carga los datos basicos de la persona (nombres, apellido 1,
apellido 2, correo), el sistema **genera una contrasena temporal**, crea la cuenta **sin
confirmar**, y envia el correo con esa credencial. La persona recibe el correo, entra, y el
sistema le **exige cambiar la contrasena** en el primer inicio de sesion.

**La contrasena nunca la elige el administrador.** Una contrasena elegida por una persona
para otra persona casi siempre es debil o reutilizada. El sistema la genera con un
generador criptografico, y el administrador nunca la ve.

---

## 2. Alcance y fuera de alcance

### En alcance

| # | Capacidad |
|---|---|
| 1 | Crear un usuario con datos basicos, rol y organizacion |
| 2 | Generar la contrasena temporal de forma criptografica |
| 3 | Enviar el correo con la credencial temporal y el enlace de confirmacion |
| 4 | Listar los usuarios de la organizacion, con su rol y su estado |
| 5 | Cambiar el rol o la organizacion de un usuario |
| 6 | Desactivar un usuario (y reactivarlo) |
| 7 | Forzar el cambio de contrasena en el primer inicio de sesion |
| 8 | Registrar toda operacion de aprovisionamiento en auditoria |

### Fuera de alcance

| # | Fuera de alcance | Va en |
|---|---|---|
| 1 | Que un usuario se registre solo | Ningun sitio. La cuenta la crea la organizacion |
| 2 | Recuperacion de contrasena por el usuario | Flujo de Supabase Auth |
| 3 | Verificacion por correo previa al primer uso | `[PENDIENTE]` Ver supuesto 3 |
| 4 | Importacion masiva desde CSV o Excel | `[PENDIENTE]` Si el cliente lo pide |
| 5 | Roles personalizados | PP-04 |
| 6 | Permisos individuales por usuario | PP-05 |
| 7 | Transferencia de un usuario entre organizaciones | `[PENDIENTE]` |
| 8 | Borrado definitivo de un usuario | `[PENDIENTE]` Hoy es desactivacion, no borrado |
| 9 | Envio de correo a multiples personas de una vez | Fuera de alcance |

---

## 3. Bloqueos y dependencias

### Lo que BLOQUEA esta HU

- **HU-01** (sesion): el administrador tiene que estar autenticado.
- **HU-02** (permisos): el rol que se asigna viene de la matriz.

### Esta HU BLOQUEA

- Nada tecnicamente. **Es la que habilita la demo**: sin ella hay un unico usuario.

---

## 4. Variables y configuracion

| Variable / parametro | dev | prod | Default |
|---|---|---|---|
| `SUPABASE_SERVICE_ROLE_KEY` | local | por definir | — (obligatoria, solo backend) |
| `RESEND_API_KEY` | — | por definir | — (opcional: sin ella el correo va al log) |
| `EMAIL_FROM` | `risk-app@localhost` | por definir | `risk-app@localhost` |
| `EMAIL_PROVEEDOR` | `log` | `resend` | `log` |
| Longitud de la contrasena temporal | 20 | 20 | 20 |
| `LINK_TTL_SEGUNDOS` (URL firmada de subida) | 900 | 900 | 900 |
| `URL_FIRMADA_TTL_SEGUNDOS` (descarga) | 3600 | 3600 | 3600 |

**El proveedor de correo se elige por entorno.** En desarrollo, `log`: el correo se escribe
en el log y el flujo se prueba sin contratar nada. En produccion, `resend` u otro.

---

## 5. Suposiciones

1. La organizacion tiene **un unico administrador** al principio, sembrado en la base. Los
   demas los crea ese administrador.
2. El correo es **la unica via de entrega** de la credencial. Si el correo no llega, el
   administrador **no puede ver la contrasena**: no se guarda en ningun lado. Hay que
   reenviar una credencial nueva.
3. La contrasena temporal se genera con un generador criptografico (`secrets`), **no** con
   `random`. Una contrasena predecible para un usuario recien creado es una puerta abierta.
4. La cuenta se crea **sin confirmar** (`email_confirm = false`). La confirmacion la hace
   el usuario desde el correo. `[PENDIENTE]` Si el cliente prefiere confirmar el correo
   antes de que el usuario pueda entrar, se invierte el orden (supuesto 3 de la seccion 8).
5. `perfiles.debe_cambiar_contrasena = true` hasta que el usuario cambie su clave. La
   interfaz lo fuerza **antes** de mostrar cualquier pantalla protegida.
6. **Desactivar no es borrar.** Un usuario desactivado conserva su historia (documentos que
   subio, analisis, auditoria) y no puede operar. El borrado definitivo se decide con el
   cliente (DP-15 y PP-01).
7. La `service_role` **solo** se usa desde el adaptador de administracion. Ningun endpoint de
   datos de negocio la alcanza.
8. El correo con la credencial **no se registra** en los logs de negocio. El log registra
   que se envio, a quien y cuando, nunca su contenido.
9. Un administrador **no puede desactivar al ultimo administrador** de la organizacion: la
   organizacion se quedaria sin quien administre.
10. Un administrador **no puede cambiarse su propio rol** a uno con menos permisos, para no
    dejar la organizacion sin administracion.

---

## 6. Modelo de datos

### Modificacion a tabla existente

```sql
-- perfiles: datos de la persona y bandera de cambio de contrasena
alter table perfiles
  add column nombres                 text,
  add column apellido_1              text,
  add column apellido_2              text,
  add column debe_cambiar_contrasena boolean not null default false;

-- El nombre completo se arma en el Resource, no se duplica en la base.
```

**Nota:** los datos personales viven en `perfiles`, no en `auth.users`. `auth.users` la
administra Supabase y no se toca desde la aplicacion (salvo por la Admin API para el alta).

### El unico uso de `service_role`

```
POST /api/v1/usuarios
  1. ctx.permisos.exige("usuarios.gestionar")     <- en el caso de uso
  2. Se genera la contrasena temporal
  3. adaptador_admin.crear_usuario(...)             <- unico uso de service_role
  4. Se registra el perfil en `perfiles`
  5. Se envia el correo
  6. Se marca debe_cambiar_contrasena = true
  7. Se registra en auditoria
```

---

## 7. Camino feliz principal

### 7.1 Crear un usuario

1. El administrador abre "Administracion > Usuarios".
2. Pulsa "Nuevo usuario".
3. El formulario pide: nombres, apellido 1, apellido 2 (opcional), correo, rol y
   organizacion. La organizacion viene precargada: el administrador no puede crear usuarios
   en otra.
4. Pulsa "Crear usuario".
5. El frontend llama a `POST /api/v1/usuarios`.
6. El caso de uso comprueba el permiso `usuarios.gestionar`. Sin el, responde 403.
7. El backend genera la contrasena temporal.
8. El backend crea el usuario en Supabase con `email_confirm = false`.
9. El backend registra el perfil en `perfiles` con el rol, la organizacion y
   `debe_cambiar_contrasena = true`.
10. El backend envia el correo con la credencial y el enlace de confirmacion.
11. El backend registra la operacion en auditoria con el actor.
12. La API responde `201` con el recurso del usuario. **La contrasena no viaja de vuelta**:
    el backend la descarta despues de enviar el correo.

```json
{
  "success": true,
  "message": "Usuario creado. Se le envio la credencial por correo.",
  "data": {
    "id": "b21e...",
    "nombres": "Luis",
    "apellido_1": "Ramirez",
    "apellido_2": "Osorio",
    "display_name": "Luis Ramirez Osorio",
    "rol": "analista",
    "organizacion_id": "c41a...",
    "debe_cambiar_contrasena": true,
    "activo": true
  },
  "errors": null,
  "timestamp": "2026-11-27T14:00:00Z"
}
```

### 7.2 La persona recibe el correo y entra

1. La persona recibe el correo con su credencial temporal.
2. Abre la aplicacion, se autentica y funciona.
3. La API responde que `debe_cambiar_contrasena = true`.
4. La UI muestra el formulario de nueva contrasena **antes** de cualquier pantalla protegida.
5. Elige una contrasena nueva. La API la cambia y limpia la bandera.
6. Recien entonces ve la aplicacion.

### 7.3 Listar usuarios

1. El administrador abre "Administracion > Usuarios".
2. La UI llama a `GET /api/v1/usuarios`.
3. La API devuelve los usuarios **de su organizacion**, con su rol y su estado.
4. La tabla muestra: nombre, correo, rol, estado y si debe cambiar la contrasena.

### 7.4 Cambiar el rol

1. El administrador cambia el rol de un usuario en la tabla.
2. La UI llama a `PATCH /api/v1/usuarios/{id}` con el nuevo rol.
3. El caso de uso comprueba `usuarios.gestionar` y que el usuario pertenece a la misma
   organizacion.
4. Se actualiza el rol y se registra en auditoria.
5. El cambio aplica **de inmediato**: los permisos se resuelven por consulta, sin cache.

### 7.5 Desactivar un usuario

1. El administrador marca al usuario como inactivo.
2. La UI pide confirmacion.
3. La API marca la cuenta en Supabase como deshabilitada.
4. El usuario no puede autenticarse. Si tenia una sesion abierta, sus peticiones pasan a
   responder 403 en cuanto el backend resuelve sus permisos como vacios.
5. La operacion queda en auditoria.

---

## 8. Caminos tristes

| # | Escenario | Comportamiento del sistema | Codigo |
|---|---|---|---|
| SP-01 | El actor no tiene `usuarios.gestionar` | `ProhibidoError` | 403 |
| SP-02 | El correo ya existe en Supabase | `ConflictoError` con mensaje explicito | 409 |
| SP-03 | El correo ya existe en `perfiles` de otra organizacion | 409. **No se revela** si el correo existe en otra organizacion, para no filtrar la base de usuarios | 409 |
| SP-04 | Falta un campo obligatorio (nombres, apellido 1 o correo) | 422 de validacion | 422 |
| SP-05 | El correo no tiene formato valido | 422 de validacion | 422 |
| SP-06 | El rol enviado no existe en la matriz | 422. No se crea el usuario | 422 |
| SP-07 | La organizacion no existe o no es la del actor | 403 | 403 |
| SP-08 | El proveedor de correo falla | El **usuario ya fue creado**. Se responde 500 con un mensaje que dice que la cuenta existe pero que el correo no pudo enviarse, y el admin puede reenviar la credencial | 500 |
| SP-09 | El administrador intenta desactivar al ultimo administrador activo | 422 con mensaje explicito | 422 |
| SP-10 | El administrador intenta cambiarse su propio rol a uno menor | 422 | 422 |
| SP-11 | El administrador intenta modificar un usuario de otra organizacion | 403 | 403 |
| SP-12 | El administrador intenta editar un usuario desactivado | Se permite reactivar, no editar el rol sin reactivarlo | 422 |

**SP-08 es el caso importante.** El orden correcto es: crear la cuenta, y si el correo falla,
informar con precision. Si se creara la cuenta **despues** del correo, un correo duplicado
dejaria cuentas huerfanas. Y si se revirtiera la cuenta cuando el correo falla, el usuario
podria haberse recibido el correo igual y encontrarse con una cuenta que ya no existe.

---

## 9. Casos limite y casos "estupidos"

### Casos limite

| # | Caso | Comportamiento del sistema |
|---|---|---|
| EC-01 | El correo tiene mayusculas | Se normaliza a minusculas antes de crear. `Ana@X.com` y `ana@x.com` son la misma persona |
| EC-02 | El correo tiene espacios al inicio o al final | Se recortan |
| EC-03 | El mismo nombre y apellido que alguien existente | Se permite. El correo es la identidad |
| EC-04 | El usuario cambia su contrasena temporal | La bandera se limpia y la contrasena temporal deja de servir |
| EC-05 | El usuario nunca entra | La cuenta queda con `debe_cambiar_contrasena = true` para siempre. No es un problema: es el estado correcto |
| EC-06 | Se reenvia la credencial de un usuario que ya entro | Se genera una contrasena nueva y se marca de nuevo `debe_cambiar_contrasena = true`. La anterior queda invalida |
| EC-07 | El administrador se desactiva a si mismo | 422. Un administrador no puede dejar la organizacion sin administrador |
| EC-08 | Un usuario desactivado tiene documentos | Los documentos siguen siendo suyos y siguen visibles para el admin. Desactivar no borra trabajo |
| EC-09 | La organizacion tiene mas de un administrador | Cualquiera de ellos puede desactivar a los demas, salvo al ultimo |

### Casos "estupidos"

| # | Caso | Comportamiento del sistema |
|---|---|---|
| CE-01 | El cliente envia `rol: "superadmin"` | 422. El rol no existe en la matriz |
| CE-02 | El cliente envia `organizacion_id` de otra organizacion | 403. La organizacion la determina el actor, no el cuerpo |
| CE-03 | El cliente envia `activo: false` al crear | Se ignora. El usuario se crea activo |
| CE-04 | El cliente intenta enviar `debe_cambiar_contrasena: false` | Se ignora. La bandera la pone el sistema |
| CE-05 | Dos administradores crean al mismo correo a la vez | Exactamente uno tiene exito; el otro recibe 409. El unico perdedor es el que choca con el constraint |
| CE-06 | El correo tiene un `+` o un `.` antes de la `@` | Se trata como correo normal. No se aplica normalizacion de estilo: es una decision del cliente (PP-05) |
| CE-07 | Nombre con 5000 caracteres | 422 de validacion por longitud |
| CE-08 | El cliente pide la contrasena temporal en la respuesta | **No se devuelve nunca.** La API responde sin ella, siempre |

---

## 10. Criterios de aceptacion

### CA-01: El admin crea un usuario
**Dado** un administrador con el permiso `usuarios.gestionar`
**Cuando** crea un usuario con nombres, apellidos, correo, rol y organizacion
**Entonces** responde 201 con el recurso del usuario
**Y** la cuenta existe en Supabase **sin confirmar**
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-02: La contrasena nunca sale del servidor
**Dado** la respuesta de `POST /api/v1/usuarios`
**Cuando** se inspecciona el cuerpo real
**Entonces** **no** contiene la contrasena temporal ni ninguna credencial
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-03: La contrasena es criptografica
**Dado** el codigo que genera la credencial
**Cuando** se revisa
**Entonces** usa un generador criptografico (`secrets`), **no** `random`
**Y** dos ejecuciones seguidas no producen la misma cadena
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-04: El correo se envia
**Dado** un usuario recien creado
**Cuando** se mira la bandeja del development
**Entonces** hay un correo con la credencial temporal y el enlace de confirmacion
**Y** el cuerpo del correo **no** aparece en los logs de negocio
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-05: El cambio de contrasena es obligatorio
**Dado** un usuario con `debe_cambiar_contrasena = true`
**Cuando** inicia sesion
**Entonces** la UI le pide la nueva contrasena antes de mostrar cualquier pantalla protegida
**Y** no puede saltarse esa pantalla
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-06: Permiso denegado
**Dado** un usuario sin `usuarios.gestionar`
**Cuando** llama a `POST /api/v1/usuarios`
**Entonces** responde 403
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-07: Correo duplicado
**Dado** un correo que ya existe
**Cuando** se intenta crear otro usuario con el
**Entonces** responde 409 y **no** se crea el usuario
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-08: El service_role no se escapa
**Dado** el codigo del backend
**Cuando** se busca el uso de `service_role`
**Entonces** solo aparece en `adapters/supabase/admin.py`
**Y** ningun router de datos de negocio lo alcanza
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-09: Aislamiento entre organizaciones
**Dado** un administrador de la organizacion A
**Cuando** intenta modificar un usuario de la organizacion B
**Entonces** responde 403
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-10: No queda sin administrador
**Dado** una organizacion con un unico administrador activo
**Cuando** intenta desactivarse a si mismo
**Entonces** responde 422 con un mensaje explicito
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-11: Desactivar es reversible
**Dado** un usuario desactivado
**Cuando** el administrador lo reactiva
**Entonces** puede volver a autenticarse
**Y** sus documentos siguen intactos
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-12: El rol cambia de inmediato
**Dado** un usuario con rol `analista`
**Cuando** el administrador se lo cambia a `auditor`
**Entonces** en la peticion siguiente ya no puede analizar, sin reiniciar sesion ni esperar
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-13: Auditoria
**Dado** un alta de usuario
**Cuando** se consulta la bitacora
**Entonces** hay una entrada con el actor, la accion y el usuario afectado
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-14: El fallo de correo no deja cuentas huerfanas
**Dado** que el proveedor de correo falla
**Cuando** se crea un usuario
**Entonces** la cuenta **si** queda creada, y la respuesta dice explicitamente que el correo
no pudo enviarse y que hay que reenviar la credencial
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL
