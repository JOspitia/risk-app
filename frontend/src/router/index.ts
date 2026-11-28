import { createRouter, createWebHistory } from 'vue-router'

/*
 * Enrutado.
 *
 * Las guardas de permiso se resuelven contra los permisos efectivos que
 * entrega `GET /api/v1/auth/me`. El router **no** es la autoridad: oculta
 * botones y rutas, pero el permiso se comprueba en el caso de uso del backend
 * (regla 2.2 de AGENTS.md). Un permiso ausente en el backend se deniega, aunque
 * la ruta exista en el frontend.
 */

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'inicio',
      component: () => import('@/views/InicioView.vue'),
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { publico: true },
    },
    {
      path: '/documentos',
      name: 'documentos',
      component: () => import('@/views/DocumentosView.vue'),
    },
    {
      path: '/documentos/:id',
      name: 'documento-detalle',
      component: () => import('@/views/DocumentoDetalleView.vue'),
    },
    {
      path: '/motor',
      name: 'motor-config',
      component: () => import('@/views/MotorConfigView.vue'),
    },
  ],
})

export { router }
