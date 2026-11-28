import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const sdk = vi.hoisted(() => ({
  getSession: vi.fn(),
  signInWithPassword: vi.fn(),
  signOut: vi.fn(),
  updateUser: vi.fn(),
  onAuthStateChange: vi.fn(),
  from: vi.fn(),
}))

vi.mock('@/api/supabase', () => ({
  supabase: {
    auth: {
      getSession: sdk.getSession,
      signInWithPassword: sdk.signInWithPassword,
      signOut: sdk.signOut,
      updateUser: sdk.updateUser,
      onAuthStateChange: sdk.onAuthStateChange,
    },
    from: sdk.from,
  },
}))

import { useSesionStore } from '@/stores/sesion'

const PERFIL = {
  id: '8f3c0000-0000-0000-0000-000000000000',
  nombres: 'Ana',
  apellido_1: 'Restrepo',
  apellido_2: null,
  display_name: 'Ana Restrepo Duque',
  rol: 'analista',
  organizacion_id: 'c41a0000-0000-0000-0000-000000000000',
  debe_cambiar_contrasena: false,
}

function envelopePerfil(debeCambiar: boolean): unknown {
  return {
    success: true,
    message: 'Perfil consultado',
    data: { ...PERFIL, debe_cambiar_contrasena: debeCambiar },
    errors: null,
    timestamp: '2026-11-27T12:00:00Z',
  }
}

function sesionSupabase(accessToken = 'token-de-prueba'): unknown {
  return {
    access_token: accessToken,
    refresh_token: 'refresh-de-prueba',
    expires_in: 3600,
    expires_at: 0,
    token_type: 'bearer',
    user: { id: 'usuario-1', email: 'ana@ejemplo.com' },
  }
}

