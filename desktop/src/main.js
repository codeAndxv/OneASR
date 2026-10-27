import { createApp } from 'vue';
import App from './App.vue';
import { initTheme } from './utils/theme';

initTheme();

const app = createApp(App);
app.mount('#app');
