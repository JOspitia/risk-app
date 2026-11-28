<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useSesionStore } from '@/stores/sesion'

const sesion = useSesionStore()
const router = useRouter()
const route = useRoute()

const correo = ref('')
const contrasena = ref('')
const mensaje = ref<string | null>(null)

async function enviar(): Promise<void> {
  mensaje.value = null
  const resultado = await sesion.iniciarSesion(correo.value, contrasena.value)
  if (!resultado.ok) {
    mensaje.value = resultado.mensaje
    return
  }
  const destino = route.query['redireccion']
  await router.push(typeof destino === 'string' ? destino : '/')
}
</script>

<template>
  <main class="mx-auto max-w-sm p-8">
    <h1 class="text-2xl font-semibold">
      Iniciar sesion
    </h1>
    <p class="mt-2 text-gray-600">
      Analisis privado de documentos.
    </p>

    <form
      class="mt-6 space-y-4"
      @submit.prevent="enviar"
    >
      <div>
        <label
          class="block text-sm font-medium"
          for="correo"
        >Correo</label>
        <input
          id="correo"
          v-model="correo"
          class="mt-1 w-full rounded border border-gray-300 px-3 py-2"
          type="email"
          name="correo"
          autocomplete="username"
          required
        >
      </div>

      <div>
        <label
          class="block text-sm font-medium"
          for="contrasena"
        >Contrasena</label>
        <input
          id="contrasena"
          v-model="contrasena"
          class="mt-1 w-full rounded border border-gray-300 px-3 py-2"
          type="password"
          name="contrasena"
          autocomplete="current-password"
          required
        >
      </div>

      <p
        v-if="mensaje"
        class="text-sm text-red-600"
        role="alert"
      >
        {{ mensaje }}
      </p>

      <button
        id="entrar"
        class="w-full rounded bg-gray-900 px-3 py-2 text-white disabled:opacity-60"
        type="submit"
        :disabled="sesion.cargando"
      >
        {{ sesion.cargando ? 'Entrando...' : 'Entrar' }}
      </button>
    </form>
  </main>
</template>
