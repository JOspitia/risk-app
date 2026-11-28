import { createMemoryHistory } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  manejador: null as (() => void | Promise<void>) | null,
}))

vi.mock('@/api/cliente', () => ({
  registrarManejadorNoAutenticado: (manejador: () => void | Promise<void>) => {
    mocks.manejador = manejador
  },
}))

const tienda = vi.hoisted(() => ({
  restaurada: true,
  autenticado: false,
  debeCambiarContrasena: false,
  restaurar: vi.fn(async () => {}),
  limpiar: vi.fn(),
}))

vi.mock('@/stores/sesion', () => ({
  useSesionStore: () => tienda,
}))

import { crearRouter } from '@/router'

describe('guard de navegacion', () => {
  beforeEach(() => {
    tienda.restaurada = true
    tienda.autenticado = false
    tienda.debeCambiarContrasena = false
    tienda.restaurar.mockClear()
    tienda.limpiar.mockClear()
  })

  it('deja pasar una ruta publica sin sesion', async () => {
    const router = crearRouter(createMemoryHistory())

    await router.push('/login')

    expect(router.currentRoute.value.name).toBe('login')
  })

  it('manda a iniciar sesion cuando no hay sesion', async () => {
    const router = crearRouter(createMemoryHistory())

    await router.push('/documentos')

    expect(router.currentRoute.value.name).toBe('login')
  })

  it('deja pasar una ruta protegida con sesion', async () => {
    tienda.autenticado = true
    const router = crearRouter(createMemoryHistory())

    await router.push('/documentos')

    expect(router.currentRoute.value.name).toBe('documentos')
  })

  it('manda al cambio de credencial cuando el backend lo pide', async () => {
    tienda.autenticado = true
    tienda.debeCambiarContrasena = true
    const router = crearRouter(createMemoryHistory())

    await router.push('/documentos')

    expect(router.currentRoute.value.name).toBe('cambiar-contrasena')
  })

  it('el cambio de credencial no se redirige a si mismo', async () => {
    tienda.autenticado = true
    tienda.debeCambiarContrasena = true
    const router = crearRouter(createMemoryHistory())

    await router.push('/cambiar-contrasena')

    expect(router.currentRoute.value.name).toBe('cambiar-contrasena')
  })

  it('restaura la sesion antes de decidir', async () => {
    tienda.restaurada = false
    tienda.autenticado = true
    const router = crearRouter(createMemoryHistory())

    await router.push('/documentos')

    expect(tienda.restaurar).toHaveBeenCalled()
    expect(router.currentRoute.value.name).toBe('documentos')
  })

  it('el cambio de credencial exige sesion', async () => {
    const router = crearRouter(createMemoryHistory())

    await router.push('/cambiar-contrasena')

    expect(router.currentRoute.value.name).toBe('login')
  })

  it('un 401 limpia la sesion y vuelve a la pantalla de acceso', async () => {
    tienda.autenticado = true
    const router = crearRouter(createMemoryHistory())
    await router.push('/documentos')

    await mocks.manejador?.()

    expect(tienda.limpiar).toHaveBeenCalled()
    expect(router.currentRoute.value.name).toBe('login')
  })
})
