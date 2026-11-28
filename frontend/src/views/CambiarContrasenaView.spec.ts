import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const tienda = vi.hoisted(() => ({
  cargando: false,
  cambiarContrasena: vi.fn(),
}))

vi.mock('@/stores/sesion', () => ({
  useSesionStore: () => tienda,
}))

import CambiarContrasenaView from '@/views/CambiarContrasenaView.vue'

async function montarVista() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'inicio', component: { template: '<p>inicio</p>' } },
      {
        path: '/cambiar-contrasena',
        name: 'cambiar-contrasena',
        component: CambiarContrasenaView,
      },
    ],
  })
  await router.push('/cambiar-contrasena')
  await router.isReady()
  const wrapper = mount(CambiarContrasenaView, { global: { plugins: [router] } })
  return { wrapper, router }
}

describe('CambiarContrasenaView', () => {
  beforeEach(() => {
    tienda.cargando = false
    tienda.cambiarContrasena.mockReset()
  })

  it('no cambia la credencial si las dos contrasenas no coinciden', async () => {
    tienda.cambiarContrasena.mockResolvedValue({ ok: true, aviso: null })
    const { wrapper } = await montarVista()

    await wrapper.find('#nueva').setValue('la-clave-nueva')
    await wrapper.find('#repeticion').setValue('otra-clave')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(tienda.cambiarContrasena).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('no coinciden')
  })

  it('cambia la credencial y sigue a la pantalla principal', async () => {
    tienda.cambiarContrasena.mockResolvedValue({ ok: true, aviso: null })
    const { wrapper, router } = await montarVista()

    await wrapper.find('#nueva').setValue('la-clave-nueva')
    await wrapper.find('#repeticion').setValue('la-clave-nueva')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(tienda.cambiarContrasena).toHaveBeenCalledWith('la-clave-nueva')
    expect(router.currentRoute.value.name).toBe('inicio')
  })

  it('muestra el error cuando el servidor rechaza el cambio', async () => {
    tienda.cambiarContrasena.mockResolvedValue({
      ok: false,
      mensaje: 'La contrasena no cumple la politica del proyecto',
    })
    const { wrapper } = await montarVista()

    await wrapper.find('#nueva').setValue('la-clave-nueva')
    await wrapper.find('#repeticion').setValue('la-clave-nueva')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('La contrasena no cumple la politica del proyecto')
  })
})
