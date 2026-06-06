# UniOps SaaS Infrastructure Guide

## 🏗️ Architectural Overview
The UniOps infrastructure is designed as a **high-availability, secure, and cost-conscious foundation** leveraging AWS and Kubernetes. The architecture follows a "Security-by-Design" approach, ensuring strict isolation between environments and least-privilege access via AWS-native identity.

### 🚀 Core Stack
- **Cloud Provider:** AWS
- **Orchestration:** Amazon EKS (Managed Node Groups)
- **IaC:** Terraform (AWS Provisioning) $\rightarrow$ Kustomize (Application Delivery)
- **Data Layer:** Amazon RDS (PostgreSQL) & Amazon S3 (Production)
- **Security:** AWS WAF, KMS, and K8s Zero-Trust NetworkPolicies
- **Secrets:** AWS Secrets Manager + IRSA (IAM Roles for Service Accounts)

---

## 🛠️ Infrastructure Layers

### 1. Provisioning (Terraform)
The infrastructure is deployed in five distinct phases to minimize blast radius:
- **Phase 01: Networking** $\rightarrow$ Custom VPC, Private/Public Subnets, ALB.
- **Phase 02: Compute (EKS)** $\rightarrow$ Managed Cluster with `t3.medium` nodes (Min 2 for HA).
- **Phase 03: Data** $\rightarrow$ Managed RDS (Postgres) and S3 for object storage.
- **Phase 04: Tools** $\rightarrow$ ALB configuration and Bastion hosts.
- **Phase 05: Security** $\rightarrow$ WAF, KMS encryption, and GuardDuty.

### 2. Application Delivery (K8s/Kustomize)
We use a **Base + Overlay** pattern to ensure parity across environments:
- **`k8s/base`**: The source of truth for all application components (Backend, Celery, Frontend) and global monitoring.
- **`k8s/overlays/local-dev`**: Optimized for velocity. Uses in-cluster PostgreSQL/Redis for rapid iteration.
- **`k8s/overlays/prod`**: Optimized for reliability. Strictly uses managed AWS services (RDS).

### 3. Security & Governance
- **Zero-Trust Networking:** Implemented via `NetworkPolicies`. All traffic is denied by default; only explicitly allowed paths (e.g., `Frontend` $\rightarrow$ `Backend` $\rightarrow$ `DB`) are permitted.
- **AWS-Native Secrets Flow:** We avoid static credentials. Pods use **IRSA** to authenticate with **AWS Secrets Manager**, retrieving secrets directly into the application context at runtime.
- **Resource Governance:** ResourceQuotas and LimitRanges are enforced to prevent "noisy neighbor" effects in the cluster.

---

## 📊 Observability Stack
A lightweight observability suite is deployed via Helm/Kustomize to monitor cluster and application health without excessive cost:
- **Prometheus:** Metrics collection with low-retention/minimal scrape intervals.
- **Grafana:** Centralized health dashboards.
- **Loki:** Lightweight log aggregation for rapid troubleshooting.

---

## 📈 Scalability & Cost
- **Horizontal Scaling:** Backend and Celery workers scale automatically via **Horizontal Pod Autoscaler (HPA)**.
- **Cost Optimization:** 
  - Use of `t3.medium` for a balance of performance and cost.
  - Managed RDS `t3.micro` for initial evaluation.
  - Single VPC to reduce NAT Gateway and networking overhead.

---

## 🚦 Deployment Flow
1. **Terraform Apply:** Provision the AWS foundation (VPC $\rightarrow$ EKS $\rightarrow$ RDS).
2. **IRSA Setup:** Configure the OIDC provider and IAM roles for pod-to-AWS communication.
3. **Kustomize Apply:** Deploy the application stack using the target overlay:
   - `kubectl apply -k k8s/overlays/local-dev` (Local Minikube)
   - `kubectl apply -k k8s/overlays/prod` (Production EKS)
4. **Observability Check:** Verify Prometheus/Grafana dashboards are active.

## 🛠️ Local Development
The project supports a **Zero-to-Running** experience via `k8s/scripts/bootstrap.sh`, which automates Minikube setup, image building, and manifest application for developers.
