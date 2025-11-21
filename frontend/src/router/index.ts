import { createRouter, createWebHistory } from 'vue-router';
import DashboardView from '../views/DashboardView.vue';
import DataCollectionView from '../views/DataCollectionView.vue';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'dashboard',
      component: DashboardView
    },
    {
      path: '/collect',
      name: 'collect',
      component: DataCollectionView
    }
  ]
});

export default router;
