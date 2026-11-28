# Historias de usuario — Risk-app

> Historias de usuario del proyecto. Cada una describe **un objetivo del usuario**, el camino
> feliz, los caminos de error y los **criterios de aceptacion** verificables.
>
> Que no duplican la especificacion tecnica: eso vive en [`../ARQUITECTURA.md`](../ARQUITECTURA.md)
> (34 ADR) y en [`../../SKILL.md`](../../SKILL.md) (los 9 contratos de codigo). Aqui va el
> **valor para el usuario** y el **como se comprueba que esta listo**.

- **Estado:** vigente
- **Ultima actualizacion:** 2026-11-27
- **Formato:** heredado de `prueba-tecnica/documentacion/` y `Serviklapp/docs/hus/`, unificado
  en el esqueleto de 10 secciones que ambos proyectos ya usaban.

---

## 1. Que aporta una HU aqui, y que no

| Ya existe | Lo que aporta la HU |
|---|---|
| Requisitos funcionales (RF-01 a RF-25) en `CONTEXTO.md` | El **recorrido** del usuario, no la lista de capacidades |
| 34 ADR con el "por que" de cada decision tecnica | Los **caminos de error**: que pasa cuando algo falla |
| Los 9 contratos de codigo del `SKILL.md` | Los **criterios de aceptacion** en formato PASS / FAIL |
| 17 gates de verificacion en `CHECKLIST.md` | El **alcance**: que queda explicitamente fuera |

**Regla:** una HU no introduce datos de negocio que no existan. Si un campo o una regla no
esta decidida, va marcado `[PENDIENTE]` y se anota en `DECISIONES-PENDIENTES.md`. No se
rellena con un ejemplo plausible.

---

## 2. Esqueleto comun

Todas las HU usan las mismas 10 secciones, en este orden:

1. **Titulo y descripcion** — el objetivo del usuario, en una frase.
2. **Alcance y fuera de alcance** — que hace esta HU y que hace la siguiente.
3. **Bloqueos y dependencias** — que tiene que existir antes, y que espera esta HU.
4. **Variables y configuracion** — parametros, con su valor por defecto.
5. **Suposiciones** — lo que se da por cierto mientras no se demuestre lo contrario.
6. **Modelo de datos** — solo si la HU crea o modifica tablas.
7. **Camino feliz principal** — paso a paso, numerado.
8. **Caminos tristes** — errores esperados, con su codigo y su mensaje.
9. **Casos limite y casos "estupidos"** — los bordes y los abuse.
10. **Criterios de aceptacion** — Given / When / Then, cada uno PASS / FAIL.

---

## 3. Indice de historias

| HU | Titulo | Cubre | Estado |
|---|---|---|---|
| [HU-01](HU-01-acceso-y-sesion.md) | Acceso y sesion | RF-01, ADR-05 | Escrita |
| [HU-02](HU-02-roles-y-permisos.md) | Roles y permisos | RF-15, ADR-12, ADR-17 | Escrita |
| [HU-03](HU-03-administracion-usuarios.md) | Administracion de usuarios | RF-16, ADR-13, ADR-18 | Escrita |
| [HU-04](HU-04-configuracion-motor.md) | Configuracion del motor IA | RF-02, RF-20, ADR-16 | Escrita |
| [HU-05](HU-05-compatibilidad-y-descarga-modelo.md) | Compatibilidad del equipo y descarga del modelo | RF-13, ADR-06, ADR-19 | Escrita |
| [HU-06](HU-06-carga-y-archivo.md) | Carga y archivo de un documento | RF-03, RF-22, ADR-20 | Escrita |
| [HU-07](HU-07-analisis-documento.md) | Analisis del documento (ETL + Map-Reduce) | RF-04 a RF-07, ADR-08, ADR-09, ADR-11 | Escrita |
| [HU-08](HU-08-seguimiento-del-trabajo.md) | Seguimiento del trabajo | RF-17, RF-18, RF-21, ADR-14 | Escrita |
| [HU-09](HU-09-consulta-de-resultados.md) | Consulta de resultados y descarga | RF-09, RF-19, RF-23, ADR-15 | Escrita |
| [HU-10](HU-10-reanalisis-con-plantilla-vigente.md) | Reanalisis con la plantilla vigente | RF-24, DP-13, ADR-20 | Escrita |
| [HU-11](HU-11-plantillas-de-extraccion.md) | Plantillas de extraccion | RF-11, ADR-34 | Escrita |
| [HU-12](HU-12-eliminacion-de-documento.md) | Eliminacion de un documento y su archivo | RF-25, ADR-20, ADR-22 | Escrita |

