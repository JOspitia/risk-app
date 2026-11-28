import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import { router } from './router'
import './styles.css'

const app = createApp(App)

// Pinia antes que el router: el router usa guardas que leen el store de sesion.
app.use(createPinia())
app.use(router)

app.mount('#app')
