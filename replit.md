# UniOps Control Tower — Workspace

## Overview

pnpm monorepo with a full-stack multi-tenant SaaS — UniOps Control Tower — an enterprise DevOps command plane with authentication, role-based access, integrations, billing, and 5 operational dashboards.

## Stack

- **Monorepo**: pnpm workspaces
- **Node.js**: 24, **TypeScript**: 5.9, **Package manager**: pnpm
- **Frontend** (`artifacts/uniops`): React + Vite + TypeScript + Tailwind v4 + Zustand + React Router v6 + Framer Motion + Recharts + Axios
- **Backend** (`artifacts/server`): Node.js + Express (CommonJS, port 3001)
- **Canvas** (`artifacts/mockup-sandbox`): Vite mockup preview server

## Key Commands

- `pnpm run typecheck` — typecheck all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/uniops run dev` — run frontend dev server (port 5000)
- `node artifacts/server/src/index.js` — run backend API server (port 3001)

## Workflows

- **Backend API**: `node artifacts/server/src/index.js` → port 3001
- **Start application**: `PORT=5000 BASE_PATH=/ pnpm --filter @workspace/uniops run dev` → port 5000

## UniOps Frontend Architecture

### Structure (`artifacts/uniops/src/`)
```
contexts/         AuthContext (real backend auth), CompanyContext, ThemeContext, NotificationContext
hooks/            use-permissions, use-auth (re-export), use-api, use-integrations, etc.
lib/              constants (ROUTES), formatters, validators, permissions, error-handler
services/
  api/            client.ts (Axios+JWT, proxies /api → http://localhost:3001)
store/            Zustand store (sidebarCollapsed, commandPalette, etc.)
components/
  Layout/         Sidebar, Header, Layout, CommandPalette
  auth/           AuthLayout, ProtectedRoute, RoleBasedRoute
pages/
  CommandCenter, DevOpsCenter, SecurityCenter, CostCenter, MLInsights
  auth/           Login, Register, CompanySignup, ForgotPassword, ResetPassword, VerifyEmail, TwoFactorAuth
  settings/       Profile, Account, Security, APIKeys, Integrations (GitHub/GitLab/Kubernetes connect modals), Billing, Appearance, Notifications, Webhooks, TeamSettings
  admin/          Users, AuditLogs, Roles, Teams, SecurityPolicies
  company/        Dashboard, Members, Usage, PendingInvitations
  integrations/   AWSIntegration, GitHubIntegration, KubernetesIntegration, SlackIntegration
  landing/        Home, Pricing, Contact
  status/         Forbidden, ServerError, Maintenance, Offline, Loading, not-found
```

### API Integration
- All HTTP calls go through `src/services/api/client.ts` (Axios with JWT Bearer header)
- Vite dev server proxies `/api/*` → `http://localhost:3001` (configured in `vite.config.ts`)
- Auth: any email + password 6+ chars logs in; backend creates user if not found
- JWT token stored in localStorage; ProtectedRoute redirects unauthenticated users
- No mock API — all data comes from the real Express backend

### Routing
- Public: `/landing`, `/pricing`, `/contact`, `/auth/*`, `/403`, `/500`, `/maintenance`, `/offline`
- Protected (AppLayout): `/command`, `/devops`, `/security`, `/cost`, `/insights`
- Settings: `/settings/profile|account|security|api-keys|integrations|billing|appearance|notifications|webhooks|team`
- Admin (role-gated): `/admin/users|roles|teams|audit|policies`
- Company: `/company/dashboard|members|usage|pending-invitations`
- Integration detail: `/integrations/aws|github|kubernetes|slack`

### Design System
- Dark enterprise theme — `hsl()` custom properties via Tailwind v4 CSS variables
- Utility classes in `index.css`: `page-header`, `page-title`, `page-subtitle`, `card-base`, `badge-medium`, `action-btn`, `action-btn-primary`, `stat-value`, `stat-label`
- Sidebar: collapsible, 3 sections (Dashboards / Administration / Settings), auth-aware user menu
- Header: live notification panel (from NotificationContext), auth-aware profile dropdown with logout

## UniOps Backend Architecture (`artifacts/server/src/`)

**Node.js + Express** — real backend replacing the previous mock API system.

### Stack
- **Framework**: Express (CommonJS, port 3001)
- **Storage**: In-memory store + `/tmp/uniops-store.json` persistence
- **Auth**: Token generation with `crypto.randomBytes`; any email + 6-char password works
- **Integrations**: GitHub REST API (`@octokit/rest`), Kubernetes (`@kubernetes/client-node`), OSV.dev (dependency scanning)

### Modules
| File | Description |
|------|-------------|
| `index.js` | Main Express server — all route handlers (748 lines) |
| `store.js` | In-memory data store + JSON persistence; seeds 7 integration stubs on startup |
| `github.js` | GitHub REST API client — repos, workflow runs, deployments, pipeline rerun |
| `kubernetes.js` | `@kubernetes/client-node` wrapper — pods, deployments, services, logs, exec, scale |
| `scanner.js` | Security scanner — OSV.dev dependency check + secret pattern detection |

### API Routes
| Namespace | Endpoints |
|-----------|-----------|
| `POST /api/auth/login` | Any email + 6+ char password; creates user if not found |
| `GET/PATCH /api/integrations` | List/update integrations; PATCH to connect (token or kubeconfig) |
| `GET /api/kubernetes/pods` | Real pods from connected cluster (empty if disconnected) |
| `GET /api/kubernetes/pods/workloads/*` | Deployments, StatefulSets, DaemonSets |
| `GET /api/kubernetes/pods/network/*` | Services, Ingresses |
| `GET /api/kubernetes/pods/batch/jobs` | Batch jobs |
| `GET /api/kubernetes/pods/config/*` | ConfigMaps, Secrets |
| `GET /api/kubernetes/pods/autoscaling/hpa` | HPA |
| `GET /api/pipelines` | Real GitHub Actions workflow runs |
| `POST /api/pipelines/:id/rerun` | Trigger rerun on GitHub |
| `GET /api/security/repos` | List repos from connected GitHub/GitLab |
| `POST /api/security/scan` | Async scan: OSV deps + secret detection |
| `GET /api/security/scan/:id` | Poll scan progress (queued→cloning→scanning→completed) |
| `GET /api/threats` | Threats derived from completed scans (secrets found) |
| `GET /api/vulnerabilities` | Vulns derived from completed scans (OSV findings) |
| `GET /api/security/score` | Score based on latest scan |
| `GET /api/costs/*`, `/api/finops/*` | Empty (until AWS/GCP connected) |
| `GET /api/ml/*` | Empty (until training data available) |
| `GET /api/compliance/*` | Static empty (no dedicated tool yet) |
| `GET /api/health` | `{ status: "ok", version: "1.0.0" }` |

### Integration Seeding
On startup, `store.js` seeds 7 disconnected integration stubs:
`github`, `gitlab`, `kubernetes`, `aws`, `gcp`, `azure`, `slack`

Connecting an integration:
- **GitHub/GitLab**: `PATCH /api/integrations/:id` with `{ credentials: { token }, status: 'connected' }`
- **Kubernetes**: `PATCH /api/integrations/:id` with `{ config: { kubeconfig, context }, credentials: { kubeconfig }, status: 'connected' }`

### Security Scanner (`scanner.js`)
1. Fetches all repo files via GitHub API (tree + blobs, up to 500 files)
2. Skips binary files, `node_modules`, `.git`, etc.
3. Runs secret pattern detection (14 patterns: AWS keys, GitHub tokens, Stripe, DB URLs, etc.)
4. Queries OSV.dev for known CVEs in `package.json` / `requirements.txt` / `go.mod` dependencies
5. Returns score (0–100), finding counts, secrets[], vulnerabilities[]
