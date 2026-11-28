import { createClient } from '@supabase/supabase-js'

/**
 * Cliente de Supabase.
 *
 * Es el unico punto donde la aplicacion habla con Supabase Auth. El backend
 * **no emite tokens** (HU-01 CA-03): el SDK los emite, los guarda en el
 * navegador y el frontend los manda en cada peticion.
 *
 * La llave es la **publicable** (`VITE_SUPABASE_PUBLISHABLE_KEY`). La llave de
 * servicio nunca llega al navegador: salta el RLS y en el navegador es publica.
 */
declare global {
  interface ImportMetaEnv {
    /**
     * Llave publicable del proyecto de Supabase.
     *
     * `frontend/env.d.ts` todavia declara la variante `VITE_SUPABASE_ANON_KEY`,
     * que ya no existe en el `.env`. La declaracion vive aqui hasta que el
     * archivo de entorno la recoja.
     */
    readonly VITE_SUPABASE_PUBLISHABLE_KEY: string
  }
}

export const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY,
  {
    auth: {
      // El SDK guarda la sesion en el almacenador del navegador: eso es lo que
      // la restaura al recargar (HU-01 7.1). No hace falta ningun plugin de
      // persistencia propio.
      persistSession: true,
      autoRefreshToken: true,
      // La aplicacion no usa el retorno de OAuth: la sesion se emite con
      // correo y contrasena.
      detectSessionInUrl: false,
    },
  },
)