function respuesta(cuerpo: unknown, estado = 200): Response {
  return new Response(JSON.stringify(cuerpo), {
    status: estado,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('store de sesion', () => {
  let orden: string[] = []
  let peticiones: Request[] = []

  beforeEach(() => {
    setActivePinia(createPinia())
    orden = []
    peticiones = []
    vi.clearAllMocks()

    sdk.onAuthStateChange.mockReturnValue({
      data: { subscription: { unsubscribe: vi.fn() } },
    })
    sdk.signOut.mockImplementation(async () => {
      orden.push('sdk:signOut')
      return { error: null }
    })
    sdk.getSession.mockImplementation(async () => ({
      data: { session: sesionSupabase() },
      error: null,
    }))
    sdk.updateUser.mockImplementation(async () => {
      orden.push('sdk:updateUser')
      return { data: { user: null }, error: null }
    })

    vi.stubGlobal(
      'fetch',
      vi.fn(async (peticion: Request) => {
        peticiones.push(peticion)
        if (peticion.method === 'POST') {
          if (peticion.url.includes('/cambiar-contrasena')) {
            orden.push('http:cambiar-contrasena')
            return respuesta({
              success: true,
              message: 'Credencial confirmada',
              data: { usuario_id: 'usuario-1', confirmado: true },
              errors: null,
              timestamp: '2026-11-27T12:00:00Z',
            })
          }
          orden.push('http:logout')
          return respuesta({
            success: true,
            message: 'Sesion cerrada',
            data: { session_id: 'sesion-1', revocado: true },
            errors: null,
            timestamp: '2026-11-27T12:00:00Z',
          })
        }
        return respuesta(envelopePerfil(false))
      }),
    )
  })

  it('restaura la sesion al recargar la pagina', async () => {
    const sesion = useSesionStore()

    await sesion.restaurar()

    expect(sesion.autenticado).toBe(true)
    expect(sesion.perfil?.display_name).toBe('Ana Restrepo Duque')
    expect(peticiones[0]?.headers.get('Authorization')).toBe('Bearer token-de-prueba')
  })

  it('sin sesion en el almacenador no queda autenticado', async () => {
    sdk.getSession.mockResolvedValue({ data: { session: null }, error: null })
    const sesion = useSesionStore()

    await sesion.restaurar()

    expect(sesion.autenticado).toBe(false)
    expect(sesion.perfil).toBeNull()
    expect(peticiones).toHaveLength(0)
  })

  it('inicia sesion con credenciales validas y pide el perfil', async () => {
    sdk.signInWithPassword.mockResolvedValue({
      data: { session: sesionSupabase(), user: null },
      error: null,
    })
    const sesion = useSesionStore()

    const resultado = await sesion.iniciarSesion('ana@ejemplo.com', 'la-clave')

    expect(resultado.ok).toBe(true)
    expect(sesion.autenticado).toBe(true)
    expect(sesion.perfil?.rol).toBe('analista')
    expect(sdk.signInWithPassword).toHaveBeenCalledWith({
      email: 'ana@ejemplo.com',
      password: 'la-clave',
    })
  })

  it('el mismo mensaje para contrasena incorrecta y para correo inexistente', async () => {
    sdk.signInWithPassword.mockResolvedValue({
      data: { session: null, user: null },
      error: { message: 'Invalid login credentials' },
    })
    const sesion = useSesionStore()

    const conClaveMala = await sesion.iniciarSesion('ana@ejemplo.com', 'mala')
    const conCorreoInexistente = await sesion.iniciarSesion('nadie@ejemplo.com', 'mala')

    expect(conClaveMala.ok).toBe(false)
    expect(conCorreoInexistente.ok).toBe(false)
    expect(conClaveMala.ok === false && conClaveMala.mensaje).toBe(
      'Correo o contrasena incorrectos',
    )
    expect(conCorreoInexistente.ok === false && conCorreoInexistente.mensaje).toBe(
      'Correo o contrasena incorrectos',
    )
  })

  it('el backend nunca recibe la contrasena', async () => {
    sdk.signInWithPassword.mockResolvedValue({
      data: { session: sesionSupabase(), user: null },
      error: null,
    })
    const sesion = useSesionStore()

    await sesion.iniciarSesion('ana@ejemplo.com', 'la-clave')

    const cuerpos = peticiones.map((peticion) => peticion.text())
    expect(cuerpos.join(' ')).not.toContain('la-clave')
  })

  it('el cierre de sesion invalida en el SDK antes de revocar en el backend', async () => {
    sdk.signInWithPassword.mockResolvedValue({
      data: { session: sesionSupabase(), user: null },
      error: null,
    })
    const sesion = useSesionStore()
    await sesion.iniciarSesion('ana@ejemplo.com', 'la-clave')
    orden = []

    await sesion.cerrarSesion()

    expect(orden).toEqual(['sdk:signOut', 'http:logout'])
    expect(sesion.autenticado).toBe(false)
    expect(sesion.perfil).toBeNull()
  })

  it('el cierre de sesion revoca con el token capturado antes del signOut', async () => {
    sdk.signInWithPassword.mockResolvedValue({
      data: { session: sesionSupabase('token-capturado'), user: null },
      error: null,
    })
    const sesion = useSesionStore()
    await sesion.iniciarSesion('ana@ejemplo.com', 'la-clave')

    await sesion.cerrarSesion()

    const peticionLogout = peticiones.find((peticion) => peticion.method === 'POST')
    expect(peticionLogout?.headers.get('Authorization')).toBe('Bearer token-capturado')
  })

  it('el cambio de credencial es obligatorio cuando el backend lo pide', async () => {
    sdk.getSession.mockImplementation(async () => ({
      data: { session: sesionSupabase() },
      error: null,
    }))
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => respuesta(envelopePerfil(true))),
    )
    const sesion = useSesionStore()

    await sesion.restaurar()

    expect(sesion.debeCambiarContrasena).toBe(true)
  })

  it('cambiar la contrasena la cambia en el SDK y la confirma al backend', async () => {
    sdk.getSession.mockImplementation(async () => ({
      data: { session: sesionSupabase() },
      error: null,
    }))
    vi.stubGlobal(
      'fetch',
      vi.fn(async (peticion: Request) => {
        peticiones.push(peticion)
        if (peticion.method === 'POST') {
          orden.push('http:cambiar-contrasena')
          return respuesta({
            success: true,
            message: 'Credencial confirmada',
            data: { usuario_id: 'usuario-1', confirmado: true },
            errors: null,
            timestamp: '2026-11-27T12:00:00Z',
          })
        }
        return respuesta(envelopePerfil(true))
      }),
    )
    const sesion = useSesionStore()
    await sesion.restaurar()

    const resultado = await sesion.cambiarContrasena('la-clave-nueva')

    expect(resultado.ok).toBe(true)
    expect(sdk.updateUser).toHaveBeenCalledWith({ password: 'la-clave-nueva' })
    expect(orden).toContain('http:cambiar-contrasena')
    expect(sesion.debeCambiarContrasena).toBe(false)
  })

  it('no escribe en la tabla de perfiles desde el navegador', async () => {
    /*
     * El frontend no toca `perfiles`: la confirma al backend.
     *
     * Escribir en la tabla de permisos desde el navegador es abrir la puerta a
     * que alguien se cambie su propio rol: el backend es quien decide.
     */
    const sesion = useSesionStore()
    await sesion.restaurar()

    await sesion.cambiarContrasena('la-clave-nueva')

    expect(sdk.from).not.toHaveBeenCalled()
  })
})
