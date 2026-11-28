# Referencias

Codigo de terceros clonado **solo para leer y comparar**. No es parte de Risk-app.

---

## Por que esta carpeta existe

Antes de implementar una funcionalidad, a veces conviene ver como la resolvio otra
persona. Aqui se clonan repositorios de referencia y se leen. De cada uno sale un
documento en `docs/` que explica que idea hay detras y que se puede aprender.

**Reglas:**

- **No se copia codigo** de aqui al proyecto. Se copian ideas, no implementaciones.
- **No se contribuye** a estos repositorios.
- **No se versiona** el `.git` de un clon. Ver la nota de abajo.
- El analisis vive en `docs/`, no en un README dentro del clon.

---

## Indice de referencias

| Carpeta | Que es | Analisis |
|---|---|---|
| `vulnerability-tracker/` | Prototipo local de seguimiento de vulnerabilidades y pentests (GRC). Node + SQLite + un HTML. Hecho por Fabioh (Mugetsuop) | [`docs/ANALISIS-REFERENCIA-VULNERABILITY-TRACKER.md`](../docs/ANALISIS-REFERENCIA-VULNERABILITY-TRACKER.md) |

---

## Como se clona una referencia

```bash
cd referencias
git clone --depth 1 https://github.com/<dueño>/<repo>.git <carpeta>
```

`--depth 1` porque no interesa la historia completa del repositorio ajeno: interesa el
estado actual.

### El `.git` del clon

Un clon trae su propio `.git`, y dentro de este repositorio eso confunde a `git status`
y al `git ls-files`. Por eso, despues de clonar:

```bash
rm -rf <carpeta>/.git
```

Sin el `.git` del clon, la carpeta es un conjunto de archivos mas en el arbol de
Risk-app. Es lo que se quiere: **una copia de lectura**, no un repositorio anidado.

> Si el clon llegara a versionarse, `git status` lo trataria como un *submodulo* o como
> archivos sin seguimiento, y el `git add` podria meterlo dentro por error. Se evita
> quitando el `.git` del clon.

---

## Cuando el analisis se aplica

Un analisis de referencia **no cambia el proyecto por si solo**. Sus conclusiones
terminan en una de estas tres:

1. **Una decision del cliente** — se registra como pregunta abierta en
   `docs/DECISIONES-PENDIENTES.md` (PP-xx).
2. **Un ADR** — si la conclusion cambia el modelo de datos, la estructura de carpetas o
   el contrato de la API.
3. **Una HU** — si la conclusion es una funcionalidad nueva que hay que especificar.

Lo que **no** se hace: meter ideas al codigo porque "en el otro proyecto lo hicieron
asi". Un prototipo local sin autenticacion, sin multiusuario y sin auditoria no es el
modelo de referencia para un producto que tiene las tres cosas.
