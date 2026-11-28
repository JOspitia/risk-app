import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'

import { describe, expect, it } from 'vitest'

import { supabase } from '@/api/supabase'

/**
 * El patron de la llave de servicio se arma por partes a proposito: si el
 * patron apareciera escrito tal cual en este archivo, el mismo escaner lo
 * encontraria en si mismo y la prueba no significaria nada.
 */
const PATRON_LLAVE_DE_SERVICIO = new RegExp(['service', 'role'].join('[_-]?'), 'i')

function archivosDe(directorio: string): string[] {
  const encontrados: string[] = []
  for (const entrada of readdirSync(directorio)) {
    const ruta = join(directorio, entrada)
    if (statSync(ruta).isDirectory()) {
      encontrados.push(...archivosDe(ruta))
      continue
    }
    // Las pruebas no llegan al bundle: no tienen por que pasar por aqui.
    if (ruta.endsWith('.spec.ts') || ruta.endsWith('.test.ts')) {
      continue
    }
    if (ruta.endsWith('.ts') || ruta.endsWith('.vue')) {
      encontrados.push(ruta)
    }
  }
  return encontrados
}

describe('cliente de Supabase', () => {
  it('se crea con la URL del proyecto y la llave publicable', () => {
    expect(supabase).toBeTruthy()
    expect(import.meta.env.VITE_SUPABASE_URL).toMatch(/^https?:\/\//)
    expect(import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY).toBeTruthy()
  })

  it('no usa la llave de servicio', () => {
    expect(import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY).not.toMatch(
      PATRON_LLAVE_DE_SERVICIO,
    )
  })

  it('no hay ninguna llave de servicio en el codigo del navegador', () => {
    // La llave de servicio salta el RLS: en el navegador es publica. Si alguna
    // vez se colara en el bundle, esta prueba lo detecta antes del despliegue.
    // La raiz del frontend es el directorio donde se corre la suite.
    const raiz = join(process.cwd(), 'src')
    const ofensores = archivosDe(raiz)
      .filter((ruta) => PATRON_LLAVE_DE_SERVICIO.test(readFileSync(ruta, 'utf8')))
      .map((ruta) => ruta.slice(raiz.length))

    expect(ofensores).toEqual([])
  })
})
