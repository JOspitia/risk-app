import createClient from 'openapi-fetch'

import { supabase } from './supabase'
import type { components, paths } from './types'

export type DetalleError = components['schemas']['DetalleError']

/**
 * Error de la API.
 *
 * La API responde siempre con el mismo envelope (`success`, `message`, `data`,
 * `errors`, `timestamp`). El error trae el estado HTTP y el codigo legible por
 * maquina: `no_autenticado`, `perfil_inexistente`, ...
 */
export class ErrorApi extends Error {
  readonly estado: number
  readonly codigo: string
  readonly detalle: string

  constructor(estado: number, codigo: string, detalle: string) {
    super(detalle)
    this.name = 'ErrorApi'
    this.estado = estado
    this.codigo = codigo
    this.detalle = detalle
  }
}

/**
 * El token que viaja en el header `Authorization`.
 *
 * Vive aqui y en ningun otro lado: **ningun `fetch` de la aplicacion escribe
 * ese header a mano** (SKILL.md 11.2). El store lo actualiza cuando la sesion
 * cambia, y el cierre de sesion vuelve a poner el token capturado para poder
 * revocar la sesion en el backend despues del `signOut`.
 */
let tokenEnCurso: string | null = null

/** El 401 ya se atendio: no se repite la redireccion hasta que haya sesion nueva. */
let atendido401 = false

export function fijarToken(token: string | null): void {
  tokenEnCurso = token
  if (token !== null) {
    // Una sesion nueva vuelve a activar el manejo del 401.
    atendido401 = false
  }
}

export function tokenActual(): string | null {
  return tokenEnCurso
}

/**
 * Lo que hace la aplicacion cuando el backend responde 401.
 *
 * Lo registra `main.ts`: limpiar la sesion y volver a la pantalla de acceso.
 * Vive como callback y no como importacion directa para que el cliente HTTP
 * no dependa del store ni del router (y para que no haya un ciclo de
 * imports entre las tres piezas).
 */
export type ManejadorNoAutenticado = () => void | Promise<void>

let manejadorNoAutenticado: ManejadorNoAutenticado | null = null

export function registrarManejadorNoAutenticado(
  manejador: ManejadorNoAutenticado | null,
): void {
  manejadorNoAutenticado = manejador
}

async function atenderNoAutenticado(): Promise<void> {
  if (atendido401) {
    return
  }
  atendido401 = true
  await manejadorNoAutenticado?.()
}

async function tokenDeSupabase(): Promise<string | null> {
  const { data } = await supabase.auth.getSession()
  return data.session?.access_token ?? null
}

/**
 * Cliente HTTP de la API.
 *
 * Un solo interceptor anade el bearer y maneja el 401. Los tipos vienen del
 * OpenAPI del backend (`api/types.ts`), generados: no se escriben a mano.
 */
export const cliente = createClient<paths>({
  baseUrl: import.meta.env.VITE_API_BASE_URL,
  // El `fetch` se resuelve en cada llamada y no al crear el cliente: si se
  // guardara la referencia, el cliente usaria siempre el `fetch` de ese
  // momento y las pruebas no podrian interceptarlo.
  fetch: (peticion) => globalThis.fetch(peticion),
})

// Un solo interceptor anade el bearer y maneja el 401. El middleware global
// se registra con `use`: en `createClient` el middleware es por peticion.
cliente.use({
  async onRequest({ request }) {
    const token = tokenEnCurso ?? (await tokenDeSupabase())
    if (token !== null) {
      request.headers.set('Authorization', `Bearer ${token}`)
    }
  },
  async onResponse({ response }) {
    if (response.status === 401) {
      await atenderNoAutenticado()
    }
  },
})

type EnvelopeDeError = {
  message: string
  errors: DetalleError[]
}

/**
 * Lee el envelope de error de una respuesta.
 *
 * El OpenAPI no documenta las respuestas de error, asi que el cuerpo llega sin
 * tipo. Se valida en el limite: si no tiene la forma del envelope, se devuelve
 * un error generico con el estado HTTP, nunca un `undefined` disfrazado.
 */
function leerEnvelope(error: unknown): EnvelopeDeError | null {
  if (typeof error !== 'object' || error === null) {
    return null
  }
  const registro = error as Record<string, unknown>
  const mensaje = registro['message']
  if (typeof mensaje !== 'string') {
    return null
  }
  const errores: DetalleError[] = []
  const lista = registro['errors']
  if (Array.isArray(lista)) {
    for (const item of lista) {
      if (typeof item !== 'object' || item === null) {
        continue
      }
      const campos = item as Record<string, unknown>
      const codigo = campos['codigo']
      const detalle = campos['detalle']
      if (typeof codigo === 'string' && typeof detalle === 'string') {
        errores.push({ codigo, detalle })
      }
    }
  }
  return { message: mensaje, errors: errores }
}

/**
 * Traduce el cuerpo de una respuesta de error en un `ErrorApi`.
 *
 * `codigo` es el identificador que la persona decide con; `detalle` es la
 * explicacion para quien la lee.
 */
export function errorDeLaRespuesta(error: unknown, estado: number): ErrorApi {
  const envelope = leerEnvelope(error)
  if (envelope === null) {
    return new ErrorApi(
      estado,
      'error_desconocido',
      `La API respondio con el estado ${estado}`,
    )
  }
  const primero = envelope.errors[0]
  if (primero === undefined) {
    return new ErrorApi(estado, 'error_desconocido', envelope.message)
  }
  return new ErrorApi(estado, primero.codigo, primero.detalle)
}
