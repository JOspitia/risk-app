# HU-01 — Acceso y sesion

## Encabezado

- **HU ID:** `HU-01`
- **Fecha:** 2026-11-27
- **Estado:** Pendiente de implementacion
- **Cubre:** RF-01 (autenticar al usuario y resolver su organizacion, rol y ambito)
- **ADR relacionados:** ADR-05 (Supabase Auth emite, el backend valida), ADR-02 (hexagonal)
- **Bloquea:** todas las demas historias
- **Bloqueado por:** nada. Es la primera.

---

## 1. Titulo y descripcion

**Titulo:** HU-01 — Acceso y sesion

**Descripcion:** Permitir que una persona se identifique en la aplicacion y que el sistema
sepa, en cada peticion, **quien es, que rol tiene y a que organizacion pertenece**. El
usuario inicia sesion con su correo y contrasena, la aplicacion guarda su sesion, y a partir
de ese momento todas sus peticiones van identificadas.

Esta historia es de **solo lectura sobre la identidad**: no crea usuarios ni cambia roles.
La creacion de usuarios es HU-03, y los permisos que el rol le da son HU-02.

El proveedor de identidad es **Supabase Auth**, que emite el token. El backend no emite
tokens: valida el que recibe y resuelve el perfil. El frontend usa el SDK de Supabase para
el login.

---

## 2. Alcance y fuera de alcance

### En alcance

| # | Capacidad |
|---|---|
| 1 | Inicio de sesion con correo y contrasena |
| 2 | Persistencia de la sesion entre recargas |
| 3 | Consulta del perfil del usuario autenticado (nombre, rol, organizacion) |
| 4 | Cierre de sesion |
| 5 | Validacion del token en cada peticion, con expiracion real |
| 6 | Comportamiento ante token ausente, invalido, expirado o adulterado |

### Fuera de alcance

| # | Fuera de alcance | Va en |
|---|---|---|
| 1 | Crear, editar o desactivar usuarios | HU-03 |
| 2 | Cambiar roles o asignar permisos | HU-02, HU-03 |
| 3 | Comprobacion de permisos sobre documentos | HU-02 |
| 4 | Hash de contrasenas: vive en Supabase Auth | Fuera del proyecto |
| 5 | Tabla de sesiones propia: la maneja Supabase Auth | Fuera del proyecto |
| 6 | Recuperacion de contrasena ("olvide mi clave") | Flujo de Supabase Auth |
| 7 | Verificacion por correo o segundo factor | Flujo de Supabase Auth |
| 8 | SSO corporativo (SAML, OIDC) | `[PENDIENTE]` Si el cliente lo pide |

---

## 3. Bloqueos y dependencias

### Lo que BLOQUEA esta HU

Nada. Es la primera en construir.

### Esta HU BLOQUEA

- HU-02 (roles y permisos), porque el permiso se comprueba en el caso de uso y necesita
  saber quien es el usuario.
- HU-03 (administracion de usuarios).
- HU-04 a HU-10, en bloque: todas las peticiones autenticadas dependen de esto.

### Requisitos de infraestructura

| Requisito | Detalle |
|---|---|
| Proyecto en Supabase | Con Auth habilitado |
| Politica RLS en `perfiles` | El backend lee el perfil con el JWT del usuario |
| Tabla `perfiles` | Debe existir y tener al menos una fila por usuario |
| `SUPABASE_JWT_SECRET` | Para verificar la firma del token. **Solo en proyectos con claves simetricas** |
| Tabla `sesiones_revocadas` | Para que el cierre de sesion invalide el token de inmediato (ADR-31) |

---

## 4. Variables y configuracion

| Variable | dev | staging | prod | Default |
|---|---|---|---|---|
| `SUPABASE_URL` | local | por definir | por definir | — (obligatoria) |
| `SUPABASE_ANON_KEY` | local | por definir | por definir | — (obligatoria) |
| `SUPABASE_JWT_SECRET` | local | por definir | por definir | — (obligatoria, 32+ chars. Solo con claves simetricas) |
| `SUPABASE_JWKS_URL` | `{SUPABASE_URL}/auth/v1/.well-known/jwks.json` | por definir | por definir | — (obligatoria con claves asimetricas) |
| `SUPABASE_SERVICE_ROLE_KEY` | local | por definir | por definir | — (obligatoria, solo backend) |
| `CORS_ORIGINS` | `http://localhost:5173` | por definir | por definir | — (obligatoria) |
| `JWT_ISSUER` | `{SUPABASE_URL}/auth/v1` | `{SUPABASE_URL}/auth/v1` | `{SUPABASE_URL}/auth/v1` | `{SUPABASE_URL}/auth/v1` |
| `JWT_AUDIENCE` | `authenticated` | `authenticated` | `authenticated` | `authenticated` |

