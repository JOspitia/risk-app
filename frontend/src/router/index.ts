import {
  createRouter,
  createWebHistory,
} from 'vue-router'
import type {
  RouteLocationNormalized,
  RouteLocationRaw,
  Router,
  RouterHistory,
} from 'vue-router'

import { registrarManejadorNoAutenticado } from '@/api/cliente'
import { useSesionStore } from '@/stores/sesion'

/*
 * Enrutado.
 *
 * Las guardas de permiso se resuelven contra los permisos efectivos que
 * entrega `GET /api/v1/auth/me`. El router **no** es la autoridad: oculta
 * botones y rutas, pero el permiso se comprueba en el caso de uso del backend
 * (regla 2.2 de AGENTS.md). Un permiso ausente en el backend se deniega, aunque
 * la ruta exista en el frontend.
 */

declare module 'vue-router' {
  interface RouteMeta {
    /** La ruta se puede abrir sin sesion. */
    publico?: boolean
  }
}

/**
 * Guard de navegacion.
 *
 * El orden es el de HU-01: primero las rutas publicas, despues la sesion, y
 * al final el cambio de credencial obligatorio (CA-12). Sin bucles: la pantalla
 * de cambio de credencial no se redirige a si misma.
 */
export async function guardDeSesion(
  to: RouteLocationNormalized,
): Promise<true | RouteLocationRaw> {
  const sesion = useSesionStore()

  // La sesion se restaura antes de decidir. Al recargar, el store todavia no
  // sabe si hay sesion: sin esto, el guard mandaria al acceso a alguien que
  // si la tiene.
  if (!sesion.restaurada) {
    await sesion.restaurar()
  }

  if (to.meta.publico === true) {
    return true
  }

  if (!sesion.autenticado) {
    return { name: 'login', query: { redireccion: to.fullPath } }
  }

  if (sesion.debeCambiarContrasena && to.name !== 'cambiar-contrasena') {
    return { name: 'cambiar-contrasena' }
  }

  return true
}

export function crearRouter(
  historia: RouterHistory = createWebHistory(import.meta.env.BASE_URL),
): Router {
  const router = createRouter({
    history: historia,
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
        path: '/cambiar-contrasena',
        name: 'cambiar-contrasena',
        component: () => import('@/views/CambiarContrasenaView.vue'),
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

  router.beforeEach(guardDeSesion)

  // El backend responde 401 cuando el token ya no sirve. La sesion se limpia
  // y se vuelve a la pantalla de acceso, **una sola vez**: el cliente HTTP no
  // repite el aviso hasta que haya una sesion nueva.
  registrarManejadorNoAutenticado(async () => {
    const sesion = useSesionStore()
    sesion.limpiar()
    if (router.currentRoute.value.name !== 'login') {
      await router.push({ name: 'login' })
    }
  })

  return router
}

export const router = crearRouter()
