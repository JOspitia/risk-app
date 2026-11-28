import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const tienda = vi.hoisted(() => ({
  cargando: false,
  iniciarSesion: vi.fn(),
}))

vi.mock('@/stores/sesion', () => ({
  useSesionStore: () => tienda,
  MENSAJE_CREDENCIALES_INVALIDAS: 'Correo o contrasena incorrectos',
}))

import LoginView from '@/views/LoginView.vue'

async function montarLogin() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'inicio', component: { template: '<p>inicio</p>' } },
      { path: '/login', name: 'login', component: LoginView },
    ],
  })
  await router.push('/login')
  await router.isReady()
  const wrapper = mount(LoginView, { global: { plugins: [router] } })
  return { wrapper, router }
}

describe('LoginView', () => {
  beforeEach(() => {
    tienda.cargando = false
    tienda.iniciarSesion.mockReset()
  })

  it('pide correo y contrasena', async () => {
    const { wrapper } = await montarLogin()

    expect(wrapper.find('#correo').exists()).toBe(true)
    expect(wrapper.find('#contrasena').exists()).toBe(true)
    expect(wrapper.find('input[type="password"]').exists()).toBe(true)
  })

  it('muestra el mensaje exacto con credenciales invalidas', async () => {
    tienda.iniciarSesion.mockResolvedValue({
      ok: false,
      mensaje: 'Correo o contrasena incorrectos',
    })
    const { wrapper } = await montarLogin()

    await wrapper.find('#correo').setValue('ana@ejemplo.com')
    await wrapper.find('#contrasena').setValue('mala')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('Correo o contrasena incorrectos')
  })

  it('el mensaje es el mismo con un correo inexistente', async () => {
    tienda.iniciarSesion.mockResolvedValue({
      ok: false,
      mensaje: 'Correo o contrasena incorrectos',
    })
    const { wrapper } = await montarLogin()

    await wrapper.find('#correo').setValue('nadie@ejemplo.com')
    await wrapper.find('#contrasena').setValue('mala')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('Correo o contrasena incorrectos')
  })

  it('navega a la pantalla principal cuando el acceso es correcto', async () => {
    tienda.iniciarSesion.mockResolvedValue({ ok: true })
    const { wrapper, router } = await montarLogin()

    await wrapper.find('#correo').setValue('ana@ejemplo.com')
    await wrapper.find('#contrasena').setValue('la-clave')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(tienda.iniciarSesion).toHaveBeenCalledWith('ana@ejemplo.com', 'la-clave')
    expect(router.currentRoute.value.name).toBe('inicio')
  })
})
