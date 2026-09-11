import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

export const ROLES = {
  OPERATOR: 'operator',
  EMPLOYEE: 'employee',
};

export const ROLE_PROFILES = {
  [ROLES.OPERATOR]: {
    role: ROLES.OPERATOR,
    name: 'S. K. Raman',
    shortName: 'OP',
    title: 'Chief Block Controller',
    badge: 'CONTROL CENTER',
    department: 'Operating / Section Controller',
    station: 'MAS Divisional Control',
    canMutate: true,
    description: 'Full operational privileges: block creation, approval, CP-SAT optimization & freight forecasting.',
  },
  [ROLES.EMPLOYEE]: {
    role: ROLES.EMPLOYEE,
    name: 'M. Arvind',
    shortName: 'EM',
    title: 'Operations Monitor / Field Observer',
    badge: 'MONITORING ONLY',
    department: 'Engineering / Station Traffic',
    station: 'Arakkonam Junction',
    canMutate: false,
    description: 'Read-only situational awareness: live possession schedules, traffic, maintenance and plan status.',
  },
};

const STORAGE_KEY = 'railway_planner_role';

/**
 * Direct accessor for current role, usable in non-React modules like api.js.
 */
export function getActiveRole() {
  if (typeof window === 'undefined') return ROLES.OPERATOR;
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === ROLES.EMPLOYEE) return ROLES.EMPLOYEE;
  return ROLES.OPERATOR;
}

export const AuthContext = createContext({
  role: ROLES.OPERATOR,
  profile: ROLE_PROFILES[ROLES.OPERATOR],
  isOperator: true,
  isEmployee: false,
  setRole: () => {},
  switchRole: () => {},
});

export function AuthProvider({ children }) {
  const [role, setRoleState] = useState(() => getActiveRole());

  const setRole = useCallback((newRole) => {
    const validatedRole = newRole === ROLES.EMPLOYEE ? ROLES.EMPLOYEE : ROLES.OPERATOR;
    setRoleState(validatedRole);
    try {
      localStorage.setItem(STORAGE_KEY, validatedRole);
    } catch {
      // Storage unavailable or quota exceeded
    }
  }, []);

  const switchRole = useCallback(() => {
    setRole(role === ROLES.OPERATOR ? ROLES.EMPLOYEE : ROLES.OPERATOR);
  }, [role, setRole]);

  // Keep localStorage in sync if changed across tabs
  useEffect(() => {
    const handleStorage = (e) => {
      if (e.key === STORAGE_KEY && e.newValue) {
        if (e.newValue === ROLES.OPERATOR || e.newValue === ROLES.EMPLOYEE) {
          setRoleState(e.newValue);
        }
      }
    };
    window.addEventListener('storage', handleStorage);
    return () => window.removeEventListener('storage', handleStorage);
  }, []);

  const profile = ROLE_PROFILES[role] || ROLE_PROFILES[ROLES.OPERATOR];
  const isOperator = role === ROLES.OPERATOR;
  const isEmployee = role === ROLES.EMPLOYEE;

  return (
    <AuthContext.Provider
      value={{
        role,
        profile,
        isOperator,
        isEmployee,
        setRole,
        switchRole,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
