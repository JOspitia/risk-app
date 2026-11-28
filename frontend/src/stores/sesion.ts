import type { AuthSession } from '@supabase/supabase-js'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { cliente, errorDeLaRespuesta, fijarToken } from '@/api/cliente'
import { supabase } from '@/api/supabase'
import type { components } from '@/api/types'

export type Perfil = components['schemas']['PerfilResource']

/**
 * El mensaje de credenciales invalidas.
 *
 * Es **el mismo** para un correo inexistente y para una contrasena incorrecta
 * (HU-01 SP-01 y CA-02): no se le dice a la persona si su correo existe.
 */
export const MENSAJE_CREDENCIALES_INVALIDAS = 'Correo o contrasena incorrectos'

export type ResultadoInicioSesion = { ok: true } | { ok: false; mensaje: string }

export type ResultadoCambioContrasena =
  | { ok: true; aviso: string | null }
  | { ok: false; mensaje: string }

export const useSesionStore = defineStore('sesion', () => {
  const sesion = ref<AuthSession | null>(null)
  const perfil = ref<Perfil | null>(null)
  /** La sesion del almacenador ya se leyo: el guard puede decidir. */
  const restaurada = ref(false)
  const cargando = ref(false)

  const autenticado = computed(() => sesion.value !== null)
  const debeCambiarContrasena = computed(
    () => perfil.value?.debe_cambiar_contrasena === true,
  )

  let promesaRestauracion: Promise<void> | null = null
  let promesaPerfil: Promise<void> | null = null
  let escuchando = false

  function aplicarSesion(nueva: AuthSession | null): void {
    sesion.value = nueva
    fijarToken(nueva?.access_token ?? null)
  }

  /** Deja la sesion limpia: sin token, sin perfil. */
  function limpiar(): void {
    sesion.value = null
    perfil.value = null
    fijarToken(null)
  }

  async function cargarPerfil(): Promise<Perfil | null> {
    if (promesaPerfil === null) {
      promesaPerfil = (async () => {
        const resultado = await cliente.GET('/api/v1/auth/me')
        if (!resultado.response.ok) {
          throw errorDeLaRespuesta(resultado.error, resultado.response.status)
        }
        perfil.value = resultado.data?.data ?? null
      })()
    }
    try {
      await promesaPerfil
    } finally {
      promesaPerfil = null
    }
    return perfil.value
  }

  /**
   * Se queda al dia con los cambios de estado de autenticacion de Supabase:
   * token renovado, sesion cerrada en otra pestana, credencial actualizada.
   */
  function escuchar(): void {
    if (escuchando) {
      return
    }
    escuchando = true
    supabase.auth.onAuthStateChange((evento, nueva) => {
      if (evento === 'SIGNED_OUT') {
        limpiar()
        return
      }
      if (nueva !== null) {
        aplicarSesion(nueva)
        if (perfil.value === null) {
          // La sesion puede venir de otra pestana: el perfil se pide entonces.
          void cargarPerfil().catch(() => {
            // El perfil se vuelve a pedir en la siguiente navegacion.
          })
        }
      }
    })
  }

  /**
   * Restaura la sesion al recargar la pagina.
   *
   * `supabase.auth.getSession()` la lee del almacenador del navegador: es el
   * SDK quien la persiste, no la aplicacion. Es idempotente: llamarla dos
   * veces no vuelve a leer el almacenador.
   */
  async function restaurar(): Promise<void> {
    if (restaurada.value) {
      return
    }
    if (promesaRestauracion !== null) {
      await promesaRestauracion
      return
    }
    promesaRestauracion = (async () => {
      try {
        const { data } = await supabase.auth.getSession()
        if (data.session !== null) {
          aplicarSesion(data.session)
          try {
            await cargarPerfil()
          } catch {
            // El perfil se vuelve a pedir. Si el 401 es la causa, el cliente
            // HTTP limpia la sesion y vuelve al acceso.
          }
        }
      } catch {
        // No se pudo leer la sesion: se sigue sin sesion y la pantalla de
        // acceso es la respuesta.
      } finally {
        restaurada.value = true
        escuchar()
      }
    })()
    try {
      await promesaRestauracion
    } finally {
      promesaRestauracion = null
    }
  }

  /**
   * Inicia sesion con correo y contrasena.
   *
   * El login lo hace el SDK de Supabase, no el backend: el backend no emite
   * tokens (HU-01 CA-03). Despues se pide el perfil a `GET /api/v1/auth/me`.
   */
  async function iniciarSesion(
    correo: string,
    contrasena: string,
  ): Promise<ResultadoInicioSesion> {
    cargando.value = true
    try {
      const { data, error } = await supabase.auth.signInWithPassword({
        email: correo,
        password: contrasena,
      })
      if (error !== null || data.session === null) {
        return { ok: false, mensaje: MENSAJE_CREDENCIALES_INVALIDAS }
      }
      aplicarSesion(data.session)
      try {
        await cargarPerfil()
      } catch {
        // La sesion esta viva aunque el perfil no haya cargado.
      }
      return { ok: true }
    } finally {
      cargando.value = false
    }
  }

  /**
   * Cierra la sesion.
   *
   * El orden lo fija HU-01 7.4: primero `signOut()` del SDK, que invalida el
   * refresh token en Supabase, y despues `POST /api/v1/auth/logout`, que
   * revoca el `session_id` en el backend. Por eso el token se **captura
   * antes** del `signOut()`: despues, el backend ya no podria resolverlo.
   */
  async function cerrarSesion(): Promise<void> {
    const token = sesion.value?.access_token ?? null

    try {
      await supabase.auth.signOut()
    } catch {
      // Si el SDK falla, el backend revoca igual.
    }

    if (token !== null) {
      try {
        await revocarEnElBackend(token)
      } catch {
        // La sesion local ya se cerro; el token caduca solo.
      }
    }

    limpiar()
  }

  async function revocarEnElBackend(token: string): Promise<void> {
    // Se vuelve a poner el token capturado: el `signOut()` ya lo borro del
    // almacenador, y el backend lo necesita para revocar la sesion.
    fijarToken(token)
    try {
      const resultado = await cliente.POST('/api/v1/auth/logout')
      if (!resultado.response.ok) {
        throw errorDeLaRespuesta(resultado.error, resultado.response.status)
      }
    } finally {
      fijarToken(null)
    }
  }

  /**
   * Cambia la credencial de la persona.
   *
   * La credencial vive en Supabase Auth (fuera del alcance del proyecto): el
   * cambio se pide al SDK con `updateUser`. La bandera
   * `perfiles.debe_cambiar_contrasena` se limpia en la fila del propio perfil,
   * que es lo que la politica de actualizacion de `perfiles` permite.
   *
   * El endpoint propio `POST /api/v1/auth/cambiar-contrasena` que aparece en
   * `docs/ARQUITECTURA.md` todavia no existe en el backend: cuando exista,
   * este es el unico punto que hay que cambiar.
   */
  async function cambiarContrasena(
    nueva: string,
  ): Promise<ResultadoCambioContrasena> {
    const { error } = await supabase.auth.updateUser({ password: nueva })
    if (error !== null) {
      return {
        ok: false,
        mensaje: error.message || 'No se pudo cambiar la contrasena',
      }
    }

    const usuarioId = sesion.value?.user?.id ?? null
    let aviso: string | null = null
    if (usuarioId !== null) {
      const resultado = await supabase
        .from('perfiles')
        .update({ debe_cambiar_contrasena: false })
        .eq('id', usuarioId)
      if (resultado.error !== null) {
        aviso =
          'La contrasena se cambio, pero el servidor no pudo confirmar el cambio. Se volvera a pedir en el proximo inicio de sesion.'
      }
    }

    if (perfil.value !== null) {
      perfil.value = { ...perfil.value, debe_cambiar_contrasena: false }
    }

    return { ok: true, aviso }
  }

  return {
    sesion,
    perfil,
    restaurada,
    cargando,
    autenticado,
    debeCambiarContrasena,
    restaurar,
    cargarPerfil,
    iniciarSesion,
    cerrarSesion,
    cambiarContrasena,
    limpiar,
  }
})
