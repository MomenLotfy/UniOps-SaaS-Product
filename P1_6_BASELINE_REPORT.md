# P1.6 — Baseline Freeze Report

**Date:** 2026-09-18 · **Branch:** `arena/01a0b237-uniops-saas-product`

## Identity & cleanliness

| Check | Expected | Observed | Status |
|---|---|---|---|
| Branch | `arena/01a0b237-uniops-saas-product` | `arena/01a0b237-uniops-saas-product` | ✅ |
| Local HEAD | `8096c21` (p1.5: report) | `8096c21e77ea84c0908b75fcc16886b3ec413c0d` | ✅ |
| Remote HEAD (ls-remote) | == local | `8096c21e77ea84c0908b75fcc16886b3ec413c0d` | ✅ in sync |
| Working tree | clean | clean (`git status --porcelain` empty) | ✅ |
| Latest P1.5 commits | 6 commits `2968736…8096c21` | present on top of `f2503d5` | ✅ |
| Environment | backend venv / pnpm / redis | all present (no rebuild needed) | ✅ |

## Baseline results

| Suite | Command | Result | Duration |
|---|---|---|---|
| Backend tests | `PYTHONPATH=. .venv/bin/python -m pytest tests/ -q` | **264 passed, 0 failed** (21 warnings) | 191.7 s |
| Frontend build | `cd artifacts/uniops && pnpm build` | **✓ built, exit 0** | 8.83 s |

## P1.5 residual state carried in

- Real K8s cluster, AWS credentials, GitLab egress, ArgoCD/observability/scanner infra, live Slack/Stripe keys: **UNVERIFIED** (infrastructure/credentials unavailable in sandbox).
- GitHub: client boundary + error contract verified real; user-scoped happy path still blocked by installation-token scope.
- Webhook endpoints now fail-closed: require `*_WEBHOOK_SECRET` / `SLACK_SIGNING_SECRET` configured or they 503.

**Gate:** baseline GREEN → audit proceeds.