> **`JWT_ISSUER` no es una cadena de la aplicacion.** El emisor real de un token emitido
> por Supabase Auth es `{SUPABASE_URL}/auth/v1`. Si el middleware exige `"risk-app"`,
> rechaza **todos** los tokens reales con 401. El valor se deriva de `SUPABASE_URL`, no se
> escribe a mano.
>
> **La firma se verifica con las claves publicas del proyecto.** Los proyectos nuevos de
> Supabase usan claves **asimetricas** (JWKS en `{SUPABASE_URL}/auth/v1/.well-known/jwks.json`,
> RS256 o ES256). `SUPABASE_JWT_SECRET` (HS256) es para proyectos antiguos. El backend
> admite las dos: la variable de entorno decide cual aplica.

**No hay TTL propio de sesion.** La duracion la define Supabase Auth. El backend no la
gestiona, solo la verifica.

**Sin feature toggles en esta HU.**

---

## 5. Suposiciones

1. Supabase Auth esta habilitado y emite JWT firmados con la clave del proyecto.
2. Cada usuario de la aplicacion tiene una fila en `perfiles` con `rol` y `organizacion_id`.
   La creacion de esa fila la hace el administrador (HU-03) o una semilla inicial.
3. El `service_role` **no** se usa para atender peticiones de usuario final: el backend
   reenvia el JWT del usuario y deja que RLS filtre.
4. Un usuario sin `organizacion_id` asignado **puede** iniciar sesion, pero no puede operar
   sobre datos de organizacion: lo ve como un error de permisos, no como un fallo de
   autenticacion. `[PENDIENTE]` Confirmar con el cliente si conviene bloquearle antes.
   La organizacion **efectiva** sale de `organizaciones_miembros`, con
   `perfiles.organizacion_id` como respaldo (ADR-33): el aislamiento se resuelve desde la
   membresia, no desde la columna del perfil.
5. La sesion persiste en el navegador mediante el SDK de Supabase, que guarda el refresh
   token en `localStorage`. `[PENDIENTE]` Evaluar `httpOnly` con cookie si el cliente tiene
   una politica de seguridad estricta.
6. El cierre de sesion invalida el refresh token en Supabase, no solo en el cliente.
7. El reloj del servidor es la referencia para la expiracion. Si el reloj del cliente esta
   desfasado, no afecta la validacion: el backend decide.
8. El mensaje de error para "correo no existe" y "contrasena incorrecta" es el mismo, y el
   tiempo de respuesta tambien. `[PROPUESTO]` Lo aplica Supabase Auth; el backend no
   reimplementa el login.

---

## 6. Modelo de datos

Esta HU **no crea tablas**. Consulta las existentes:

| Tabla | Columnas usadas | Para que |
|---|---|---|
| `auth.users` | `id`, `email` | Identidad, gestionada por Supabase Auth |
| `perfiles` | `id`, `organizacion_id`, `rol`, `nombres`, `apellido_1`, `apellido_2`, `display_name`, `debe_cambiar_contrasena` | Datos de negocio del usuario |

**Nota:** `perfiles.id` es la FK a `auth.users.id`. El backend **no** consulta `auth.users`
directamente: la informacion de negocio esta en `perfiles`, y `auth.users` solo se usa en
la administracion de usuarios (HU-03).

---

## 7. Camino feliz principal

### 7.1 Iniciar sesion

1. El usuario abre la aplicacion y es redirigido a la pantalla de acceso.
2. Escribe su correo y contrasena.
3. El frontend llama al SDK de Supabase (`signInWithPassword`) con la URL y la `anon_key`.
4. Supabase Auth valida las credenciales y devuelve un access token (JWT) y un refresh token.
5. El frontend guarda la sesion en el almacenador del SDK y la suscribe en el store de Pinia.
6. El frontend llama a `GET /api/v1/auth/me` con el token en el header `Authorization`.
7. El backend extrae el token, verifica firma, `exp`, `aud` e `iss`, y consulta `perfiles`
   usando el mismo token (para que RLS filtre).
8. El backend construye el `AuditContext` con `usuario_id`, `rol` y `organizacion_id`.
9. El backend responde `200` con el envelope y el recurso de perfil.
10. El frontend guarda el perfil en el store y redirige a la pantalla principal.

### 7.2 Navegar con la sesion activa

