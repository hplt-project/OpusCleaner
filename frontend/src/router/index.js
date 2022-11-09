import { createRouter, createWebHashHistory } from 'vue-router'

const router = createRouter({
  history: createWebHashHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'list-datasets',
      component: () => import('../views/ListDatasetsView.vue')
    },
    {
      path: '/datasets/:datasetName/configuration',
      name: 'edit-filters',
      component: () => import('../views/EditFiltersView.vue')
    },
    {
      path: '/download/',
      name: 'add-dataset',
      component: () => import('../views/AddDatasetView.vue')
    },
  ]
})

export default router
