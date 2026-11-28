<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

import { useSesionStore } from '@/stores/sesion'

const sesion = useSesionStore()
const router = useRouter()

const nueva = ref('')
const repeticion = ref('')
const mensaje = ref<string | null>(null)
const aviso = ref<string | null>(null)

async function enviar(): Promise<void> {
  mensaje.value = null
  aviso.value = null

  if (nueva.value.length === 0) {
    mensaje.value = 'Escribe la contrasena nueva'
    return
  }
  if (nueva.value !== repeticion.value) {
    mensaje.value = 'Las contrasenas no coinciden'
    return
  }

  const resultado = await sesion.cambiarContrasena(nueva.value)
  if (!resultado.ok) {
    mensaje.value = resultado.mensaje
    return
  }
  if (resultado.aviso !== null) {
    aviso.value = resultado.aviso
  }
  await router.push('/')
}
</script>

<template>
  <main class="mx-auto max-w-sm p-8">
    <h1 class="text-2xl font-semibold">
      Cambiar la contrasena
    </h1>
    <p class="mt-2 text-gray-600">
      Tu credencial es temporal. Elige una contrasena nueva para seguir.
    </p>

    <form
      class="mt-6 space-y-4"
      @submit.prevent="enviar"
    >
      <div>
        <label
          class="block text-sm font-medium"
          for="nueva"
        >Contrasena nueva</label>
        <input
          id="nueva"
          v-model="nueva"
          class="mt-1 w-full rounded border border-gray-300 px-3 py-2"
          type="password"
          name="nueva"
          autocomplete="new-password"
          required
        >
      </div>

      <div>
        <label
          class="block text-sm font-medium"
          for="repeticion"
        >Repite la contrasena</label>
        <input
          id="repeticion"
          v-model="repeticion"
          class="mt-1 w-full rounded border border-gray-300 px-3 py-2"
          type="password"
          name="repeticion"
          autocomplete="new-password"
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

      <p
        v-if="aviso"
        class="text-sm text-amber-700"
        role="status"
      >
        {{ aviso }}
      </p>

      <button
        id="guardar"
        class="w-full rounded bg-gray-900 px-3 py-2 text-white disabled:opacity-60"
        type="submit"
        :disabled="sesion.cargando"
      >
        {{ sesion.cargando ? 'Guardando...' : 'Guardar la contrasena' }}
      </button>
    </form>
  </main>
</template>
