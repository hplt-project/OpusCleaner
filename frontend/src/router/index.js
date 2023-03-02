import { createRouter, createWebHashHistory } from 'vue-router'
import Modal from '../components/Modal.vue';

const router = createRouter({
  history: createWebHashHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'list-datasets',
      component: () => import('../views/ListDatasetsView.vue'),
      children: [
        {
          name: 'edit-filters-yaml',
          path: '/datasets/:datasetName/:format',
          component: Modal,
          props: {
            component: () => import('../views/EditFiltersYamlView.vue'),
            format: 'configuration-for-opusfilter.yaml'
          }
        }
      ]
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
