export type PlanTier = 'starter' | 'professional' | 'enterprise';
export type BillingCycle = 'monthly' | 'annual';
export type CompanyStatus = 'active' | 'suspended' | 'trial';

export interface Company {
  id: string;
  name: string;
  slug: string;
  logo?: string;
  domain: string;
  domainVerified: boolean;
  status: CompanyStatus;
  plan: PlanTier;
  billingCycle: BillingCycle;
  memberCount: number;
  maxMembers: number;
  createdAt: string;
  ownerId: string;
  address?: CompanyAddress;
  settings: CompanySettings;
}

export interface CompanyAddress {
  line1: string;
  line2?: string;
  city: string;
  state: string;
  country: string;
  postalCode: string;
}

export interface CompanySettings {
  enforceSSO: boolean;
  enforce2FA: boolean;
  allowedDomains: string[];
  sessionTimeout: number;
  ipWhitelist: string[];
}

export interface Subscription {
  id: string;
  plan: PlanTier;
  status: 'active' | 'cancelled' | 'past_due' | 'trialing';
  billingCycle: BillingCycle;
  currentPeriodStart: string;
  currentPeriodEnd: string;
  cancelAtPeriodEnd: boolean;
  trialEndsAt?: string;
  amount: number;
  currency: string;
}

export interface Invoice {
  id: string;
  number: string;
  amount: number;
  currency: string;
  status: 'paid' | 'open' | 'void' | 'uncollectible';
  period: string;
  paidAt?: string;
  downloadUrl: string;
}

export interface UsageStats {
  users: { used: number; limit: number };
  integrations: { used: number; limit: number };
  apiCalls: { used: number; limit: number };
  dataRetention: { days: number; limit: number };
}