1. El usuario navega a una pantalla protegida.
2. El cliente HTTP adjunta el token a la peticion de forma automatica.
3. El middleware valida el token y construye el contexto.
4. El caso de uso comprueba el permiso que corresponda (HU-02).
5. La respuesta llega con el envelope esperado.

### 7.3 Consultar el perfil

1. El frontend llama a `GET /api/v1/auth/me`.
2. El backend responde `200`:

```json
{
  "success": true,
  "message": "OK",
  "data": {
    "id": "8f3c...",
    "nombres": "Ana",
    "apellido_1": "Restrepo",
    "apellido_2": "Duque",
    "display_name": "Ana Restrepo Duque",
    "rol": "analista",
    "organizacion_id": "c41a...",
    "debe_cambiar_contrasena": false
  },
  "errors": null,
  "timestamp": "2026-11-27T12:00:00Z"
}
```

3. **El recurso no expone** `auth.users`, ni el hash de la contrasena, ni el refresh token.

### 7.4 Cerrar sesion

1. El usuario hace clic en "Salir".
2. El frontend llama a `signOut()` del SDK, que invalida el refresh token en Supabase.
3. El frontend llama a `POST /api/v1/auth/logout`.
4. El backend registra el evento en auditoria y responde `200`.
5. El frontend limpia el store y redirige a la pantalla de acceso.

---

## 8. Caminos tristes

| # | Escenario | Comportamiento del sistema | Codigo |
|---|---|---|---|
| SP-01 | Credenciales invalidas | El SDK devuelve error. La UI muestra "Correo o contrasena incorrectos". **El mismo mensaje** para correo inexistente y contrasena incorrecta | 400 en el SDK |
| SP-02 | Token ausente en una ruta protegida | El contexto queda anonimo. El guard levanta `NoAutenticadoError` | 401 |
| SP-03 | Token malformado (no es un JWT) | Igual que SP-02. **Nunca 500** | 401 |
| SP-04 | Token con firma adulterada | Igual que SP-02 | 401 |
| SP-05 | Token expirado | El SDK lo refresca de forma transparente si tiene refresh token valido. Si no, la UI cierra la sesion | 401 |
| SP-06 | Usuario desactivado en Supabase Auth | El login se rechaza | 401 |
| SP-07 | Usuario autenticado **sin fila en `perfiles`** | Se responde `403` con el codigo `perfil_inexistente`. No 500, no 404. Tambien es el caso de una **cuenta eliminada**: el backend no consulta `auth.users` (seccion 6), asi que no puede distinguirla de una que nunca tuvo perfil | 403 |
| SP-08 | Usuario autenticado **sin `organizacion_id`** | Sesion iniciada. Las operaciones que requieren organizacion devuelven `403` | 403 |
| SP-09 | Token de un proyecto de Supabase distinto | La firma no verifica | 401 |
| SP-10 | El usuario tiene `debe_cambiar_contrasena = true` | La UI muestra el formulario de nueva contrasena **antes** de cualquier pantalla protegida | 200 (sesion valida) |

---

## 9. Casos limite y casos "estupidos"

### Casos limite

| # | Caso | Comportamiento del sistema |
|---|---|---|
| EC-01 | Dos sesiones abiertas del mismo usuario en pestanas distintas | Ambas funcionan. La sesion se guarda por pestana, no por navegador |
| EC-02 | El usuario inicia sesion en otro equipo | Sesion independiente. `perfiles.debe_cambiar_contrasena` es por usuario, no por dispositivo |
| EC-03 | Refresh token expirado pero access token vigente | El access token sigue sirviendo hasta su expiracion. Despues, la UI cierra la sesion |
| EC-04 | El reloj del navegador va adelantado | No afecta nada: el backend valida contra su propio reloj |
| EC-05 | El usuario cierra la pestana a mitad de una peticion | La peticion se cancela. El backend no deja registros a medias: cada peticion es independiente |
| EC-06 | Un usuario pertenece a dos organizaciones | `[PENDIENTE]` El modelo `organizaciones_miembros` lo permite, pero el `perfil` tiene un solo `organizacion_id`. Hay que decidir si el contexto lleva una o varias organizaciones. **Supuesto aplicado:** la organizacion efectiva es la primera membresia por orden de creacion (PP-01) |
| EC-07 | `perfiles.rol` con un valor que no existe en la matriz | El backend lo rechaza al resolver permisos y responde `403`, no 500 |

### Casos "estupidos"

