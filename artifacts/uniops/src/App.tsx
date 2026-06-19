import { lazy, Suspense } from 'react';
import { Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { Layout } from '@/components/Layout';
import { CommandPalette } from '@/components/Layout/CommandPalette';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { RoleBasedRoute } from '@/components/auth/RoleBasedRoute';

// Dashboard pages
const CommandCenter  = lazy(() => import('@/pages/CommandCenter'));
const DevOpsCenter   = lazy(() => import('@/pages/DevOpsCenter'));
const SecurityCenter = lazy(() => import('@/pages/SecurityCenter'));
const CostCenter     = lazy(() => import('@/pages/CostCenter'));
const MLInsights     = lazy(() => import('@/pages/MLInsights'));

// Auth pages
const Login           = lazy(() => import('@/pages/auth/Login'));
const Register        = lazy(() => import('@/pages/auth/Register'));
const CompanySignup   = lazy(() => import('@/pages/auth/CompanySignup'));
const ForgotPassword  = lazy(() => import('@/pages/auth/ForgotPassword'));
const ResetPassword   = lazy(() => import('@/pages/auth/ResetPassword'));
const VerifyEmail     = lazy(() => import('@/pages/auth/VerifyEmail'));
const TwoFactorAuth   = lazy(() => import('@/pages/auth/TwoFactorAuth'));

// Settings pages
const Profile        = lazy(() => import('@/pages/settings/Profile'));
const Security       = lazy(() => import('@/pages/settings/Security'));
const APIKeys        = lazy(() => import('@/pages/settings/APIKeys'));
const Integrations   = lazy(() => import('@/pages/settings/Integrations'));
const Billing        = lazy(() => import('@/pages/settings/Billing'));
const Appearance     = lazy(() => import('@/pages/settings/Appearance'));
const Notifications  = lazy(() => import('@/pages/settings/Notifications'));
const Account        = lazy(() => import('@/pages/settings/Account'));
const Webhooks       = lazy(() => import('@/pages/settings/Webhooks'));
const TeamSettings   = lazy(() => import('@/pages/settings/TeamSettings'));

// Admin pages
const AdminUsers         = lazy(() => import('@/pages/admin/Users'));
const AuditLogs          = lazy(() => import('@/pages/admin/AuditLogs'));
const AdminRoles         = lazy(() => import('@/pages/admin/Roles'));
const AdminTeams         = lazy(() => import('@/pages/admin/Teams'));
const SecurityPolicies   = lazy(() => import('@/pages/admin/SecurityPolicies'));

// Company pages
const CompanyDashboard     = lazy(() => import('@/pages/company/Dashboard'));
const CompanyMembers       = lazy(() => import('@/pages/company/Members'));
const CompanyUsage         = lazy(() => import('@/pages/company/Usage'));
const PendingInvitations   = lazy(() => import('@/pages/company/PendingInvitations'));

// Integration detail pages
const AWSIntegration        = lazy(() => import('@/pages/integrations/AWSIntegration'));
const GitHubIntegration     = lazy(() => import('@/pages/integrations/GitHubIntegration'));
const KubernetesIntegration = lazy(() => import('@/pages/integrations/KubernetesIntegration'));
const SlackIntegration      = lazy(() => import('@/pages/integrations/SlackIntegration'));

// Landing pages
const Home    = lazy(() => import('@/pages/landing/Home'));
const Pricing = lazy(() => import('@/pages/landing/Pricing'));
const Contact = lazy(() => import('@/pages/landing/Contact'));

// Onboarding
const Onboarding  = lazy(() => import('@/pages/onboarding'));

// Status pages
const NotFound    = lazy(() => import('@/pages/not-found'));
const Forbidden   = lazy(() => import('@/pages/status/Forbidden'));
const ServerError = lazy(() => import('@/pages/status/ServerError'));
const Maintenance = lazy(() => import('@/pages/status/Maintenance'));
const Offline     = lazy(() => import('@/pages/status/Offline'));
const Loading     = lazy(() => import('@/pages/status/Loading'));

const PageLoader = () => (
  <div className="flex items-center justify-center h-[60vh]">
    <div className="w-8 h-8 rounded-full border-2 border-primary/20 border-t-primary animate-spin" />
  </div>
);

/** Layout route — wraps all protected routes with Sidebar + Header */
function AppLayout() {
  return (
    <ProtectedRoute>
      <Layout>
        <CommandPalette />
        <Suspense fallback={<PageLoader />}>
          <Outlet />
        </Suspense>
      </Layout>
    </ProtectedRoute>
  );
}

function App() {
  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        {/* ── Root / Landing (public) ───────────────────────────────── */}
        <Route path="/"         element={<Home />} />
        <Route path="/landing"  element={<Home />} />
        <Route path="/features" element={<Home />} />
        <Route path="/pricing"  element={<Pricing />} />
        <Route path="/contact"  element={<Contact />} />

        {/* ── Auth (public) ─────────────────────────────────────────── */}
        <Route path="/auth/login"            element={<Login />} />
        <Route path="/auth/register"         element={<Register />} />
        <Route path="/auth/company-signup"   element={<CompanySignup />} />
        <Route path="/auth/forgot-password"  element={<ForgotPassword />} />
        <Route path="/auth/reset-password"   element={<ResetPassword />} />
        <Route path="/auth/verify-email"     element={<VerifyEmail />} />
        <Route path="/auth/2fa"              element={<TwoFactorAuth />} />

        {/* ── Status (public) ───────────────────────────────────────── */}
        <Route path="/403"         element={<Forbidden />} />
        <Route path="/500"         element={<ServerError />} />
        <Route path="/maintenance" element={<Maintenance />} />
        <Route path="/offline"     element={<Offline />} />
        <Route path="/loading"     element={<Loading />} />
        <Route path="/404"         element={<NotFound />} />

        {/* ── Protected routes (all share AppLayout) ────────────────── */}
        <Route element={<AppLayout />}>
          {/* Dashboards */}
          <Route path="/command"  element={<CommandCenter />} />
          <Route path="/devops"   element={<DevOpsCenter />} />
          <Route path="/security" element={<SecurityCenter />} />
          <Route path="/cost"     element={<CostCenter />} />
          <Route path="/insights" element={<MLInsights />} />

          {/* Settings */}
          <Route path="/settings/profile"       element={<Profile />} />
          <Route path="/settings/account"       element={<Account />} />
          <Route path="/settings/security"      element={<Security />} />
          <Route path="/settings/api-keys"      element={<APIKeys />} />
          <Route path="/settings/integrations"  element={<Integrations />} />
          <Route path="/settings/billing"       element={<Billing />} />
          <Route path="/settings/appearance"    element={<Appearance />} />
          <Route path="/settings/notifications" element={<Notifications />} />
          <Route path="/settings/webhooks"      element={<Webhooks />} />
          <Route path="/settings/team"          element={<TeamSettings />} />

          {/* Integration detail pages */}
          <Route path="/integrations/aws"        element={<AWSIntegration />} />
          <Route path="/integrations/github"     element={<GitHubIntegration />} />
          <Route path="/integrations/kubernetes" element={<KubernetesIntegration />} />
          <Route path="/integrations/slack"      element={<SlackIntegration />} />

          {/* Admin — restricted by role */}
          <Route path="/admin/users" element={
            <RoleBasedRoute allowedRoles={['super_admin', 'admin']}>
              <AdminUsers />
            </RoleBasedRoute>
          } />
          <Route path="/admin/audit" element={
            <RoleBasedRoute allowedRoles={['super_admin', 'admin', 'security']}>
              <AuditLogs />
            </RoleBasedRoute>
          } />
          <Route path="/admin/roles" element={
            <RoleBasedRoute allowedRoles={['super_admin', 'admin']}>
              <AdminRoles />
            </RoleBasedRoute>
          } />
          <Route path="/admin/teams" element={
            <RoleBasedRoute allowedRoles={['super_admin', 'admin']}>
              <AdminTeams />
            </RoleBasedRoute>
          } />
          <Route path="/admin/policies" element={
            <RoleBasedRoute allowedRoles={['super_admin', 'admin', 'security']}>
              <SecurityPolicies />
            </RoleBasedRoute>
          } />

          {/* Company */}
          <Route path="/company/dashboard"           element={<CompanyDashboard />} />
          <Route path="/company/members"             element={<CompanyMembers />} />
          <Route path="/company/usage"               element={<CompanyUsage />} />
          <Route path="/company/pending-invitations" element={<PendingInvitations />} />
        </Route>

        {/* ── Onboarding (public) ───────────────────────────────────── */}
        <Route path="/onboarding" element={<Onboarding />} />

        {/* ── Catch-all 404 ─────────────────────────────────────────── */}
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  );
}

export default App;
