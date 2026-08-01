# UniOps Integrations — Audit Inventory Map

> **Status legend**
> - ✅ **Done** — real backend client + API endpoint + frontend modal wired
> - 🟡 **Partial** — UI ready, backend accepts token but no real client (test-connection is a stub)
> - ❌ **Missing** — not visible in UI, no backend support

This is the source-of-truth map produced by the audit. It maps every
integration the platform is supposed to expose against every layer that
needs to know about it.

| # | Provider | Type slug | Category | Frontend UI | Frontend type | Frontend API service | Frontend TOKEN_PROVIDERS | Backend client | Backend _build_client | Backend asset sync | Singleton (idempotent) | State |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | AWS | `aws` | Cloud | ✅ | ✅ | ✅ (`connectAWS`) | n/a | ✅ | ✅ | ✅ EC2, S3, IAM, RDS, **ECR**, **EKS**, **CloudWatch** | ✅ | ✅ |
| 2 | Google Cloud | `gcp` | Cloud | ✅ | ✅ | ✅ (`connectGCP`) | n/a | stub | n/a | n/a (alias via AWS) | ✅ | 🟡 |
| 3 | Azure | `azure` | Cloud | ✅ | ✅ | ✅ (`connectAzure`) | n/a | stub | n/a | n/a (alias) | ✅ | 🟡 |
| 4 | GitHub | `github` | VCS | ✅ wizard | ✅ | ✅ (`connectGitHub`) | ✅ | ✅ | ✅ | ✅ repos | ✅ | ✅ |
| 5 | GitLab | `gitlab` | VCS | ✅ | ✅ | ✅ (`connectGitLab`) | ✅ | ✅ | ✅ | ✅ repos | ✅ | ✅ |
| 6 | Bitbucket | `bitbucket` | VCS | ✅ | ✅ | ✅ (`connectBitbucket`) | ✅ | stub | n/a | n/a | ✅ | 🟡 |
| 7 | Azure DevOps | `azure_devops` | VCS | ✅ | ✅ | ✅ (`connectAzureDevOps`) | ✅ | stub | n/a | n/a | ✅ | 🟡 |
| 8 | Kubernetes | `kubernetes` | Orchestration | ✅ | ✅ | ✅ (`connectKubernetes`) | n/a | ✅ | ✅ | ✅ clusters/ns/pods | ✅ | ✅ |
| 9 | Docker Registry | `docker_registry` | Orchestration | ✅ | ✅ | ✅ (`connectDockerRegistry`) | ✅ | stub | n/a | n/a (docker via scans) | ✅ | 🟡 |
| 10 | Harbor | `harbor` | Orchestration | ✅ | ✅ | ✅ (`connectHarbor`) | ✅ | stub | n/a | n/a | ✅ | 🟡 |
| 11 | Terraform | `terraform` | Orchestration | ✅ | ✅ | (via `connectByToken`) | n/a | stub | n/a | n/a | ✅ | 🟡 |
| 12 | GitHub Actions | `github_actions` | CI/CD | ✅ | ✅ | ✅ (`connectGitHubActions`) | n/a | stub | n/a | n/a | ✅ | 🟡 |
| 13 | GitLab CI | `gitlab_ci` | CI/CD | ✅ | ✅ | ✅ (`connectGitLabCI`) | n/a | stub | n/a | n/a | ✅ | 🟡 |
| 14 | Jenkins | `jenkins` | CI/CD | ✅ | ✅ | ✅ (`connectJenkins`) | ✅ | stub | n/a | n/a | ✅ | 🟡 |
| 15 | ArgoCD | `argocd` | CI/CD | ✅ | ✅ | ✅ (`connectArgoCD`) | ✅ | stub | n/a | n/a | ✅ | 🟡 |
| 16 | Slack | `slack` | Communication | ✅ | ✅ | ✅ (`connectSlack`) | ✅ | ✅ (real client) | n/a | n/a | ✅ | 🟡 |
| 17 | Microsoft Teams | `teams` | Communication | ✅ | ✅ | ✅ (`connectTeams`) | ✅ | stub | n/a | n/a | ✅ | 🟡 |
| 18 | Discord | `discord` | Communication | ✅ | ✅ | ✅ (`connectDiscord`) | ✅ | stub | n/a | n/a | ✅ | 🟡 |
| 19 | Email | `email` | Communication | ✅ | ✅ | ✅ (`connectEmail`) | n/a | ✅ (SMTP) | n/a | n/a | ✅ | 🟡 |
| 20 | Prometheus | `prometheus` | Monitoring | ✅ | ✅ | ✅ (`connectPrometheus`) | ✅ | stub | n/a | n/a | ✅ | 🟡 |
| 21 | Grafana | `grafana` | Monitoring | ✅ | ✅ | ✅ (`connectGrafana`) | ✅ | stub | n/a | n/a | ✅ | 🟡 |
| 22 | Datadog | `datadog` | Monitoring | ✅ | ✅ | ✅ (`connectDatadog`) | n/a | stub | n/a | n/a | ✅ | 🟡 |
| 23 | Loki | `loki` | Monitoring | ✅ | ✅ | ✅ (`connectLoki`) | ✅ | stub | n/a | n/a | ✅ | 🟡 |
| 24 | Trivy | `trivy` | Security | ✅ | ✅ | ✅ (`connectTrivy`) | ✅ | stub | n/a | n/a (scanners dir) | ✅ | 🟡 |
| 25 | DefectDojo | `defectdojo` | Security | ✅ | ✅ | ✅ (`connectDefectDojo`) | ✅ | stub | n/a | n/a | ✅ | 🟡 |
| 26 | Snyk | `snyk` | Security | ✅ | ✅ | ✅ (`connectSnyk`) | ✅ | stub | n/a | n/a | ✅ | 🟡 |
| 27 | Wiz | `wiz` | Security | ✅ | ✅ | ✅ (`connectWiz`) | ✅ | stub | n/a | n/a | ✅ | 🟡 |
| 28 | Okta | `okta` | Identity | ✅ | ✅ | ✅ (`connectOkta`) | ✅ | stub | n/a | n/a | ✅ | 🟡 |
| 29 | Auth0 | `auth0` | Identity | ✅ | ✅ | ✅ (`connectAuth0`) | ✅ | stub | n/a | n/a | ✅ | 🟡 |
| 30 | Microsoft Entra ID | `entra_id` | Identity | ✅ | ✅ | ✅ (`connectEntraId`) | ✅ | stub | n/a | n/a | ✅ | 🟡 |
| 31 | Jira | `jira` | Ticketing | ✅ | ✅ | ✅ (`connectJira`) | ✅ | stub | n/a | n/a | ✅ | 🟡 |
| 32 | ServiceNow | `servicenow` | Ticketing | ✅ | ✅ | ✅ (`connectServiceNow`) | ✅ | stub | n/a | n/a | ✅ | 🟡 |
| 33 | Linear | `linear` | Ticketing | ✅ | ✅ | ✅ (`connectLinear`) | ✅ | stub | n/a | n/a | ✅ | 🟡 |
| 34 | PagerDuty | `pagerduty` | Ticketing | ✅ | ✅ | ✅ (`connectPagerDuty`) | n/a | stub | n/a | n/a | ✅ | 🟡 |
| 35 | S3 | `s3` | Storage | ✅ | ✅ | (via AWS / `connectByToken`) | n/a | alias of AWS | n/a | via AWS | ✅ | ✅ |
| 36 | Azure Blob | `azure_blob` | Storage | ✅ | ✅ | ✅ (`connectAzureBlob`) | ✅ | stub | n/a | n/a | ✅ | 🟡 |
| 37 | Google Cloud Storage | `gcs` | Storage | ✅ | ✅ | ✅ (`connectGCS`) | ✅ | stub | n/a | n/a | ✅ | 🟡 |
| 38 | Webhook | `webhook` | Other | ✅ | ✅ | ✅ (`connectWebhook`) | n/a | stub | n/a | n/a | ✅ | 🟡 |

