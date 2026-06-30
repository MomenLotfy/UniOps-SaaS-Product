---
name: Security Center tab architecture
description: Key decisions for KubernetesSecurity.tsx and Threats.tsx rewrites — backend fields, JSX operator rules, API patterns.
---

## JSX Operator Precedence Rule
Babel parser (vite:react-babel) forbids mixing `??` with `||`/`&&` without explicit parens inside JSX attribute expressions. Always wrap: `(a || b) ?? fallback`, never `a || b ?? fallback`.

**Why:** Babel's parser enforces this for clarity; it is a parse error not a runtime error, so it silently breaks HMR.

**How to apply:** Any time you write `|| ... ??` or `&& ... ??` inside a JSX `{}` expression, add parentheses around the `||`/`&&` side.

## Backend API field mapping (Threats)
- `ThreatResponse`: id, title, description, severity, category, source, status, resource, namespace, ip, mitre_tactic, mitre_technique, raw_data, detected_at, resolved_at, created_at, updated_at
- EPSS/CVSS/KEV/threat_actor are NOT top-level fields — they live in `raw_data` as `epss_score`, `cvss_v3_score`, `kev`, `threat_actor`
- Stats endpoint (`/threats/stats`): total, critical, high, medium, low, open, resolved — extended fields (assets_affected, etc.) may be absent; always guard with `?? 0`

## Backend API field mapping (KubernetesSecurity)
- `/k8s/clusters` returns cluster list; findings_count and risk_score may be null
- `/clusters/{id}/namespaces`, `/clusters/{id}/nodes`, `/clusters/{id}/deployments`, `/clusters/{id}/services`, `/clusters/{id}/ingresses` — all return `{ data: [...] }` or bare arrays; use `raw?.data ?? raw ?? []` pattern
- `/kubernetes/pods/stats` returns `{ running, pending, failed, total, cpu_percent, memory_percent, restart_count }`

## `useApi` unwrap pattern
The hook auto-unwraps `{ success, data, message }` envelope. Paginated responses return `{ data: [...], total, pages }`. Access as `raw?.data ?? raw` for single objects or `raw?.data?.data ?? []` for paginated lists.

## `buildQs` hoisting
`buildQs` defined as a `function` declaration at the bottom of Threats.tsx is safely hoisted and usable above its definition. This pattern is intentional.
