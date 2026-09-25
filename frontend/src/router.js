/**
 * Lightweight client-side router and URL utilities for Railway Block Planner.
 * Supports both standard HTML5 pathname routing and hash fallback.
 */

import { ROLES } from './auth/AuthContext';

export const OPERATOR_ROUTES = {
  DASHBOARD: '/operator/dashboard',
  SCHEDULE: '/operator/schedule',
  BLOCKS: '/operator/blocks',
  MAINTENANCE: '/operator/maintenance',
  TRAINS: '/operator/trains',
  FORECAST: '/operator/forecast',
  OPTIMIZATION: '/operator/optimization',
  CONFLICTS: '/operator/conflicts',
};

export const EMPLOYEE_ROUTES = {
  DASHBOARD: '/employee/dashboard',
  SCHEDULE: '/employee/schedule',
  BLOCKS: '/employee/blocks',
  MAINTENANCE: '/employee/maintenance',
  TRAINS: '/employee/trains',
  FORECAST: '/employee/forecast',
  PLAN_STATUS: '/employee/plan-status',
  CONFLICTS: '/employee/conflicts',
};

/**
 * Normalize and parse current path from window.location.
 */
export function getCurrentPath() {
  if (typeof window === 'undefined') return OPERATOR_ROUTES.DASHBOARD;
  
  // Check hash first if present (e.g. #/employee/schedule)
  if (window.location.hash && window.location.hash.startsWith('#/')) {
    return window.location.hash.slice(1);
  }
  
  const pathname = window.location.pathname || '/';
  return pathname;
}

/**
 * Navigate to a new path cleanly using pushState and custom route change event.
 */
export function navigateTo(path) {
  if (typeof window === 'undefined') return;
  if (path === getCurrentPath()) return;

  window.history.pushState({}, '', path);
  window.dispatchEvent(new CustomEvent('app:navigate', { detail: { path } }));
}

/**
 * Match current path to view key and role.
 */
export function resolveRoute(path, activeRole) {
  const cleanPath = (path || '').toLowerCase().replace(/\/+$/, '');

  // Operator paths
  if (cleanPath.startsWith('/operator')) {
    if (cleanPath.includes('/schedule')) return { role: ROLES.OPERATOR, page: 'schedule', path: OPERATOR_ROUTES.SCHEDULE };
    if (cleanPath.includes('/blocks')) return { role: ROLES.OPERATOR, page: 'blocks', path: OPERATOR_ROUTES.BLOCKS };
    if (cleanPath.includes('/maintenance')) return { role: ROLES.OPERATOR, page: 'maintenance', path: OPERATOR_ROUTES.MAINTENANCE };
    if (cleanPath.includes('/trains')) return { role: ROLES.OPERATOR, page: 'trains', path: OPERATOR_ROUTES.TRAINS };
    if (cleanPath.includes('/forecast')) return { role: ROLES.OPERATOR, page: 'forecast', path: OPERATOR_ROUTES.FORECAST };
    if (cleanPath.includes('/optimization')) return { role: ROLES.OPERATOR, page: 'optimization', path: OPERATOR_ROUTES.OPTIMIZATION };
    if (cleanPath.includes('/conflicts')) return { role: ROLES.OPERATOR, page: 'conflicts', path: OPERATOR_ROUTES.CONFLICTS };
    return { role: ROLES.OPERATOR, page: 'dashboard', path: OPERATOR_ROUTES.DASHBOARD };
  }

  // Employee paths
  if (cleanPath.startsWith('/employee')) {
    if (cleanPath.includes('/schedule')) return { role: ROLES.EMPLOYEE, page: 'schedule', path: EMPLOYEE_ROUTES.SCHEDULE };
    if (cleanPath.includes('/blocks')) return { role: ROLES.EMPLOYEE, page: 'blocks', path: EMPLOYEE_ROUTES.BLOCKS };
    if (cleanPath.includes('/maintenance')) return { role: ROLES.EMPLOYEE, page: 'maintenance', path: EMPLOYEE_ROUTES.MAINTENANCE };
    if (cleanPath.includes('/trains')) return { role: ROLES.EMPLOYEE, page: 'trains', path: EMPLOYEE_ROUTES.TRAINS };
    if (cleanPath.includes('/forecast')) return { role: ROLES.EMPLOYEE, page: 'forecast', path: EMPLOYEE_ROUTES.FORECAST };
    if (cleanPath.includes('/plan-status')) return { role: ROLES.EMPLOYEE, page: 'plan-status', path: EMPLOYEE_ROUTES.PLAN_STATUS };
    if (cleanPath.includes('/conflicts')) return { role: ROLES.EMPLOYEE, page: 'conflicts', path: EMPLOYEE_ROUTES.CONFLICTS };
    return { role: ROLES.EMPLOYEE, page: 'dashboard', path: EMPLOYEE_ROUTES.DASHBOARD };
  }

  // Default fallback according to active role
  if (activeRole === ROLES.EMPLOYEE) {
    return { role: ROLES.EMPLOYEE, page: 'dashboard', path: EMPLOYEE_ROUTES.DASHBOARD };
  }
  return { role: ROLES.OPERATOR, page: 'dashboard', path: OPERATOR_ROUTES.DASHBOARD };
}
