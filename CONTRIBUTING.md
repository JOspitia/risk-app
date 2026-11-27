# Guia de commits y pull requests

> Como se escriben los mensajes de commit y los pull requests de este repositorio.
> **La convencion es parte del proyecto**: se aplica desde el primer commit.

- **Estado:** vigente
- **Ultima actualizacion:** 2026-11-27

---

## 1. Por que una convencion

El historial de un repositorio es documentacion. Un mensaje de commit bien escrito
responde tres preguntas sin abrir el diff:

1. **Que** cambio.
2. **Por que** cambio (el "por que" no se deduce del diff).
3. **Como se verifica** que esta bien.

El repositorio ya tiene esa capa de verdad en los ADR y en las historias de usuario. El
commit es la capa de **resumen y trazabilidad** que las conecta.

---

## 2. Formato del commit

Se usa **Conventional Commits**, con los tipos en ingles (los usa la maquinaria) y el
contenido en espanol.

```
<tipo>(<ámbito>): <descripción>

<cuerpo: qué y por qué>

<pie: referencias>
```

### 2.1 Tipos

| Tipo | Cuando |
|---|---|
| `feat` | Capacidad nueva para el usuario |
| `fix` | Correccion de un defecto |
| `docs` | Documentacion: `.md`, ADR, HU, diagramas |
| `refactor` | Reestructuracion **sin** cambio de comportamiento |
| `test` | Pruebas nuevas o corregidas |
| `perf` | Mejora de rendimiento |
| `build` | Dependencias, `pyproject.toml`, `Dockerfile`, CI |
| `chore` | Tareas que no tocan codigo ni docs (formateo, `.gitignore`) |
| `revert` | Reversa de un commit anterior |
| `ci` | Configuracion de integracion continua |

### 2.2 Ambito

Opcional. Es el modulo afectado, en minusculas y sin espacios:

```
auth, permisos, pipeline, storage, llm, frontend, migraciones, docs, infra
```

### 2.3 Descripcion

- **Imperativo**: "agrega", no "agregado" ni "agrega".
- **En espanol, sin anglicismos innecesarios.**
- **Sin punto final.**
- **Corta**: 72 caracteres como maximo. Si no cabe, el detalle va en el cuerpo.
- **Contexto en la primera linea**: "agrega" solo no dice nada. "agrega validacion de
  esquema a la salida del LLM" si.

### 2.4 Cuerpo

Se usa cuando la primera linea no explica el **por que**. Envoltorio de 72 caracteres.

```
docs: agrega HU de analisis del documento

La HU fija el flujo Map-Reduce y el error explicito cuando el PDF no
tiene capa de texto. Sin ella, ese fallo queda como un analisis vacio
marcado como completado.

Cierra HU-07.
```

### 2.5 Pie

```
Refs: HU-07
Cierra: ADR-11
```

Si el commit implementa un ADR o una HU, se referencia. Eso permite reconstruir por que
existe cada linea de codigo.

---

## 3. Ejemplos

```
docs: estructura documental inicial de Risk-app
docs: agrega HU de roles y permisos
feat(auth): valida el JWT de Supabase en cada peticion
fix(permisos): deniega por defecto cuando el permiso no esta en la matriz
refactor(chunking): deriva el tamano de bloque de la ventana del modelo
test(documentos): cubre el ciclo de vida completo contra Supabase real
build: fija Python 3.14.10 y FastAPI 0.165.0
chore: excluye la documentacion generada del control de versiones
```

---

## 4. Reglas de los commits

1. **Un commit, un objetivo.** Si el mensaje necesita una "y", probablemente son dos
   commits.
2. **El commit no rompe el build.** Si un commit deja la suite en rojo, el historial miente
   sobre que estado tiene el proyecto.
3. **No se reescribe historia publicada.** Si algo ya se empujó, se corrige con un commit
   nuevo, no con un rebase.
4. **El cuerpo explica el por que.** El *que* ya esta en el diff.
5. **Se commitea temprano y seguido.** Un commit por unidad logica terminada.
6. **Sin secretos.** Ni claves, ni `.env`, ni tokens. El `.gitignore` los excluye, pero la
   responsabilidad es de quien commitea.

---

## 5. Ramas

| Rama | Uso |
|---|---|
| `main` | Rama estable. Lo que se despliega |
| `feat/<descripcion>` | Capacidad nueva |
| `fix/<descripcion>` | Correccion de un defecto |
| `docs/<descripcion>` | Documentacion |
| `refactor/<descripcion>` | Reestructuracion |

**Regla:** `main` solo recibe cambios que pasaron el gate del `CHECKLIST.md`. El trabajo
ocurre en una rama y llega a `main` por pull request.

---

## 6. Pull request

### 6.1 Titulo

Usa **el mismo formato del commit**. El titulo del PR es el resumen de la rama, y un PR
con el titulo "cambios varios" no se puede revisar.

```
feat(pipeline): agrega el analisis Map-Reduce en el navegador
```

### 6.2 Cuerpo

Cinco bloques, en este orden:

```markdown
## Que

Una o dos frases. Que hace el PR.

## Por que

El problema que resuelve. Si responde a un ADR o a una HU, se cita aqui.

## Como se valido

Que se ejecuto y que salio. Si no se ejecutaron pruebas, se dice explicitamente.

## Trazabilidad

- RF: RF-04, RF-05, RF-06
- ADR: ADR-08, ADR-09
- HU: HU-07

## Checklist

- [ ] El caso de uso devuelve un DTO, no una entidad cruda
- [ ] La salida del LLM se valida contra el esquema antes de persistir
- [ ] Las pruebas del ciclo de vida pasan contra Supabase real
```

### 6.3 Antes de pedir la revision

- [ ] La rama esta actualizada con `main`.
- [ ] `CHECKLIST.md` pasa en los gates que aplican a este cambio.
- [ ] Los criterios de aceptacion de la HU afectada tienen prueba.
- [ ] El PR explica el **por que**, no solo el **que**.
- [ ] No hay secretos, ni `.env`, ni datos reales de cliente.

### 6.4 Merge

- Con squash cuando la rama tenga commits de exploracion que no cuentan como historia.
- Con merge commit cuando cada commit tenga sentido por si solo. **Este repositorio usa la
  segunda forma**: cada commit del historial tiene que explicar algo.

---

## 7. Que NO va en un commit

| No va | Por que | Donde va |
|---|---|---|
| Claves, tokens, `.env` | Es una fuga, y el historial no se puede limpiar de verdad | Variables de entorno del proveedor |
| Archivos generados (`dist/`, `__pycache__/`) | Ruido en el diff | Se regeneran |
| Cambios de formato junto a cambios de logica | Dificulta revisar el diff real | Commits separados |
| Archivos de mas de 500 lineas generados a mano | No se revisan | Se generan de una plantilla |
| El texto del documento de un cliente | Es el activo mas sensible del proyecto | Almacenamiento privado, con RLS |

---

## 8. Referencia

| Documento | Que contiene |
|---|---|
| [`AGENTS.md`](AGENTS.md) | Reglas del repositorio y orden de lectura |
| [`CHECKLIST.md`](CHECKLIST.md) | Gates que hay que pasar antes de mergear |
| [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md) | Tabla de ADR |
| [`docs/HU/INDICE.md`](docs/HU/INDICE.md) | Historias de usuario y su trazabilidad |
