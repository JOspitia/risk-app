import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const sdk = vi.hoisted(() => ({
  getSession: vi.fn(),
}))

vi.mock('@/api/supabase', () => ({
  supabase: {
    auth: {
      getSession: sdk.getSession,
    },
  },
}))

import {
  cliente,
  errorDeLaRespuesta,
  fijarToken,
  registrarManejadorNoAutenticado,
} from '@/api/cliente'

const PERFIL = {
  id: '8f3c0000-0000-0000-0000-000000000000',
  nombres: 'Ana',
  apellido_1: 'Restrepo',
  apellido_2: null,
  display_name: 'Ana Restrepo',
  rol: 'analista',
  organizacion_id: 'c41a0000-0000-0000-0000-000000000000',
  debe_cambiar_contrasena: false,
}

const ENVELOPE_PERFIL = {
  success: true,
  message: 'Perfil consultado',
  data: PERFIL,
  errors: null,
  timestamp: '2026-11-27T12:00:00Z',
}

const ENVELOPE_ERROR = {
  success: false,
  message: 'No autenticado',
  data: null,
  errors: [{ codigo: 'no_autenticado', detalle: 'Falta el token' }],
  timestamp: '2026-11-27T12:00:00Z',
}

function respuesta(cuerpo: unknown, estado: number): Response {
  return new Response(JSON.stringify(cuerpo), {
    status: estado,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('cliente HTTP', () => {
  let peticiones: Request[] = []

  beforeEach(() => {
    peticiones = []
    sdk.getSession.mockResolvedValue({ data: { session: null }, error: null })
    // Un token vigente reinicia el manejo del 401: el modulo remembers si
    // ya aviso, y cada prueba empieza desde cero.
    fijarToken('token-de-prueba')
    vi.stubGlobal(
      'fetch',
      vi.fn(async (peticion: Request) => {
        peticiones.push(peticion)
        return respuesta(ENVELOPE_PERFIL, 200)
      }),
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    fijarToken(null)
    registrarManejadorNoAutenticado(null)
  })

  it('escribe el token en el header Authorization', async () => {
    await cliente.GET('/api/v1/auth/me')

    expect(peticiones).toHaveLength(1)
    expect(peticiones[0]?.headers.get('Authorization')).toBe('Bearer token-de-prueba')
  })

  it('no escribe el header Authorization cuando no hay sesion', async () => {
    fijarToken(null)

    await cliente.GET('/api/v1/auth/me')

    expect(peticiones[0]?.headers.get('Authorization')).toBeNull()
  })

  it('toma el token del SDK cuando el store todavia no lo tiene', async () => {
    fijarToken(null)
    sdk.getSession.mockResolvedValue({
      data: {
        session: { access_token: 'token-del-sdk', refresh_token: 'r', expires_in: 1 },
      },
      error: null,
    })

    await cliente.GET('/api/v1/auth/me')

    expect(peticiones[0]?.headers.get('Authorization')).toBe('Bearer token-del-sdk')
  })

  it('avisa una sola vez cuando el backend responde 401', async () => {
    const manejador = vi.fn()
    registrarManejadorNoAutenticado(manejador)
    vi.stubGlobal('fetch', vi.fn(async () => respuesta(ENVELOPE_ERROR, 401)))

    await cliente.GET('/api/v1/auth/me')
    await cliente.GET('/api/v1/auth/me')

    expect(manejador).toHaveBeenCalledTimes(1)
  })

  it('una sesion nueva vuelve a activar el manejo del 401', async () => {
    const manejador = vi.fn()
    registrarManejadorNoAutenticado(manejador)
    vi.stubGlobal('fetch', vi.fn(async () => respuesta(ENVELOPE_ERROR, 401)))

    await cliente.GET('/api/v1/auth/me')
    fijarToken('token-nuevo')
    await cliente.GET('/api/v1/auth/me')

    expect(manejador).toHaveBeenCalledTimes(2)
  })

  it('traduce el envelope de error en un error con estado y codigo', () => {
    const error = errorDeLaRespuesta(ENVELOPE_ERROR, 401)

    expect(error.estado).toBe(401)
    expect(error.codigo).toBe('no_autenticado')
    expect(error.detalle).toBe('Falta el token')
  })

  it('un cuerpo que no es el envelope tambien produce un error con estado', () => {
    const error = errorDeLaRespuesta('texto plano', 500)

    expect(error.estado).toBe(500)
    expect(error.codigo).toBe('error_desconocido')
  })
})
