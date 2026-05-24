export type UserRole = 'super_admin' | 'admin' | 'devops' | 'security' | 'finops' | 'viewer';

export type UserStatus = 'active' | 'inactive' | 'pending' | 'suspended';

export interface Permission {
  resource: string;
  actions: ('read' | 'write' | 'delete' | 'admin')[];
}

export interface User {
  id: string;
  email: string;
  firstName: string;
  lastName: string;
  displayName: string;
  avatar?: string;
  role: UserRole;
  status: UserStatus;
  companyId: string;
  teamIds: string[];
  permissions: Permission[];
  lastLogin?: string;
  createdAt: string;
  updatedAt: string;
  twoFactorEnabled: boolean;
  emailVerified: boolean;
}

export interface UserInvitation {
  id: string;
  email: string;
  role: UserRole;
  teamId?: string;
  invitedBy: string;
  expiresAt: string;
  status: 'pending' | 'accepted' | 'expired';
}

export interface UserSession {
  id: string;
  device: string;
  browser: string;
  os: string;
  ip: string;
  location: string;
  current: boolean;
  lastActive: string;
}

export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
  expiresAt: number;
}

export interface LoginCredentials {
  email: string;
  password: string;
  rememberMe?: boolean;
}

export interface RegisterData {
  firstName: string;
  lastName: string;
  email: string;
  password: string;
  confirmPassword: string;
}
