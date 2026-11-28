import { describe, expect, it } from 'vitest'

/**
 * Verifica que Vite expone las variables de entorno del frontend.
 *
 * El prefijo `VITE_` lo elige el bundler, y el fallo no aparece al arrancar: si el
 * nombre esta mal, la variable llega al navegador como `undefined` y el error sale
 * en la consola del navegador, en produccion, sin ningun aviso en la compilacion.
 *
 * Esta prueba falla en la compilacion si el `.env` esta mal, que es donde tiene que
 * fallar.
 */
describe('variables de entorno', () => {
  it('expone la URL de Supabase', () => {
    expect(import.meta.env.VITE_SUPABASE_URL).toBeTruthy()
    expect(import.meta.env.VITE_SUPABASE_URL).toMatch(/^https?:\/\//)
  })

  it('expone la publishable key de Supabase', () => {
    expect(import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY).toBeTruthy()
  })

  it('expone la URL de la API', () => {
    expect(import.meta.env.VITE_API_BASE_URL).toBeTruthy()
  })

  it('NO expone la llave de servicio', () => {
    // Si alguna vez se colara una `service_role` en el bundle del navegador, esta
    // prueba lo detecta. En el navegador es publica: salta el RLS.
    const exposed = Object.entries(import.meta.env).filter(([clave]) =>
      /service_role|secret/i.test(clave),
    )
    expect(exposed).toEqual([])
  })
})
