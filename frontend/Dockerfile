# =============================================================================
# El frontend en Docker
#
# Dos etapas, y cada una sirve para una cosa distinta:
#
# - **dev**: el servidor de desarrollo de Vite, con recarga en caliente. Es lo que
#   se usa para trabajar: se edita el codigo en el host y la pagina recarga sola.
# - **prod**: el bundle de produccion servido por nginx. Es lo que se despliega
#   en Vercel, asi que es lo que hay que validar a mano antes de publicar.
#
# Las dos etapas usan la misma imagen: `docker compose --profile dev up -d` y
# `docker compose --profile prod up -d` levantan la que corresponde.
#
# -----------------------------------------------------------------------------
# LAS VARIABLES DE ENTORNO
#
# Las variables `VITE_` se leen **al compilar**, no al arrancar: Vite las
# hornea en el bundle. Por eso en la etapa `prod` son argumentos de build, y por
# eso un `docker compose up` sin reconstruir NO cambia las variables.
#
# Este archivo **no lleva llaves de verdad**. Las variables usan la forma
# `${VARIABLE:-valor_por_defecto}`, y los valores por defecto son los del stack
# local de desarrollo, que son publicos: los imprime `supabase start`.
#
# Lo mismo que en el compose del backend, y por el mismo motivo: la push
# protection de GitHub bloquea cualquier push que contenga una llave de
# Supabase, y hace bien.
# =============================================================================

# -----------------------------------------------------------------------------
# Las dependencias.
#
# Es una etapa aparte para que la capa de `node_modules` no se invalide cada vez
# que cambia un archivo del codigo: se copia desde aqui, no desde el contexto.
# -----------------------------------------------------------------------------
FROM node:24-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --legacy-peer-deps

# -----------------------------------------------------------------------------
# Desarrollo: el servidor de Vite, escuchando en todas las interfaces.
#
# `0.0.0.0` es lo que hace que el contenedor sea alcanzable desde el host: si
# escucha solo en `localhost`, el navegador del host no lo encuentra.
#
# Las variables se leen en tiempo de ejecucion (Vite las expone al arrancar el
# dev server), asi que aqui llegan por `environment`.
# -----------------------------------------------------------------------------
FROM node:24-alpine AS dev
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY package.json package-lock.json ./
COPY index.html tsconfig*.json vite.config.ts ./
COPY src ./src
COPY public ./public
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# -----------------------------------------------------------------------------
# Compilacion: el bundle de produccion.
#
# Las variables `VITE_` llegan como argumentos de build, que es la unica forma
# de que acaben dentro del bundle.
# -----------------------------------------------------------------------------
FROM node:24-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY package.json package-lock.json ./
COPY index.html tsconfig*.json vite.config.ts ./
COPY src ./src
COPY public ./public
ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_PUBLISHABLE_KEY
ARG VITE_API_BASE_URL
ENV VITE_SUPABASE_URL=$VITE_SUPABASE_URL
ENV VITE_SUPABASE_PUBLISHABLE_KEY=$VITE_SUPABASE_PUBLISHABLE_KEY
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

# -----------------------------------------------------------------------------
# Produccion: nginx sirve el bundle.
#
# El `try_files` es lo que hace que la aplicacion de una sola pagina funcione:
# cualquier ruta que no sea un archivo del bundle se responde con `index.html`,
# para que el enrutador del navegador tome la ruta.
# -----------------------------------------------------------------------------
FROM nginx:alpine AS prod
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
