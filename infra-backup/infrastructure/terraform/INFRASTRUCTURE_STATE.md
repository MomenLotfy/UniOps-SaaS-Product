# Infrastructure State Reference
Last Updated: 2026-06-02

## Terraform Backend
- Bucket: `uniops-terraform-state-8j3k9l` (us-east-2)
- Table: `uniops-terraform-locks` (us-east-2)

## Target Architecture
- Compute: Amazon EKS (Managed Nodes, t3.medium x2)
- Networking: Single VPC, Public/Private subnets, ALB.
- Data: RDS PostgreSQL (db.t3.micro), S3.
- Security: IRSA + AWS Secrets Manager, WAF, Zero-Trust NetPol.
- Observability: Prometheus + Grafana + Loki (Lightweight).
- Dev Workflow: bootstrap.sh (Minikube) preserved.