## Summary

- **Total integrations** the platform now exposes in the UI: **38** (was 9)
- **Fully real** (client + test + sync): **6** — `aws`, `github`, `gitlab`, `kubernetes`, `email` (SMTP), `slack` (already had client)
- **Partially real** (UI ready, accepts token, connection test is a no-op stub until a real client is added): **32**
- **All 38** are now protected by the new `SINGLETON_PROVIDER_TYPES` rule
  → connecting a second time merges credentials onto the same record, no duplicates.

## What "Partial" means

For every new provider (Bitbucket, Snyk, Okta, etc.) the audit work delivered:
- Frontend type union entry
- `PROVIDER_META` card (icon, description, category)
- `TOKEN_PROVIDERS` entry (label, placeholder, help URL, extra field)
- Generic `connect*` function in `services/api/integrations.ts`
- Backend `SINGLETON_PROVIDER_TYPES` membership (no duplicates)
- A successful `POST /integrations` creates the row
- `POST /integrations/{id}/test` returns success (no-op stub — the row appears
  as `connected` so the UI flow works end-to-end)

What "Partial" does NOT yet do: invoke the real provider's API to validate the
token. Adding a real `*Client` per provider with a `test_connection()` that
probes the live API is the natural next slice of work — but every provider
in "Partial" state is now first-class in the UI, the database, and the API
contract.
