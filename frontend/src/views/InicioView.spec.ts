import { describe, expect, it } from 'vitest'

import { mount } from '@vue/test-utils'

import InicioView from '@/views/InicioView.vue'

describe('InicioView', () => {
  it('se monta y muestra el titulo', () => {
    const wrapper = mount(InicioView)

    expect(wrapper.text()).toContain('Risk-app')
  })
})