### 3.1 Orden de implementacion

Las HU no son todas independientes. Este es el orden en que se pueden construir:

```
HU-01 (sesion)
   |
   +-> HU-02 (permisos) -----> HU-03 (admin usuarios)
   |                                |
   +-> HU-04 (motor) --------- HU-05 (compatibilidad)
   |                                |
   +-> HU-06 (carga) ----------> HU-07 (analisis) --> HU-08 (seguimiento)
   |                                                              |
   +--------------------------------------------------------------+--> HU-09 (consulta)
   |                                                                      |
   +-> HU-11 (plantillas) ---> HU-12 (eliminacion)                        |
   |                                                                      |
   +----------------------------------------------------------------------+--> HU-10 (reanalisis)
```

**HU-01 es la unica bloqueante de todas.** Las demas se pueden construir en cualquier
orden siempre que sus bloqueos esten resueltos.

**HU-11 (plantillas) va antes que HU-07 (analisis) en la practica**, aunque no lo bloquee
formalmente: el analisis necesita una plantilla que extraer, y la plantilla semilla v1
viene en la migracion. Lo que bloquea HU-07 es que la semilla exista, no que la HU este
terminada.

**HU-12 (eliminacion) es la ultima**: necesita que exista el archivo archivado, que es
HU-06.

---

## 4. Como se usa una HU en el trabajo diario

- **Al implementar:** la HU dice que comportamiento se espera. Los criterios de
  aceptacion se traducen **directamente en pruebas**. Si un criterio no tiene prueba, la HU
  no esta terminada.
- **Al revisar:** se recorre la lista de criterios de aceptacion y se marca PASS / FAIL. Un
  FAIL significa que la HU no esta lista.
- **Al hacer la demo:** el camino feliz de cada HU arma el guion. Si una HU no esta, la demo
  pierde un paso.
- **Al integrar el frontend:** el gate 9 de `CHECKLIST.md` (listo para el frontend)
  verifica que la API cumple lo que las HU prometen.

### 4.1 Las HU guian; el checklist verifica

Es la pregunta que mas se repite al retomar el proyecto: **¿sigo la HU o el gate?**

**Las HU guian.** Son la unidad de trabajo: cada una describe un comportamiento del
usuario, con su camino feliz, sus caminos de error y sus criterios de aceptacion. Se
implementa **una HU**, no "un gate".

**El checklist verifica.** Los gates no son una lista de trabajo: son **condiciones que
deben cumplirse** para que lo implementado sea correcto. Un gate no se "implementa": se
**marca** cuando el codigo que lo sustenta existe y esta verificado.

> Un gate no es una tarea. Es una propiedad que el codigo tiene o no tiene.

### 4.2 El ciclo

```
1. Elegir la HU siguiente (por el grafo de dependencias de la seccion 3)
2. Implementar su comportamiento, con sus pruebas
3. Verificar los gates que esa HU toca  ->  marcar [x] con la evidencia
4. La HU esta lista cuando sus criterios de aceptacion dan PASS
```

El paso 3 es el que conecta las dos cosas: **al terminar una HU se activan los items del
checklist que esa HU cubre**. No al revés.

### 4.3 Donde esta la tabla de "que gate toca que HU"

En [CHECKLIST.md](../../CHECKLIST.md), seccion **"Gates por HU"**. Es el unico lugar donde
se ve, para todas las HU, que items del checklist se activan al cerrar cada una.
---

## 5. Trazabilidad

Cada HU declara que **RF** (requisito funcional) y que **ADR** (decision tecnica) cubre.
Si un cambio de codigo invalida una HU, se actualizan los dos en el mismo commit.

El indice completo de RF vive en [`../CONTEXTO.md`](../CONTEXTO.md#71-funcionales) y el de
ADR en [`../ARQUITECTURA.md`](../ARQUITECTURA.md#10-registro-de-decisiones-adr).
