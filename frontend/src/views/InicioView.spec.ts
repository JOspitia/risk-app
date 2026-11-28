import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const tienda = vi.hoisted(() => ({
  cargando: false,
  autenticado: true,
  perfil: {
    id: '8f3c0000-0000-0000-0000-000000000000',
    nombres: 'Ana',
    apellido_1: 'Restrepo',
    apellido_2: null,
    display_name: 'Ana Restrepo Duque',
    rol: 'analista',
    organizacion_id: 'c41a0000-0000-0000-0000-000000000000',
    debe_cambiar_contrasena: false,
  },
  cerrarSesion: vi.fn(),
}))

vi.mock('@/stores/sesion', () => ({
  useSesionStore: () => tienda,
}))

import InicioView from '@/views/InicioView.vue'

async function montarInicio() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'inicio', component: InicioView },
      { path: '/login', name: 'login', component: { template: '<p>acceso</p>' } },
    ],
  })
  await router.push('/')
  await router.isReady()
  const wrapper = mount(InicioView, { global: { plugins: [router] } })
  return { wrapper, router }
}

describe('InicioView', () => {
  beforeEach(() => {
    tienda.cerrarSesion.mockReset()
    tienda.cerrarSesion.mockResolvedValue(undefined)
  })

  it('se monta y muestra el titulo', () => {
    const wrapper = mount(InicioView, {
      global: {
        plugins: [
          createRouter({
            history: createMemoryHistory(),
            routes: [{ path: '/', name: 'inicio', component: InicioView }],
          }),
        ],
      },
    })

    expect(wrapper.text()).toContain('Risk-app')
  })

  it('muestra el perfil del usuario', async () => {
    const { wrapper } = await montarInicio()

    expect(wrapper.text()).toContain('Ana Restrepo Duque')
    expect(wrapper.text()).toContain('analista')
  })

  it('cierra la sesion y vuelve a la pantalla de acceso', async () => {
    const { wrapper, router } = await montarInicio()

    await wrapper.find('#salir').trigger('click')
    await flushPromises()

    expect(tienda.cerrarSesion).toHaveBeenCalled()
    expect(router.currentRoute.value.name).toBe('login')
  })
})
