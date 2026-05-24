export const APP_NAME = 'UniOps';
export const APP_TAGLINE = 'Control Tower';
export const APP_VERSION = '1.0.0';

export const ROUTES = {
  // Landing
  HOME: '/',
  FEATURES: '/features',
  PRICING: '/pricing',
  ABOUT: '/about',
  CONTACT: '/contact',

  // Auth
  LOGIN: '/auth/login',
  REGISTER: '/auth/register',
  COMPANY_SIGNUP: '/auth/company-signup',
  FORGOT_PASSWORD: '/auth/forgot-password',
  RESET_PASSWORD: '/auth/reset-password',
  VERIFY_EMAIL: '/auth/verify-email',
  TWO_FACTOR: '/auth/2fa',

  // Dashboard
  COMMAND: '/command',
  DEVOPS: '/devops',
  SECURITY: '/security',
  COST: '/cost',
  INSIGHTS: '/insights',

  // Settings
  SETTINGS_PROFILE: '/settings/profile',
  SETTINGS_ACCOUNT: '/settings/account',
  SETTINGS_NOTIFICATIONS: '/settings/notifications',
  SETTINGS_BILLING: '/settings/billing',
  SETTINGS_API_KEYS: '/settings/api-keys',
  SETTINGS_WEBHOOKS: '/settings/webhooks',
  SETTINGS_APPEARANCE: '/settings/appearance',
  SETTINGS_SECURITY: '/settings/security',
  SETTINGS_TEAM: '/settings/team',
  SETTINGS_INTEGRATIONS: '/settings/integrations',

  // Admin
  ADMIN_USERS: '/admin/users',
  ADMIN_ROLES: '/admin/roles',
  ADMIN_TEAMS: '/admin/teams',
  ADMIN_AUDIT: '/admin/audit',
  ADMIN_POLICIES: '/admin/policies',

  // Company
  COMPANY_DASHBOARD: '/company/dashboard',
  COMPANY_MEMBERS: '/company/members',
  COMPANY_USAGE: '/company/usage',

  // Status
  NOT_FOUND: '/404',
  FORBIDDEN: '/403',
  SERVER_ERROR: '/500',
} as const;

export const ROLE_LABELS: Record<string, string> = {
  super_admin: 'Super Admin',
  admin: 'Admin',
  devops: 'DevOps Engineer',
  security: 'Security Engineer',
  finops: 'FinOps Analyst',
  viewer: 'Viewer',
};

export const ROLE_COLORS: Record<string, string> = {
  super_admin: 'text-red-400',
  admin: 'text-orange-400',
  devops: 'text-blue-400',
  security: 'text-yellow-400',
  finops: 'text-green-400',
  viewer: 'text-muted-foreground',
};

export const PLAN_LABELS: Record<string, string> = {
  starter: 'Starter',
  professional: 'Professional',
  enterprise: 'Enterprise',
};

export const PLAN_LIMITS = {
  starter:      { members: 5,   integrations: 3,  apiCalls: 10_000 },
  professional: { members: 25,  integrations: 15, apiCalls: 100_000 },
  enterprise:   { members: 999, integrations: 999, apiCalls: 9_999_999 },
};

// FastAPI backend serves all routes under /api/v1/
// In dev: Vite proxy forwards /api/v1/* → http://localhost:8000/api/v1/*
// In prod: Nginx forwards /api/* → http://backend:8000 (path preserved)
export const API_BASE_URL = import.meta.env.VITE_API_URL ?? '/api/v1';

export const TOKEN_KEY = 'uniops_token';
export const REFRESH_TOKEN_KEY = 'uniops_refresh_token';
export const USER_KEY = 'uniops_user';
export const COMPANY_KEY = 'uniops_company';
