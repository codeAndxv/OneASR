import { createRouter, createWebHistory } from 'vue-router'
import Layout from '../views/Layout.vue'

const routes = [
  {
    path: '/',
    component: Layout,
    children: [
      {
        path: '',
        name: 'Transcribe',
        component: () => import('../views/Transcribe.vue'),
      },
      {
        path: 'files',
        name: 'FileUpload',
        component: () => import('../views/FileUpload.vue'),
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
