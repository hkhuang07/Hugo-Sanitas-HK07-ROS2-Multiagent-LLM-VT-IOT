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
      path: '/digital-twin',
      name: 'DigitalTwin',
      component: () => import('../views/DigitalTwinView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/map',
      name: 'Map',
      component: () => import('../views/MapView.vue'),
      meta: { requiresAuth: true }
    },

    {
      path: '/sensor-telemetry',
      name: 'SensorTelemetry',
      component: () => import('../views/SensorTelemetryView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/vision',
      name: 'Vision',
      component: () => import('../views/HugoVisionView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/system-observer',
      name: 'SystemObserver',
      component: () => import('../views/SystemObserverView.vue'),
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
// NOTE: We await authStore.tryAutoLogin() on the first navigation so that the guard
// never reads isAuthenticated before auto-login has settled.
// On subsequent navigations _authResolved is true, so it skips the await.
let _authResolved = false

router.beforeEach(async (to) => {
  const authStore = useAuthStore()

  // Block ONLY on first navigation — wait for refresh-token auto-login to finish
  if (!_authResolved) {
    await authStore.tryAutoLogin()
    _authResolved = true
  }

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    return { name: 'Login' }
  }
  if (!to.meta.requiresAuth && authStore.isAuthenticated && to.name === 'Login') {
    return { name: 'Dashboard' }
  }
})

