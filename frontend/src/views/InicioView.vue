<script setup lang="ts">
import { useRouter } from 'vue-router'

import { useSesionStore } from '@/stores/sesion'

const sesion = useSesionStore()
const router = useRouter()

async function salir(): Promise<void> {
  await sesion.cerrarSesion()
  await router.push({ name: 'login' })
}
</script>

<template>
  <main class="p-8">
    <h1 class="text-2xl font-semibold">
      Risk-app
    </h1>
    <p class="mt-2 text-gray-600">
      Analisis privado de documentos.
    </p>

    <section
      v-if="sesion.perfil"
      class="mt-6 space-y-1"
    >
      <h2 class="text-lg font-medium">
        {{ sesion.perfil.display_name ?? sesion.perfil.nombres }}
      </h2>
      <p class="text-sm text-gray-600">
        Rol: {{ sesion.perfil.rol }}
      </p>
    </section>

    <button
      id="salir"
      class="mt-6 rounded border border-gray-300 px-3 py-2 text-sm"
      type="button"
      :disabled="sesion.cargando"
      @click="salir"
    >
      Salir
    </button>
  </main>
</template>
