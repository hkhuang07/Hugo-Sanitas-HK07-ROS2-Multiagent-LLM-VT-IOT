import { createRouter, createWebHistory } from 'vue-router'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('../views/LoginView.vue'),
      meta: { requiresAuth: false }
    },
    {
      path: '/',
      name: 'Dashboard',
      component: () => import('../views/DashboardView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/agents',
      name: 'Agents',
      component: () => import('../views/AgentsView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/companion',
      name: 'Companion',
      component: () => import('../views/CompanionView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/history',
      name: 'History',
      component: () => import('../views/HealthHistoryView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/safety',
      name: 'Safety',
      component: () => import('../views/SafetyView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/emergency',
      name: 'Emergency',
      component: () => import('../views/EmergencyView.vue'),
      meta: { requiresAuth: false }
    },
    {
      path: '/profile',
      name: 'Profile',
      component: () => import('../views/ProfileSettingsView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/'
    }
  ]
})

import { useAuthStore } from '../stores/auth'

// Navigation guard
router.beforeEach((to) => {
  const authStore = useAuthStore()
  
  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    return { name: 'Login' }
  }
  if (!to.meta.requiresAuth && authStore.isAuthenticated && to.name === 'Login') {
    return { name: 'Dashboard' }
  }
})
