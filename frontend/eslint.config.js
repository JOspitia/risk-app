import js from '@eslint/js'
import pluginVue from 'eslint-plugin-vue'
import globals from 'globals'
import tseslint from 'typescript-eslint'

/*
 * ESLint en formato plano (el unico que acepta ESLint 10).
 *
 * Las reglas que no se listan estan apagadas a proposito: un linter que
 * aparecen errores que nadie va a arreglar es un linter que nadie corre.
 */
export default [
  {
    ignores: ['dist/**', 'node_modules/**', 'coverage/**', 'src/api/types.ts'],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  ...pluginVue.configs['flat/recommended'],
  {
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.node,
      },
    },
    rules: {
      // Vue 3 ya no necesita la regla de multi-word: el SFC da contexto.
      'vue/multi-word-component-names': 'off',
      // El template de Vue usa `any` con frecuencia: `vue-tsc` ya verifica tipos.
      '@typescript-eslint/no-explicit-any': 'warn',
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
      ],
    },
  },
]