| # | Caso | Comportamiento del sistema |
|---|---|---|
| CE-01 | Header `Authorization: Bearer` sin token | 401. No 500 |
| CE-02 | Header `Authorization: <token>` sin la palabra `Bearer` | El backend lo rechaza con 401 en vez de adivinar |
| CE-03 | Token con espacios al inicio o al final | Se recorta; si sigue siendo invalido, 401 |
| CE-04 | Token de otro formato (opaque, no JWT) | 401 |
| CE-05 | Envio de un token en el cuerpo o en query params | El backend **solo** lee el header `Authorization`. El token en el cuerpo se ignora |
| CE-06 | Corpus JSON vacio en `POST /auth/logout` | 200. Cerrar sesion no necesita cuerpo |
| CE-07 | Header `Authorization` repetido | Se toma el primero. Se registra como anomalia en auditoria |
| CE-08 | Token con `exp` en el pasado y `iat` en el futuro | 401. La coherencia temporal se verifica |

---

## 10. Criterios de aceptacion

### CA-01: Login correcto
**Dado** un usuario existente con credenciales validas
**Cuando** envia su correo y contrasena
**Entonces** el sistema inicia sesion y navega a la pantalla principal
**Y** el perfil con nombre, rol y organizacion esta disponible en el store
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-02: Credenciales invalidas
**Dado** un usuario que escribe una contrasena incorrecta
**Cuando** intenta iniciar sesion
**Entonces** el mensaje es "Correo o contrasena incorrectos"
**Y** es **exactamente el mismo** que se muestra cuando el correo no existe
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-03: El backend no emite tokens
**Dado** el codigo de la API
**Cuando** se revisan los endpoints de autenticacion
**Entonces** **no existe** ningun endpoint que emita un token de sesion propio
**Y** el unico endpoint de autenticacion con escritura es el cierre de sesion
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-04: Token valido
**Dado** un token valido
**Cuando** se llama a `GET /api/v1/auth/me`
**Entonces** responde 200 con el perfil en el envelope
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-05: Token ausente
**Dado** una peticion a una ruta protegida sin header `Authorization`
**Cuando** se envia la peticion
**Entonces** responde 401 con el envelope de error
**Y** el codigo de error legible por maquina es `no_autenticado`
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-06: Token malformado o con firma adulterada
**Dado** un token invalido en cualquier forma
**Cuando** se envia la peticion
**Entonces** responde 401, **nunca 500**
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-07: El recurso no filtra datos sensibles
**Dado** la respuesta de `GET /api/v1/auth/me`
**Cuando** se inspecciona el cuerpo real
**Entonces** no contiene `auth.users`, ni hash de contrasena, ni refresh token, ni
`service_role`
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-08: El service_role no atiende peticiones de usuario
**Dado** el codigo del backend
**Cuando** se busca el uso de `service_role`
**Entonces** solo aparece en el adaptador de administracion de usuarios
**Y** ningun router de peticiones de usuario final lo alcanza
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-09: El perfil no se filtra por RLS
**Dado** un usuario de la organizacion A
**Cuando** pide el perfil de un usuario de la organizacion B
**Entonces** no lo obtiene: 404 o 403 segun la politica
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-10: Marcas de tiempo ISO-8601
**Dado** la respuesta de `GET /api/v1/auth/me`
**Cuando** se lee `timestamp` en JavaScript
**Entonces** `new Date(valor)` devuelve la fecha correcta, y el valor es una cadena RFC 3339,
no un numero
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-11: Cierre de sesion
**Dado** un usuario autenticado
**Cuando** cierra sesion
**Entonces** el backend responde 200 y registra el evento en auditoria
**Y** el `session_id` del token queda registrado en `sesiones_revocadas`
**Y** el token anterior **no vuelve a servir** en la peticion siguiente, sin esperar la
expiracion natural
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-12: Cambio de contrasena obligatorio
**Dado** un usuario con `debe_cambiar_contrasena = true`
**Cuando** inicia sesion
**Entonces** la UI le pide la nueva contrasena antes de mostrar cualquier pantalla protegida
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-13: La llave de firma no es obligatoria
**Dado** un entorno sin `SUPABASE_JWT_SECRET`
**Cuando** la aplicacion valida un token
**Entonces** lo valida con el **JWKS del proyecto** (`ES256`). `SUPABASE_JWT_SECRET` es
**opcional**: solo se usa si el token declara el algoritmo simetrico `HS256`
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL

### CA-14: Dos sesiones simultaneas
**Dado** el mismo usuario en dos navegadores
**Cuando** ambos estan autenticados
**Entonces** las dos sesiones funcionan de forma independiente
&nbsp;&nbsp;&nbsp;&nbsp;PASS / FAIL
